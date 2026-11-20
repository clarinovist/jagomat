"""Skema SQLite privat untuk Pendamping Jagomat.

Basis data ini sengaja terpisah dari data belajar. Migrasi hanya additive,
idempoten, dan selalu mengaktifkan foreign key pada setiap koneksi.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import jurnal_wal

BAWAAN = Path(os.environ.get("PENDAMPING_BERKAS_DB", "/data/pendamping.db"))
VERSI_SKEMA = 4

_DDL = """
CREATE TABLE IF NOT EXISTS migrasi_pendamping (
    versi INTEGER PRIMARY KEY,
    diterapkan TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chat (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    mode_memori TEXT NOT NULL CHECK (mode_memori IN ('aktif', 'tanpa_memori')),
    context_kind TEXT,
    context_id TEXT,
    context_version INTEGER,
    context_resource_version TEXT,
    versi INTEGER NOT NULL DEFAULT 1 CHECK (versi >= 1),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL,
    dihapus INTEGER,
    purge_setelah INTEGER,
    CHECK ((dihapus IS NULL AND purge_setelah IS NULL) OR
           (dihapus IS NOT NULL AND purge_setelah IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_chat_pemilik_status
    ON chat(account_id, dihapus, diperbarui);
CREATE INDEX IF NOT EXISTS idx_chat_purge ON chat(purge_setelah);

CREATE TABLE IF NOT EXISTS pesan (
    id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chat(id) ON DELETE RESTRICT,
    urut INTEGER NOT NULL CHECK (urut >= 1),
    peran TEXT NOT NULL CHECK (peran IN ('pengguna', 'asisten')),
    teks TEXT NOT NULL CHECK (length(teks) BETWEEN 1 AND 8000),
    status TEXT NOT NULL CHECK (status IN ('final', 'gagal')),
    request_id TEXT,
    dibuat INTEGER NOT NULL,
    UNIQUE(chat_id, urut),
    UNIQUE(request_id)
);
CREATE INDEX IF NOT EXISTS idx_pesan_chat ON pesan(chat_id, urut);

CREATE TABLE IF NOT EXISTS preferensi_memori (
    account_id TEXT PRIMARY KEY,
    aktif INTEGER NOT NULL CHECK (aktif IN (0, 1)),
    versi INTEGER NOT NULL DEFAULT 1 CHECK (versi >= 1),
    diperbarui INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS memori (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    lingkup TEXT NOT NULL CHECK (lingkup = 'preferensi_orang_tua'),
    isi TEXT NOT NULL CHECK (length(isi) BETWEEN 1 AND 500),
    versi INTEGER NOT NULL DEFAULT 1 CHECK (versi >= 1),
    sumber_chat_id TEXT REFERENCES chat(id) ON DELETE RESTRICT,
    dikonfirmasi INTEGER NOT NULL CHECK (dikonfirmasi IN (0, 1)),
    dibuat INTEGER NOT NULL,
    dihapus INTEGER
);
CREATE INDEX IF NOT EXISTS idx_memori_pemilik
    ON memori(account_id, dikonfirmasi, dihapus);

CREATE TABLE IF NOT EXISTS persetujuan (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    kategori TEXT NOT NULL,
    diberikan INTEGER NOT NULL,
    dicabut INTEGER,
    versi INTEGER NOT NULL DEFAULT 1 CHECK (versi >= 1)
);
CREATE INDEX IF NOT EXISTS idx_persetujuan_pemilik
    ON persetujuan(account_id, kategori, dicabut);

CREATE TABLE IF NOT EXISTS persetujuan_konteks (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    jenis TEXT NOT NULL CHECK (jenis IN ('anak', 'sesi', 'soal')),
    resource_id TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    kategori TEXT NOT NULL CHECK (kategori IN ('ringkasan_netral', 'soal_resmi')),
    diberikan INTEGER NOT NULL,
    dicabut INTEGER,
    versi INTEGER NOT NULL DEFAULT 1 CHECK (versi >= 1)
);
CREATE INDEX IF NOT EXISTS idx_persetujuan_konteks_pemilik
    ON persetujuan_konteks(account_id, jenis, resource_id, dicabut);

CREATE TABLE IF NOT EXISTS operasi (
    request_id TEXT PRIMARY KEY,
    chat_id TEXT NOT NULL REFERENCES chat(id) ON DELETE RESTRICT,
    account_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'selesai', 'gagal')),
    chat_version INTEGER NOT NULL,
    consent_version INTEGER NOT NULL,
    memory_version INTEGER NOT NULL,
    context_version INTEGER NOT NULL,
    dibuat INTEGER NOT NULL,
    selesai INTEGER
);
CREATE INDEX IF NOT EXISTS idx_operasi_pemilik_status
    ON operasi(account_id, status, dibuat);

CREATE TABLE IF NOT EXISTS usulan_latihan (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    chat_id TEXT NOT NULL REFERENCES chat(id) ON DELETE RESTRICT,
    sumber_request_id TEXT NOT NULL UNIQUE
        REFERENCES operasi(request_id) ON DELETE RESTRICT,
    payload_json TEXT NOT NULL,
    hash_usulan TEXT NOT NULL CHECK (length(hash_usulan) = 64),
    versi INTEGER NOT NULL DEFAULT 1 CHECK (versi >= 1),
    chat_version INTEGER NOT NULL,
    consent_version INTEGER NOT NULL,
    context_version INTEGER NOT NULL,
    context_resource_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'menunggu'
        CHECK (status IN ('menunggu', 'selesai')),
    request_id_konfirmasi TEXT UNIQUE,
    sesi_id INTEGER,
    dibuat INTEGER NOT NULL,
    selesai INTEGER,
    CHECK ((status = 'menunggu' AND sesi_id IS NULL AND selesai IS NULL) OR
           (status = 'selesai' AND sesi_id IS NOT NULL AND selesai IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_usulan_pemilik_chat
    ON usulan_latihan(account_id, chat_id, status, dibuat);

-- Satu tinjauan terbaru per usulan; bukti review menyimpan hash token form.
-- Purge usulan juga menghapus bukti review, bukan ledger idempotensi DB belajar.
CREATE TABLE IF NOT EXISTS tinjauan_usulan (
    usulan_id TEXT PRIMARY KEY REFERENCES usulan_latihan(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash) = 64),
    ikatan_hash TEXT NOT NULL CHECK (length(ikatan_hash) = 64),
    dibuat INTEGER NOT NULL,
    kedaluarsa INTEGER NOT NULL CHECK (kedaluarsa > dibuat)
);
"""


def buka(path: Path | str | None = None) -> sqlite3.Connection:
    """Buka DB Pendamping dengan FK aktif dan hasil berbentuk Row."""
    tujuan = Path(path) if path is not None else BAWAAN
    kon = sqlite3.connect(tujuan)
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys = ON")
    return kon


def siapkan(path: Path | str | None = None) -> None:
    """Buat/naikkan skema secara idempoten dalam satu transaksi."""
    tujuan = Path(path) if path is not None else BAWAAN
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    with buka(tujuan) as kon:
        jurnal_wal.aktifkan(kon)
        versi = kon.execute("PRAGMA user_version").fetchone()[0]
        if versi > VERSI_SKEMA:
            raise RuntimeError("skema Pendamping lebih baru dari aplikasi")
        kon.executescript(_DDL)
        kolom_chat = {
            baris["name"] for baris in kon.execute("PRAGMA table_info(chat)")
        }
        if "context_resource_version" not in kolom_chat:
            kon.execute(
                "ALTER TABLE chat ADD COLUMN context_resource_version TEXT"
            )
        for nomor in range(1, VERSI_SKEMA + 1):
            kon.execute(
                "INSERT OR IGNORE INTO migrasi_pendamping(versi) VALUES (?)",
                (nomor,),
            )
        kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")
    tujuan.chmod(0o600)
