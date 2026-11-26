"""Sisa copy Peta otomatis: janji terbit tanpa tenggat 48 jam, contoh tanpa catatan Guru, dan contoh penjualan.

Data sintetis saja. Laporan yang diterbitkan sistem tidak menyebut Guru dan tidak memuat janji 48 jam; jalur laporan
Guru yang sungguhan tetap memajang kartu catatan Guru.
"""
from __future__ import annotations

import dataclasses
from dataclasses import replace

import funnel_contoh
import peta_contoh_data
import peta_laporan
import peta_laporan_ortu_pages as ortu
import peta_ringkasan
import pesanan_voucher_pages as hv
from pesanan_murid_kit import KEADAAN_TERLAMBAT as DASAR

FRASA_TENGGAT = ("48 jam", "paling lambat", "sudah lewat janji")
DATA = peta_contoh_data.DATA_CONTOH


def _tanpa_potongan(isi: str) -> str:
    """Kartu tanpa kalimat potongan kelas bersama; kalimat itu di luar copy janji dan belum diubah."""
    return isi.replace(hv.COPY_POTONGAN, "")


# --- janji terbit pembeli (pesanan_voucher_pages) -----------------------------------------------

def test_teks_janji_belum_terbit_tanpa_tenggat_dan_tanpa_guru():
    # Arrange
    belum_terbit = replace(DASAR, terbit=None, terlambat=False)

    # Act
    janji = hv.teks_janji(belum_terbit)

    # Assert
    assert janji == hv.COPY_JANJI
    assert "langsung terbit setelah pembayaran terverifikasi" in janji
    assert not any(frasa in janji for frasa in FRASA_TENGGAT)
    assert "Guru" not in janji


def test_teks_janji_sudah_terbit_menyatakan_laporan_sudah_terbit():
    sudah_terbit = replace(DASAR, terbit="2026-11-26T09:00:00")
    assert hv.teks_janji(sudah_terbit) == hv.COPY_TERBIT


def test_bagian_laporan_kartu_terlambat_tanpa_guru_dan_tanpa_tenggat_48_jam():
    isi = _tanpa_potongan(hv.kartu_voucher(replace(DASAR, terbit=None, terlambat=True)))
    # Terlambat menggantikan janji: tidak boleh ada "langsung terbit" bersama "belum terbit".
    assert hv.COPY_TERLAMBAT in isi and hv.COPY_JANJI not in isi
    assert not any(frasa in isi for frasa in FRASA_TENGGAT)
    assert "Guru" not in isi


def test_kalimat_terlambat_tidak_menyebut_guru_dan_mengarahkan_ke_whatsapp():
    assert "WhatsApp" in hv.COPY_TERLAMBAT
    assert "Guru" not in hv.COPY_TERLAMBAT
    assert not any(frasa in hv.COPY_TERLAMBAT for frasa in FRASA_TENGGAT)


# --- contoh penjualan (funnel_contoh) ------------------------------------------------------------

def test_halaman_contoh_penjualan_memakai_mode_laporan_sistem():
    blok_sistem = ortu.blok_peta({**funnel_contoh.CONTOH_PETA_V1, "oleh_sistem": True})
    assert blok_sistem in funnel_contoh.halaman_contoh_peta().decode()


def test_blok_contoh_penjualan_tanpa_lencana_dan_catatan_guru():
    blok = ortu.blok_peta({**funnel_contoh.CONTOH_PETA_V1, "oleh_sistem": True})
    assert ortu.COPY_PENGANTAR_SISTEM in blok
    assert ortu.COPY_LENCANA not in blok and ortu.COPY_CATATAN_JUDUL not in blok
    assert "Guru" not in blok
    assert not any(frasa in blok for frasa in FRASA_TENGGAT)


def test_halaman_contoh_penjualan_tanpa_lencana_dan_catatan_guru_di_seluruh_halaman():
    halaman = funnel_contoh.halaman_contoh_peta().decode()
    assert ortu.COPY_LENCANA not in halaman and ortu.COPY_CATATAN_JUDUL not in halaman


# --- panel ringkasan laporan (peta_ringkasan) ----------------------------------------------------

def test_laporan_contoh_publik_tanpa_catatan_dan_nama_guru():
    isi = peta_laporan.render_laporan(DATA, contoh=True)
    assert "Catatan Guru" not in isi
    assert DATA.guru.nama not in isi
    assert "temuan utama" in isi and "temuan Guru" not in isi


def test_laporan_sungguhan_tetap_memuat_catatan_dan_nama_guru():
    isi = peta_laporan.render_laporan(DATA, contoh=False)
    assert "Catatan Guru" in isi and DATA.guru.nama in isi


def test_kartu_catatan_guru_kosong_untuk_contoh_walau_sudah_ditinjau():
    assert DATA.ditinjau and DATA.catatan_guru.strip()
    assert peta_ringkasan.kartu_catatan_guru(DATA, contoh=True) == ""


def test_kartu_catatan_guru_kosong_bila_catatan_hanya_spasi():
    tanpa_catatan = dataclasses.replace(DATA, catatan_guru="   ")
    assert peta_ringkasan.kartu_catatan_guru(tanpa_catatan, contoh=False) == ""


def test_kartu_lembar_ajak_memakai_kata_temuan_utama_bukan_guru():
    kartu = peta_ringkasan.kartu_lembar_ajak()
    assert "temuan utama" in kartu and "Guru" not in kartu
