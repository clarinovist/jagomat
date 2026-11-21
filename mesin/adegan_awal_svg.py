"""SVG adegan awal v1: `deret_ikon` di sini, `turus`, `pita_ukur`, dan `bentuk` di modul sendiri.

Deterministik (tanpa acak/waktu). `render_adegan_awal` memvalidasi ulang data pada
batas renderer lalu memilih sub-adegan dari field `adegan`. `deret_ikon`: tiap ikon
adalah SATU elemen `<image>` dengan `href` ke aset terdaftar
`/aset/ikon-<nama>-v1.webp`, sehingga banyak elemen `<image>` dalam satu baris sama
dengan jumlah benda pada kategori itu. Judul dan uraian aksesibel menyebut nama
baris, tidak pernah banyak ikon atau jawaban. Informasi hanya dibawa jumlah elemen
dan label teks, bukan warna.

Bila `satuan_ikon` > 1 (satu gambar mewakili beberapa benda, P2) legenda teks
"Satu gambar mewakili N benda." tampil di atas semua baris, DI LUAR `<g class="baris-adegan">`
sehingga tidak ikut terhitung sebagai ikon atau label baris; jumlah `<image>` per baris
tetap sama dengan banyak gambar, dan nilai benda = banyak gambar x `satuan_ikon`.
Dengan `satuan_ikon` 1 keluaran sama persis dengan sebelum ada legenda.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import design_tokens as T
from adegan_awal_dasar_svg import (
    bungkus_svg, daftar_nama, garis_pemisah, jalur_ikon, label_sejajar, potong_label, teks_label,
)
from adegan_awal_bentuk_svg import render_bentuk, ringkasan_bentuk
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


def _teks_satuan(satuan: int) -> str:
    return f"Satu gambar mewakili {satuan} benda."


def _legenda(satuan: int) -> tuple:
    """Legenda skala (markup, tinggi); kosong bila satu gambar = satu benda."""
    if satuan == 1:
        return "", 0
    tinggi = T.ADEGAN_FONT + 2 * T.ADEGAN_JEDA_BARIS  # ruang untuk turun-huruf sebelum garis
    teks = teks_label(_teks_satuan(satuan), T.ADEGAN_MARGIN, T.ADEGAN_MARGIN + T.ADEGAN_FONT,
                      satu_baris=True)
    garis = garis_pemisah(T.ADEGAN_MARGIN + tinggi - T.ADEGAN_JEDA_BARIS // 2)
    return '<g class="legenda-adegan">' + teks + garis + "</g>", tinggi


def _semua_baris(baris, atas_awal: int = T.ADEGAN_MARGIN) -> tuple:
    atas, bagian = atas_awal, []
    for isi in baris:
        markup, tinggi = _baris(isi, atas)
        bagian.append(markup)
        atas += tinggi
    return "".join(bagian), atas


def _uraian(baris, satuan: int = 1) -> str:
    dasar = (
        f"Satu baris gambar untuk tiap kategori: {daftar_nama([isi['nama'] for isi in baris])}. "
        "Hitung gambar pada baris yang ditanyakan."
    )
    return dasar if satuan == 1 else f"{dasar} {_teks_satuan(satuan)}"


def _render_deret_ikon(data: Mapping[str, Any], namespace: str) -> str:
    satuan = data["satuan_ikon"]
    legenda, tinggi_legenda = _legenda(satuan)
    isi, tinggi = _semua_baris(data["baris"], T.ADEGAN_MARGIN + tinggi_legenda)
    return bungkus_svg(namespace, tinggi, _JUDUL, _uraian(data["baris"], satuan), legenda + isi)


def _ringkasan_deret_ikon(data: Mapping[str, Any]) -> str:
    daftar = ", ".join(
        f"{isi['nama']} memiliki {isi['jumlah']} gambar" for isi in data["baris"]
    )
    return f"Fakta visual: {daftar}; satu gambar mewakili {data['satuan_ikon']} benda."


_RENDERER = {
    "deret_ikon": _render_deret_ikon,
    "turus": render_turus,
    "pita_ukur": render_pita_ukur,
    "bentuk": render_bentuk,
}
_RINGKASAN = {
    "deret_ikon": _ringkasan_deret_ikon,
    "turus": ringkasan_turus,
    "pita_ukur": ringkasan_pita_ukur,
    "bentuk": ringkasan_bentuk,
}


def render_adegan_awal(data: Mapping[str, Any], namespace: str) -> str:
    """Render descriptor `adegan_awal` v1; data diuji ulang pada batas renderer."""
    validasi_adegan_awal(data)
    return _RENDERER[data["adegan"]](data, namespace)


def ringkasan_adegan_awal(data: Mapping[str, Any]) -> str:
    """Fakta visual polos untuk konteks non-HTML (pola `ringkasan_piktogram`)."""
    validasi_adegan_awal(data)
    return _RINGKASAN[data["adegan"]](data)
