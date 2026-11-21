"""Pembantu tes `kenali_bangun_awal`: fakta bangun/benda dan solver TEKS yang ditulis ulang di tes.

Dipakai `test_matematika_awal_kenali_bangun_awal` dan `test_visual_adegan_awal_bentuk`. Fakta
sengaja ditulis ulang di sini (bukan diimpor dari `bentuk_katalog`) supaya tes menangkap salah
fakta di modul jenis. Solver hanya membaca teks soal; kalimat ciri dibaca lewat predikat regex
dan harus cocok dengan TEPAT SATU bangun pada himpunan level.
"""
from __future__ import annotations

import re

DATAR_TES = {"P1": ("segitiga", "persegi", "persegi panjang", "lingkaran"),
             "P2": ("segitiga", "persegi", "persegi panjang", "lingkaran")}
RUANG_TES = {"P1": ("kubus", "balok", "bola", "tabung"),
             "P2": ("kubus", "balok", "bola", "tabung", "kerucut")}
# Fakta benda ditulis ulang di tes (sumber independen).
BENDA_TES = {
    "dadu": "kubus", "rubik": "kubus", "kotak kado yang semua sisinya persegi": "kubus",
    "kardus mi instan": "balok", "kotak sepatu": "balok", "batu bata": "balok",
    "bola sepak": "bola", "kelereng": "bola", "bola basket": "bola",
    "kaleng susu": "tabung", "kaleng cat": "tabung", "lilin batang yang bulat": "tabung",
    "topi ulang tahun": "kerucut", "cone es krim": "kerucut", "tumpeng nasi": "kerucut",
}


def _cocok_datar(bangun: str, ciri: str) -> bool:
    if bangun == "segitiga":
        return bool(re.search(r"\b3 (sisi|sudut)", ciri))
    if bangun == "persegi":
        return "sama panjang" in ciri and not re.search(r"tidak semua|berhadapan", ciri)
    if bangun == "persegi panjang":
        return bool(re.search(r"tidak semua|2 sisi panjang", ciri))
    return bool(re.search(r"tidak punya sudut|bulat", ciri))  # lingkaran


def _cocok_ruang(bangun: str, ciri: str) -> bool:
    if bangun == "kubus":
        return "6 sisi" in ciri and "persegi" in ciri and "persegi panjang" not in ciri
    if bangun == "balok":
        return "6 sisi" in ciri and "persegi panjang" in ciri
    if bangun == "bola":
        return "tidak punya sisi datar" in ciri
    if bangun == "tabung":
        return bool(re.search(r"2 sisi datar|alas dan tutup", ciri))
    return bool(re.search(r"1 sisi datar|titik puncak|runcing", ciri))  # kerucut


def _tunggal(himpunan: tuple, cocok, ciri: str) -> str:
    kandidat_cocok = [b for b in himpunan if cocok(b, ciri)]
    assert len(kandidat_cocok) == 1, ("ciri tidak menunjuk tepat satu bangun", ciri, kandidat_cocok)
    return kandidat_cocok[0]


def solver_dari_teks(teks: str, level: str) -> str:
    baris = teks.split("\n")
    if len(baris) == 1:
        cocok = re.fullmatch(r"(.+) berbentuk seperti bangun ruang apa\?", baris[0])
        assert cocok, ("bentuk benda tidak dikenal", teks)
        benda = cocok.group(1)
        bangun = {b.capitalize(): v for b, v in BENDA_TES.items()}[benda]
        assert bangun in RUANG_TES[level], (teks, "bangun di luar himpunan level")
        return bangun
    assert len(baris) == 2, teks
    ciri, tanya = baris
    if tanya == "Bangun datar apa ini?":
        isi = re.fullmatch(r"Bangun ini (.+)\.", ciri)
        assert isi, ciri
        return _tunggal(DATAR_TES[level], _cocok_datar, isi.group(1))
    if tanya == "Bangun ruang apa ini?":
        isi = re.fullmatch(r"Bangun ruang ini (.+)\.", ciri)
        assert isi, ciri
        return _tunggal(RUANG_TES[level], _cocok_ruang, isi.group(1))
    cocok = re.fullmatch(r"(Bu \w+|Pak \w+) menggambar: (.+)\.", ciri)
    assert cocok, ("daftar tidak dikenal", ciri)
    daftar = cocok.group(2).split(", ")
    assert all(n in DATAR_TES[level] for n in daftar), (daftar, "bangun di luar himpunan level")
    assert 4 <= len(daftar) <= 10 and len(set(daftar)) >= 2
    tanya_isi = re.fullmatch(r"Berapa banyak ([a-z ]+)\?", tanya)
    assert tanya_isi and tanya_isi.group(1) in DATAR_TES[level], tanya
    hitungan = [daftar.count(n) for n in DATAR_TES[level]]
    ditanya = daftar.count(tanya_isi.group(1))
    assert 1 <= ditanya <= 8 and hitungan.count(ditanya) == 1, ("jumlah ditanya harus unik", daftar)
    return str(ditanya)


