"""SVG sub-adegan `jam_analog`: muka jam dinding berjarum, jam penuh atau setengah jam.

KONTRAK: satu `<g class="jam-gambar">` berisi muka (`muka-jam`), 48 tanda menit (satu `path`
`tanda-menit`), 12 tanda jam (`tanda-jam`), 12 angka (`angka-jam`, 1..12 tetap, bukan jawaban),
jarum panjang (`<line class="jarum-panjang">`, digambar lebih dulu), jarum pendek
(`<line class="jarum-pendek">`, lebih pendek dan lebih tebal, digambar di atasnya agar tetap
terlihat saat kedua jarum bertumpuk pada pukul 12.00), dan titik pusat. WAKTU HANYA TERBACA DARI
KOORDINAT KEDUA `<line>` jarum: tidak ada `transform`, kelas, id, atribut, judul, atau uraian
yang bergantung pada jam atau menit. Sisa gambar (muka, tanda, angka) sama untuk semua waktu.
Sudut dihitung dari atas searah jarum jam: jarum jam = (jam % 12) * 30 + menit * 0,5 derajat,
jarum menit = menit * 6 derajat; ujung jarum dihitung dengan trigonometri lalu dibulatkan.
Data sudah divalidasi oleh `adegan_awal_svg.render_adegan_awal`.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

import design_tokens as T
from adegan_awal_dasar_svg import bungkus_svg

_JUDUL = "Gambar jam"
_URAIAN = "Jam dinding berjarum. Perhatikan letak kedua jarumnya."
_RINGKASAN = "Fakta visual: gambar jam dinding berjarum dengan jarum pendek dan jarum panjang."
_PUSAT_X = T.ADEGAN_LEBAR / 2
_PUSAT_Y = T.ADEGAN_JAM_TINGGI / 2
_DERAJAT_PER_JAM = 30
_DERAJAT_PER_MENIT = 6
_DERAJAT_JAM_PER_MENIT = 0.5
_TITIK_PER_PUTARAN = 60
_DESIMAL = 2
_GESER_BARIS_ANGKA = 0.35  # pusat teks angka dari garis dasar, kali ukuran huruf


def sudut_jarum_jam(jam: int, menit: int) -> float:
    """Derajat jarum pendek dari arah atas, searah jarum jam (jam 12 sama dengan 0)."""
    return (jam % 12) * _DERAJAT_PER_JAM + menit * _DERAJAT_JAM_PER_MENIT


def sudut_jarum_menit(menit: int) -> float:
    return menit * _DERAJAT_PER_MENIT


def _angka(nilai: float) -> str:
    """Koordinat dibulatkan dua desimal; tanpa `-0`."""
    bulat = round(nilai, _DESIMAL) + 0.0
    return f"{0.0 if bulat == 0 else bulat:g}"


def _titik(derajat: float, jarak: float) -> tuple:
    rad = math.radians(derajat)
    return _PUSAT_X + jarak * math.sin(rad), _PUSAT_Y - jarak * math.cos(rad)


def _garis(kelas: str, derajat: float, dari: float, sampai: float, tebal: float, warna: str) -> str:
    x1, y1 = _titik(derajat, dari)
    x2, y2 = _titik(derajat, sampai)
    return (f'<line class="{kelas}" x1="{_angka(x1)}" y1="{_angka(y1)}" x2="{_angka(x2)}" '
            f'y2="{_angka(y2)}" stroke="{warna}" stroke-width="{tebal:g}"/>')


def _muka() -> str:
    return (f'<circle class="muka-jam" cx="{_PUSAT_X:g}" cy="{_PUSAT_Y:g}" r="{T.ADEGAN_JAM_RADIUS}" '
            f'fill="{T.ADEGAN_JAM_MUKA}" stroke="{T.TEKS_UTAMA}" '
            f'stroke-width="{T.ADEGAN_JAM_TEBAL_MUKA}"/>')


def _tanda_menit() -> str:
    """Satu path berisi 48 ruas pendek (60 titik dikurangi 12 titik jam)."""
    ruas = []
    for ke in range(_TITIK_PER_PUTARAN):
        if ke % 5 == 0:
            continue
        x1, y1 = _titik(ke * _DERAJAT_PER_MENIT, T.ADEGAN_JAM_TICK_MENIT)
        x2, y2 = _titik(ke * _DERAJAT_PER_MENIT, T.ADEGAN_JAM_TICK_LUAR)
        ruas.append(f"M{_angka(x1)} {_angka(y1)}L{_angka(x2)} {_angka(y2)}")
    return (f'<path class="tanda-menit" d="{"".join(ruas)}" fill="none" stroke="{T.TEKS_UTAMA}" '
            f'stroke-width="{T.ADEGAN_JAM_TEBAL_TICK_MENIT:g}"/>')


def _tanda_jam() -> str:
    return "".join(
        _garis("tanda-jam", ke * _DERAJAT_PER_JAM, T.ADEGAN_JAM_TICK_JAM, T.ADEGAN_JAM_TICK_LUAR,
               T.ADEGAN_JAM_TEBAL_TICK_JAM, T.TEKS_UTAMA)
        for ke in range(1, 13))


def _angka_jam() -> str:
    bagian = []
    for ke in range(1, 13):
        x, y = _titik(ke * _DERAJAT_PER_JAM, T.ADEGAN_JAM_ANGKA_JARI)
        bagian.append(
            f'<text class="angka-jam" x="{_angka(x)}" y="{_angka(y + _GESER_BARIS_ANGKA * T.ADEGAN_JAM_ANGKA_FONT)}" '
            f'text-anchor="middle" font-size="{T.ADEGAN_JAM_ANGKA_FONT}" '
            f'fill="{T.TEKS_UTAMA}">{ke}</text>')
    return "".join(bagian)


def _jarum(jam: int, menit: int) -> str:
    """Jarum panjang dulu, jarum pendek (lebih tebal) di atasnya, lalu titik pusat."""
    panjang = _garis("jarum-panjang", sudut_jarum_menit(menit), 0, T.ADEGAN_JAM_PANJANG_PANJANG,
                     T.ADEGAN_JAM_TEBAL_PANJANG, T.TEKS_UTAMA)
    pendek = _garis("jarum-pendek", sudut_jarum_jam(jam, menit), 0, T.ADEGAN_JAM_PANJANG_PENDEK,
                    T.ADEGAN_JAM_TEBAL_PENDEK, T.TEKS_UTAMA)
    pusat = (f'<circle class="pusat-jam" cx="{_PUSAT_X:g}" cy="{_PUSAT_Y:g}" r="{T.ADEGAN_JAM_PUSAT}" '
             f'fill="{T.TEKS_UTAMA}"/>')
    return panjang + pendek + pusat


def render_jam_analog(data: Mapping[str, Any], namespace: str) -> str:
    isi = _muka() + _tanda_menit() + _tanda_jam() + _angka_jam() + _jarum(data["jam"], data["menit"])
    return bungkus_svg(namespace, T.ADEGAN_JAM_TINGGI, _JUDUL, _URAIAN, f'<g class="jam-gambar">{isi}</g>')


def ringkasan_jam_analog(data: Mapping[str, Any]) -> str:
    """Fakta visual polos tanpa waktu: pada soal baca jam, waktu itu sendiri adalah jawaban."""
    return _RINGKASAN
