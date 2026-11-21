"""Gambar SVG topik Bilangan: deret kartu angka, pola permen, dan rangkaian manik.

Elemen yang dihitung anak diberi atribut `data-*` (`data-kartu`, `data-pola`, `data-permen`,
`data-manik`) supaya tes bisa menghitung ulang apa yang benar-benar tergambar.
Teks alternatif tidak memuat angka. Warna hanya dari `design_tokens`.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

import contest_svg_common as S
import design_tokens as T

MARGIN = 10
JARAK_KARTU = 6
LEBAR_KARTU_RATUSAN = 58
LEBAR_KARTU_BIASA = S.KARTU_LEBAR
KARTU_PER_BARIS = 8
RATUSAN_PER_BARIS = 5
PULUHAN_PER_BARIS = 7

POLA_LEBAR_KOTAK = 92
POLA_TINGGI_KOTAK = 104
POLA_JARAK_KOTAK = 6
POLA_TINGGI_LABEL = 22
POLA_UKURAN_LABEL = 14
POLA_ATAS = 32
POLA_RADIUS = 4.5
POLA_SPASI_SEGITIGA_X = 11
POLA_SPASI_Y = 14
POLA_SPASI_GRID_X = 14
POLA_PER_BARIS_GRID = 4

MANIK_RADIUS = 13
MANIK_LANGKAH = 30
MANIK_TINGGI = 44
MANIK_LEBAR_TITIK = 36

WARNA_MANIK = {
    "merah": T.GEO_LOMBA_MERAH,
    "biru": T.GEO_LOMBA_BIRU,
    "kuning": T.GEO_LOMBA_KUNING,
    "hijau": T.GEO_LOMBA_HIJAU,
}

Titik = Tuple[float, float]


def _kartu(x, y, isi, lebar) -> str:
    """Satu kartu angka; `data-kartu` memuat tulisan pada kartu."""
    return f'<g data-kartu="{S.esc(isi)}">{S.kartu_angka(x, y, isi, lebar=lebar)}</g>'


def _deret(isi_kartu: Sequence, lebar: int, per_baris: int, y0: float) -> Tuple[str, float]:
    """Kartu ditata baris demi baris; mengembalikan (markup, tinggi yang terpakai)."""
    bagian = []
    for indeks, isi in enumerate(isi_kartu):
        x = MARGIN + (indeks % per_baris) * (lebar + JARAK_KARTU)
        y = y0 + (indeks // per_baris) * (S.KARTU_TINGGI + JARAK_KARTU)
        bagian.append(_kartu(x, y, isi, lebar))
    baris = (len(isi_kartu) + per_baris - 1) // per_baris
    return "".join(bagian), baris * (S.KARTU_TINGGI + JARAK_KARTU)


def _lebar_deret(jumlah: int, lebar: int, per_baris: int) -> float:
    kolom = min(jumlah, per_baris)
    return kolom * lebar + max(kolom - 1, 0) * JARAK_KARTU


def svg_deret_kartu(isi_kartu: Sequence[int]) -> str:
    """Satu deret kartu angka (kiri ke kanan) bertulisan `isi_kartu`."""
    isi, tinggi = _deret(list(isi_kartu), LEBAR_KARTU_BIASA, KARTU_PER_BARIS, MARGIN)
    lebar = 2 * MARGIN + _lebar_deret(len(isi_kartu), LEBAR_KARTU_BIASA, KARTU_PER_BARIS)
    return S.bungkus(isi, lebar, 2 * MARGIN + tinggi - JARAK_KARTU, "Deret kartu angka")


def svg_kartu_nilai_tempat(ratusan: int, puluhan: int, satuan: int) -> str:
    """Kartu 100, 10, dan 1 (tiap jenis di barisnya sendiri); jenis yang banyaknya 0 tidak digambar."""
    kelompok = (
        ("100", ratusan, LEBAR_KARTU_RATUSAN, RATUSAN_PER_BARIS),
        ("10", puluhan, LEBAR_KARTU_BIASA, PULUHAN_PER_BARIS),
        ("1", satuan, LEBAR_KARTU_BIASA, PULUHAN_PER_BARIS),
    )
    bagian: List[str] = []
    y = float(MARGIN)
    lebar_maks = 0.0
    for isi, banyak, lebar, per_baris in kelompok:
        if banyak == 0:
            continue
        markup, tinggi = _deret([isi] * banyak, lebar, per_baris, y)
        bagian.append(markup)
        y += tinggi
        lebar_maks = max(lebar_maks, _lebar_deret(banyak, lebar, per_baris))
    return S.bungkus("".join(bagian), 2 * MARGIN + lebar_maks, y + MARGIN - JARAK_KARTU,
                     "Kartu angka bernilai seratus, sepuluh, dan satu")


def titik_segitiga(pola_ke: int, kelipatan: int) -> List[Titik]:
    """Titik permen pola segitiga: baris ke-j berisi `kelipatan * j` permen, rata tengah kotak."""
    titik: List[Titik] = []
    for baris in range(1, pola_ke + 1):
        banyak = kelipatan * baris
        lebar = (banyak - 1) * POLA_SPASI_SEGITIGA_X
        x0 = POLA_LEBAR_KOTAK / 2 - lebar / 2
        y = POLA_ATAS + (baris - 1) * POLA_SPASI_Y
        titik.extend((x0 + indeks * POLA_SPASI_SEGITIGA_X, y) for indeks in range(banyak))
    return titik


def titik_kisi(banyak: int) -> List[Titik]:
    """Titik permen pola 'bertambah tetap': ditata rapat, empat per baris, rata tengah kotak."""
    lebar = (POLA_PER_BARIS_GRID - 1) * POLA_SPASI_GRID_X
    x0 = POLA_LEBAR_KOTAK / 2 - lebar / 2
    return [(x0 + (indeks % POLA_PER_BARIS_GRID) * POLA_SPASI_GRID_X,
             POLA_ATAS + (indeks // POLA_PER_BARIS_GRID) * POLA_SPASI_Y)
            for indeks in range(banyak)]


def _permen(x, y) -> str:
    return (f'<circle data-permen="1" cx="{S.angka(x)}" cy="{S.angka(y)}" r="{S.angka(POLA_RADIUS)}" '
            f'fill="{T.GEO_LOMBA_HIJAU}" stroke="{T.GEO_LOMBA_GARIS}" '
            f'stroke-width="{S.angka(T.GEO_GARIS_TIPIS)}"/>')


def svg_pola_permen(daftar_titik: Sequence[Sequence[Titik]]) -> str:
    """Kotak berlabel 'Pola 1', 'Pola 2', ... masing-masing berisi permen pada titiknya."""
    bagian: List[str] = []
    for indeks, titik in enumerate(daftar_titik):
        x0 = MARGIN + indeks * (POLA_LEBAR_KOTAK + POLA_JARAK_KOTAK)
        isi = [S.kotak(x0, MARGIN, POLA_LEBAR_KOTAK, POLA_TINGGI_KOTAK, isi=T.GEO_LOMBA_LATAR,
                       tebal=T.GEO_GARIS_TIPIS),
               S.teks(x0 + POLA_LEBAR_KOTAK / 2, MARGIN + POLA_TINGGI_LABEL / 2 + 2,
                      f"Pola {indeks + 1}", ukuran=POLA_UKURAN_LABEL, tebal=True)]
        isi.extend(_permen(x0 + x, MARGIN + y) for x, y in titik)
        bagian.append(f'<g data-pola="{indeks + 1}">{"".join(isi)}</g>')
    jumlah = len(daftar_titik)
    lebar = 2 * MARGIN + jumlah * POLA_LEBAR_KOTAK + (jumlah - 1) * POLA_JARAK_KOTAK
    return S.bungkus("".join(bagian), lebar, 2 * MARGIN + POLA_TINGGI_KOTAK,
                     "Pola gambar permen yang bertambah")


def _manik(cx, cy, warna: str) -> str:
    return (f'<circle data-manik="{S.esc(warna)}" cx="{S.angka(cx)}" cy="{S.angka(cy)}" '
            f'r="{S.angka(MANIK_RADIUS)}" fill="{WARNA_MANIK[warna]}" stroke="{T.GEO_LOMBA_GARIS}" '
            f'stroke-width="{S.angka(T.GEO_GARIS)}"/>')


def svg_rangkaian_manik(warna_tergambar: Sequence[str]) -> str:
    """Rangkaian manik dari kiri ke kanan, diakhiri tanda '...' (pola berlanjut)."""
    cy = MANIK_TINGGI / 2
    bagian = [_manik(MARGIN + MANIK_RADIUS + indeks * MANIK_LANGKAH, cy, warna)
              for indeks, warna in enumerate(warna_tergambar)]
    x_titik = MARGIN + len(warna_tergambar) * MANIK_LANGKAH + MANIK_LEBAR_TITIK / 2
    bagian.append(S.teks(x_titik, cy, "...", ukuran=S.KARTU_FONT, tebal=True))
    lebar = 2 * MARGIN + len(warna_tergambar) * MANIK_LANGKAH + MANIK_LEBAR_TITIK
    return S.bungkus("".join(bagian), lebar, MANIK_TINGGI, "Rangkaian manik berpola")
