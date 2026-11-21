"""SVG sub-adegan `turus`: satu baris garis turus per kategori.

KONTRAK HITUNG: tiap SATU unit = TEPAT SATU elemen `<line class="turus-garis">`.
Empat unit pertama tiap kelompok lima berupa garis tegak; unit kelima kelompok itu
SATU garis miring yang memotong keempat garis sebelumnya. Sisa (kurang dari lima)
berupa garis tegak biasa. Jadi banyak `<line class="turus-garis">` dalam satu
`<g class="baris-turus">` sama dengan jumlah baris itu. Garis pemisah baris memakai
kelas lain (`pemisah-baris`) dan diletakkan di luar `<g class="baris-turus">`.
Informasi dibawa jumlah garis dan label teks, bukan warna (semua garis satu warna).
Data sudah divalidasi oleh `adegan_awal_svg.render_adegan_awal`.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import design_tokens as T
from adegan_awal_dasar_svg import (
    bungkus_svg, daftar_nama, garis_pemisah, label_sejajar, potong_label,
)

KELOMPOK = 5
_JUDUL = "Turus per kategori"
_LEBAR_KELOMPOK = 2 * T.ADEGAN_TURUS_LEBIH + (KELOMPOK - 2) * T.ADEGAN_TURUS_JARAK
_SLOT_KELOMPOK = _LEBAR_KELOMPOK + T.ADEGAN_TURUS_JEDA


def _tinggi_baris(nama: str) -> int:
    isi = max(T.ADEGAN_TURUS_TINGGI, len(potong_label(nama)) * T.ADEGAN_LEADING)
    return isi + T.ADEGAN_JEDA_BARIS


def _garis(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line class="turus-garis" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{T.TEKS_UTAMA}" stroke-width="{T.ADEGAN_TURUS_TEBAL}"/>'
    )


def _unit(indeks: int, atas: int) -> str:
    """Unit ke-`indeks` (basis nol): garis tegak, atau coretan miring bila kelima."""
    kiri = T.ADEGAN_IKON_X + (indeks // KELOMPOK) * _SLOT_KELOMPOK
    urutan = indeks % KELOMPOK
    bawah = atas + T.ADEGAN_TURUS_TINGGI
    if urutan < KELOMPOK - 1:
        x = kiri + T.ADEGAN_TURUS_LEBIH + urutan * T.ADEGAN_TURUS_JARAK
        return _garis(x, atas, x, bawah)
    inset = T.ADEGAN_TURUS_MIRING_INSET
    return _garis(kiri, bawah - inset, kiri + _LEBAR_KELOMPOK, atas + inset)


def _baris(isi: Mapping[str, Any], atas: int) -> tuple:
    """Satu baris: (markup `<g>` + pemisah, tinggi baris)."""
    tinggi = _tinggi_baris(isi["nama"])
    garis = "".join(_unit(i, atas) for i in range(isi["jumlah"]))
    label = label_sejajar(isi["nama"], atas, T.ADEGAN_TURUS_TINGGI)
    pemisah = garis_pemisah(atas + tinggi - T.ADEGAN_JEDA_BARIS // 2, "pemisah-baris")
    return '<g class="baris-turus">' + label + garis + "</g>" + pemisah, tinggi


def _semua_baris(baris) -> tuple:
    atas, bagian = T.ADEGAN_MARGIN, []
    for isi in baris:
        markup, tinggi = _baris(isi, atas)
        bagian.append(markup)
        atas += tinggi
    return "".join(bagian), atas


def _uraian(baris) -> str:
    return (
        f"Satu baris turus untuk tiap kategori: {daftar_nama([isi['nama'] for isi in baris])}. "
        "Hitung garis pada baris yang ditanyakan; tiap lima garis dikelompokkan dengan coretan miring."
    )


def render_turus(data: Mapping[str, Any], namespace: str) -> str:
    isi, tinggi = _semua_baris(data["baris"])
    return bungkus_svg(namespace, tinggi, _JUDUL, _uraian(data["baris"]), isi)


def ringkasan_turus(data: Mapping[str, Any]) -> str:
    daftar = ", ".join(f"{isi['nama']} memiliki {isi['jumlah']} garis" for isi in data["baris"])
    return f"Fakta visual: {daftar}; tiap lima garis dikelompokkan dengan coretan miring."
