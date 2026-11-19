"""Rute GET publik funnel Cek Kemampuan: `/cek-kemampuan`, `/paket-coba`, `/contoh-peta-kemampuan`.

Dipanggil sebelum `_lolos_sandi`: publik untuk anonim dan guru. Tidak ada
handler POST. Sakelar `FUNNEL_AKTIF` mati (bawaan) -> halaman status "belum
dibuka" dengan kode 200, tanpa form dan tanpa tautan ke jalur cek.
Tidak membaca data keluarga atau anak.
"""
from __future__ import annotations

import sqlite3
import time

JALUR_FUNNEL = ("/cek-kemampuan", "/paket-coba", "/contoh-peta-kemampuan")
TTL_PROFIL_DETIK = 30
_cache_profil: dict = {}  # path DB -> (kedaluwarsa monotonik, hasil baca_publik)


def _dukungan():
    import admin_store
    import support_settings

    try:
        return support_settings.baca_publik(admin_store.BAWAAN)
    except admin_store.StoreBelumSiap:
        return None


def _sekarang() -> float:
    """Jam cache profil; fungsi terpisah agar tes dapat menyuntikkan waktu."""
    return time.monotonic()


def _reset_cache_profil() -> None:
    """Kosongkan cache profil (untuk tes dan operator)."""
    _cache_profil.clear()


def _baca_profil(path) -> tuple:
    import profil_guru_settings

    try:
        return profil_guru_settings.baca_publik(path)
    # Diketahui/diterima: galat ditelan tanpa log; halaman publik tampil tanpa kartu, bukan 500.
    except (OSError, RuntimeError, ValueError, sqlite3.Error):
        return ()


def _profil_guru() -> tuple:
    """Profil guru tampil=1 dari store admin, di-cache `TTL_PROFIL_DETIK` per path DB.

    Perubahan admin tampil di halaman publik paling lambat setelah `TTL_PROFIL_DETIK`
    detik. Hasil `()` akibat galat ikut di-cache agar kegagalan tidak membanjiri DB.
    Satu-satunya state bersama adalah `_cache_profil` (isinya tuple tak berubah).
    """
    import admin_store

    path = admin_store.BAWAAN
    kini = _sekarang()
    tersimpan = _cache_profil.get(path)
    if tersimpan is not None and kini < tersimpan[0]:
        return tersimpan[1]
    hasil = _baca_profil(path)
    _cache_profil[path] = (kini + TTL_PROFIL_DETIK, hasil)
    return hasil


def tangani_get(penangan, jalur: str) -> bool:
    """Render halaman funnel atau status belum dibuka; False bila bukan rutenya."""
    if jalur not in JALUR_FUNNEL:
        return False
    import funnel_flag
    import funnel_pages

    dukungan = _dukungan()
    if not funnel_flag.funnel_aktif():
        penangan._kirim(funnel_pages.halaman_belum_dibuka(dukungan))
        return True
    if jalur == "/cek-kemampuan":
        penangan._kirim(funnel_pages.halaman_cek_kemampuan(dukungan))
    elif jalur == "/contoh-peta-kemampuan":
        import funnel_contoh

        penangan._kirim(funnel_contoh.halaman_contoh_peta(dukungan, _profil_guru()))
    else:
        penangan._kirim(funnel_pages.halaman_paket_coba(dukungan, _profil_guru()))
    return True
