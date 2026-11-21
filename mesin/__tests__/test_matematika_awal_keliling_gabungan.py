"""Matematika Awal, jenis keliling_gabungan (P5): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang hanya
membaca TEKS soal dan menghitung keliling dari garis tepi (bangun gabungan digambar di
kisi satuan atau dihitung dari sisi luarnya), bukan memakai rumus modul. Bangun tak
ambigu: dua persegi panjang bersisi lebar sama disambung penuh pada sisi lebarnya; pojok
yang dipotong selalu persegi kecil dengan sisi < sisi terpendek.
"""
from __future__ import annotations

import json
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
VARIAN = ("persegi_persegipanjang", "dua_persegipanjang", "bentuk_L",
          "segitiga_sama_sisi_di_persegi")
TANYA = ("keliling_persegi", "keliling_persegipanjang", "sisi_dari_keliling",
         "panjang_dari_keliling")
UKURAN_TANYA = {"keliling_persegi": 58, "keliling_persegipanjang": 182,
                "sisi_dari_keliling": 58, "panjang_dari_keliling": 154}
UKURAN_PER_VARIAN = {"persegi_persegipanjang": 452, "dua_persegipanjang": 220,
                     "bentuk_L": 216, "segitiga_sama_sisi_di_persegi": 58}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
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
    assert 230 < min(hitung.values()) and max(hitung.values()) < 370, hitung


def test_level_selain_p5_ditolak():
    for level in ("P1", "P3", "P4", "P6", "", None):
        with pytest.raises(ValueError):
            modul.domain_parameter(level)
        with pytest.raises(ValueError):
            modul.parameter(random.Random(0), level)


def test_panjang_sisi_dalam_rentang_2_sampai_30_dan_bentuk_sah():
    for p in _domain():
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
        assert re.fullmatch(r"[1-9]\d*", soal.kunci), soal.kunci


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
        assert all(re.fullmatch(r"\d+", m.jawaban) for m in soal.malrule), p


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
        assert soal.kunci in set(re.findall(r"\d+", teks)), ("kunci tak ada", teks)
        assert teks.rstrip(".").endswith(f"Jadi jawabannya {soal.kunci}"), teks


def test_pembahasan_hitungan_cocok_dengan_kunci():
    for p in _domain():
        soal = _soal(p)
        hasil = re.findall(r"= (\d+)(?: [a-z]+)?[.,]? Jadi jawabannya", soal.pembahasan)
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
