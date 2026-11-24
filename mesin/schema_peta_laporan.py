"""Skema laporan Peta Kemampuan untuk orang tua (D1-1): satu tabel aditif, ditulis dan diterbitkan Guru.

`peta_laporan` menyimpan SATU laporan per anak: snapshot isi (JSON allowlist yang dibekukan saat draf dibuat,
karena data per materi cek gratis hilang oleh retensi 30 hari), catatan Guru, dan keadaan terbit. Tanpa FK ke
`sesi`/`cek_gratis` supaya tidak menahan sapuan retensi, dan tanpa kolom kontak atau nama anak.

Penjagaan (trigger, bukan hanya kode):
- laporan yang sudah terbit tidak dapat di-UPDATE sama sekali;
- `id`, `siswa_id`, `isi`, `guru`, `dibuat` tidak pernah berubah lewat UPDATE (hanya catatan dan kolom terbit);
- TERBIT hanya bila catatan (setelah dipangkas spasi/tab/baris baru) tidak kosong;
- baris baru wajib berstatus draf (INSERT yang langsung terbit ditolak).

SENGAJA tanpa trigger DELETE: penghapusan anak (`ON DELETE CASCADE`) dan `family_deletion` (penghapusan eksplisit,
karena siswa hanya dianonimkan) harus tetap menghapus baris laporan, termasuk yang sudah terbit (privasi). Larangan
menghapus laporan terbit oleh Guru ditegakkan di `peta_laporan_store.hapus_draf`.
"""

SKEMA_PETA_LAPORAN = """
CREATE TABLE IF NOT EXISTS peta_laporan (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    siswa_id         INTEGER NOT NULL UNIQUE REFERENCES siswa(id) ON DELETE CASCADE,
    isi              TEXT    NOT NULL CHECK (length(isi) BETWEEN 2 AND 8000),
    catatan          TEXT    NOT NULL DEFAULT '' CHECK (length(catatan) <= 2000),
    guru             TEXT    NOT NULL CHECK (length(guru) BETWEEN 1 AND 64),
    dibuat           TEXT    NOT NULL,
    diterbitkan      TEXT,
    diterbitkan_oleh TEXT,
    CHECK ((diterbitkan IS NULL) = (diterbitkan_oleh IS NULL)),
    CHECK (diterbitkan_oleh IS NULL OR length(diterbitkan_oleh) BETWEEN 1 AND 64)
);

CREATE TRIGGER IF NOT EXISTS peta_laporan_insert_draf BEFORE INSERT ON peta_laporan
WHEN NEW.diterbitkan IS NOT NULL OR NEW.diterbitkan_oleh IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'laporan peta harus dibuat sebagai draf'); END;

CREATE TRIGGER IF NOT EXISTS peta_laporan_terbit_tetap BEFORE UPDATE ON peta_laporan
WHEN OLD.diterbitkan IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'laporan peta terbit tidak dapat diubah'); END;

CREATE TRIGGER IF NOT EXISTS peta_laporan_isi_tetap BEFORE UPDATE ON peta_laporan
WHEN NEW.id IS NOT OLD.id OR NEW.siswa_id IS NOT OLD.siswa_id OR NEW.isi IS NOT OLD.isi
  OR NEW.guru IS NOT OLD.guru OR NEW.dibuat IS NOT OLD.dibuat
BEGIN SELECT RAISE(ABORT, 'isi laporan peta tidak dapat diubah'); END;

CREATE TRIGGER IF NOT EXISTS peta_laporan_terbit_butuh_catatan BEFORE UPDATE ON peta_laporan
WHEN NEW.diterbitkan IS NOT NULL AND length(trim(NEW.catatan, ' ' || char(9, 10, 13))) = 0
BEGIN SELECT RAISE(ABORT, 'laporan peta tidak dapat terbit tanpa catatan'); END;
"""
