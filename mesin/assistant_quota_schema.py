"""Ledger kuota layanan admin9, migrasi opt-in terpisah dari startup/GET.

DDL dipasang hanya admin_store.migrasikan_kuota_pendamping pada admin8 existing.
Schema tidak memberi hak/trial/window atau mengaktifkan enforcement. Produksi
memerlukan backup/rehearsal/recovery9 exact. Tabel paket_* tidak diubah.
"""
import sqlite3

VERSI_SKEMA = 9
TABEL = ("kuota_pendamping_jendela", "kuota_pendamping_operasi")
DDL = """
CREATE TABLE kuota_pendamping_jendela (
    akun_id TEXT NOT NULL,
    jendela_id TEXT NOT NULL CHECK(length(jendela_id)=64),
    fitur TEXT NOT NULL CHECK(fitur IN ('balasan_pendamping','pembacaan_foto')),
    entitlement_sidik TEXT NOT NULL CHECK(length(entitlement_sidik)=64),
    sumber TEXT NOT NULL CHECK(sumber IN ('trial','grant_paket')),
    sumber_id TEXT NOT NULL,
    paket TEXT NOT NULL CHECK(paket IN ('coba_gratis','jago_pro')),
    entitlement_mulai INTEGER NOT NULL CHECK(entitlement_mulai>=0),
    entitlement_akhir INTEGER NOT NULL CHECK(entitlement_akhir>entitlement_mulai),
    mulai INTEGER NOT NULL CHECK(mulai>=entitlement_mulai),
    akhir INTEGER NOT NULL CHECK(akhir>mulai AND akhir<=entitlement_akhir),
    batas INTEGER NOT NULL CHECK(batas IN (2,5,10,50)),
    PRIMARY KEY(akun_id,jendela_id,fitur)
);
CREATE TABLE kuota_pendamping_operasi (
    operasi_id TEXT PRIMARY KEY,
    akun_id TEXT NOT NULL,
    jendela_id TEXT NOT NULL,
    fitur TEXT NOT NULL,
    entitlement_sidik TEXT NOT NULL CHECK(length(entitlement_sidik)=64),
    status TEXT NOT NULL CHECK(status IN ('reserved','completed','released','unknown')),
    dibuat INTEGER NOT NULL CHECK(dibuat>=0),
    diperbarui INTEGER NOT NULL CHECK(diperbarui>=dibuat),
    FOREIGN KEY(akun_id,jendela_id,fitur)
        REFERENCES kuota_pendamping_jendela(akun_id,jendela_id,fitur) ON DELETE RESTRICT
);
CREATE INDEX kuota_pendamping_operasi_jendela
    ON kuota_pendamping_operasi(akun_id,jendela_id,fitur,status);
CREATE TRIGGER kuota_pendamping_jendela_tolak_update
BEFORE UPDATE ON kuota_pendamping_jendela
BEGIN SELECT RAISE(ABORT,'jendela kuota immutable'); END;
CREATE TRIGGER kuota_pendamping_jendela_tolak_delete
BEFORE DELETE ON kuota_pendamping_jendela
BEGIN SELECT RAISE(ABORT,'jendela kuota immutable'); END;
CREATE TRIGGER kuota_pendamping_jendela_tolak_replace
BEFORE INSERT ON kuota_pendamping_jendela
WHEN EXISTS(SELECT 1 FROM kuota_pendamping_jendela WHERE
    akun_id=NEW.akun_id AND jendela_id=NEW.jendela_id AND fitur=NEW.fitur)
BEGIN SELECT RAISE(ABORT,'jendela kuota duplikat'); END;
CREATE TRIGGER kuota_pendamping_operasi_tolak_delete
BEFORE DELETE ON kuota_pendamping_operasi
BEGIN SELECT RAISE(ABORT,'operasi kuota durable'); END;
CREATE TRIGGER kuota_pendamping_operasi_tolak_replace
BEFORE INSERT ON kuota_pendamping_operasi
WHEN EXISTS(SELECT 1 FROM kuota_pendamping_operasi WHERE operasi_id=NEW.operasi_id)
BEGIN SELECT RAISE(ABORT,'operasi kuota duplikat'); END;
CREATE TRIGGER kuota_pendamping_operasi_ikat_update
BEFORE UPDATE ON kuota_pendamping_operasi
WHEN NEW.operasi_id!=OLD.operasi_id OR NEW.akun_id!=OLD.akun_id
    OR NEW.jendela_id!=OLD.jendela_id OR NEW.fitur!=OLD.fitur
    OR NEW.entitlement_sidik!=OLD.entitlement_sidik OR NEW.dibuat!=OLD.dibuat
    OR NEW.diperbarui<OLD.diperbarui
    OR OLD.status IN ('completed','released')
    OR (OLD.status='unknown' AND NEW.status='reserved')
BEGIN SELECT RAISE(ABORT,'transisi operasi kuota tidak sah'); END;
"""


def struktur(kon):
    return tuple(tuple(r) for r in kon.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE tbl_name GLOB 'kuota_pendamping_*' ORDER BY type,name"))


def validasi(kon):
    acuan = sqlite3.connect(":memory:")
    try:
        acuan.executescript(DDL)
        if struktur(kon) != struktur(acuan):
            raise ValueError("struktur kuota Pendamping tidak lengkap")
    finally:
        acuan.close()
