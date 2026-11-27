"""Butir antrean admin untuk pengajuan jadwal Private yang masih hidup (read-only, hanya angka).

Hitungan = pengajuan 'diajukan' yang belum basi (`jadwal_private.jumlah_menunggu`). Galat baca (DB admin belum
berjadwal, berkas private belum ada atau rusak, berkas akun tak terbaca) berarti 0: penanda antrean tidak boleh
menjatuhkan halaman admin. Tanpa nama anak, orang tua, atau guru di keluaran.
"""
from __future__ import annotations

import admin_transfer_menunggu as menunggu
import jadwal_private as jp
import jadwal_private_dasar as dsr
import jadwal_private_pola as jpp
import jadwal_store as js

GALAT_BACA_PRIVATE = menunggu.GALAT_BACA + (dsr.GalatJadwalPrivate, OSError, ValueError)


def guru_aktif() -> frozenset:
    """Id akun guru aktif. Impor malas: modul antrean tidak menarik `admin_http` saat dimuat."""
    import jadwal_admin_http
    return frozenset(jadwal_admin_http.guru_map())


def jumlah(path_admin, sekarang: float) -> int:
    """Pengajuan Private yang masih hidup (slot lama + pola 2 hari); galat baca apa pun = 0 (fail-safe)."""
    try:
        with js.buka(path_admin) as kon:
            return jp.jumlah_menunggu(kon, sekarang, guru_aktif()) + jpp.jumlah_menunggu()
    except GALAT_BACA_PRIVATE:
        return 0
