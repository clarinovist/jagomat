"""HTTP end-to-end pusat kendali admin Gelombang C."""
from __future__ import annotations

import html.parser
import http.client
import http.cookies
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_store  # noqa: E402
import auth  # noqa: E402
import database  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402

SANDI_ADMIN = "sandi-admin-http-c-123"
SANDI_ORANG_TUA = "sandi-orang-tua-http-c-123"


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _minta(
    server, jalur, *, data=None, raw=None, cookie=None, auth_basic=None,
    headers=None,
):
    tubuh = raw if raw is not None else (
        None if data is None else urllib.parse.urlencode(data).encode()
    )
    alamat = urllib.parse.urlsplit(server.alamat)
    tajuk = dict(headers or {})
    if tubuh is not None:
        tajuk.setdefault("Content-Type", "application/x-www-form-urlencoded")
    if cookie:
        tajuk["Cookie"] = "osn_sesi=" + cookie
    if auth_basic:
        import base64
        nilai = base64.b64encode(
            (auth_basic[0] + ":" + auth_basic[1]).encode()
        ).decode()
        tajuk["Authorization"] = "Basic " + nilai
    koneksi = http.client.HTTPConnection(alamat.hostname, alamat.port, timeout=10)
    try:
        koneksi.request(
            "POST" if tubuh is not None else "GET", jalur,
            body=tubuh, headers=tajuk,
        )
        respons = koneksi.getresponse()
        return (
            respons.status, respons.read().decode("utf-8", "replace"),
            dict(respons.getheaders()),
        )
    finally:
        koneksi.close()


def _unggah(server, cookie, data, csv):
    batas = '----jagomat-sintetis-test'
    raw = b''
    for nama, nilai in data.items():
        raw += ('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n' % (batas, nama, nilai)).encode()
    raw += ('--%s\r\nContent-Disposition: form-data; name="csv"; filename="sintetis.csv"\r\nContent-Type: text/csv\r\n\r\n' % batas).encode()
    raw += csv if isinstance(csv, bytes) else csv.encode()
    raw += ('\r\n--%s--\r\n' % batas).encode()
    return _minta(server, '/admin/bulk/impor', cookie=cookie, raw=raw,
        headers={'Content-Type': 'multipart/form-data; boundary=' + batas, 'Origin': server.alamat})


def _masuk(server, nama, sandi):
    return _minta(server, "/masuk", data={"nama": nama, "sandi": sandi})


def _login(server, nama, sandi):
    kode, _, header = _minta(
        server, "/masuk", data={"nama": nama, "sandi": sandi}
    )
    assert kode == 303
    cookie = http.cookies.SimpleCookie(header["Set-Cookie"])
    return cookie["osn_sesi"].value


def _hidden(isi, nama):
    cocok = re.search(r'name="%s" value="([^"]+)"' % re.escape(nama), isi)
    assert cocok, (nama, isi[:500])
    return cocok.group(1)


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    auth.tambah_akun("Admin-C", SANDI_ADMIN, "admin")
    auth.tambah_akun("Ortu-C", SANDI_ORANG_TUA, "guru")
    with s.buka() as kon:
        siswa = database.tambah_siswa(kon, "Anak C", "P3", pemilik="Ortu-C")
    s.siswa_c = siswa
    yield s
    s.berhenti()


def test_detail_dan_tinjauan_target_hilang_memiliki_404_identik(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    keluarga = _minta(
        server, "/admin?section=keluarga&id=akun_" + "f" * 32,
        cookie=token,
    )
    siswa = _minta(server, "/admin?section=siswa&id=999999", cookie=token)
    target = _minta(
        server,
        "/admin/tinjau?aksi=account_password_reset&id=akun_" + "f" * 32,
        cookie=token,
    )
    assert keluarga[0] == siswa[0] == target[0] == 404
    assert keluarga[1] == siswa[1] == target[1]


def test_get_admin_tidak_membuat_store_yang_hilang(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    admin_store.BAWAAN.unlink()
    kode, isi, _ = _minta(server, "/admin?section=ringkasan", cookie=token)
    assert kode == 200 and "belum tersedia" in isi
    assert not admin_store.BAWAAN.exists()
    kode, _, _ = _minta(server, "/admin?section=pendaftaran", cookie=token)
    assert kode == 503 and not admin_store.BAWAAN.exists()


def test_admin_sections_privat_dan_nonadmin_404_identik(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    for section in ("ringkasan", "keluarga", "siswa", "pendaftaran", "riwayat"):
        kode, isi, header = _minta(
            server, "/admin?section=" + section, cookie=token
        )
        assert kode == 200 and "Panel Pengelola" in isi
        assert header["Cache-Control"] == "no-store"
        assert header["Referrer-Policy"] == "no-referrer"
        assert header["X-Frame-Options"] == "DENY"
        assert "noindex" in header["X-Robots-Tag"]
        assert "frame-ancestors 'none'" in header["Content-Security-Policy"]
    anonim = _minta(server, "/admin")[0:2]
    guru = _minta(server, "/admin", auth_basic=("guru", SANDI_GURU))[0:2]
    murid = _minta(server, "/admin", auth_basic=("feby", SANDI_MURID))[0:2]
    assert anonim == guru == murid
    assert anonim[0] == 404 and "Anak C" not in anonim[1]


def test_search_post_tidak_menaruh_nama_di_url_dan_tanpa_write(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _, awal, _ = _minta(server, "/admin?section=keluarga", cookie=token)
    csrf = _hidden(awal, "csrf")
    akun_sebelum = auth.BERKAS_SANDI.read_bytes()
    admin_sebelum = admin_store.BAWAAN.read_bytes()

    kode, isi, _ = _minta(
        server, "/admin", cookie=token,
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
        data={
            "mode": "cari", "section": "keluarga", "csrf": csrf,
            "cari": "Ortu-C", "status": "semua", "memiliki_anak": "semua",
        },
    )
    assert kode == 200 and "Ortu-C" in isi
    assert "?" not in urllib.parse.urlsplit(server.alamat + "/admin").path
    assert auth.BERKAS_SANDI.read_bytes() == akun_sebelum
    assert admin_store.BAWAAN.read_bytes() == admin_sebelum


def test_admin_post_menolak_cross_site_duplikat_asing_tanpa_efek(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _, halaman, _ = _minta(server, "/admin?section=keluarga", cookie=token)
    csrf = _hidden(halaman, "csrf")
    sebelum_auth = auth.BERKAS_SANDI.read_bytes()
    sebelum_admin = admin_store.BAWAAN.read_bytes()
    dasar = urllib.parse.urlencode({
        "mode": "cari", "section": "keluarga", "csrf": csrf,
        "cari": "Ortu-C", "status": "semua", "memiliki_anak": "semua",
    }).encode()
    kasus = (
        (dasar, {"Sec-Fetch-Site": "cross-site", "Origin": "http://127.0.0.1.invalid"}, 403),
        (dasar + b"&cari=duplikat", {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}, 400),
        (dasar + b"&asing=1", {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}, 400),
    )
    for raw, header, status in kasus:
        kode, _, _ = _minta(
            server, "/admin", raw=raw, cookie=token, headers=header
        )
        assert kode == status
        assert auth.BERKAS_SANDI.read_bytes() == sebelum_auth
        assert admin_store.BAWAAN.read_bytes() == sebelum_admin


def test_basic_admin_boleh_baca_tapi_tidak_mendapat_form_tindakan(server):
    kode, isi, _ = _minta(
        server, "/admin?section=ringkasan", auth_basic=("Admin-C", SANDI_ADMIN)
    )
    assert kode == 200 and "Panel Pengelola" in isi
    kode, isi, _ = _minta(
        server, "/admin/tinjau?aksi=account_teacher_create",
        auth_basic=("Admin-C", SANDI_ADMIN),
    )
    assert kode == 403
    assert 'name="sandi_baru"' not in isi


def test_token_review_tamper_stale_dan_target_berubah_tanpa_efek(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    target = auth.cari_akun("Ortu-C")
    _, review, _ = _minta(
        server,
        "/admin/tinjau?aksi=account_password_reset&id=" + target["id_akun"],
        cookie=token,
    )
    data = {
        "aksi": "account_password_reset", "csrf": _hidden(review, "csrf"),
        "tinjauan": _hidden(review, "tinjauan") + "x",
        "sandi_baru": "sandi-tidak-dipakai-c", "reauth": SANDI_ADMIN,
    }
    sebelum = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _minta(
        server, "/admin/akun", cookie=token, data=data,
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 403 and auth.BERKAS_SANDI.read_bytes() == sebelum

    _, review_stale, _ = _minta(
        server,
        "/admin/tinjau?aksi=account_password_reset&id=" + target["id_akun"],
        cookie=token,
    )
    assert auth.setel_sandi_guru("Ortu-C", "sandi-diubah-di-tab-lain")
    kode, _, _ = _minta(
        server, "/admin/akun", cookie=token,
        data={
            "aksi": "account_password_reset",
            "csrf": _hidden(review_stale, "csrf"),
            "tinjauan": _hidden(review_stale, "tinjauan"),
            "sandi_baru": "sandi-tidak-menimpa", "reauth": SANDI_ADMIN,
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 409
    assert auth.periksa_peran("Ortu-C", "sandi-diubah-di-tab-lain", "guru")


def test_create_guru_review_final_reauth_csrf_dan_replay_metadata(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, review, _ = _minta(
        server, "/admin/tinjau?aksi=account_teacher_create", cookie=token
    )
    assert kode == 200
    csrf, tinjauan = _hidden(review, "csrf"), _hidden(review, "tinjauan")
    assert "name=\"alias\"" in review and SANDI_ORANG_TUA not in review
    data = {
        "aksi": "account_teacher_create", "csrf": csrf,
        "tinjauan": tinjauan, "alias": "Ortu-Baru-C",
        "sandi_baru": "sandi-orang-tua-baru-c", "reauth": SANDI_ADMIN,
    }
    kode, hasil, header = _minta(
        server, "/admin/akun", cookie=token, data=data,
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 200 and "Simpan akses sekarang" in hasil
    assert "sandi-orang-tua-baru-c" in hasil
    assert header["Cache-Control"] == "no-store"
    akun = auth.cari_akun("Ortu-Baru-C")
    assert akun is not None and akun["peran"] == "guru"

    kode, isi_replay, header_replay = _minta(
        server, "/admin/akun", cookie=token,
        data={**data, "sandi_baru": "sandi-berbeda-pada-replay"},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 303 and "sandi-berbeda-pada-replay" not in isi_replay
    assert header_replay["Location"].startswith("/admin?section=")


def test_reset_guru_menolak_csrf_origin_dan_reauth_tanpa_efek(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    target = auth.cari_akun("Ortu-C")
    _, review, _ = _minta(
        server,
        "/admin/tinjau?aksi=account_password_reset&id=" + target["id_akun"],
        cookie=token,
    )
    csrf, tinjauan = _hidden(review, "csrf"), _hidden(review, "tinjauan")
    dasar = {
        "aksi": "account_password_reset", "csrf": csrf,
        "tinjauan": tinjauan, "sandi_baru": "sandi-reset-http-c-123",
        "reauth": SANDI_ADMIN,
    }
    sebelum = auth.BERKAS_SANDI.read_bytes()
    for ubah, tajuk, status in (
        ({"csrf": "palsu"}, {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}, 403),
        ({"reauth": "salah"}, {"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"}, 403),
        ({}, {"Origin": "https://asing.invalid", "Sec-fetch-site": "cross-site"}, 403),
    ):
        kode, _, _ = _minta(
            server, "/admin/akun", cookie=token,
            data={**dasar, **ubah}, headers=tajuk,
        )
        assert kode == status
        assert auth.BERKAS_SANDI.read_bytes() == sebelum


def test_target_admin_tidak_dapat_ditinjau_atau_dimutasi(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    admin = auth.cari_akun("Admin-C")
    kode, isi, _ = _minta(
        server,
        "/admin/tinjau?aksi=account_password_reset&id=" + admin["id_akun"],
        cookie=token,
    )
    assert kode == 404 and 'name="sandi_baru"' not in isi


def test_ubah_kelas_dan_create_login_murid_actual_domain(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _, review, _ = _minta(
        server, "/admin/tinjau?aksi=student_level_update&id=%d" % server.siswa_c,
        cookie=token,
    )
    kode, _, header = _minta(
        server, "/admin/siswa", cookie=token,
        data={
            "aksi": "student_level_update", "csrf": _hidden(review, "csrf"),
            "tinjauan": _hidden(review, "tinjauan"), "tingkat_baru": "P4",
            "reauth": SANDI_ADMIN,
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 303 and header["Location"].endswith(str(server.siswa_c))
    with server.buka() as kon:
        assert kon.execute(
            "SELECT tingkat FROM siswa WHERE id=?", (server.siswa_c,)
        ).fetchone()[0] == "P4"

    _, review_login, _ = _minta(
        server, "/admin/tinjau?aksi=student_login_create&id=%d" % server.siswa_c,
        cookie=token,
    )
    kode, hasil, _ = _minta(
        server, "/admin/akun", cookie=token,
        data={
            "aksi": "student_login_create",
            "csrf": _hidden(review_login, "csrf"),
            "tinjauan": _hidden(review_login, "tinjauan"),
            "alias": "Anak-C-Login", "sandi_baru": "sandi-anak-c",
            "reauth": SANDI_ADMIN,
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 200 and "Simpan akses sekarang" in hasil
    assert auth.cari_akun("Anak-C-Login")["siswa_id"] == server.siswa_c


def test_bulk_csv_invalid_ditolak_sebelum_batch_atau_akun(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _, halaman, _ = _minta(server, "/admin?section=keluarga", cookie=token)
    csrf = re.findall(r'name="csrf" value="([^"]+)"', halaman)[-1]
    tinjauan = re.findall(r'name="tinjauan" value="([^"]+)"', halaman)[-1]
    sebelum_auth = auth.BERKAS_SANDI.read_bytes()
    kode, _, _ = _unggah(server, token, {
        "aksi": "bulk_teacher_create", "csrf": csrf,
        "tinjauan": tinjauan, "reauth": SANDI_ADMIN,
    }, "pengguna,email\nBulk-X,x@example.test\n")
    assert kode == 400 and auth.BERKAS_SANDI.read_bytes() == sebelum_auth
    transient = Path(__import__("os").environ["ADMIN_TRANSIENT_DB"])
    import sqlite3
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute("SELECT COUNT(*) FROM draft_bulk").fetchone()[0] == 0


def test_bulk_create_dua_akun_tampil_sekali_dan_replay_tanpa_credential(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _, halaman, _ = _minta(server, "/admin?section=keluarga", cookie=token)
    # Form bulk berada setelah form pencarian; ambil pasangan token terakhir.
    csrf = re.findall(r'name="csrf" value="([^"]+)"', halaman)[-1]
    tinjauan = re.findall(r'name="tinjauan" value="([^"]+)"', halaman)[-1]
    kode, preview, _ = _unggah(server, token, {
        "aksi": "bulk_teacher_create", "csrf": csrf,
        "tinjauan": tinjauan, "reauth": SANDI_ADMIN,
    }, "pengguna\nBulk-C-A\nBulk-C-B\n")
    assert kode == 200 and "Tinjau batch" in preview
    proses = {
        "csrf": _hidden(preview, "csrf"),
        "tinjauan": _hidden(preview, "tinjauan"),
        "batch_id": _hidden(preview, "batch_id"),
        "reauth": SANDI_ADMIN, "konfirmasi": "1",
    }
    kode, hasil, _ = _minta(
        server, "/admin/bulk/proses", cookie=token, data=proses,
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 200 and hasil.count('aria-label="Sandi baru"') == 2
    assert auth.cari_akun("Bulk-C-A") is not None
    assert auth.cari_akun("Bulk-C-B") is not None

    kode, replay, _ = _minta(
        server, "/admin/bulk/proses", cookie=token, data=proses,
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 200 and 'aria-label="Sandi baru"' not in replay


def test_reset_revoke_delete_guru_actual_dan_replay_aman(server):
    token_admin = _login(server, "Admin-C", SANDI_ADMIN)
    target = auth.cari_akun("Ortu-C")
    token_target = _login(server, "Ortu-C", SANDI_ORANG_TUA)

    def tinjau(aksi):
        _, isi, _ = _minta(
            server, "/admin/tinjau?aksi=%s&id=%s" % (aksi, target["id_akun"]),
            cookie=token_admin,
        )
        return _hidden(isi, "csrf"), _hidden(isi, "tinjauan")

    csrf, review = tinjau("account_password_reset")
    data = {
        "aksi": "account_password_reset", "csrf": csrf, "tinjauan": review,
        "sandi_baru": "sandi-reset-c-456", "reauth": SANDI_ADMIN,
    }
    kode, hasil, _ = _minta(
        server, "/admin/akun", cookie=token_admin, data=data,
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 200 and "sandi-reset-c-456" in hasil
    revisi = auth.cari_akun("Ortu-C")["revisi_auth"]
    kode, replay, _ = _minta(
        server, "/admin/akun", cookie=token_admin,
        data={**data, "sandi_baru": "sandi-replay-tidak-dipakai"},
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 303 and "sandi-replay-tidak-dipakai" not in replay
    assert auth.cari_akun("Ortu-C")["revisi_auth"] == revisi
    assert sessions.ambil_principal(token_target) is None

    target = auth.cari_akun("Ortu-C")
    csrf, review = tinjau("account_session_revoke")
    kode, _, _ = _minta(
        server, "/admin/akun", cookie=token_admin,
        data={
            "aksi": "account_session_revoke", "csrf": csrf,
            "tinjauan": review, "reauth": SANDI_ADMIN, "konfirmasi": "1",
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 303
    target = auth.cari_akun("Ortu-C")
    csrf, review = tinjau("account_login_delete")
    kode, _, _ = _minta(
        server, "/admin/akun", cookie=token_admin,
        data={
            "aksi": "account_login_delete", "csrf": csrf,
            "tinjauan": review, "reauth": SANDI_ADMIN, "konfirmasi": "1",
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 303 and auth.cari_akun("Ortu-C") is None
    with server.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM siswa WHERE pemilik='Ortu-C'").fetchone()[0] == 1


def test_audit_ui_tidak_memuat_credential_atau_alias(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    _, review, _ = _minta(
        server, "/admin/tinjau?aksi=account_teacher_create", cookie=token
    )
    rahasia = "sandi-tidak-boleh-di-audit"
    _minta(
        server, "/admin/akun", cookie=token,
        data={
            "aksi": "account_teacher_create", "csrf": _hidden(review, "csrf"),
            "tinjauan": _hidden(review, "tinjauan"), "alias": "Audit-C",
            "sandi_baru": rahasia, "reauth": SANDI_ADMIN,
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    kode, isi, _ = _minta(server, "/admin?section=riwayat", cookie=token)
    assert kode == 200 and "Buat orang tua" in isi
    assert rahasia not in isi and "Audit-C" not in isi


def test_pendaftaran_open_closed_missing_dan_login_existing(server):
    kode, halaman, _ = _minta(server, "/daftar")
    assert kode == 200 and 'name="token_form"' in halaman
    token_form = _hidden(halaman, "token_form")
    kode, _, header = _minta(
        server, "/daftar",
        data={
            "nama": "Publik-C", "sandi": "sandi-publik-c",
            "setuju": "1", "token_form": token_form,
        },
    )
    assert kode == 303 and "Set-Cookie" in header

    token_admin = _login(server, "Admin-C", SANDI_ADMIN)
    _, panel, _ = _minta(server, "/admin?section=pendaftaran", cookie=token_admin)
    kode, _, _ = _minta(
        server, "/admin/pendaftaran", cookie=token_admin,
        data={
            "aksi": "registration_config_update", "csrf": _hidden(panel, "csrf"),
            "tinjauan": _hidden(panel, "tinjauan"),
            "pesan_kode": "closed_standard", "reauth": SANDI_ADMIN,
        },
        headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
    )
    assert kode == 303
    kode, tutup, _ = _minta(server, "/daftar")
    assert kode == 200 and 'name="sandi"' not in tutup
    kode, _, _ = _minta(
        server, "/daftar",
        data={
            "nama": "Ditolak-C", "sandi": "sandi-ditolak-c",
            "setuju": "1", "token_form": token_form,
        },
    )
    assert kode == 403 and auth.cari_akun("Ditolak-C") is None
    assert _masuk(server, "Publik-C", "sandi-publik-c")[0] == 303

    admin_store.BAWAAN.unlink()
    assert _minta(server, "/daftar")[0] == 503
    assert _masuk(server, "Publik-C", "sandi-publik-c")[0] == 303


def test_pendaftaran_menolak_token_palsu_dan_field_ganda_tanpa_akun(server):
    kasus = (
        urllib.parse.urlencode({
            "nama": "Palsu-C", "sandi": "sandi-palsu-c", "setuju": "1",
            "token_form": "palsu",
        }).encode(),
        (
            "nama=Ganda-C&nama=Ganda-Lain&sandi=sandi-ganda-c&setuju=1&"
            "token_form=palsu"
        ).encode(),
    )
    for raw in kasus:
        kode, _, _ = _minta(
            server, "/daftar", raw=raw,
            headers={"Origin": server.alamat, "Sec-Fetch-Site": "same-origin"},
        )
        assert kode in (400, 403)
        assert auth.cari_akun("Palsu-C") is None
        assert auth.cari_akun("Ganda-C") is None


def test_akun_admin_lama_tidak_menyediakan_bypass_lintas_keluarga(server):
    token = _login(server, "Admin-C", SANDI_ADMIN)
    kode, _, header = _minta(server, "/akun?section=siswa", cookie=token)
    assert kode == 303 and header["Location"] == "/admin"
    kode, isi, _ = _minta(server, "/akun", cookie=token)
    assert kode == 200
    assert "Akun saya" in isi
    assert "Tambah anak" not in isi
