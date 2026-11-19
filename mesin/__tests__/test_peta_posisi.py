"""Posisi anak (persentil + peringkat): fungsi murni, data sintetis."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis_skor  # noqa: E402
from peta_posisi import HasilPosisi, MINIMAL_PEMBANDING, hitung_posisi  # noqa: E402


def test_kurang_dari_minimal_mengembalikan_none():
    assert hitung_posisi(70, [70] * (MINIMAL_PEMBANDING - 1)) is None
    assert hitung_posisi(70, []) is None


def test_tepat_minimal_dihitung():
    hasil = hitung_posisi(70, [70] * MINIMAL_PEMBANDING)
    assert isinstance(hasil, HasilPosisi) and hasil.penyebut == MINIMAL_PEMBANDING


def test_minimal_bisa_diganti():
    assert hitung_posisi(50, [10, 50, 90], minimal=3) is not None
    assert hitung_posisi(50, [10, 50, 90], minimal=4) is None


def test_semua_sama_persentil_50_peringkat_1():
    hasil = hitung_posisi(60, [60] * 40)
    assert (hasil.persentil, hasil.peringkat, hasil.penyebut) == (50, 1, 40)


def test_skor_tertinggi_unik_peringkat_1_persentil_dibulatkan_ke_100():
    pembanding = [100] + [50] * 39
    hasil = hitung_posisi(100, pembanding)
    # (39 + 0,5) / 40 x 100 = 98,75 -> 99
    assert (hasil.persentil, hasil.peringkat, hasil.penyebut) == (99, 1, 40)


def test_skor_terendah_unik_peringkat_terakhir():
    pembanding = [0] + [50] * 39
    hasil = hitung_posisi(0, pembanding)
    # (0 + 0,5) / 40 x 100 = 1,25 -> 1
    assert (hasil.persentil, hasil.peringkat, hasil.penyebut) == (1, 40, 40)
    assert hasil.peringkat <= hasil.penyebut


def test_seri_dihitung_setengah_dan_peringkat_tidak_menghitung_seri():
    pembanding = [40] * 10 + [60] * 10 + [80] * 10
    hasil = hitung_posisi(60, pembanding)
    # rendah=10, sama=10, tinggi=10: (10 + 5) / 30 x 100 = 50
    assert (hasil.persentil, hasil.peringkat) == (50, 11)


def test_pembulatan_setengah_ke_atas_bukan_bankir():
    # (rendah 1 + sama/2 0,5) / 30... pilih angka yang tepat .5: n=40, rendah=1, sama=0
    # (1 + 0) / 40 x 100 = 2,5 -> 3 (bankir memberi 2)
    pembanding = [10] + [90] * 39
    hasil = hitung_posisi(50, pembanding)
    assert hasil.persentil == 3
    # n=40, rendah=3, sama=0: 7,5 -> 8 (bankir juga 8); rendah=5: 12,5 -> 13 (bankir 12)
    assert hitung_posisi(50, [10] * 5 + [90] * 35).persentil == 13


def test_persentil_sama_dengan_rumus_pecahan_eksak():
    from fractions import Fraction

    pembanding = [(i * 7) % 101 for i in range(57)]
    for skor in (0, 13, 50, 77, 100):
        hasil = hitung_posisi(skor, pembanding)
        rendah = sum(1 for b in pembanding if b < skor)
        sama = sum(1 for b in pembanding if b == skor)
        eksak = (rendah + Fraction(sama, 2)) / len(pembanding) * 100
        assert hasil.persentil == int(eksak + Fraction(1, 2))


def test_memakai_pembulatan_yang_sama_dengan_hitung_skor():
    assert hitung_posisi(50, [10] + [90] * 39).persentil == cek_gratis_skor.hitung_skor(2, 80)


def test_hasil_tidak_bisa_diubah():
    hasil = hitung_posisi(70, [70] * 30)
    with pytest.raises(Exception):
        hasil.persentil = 1  # type: ignore[misc]


def test_menerima_generator_dan_tuple():
    assert hitung_posisi(70, (70 for _ in range(30))).penyebut == 30
    assert hitung_posisi(70, tuple([70] * 30)).penyebut == 30


@pytest.mark.parametrize("skor", [-1, 101, 70.0, "70", None, True])
def test_skor_tidak_sah(skor):
    with pytest.raises(ValueError):
        hitung_posisi(skor, [70] * 30)


@pytest.mark.parametrize("butir", [-1, 101, 55.5, "55", None, True])
def test_pembanding_tidak_sah(butir):
    with pytest.raises(ValueError):
        hitung_posisi(70, [70] * 29 + [butir])


def test_pembanding_bukan_iterabel():
    with pytest.raises(ValueError):
        hitung_posisi(70, 30)


@pytest.mark.parametrize("minimal", [0, -5, 2.5, "30", True])
def test_minimal_tidak_sah(minimal):
    with pytest.raises(ValueError):
        hitung_posisi(70, [70] * 30, minimal=minimal)


def test_label_materi_batas_80_dan_minimal_soal():
    assert cek_gratis_skor.label_materi(4, 5) == "Kuat"
    assert cek_gratis_skor.label_materi(7, 8) == "Kuat"  # 87,5 -> 88
    assert cek_gratis_skor.label_materi(3, 6) == "Perlu diperkuat"
    assert cek_gratis_skor.label_materi(3, 4) == "Perlu diperkuat"  # 75
    assert cek_gratis_skor.label_materi(2, 2) == "Belum cukup soal"
    assert cek_gratis_skor.label_materi(1, 1) == "Belum cukup soal"
    with pytest.raises(ValueError):
        cek_gratis_skor.label_materi(0, 0)


def test_label_materi_mengikuti_persen_tampil_di_batas_79_5():
    # 35/44 = 79,5% tampil 80%, jadi harus Kuat (label tidak boleh melawan angka).
    assert cek_gratis_skor.hitung_skor(35, 44) == 80
    assert cek_gratis_skor.label_materi(35, 44) == "Kuat"
    assert cek_gratis_skor.hitung_skor(34, 43) == 79
    assert cek_gratis_skor.label_materi(34, 43) == "Perlu diperkuat"
