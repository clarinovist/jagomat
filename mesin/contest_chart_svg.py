"""Grafik SVG Latihan Lomba: garis nilai per sesi dan bar persen (fungsi murni, tanpa pustaka luar).

Keluaran deterministik: angka diformat satu desimal, tanpa skrip dan tanpa tautan. Warna dari
``design_tokens`` (tanpa hex di sini). Setiap titik grafik membawa ``data-nilai`` dan ``<title>``
agar bisa dibaca pembaca layar dan diuji tanpa merender.
"""
from __future__ import annotations

import html
from typing import Sequence

import design_tokens as T

NILAI_MAKS_BAWAAN = 10
LEBAR, TINGGI = 320, 176
_KIRI, _KANAN, _ATAS, _BAWAH = 36, 304, 14, 140
_Y_LABEL_SESI = 160
_MAKS_LABEL_SESI = 10
_BATAS_TITIK_BESAR = 15
_JARI_TITIK, _JARI_TITIK_KECIL = 4, 3
_LEBAR_BAR = 100
_TINGGI_BAR = 8
PESAN_KOSONG = "Belum ada nilai untuk digambar."


def _f(angka: float) -> str:
    return f"{angka:.1f}"


def _periksa(nilai: Sequence[int], maks: int) -> None:
    if isinstance(maks, bool) or not isinstance(maks, int) or maks < 1:
        raise ValueError(f"maks tidak sah: {maks!r}")
    for butir in nilai:
        if isinstance(butir, bool) or not isinstance(butir, int) or not 0 <= butir <= maks:
            raise ValueError(f"nilai di luar 0..{maks}: {butir!r}")


def _y(nilai: float, maks: int) -> float:
    return _BAWAH - (_BAWAH - _ATAS) * nilai / maks


def _posisi_x(indeks: int, banyak: int) -> float:
    if banyak == 1:
        return (_KIRI + _KANAN) / 2
    return _KIRI + (_KANAN - _KIRI) * indeks / (banyak - 1)


def _sumbu(maks: int) -> str:
    garis = []
    for nilai in sorted({0, maks // 2, maks}):
        y = _f(_y(nilai, maks))
        garis.append(
            f'<line x1="{_KIRI}" y1="{y}" x2="{_KANAN}" y2="{y}" stroke="{T.ANAK_BORDER_PIL}" stroke-width="1"/>'
            f'<text x="{_KIRI - 6}" y="{_f(_y(nilai, maks) + 3.5)}" text-anchor="end" font-size="10" '
            f'fill="{T.ANAK_TEKS_REDUP}">{nilai}</text>')
    return "".join(garis)


def _label_sesi(banyak: int, nomor_awal: int) -> str:
    langkah = -(-banyak // _MAKS_LABEL_SESI)
    return "".join(
        f'<text x="{_f(_posisi_x(i, banyak))}" y="{_Y_LABEL_SESI}" text-anchor="middle" font-size="10" '
        f'fill="{T.ANAK_TEKS_REDUP}">{nomor_awal + i}</text>'
        for i in range(0, banyak, langkah))


def _garis(nilai: Sequence[int], maks: int) -> str:
    if len(nilai) < 2:
        return ""
    titik = " ".join(f"{_f(_posisi_x(i, len(nilai)))},{_f(_y(v, maks))}" for i, v in enumerate(nilai))
    return (f'<polyline points="{titik}" fill="none" stroke="{T.ANAK_AKSEN}" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round"/>')


def _titik(nilai: Sequence[int], maks: int, nomor_awal: int) -> str:
    jari = _JARI_TITIK if len(nilai) <= _BATAS_TITIK_BESAR else _JARI_TITIK_KECIL
    return "".join(
        f'<circle cx="{_f(_posisi_x(i, len(nilai)))}" cy="{_f(_y(v, maks))}" r="{jari}" data-nilai="{v}" '
        f'fill="{T.ANAK_AKSEN}" stroke="{T.LATAR_KARTU}" stroke-width="1.5">'
        f'<title>Sesi {nomor_awal + i}: nilai {v}</title></circle>'
        for i, v in enumerate(nilai))


def grafik_nilai(nilai: Sequence[int], maks: int = NILAI_MAKS_BAWAAN, nomor_awal: int = 1) -> str:
    """Grafik garis nilai per sesi (urut dari yang terlama); `nomor_awal` = nomor sesi pertama yang digambar.

    Nol titik menghasilkan paragraf pesan kosong (bukan SVG); nilai di luar 0..maks memicu ValueError.
    """
    _periksa(nilai, maks)
    if not nilai:
        return f'<p class="hl-kosong">{PESAN_KOSONG}</p>'
    label = (f"Grafik garis nilai {len(nilai)} sesi latihan, skala 0 sampai {maks}, "
             f"dari sesi {nomor_awal} sampai sesi {nomor_awal + len(nilai) - 1}")
    return (f'<svg class="hl-grafik" viewBox="0 0 {LEBAR} {TINGGI}" role="img" aria-label="{html.escape(label)}">'
            f'{_sumbu(maks)}{_garis(nilai, maks)}{_titik(nilai, maks, nomor_awal)}'
            f'{_label_sesi(len(nilai), nomor_awal)}</svg>')


def bar_persen(benar: int, total: int, label: str) -> str:
    """Satu bar horizontal benar/total (SVG); `label` jadi teks aksesibel (di-escape)."""
    if total < 0 or not 0 <= benar <= total:
        raise ValueError(f"benar/total tidak sah: {benar}/{total}")
    lebar = _LEBAR_BAR * benar // total if total else 0
    return (f'<svg class="hl-bar" viewBox="0 0 {_LEBAR_BAR} {_TINGGI_BAR}" preserveAspectRatio="none" role="img" '
            f'aria-label="{html.escape(label)}">'
            f'<rect width="{_LEBAR_BAR}" height="{_TINGGI_BAR}" fill="{T.ANAK_NETRAL_LATAR}"/>'
            f'<rect width="{lebar}" height="{_TINGGI_BAR}" fill="{T.ANAK_AKSEN}" data-benar="{benar}" '
            f'data-total="{total}"/></svg>')
