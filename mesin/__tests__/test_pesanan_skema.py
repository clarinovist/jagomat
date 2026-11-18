"""Skema pesanan: opt-in aditif, idempoten, fail-closed bila parsial, append-only."""
import sqlite3

import pytest

import admin_store
import pesanan
import schema_pesanan
from pesanan_kit import (AKUN_A, MERCHANT, SEKARANG, TRANSAKSI, buat,
                         hitung, operasi, ord_id, siapkan_db, snapshot_langganan,
                         terapkan)

HEX64 = "ab" * 32


def dump(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


@pytest.fixture
def db(tmp_path):
    return siapkan_db(tmp_path)


def test_siapkan_standar_tidak_memasang_pesanan_dan_absent_sah(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    with admin_store.buka_baca(path) as kon:
        assert schema_pesanan.validasi(kon) is False
        assert not schema_pesanan.struktur(kon)
    with pytest.raises(admin_store.StoreBelumSiap):
        with pesanan.buka(path):
            pass


def test_migrasi_idempoten_dan_user_version_tetap(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    with sqlite3.connect(path) as kon:
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
    schema_pesanan.migrasikan(path)
    pertama = dump(path)
    schema_pesanan.migrasikan(path)
    admin_store.siapkan(path, sekarang=99)
    assert dump(path) == pertama
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi
        assert schema_pesanan.validasi(kon) is True
        assert {r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'pesanan_*'")
        } == set(schema_pesanan.TABEL)
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()


def test_skema_parsial_atau_berbeda_ditolak_fail_closed(db):
    with sqlite3.connect(db) as kon:
        kon.execute("DROP TRIGGER pesanan_refund_tolak_update")
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(db):
            pass
    with pytest.raises(admin_store.StoreBelumSiap):
        with pesanan.buka(db, tulis_data=True):
            pass


def test_tabel_hilang_sebagian_ditolak(db):
    with sqlite3.connect(db) as kon:
        kon.execute("PRAGMA foreign_keys=OFF")
        for trg in [r[0] for r in kon.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='pesanan_yatim'")]:
            kon.execute("DROP TRIGGER %s" % trg)
        kon.execute("DROP TABLE pesanan_yatim")
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(db):
            pass


def test_langganan_tidak_tersentuh_oleh_migrasi(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    with sqlite3.connect(path) as kon:
        sebelum = snapshot_langganan(kon)
        struktur_lama = tuple(kon.execute(
            "SELECT name,sql FROM sqlite_master WHERE name GLOB 'langganan_*' ORDER BY name"))
    schema_pesanan.migrasikan(path)
    with sqlite3.connect(path) as kon:
        assert snapshot_langganan(kon) == sebelum
        assert tuple(kon.execute(
            "SELECT name,sql FROM sqlite_master WHERE name GLOB 'langganan_*' ORDER BY name")
        ) == struktur_lama


def _isi_semua(kon):
    """Satu baris di tiap tabel bukti (order, pengamatan, receipt, refund, yatim)."""
    order = buat(kon, 1)
    terapkan(kon, order, 1)
    pesanan.catat_refund(kon, order["order_id"], operasi(2), "admin_a", "kebijakan", SEKARANG)
    pesanan.catat_yatim(kon, "ord_tidak_dikenal", "settlement", HEX64, SEKARANG, operasi(3))


@pytest.mark.parametrize("tabel", schema_pesanan.TABEL)
@pytest.mark.parametrize("aksi,sql", [
    ("update", "UPDATE {t} SET dibuat='2030-01-01T00:00:00'"),
    ("delete", "DELETE FROM {t}"),
])
def test_tabel_bukti_tolak_update_dan_delete(db, tabel, aksi, sql):
    with pesanan.buka(db, tulis_data=True) as kon:
        _isi_semua(kon)
        assert hitung(kon, tabel) >= 1
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            kon.execute(sql.format(t=tabel))
        kon.rollback()
        assert hitung(kon, tabel) >= 1


def test_insert_or_replace_ditolak_pada_semua_kunci_unik(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order = buat(kon, 1)
        terapkan(kon, order, 1)
        sebelum = dump(db)
        kunci_ganda = [
            "INSERT OR REPLACE INTO pesanan_order SELECT * FROM pesanan_order",
            "INSERT OR REPLACE INTO pesanan_jendela SELECT * FROM pesanan_jendela",
            "INSERT OR REPLACE INTO pesanan_pengamatan SELECT * FROM pesanan_pengamatan",
            "INSERT OR REPLACE INTO pesanan_receipt SELECT * FROM pesanan_receipt",
        ]
        for sql in kunci_ganda:
            with pytest.raises(sqlite3.IntegrityError, match="duplikat|berurutan"):
                kon.execute(sql)
        kon.rollback()
    assert dump(db) == sebelum


def test_kunci_unik_tingkat_db_siswa_idempotency_dan_receipt_per_order(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order = buat(kon, 1)
        terapkan(kon, order, 1)
        salin = ("INSERT INTO pesanan_order(order_id,akun_id,siswa_id,cek_id,rupiah,currency,"
                 "provider,channel,merchant,idempotency_key,dibuat,kedaluwarsa) "
                 "VALUES(?,?,?,?,49000,'IDR','midtrans','qris',?,?,?,?)")
        dasar = (AKUN_A, 9, 9, MERCHANT, "ord-x-%026d" % 9, SEKARANG, "2026-11-19T10:00:00")
        kon.execute(salin, (ord_id(9),) + dasar)   # bukti: baris dasar sah
        for ganti in (dict(siswa=1), dict(kunci=order["idempotency_key"])):
            argumen = list(dasar)
            argumen[1] = ganti.get("siswa", 10)
            argumen[4] = ganti.get("kunci", "ord-y-%026d" % 10)
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(salin, (ord_id(10),) + tuple(argumen))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO pesanan_receipt VALUES('midtrans','trx-lain',?,'lunas',49000,'ok',?)",
                        (order["order_id"], SEKARANG))
        kon.rollback()


def test_receipt_lunas_wajib_nominal_sama_dengan_order_di_tingkat_db(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        order = buat(kon, 1)
        with pytest.raises(sqlite3.IntegrityError, match="tidak cocok"):
            kon.execute("INSERT INTO pesanan_receipt VALUES('midtrans',?,?,'lunas',48000,'ok',?)",
                        (TRANSAKSI, order["order_id"], SEKARANG))
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("INSERT INTO pesanan_receipt VALUES('midtrans',?,?,'lunas',49000,'nominal',?)",
                        (TRANSAKSI, order["order_id"], SEKARANG))
        kon.rollback()


def test_check_format_order_dan_nominal_di_tingkat_db(db):
    sisip = ("INSERT INTO pesanan_order(order_id,akun_id,siswa_id,cek_id,rupiah,currency,provider,"
             "channel,merchant,idempotency_key,dibuat,kedaluwarsa) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)")
    sah = [ord_id(1), AKUN_A, 1, 1, 49000, "IDR", "midtrans", "qris", MERCHANT,
           "ord-" + "1" * 32, SEKARANG, "2026-11-19T10:00:00"]
    buruk = [(0, "inv_" + "1" * 32), (1, "akun_zz"), (4, 0), (4, 10000001), (5, "USD"),
             (6, "lain"), (7, "kartu"), (9, "pendek"), (11, SEKARANG)]
    with pesanan.buka(db, tulis_data=True) as kon:
        for indeks, nilai in buruk:
            argumen = list(sah)
            argumen[indeks] = nilai
            with pytest.raises(sqlite3.IntegrityError):
                kon.execute(sisip, argumen)
        kon.rollback()
        assert hitung(kon, "pesanan_order") == 0



def test_jendela_pertama_ada_untuk_setiap_order_dan_tabel_jendela_dikenali_skema(db):
    assert "pesanan_jendela" in schema_pesanan.TABEL
    with pesanan.buka(db, tulis_data=True) as kon:
        order = buat(kon, 1)
        baris = kon.execute("SELECT order_id,urutan,idempotency_key,operasi_id FROM pesanan_jendela"
                            ).fetchall()
        assert [tuple(b) for b in baris] == [(order["order_id"], 1, order["idempotency_key"], None)]


def test_trigger_jendela_dihapus_membuat_skema_ditolak(db):
    with sqlite3.connect(db) as kon:
        kon.execute("DROP TRIGGER pesanan_jendela_berurutan")
    with pytest.raises(admin_store.StoreBelumSiap):
        with pesanan.buka(db):
            pass
