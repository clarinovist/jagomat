"""Format tampilan Latihan Lomba: tanggal WIB, durasi, persen, dan angka desimal ala Indonesia.

Fungsi murni tanpa akses DB. WIB dipakai sebagai UTC+7 tetap (Indonesia tidak memakai waktu musim panas).
"""
from __future__ import annotations

import datetime

OFFSET_WIB_DETIK = 7 * 3600
DETIK_PER_MENIT = 60
BULAN_SINGKAT = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
_NOL_UTC = datetime.datetime(1970, 1, 1)


def tanggal_wib(epoch: int) -> str:
    """Epoch detik -> "21 Nov 2026, 19:31" (WIB, bulan singkat Indonesia)."""
    waktu = _NOL_UTC + datetime.timedelta(seconds=int(epoch) + OFFSET_WIB_DETIK)
    return f"{waktu.day} {BULAN_SINGKAT[waktu.month - 1]} {waktu.year}, {waktu.hour:02d}:{waktu.minute:02d}"


def tanggal_pendek_wib(epoch: int) -> str:
    """Epoch detik -> "21 Nov 2026" (WIB, tanpa jam)."""
    return tanggal_wib(epoch).split(",")[0]


def durasi_menit_detik(detik: int) -> str:
    """Detik -> "05:03"; nilai negatif dianggap nol."""
    detik = max(0, int(detik))
    return f"{detik // DETIK_PER_MENIT:02d}:{detik % DETIK_PER_MENIT:02d}"


def persen(benar: int, total: int) -> int:
    """Persen bulat (dibulatkan ke bawah); 0 bila total 0."""
    if total <= 0:
        return 0
    return (int(benar) * 100) // int(total)


def desimal(nilai: float) -> str:
    """Satu angka di belakang koma dengan koma Indonesia: 6.5 -> "6,5", 7 -> "7,0"."""
    return f"{nilai:.1f}".replace(".", ",")
