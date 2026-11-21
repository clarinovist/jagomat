"""SVG sub-adegan `bentuk`: satu bangun, atau satu baris 1..10 bangun datar.

KONTRAK HITUNG: SELALU satu `<g class="baris-bangun">` berisi 1..10 `<g class="bangun-gambar">`
(satu per bangun, urut tampil kiri ke kanan lalu atas ke bawah). Bangun datar = TEPAT SATU
elemen bentuk (`polygon` atau `circle`) di dalam `bangun-gambar`; bangun ruang = beberapa
elemen (lihat `adegan_awal_bangun_svg`). Judul dan teks lain TIDAK ada di dalam
`baris-bangun`. Kelas dan atribut sengaja netral: jenis bangun hanya terbaca dari GEOMETRI,
tidak dari nama kelas, id, judul, atau uraian (uraian hanya "satu bangun" atau "beberapa
bangun", tanpa nama dan tanpa jumlah).
Data sudah divalidasi oleh `adegan_awal_svg.render_adegan_awal`.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import bentuk_katalog as K
import design_tokens as T
from adegan_awal_bangun_svg import gambar_bangun
from adegan_awal_dasar_svg import bungkus_svg, daftar_nama

_JUDUL = "Gambar bangun"
_URAIAN = {"satu": "Satu bangun pada gambar. Perhatikan bentuknya.",
           "baris": "Beberapa bangun pada satu gambar. Perhatikan bentuk tiap bangun."}
_SKALA = {"kecil": T.ADEGAN_BANGUN_SKALA_KECIL, "besar": 1.0}


def _kotak(bangun, ukuran_dasar: float) -> float:
    return ukuran_dasar * _SKALA[bangun["ukuran"]]


def _satu(bangun) -> tuple:
    """(markup `bangun-gambar`, tinggi viewBox) untuk tampil `satu`."""
    tinggi = T.ADEGAN_BANGUN_TINGGI_SATU
    isi = gambar_bangun(bangun, T.ADEGAN_LEBAR / 2, tinggi / 2,
                        _kotak(bangun, T.ADEGAN_BANGUN_KOTAK_SATU))
    return f'<g class="bangun-gambar">{isi}</g>', tinggi


def _baris(daftar) -> tuple:
    """(markup deret `bangun-gambar`, tinggi viewBox): lima per baris, tiap baris dipusatkan."""
    sel, kolom = T.ADEGAN_BANGUN_SEL, T.ADEGAN_BANGUN_KOLOM
    larik = -(-len(daftar) // kolom)
    bagian = []
    for indeks, bangun in enumerate(daftar):
        baris, urut = divmod(indeks, kolom)
        banyak = min(kolom, len(daftar) - baris * kolom)
        cx = (T.ADEGAN_LEBAR - banyak * sel) / 2 + urut * sel + sel / 2
        cy = T.ADEGAN_MARGIN + baris * sel + sel / 2
        isi = gambar_bangun(bangun, cx, cy, _kotak(bangun, T.ADEGAN_BANGUN_KOTAK_SEL))
        bagian.append(f'<g class="bangun-gambar">{isi}</g>')
    return "".join(bagian), larik * sel + 2 * T.ADEGAN_MARGIN


def render_bentuk(data: Mapping[str, Any], namespace: str) -> str:
    tampil, daftar = data["tampil"], data["bangun"]
    isi, tinggi = _satu(daftar[0]) if tampil == "satu" else _baris(daftar)
    return bungkus_svg(namespace, tinggi, _JUDUL, _URAIAN[tampil],
                       f'<g class="baris-bangun">{isi}</g>')


def _ringkas_satu(bangun) -> str:
    jenis = "datar" if K.jenis_bangun(bangun["nama"]) == K.JENIS_DATAR else "ruang"
    return f"satu bangun {jenis} dengan ciri: {K.CIRI_RINGKAS[bangun['nama']]}"


def ringkasan_bentuk(data: Mapping[str, Any]) -> str:
    """Fakta visual polos; bangun tunggal lewat cirinya (tanpa nama), baris lewat urutan nama."""
    daftar = data["bangun"]
    if data["tampil"] == "satu":
        return f"Fakta visual: {_ringkas_satu(daftar[0])}."
    nama = daftar_nama([bangun["nama"] for bangun in daftar])
    return f"Fakta visual: satu baris bangun datar dari kiri ke kanan: {nama}."
