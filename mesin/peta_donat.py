"""Donat pola kesalahan (SVG) untuk laporan Peta Kemampuan.

Irisan sebanding dengan JUMLAH jawaban salah per pola (bukan persen), dimulai dari
jam 12 searah jarum jam. Tiap irisan dan kartu keterangannya membawa
`data-pola` agar skrip (`peta_browser`) bisa menyorotnya; warna lewat kelas
`peta-w<i>-st` (CSS), bukan atribut warna. Fallback tanpa JS: daftar pola dan
semua detailnya tetap tampil di luar SVG.
"""
from __future__ import annotations

import math
import textwrap
from typing import List, Tuple

from peta_teks import e

LEBAR = 690
PUSAT_X = LEBAR // 2
JARI = 92
TEBAL_CINCIN = 46
JARI_LUAR = JARI + TEBAL_CINCIN // 2
JARI_LUBANG = 65
JARI_ANGKA = 15
CELAH_DERAJAT = 2.0
LEBAR_KARTU = 215
JARAK_KARTU = 14
TINGGI_MIN = 380
MARGIN_ATAS = 18
BARIS_PER_KARTU = 19
LEBAR_JUDUL_KARTU = 20
JUMLAH_WARNA = 4
# Jendela potong untuk layar sempit (hanya cincin): sisi bujur sangkar di sekitar pusat.
SISI_POTONG = 2 * (JARI_LUAR + 22)


def _titik(derajat: float, jari: float) -> Tuple[float, float, float]:
    """(x, y) pada sudut `derajat` dari jam 12 searah jarum jam; y dari pusat atas."""
    radian = math.radians(derajat)
    return jari * math.sin(radian), -jari * math.cos(radian), radian


def _irisan(pola: tuple) -> List[tuple]:
    """[(pola, awal, akhir, tengah)] dalam derajat; `awal`/`akhir` sudah dikurangi celah."""
    total = sum(p.jumlah for p in pola)
    hasil, sudut = [], 0.0
    celah = CELAH_DERAJAT / 2 if len(pola) > 1 else 0.0
    for p in pola:
        lebar = 360.0 * p.jumlah / total
        hasil.append((p, sudut + celah, sudut + lebar - celah, sudut + lebar / 2))
        sudut += lebar
    return hasil


def _busur(cx: float, cy: float, awal: float, akhir: float) -> str:
    x0, y0, _ = _titik(awal, JARI)
    x1, y1, _ = _titik(akhir, JARI)
    besar = 1 if akhir - awal > 180 else 0
    return "M%.1f %.1f A%d %d 0 %d 1 %.1f %.1f" % (cx + x0, cy + y0, JARI, JARI, besar, cx + x1, cy + y1)


def _kelas_warna(indeks: int) -> str:
    return "w%d" % (indeks % JUMLAH_WARNA)


def _irisan_svg(irisan: List[tuple], pusat_y: float, total_salah: int) -> str:
    bagian = []
    for indeks, (pola, awal, akhir, _tengah_derajat) in enumerate(irisan):
        warna = _kelas_warna(indeks)
        atribut = (
            'class="peta-seg-st peta-seg-%s-st" data-pola="%s" data-angka="%d" '
            'data-teks="dari %d salah" data-kecil="di pola ini"'
        ) % (warna, e(pola.kunci), pola.jumlah, total_salah)
        if len(irisan) == 1:
            bagian.append('<circle %s cx="%d" cy="%.1f" r="%d"/>' % (atribut, PUSAT_X, pusat_y, JARI))
        else:
            bagian.append('<path %s d="%s"/>' % (atribut, _busur(PUSAT_X, pusat_y, awal, akhir)))
    return "".join(bagian)


def _angka_irisan(irisan: List[tuple], pusat_y: float) -> str:
    bagian = []
    for indeks, (pola, _awal, _akhir, tengah) in enumerate(irisan):
        dx, dy, _ = _titik(tengah, JARI)
        bagian.append(
            '<g class="peta-seg-st" data-pola="%s"><circle class="peta-bulat-%s-st" cx="%.1f" cy="%.1f" r="%d"/>'
            '<text class="peta-angka-st" x="%.1f" y="%.1f" text-anchor="middle">%d</text></g>'
            % (e(pola.kunci), _kelas_warna(indeks), PUSAT_X + dx, pusat_y + dy, JARI_ANGKA,
               PUSAT_X + dx, pusat_y + dy + 5.5, pola.jumlah)
        )
    return "".join(bagian)


def _tinggi_kartu(pola) -> int:
    baris = len(textwrap.wrap(pola.nama, LEBAR_JUDUL_KARTU)) + 2
    return 14 + BARIS_PER_KARTU * baris


def _terbanyak(pola: tuple):
    """Kunci pola dengan jumlah terbesar bila tunggal; None bila seri."""
    urut = sorted(pola, key=lambda p: -p.jumlah)
    if len(urut) > 1 and urut[0].jumlah == urut[1].jumlah:
        return None
    return urut[0].kunci


def _kartu(pola, indeks: int, x: float, y: float, tinggi: int, terbanyak, total_salah: int) -> str:
    warna = _kelas_warna(indeks)
    judul = textwrap.wrap(pola.nama, LEBAR_JUDUL_KARTU)
    teks_x = x + 46
    garis = []
    for n, baris in enumerate(judul):
        garis.append('<text class="peta-l-judul-st" x="%.1f" y="%.1f">%s</text>' % (teks_x, y + 22 + n * BARIS_PER_KARTU, e(baris)))
    dasar = y + 22 + len(judul) * BARIS_PER_KARTU
    sub = "%d dari %d" % (pola.jumlah, total_salah) + (" · terbanyak" if pola.kunci == terbanyak else "")
    garis.append('<text class="peta-l-sub-st" x="%.1f" y="%.1f">%s</text>' % (teks_x, dasar, e(sub)))
    garis.append('<text class="peta-l-materi-st" x="%.1f" y="%.1f">%s</text>' % (teks_x, dasar + 17, e(pola.asal)))
    return (
        '<rect class="peta-kotak-%s-st" x="%.1f" y="%.1f" width="%d" height="%d" rx="14"/>'
        '<circle class="peta-bulat-%s-st" cx="%.1f" cy="%.1f" r="15"/>'
        '<text class="peta-simbol-st" x="%.1f" y="%.1f" text-anchor="middle">%s</text>%s'
    ) % (warna, x, y, LEBAR_KARTU, tinggi, warna, x + 24, y + tinggi / 2, x + 24, y + tinggi / 2 + 6, e(pola.simbol), "".join(garis))


def _penghubung(indeks: int, sisi: str, tepi_x: float, kartu_y: float, tinggi: int, pusat_y: float, tengah: float) -> str:
    tx, ty, _ = _titik(tengah, JARI_LUAR + 4)
    ujung_x, ujung_y = PUSAT_X + tx, pusat_y + ty
    arah = -1 if sisi == "kanan" else 1
    siku_x = ujung_x + arah * 26
    titik = "%.1f,%.1f %.1f,%.1f %.1f,%.1f" % (tepi_x, kartu_y + tinggi / 2, siku_x, kartu_y + tinggi / 2, ujung_x, ujung_y)
    return '<polyline class="peta-garis-%s-st" points="%s" marker-end="url(#peta-panah-%d)"/>' % (_kelas_warna(indeks), titik, indeks % JUMLAH_WARNA)


def _susun_sisi(item: List[tuple], pusat_y: float) -> List[tuple]:
    """[(item, y atas, tinggi)] ditumpuk vertikal di sekitar `pusat_y`, urut atas ke bawah."""
    item = sorted(item, key=lambda butir: butir[2])
    tinggi = [_tinggi_kartu(butir[1]) for butir in item]
    total = sum(tinggi) + JARAK_KARTU * max(len(item) - 1, 0)
    y, hasil = pusat_y - total / 2, []
    for butir, t in zip(item, tinggi):
        hasil.append((butir, y, t))
        y += t + JARAK_KARTU
    return hasil


def _tinggi_total(irisan: List[tuple]) -> int:
    kanan = [p for p, _a, _b, t in irisan if math.sin(math.radians(t)) >= 0]
    kiri = [p for p, _a, _b, t in irisan if math.sin(math.radians(t)) < 0]
    terbesar = max(sum(_tinggi_kartu(p) + JARAK_KARTU for p in sisi) for sisi in (kanan, kiri) if sisi) if irisan else 0
    return int(max(TINGGI_MIN, terbesar + 2 * MARGIN_ATAS))


def _kartu_dan_garis(irisan: List[tuple], pusat_y: float, total_salah: int) -> str:
    terbanyak = _terbanyak(tuple(p for p, _a, _b, _t in irisan))
    sisi_item = {"kanan": [], "kiri": []}
    for indeks, (pola, _a, _b, tengah) in enumerate(irisan):
        _x, y_tengah, _r = _titik(tengah, JARI)
        sisi = "kanan" if math.sin(math.radians(tengah)) >= 0 else "kiri"
        sisi_item[sisi].append((indeks, pola, y_tengah, tengah))
    bagian = []
    for sisi, item in sisi_item.items():
        x = LEBAR - LEBAR_KARTU if sisi == "kanan" else 0
        tepi = x if sisi == "kanan" else x + LEBAR_KARTU
        for (indeks, pola, _y, tengah), y, tinggi in _susun_sisi([(i, p, yy, t) for i, p, yy, t in item], pusat_y):
            isi = _penghubung(indeks, sisi, tepi, y, tinggi, pusat_y, tengah) + _kartu(pola, indeks, x, y, tinggi, terbanyak, total_salah)
            bagian.append('<g class="peta-seg-st peta-lbl-st" data-pola="%s">%s</g>' % (e(pola.kunci), isi))
    return "".join(bagian)


def _penanda_panah() -> str:
    penanda = (
        '<marker id="peta-panah-%d" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
        'orient="auto-start-reverse"><path class="peta-panah-w%d-st" d="M0 0 10 5 0 10z"/></marker>'
    )
    return "<defs>%s</defs>" % "".join(penanda % (i, i) for i in range(JUMLAH_WARNA))


def _tengah(pusat_y: float, total_salah: int, total_soal: int) -> str:
    return (
        '<circle class="peta-lubang-st" cx="%d" cy="%.1f" r="%d"/>'
        '<text class="peta-t-angka-st" id="peta-donat-angka" x="%d" y="%.1f" text-anchor="middle">%d</text>'
        '<text class="peta-t-teks-st" id="peta-donat-teks" x="%d" y="%.1f" text-anchor="middle">jawaban salah</text>'
        '<text class="peta-t-kecil-st" id="peta-donat-kecil" x="%d" y="%.1f" text-anchor="middle">dari %d soal</text>'
    ) % (PUSAT_X, pusat_y, JARI_LUBANG, PUSAT_X, pusat_y + 6, total_salah,
         PUSAT_X, pusat_y + 30, PUSAT_X, pusat_y + 48, total_soal)


def _ringkasan_aria(pola: tuple, total_salah: int, total_soal: int) -> str:
    rinci = ", ".join("%d %s" % (p.jumlah, p.nama.lower()) for p in pola)
    return "%d jawaban salah dari %d soal: %s" % (total_salah, total_soal, rinci)


def _posisi_potong(tinggi: int) -> str:
    """Atribut gaya jendela potong layar sempit: lebar svg dan geseran dalam persen."""
    skala = 100.0 * LEBAR / SISI_POTONG
    kiri = -100.0 * (PUSAT_X - SISI_POTONG / 2) / SISI_POTONG
    atas = -(tinggi / 2 - SISI_POTONG / 2) * skala / LEBAR
    return "--peta-w:%.1f%%;--peta-x:%.1f%%;--peta-y:%.1f%%" % (skala, kiri, atas)


def render_donat(pola: tuple, total_soal: int, total_salah: int) -> str:
    """Markup donat; tanpa pola (tidak ada jawaban salah) menampilkan cincin kosong bertulisan 0."""
    if not pola or total_salah < 1:
        return (
            '<div class="peta-donat-st" id="peta-donat"><svg viewBox="0 0 %d %d" role="img" aria-label="Tidak ada jawaban salah">'
            '<circle class="peta-cincin-kosong-st" cx="%d" cy="%d" r="%d"/>%s</svg></div>'
        ) % (LEBAR, TINGGI_MIN, PUSAT_X, TINGGI_MIN // 2, JARI, _tengah(TINGGI_MIN / 2, 0, total_soal))
    tinggi = _tinggi_total(_irisan(pola))
    pusat_y = tinggi / 2
    irisan = _irisan(pola)
    return (
        '<div class="peta-donat-st" id="peta-donat" style="%s"><svg viewBox="0 0 %d %d" role="img" aria-label="%s">'
        '%s<circle class="peta-cincin-kosong-st" cx="%d" cy="%.1f" r="%d"/>%s%s%s%s</svg></div>'
    ) % (
        _posisi_potong(tinggi), LEBAR, tinggi, e(_ringkasan_aria(pola, total_salah, total_soal)),
        _penanda_panah(), PUSAT_X, pusat_y, JARI,
        _irisan_svg(irisan, pusat_y, total_salah), _kartu_dan_garis(irisan, pusat_y, total_salah),
        _angka_irisan(irisan, pusat_y), _tengah(pusat_y, total_salah, total_soal),
    )
