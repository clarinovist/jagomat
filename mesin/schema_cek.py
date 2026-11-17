"""Skema cek kemampuan gratis (funnel Fase 2): satu tabel aditif dan idempoten.

Satu baris = satu cek untuk satu anak (`UNIQUE(siswa_id)` menegakkan "satu cek per
anak" di level basis data, bukan pembatas laju). Kunci kepemilikan hasil adalah
`id_akun` (ID acak dari `sandi.json`), bukan nama login.

Bahan mentah cek adalah baris `sesi` biasa (`sesi_id`, cascade ke jawaban dan
diagnosis). Setelah retensi, bahan itu dihapus dan `sesi_id` menjadi NULL
(`ON DELETE SET NULL` menjaga hal yang sama bila guru menghapus sesinya lebih
dulu), sedangkan turunan (`skor`, `kategori`, `ringkasan`) tetap ada.

`siswa_id` memakai `ON DELETE CASCADE`: anak yang dihapus guru/admin membawa
serta turunan skornya, tidak menyisakan hasil tentang anak yang sudah tidak ada.
Penghapusan keluarga (pseudonimisasi, bukan DELETE siswa) memakai hook
`cek_gratis.hapus_cek_keluarga`.

CHECK berlaku untuk semua baris karena tabel ini baru (CHECK tidak menyentuh
tabel lama, lihat catatan di `schema.py`). Kolom turunan hanya boleh terisi
bersamaan, sehingga skor tanpa kategori/waktu selesai tidak mungkin tersimpan.
"""

SKEMA_CEK_GRATIS = """
CREATE TABLE IF NOT EXISTS cek_gratis (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id           INTEGER NOT NULL UNIQUE REFERENCES siswa(id) ON DELETE CASCADE,
    id_akun            TEXT    NOT NULL
        CHECK (length(id_akun) = 37
               AND id_akun GLOB 'akun_*'
               AND substr(id_akun, 6) NOT GLOB '*[^0-9a-f]*'),
    sesi_id            INTEGER REFERENCES sesi(id) ON DELETE SET NULL,
    setuju_pada        TEXT    NOT NULL,
    versi_notice       TEXT    NOT NULL,
    dibuat             TEXT    NOT NULL,
    selesai_pada       TEXT,
    skor               INTEGER CHECK (skor IS NULL OR skor BETWEEN 0 AND 100),
    kategori           TEXT    CHECK (kategori IS NULL OR kategori IN (
        'Sangat baik', 'Cukup baik', 'Perlu penguatan', 'Perlu pendampingan')),
    ringkasan          TEXT,
    jumlah_soal        INTEGER NOT NULL DEFAULT 15 CHECK (jumlah_soal > 0),
    bahan_dihapus_pada TEXT,
    CHECK ((skor IS NULL AND kategori IS NULL AND ringkasan IS NULL
            AND selesai_pada IS NULL)
        OR (skor IS NOT NULL AND kategori IS NOT NULL AND ringkasan IS NOT NULL
            AND selesai_pada IS NOT NULL)),
    CHECK (bahan_dihapus_pada IS NULL OR sesi_id IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_cek_gratis_akun ON cek_gratis(id_akun);
"""
