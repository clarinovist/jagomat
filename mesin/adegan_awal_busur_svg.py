"""SVG sub-adegan `busur`: busur derajat setengah lingkaran dengan dua skala dan sinar sudut.

KONTRAK: satu `<g class="busur-gambar">` berisi badan busur (`badan-busur`, path setengah
lingkaran), tiga path tanda (`tanda-satuan` tiap 1 derajat, `tanda-lima` tiap 5, `tanda-sepuluh`
tiap 10), garis alas (`garis-alas`), satu `<line class="sinar-sudut">` per sinar (berpangkal di
titik pusat), 38 kotak latar angka (`latar-angka`, seisi busur, digambar sesudah sinar agar sinar
yang lewat tidak menimpa angka), 19 angka skala luar (`angka-luar`, 0..180 dari kanan) dan 19
angka skala dalam (`angka-dalam`, 180..0 dari kanan), titik pusat (`pusat-busur`), satu huruf per ujung sinar
(`huruf-sinar`) dan satu huruf titik sudut (`huruf-titik`). Semua bagian selain sinar dan huruf
SAMA untuk semua soal. BESAR SUDUT HANYA TERBACA DARI KOORDINAT UJUNG `<line class="sinar-sudut">`
terhadap titik pusat (huruf ujung sinar memberi tahu sinar mana yang bernama apa); tidak ada
`transform`, kelas, id, atribut, judul, atau uraian yang menyebut besar sudut, banyak sinar, atau
skala yang dipakai. Arah dihitung dari kanan berlawanan arah jarum jam, jadi skala luar terbaca
sama dengan arahnya dan skala dalam terbaca 180 dikurangi arahnya. Data sudah divalidasi oleh
`adegan_awal_svg.render_adegan_awal`.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

import design_tokens as T
from adegan_awal_dasar_svg import bungkus_svg

_JUDUL = "Gambar busur derajat"
_URAIAN = "Busur derajat dengan dua skala dan sinar sudut. Perhatikan letak sinar pada skala."
_RINGKASAN = ("Fakta visual: gambar busur derajat dengan skala luar dan skala dalam, "
              "titik sudut di pusatnya, dan sinar yang ujungnya diberi huruf.")
_PUSAT_X = T.ADEGAN_LEBAR / 2
_PUSAT_Y = T.ADEGAN_BUSUR_PUSAT_Y
_DERAJAT_SETENGAH = 180
_LANGKAH_ANGKA = 10
_LANGKAH_LIMA = 5
_DESIMAL = 2
_GESER_BARIS = 0.35  # pusat teks dari garis dasar, kali ukuran huruf


def _angka(nilai: float) -> str:
    """Koordinat dibulatkan dua desimal; tanpa `-0`."""
    bulat = round(nilai, _DESIMAL) + 0.0
    return f"{0.0 if bulat == 0 else bulat:g}"


def titik_busur(derajat: float, jarak: float) -> tuple:
    """Titik pada arah `derajat` (dari kanan, berlawanan arah jarum jam) dan `jarak` dari pusat."""
    rad = math.radians(derajat)
    return _PUSAT_X + jarak * math.cos(rad), _PUSAT_Y - jarak * math.sin(rad)


def _ruas(derajat: int, panjang: float) -> str:
    x1, y1 = titik_busur(derajat, T.ADEGAN_BUSUR_RADIUS - panjang)
    x2, y2 = titik_busur(derajat, T.ADEGAN_BUSUR_RADIUS)
    return f"M{_angka(x1)} {_angka(y1)}L{_angka(x2)} {_angka(y2)}"


def _jenis_tanda(derajat: int) -> int:
    """Indeks panjang tanda: 0 = tiap 1 derajat, 1 = tiap 5, 2 = tiap 10."""
    if derajat % _LANGKAH_ANGKA == 0:
        return 2
    return 1 if derajat % _LANGKAH_LIMA == 0 else 0


def _badan() -> str:
    r = T.ADEGAN_BUSUR_RADIUS
    kiri, kanan = _angka(_PUSAT_X - r), _angka(_PUSAT_X + r)
    return (f'<path class="badan-busur" d="M{kiri} {_angka(_PUSAT_Y)}A{r} {r} 0 0 1 {kanan} '
            f'{_angka(_PUSAT_Y)}Z" fill="{T.ADEGAN_BUSUR_ISI}" stroke="{T.TEKS_UTAMA}" '
            f'stroke-width="{T.ADEGAN_BUSUR_TEBAL_TEPI:g}"/>')


def _tanda() -> str:
    """Tiga path tanda (1, 5, 10 derajat), tiap path satu ketebalan."""
    bagian = {0: [], 1: [], 2: []}
    for derajat in range(_DERAJAT_SETENGAH + 1):
        jenis = _jenis_tanda(derajat)
        bagian[jenis].append(_ruas(derajat, T.ADEGAN_BUSUR_TANDA[jenis]))
    kelas = ("tanda-satuan", "tanda-lima", "tanda-sepuluh")
    return "".join(
        f'<path class="{kelas[j]}" d="{"".join(bagian[j])}" fill="none" stroke="{T.TEKS_UTAMA}" '
        f'stroke-width="{T.ADEGAN_BUSUR_TEBAL_TANDA[j]:g}"/>' for j in (0, 1, 2))


def _garis_alas() -> str:
    lebih = T.ADEGAN_BUSUR_RADIUS + T.ADEGAN_BUSUR_ALAS_LEBIH
    return (f'<line class="garis-alas" x1="{_angka(_PUSAT_X - lebih)}" y1="{_angka(_PUSAT_Y)}" '
            f'x2="{_angka(_PUSAT_X + lebih)}" y2="{_angka(_PUSAT_Y)}" stroke="{T.TEKS_UTAMA}" '
            f'stroke-width="{T.ADEGAN_BUSUR_TEBAL_ALAS:g}"/>')


def _teks(kelas: str, x: float, y: float, ukuran: float, warna: str, isi: str) -> str:
    return (f'<text class="{kelas}" x="{_angka(x)}" y="{_angka(y + _GESER_BARIS * ukuran)}" '
            f'text-anchor="middle" font-size="{ukuran:g}" fill="{warna}">{isi}</text>')


def _titik_angka(derajat: int, jarak: float) -> tuple:
    """Pusat angka skala; angka di garis alas (0 dan 180) naik sedikit agar tidak tertimpa garis."""
    x, y = titik_busur(derajat, jarak)
    di_alas = derajat in (0, _DERAJAT_SETENGAH)
    return x, y - (T.ADEGAN_BUSUR_ANGKA_NAIK if di_alas else 0)


def _latar_angka(pusat: tuple, isi: str) -> str:
    """Kotak seisi busur di belakang angka supaya sinar yang lewat tidak menimpa angkanya."""
    lebar = len(isi) * T.ADEGAN_BUSUR_LEBAR_HURUF * T.ADEGAN_BUSUR_ANGKA_FONT
    lebar += 2 * T.ADEGAN_BUSUR_LATAR_ANGKA_LEBIH
    tinggi = T.ADEGAN_BUSUR_ANGKA_FONT
    return (f'<rect class="latar-angka" x="{_angka(pusat[0] - lebar / 2)}" '
            f'y="{_angka(pusat[1] - tinggi / 2)}" width="{_angka(lebar)}" height="{_angka(tinggi)}" '
            f'fill="{T.ADEGAN_BUSUR_ISI}"/>')


def _angka_skala() -> str:
    """Angka tiap 10 derajat: skala luar 0..180 dari kanan, skala dalam 180..0 dari kanan."""
    latar, teks = [], []
    for derajat in range(0, _DERAJAT_SETENGAH + 1, _LANGKAH_ANGKA):
        luar = _titik_angka(derajat, T.ADEGAN_BUSUR_ANGKA_LUAR_JARI)
        dalam = _titik_angka(derajat, T.ADEGAN_BUSUR_ANGKA_DALAM_JARI)
        isi_dalam = str(_DERAJAT_SETENGAH - derajat)
        latar += [_latar_angka(luar, str(derajat)), _latar_angka(dalam, isi_dalam)]
        teks.append(_teks("angka-luar", *luar, T.ADEGAN_BUSUR_ANGKA_FONT, T.TEKS_UTAMA, str(derajat)))
        teks.append(_teks("angka-dalam", *dalam, T.ADEGAN_BUSUR_ANGKA_FONT,
                          T.ADEGAN_BUSUR_ANGKA_DALAM, isi_dalam))
    return "".join(latar) + "".join(teks)


def _sinar(daftar: list) -> str:
    bagian = []
    for isi in daftar:
        x2, y2 = titik_busur(isi["sudut"], T.ADEGAN_BUSUR_PANJANG_SINAR)
        bagian.append(
            f'<line class="sinar-sudut" x1="{_angka(_PUSAT_X)}" y1="{_angka(_PUSAT_Y)}" '
            f'x2="{_angka(x2)}" y2="{_angka(y2)}" stroke="{T.ADEGAN_BUSUR_SINAR}" '
            f'stroke-width="{T.ADEGAN_BUSUR_TEBAL_SINAR:g}"/>')
    return "".join(bagian)


def _huruf(daftar: list, pusat: str) -> str:
    bagian = [_teks("huruf-sinar", *titik_busur(isi["sudut"], T.ADEGAN_BUSUR_HURUF_JARI),
                    T.ADEGAN_BUSUR_HURUF_FONT, T.TEKS_UTAMA, isi["huruf"]) for isi in daftar]
    bagian.append(_teks("huruf-titik", _PUSAT_X, _PUSAT_Y + T.ADEGAN_BUSUR_HURUF_TITIK_TURUN,
                        T.ADEGAN_BUSUR_HURUF_FONT, T.TEKS_UTAMA, pusat))
    return "".join(bagian)


def _pusat() -> str:
    return (f'<circle class="pusat-busur" cx="{_angka(_PUSAT_X)}" cy="{_angka(_PUSAT_Y)}" '
            f'r="{T.ADEGAN_BUSUR_PUSAT}" fill="{T.ADEGAN_BUSUR_SINAR}"/>')


def render_busur(data: Mapping[str, Any], namespace: str) -> str:
    daftar = [dict(isi) for isi in data["sinar"]]
    isi = (_badan() + _tanda() + _garis_alas() + _sinar(daftar) + _angka_skala() + _pusat()
           + _huruf(daftar, data["pusat"]))
    return bungkus_svg(namespace, T.ADEGAN_BUSUR_TINGGI, _JUDUL, _URAIAN,
                       f'<g class="busur-gambar">{isi}</g>')


def ringkasan_busur(data: Mapping[str, Any]) -> str:
    """Fakta visual polos tanpa besar sudut atau banyak sinar."""
    return _RINGKASAN
