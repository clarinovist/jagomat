"""Domain harga: nominal proporsional, nilai aktif gagal aman, ubah harga, riwayat, dan penjaga drift katalog."""
import contextlib
import dataclasses
import sqlite3

import pytest

import admin_store_core
import harga
import paket_belajar_katalog as katalog
import pesanan_dasar
from harga_kit import ADMIN, SEKARANG, SESUDAH, siapkan_db_admin_saja, siapkan_db_harga


@pytest.fixture
def db(tmp_path):
    return siapkan_db_harga(tmp_path)


@contextlib.contextmanager
def ro(path):
    kon = admin_store_core.koneksi(path, "ro")
    try:
        yield kon
    finally:
        kon.close()


@pytest.mark.parametrize("harga_bulanan,sisa,diharapkan", [
    (300_000, 7, 262_500),
    (300_000, 5, 187_500),
    (300_000, 8, 300_000),
    (300_000, 6, 225_000),
    (4, 5, 3),
])
def test_proporsional_pembulatan_setengah_naik(harga_bulanan, sisa, diharapkan):
    assert harga.nominal_proporsional(harga_bulanan, sisa) == diharapkan


@pytest.mark.parametrize("sisa", [4, 9, 0])
def test_proporsional_menolak_sisa_di_luar_rentang(sisa):
    with pytest.raises(ValueError, match="sisa"):
        harga.nominal_proporsional(300_000, sisa)


def test_proporsional_menolak_bool_sebagai_sisa():
    with pytest.raises(ValueError, match="sisa"):
        harga.nominal_proporsional(300_000, True)


def test_harga_awal_cocok_katalog_paket_belajar():
    assert harga.HARGA_AWAL["private"] == katalog.HARGA_PRIVATE_PER_PERTEMUAN * katalog.PERTEMUAN_PER_BULAN
    assert harga.HARGA_AWAL["mini"] == katalog.HARGA_MINI


def test_pertemuan_per_bulan_cocok_katalog():
    assert harga.PERTEMUAN_PER_BULAN == katalog.PERTEMUAN_PER_BULAN


def test_harga_awal_peta_sama_dengan_pesanan_dasar_dan_deposit():
    assert harga.HARGA_AWAL["peta"] == pesanan_dasar.RUPIAH_PAKET == katalog.RUPIAH_DEPOSIT


def test_harga_awal_tak_bisa_diubah():
    with pytest.raises(TypeError):
        harga.HARGA_AWAL["private"] = 1


def test_skema_belum_terpasang_memakai_nilai_awal_tanpa_membuat_objek(tmp_path):
    path = siapkan_db_admin_saja(tmp_path)
    with ro(path) as kon:
        semua = dict(harga.harga_semua(kon))
        aktif = harga.harga_aktif(kon, "private")
        objek = kon.execute("SELECT name FROM sqlite_master WHERE tbl_name GLOB 'harga_*'").fetchall()
    assert semua == dict(harga.HARGA_AWAL)
    assert aktif == 640_000
    assert objek == []


def test_baris_tak_ada_memakai_nilai_awal(db):
    with ro(db) as kon:
        assert dict(harga.harga_semua(kon)) == dict(harga.HARGA_AWAL)


def test_skema_rusak_melempar_bukan_nilai_awal(db):
    raw = sqlite3.connect(str(db))
    try:
        raw.execute("DROP TRIGGER harga_riwayat_tolak_update")
        raw.commit()
    finally:
        raw.close()
    with ro(db) as kon:
        with pytest.raises(ValueError):
            harga.harga_aktif(kon, "private")


def test_kode_tak_dikenal_ditolak_pada_baca(db):
    with ro(db) as kon:
        with pytest.raises(ValueError, match="kode"):
            harga.harga_aktif(kon, "harian")


def test_ubah_harga_menulis_produk_dan_riwayat_dengan_lama_nilai_awal(db):
    hasil = harga.ubah_harga(db, "private", 600_000, 640_000, ADMIN, SEKARANG)
    assert hasil == harga.HasilUbahHarga("private", 640_000, 600_000)
    with ro(db) as kon:
        assert harga.harga_aktif(kon, "private") == 600_000
        riwayat = harga.riwayat(kon)
    assert len(riwayat) == 1
    assert (riwayat[0].kode, riwayat[0].lama, riwayat[0].baru) == ("private", 640_000, 600_000)
    assert (riwayat[0].oleh, riwayat[0].waktu) == (ADMIN, SEKARANG)


def test_revisi_kedua_mencatat_lama_harga_efektif_sebelumnya(db):
    harga.ubah_harga(db, "private", 600_000, 640_000, ADMIN, SEKARANG)
    hasil = harga.ubah_harga(db, "private", 620_000, 600_000, ADMIN, SESUDAH)
    assert hasil.lama == 600_000
    with ro(db) as kon:
        riwayat = harga.riwayat(kon)
    assert [(r.lama, r.baru) for r in riwayat] == [(600_000, 620_000), (640_000, 600_000)]


def test_konflik_revisi_tidak_menulis(db):
    with pytest.raises(harga.KonflikHarga):
        harga.ubah_harga(db, "private", 600_000, 999_000, ADMIN, SEKARANG)
    with ro(db) as kon:
        assert harga.harga_aktif(kon, "private") == 640_000
        assert harga.riwayat(kon) == ()


def test_skema_belum_terpasang_ditolak_tanpa_membuat_tabel(tmp_path):
    path = siapkan_db_admin_saja(tmp_path)
    with pytest.raises(harga.HargaBelumTerpasang):
        harga.ubah_harga(path, "private", 600_000, 640_000, ADMIN, SEKARANG)
    with ro(path) as kon:
        assert kon.execute("SELECT name FROM sqlite_master WHERE tbl_name GLOB 'harga_*'").fetchall() == []


def test_peta_tidak_bisa_diubah_dan_tidak_menulis(db):
    with pytest.raises(ValueError, match="Peta belum bisa diatur"):
        harga.ubah_harga(db, "peta", 50_000, 49_000, ADMIN, SEKARANG)
    with ro(db) as kon:
        assert harga.riwayat(kon) == ()


def test_nilai_tak_valid_tidak_menulis_satu_pun(db):
    with pytest.raises(ValueError, match="rentang"):
        harga.ubah_harga(db, "private", 9_501_000, 640_000, ADMIN, SEKARANG)
    with ro(db) as kon:
        assert harga.harga_aktif(kon, "private") == 640_000
        assert harga.riwayat(kon) == ()


@pytest.mark.parametrize("oleh", ["", "   ", "a" * 101, "admin\n"])
def test_oleh_tak_sah_ditolak_sebelum_transaksi(db, oleh):
    with pytest.raises(ValueError, match="oleh"):
        harga.ubah_harga(db, "private", 600_000, 640_000, oleh, SEKARANG)


@pytest.mark.parametrize("waktu", ["2026-11-25T08:00:00Z", "2026-11-25 08:00:00"])
def test_waktu_tak_sah_ditolak(db, waktu):
    with pytest.raises(ValueError, match="waktu"):
        harga.ubah_harga(db, "private", 600_000, 640_000, ADMIN, waktu)


def test_riwayat_terbaru_dulu_dan_membatasi_jumlah(db):
    harga.ubah_harga(db, "private", 600_000, 640_000, ADMIN, SEKARANG)
    harga.ubah_harga(db, "private", 610_000, 600_000, ADMIN, SESUDAH)
    harga.ubah_harga(db, "private", 620_000, 610_000, ADMIN, SESUDAH)
    with ro(db) as kon:
        semua = harga.riwayat(kon)
        dua = harga.riwayat(kon, batas=2)
    assert [r.baru for r in semua] == [620_000, 610_000, 600_000]
    assert [r.baru for r in dua] == [620_000, 610_000]


def test_riwayat_tanpa_skema_kosong(tmp_path):
    path = siapkan_db_admin_saja(tmp_path)
    with ro(path) as kon:
        assert harga.riwayat(kon) == ()


@pytest.mark.parametrize("batas", [0, -1, True])
def test_riwayat_batas_tak_sah_ditolak(db, batas):
    with ro(db) as kon:
        with pytest.raises(ValueError, match="batas"):
            harga.riwayat(kon, batas=batas)


def test_hasil_dan_riwayat_tak_berubah(db):
    hasil = harga.ubah_harga(db, "mini", 310_000, 300_000, ADMIN, SEKARANG)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hasil.baru = 1
    with ro(db) as kon:
        catatan = harga.riwayat(kon)[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        catatan.baru = 1
