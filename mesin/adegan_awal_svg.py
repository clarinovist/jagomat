"""SVG adegan awal v1: `deret_ikon` di sini, `turus` dan `pita_ukur` di modul sendiri.

Deterministik (tanpa acak/waktu). `render_adegan_awal` memvalidasi ulang data pada
batas renderer lalu memilih sub-adegan dari field `adegan`. `deret_ikon`: tiap ikon
adalah SATU elemen `<image>` dengan `href` ke aset terdaftar
`/aset/ikon-<nama>-v1.webp`, sehingga banyak elemen `<image>` dalam satu baris sama
dengan jumlah benda pada kategori itu. Judul dan uraian aksesibel menyebut nama
baris, tidak pernah banyak ikon atau jawaban. Informasi hanya dibawa jumlah elemen
dan label teks, bukan warna.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import design_tokens as T
from adegan_awal_dasar_svg import (
    bungkus_svg, daftar_nama, garis_pemisah, jalur_ikon, label_sejajar, potong_label,
)
from adegan_awal_data import validasi_adegan_awal
from adegan_awal_turus_svg import render_turus, ringkasan_turus
from adegan_awal_ukur_svg import render_pita_ukur, ringkasan_pita_ukur

_PITCH = T.ADEGAN_IKON + T.ADEGAN_IKON_JARAK
_JUDUL = "Gambar benda per kategori"

__all__ = ("jalur_ikon", "render_adegan_awal", "ringkasan_adegan_awal", "validasi_adegan_awal")


def _sublarik(jumlah: int) -> int:
    return max(1, math.ceil(jumlah / T.ADEGAN_KOLOM))


def _tinggi_baris(nama: str, jumlah: int) -> int:
    isi = max(_sublarik(jumlah) * _PITCH, len(potong_label(nama)) * T.ADEGAN_LEADING)
    return isi + T.ADEGAN_JEDA_BARIS


def _ikon(nama: str, indeks: int, atas: int) -> str:
    kolom, larik = indeks % T.ADEGAN_KOLOM, indeks // T.ADEGAN_KOLOM
    return (
        f'<image href="{jalur_ikon(nama)}" x="{T.ADEGAN_IKON_X + kolom * _PITCH}" '
        f'y="{atas + larik * _PITCH}" width="{T.ADEGAN_IKON}" height="{T.ADEGAN_IKON}"/>'
    )


def _baris(isi: Mapping[str, Any], atas: int) -> tuple:
    """Satu baris sebagai `<g>`; kembalikan (markup, tinggi baris)."""
    tinggi = _tinggi_baris(isi["nama"], isi["jumlah"])
    ikon = "".join(_ikon(isi["ikon"], i, atas) for i in range(isi["jumlah"]))
    garis = garis_pemisah(atas + tinggi - T.ADEGAN_JEDA_BARIS // 2)
    markup = (
        '<g class="baris-adegan">' + label_sejajar(isi["nama"], atas, _PITCH) + ikon + garis + "</g>"
    )
    return markup, tinggi


def _semua_baris(baris) -> tuple:
    atas, bagian = T.ADEGAN_MARGIN, []
    for isi in baris:
        markup, tinggi = _baris(isi, atas)
        bagian.append(markup)
        atas += tinggi
    return "".join(bagian), atas


def _uraian(baris) -> str:
    return (
        f"Satu baris gambar untuk tiap kategori: {daftar_nama([isi['nama'] for isi in baris])}. "
        "Hitung gambar pada baris yang ditanyakan."
    )


def _render_deret_ikon(data: Mapping[str, Any], namespace: str) -> str:
    isi, tinggi = _semua_baris(data["baris"])
    return bungkus_svg(namespace, tinggi, _JUDUL, _uraian(data["baris"]), isi)


def _ringkasan_deret_ikon(data: Mapping[str, Any]) -> str:
    daftar = ", ".join(
        f"{isi['nama']} memiliki {isi['jumlah']} gambar" for isi in data["baris"]
    )
    return f"Fakta visual: {daftar}; satu gambar mewakili {data['satuan_ikon']} benda."


_RENDERER = {
    "deret_ikon": _render_deret_ikon,
    "turus": render_turus,
    "pita_ukur": render_pita_ukur,
}
_RINGKASAN = {
    "deret_ikon": _ringkasan_deret_ikon,
    "turus": ringkasan_turus,
    "pita_ukur": ringkasan_pita_ukur,
}


def render_adegan_awal(data: Mapping[str, Any], namespace: str) -> str:
    """Render descriptor `adegan_awal` v1; data diuji ulang pada batas renderer."""
    validasi_adegan_awal(data)
    return _RENDERER[data["adegan"]](data, namespace)


def ringkasan_adegan_awal(data: Mapping[str, Any]) -> str:
    """Fakta visual polos untuk konteks non-HTML (pola `ringkasan_piktogram`)."""
    validasi_adegan_awal(data)
    return _RINGKASAN[data["adegan"]](data)
