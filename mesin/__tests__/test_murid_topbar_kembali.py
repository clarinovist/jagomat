"""Tautan topbar murid: Paket, Latihan Harian, dan Peta kembali ke Halaman Ayah/Bunda, bukan Beranda.

Murni render (data sintetis, tanpa DB/HTTP). Peran guru tidak ikut berubah.
"""
import pytest

import harian_langganan_pages as harian
import harian_langganan_ringkas as ringkas
import kelas_pages as kelas
import orang_tua_pages
import orang_tua_style
import pesanan_dasar as d
import pesanan_murid_pages
import pesanan_pages as peta
from murid_shell import PANAH_KEMBALI, aksi_topbar
from pesanan_permukaan import PERAN_MURID

MURID = ("akun-uji", PERAN_MURID)
GURU = ("akun-uji", "guru")
REKENING = {"nama_bank": "Bank Contoh", "nomor_label": "1234 5678 90", "atas_nama": "PT Contoh Sintetis"}
TOPBAR_KEMBALI = aksi_topbar("/murid/orang-tua", "Halaman Ayah/Bunda", PANAH_KEMBALI)
TOPBAR_BERANDA = aksi_topbar("/murid", "Beranda", PANAH_KEMBALI)
TAMPILAN_BAYAR = {"status": d.STATUS_BELUM_BAYAR, "nama_anak": "Anak Sintetis", "qr": False, "aksi": None,
                  "boleh_ulang": False, "belum_terperiksa": False}


class _Rekening:
    nama_bank, nomor_label, atas_nama = REKENING["nama_bank"], REKENING["nomor_label"], REKENING["atas_nama"]


def _token(aksi):
    return "tok." + aksi


PRODUSEN_MURID = {
    "paket_info": lambda: kelas.halaman_info("Judul", "Teks"),
    "latihan_info": lambda: harian.halaman_info("Judul", "Teks"),
    "latihan_langganan": lambda: harian.halaman_langganan(
        ringkas.Ringkasan("gratis", None, 0, None), None, _Rekening(), _token),
    "peta_belum_memesan": lambda: peta.halaman_belum_memesan(MURID, "tok"),
    "peta_tertutup": lambda: peta.halaman_tertutup(MURID),
    "peta_info": lambda: peta.halaman_info(MURID, "Judul", "Teks"),
    "peta_status": lambda: peta.halaman_status(MURID, TAMPILAN_BAYAR, "tok"),
}


@pytest.mark.parametrize("nama", list(PRODUSEN_MURID), ids=list(PRODUSEN_MURID))
def test_topbar_murid_kembali_ke_halaman_ortu_bukan_beranda(nama):
    # Arrange
    produsen = PRODUSEN_MURID[nama]

    # Act
    html = produsen().decode()

    # Assert
    assert TOPBAR_KEMBALI in html
    assert TOPBAR_BERANDA not in html


def test_topbar_peta_guru_tetap_tanpa_tautan_halaman_ortu():
    # Arrange
    # (peran guru memakai rute guru; tautan Halaman Ayah/Bunda hanya untuk murid)

    # Act
    html = peta.halaman_info(GURU, "Judul", "Teks").decode()

    # Assert
    assert "/murid/orang-tua" not in html
    assert "Halaman Ayah/Bunda" not in html
    assert 'href="/guru"' in html


def test_tujuan_dan_label_kembali_murid_mengikuti_rute_dan_judul_ortu():
    # Arrange
    tujuan_rute = orang_tua_style.RUTE
    judul_ortu = orang_tua_pages.COPY_JUDUL

    # Act
    tujuan = pesanan_murid_pages.TUJUAN_ORANG_TUA
    label = pesanan_murid_pages.LABEL_ORANG_TUA

    # Assert
    assert tujuan == tujuan_rute == "/murid/orang-tua"
    assert label == judul_ortu == "Halaman Ayah/Bunda"


def test_copy_akibat_hapus_memakai_ejaan_terlanjur():
    # Arrange
    copy = kelas.COPY_AKIBAT_HAPUS

    # Act / Assert
    assert "terlanjur" in copy
    assert "telanjur" not in copy
