"""Receipt persetujuan awal; optional-additive dan tidak memigrasi saat GET."""
import sqlite3

DDL = """
CREATE TABLE policy_receipt (
    akun_id TEXT PRIMARY KEY,
    versi TEXT NOT NULL,
    epoch TEXT NOT NULL CHECK(length(epoch)=32),
    revisi INTEGER NOT NULL CHECK(revisi>=1),
    operasi TEXT NOT NULL UNIQUE,
    dibuat INTEGER NOT NULL CHECK(dibuat>=0),
    alur INTEGER NOT NULL CHECK(alur IN (0,1)),
    hasil INTEGER NOT NULL CHECK(hasil IN (0,1)),
    chat INTEGER NOT NULL CHECK(chat IN (0,1)),
    CHECK(alur=1 OR (hasil=0 AND chat=0))
);
"""


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE tbl_name GLOB 'policy_*' ORDER BY type,name"))


def validasi(kon):
    aktual=struktur(kon)
    if not aktual:
        return False
    acuan=sqlite3.connect(':memory:')
    try:
        acuan.executescript(DDL)
        if aktual!=struktur(acuan):
            raise ValueError('schema persetujuan tidak sah')
    finally:
        acuan.close()
    return True


def migrasikan(path):
    import admin_store
    import admin_store_core
    import sensor_schema
    sensor_schema.migrasikan(path)
    with admin_store._transaksi(path) as kon:
        if not struktur(kon):
            admin_store_core.jalankan_ddl(kon,DDL)
        validasi(kon)
