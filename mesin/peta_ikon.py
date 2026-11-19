"""Ikon SVG dan ubin warna laporan Peta Kemampuan (PANDUAN §5).

Ikon memakai `currentColor`, jadi warna datang dari kelas ubin di CSS. Ikon dan
warna hanya pendukung: status selalu berteks di tempat pemakaiannya.
"""
from __future__ import annotations

from typing import Tuple

import html

_BENTUK = {
    "tambah": '<path d="M8 4.5v8M4 8.5h8"/><path d="M13 17.5h7"/>',
    "kali": '<path d="M7 7l10 10M17 7 7 17"/>',
    "bagi": (
        '<circle cx="12" cy="5.5" r="1.8" fill="currentColor" stroke="none"/><path d="M5 12h14"/>'
        '<circle cx="12" cy="18.5" r="1.8" fill="currentColor" stroke="none"/>'
    ),
    "pecahan": (
        '<circle cx="12" cy="12" r="8.5"/>'
        '<path d="M12 12V3.5A8.5 8.5 0 1 1 3.5 12Z" fill="currentColor" fill-opacity=".35"/>'
        '<path d="M12 3.5V12H3.5"/>'
    ),
    "buku": (
        '<path d="M3 5.5h5.5A3.5 3.5 0 0 1 12 9v11a2.5 2.5 0 0 0-2.5-2.5H3z"/>'
        '<path d="M21 5.5h-5.5A3.5 3.5 0 0 0 12 9v11a2.5 2.5 0 0 1 2.5-2.5H21z"/>'
    ),
    "bintang": '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    "pena": '<path d="M4 20l1-4L16.5 4.5a2.1 2.1 0 0 1 3 3L8 19z"/><path d="M14.5 6.5l3 3"/>',
    "cek": '<path d="M20 6 9 17l-5-5"/>',
    "panah-atas": '<path d="M12 19V5M5 12l7-7 7 7"/>',
    "panah-kanan": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "panah-bawah": '<path d="m6 9 6 6 6-6"/>',
    "lembar": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
    "resep": '<path d="M6 3h9l4 4v14H6z"/><path d="M9 11h7M9 15h7M9 7h3"/>',
    "cari": '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/>',
    "roket": (
        '<path d="M12 15c-1.5-1.5-3-3.5-3-6.5C9 5 11 3 12 2.5 13 3 15 5 15 8.5c0 3-1.5 5-3 6.5z"/>'
        '<path d="M9 11.5 6 13l1 4 2.5-1.5M15 11.5l3 1.5-1 4-2.5-1.5"/><circle cx="12" cy="8" r="1.3"/>'
    ),
    "peta": '<path d="M9 4 3.5 6v14L9 18l6 2 5.5-2V4L15 6z"/><path d="M9 4v14M15 6v14"/>',
    "voucher": (
        '<path d="M3 9a2 2 0 0 0 0 6v3a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-3a2 2 0 0 0 0-6V6a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1z"/>'
        '<path d="M14 5v14" stroke-dasharray="2 2"/>'
    ),
    "cetak": '<path d="M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v7H6z"/>',
}
_SVG = (
    '<svg width="{u}" height="{u}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{d}</svg>'
)

# kunci materi -> (ikon, warna ubin). Materi lain jatuh ke bentuk bawaan.
_MATERI = {
    "penjumlahan": ("tambah", "teal"),
    "perkalian": ("kali", "koral"),
    "pembagian": ("bagi", "amber"),
    "pecahan": ("pecahan", "navy"),
    "soal-cerita": ("buku", "mint"),
}
_MATERI_BAWAAN = ("bintang", "navy")
WARNA = ("teal", "koral", "amber", "navy", "mint")
UKURAN_UBIN = {"s": 28, "m": 40, "l": 52, "xl": 72}
RASIO_IKON = 0.54


def ikon(nama: str, ukuran: int = 20, tebal: str = "2.4") -> str:
    """SVG ikon bernama; nama tak dikenal jatuh ke bintang (tidak pernah gagal render)."""
    return _SVG.format(u=ukuran, w=tebal, d=_BENTUK.get(nama, _BENTUK["bintang"]))


def ikon_materi(kunci: str) -> Tuple[str, str]:
    """(nama ikon, warna) untuk satu materi."""
    return _MATERI.get(kunci, _MATERI_BAWAAN)


def ubin(nama_ikon: str, warna: str, ukuran: str = "m") -> str:
    """Ubin berwarna berisi ikon; `ukuran` salah satu kunci `UKURAN_UBIN`."""
    sisi = UKURAN_UBIN.get(ukuran, UKURAN_UBIN["m"])
    kelas = "peta-ubin-st peta-ubin-%s-st peta-u-%s-st" % (warna if warna in WARNA else "navy", ukuran if ukuran in UKURAN_UBIN else "m")
    return '<span class="%s">%s</span>' % (html.escape(kelas, quote=True), ikon(nama_ikon, round(sisi * RASIO_IKON)))


def ubin_materi(kunci: str, ukuran: str = "m") -> str:
    nama_ikon, warna = ikon_materi(kunci)
    return ubin(nama_ikon, warna, ukuran)

