"""Schema dan koneksi SQLite transient untuk batch admin."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3


VERSI_TRANSIENT = 2

class BulkTidakSah(ValueError):
    """CSV, snapshot, atau state batch tidak memenuhi kontrak sempit."""

_DDL_TRANSIENT = """
CREATE TABLE IF NOT EXISTS draft_bulk (
    batch_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    session_binding TEXT NOT NULL CHECK(length(session_binding)=64),
    aksi TEXT NOT NULL,
    target_peran TEXT NOT NULL CHECK(target_peran IN ('guru','murid')),
    kedaluwarsa INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('ready','running','partial','stopped','succeeded','attention')),
    preflight_selesai INTEGER NOT NULL DEFAULT 0 CHECK(preflight_selesai IN (0,1)),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS item_bulk (
    batch_id TEXT NOT NULL REFERENCES draft_bulk(batch_id) ON DELETE CASCADE,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    operasi_id TEXT NOT NULL UNIQUE,
    target_id TEXT NOT NULL,
    target_revisi INTEGER NOT NULL CHECK(target_revisi>=0),
    alias_valid TEXT,
    status TEXT NOT NULL CHECK(status IN (
        'pending','succeeded','failed_before_commit','conflict','uncertain','cancelled'
    )),
    hasil_id TEXT,
    credential_status TEXT NOT NULL DEFAULT 'not_applicable'
        CHECK(credential_status IN ('not_applicable','unconfirmed','confirmed')),
    PRIMARY KEY(batch_id,item_id),
    UNIQUE(batch_id,target_id)
);
CREATE TABLE IF NOT EXISTS kelompok_bulk (
    kelompok_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES draft_bulk(batch_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK(status IN ('running','completed','attention')),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kelompok_bulk_item (
    kelompok_id TEXT NOT NULL REFERENCES kelompok_bulk(kelompok_id) ON DELETE CASCADE,
    batch_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    PRIMARY KEY(kelompok_id,item_id),
    FOREIGN KEY(batch_id,item_id) REFERENCES item_bulk(batch_id,item_id) ON DELETE CASCADE
);
"""

def _uri(path: Path, mode: str) -> str:
    return path.resolve().as_uri() + "?mode=" + mode

def siapkan_transient(path) -> None:
    tujuan = Path(path)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    kon = sqlite3.connect(str(tujuan), timeout=5.0)
    try:
        versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
        if versi > VERSI_TRANSIENT:
            raise BulkTidakSah("skema draft lebih baru")
        kon.execute("PRAGMA foreign_keys=OFF" if versi == 1 else "PRAGMA foreign_keys=ON")
        if versi == 1:
            kon.execute("BEGIN IMMEDIATE")
            kon.execute(
                "ALTER TABLE draft_bulk ADD COLUMN preflight_selesai INTEGER NOT NULL DEFAULT 0 CHECK(preflight_selesai IN (0,1))"
            )
            kon.execute("ALTER TABLE item_bulk RENAME TO item_bulk_v1")
            kon.execute(
                """CREATE TABLE item_bulk (
                    batch_id TEXT NOT NULL REFERENCES draft_bulk(batch_id) ON DELETE CASCADE,
                    item_id TEXT NOT NULL,
                    urutan INTEGER NOT NULL,
                    operasi_id TEXT NOT NULL UNIQUE,
                    target_id TEXT NOT NULL,
                    target_revisi INTEGER NOT NULL CHECK(target_revisi>=0),
                    alias_valid TEXT,
                    status TEXT NOT NULL CHECK(status IN (
                        'pending','succeeded','failed_before_commit','conflict','uncertain','cancelled'
                    )),
                    hasil_id TEXT,
                    credential_status TEXT NOT NULL DEFAULT 'not_applicable'
                        CHECK(credential_status IN ('not_applicable','unconfirmed','confirmed')),
                    PRIMARY KEY(batch_id,item_id),
                    UNIQUE(batch_id,target_id)
                )"""
            )
            kon.execute(
                """INSERT INTO item_bulk(
                       batch_id,item_id,urutan,operasi_id,target_id,target_revisi,
                       alias_valid,status,hasil_id,credential_status)
                   SELECT batch_id,item_id,urutan,operasi_id,target_id,target_revisi,
                          alias_valid,status,NULL,
                          CASE WHEN status='succeeded' AND EXISTS(
                              SELECT 1 FROM draft_bulk d
                              WHERE d.batch_id=item_bulk_v1.batch_id
                                AND d.aksi IN ('account_teacher_create','account_password_reset')
                          ) THEN 'unconfirmed' ELSE 'not_applicable' END
                   FROM item_bulk_v1"""
            )
            kon.execute("DROP TABLE item_bulk_v1")
            kon.execute("PRAGMA user_version=2")
            kon.commit()
            kon.execute("PRAGMA foreign_keys=ON")
        kon.executescript(_DDL_TRANSIENT)
        kon.execute("PRAGMA user_version=2")
        kon.commit()
        if kon.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BulkTidakSah("integritas store transient gagal")
        if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BulkTidakSah("foreign key store transient gagal")
    except Exception:
        if kon.in_transaction:
            kon.rollback()
        raise
    finally:
        kon.close()
    tujuan.chmod(0o600)

@contextmanager
def _transaksi(path):
    try:
        kon = sqlite3.connect(_uri(Path(path), "rw"), uri=True, timeout=5.0)
    except sqlite3.Error as galat:
        raise BulkTidakSah("store transient tidak tersedia") from galat
    kon.row_factory = sqlite3.Row
    try:
        kon.execute("PRAGMA foreign_keys=ON")
        if int(kon.execute("PRAGMA user_version").fetchone()[0]) != VERSI_TRANSIENT:
            raise BulkTidakSah("store transient belum siap")
        kon.execute("BEGIN IMMEDIATE")
        yield kon
        kon.commit()
    except Exception:
        kon.rollback()
        raise
    finally:
        kon.close()

def _buka_baca_transient(path):
    try:
        kon = sqlite3.connect(_uri(Path(path), "ro"), uri=True, timeout=5.0)
    except sqlite3.Error:
        return None
    kon.row_factory = sqlite3.Row
    try:
        if int(kon.execute("PRAGMA user_version").fetchone()[0]) != VERSI_TRANSIENT:
            kon.close()
            return None
    except sqlite3.Error:
        kon.close()
        return None
    return kon
