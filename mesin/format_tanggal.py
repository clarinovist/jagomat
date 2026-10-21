"""Format tanggal tampilan yang seragam: "22 Sep 2026", jam hanya bila perlu."""
from __future__ import annotations

from datetime import date, datetime

BULAN_PENDEK = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
                "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


def tanggal_pendek(nilai: date) -> str:
    return f"{nilai.day} {BULAN_PENDEK[nilai.month - 1]} {nilai.year}"


def waktu_wib(nilai: datetime) -> str:
    """Waktu sudah dalam WIB; jam memakai titik sesuai kebiasaan Indonesia."""
    return f"{tanggal_pendek(nilai)}, {nilai:%H.%M} WIB"
