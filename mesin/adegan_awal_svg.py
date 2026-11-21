"""SVG adegan awal v1 (`deret_ikon`): satu baris ikon benda per kategori.

Deterministik (tanpa acak/waktu). Tiap ikon adalah SATU elemen `<image>` dengan
`href` ke aset terdaftar `/aset/ikon-<nama>-v1.png`, sehingga banyak elemen
`<image>` dalam satu baris sama dengan jumlah benda pada kategori itu. Judul dan
uraian aksesibel menyebut nama baris, tidak pernah banyak ikon atau jawaban.
Informasi hanya dibawa jumlah ikon dan label teks, bukan warna.
"""
from __future__ import annotations

import hashlib
import html
import math
from collections.abc import Mapping
from typing import Any

import design_tokens as T
from adegan_awal_data import validasi_adegan_awal

_PITCH = T.ADEGAN_IKON + T.ADEGAN_IKON_JARAK
_JUDUL = "Gambar benda per kategori"


def jalur_ikon(nama: str) -> str:
    """URL aset ikon; `nama` sudah lolos allow-list validator."""
    return f"/aset/ikon-{nama}-v1.png"


def _ident(namespace: Any) -> str:
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace adegan wajib teks tidak kosong")
    try:
        sidik = hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:20]
    except UnicodeError as galat:
        raise ValueError("namespace adegan tidak valid") from galat
    return "adegan-" + sidik


def _potong_label(nama: str) -> tuple:
    """Bagi label panjang per N karakter tanpa mengubah isinya."""
    batas = T.ADEGAN_LABEL_PER_BARIS
    return tuple(nama[i:i + batas] for i in range(0, len(nama), batas))


def _sublarik(jumlah: int) -> int:
    return max(1, math.ceil(jumlah / T.ADEGAN_KOLOM))


def _tinggi_baris(nama: str, jumlah: int) -> int:
    isi = max(_sublarik(jumlah) * _PITCH, len(_potong_label(nama)) * T.ADEGAN_LEADING)
    return isi + T.ADEGAN_JEDA_BARIS


def _label(nama: str, atas: int) -> str:
    potongan = _potong_label(nama)
    tengah = atas + (_PITCH - (len(potongan) - 1) * T.ADEGAN_LEADING) / 2 + T.ADEGAN_FONT / 3
    awal = max(atas + T.ADEGAN_FONT, tengah)
    atribut = f'font-size="{T.ADEGAN_FONT}" fill="{T.TEKS_UTAMA}"'
    if len(potongan) == 1:
        return f'<text x="{T.ADEGAN_MARGIN}" y="{awal:g}" {atribut}>{html.escape(nama)}</text>'
    isi = "".join(
        f'<tspan x="{T.ADEGAN_MARGIN}" y="{awal + i * T.ADEGAN_LEADING:g}">'
        f"{html.escape(bagian)}</tspan>"
        for i, bagian in enumerate(potongan)
    )
    return f"<text {atribut}>{isi}</text>"


def _ikon(nama: str, indeks: int, atas: int) -> str:
    kolom, larik = indeks % T.ADEGAN_KOLOM, indeks // T.ADEGAN_KOLOM
    return (
        f'<image href="{jalur_ikon(nama)}" x="{T.ADEGAN_IKON_X + kolom * _PITCH}" '
        f'y="{atas + larik * _PITCH}" width="{T.ADEGAN_IKON}" height="{T.ADEGAN_IKON}"/>'
    )


def _garis_pemisah(bawah: int) -> str:
    return (
        f'<line x1="{T.ADEGAN_MARGIN}" y1="{bawah}" x2="{T.ADEGAN_LEBAR - T.ADEGAN_MARGIN}" '
        f'y2="{bawah}" stroke="{T.BORDER_HALUS}" stroke-width="{T.ADEGAN_GARIS}"/>'
    )


def _baris(isi: Mapping[str, Any], atas: int) -> tuple:
    """Satu baris sebagai `<g>`; kembalikan (markup, tinggi baris)."""
    tinggi = _tinggi_baris(isi["nama"], isi["jumlah"])
    ikon = "".join(_ikon(isi["ikon"], i, atas) for i in range(isi["jumlah"]))
    garis = _garis_pemisah(atas + tinggi - T.ADEGAN_JEDA_BARIS // 2)
    markup = '<g class="baris-adegan">' + _label(isi["nama"], atas) + ikon + garis + "</g>"
    return markup, tinggi


def _semua_baris(baris) -> tuple:
    atas, bagian = T.ADEGAN_MARGIN, []
    for isi in baris:
        markup, tinggi = _baris(isi, atas)
        bagian.append(markup)
        atas += tinggi
    return "".join(bagian), atas


def _daftar_nama(baris) -> str:
    nama = [isi["nama"] for isi in baris]
    if len(nama) == 1:
        return nama[0]
    return ", ".join(nama[:-1]) + " dan " + nama[-1]


def _uraian(baris) -> str:
    return (
        f"Satu baris gambar untuk tiap kategori: {_daftar_nama(baris)}. "
        "Hitung gambar pada baris yang ditanyakan."
    )


def render_adegan_awal(data: Mapping[str, Any], namespace: str) -> str:
    """Render descriptor `adegan_awal` v1; data diuji ulang pada batas renderer."""
    validasi_adegan_awal(data)
    ident = _ident(namespace)
    isi, tinggi = _semua_baris(data["baris"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {T.ADEGAN_LEBAR} {tinggi}" '
        f'role="img" aria-labelledby="{ident}-judul {ident}-uraian" '
        f'style="display:block;width:100%;max-width:{T.LEBAR_VISUAL_SOAL};height:auto;'
        f'margin:{T.JARAK_VISUAL_SOAL} auto">'
        f'<title id="{ident}-judul">{_JUDUL}</title>'
        f'<desc id="{ident}-uraian">{html.escape(_uraian(data["baris"]))}</desc>{isi}</svg>'
    )


def ringkasan_adegan_awal(data: Mapping[str, Any]) -> str:
    """Fakta visual polos untuk konteks non-HTML (pola `ringkasan_piktogram`)."""
    validasi_adegan_awal(data)
    daftar = ", ".join(
        f"{isi['nama']} memiliki {isi['jumlah']} gambar" for isi in data["baris"]
    )
    return f"Fakta visual: {daftar}; satu gambar mewakili {data['satuan_ikon']} benda."
