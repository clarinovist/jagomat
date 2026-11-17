"""Skema kontak WhatsApp per akun: satu tabel aditif dan idempoten.

Kunci `id_akun` (ID acak dari `sandi.json`), bukan nama login, supaya nama login
yang dipakai ulang tidak mewarisi kontak lama. Tabel ini sengaja berdiri sendiri:
tanpa foreign key ke `siswa` dan tanpa kolom nama anak, karena kontak hanya milik
orang dewasa pembayar dan tidak boleh tertaut ke data belajar anak.

CHECK memeriksa bentuk nomor ternormalisasi (62 + 8 + 8..12 digit, hanya angka);
tabel ini baru sehingga CHECK berlaku untuk semua baris (CHECK tidak menyentuh
tabel lama, lihat catatan di `schema.py`).
"""

SKEMA_KONTAK_AKUN = """
CREATE TABLE IF NOT EXISTS kontak_akun (
    id_akun            TEXT PRIMARY KEY,
    wa                 TEXT NOT NULL
        CHECK (length(wa) BETWEEN 11 AND 15
               AND wa GLOB '628*'
               AND wa NOT GLOB '*[^0-9]*'),
    dibuat             TEXT NOT NULL,
    diperbarui         TEXT NOT NULL,
    aktivitas_terakhir TEXT NOT NULL
);
"""
