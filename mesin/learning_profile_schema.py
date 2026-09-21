"""Metadata kelas sekolah aditif; tidak menafsirkan ulang tingkat warisan."""

SKEMA_PROFIL_BELAJAR = """
-- Belum ada baris berarti kelas sekolah belum dikonfirmasi, bukan kelas P3.
-- Metadata ini bukan bukti pedagogis dan tidak menahan penghapusan anak yang sah.
CREATE TABLE IF NOT EXISTS profil_belajar (
    siswa_id INTEGER PRIMARY KEY REFERENCES siswa(id) ON DELETE CASCADE,
    kelas_sekolah INTEGER CHECK (
        kelas_sekolah IS NULL OR
        (typeof(kelas_sekolah) = 'integer' AND kelas_sekolah BETWEEN 1 AND 6)
    ),
    revisi INTEGER NOT NULL CHECK (typeof(revisi) = 'integer' AND revisi > 0)
);
"""
