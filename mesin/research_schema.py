"""Schema SQLite terpisah untuk data wawancara riset konsumen."""
from __future__ import annotations

import sqlite3


VERSI_SKEMA = 1

DDL = """
CREATE TABLE studi_riset (
    slug TEXT PRIMARY KEY CHECK(length(slug) BETWEEN 3 AND 80),
    judul TEXT NOT NULL CHECK(length(trim(judul)) BETWEEN 1 AND 160),
    target TEXT NOT NULL CHECK(length(trim(target)) BETWEEN 1 AND 500),
    status TEXT NOT NULL CHECK(status IN ('aktif','ditutup')),
    dibuat INTEGER NOT NULL CHECK(dibuat>=0),
    ditutup INTEGER CHECK(ditutup IS NULL OR ditutup>=dibuat)
);
CREATE TABLE instrumen_riset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    studi_slug TEXT NOT NULL REFERENCES studi_riset(slug) ON DELETE RESTRICT,
    kode_versi TEXT NOT NULL UNIQUE CHECK(length(kode_versi) BETWEEN 3 AND 80),
    snapshot_json TEXT NOT NULL CHECK(length(snapshot_json) BETWEEN 2 AND 65535),
    sidik TEXT NOT NULL UNIQUE CHECK(length(sidik)=64),
    diterbitkan INTEGER NOT NULL CHECK(diterbitkan>=0)
);
CREATE TABLE wawancara_riset (
    id TEXT PRIMARY KEY CHECK(length(id)=36 AND substr(id,1,4)='waw_'),
    studi_slug TEXT NOT NULL REFERENCES studi_riset(slug) ON DELETE RESTRICT,
    instrumen_id INTEGER NOT NULL REFERENCES instrumen_riset(id) ON DELETE RESTRICT,
    kode_responden TEXT NOT NULL CHECK(length(kode_responden) BETWEEN 3 AND 32),
    actor_id TEXT NOT NULL CHECK(length(actor_id) BETWEEN 8 AND 80),
    sumber TEXT NOT NULL CHECK(sumber IN ('meta_ads','referensi','komunitas','internal','lainnya')),
    consent_wawancara INTEGER NOT NULL CHECK(consent_wawancara=1),
    consent_rekaman INTEGER NOT NULL CHECK(consent_rekaman IN (0,1)),
    status TEXT NOT NULL CHECK(status IN ('draf','final','perlu_redaksi','ditarik')),
    revisi INTEGER NOT NULL CHECK(revisi>=1),
    diwawancarai INTEGER NOT NULL CHECK(diwawancarai>=0),
    dibuat INTEGER NOT NULL CHECK(dibuat>=0),
    diperbarui INTEGER NOT NULL CHECK(diperbarui>=dibuat),
    difinalkan INTEGER CHECK(difinalkan IS NULL OR difinalkan>=dibuat),
    retensi_hingga INTEGER NOT NULL CHECK(retensi_hingga>dibuat),
    UNIQUE(studi_slug,kode_responden),
    CHECK((status='final' AND difinalkan IS NOT NULL)
          OR (status!='final' AND difinalkan IS NULL))
);
CREATE INDEX idx_wawancara_riset_status ON wawancara_riset(status,diperbarui DESC);
CREATE INDEX idx_wawancara_riset_retensi ON wawancara_riset(retensi_hingga,status);
CREATE TABLE jawaban_riset (
    wawancara_id TEXT NOT NULL REFERENCES wawancara_riset(id) ON DELETE CASCADE,
    pertanyaan_kode TEXT NOT NULL CHECK(length(pertanyaan_kode) BETWEEN 2 AND 8),
    status_jawaban TEXT NOT NULL CHECK(status_jawaban IN ('dijawab','tidak_dibahas','tidak_tahu','menolak')),
    jawaban_responden TEXT NOT NULL CHECK(length(jawaban_responden)<=6000),
    kutipan_responden TEXT NOT NULL CHECK(length(kutipan_responden)<=2000),
    kutipan_terpilih INTEGER NOT NULL CHECK(kutipan_terpilih IN (0,1)),
    catatan_interviewer TEXT NOT NULL CHECK(length(catatan_interviewer)<=4000),
    kode_utama TEXT CHECK(kode_utama IS NULL OR length(kode_utama) BETWEEN 3 AND 64),
    status_klarifikasi TEXT NOT NULL CHECK(status_klarifikasi IN ('tidak_perlu','sudah','ambigu')),
    revisi INTEGER NOT NULL CHECK(revisi>=1),
    diperbarui INTEGER NOT NULL CHECK(diperbarui>=0),
    PRIMARY KEY(wawancara_id,pertanyaan_kode),
    CHECK(status_jawaban='dijawab' OR (
        jawaban_responden='' AND kutipan_responden='' AND kutipan_terpilih=0
        AND kode_utama IS NULL
    ))
);
CREATE TABLE kode_tambahan_riset (
    wawancara_id TEXT NOT NULL,
    pertanyaan_kode TEXT NOT NULL,
    kode TEXT NOT NULL CHECK(length(kode) BETWEEN 3 AND 64),
    PRIMARY KEY(wawancara_id,pertanyaan_kode,kode),
    FOREIGN KEY(wawancara_id,pertanyaan_kode)
        REFERENCES jawaban_riset(wawancara_id,pertanyaan_kode) ON DELETE CASCADE
);
CREATE TABLE audit_riset (
    operasi_id TEXT PRIMARY KEY CHECK(length(operasi_id)=35 AND substr(operasi_id,1,3)='op_'),
    actor_id TEXT NOT NULL CHECK(length(actor_id) BETWEEN 8 AND 80),
    aksi TEXT NOT NULL CHECK(aksi IN (
        'buat','ubah_jawaban','finalisasi','buka_koreksi',
        'tandai_redaksi','tarik_consent','ekspor','hapus_retensi'
    )),
    target_id TEXT NOT NULL CHECK(length(target_id) BETWEEN 5 AND 80),
    sidik_perintah TEXT NOT NULL CHECK(length(sidik_perintah)=64),
    hasil TEXT NOT NULL CHECK(hasil='sukses'),
    dibuat INTEGER NOT NULL CHECK(dibuat>=0)
);
CREATE INDEX idx_audit_riset_target ON audit_riset(target_id,dibuat DESC);
CREATE TRIGGER studi_riset_tolak_delete BEFORE DELETE ON studi_riset
BEGIN SELECT RAISE(ABORT,'studi riset tidak boleh dihapus'); END;
CREATE TRIGGER instrumen_riset_tolak_update BEFORE UPDATE ON instrumen_riset
BEGIN SELECT RAISE(ABORT,'instrumen riset immutable'); END;
CREATE TRIGGER instrumen_riset_tolak_delete BEFORE DELETE ON instrumen_riset
BEGIN SELECT RAISE(ABORT,'instrumen riset immutable'); END;
CREATE TRIGGER audit_riset_tolak_update BEFORE UPDATE ON audit_riset
BEGIN SELECT RAISE(ABORT,'audit riset immutable'); END;
CREATE TRIGGER audit_riset_tolak_delete BEFORE DELETE ON audit_riset
BEGIN SELECT RAISE(ABORT,'audit riset immutable'); END;
CREATE TRIGGER audit_riset_tolak_replace BEFORE INSERT ON audit_riset
WHEN EXISTS(SELECT 1 FROM audit_riset WHERE operasi_id=NEW.operasi_id)
BEGIN SELECT RAISE(ABORT,'operasi riset duplikat'); END;
"""

KOLOM = {
    "studi_riset": {"slug", "judul", "target", "status", "dibuat", "ditutup"},
    "instrumen_riset": {"id", "studi_slug", "kode_versi", "snapshot_json", "sidik", "diterbitkan"},
    "wawancara_riset": {
        "id", "studi_slug", "instrumen_id", "kode_responden", "actor_id", "sumber",
        "consent_wawancara", "consent_rekaman", "status", "revisi", "diwawancarai",
        "dibuat", "diperbarui", "difinalkan", "retensi_hingga",
    },
    "jawaban_riset": {
        "wawancara_id", "pertanyaan_kode", "status_jawaban", "jawaban_responden",
        "kutipan_responden", "kutipan_terpilih", "catatan_interviewer", "kode_utama",
        "status_klarifikasi", "revisi", "diperbarui",
    },
    "kode_tambahan_riset": {"wawancara_id", "pertanyaan_kode", "kode"},
    "audit_riset": {"operasi_id", "actor_id", "aksi", "target_id", "sidik_perintah", "hasil", "dibuat"},
}
TRIGGER = frozenset((
    "studi_riset_tolak_delete", "instrumen_riset_tolak_update",
    "instrumen_riset_tolak_delete", "audit_riset_tolak_update",
    "audit_riset_tolak_delete", "audit_riset_tolak_replace",
))


def jalankan_ddl(kon: sqlite3.Connection, skrip: str) -> None:
    bagian = ""
    for baris in skrip.splitlines(keepends=True):
        bagian += baris
        if sqlite3.complete_statement(bagian):
            kon.execute(bagian)
            bagian = ""
    if bagian.strip():
        raise ValueError("DDL riset tidak lengkap")


def validasi(kon: sqlite3.Connection) -> None:
    if int(kon.execute("PRAGMA user_version").fetchone()[0]) != VERSI_SKEMA:
        raise ValueError("versi database riset tidak sah")
    for tabel, wajib in KOLOM.items():
        aktual = {str(baris[1]) for baris in kon.execute("PRAGMA table_info(%s)" % tabel)}
        if aktual != wajib:
            raise ValueError("struktur database riset tidak lengkap")
    trigger = {
        str(baris[0]) for baris in kon.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )
    }
    if not TRIGGER <= trigger:
        raise ValueError("pengaman database riset tidak lengkap")
    if kon.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise ValueError("foreign key database riset tidak sah")
