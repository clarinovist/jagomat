"""Fungsi murni cek gratis: skor, kategori, ringkasan, pemetaan kelas, waktu."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cek_gratis_skor as skor  # noqa: E402
import topik_awam  # noqa: E402


def _nama(topik_id):
    return topik_awam.nama(topik_id)


# --- hitung_skor ------------------------------------------------------------

@pytest.mark.parametrize("benar,jumlah,harapan", [
    (0, 15, 0), (15, 15, 100), (1, 15, 7), (2, 15, 13), (9, 15, 60),
    (13, 15, 87), (12, 15, 80),
    (1, 8, 13),   # 12,5 -> 13 (setengah ke atas, bukan pembulatan bankir)
    (3, 8, 38),   # 37,5 -> 38
    (1, 200, 1),  # 0,5 -> 1
])
def test_hitung_skor_membulatkan_setengah_ke_atas(benar, jumlah, harapan):
    assert skor.hitung_skor(benar, jumlah) == harapan


@pytest.mark.parametrize("benar,jumlah", [
    (-1, 15), (16, 15), (0, 0), (0, -3), (True, 15), (5, True), (5.0, 15), (5, 15.0),
    ("5", 15), (None, 15),
])
def test_hitung_skor_menolak_masukan_tidak_sah(benar, jumlah):
    with pytest.raises(ValueError):
        skor.hitung_skor(benar, jumlah)


# --- kategori_dari_skor -----------------------------------------------------

@pytest.mark.parametrize("nilai,harapan", [
    (100, "Sangat baik"), (85, "Sangat baik"), (84, "Cukup baik"),
    (65, "Cukup baik"), (64, "Perlu penguatan"), (40, "Perlu penguatan"),
    (39, "Perlu pendampingan"), (0, "Perlu pendampingan"),
])
def test_kategori_di_batas_85_65_40(nilai, harapan):
    assert skor.kategori_dari_skor(nilai) == harapan


@pytest.mark.parametrize("nilai", [-1, 101, True, 50.0, "50", None])
def test_kategori_menolak_skor_tidak_sah(nilai):
    with pytest.raises(ValueError):
        skor.kategori_dari_skor(nilai)


def test_empat_label_kategori_dan_konstanta_plan():
    assert skor.KATEGORI == ("Sangat baik", "Cukup baik", "Perlu penguatan", "Perlu pendampingan")
    assert (skor.JUMLAH_SOAL, skor.RETENSI_SELESAI_HARI, skor.RETENSI_BELUM_SELESAI_HARI) == (15, 30, 7)
    assert skor.TOPIK_LAMA == ("pola-bilangan", "statistika", "geometri-datar")
    assert skor.TOPIK_PER_KELAS == {
        3: ("berhitung-sekolah", "geometri-datar", "statistika"),
        4: ("berhitung-sekolah", "pengukuran", "geometri-datar"),
        5: ("aritmetika-dasar", "aritmatika-lanjut", "geometri-datar"),
        6: ("aritmetika-dasar", "aritmatika-lanjut", "geometri-datar"),
    }
    assert (skor.TOPIK_DASAR, skor.VERSI_NOTICE) == ("bilangan-dasar", "v1")


@pytest.mark.parametrize("kelas", [3, 4, 5, 6])
def test_topik_untuk_kelas_sesuai_peta(kelas):
    assert skor.topik_untuk_kelas(kelas) == skor.TOPIK_PER_KELAS[kelas]


@pytest.mark.parametrize("kelas", [0, 1, 2, 7, True, 3.0, "3", None])
def test_topik_untuk_kelas_menolak_kelas_di_luar_3_sampai_6(kelas):
    with pytest.raises(ValueError):
        skor.topik_untuk_kelas(kelas)


def test_semua_topik_cek_gabungan_deterministik_tanpa_duplikat():
    semua = skor.semua_topik_cek()
    assert len(semua) == len(set(semua))
    assert set(semua) == {
        "berhitung-sekolah", "geometri-datar", "statistika", "pengukuran",
        "aritmetika-dasar", "aritmatika-lanjut", "pola-bilangan", "bilangan-dasar",
    }
    assert semua == skor.semua_topik_cek()


# --- ringkas ----------------------------------------------------------------

def test_ringkas_kuat_dan_perlu_dengan_nama_topik_awam():
    hasil = skor.ringkas([("pola-bilangan", 5, 5), ("statistika", 3, 5), ("geometri-datar", 1, 5)])
    assert hasil == {"kuat": [_nama("pola-bilangan")], "perlu": [_nama("geometri-datar")]}


def test_ringkas_abaikan_topik_di_bawah_tiga_soal():
    hasil = skor.ringkas([("pola-bilangan", 2, 2), ("statistika", 0, 2), ("geometri-datar", 3, 3)])
    assert hasil == {"kuat": [_nama("geometri-datar")], "perlu": []}


def test_ringkas_batas_rasio_inklusif_dan_zona_tengah_kosong():
    # 4/5 = 0,8 -> kuat; 5/10 = 0,5 -> perlu; 3/5 = 0,6 -> tidak masuk mana pun.
    hasil = skor.ringkas([("pola-bilangan", 4, 5), ("statistika", 5, 10), ("geometri-datar", 3, 5)])
    assert hasil == {"kuat": [_nama("pola-bilangan")], "perlu": [_nama("statistika")]}


def test_ringkas_maksimal_dua_butir_dan_urutan_deterministik():
    hasil = skor.ringkas([("statistika", 5, 5), ("pola-bilangan", 5, 5), ("geometri-datar", 4, 5)])
    assert hasil["kuat"] == [_nama("pola-bilangan"), _nama("statistika")]
    sebaliknya = skor.ringkas([("geometri-datar", 0, 5), ("statistika", 1, 5), ("pola-bilangan", 2, 5)])
    assert sebaliknya["perlu"] == [_nama("geometri-datar"), _nama("statistika")]


def test_ringkas_tanpa_data_mengembalikan_dua_daftar_kosong():
    assert skor.ringkas([]) == {"kuat": [], "perlu": []}


@pytest.mark.parametrize("masukan", [
    [("pola-bilangan", 6, 5)], [("pola-bilangan", -1, 5)], [("pola-bilangan", 1, 0)],
    [("", 1, 5)], [(None, 1, 5)], [("pola-bilangan", 1)], [("pola-bilangan", True, 5)],
    [("topik-tidak-ada", 5, 5)], [5],
])
def test_ringkas_menolak_butir_tidak_sah(masukan):
    with pytest.raises(ValueError):
        skor.ringkas(masukan)


def test_ringkas_tidak_memuat_angka_per_topik():
    hasil = skor.ringkas([("pola-bilangan", 5, 5), ("geometri-datar", 0, 5)])
    teks = repr(hasil)
    assert not any(c.isdigit() for c in teks)


# --- level_untuk_kelas ------------------------------------------------------

@pytest.mark.parametrize("kelas", [1, 2, 3, 4, 5, 6])
def test_level_untuk_kelas_sah(kelas):
    assert skor.level_untuk_kelas(kelas) == "P%d" % kelas


@pytest.mark.parametrize("kelas", [0, 7, -1, True, 3.0, "3", 10])
def test_level_untuk_kelas_di_luar_enam_ditolak(kelas):
    with pytest.raises(ValueError, match="kelas 1 sampai 6"):
        skor.level_untuk_kelas(kelas)


def test_level_untuk_kelas_kosong_pesan_jujur():
    with pytest.raises(ValueError, match="belum diisi"):
        skor.level_untuk_kelas(None)


# --- waktu ------------------------------------------------------------------

def test_waktu_teks_baku_dan_zona_dikonversi_ke_utc():
    assert skor.waktu_teks("2026-11-18T10:00:00") == "2026-11-18T10:00:00"
    assert skor.waktu_teks("2026-11-18 10:00:00") == "2026-11-18T10:00:00"
    assert skor.waktu_teks("2026-11-18T10:00:00+07:00") == "2026-11-18T03:00:00"


@pytest.mark.parametrize("nilai", [None, 123, "bukan waktu", ""])
def test_waktu_tidak_sah_ditolak(nilai):
    with pytest.raises(ValueError):
        skor.waktu_teks(nilai)
