"""Skema purna_*: aditif di atas pesanan v1 + transfer_*, fail-closed, append-only, guard tingkat DB.

Skenario guard ditulis sebagai fungsi `skenario_*(kon)` yang melempar `GuardSalah` bila DB tidak
berperilaku sesuai aturan. Tes biasa menjalankannya pada DB yang dimigrasikan `schema_purna.migrasikan`;
tes mutation menjalankan skenario YANG SAMA pada salinan sementara yang DDL-nya sudah dilucuti satu guard
dan menuntut `GuardSalah` (merah karena asersi guard, bukan karena fixture/import rusak).
"""
import contextlib
import re
import sqlite3

import pytest

import admin_store
import pesanan
import pesanan_transfer as tf
import schema_pesanan
import schema_purna
import schema_transfer
from pesanan_kit import SEKARANG, buat, hitung, operasi, siapkan_db, terapkan
from transfer_kit import ADMIN, menunggu, siapkan_db_transfer

WAKTU_SETUJU = "2026-11-18T12:00:00"
TABEL_PURNA = ("purna_voucher_pakai", "purna_pilihan_terlambat")


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
SQL_PILIH = "INSERT INTO purna_pilihan_terlambat VALUES(?,?,?)"


def pakai(order_id, n=1, *, pelaku=ADMIN, catatan="kelas", dibuat=SEKARANG, operasi_id=None):
    return (operasi_id or operasi(n), order_id, pelaku, catatan, dibuat)


def pilih(order_id, pilihan="menunggu", dibuat=SEKARANG):
    return (order_id, pilihan, dibuat)


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


def skenario_update_pilihan(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_PILIH, pilih(oid))
    harus_abort(kon, "UPDATE purna_pilihan_terlambat SET pilihan='uang_kembali'", (), "immutable")
    assert kon.execute("SELECT pilihan FROM purna_pilihan_terlambat").fetchone()[0] == "menunggu"


def skenario_delete_pilihan(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_PILIH, pilih(oid))
    harus_abort(kon, "DELETE FROM purna_pilihan_terlambat", (), "immutable")
    assert hitung(kon, "purna_pilihan_terlambat") == 1


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


def skenario_replace_pilihan(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_PILIH, pilih(oid, "menunggu"))
    harus_abort(kon, "INSERT OR REPLACE INTO purna_pilihan_terlambat VALUES(?,?,?)",
                pilih(oid, "uang_kembali"), "duplikat")
    assert kon.execute("SELECT pilihan FROM purna_pilihan_terlambat").fetchone()[0] == "menunggu"


def skenario_lunas_voucher(kon):
    belum = order_belum_lunas(kon, 1)
    diperiksa = order_receipt_perlu_diperiksa(kon, 2)
    for n, oid in ((1, belum), (2, diperiksa)):
        harus_abort(kon, SQL_PAKAI, pakai(oid, n), "voucher purna hanya untuk order lunas")
    assert hitung(kon, "purna_voucher_pakai") == 0


def skenario_lunas_pilihan(kon):
    belum = order_belum_lunas(kon, 1)
    diperiksa = order_receipt_perlu_diperiksa(kon, 2)
    for oid in (belum, diperiksa):
        harus_abort(kon, SQL_PILIH, pilih(oid), "pilihan terlambat hanya untuk order lunas")
    assert hitung(kon, "purna_pilihan_terlambat") == 0


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


def skenario_refund_pilihan(kon):
    for oid in _order_direfund(kon):
        harus_abort(kon, SQL_PILIH, pilih(oid), "pilihan terlambat ditolak: order sudah direfund")
    assert hitung(kon, "purna_pilihan_terlambat") == 0


def skenario_voucher_dipakai_menolak_pilihan(kon):
    oid = order_qris_lunas(kon, 1)
    harus_lolos(kon, SQL_PAKAI, pakai(oid))
    for pilihan in ("menunggu", "uang_kembali"):
        harus_abort(kon, SQL_PILIH, pilih(oid, pilihan),
                    "pilihan terlambat ditolak: voucher order sudah dipakai")
    assert hitung(kon, "purna_pilihan_terlambat") == 0


def skenario_uang_kembali_menolak_voucher(kon):
    oid = order_transfer_lunas(kon, 1)
    harus_lolos(kon, SQL_PILIH, pilih(oid, "uang_kembali"))
    harus_abort(kon, SQL_PAKAI, pakai(oid), "voucher purna ditolak: order sudah memilih uang kembali")
    assert hitung(kon, "purna_voucher_pakai") == 0


def skenario_jalur_sah(kon):
    """Kasus yang HARUS lolos: QRIS-lunas dan transfer-lunas; pilihan 'menunggu' tidak menghalangi voucher."""
    o_qris, o_transfer = order_qris_lunas(kon, 1), order_transfer_lunas(kon, 2)
    o_menunggu, o_kembali = order_qris_lunas(kon, 3), order_transfer_lunas(kon, 4)
    harus_lolos(kon, SQL_PAKAI, pakai(o_qris, 1))
    harus_lolos(kon, SQL_PAKAI, pakai(o_transfer, 2, catatan="lainnya"))
    harus_lolos(kon, SQL_PILIH, pilih(o_menunggu, "menunggu"))
    harus_lolos(kon, SQL_PAKAI, pakai(o_menunggu, 3))
    harus_lolos(kon, SQL_PILIH, pilih(o_kembali, "uang_kembali"))
    assert hitung(kon, "purna_voucher_pakai") == 3 and hitung(kon, "purna_pilihan_terlambat") == 2


SKENARIO = {fn.__name__: fn for fn in (
    skenario_update_voucher, skenario_delete_voucher, skenario_update_pilihan,
    skenario_delete_pilihan, skenario_replace_voucher, skenario_replace_pilihan,
    skenario_lunas_voucher, skenario_lunas_pilihan, skenario_refund_voucher,
    skenario_refund_pilihan, skenario_voucher_dipakai_menolak_pilihan,
    skenario_uang_kembali_menolak_voucher, skenario_jalur_sah)}


def jalankan(path, skenario):
    with pesanan.buka(path, tulis_data=True) as kon:
        try:
            SKENARIO[skenario](kon)
        finally:
            kon.rollback()


@pytest.fixture
def db(tmp_path):
    return siapkan_db_purna(tmp_path)


# --- struktur, migrasi, fail-closed ---------------------------------------------------------

def test_konstanta_publik():
    assert schema_purna.TABEL == TABEL_PURNA
    assert schema_purna.CATATAN_PAKAI == ("kelas", "lainnya")
    assert schema_purna.PILIHAN_TERLAMBAT == ("menunggu", "uang_kembali")


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
    "DROP TRIGGER purna_pilihan_terlambat_tolak_replace",
    "DROP TRIGGER purna_voucher_pakai_lunas",
    "DROP TRIGGER purna_pilihan_terlambat_voucher_dipakai",
    "DROP TRIGGER purna_voucher_pakai_uang_kembali",
])
def test_struktur_parsial_atau_berbeda_ditolak_validasi_dan_migrasi(db, rusak):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        kon.execute(rusak)
        kon.commit()
    sebelum = dump(db)
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_purna.validasi(kon)
    with pytest.raises(ValueError):
        schema_purna.migrasikan(db)
    assert dump(db) == sebelum


def test_tabel_hilang_sebagian_ditolak(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        for trg in [r[0] for r in kon.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name='purna_pilihan_terlambat'")]:
            kon.execute("DROP TRIGGER %s" % trg)
        kon.execute("DROP TABLE purna_pilihan_terlambat")
        kon.commit()
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_purna.validasi(kon)
    with pytest.raises(ValueError):
        schema_purna.migrasikan(db)


def test_definisi_tabel_berbeda_ditolak(db):
    with contextlib.closing(sqlite3.connect(db)) as kon:
        kon.execute("ALTER TABLE purna_voucher_pakai ADD COLUMN bebas TEXT")
        kon.commit()
    with pytest.raises(ValueError):
        with contextlib.closing(sqlite3.connect(db)) as kon:
            schema_purna.validasi(kon)
    with pytest.raises(ValueError):
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
        kon.execute(SQL_PILIH, pilih(lain))
        kon.commit()
        assert not kon.execute("PRAGMA foreign_key_check").fetchall()
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute("DELETE FROM pesanan_order WHERE order_id=?", (oid,))
        kon.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(SQL_PILIH, pilih("ord_" + "0" * 32))      # order tidak ada


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


@pytest.mark.parametrize("nilai", [dict(pilihan="batal"), dict(pilihan=""), dict(dibuat="kemarin")])
def test_check_kolom_pilihan_terlambat(db, nilai):
    with pesanan.buka(db, tulis_data=True) as kon:
        oid = order_qris_lunas(kon, 1)
        with pytest.raises(sqlite3.IntegrityError):
            kon.execute(SQL_PILIH, pilih(oid, **nilai))
        kon.rollback()
        assert hitung(kon, "purna_pilihan_terlambat") == 0


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


def _ganti(ddl, lama, baru):
    assert lama in ddl, "mutasi hampa: %r tidak ada di DDL" % lama
    return ddl.replace(lama, baru)


GUARD = (
    ("purna_voucher_pakai_tolak_update", "skenario_update_voucher"),
    ("purna_voucher_pakai_tolak_delete", "skenario_delete_voucher"),
    ("purna_voucher_pakai_tolak_replace", "skenario_replace_voucher"),
    ("purna_pilihan_terlambat_tolak_update", "skenario_update_pilihan"),
    ("purna_pilihan_terlambat_tolak_delete", "skenario_delete_pilihan"),
    ("purna_pilihan_terlambat_tolak_replace", "skenario_replace_pilihan"),
    ("purna_voucher_pakai_lunas", "skenario_lunas_voucher"),
    ("purna_pilihan_terlambat_lunas", "skenario_lunas_pilihan"),
    ("purna_voucher_pakai_refund", "skenario_refund_voucher"),
    ("purna_pilihan_terlambat_refund", "skenario_refund_pilihan"),
    ("purna_pilihan_terlambat_voucher_dipakai", "skenario_voucher_dipakai_menolak_pilihan"),
    ("purna_voucher_pakai_uang_kembali", "skenario_uang_kembali_menolak_voucher"),
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
    ("uang-kembali-terlalu-luas",
     ("pilihan='uang_kembali'", "pilihan IS NOT NULL"),
     "skenario_jalur_sah"),
    ("uang-kembali-tanpa-filter-pilihan",
     ("pilihan='uang_kembali'", "1"),
     "skenario_jalur_sah"),
    ("replace-voucher-tanpa-kunci-operasi",
     ("operasi_id=NEW.operasi_id", "0"),
     "skenario_replace_voucher"),
    ("replace-voucher-tanpa-kunci-order",
     ("OR order_id=NEW.order_id)", "OR 0)"),
     "skenario_replace_voucher"),
)


@pytest.mark.parametrize("label,penggantian,skenario", CABANG, ids=[c[0] for c in CABANG])
def test_mutation_cabang_kondisi_dilucuti_skenario_merah(tmp_path, label, penggantian, skenario):
    ddl = _ganti(schema_purna.DDL, *penggantian)
    dimutasi = siapkan_db_purna(tmp_path / "mutasi", ddl)
    with pytest.raises(GuardSalah):
        jalankan(dimutasi, skenario)
    jalankan(siapkan_db_purna(tmp_path / "pulih"), skenario)
