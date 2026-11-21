"""Gambar soal Operasi Hitung: deret emoji benda/hewan yang bisa dihitung ulang dari atribut `data-*`.

Tata letak memakai kisi tetap (tidak bergantung ukuran emoji). Setiap benda yang dihitung anak
membawa `data-objek` (nama benda) dan, bila ada beberapa kelompok, `data-kelompok` (nomor kelompok).
Tanda operasi digambar sebagai teks "+" atau "−" di antara kelompok.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

import design_tokens as T
from contest_svg_common import angka, bungkus, esc, teks

SEL = 30                  # jarak antar ikon dalam kisi
UKURAN_IKON = 24
MARGIN = 8
PER_BARIS_KELOMPOK = 3    # kelompok pada soal hitung: tiga ikon per baris
JARAK_OPERATOR = 28       # lebar ruang untuk tanda + atau −
UKURAN_OPERATOR = 24
PER_BARIS_HEWAN = 6
SEL_HEWAN = 40
UKURAN_HEWAN = 30
PER_BARIS_KUE = 10
JARAK_KE_ANAK = 14
SEL_ANAK = 38
UKURAN_ANAK = 28
TANDA_TAMBAH = "+"
TANDA_KURANG = "−"
EMOJI_ANAK = "\U0001F9D2"
ALT_HITUNG = "Gambar benda yang dihitung"
ALT_HEWAN = "Gambar hewan yang dihitung"
ALT_BAGI = "Gambar benda dan anak yang membaginya"


def ikon(pusat_x, pusat_y, objek: str, emoji: str, ukuran: int, kelompok=None) -> str:
    """Satu emoji dengan penanda `data-objek` (dan `data-kelompok` bila diberikan)."""
    penanda = f' data-kelompok="{esc(kelompok)}"' if kelompok is not None else ""
    return (
        f'<text x="{angka(pusat_x)}" y="{angka(pusat_y)}" font-size="{angka(ukuran)}" '
        f'text-anchor="middle" dominant-baseline="central" data-objek="{esc(objek)}"{penanda} '
        f'fill="{T.GEO_LOMBA_GARIS}">{esc(emoji)}</text>'
    )


def _deret(objek: str, emoji: str, jumlah: int, x0, y0, per_baris: int, sel: int,
           ukuran: int, kelompok=None) -> Tuple[str, int, int]:
    """Ikon ditata per baris mulai (x0, y0); mengembalikan (svg, lebar, tinggi) deretnya."""
    if jumlah < 1 or per_baris < 1:
        raise ValueError("jumlah dan per_baris wajib minimal 1")
    bagian = []
    for indeks in range(jumlah):
        kolom, baris = indeks % per_baris, indeks // per_baris
        bagian.append(ikon(x0 + kolom * sel + sel / 2, y0 + baris * sel + sel / 2,
                           objek, emoji, ukuran, kelompok))
    kolom_terpakai = min(jumlah, per_baris)
    baris_terpakai = (jumlah + per_baris - 1) // per_baris
    return "".join(bagian), kolom_terpakai * sel, baris_terpakai * sel


def gambar_hitung(objek: str, emoji: str, jumlah: Sequence[int], operator: Sequence[str]) -> str:
    """Kelompok benda dari kiri ke kanan dipisah tanda operasi ('+' atau '-')."""
    if len(operator) != len(jumlah) - 1:
        raise ValueError("operator wajib satu lebih sedikit dari kelompok")
    tinggi_isi = max((n + PER_BARIS_KELOMPOK - 1) // PER_BARIS_KELOMPOK for n in jumlah) * SEL
    bagian: List[str] = []
    x = MARGIN
    for indeks, banyak in enumerate(jumlah):
        isi, lebar, _ = _deret(objek, emoji, banyak, x, MARGIN, PER_BARIS_KELOMPOK, SEL,
                               UKURAN_IKON, kelompok=indeks)
        bagian.append(isi)
        x += lebar
        if indeks < len(operator):
            tanda = TANDA_TAMBAH if operator[indeks] == "+" else TANDA_KURANG
            bagian.append(teks(x + JARAK_OPERATOR / 2, MARGIN + tinggi_isi / 2, tanda,
                               ukuran=UKURAN_OPERATOR, tebal=True))
            x += JARAK_OPERATOR
    return bungkus("".join(bagian), x + MARGIN, tinggi_isi + 2 * MARGIN, ALT_HITUNG)


def gambar_hewan(daftar: Sequence[Tuple[str, str, int]]) -> str:
    """Hewan ditata berurutan per jenis: `daftar` = [(nama, emoji, jumlah), ...]."""
    urut = [(nama, emoji) for nama, emoji, jumlah in daftar for _ in range(jumlah)]
    if not urut:
        raise ValueError("daftar hewan kosong")
    bagian = []
    for indeks, (nama, emoji) in enumerate(urut):
        kolom, baris = indeks % PER_BARIS_HEWAN, indeks // PER_BARIS_HEWAN
        bagian.append(ikon(MARGIN + kolom * SEL_HEWAN + SEL_HEWAN / 2,
                           MARGIN + baris * SEL_HEWAN + SEL_HEWAN / 2, nama, emoji, UKURAN_HEWAN))
    lebar = min(len(urut), PER_BARIS_HEWAN) * SEL_HEWAN + 2 * MARGIN
    tinggi = ((len(urut) + PER_BARIS_HEWAN - 1) // PER_BARIS_HEWAN) * SEL_HEWAN + 2 * MARGIN
    return bungkus("".join(bagian), lebar, tinggi, ALT_HEWAN)


def gambar_bagi(objek: str, emoji: str, jumlah_benda: int, jumlah_anak: int) -> str:
    """Seluruh benda awal (sepuluh per baris), lalu deretan anak di bawahnya."""
    isi_benda, lebar_benda, tinggi_benda = _deret(
        objek, emoji, jumlah_benda, MARGIN, MARGIN, PER_BARIS_KUE, SEL, UKURAN_IKON)
    y_anak = MARGIN + tinggi_benda + JARAK_KE_ANAK
    isi_anak, lebar_anak, tinggi_anak = _deret(
        "anak", EMOJI_ANAK, jumlah_anak, MARGIN, y_anak, jumlah_anak, SEL_ANAK, UKURAN_ANAK)
    lebar = max(lebar_benda, lebar_anak) + 2 * MARGIN
    return bungkus(isi_benda + isi_anak, lebar, y_anak + tinggi_anak + MARGIN, ALT_BAGI)
