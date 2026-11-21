"""Matematika Awal, jenis pecahan_bilangan_asli_desimal (P6): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (regex), tanpa memakai
parameter atau tabel dari modul jenis; desimal dihitung dengan pembagian bersusun bilangan
bulat, bukan dengan fungsi format modul. Malrule hanya HIPOTESIS kesalahan umum yang ditinjau
guru; yang dijaga di sini: bukan kunci (menurut NILAI), tidak kembar, selalu ada jalur K di
SETIAP parameter sah, dan cukup banyak pengecoh berbeda nilai untuk pilihan ganda. Tes ini
sengaja tidak bergantung pada registrasi topik: ia memanggil modul jenis langsung.

Perluasan v2 menambah enam varian di belakang (bagian "perluasan v2" di bawah). Tes untuk enam
varian lama tidak diubah selain: (1) tes yang menyapu `_domain()` penuh dan hanya berlaku untuk
varian lama kini menyapu `_domain_lama()`, (2) ambang minimal hitungan sampler per varian turun
dari 15 ke 8 karena undian kini dibagi dua belas varian, (3) `solver_dari_teks` lebih dulu
memeriksa varian v2. Hash identitas domain lama dikunci di tes v2.
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

import awal_pecahan_bilangan_asli_desimal as modul
import diagnosis
from multiple_choice import nilai_semantis
from templates import Soal

TID = "pecahan_bilangan_asli_desimal"
LEVEL = "P6"
SEED = range(200)
VARIAN = ("kali_asli", "bagi_asli", "asli_kali", "ke_desimal", "desimal_ke_pecahan", "cerita")
UKURAN_VARIAN = {"kali_asli": 141, "bagi_asli": 168, "asli_kali": 141, "ke_desimal": 43,
                 "desimal_ke_pecahan": 39, "cerita": 618}
AKAR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"\b(malrule|diagnosis|kode|template|kunci|hipotesis|guru)\b", re.I)
AKHIRAN = r" \(tulis hasilnya dalam bentuk paling sederhana\)"
# empat pengecoh murni malrule di seluruh domain; kebijakan PG bawaan (empat-v1) butuh 3.
PENGECOH_PERLU = 3
MIN_SAMPLER = 8  # dua belas varian seragam: rata-rata 16,7 dari 200 seed


# ── solver terpisah: hanya membaca teks ──────────────────────────────────

def _tulis_pecahan(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def _desimal_bersusun(pembilang: int, penyebut: int) -> str:
    """Pembagian bersusun: tulis desimal berhenti dengan koma, tanpa nol di belakang."""
    bulat, sisa = divmod(pembilang, penyebut)
    angka = ""
    for _ in range(8):
        if sisa == 0:
            break
        sisa *= 10
        angka += str(sisa // penyebut)
        sisa %= penyebut
    assert sisa == 0, "desimal tidak berhenti"
    return f"{bulat},{angka}" if angka else str(bulat)


def _solver_kali_asli(teks: str) -> str:
    cocok = re.fullmatch(r"Hitung: (\d+)/(\d+) × (\d+) = \.\.\." + AKHIRAN, teks)
    assert cocok, teks
    a, b, n = map(int, cocok.groups())
    return _tulis_pecahan(Fraction(a * n, b))


def _solver_bagi_asli(teks: str) -> str:
    cocok = re.fullmatch(r"Hitung: (\d+)/(\d+) ÷ (\d+) = \.\.\." + AKHIRAN, teks)
    assert cocok, teks
    a, b, n = map(int, cocok.groups())
    return _tulis_pecahan(Fraction(a, b * n))


def _solver_asli_kali(teks: str) -> str:
    cocok = re.fullmatch(r"Hitung: (\d+) × (\d+)/(\d+) = \.\.\." + AKHIRAN, teks)
    assert cocok, teks
    n, a, b = map(int, cocok.groups())
    return _tulis_pecahan(Fraction(n * a, b))


def _solver_ke_desimal(teks: str) -> str:
    cocok = re.fullmatch(r"Ubah pecahan (\d+)/(\d+) menjadi bilangan desimal\. "
                         r"Jawabannya \.\.\. \(tulis dengan tanda koma\)", teks)
    assert cocok, teks
    a, b = map(int, cocok.groups())
    return _desimal_bersusun(a, b)


def _solver_desimal_ke_pecahan(teks: str) -> str:
    cocok = re.fullmatch(r"Ubah bilangan desimal (\d+),(\d+) menjadi pecahan paling sederhana\. "
                         r"Jawabannya \.\.\. \(tulis dengan garis miring, contoh 2/3\)", teks)
    assert cocok, teks
    belakang = cocok.group(2)
    assert cocok.group(1) == "0" and not belakang.endswith("0"), teks
    pembilang, penyebut = int(belakang), 10 ** len(belakang)
    g = math.gcd(pembilang, penyebut)
    return f"{pembilang // g}/{penyebut // g}"


# (potongan kalimat khas, operasi, regex pengambil n)
_CIRI_CERITA = (
    ("dipotong menjadi", "bagi", r"menjadi (\d+) bagian sama panjang"),
    ("dibagi sama banyak", "bagi", r"ke dalam (\d+) kantong"),
    ("Setiap hari", "kali", r"dalam (\d+) hari"),
    ("Satu bungkus kue", "kali", r"berat (\d+) bungkus kue"),
)


def _solver_cerita(teks: str) -> str:
    cocok_awal = re.fullmatch(r"(.+\?)" + AKHIRAN, teks)
    assert cocok_awal, teks
    soal = cocok_awal.group(1)
    pecahan = re.findall(r"(\d+)/(\d+)", soal)
    assert len(pecahan) == 1, teks
    a, b = map(int, pecahan[0])
    ditemukan = [(op, pola) for ciri, op, pola in _CIRI_CERITA if ciri in soal]
    assert len(ditemukan) == 1, teks
    operasi, pola = ditemukan[0]
    n = int(re.search(pola, soal).group(1))
    return _tulis_pecahan(Fraction(a * n, b) if operasi == "kali" else Fraction(a, b * n))


def solver_dari_teks(teks: str) -> str:
    baru = _solver_v2(teks)
    if baru is not None:
        return baru
    if teks.startswith("Hitung: "):
        if " ÷ " in teks:
            return _solver_bagi_asli(teks)
        if re.match(r"Hitung: \d+ × ", teks):
            return _solver_asli_kali(teks)
        return _solver_kali_asli(teks)
    if teks.startswith("Ubah pecahan"):
        return _solver_ke_desimal(teks)
    if teks.startswith("Ubah bilangan desimal"):
        return _solver_desimal_ke_pecahan(teks)
    return _solver_cerita(teks)


# ── pembantu ─────────────────────────────────────────────────────────────

def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(p: dict) -> Soal:
    return modul.pecahan_bilangan_asli_desimal(**p)


def _nilai(teks: str):
    return nilai_semantis(teks, "angka")


def _kanon(p: dict) -> str:
    return json.dumps(p, sort_keys=True)


def _varian(varian: str) -> list:
    return [p for p in _domain() if p["varian"] == varian]


def _domain_lama() -> list:
    return [p for p in _domain() if p["varian"] in VARIAN]


# ── domain dan sampler ───────────────────────────────────────────────────

def test_ukuran_domain_per_varian_tidak_kembar_dan_cukup():
    domain = _domain()
    assert len({_kanon(p) for p in domain}) == len(domain), "domain berisi duplikat"
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_VARIAN
    assert all(n >= 39 for n in per_varian.values())


def test_domain_bukan_mutable_bersama_dan_level_lain_ditolak():
    _domain()[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] != "rusak"
    for level in ("P1", "P2", "P5", "kelas 6", ""):
        with pytest.raises(ValueError, match="level"):
            modul.domain_parameter(level)
        with pytest.raises(ValueError, match="level"):
            modul.parameter(random.Random(0), level)
    assert modul.LEVEL == (LEVEL,)


def test_sampler_tetap_di_domain_dan_menjangkau_semua_varian_seimbang():
    kanon = {_kanon(p) for p in _domain()}
    hitung = {v: 0 for v in VARIAN}
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert _kanon(p) in kanon, (seed, p)
        hitung[p["varian"]] = hitung.get(p["varian"], 0) + 1
    assert all(n >= MIN_SAMPLER for n in hitung.values()), hitung


def test_sampler_murni_dari_rng_seed_sama_hasil_sama():
    for seed in range(50):
        assert modul.parameter(random.Random(seed), LEVEL) == modul.parameter(random.Random(seed), LEVEL)


def test_tanda_tangan_dan_teks_unik_di_seluruh_domain():
    from dataclasses import replace
    soal = [replace(_soal(p), level=LEVEL) for p in _domain()]
    assert len({s.tanda_tangan for s in soal}) == len(soal)
    assert len({s.teks for s in soal}) == len(soal), "dua parameter berbeda menghasilkan teks sama"
    assert all(s.parameter == p for s, p in zip(soal, _domain()))


def test_batas_angka_domain_diperiksa_dari_teks_bukan_tabel_modul():
    for p in _domain():
        teks = _soal(p).teks
        if p["varian"] in ("kali_asli", "bagi_asli", "asli_kali", "cerita"):
            a, b = map(int, re.search(r"(\d+)/(\d+)", teks).groups())
            n = p["n"]
            assert 2 <= b <= 12 and 0 < a < b and math.gcd(a, b) == 1, teks
            assert 2 <= n <= 12, teks
        if p["varian"] in ("kali_asli", "asli_kali"):
            hasil = Fraction(a * n, b)
            assert hasil.denominator == 1 or hasil < 1, ("bilangan campur", teks)
        if p["varian"] == "bagi_asli":
            assert Fraction(a, b * n).denominator <= 24, teks
        if p["varian"] == "ke_desimal":
            a, b = map(int, re.search(r"(\d+)/(\d+)", teks).groups())
            assert b in (2, 4, 5, 8, 10, 20, 25) and 0 < a < b and math.gcd(a, b) == 1, teks
        if p["varian"] == "desimal_ke_pecahan":
            belakang = re.search(r"desimal 0,(\d+) ", teks).group(1)
            assert len(belakang) <= 2 and not belakang.endswith("0"), teks
            penyebut = Fraction(int(belakang), 10 ** len(belakang)).denominator
            assert penyebut in (2, 4, 5, 10, 20, 25), teks


# ── kunci ────────────────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.bagian == "A" and soal.template_id == TID


def test_sapuan_seed_kunci_sama_dengan_solver_teks():
    for seed in SEED:
        soal = _soal(modul.parameter(random.Random(seed), LEVEL))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_bentuk_kunci_pecahan_sederhana_atau_bulat_dan_desimal_koma_tanpa_nol_belakang():
    for p in _domain_lama():
        kunci = _soal(p).kunci
        assert kunci == kunci.strip() and " " not in kunci
        if p["varian"] == "ke_desimal":
            assert re.fullmatch(r"0,[0-9]*[1-9]", kunci), kunci
            continue
        if re.fullmatch(r"[1-9][0-9]*", kunci):
            assert p["varian"] in ("kali_asli", "asli_kali", "cerita"), (p, "bulat hanya dari kali")
            continue
        cocok = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", kunci)
        assert cocok, (p, kunci)
        pembilang, penyebut = int(cocok.group(1)), int(cocok.group(2))
        assert math.gcd(pembilang, penyebut) == 1, ("harus paling sederhana", kunci)
        assert pembilang < penyebut, ("bukan pecahan biasa (bilangan campur)", kunci)


def test_kunci_contoh_tangan():
    f = modul.pecahan_bilangan_asli_desimal
    assert f(varian="kali_asli", a=3, b=8, n=2).kunci == "3/4"
    assert f(varian="kali_asli", a=3, b=4, n=8).kunci == "6"
    assert f(varian="kali_asli", a=1, b=6, n=3).kunci == "1/2"
    assert f(varian="bagi_asli", a=2, b=3, n=4).kunci == "1/6"
    assert f(varian="bagi_asli", a=3, b=4, n=2).kunci == "3/8"
    assert f(varian="asli_kali", a=2, b=3, n=6).kunci == "4"
    assert f(varian="ke_desimal", a=3, b=8).kunci == "0,375"
    assert f(varian="ke_desimal", a=1, b=2).kunci == "0,5"
    assert f(varian="ke_desimal", a=3, b=25).kunci == "0,12"
    assert f(varian="ke_desimal", a=1, b=20).kunci == "0,05"
    assert f(varian="desimal_ke_pecahan", perseratus=75).kunci == "3/4"
    assert f(varian="desimal_ke_pecahan", perseratus=5).kunci == "1/20"
    assert f(varian="desimal_ke_pecahan", perseratus=40).kunci == "2/5"
    assert f(varian="cerita", cerita=0, a=3, b=4, n=3).kunci == "1/4"
    assert f(varian="cerita", cerita=2, a=1, b=4, n=2).kunci == "1/2"
    assert f(varian="kali_asli", a=3, b=8, n=2).teks == (
        "Hitung: 3/8 × 2 = ... (tulis hasilnya dalam bentuk paling sederhana)")
    assert f(varian="cerita", cerita=0, a=3, b=4, n=3).teks == (
        "Sebuah tali panjangnya 3/4 m dipotong menjadi 3 bagian sama panjang. "
        "Berapa meter panjang tiap bagian? (tulis hasilnya dalam bentuk paling sederhana)")


def test_kunci_pecahan_dan_desimal_dibaca_pembanding_bawaan():
    for p in _domain():
        soal = _soal(p)
        assert diagnosis.setara(soal.kunci, soal.kunci, soal=soal)
    d = modul.pecahan_bilangan_asli_desimal(varian="ke_desimal", a=3, b=4)
    assert diagnosis.setara("0.75", d.kunci, soal=d), "titik desimal diterima, kunci tetap koma"
    assert diagnosis.setara("0,75", d.kunci, soal=d)
    assert not diagnosis.setara("0,750", d.kunci, soal=d), "konvensi kunci: tanpa nol di belakang"
    s = modul.pecahan_bilangan_asli_desimal(varian="kali_asli", a=3, b=8, n=2)
    assert diagnosis.setara("3/4", s.kunci, soal=s)
    assert not diagnosis.setara("6/8", s.kunci, soal=s), "pecahan hanya cocok sebagai string persis"


def test_varian_asli_kali_dan_kali_asli_berkunci_sama_tetapi_teks_beda():
    for p in _varian("kali_asli"):
        q = dict(p, varian="asli_kali")
        assert _soal(p).kunci == _soal(q).kunci
        assert _soal(p).teks != _soal(q).teks


def test_bilangan_campur_tidak_pernah_jadi_kunci_dan_bagi_selalu_pecahan_biasa():
    for p in _varian("bagi_asli"):
        assert "/" in _soal(p).kunci
    for p in _domain_lama():
        if p["varian"] in ("kali_asli", "asli_kali"):
            kunci = _soal(p).kunci
            assert "/" not in kunci or _nilai(kunci) < 1


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        nilai = [_nilai(m.jawaban) for m in soal.malrule]
        assert _nilai(soal.kunci) not in nilai, (p, "malrule sama dengan kunci menurut nilai")
        assert len(set(nilai)) == len(nilai), (p, "malrule kembar menurut nilai")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert {m.kode for m in soal.malrule} == {"K"}
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert all(m.alasan.strip() and m.alasan[0].isupper() and m.alasan.endswith(".")
                   for m in soal.malrule), (p, [m.alasan for m in soal.malrule])
        assert all(m.alasan.startswith(f"Menjawab {m.jawaban}: kemungkinan ")
                   for m in soal.malrule), (p, [m.alasan for m in soal.malrule])


def test_malrule_cukup_untuk_pengecoh_pilihan_ganda_seluruh_domain():
    """Proksi kebijakan PG bawaan (empat-v1, angka): pengecoh beda nilai dari kunci dan satu sama lain."""
    for p in _domain():
        soal = _soal(p)
        benar = nilai_semantis(soal.kunci, "angka")
        pengecoh = {nilai_semantis(m.jawaban, "angka") for m in soal.malrule} - {benar}
        assert len(pengecoh) >= PENGECOH_PERLU, (p, [m.jawaban for m in soal.malrule])


def _harapan_kali(a: int, b: int, n: int) -> set:
    hasil = Fraction(a * n, b)
    return {Fraction(a, b), Fraction(a, b * n), Fraction(a + n, b), 1 / hasil}


def _harapan_bagi(a: int, b: int, n: int) -> set:
    hasil = Fraction(a, b * n)
    return {Fraction(a * n, b), Fraction(a, b), Fraction(b, a * n), 1 / hasil}


def test_malrule_kali_dan_bagi_pecahan_dengan_bilangan_asli():
    for p in _domain_lama():
        if p["varian"] in ("ke_desimal", "desimal_ke_pecahan"):
            continue
        soal = _soal(p)
        a, b, n = p["a"], p["b"], p["n"]
        operasi = p["varian"] if p["varian"] != "cerita" else modul.CERITA[p["cerita"]][0]
        kali = operasi in ("kali_asli", "asli_kali", "kali")
        harapan = (_harapan_kali if kali else _harapan_bagi)(a, b, n) - {_nilai(soal.kunci)}
        assert {_nilai(m.jawaban) for m in soal.malrule} == harapan, p


def test_malrule_kali_memuat_penyebut_ikut_dikali_dan_pembilang_penyebut_tertukar():
    soal = modul.pecahan_bilangan_asli_desimal(varian="kali_asli", a=3, b=8, n=2)
    jawaban = {m.id.split(".")[1]: m.jawaban for m in soal.malrule}
    assert jawaban == {"kali_dua_sisi": "3/8", "kali_penyebut_saja": "3/16",
                       "tambah_pembilang": "5/8", "hasil_terbalik": "4/3"}


def test_malrule_bagi_memuat_dikali_bukan_dibagi_dan_pecahan_dibalik():
    soal = modul.pecahan_bilangan_asli_desimal(varian="bagi_asli", a=2, b=3, n=4)
    jawaban = {m.id.split(".")[1]: m.jawaban for m in soal.malrule}
    assert jawaban == {"bagi_jadi_kali": "8/3", "kali_dua_sisi": "2/3",
                       "pecahan_dibalik": "3/8", "hasil_terbalik": "6"}


def test_malrule_ke_desimal_titik_salah_pisah_koma_dan_susun_belakang_koma():
    for p in _varian("ke_desimal"):
        soal = _soal(p)
        a, b = p["a"], p["b"]
        x = Fraction(a, b)
        harapan = {x * 10, x / 10, _nilai(f"{a},{b}"), _nilai(f"0,{a}{b}")} - {x}
        assert {_nilai(m.jawaban) for m in soal.malrule} == harapan, p
    soal = modul.pecahan_bilangan_asli_desimal(varian="ke_desimal", a=3, b=4)
    assert {m.jawaban for m in soal.malrule} == {"7,5", "0,075", "3,4", "0,34"}


def test_malrule_desimal_ke_pecahan_tertukar_penyebut_salah_dan_satu_per_angka():
    soal = modul.pecahan_bilangan_asli_desimal(varian="desimal_ke_pecahan", perseratus=75)
    assert {m.jawaban for m in soal.malrule} == {"4/3", "15/2", "3/40", "1/75"}
    soal = modul.pecahan_bilangan_asli_desimal(varian="desimal_ke_pecahan", perseratus=50)
    assert {m.jawaban for m in soal.malrule} == {"2", "5", "1/20", "1/5"}
    for p in _varian("desimal_ke_pecahan"):
        s = _soal(p)
        x = Fraction(p["perseratus"], 100)
        assert 1 / x in {_nilai(m.jawaban) for m in s.malrule}, p


# ── pembahasan dan bahasa ────────────────────────────────────────────────

def test_pembahasan_dan_teks_bahasa_anak_tanpa_istilah_guru_dan_memuat_kunci():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert re.search(r"(?<![\w/,])" + re.escape(soal.kunci) + r"(?![\w/]|,\d)",
                         soal.pembahasan), (p, soal.pembahasan)
        assert soal.pembahasan.strip() != soal.kunci and len(soal.pembahasan) > 40
        assert "Cocokkan dengan caramu" not in soal.pembahasan
        assert soal.teks.endswith(")") and "\n" not in soal.teks and "\n" not in soal.pembahasan


def test_pembahasan_tidak_menyebut_sederhanakan_bila_sudah_sederhana():
    soal = modul.pecahan_bilangan_asli_desimal(varian="kali_asli", a=1, b=4, n=3)
    assert "Sederhanakan" not in soal.pembahasan
    soal = modul.pecahan_bilangan_asli_desimal(varian="kali_asli", a=3, b=8, n=2)
    assert "Sederhanakan 6/8" in soal.pembahasan and soal.pembahasan.count("3/4") >= 2


def test_nama_anak_hanya_dari_daftar_sintetis_umum():
    dikenal = re.compile(r"\b(Rina|Budi|Dita|Eko|Ani|Andi|Sari|Tono|Siti|Joko)\b")
    muncul = set()
    for p in _varian("cerita"):
        soal = _soal(p)
        muncul |= set(dikenal.findall(soal.teks + soal.pembahasan))
    assert muncul <= {"Rina", "Budi", "Dita", "Eko"}, muncul
    assert muncul, "cerita memuat nama anak sintetis"


# ── penolakan parameter di luar domain ───────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada"),
    dict(varian="kali_asli", a=3, b=4, n=5),                 # 15/4: bilangan campur
    dict(varian="kali_asli", a=3, b=4, n=1),                 # n < 2
    dict(varian="kali_asli", a=3, b=4, n=13),                # n > 12
    dict(varian="kali_asli", a=2, b=4, n=2),                 # operan tidak sederhana
    dict(varian="kali_asli", a=4, b=4, n=2),                 # bukan pecahan biasa
    dict(varian="kali_asli", a=5, b=4, n=2),
    dict(varian="kali_asli", a=1, b=13, n=13),               # penyebut > 12
    dict(varian="kali_asli", a=3, b=4),
    dict(varian="kali_asli", a=3, b=4, n=8, perseratus=5),
    dict(varian="kali_asli", a=True, b=4, n=8),
    dict(varian="kali_asli", a=3.0, b=4, n=8),
    dict(varian="kali_asli", a="3", b=4, n=8),
    dict(varian="kali_asli", a=-3, b=4, n=8),
    dict(varian="asli_kali", a=3, b=4, n=5),
    dict(varian="bagi_asli", a=7, b=12, n=12),               # penyebut hasil 144 > 24
    dict(varian="bagi_asli", a=1, b=11, n=3),                # penyebut hasil 33 > 24
    dict(varian="bagi_asli", a=2, b=4, n=2),
    dict(varian="bagi_asli", a=2, b=3, n=1),
    dict(varian="ke_desimal", a=1, b=3),                     # tidak berhenti
    dict(varian="ke_desimal", a=1, b=6),
    dict(varian="ke_desimal", a=2, b=4),                     # tidak sederhana
    dict(varian="ke_desimal", a=1, b=16),                    # penyebut tak terdaftar
    dict(varian="ke_desimal", a=1, b=50),
    dict(varian="ke_desimal", a=3, b=4, n=2),
    dict(varian="desimal_ke_pecahan", perseratus=0),
    dict(varian="desimal_ke_pecahan", perseratus=100),       # satu utuh
    dict(varian="desimal_ke_pecahan", perseratus=1),         # 1/100
    dict(varian="desimal_ke_pecahan", perseratus=33),        # 33/100
    dict(varian="desimal_ke_pecahan", perseratus=2),         # 1/50
    dict(varian="desimal_ke_pecahan", perseratus=75.0),
    dict(varian="desimal_ke_pecahan", perseratus=True),
    dict(varian="desimal_ke_pecahan"),
    dict(varian="cerita", cerita=4, a=3, b=4, n=3),          # indeks cerita tak terdaftar
    dict(varian="cerita", cerita=-1, a=3, b=4, n=3),
    dict(varian="cerita", cerita=0, a=3, b=4),
    dict(varian="cerita", cerita=0, a=1, b=11, n=3),         # bagi: penyebut hasil > 24
    dict(varian="cerita", cerita=2, a=3, b=4, n=5),          # kali: bilangan campur
    dict(varian="cerita", a=3, b=4, n=3),
])
def test_parameter_tidak_sah_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.pecahan_bilangan_asli_desimal(**parameter)


def test_parameter_tanpa_varian_ditolak():
    with pytest.raises(TypeError):
        modul.pecahan_bilangan_asli_desimal()
    with pytest.raises(ValueError, match="di luar domain"):
        modul.pecahan_bilangan_asli_desimal(varian=None)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
import awal_pecahan_bilangan_asli_desimal as m
hasil = []
for seed in range(120):
    p = m.parameter(random.Random(seed), "P6")
    s = m.pecahan_bilangan_asli_desimal(**p)
    hasil.append([p, s.teks, s.kunci, s.pembahasan,
                  [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
hasil.append([[d, m.pecahan_bilangan_asli_desimal(**d).teks] for d in m.domain_parameter("P6")])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSN_MATEMATIKA_AWAL")}
    env["PYTHONHASHSEED"] = hash_seed
    hasil = subprocess.run([sys.executable, "-c", _KODE % {"akar": str(AKAR_MODUL)}],
                           env=env, capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def _dalam_proses():
    hasil = []
    for seed in range(120):
        p = modul.parameter(random.Random(seed), LEVEL)
        s = modul.pecahan_bilangan_asli_desimal(**p)
        hasil.append([p, s.teks, s.kunci, s.pembahasan,
                      [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
    hasil.append([[d, modul.pecahan_bilangan_asli_desimal(**d).teks] for d in modul.domain_parameter(LEVEL)])
    return json.loads(json.dumps(hasil, sort_keys=True))


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert a == _dalam_proses(), "proses anak harus memuat modul yang sama dengan tes"


# ══ perluasan v2: hasil tak wajar, campuran, pembulatan, persen ═══════════
# Solver terpisah di bawah hanya membaca TEKS (regex); tidak memakai tabel modul.

import hashlib

VARIAN_V2 = ("kali_asli_tak_wajar", "bagi_asli_tak_wajar", "campur_ke_biasa",
             "ke_desimal_berulang_dibulatkan", "desimal_ke_persen_pecahan",
             "cerita_kali_bagi_pecahan")
UKURAN_V2 = {"kali_asli_tak_wajar": 818, "bagi_asli_tak_wajar": 600, "campur_ke_biasa": 225,
             "ke_desimal_berulang_dibulatkan": 30, "desimal_ke_persen_pecahan": 138,
             "cerita_kali_bagi_pecahan": 2140}
UKURAN_DOMAIN_LAMA = 1150
# Hash identitas enam varian lama (parameter, teks, kunci, pembahasan, malrule) sebelum v2.
HASH_DOMAIN_LAMA = "8a2993d5082110b2a6073f68620f5df921b4fc2a32d53f13865062b93dc5a098"
AKHIRAN_TW = re.compile(r"\(tulis hasilnya sebagai pecahan biasa paling sederhana, contoh (\d+)/(\d+); "
                        r"bila hasilnya bilangan bulat, tulis bilangannya saja\)")
CONTOH_GARIS_MIRING = re.compile(r"\(tulis dengan garis miring, contoh (\d+)/(\d+)\)")
# (potongan khas, operasi, regex pengambil n); untuk tujuh cerita v2
_CIRI_CERITA_V2 = (
    ("Satu kantong beras", "kali", r"berat (\d+) kantong beras"),
    ("Dita membaca buku", "kali", r"dalam (\d+) hari"),
    ("Satu botol sirup", "kali", r"dalam (\d+) botol yang sama"),
    ("sebuah gelang dari tali", "kali", r"untuk (\d+) gelang"),
    ("Sebuah botol berisi", "bagi", r"ke dalam (\d+) gelas kecil"),
    ("Pita itu dipotong sama panjang", "bagi", r"menjadi (\d+) potong"),
    ("Budi membagi", "bagi", r"ke dalam (\d+) plastik"),
)


def _periksa_contoh(contoh: tuple, kunci: str) -> None:
    assert f"{contoh[0]}/{contoh[1]}" != kunci, ("contoh bentuk sama dengan jawaban", kunci)


def _solver_kali_tw(teks: str) -> str:
    cocok = re.fullmatch(r"Hitung: (?:(\d+)/(\d+) × (\d+)|(\d+) × (\d+)/(\d+)) = \.\.\. (\(.*\))", teks)
    assert cocok, teks
    a1, b1, n1, n2, a2, b2, akhir = cocok.groups()
    a, b, n = (int(a1), int(b1), int(n1)) if a1 else (int(a2), int(b2), int(n2))
    kunci = _tulis_pecahan(Fraction(a * n, b))
    cocok_akhir = AKHIRAN_TW.fullmatch(akhir)
    assert cocok_akhir, teks
    _periksa_contoh(cocok_akhir.groups(), kunci)
    return kunci


def _solver_bagi_campur(teks: str) -> str:
    cocok = re.fullmatch(r"Hitung: (\d+) (\d+)/(\d+) ÷ (\d+) = \.\.\." + AKHIRAN, teks)
    assert cocok, teks
    w, p, b, n = map(int, cocok.groups())
    return _tulis_pecahan(Fraction(w * b + p, b * n))


def _solver_campur_ke_biasa(teks: str) -> str:
    cocok = re.fullmatch(r"Pecahan campuran (\d+) (\d+)/(\d+) ditulis sebagai pecahan biasa menjadi \.\.\. "
                         r"(\(.*\))", teks)
    assert cocok, teks
    w, p, b = map(int, cocok.groups()[:3])
    kunci = _tulis_pecahan(Fraction(w * b + p, b))
    contoh = CONTOH_GARIS_MIRING.fullmatch(cocok.group(4))
    assert contoh, teks
    _periksa_contoh(contoh.groups(), kunci)
    return kunci


def _solver_berulang(teks: str) -> str:
    cocok = re.fullmatch(r"Ubah pecahan (\d+)/(\d+) menjadi bilangan desimal, dibulatkan sampai satu angka "
                         r"di belakang koma\. Jawabannya \.\.\. \(tulis dengan tanda koma\)", teks)
    assert cocok, teks
    a, b = map(int, cocok.groups())
    puluhan = (20 * a + b) // (2 * b)  # pembulatan setengah ke atas dengan bilangan bulat
    assert 0 < puluhan < 10, teks
    return f"0,{puluhan}"


def _solver_persen_pecahan(teks: str) -> str:
    cocok = re.fullmatch(r"Nyatakan (0,\d+) sebagai persen\. Jawabannya \.\.\. persen "
                         r"\(tulis angkanya saja\)", teks)
    if cocok:
        persen = Fraction(cocok.group(1).replace(",", ".")) * 100
        assert persen.denominator == 1, teks
        return str(persen.numerator)
    cocok = re.fullmatch(r"Nyatakan (\d+)% sebagai pecahan paling sederhana\. "
                         r"Jawabannya \.\.\. \(tulis dengan garis miring, contoh 2/3\)", teks)
    assert cocok, teks
    return _tulis_pecahan(Fraction(int(cocok.group(1)), 100))


def _solver_cerita_v2(teks: str, ciri: tuple) -> str:
    _, operasi, pola = ciri
    pecahan = re.findall(r"(\d+)/(\d+)", teks.split("?")[0])
    assert len(pecahan) == 1, teks
    a, b = map(int, pecahan[0])
    n = int(re.search(pola, teks).group(1))
    sisa = teks.split("?", 1)[1].strip()
    if operasi == "kali":
        kunci = _tulis_pecahan(Fraction(a * n, b))
        cocok = AKHIRAN_TW.fullmatch(sisa)
        assert cocok, teks
        _periksa_contoh(cocok.groups(), kunci)
        return kunci
    assert sisa == "(tulis hasilnya dalam bentuk paling sederhana)", teks
    return _tulis_pecahan(Fraction(a, b * n))


def _solver_v2(teks: str):
    """Kunci untuk teks varian v2, atau None bila teks milik enam varian lama."""
    if "menjadi bilangan desimal, dibulatkan" in teks:
        return _solver_berulang(teks)
    if teks.startswith("Pecahan campuran "):
        return _solver_campur_ke_biasa(teks)
    if teks.startswith("Nyatakan "):
        return _solver_persen_pecahan(teks)
    ditemukan = [c for c in _CIRI_CERITA_V2 if c[0] in teks]
    if ditemukan:
        assert len(ditemukan) == 1, teks
        return _solver_cerita_v2(teks, ditemukan[0])
    if teks.startswith("Hitung: ") and AKHIRAN_TW.search(teks):
        return _solver_kali_tw(teks)
    if re.match(r"Hitung: \d+ \d+/\d+ ÷ ", teks):
        return _solver_bagi_campur(teks)
    return None


def _domain_v2() -> list:
    return [p for p in _domain() if p["varian"] in VARIAN_V2]


def _bagi_dari_teks(teks: str) -> tuple:
    """(pembilang tak wajar, penyebut, n) dari teks 'Hitung: 5/3 ÷ 2' atau 'Hitung: 1 2/3 ÷ 2'."""
    cocok = re.match(r"Hitung: (?:(\d+) )?(\d+)/(\d+) ÷ (\d+) = ", teks)
    assert cocok, teks
    w, p, b, n = cocok.groups()
    return (int(w or 0) * int(b) + int(p), int(b), int(n))


# ── domain v2 ────────────────────────────────────────────────────────────

def test_v2_domain_lama_identik_dan_tetap_di_depan():
    domain = _domain()
    lama = domain[:UKURAN_DOMAIN_LAMA]
    assert all(p["varian"] in VARIAN for p in lama)
    assert all(p["varian"] in VARIAN_V2 for p in domain[UKURAN_DOMAIN_LAMA:])
    isi = [[p, s.teks, s.kunci, s.pembahasan, [[x.id, x.jawaban, x.alasan] for x in s.malrule]]
           for p in lama for s in (_soal(p),)]
    assert hashlib.sha256(json.dumps(isi, sort_keys=True).encode()).hexdigest() == HASH_DOMAIN_LAMA


def test_v2_ukuran_domain_per_varian_tidak_kembar_dan_cukup():
    per_varian = {v: len(_varian(v)) for v in VARIAN_V2}
    assert per_varian == UKURAN_V2
    assert len(_domain()) == UKURAN_DOMAIN_LAMA + sum(UKURAN_V2.values())
    assert all(n >= 30 for n in per_varian.values())
    assert "biasa_ke_campur" not in modul.VARIAN
    assert modul.VARIAN == VARIAN + VARIAN_V2


def test_v2_sampler_menjangkau_semua_varian_baru_seimbang_dan_tetap_di_domain():
    kanon = {_kanon(p) for p in _domain()}
    hitung = {v: 0 for v in VARIAN + VARIAN_V2}
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert _kanon(p) in kanon, (seed, p)
        hitung[p["varian"]] += 1
    assert all(n >= MIN_SAMPLER for n in hitung.values()), hitung


def test_v2_batas_angka_diperiksa_dari_teks():
    for p in _domain_v2():
        teks = _soal(p).teks
        v = p["varian"]
        if v == "kali_asli_tak_wajar":
            a, b = map(int, re.search(r"(\d+)/(\d+)", teks).groups())
            n = p["n"]
            assert 2 <= b <= 12 and 0 < a < b and math.gcd(a, b) == 1 and 2 <= n <= 12, teks
            assert Fraction(a * n, b) > 1, ("hasil harus lebih dari 1", teks)
        if v == "bagi_asli_tak_wajar":
            a, b, n = _bagi_dari_teks(teks)
            assert 2 <= b <= 12 and b < a < 3 * b and math.gcd(a, b) == 1 and 2 <= n <= 12, teks
            hasil = Fraction(a, b * n)
            assert hasil < 1 and hasil.denominator <= 24, ("hasil pecahan kurang dari 1", teks)
        if v == "campur_ke_biasa":
            w, a, b = map(int, re.search(r"campuran (\d+) (\d+)/(\d+) ", teks).groups())
            assert 1 <= w <= 5 and 2 <= b <= 12 and 0 < a < b and math.gcd(a, b) == 1, teks
        if v == "ke_desimal_berulang_dibulatkan":
            a, b = map(int, re.search(r"pecahan (\d+)/(\d+) ", teks).groups())
            assert b in (3, 6, 7, 9, 11, 12) and 0 < a < b and math.gcd(a, b) == 1, teks
        if v == "cerita_kali_bagi_pecahan":
            a, b = map(int, re.search(r"(\d+)/(\d+)", teks).groups())
            assert 2 <= b <= 12 and 0 < a < b and math.gcd(a, b) == 1, teks


def test_v2_tidak_ada_kasus_di_tengah_pembulatan():
    for p in _varian("ke_desimal_berulang_dibulatkan"):
        x = Fraction(p["a"], p["b"]) * 100
        assert not (x.denominator == 1 and x.numerator % 10 == 5), ("tepat di tengah", p)
        assert x.denominator != 1, ("desimal berhenti dua angka tidak dipakai di sini", p)


# ── kunci v2 ─────────────────────────────────────────────────────────────

def test_v2_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain_v2():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.bagian == "A" and soal.template_id == TID


def test_v2_bentuk_kunci_per_varian():
    for p in _domain_v2():
        kunci = _soal(p).kunci
        v = p["varian"]
        assert kunci == kunci.strip() and " " not in kunci
        if v in ("kali_asli_tak_wajar",) or (v == "cerita_kali_bagi_pecahan"
                                             and p["cerita"] < 4):
            if "/" in kunci:
                a, b = map(int, kunci.split("/"))
                assert a > b > 1 and math.gcd(a, b) == 1, ("pecahan tak wajar paling sederhana", kunci)
            else:
                assert re.fullmatch(r"[1-9][0-9]*", kunci) and int(kunci) > 1, kunci
        elif v in ("bagi_asli_tak_wajar", "cerita_kali_bagi_pecahan"):
            a, b = map(int, kunci.split("/"))
            assert 0 < a < b and math.gcd(a, b) == 1, ("pecahan biasa kurang dari 1", kunci)
        elif v == "campur_ke_biasa":
            a, b = map(int, kunci.split("/"))
            assert a > b > 1 and math.gcd(a, b) == 1, kunci
        elif v == "ke_desimal_berulang_dibulatkan":
            assert re.fullmatch(r"0,[1-9]", kunci), kunci
        elif p["arah"] == "ke_persen":
            assert re.fullmatch(r"[1-9][0-9]?", kunci), kunci
        else:
            a, b = map(int, kunci.split("/"))
            assert 0 < a < b and math.gcd(a, b) == 1 and b in (2, 4, 5, 10, 20, 25), kunci


def test_v2_kunci_contoh_tangan():
    f = modul.pecahan_bilangan_asli_desimal
    assert f(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=0).kunci == "15/4"
    assert f(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=1).kunci == "15/4"
    assert f(varian="kali_asli_tak_wajar", a=3, b=4, n=8, urut=0).kunci == "6"
    assert f(varian="kali_asli_tak_wajar", a=1, b=3, n=7, urut=0).kunci == "7/3"
    assert f(varian="bagi_asli_tak_wajar", a=5, b=3, n=2, bentuk="biasa").kunci == "5/6"
    assert f(varian="bagi_asli_tak_wajar", a=5, b=3, n=2, bentuk="campur").kunci == "5/6"
    assert f(varian="bagi_asli_tak_wajar", a=5, b=3, n=5, bentuk="biasa").kunci == "1/3"
    assert f(varian="campur_ke_biasa", w=2, a=1, b=4).kunci == "9/4"
    assert f(varian="campur_ke_biasa", w=1, a=3, b=8).kunci == "11/8"
    for a, b, k in ((1, 3, "0,3"), (2, 3, "0,7"), (5, 6, "0,8"), (1, 12, "0,1"),
                    (11, 12, "0,9"), (1, 7, "0,1"), (6, 7, "0,9"), (2, 9, "0,2")):
        assert f(varian="ke_desimal_berulang_dibulatkan", a=a, b=b).kunci == k, (a, b)
    assert f(varian="desimal_ke_persen_pecahan", arah="ke_persen", perseratus=25).kunci == "25"
    assert f(varian="desimal_ke_persen_pecahan", arah="ke_persen", perseratus=5).kunci == "5"
    assert f(varian="desimal_ke_persen_pecahan", arah="ke_pecahan", perseratus=75).kunci == "3/4"
    assert f(varian="desimal_ke_persen_pecahan", arah="ke_pecahan", perseratus=5).kunci == "1/20"
    assert f(varian="cerita_kali_bagi_pecahan", cerita=4, a=3, b=4, n=3).kunci == "1/4"
    assert f(varian="cerita_kali_bagi_pecahan", cerita=0, a=2, b=3, n=5).kunci == "10/3"
    assert f(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=0).teks == (
        "Hitung: 3/4 × 5 = ... (tulis hasilnya sebagai pecahan biasa paling sederhana, contoh 7/3; "
        "bila hasilnya bilangan bulat, tulis bilangannya saja)")
    assert f(varian="kali_asli_tak_wajar", a=1, b=3, n=7, urut=1).teks == (
        "Hitung: 7 × 1/3 = ... (tulis hasilnya sebagai pecahan biasa paling sederhana, contoh 5/2; "
        "bila hasilnya bilangan bulat, tulis bilangannya saja)"), "contoh dialihkan bila sama dengan kunci"
    assert f(varian="ke_desimal_berulang_dibulatkan", a=2, b=3).teks == (
        "Ubah pecahan 2/3 menjadi bilangan desimal, dibulatkan sampai satu angka di belakang koma. "
        "Jawabannya ... (tulis dengan tanda koma)")


def test_v2_kalimat_menyatakan_bentuk_jawaban_tegas():
    for p in _domain_v2():
        teks = _soal(p).teks
        v = p["varian"]
        if v == "kali_asli_tak_wajar" or (v == "cerita_kali_bagi_pecahan" and p["cerita"] < 4):
            assert "tulis hasilnya sebagai pecahan biasa paling sederhana, contoh " in teks, teks
        if v == "ke_desimal_berulang_dibulatkan":
            assert "dibulatkan sampai satu angka di belakang koma" in teks, teks
        if v == "campur_ke_biasa":
            assert "ditulis sebagai pecahan biasa" in teks and "contoh" in teks, teks


def test_v2_kunci_dibaca_pembanding_bawaan_pecahan_tak_wajar_string_persis():
    s = modul.pecahan_bilangan_asli_desimal(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=0)
    assert diagnosis.setara("15/4", s.kunci, soal=s)
    assert not diagnosis.setara("30/8", s.kunci, soal=s)
    assert not diagnosis.setara("3 3/4", s.kunci, soal=s), "campuran bukan kunci; soal meminta pecahan biasa"
    b = modul.pecahan_bilangan_asli_desimal(varian="kali_asli_tak_wajar", a=3, b=4, n=8, urut=0)
    assert diagnosis.setara("6", b.kunci, soal=b)
    d = modul.pecahan_bilangan_asli_desimal(varian="ke_desimal_berulang_dibulatkan", a=2, b=3)
    assert diagnosis.setara("0.7", d.kunci, soal=d) and diagnosis.setara("0,7", d.kunci, soal=d)
    assert not diagnosis.setara("0,67", d.kunci, soal=d)


def test_v2_campuran_tidak_pernah_menjadi_kunci_karena_pg_tidak_membacanya():
    with pytest.raises(ValueError):
        nilai_semantis("2 1/4", "angka")
    for p in _domain_v2():
        assert " " not in _soal(p).kunci
    with pytest.raises(ValueError, match="di luar domain"):
        modul.pecahan_bilangan_asli_desimal(varian="biasa_ke_campur", a=1, b=4, w=2)


def test_v2_bagi_tak_wajar_kedua_bentuk_dan_hasil_selalu_pecahan_kurang_dari_1():
    biasa = {(p["a"], p["b"], p["n"]) for p in _varian("bagi_asli_tak_wajar") if p["bentuk"] == "biasa"}
    campur = {(p["a"], p["b"], p["n"]) for p in _varian("bagi_asli_tak_wajar") if p["bentuk"] == "campur"}
    assert biasa == campur and len(biasa) == 300
    for p in _varian("bagi_asli_tak_wajar"):
        soal = _soal(p)
        assert p["a"] > p["b"], "operan tak wajar"
        if p["bentuk"] == "campur":
            assert re.match(r"Hitung: \d+ \d+/\d+ ÷ ", soal.teks), soal.teks
        else:
            assert re.match(r"Hitung: \d+/\d+ ÷ ", soal.teks), soal.teks
        assert _nilai(soal.kunci) < 1


# ── malrule v2 ───────────────────────────────────────────────────────────

def _harapan_malrule_v2(p: dict, kunci: Fraction) -> set:
    v = p["varian"]
    if v in ("kali_asli_tak_wajar", "cerita_kali_bagi_pecahan") and (
            v == "kali_asli_tak_wajar" or p["cerita"] < 4):
        a, b, n = p["a"], p["b"], p["n"]
        hasil = Fraction(a * n, b)
        return {Fraction(a, b), Fraction(a, b * n), Fraction(a + n, b), 1 / hasil,
                Fraction(b * n, a)} - {kunci}
    if v == "cerita_kali_bagi_pecahan":
        return _harapan_bagi(p["a"], p["b"], p["n"]) - {kunci}
    if v == "bagi_asli_tak_wajar":
        a, b, n = p["a"], p["b"], p["n"]
        ekstra = {Fraction(a % b, b * n)} if p["bentuk"] == "campur" else set()
        return (_harapan_bagi(a, b, n) | ekstra) - {kunci}
    if v == "campur_ke_biasa":
        w, a, b = p["w"], p["a"], p["b"]
        return {Fraction(w + a, b), Fraction(w * a, b), Fraction(int(f"{w}{a}"), b),
                Fraction(w * b, b), Fraction(b, w * b + a)} - {kunci}
    if v == "ke_desimal_berulang_dibulatkan":
        a, b = p["a"], p["b"]
        x = Fraction(a, b)
        asli = math.floor(x * 10)
        return {Fraction(math.ceil(x * 10), 10), Fraction(asli, 10),
                Fraction(math.floor(x * 100 + Fraction(1, 2)), 100),
                kunci / 10, kunci * 10, _nilai(f"{a},{b}")} - {kunci}
    m = p["perseratus"]
    if p["arah"] == "ke_persen":
        return {Fraction(m, 10), Fraction(m, 100), Fraction(10 * m)} - {kunci}
    return {Fraction(100, m), Fraction(m, 10), Fraction(m, 1000), Fraction(1, m)} - {kunci}


def test_v2_malrule_sama_dengan_himpunan_hipotesis_dihitung_ulang_per_varian():
    for p in _domain_v2():
        soal = _soal(p)
        kunci = _nilai(soal.kunci)
        harapan = _harapan_malrule_v2(p, kunci)
        harapan = {x for x in harapan if x != kunci}
        assert {_nilai(m.jawaban) for m in soal.malrule} == harapan, (p, [m.jawaban for m in soal.malrule])


def test_v2_malrule_jalur_k_tidak_kembar_dan_ada_pengecoh_cukup():
    for p in _domain_v2():
        soal = _soal(p)
        nilai = [_nilai(m.jawaban) for m in soal.malrule]
        assert _nilai(soal.kunci) not in nilai, p
        assert len(set(nilai)) == len(nilai), p
        assert len({m.jawaban for m in soal.malrule}) == len(soal.malrule), p
        assert {m.kode for m in soal.malrule} == {"K"} and len(nilai) >= PENGECOH_PERLU, p


def test_v2_malrule_contoh_tangan_utama():
    f = modul.pecahan_bilangan_asli_desimal
    s = f(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=0)
    ada = {m.id.split(".")[1]: m.jawaban for m in s.malrule}
    assert ada == {"kali_dua_sisi": "3/4", "kali_penyebut_saja": "3/20", "tambah_pembilang": "2",
                   "hasil_terbalik": "4/15", "pecahan_dibalik_lalu_dikali": "20/3"}
    s = f(varian="campur_ke_biasa", w=2, a=1, b=4)
    ada = {m.id.split(".")[1]: m.jawaban for m in s.malrule}
    assert ada == {"bulat_ditambah_pembilang": "3/4", "bulat_dikali_pembilang": "2/4",
                   "angka_berdampingan": "21/4", "pembilang_tidak_ditambah": "8/4",
                   "pembilang_penyebut_tertukar": "4/9"}
    s = f(varian="ke_desimal_berulang_dibulatkan", a=2, b=3)
    ada = {m.id.split(".")[1]: m.jawaban for m in s.malrule}
    assert ada["dipotong_tanpa_dibulatkan"] == "0,6" and ada["dua_angka_belakang_koma"] == "0,67"
    assert "dibulatkan_ke_atas" not in ada, "sama dengan jawaban benar dibuang"
    s = f(varian="desimal_ke_persen_pecahan", arah="ke_persen", perseratus=25)
    assert {m.jawaban for m in s.malrule} == {"2,5", "0,25", "250"}
    s = f(varian="desimal_ke_persen_pecahan", arah="ke_pecahan", perseratus=75)
    assert {m.jawaban for m in s.malrule} == {"4/3", "15/2", "3/40", "1/75"}


def test_v2_malrule_pembulatan_salah_arah_ada_untuk_pecahan_naik_dan_turun():
    soal_turun = modul.pecahan_bilangan_asli_desimal(varian="ke_desimal_berulang_dibulatkan", a=1, b=3)
    ada = {m.id.split(".")[1]: m.jawaban for m in soal_turun.malrule}
    assert ada["dibulatkan_ke_atas"] == "0,4" and "dipotong_tanpa_dibulatkan" not in ada
    naik = modul.pecahan_bilangan_asli_desimal(varian="ke_desimal_berulang_dibulatkan", a=5, b=6)
    ada = {m.id.split(".")[1]: m.jawaban for m in naik.malrule}
    assert ada["dibulatkan_ke_atas"] == "0,9" and "dipotong_tanpa_dibulatkan" not in ada


# ── pembahasan v2 ────────────────────────────────────────────────────────

def test_v2_pembahasan_dan_teks_bahasa_anak_dan_memuat_kunci():
    for p in _domain_v2():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert re.search(r"(?<![\w/,])" + re.escape(soal.kunci) + r"(?![\w/]|,\d)",
                         soal.pembahasan), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40 and "\n" not in soal.pembahasan and "\n" not in soal.teks
        assert soal.teks.endswith(")")


def test_v2_pembahasan_tak_wajar_menjelaskan_pembilang_lebih_besar_hanya_bila_pecahan():
    s = modul.pecahan_bilangan_asli_desimal(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=0)
    assert "lebih besar dari penyebut" in s.pembahasan and "15/4" in s.pembahasan
    s = modul.pecahan_bilangan_asli_desimal(varian="kali_asli_tak_wajar", a=3, b=4, n=8, urut=0)
    assert "lebih besar dari penyebut" not in s.pembahasan and "Sederhanakan 24/4" in s.pembahasan
    s = modul.pecahan_bilangan_asli_desimal(varian="bagi_asli_tak_wajar", a=5, b=3, n=2, bentuk="campur")
    assert "1 × 3 + 2 = 5" in s.pembahasan


def test_v2_nama_anak_hanya_dari_daftar_sintetis_umum():
    dikenal = re.compile(r"\b(Rina|Budi|Dita|Eko|Ani|Andi|Sari|Tono|Siti|Joko)\b")
    muncul = set()
    for p in _varian("cerita_kali_bagi_pecahan"):
        soal = _soal(p)
        muncul |= set(dikenal.findall(soal.teks + soal.pembahasan))
    assert muncul == {"Rina", "Budi", "Dita", "Eko"}, muncul


def test_v2_semua_tujuh_cerita_dan_operasinya_dijangkau():
    indeks = {p["cerita"] for p in _varian("cerita_kali_bagi_pecahan")}
    assert indeks == set(range(7))
    assert len(modul.CERITA_TAK_WAJAR) == 7 and len(modul.CERITA) == 4


# ── penolakan v2 ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="kali_asli_tak_wajar", a=1, b=4, n=2, urut=0),            # 1/2 < 1
    dict(varian="kali_asli_tak_wajar", a=2, b=4, n=5, urut=0),            # operan tak sederhana
    dict(varian="kali_asli_tak_wajar", a=3, b=4, n=5),                    # urut hilang
    dict(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=2),
    dict(varian="kali_asli_tak_wajar", a=3, b=4, n=5, urut=True),
    dict(varian="kali_asli_tak_wajar", a=3, b=4, n=1, urut=0),
    dict(varian="kali_asli_tak_wajar", a=3, b=4, n=13, urut=0),
    dict(varian="kali_asli_tak_wajar", a=5, b=4, n=5, urut=0),            # operan sudah tak wajar
    dict(varian="kali_asli_tak_wajar", a=1, b=13, n=12, urut=0),
    dict(varian="kali_asli_tak_wajar", a=3.0, b=4, n=5, urut=0),
    dict(varian="bagi_asli_tak_wajar", a=2, b=3, n=2, bentuk="biasa"),    # operan kurang dari 1
    dict(varian="bagi_asli_tak_wajar", a=5, b=3, n=2),                    # bentuk hilang
    dict(varian="bagi_asli_tak_wajar", a=5, b=3, n=2, bentuk="lain"),
    dict(varian="bagi_asli_tak_wajar", a=8, b=3, n=2, bentuk="biasa"),    # hasil 4/3 lebih dari 1
    dict(varian="bagi_asli_tak_wajar", a=6, b=3, n=2, bentuk="biasa"),    # tak sederhana
    dict(varian="bagi_asli_tak_wajar", a=13, b=12, n=12, bentuk="biasa"), # penyebut hasil 144
    dict(varian="bagi_asli_tak_wajar", a=5, b=3, n=1, bentuk="biasa"),
    dict(varian="bagi_asli_tak_wajar", a=9, b=3, n=2, bentuk="campur"),
    dict(varian="campur_ke_biasa", w=0, a=1, b=4),
    dict(varian="campur_ke_biasa", w=6, a=1, b=4),
    dict(varian="campur_ke_biasa", w=2, a=4, b=4),
    dict(varian="campur_ke_biasa", w=2, a=2, b=4),
    dict(varian="campur_ke_biasa", w=2, a=1, b=13),
    dict(varian="campur_ke_biasa", w=2, a=1),
    dict(varian="campur_ke_biasa", w=2.0, a=1, b=4),
    dict(varian="biasa_ke_campur", w=2, a=1, b=4),
    dict(varian="ke_desimal_berulang_dibulatkan", a=1, b=4),              # tengah pembulatan, berhenti
    dict(varian="ke_desimal_berulang_dibulatkan", a=1, b=8),
    dict(varian="ke_desimal_berulang_dibulatkan", a=3, b=9),              # tak sederhana
    dict(varian="ke_desimal_berulang_dibulatkan", a=1, b=13),
    dict(varian="ke_desimal_berulang_dibulatkan", a=3, b=3),
    dict(varian="ke_desimal_berulang_dibulatkan", a=1, b=3, n=2),
    dict(varian="desimal_ke_persen_pecahan", arah="ke_persen"),
    dict(varian="desimal_ke_persen_pecahan", perseratus=25),
    dict(varian="desimal_ke_persen_pecahan", arah="lain", perseratus=25),
    dict(varian="desimal_ke_persen_pecahan", arah="ke_persen", perseratus=0),
    dict(varian="desimal_ke_persen_pecahan", arah="ke_persen", perseratus=100),
    dict(varian="desimal_ke_persen_pecahan", arah="ke_pecahan", perseratus=33),
    dict(varian="desimal_ke_persen_pecahan", arah="ke_pecahan", perseratus=1),
    dict(varian="desimal_ke_persen_pecahan", arah="ke_persen", perseratus=25.0),
    dict(varian="cerita_kali_bagi_pecahan", cerita=7, a=3, b=4, n=3),
    dict(varian="cerita_kali_bagi_pecahan", cerita=-1, a=3, b=4, n=3),
    dict(varian="cerita_kali_bagi_pecahan", cerita=0, a=1, b=4, n=2),     # kali, hasil kurang dari 1
    dict(varian="cerita_kali_bagi_pecahan", cerita=4, a=1, b=11, n=3),    # bagi, penyebut hasil 33
    dict(varian="cerita_kali_bagi_pecahan", cerita=4, a=3, b=4),
    dict(varian="cerita_kali_bagi_pecahan", a=3, b=4, n=3),
])
def test_v2_parameter_tidak_sah_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.pecahan_bilangan_asli_desimal(**parameter)
