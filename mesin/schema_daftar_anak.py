"""Skema pendaftaran akun anak: dua tabel aditif dan idempoten, tanpa migrasi.

`persetujuan_daftar_anak`: bukti orang tua/wali menyetujui saat mendaftarkan anak (satu baris per anak;
`versi_notice` = versi notice yang sama dengan `cek_gratis.versi_notice`). Ditulis di transaksi DB yang sama
dengan baris `siswa`. `pin_orang_tua`: hash PIN tirai halaman orang tua (format `auth.buat_hash`: garam,
kunci, iterasi); PIN mentah tidak pernah disimpan. PIN tirai bukan batas keamanan data. Keduanya terikat anak
(`siswa_id`, CASCADE) dan tanpa kolom kontak.
"""

SKEMA_DAFTAR_ANAK = """
CREATE TABLE IF NOT EXISTS persetujuan_daftar_anak (
    siswa_id     INTEGER PRIMARY KEY REFERENCES siswa(id) ON DELETE CASCADE,
    versi_notice TEXT NOT NULL CHECK (length(versi_notice) BETWEEN 1 AND 20),
    setuju_pada  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pin_orang_tua (
    siswa_id   INTEGER PRIMARY KEY REFERENCES siswa(id) ON DELETE CASCADE,
    garam      TEXT    NOT NULL CHECK (length(garam) > 0),
    kunci      TEXT    NOT NULL CHECK (length(kunci) > 0),
    iterasi    INTEGER NOT NULL CHECK (iterasi >= 1),
    dibuat     TEXT    NOT NULL,
    diperbarui TEXT    NOT NULL
);
"""
