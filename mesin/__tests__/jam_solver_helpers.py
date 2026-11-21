"""Solver mandiri `baca_jam_awal`: hanya membaca TEKS soal (tanpa memanggil kode jenis).

Letak jarum pada teks dibaca lewat regex; hitungan jam memakai muka jam 1..12 yang ditulis ulang
di sini (rumus berbeda dari kode produksi: `(jam + k) % 12 or 12`). Dipakai tes jenis dan tes visual.
"""
from __future__ import annotations

import re

PENUH = re.compile(
    r"jarum pendek menunjuk angka (\d+) dan jarum panjang menunjuk angka (\d+)", re.I)
SETENGAH = re.compile(
    r"jarum pendek ada di antara angka (\d+) dan (\d+), jarum panjang menunjuk angka (\d+)", re.I)
BACA_PENUH = "Pukul berapa jam ini? Tulis angka jamnya."
BACA_SETENGAH = "Pukul berapa jam ini? Tulis jam, lalu titik, lalu menitnya."
KEMUDIAN = re.compile(r"(\d+) jam lagi, pukul berapa\? Tulis angka jamnya\.")
SELESAI = re.compile(r"(\w+) (.+) selama (\d+) jam\. Pukul berapa \1 selesai\? Tulis angka jamnya\.")


def jam_setelah(jam: int, lama: int) -> int:
    """Muka jam: sesudah 12 kembali ke 1 (rumus sendiri, bukan salinan kode produksi)."""
    return (jam + lama) % 12 or 12


def jawab_dari_waktu(tanya: str, jam: int, menit: int) -> str:
    """Jawaban dari pertanyaan (baris terakhir teks) dan waktu pada jam (dari teks atau gambar)."""
    if tanya == BACA_PENUH:
        assert menit == 0, (tanya, jam, menit)
        return str(jam)
    if tanya == BACA_SETENGAH:
        assert menit == 30, (tanya, jam, menit)
        return f"{jam}.30"
    assert menit == 0, (tanya, jam, menit)
    kemudian, selesai = KEMUDIAN.fullmatch(tanya), SELESAI.fullmatch(tanya)
    assert bool(kemudian) != bool(selesai), ("pertanyaan tidak dikenal", tanya)
    lama = int((kemudian or selesai).group(1 if kemudian else 3))
    return str(jam_setelah(jam, lama))


def waktu_dari_kalimat(kalimat: str) -> tuple:
    """(jam, menit) dari kalimat letak jarum; wajib persis satu pola yang cocok."""
    setengah, penuh = SETENGAH.search(kalimat), PENUH.search(kalimat)
    assert bool(setengah) != bool(penuh), ("kalimat letak jarum ambigu atau kosong", kalimat)
    if setengah:
        a, b, panjang = map(int, setengah.groups())
        assert panjang == 6 and b == a % 12 + 1, kalimat
        return a, 30
    jam, panjang = map(int, penuh.groups())
    assert panjang == 12 and 1 <= jam <= 12, kalimat
    return jam, 0


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks soal tanpa gambar (dua baris: letak jarum, lalu pertanyaan)."""
    baris = teks.split("\n")
    assert len(baris) == 2, teks
    jam, menit = waktu_dari_kalimat(baris[0])
    return jawab_dari_waktu(baris[1], jam, menit)
