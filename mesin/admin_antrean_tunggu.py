"""Butir antrean admin untuk anak yang menunggu kursi Mini Class (F2c; read-only, hanya angka).

Hitungan = entri daftar tunggu 'menunggu' yang ordernya belum ditempatkan (`jadwal_tunggu_mini.jumlah_menunggu_kursi`).
Galat baca (DB admin belum berjadwal, berkas private belum ada atau rusak) berarti 0: penanda antrean tidak boleh
menjatuhkan halaman admin. Tanpa nama anak, orang tua, atau order di keluaran.
"""
from __future__ import annotations

import admin_transfer_menunggu as menunggu
import jadwal_private_dasar as dsr
import jadwal_store as js
import jadwal_tunggu_mini as jtg

GALAT_BACA_TUNGGU = menunggu.GALAT_BACA + (dsr.GalatJadwalPrivate, OSError, ValueError)


def jumlah(path_admin) -> int:
    """Jumlah anak yang menunggu kursi Mini Class; galat baca apa pun = 0 (fail-safe)."""
    try:
        with js.buka(path_admin) as kon:
            return jtg.jumlah_menunggu_kursi(kon)
    except GALAT_BACA_TUNGGU:
        return 0
