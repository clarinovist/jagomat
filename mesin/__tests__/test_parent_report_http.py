"""Rute HTTP laporan guru -> orang tua: kepemilikan, token, header, allowlist.

Server nyata di port acak dengan DB/sandi sintetis (pola ``test_share_link``).
Yang diuji di sini adalah lapisan routing dan respons; kontrak domain ada di
``test_parent_report_domain.py``.
"""
from __future__ import annotations

import hashlib
import html
import http.client
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import database  # noqa: E402
import domain_clock  # noqa: E402
import parent_report  # noqa: E402
import parent_report_store  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji, _basic  # noqa: E402

SANDI_GURU_LAIN = "sandi-guru-lain-123"
SANDI_ADMIN = "sandi-pengelola-9999"
TOKEN_RE = re.compile(r'id="tautan-laporan"[^>]*value="([A-Za-z0-9_-]{43})"')


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    hari = domain_clock.hari_wib()
    with s.buka() as kon:
        anak = database.tambah_siswa(kon, "Bima Laporan", "P3", pemilik="guru")
        asing = database.tambah_siswa(kon, "Rara Laporan", "P4", pemilik="lain")
        sesi = database.buat_sesi(
            kon, anak, seed=7, jumlah_soal=1, tanggal=hari.isoformat(),
        )
        database.tandai_selesai(kon, sesi)
        soal = database.isi_sesi(kon, sesi)[0]["sesi_soal_id"]
        database.konfirmasi_hasil(kon, sesi, guru="guru", dilewati={soal})
    auth.tambah_akun("guru-lain", SANDI_GURU_LAIN, "guru", path=auth.BERKAS_SANDI)
    auth.tambah_akun("pengelola-uji", SANDI_ADMIN, "admin", path=auth.BERKAS_SANDI)
    yield s, {"anak": anak, "asing": asing, "sesi": sesi}
    s.berhenti()


def _minta(
    server, jalur, *, data=None, auth_=("guru", SANDI_GURU), headers=None,
):
    """Permintaan tanpa mengikuti redirect: status 303 harus terlihat apa adanya."""
    import urllib.parse

    alamat = urlparse(server.alamat)
    tubuh = None if data is None else urllib.parse.urlencode(data).encode()
    tajuk = dict(headers or {})
    if tubuh is not None:
        tajuk.setdefault("Content-Type", "application/x-www-form-urlencoded")
    if auth_ is not None:
        tajuk["Authorization"] = _basic(*auth_)
    koneksi = http.client.HTTPConnection(
        alamat.hostname, alamat.port, timeout=10)
    try:
        koneksi.request(
            "POST" if tubuh is not None else "GET", jalur,
            body=tubuh, headers=tajuk,
        )
        respons = koneksi.getresponse()
        return (respons.status, respons.read().decode("utf-8", "replace"),
                dict(respons.getheaders()))
    finally:
        koneksi.close()


def _guru(server, jalur, data=None, pengguna="guru", sandi=SANDI_GURU):
    return _minta(server, jalur, data=data, auth_=(pengguna, sandi))


def _buat_draf(server, anak, data=None):
    kode, _, header = _guru(server, f"/anak/{anak}/laporan-ortu",
                            data=data or {"periode": "30"})
    assert kode == 303, kode
    cocok = re.match(rf"/anak/{anak}/laporan-ortu/([0-9]+)", header["Location"])
    assert cocok, header["Location"]
    return int(cocok.group(1))


def _terbitkan(server, anak, laporan):
    kode, isi, header = _guru(
        server, f"/anak/{anak}/laporan-ortu/{laporan}/terbitkan", data={},
    )
    assert kode == 200, (kode, isi[:300])
    cocok = TOKEN_RE.search(isi)
    assert cocok, isi[:2000]
    return cocok.group(1), isi, header


def _teks_tampil(isi: str) -> str:
    tanpa_gaya = re.sub(r"<style\b.*?</style>", " ", isi, flags=re.S)
    tanpa_tajuk = re.sub(r"<[^>]+>", " ", tanpa_gaya)
    return html.unescape(tanpa_tajuk)


def _iterdump(server):
    with server.buka() as kon:
        return tuple(kon.iterdump())


def test_entry_point_tunggal_di_tab_perkembangan(server):
    s, ids = server
    kode, isi, _ = _guru(s, f"/anak/{ids['anak']}?section=perkembangan")
    assert kode == 200
    tautan = f'href="/anak/{ids["anak"]}/laporan-ortu"'
    assert isi.count(tautan) == 1
    assert "Laporan untuk orang tua" in isi
    kode, riwayat, _ = _guru(s, f"/anak/{ids['anak']}?section=riwayat")
    assert kode == 200 and tautan not in riwayat


def test_draf_pratinjau_lalu_terbit_dan_token_hanya_sekali(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    kode, pratinjau, header = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}")
    assert kode == 200
    assert "DRAF LAPORAN" in pratinjau
    assert "Pola Bilangan" in pratinjau
    assert "Yang dilatih" in pratinjau
    assert "Belum ada tautan." in pratinjau
    assert 'id="tautan-laporan"' not in pratinjau
    assert "<script" not in pratinjau and "fonts.googleapis" not in pratinjau
    assert header["Cache-Control"] == "no-store"
    assert header["Referrer-Policy"] == "no-referrer"
    assert header["X-Robots-Tag"] == "noindex, nofollow"

    token, terbit, _ = _terbitkan(s, ids["anak"], laporan)
    assert "LAPORAN TERBIT" in terbit
    assert "tampil sekali" in terbit
    assert "<script" not in terbit and "fonts.googleapis" not in terbit
    assert "Pilih seluruh isi kotak" in terbit

    kode, ulang, _ = _guru(s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}")
    assert kode == 200
    assert 'id="tautan-laporan"' not in ulang
    assert token not in ulang


def test_halaman_orang_tua_isi_allowlist_dan_header_lengkap(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    _guru(s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/catatan",
          data={"catatan": "Bima makin tenang membaca soal."})
    token, _, _ = _terbitkan(s, ids["anak"], laporan)

    kode, isi, header = s.minta(f"/laporan-ortu/{token}")
    assert kode == 200
    assert header["Cache-Control"] == "no-store"
    assert header["Referrer-Policy"] == "no-referrer"
    assert header["X-Robots-Tag"] == "noindex, nofollow"
    assert header["X-Frame-Options"] == "DENY"
    assert header["X-Content-Type-Options"] == "nosniff"
    csp = header["Content-Security-Policy"]
    assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
    assert "form-action 'none'" in csp
    assert "Set-Cookie" not in header
    assert "<script" not in isi
    assert "https://" not in isi
    assert "fonts.googleapis" not in isi
    assert "<form" not in isi and "<a " not in isi

    judul = re.search(r"<title>(.*?)</title>", isi, re.S).group(1)
    assert "Bima Laporan" not in judul
    assert "og:" not in isi and "twitter:" not in isi

    teks = _teks_tampil(isi)
    assert "Bima Laporan" in teks
    assert "Pola Bilangan" in teks
    assert "Yang dilatih" in teks
    assert "Tahap belajar sekarang" in teks
    assert "Langkah berikutnya" in teks
    assert "Bima makin tenang membaca soal." in teks
    for terlarang in ("malrule", "miskonsepsi", "diagnosis", "kunci",
                      "Variasi", "benar /", "P3", "P4", "P5", "P6",
                      "%", "K1", "#1", "/sesi/", "Sesi #", "kelas",
                      "persentase"):
        assert terlarang not in teks, terlarang


def test_query_tidak_dipantulkan_dan_body_identik(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    kode_a, biasa, _ = s.minta(f"/laporan-ortu/{token}")
    kode_b, disusup, _ = s.minta(
        f"/laporan-ortu/{token}?nama=%3Cscript%3Ealert(1)%3C/script%3E")
    assert kode_a == kode_b == 200
    assert biasa == disusup


@pytest.mark.parametrize("jalur", [
    "/laporan-ortu", "/laporan-ortu/", "/laporan-ortu/pendek",
    "/laporan-ortu/" + "x" * 42, "/laporan-ortu/" + "x" * 44,
])
def test_jalur_token_tidak_kanonis_404(server, jalur):
    s, _ = server
    kode, isi, header = s.minta(jalur)
    assert kode == 404
    assert "Laporan tidak dapat dibuka" in isi
    assert header["Cache-Control"] == "no-store"
    assert header["Cache-Control"] == "no-store"
    assert "default-src 'none'" in header["Content-Security-Policy"]


def test_404_identik_untuk_semua_keadaan_tidak_sah(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    _, acuan, header_acuan = s.minta("/laporan-ortu/" + "z" * 43)

    def sama(jalur):
        kode, isi, header = s.minta(jalur)
        assert kode == 404, (jalur, kode)
        assert isi == acuan, jalur
        assert header["Cache-Control"] == header_acuan["Cache-Control"]
        assert header["Content-Security-Policy"] == \
            header_acuan["Content-Security-Policy"]

    sama("/laporan-ortu/" + "y" * 43)
    with s.buka() as kon:
        kon.execute("UPDATE tautan_laporan SET kedaluarsa = 0 WHERE siswa_id = ?",
                    (ids["anak"],))
    sama(f"/laporan-ortu/{token}")

    with s.buka() as kon:
        kon.execute(
            "UPDATE tautan_laporan SET kedaluarsa = ?, dicabut = NULL "
            "WHERE siswa_id = ?",
            (parent_report_store.sekarang_detik() + 10_000, ids["anak"]),
        )
    kode, _, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/tautan/cabut", data={})
    assert kode == 303
    sama(f"/laporan-ortu/{token}")


def test_tautan_ke_draf_atau_anak_dihapus_404_identik(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    _, acuan, _ = s.minta("/laporan-ortu/" + "z" * 43)

    # Tautan sah yang ditunjuk ke laporan draf: tetap 404 (diterbitkan IS NULL).
    draf = _buat_draf(s, ids["anak"])
    with s.buka() as kon:
        kon.execute("UPDATE tautan_laporan SET laporan_id = ? WHERE siswa_id = ?",
                    (draf, ids["anak"]))
    kode, isi, _ = s.minta(f"/laporan-ortu/{token}")
    assert kode == 404 and isi == acuan

    # Anak dengan laporan tetapi tanpa sesi: cascade menghapus laporan + tautan.
    with s.buka() as kon:
        lain = database.tambah_siswa(kon, "Anak Tanpa Riwayat", "P3", pemilik="guru")
    laporan_lain = _buat_draf(s, lain)
    # Anak tanpa sesi tidak punya topik terkonfirmasi; rute menolak terbit.
    # Untuk menguji cascade penghapusan, terbitkan langsung di domain.
    with s.buka() as kon:
        token_lain = parent_report_store.terbitkan(
            kon, laporan_lain, lain,
            parent_report.kejadian_terakhir(kon, lain), "guru",
        )
    with s.buka() as kon:
        kon.execute("DELETE FROM siswa WHERE id = ?", (lain,))
    kode, isi, _ = s.minta(f"/laporan-ortu/{token_lain}")
    assert kode == 404 and isi == acuan


def test_rotasi_dan_cabut_lewat_http(server):
    s, ids = server
    pertama = _buat_draf(s, ids["anak"])
    token1, _, _ = _terbitkan(s, ids["anak"], pertama)
    kedua = _buat_draf(s, ids["anak"],
                       data={"periode": "custom",
                             "mulai": domain_clock.hari_wib().replace(day=1).isoformat(),
                             "sampai": domain_clock.hari_wib().isoformat()})
    token2, _, _ = _terbitkan(s, ids["anak"], kedua)
    assert token1 != token2
    assert s.minta(f"/laporan-ortu/{token1}")[0] == 404
    assert s.minta(f"/laporan-ortu/{token2}")[0] == 200

    kode, _, header = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{kedua}/tautan/cabut", data={})
    assert kode == 303 and header["Location"].endswith("pesan=tautan-dicabut")
    assert s.minta(f"/laporan-ortu/{token2}")[0] == 404
    kode, _, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{kedua}/tautan/cabut", data={})
    assert kode == 303  # idempoten


def test_ganti_tautan_menampilkan_token_baru_dan_mematikan_yang_lama(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    token1, _, _ = _terbitkan(s, ids["anak"], laporan)
    kode, isi, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/tautan", data={})
    assert kode == 200
    token2 = TOKEN_RE.search(isi).group(1)
    assert token2 != token1
    assert s.minta(f"/laporan-ortu/{token1}")[0] == 404
    assert s.minta(f"/laporan-ortu/{token2}")[0] == 200


def test_terbit_pada_draf_dengan_catatan_dan_tanpa_topik_ditolak(server):
    s, _ = server
    with s.buka() as kon:
        kosong = database.tambah_siswa(kon, "Anak Belum Ditinjau", "P3", pemilik="guru")
        sesi = database.buat_sesi(
            kon, kosong, seed=19, jumlah_soal=1,
            tanggal=domain_clock.hari_wib().isoformat(),
        )
        database.tandai_selesai(kon, sesi)  # selesai, belum dikonfirmasi guru
    laporan = _buat_draf(s, kosong)
    kode, isi, _ = _guru(
        s, f"/anak/{kosong}/laporan-ortu/{laporan}/terbitkan", data={})
    assert kode == 409
    assert "Belum ada latihan yang selesai dan dikonfirmasi" in isi
    with s.buka() as kon:
        assert kon.execute(
            "SELECT diterbitkan FROM laporan_ortu WHERE id = ?", (laporan,)
        ).fetchone()["diterbitkan"] is None
        assert kon.execute("SELECT COUNT(*) FROM tautan_laporan").fetchone()[0] == 0


def test_tautan_tidak_bisa_dibuat_untuk_draf(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    kode, _, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/tautan", data={})
    assert kode == 409
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM tautan_laporan").fetchone()[0] == 0


def test_hapus_draf_lewat_http_dan_terbit_tidak_bisa_dihapus(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    kode, _, header = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/hapus", data={})
    assert kode == 303 and header["Location"].endswith("pesan=draf-dihapus")
    with s.buka() as kon:
        assert parent_report_store.ambil(kon, laporan) is None

    terbit = _buat_draf(s, ids["anak"])
    _terbitkan(s, ids["anak"], terbit)
    kode, isi, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{terbit}/hapus", data={})
    assert kode == 409
    assert "tidak dapat dihapus" in isi


def test_laporan_terbit_tidak_bisa_diubah_lewat_catatan(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    _terbitkan(s, ids["anak"], laporan)
    kode, isi, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/catatan",
        data={"catatan": "Ubah setelah terbit"})
    assert kode == 409
    with s.buka() as kon:
        assert parent_report_store.ambil(kon, laporan)["catatan"] == ""


def test_guru_asing_404_identik_tanpa_efek_samping(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    sebelum = _iterdump(s)
    for jalur, data in (
        (f"/anak/{ids['asing']}/laporan-ortu", {"periode": "30"}),
        (f"/anak/{ids['asing']}/laporan-ortu/{laporan}/catatan", {"catatan": "x"}),
        (f"/anak/{ids['asing']}/laporan-ortu/{laporan}/terbitkan", {}),
        (f"/anak/{ids['asing']}/laporan-ortu/{laporan}/tautan/cabut", {}),
    ):
        kode, isi, _ = _guru(s, jalur, data=data)
        assert kode == 404, jalur
        assert "Halaman tidak ada" in isi
    kode_a, asing, _ = _guru(s, f"/anak/{ids['asing']}/laporan-ortu")
    kode_b, tidak_ada, _ = _guru(s, "/anak/999999/laporan-ortu")
    assert kode_a == kode_b == 404 and asing == tidak_ada
    assert _iterdump(s) == sebelum


def test_murid_dan_anonim_tidak_bisa_menulis_atau_membaca(server):
    s, ids = server
    sebelum = _iterdump(s)
    for auth_ in (("feby", SANDI_MURID), None):
        kode, _, _ = _minta(
            s, f"/anak/{ids['anak']}/laporan-ortu", data={"periode": "30"},
            auth_=auth_,
        )
        assert kode == 401
        kode, _, _ = _minta(s, f"/anak/{ids['anak']}/laporan-ortu", auth_=auth_)
        assert kode == 401
    assert _iterdump(s) == sebelum


def test_admin_hanya_membaca_tidak_menulis(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    sebelum = _iterdump(s)
    for jalur, data in (
        (f"/anak/{ids['anak']}/laporan-ortu", {"periode": "30"}),
        (f"/anak/{ids['anak']}/laporan-ortu/{laporan}/catatan", {"catatan": "x"}),
        (f"/anak/{ids['anak']}/laporan-ortu/{laporan}/terbitkan", {}),
        (f"/anak/{ids['anak']}/laporan-ortu/{laporan}/tautan", {}),
        (f"/anak/{ids['anak']}/laporan-ortu/{laporan}/tautan/cabut", {}),
        (f"/anak/{ids['anak']}/laporan-ortu/{laporan}/hapus", {}),
    ):
        kode, _, _ = _guru(s, jalur, data=data,
                           pengguna="pengelola-uji", sandi=SANDI_ADMIN)
        assert kode == 404, jalur
    assert _iterdump(s) == sebelum
    # Admin boleh membaca pratinjau dan halaman baca-saja tetap hidup.
    kode, isi, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}",
        pengguna="pengelola-uji", sandi=SANDI_ADMIN)
    assert kode == 200 and "PRATINJAU" in isi
    assert "Admin hanya dapat melihat" in _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu",
        pengguna="pengelola-uji", sandi=SANDI_ADMIN)[1]
    assert s.minta(f"/laporan-ortu/{token}")[0] == 200


def test_penerbitan_dan_pencabutan_tidak_menulis_bukti_maupun_sesi(server):
    s, ids = server

    def tabel_bukti(kon):
        return {
            nama: tuple(kon.execute(f'SELECT * FROM "{nama}" ORDER BY rowid'))
            for nama in ("konfirmasi_hasil", "snapshot_outcome",
                         "kejadian_belajar", "bukti_fokus", "sesi")
        }

    with s.buka() as kon:
        sebelum = tabel_bukti(kon)
    laporan = _buat_draf(s, ids["anak"])
    _guru(s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/catatan",
          data={"catatan": "Catatan"})
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    _guru(s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/tautan", data={})
    _guru(s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/tautan/cabut", data={})
    with s.buka() as kon:
        assert tabel_bukti(kon) == sebelum
    assert s.minta(f"/laporan-ortu/{token}")[0] == 404


def test_watermark_bukti_baru_tampil_di_halaman_guru_tanpa_mengubah_laporan(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    _, halaman_awal, _ = s.minta(f"/laporan-ortu/{token}")
    with s.buka() as kon:
        sesi = database.buat_sesi(
            kon, ids["anak"], seed=23, jumlah_soal=1,
            tanggal=domain_clock.hari_wib().isoformat(),
        )
        database.tandai_selesai(kon, sesi)
        soal = database.isi_sesi(kon, sesi)[0]["sesi_soal_id"]
        database.konfirmasi_hasil(kon, sesi, guru="guru", dilewati={soal})
    kode, isi, _ = _guru(s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}")
    assert kode == 200
    assert "Bukti berubah setelah laporan ini diterbitkan" in isi
    assert "1 kejadian baru" in isi
    _, halaman_akhir, _ = s.minta(f"/laporan-ortu/{token}")
    assert halaman_akhir == halaman_awal


def test_catatan_di_escape_dan_kepanjangan_ditolak(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    kode, _, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/catatan",
        data={"catatan": "<script>alert(1)</script>"})
    assert kode == 303
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    isi = s.minta(f"/laporan-ortu/{token}")[1]
    assert "<script" not in isi
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in isi

    kode, isi, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{laporan}/catatan",
        data={"catatan": "x" * 2001})
    # Validasi bentuk catatan berjalan sebelum aturan terbit: 400, tanpa tulis.
    assert kode == 400
    assert parent_report_store.catatan_aman("x" * 2000)
    draf = _buat_draf(s, ids["anak"])
    kode, isi, _ = _guru(
        s, f"/anak/{ids['anak']}/laporan-ortu/{draf}/catatan",
        data={"catatan": "x" * 2001})
    assert kode == 400
    assert "terlalu panjang" in isi


def _post_raw(server, jalur, data=b"", headers=None):
    koneksi = http.client.HTTPConnection(
        server.server.server_address[0], server.server.server_address[1])
    tajuk = {
        "Authorization": _basic("guru", SANDI_GURU),
        "Content-Type": "application/x-www-form-urlencoded",
        **(headers or {}),
    }
    koneksi.request("POST", jalur, body=data, headers=tajuk)
    respons = koneksi.getresponse()
    hasil = (respons.status, respons.read().decode(), dict(respons.getheaders()))
    koneksi.close()
    return hasil


def test_payload_rusak_ditolak_sebelum_mutasi(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    jalur = f"/anak/{ids['anak']}/laporan-ortu/{laporan}/catatan"
    for mentah, tajuk, kode_harap in (
        (b"catatan=a&catatan=b", {}, 400),
        (b"catatan=%FF", {}, 400),
        (b"", {"Content-Length": "1000001"}, 413),
        (b"", {"Origin": "https://asing.invalid"}, 403),
    ):
        kode, _, _ = _post_raw(s, jalur, mentah, tajuk)
        assert kode == kode_harap, (mentah, tajuk)
    with s.buka() as kon:
        assert parent_report_store.ambil(kon, laporan)["catatan"] == ""


def test_post_raksasa_ditolak_413_sebelum_membaca_body(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    alamat = urlparse(s.alamat)
    koneksi = http.client.HTTPConnection(
        alamat.hostname, alamat.port, timeout=10)
    koneksi.putrequest(
        "POST", f"/anak/{ids['anak']}/laporan-ortu/{laporan}/terbitkan")
    koneksi.putheader("Authorization", _basic("guru", SANDI_GURU))
    koneksi.putheader("Content-Type", "application/x-www-form-urlencoded")
    koneksi.putheader("Content-Length", "1100000")
    koneksi.endheaders()
    respons = koneksi.getresponse()
    kode = respons.status
    respons.read()
    koneksi.close()
    assert kode == 413
    with s.buka() as kon:
        assert kon.execute(
            "SELECT diterbitkan FROM laporan_ortu WHERE id = ?", (laporan,)
        ).fetchone()["diterbitkan"] is None


def test_token_tersimpan_hanya_sebagai_hash_lewat_http(server):
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    with s.buka() as kon:
        baris = kon.execute(
            "SELECT token_hash FROM tautan_laporan WHERE siswa_id = ?",
            (ids["anak"],),
        ).fetchone()
    assert baris["token_hash"] == hashlib.sha256(
        token.encode("ascii")).hexdigest()
    assert token not in "".join(_iterdump(s))


def test_kedaluarsa_30_hari_dengan_waktu_dibekukan(server, monkeypatch):
    """TTL domain: batas tepat 30 hari, tanpa perpanjangan saat dibuka."""
    s, ids = server
    laporan = _buat_draf(s, ids["anak"])
    awal = 1_000_000
    monkeypatch.setattr(parent_report_store, "sekarang_detik", lambda: awal)
    token, _, _ = _terbitkan(s, ids["anak"], laporan)
    with s.buka() as kon:
        baris = kon.execute(
            "SELECT kedaluarsa FROM tautan_laporan WHERE siswa_id = ?",
            (ids["anak"],),
        ).fetchone()
    batas = awal + parent_report_store.TTL_DETIK
    assert parent_report_store.TTL_DETIK == 30 * 24 * 60 * 60
    assert baris["kedaluarsa"] == batas

    monkeypatch.setattr(
        parent_report_store, "sekarang_detik", lambda: batas - 1)
    assert s.minta(f"/laporan-ortu/{token}")[0] == 200
    with s.buka() as kon:
        assert kon.execute(
            "SELECT kedaluarsa FROM tautan_laporan WHERE siswa_id = ?",
            (ids["anak"],),
        ).fetchone()["kedaluarsa"] == batas  # membuka tautan tidak memperpanjang

    monkeypatch.setattr(parent_report_store, "sekarang_detik", lambda: batas)
    assert s.minta(f"/laporan-ortu/{token}")[0] == 404
