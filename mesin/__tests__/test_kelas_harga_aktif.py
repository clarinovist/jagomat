"""Harga aktif admin dibaca tagihan dan kartu paket kelas; tagihan yang sudah dibuat tidak berubah. Data sintetis.

Bagian pertama memakai DB kelas tanpa tabel harga_* (perilaku lama harus identik). Bagian berikutnya memasang
schema_harga dan mengubah harga lewat harga.ubah_harga. Bagian unit katalog memakai API baru (paket_dengan_harga,
hitung_rincian dengan harga_paket); merahnya di sana berupa TypeError/AttributeError, sengaja.
"""
from __future__ import annotations

import sqlite3

import pytest

import harga
import kelas_pages
import kelas_store
import paket_belajar_katalog as katalog
import schema_harga
from harga_kit import ADMIN as ADMIN_HARGA, SEKARANG
from kelas_kit import (AKUN_A, KINI, db_kelas, kon_kelas, peta_lunas, siapkan_db_kelas, tagih)  # noqa: F401

MINI_BARU = 320_000
PRIVATE_BARU = 700_000
DEPOSIT_PETA = 49_000
TOKEN_SINTETIS = "token-sintetis"


def db_harga(tmp_path):
    """DB kelas dengan tabel harga_* terpasang; kosong = nilai awal HARGA_AWAL sampai admin mengubah harga."""
    path = siapkan_db_kelas(tmp_path)
    schema_harga.migrasikan(path)
    return path


@pytest.fixture
def db_harga_kelas(tmp_path):
    return db_harga(tmp_path)


def ubah(path, kode, baru, lama):
    return harga.ubah_harga(path, kode, baru, lama, ADMIN_HARGA, SEKARANG)


def kartu(kon, siswa=1, akun=AKUN_A, sekarang=KINI):
    return {c.paket.kode: c for c in kelas_store.kartu_paket(kon, akun, siswa, sekarang)}


def _rusakkan_harga(path):
    """Hapus trigger append-only harga_riwayat: skema harga menjadi parsial, validasi melempar ValueError."""
    koneksi = sqlite3.connect(path)
    try:
        koneksi.execute("DROP TRIGGER harga_riwayat_tolak_update")
        koneksi.commit()
    finally:
        koneksi.close()


def _jumlah_tagihan(kon):
    order = kon.execute("SELECT COUNT(*) FROM kelas_order").fetchone()[0]
    tagihan = kon.execute("SELECT COUNT(*) FROM kelas_tagihan").fetchone()[0]
    return order, tagihan


# --- tanpa tabel harga_*: perilaku lama harus identik ----------------------------------------------

def test_tanpa_harga_terpasang_kartu_memakai_harga_katalog(kon_kelas):
    kartu_kode = kartu(kon_kelas)
    assert kartu_kode["mini"].paket.harga == 300_000
    assert kartu_kode["private"].paket.harga == 640_000
    assert kartu_kode["mini"].rincian.nominal == 300_000
    assert kartu_kode["private"].rincian.nominal == 640_000


def test_tanpa_harga_terpasang_deposit_peta_memotong_591000_dan_251000(kon_kelas):
    peta_lunas(kon_kelas, 1)
    kartu_kode = kartu(kon_kelas)
    assert kartu_kode["private"].rincian.nominal == 591_000
    assert kartu_kode["mini"].rincian.nominal == 251_000
    assert kartu_kode["mini"].rincian.potongan_deposit == DEPOSIT_PETA


def test_tanpa_harga_terpasang_tagihan_mini_300000(kon_kelas):
    tagihan = tagih(kon_kelas, 1, "mini")
    assert tagihan.rincian.harga_dasar == 300_000
    assert tagihan.total == 300_000 + tagihan.kode_unik


# --- harga aktif dipasang lewat harga.ubah_harga ------------------------------------------------------

def test_tagihan_baru_memakai_harga_mini_aktif(db_harga_kelas):
    ubah(db_harga_kelas, "mini", MINI_BARU, 300_000)
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        tagihan = tagih(kon, 1, "mini")
    assert tagihan.rincian.harga_dasar == MINI_BARU
    assert tagihan.rincian.nominal == MINI_BARU
    assert 1 <= tagihan.kode_unik <= 999
    assert tagihan.total == MINI_BARU + tagihan.kode_unik


def test_kode_unik_tagihan_harga_aktif_unik_antar_anak(db_harga_kelas):
    ubah(db_harga_kelas, "mini", MINI_BARU, 300_000)
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        pertama = tagih(kon, 1, "mini")
        kedua = tagih(kon, 2, "mini")
    assert (pertama.total, kedua.total) == (320_001, 320_002)


def test_kartu_menampilkan_harga_aktif_dan_rincian_seragam(db_harga_kelas):
    ubah(db_harga_kelas, "private", PRIVATE_BARU, 640_000)
    ubah(db_harga_kelas, "mini", MINI_BARU, 300_000)
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        peta_lunas(kon, 1)
        kartu_kode = kartu(kon)
    private, mini = kartu_kode["private"], kartu_kode["mini"]
    assert private.paket.harga == PRIVATE_BARU == private.rincian.harga_dasar
    assert private.rincian.potongan_deposit == DEPOSIT_PETA
    assert private.rincian.nominal == 651_000
    assert mini.paket.harga == MINI_BARU == mini.rincian.harga_dasar
    assert mini.rincian.potongan_deposit == DEPOSIT_PETA
    assert mini.rincian.nominal == 271_000


def test_harga_diubah_setelah_tagihan_tidak_mengubah_tagihan_lama(db_harga_kelas):
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        lama = tagih(kon, 1, "mini")
    ubah(db_harga_kelas, "mini", MINI_BARU, 300_000)
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        dibaca = kelas_store.tagihan_terbuka(kon, AKUN_A, 1, "mini", KINI)
        baru = tagih(kon, 2, "mini")
    assert dibaca is not None
    assert (dibaca.rincian.harga_dasar, dibaca.rincian.nominal, dibaca.total) == (300_000, 300_000, lama.total)
    assert dibaca.kode_unik == lama.kode_unik
    assert baru.rincian.harga_dasar == MINI_BARU


def test_kartu_dengan_tagihan_terbuka_memakai_harga_tersimpan(db_harga_kelas):
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        tagih(kon, 1, "mini")
    ubah(db_harga_kelas, "mini", MINI_BARU, 300_000)
    with kelas_store.buka(db_harga_kelas) as kon:
        mini = kartu(kon)["mini"]
    assert mini.ada_tagihan_terbuka is True
    assert mini.paket.harga == 300_000 == mini.rincian.harga_dasar


def test_halaman_tagihan_menampilkan_harga_tersimpan(db_harga_kelas):
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        tagih(kon, 1, "mini")
    ubah(db_harga_kelas, "mini", MINI_BARU, 300_000)
    with kelas_store.buka(db_harga_kelas) as kon:
        tagihan = kelas_store.tagihan_terbuka(kon, AKUN_A, 1, "mini", KINI)
    isi = kelas_pages.halaman_tagihan(tagihan, katalog.ambil("mini"), "Bank: sintetis",
                                      lambda aksi: TOKEN_SINTETIS).decode("utf-8")
    assert "Rp300.000" in isi
    assert "Rp320.000" not in isi


# --- galat skema harga rusak: gagal tertutup untuk tagihan baru ----------------------------------------

def test_buat_tagihan_gagal_tertutup_saat_skema_harga_rusak(db_harga_kelas):
    _rusakkan_harga(db_harga_kelas)
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        sebelum = _jumlah_tagihan(kon)
        with pytest.raises(ValueError):
            tagih(kon, 1, "mini")
        assert _jumlah_tagihan(kon) == sebelum
        assert kon.in_transaction is False


def test_kartu_gagal_tertutup_saat_skema_harga_rusak(db_harga_kelas):
    _rusakkan_harga(db_harga_kelas)
    with kelas_store.buka(db_harga_kelas) as kon:
        with pytest.raises(ValueError):
            kelas_store.kartu_paket(kon, AKUN_A, 1, KINI)


def test_tagihan_terbuka_lama_tetap_terbaca_saat_skema_harga_rusak(db_harga_kelas):
    with kelas_store.buka(db_harga_kelas, tulis_data=True) as kon:
        tagih(kon, 1, "mini")
    _rusakkan_harga(db_harga_kelas)
    with kelas_store.buka(db_harga_kelas) as kon:
        tagihan = kelas_store.tagihan_terbuka(kon, AKUN_A, 1, "mini", KINI)
    assert tagihan.rincian.harga_dasar == 300_000


# --- unit katalog (fungsi murni, tanpa DB): API baru, merah sebagai TypeError/AttributeError -------------

def test_hitung_rincian_memakai_harga_paket_yang_diberikan():
    rincian = katalog.hitung_rincian("mini", deposit_aktif=False, harga_paket=MINI_BARU)
    assert (rincian.harga_dasar, rincian.potongan_deposit, rincian.nominal) == (MINI_BARU, 0, MINI_BARU)


def test_hitung_rincian_tanpa_harga_paket_tetap_harga_katalog():
    assert katalog.hitung_rincian("mini", deposit_aktif=True, harga_paket=None) == \
        katalog.hitung_rincian("mini", deposit_aktif=True)
    assert katalog.hitung_rincian("mini", deposit_aktif=True).nominal == 251_000


@pytest.mark.parametrize("nilai", [True, False, 0, -1, 320_000.0, "320000"])
def test_hitung_rincian_menolak_harga_paket_bukan_bilangan_bulat_positif(nilai):
    with pytest.raises(ValueError):
        katalog.hitung_rincian("mini", deposit_aktif=False, harga_paket=nilai)


def test_hitung_rincian_menolak_nominal_tidak_positif_setelah_deposit():
    with pytest.raises(ValueError):
        katalog.hitung_rincian("mini", deposit_aktif=True, harga_paket=DEPOSIT_PETA)


def test_paket_dengan_harga_menyalin_tanpa_mengubah_katalog():
    salinan = katalog.paket_dengan_harga("mini", MINI_BARU)
    assert salinan.harga == MINI_BARU
    assert (salinan.kode, salinan.kuota, salinan.pertemuan) == ("mini", 5, 8)
    assert katalog.ambil("mini").harga == 300_000


# --- copy harga Mini di contoh Peta publik (peta_misi -> funnel_contoh -> funnel_http) ---------------

COPY_MINI_300 = "Rp300.000 per bulan, 8 pertemuan."


def test_copy_peta_default_tetap_rp300000():
    import funnel_contoh
    import peta_misi
    assert COPY_MINI_300 in peta_misi._program("")
    assert COPY_MINI_300 in funnel_contoh.halaman_contoh_peta().decode("utf-8")


def test_copy_peta_memakai_harga_mini_aktif():
    import funnel_contoh
    isi = funnel_contoh.halaman_contoh_peta(harga_mini=MINI_BARU).decode("utf-8")
    assert "Rp320.000 per bulan, 8 pertemuan." in isi
    assert COPY_MINI_300 not in isi


def test_harga_mini_publik_membaca_harga_aktif(tmp_path, monkeypatch):
    import admin_store
    import funnel_http
    from harga_kit import siapkan_db_harga
    path = siapkan_db_harga(tmp_path)
    harga.ubah_harga(path, "mini", MINI_BARU, 300_000, ADMIN_HARGA, SEKARANG)
    monkeypatch.setattr(admin_store, "BAWAAN", path)
    assert funnel_http._harga_mini_aktif() == MINI_BARU


def test_harga_mini_publik_tanpa_tabel_harga_memakai_katalog(tmp_path, monkeypatch):
    import admin_store
    import funnel_http
    from harga_kit import siapkan_db_admin_saja
    monkeypatch.setattr(admin_store, "BAWAAN", siapkan_db_admin_saja(tmp_path))
    assert funnel_http._harga_mini_aktif() == 300_000


def test_harga_mini_publik_galat_skema_jatuh_ke_katalog_tanpa_500(tmp_path, monkeypatch):
    import admin_store
    import funnel_http
    from harga_kit import siapkan_db_harga
    path = siapkan_db_harga(tmp_path)
    _rusakkan_harga(path)
    monkeypatch.setattr(admin_store, "BAWAAN", path)
    assert funnel_http._harga_mini_aktif() is None
