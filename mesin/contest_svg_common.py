"""Primitif SVG bersama untuk gambar soal Latihan Lomba.

Semua warna dan tebal garis berasal dari `design_tokens` (awalan `GEO_LOMBA_`/`GEO_`).
Teks alternatif (`alt`) tidak boleh memuat angka; kunci bisa bocor lewat pembaca layar.
"""
from __future__ import annotations

import html
import math
from typing import List, Optional, Sequence, Tuple

import design_tokens as T

JAM_MAKS = 23
MENIT_MAKS = 59
DERAJAT_PER_JAM = 30.0
DERAJAT_PER_MENIT_DI_JARUM_JAM = 0.5
DERAJAT_PER_MENIT = 6.0
JAM_DALAM_SETENGAH_HARI = 12
JAM_RADIUS_ANGKA = 0.78
JAM_RADIUS_TANDA = 0.9
JAM_PANJANG_JARUM_JAM = 0.5
JAM_PANJANG_JARUM_MENIT = 0.75
JAM_UKURAN_ANGKA = 0.22
JAM_TEBAL_JARUM_JAM = 0.07
JAM_TEBAL_JARUM_MENIT = 0.045
KARTU_LEBAR = 44
KARTU_TINGGI = 48
KARTU_FONT = 26
KARTU_RADIUS = 6


def esc(teks) -> str:
    return html.escape(str(teks), quote=True)


def angka(nilai) -> str:
    """Angka pendek dan deterministik untuk atribut SVG (tanpa nol di belakang koma)."""
    teks = f"{float(nilai):.2f}".rstrip("0").rstrip(".")
    return "0" if teks in ("", "-0") else teks


def _atribut(extra: dict) -> str:
    return "".join(f' {nama.replace("_", "-")}="{esc(nilai)}"' for nama, nilai in extra.items())


def bungkus(isi: str, lebar, tinggi, alt: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {angka(lebar)} {angka(tinggi)}" '
        f'role="img" aria-label="{esc(alt)}" class="soal-gambar" '
        f'style="display:block;width:100%;max-width:{angka(lebar)}px;height:auto;margin:0 auto">'
        f'{isi}</svg>'
    )


def garis(x1, y1, x2, y2, warna: Optional[str] = None, tebal=None, **extra) -> str:
    return (
        f'<line{_atribut(extra)} x1="{angka(x1)}" y1="{angka(y1)}" x2="{angka(x2)}" y2="{angka(y2)}" '
        f'stroke="{warna or T.GEO_LOMBA_GARIS}" stroke-width="{angka(tebal or T.GEO_GARIS)}" '
        f'stroke-linecap="round"/>'
    )


def teks(x, y, isi, ukuran=18, tebal: bool = False, jangkar: str = "middle",
         warna: Optional[str] = None) -> str:
    berat = ' font-weight="bold"' if tebal else ""
    return (
        f'<text x="{angka(x)}" y="{angka(y)}" font-size="{angka(ukuran)}" text-anchor="{jangkar}" '
        f'dominant-baseline="central" font-family="sans-serif"{berat} '
        f'fill="{warna or T.GEO_LOMBA_GARIS}">{esc(isi)}</text>'
    )


def kotak(x, y, lebar, tinggi, isi: Optional[str] = None, garis_warna: Optional[str] = None,
          radius=0, tebal=None) -> str:
    return (
        f'<rect x="{angka(x)}" y="{angka(y)}" width="{angka(lebar)}" height="{angka(tinggi)}" '
        f'rx="{angka(radius)}" fill="{isi or T.GEO_LOMBA_LATAR}" '
        f'stroke="{garis_warna or T.GEO_LOMBA_GARIS}" stroke-width="{angka(tebal or T.GEO_GARIS)}"/>'
    )


def lingkaran(cx, cy, radius, isi: Optional[str] = None, garis_warna: Optional[str] = None,
              tebal=None) -> str:
    return (
        f'<circle cx="{angka(cx)}" cy="{angka(cy)}" r="{angka(radius)}" '
        f'fill="{isi or T.GEO_LOMBA_LATAR}" stroke="{garis_warna or T.GEO_LOMBA_GARIS}" '
        f'stroke-width="{angka(tebal or T.GEO_GARIS)}"/>'
    )


def poligon(titik: Sequence[Tuple[float, float]], isi: Optional[str] = None,
            garis_warna: Optional[str] = None, tebal=None) -> str:
    daftar = " ".join(f"{angka(x)},{angka(y)}" for x, y in titik)
    return (
        f'<polygon points="{daftar}" fill="{isi or T.GEO_LOMBA_LATAR}" '
        f'stroke="{garis_warna or T.GEO_LOMBA_GARIS}" stroke-width="{angka(tebal or T.GEO_GARIS)}" '
        f'stroke-linejoin="round"/>'
    )


def kartu_angka(x, y, isi, lebar=KARTU_LEBAR, tinggi=KARTU_TINGGI) -> str:
    """Kartu bernomor ala contoh lomba: kotak bersudut membulat berisi satu teks tebal."""
    return (
        kotak(x, y, lebar, tinggi, radius=KARTU_RADIUS)
        + teks(x + lebar / 2, y + tinggi / 2, isi, ukuran=KARTU_FONT, tebal=True)
    )


def grid_titik(jumlah: int, per_baris: int, x0, y0, dx, dy) -> List[Tuple[float, float]]:
    """Titik pojok kiri-atas untuk `jumlah` objek ditata baris demi baris."""
    if per_baris < 1:
        raise ValueError("per_baris wajib minimal 1")
    return [(x0 + (indeks % per_baris) * dx, y0 + (indeks // per_baris) * dy)
            for indeks in range(jumlah)]


def sudut_jarum(jam: int, menit: int) -> Tuple[float, float]:
    """(sudut jarum pendek, sudut jarum panjang) dalam derajat searah jarum jam dari angka 12.

    Jarum pendek ikut bergeser setengah derajat per menit, jadi pada 08.30 ia tepat di antara
    angka 8 dan 9.
    """
    if isinstance(jam, bool) or isinstance(menit, bool) \
            or not isinstance(jam, int) or not isinstance(menit, int) \
            or not 0 <= jam <= JAM_MAKS or not 0 <= menit <= MENIT_MAKS:
        raise ValueError(f"waktu tidak sah: {jam!r}.{menit!r}")
    sudut_jam = (jam % JAM_DALAM_SETENGAH_HARI) * DERAJAT_PER_JAM \
        + menit * DERAJAT_PER_MENIT_DI_JARUM_JAM
    return (float(sudut_jam), float(menit * DERAJAT_PER_MENIT))


def _titik(cx, cy, radius, derajat) -> Tuple[float, float]:
    radian = math.radians(derajat)
    return (cx + radius * math.sin(radian), cy - radius * math.cos(radian))


def jam_analog(cx, cy, radius, jam: int, menit: int) -> str:
    """Muka jam analog dengan 12 angka dan dua jarum; tanpa label waktu digital."""
    sudut_jam, sudut_menit = sudut_jarum(jam, menit)
    bagian = [lingkaran(cx, cy, radius)]
    for indeks in range(JAM_DALAM_SETENGAH_HARI):
        derajat = indeks * DERAJAT_PER_JAM
        awal = _titik(cx, cy, radius * JAM_RADIUS_TANDA, derajat)
        akhir = _titik(cx, cy, radius, derajat)
        bagian.append(garis(*awal, *akhir, tebal=T.GEO_GARIS_TIPIS))
        x, y = _titik(cx, cy, radius * JAM_RADIUS_ANGKA, derajat)
        bagian.append(teks(x, y, indeks or JAM_DALAM_SETENGAH_HARI,
                           ukuran=radius * JAM_UKURAN_ANGKA))
    ujung_jam = _titik(cx, cy, radius * JAM_PANJANG_JARUM_JAM, sudut_jam)
    ujung_menit = _titik(cx, cy, radius * JAM_PANJANG_JARUM_MENIT, sudut_menit)
    bagian.append(garis(cx, cy, *ujung_jam, tebal=radius * JAM_TEBAL_JARUM_JAM, data_jarum="jam"))
    bagian.append(garis(cx, cy, *ujung_menit, tebal=radius * JAM_TEBAL_JARUM_MENIT,
                        data_jarum="menit"))
    bagian.append(lingkaran(cx, cy, radius * JAM_TEBAL_JARUM_JAM, isi=T.GEO_LOMBA_GARIS))
    return "".join(bagian)
