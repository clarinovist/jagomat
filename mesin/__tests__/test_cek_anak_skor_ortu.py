"""Alur ujung akun anak: cek dikumpulkan lewat tautan anak -> skor tersimpan -> halaman Ayah/Bunda menampilkan hasil.

Tanpa penilaian manual di tes (penilaian manual dulu menutupi celah skor NULL setelah kumpul). Data sintetis di tmp_path.
"""
import pytest

import cek_gratis
import cek_gratis_kit as kit_cek
import cek_gratis_skor
import orang_tua_pages as halaman
from cek_murid_kit import (  # noqa: F401  (server/gerbang_hidup adalah fixture)
    JUMLAH_SOAL, POLA_REVISI, Anak, gerbang_hidup, kirim, server,
)

RUTE_ORTU = "/murid/orang-tua"
TEKS_LANJUT = "Lanjutkan cek"
HASIL_SELESAI = {"status": "selesai", "skor": 60, "kategori": "Perlu penguatan",
                 "ringkasan": {"kuat": ["Penjumlahan"], "perlu": ["Pecahan"]}, "jumlah_soal": 15}
HASIL_BELUM_SELESAI = {"status": "belum_selesai", "skor": None, "kategori": None,
                       "ringkasan": {"kuat": [], "perlu": []}, "jumlah_soal": 15}
HASIL_BELUM_MULAI = {**HASIL_BELUM_SELESAI, "status": "belum_mulai"}


def _jawab_dan_kumpul(server, anak, lokasi, benar=7):
    """Jawab sintetis lalu kumpul lewat rute tautan anak yang asli (tanpa memanggil penilaian)."""
    baris = anak.baris_cek()
    with server.buka() as kon:
        kit_cek.jawab(kon, baris["sesi_id"], semua_benar=benar)
    _, peta, _ = kirim(server, lokasi.split("?")[0] + "?peta=1")
    revisi = POLA_REVISI.search(peta).group(1)
    return kirim(server, lokasi.split("?")[0], {"aksi": "kumpul", "revisi_pekerjaan": revisi})


def _anak_mulai(server, nama):
    anak = Anak(server, nama)
    _, _, header = anak.post()
    return anak, header["Location"]


# --- perbaikan A: skor ditulis saat kumpul ---------------------------------------------

def test_kumpul_lewat_tautan_anak_langsung_menyimpan_skor_dan_halaman_ortu_menampilkan_hasil(server, gerbang_hidup):
    anak, lokasi = _anak_mulai(server, "raka-ortu-a")
    kode, hore, _ = _jawab_dan_kumpul(server, anak, lokasi)
    assert kode == 200 and "Hore" in hore
    baris = anak.baris_cek()
    assert baris["skor"] == cek_gratis_skor.hitung_skor(7, JUMLAH_SOAL)  # ditulis saat kumpul, bukan saat halaman dibuka
    assert baris["kategori"] and baris["selesai_pada"]
    kode, isi, _ = anak.get(RUTE_ORTU)
    assert kode == 200
    assert "belum selesai dikerjakan" not in isi and "Ringkasan awal" in isi
    assert TEKS_LANJUT not in isi


def test_kumpul_tidak_menyentuh_cek_akun_lain(server, gerbang_hidup):
    anak_a, lokasi_a = _anak_mulai(server, "raka-ortu-b1")
    anak_b, _ = _anak_mulai(server, "dina-ortu-b2")
    _jawab_dan_kumpul(server, anak_a, lokasi_a)
    assert anak_a.baris_cek()["skor"] is not None
    assert anak_b.baris_cek()["skor"] is None


def test_selesaikan_sesi_tanpa_baris_cek_tidak_melakukan_apa_apa(server, gerbang_hidup):
    with server.buka() as kon:
        assert cek_gratis.selesaikan_sesi(kon, 987654, kit_cek.SEKARANG) is False


# --- perbaikan B: penyelamat data lama saat halaman dibuka -------------------------------

def test_sesi_sudah_selesai_tapi_skor_kosong_ternilai_saat_halaman_ortu_dibuka(server, gerbang_hidup):
    anak, _ = _anak_mulai(server, "raka-ortu-c")
    sesi_id = anak.baris_cek()["sesi_id"]
    with server.buka() as kon:  # meniru data sebelum perbaikan: sesi selesai, skor NULL
        kit_cek.jawab(kon, sesi_id, semua_benar=9)
        kit_cek.tandai_selesai(kon, sesi_id)
    assert anak.baris_cek()["skor"] is None
    kode, isi, _ = anak.get(RUTE_ORTU)
    assert kode == 200 and "belum selesai dikerjakan" not in isi and "Ringkasan awal" in isi
    skor = anak.baris_cek()["skor"]
    assert skor == cek_gratis_skor.hitung_skor(9, JUMLAH_SOAL)
    anak.get(RUTE_ORTU)  # idempoten: dibuka lagi tidak mengubah skor
    assert anak.baris_cek()["skor"] == skor


def test_sesi_belum_selesai_tetap_belum_selesai_dan_punya_tautan_lanjut(server, gerbang_hidup):
    anak, _ = _anak_mulai(server, "raka-ortu-d")
    kode, isi, _ = anak.get(RUTE_ORTU)
    assert kode == 200 and "belum selesai dikerjakan" in isi and TEKS_LANJUT in isi
    assert anak.baris_cek()["skor"] is None


def test_belum_mulai_punya_tautan_lanjut_ke_beranda_anak(server, gerbang_hidup):
    anak = Anak(server, "raka-ortu-e")
    kode, isi, _ = anak.get(RUTE_ORTU)
    assert kode == 200 and "belum dikerjakan" in isi
    assert f'href="{halaman.RUTE_BERANDA_ANAK}">{TEKS_LANJUT}</a>' in isi


# --- perbaikan tautan jalan keluar (render murni) ----------------------------------------

@pytest.mark.parametrize("hasil", [HASIL_BELUM_MULAI, HASIL_BELUM_SELESAI])
def test_blok_cek_belum_selesai_punya_satu_tautan_ke_kartu_cek_di_beranda(hasil):
    isi = halaman._blok_cek(hasil, "Anak Sintetis")
    assert isi.count(TEKS_LANJUT) == 1
    assert 'href="/murid#judul-cek-murid"' in isi and "ortu-tombol-st ortu-tombol-pinggir-st" in isi


def test_blok_cek_selesai_tanpa_tautan_lanjut():
    assert TEKS_LANJUT not in halaman._blok_cek(HASIL_SELESAI, "Anak Sintetis")
