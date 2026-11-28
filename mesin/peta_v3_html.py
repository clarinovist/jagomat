"""Pembantu HTML laporan Peta versi 3 (F6): escape, gabung nama, kartu bagian, dan penghapus atribut style.

Atribut `style=` dihapus dari keluaran pembuat maskot dan logo (`brand`), karena CSP dan tes markup melarangnya di
dalam `<main>`. Ukuran dan warna gambar itu diatur di `peta_style_laporan_v3` lewat kelas.
"""
from __future__ import annotations

import re

import peta_laporan_ortu_pages as v1

_ATRIBUT_STYLE = re.compile(r' style="[^"]*"')


def e(teks) -> str:
    return v1._e(teks)


def tanggal(teks: str) -> str:
    return v1._tanggal(teks)


def tanpa_style(html: str) -> str:
    """HTML dengan atribut `style` dibuang; kelas dan atribut lain tetap."""
    return _ATRIBUT_STYLE.sub("", html)


def gabung(nama: list) -> str:
    """'A', 'A dan B', atau 'A, B dan C' dengan urutan tetap."""
    if len(nama) <= 1:
        return "".join(nama)
    return ", ".join(nama[:-1]) + " dan " + nama[-1]


def kartu(judul_id: str, judul: str, isi: str, kelas: str = "") -> str:
    """Kartu bagian dengan judul h3 yang ditautkan `aria-labelledby`; `isi` sudah berupa HTML aman."""
    atribut = f" {kelas}" if kelas else ""
    return (f'<section class="ortu-peta-v3-kartu-st{atribut}" aria-labelledby="{judul_id}">'
            f'<h3 id="{judul_id}">{e(judul)}</h3>{isi}</section>')
