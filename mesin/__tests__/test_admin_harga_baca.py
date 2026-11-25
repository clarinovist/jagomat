"""Model baca Harga admin (admin_harga_baca): nilai awal, sumber, setelah deposit, skema belum/rusak. Data SINTETIS."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_harga_baca as baca  # noqa: E402
import harga  # noqa: E402
import harga_aturan as a  # noqa: E402
from harga_kit import ADMIN, SEKARANG, siapkan_db_admin_saja, siapkan_db_harga  # noqa: E402


def _produk(tampilan, kode):
    return next(p for p in tampilan.produk if p.kode == kode)


def test_tanpa_skema_terpasang_false_dan_nilai_awal(tmp_path):
    tampilan = baca.muat(siapkan_db_admin_saja(tmp_path))
    assert tampilan.terpasang is False and tampilan.riwayat == ()
    assert _produk(tampilan, "private").rupiah == 640_000
    assert _produk(tampilan, "mini").rupiah == 300_000
    assert _produk(tampilan, "private").diubah == "" and _produk(tampilan, "private").setelah_deposit == 591_000


def test_peta_selalu_hanya_baca_tanpa_setelah_deposit(tmp_path):
    peta = _produk(baca.muat(siapkan_db_harga(tmp_path)), "peta")
    assert peta.bisa_diubah is False and peta.setelah_deposit is None and peta.rupiah == 49_000


def test_setelah_ubah_sumber_waktu_dan_riwayat_terbaru(tmp_path):
    path = siapkan_db_harga(tmp_path)
    harga.ubah_harga(path, "private", 700_000, 640_000, ADMIN, SEKARANG)
    tampilan = baca.muat(path)
    private = _produk(tampilan, "private")
    assert tampilan.terpasang is True and private.rupiah == 700_000 and private.diubah == SEKARANG
    assert private.setelah_deposit == 651_000
    assert _produk(tampilan, "mini").diubah == ""
    # lama = harga efektif sebelumnya (nilai awal saat pertama kali diubah); lihat harga.py.
    assert [(r.kode, r.lama, r.baru) for r in tampilan.riwayat] == [("private", 640_000, 700_000)]


def test_latihan_harian_dibaca_dari_katalog_harian(tmp_path):
    tampilan = baca.muat(siapkan_db_harga(tmp_path))
    assert {(b.kode, b.rupiah) for b in tampilan.harian} == {("bulanan", 39_000), ("tahunan", 349_000)}


def test_skema_rusak_melempar_value_error(tmp_path):
    path = siapkan_db_harga(tmp_path)
    kon = sqlite3.connect(path)
    try:
        kon.execute("DROP TRIGGER harga_riwayat_tolak_update")
        kon.commit()
    finally:
        kon.close()
    with pytest.raises(ValueError):
        baca.muat(path)


def test_batas_nilai_tetap_milik_harga_aturan():
    assert (a.HARGA_MIN, a.HARGA_MAKS, a.KELIPATAN) == (10_000, 9_000_000, 1_000)
