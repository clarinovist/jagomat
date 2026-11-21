"""Skema Latihan Lomba (Grand Final Corexis): tiga tabel aditif, terpisah dari tabel sesi guru.

`lomba_sesi` menyimpan batas waktu sebagai epoch detik dari jam server; indeks unik parsial
menjamin satu sesi berjalan per anak walau dua permintaan "Mulai" datang bersamaan.
`lomba_soal` menyimpan soal yang sudah dirender (utuh, termasuk kunci dan pembahasan) supaya
mengubah template kelak tidak mengubah riwayat; halaman anak hanya boleh membaca kolom aman.
`lomba_jawaban` menyimpan jawaban terakhir per nomor. Semua milik siswa dan ikut terhapus
bersama siswa (ON DELETE CASCADE), seperti `laporan_ortu`.
"""

SKEMA_LOMBA = """
CREATE TABLE IF NOT EXISTS lomba_sesi (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id      INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
    paket_id      TEXT    NOT NULL,
    seed          INTEGER NOT NULL,
    mulai_epoch   INTEGER NOT NULL,
    batas_epoch   INTEGER NOT NULL,
    selesai_epoch INTEGER,
    status        TEXT    NOT NULL CHECK (status IN ('berjalan', 'dikumpul', 'waktu_habis')),
    CHECK (batas_epoch > mulai_epoch),
    CHECK ((status = 'berjalan') = (selesai_epoch IS NULL)),
    CHECK (selesai_epoch IS NULL
           OR (selesai_epoch >= mulai_epoch AND selesai_epoch <= batas_epoch))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_lomba_sesi_berjalan ON lomba_sesi(siswa_id) WHERE status = 'berjalan';
CREATE INDEX IF NOT EXISTS idx_lomba_sesi_siswa ON lomba_sesi(siswa_id, id);

CREATE TABLE IF NOT EXISTS lomba_soal (
    sesi_id              INTEGER NOT NULL REFERENCES lomba_sesi(id) ON DELETE CASCADE,
    nomor                INTEGER NOT NULL CHECK (nomor BETWEEN 1 AND 10),
    template_id          TEXT    NOT NULL,
    topik                TEXT    NOT NULL,
    jenis                TEXT    NOT NULL CHECK (jenis IN ('pg', 'isian')),
    tingkat              INTEGER NOT NULL CHECK (tingkat BETWEEN 1 AND 3),
    tanda_tangan         TEXT    NOT NULL,
    parameter            TEXT    NOT NULL,
    inggris              INTEGER NOT NULL DEFAULT 0 CHECK (inggris IN (0, 1)),
    teks                 TEXT    NOT NULL,
    svg                  TEXT    NOT NULL DEFAULT '',
    kunci                TEXT    NOT NULL,
    pilihan_json         TEXT    NOT NULL DEFAULT '[]',
    gambar_pilihan_json  TEXT    NOT NULL DEFAULT '[]',
    posisi_kunci         INTEGER NOT NULL CHECK (posisi_kunci BETWEEN -1 AND 3),
    pengecoh_json        TEXT    NOT NULL DEFAULT '[]',
    pembahasan_json      TEXT    NOT NULL,
    PRIMARY KEY (sesi_id, nomor)
);

CREATE TABLE IF NOT EXISTS lomba_jawaban (
    sesi_id      INTEGER NOT NULL,
    nomor        INTEGER NOT NULL,
    jawaban      TEXT    NOT NULL CHECK (length(jawaban) BETWEEN 1 AND 6),
    diubah_epoch INTEGER NOT NULL,
    PRIMARY KEY (sesi_id, nomor),
    FOREIGN KEY (sesi_id, nomor) REFERENCES lomba_soal(sesi_id, nomor) ON DELETE CASCADE
);
"""
