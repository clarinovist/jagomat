"""Pemformat teks bersama laporan dan lembar Peta Kemampuan. Fungsi murni.

Semua teks dari data lewat `e()` (escape) sebelum masuk markup.
"""
from __future__ import annotations

import html
from datetime import date

BULAN_PENDEK = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
COPY_POSISI_BELUM = "Peringkat muncul setelah cukup data"
PERSENTIL_MAKS_TAMPIL = 99


def e(teks) -> str:
    """Escape teks untuk isi dan atribut."""
    return html.escape(str(teks), quote=True)


def tanggal_pendek(tanggal: date) -> str:
    """`1 Nov 2026`."""
    return "%d %s %d" % (tanggal.day, BULAN_PENDEK[tanggal.month - 1], tanggal.year)


def tanggal_cap(tanggal: date) -> str:
    """`19·11·26`, untuk cap lembar."""
    return "%02d·%02d·%02d" % (tanggal.day, tanggal.month, tanggal.year % 100)


def inisial(nama: str) -> str:
    """Dua huruf awal dari dua kata pertama nama; "?" bila kosong."""
    kata = [k for k in nama.replace("(", " ").split() if k[:1].isalpha()]
    return "".join(k[0].upper() for k in kata[:2]) or "?"


def teks_peringkat(posisi) -> str:
    """`Peringkat 67 dari 214`, atau pesan menunggu data."""
    if posisi is None:
        return COPY_POSISI_BELUM
    return "Peringkat %d dari %d" % (posisi.peringkat, posisi.penyebut)


def kalimat_posisi(posisi, kelas: int) -> str:
    """Kalimat utama posisi (markup, `<b>` untuk angka); nilai sudah aman.

    Tidak pernah menulis "lebih tinggi dari 100%": persentil dijepit ke 99, skor
    tertinggi diberi kalimat sendiri, dan persentil 0 tidak memakai "lebih tinggi".
    """
    if posisi is None:
        return e(COPY_POSISI_BELUM)
    if posisi.peringkat == 1:
        return "Skor <b>tertinggi</b> di antara anak kelas %d" % kelas
    if posisi.persentil < 1:
        return "Posisi di antara anak kelas %d" % kelas
    return "Lebih tinggi dari <b>%d%%</b> anak kelas %d" % (min(posisi.persentil, PERSENTIL_MAKS_TAMPIL), kelas)


def teks_biasa(markup: str) -> str:
    """Kalimat posisi tanpa tag, untuk atribut aria-label."""
    return markup.replace("<b>", "").replace("</b>", "")


def sebaran_kelompok(skor_pembanding, jumlah_kelompok: int = 10, lebar: int = 10) -> tuple:
    """Banyak skor per kelompok 0-9, 10-19, ..., 90-100 (kelompok terakhir menampung 100)."""
    hitung = [0] * jumlah_kelompok
    for skor in skor_pembanding:
        hitung[min(skor // lebar, jumlah_kelompok - 1)] += 1
    return tuple(hitung)


def kelompok_skor(skor: int, jumlah_kelompok: int = 10, lebar: int = 10) -> int:
    return min(skor // lebar, jumlah_kelompok - 1)


def label_kelompok(indeks: int, jumlah_kelompok: int = 10, lebar: int = 10) -> str:
    """`70–79`, dan `90–100` untuk kelompok terakhir."""
    bawah = indeks * lebar
    atas = 100 if indeks == jumlah_kelompok - 1 else bawah + lebar - 1
    return "%d–%d" % (bawah, atas)
