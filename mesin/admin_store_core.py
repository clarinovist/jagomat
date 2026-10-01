"""Core koneksi dan kontrak schema SQLite pusat kendali admin."""
from __future__ import annotations

from pathlib import Path
import sqlite3


VERSI_SKEMA = 7


class StoreBelumSiap(RuntimeError):
    """Database admin belum dibootstrap atau tidak dapat dibuka aman."""


DDL = """
CREATE TABLE IF NOT EXISTS konfigurasi_pendaftaran (
    id INTEGER PRIMARY KEY CHECK (id=1),
    revisi INTEGER NOT NULL CHECK (revisi>=1),
    dibuka INTEGER NOT NULL CHECK (dibuka IN (0,1)),
    pesan_kode TEXT NOT NULL CHECK (
        pesan_kode IN ('closed_standard','closed_maintenance')
    ),
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS operasi_admin (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    aksi TEXT NOT NULL CHECK (aksi IN (
        'account_password_reset','account_session_revoke',
        'account_login_delete','student_login_delete_step','account_teacher_create',
        'student_login_create','student_level_update','student_school_grade_update','student_delete',
        'registration_config_update'
    )),
    jenis_target TEXT NOT NULL CHECK (
        jenis_target IN ('account','account_candidate','student','registration_config')
    ),
    target_id TEXT NOT NULL,
    target_peran TEXT CHECK (target_peran IS NULL OR target_peran IN ('guru','murid')),
    revisi_target INTEGER NOT NULL CHECK (revisi_target>=0),
    sidik_perintah TEXT NOT NULL CHECK (length(sidik_perintah)=64),
    status TEXT NOT NULL CHECK (status IN (
        'reserved','succeeded','failed_before_commit',
        'conflict','uncertain','cancelled'
    )),
    hasil_kode TEXT,
    revisi_hasil INTEGER,
    hasil_id TEXT,
    credential_status TEXT NOT NULL CHECK (
        credential_status IN ('not_applicable','unconfirmed','confirmed')
    ),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS receipt_admin (
    operasi_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    aksi TEXT NOT NULL CHECK(aksi IN ('student_level_update','student_school_grade_update','student_delete')),
    jenis_target TEXT NOT NULL CHECK(jenis_target='student'),
    target_id TEXT NOT NULL,
    sidik_perintah TEXT NOT NULL CHECK(length(sidik_perintah)=64),
    hasil_kode TEXT NOT NULL CHECK(hasil_kode IN ('student_level_updated','student_school_grade_updated','student_deleted')),
    dibuat INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_admin (
    id INTEGER PRIMARY KEY,
    operasi_id TEXT NOT NULL REFERENCES operasi_admin(operasi_id) ON DELETE RESTRICT,
    actor_id TEXT NOT NULL,
    aksi TEXT NOT NULL,
    jenis_target TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_peran TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'succeeded','failed_before_commit','conflict','uncertain','cancelled'
    )),
    hasil_kode TEXT NOT NULL CHECK (hasil_kode IN (
        'password_reset','sessions_revoked','login_deleted','teacher_created',
        'student_login_created','student_level_updated','student_school_grade_updated','student_deleted','config_updated',
        'target_changed','input_rejected','domain_not_committed','domain_uncertain'
    )),
    dibuat INTEGER NOT NULL,
    UNIQUE (operasi_id,status)
);
CREATE INDEX IF NOT EXISTS idx_audit_admin_waktu
    ON audit_admin(dibuat DESC,id DESC);
CREATE TABLE IF NOT EXISTS audit_admin_perubahan (
    audit_id INTEGER NOT NULL REFERENCES audit_admin(id) ON DELETE CASCADE,
    field_kode TEXT NOT NULL,
    nilai_lama TEXT NOT NULL,
    nilai_baru TEXT NOT NULL,
    PRIMARY KEY (audit_id,field_kode)
);
CREATE TABLE IF NOT EXISTS batch_admin (
    batch_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    session_hash TEXT NOT NULL CHECK(length(session_hash)=64),
    aksi TEXT NOT NULL CHECK(aksi IN (
        'account_teacher_create','account_password_reset','account_session_revoke'
    )),
    target_peran TEXT NOT NULL CHECK(target_peran IN ('guru','murid')),
    jumlah_total INTEGER NOT NULL CHECK(jumlah_total BETWEEN 1 AND 100),
    status TEXT NOT NULL CHECK(status IN (
        'ready','running','partial','stopped','succeeded','attention'
    )),
    kelompok_aktif_id TEXT,
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS batch_admin_item (
    batch_id TEXT NOT NULL REFERENCES batch_admin(batch_id) ON DELETE RESTRICT,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    operasi_id TEXT NOT NULL UNIQUE,
    target_id TEXT NOT NULL,
    target_revisi INTEGER NOT NULL CHECK(target_revisi>=0),
    status TEXT NOT NULL CHECK(status IN (
        'pending','succeeded','failed_before_commit','conflict','uncertain','cancelled'
    )),
    hasil_id TEXT,
    credential_status TEXT NOT NULL CHECK(
        credential_status IN ('not_applicable','unconfirmed','confirmed')
    ),
    diperbarui INTEGER NOT NULL,
    PRIMARY KEY(batch_id,item_id),
    UNIQUE(batch_id,target_id)
);
CREATE TABLE IF NOT EXISTS kelompok_admin (
    kelompok_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batch_admin(batch_id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK(status IN ('running','completed','attention')),
    dibuat INTEGER NOT NULL,
    diperbarui INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kelompok_admin_item (
    kelompok_id TEXT NOT NULL REFERENCES kelompok_admin(kelompok_id) ON DELETE RESTRICT,
    batch_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    urutan INTEGER NOT NULL,
    PRIMARY KEY(kelompok_id,item_id),
    FOREIGN KEY(batch_id,item_id) REFERENCES batch_admin_item(batch_id,item_id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS penyerahan_admin (
    operasi_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL REFERENCES batch_admin(batch_id) ON DELETE RESTRICT,
    actor_id TEXT NOT NULL,
    actor_revisi INTEGER NOT NULL CHECK(actor_revisi>=0),
    sidik_item TEXT NOT NULL CHECK(length(sidik_item)=64),
    jumlah INTEGER NOT NULL CHECK(jumlah BETWEEN 1 AND 100),
    dibuat INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS penyerahan_admin_item (
    operasi_id TEXT NOT NULL REFERENCES penyerahan_admin(operasi_id) ON DELETE RESTRICT,
    batch_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    PRIMARY KEY(operasi_id,item_id),
    FOREIGN KEY(batch_id,item_id) REFERENCES batch_admin_item(batch_id,item_id) ON DELETE RESTRICT
);
"""

KOLOM_WAJIB = {
    "konfigurasi_pendaftaran": {
        "id", "revisi", "dibuka", "pesan_kode", "diperbarui",
    },
    "operasi_admin": {
        "operasi_id", "actor_id", "aksi", "jenis_target", "target_id",
        "target_peran", "revisi_target", "sidik_perintah", "status",
        "hasil_kode", "revisi_hasil", "hasil_id", "credential_status", "dibuat",
        "diperbarui",
    },
    "receipt_admin": {
        "operasi_id", "actor_id", "aksi", "jenis_target", "target_id",
        "sidik_perintah", "hasil_kode", "dibuat",
    },
    "audit_admin": {
        "id", "operasi_id", "actor_id", "aksi", "jenis_target",
        "target_id", "target_peran", "status", "hasil_kode", "dibuat",
    },
    "audit_admin_perubahan": {
        "audit_id", "field_kode", "nilai_lama", "nilai_baru",
    },
    "batch_admin": {
        "batch_id", "actor_id", "actor_revisi", "session_hash", "aksi",
        "target_peran", "jumlah_total", "status", "kelompok_aktif_id",
        "dibuat", "diperbarui",
    },
    "batch_admin_item": {
        "batch_id", "item_id", "urutan", "operasi_id", "target_id",
        "target_revisi", "status", "hasil_id", "credential_status",
        "diperbarui",
    },
    "kelompok_admin": {
        "kelompok_id", "batch_id", "status", "dibuat", "diperbarui",
    },
    "kelompok_admin_item": {
        "kelompok_id", "batch_id", "item_id", "urutan",
    },
    "penyerahan_admin": {
        "operasi_id", "batch_id", "actor_id", "actor_revisi",
        "sidik_item", "jumlah", "dibuat",
    },
    "penyerahan_admin_item": {
        "operasi_id", "batch_id", "item_id",
    },
}

def uri(path: Path, mode: str) -> str:
    return path.resolve().as_uri() + "?mode=" + mode

def koneksi(path: Path, mode: str) -> sqlite3.Connection:
    try:
        kon = sqlite3.connect(uri(path, mode), uri=True, timeout=5.0)
    except sqlite3.Error as galat:
        raise StoreBelumSiap("store admin tidak tersedia") from galat
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA foreign_keys=ON")
    kon.execute("PRAGMA busy_timeout=5000")
    return kon

def validasi_skema(kon: sqlite3.Connection) -> None:
    versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
    import subscription_package_schema as paket_schema
    import assistant_quota_schema as kuota_schema
    if versi > kuota_schema.VERSI_SKEMA:
        raise StoreBelumSiap("skema admin lebih baru dari aplikasi")
    if versi not in (VERSI_SKEMA, paket_schema.VERSI_SKEMA, kuota_schema.VERSI_SKEMA):
        raise StoreBelumSiap("store admin belum dimigrasikan")
    try:
        if versi >= paket_schema.VERSI_SKEMA:
            paket_schema.validasi(kon)
        elif paket_schema.struktur(kon):
            raise ValueError("tabel paket tanpa versi migrasi")
    except (ValueError, sqlite3.Error):
        raise StoreBelumSiap("struktur ledger paket tidak lengkap") from None
    try:
        if versi == kuota_schema.VERSI_SKEMA:
            kuota_schema.validasi(kon)
        elif kuota_schema.struktur(kon):
            raise ValueError("tabel kuota tanpa versi migrasi")
    except (ValueError, sqlite3.Error):
        raise StoreBelumSiap("struktur ledger kuota tidak lengkap") from None
    for tabel, wajib in KOLOM_WAJIB.items():
        aktual = {
            str(baris[1]) for baris in kon.execute("PRAGMA table_info(%s)" % tabel)
        }
        if not wajib <= aktual:
            raise StoreBelumSiap("struktur store admin tidak lengkap")
    import subscription_schema
    try:
        subscription_schema.validasi(kon)
        subscription_schema.validasi_penutupan(kon)
    except (ValueError, sqlite3.Error):
        raise StoreBelumSiap("struktur ledger langganan tidak lengkap") from None
    import admin_launch_schema
    try:
        admin_launch_schema.validasi(kon)
    except (ValueError, sqlite3.Error):
        raise StoreBelumSiap("struktur layanan admin tidak lengkap") from None
    # Konfigurasi dukungan adalah schema aditif opt-in tanpa bump user_version:
    # absent masih sah sebelum migrasi, tetapi struktur parsial harus fail-closed.
    import support_settings
    try:
        support_settings.validasi_schema(kon)
    except (ValueError, sqlite3.Error):
        raise StoreBelumSiap("struktur dukungan tidak lengkap") from None

def jalankan_ddl(kon: sqlite3.Connection, skrip: str) -> None:
    """Jalankan DDL utuh tanpa implicit commit dari ``executescript``."""
    bagian = ""
    for baris in skrip.splitlines(keepends=True):
        bagian += baris
        if sqlite3.complete_statement(bagian):
            kon.execute(bagian)
            bagian = ""
    if bagian.strip():
        raise StoreBelumSiap("DDL store admin tidak lengkap")
