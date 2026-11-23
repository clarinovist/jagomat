"""Skema Latihan Harian per tingkat: tiga tabel aditif dan idempoten, tanpa migrasi, terpisah dari tabel lomba.

`harian_sesi`: satu sesi 10 soal; indeks unik parsial menjamin SATU sesi berjalan per anak walau dua permintaan
"Mulai" datang bersamaan. `seed` (dari `secrets`) disimpan supaya sesi dapat dirakit ulang; waktu = epoch detik
jam server. `harian_soal`: snapshot soal yang sudah dirender saat sesi dibuat (penyajian, empat opsi, indeks
kunci, pembahasan) supaya mengubah template kelak tidak mengubah riwayat; halaman soal hanya membaca kolom aman,
kunci dan pembahasan baru dibaca setelah jawaban soal itu terkunci. `harian_jawaban`: satu jawaban per soal
(`PRIMARY KEY (sesi_id, nomor)`; jawaban kedua ditolak oleh PK), berisi pilihan dan hasil benar/salah.
Bukan bukti siklus belajar: tidak ada FK ke tabel sesi/diagnosis/learning_cycle. Semua milik siswa dan ikut terhapus
bersama siswa (ON DELETE CASCADE); `family_deletion` menghapusnya eksplisit karena siswa hanya dianonimkan.
"""

SKEMA_HARIAN_LATIHAN = """
CREATE TABLE IF NOT EXISTS harian_sesi (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id      INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
    tingkat       TEXT    NOT NULL CHECK (tingkat IN ('t1', 't2', 't3', 't4', 't5', 't6', 'osn-pemula', 'osn-lanjut')),
    seed          INTEGER NOT NULL CHECK (seed BETWEEN 1 AND 2147483647),
    jumlah_soal   INTEGER NOT NULL CHECK (jumlah_soal BETWEEN 1 AND 10),
    mulai_epoch   INTEGER NOT NULL,
    selesai_epoch INTEGER,
    status        TEXT    NOT NULL CHECK (status IN ('berjalan', 'selesai')),
    CHECK ((status = 'berjalan') = (selesai_epoch IS NULL)),
    CHECK (selesai_epoch IS NULL OR selesai_epoch >= mulai_epoch)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_harian_sesi_berjalan ON harian_sesi(siswa_id) WHERE status = 'berjalan';
CREATE INDEX IF NOT EXISTS idx_harian_sesi_siswa ON harian_sesi(siswa_id, mulai_epoch);

CREATE TABLE IF NOT EXISTS harian_soal (
    sesi_id        INTEGER NOT NULL REFERENCES harian_sesi(id) ON DELETE CASCADE,
    nomor          INTEGER NOT NULL CHECK (nomor BETWEEN 1 AND 10),
    template_id    TEXT    NOT NULL,
    topik_id       TEXT    NOT NULL,
    level          TEXT    NOT NULL,
    sumber         TEXT    NOT NULL,
    ulangan        INTEGER NOT NULL CHECK (ulangan IN (0, 1)),
    tanda_tangan   TEXT    NOT NULL,
    penyajian_json TEXT    NOT NULL,
    opsi_json      TEXT    NOT NULL,
    kunci_indeks   INTEGER NOT NULL CHECK (kunci_indeks BETWEEN 0 AND 3),
    pembahasan     TEXT    NOT NULL CHECK (length(pembahasan) > 0),
    PRIMARY KEY (sesi_id, nomor)
);

CREATE TABLE IF NOT EXISTS harian_jawaban (
    sesi_id       INTEGER NOT NULL,
    nomor         INTEGER NOT NULL,
    pilihan       INTEGER NOT NULL CHECK (pilihan BETWEEN 0 AND 3),
    benar         INTEGER NOT NULL CHECK (benar IN (0, 1)),
    dijawab_epoch INTEGER NOT NULL,
    PRIMARY KEY (sesi_id, nomor),
    FOREIGN KEY (sesi_id, nomor) REFERENCES harian_soal(sesi_id, nomor) ON DELETE CASCADE
);
"""
