"""Skema harga_*: DDL terpasang persis, validasi absen/parsial/beda, CHECK, dan riwayat append-only."""
import sqlite3

import pytest

import admin_store
import schema_harga
import schema_pesanan
import schema_purna
import schema_transfer
from harga_kit import ADMIN, SEKARANG, siapkan_db_admin_saja, siapkan_db_harga
from purna_kit import siapkan_db_purna

TABEL_HARGA = {"harga_produk", "harga_riwayat"}
TRIGGER_RIWAYAT = {"harga_riwayat_tolak_update", "harga_riwayat_tolak_delete", "harga_riwayat_tolak_replace"}


def hubungkan(path):
    return sqlite3.connect(str(path))


def sisip_riwayat(path, kode="private", lama=None, baru=600_000):
    kon = hubungkan(path)
    try:
        kon.execute("INSERT INTO harga_riwayat(kode,lama,baru,oleh,waktu) VALUES(?,?,?,?,?)",
                    (kode, lama, baru, ADMIN, SEKARANG))
        kon.commit()
    finally:
        kon.close()


def harus_abort(path, sql, params, pesan):
    kon = hubungkan(path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match=pesan):
            kon.execute(sql, params)
        kon.rollback()
    finally:
        kon.close()


def objek_harga(path):
    kon = hubungkan(path)
    try:
        return {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE tbl_name GLOB 'harga_*'")}
    finally:
        kon.close()


@pytest.fixture
def db(tmp_path):
    return siapkan_db_harga(tmp_path)


def test_belum_dipasang_validasi_false_dan_tanpa_objek(tmp_path):
    path = siapkan_db_admin_saja(tmp_path)
    kon = hubungkan(path)
    try:
        assert schema_harga.validasi(kon) is False
        assert schema_harga.struktur(kon) == ()
    finally:
        kon.close()


def test_migrasikan_memasang_dua_tabel_dan_tiga_trigger(db):
    objek = objek_harga(db)
    assert {n for n in objek if n in TABEL_HARGA} == TABEL_HARGA
    assert TRIGGER_RIWAYAT <= objek


def test_migrasikan_idempoten_dan_tidak_mengubah_user_version(tmp_path):
    path = siapkan_db_admin_saja(tmp_path)
    kon = hubungkan(path)
    versi_awal = kon.execute("PRAGMA user_version").fetchone()[0]
    kon.close()
    schema_harga.migrasikan(path)
    struktur_pertama = objek_harga(path)
    schema_harga.migrasikan(path)
    kon = hubungkan(path)
    try:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi_awal
        assert schema_harga.validasi(kon) is True
    finally:
        kon.close()
    assert objek_harga(path) == struktur_pertama


def test_validasi_menolak_trigger_hilang_dengan_valueerror(db):
    kon = hubungkan(db)
    kon.execute("DROP TRIGGER harga_riwayat_tolak_update")
    kon.commit()
    try:
        with pytest.raises(ValueError):
            schema_harga.validasi(kon)
    finally:
        kon.close()


def test_validasi_menolak_objek_asing_di_namespace_harga(db):
    kon = hubungkan(db)
    kon.execute("CREATE INDEX harga_asing ON harga_produk(rupiah)")
    kon.commit()
    try:
        with pytest.raises(ValueError):
            schema_harga.validasi(kon)
    finally:
        kon.close()


def test_check_rupiah_menolak_di_luar_rentang_dan_bukan_kelipatan(db):
    harus_abort(db, "INSERT INTO harga_produk VALUES('private',9001000,?,?)", (SEKARANG, ADMIN), "CHECK")
    harus_abort(db, "INSERT INTO harga_produk VALUES('private',640500,?,?)", (SEKARANG, ADMIN), "CHECK")
    harus_abort(db, "INSERT INTO harga_produk VALUES('private',9999,?,?)", (SEKARANG, ADMIN), "CHECK")


def test_check_kode_hanya_tiga_produk(db):
    harus_abort(db, "INSERT INTO harga_produk VALUES('harian',39000,?,?)", (SEKARANG, ADMIN), "CHECK")


def test_check_oleh_dan_waktu_menolak_panjang_dan_format_z(db):
    harus_abort(db, "INSERT INTO harga_produk VALUES('mini',300000,?,?)", (SEKARANG, "a" * 101), "CHECK")
    harus_abort(db, "INSERT INTO harga_produk VALUES('mini',300000,?,?)",
                ("2026-11-25T08:00:00Z", ADMIN), "CHECK")


def test_harga_produk_boleh_diperbarui_tanpa_trigger(db):
    kon = hubungkan(db)
    try:
        kon.execute("INSERT INTO harga_produk VALUES('mini',300000,?,?)", (SEKARANG, ADMIN))
        kon.execute("UPDATE harga_produk SET rupiah=310000 WHERE kode='mini'")
        kon.commit()
        assert kon.execute("SELECT rupiah FROM harga_produk WHERE kode='mini'").fetchone()[0] == 310_000
    finally:
        kon.close()


def test_riwayat_menerima_baris_baru(db):
    sisip_riwayat(db)
    kon = hubungkan(db)
    try:
        assert kon.execute("SELECT COUNT(*) FROM harga_riwayat").fetchone()[0] == 1
    finally:
        kon.close()


def test_riwayat_menolak_update_append_only(db):
    sisip_riwayat(db)
    harus_abort(db, "UPDATE harga_riwayat SET baru=1 WHERE id=1", (), "immutable")


def test_riwayat_menolak_delete_append_only(db):
    sisip_riwayat(db)
    harus_abort(db, "DELETE FROM harga_riwayat WHERE id=1", (), "immutable")


def test_riwayat_menolak_insert_or_replace_pada_id_sama(db):
    sisip_riwayat(db)
    harus_abort(db, "INSERT OR REPLACE INTO harga_riwayat(id,kode,lama,baru,oleh,waktu) VALUES(1,'mini',NULL,300000,?,?)",
                (ADMIN, SEKARANG), "duplikat")


def test_rollback_aman_pesanan_transfer_purna_tetap_valid(tmp_path):
    path = siapkan_db_purna(tmp_path)
    schema_harga.migrasikan(path)
    kon = hubungkan(path)
    try:
        assert schema_pesanan.validasi(kon) is True
        assert schema_transfer.validasi(kon) is True
        assert schema_purna.validasi(kon) is True
    finally:
        kon.close()
    with admin_store.buka_baca(path) as baca:
        assert baca.execute("SELECT COUNT(*) FROM harga_produk").fetchone()[0] == 0


def test_tanpa_baris_seed_setelah_migrasi(db):
    kon = hubungkan(db)
    try:
        assert kon.execute("SELECT COUNT(*) FROM harga_produk").fetchone()[0] == 0
    finally:
        kon.close()
