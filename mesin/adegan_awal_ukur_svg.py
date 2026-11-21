"""SVG sub-adegan `pita_ukur`: dua batang ukur dari ikon satuan (klip, ubin, balok).

KONTRAK HITUNG: tiap `<g class="batang-ukur">` berisi TEPAT `jumlah` elemen
`<image class="unit-ukur">` (satu per sel, ujung ke ujung tanpa celah) di atas satu
`<rect class="pita">` selebar jumlah x sel. Ikon benda (bila ada) adalah satu
`<image class="ikon-benda">` dan BUKAN unit. Ikon klip yang tinggi-sempit diputar 90
derajat pada elemen `<image>`-nya agar rebah horizontal; ubin dan balok apa adanya.
Dua susunan: `bertumpuk` (dua batang di bawah satu sama lain, rata kiri, label dan
ikon benda di kolom kiri) dan `sambung` (dua potong dalam satu deret horizontal,
label potong pertama di atas dan potong kedua di bawah, warna bukan satu-satunya
pembeda). Ukuran sel sama untuk kedua batang agar panjang jujur dibandingkan.
Data sudah divalidasi oleh `adegan_awal_svg.render_adegan_awal`.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import design_tokens as T
from adegan_awal_dasar_svg import (
    bungkus_svg, daftar_nama, garis_pemisah, jalur_ikon, potong_label,
    teks_label,
)

_JUDUL = "Gambar ukuran benda dengan satuan"
# Ikon satuan -> derajat putar; klip digambar tegak sehingga perlu direbahkan.
_ROTASI = {"klip": 90}
_ISI = {"netral": T.ADEGAN_PITA_ISI_NETRAL, "merah": T.ADEGAN_PITA_ISI_MERAH,
        "biru": T.ADEGAN_PITA_ISI_BIRU}
_GARIS = {"netral": T.ADEGAN_PITA_GARIS_NETRAL, "merah": T.ADEGAN_PITA_GARIS_MERAH,
          "biru": T.ADEGAN_PITA_GARIS_BIRU}


def _sel(susun: str, batang) -> int:
    """Sisi sel (bulat): sama untuk kedua batang; sambung memakai total, bertumpuk yang terpanjang."""
    jumlah = [isi["jumlah"] for isi in batang]
    if susun == "bertumpuk":
        ruang, terpanjang = T.ADEGAN_LEBAR - T.ADEGAN_MARGIN - T.ADEGAN_IKON_X, max(jumlah)
    else:
        ruang, terpanjang = T.ADEGAN_LEBAR - 2 * T.ADEGAN_MARGIN, sum(jumlah)
    return min(T.ADEGAN_UKUR_SEL_MAKS, ruang // terpanjang)


def _unit(satuan: str, x: float, y: float, sel: int) -> str:
    putar = ""
    if satuan in _ROTASI:
        putar = f' transform="rotate({_ROTASI[satuan]} {x + sel / 2:g} {y + sel / 2:g})"'
    return (
        f'<image class="unit-ukur" href="{jalur_ikon(satuan)}" x="{x:g}" y="{y:g}" '
        f'width="{sel}" height="{sel}"{putar}/>'
    )


def _pita(warna: str, x: float, y: float, jumlah: int, sel: int) -> str:
    return (
        f'<rect class="pita" x="{x:g}" y="{y:g}" width="{jumlah * sel}" height="{sel}" '
        f'fill="{_ISI[warna]}" stroke="{_GARIS[warna]}" stroke-width="{T.ADEGAN_GARIS}"/>'
    )


def _pita_dan_unit(isi: Mapping[str, Any], satuan: str, x: float, y: float, sel: int) -> str:
    unit = "".join(_unit(satuan, x + i * sel, y, sel) for i in range(isi["jumlah"]))
    return _pita(isi["warna"], x, y, isi["jumlah"], sel) + unit


def _ikon_benda(nama: str, atas: float) -> str:
    return (
        f'<image class="ikon-benda" href="{jalur_ikon(nama)}" x="{T.ADEGAN_MARGIN}" '
        f'y="{atas:g}" width="{T.ADEGAN_UKUR_BENDA}" height="{T.ADEGAN_UKUR_BENDA}"/>'
    )


def _kolom_kiri(isi: Mapping[str, Any], atas: int) -> tuple:
    """Ikon benda (bila ada) lalu label; kembalikan (markup, tinggi isi kolom)."""
    ikon = isi["ikon"]
    label_atas = atas + (T.ADEGAN_UKUR_BENDA + T.ADEGAN_UKUR_JARAK if ikon else 0)
    markup = _ikon_benda(ikon, atas) if ikon else ""
    nama = isi["nama"]
    markup += teks_label(nama, T.ADEGAN_MARGIN, label_atas + T.ADEGAN_FONT)
    return markup, label_atas - atas + len(potong_label(nama)) * T.ADEGAN_LEADING


def _baris_tumpuk(isi: Mapping[str, Any], satuan: str, sel: int, atas: int) -> tuple:
    """Satu batang bertumpuk: (markup `<g>`, tinggi baris termasuk jeda)."""
    kolom, tinggi_isi = _kolom_kiri(isi, atas)
    tinggi = max(tinggi_isi, sel)
    y_pita = atas + (tinggi - sel) // 2
    pita = _pita_dan_unit(isi, satuan, T.ADEGAN_IKON_X, y_pita, sel)
    return '<g class="batang-ukur">' + kolom + pita + "</g>", tinggi + T.ADEGAN_JEDA_BARIS


def _render_bertumpuk(data: Mapping[str, Any], sel: int) -> tuple:
    atas, bagian = T.ADEGAN_MARGIN, []
    terakhir = len(data["batang"]) - 1
    for urutan, isi in enumerate(data["batang"]):
        markup, tinggi = _baris_tumpuk(isi, data["satuan"], sel, atas)
        bagian.append(markup)
        if urutan < terakhir:
            bagian.append(garis_pemisah(atas + tinggi - T.ADEGAN_JEDA_BARIS // 2, "pemisah-baris"))
        atas += tinggi
    return "".join(bagian), atas


def _render_sambung(data: Mapping[str, Any], sel: int) -> tuple:
    """Dua potong satu deret; label potong pertama di atas (rata kiri), kedua di bawah (rata kanan)."""
    pertama, kedua = data["batang"]
    y_pita = T.ADEGAN_MARGIN + T.ADEGAN_LEADING + T.ADEGAN_UKUR_JARAK
    x_kedua = T.ADEGAN_MARGIN + pertama["jumlah"] * sel
    x_akhir = x_kedua + kedua["jumlah"] * sel
    dasar_bawah = y_pita + sel + T.ADEGAN_UKUR_JARAK + T.ADEGAN_FONT
    atas_label = teks_label(pertama["nama"], T.ADEGAN_MARGIN, T.ADEGAN_MARGIN + T.ADEGAN_FONT,
                            satu_baris=True)
    bawah_label = teks_label(kedua["nama"], x_akhir, dasar_bawah, "end", satu_baris=True)
    satu = '<g class="batang-ukur">' + atas_label
    satu += _pita_dan_unit(pertama, data["satuan"], T.ADEGAN_MARGIN, y_pita, sel) + "</g>"
    dua = '<g class="batang-ukur">'
    dua += _pita_dan_unit(kedua, data["satuan"], x_kedua, y_pita, sel) + bawah_label + "</g>"
    return satu + dua, dasar_bawah + T.ADEGAN_MARGIN


def _uraian(data: Mapping[str, Any]) -> str:
    nama = daftar_nama([isi["nama"] for isi in data["batang"]])
    satuan = data["satuan"]
    if data["susun"] == "sambung":
        return (f"Dua potong disambung ujung ke ujung, {nama}; tiap potong tersusun dari {satuan}. "
                f"Hitung {satuan} pada tiap potong.")
    return f"Dua batang ukur tersusun dari {satuan}: {nama}. Hitung {satuan} pada tiap batang."


def render_pita_ukur(data: Mapping[str, Any], namespace: str) -> str:
    sel = _sel(data["susun"], data["batang"])
    gambar = _render_sambung if data["susun"] == "sambung" else _render_bertumpuk
    isi, tinggi = gambar(data, sel)
    return bungkus_svg(namespace, tinggi, _JUDUL, _uraian(data), isi)


def ringkasan_pita_ukur(data: Mapping[str, Any]) -> str:
    daftar = ", ".join(f"{isi['nama']} sepanjang {isi['jumlah']} {data['satuan']}"
                       for isi in data["batang"])
    sambung = "; kedua potong disambung ujung ke ujung" if data["susun"] == "sambung" else ""
    return f"Fakta visual: {daftar}{sambung}."
