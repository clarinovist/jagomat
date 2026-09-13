"""Regresi HTTP principal tunggal dan revokasi berbasis revisi_auth."""
from __future__ import annotations

import http.cookies
import json
from pathlib import Path
import re
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import sessions  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402

SANDI_ADMIN = "sandi-admin-sintetis-123"
SANDI_ORANG_TUA = "sandi-orang-tua-sintetis-123"
SANDI_BARU = "sandi-orang-tua-baru-456"


class _TanpaIkut(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _tanpa_ikut():
    return urllib.request.build_opener(_TanpaIkut)


def _masuk(server, nama, sandi):
    req = urllib.request.Request(
        server.alamat + "/masuk",
        data=urllib.parse.urlencode({"nama": nama, "sandi": sandi}).encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        _tanpa_ikut().open(req, timeout=10)
    except urllib.error.HTTPError as galat:
        kode = galat.code
        header = galat.headers
        isi = galat.read().decode("utf-8", "replace")
    else:  # pragma: no cover
        pytest.fail("login tidak redirect")
    token = None
    nilai = header.get("Set-Cookie", "")
    if nilai:
        cookie = http.cookies.SimpleCookie(nilai)
        if "osn_sesi" in cookie:
            token = cookie["osn_sesi"].value
    return kode, token, isi


@pytest.fixture()
def server(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    with server.buka() as kon:
        siswa = database.tambah_siswa(
            kon, "Anak Sintetis", "P3", pemilik="Ortu-Sintetis"
        )
        database.buat_sesi(kon, siswa, seed=91)
    auth.tambah_akun(
        "Ortu-Sintetis", SANDI_ORANG_TUA, "guru", path=auth.BERKAS_SANDI
    )
    auth.tambah_akun(
        "Admin-Sintetis", SANDI_ADMIN, "admin", path=auth.BERKAS_SANDI
    )
    yield server
    server.berhenti()


def test_login_dan_daftar_menerbitkan_metadata_sesi_lengkap(server):
    _, token_login, _ = _masuk(server, "ortu-sintetis", SANDI_ORANG_TUA)
    assert token_login
    entri_login = sessions.muat()[token_login]
    akun_login = auth.cari_akun("Ortu-Sintetis")
    assert (
        entri_login["pengguna"], entri_login["peran"],
        entri_login["id_akun"], entri_login["revisi_auth"],
    ) == (
        akun_login["pengguna"], akun_login["peran"],
        akun_login["id_akun"], akun_login["revisi_auth"],
    )

    halaman_daftar = server.minta("/daftar")[1]
    token_form = re.search(r'name="token_form" value="([^"]+)"', halaman_daftar).group(1)
    req = urllib.request.Request(
        server.alamat + "/daftar",
        data=urllib.parse.urlencode({
            "nama": "Daftar-Sintetis", "sandi": "sandi-daftar-sintetis",
            "setuju": "1", "token_form": token_form,
        }).encode(),
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        _tanpa_ikut().open(req, timeout=10)
    except urllib.error.HTTPError as galat:
        assert galat.code == 303
        cookie = http.cookies.SimpleCookie(galat.headers["Set-Cookie"])
        token_daftar = cookie["osn_sesi"].value
    else:  # pragma: no cover
        pytest.fail("pendaftaran tidak redirect")
    entri_daftar = sessions.muat()[token_daftar]
    akun_daftar = auth.cari_akun("Daftar-Sintetis")
    assert entri_daftar["id_akun"] == akun_daftar["id_akun"]
    assert entri_daftar["revisi_auth"] == akun_daftar["revisi_auth"] == 1


def test_cookie_guru_ditolak_setelah_reset_delete_dan_recreate_http(server):
    kode, token, _ = _masuk(server, "ortu-sintetis", SANDI_ORANG_TUA)
    assert kode == 303 and token
    assert "Anak Sintetis" in server.minta("/guru", cookie=token)[1]

    assert auth.setel_sandi_guru("Ortu-Sintetis", SANDI_BARU)
    kode_reset, isi_reset, _ = server.minta("/guru", cookie=token)
    assert kode_reset == 401
    assert "Anak Sintetis" not in isi_reset

    _, token_baru, _ = _masuk(server, "Ortu-Sintetis", SANDI_BARU)
    assert token_baru
    assert auth.hapus_akun_guru("Ortu-Sintetis")
    kode_hapus, isi_hapus, _ = server.minta("/guru", cookie=token_baru)
    assert kode_hapus == 401
    assert "Anak Sintetis" not in isi_hapus

    auth.tambah_akun("Ortu-Sintetis", "sandi-recreate-789", "guru")
    kode_recreate, isi_recreate, _ = server.minta("/guru", cookie=token_baru)
    assert kode_recreate == 401
    assert "Anak Sintetis" not in isi_recreate


def test_cookie_admin_ditolak_setelah_ganti_sandi_sendiri(server):
    _, token, _ = _masuk(server, "Admin-Sintetis", SANDI_ADMIN)
    assert token
    sandi_baru = "sandi-admin-baru-sintetis-456"
    kode, _, _ = server.minta(
        "/akun",
        auth=("Admin-Sintetis", SANDI_ADMIN),
        data={
            "aksi": "sandi", "lama": SANDI_ADMIN,
            "baru": sandi_baru, "ulang": sandi_baru,
        },
    )
    assert kode == 200
    assert auth.periksa_peran("Admin-Sintetis", sandi_baru, "admin")
    assert server.minta("/admin", cookie=token)[0] == 404
    assert server.minta("/admin/ai", cookie=token)[0] == 404


def test_cookie_admin_stale_role_delete_legacy_ditolak_admin_dan_ai(server):
    _, token, _ = _masuk(server, "Admin-Sintetis", SANDI_ADMIN)
    assert token
    assert server.minta("/admin", cookie=token)[0] == 200
    assert server.minta("/admin/ai", cookie=token)[0] == 200

    akun = auth.muat_akun()
    for item in akun:
        if item["pengguna"] == "Admin-Sintetis":
            item["peran"] = "guru"
            item["revisi_auth"] += 1
    with __import__("json_storage").transaksi_json(auth.BERKAS_SANDI):
        auth._tulis_akun_atomik({"akun": akun}, auth.BERKAS_SANDI)
    assert server.minta("/admin", cookie=token)[0] == 404
    assert server.minta("/admin/ai", cookie=token)[0] == 404
    kode_post, _, _ = server.minta(
        "/admin", cookie=token,
        data={
            "aksi": "guru_baru", "pengguna": "tidak-boleh-terbuat",
            "sandi": "sandi-target-sintetis-123",
        },
    )
    assert kode_post == 404
    assert auth.cari_akun("tidak-boleh-terbuat") is None

    akun = [item for item in auth.muat_akun() if item["pengguna"] != "Admin-Sintetis"]
    with __import__("json_storage").transaksi_json(auth.BERKAS_SANDI):
        auth._tulis_akun_atomik({"akun": akun}, auth.BERKAS_SANDI)
    assert server.minta("/admin", cookie=token)[0] == 404

    sessions.BERKAS_SESI.write_text(json.dumps({
        "legacy": {
            "pengguna": "Admin-Sintetis", "peran": "admin",
            "kedaluarsa": 9_999_999_999,
        }
    }), encoding="utf-8")
    assert server.minta("/admin", cookie="legacy")[0] == 404
    assert server.minta("/admin/ai", cookie="legacy")[0] == 404


def test_basic_casefold_memakai_username_kanonik_dan_kepemilikan(server):
    kode, isi, _ = server.minta(
        "/guru", auth=("ortu-sintetis", SANDI_ORANG_TUA)
    )
    assert kode == 200
    assert "Anak Sintetis" in isi


def test_cookie_guru_stale_ditolak_di_pendamping(server, monkeypatch):
    monkeypatch.setenv("PENDAMPING_AKTIF", "1")
    _, token, _ = _masuk(server, "Ortu-Sintetis", SANDI_ORANG_TUA)
    assert token
    assert auth.setel_sandi_guru("Ortu-Sintetis", SANDI_BARU)
    kode, isi, _ = server.minta("/pendamping", cookie=token)
    assert kode == 401
    assert "Perlu masuk lagi" in isi


def test_cookie_murid_stale_reset_ditolak_tanpa_efek(server):
    with server.buka() as kon:
        siswa = kon.execute(
            "SELECT id FROM siswa WHERE nama='Anak Sintetis'"
        ).fetchone()["id"]
    auth.tambah_akun(
        "Murid-Sintetis", "sandi-murid-sintetis", "murid",
        siswa_id=siswa,
    )
    _, token, _ = _masuk(server, "Murid-Sintetis", "sandi-murid-sintetis")
    assert token and server.minta("/murid", cookie=token)[0] == 200
    assert auth.setel_sandi_murid("Murid-Sintetis", "sandi-murid-baru")
    kode, isi, _ = server.minta("/murid", cookie=token)
    assert kode == 200  # urllib mengikuti 303 ke /masuk
    assert "Daftar latihan" not in isi


def test_get_principal_tidak_memigrasi_atau_menulis_auth(server):
    sebelum = auth.BERKAS_SANDI.read_bytes()
    _, token, _ = _masuk(server, "Ortu-Sintetis", SANDI_ORANG_TUA)
    assert token
    setelah_login = auth.BERKAS_SANDI.read_bytes()
    assert setelah_login == sebelum
    assert server.minta("/guru", cookie=token)[0] == 200
    assert auth.BERKAS_SANDI.read_bytes() == setelah_login


def test_race_login_reset_tidak_menerbitkan_cookie_sah_dari_sandi_lama(
    server, monkeypatch
):
    mulai_reset = threading.Event()
    lanjut_login = threading.Event()
    asli = sessions.buat_dari_principal

    def disela(principal, *args, **kwargs):
        mulai_reset.set()
        assert lanjut_login.wait(5)
        return asli(principal, *args, **kwargs)

    monkeypatch.setattr(sessions, "buat_dari_principal", disela)
    hasil = {}

    def login_lama():
        hasil["login"] = _masuk(server, "Ortu-Sintetis", SANDI_ORANG_TUA)

    ulir = threading.Thread(target=login_lama)
    ulir.start()
    assert mulai_reset.wait(5)
    assert auth.setel_sandi_guru("Ortu-Sintetis", SANDI_BARU)
    lanjut_login.set()
    ulir.join(10)

    kode, token, _ = hasil["login"]
    assert kode == 409
    assert token is None
    assert _masuk(server, "Ortu-Sintetis", SANDI_BARU)[0] == 303
