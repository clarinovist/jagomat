"""Solver mandiri `tampak_kubus_awal`: hanya membaca TEKS soal (tanpa memanggil kode jenis).

Tinggi tiap tumpukan dibaca lewat regex dari kalimat pertama; banyak kubus dan banyak persegi tiap
tampak dihitung dengan rumus yang ditulis ulang di sini (jumlah semua tumpukan; tumpukan tak kosong;
jumlah tinggi tertinggi tiap kolom; jumlah tinggi tertinggi tiap baris). Dipakai tes jenis dan tes visual.
Orientasi: baris pertama = baris DEPAN, kolom dari kiri ke kanan; tampak depan dilihat dari depan,
tampak samping dari sisi kanan.
"""
from __future__ import annotations

import re

POLA_ALAS = re.compile(
    r"Kubus-kubus satuan disusun pada alas (\d) baris dan (\d) kolom\. "
    r"Tinggi tumpukan dari kiri ke kanan, (.+) \(0 artinya kosong\)\. "
    r"Tiap tumpukan berdiri di lantai\.")
POLA_BARIS = re.compile(r"baris (depan|tengah|belakang): (\d(?:, \d)*)")
URUTAN_BARIS = {2: ["depan", "belakang"], 3: ["depan", "tengah", "belakang"]}
TANYA_KUBUS = "Berapa banyak kubus satuan seluruhnya, termasuk yang tertutup? Tulis angkanya saja."
TANYA_ATAS = "Berapa banyak persegi pada tampak atas (dilihat dari atas)? Tulis angkanya saja."
TANYA_DEPAN = "Berapa banyak persegi pada tampak depan (dilihat dari depan)? Tulis angkanya saja."
TANYA_SAMPING = "Berapa banyak persegi pada tampak samping (dilihat dari sisi kanan)? Tulis angkanya saja."
TANYA_DIKENAL = (TANYA_KUBUS, TANYA_ATAS, TANYA_DEPAN, TANYA_SAMPING)
PENGANTAR_VISUAL = "Perhatikan gambar kubus-kubus satuan. Tiap tumpukan berdiri di lantai."


def jawab_dari_sel(tanya: str, sel: dict) -> str:
    """Jawaban dari pertanyaan dan tinggi tiap sel `{(kolom, baris): tinggi}` (tinggi > 0)."""
    assert tanya in TANYA_DIKENAL, ("pertanyaan tidak dikenal", tanya)
    assert sel and all(h > 0 for h in sel.values()), sel
    if tanya == TANYA_KUBUS:
        return str(sum(sel.values()))
    if tanya == TANYA_ATAS:
        return str(len(sel))
    sumbu = 0 if tanya == TANYA_DEPAN else 1  # depan: kelompok per kolom; samping: per baris
    terbesar: dict = {}
    for sel_kunci, h in sel.items():
        terbesar[sel_kunci[sumbu]] = max(terbesar.get(sel_kunci[sumbu], 0), h)
    return str(sum(terbesar.values()))


def sel_dari_lajur(lajur: list) -> dict:
    """`{(kolom, baris): tinggi}` untuk petak terisi; baris 0 = baris depan."""
    return {(x, y): h for y, baris in enumerate(lajur) for x, h in enumerate(baris) if h}


def lajur_dari_teks(kalimat: str) -> list:
    """Tinggi tiap baris (depan lebih dulu) dari kalimat pertama versi teks; wajib terbaca penuh."""
    cocok = POLA_ALAS.fullmatch(kalimat)
    assert cocok, kalimat
    banyak_baris, banyak_kolom, isi = int(cocok.group(1)), int(cocok.group(2)), cocok.group(3)
    assert banyak_baris in URUTAN_BARIS, banyak_baris
    potongan = isi.split("; ")
    baris = [POLA_BARIS.fullmatch(p) for p in potongan]
    assert all(baris), isi
    assert [b.group(1) for b in baris] == URUTAN_BARIS[banyak_baris], isi
    lajur = [[int(n) for n in b.group(2).split(", ")] for b in baris]
    assert all(len(isi_baris) == banyak_kolom for isi_baris in lajur), lajur
    assert all(0 <= h <= 3 for isi_baris in lajur for h in isi_baris), lajur
    return lajur


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks soal tanpa gambar (dua baris: tinggi tiap tumpukan, lalu pertanyaan)."""
    baris = teks.split("\n")
    assert len(baris) == 2, teks
    return jawab_dari_sel(baris[1], sel_dari_lajur(lajur_dari_teks(baris[0])))
