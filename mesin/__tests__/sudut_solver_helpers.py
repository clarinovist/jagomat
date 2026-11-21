"""Solver mandiri `ukur_sudut_awal`: hanya membaca TEKS soal (tanpa memanggil kode jenis).

Letak kaki sudut pada skala dibaca lewat regex; besar sudut, golongan, perbandingan, dan selisih
dihitung dengan rumus yang ditulis ulang di sini. Dipakai tes jenis dan tes visual.
"""
from __future__ import annotations

import re

KAKI_NOL = re.compile(r"Kaki ([BO])A menunjuk angka 0 pada skala (luar|dalam) busur derajat\.")
KAKI = re.compile(r"Kaki ([BO])([BC]) menunjuk angka (\d+) pada skala (luar|dalam) "
                  r"dan angka (\d+) pada skala (luar|dalam)\.")
GESER = re.compile(r"Pada skala luar busur derajat, kaki BA menunjuk angka (\d+) "
                   r"dan kaki BC menunjuk angka (\d+)\.")
TANYA_BESAR = "Berapa besar sudut ABC? Tulis angkanya saja."
TANYA_JENIS = "Sudut ABC termasuk jenis apa? Tulis lancip, siku, atau tumpul."
TANYA_BANDING = "Sudut mana yang lebih besar, AOB atau AOC? Tulis B atau C."
TANYA_SELISIH = "Berapa selisih besar sudut AOB dan sudut AOC? Tulis angkanya saja."
TANYA_DIKENAL = (TANYA_BESAR, TANYA_JENIS, TANYA_BANDING, TANYA_SELISIH)
LURUS = 180


def golongan(sudut: int) -> str:
    """Golongan sudut: kurang dari 90 lancip, tepat 90 siku, selebihnya tumpul."""
    if sudut == 90:
        return "siku"
    return "lancip" if sudut < 90 else "tumpul"


def jawab_dari_sudut(tanya: str, sudut_ab: int, sudut_ac: int | None = None) -> str:
    """Jawaban dari pertanyaan dan besar sudut yang diukur dari kaki A (dari gambar atau teks)."""
    assert tanya in TANYA_DIKENAL, ("pertanyaan tidak dikenal", tanya)
    if tanya == TANYA_BESAR:
        return str(sudut_ab)
    if tanya == TANYA_JENIS:
        return golongan(sudut_ab)
    assert sudut_ac is not None and sudut_ab != sudut_ac, (tanya, sudut_ab, sudut_ac)
    if tanya == TANYA_BANDING:
        return "B" if sudut_ab > sudut_ac else "C"
    return str(abs(sudut_ab - sudut_ac))


def _bacaan_pada_skala_nol(skala_nol: str, kaki: tuple) -> int:
    """Angka kaki pada skala yang bernilai 0 di kaki A; kedua angka harus saling melengkapi 180."""
    _, _, angka1, skala1, angka2, skala2 = kaki
    assert {skala1, skala2} == {"luar", "dalam"}, kaki
    assert int(angka1) + int(angka2) == LURUS, kaki
    return int(angka1) if skala1 == skala_nol else int(angka2)


def _sisa_kosong(kalimat: str, cocok: list) -> bool:
    sisa = kalimat
    for m in cocok:
        sisa = sisa.replace(m.group(0), "")
    return not sisa.strip()


def _sudut_dari_kalimat(kalimat: str) -> tuple:
    """(sudut BC, sudut CC atau None) pada kalimat versi teks; wajib terbaca penuh."""
    geser = GESER.fullmatch(kalimat)
    if geser:
        a, b = map(int, geser.groups())
        return abs(a - b), None
    nol = KAKI_NOL.findall(kalimat)
    kaki = list(KAKI.finditer(kalimat))
    assert len(nol) == 1 and 1 <= len(kaki) <= 2, kalimat
    assert _sisa_kosong(kalimat, list(KAKI_NOL.finditer(kalimat)) + kaki), kalimat
    titik = {m.group(1) for m in kaki} | {nol[0][0]}
    assert len(titik) == 1, ("titik sudut tidak konsisten", kalimat)
    bacaan = [_bacaan_pada_skala_nol(nol[0][1], m.groups()) for m in kaki]
    return bacaan[0], (bacaan[1] if len(bacaan) == 2 else None)


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks soal tanpa gambar (dua baris: letak kaki pada skala, lalu pertanyaan)."""
    baris = teks.split("\n")
    assert len(baris) == 2, teks
    pertama, kedua = _sudut_dari_kalimat(baris[0])
    if baris[1] == TANYA_SELISIH or baris[1] == TANYA_BANDING:
        assert [m.group(2) for m in KAKI.finditer(baris[0])] == ["B", "C"], baris[0]
    return jawab_dari_sudut(baris[1], pertama, kedua)
