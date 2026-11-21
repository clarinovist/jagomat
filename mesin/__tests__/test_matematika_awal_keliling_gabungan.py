"""Matematika Awal, jenis keliling_gabungan (P5): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang hanya
membaca TEKS soal dan menghitung keliling dari garis tepi (bangun gabungan digambar di
kisi satuan atau dihitung dari sisi luarnya), bukan memakai rumus modul. Bangun tak
ambigu: dua persegi panjang bersisi lebar sama disambung penuh pada sisi lebarnya; pojok
yang dipotong selalu persegi kecil dengan sisi < sisi terpendek.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import awal_keliling_gabungan as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "keliling_gabungan"
LEVEL = "P5"
SEED = range(200)
VARIAN_LAMA = ("persegi_persegipanjang", "dua_persegipanjang", "bentuk_L",
               "segitiga_sama_sisi_di_persegi")
VARIAN_BARU = ("segitiga", "jajar_genjang_belah_ketupat", "trapesium", "lingkaran",
               "bentuk_T_U_tangga")
VARIAN = VARIAN_LAMA + VARIAN_BARU
TANYA = ("keliling_persegi", "keliling_persegipanjang", "sisi_dari_keliling",
         "panjang_dari_keliling")
UKURAN_TANYA = {"keliling_persegi": 58, "keliling_persegipanjang": 182,
                "sisi_dari_keliling": 58, "panjang_dari_keliling": 154}
UKURAN_PER_VARIAN = {"persegi_persegipanjang": 452, "dua_persegipanjang": 220,
                     "bentuk_L": 216, "segitiga_sama_sisi_di_persegi": 58,
                     "segitiga": 464, "jajar_genjang_belah_ketupat": 402, "trapesium": 404,
                     "lingkaran": 56, "bentuk_T_U_tangga": 384}
UKURAN_SUB_BARU = {"keliling_sembarang": 86, "keliling_sama_kaki": 88, "keliling_sama_sisi": 58,
                   "cari_sisi_ketiga": 86, "cari_sisi_sama_sisi": 58, "cari_alas_sama_kaki": 88,
                   "jajar_genjang": 180, "jajar_genjang_tinggi": 16, "belah_ketupat": 58,
                   "cari_sisi_belah_ketupat": 58, "layang_layang": 90,
                   "trapesium_sembarang": 208, "trapesium_sama_kaki": 136,
                   "trapesium_sama_kaki_tinggi": 60, "keliling_dari_jari": 20,
                   "keliling_dari_diameter": 16, "keliling_setengah_lingkaran": 20,
                   "tangga": 96, "huruf_U": 144, "huruf_T": 144}
UKURAN_LAMA = 946  # domain sebelum varian tambahan: harus tetap persis (append-only)
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
KUNCI_POLOS = re.compile(r"[1-9]\d*(?:,\d*[1-9])?")  # bulat atau desimal berkoma tanpa nol buntut
ANGKA_POLOS = re.compile(r"\d+(?:,\d+)?")
SATUAN = ("cm", "m")
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)


# ── solver dari teks: keliling dari garis tepi ───────────────────────────

def keliling_kisi(sel: set) -> int:
    """Keliling gabungan sel satuan = banyak sisi sel yang tidak berbatasan dengan sel lain."""
    hasil = 0
    for (x, y) in sel:
        for tetangga in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            hasil += tetangga not in sel
    return hasil


def persegi_panjang(x0: int, y0: int, panjang: int, lebar: int) -> set:
    return {(x, y) for x in range(x0, x0 + panjang) for y in range(y0, y0 + lebar)}


def _persegi(s):
    return keliling_kisi(persegi_panjang(0, 0, s, s))


def _pp(p, l):
    assert p > l, "panjang harus lebih dari lebar"
    return keliling_kisi(persegi_panjang(0, 0, p, l))


def _dari_keliling_persegi(k):
    s = k / 4
    assert s == int(s) and _persegi(int(s)) == k
    return s


def _panjang_dari_keliling(k, l):
    p = k / 2 - l
    assert p == int(p) and p > l and _pp(int(p), l) == k
    return p


def _dua_pp(l, p1, l2, p2, l3):
    assert l == l2 == l3, "lebar kedua persegi panjang harus sama"
    assert p1 > l and p2 > l and p1 != p2, "sisi lebar harus sisi terpendek, panjang beda"
    gabung = persegi_panjang(0, 0, p1, l) | persegi_panjang(p1, 0, p2, l)
    assert len(gabung) == (p1 + p2) * l, "tidak boleh menumpuk"
    return keliling_kisi(gabung)


def _bentuk_l(p, l, s):
    assert p > l and s < min(p, l), "pojok yang dipotong harus lebih kecil dari sisi terpendek"
    sel = persegi_panjang(0, 0, p, l) - persegi_panjang(0, 0, s, s)  # pojok kiri bawah
    return keliling_kisi(sel)


def _segitiga_di_persegi(s, s2):
    assert s == s2, "segitiga sama sisi harus bersisi sama dengan persegi"
    sisi_persegi = 4 * s
    sisi_segitiga = 3 * s
    menempel = s  # satu sisi persegi berimpit satu sisi segitiga: keduanya hilang dari tepi
    return sisi_persegi + sisi_segitiga - 2 * menempel


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; satuan harus konsisten dan bangun harus sah."""
    satuan = re.search(r"\b(cm|m)\b", teks)
    assert satuan, teks
    u = satuan.group(1)
    lawan = "m" if u == "cm" else "cm"
    assert not re.search(rf"\d {lawan}\b", teks), ("satuan campur", teks)
    s = re.escape(u)
    cocok = re.fullmatch(
        rf"Sebuah persegi mempunyai panjang sisi (\d+) {s}\. Berapa {s} keliling persegi itu\?",
        teks)
    if cocok:
        return str(_persegi(int(cocok.group(1))))
    cocok = re.fullmatch(
        rf"Sebuah persegi panjang mempunyai panjang (\d+) {s} dan lebar (\d+) {s}\. "
        rf"Berapa {s} keliling persegi panjang itu\?", teks)
    if cocok:
        return str(_pp(int(cocok.group(1)), int(cocok.group(2))))
    cocok = re.fullmatch(
        rf"Keliling sebuah persegi adalah (\d+) {s}\. Berapa {s} panjang sisi persegi itu\?",
        teks)
    if cocok:
        return str(int(_dari_keliling_persegi(int(cocok.group(1)))))
    cocok = re.fullmatch(
        rf"Keliling sebuah persegi panjang adalah (\d+) {s} dan lebarnya (\d+) {s}\. "
        rf"Berapa {s} panjang sisinya yang lebih panjang\?", teks)
    if cocok:
        return str(int(_panjang_dari_keliling(int(cocok.group(1)), int(cocok.group(2)))))
    cocok = re.fullmatch(
        rf"Persegi panjang pertama panjangnya (\d+) {s} dan lebarnya (\d+) {s}\. "
        rf"Persegi panjang kedua panjangnya (\d+) {s} dan lebarnya (\d+) {s}\. Keduanya "
        rf"disambung rapat pada sisi lebarnya \((\d+) {s}\) tanpa saling menumpuk sehingga "
        rf"membentuk satu persegi panjang yang lebih besar\. Berapa {s} keliling bangun "
        rf"gabungan itu\?", teks)
    if cocok:
        p1, l1, p2, l2, l3 = (int(x) for x in cocok.groups())
        return str(_dua_pp(l1, p1, l2, p2, l3))
    cocok = re.fullmatch(
        rf"Sebuah persegi panjang mempunyai panjang (\d+) {s} dan lebar (\d+) {s}\. Pada "
        rf"salah satu pojoknya dipotong sebuah persegi kecil dengan sisi (\d+) {s} sehingga "
        rf"bangunnya berbentuk huruf L\. Berapa {s} keliling bangun berbentuk L itu\?", teks)
    if cocok:
        p, l, potong = (int(x) for x in cocok.groups())
        return str(_bentuk_l(p, l, potong))
    cocok = re.fullmatch(
        rf"Sebuah persegi mempunyai panjang sisi (\d+) {s}\. Pada salah satu sisinya "
        rf"ditempelkan sebuah segitiga sama sisi yang panjang sisinya juga (\d+) {s}, tepat "
        rf"berimpit dengan sisi persegi itu \(seperti atap rumah\)\. Berapa {s} keliling "
        rf"bangun gabungan itu\?", teks)
    if cocok:
        return str(_segitiga_di_persegi(int(cocok.group(1)), int(cocok.group(2))))
    return solver_baru(teks, s)


# ── solver varian tambahan: geometri dari teks, bukan rumus modul ─────────

def keliling_poligon(titik: list) -> int:
    """Jumlah panjang tepi poligon tertutup; harus bulat (galat < 1e-6)."""
    total = sum(math.dist(titik[i], titik[(i + 1) % len(titik)]) for i in range(len(titik)))
    assert abs(total - round(total)) < 1e-6, total
    return round(total)


def _segitiga_sah(a, b, c):
    assert a + b > c and a + c > b and b + c > a, "ketidaksamaan segitiga"
    return a + b + c


def _trapesium_titik(atas, bawah, kaki1, kaki2):
    """A(0,0) B(bawah,0), D dan C di atas; kaki AD = kaki1, BC = kaki2."""
    s = bawah - atas
    assert s > 0
    x = Fraction(s * s + kaki1 ** 2 - kaki2 ** 2, 2 * s)
    h2 = kaki1 ** 2 - x ** 2
    assert h2 > 0, "trapesium tak ada: kaki terlalu pendek/panjang"
    h = math.sqrt(h2)
    return [(0, 0), (bawah, 0), (float(x) + atas, h), (float(x), h)]


def _komaa(nilai: Fraction) -> str:
    from decimal import Decimal
    d = (Decimal(nilai.numerator) / Decimal(nilai.denominator)).normalize()
    return format(d, "f").replace(".", ",")


def _pi_dari_teks(pi: str, jari: int) -> Fraction:
    if pi == "22/7":
        assert jari % 7 == 0 and jari <= 35, "22/7 hanya untuk jari-jari kelipatan 7"
        return Fraction(22, 7)
    assert pi == "3,14" and jari % 10 == 0 and jari <= 50
    return Fraction(314, 100)


def _sel_tangga(n, lebar, turun, tinggi_kanan):
    assert tinggi_kanan == turun, "anak tangga paling kanan setinggi satu turunan"
    sel = set()
    for i in range(n):
        tinggi = tinggi_kanan + (n - 1 - i) * turun
        sel |= persegi_panjang(i * lebar, 0, lebar, tinggi)
    return sel


def _sel_u(w, h, g, d):
    assert g < w and d < h and (w - g) % 2 == 0 and (w - g) // 2 >= 2, "U tak sah"
    x0 = (w - g) // 2
    return persegi_panjang(0, 0, w, h) - persegi_panjang(x0, h - d, g, d)


def _sel_t(w, a, t, h):
    assert t < w and (w - t) % 2 == 0, "tiang harus tepat di tengah"
    x0 = (w - t) // 2
    return persegi_panjang(0, h, w, a) | persegi_panjang(x0, 0, t, h)


def solver_baru(teks: str, u: str) -> str:
    s = re.escape(u)
    n = rf"(\d+) {s}"
    bil = lambda grup: [int(x) for x in grup]  # noqa: E731

    def cocok(pola):
        return re.fullmatch(pola, teks)

    if (m := cocok(rf"Sebuah segitiga mempunyai sisi-sisi sepanjang {n}, {n}, dan {n}\. "
                   rf"Berapa {s} keliling segitiga itu\?")):
        return str(_segitiga_sah(*bil(m.groups())))
    if (m := cocok(rf"Sebuah segitiga sama kaki mempunyai dua kaki yang sama panjang, "
                   rf"masing-masing {n}, dan alas {n}\. Berapa {s} keliling segitiga itu\?")):
        k, a = bil(m.groups())
        assert k != a
        return str(_segitiga_sah(k, k, a))
    if (m := cocok(rf"Sebuah segitiga sama sisi mempunyai panjang sisi {n}\. Berapa {s} "
                   rf"keliling segitiga itu\?")):
        return str(_segitiga_sah(*(bil(m.groups()) * 3)))
    if (m := cocok(rf"Keliling sebuah segitiga adalah {n}\. Dua sisinya panjangnya {n} dan "
                   rf"{n}\. Berapa {s} panjang sisi yang ketiga\?")):
        keliling, a, b = bil(m.groups())
        c = keliling - a - b
        assert _segitiga_sah(a, b, c) == keliling
        return str(c)
    if (m := cocok(rf"Keliling sebuah segitiga sama sisi adalah {n}\. Berapa {s} panjang "
                   rf"sisi segitiga itu\?")):
        keliling = bil(m.groups())[0]
        assert keliling % 3 == 0
        return str(keliling // 3)
    if (m := cocok(rf"Keliling sebuah segitiga sama kaki adalah {n}\. Panjang kedua kakinya "
                   rf"masing-masing {n}\. Berapa {s} panjang alasnya\?")):
        keliling, k = bil(m.groups())
        a = keliling - 2 * k
        assert a != k and _segitiga_sah(k, k, a) == keliling
        return str(a)
    return solver_baru_datar(teks, u)


def solver_baru_datar(teks: str, u: str) -> str:
    s = re.escape(u)
    n = rf"(\d+) {s}"
    bil = lambda grup: [int(x) for x in grup]  # noqa: E731

    def cocok(pola):
        return re.fullmatch(pola, teks)

    if (m := cocok(rf"Sebuah jajar genjang mempunyai alas {n} dan sisi miring {n}\. "
                   rf"Sisi-sisi yang berhadapan sama panjang\. Berapa {s} keliling jajar "
                   rf"genjang itu\?")):
        a, b = bil(m.groups())
        assert a != b
        return str(keliling_poligon([(0, 0), (a, 0), (a + b / 2, b * math.sqrt(3) / 2),
                                     (b / 2, b * math.sqrt(3) / 2)]))
    if (m := cocok(rf"Sebuah jajar genjang mempunyai alas {n}, sisi miring {n}, dan tinggi "
                   rf"{n}\. Sisi-sisi yang berhadapan sama panjang\. Berapa {s} keliling "
                   rf"jajar genjang itu\?")):
        a, b, t = bil(m.groups())
        assert 0 < t < b
        x = math.sqrt(b * b - t * t)
        return str(keliling_poligon([(0, 0), (a, 0), (a + x, t), (x, t)]))
    if (m := cocok(rf"Sebuah belah ketupat mempunyai empat sisi yang sama panjang, "
                   rf"masing-masing {n}\. Berapa {s} keliling belah ketupat itu\?")):
        sisi = bil(m.groups())[0]
        return str(keliling_poligon([(0, 0), (sisi, 0), (sisi * 1.5, sisi * math.sqrt(3) / 2),
                                     (sisi / 2, sisi * math.sqrt(3) / 2)]))
    if (m := cocok(rf"Keliling sebuah belah ketupat adalah {n}\. Berapa {s} panjang sisi "
                   rf"belah ketupat itu\?")):
        keliling = bil(m.groups())[0]
        assert keliling % 4 == 0
        sisi = keliling // 4
        assert keliling_poligon([(0, 0), (sisi, 0), (sisi * 1.5, sisi * math.sqrt(3) / 2),
                                 (sisi / 2, sisi * math.sqrt(3) / 2)]) == keliling
        return str(sisi)
    if (m := cocok(rf"Sebuah layang-layang mempunyai dua sisi pendek yang sama panjang, "
                   rf"masing-masing {n}, dan dua sisi panjang yang sama panjang, masing-masing "
                   rf"{n}\. Berapa {s} keliling layang-layang itu\?")):
        a, b = bil(m.groups())
        assert a < b
        e = math.hypot(a, b)  # diagonal simetri; sudut di B dan D siku-siku
        titik = [(0, 0), (a * a / e, a * b / e), (e, 0), (a * a / e, -a * b / e)]
        return str(keliling_poligon(titik))
    return solver_baru_trapesium(teks, u)


def solver_baru_trapesium(teks: str, u: str) -> str:
    s = re.escape(u)
    n = rf"(\d+) {s}"
    bil = lambda grup: [int(x) for x in grup]  # noqa: E731

    def cocok(pola):
        return re.fullmatch(pola, teks)

    if (m := cocok(rf"Sebuah trapesium mempunyai sepasang sisi sejajar dengan panjang {n} "
                   rf"dan {n}\. Dua sisi miringnya panjangnya {n} dan {n}\. Berapa {s} "
                   rf"keliling trapesium itu\?")):
        a, b, c, d = bil(m.groups())
        assert a < b and c != d
        return str(keliling_poligon(_trapesium_titik(a, b, c, d)))
    if (m := cocok(rf"Sebuah trapesium sama kaki mempunyai sisi sejajar {n} dan {n}\. Kedua "
                   rf"kakinya sama panjang, masing-masing {n}\. Berapa {s} keliling "
                   rf"trapesium itu\?")):
        a, b, c = bil(m.groups())
        titik = _trapesium_titik(a, b, c, c)
        return str(keliling_poligon(titik))
    if (m := cocok(rf"Sebuah trapesium sama kaki mempunyai sisi sejajar {n} dan {n}\. Kedua "
                   rf"kakinya sama panjang, masing-masing {n}, dan tingginya {n}\. Berapa {s} "
                   rf"keliling trapesium itu\?")):
        a, b, c, t = bil(m.groups())
        assert c * c == t * t + ((b - a) // 2) ** 2 and (b - a) % 2 == 0, "tinggi tak cocok"
        return str(keliling_poligon(_trapesium_titik(a, b, c, c)))
    return solver_baru_lingkaran(teks, u)


def solver_baru_lingkaran(teks: str, u: str) -> str:
    s = re.escape(u)
    n = rf"(\d+) {s}"
    pi = r"(22/7|3,14)"

    def cocok(pola):
        return re.fullmatch(pola, teks)

    if (m := cocok(rf"Sebuah lingkaran mempunyai jari-jari {n}\. Gunakan π = {pi}\. Berapa "
                   rf"{s} keliling lingkaran itu\?")):
        r = int(m.group(1))
        return _komaa(2 * _pi_dari_teks(m.group(2), r) * r)
    if (m := cocok(rf"Sebuah lingkaran mempunyai diameter {n}\. Gunakan π = {pi}\. Berapa "
                   rf"{s} keliling lingkaran itu\?")):
        d = int(m.group(1))
        nilai = _pi_dari_teks(m.group(2), d // 2 if m.group(2) == "22/7" else d)
        return _komaa(nilai * d)
    if (m := cocok(rf"Sebuah bangun berbentuk setengah lingkaran dengan jari-jari {n}\. "
                   rf"Keliling bangun itu adalah panjang lengkungannya ditambah panjang sisi "
                   rf"lurusnya \(diameter\)\. Gunakan π = {pi}\. Berapa {s} keliling bangun "
                   rf"itu\?")):
        r = int(m.group(1))
        return _komaa(_pi_dari_teks(m.group(2), r) * r + 2 * r)
    if (m := cocok(rf"Sebuah bangun berbentuk tangga memiliki (\d+) anak tangga\. Sisi "
                   rf"bawahnya datar dan sisi kirinya tegak lurus\. Dari kiri ke kanan, setiap "
                   rf"anak tangga lebarnya {n} dan lebih rendah {n} daripada anak tangga di "
                   rf"sebelah kirinya, sedangkan anak tangga paling kanan tingginya {n}\. "
                   rf"Berapa {s} keliling bangun itu\?")):
        banyak, lebar, turun, kanan = (int(x) for x in m.groups())
        return str(keliling_kisi(_sel_tangga(banyak, lebar, turun, kanan)))
    if (m := cocok(rf"Sebuah bangun berbentuk huruf U dibuat dari persegi panjang berukuran "
                   rf"{n} × {n} \(mendatar × tegak\)\. Dari tengah sisi atasnya dibuang "
                   rf"persegi panjang berukuran {n} × {n} \(mendatar × tegak\), sehingga "
                   rf"tersisa dua tiang yang sama lebar\. Berapa {s} keliling bangun itu\?")):
        return str(keliling_kisi(_sel_u(*(int(x) for x in m.groups()))))
    if (m := cocok(rf"Sebuah bangun berbentuk huruf T dibuat dari dua persegi panjang\. "
                   rf"Palang di atas berukuran {n} × {n} \(mendatar × tegak\)\. Tiang di "
                   rf"bawahnya berukuran {n} × {n} \(mendatar × tegak\), menempel rapat di "
                   rf"tengah sisi bawah palang\. Berapa {s} keliling bangun itu\?")):
        return str(keliling_kisi(_sel_t(*(int(x) for x in m.groups()))))
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(parameter: dict):
    return getattr(modul, TID)(**parameter)


def _pengecoh_angka(soal) -> set:
    benar = nilai_semantis(soal.kunci, "angka")
    hasil = set()
    for m in soal.malrule:
        n = nilai_semantis(m.jawaban, "angka")
        if n >= 0 and n != benar:
            hasil.add(n)
    return hasil


# ── kontrak modul dan domain ─────────────────────────────────────────────

def test_kontrak_modul_nama_dan_level():
    assert modul.TEMPLATE_ID == TID
    assert tuple(modul.LEVEL) == (LEVEL,)
    assert modul.TEMPLATE_ID == getattr(modul, TID).__name__


def test_domain_ukuran_per_varian_tanpa_duplikat():
    domain = _domain()
    assert len(domain) == UKURAN_DOMAIN
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"
    for varian, ukuran in UKURAN_PER_VARIAN.items():
        assert sum(1 for p in domain if p["varian"] == varian) == ukuran, varian
    for tanya, ukuran in UKURAN_TANYA.items():
        assert sum(1 for p in domain if p.get("tanya") == tanya) == ukuran, tanya
    for sub, ukuran in UKURAN_SUB_BARU.items():
        assert sum(1 for p in domain if sub in (p.get("tanya"), p.get("bentuk"))) == ukuran, sub
    assert [dict(p) for p in domain[:UKURAN_LAMA]] == [dict(p) for p in domain
                                                       if p["varian"] in VARIAN_LAMA]
    assert all(p["varian"] in VARIAN_BARU for p in domain[UKURAN_LAMA:])
    assert {p["satuan"] for p in domain} == set(SATUAN)
    assert {p["varian"] for p in domain} == set(VARIAN)


def test_domain_dict_baru_tiap_panggilan_dan_tuple_beku():
    domain = _domain()
    assert isinstance(domain, tuple)
    domain[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] != "rusak"


def test_sampel_selalu_di_dalam_domain_dan_menyentuh_semua_varian_dan_tanya():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian, tanya, satuan = set(), set(), set()
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
        tanya.add(p.get("tanya"))
        satuan.add(p["satuan"])
    assert varian == set(VARIAN) and set(TANYA) <= tanya and satuan == set(SATUAN)


def test_sampler_memilih_varian_seragam_bukan_menurut_ukuran_domain():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(1200):
        hitung[modul.parameter(random.Random(seed), LEVEL)["varian"]] += 1
    assert 90 < min(hitung.values()) and max(hitung.values()) < 180, hitung


def test_level_selain_p5_ditolak():
    for level in ("P1", "P3", "P4", "P6", "", None):
        with pytest.raises(ValueError):
            modul.domain_parameter(level)
        with pytest.raises(ValueError):
            modul.parameter(random.Random(0), level)


def test_panjang_sisi_dalam_rentang_2_sampai_30_dan_bentuk_sah():
    for p in _domain()[:UKURAN_LAMA]:
        angka = [v for k, v in p.items() if isinstance(v, int)]
        assert all(2 <= a <= 30 for a in angka), p
        if p["varian"] == "bentuk_L":
            assert p["panjang"] > p["lebar"] and p["potong"] < min(p["panjang"], p["lebar"]), p
        if p["varian"] == "dua_persegipanjang":
            w, p1, p2 = p["lebar"], p["panjang1"], p["panjang2"]
            assert p1 > p2 > w, p
        if p.get("tanya") in ("keliling_persegipanjang", "panjang_dari_keliling"):
            assert p["panjang"] > p["lebar"], p


# ── kunci ────────────────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.parameter == p
        assert soal.template_id == TID and soal.bagian == "A"
        assert KUNCI_POLOS.fullmatch(soal.kunci), soal.kunci


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.keliling_gabungan
    s = f(varian="persegi_persegipanjang", tanya="keliling_persegi", satuan="cm", sisi=12)
    assert (s.teks, s.kunci) == (
        "Sebuah persegi mempunyai panjang sisi 12 cm. Berapa cm keliling persegi itu?", "48")
    s = f(varian="persegi_persegipanjang", tanya="keliling_persegipanjang", satuan="m",
          panjang=9, lebar=4)
    assert s.kunci == "26" and "Berapa m keliling" in s.teks
    s = f(varian="persegi_persegipanjang", tanya="sisi_dari_keliling", satuan="cm", sisi=7)
    assert s.kunci == "7" and "adalah 28 cm" in s.teks
    s = f(varian="persegi_persegipanjang", tanya="panjang_dari_keliling", satuan="cm",
          panjang=9, lebar=4)
    assert s.kunci == "9" and "adalah 26 cm" in s.teks
    s = f(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=8, panjang2=5)
    assert s.kunci == "32"
    s = f(varian="bentuk_L", satuan="cm", panjang=12, lebar=8, potong=3)
    assert s.kunci == "40"
    s = f(varian="segitiga_sama_sisi_di_persegi", satuan="m", sisi=6)
    assert s.kunci == "30"


def test_keliling_bentuk_l_tidak_bergantung_pada_ukuran_potongan():
    f = modul.keliling_gabungan
    kunci = {f(varian="bentuk_L", satuan="cm", panjang=10, lebar=7, potong=s).kunci
             for s in (2, 3)}
    assert kunci == {"34"}


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        kunci = normalisasi(soal.kunci)
        jawaban = [normalisasi(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)
        assert not TERLARANG.search(" ".join(m.alasan for m in soal.malrule)), p
        assert all(ANGKA_POLOS.fullmatch(m.jawaban) for m in soal.malrule), p
        assert all(not m.jawaban.endswith("0") or "," not in m.jawaban for m in soal.malrule), p


def test_tiap_parameter_punya_cukup_pengecoh_angka_untuk_pilihan_ganda():
    kurang_dari_tiga = []
    for p in _domain():
        soal = _soal(p)
        jumlah = len(_pengecoh_angka(soal))
        assert jumlah >= 2, (p, [m.jawaban for m in soal.malrule])
        if jumlah < 3:
            kurang_dari_tiga.append(p)
    assert not kurang_dari_tiga, kurang_dari_tiga[:3]


def test_tabrakan_kunci_dengan_malrule_tetap_menyisakan_jalur_k():
    f = modul.keliling_gabungan
    # sisi 4: luas persegi 16 = keliling 16 -> K luas dibuang, K lain tetap ada.
    soal = f(varian="persegi_persegipanjang", tanya="keliling_persegi", satuan="cm", sisi=4)
    assert "16" not in {m.jawaban for m in soal.malrule}
    assert {"8", "12", "20"} <= {m.jawaban for m in soal.malrule}
    # sisi 5: segitiga di persegi, luas persegi 25 = 5s = kunci.
    soal = f(varian="segitiga_sama_sisi_di_persegi", satuan="cm", sisi=5)
    assert soal.kunci == "25" and "25" not in {m.jawaban for m in soal.malrule}
    assert any(m.kode == "K" for m in soal.malrule)


def test_malrule_sisi_menempel_dihitung_dan_potongan_salah_dibaca():
    f = modul.keliling_gabungan
    soal = f(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=8, panjang2=5)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["38"] == "K" and per["39"] == "K" and per["29"] == "H" and per["35"] == "H"
    soal = f(varian="segitiga_sama_sisi_di_persegi", satuan="cm", sisi=6)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["42"] == "K" and per["24"] == "K" and per["36"] in ("K", "H")
    soal = f(varian="bentuk_L", satuan="cm", panjang=12, lebar=8, potong=3)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["34"] == "K" and per["46"] == "K" and per["87"] == "K"
    assert per["37"] == "H" and per["43"] == "H"
    soal = f(varian="persegi_persegipanjang", tanya="keliling_persegipanjang", satuan="cm",
             panjang=9, lebar=4)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["36"] == "K" and per["13"] == "K" and per["22"] == "H" and per["30"] == "H"
    soal = f(varian="persegi_persegipanjang", tanya="sisi_dari_keliling", satuan="cm", sisi=7)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["14"] == "K" and per["28"] == "K" and per["8"] == "H" and per["6"] == "H"
    soal = f(varian="persegi_persegipanjang", tanya="panjang_dari_keliling", satuan="cm",
             panjang=9, lebar=4)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["13"] == "K" and per["22"] == "K" and per["4"] == "K" and per["10"] == "H"


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 60 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        assert soal.kunci in set(re.findall(r"\d+(?:,\d+)?", teks)), ("kunci tak ada", teks)
        assert teks.rstrip(".").endswith(f"Jadi jawabannya {soal.kunci}"), teks


def test_pembahasan_hitungan_cocok_dengan_kunci():
    for p in _domain():
        soal = _soal(p)
        hasil = re.findall(r"= (\d+(?:,\d+)?)(?: [a-z]+)?[.,]? Jadi jawabannya",
                           soal.pembahasan)
        if p.get("tanya") in ("sisi_dari_keliling", "panjang_dari_keliling"):
            continue
        assert hasil and hasil[-1] == soal.kunci, (p, soal.pembahasan)


def test_pembahasan_menjelaskan_sisi_menempel_dan_bentuk_l():
    f = modul.keliling_gabungan
    gabung = f(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=8,
               panjang2=5).pembahasan
    assert "tidak ikut menjadi keliling" in gabung and "8 + 5 = 13" in gabung
    assert "2 × (13 + 3) = 32" in gabung
    bentuk = f(varian="bentuk_L", satuan="cm", panjang=12, lebar=8, potong=3).pembahasan
    assert "sama dengan keliling persegi panjang asalnya" in bentuk
    atap = f(varian="segitiga_sama_sisi_di_persegi", satuan="cm", sisi=6).pembahasan
    assert "5 × 6 = 30" in atap


def test_teks_tanpa_gambar_satu_satuan_dan_satu_pertanyaan():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        assert teks.count("?") == 1 and teks.endswith("?")
        lawan = "m" if p["satuan"] == "cm" else "cm"
        assert not re.search(rf"\d {lawan}\b", teks), teks


# ── varian tambahan: domain, bentuk sah, kunci tangan, malrule ────────────

def _sub(p: dict) -> str:
    return p.get("tanya") or p.get("bentuk", "")


def _domain_baru() -> tuple:
    return tuple(p for p in _domain() if p["varian"] in VARIAN_BARU)


def test_varian_baru_angka_dalam_rentang_50_dan_pi_sesuai_aturan():
    for p in _domain_baru():
        angka = [v for k, v in p.items() if isinstance(v, int)]
        assert all(2 <= a <= 50 for a in angka), p
        if p["varian"] == "lingkaran":
            ukuran = p.get("jari", p.get("diameter"))
            if p["pi"] == "22/7":
                assert p.get("jari", p.get("diameter", 0) // 2) in (7, 14, 21, 28, 35), p
                assert ukuran % 7 == 0 or ukuran in (14, 28, 42), p
            else:
                assert p["pi"] == "3,14" and ukuran % 10 == 0, p
    pi_dipakai = {(p["pi"], _sub(p)) for p in _domain_baru() if p["varian"] == "lingkaran"}
    assert len(pi_dipakai) == 6, pi_dipakai


def test_sampler_menyentuh_semua_sub_bentuk_baru_dan_kedua_pi():
    sub, pi = set(), set()
    for seed in range(2000):
        p = modul.parameter(random.Random(seed), LEVEL)
        if p["varian"] in VARIAN_BARU:
            sub.add(_sub(p))
            pi.add(p.get("pi"))
    assert sub == set(UKURAN_SUB_BARU), set(UKURAN_SUB_BARU) - sub
    assert {"22/7", "3,14"} <= pi


def test_geometri_bentuk_tak_ambigu_di_domain_baru():
    for p in _domain_baru():
        sub = _sub(p)
        if sub in ("keliling_sembarang", "cari_sisi_ketiga"):
            assert p["a"] < p["b"] < p["c"] < p["a"] + p["b"], p
        if sub in ("keliling_sama_kaki", "cari_alas_sama_kaki"):
            assert p["alas"] != p["kaki"] and p["alas"] < 2 * p["kaki"], p
        if sub == "jajar_genjang":
            assert p["alas"] != p["miring"], p
        if sub == "jajar_genjang_tinggi":
            assert p["tinggi"] < p["miring"] and p["alas"] != p["miring"], p
        if sub == "layang_layang":
            assert p["pendek"] < p["panjang"], p
        if sub == "trapesium_sembarang":
            s = p["bawah"] - p["atas"]
            assert s >= 2 and p["kaki1"] < p["kaki2"], p
            assert p["kaki2"] - p["kaki1"] < s < p["kaki1"] + p["kaki2"], p
        if sub == "trapesium_sama_kaki":
            assert 0 < p["bawah"] - p["atas"] < 2 * p["kaki"], p
        if sub == "trapesium_sama_kaki_tinggi":
            setengah = (p["bawah"] - p["atas"]) // 2
            assert p["kaki"] ** 2 == p["tinggi"] ** 2 + setengah ** 2, p
        if sub == "huruf_U":
            assert (p["lebar"] - p["celah"]) % 2 == 0 and (p["lebar"] - p["celah"]) // 2 >= 2, p
            assert p["dalam"] <= p["tinggi"] - 2, p
        if sub == "huruf_T":
            assert (p["palang"] - p["tiang"]) % 2 == 0 and p["tiang"] < p["palang"], p


def test_kunci_contoh_tangan_varian_baru_teks_dan_desimal_koma():
    f = modul.keliling_gabungan
    s = f(varian="segitiga", tanya="keliling_sembarang", satuan="cm", a=4, b=6, c=9)
    assert s.kunci == "19" and "sisi-sisi sepanjang 4 cm, 6 cm, dan 9 cm" in s.teks
    s = f(varian="segitiga", tanya="keliling_sama_kaki", satuan="cm", kaki=8, alas=3)
    assert s.kunci == "19"
    s = f(varian="segitiga", tanya="keliling_sama_sisi", satuan="m", sisi=7)
    assert s.kunci == "21"
    s = f(varian="segitiga", tanya="cari_sisi_ketiga", satuan="cm", a=4, b=6, c=9)
    assert s.kunci == "9" and "adalah 19 cm" in s.teks
    s = f(varian="segitiga", tanya="cari_sisi_sama_sisi", satuan="cm", sisi=7)
    assert s.kunci == "7" and "adalah 21 cm" in s.teks
    s = f(varian="segitiga", tanya="cari_alas_sama_kaki", satuan="cm", kaki=8, alas=3)
    assert s.kunci == "3" and "adalah 19 cm" in s.teks
    gg = "jajar_genjang_belah_ketupat"
    assert f(varian=gg, tanya="jajar_genjang", satuan="cm", alas=10, miring=6).kunci == "32"
    assert f(varian=gg, tanya="jajar_genjang_tinggi", satuan="cm", alas=8, miring=5,
             tinggi=4).kunci == "26"
    assert f(varian=gg, tanya="belah_ketupat", satuan="cm", sisi=9).kunci == "36"
    assert f(varian=gg, tanya="cari_sisi_belah_ketupat", satuan="cm", sisi=9).kunci == "9"
    assert f(varian=gg, tanya="layang_layang", satuan="cm", pendek=5, panjang=9).kunci == "28"
    tr = "trapesium"
    assert f(varian=tr, tanya="trapesium_sembarang", satuan="cm", atas=5, bawah=9, kaki1=3,
             kaki2=6).kunci == "23"
    assert f(varian=tr, tanya="trapesium_sama_kaki", satuan="cm", atas=4, bawah=10,
             kaki=5).kunci == "24"
    assert f(varian=tr, tanya="trapesium_sama_kaki_tinggi", satuan="cm", atas=6, bawah=12,
             kaki=5, tinggi=4).kunci == "28"
    ling = "lingkaran"
    s = f(varian=ling, tanya="keliling_dari_jari", satuan="cm", pi="22/7", jari=14)
    assert s.kunci == "88" and "π = 22/7" in s.teks
    s = f(varian=ling, tanya="keliling_dari_jari", satuan="cm", pi="3,14", jari=10)
    assert s.kunci == "62,8" and "π = 3,14" in s.teks
    assert f(varian=ling, tanya="keliling_dari_diameter", satuan="m", pi="3,14",
             diameter=30).kunci == "94,2"
    assert f(varian=ling, tanya="keliling_dari_diameter", satuan="m", pi="22/7",
             diameter=28).kunci == "88"
    s = f(varian=ling, tanya="keliling_setengah_lingkaran", satuan="cm", pi="22/7", jari=7)
    assert s.kunci == "36" and "lengkungannya ditambah panjang sisi lurusnya" in s.teks
    s = f(varian=ling, tanya="keliling_setengah_lingkaran", satuan="cm", pi="3,14", jari=10)
    assert s.kunci == "51,4"
    assert f(varian=ling, tanya="keliling_dari_jari", satuan="cm", pi="3,14",
             jari=50).kunci == "314"
    bt = "bentuk_T_U_tangga"
    assert f(varian=bt, bentuk="tangga", satuan="cm", anak_tangga=3, lebar=2,
             tinggi=3).kunci == "30"
    assert f(varian=bt, bentuk="huruf_U", satuan="cm", lebar=10, tinggi=8, celah=4,
             dalam=5).kunci == "46"
    assert f(varian=bt, bentuk="huruf_T", satuan="cm", palang=10, tinggi_palang=3, tiang=4,
             tinggi_tiang=8).kunci == "42"


def test_keliling_u_lebih_besar_dari_pembatas_sedangkan_t_dan_tangga_sama():
    f = modul.keliling_gabungan
    bt = "bentuk_T_U_tangga"
    u = f(varian=bt, bentuk="huruf_U", satuan="cm", lebar=10, tinggi=8, celah=4, dalam=5)
    assert u.kunci == str(2 * (10 + 8) + 2 * 5)
    t = f(varian=bt, bentuk="huruf_T", satuan="cm", palang=10, tinggi_palang=3, tiang=4,
          tinggi_tiang=8)
    assert t.kunci == str(2 * (10 + 3 + 8))
    for tiang in (2, 4, 6):
        k = {f(varian=bt, bentuk="huruf_T", satuan="cm", palang=10, tinggi_palang=3,
               tiang=tiang, tinggi_tiang=8).kunci}
        assert k == {"42"}


def test_kunci_desimal_koma_tanpa_nol_buntut_dan_bukan_pecahan():
    desimal = 0
    for p in _domain_baru():
        kunci = _soal(p).kunci
        assert "/" not in kunci and "." not in kunci, (p, kunci)
        if "," in kunci:
            desimal += 1
            assert not kunci.endswith("0") and len(kunci.split(",")[1]) <= 2, kunci
            assert p["varian"] == "lingkaran" and p["pi"] == "3,14", p
    assert desimal > 0


def test_malrule_varian_baru_jalur_k_spesifik():
    f = modul.keliling_gabungan

    def peta(**parameter):
        return {m.jawaban: m.kode for m in f(**parameter).malrule}

    per = peta(varian="segitiga", tanya="keliling_sembarang", satuan="cm", a=4, b=6, c=9)
    assert per["10"] == "K" and per["15"] == "K" and per["27"] == "K" and per["20"] == "H"
    per = peta(varian="trapesium", tanya="trapesium_sembarang", satuan="cm", atas=5, bawah=9,
               kaki1=3, kaki2=6)
    assert per["14"] == "K" and per["9"] == "K" and per["17"] == "K" and per["20"] == "K"
    per = peta(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi="3,14", jari=10)
    assert per["31,4"] == "K" and per["314"] == "K" and per["60"] == "K"
    per = peta(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi="22/7", jari=7)
    assert per["22"] == "K" and per["154"] == "K" and per["43,96"] == "K"
    per = peta(varian="lingkaran", tanya="keliling_dari_diameter", satuan="cm", pi="3,14",
               diameter=10)
    assert per["62,8"] == "K" and per["15,7"] == "K" and per["78,5"] == "K"
    per = peta(varian="lingkaran", tanya="keliling_setengah_lingkaran", satuan="cm",
               pi="22/7", jari=7)
    assert per["22"] == "K" and per["44"] == "K" and per["29"] == "K" and per["77"] == "K"
    per = peta(varian="bentuk_T_U_tangga", bentuk="huruf_U", satuan="cm", lebar=10, tinggi=8,
               celah=4, dalam=5)
    assert per["36"] == "K" and per["26"] == "K" and per["50"] == "K" and per["60"] == "K"
    assert per["41"] == "H" and per["47"] == "H"
    per = peta(varian="bentuk_T_U_tangga", bentuk="huruf_T", satuan="cm", palang=10,
               tinggi_palang=3, tiang=4, tinggi_tiang=8)
    assert per["50"] == "K" and per["62"] == "K" and per["36"] == "K" and per["26"] == "K"
    assert per["43"] == "H"
    per = peta(varian="bentuk_T_U_tangga", bentuk="tangga", satuan="cm", anak_tangga=3,
               lebar=2, tinggi=3)
    assert per["36"] == "K" and per["15"] == "K" and per["18"] == "K" and per["22"] == "K"
    assert per["31"] == "H"


def test_tabrakan_malrule_varian_baru_disaring_dan_jalur_k_tersisa():
    f = modul.keliling_gabungan
    # sisi 3 segitiga sama sisi: s*s = 9 = kunci, K luas dibuang, K lain tetap ada.
    soal = f(varian="segitiga", tanya="keliling_sama_sisi", satuan="cm", sisi=3)
    assert soal.kunci == "9" and "9" not in {m.jawaban for m in soal.malrule}
    assert sum(1 for m in soal.malrule if m.kode == "K") >= 2


def test_pembahasan_varian_baru_menjelaskan_konsep_tanpa_istilah_guru():
    f = modul.keliling_gabungan
    u = f(varian="bentuk_T_U_tangga", bentuk="huruf_U", satuan="cm", lebar=10, tinggi=8,
          celah=4, dalam=5).pembahasan
    assert "dasar celah" in u and "2 × 5 = 10" in u and "= 46 cm" in u
    t = f(varian="bentuk_T_U_tangga", bentuk="huruf_T", satuan="cm", palang=10,
          tinggi_palang=3, tiang=4, tinggi_tiang=8).pembahasan
    assert "2 × (10 + 3 + 8) = 42 cm" in t
    j = f(varian="jajar_genjang_belah_ketupat", tanya="jajar_genjang_tinggi", satuan="cm",
          alas=8, miring=5, tinggi=4).pembahasan
    assert "Tinggi bukan salah satu sisi" in j
    c = f(varian="lingkaran", tanya="keliling_setengah_lingkaran", satuan="cm", pi="22/7",
          jari=7).pembahasan
    assert "22/7 × 7 = 22 cm" in c and "= 36 cm" in c


def test_varian_baru_teks_menyatakan_fakta_tegas():
    f = modul.keliling_gabungan
    teks = f(varian="jajar_genjang_belah_ketupat", tanya="layang_layang", satuan="cm",
             pendek=5, panjang=9).teks
    assert "dua sisi pendek yang sama panjang" in teks and "dua sisi panjang" in teks
    teks = f(varian="trapesium", tanya="trapesium_sama_kaki", satuan="cm", atas=4, bawah=10,
             kaki=5).teks
    assert "Kedua kakinya sama panjang" in teks
    teks = f(varian="jajar_genjang_belah_ketupat", tanya="jajar_genjang", satuan="cm", alas=10,
             miring=6).teks
    assert "Sisi-sisi yang berhadapan sama panjang" in teks
    for p in _domain_baru():
        if p["varian"] == "lingkaran":
            assert "π = " + p["pi"] in _soal(p).teks


# ── parameter di luar domain ─────────────────────────────────────────────

_P = dict(varian="persegi_persegipanjang", satuan="cm")


@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada"),
    dict(**_P, tanya="keliling_persegi"),
    dict(**_P, tanya="keliling_persegi", sisi=1),
    dict(**_P, tanya="keliling_persegi", sisi=31),
    dict(**_P, tanya="keliling_persegi", sisi=4.0),
    dict(**_P, tanya="keliling_persegi", sisi=True),
    dict(**_P, tanya="keliling_persegi", sisi="4"),
    dict(varian="persegi_persegipanjang", satuan="km", tanya="keliling_persegi", sisi=4),
    dict(varian="persegi_persegipanjang", satuan="CM", tanya="keliling_persegi", sisi=4),
    dict(varian="persegi_persegipanjang", tanya="keliling_persegi", sisi=4),
    dict(**_P, tanya="luas_persegi", sisi=4),
    dict(**_P, tanya="keliling_persegi", sisi=4, lebar=3),
    dict(**_P, tanya="keliling_persegipanjang", panjang=5, lebar=5),
    dict(**_P, tanya="keliling_persegipanjang", panjang=4, lebar=5),
    dict(**_P, tanya="keliling_persegipanjang", panjang=16, lebar=5),
    dict(**_P, tanya="keliling_persegipanjang", panjang=9, lebar=1),
    dict(**_P, tanya="sisi_dari_keliling", sisi=31),
    dict(**_P, tanya="panjang_dari_keliling", panjang=5, lebar=5),
    dict(**_P, tanya="panjang_dari_keliling", panjang=17, lebar=3),
    dict(**_P, tanya="panjang_dari_keliling", panjang=12, lebar=9),
    dict(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=5, panjang2=8),
    dict(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=8, panjang2=8),
    dict(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=8, panjang2=3),
    dict(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=12, panjang2=5),
    dict(varian="dua_persegipanjang", satuan="cm", lebar=7, panjang1=11, panjang2=9),
    dict(varian="dua_persegipanjang", satuan="cm", lebar=3, panjang1=8),
    dict(varian="bentuk_L", satuan="cm", panjang=12, lebar=8, potong=8),
    dict(varian="bentuk_L", satuan="cm", panjang=12, lebar=8, potong=4),
    dict(varian="bentuk_L", satuan="cm", panjang=12, lebar=8, potong=1),
    dict(varian="bentuk_L", satuan="cm", panjang=8, lebar=12, potong=3),
    dict(varian="bentuk_L", satuan="cm", panjang=8, lebar=8, potong=3),
    dict(varian="bentuk_L", satuan="cm", panjang=15, lebar=8, potong=3),
    dict(varian="bentuk_L", satuan="cm", panjang=12, lebar=3, potong=2),
    dict(varian="segitiga_sama_sisi_di_persegi", satuan="cm", sisi=1),
    dict(varian="segitiga_sama_sisi_di_persegi", satuan="cm", sisi=31),
    dict(varian="segitiga_sama_sisi_di_persegi", satuan="cm", sisi=5, panjang=5),
    dict(varian="segitiga_sama_sisi_di_persegi", satuan="cm"),
    dict(varian="segitiga", tanya="keliling_sembarang", satuan="cm", a=3, b=4, c=8),
    dict(varian="segitiga", tanya="keliling_sembarang", satuan="cm", a=3, b=4, c=7),
    dict(varian="segitiga", tanya="keliling_sembarang", satuan="cm", a=4, b=4, c=5),
    dict(varian="segitiga", tanya="keliling_sembarang", satuan="cm", a=5, b=4, c=6),
    dict(varian="segitiga", tanya="keliling_sama_kaki", satuan="cm", kaki=5, alas=5),
    dict(varian="segitiga", tanya="keliling_sama_kaki", satuan="cm", kaki=3, alas=6),
    dict(varian="segitiga", tanya="keliling_sama_sisi", satuan="cm", sisi=31),
    dict(varian="segitiga", tanya="cari_sisi_sama_sisi", satuan="cm", sisi=1),
    dict(varian="segitiga", tanya="cari_alas_sama_kaki", satuan="cm", kaki=4, alas=8),
    dict(varian="segitiga", tanya="keliling_sama_sisi", satuan="cm", sisi=4.0),
    dict(varian="segitiga", tanya="keliling_segitiga_siku", satuan="cm", sisi=4),
    dict(varian="jajar_genjang_belah_ketupat", tanya="jajar_genjang", satuan="cm", alas=5,
         miring=5),
    dict(varian="jajar_genjang_belah_ketupat", tanya="jajar_genjang", satuan="cm", alas=13,
         miring=5),
    dict(varian="jajar_genjang_belah_ketupat", tanya="jajar_genjang_tinggi", satuan="cm",
         alas=8, miring=5, tinggi=5),
    dict(varian="jajar_genjang_belah_ketupat", tanya="jajar_genjang_tinggi", satuan="cm",
         alas=8, miring=5, tinggi=6),
    dict(varian="jajar_genjang_belah_ketupat", tanya="layang_layang", satuan="cm", pendek=9,
         panjang=5),
    dict(varian="jajar_genjang_belah_ketupat", tanya="layang_layang", satuan="cm", pendek=5,
         panjang=5),
    dict(varian="jajar_genjang_belah_ketupat", tanya="belah_ketupat", satuan="cm", sisi=1),
    dict(varian="trapesium", tanya="trapesium_sembarang", satuan="cm", atas=5, bawah=9,
         kaki1=6, kaki2=3),
    dict(varian="trapesium", tanya="trapesium_sembarang", satuan="cm", atas=5, bawah=9,
         kaki1=3, kaki2=3),
    dict(varian="trapesium", tanya="trapesium_sembarang", satuan="cm", atas=5, bawah=9,
         kaki1=3, kaki2=8),
    dict(varian="trapesium", tanya="trapesium_sembarang", satuan="cm", atas=5, bawah=6,
         kaki1=3, kaki2=4),
    dict(varian="trapesium", tanya="trapesium_sama_kaki", satuan="cm", atas=4, bawah=10,
         kaki=3),
    dict(varian="trapesium", tanya="trapesium_sama_kaki", satuan="cm", atas=4, bawah=9,
         kaki=5),
    dict(varian="trapesium", tanya="trapesium_sama_kaki_tinggi", satuan="cm", atas=6,
         bawah=12, kaki=5, tinggi=5),
    dict(varian="trapesium", tanya="trapesium_sama_kaki_tinggi", satuan="cm", atas=6,
         bawah=13, kaki=5, tinggi=4),
    dict(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi="22/7", jari=10),
    dict(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi="22/7", jari=42),
    dict(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi="3,14", jari=7),
    dict(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi="3,14", jari=60),
    dict(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi="3.14", jari=10),
    dict(varian="lingkaran", tanya="keliling_dari_jari", satuan="cm", pi=3.14, jari=10),
    dict(varian="lingkaran", tanya="keliling_dari_diameter", satuan="cm", pi="22/7",
         diameter=10),
    dict(varian="lingkaran", tanya="keliling_dari_diameter", satuan="cm", pi="3,14",
         diameter=15),
    dict(varian="lingkaran", tanya="keliling_dari_diameter", satuan="cm", pi="3,14", jari=10),
    dict(varian="lingkaran", tanya="keliling_setengah_lingkaran", satuan="cm", pi="22/7",
         jari=8),
    dict(varian="lingkaran", tanya="keliling_setengah_lingkaran", satuan="cm", pi="22/7",
         diameter=14),
    dict(varian="bentuk_T_U_tangga", bentuk="tangga", satuan="cm", anak_tangga=1, lebar=2,
         tinggi=3),
    dict(varian="bentuk_T_U_tangga", bentuk="tangga", satuan="cm", anak_tangga=5, lebar=2,
         tinggi=3),
    dict(varian="bentuk_T_U_tangga", bentuk="huruf_U", satuan="cm", lebar=10, tinggi=8, celah=3,
         dalam=4),
    dict(varian="bentuk_T_U_tangga", bentuk="huruf_U", satuan="cm", lebar=8, tinggi=8, celah=6,
         dalam=4),
    dict(varian="bentuk_T_U_tangga", bentuk="huruf_U", satuan="cm", lebar=10, tinggi=8, celah=4,
         dalam=7),
    dict(varian="bentuk_T_U_tangga", bentuk="huruf_U", satuan="cm", lebar=10, tinggi=8, celah=4,
         dalam=8),
    dict(varian="bentuk_T_U_tangga", bentuk="huruf_T", satuan="cm", palang=10, tinggi_palang=3,
         tiang=3, tinggi_tiang=8),
    dict(varian="bentuk_T_U_tangga", bentuk="huruf_T", satuan="cm", palang=10, tinggi_palang=3,
         tiang=10, tinggi_tiang=8),
    dict(varian="bentuk_T_U_tangga", bentuk="huruf_T", satuan="cm", palang=10, tinggi_palang=3,
         tiang=4),
    dict(varian="bentuk_T_U_tangga", bentuk="berlian", satuan="cm"),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.keliling_gabungan(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_keliling_gabungan as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P5")
    s = m.keliling_gabungan(**p)
    hasil.append([p, s.teks, s.kunci, s.pembahasan,
                  [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    kode = _KODE % {"akar": str(AKAR_MESIN), "dir": str(DIR_MODUL)}
    hasil = subprocess.run([sys.executable, "-c", kode], env=env,
                           capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == 150
