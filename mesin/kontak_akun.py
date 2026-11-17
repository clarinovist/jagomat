"""Kontak WhatsApp per akun: normalisasi nomor dan simpan/ambil/hapus.

Kunci baris adalah `id_akun` (ID acak dari `sandi.json`), bukan nama login dan
bukan data anak. Nomor hanya milik orang dewasa pembayar; modul ini tidak pernah
mencatat, mencetak, atau memasukkan nomor ke pesan galat.

`simpan` dan `hapus` bekerja di dalam transaksi pemanggil dan tidak commit
sendiri, supaya registrasi dapat menulis kontak bersama baris lain secara atomik.
Waktu disuntik (string ISO) agar tes deterministik.
"""
from __future__ import annotations

import re
from datetime import datetime

from auth import id_akun_sah

PANJANG_MASUKAN_MAKS = 32
_PEMISAH = " -.()"
_POLA_WA = re.compile(r"628[0-9]{8,12}")
_KOLOM = ("id_akun", "wa", "dibuat", "diperbarui", "aktivitas_terakhir")


def normalisasi_wa(teks) -> str | None:
    """Ubah `08…`, `+62…`, atau `62…` menjadi `628…`; selain itu None.

    Spasi, strip, titik, dan kurung dibuang. Fungsi murni.
    """
    if type(teks) is not str or len(teks) > PANJANG_MASUKAN_MAKS:
        return None
    bersih = teks.strip()
    awal_plus = bersih.startswith("+")
    isi = bersih[1:] if awal_plus else bersih
    angka = "".join(c for c in isi if c not in _PEMISAH)
    if not (angka.isascii() and angka.isdigit()):
        return None
    if angka.startswith("0") and not awal_plus:
        angka = "62" + angka[1:]
    elif not angka.startswith("62"):
        return None
    return angka if _POLA_WA.fullmatch(angka) else None


def _periksa_id_akun(id_akun) -> None:
    if not id_akun_sah(id_akun):
        raise ValueError("id_akun tidak sah")


def _periksa_waktu(sekarang) -> None:
    if type(sekarang) is not str:
        raise ValueError("waktu harus string ISO")
    try:
        datetime.fromisoformat(sekarang)
    except ValueError:
        raise ValueError("waktu bukan format ISO") from None


def simpan(kon, id_akun, wa_ternormalisasi, sekarang) -> None:
    """Upsert kontak akun di transaksi pemanggil (tanpa commit).

    `dibuat` tetap pada pemanggilan berikutnya; `diperbarui` dan
    `aktivitas_terakhir` mengikuti `sekarang`.
    """
    _periksa_id_akun(id_akun)
    if type(wa_ternormalisasi) is not str or normalisasi_wa(wa_ternormalisasi) != wa_ternormalisasi:
        raise ValueError("nomor WhatsApp belum ternormalisasi")
    _periksa_waktu(sekarang)
    kon.execute(
        """INSERT INTO kontak_akun(id_akun, wa, dibuat, diperbarui, aktivitas_terakhir)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(id_akun) DO UPDATE SET
               wa = excluded.wa,
               diperbarui = excluded.diperbarui,
               aktivitas_terakhir = excluded.aktivitas_terakhir""",
        (id_akun, wa_ternormalisasi, sekarang, sekarang, sekarang),
    )


def ambil(kon, id_akun) -> dict | None:
    """Baris kontak sebagai dict baru, atau None bila akun belum punya kontak."""
    _periksa_id_akun(id_akun)
    baris = kon.execute(
        "SELECT " + ", ".join(_KOLOM) + " FROM kontak_akun WHERE id_akun = ?",
        (id_akun,),
    ).fetchone()
    return None if baris is None else dict(zip(_KOLOM, tuple(baris)))


def hapus(kon, id_akun) -> bool:
    """Hapus kontak akun di transaksi pemanggil; True bila ada baris terhapus."""
    _periksa_id_akun(id_akun)
    return kon.execute("DELETE FROM kontak_akun WHERE id_akun = ?", (id_akun,)).rowcount > 0
