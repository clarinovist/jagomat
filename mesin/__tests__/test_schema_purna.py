"""Skema purna_*: aditif di atas pesanan v1 + transfer_*, fail-closed, append-only, guard tingkat DB.

Skenario guard ditulis sebagai fungsi `skenario_*(kon)` yang melempar `GuardSalah` bila DB tidak
berperilaku sesuai aturan. Tes biasa menjalankannya pada DB yang dimigrasikan `schema_purna.migrasikan`;
tes mutation menjalankan skenario YANG SAMA pada salinan sementara yang DDL-nya sudah dilucuti satu guard
dan menuntut `GuardSalah` (merah karena asersi guard, bukan karena fixture/import rusak).
"""
import contextlib
from pathlib import Path
import re
import sqlite3

import pytest

import admin_store
import admin_store_core
import pesanan
import pesanan_transfer as tf
import schema_pesanan
import schema_purna
import schema_transfer
from pesanan_kit import SEKARANG, buat, hitung, operasi, siapkan_db, terapkan
from transfer_kit import ADMIN, menunggu, siapkan_db_transfer

WAKTU_SETUJU = "2026-11-18T12:00:00"
TABEL_PURNA = ("purna_voucher_pakai", "purna_laporan_terbit")
TERBIT_SAH = "2026-11-20T10:00:00"   # sesudah waktu lunas fixture (QRIS 18 Nov 10:00, transfer 18 Nov 12:00)


class GuardSalah(AssertionError):
    """Guard DB tidak berperilaku sesuai aturan (tidak menolak, salah pesan, atau salah menolak)."""


def harus_abort(kon, sql, params, pesan):
    try:
        kon.execute(sql, params)
    except sqlite3.IntegrityError as galat:
        if pesan not in str(galat):
            raise GuardSalah("pesan abort %r tidak memuat %r" % (str(galat), pesan))
        return
    raise GuardSalah("tidak ditolak: %s" % sql)


def harus_lolos(kon, sql, params):
    try:
        kon.execute(sql, params)
    except sqlite3.IntegrityError as galat:
        raise GuardSalah("salah ditolak (%s): %s" % (galat, sql))


def dump(path):
    with contextlib.closing(sqlite3.connect(path)) as kon:
        return tuple(kon.iterdump())


def struktur_ns(path, glob):
    with contextlib.closing(sqlite3.connect(path)) as kon:
        return tuple(tuple(r) for r in kon.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE tbl_name GLOB ? "
            "ORDER BY type,name", (glob,)))


def siapkan_db_purna(tmp_path, ddl=None):
    """DB sintetis pesanan + transfer + purna (lewat migrasikan, atau DDL termutasi bila diberikan)."""
    path = siapkan_db_transfer(tmp_path)
    if ddl is None:
        schema_purna.migrasikan(path)
        return path
    with contextlib.closing(sqlite3.connect(path)) as kon:
        kon.executescript(ddl)
    return path


# --- fixture order sintetis ---------------------------------------------------------------

def order_qris_lunas(kon, n):
    order = buat(kon, n)
    terapkan(kon, order, n, transaction_id="trx-sintetis-%04d" % n)
    return order["order_id"]


def order_transfer_lunas(kon, n):
    order, _ = menunggu(kon, n)
    tf.setujui(kon, order["order_id"], ADMIN, WAKTU_SETUJU)
    return order["order_id"]


def order_belum_lunas(kon, n):
    return buat(kon, n)["order_id"]


def order_receipt_perlu_diperiksa(kon, n):
    order = buat(kon, n)
    terapkan(kon, order, n, transaction_id="trx-sintetis-%04d" % n, gross_amount="1000.00")
    return order["order_id"]


def refund(kon, order_id, n):
    pesanan.catat_refund(kon, order_id, operasi(n), ADMIN, "kebijakan", SEKARANG)


SQL_PAKAI = "INSERT INTO purna_voucher_pakai VALUES(?,?,?,?,?)"
SQL_TERBIT = "INSERT INTO purna_laporan_terbit VALUES(?,?,?,?)"


def pakai(order_id, n=1, *, pelaku=ADMIN, catatan="kelas", dibuat=SEKARANG, operasi_id=None):
    return (operasi_id or operasi(n), order_id, pelaku, catatan, dibuat)


def terbit(order_id, *, waktu=TERBIT_SAH, pelaku=ADMIN, dibuat=None):
    return (order_id, waktu, pelaku, dibuat or waktu)


# --- skenario guard (dipakai tes biasa DAN tes mutation) -----------------------------------

def skenario_update_voucher(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_PAKAI, pakai(oid))
    harus_abort(kon, "UPDATE purna_voucher_pakai SET catatan_kode='lainnya'", (), "immutable")
    assert kon.execute("SELECT catatan_kode FROM purna_voucher_pakai").fetchone()[0] == "kelas"


def skenario_delete_voucher(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_PAKAI, pakai(oid))
    harus_abort(kon, "DELETE FROM purna_voucher_pakai", (), "immutable")
    assert hitung(kon, "purna_voucher_pakai") == 1


def skenario_replace_voucher(kon):
    o1, o2 = order_qris_lunas(kon, 1), order_qris_lunas(kon, 2)
    harus_lolos(kon, SQL_PAKAI, pakai(o1, 1))
    # kunci operasi_id sama, order lain
    harus_abort(kon, "INSERT OR REPLACE INTO purna_voucher_pakai VALUES(?,?,?,?,?)",
                pakai(o2, 1), "duplikat")
    # kunci order_id sama, operasi_id lain
    harus_abort(kon, "INSERT OR REPLACE INTO purna_voucher_pakai VALUES(?,?,?,?,?)",
                pakai(o1, 2, catatan="lainnya"), "duplikat")
    isi = kon.execute("SELECT operasi_id,order_id,catatan_kode FROM purna_voucher_pakai").fetchall()
    assert [tuple(r) for r in isi] == [(operasi(1), o1, "kelas")]


def skenario_update_laporan(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_TERBIT, terbit(oid))
    harus_abort(kon, "UPDATE purna_laporan_terbit SET dicatat_oleh='lain'", (), "immutable")
    assert kon.execute("SELECT dicatat_oleh FROM purna_laporan_terbit").fetchone()[0] == ADMIN


def skenario_delete_laporan(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_TERBIT, terbit(oid))
    harus_abort(kon, "DELETE FROM purna_laporan_terbit", (), "immutable")
    assert hitung(kon, "purna_laporan_terbit") == 1


def skenario_replace_laporan(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_TERBIT, terbit(oid))
    harus_abort(kon, "INSERT OR REPLACE INTO purna_laporan_terbit VALUES(?,?,?,?)",
                terbit(oid, waktu="2026-11-21T10:00:00", pelaku="admin_lain"), "duplikat")
    isi = kon.execute("SELECT terbit,dicatat_oleh FROM purna_laporan_terbit").fetchall()
    assert [tuple(r) for r in isi] == [(TERBIT_SAH, ADMIN)]


def skenario_lunas_laporan(kon):
    belum = order_belum_lunas(kon, 1)
    diperiksa = order_receipt_perlu_diperiksa(kon, 2)
    for oid in (belum, diperiksa):
        harus_abort(kon, SQL_TERBIT, terbit(oid), "laporan terbit hanya untuk order lunas")
    assert hitung(kon, "purna_laporan_terbit") == 0


def skenario_refund_laporan(kon):
    for oid in _order_direfund(kon):
        harus_abort(kon, SQL_TERBIT, terbit(oid), "laporan terbit ditolak: order sudah direfund")
    assert hitung(kon, "purna_laporan_terbit") == 0


def skenario_laporan_sebelum_lunas(kon):
    """Terbit lebih awal dari waktu lunas ditolak (QRIS dan transfer); tepat sama dengan waktu lunas sah."""
    o_qris, o_transfer = order_qris_lunas(kon, 1), order_transfer_lunas(kon, 2)
    pesan = "laporan terbit ditolak: lebih awal dari waktu lunas"
    harus_abort(kon, SQL_TERBIT, terbit(o_qris, waktu="2026-11-18T09:59:59"), pesan)
    harus_abort(kon, SQL_TERBIT, terbit(o_transfer, waktu="2026-11-18T11:59:59"), pesan)
    assert hitung(kon, "purna_laporan_terbit") == 0
    harus_lolos(kon, SQL_TERBIT, terbit(o_qris, waktu=SEKARANG))
    harus_lolos(kon, SQL_TERBIT, terbit(o_transfer, waktu=WAKTU_SETUJU))
    assert hitung(kon, "purna_laporan_terbit") == 2


def skenario_lunas_voucher(kon):
    belum = order_belum_lunas(kon, 1)
    diperiksa = order_receipt_perlu_diperiksa(kon, 2)
    for n, oid in ((1, belum), (2, diperiksa)):
        harus_abort(kon, SQL_PAKAI, pakai(oid, n), "voucher purna hanya untuk order lunas")
    assert hitung(kon, "purna_voucher_pakai") == 0


def _order_direfund(kon):
    o_qris = order_qris_lunas(kon, 1)
    o_transfer = order_transfer_lunas(kon, 2)
    refund(kon, o_qris, 1)
    refund(kon, o_transfer, 2)
    assert hitung(kon, "pesanan_refund") == 1 and hitung(kon, "transfer_refund") == 1
    return o_qris, o_transfer


def skenario_refund_voucher(kon):
    for n, oid in enumerate(_order_direfund(kon), start=1):
        harus_abort(kon, SQL_PAKAI, pakai(oid, n), "voucher purna ditolak: order sudah direfund")
    assert hitung(kon, "purna_voucher_pakai") == 0


def skenario_jalur_sah(kon):
    """Kasus yang HARUS lolos: order QRIS-lunas dan transfer-lunas untuk voucher dan laporan terbit."""
    o_qris, o_transfer = order_qris_lunas(kon, 1), order_transfer_lunas(kon, 2)
    harus_lolos(kon, SQL_PAKAI, pakai(o_qris, 1))
    harus_lolos(kon, SQL_PAKAI, pakai(o_transfer, 2, catatan="lainnya"))
    assert hitung(kon, "purna_voucher_pakai") == 2
    harus_lolos(kon, SQL_TERBIT, terbit(o_qris))
    harus_lolos(kon, SQL_TERBIT, terbit(o_transfer))
    assert hitung(kon, "purna_laporan_terbit") == 2


SKENARIO = {fn.__name__: fn for fn in (
    skenario_update_voucher, skenario_delete_voucher, skenario_replace_voucher,
    skenario_lunas_voucher, skenario_refund_voucher, skenario_jalur_sah,
    skenario_update_laporan, skenario_delete_laporan, skenario_replace_laporan,
    skenario_lunas_laporan, skenario_refund_laporan, skenario_laporan_sebelum_lunas)}


def jalankan(path, skenario):
    # Koneksi langsung tanpa validasi skema: store sengaja menolak purna yang dilucuti guard-nya
    # (fail-closed), sedangkan mutation memang menjalankan skenario pada DB termutasi itu.
    kon = admin_store_core.koneksi(Path(path), "rw")
    try:
        SKENARIO[skenario](kon)
    finally:
        kon.rollback()
        kon.close()


@pytest.fixture
def db(tmp_path):
    return siapkan_db_purna(tmp_path)


# --- struktur, migrasi, fail-closed ---------------------------------------------------------

def test_konstanta_publik():
    assert schema_purna.TABEL == TABEL_PURNA
    assert schema_purna.CATATAN_PAKAI == ("kelas", "lainnya")
    assert not hasattr(schema_purna, "PILIHAN_TERLAMBAT")


def test_skema_tanpa_tabel_pilihan_terlambat(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        objek = {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE name GLOB 'purna_*'")}
    assert not any("pilihan" in nama or "uang_kembali" in nama for nama in objek)
    assert "pilihan" not in schema_purna.DDL and "uang_kembali" not in schema_purna.DDL
    with contextlib.closing(sqlite3.connect(db)) as kon:
        tabel = {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'purna_*'")}
    assert tabel == set(TABEL_PURNA)


def test_db_berisi_tabel_pilihan_lama_ditolak_validasi(db):
    # Skema lama belum pernah dirilis; DB yang masih memuat tabel pilihan dianggap berbeda (tanpa migrasi turun).
    with contextlib.closing(sqlite3.connect(db)) as kon:
        kon.execute("CREATE TABLE purna_pilihan_terlambat (order_id TEXT, pilihan TEXT, dibuat TEXT)")
        kon.commit()
        with pytest.raises(ValueError):
            schema_purna.validasi(kon)


def test_absen_sah_dan_tidak_dipasang_oleh_migrasi_pesanan_atau_transfer(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    with admin_store.buka_baca(path) as kon:
        assert schema_purna.validasi(kon) is False
        assert not schema_purna.struktur(kon)
        assert schema_transfer.validasi(kon) is True


def test_migrasi_idempoten_user_version_tetap_dan_tabel_lengkap(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    with contextlib.closing(sqlite3.connect(path)) as kon:
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
    schema_purna.migrasikan(path)
    pertama = dump(path)
    schema_purna.migrasikan(path)
    admin_store.siapkan(path, sekarang=99)
    assert dump(path) == pertama
    with admin_store.buka_baca(path) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == versi
        assert schema_purna.validasi(kon) is True
        assert {r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'purna_*'")
        } == set(schema_purna.TABEL)
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()


def test_migrasi_ditolak_bila_pesanan_belum_terpasang(tmp_path):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    with pytest.raises(admin_store.StoreBelumSiap):
        schema_purna.migrasikan(path)
    assert not struktur_ns(path, "purna_*")


def test_migrasi_ditolak_bila_transfer_belum_terpasang(tmp_path):
    path = siapkan_db(tmp_path)
    with pytest.raises(admin_store.StoreBelumSiap):
        schema_purna.migrasikan(path)
    assert not struktur_ns(path, "purna_*")


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER purna_voucher_pakai_tolak_update",
    "DROP TRIGGER purna_voucher_pakai_lunas",
    "DROP TRIGGER purna_voucher_pakai_refund",
    "DROP TRIGGER purna_laporan_terbit_sebelum_lunas",
    "DROP TRIGGER purna_laporan_terbit_lunas",
    "DROP TRIGGER purna_laporan_terbit_tolak_replace",
])
def test_struktur_parsial_atau_berbeda_ditolak_validasi_dan_migrasi(db, rusak):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        kon.execute(rusak)
        kon.commit()
    sebelum = dump(db)
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_purna.validasi(kon)
    with pytest.raises((ValueError, admin_store.StoreBelumSiap)):   # store fail-closed menolak lebih dulu
        schema_purna.migrasikan(db)
    assert dump(db) == sebelum


def test_tabel_hilang_sebagian_ditolak(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        for trg in [r[0] for r in kon.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name='purna_laporan_terbit'")]:
            kon.execute("DROP TRIGGER %s" % trg)
        kon.execute("DROP TABLE purna_laporan_terbit")
        kon.commit()
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_purna.validasi(kon)
    with pytest.raises((ValueError, admin_store.StoreBelumSiap)):   # store fail-closed menolak lebih dulu
        schema_purna.migrasikan(db)


def test_definisi_tabel_berbeda_ditolak(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        kon.execute("ALTER TABLE purna_voucher_pakai ADD COLUMN bebas TEXT")
        kon.commit()
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_purna.validasi(kon)
    with pytest.raises((ValueError, admin_store.StoreBelumSiap)):   # store fail-closed menolak lebih dulu
        schema_purna.migrasikan(db)


def test_purna_tanpa_transfer_atau_tanpa_pesanan_ditolak_validasi(tmp_path):
    tanpa_transfer = siapkan_db(tmp_path / "a")
    tanpa_pesanan = tmp_path / "b.db"
    admin_store.siapkan(tanpa_pesanan, sekarang=1)
    for path in (tanpa_transfer, tanpa_pesanan):
        with contextlib.closing(sqlite3.connect(path)) as kon:
            kon.execute("PRAGMA foreign_keys=OFF")
            kon.executescript(schema_purna.DDL)
        with pytest.raises(ValueError):
            with contextlib.closing(sqlite3.connect(path)) as kon:
                schema_purna.validasi(kon)


def test_ddl_dan_validasi_pesanan_serta_transfer_byte_identik_setelah_purna_terpasang(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    pesanan_lama, transfer_lama = struktur_ns(path, "pesanan_*"), struktur_ns(path, "transfer_*")
    schema_purna.migrasikan(path)
    assert struktur_ns(path, "pesanan_*") == pesanan_lama
    assert struktur_ns(path, "transfer_*") == transfer_lama
    with contextlib.closing(sqlite3.connect(path)) as kon:
        assert schema_pesanan.validasi(kon) is True
        assert schema_transfer.validasi(kon) is True
        assert not kon.execute(
            "SELECT 1 FROM sqlite_master WHERE name GLOB 'purna_*' AND "
            "(tbl_name GLOB 'pesanan_*' OR tbl_name GLOB 'transfer_*')").fetchall()
    # image lama (tanpa modul purna) tetap dapat membuka DB yang sudah bertabel purna_* (rollback aman)
    with pesanan.buka(path) as kon:
        assert schema_pesanan.validasi(kon) is True
    with tf.buka(path):
        pass


def test_fk_ke_pesanan_order_restrict_dan_foreign_key_check_kosong(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        for tabel in TABEL_PURNA:
            fk = kon.execute("PRAGMA foreign_key_list(%s)" % tabel).fetchall()
            assert [(r[2], r[3], r[4], r[6]) for r in fk] == [
                ("pesanan_order", "order_id", "order_id", "RESTRICT")]
    with pesanan.buka(db, tulis_data=True) as kon:
        oid, lain = order_qris_lunas(kon, 1), order_qris_lunas(kon, 2)
        kon.execute(SQL_PAKAI, pakai(oid))
        kon.execute(SQL_TERBIT, terbit(lain))
        kon.commit()
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("DELETE FROM pesanan_order WHERE order_id=?", (oid,))
        kon.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(SQL_PAKAI, pakai("ord_" + "0" * 32))      # order tidak ada


@pytest.mark.parametrize("nilai", [
    dict(operasi_id="pendek"), dict(operasi_id="op sintetis 0001"), dict(operasi_id="x" * 65),
    dict(pelaku=""), dict(pelaku="admin sintetis"), dict(pelaku="a" * 65),
    dict(catatan="refund"), dict(dibuat="kemarin"), dict(dibuat="2026-11-18 10:00:00"),
])
def test_check_kolom_voucher_pakai(db, nilai):
    with pesanan.buka(db, tulis_data=True) as kon:
        oid = order_qris_lunas(kon, 1)
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(SQL_PAKAI, pakai(oid, **nilai))
        kon.rollback()
        assert hitung(kon, "purna_voucher_pakai") == 0


@pytest.mark.parametrize("nilai", [
    dict(pelaku=""), dict(pelaku="admin sintetis"), dict(pelaku="a" * 65),
    dict(waktu="kemarin"), dict(waktu="2026-11-20 10:00:00"), dict(dibuat="kemarin"),
])
def test_check_kolom_laporan_terbit(db, nilai):
    with pesanan.buka(db, tulis_data=True) as kon:
        oid = order_qris_lunas(kon, 1)
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(SQL_TERBIT, terbit(oid, **nilai))
        kon.rollback()
        assert hitung(kon, "purna_laporan_terbit") == 0


# --- guard tingkat DB (skenario dijalankan pada DB hasil migrasikan) ---------------------------

@pytest.mark.parametrize("skenario", sorted(SKENARIO))
def test_skenario_guard_hijau_pada_skema_utuh(db, skenario):
    jalankan(db, skenario)


def test_jalur_sah_dan_tolak_tidak_menyentuh_pesanan_maupun_transfer(db):
    with pesanan.buka(db, tulis_data=True) as kon:
        oid = order_qris_lunas(kon, 1)
        sebelum = {t: hitung(kon, t) for t in schema_pesanan.TABEL + schema_transfer.TABEL}
        kon.execute(SQL_PAKAI, pakai(oid))
        kon.commit()
        assert {t: hitung(kon, t) for t in schema_pesanan.TABEL + schema_transfer.TABEL} == sebelum


# --- mutation: tiap guard dilucuti pada salinan sementara; skenario yang menjaganya harus MERAH ---

def _lucuti_trigger(ddl, nama):
    hasil, n = re.subn(r"CREATE TRIGGER %s BEFORE .*?END;\n" % re.escape(nama), "", ddl,
                       flags=re.DOTALL)
    assert n == 1, "mutasi hampa: trigger %s tidak ditemukan" % nama
    return hasil


# Cabang yang memang berulang di beberapa trigger (mutasi sengaja menyentuh semuanya).
_CABANG_BERULANG = {
    "NOT EXISTS(SELECT 1 FROM pesanan_receipt WHERE order_id=NEW.order_id AND hasil='lunas')",
    "NOT EXISTS(SELECT 1 FROM transfer_lunas WHERE order_id=NEW.order_id)",
    "pesanan_receipt WHERE order_id=NEW.order_id AND hasil='lunas'",
    "EXISTS(SELECT 1 FROM pesanan_refund WHERE order_id=NEW.order_id)",
    "EXISTS(SELECT 1 FROM transfer_refund WHERE order_id=NEW.order_id)",
    "operasi_id=NEW.operasi_id",
}


def _ganti(ddl, lama, baru):
    assert lama in ddl, "mutasi hampa: %r tidak ada di DDL" % lama
    assert lama in _CABANG_BERULANG or ddl.count(lama) == 1, "pola mutasi harus unik: %r" % lama
    return ddl.replace(lama, baru)


GUARD = (
    ("purna_voucher_pakai_tolak_update", "skenario_update_voucher"),
    ("purna_voucher_pakai_tolak_delete", "skenario_delete_voucher"),
    ("purna_voucher_pakai_tolak_replace", "skenario_replace_voucher"),
    ("purna_voucher_pakai_lunas", "skenario_lunas_voucher"),
    ("purna_voucher_pakai_refund", "skenario_refund_voucher"),
    ("purna_laporan_terbit_tolak_update", "skenario_update_laporan"),
    ("purna_laporan_terbit_tolak_delete", "skenario_delete_laporan"),
    ("purna_laporan_terbit_tolak_replace", "skenario_replace_laporan"),
    ("purna_laporan_terbit_lunas", "skenario_lunas_laporan"),
    ("purna_laporan_terbit_refund", "skenario_refund_laporan"),
    ("purna_laporan_terbit_sebelum_lunas", "skenario_laporan_sebelum_lunas"),
)


def test_daftar_guard_mutation_lengkap_sama_dengan_trigger_di_skema(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        trigger = {r[0] for r in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name GLOB 'purna_*'")}
    assert trigger == {nama for nama, _ in GUARD}


@pytest.mark.parametrize("nama,skenario", GUARD)
def test_mutation_tanpa_guard_skenario_merah_lalu_hijau_saat_dipulihkan(tmp_path, nama, skenario):
    dimutasi = siapkan_db_purna(tmp_path / "mutasi", _lucuti_trigger(schema_purna.DDL, nama))
    with contextlib.closing(sqlite3.connect(dimutasi)) as kon:
        assert not kon.execute("SELECT 1 FROM sqlite_master WHERE name=?", (nama,)).fetchall()
    with pytest.raises(GuardSalah):
        jalankan(dimutasi, skenario)
    jalankan(siapkan_db_purna(tmp_path / "pulih"), skenario)


# Mutasi pada satu cabang kondisi (bukan seluruh trigger): cabang yang hilang harus ketahuan.
CABANG = (
    ("lunas-tanpa-cabang-receipt",
     ("NOT EXISTS(SELECT 1 FROM pesanan_receipt WHERE order_id=NEW.order_id AND hasil='lunas')", "1"),
     "skenario_jalur_sah"),
    ("lunas-tanpa-cabang-transfer-lunas",
     ("NOT EXISTS(SELECT 1 FROM transfer_lunas WHERE order_id=NEW.order_id)", "1"),
     "skenario_jalur_sah"),
    ("lunas-tanpa-filter-hasil-lunas",
     ("pesanan_receipt WHERE order_id=NEW.order_id AND hasil='lunas'",
      "pesanan_receipt WHERE order_id=NEW.order_id"),
     "skenario_lunas_voucher"),
    ("refund-tanpa-cabang-pesanan-refund",
     ("EXISTS(SELECT 1 FROM pesanan_refund WHERE order_id=NEW.order_id)", "0"),
     "skenario_refund_voucher"),
    ("refund-tanpa-cabang-transfer-refund",
     ("EXISTS(SELECT 1 FROM transfer_refund WHERE order_id=NEW.order_id)", "0"),
     "skenario_refund_voucher"),
    ("replace-voucher-tanpa-kunci-operasi",
     ("operasi_id=NEW.operasi_id", "0"),
     "skenario_replace_voucher"),
    ("replace-voucher-tanpa-kunci-order",
     ("OR order_id=NEW.order_id)", "OR 0)"),
     "skenario_replace_voucher"),
    ("terbit-sama-dengan-waktu-lunas-jadi-ditolak",
     ("NEW.terbit < COALESCE", "NEW.terbit <= COALESCE"),
     "skenario_laporan_sebelum_lunas"),
    ("terbit-sebelum-lunas-tanpa-cabang-transfer",
     ("(SELECT dibuat FROM transfer_lunas WHERE order_id=NEW.order_id)", "NULL"),
     "skenario_laporan_sebelum_lunas"),
    ("terbit-sebelum-lunas-tanpa-cabang-receipt",
     ("(SELECT dibuat FROM pesanan_receipt WHERE order_id=NEW.order_id AND hasil='lunas'),", "NULL,"),
     "skenario_laporan_sebelum_lunas"),
    ("terbit-sebelum-lunas-arah-terbalik",
     ("NEW.terbit < COALESCE", "NEW.terbit > COALESCE"),
     "skenario_laporan_sebelum_lunas"),
)


@pytest.mark.parametrize("label,penggantian,skenario", CABANG, ids=[c[0] for c in CABANG])
def test_mutation_cabang_kondisi_dilucuti_skenario_merah(tmp_path, label, penggantian, skenario):
    ddl = _ganti(schema_purna.DDL, *penggantian)
    dimutasi = siapkan_db_purna(tmp_path / "mutasi", ddl)
    with pytest.raises(GuardSalah):
        jalankan(dimutasi, skenario)
    jalankan(siapkan_db_purna(tmp_path / "pulih"), skenario)
