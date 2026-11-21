"""Bagian SVG bersama sub-adegan `adegan_awal` v1 (deret_ikon, turus, pita_ukur).

Semua deterministik (tanpa acak/waktu). Pemanggil WAJIB sudah memvalidasi data
(`validasi_adegan_awal`); modul ini hanya merakit markup dari data tervalidasi.
"""
from __future__ import annotations

import hashlib
import html
from typing import Any, Optional

import design_tokens as T


def jalur_ikon(nama: str) -> str:
    """URL aset ikon; `nama` sudah lolos allow-list validator."""
    return f"/aset/ikon-{nama}-v1.webp"


def ident(namespace: Any) -> str:
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace adegan wajib teks tidak kosong")
    try:
        sidik = hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:20]
    except UnicodeError as galat:
        raise ValueError("namespace adegan tidak valid") from galat
    return "adegan-" + sidik


def potong_label(nama: str) -> tuple:
    """Bagi label panjang per N karakter tanpa mengubah isinya."""
    batas = T.ADEGAN_LABEL_PER_BARIS
    return tuple(nama[i:i + batas] for i in range(0, len(nama), batas))


def teks_label(nama: str, x: float, awal: float, jangkar: Optional[str] = None,
               satu_baris: bool = False) -> str:
    """Label satu atau beberapa baris; `awal` = garis dasar baris pertama.

    `satu_baris` menahan pemotongan per N karakter (untuk label datar yang lebar).
    """
    potongan = (nama,) if satu_baris else potong_label(nama)
    posisi = f' text-anchor="{jangkar}"' if jangkar else ""
    atribut = f'font-size="{T.ADEGAN_FONT}" fill="{T.TEKS_UTAMA}"'
    if len(potongan) == 1:
        return f'<text x="{x:g}" y="{awal:g}"{posisi} {atribut}>{html.escape(nama)}</text>'
    isi = "".join(
        f'<tspan x="{x:g}" y="{awal + i * T.ADEGAN_LEADING:g}">{html.escape(bagian)}</tspan>'
        for i, bagian in enumerate(potongan)
    )
    return f"<text{posisi} {atribut}>{isi}</text>"


def label_sejajar(nama: str, atas: float, tinggi_acuan: float) -> str:
    """Label di kolom kiri, dipusatkan terhadap `tinggi_acuan` baris isi."""
    potongan = potong_label(nama)
    tengah = atas + (tinggi_acuan - (len(potongan) - 1) * T.ADEGAN_LEADING) / 2 + T.ADEGAN_FONT / 3
    return teks_label(nama, T.ADEGAN_MARGIN, max(atas + T.ADEGAN_FONT, tengah))


def garis_pemisah(bawah: float, kelas: Optional[str] = None) -> str:
    atribut_kelas = f' class="{kelas}"' if kelas else ""
    return (
        f'<line{atribut_kelas} x1="{T.ADEGAN_MARGIN}" y1="{bawah:g}" '
        f'x2="{T.ADEGAN_LEBAR - T.ADEGAN_MARGIN}" y2="{bawah:g}" '
        f'stroke="{T.BORDER_HALUS}" stroke-width="{T.ADEGAN_GARIS}"/>'
    )


def daftar_nama(nama: list) -> str:
    if len(nama) == 1:
        return nama[0]
    return ", ".join(nama[:-1]) + " dan " + nama[-1]


def bungkus_svg(namespace: str, tinggi: float, judul: str, uraian: str, isi: str) -> str:
    """Pembungkus `<svg>` beraksesibilitas (title + desc terhubung lewat aria)."""
    kode = ident(namespace)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {T.ADEGAN_LEBAR} {tinggi:g}" '
        f'role="img" aria-labelledby="{kode}-judul {kode}-uraian" '
        f'style="display:block;width:100%;max-width:{T.LEBAR_VISUAL_SOAL};height:auto;'
        f'margin:{T.JARAK_VISUAL_SOAL} auto">'
        f'<title id="{kode}-judul">{html.escape(judul)}</title>'
        f'<desc id="{kode}-uraian">{html.escape(uraian)}</desc>{isi}</svg>'
    )
