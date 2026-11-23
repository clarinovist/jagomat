"""PIN tirai halaman orang tua: simpan hash, periksa waktu-tetap, hapus.

Format hash = `auth.buat_hash` (PBKDF2, garam acak, iterasi tersimpan); PIN mentah tidak pernah disimpan,
dicatat, atau dimasukkan ke receipt/log. Perbandingan memakai `auth.periksa` (compare_digest). PIN 4 digit
tidak tahan tebakan luring: ini TIRAI, bukan batas keamanan data; jeda/laju percobaan ada di lapisan HTTP (F3).
Semua fungsi bekerja di transaksi pemanggil dan tidak commit sendiri.
"""
from __future__ import annotations

import re

import auth
from daftar_anak_store import waktu_utc

PESAN_PIN_TIDAK_SAH = "PIN harus 4 angka."
_POLA_PIN = re.compile(r"[0-9]{4}")
_PENGGUNA_PIN = "pin"
_KOLOM_HASH = ("garam", "kunci", "iterasi")


def pin_sah(pin) -> bool:
    """True hanya untuk str berisi tepat 4 digit ASCII."""
    return type(pin) is str and _POLA_PIN.fullmatch(pin) is not None


def buat_hash_pin(pin: str) -> dict:
    """Hash PIN (garam acak) siap disimpan; menolak PIN yang bukan 4 digit."""
    if not pin_sah(pin):
        raise ValueError(PESAN_PIN_TIDAK_SAH)
    return auth.buat_hash(pin)


def simpan_hash(kon, siswa_id: int, hash_pin: dict, kini: int) -> None:
    """Upsert hash PIN anak; `dibuat` tetap, `diperbarui` mengikuti `kini`."""
    if type(siswa_id) is not int or siswa_id <= 0:
        raise ValueError("siswa_id tidak sah")
    if type(hash_pin) is not dict or set(hash_pin) != set(_KOLOM_HASH):
        raise ValueError("hash PIN tidak sah")
    waktu = waktu_utc(kini)
    kon.execute(
        """INSERT INTO pin_orang_tua(siswa_id, garam, kunci, iterasi, dibuat, diperbarui)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(siswa_id) DO UPDATE SET
               garam = excluded.garam, kunci = excluded.kunci,
               iterasi = excluded.iterasi, diperbarui = excluded.diperbarui""",
        (siswa_id, hash_pin["garam"], hash_pin["kunci"], hash_pin["iterasi"], waktu, waktu),
    )


def simpan(kon, siswa_id: int, pin: str, kini: int) -> None:
    """Pasang atau ganti PIN anak (hash dibuat di sini)."""
    simpan_hash(kon, siswa_id, buat_hash_pin(pin), kini)


def ada_pin(kon, siswa_id: int) -> bool:
    return kon.execute(
        "SELECT 1 FROM pin_orang_tua WHERE siswa_id = ?", (siswa_id,)
    ).fetchone() is not None


def periksa_pin(kon, siswa_id: int, pin) -> bool:
    """True bila PIN cocok. Tanpa PIN tersimpan, PIN tak sah, atau salah -> False (tanpa membedakan)."""
    baris = kon.execute(
        "SELECT garam, kunci, iterasi FROM pin_orang_tua WHERE siswa_id = ?", (siswa_id,)
    ).fetchone()
    if baris is None or not pin_sah(pin):
        return False
    data = {"pengguna": _PENGGUNA_PIN, "garam": baris[0], "kunci": baris[1], "iterasi": baris[2]}
    return auth.periksa(_PENGGUNA_PIN, pin, data)


def hapus(kon, siswa_id: int) -> bool:
    """Hapus PIN anak; True bila ada baris terhapus."""
    return kon.execute("DELETE FROM pin_orang_tua WHERE siswa_id = ?", (siswa_id,)).rowcount > 0
