"""Grafik laporan Peta versi 3 (F6): donat skor dan grafik waktu per nomor soal, keduanya SVG tanpa atribut style.

Warna dan ukuran tampilan datang dari kelas di `peta_style_laporan_v3`. Grafik waktu memakai viewBox dengan satu kolom
per nomor dan `preserveAspectRatio="none"`, jadi angka nomor di bawahnya (flex sama lebar) selalu sejajar dengan
batang. Setiap nomor juga punya teks sr-only (daftar `ul`), karena anak tidak boleh hanya membaca warna.
"""
from __future__ import annotations

import math

import peta_laporan_snapshot as snap
import peta_v3_aturan as aturan
from peta_v3_html import e

JARI_DONAT = 14
KELILING_DONAT = 2 * math.pi * JARI_DONAT
SKALA_SKOR = 100
TINGGI_WAKTU = 150  # satuan viewBox; tinggi nyata diatur CSS
LEBAR_PER_SOAL = 40  # satuan viewBox per nomor soal
CELAH_BATANG = 8  # celah antarbatang dalam satuan viewBox
TINGGI_BATANG_ABU = 6  # tinggi batang tanpa catatan waktu (dilewati, atau detik kosong)

JENIS_BENAR = "benar"
JENIS_SALAH = "salah"
JENIS_CEPAT = "cepat"
JENIS_ABU = "abu"
COPY_LABEL_WAKTU = "Waktu per soal."
COPY_LABEL_BENAR = "Soal benar: %s."
COPY_LABEL_CEPAT = "Soal dijawab di bawah %d detik dan salah: %s."
COPY_LABEL_TERLAMA = "Soal paling lama: nomor %d, %d detik."
COPY_LEG = {
    JENIS_BENAR: "Benar",
    JENIS_SALAH: "Salah",
    JENIS_CEPAT: "Dijawab di bawah %d detik",
    JENIS_ABU: "Tanpa catatan waktu",
}
COPY_LEG_RATA = "Rata-rata %d detik"
COPY_SR_NOMOR = "Nomor %d: %s."


def donat(skor: int) -> str:
    """Donat skor/100: cincin lingkaran dengan panjang busur sebanding skor, angka di tengah."""
    panjang = KELILING_DONAT * skor / SKALA_SKOR
    atribut = f'cx="18" cy="18" r="{JARI_DONAT}" fill="none" stroke-width="4.2"'
    return ('<div class="ortu-peta-v3-cincin-st">'
            '<svg viewBox="0 0 36 36" aria-hidden="true" focusable="false">'
            f'<circle class="ortu-peta-v3-cincin-jalur-st" {atribut}/>'
            f'<circle class="ortu-peta-v3-cincin-isi-st" {atribut} stroke-linecap="round" '
            f'stroke-dasharray="{panjang:.2f} {KELILING_DONAT:.2f}"/>'
            '</svg>'
            f'<span class="ortu-peta-v3-cincin-angka-st"><b>{skor}</b><small>/{SKALA_SKOR}</small></span></div>')


def jenis_batang(butir: dict) -> str:
    """Jenis batang: abu bila tanpa detik; lalu benar; lalu salah terlalu cepat; selain itu salah biasa."""
    if butir["detik"] is None:
        return JENIS_ABU
    if butir["benar"] == 1:
        return JENIS_BENAR
    if aturan.terlalu_cepat(butir):
        return JENIS_CEPAT
    return JENIS_SALAH


def _maks_detik(soal) -> int:
    """Skala tinggi grafik: detik terbesar, minimal 1 agar tidak membagi dengan nol."""
    detik = [b["detik"] for b in soal if b["detik"] is not None]
    return max(detik + [1])


def _tinggi(butir: dict, maks: int) -> float:
    if butir["detik"] is None:
        return TINGGI_BATANG_ABU
    return max(TINGGI_BATANG_ABU, butir["detik"] / maks * TINGGI_WAKTU)


def _batang(indeks: int, butir: dict, maks: int) -> str:
    tinggi = _tinggi(butir, maks)
    x = indeks * LEBAR_PER_SOAL + CELAH_BATANG / 2
    lebar = LEBAR_PER_SOAL - CELAH_BATANG
    return (f'<rect class="ortu-peta-v3-batang-{jenis_batang(butir)}-st" '
            f'x="{x:.2f}" y="{TINGGI_WAKTU - tinggi:.2f}" width="{lebar}" height="{tinggi:.2f}"/>')


def _garis_rata(rata, maks: int, lebar: int) -> str:
    if rata is None:
        return ""
    posisi = min(max(TINGGI_WAKTU - rata / maks * TINGGI_WAKTU, 0), TINGGI_WAKTU)
    return (f'<line class="ortu-peta-v3-rata-st" x1="0" x2="{lebar}" y1="{posisi:.2f}" y2="{posisi:.2f}" '
            'vector-effect="non-scaling-stroke" stroke-dasharray="6 4"/>')


def _nomor_soal(soal, jenis: str) -> list:
    return [str(b["nomor"]) for b in soal if jenis_batang(b) == jenis]


def soal_terlama(soal):
    """Butir dengan detik terbesar (nomor terkecil bila seri); None bila tak ada detik sama sekali."""
    berdetik = [b for b in soal if b["detik"] is not None]
    if not berdetik:
        return None
    return min(berdetik, key=lambda b: (-b["detik"], b["nomor"]))


def _label_aria(soal) -> str:
    """Ringkasan untuk aria-label grafik: soal benar, soal terlalu cepat, dan soal paling lama bila ada detik."""
    bagian = [COPY_LABEL_WAKTU]
    benar = _nomor_soal(soal, JENIS_BENAR)
    if benar:
        bagian.append(COPY_LABEL_BENAR % ", ".join(benar))
    cepat = _nomor_soal(soal, JENIS_CEPAT)
    if cepat:
        bagian.append(COPY_LABEL_CEPAT % (snap.AMBANG_CEPAT_DETIK, ", ".join(cepat)))
    terlama = soal_terlama(soal)
    if terlama is not None:
        bagian.append(COPY_LABEL_TERLAMA % (terlama["nomor"], terlama["detik"]))
    return " ".join(bagian)


def _teks_sr(butir: dict) -> str:
    """Teks sr-only satu nomor: hasil, detik (bila ada), dan tanda terlalu cepat."""
    prefiks = "dilewati" if not butir["dijawab"] else ("benar" if butir["benar"] == 1 else "salah")
    if butir["detik"] is None:
        return f"{prefiks}, tanpa catatan waktu"
    teks = f"{prefiks}, {butir['detik']} detik"
    if aturan.terlalu_cepat(butir):
        teks += f", dijawab di bawah {snap.AMBANG_CEPAT_DETIK} detik"
    return teks


def _sr_daftar(soal) -> str:
    butir = "".join(f"<li>{e(COPY_SR_NOMOR % (b['nomor'], _teks_sr(b)))}</li>" for b in soal)
    return f'<ul class="ortu-peta-v3-sr-st">{butir}</ul>'


def _nomor_baris(soal) -> str:
    angka = "".join(f"<span>{b['nomor']}</span>" for b in soal)
    return f'<div class="ortu-peta-v3-no-st" aria-hidden="true">{angka}</div>'


def _kata_legenda(jenis: str) -> str:
    if jenis == JENIS_CEPAT:
        return COPY_LEG[jenis] % snap.AMBANG_CEPAT_DETIK
    return COPY_LEG[jenis]


def _legenda(soal, rata) -> str:
    jenis_ada = []
    for butir in soal:
        jenis = jenis_batang(butir)
        if jenis not in jenis_ada:
            jenis_ada.append(jenis)
    teks = [(jenis, _kata_legenda(jenis))
            for jenis in (JENIS_BENAR, JENIS_SALAH, JENIS_CEPAT, JENIS_ABU) if jenis in jenis_ada]
    butir = [f'<li><span class="ortu-peta-v3-swatch-st ortu-peta-v3-swatch-{jenis}-st" aria-hidden="true"></span>'
             f"{e(kata)}</li>" for jenis, kata in teks]
    if rata is not None:
        butir.append('<li><span class="ortu-peta-v3-swatch-st ortu-peta-v3-swatch-rata-st" aria-hidden="true"></span>'
                     f"{e(COPY_LEG_RATA % rata)}</li>")
    return f'<ul class="ortu-peta-v3-leg-st">{"".join(butir)}</ul>'


def grafik_waktu(soal, rata) -> str:
    """Grafik waktu per nomor (SVG), nomor di bawahnya, daftar sr-only per nomor, dan legenda.

    `soal` = butir versi 3 berurutan nomor; `rata` = rata detik per soal atau None (garis rata-rata dihilangkan).
    """
    maks = _maks_detik(soal)
    lebar = len(soal) * LEBAR_PER_SOAL
    batang = "".join(_batang(indeks, butir, maks) for indeks, butir in enumerate(soal))
    svg = (f'<svg class="ortu-peta-v3-waktu-st" viewBox="0 0 {lebar} {TINGGI_WAKTU}" preserveAspectRatio="none" '
           f'role="img" aria-label="{e(_label_aria(soal))}" focusable="false">'
           f'{batang}{_garis_rata(rata, maks, lebar)}</svg>')
    return svg + _nomor_baris(soal) + _legenda(soal, rata) + _sr_daftar(soal)
