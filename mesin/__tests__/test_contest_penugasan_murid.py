"""Mode Lomba per anak, sisi murid: tanpa penugasan aktif dari Guru, Lomba tidak tampil dan semua rutenya 404.

Sakelar induk (`OSN_LOMBA`) hidup di semua tes ini; yang diuji adalah gerbang per anak (`contest_gate.aktif_untuk`).
404 harus byte-identik (tubuh dan header) dengan jalur murid tak dikenal dan tanpa efek samping (tidak ada sesi
baru, tidak ada jawaban tertulis). Data sintetis di tmp_path; jam server dipalsukan.
"""
import datetime
import itertools
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import auth  # noqa: E402
import contest_assignment_store as AS  # noqa: E402
import contest_http  # noqa: E402
import contest_store  # noqa: E402
import database  # noqa: E402
from http_test_kit import ServerUji  # noqa: E402
from test_contest_http import (  # noqa: E402
    MURID_DUA, MURID_SATU, RUTE_GET, RUTE_POST, SANDI_DUA, T0, _get, _jawaban, _keadaan, _Jam, _mulai, _nomor_berjenis, _post,
)

SEBELUM_LOMBA = 1_795_000_000        # 18 Nov 2026: hitung mundur "Lomba tinggal 24 hari lagi"


@pytest.fixture
def jam(monkeypatch):
    jam_uji = _Jam(T0)
    monkeypatch.setattr(contest_http, "_sekarang", jam_uji)
    return jam_uji


@pytest.fixture
def server(tmp_path, monkeypatch, jam):
    """Sakelar induk hidup; dua anak, KEDUANYA tanpa penugasan (Guru belum mengaktifkan)."""
    monkeypatch.setenv("OSN_LOMBA", "1")
    benih = itertools.count(101)
    monkeypatch.setattr(contest_store.secrets, "randbits", lambda _bit: next(benih))
    uji = ServerUji(tmp_path, monkeypatch)
    try:
        with uji.buka() as kon:
            uji.anak_satu = database.tambah_siswa(kon, "feby", pemilik="guru")
            uji.anak_dua = database.tambah_siswa(kon, "Budi Sintetis", pemilik="guru")
        auth.tambah_akun("budi-uji", SANDI_DUA, "murid", siswa_id=uji.anak_dua)
        yield uji
    finally:
        uji.berhenti()


def _tugaskan(uji, siswa_id, *, aktif=True, target=None, hitung_mundur=None):
    with uji.buka() as kon:
        AS.atur(kon, siswa_id, aktif=aktif, target_harian=target, tampil_hitung_mundur=hitung_mundur, durasi_latihan_detik=None, durasi_simulasi_detik=None,
                tanggal_lomba=datetime.date(2026, 12, 12), nama_lomba=None, sekarang=T0, oleh="guru-uji")


def _tak_dikenal(uji, pengguna=MURID_SATU):
    return _get(uji, "/murid/tidak-ada", pengguna)


def _jumlah_sesi(uji):
    with uji.buka() as kon:
        return kon.execute("SELECT COUNT(*) FROM lomba_sesi").fetchone()[0]


# --- tanpa penugasan: 404 identik, tanpa efek samping -------------------------------------------------

@pytest.mark.parametrize("jalur", RUTE_GET)
def test_get_tanpa_baris_penugasan_identik_dengan_jalur_murid_tak_dikenal(server, jalur):
    lomba = _get(server, jalur)

    assert lomba.kode == 404
    assert lomba.sidik() == _tak_dikenal(server).sidik()


@pytest.mark.parametrize("jalur", RUTE_GET)
def test_get_dengan_penugasan_dimatikan_identik_dengan_jalur_murid_tak_dikenal(server, jalur):
    _tugaskan(server, server.anak_satu, aktif=False)

    lomba = _get(server, jalur)

    assert lomba.kode == 404 and lomba.sidik() == _tak_dikenal(server).sidik()


@pytest.mark.parametrize("jalur", RUTE_POST)
def test_post_tanpa_penugasan_dijawab_404_identik_dan_tanpa_efek_samping(server, jalur):
    sebelum = _keadaan(server)

    lomba = _post(server, jalur, {"no": "1", "jawaban": "A"})

    assert lomba.kode == 404 and lomba.sidik() == _tak_dikenal(server).sidik()
    assert _keadaan(server) == sebelum


def test_post_mulai_tanpa_penugasan_tidak_membuat_sesi(server):
    _post(server, "/murid/lomba/mulai")
    _post(server, "/murid/lomba/mulai", pengguna=MURID_DUA)

    assert _jumlah_sesi(server) == 0


def test_penugasan_satu_anak_tidak_membuka_lomba_untuk_anak_lain(server):
    _tugaskan(server, server.anak_satu)

    assert _get(server, "/murid/lomba").kode == 200
    lain = _get(server, "/murid/lomba", MURID_DUA)
    assert lain.kode == 404 and lain.sidik() == _tak_dikenal(server, MURID_DUA).sidik()
    _post(server, "/murid/lomba/mulai", pengguna=MURID_DUA)
    assert _jumlah_sesi(server) == 0


def test_penugasan_aktif_membuka_seluruh_alur_lomba(server):
    _tugaskan(server, server.anak_satu)

    sesi_id = _mulai(server)

    assert _get(server, f"/murid/lomba/sesi/{sesi_id}?no=1").kode == 200
    assert _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul").lokasi == f"/murid/lomba/hasil/{sesi_id}"


# --- penugasan dimatikan saat sesi berjalan -----------------------------------------------------------

def test_penugasan_dimatikan_saat_sesi_berjalan_menutup_akses_tanpa_menulis_dan_data_tetap(server):
    _tugaskan(server, server.anak_satu)
    sesi_id = _mulai(server)
    nomor = str(_nomor_berjenis(server, sesi_id, "pg"))
    assert _post(server, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": nomor, "jawaban": "A", "aksi": "simpan"}).kode == 303
    tersimpan = _jawaban(server, sesi_id)
    assert tersimpan

    _tugaskan(server, server.anak_satu, aktif=False)
    sebelum = _keadaan(server)

    assert _get(server, f"/murid/lomba/sesi/{sesi_id}?no=1").sidik() == _tak_dikenal(server).sidik()
    tulis = _post(server, f"/murid/lomba/sesi/{sesi_id}/jawab", {"no": nomor, "jawaban": "B", "aksi": "simpan"})
    assert tulis.sidik() == _tak_dikenal(server).sidik()
    assert _post(server, f"/murid/lomba/sesi/{sesi_id}/kumpul").kode == 404
    assert _keadaan(server) == sebelum

    _tugaskan(server, server.anak_satu, aktif=True)           # Guru mengaktifkan lagi: sesi dan jawaban utuh
    assert _get(server, f"/murid/lomba/sesi/{sesi_id}?no=1").kode == 200
    assert _jawaban(server, sesi_id) == tersimpan


# --- beranda murid ------------------------------------------------------------------------------------

def test_beranda_tanpa_penugasan_byte_identik_dengan_beranda_saat_sakelar_induk_mati(server, monkeypatch):
    hidup_tanpa_penugasan = _get(server, "/murid")
    monkeypatch.setenv("OSN_LOMBA", "0")
    mati = _get(server, "/murid")

    assert hidup_tanpa_penugasan.kode == 200 and "/murid/lomba" not in hidup_tanpa_penugasan.isi.decode()
    assert hidup_tanpa_penugasan.sidik() == mati.sidik()


def test_beranda_penugasan_dimatikan_tidak_memuat_lomba(server):
    _tugaskan(server, server.anak_satu, aktif=False)

    assert "/murid/lomba" not in _get(server, "/murid").isi.decode()


def test_beranda_dengan_penugasan_aktif_memuat_kartu_mode_lomba(server):
    _tugaskan(server, server.anak_satu)

    isi = _get(server, "/murid").isi.decode()

    assert "/murid/lomba" in isi and "Mode Lomba" in isi


def test_beranda_anak_lain_tidak_memuat_lomba_walau_anak_satu_ditugaskan(server):
    _tugaskan(server, server.anak_satu)

    assert "/murid/lomba" not in _get(server, "/murid", MURID_DUA).isi.decode()


# --- override paket oleh penugasan --------------------------------------------------------------------

def _teks(uji):
    return re.sub(r"<[^>]+>", " ", _get(uji, "/murid/lomba").isi.decode())


def test_halaman_awal_memakai_target_dan_hitung_mundur_paket_bila_penugasan_tidak_menimpa(server, jam):
    jam.t = SEBELUM_LOMBA
    _tugaskan(server, server.anak_satu)

    teks = _teks(server)

    assert "Latihan hari ini: 0 dari 2" in teks and "Lomba tinggal 24 hari lagi" in teks


def test_halaman_awal_memakai_target_dari_penugasan(server, jam):
    jam.t = SEBELUM_LOMBA
    _tugaskan(server, server.anak_satu, target=3)

    assert "Latihan hari ini: 0 dari 3" in _teks(server)


def test_target_nol_dari_penugasan_menyembunyikan_target(server, jam):
    jam.t = SEBELUM_LOMBA
    _tugaskan(server, server.anak_satu, target=0)

    assert "Latihan hari ini" not in _teks(server)


def test_hitung_mundur_dimatikan_oleh_penugasan(server, jam):
    jam.t = SEBELUM_LOMBA
    _tugaskan(server, server.anak_satu, hitung_mundur=False)

    teks = _teks(server)

    assert "Lomba tinggal" not in teks and "Latihan hari ini: 0 dari 2" in teks


# --- tanggal lomba per anak (23 Nov 2026) --------------------------------------------------------------------

def _tugaskan_tanggal(uji, siswa_id, tanggal, nama=None):
    with uji.buka() as kon:
        AS.atur(kon, siswa_id, aktif=True, target_harian=None, tampil_hitung_mundur=None, durasi_latihan_detik=None,
                durasi_simulasi_detik=None, tanggal_lomba=tanggal, nama_lomba=nama, sekarang=T0, oleh="guru-uji")


def test_dua_anak_melihat_hitung_mundur_ke_tanggal_masing_masing_dan_tidak_melihat_nama(server, jam):
    jam.t = SEBELUM_LOMBA          # 18 Nov 2026 WIB
    _tugaskan_tanggal(server, server.anak_satu, datetime.date(2026, 11, 28), nama="NamaRahasiaGuruSintetis")
    _tugaskan_tanggal(server, server.anak_dua, datetime.date(2026, 12, 30))

    satu = _get(server, "/murid/lomba").isi.decode()
    dua = _get(server, "/murid/lomba", MURID_DUA).isi.decode()

    assert "Lomba tinggal 10 hari lagi" in re.sub(r"<[^>]+>", " ", satu)
    assert "Lomba tinggal 42 hari lagi" in re.sub(r"<[^>]+>", " ", dua)
    assert "NamaRahasiaGuruSintetis" not in satu and "Mode Lomba" in satu


def test_anak_tanpa_tanggal_tidak_melihat_hitung_mundur_walau_paket_punya_tanggal(server, jam):
    jam.t = SEBELUM_LOMBA
    _tugaskan_tanggal(server, server.anak_satu, None)

    assert "Lomba tinggal" not in _teks(server)
