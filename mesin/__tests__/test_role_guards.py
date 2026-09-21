"""Palang peran: akun murid TIDAK boleh menyentuh rute guru, GET maupun POST.

PERNAH SALAH (26 Agustus 2026, ditemukan lewat audit server hidup): palang
utama hanya memeriksa "nama+sandi benar". Akun murid bisa membuka /sesi/<id>
(kunci jawaban), /laporan/<id>, bahkan me-reset sandi murid lain lewat POST
/akun. Test ini menjaga arah terlarang itu — arah sebaliknya (guru ke
/murid) memang sengaja ditolak dan sudah dijaga di _rute_murid_get.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import auth  # noqa: E402
from http_test_kit import SANDI_GURU, SANDI_MURID, ServerUji  # noqa: E402


@pytest.fixture()
def server(tmp_path, monkeypatch):
    s = ServerUji(tmp_path, monkeypatch)
    with s.buka() as kon:
        sid = database.tambah_siswa(kon, "Putri", pemilik="guru")
        sesi_id = database.buat_sesi(kon, sid, seed=7)
    yield s, sesi_id, sid
    s.berhenti()


RUTE_GURU_GET = [
    # "/" TIDAK masuk daftar: sejak launch publik, / adalah landing publik
    # untuk anonim & murid (dashboard guru hanya untuk sesi guru — dijaga
    # test_publik.py). Palang yang dijaga di sini = rute berisi data anak.
    "/akun",
    "/sesi/{sesi}",
    "/laporan/{sesi}",
    "/lembar/{sesi}",
    "/lembar/{sesi}/penilaian",
]


@pytest.mark.parametrize("jalur", RUTE_GURU_GET)
def test_murid_ditolak_di_rute_guru_get(server, jalur):
    s, sesi_id, _ = server
    kode, isi, _ = s.minta(jalur.format(sesi=sesi_id), auth=("feby", SANDI_MURID))
    assert kode == 401, f"{jalur} terbuka untuk murid"
    # Halaman 401 harus halaman "Perlu masuk", bukan halaman guru yang bocor.
    # Jangan periksa "kunci" di seluruh HTML (CSS mengandung .kunci{}) , tapi
    # di bagian kata yang berarti — kata itu tidak ada di halaman 401.
    assert "perlu masuk" in isi.lower()


@pytest.mark.parametrize(
    "jalur,data",
    [
        ("/akun", {"aksi": "akun_murid_sandi", "nama": "feby", "baru": "diserang-99999"}),
        ("/akun", {"aksi": "akun_murid_hapus", "nama": "feby"}),
        ("/akun", {"aksi": "anak_baru", "nama": "Penyusup", "tingkat": "P3",
                   "sandi_anak": "sandi-uji-12345"}),
        ("/sesi-baru/{siswa}", {}),
    ],
)
def test_murid_ditolak_di_rute_guru_post(server, jalur, data):
    s, _, siswa_id = server
    kode, _, _ = s.minta(
        jalur.format(siswa=siswa_id),
        auth=("feby", SANDI_MURID),
        data=data,
    )
    assert kode == 401, f"POST {jalur} lolos untuk murid"


def test_mutasi_ditolak_tidak_terjadi(server):
    """Tolakan bukan sekadar status: tidak ada perubahan di berkas akun."""
    s, _, _ = server
    s.minta(
        "/akun",
        auth=("feby", SANDI_MURID),
        data={"aksi": "akun_murid_sandi", "nama": "feby", "baru": "diserang-99999"},
    )
    assert auth.periksa("feby", SANDI_MURID), "sandi feby ternyata berubah!"


def test_guru_masih_lolos_semua_rute_get(server):
    """Regresi: palang baru tidak boleh mengunci guru."""
    s, sesi_id, _ = server
    for jalur in RUTE_GURU_GET:
        kode, _, _ = s.minta(jalur.format(sesi=sesi_id), auth=("guru", SANDI_GURU))
        assert kode == 200, f"{jalur} jadi tertutup untuk guru"


def test_guru_masih_lolos_post_akun(server):
    s, _, _ = server
    kode, _, _ = s.minta(
        "/akun",
        auth=("guru", SANDI_GURU),
        data={"aksi": "anak_baru", "nama": "Baru", "profil_parameter": "P4",
              "sandi_anak": "sandi-baru-12345"},
    )
    assert kode == 200


def test_murid_rutenya_sendiri_tetap_jalan(server):
    s, _, _ = server
    kode, _, _ = s.minta("/murid", auth=("feby", SANDI_MURID))
    assert kode == 200


def test_murid_get_tanpa_sesi_diarahkan_ke_halaman_masuk(server):
    """Muat-ulang dengan kuki hilang/kedaluwarsa dulu menjatuhkan anak ke
    halaman 401 polos; kini GET dibawa ke /masuk dengan pesan yang jelas."""
    s, _, _ = server
    kode, isi, _ = s.minta("/murid")
    # urllib mengikuti 303: ujungnya halaman masuk + pesan, bukan halaman murid.
    assert kode == 200
    assert "Pilih sesi" not in isi
    assert "Masuk lagi dengan nama" in isi


def test_murid_get_tanpa_sesi_303_ke_masuk(server):
    """Bentuk mentahnya: 303 ke /masuk?galat=..., bukan 401 polos."""
    import urllib.error
    import urllib.parse
    import urllib.request

    s, _, _ = server

    class TanpaIkut(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(TanpaIkut)
    req = urllib.request.Request(s.alamat + "/murid")
    try:
        opener.open(req)
        raise AssertionError("GET /murid tanpa sesi harusnya 303")
    except urllib.error.HTTPError as e:
        assert e.code == 303
        # unquote_plus: urlencode memakai '+' untuk spasi.
        lokasi = urllib.parse.unquote_plus(dict(e.headers).get("Location", ""))
        assert lokasi.startswith("/masuk?")
        assert "galat=" in lokasi
        assert "Masuk lagi" in lokasi


def test_murid_post_tanpa_sesi_tetap_401(server):
    """Kirim jawaban tanpa sesi tetap ditolak 401 — palang tulis tidak
    boleh melemah karena pengalihan ramah di jalur GET."""
    s, _, _ = server
    kode, _, _ = s.minta("/murid/kerjakan/1", data={})
    assert kode == 401


def test_tanpa_kredensial_rute_guru_tetap_401(server):
    """Palang pindah ke rute data; / kini landing publik (200)."""
    s, sesi_id, _ = server
    assert s.minta("/")[0] == 200  # landing, bukan 401
    assert s.minta(f"/sesi/{sesi_id}")[0] == 401
    assert s.minta("/akun")[0] == 401


def test_sandi_salah_rute_guru_tetap_401(server):
    s, sesi_id, _ = server
    assert s.minta(f"/sesi/{sesi_id}", auth=("guru", "sandalah-yang-salah"))[0] == 401
