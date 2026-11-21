"""SVG sub-adegan `tumpukan_kubus`: kubus satuan isometrik di atas lantai berpetak.

KONTRAK: satu `<g class="tumpukan-gambar">` berisi lantai (`lantai-petak`, jajar genjang berisi) dan
garis petaknya (`garis-lantai`), lalu satu `<g class="kolom-kubus">` untuk TIAP PETAK TERISI, digambar
dari baris belakang ke depan dan, dalam satu baris, dari kolom kiri ke kanan (urutan lukis yang benar
untuk sudut pandang depan-kanan-atas). Tiap `kolom-kubus` berisi tepat `tinggi` buah
`<g class="kubus-satuan">` (SEMUA kubus digambar, termasuk yang tertutup, dari lapis bawah ke atas) dan
tidak memuat elemen lain; tiap `kubus-satuan` berisi tiga `<path>`: `muka-atas`, `muka-kiri` (muka
yang menghadap depan), dan `muka-kanan`. Dua label tetap (`arah-gambar`, "depan" dan "kanan") menandai
sisi depan (tepi kiri-bawah lantai) dan sisi kanan (tepi kanan-bawah lantai). Selain `kolom-kubus`,
gambar hanya bergantung pada banyak baris dan kolom alas (fakta gambar), bukan pada tinggi tumpukan.
BANYAK KUBUS DAN TAMPAK HANYA TERBACA DARI STRUKTUR DAN POSISI `kolom-kubus`/`kubus-satuan`; tidak ada
`transform`, kelas, id, atribut, judul, atau uraian yang menyebut tinggi, banyak kubus, atau jawaban.
Proyeksi: sumbu kolom (ke kanan) menuju kanan-bawah layar, sumbu baris (ke belakang) menuju kanan-atas,
sumbu tinggi tegak ke atas; titik (x, y, z) berada di
`(ox + (x + y) * LEBAR_MUKA, oy + (x - y) * MIRING - z * RUSUK)`. Ukuran kubus tetap untuk semua soal dan
gambar dipusatkan menurut alas. Data sudah divalidasi oleh `adegan_awal_svg.render_adegan_awal`.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import design_tokens as T
from adegan_awal_dasar_svg import bungkus_svg

_JUDUL = "Gambar susunan kubus satuan"
_URAIAN = ("Susunan kubus satuan di atas lantai berpetak, dilihat dari depan sedikit dari kanan "
           "dan atas. Sisi depan dan sisi kanan diberi tanda.")
_RINGKASAN = ("Fakta visual: gambar susunan kubus satuan di atas lantai berpetak, tiap kubus "
              "digambar dengan tiga muka, sisi depan dan sisi kanan diberi tanda.")
_DESIMAL = 2
_MUKA_ATAS, _MUKA_KIRI, _MUKA_KANAN = T.ADEGAN_TUMPUKAN_MUKA


def _angka(nilai: float) -> str:
    """Koordinat dibulatkan dua desimal; tanpa `-0`."""
    bulat = round(nilai, _DESIMAL) + 0.0
    return f"{0.0 if bulat == 0 else bulat:g}"


class _Proyeksi:
    """Titik dunia (kolom x, baris y, tinggi z) ke koordinat layar untuk satu alas."""

    def __init__(self, baris: int, kolom: int) -> None:
        a, b = T.ADEGAN_TUMPUKAN_LEBAR_MUKA, T.ADEGAN_TUMPUKAN_MIRING
        tinggi_isi = ((baris + kolom) * b + T.ADEGAN_TUMPUKAN_TINGGI_MAKS * T.ADEGAN_TUMPUKAN_RUSUK
                      + T.ADEGAN_TUMPUKAN_LABEL_RUANG)
        self.ox = (T.ADEGAN_LEBAR - (baris + kolom) * a) / 2
        self.oy = ((T.ADEGAN_TUMPUKAN_TINGGI - tinggi_isi) / 2 + baris * b
                   + T.ADEGAN_TUMPUKAN_TINGGI_MAKS * T.ADEGAN_TUMPUKAN_RUSUK)

    def titik(self, x: float, y: float, z: float) -> tuple:
        return (self.ox + (x + y) * T.ADEGAN_TUMPUKAN_LEBAR_MUKA,
                self.oy + (x - y) * T.ADEGAN_TUMPUKAN_MIRING - z * T.ADEGAN_TUMPUKAN_RUSUK)


def _jalur(titik: list) -> str:
    awal, *sisa = titik
    return (f"M{_angka(awal[0])} {_angka(awal[1])}"
            + "".join(f"L{_angka(x)} {_angka(y)}" for x, y in sisa) + "Z")


def _muka(kelas: str, titik: list, warna: str) -> str:
    return (f'<path class="{kelas}" d="{_jalur(titik)}" fill="{warna}" stroke="{T.TEKS_UTAMA}" '
            f'stroke-width="{T.ADEGAN_TUMPUKAN_TEBAL:g}"/>')


def _kubus(p: _Proyeksi, x: int, y: int, z: int) -> str:
    """Tiga muka kubus satuan di (x, y, z): atas, kiri (menghadap depan), kanan."""
    atas = [p.titik(x, y, z + 1), p.titik(x + 1, y, z + 1), p.titik(x + 1, y + 1, z + 1),
            p.titik(x, y + 1, z + 1)]
    kiri = [p.titik(x, y, z + 1), p.titik(x + 1, y, z + 1), p.titik(x + 1, y, z), p.titik(x, y, z)]
    kanan = [p.titik(x + 1, y, z + 1), p.titik(x + 1, y + 1, z + 1), p.titik(x + 1, y + 1, z),
             p.titik(x + 1, y, z)]
    return ('<g class="kubus-satuan">' + _muka("muka-atas", atas, _MUKA_ATAS)
            + _muka("muka-kiri", kiri, _MUKA_KIRI) + _muka("muka-kanan", kanan, _MUKA_KANAN) + "</g>")


def _kolom(p: _Proyeksi, x: int, y: int, tinggi: int) -> str:
    isi = "".join(_kubus(p, x, y, z) for z in range(tinggi))
    return f'<g class="kolom-kubus">{isi}</g>'


def _lantai(p: _Proyeksi, baris: int, kolom: int) -> str:
    sudut = [p.titik(0, 0, 0), p.titik(kolom, 0, 0), p.titik(kolom, baris, 0), p.titik(0, baris, 0)]
    garis = []
    for i in range(1, kolom):
        (x1, y1), (x2, y2) = p.titik(i, 0, 0), p.titik(i, baris, 0)
        garis.append(f"M{_angka(x1)} {_angka(y1)}L{_angka(x2)} {_angka(y2)}")
    for j in range(1, baris):
        (x1, y1), (x2, y2) = p.titik(0, j, 0), p.titik(kolom, j, 0)
        garis.append(f"M{_angka(x1)} {_angka(y1)}L{_angka(x2)} {_angka(y2)}")
    badan = (f'<path class="lantai-petak" d="{_jalur(sudut)}" fill="{T.ADEGAN_TUMPUKAN_LANTAI_ISI}" '
             f'stroke="{T.ADEGAN_TUMPUKAN_LANTAI_GARIS}" stroke-width="{T.ADEGAN_TUMPUKAN_TEBAL_LANTAI:g}"/>')
    petak = (f'<path class="garis-lantai" d="{"".join(garis)}" fill="none" '
             f'stroke="{T.ADEGAN_TUMPUKAN_LANTAI_GARIS}" stroke-width="{T.ADEGAN_TUMPUKAN_TEBAL_LANTAI:g}"/>'
             if garis else "")
    return badan + petak


def _label(kelas_teks: str, x: float, y: float, isi: str) -> str:
    return (f'<text class="{kelas_teks}" x="{_angka(x)}" y="{_angka(y)}" text-anchor="middle" '
            f'font-size="{T.ADEGAN_TUMPUKAN_LABEL_FONT:g}" fill="{T.TEKS_UTAMA}">{isi}</text>')


def _label_arah(p: _Proyeksi, baris: int, kolom: int) -> str:
    """"depan" di bawah tepi depan lantai (agak ke kiri) dan "kanan" di bawah tepi kanan lantai (agak ke kanan)."""
    depan = p.titik(kolom / 2, 0, 0)
    kanan = p.titik(kolom, baris / 2, 0)
    turun, geser = T.ADEGAN_TUMPUKAN_LABEL_TURUN, T.ADEGAN_TUMPUKAN_LABEL_GESER
    return (_label("arah-gambar", depan[0] - geser, depan[1] + turun, "depan")
            + _label("arah-gambar", kanan[0] + geser, kanan[1] + turun, "kanan"))


def render_tumpukan(data: Mapping[str, Any], namespace: str) -> str:
    lajur = [list(isi) for isi in data["tinggi"]]
    baris, kolom = len(lajur), len(lajur[0])
    p = _Proyeksi(baris, kolom)
    kolom_kubus = "".join(
        _kolom(p, x, y, lajur[y][x])
        for y in range(baris - 1, -1, -1) for x in range(kolom) if lajur[y][x])
    isi = _lantai(p, baris, kolom) + kolom_kubus + _label_arah(p, baris, kolom)
    return bungkus_svg(namespace, T.ADEGAN_TUMPUKAN_TINGGI, _JUDUL, _URAIAN,
                       f'<g class="tumpukan-gambar">{isi}</g>')


def ringkasan_tumpukan(data: Mapping[str, Any]) -> str:
    """Fakta visual polos tanpa tinggi tumpukan atau banyak kubus."""
    return _RINGKASAN
