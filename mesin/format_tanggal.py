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


def tanggal_dari_teks(nilai) -> str:
    """Tanggal ISO dari database; nilai warisan yang aneh tampil apa adanya."""
    mentah = str(nilai or "").strip()
    if not mentah:
        return "—"
    try:
        return tanggal_pendek(date.fromisoformat(mentah[:10]))
    except ValueError:
        return mentah


def waktu_dari_teks(nilai) -> str:
    """Stempel waktu database (sudah WIB); tanggal saja bila tanpa jam."""
    mentah = str(nilai or "").strip()
    if not mentah:
        return "—"
    try:
        return waktu_wib(datetime.fromisoformat(mentah)) if len(mentah) > 10 else tanggal_pendek(date.fromisoformat(mentah))
    except ValueError:
        return mentah
