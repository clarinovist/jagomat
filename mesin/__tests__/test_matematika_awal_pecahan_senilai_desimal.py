"""Matematika Awal, jenis pecahan_senilai_desimal (P4): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang hanya
membaca TEKS soal dan memakai aritmetika pecahan/desimal sendiri (bukan fungsi modul).
Malrule hanya HIPOTESIS kesalahan umum; yang dijaga: bukan kunci (menurut teks maupun
nilai, kecuali H "belum paling sederhana"), tidak kembar, selalu ada jalur K, dan cukup
pengecoh berbeda nilai untuk pilihan ganda.
"""
from __future__ import annotations

from decimal import Decimal
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

import awal_pecahan_senilai_desimal as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "pecahan_senilai_desimal"
LEVEL = "P4"
SEED = range(200)
VARIAN = ("bagian_dari", "senilai_isi", "senilai_sederhana", "ke_desimal", "ke_persen",
          "desimal_ke_pecahan")
UKURAN_PER_VARIAN = {"bagian_dari": 120, "senilai_isi": 38, "senilai_sederhana": 38,
                     "ke_desimal": 35, "ke_persen": 27, "desimal_ke_pecahan": 17}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # tetap benar untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)
SENILAI_BOLEH = {TID + ".belum_paling_sederhana"}  # H yang sengaja bernilai sama dengan kunci


def _nilai(teks: str) -> Fraction:
    return Fraction(teks.replace(",", "."))


def _desimal_tes(n: int, d: int) -> str:
    """Desimal koma ringkas dari n/d memakai Decimal (fakta tes, bukan fungsi modul)."""
    teks = str(Decimal(n) / Decimal(d))
    assert "E" not in teks and not teks.endswith("0"), teks
    return teks.replace(".", ",")


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; tidak memakai parameter atau konstanta modul."""
    cocok = re.fullmatch(
        r"(\w+) memiliki (\d+) (\w+)\. 1/(\d+) dari \3 itu diberikan kepada (\w+)\. "
        r"Banyak \3 yang diberikan ada \.\.\. (\w+)\.", teks)
    if cocok:
        total, d = int(cocok.group(2)), int(cocok.group(4))
        assert total % d == 0, ("jumlah harus habis dibagi penyebut", teks)
        assert cocok.group(1) != cocok.group(5), teks
        return str(total // d)
    cocok = re.fullmatch(r"(\d+)/(\d+) = \.\.\./(\d+)", teks)
    if cocok:
        a, b, baru = map(int, cocok.groups())
        assert baru % b == 0 and baru > b and gcd_ok(a, b), ("senilai tak bulat", teks)
        return str(a * (baru // b))
    cocok = re.fullmatch(
        r"Pecahan senilai dengan (\d+)/(\d+) yang paling sederhana adalah \.\.\.", teks)
    if cocok:
        atas, bawah = int(cocok.group(1)), int(cocok.group(2))
        g = math.gcd(atas, bawah)
        assert g > 1 and atas < bawah, ("harus belum sederhana dan wajar", teks)
        return f"{atas // g}/{bawah // g}"
    cocok = re.fullmatch(r"Pecahan (\d+)/(\d+) jika ditulis sebagai desimal adalah \.\.\.", teks)
    if cocok:
        n, d = int(cocok.group(1)), int(cocok.group(2))
        assert n < d and d in (2, 4, 5, 10, 20, 25, 100), teks
        return _desimal_tes(n, d)
    cocok = re.fullmatch(r"(\d+)/(\d+) = \.\.\. %", teks)
    if cocok:
        n, d = int(cocok.group(1)), int(cocok.group(2))
        assert n < d and d in (2, 4, 5, 10, 20, 25), teks
        assert (n * 100) % d == 0, teks
        return str(n * 100 // d)
    cocok = re.fullmatch(
        r"Desimal (0,\d+) jika ditulis sebagai pecahan paling sederhana adalah \.\.\.", teks)
    if cocok:
        pecahan = Fraction(Decimal(cocok.group(1).replace(",", ".")))
        return f"{pecahan.numerator}/{pecahan.denominator}"
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


def gcd_ok(a: int, b: int) -> bool:
    return math.gcd(a, b) == 1 and a < b


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(parameter: dict):
    return getattr(modul, TID)(**parameter)


def _pengecoh_nilai(soal) -> set:
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
    assert callable(getattr(modul, TID))
    assert modul.TEMPLATE_ID == getattr(modul, TID).__name__


def test_domain_ukuran_per_varian_tanpa_duplikat():
    domain = _domain()
    assert len(domain) == UKURAN_DOMAIN
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"
    for varian, ukuran in UKURAN_PER_VARIAN.items():
        assert sum(1 for p in domain if p["varian"] == varian) == ukuran, varian
    assert {p["varian"] for p in domain} == set(VARIAN)


def test_domain_dict_baru_tiap_panggilan_dan_tuple_beku():
    domain = _domain()
    assert isinstance(domain, tuple)
    domain[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] != "rusak"


def test_domain_batas_rentang_kelas_4():
    for p in _domain():
        if p["varian"] == "bagian_dari":
            assert p["d"] in (2, 3, 4, 5, 10) and 2 <= p["k"] <= 9 and 0 <= p["benda"] <= 2
        if p["varian"] in ("senilai_isi", "senilai_sederhana"):
            assert math.gcd(p["a"], p["b"]) == 1 and p["a"] < p["b"]
            assert 2 <= p["f"] <= 5 and p["b"] * p["f"] <= 24
        if p["varian"] in ("ke_desimal", "ke_persen"):
            assert 1 <= p["n"] < p["d"]
            assert p["d"] in ((2, 4, 5, 10, 20, 25, 100) if p["varian"] == "ke_desimal"
                              else (2, 4, 5, 10, 20, 25))
        if p["varian"] == "desimal_ke_pecahan":
            assert 1 <= p["perseratus"] <= 99


def test_sampel_selalu_di_dalam_domain_dan_menyentuh_semua_varian():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian = set()
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
    assert varian == set(VARIAN)


def test_sampler_murni_dari_rng_seed_sama_hasil_sama():
    a = [modul.parameter(random.Random(s), LEVEL) for s in SEED]
    b = [modul.parameter(random.Random(s), LEVEL) for s in SEED]
    assert a == b
    assert len({json.dumps(p, sort_keys=True) for p in a}) > 60


def test_level_selain_p4_ditolak():
    for level in ("P1", "P2", "P3", "P5", "P6", "", None):
        with pytest.raises(ValueError):
            modul.domain_parameter(level)
        with pytest.raises(ValueError):
            modul.parameter(random.Random(0), level)


# ── kunci ────────────────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.parameter == p
        assert soal.template_id == TID and soal.bagian == "A"
        assert re.fullmatch(r"\d+|\d+/\d+|0,\d*[1-9]", soal.kunci), ("bentuk kunci", soal.kunci)


def test_kunci_pecahan_paling_sederhana_dan_desimal_tanpa_nol_ekor():
    for p in _domain():
        soal = _soal(p)
        if "/" in soal.kunci:
            a, b = map(int, soal.kunci.split("/"))
            assert math.gcd(a, b) == 1 and b > 1, (p, soal.kunci)
        if "," in soal.kunci:
            assert not soal.kunci.endswith("0") and soal.kunci.startswith("0,"), soal.kunci


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.pecahan_senilai_desimal
    bagian = f(varian="bagian_dari", d=4, k=5, benda=0)
    assert bagian.teks == ("Rina memiliki 20 kelereng. 1/4 dari kelereng itu diberikan kepada "
                           "Budi. Banyak kelereng yang diberikan ada ... butir.")
    assert bagian.kunci == "5"
    assert f(varian="senilai_isi", a=1, b=2, f=3).teks == "1/2 = .../6"
    assert f(varian="senilai_isi", a=1, b=2, f=3).kunci == "3"
    sed = f(varian="senilai_sederhana", a=1, b=2, f=2)
    assert sed.teks == "Pecahan senilai dengan 2/4 yang paling sederhana adalah ..."
    assert sed.kunci == "1/2"
    assert f(varian="ke_desimal", n=1, d=4).kunci == "0,25"
    assert f(varian="ke_desimal", n=1, d=2).kunci == "0,5"
    assert f(varian="ke_desimal", n=7, d=100).kunci == "0,07"
    assert f(varian="ke_desimal", n=3, d=20).kunci == "0,15"
    assert f(varian="ke_persen", n=3, d=4).teks == "3/4 = ... %"
    assert f(varian="ke_persen", n=3, d=4).kunci == "75"
    assert f(varian="ke_persen", n=7, d=20).kunci == "35"
    dp = f(varian="desimal_ke_pecahan", perseratus=25)
    assert dp.teks == ("Desimal 0,25 jika ditulis sebagai pecahan paling sederhana adalah ...")
    assert dp.kunci == "1/4"
    assert f(varian="desimal_ke_pecahan", perseratus=5).kunci == "1/20"
    assert f(varian="desimal_ke_pecahan", perseratus=75).kunci == "3/4"


def test_kunci_desimal_dinormalisasi_koma_menjadi_titik_seperti_template_lain():
    assert normalisasi(modul.pecahan_senilai_desimal(
        varian="ke_desimal", n=3, d=4).kunci) == "0.75"
    assert normalisasi("0,75") == normalisasi("0,75 ")


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


def test_malrule_bernilai_beda_dari_kunci_kecuali_belum_sederhana():
    for p in _domain():
        soal = _soal(p)
        benar = _nilai(soal.kunci)
        for m in soal.malrule:
            if m.id in SENILAI_BOLEH:
                assert m.kode == "H" and _nilai(m.jawaban) == benar, (p, m)
                continue
            assert _nilai(m.jawaban) != benar, (p, m.id, m.jawaban, soal.kunci)
        k = [m for m in soal.malrule if m.kode == "K"]
        assert k and all(m.id not in SENILAI_BOLEH for m in k)


def test_tiap_parameter_punya_cukup_pengecoh_berbeda_nilai_untuk_pilihan_ganda():
    for p in _domain():
        soal = _soal(p)
        assert len(_pengecoh_nilai(soal)) >= 2, (p, [m.jawaban for m in soal.malrule])


def test_malrule_bernilai_benar_untuk_hipotesisnya():
    f = modul.pecahan_senilai_desimal
    bagian = {m.id.split(".")[-1]: (m.jawaban, m.kode)
              for m in f(varian="bagian_dari", d=4, k=5, benda=0).malrule}
    assert bagian["penyebut_dikali"] == ("80", "K")
    assert bagian["pembilang_saja"] == ("20", "K")
    assert bagian["dikurangi_penyebut"] == ("16", "K")
    assert bagian["jawab_sisa"] == ("15", "H")
    isi = {m.id.split(".")[-1]: m.jawaban
           for m in f(varian="senilai_isi", a=2, b=3, f=4).malrule}
    assert isi == {"pembilang_ditambah": "11", "pembilang_tetap": "2",
                   "penyebut_jadi_pembilang": "12"}
    sed = {m.id.split(".")[-1]: m.jawaban
           for m in f(varian="senilai_sederhana", a=2, b=3, f=3).malrule}
    assert sed == {"hanya_pembilang_dibagi": "2/9", "hanya_penyebut_dibagi": "6/3",
                   "pembilang_penyebut_tertukar": "3/2"}
    des = {m.id.split(".")[-1]: m.jawaban
           for m in f(varian="ke_desimal", n=1, d=4).malrule}
    assert des == {"titik_geser_kanan": "2,5", "titik_geser_kiri": "0,025",
                   "pembilang_di_belakang_koma": "0,1", "pembilang_penyebut_tertukar": "4"}
    per = {m.id.split(".")[-1]: (m.jawaban, m.kode)
           for m in f(varian="ke_persen", n=3, d=4).malrule}
    # jawab_sisa (25) kembar dengan pembilang_diabaikan (25) pada 3/4, jadi disaring.
    assert per == {"persen_sama_pembilang": ("3", "K"), "pembilang_kali_seratus": ("300", "K"),
                   "pembilang_diabaikan": ("25", "K"), "penyebut_jadi_persen": ("4", "K")}
    sisa = {m.id.split(".")[-1]: (m.jawaban, m.kode)
            for m in f(varian="ke_persen", n=1, d=4).malrule}
    assert sisa["jawab_sisa"] == ("75", "H")
    dp = {m.id.split(".")[-1]: (m.jawaban, m.kode)
          for m in f(varian="desimal_ke_pecahan", perseratus=25).malrule}
    assert dp == {"pembilang_penyebut_tertukar": ("4/1", "K"),
                  "angka_koma_jadi_penyebut": ("1/25", "K"),
                  "angka_koma_per_sepuluh": ("25/10", "K"),
                  "belum_paling_sederhana": ("25/100", "H")}


def test_titik_desimal_salah_tempat_ada_di_setiap_soal_desimal():
    for p in _domain():
        if p["varian"] != "ke_desimal":
            continue
        soal = _soal(p)
        kunci = _nilai(soal.kunci)
        nilai_k = {_nilai(m.jawaban) for m in soal.malrule if m.kode == "K"}
        assert kunci * 10 in nilai_k and kunci / 10 in nilai_k, (p, soal.malrule)


def test_persen_sama_pembilang_dan_pembilang_dikali_hanya_jalur_k():
    for p in _domain():
        if p["varian"] != "ke_persen":
            continue
        soal = _soal(p)
        k = {m.id.split(".")[-1] for m in soal.malrule if m.kode == "K"}
        assert "persen_sama_pembilang" in k, p  # d < 100, jadi pembilang tak pernah sama dengan kunci
        assert "pembilang_kali_seratus" in k, p


def test_belum_sederhana_hanya_h_dan_bernilai_sama_dengan_kunci():
    ada = 0
    for p in _domain():
        if p["varian"] != "desimal_ke_pecahan":
            continue
        soal = _soal(p)
        for m in soal.malrule:
            if m.id in SENILAI_BOLEH:
                ada += 1
                assert m.kode == "H" and _nilai(m.jawaban) == _nilai(soal.kunci)
                assert normalisasi(m.jawaban) != normalisasi(soal.kunci)
    assert ada >= 10


# ── pembahasan dan teks ──────────────────────────────────────────────────

def _kunci_muncul(kunci: str, teks: str) -> bool:
    awal = r"(?<![\d,/.])"
    akhir = r"(?![\d/])" if "," in kunci or "/" in kunci else r"(?![\d,])"
    return re.search(awal + re.escape(kunci) + akhir, teks) is not None


def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 40 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        assert _kunci_muncul(soal.kunci, teks), ("kunci tidak muncul di pembahasan", p, teks)


def test_pembahasan_menyebut_langkah_yang_benar():
    f = modul.pecahan_senilai_desimal
    assert "20 ÷ 4 = 5" in f(varian="bagian_dari", d=4, k=5, benda=0).pembahasan
    assert "2 × 4 = 8" in f(varian="senilai_isi", a=2, b=3, f=4).pembahasan
    assert "6 ÷ 3 = 2" in f(varian="senilai_sederhana", a=2, b=3, f=3).pembahasan
    assert "75/100" in f(varian="ke_desimal", n=3, d=4).pembahasan
    assert "0,50, ditulis 0,5" in f(varian="ke_desimal", n=1, d=2).pembahasan
    assert "75/100 = 75%" in f(varian="ke_persen", n=3, d=4).pembahasan
    assert "25/100" in f(varian="desimal_ke_pecahan", perseratus=25).pembahasan


def test_teks_tanpa_gambar_satu_pertanyaan_dan_nama_sintetis():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        assert teks.count("...") == 1, teks
        assert "None" not in teks and "{" not in teks


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", d=4, k=5, benda=0),
    dict(varian="bagian_dari"),
    dict(varian="bagian_dari", d=4, k=5),
    dict(varian="bagian_dari", d=6, k=5, benda=0),
    dict(varian="bagian_dari", d=4, k=1, benda=0),
    dict(varian="bagian_dari", d=4, k=10, benda=0),
    dict(varian="bagian_dari", d=4, k=5, benda=3),
    dict(varian="bagian_dari", d=4, k=5, benda=-1),
    dict(varian="bagian_dari", d=4, k=True, benda=0),
    dict(varian="bagian_dari", d=4, k="5", benda=0),
    dict(varian="bagian_dari", d=4, k=5.0, benda=0),
    dict(varian="bagian_dari", d=4, k=5, benda=0, n=1),
    dict(varian="senilai_isi", a=2, b=4, f=2),
    dict(varian="senilai_isi", a=1, b=2, f=1),
    dict(varian="senilai_isi", a=1, b=2, f=6),
    dict(varian="senilai_isi", a=1, b=6, f=5),
    dict(varian="senilai_isi", a=3, b=2, f=2),
    dict(varian="senilai_sederhana", a=1, b=2),
    dict(varian="senilai_sederhana", a=2, b=2, f=2),
    dict(varian="senilai_sederhana", a=5, b=5, f=3),
    dict(varian="senilai_sederhana", a=1, b=7, f=2),
    dict(varian="ke_desimal", n=1, d=3),
    dict(varian="ke_desimal", n=2, d=4),
    dict(varian="ke_desimal", n=1, d=1),
    dict(varian="ke_desimal", n=0, d=4),
    dict(varian="ke_desimal", n=4, d=4),
    dict(varian="ke_desimal", n=1),
    dict(varian="ke_persen", n=1, d=100),
    dict(varian="ke_persen", n=1, d=3),
    dict(varian="ke_persen", n=2, d=4),
    dict(varian="ke_persen", n=5, d=4),
    dict(varian="desimal_ke_pecahan", perseratus=0),
    dict(varian="desimal_ke_pecahan", perseratus=100),
    dict(varian="desimal_ke_pecahan", perseratus=10),
    dict(varian="desimal_ke_pecahan", perseratus=33),
    dict(varian="desimal_ke_pecahan", perseratus=25.0),
    dict(varian="desimal_ke_pecahan"),
    dict(varian=["ke_persen"], n=3, d=4),
    dict(varian=None, n=3, d=4),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.pecahan_senilai_desimal(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_pecahan_senilai_desimal as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P4")
    s = m.pecahan_senilai_desimal(**p)
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
