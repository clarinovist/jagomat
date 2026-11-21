"""Format tampilan Latihan Lomba: tanggal WIB (UTC+7 tetap), durasi mm:ss, persen, angka desimal Indonesia."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_format as F  # noqa: E402


@pytest.mark.parametrize("epoch,harapan", [
    (0, "1 Jan 1970, 07:00"),
    (1_800_000_000, "15 Jan 2027, 15:00"),
    (1_800_000_000 - 7 * 3600, "15 Jan 2027, 08:00"),
    (1_795_000_000, "18 Nov 2026, 18:06"),
    (1_800_000_000 + 9 * 3600, "16 Jan 2027, 00:00"),     # lewat tengah malam WIB
    (1_800_000_000 + 8 * 3600 + 3540, "15 Jan 2027, 23:59"),
])
def test_tanggal_wib_memakai_utc_tambah_tujuh_dan_bulan_singkat_indonesia(epoch, harapan):
    assert F.tanggal_wib(epoch) == harapan


def test_tanggal_wib_memakai_nama_bulan_indonesia_untuk_ke_dua_belas_bulan():
    awal_bulan = [1_767_225_600 + hari * 86_400 for hari in (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)]

    nama = [F.tanggal_wib(epoch).split()[1] for epoch in awal_bulan]

    assert nama == ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def test_tanggal_pendek_wib_membuang_jam():
    assert F.tanggal_pendek_wib(1_800_000_000) == "15 Jan 2027"


@pytest.mark.parametrize("detik,harapan", [(0, "00:00"), (5, "00:05"), (303, "05:03"), (900, "15:00"), (3599, "59:59"),
                                           (-4, "00:00")])
def test_durasi_menit_detik_dua_digit_dan_negatif_jadi_nol(detik, harapan):
    assert F.durasi_menit_detik(detik) == harapan


@pytest.mark.parametrize("benar,total,harapan", [(0, 0, 0), (3, 0, 0), (0, 3, 0), (1, 3, 33), (2, 3, 66), (3, 3, 100),
                                                  (7, 10, 70), (5, 9, 55)])
def test_persen_bulat_ke_bawah_dan_nol_bila_total_nol(benar, total, harapan):
    assert F.persen(benar, total) == harapan


@pytest.mark.parametrize("nilai,harapan", [(6.5, "6,5"), (7, "7,0"), (0.04, "0,0"), (1.25, "1,2"), (10, "10,0")])
def test_desimal_memakai_koma_dan_satu_angka_belakang_koma(nilai, harapan):
    assert F.desimal(nilai) == harapan
