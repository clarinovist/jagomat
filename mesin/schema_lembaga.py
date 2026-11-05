"""Skema lembaga les (pemilik les): tiga tabel aditif dan idempoten.

`lembaga` mengikat satu akun guru sebagai pemilik. `anggota_lembaga` memuat
guru anggota (pemilik bersifat implisit, bukan baris anggota); satu guru hanya
boleh masuk satu lembaga. `pindah_siswa` adalah jejak pemindahan anak antar guru
di lembaga yang sama: tidak boleh dihapus langsung dan kolom intinya tidak boleh
berubah. Kolom nama guru (`dari`/`ke`/`oleh`) sengaja boleh diubah karena
penghapusan keluarga memseudonimkannya. Tanpa kolom kontak apa pun.
"""

SKEMA_LEMBAGA = """
CREATE TABLE IF NOT EXISTS lembaga (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nama    TEXT NOT NULL CHECK (length(trim(nama)) BETWEEN 1 AND 80),
    pemilik TEXT NOT NULL UNIQUE,
    dibuat  TEXT NOT NULL DEFAULT (datetime('now', '+7 hours'))
);

CREATE TABLE IF NOT EXISTS anggota_lembaga (
    lembaga_id INTEGER NOT NULL REFERENCES lembaga(id) ON DELETE CASCADE,
    guru       TEXT    NOT NULL UNIQUE,
    dibuat     TEXT    NOT NULL DEFAULT (datetime('now', '+7 hours')),
    PRIMARY KEY (lembaga_id, guru)
);

CREATE TABLE IF NOT EXISTS pindah_siswa (
    id         INTEGER PRIMARY KEY,
    siswa_id   INTEGER NOT NULL REFERENCES siswa(id) ON DELETE CASCADE,
    lembaga_id INTEGER,
    dari       TEXT NOT NULL,
    ke         TEXT NOT NULL,
    oleh       TEXT NOT NULL,
    dibuat     TEXT NOT NULL DEFAULT (datetime('now', '+7 hours'))
);
CREATE INDEX IF NOT EXISTS idx_pindah_siswa_siswa ON pindah_siswa(siswa_id, id);

-- Hapus langsung ditolak selama anaknya masih ada; hapus berantai karena
-- anaknya dihapus (siswa sudah tidak ada saat trigger berjalan) diizinkan.
CREATE TRIGGER IF NOT EXISTS pindah_siswa_tolak_delete
BEFORE DELETE ON pindah_siswa
WHEN EXISTS (SELECT 1 FROM siswa WHERE id = OLD.siswa_id) BEGIN
    SELECT RAISE(ABORT, 'pindah_siswa append-only');
END;
CREATE TRIGGER IF NOT EXISTS pindah_siswa_tolak_ubah_inti
BEFORE UPDATE OF id, siswa_id, lembaga_id, dibuat ON pindah_siswa BEGIN
    SELECT RAISE(ABORT, 'pindah_siswa append-only');
END;
"""
