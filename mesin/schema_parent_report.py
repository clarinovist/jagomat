"""Skema laporan guru -> orang tua (G3): dua tabel aditif, tanpa kolom kontak.

`laporan_ortu` menyimpan snapshot presentasi (JSON allowlist) yang dibekukan saat
terbit. `tautan_laporan` adalah bearer baca-saja: hanya hash SHA-256 token yang
disimpan, satu tautan aktif per anak, dan FK komposit mencegah tautan menunjuk
laporan anak lain.
"""

SKEMA_LAPORAN_ORTU = """
CREATE TABLE IF NOT EXISTS laporan_ortu (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id          INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
    periode_mulai     TEXT    NOT NULL,
    periode_akhir     TEXT    NOT NULL,
    catatan           TEXT    NOT NULL DEFAULT '' CHECK (length(catatan) <= 2000),
    isi               TEXT    NOT NULL,
    guru              TEXT    NOT NULL DEFAULT '',
    dibuat            TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours')),
    diterbitkan       TEXT,
    kejadian_terakhir INTEGER NOT NULL DEFAULT 0,
    CHECK (periode_mulai <= periode_akhir),
    UNIQUE (id, siswa_id)
);
CREATE INDEX IF NOT EXISTS idx_laporan_ortu_siswa ON laporan_ortu(siswa_id, id);

CREATE TABLE IF NOT EXISTS tautan_laporan (
    siswa_id    INTEGER PRIMARY KEY REFERENCES siswa(id) ON DELETE CASCADE,
    laporan_id  INTEGER NOT NULL,
    token_hash  TEXT    NOT NULL UNIQUE,
    dibuat      INTEGER NOT NULL,
    kedaluarsa  INTEGER NOT NULL,
    dicabut     INTEGER,
    FOREIGN KEY (laporan_id, siswa_id)
        REFERENCES laporan_ortu(id, siswa_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tautan_laporan_hash ON tautan_laporan(token_hash);
"""
