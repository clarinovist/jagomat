"""Bilangan rasional katalog: format eksak, tanpa float atau pembulatan diam-diam."""
from fractions import Fraction
import re

PETUNJUK_EKSAK = " Jawab tanpa pembulatan; boleh memakai pecahan a/b atau desimal eksak."
TEMPLATE_EKSAK = frozenset({"perbandingan_senilai", "perbandingan_berbalik", "kerja_bersama",
    "lingkaran_keliling_luas", "juring", "rata_rata_gabungan", "median_modus",
    "volume_prisma_tabung", "skala_peta", "jumlah_deret", "jam_menit_detik", "perbandingan_volume"})


def format_angka(nilai):
    """Desimal berhingga ditulis utuh; pecahan berulang tetap a/b."""
    nilai = Fraction(nilai)
    penyebut = nilai.denominator
    dua = lima = 0
    while penyebut % 2 == 0:
        penyebut //= 2
        dua += 1
    while penyebut % 5 == 0:
        penyebut //= 5
        lima += 1
    if penyebut != 1:
        return str(nilai)
    digit = max(dua, lima)
    skala = 10 ** digit
    angka = abs(nilai.numerator) * (skala // nilai.denominator)
    tanda = "-" if nilai < 0 else ""
    if not digit:
        return tanda + str(angka)
    return tanda + (f"{angka // skala},{angka % skala:0{digit}d}").rstrip("0").rstrip(",")


def baca_angka(teks):
    """Parser terbatas untuk skalar katalog; bukan eval/normalisasi daftar."""
    if not isinstance(teks, str) or len(teks) > 128:
        return None
    t = teks.strip().replace("−", "-")
    if not re.fullmatch(r"[+-]?[0-9]+(?:[.,][0-9]+|\s*/\s*[0-9]+)?", t):
        return None
    try:
        return Fraction(re.sub(r"\s+", "", t).replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None
