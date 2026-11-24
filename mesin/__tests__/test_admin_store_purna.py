"""Store admin menolak (fail-closed) struktur purna_* yang parsial/berbeda; absen tetap sah."""
import sqlite3

import pytest

import admin_store
import schema_pesanan
import schema_purna
from transfer_kit import siapkan_db_transfer


def _buka(path):
    with admin_store.buka_baca(path):
        pass


def _ubah(path, sql):
    with sqlite3.connect(path) as kon:
        kon.execute("PRAGMA foreign_keys=OFF")
        kon.executescript(sql)


def test_db_tanpa_purna_tetap_terbuka(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    _buka(path)
    with admin_store.buka_baca(path) as kon:
        assert schema_purna.validasi(kon) is False


def test_db_tanpa_pesanan_dan_transfer_tetap_terbuka(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    _buka(path)


def test_db_dengan_purna_utuh_terbuka_baca_dan_tulis(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    schema_purna.migrasikan(path)
    _buka(path)
    with admin_store._transaksi(path):
        pass


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER purna_voucher_pakai_tolak_update",
    "DROP TRIGGER purna_laporan_terbit_lunas",
    "DROP TRIGGER purna_pilihan_terlambat_tolak_replace",
])
def test_purna_dengan_trigger_hilang_ditolak(tmp_path, rusak):
    path = siapkan_db_transfer(tmp_path)
    schema_purna.migrasikan(path)
    _ubah(path, rusak)
    with pytest.raises(admin_store.StoreBelumSiap, match="purna"):
        _buka(path)
    with pytest.raises(admin_store.StoreBelumSiap, match="purna"):
        with admin_store._transaksi(path):
            pass


def test_purna_dengan_tabel_hilang_ditolak(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    schema_purna.migrasikan(path)
    with sqlite3.connect(path) as kon:
        trigger = [r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='purna_laporan_terbit'")]
    _ubah(path, "".join("DROP TRIGGER %s;" % t for t in trigger) + "DROP TABLE purna_laporan_terbit;")
    with pytest.raises(admin_store.StoreBelumSiap, match="purna"):
        _buka(path)


def test_tabel_purna_liar_tanpa_ledger_ditolak(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    _ubah(path, "CREATE TABLE purna_voucher_pakai(x)")
    with pytest.raises(admin_store.StoreBelumSiap, match="purna"):
        _buka(path)


def test_purna_tanpa_transfer_ditolak(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    schema_pesanan.migrasikan(path)
    _ubah(path, schema_purna.DDL)
    with pytest.raises(admin_store.StoreBelumSiap):
        _buka(path)


def test_purna_tanpa_pesanan_dan_transfer_ditolak(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    _ubah(path, schema_purna.DDL)
    with pytest.raises(admin_store.StoreBelumSiap):
        _buka(path)
