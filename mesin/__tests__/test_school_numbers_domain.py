"""Bilangan Sekolah, jenis nilai_tempat_besar (Tahap A): domain, solver, malrule.

Kunci dicek oleh solver TERPISAH yang hanya membaca teks soal (regex), bukan
parameter dan bukan kode template. Malrule hanya HIPOTESIS kesalahan umum;
yang dijaga di sini: bukan kunci, tidak kembar, dan memang dua jalur K.
"""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import generator
import topics
from templates import REGISTRI, Soal

TOPIK = "bilangan-sekolah"
TID = "nilai_tempat_besar"
LEVEL = ("P3", "P4", "P5")
SEED = range(25)
RENTANG = {"P3": (100, 999), "P4": (1000, 9999), "P5": (10000, 999999)}
VARIAN = ("nilai_angka", "lengkapi_panjang", "susun_panjang")
AKAR_MESIN = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def sakelar_hidup(monkeypatch):
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")


def _angka(teks: str) -> int:
    return int(teks.replace(".", ""))


def _soal(level: str, seed: int) -> Soal:
    paket = topics.ambil(TOPIK)
    return generator._soal_layak(paket, TID, random.Random(seed), level)


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; sengaja tidak memakai parameter atau modul topik."""
    cocok = re.fullmatch(r"Nilai angka (\d) pada bilangan ([\d.]+) adalah \.\.\.", teks)
    if cocok:
        digit, bilangan = cocok.group(1), str(_angka(cocok.group(2)))
        assert bilangan.count(digit) == 1, "angka yang ditanya harus tunggal"
        return str(int(digit) * 10 ** (len(bilangan) - 1 - bilangan.index(digit)))
    cocok = re.fullmatch(r"Lengkapi bentuk panjang: ([\d.]+) = (.+)", teks)
    if cocok:
        bagian = cocok.group(2).split(" + ")
        assert bagian.count("...") == 1
        sisa = sum(_angka(b) for b in bagian if b != "...")
        return str(_angka(cocok.group(1)) - sisa)
    cocok = re.fullmatch(r"Tulis sebagai satu bilangan: (.+) = \.\.\.", teks)
    if cocok:
        return str(sum(_angka(b) for b in cocok.group(1).split(" + ")))
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


# ── domain ───────────────────────────────────────────────────────────────

def test_topik_terdaftar_tiga_level_memuat_nilai_tempat_besar():
    paket = topics.ambil(TOPIK)
    assert tuple(paket.komposisi) == LEVEL
    for level in LEVEL:
        assert TID in paket.komposisi[level]
    assert TID in paket.templates
    assert TID in topics.registri() and TID in REGISTRI
    assert paket.hanya_manual is True
    assert not paket.unik_per_lembar


@pytest.mark.parametrize("level", LEVEL)
def test_rentang_bilangan_mengikuti_level(level):
    bawah, atas = RENTANG[level]
    for seed in SEED:
        soal = _soal(level, seed)
        n = soal.parameter["bilangan"]
        assert bawah <= n <= atas, (level, seed, n)
        assert len(set(str(n))) == len(str(n)), "angka tidak boleh berulang"
        assert str(n)[0] != "0"


def test_p5_memakai_lima_dan_enam_angka():
    panjang = {len(str(_soal("P5", s).parameter["bilangan"])) for s in range(60)}
    assert panjang == {5, 6}


@pytest.mark.parametrize("level", LEVEL)
def test_ketiga_bentuk_muncul_dan_posisi_bukan_satuan(level):
    ditemui = set()
    for seed in range(80):
        p = _soal(level, seed).parameter
        ditemui.add(p["varian"])
        if "posisi" in p:
            assert 1 <= p["posisi"] < len(str(p["bilangan"]))
    assert ditemui == set(VARIAN)


@pytest.mark.parametrize("level", LEVEL)
def test_bentuk_panjang_tanpa_angka_nol(level):
    for seed in range(80):
        p = _soal(level, seed).parameter
        if p["varian"] != "nilai_angka":
            assert "0" not in str(p["bilangan"])


@pytest.mark.parametrize("level", LEVEL)
def test_angka_nol_boleh_muncul_hanya_di_nilai_angka_dan_tidak_ditanya(level):
    ada_nol = False
    for seed in range(120):
        p = _soal(level, seed).parameter
        if p["varian"] != "nilai_angka":
            continue
        n = str(p["bilangan"])
        ada_nol = ada_nol or "0" in n
        ditanya = n[len(n) - 1 - p["posisi"]]
        assert ditanya != "0", "angka yang ditanya tidak boleh 0 (kunci 0 = angka saja)"
    assert ada_nol, "nol di posisi lain perlu ikut diuji pada nilai_angka"


# ── solver terpisah ──────────────────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_kunci_sama_dengan_solver_dari_teks(level):
    for seed in SEED:
        soal = _soal(level, seed)
        assert soal.kunci == solver_dari_teks(soal.teks), (level, seed, soal.teks)
        assert soal.kunci.isdigit() and not soal.kunci.startswith("0")


def test_kunci_contoh_tangan():
    f = REGISTRI[TID]
    assert f(varian="nilai_angka", bilangan=4372, posisi=2).kunci == "300"
    assert f(varian="nilai_angka", bilangan=4372, posisi=3).kunci == "4000"
    assert f(varian="nilai_angka", bilangan=4372, posisi=1).kunci == "70"
    assert f(varian="lengkapi_panjang", bilangan=4372, posisi=2).kunci == "300"
    assert f(varian="susun_panjang", bilangan=4372).kunci == "4372"
    assert f(varian="nilai_angka", bilangan=506, posisi=2).kunci == "500"
    assert f(varian="nilai_angka", bilangan=243561, posisi=5).kunci == "200000"
    assert f(varian="nilai_angka", bilangan=243561, posisi=3).kunci == "3000"


def test_teks_memakai_titik_ribuan_dan_kunci_angka_polos():
    f = REGISTRI[TID]
    soal = f(varian="nilai_angka", bilangan=234567, posisi=4)
    assert soal.teks == "Nilai angka 3 pada bilangan 234.567 adalah ..."
    assert soal.kunci == "30000"
    soal = f(varian="lengkapi_panjang", bilangan=4372, posisi=2)
    assert soal.teks == "Lengkapi bentuk panjang: 4.372 = 4.000 + ... + 70 + 2"
    soal = f(varian="susun_panjang", bilangan=4372)
    assert soal.teks == "Tulis sebagai satu bilangan: 4.000 + 300 + 70 + 2 = ..."


# ── malrule ──────────────────────────────────────────────────────────────

def _digit_dan_tempat(soal):
    p = soal.parameter
    n = str(p["bilangan"])
    return int(n[len(n) - 1 - p["posisi"]]), p["posisi"], len(n) - 1


@pytest.mark.parametrize("level", LEVEL)
def test_malrule_bukan_kunci_tidak_kembar_dan_dua_jalur_k(level):
    for seed in SEED:
        soal = _soal(level, seed)
        jawaban = [m.jawaban for m in soal.malrule]
        assert soal.kunci not in jawaban, (level, seed)
        assert len(set(jawaban)) == len(jawaban), (level, seed, jawaban)
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert sum(m.kode == "K" for m in soal.malrule) >= 2, (level, seed)
        assert all(m.alasan.strip() for m in soal.malrule)


def test_dua_jalur_k_selalu_ada_pada_sapu_besar():
    for level in LEVEL:
        for seed in range(400):
            soal = _soal(level, seed)
            assert sum(m.kode == "K" for m in soal.malrule) >= 2, (level, seed, soal.teks)


@pytest.mark.parametrize("level", LEVEL)
def test_nilai_angka_malrule_angka_saja_dan_tetangga(level):
    ada_atas = ada_bawah = False
    for seed in range(300):
        soal = _soal(level, seed)
        if soal.parameter["varian"] not in ("nilai_angka", "lengkapi_panjang"):
            continue
        d, p, atas = _digit_dan_tempat(soal)
        peta = {m.id: m for m in soal.malrule}
        saja = peta["nilai_tempat_besar.angka_saja"]
        assert saja.jawaban == str(d) and saja.kode == "K"
        tetangga = peta["nilai_tempat_besar.tempat_tetangga"]
        assert tetangga.kode == "K"
        harapan = d * 10 ** (p + 1) if p < atas else d * 10 ** (p - 1)
        assert tetangga.jawaban == str(harapan)
        ada_atas = ada_atas or p < atas
        ada_bawah = ada_bawah or p == atas
        for m in soal.malrule:
            assert m.jawaban in {str(d), str(d * 10 ** (p + 1)), str(d * 10 ** (p - 1))}
    assert ada_atas and ada_bawah, "kedua arah tetangga harus teruji"


def test_posisi_puluhan_tetap_punya_dua_jalur_k():
    # Tetangga bawah puluhan = d x 1 = angka saja; tetangga yang dipakai harus atas.
    soal = REGISTRI[TID](varian="nilai_angka", bilangan=4372, posisi=1)
    kode = {m.id: (m.kode, m.jawaban) for m in soal.malrule}
    assert kode["nilai_tempat_besar.angka_saja"] == ("K", "7")
    assert kode["nilai_tempat_besar.tempat_tetangga"] == ("K", "700")


def test_posisi_teratas_memakai_tetangga_bawah():
    soal = REGISTRI[TID](varian="nilai_angka", bilangan=4372, posisi=3)
    kode = {m.id: (m.kode, m.jawaban) for m in soal.malrule}
    assert kode["nilai_tempat_besar.angka_saja"] == ("K", "4")
    assert kode["nilai_tempat_besar.tempat_tetangga"] == ("K", "400")


def test_susun_panjang_malrule_angka_dijumlah_dan_tertukar():
    soal = REGISTRI[TID](varian="susun_panjang", bilangan=4372)
    peta = {m.id: m for m in soal.malrule}
    assert peta["nilai_tempat_besar.angka_dijumlah"].jawaban == str(4 + 3 + 7 + 2)
    assert peta["nilai_tempat_besar.angka_teratas_tertukar"].jawaban == "3472"
    assert {m.kode for m in (peta["nilai_tempat_besar.angka_dijumlah"],
                             peta["nilai_tempat_besar.angka_teratas_tertukar"])} == {"K"}


@pytest.mark.parametrize("level", LEVEL)
def test_susun_panjang_malrule_semua_sah(level):
    for seed in range(300):
        soal = _soal(level, seed)
        if soal.parameter["varian"] != "susun_panjang":
            continue
        n = str(soal.parameter["bilangan"])
        harapan = {str(sum(map(int, n))), n[1] + n[0] + n[2:], str(int(n) - int(n[-1]))}
        assert {m.jawaban for m in soal.malrule} <= harapan
        assert {m.id for m in soal.malrule} >= {
            "nilai_tempat_besar.angka_dijumlah", "nilai_tempat_besar.angka_teratas_tertukar"}


# ── validasi masukan ─────────────────────────────────────────────────────

@pytest.mark.parametrize("kwargs", [
    dict(varian="tidak_ada", bilangan=4372, posisi=2),
    dict(varian="nilai_angka", bilangan=4372, posisi=0),      # satuan: angka saja = kunci
    dict(varian="nilai_angka", bilangan=4372, posisi=4),      # di luar bilangan
    dict(varian="nilai_angka", bilangan=4372, posisi=-1),
    dict(varian="nilai_angka", bilangan=4372, posisi=True),
    dict(varian="nilai_angka", bilangan=4372, posisi="2"),
    dict(varian="nilai_angka", bilangan=4372),                 # posisi wajib
    dict(varian="nilai_angka", bilangan=4372.0, posisi=2),
    dict(varian="nilai_angka", bilangan="4372", posisi=2),
    dict(varian="nilai_angka", bilangan=4772, posisi=2),       # angka berulang
    dict(varian="nilai_angka", bilangan=99, posisi=1),         # terlalu pendek
    dict(varian="nilai_angka", bilangan=1000000, posisi=3),    # terlalu besar
    dict(varian="nilai_angka", bilangan=4072, posisi=2),       # angka yang ditanya 0
    dict(varian="lengkapi_panjang", bilangan=4072, posisi=2),  # bentuk panjang tanpa nol
    dict(varian="lengkapi_panjang", bilangan=4372, posisi=0),
    dict(varian="susun_panjang", bilangan=4072),
    dict(varian="susun_panjang", bilangan=4372, posisi=2),     # posisi tidak dipakai
    dict(varian="susun_panjang", bilangan=4472),
    dict(varian=None, bilangan=4372),
])
def test_parameter_di_luar_domain_ditolak(kwargs):
    with pytest.raises(ValueError):
        REGISTRI[TID](**kwargs)


def test_tempat_nol_di_nilai_angka_sah_selama_tidak_ditanya():
    soal = REGISTRI[TID](varian="nilai_angka", bilangan=4072, posisi=3)
    assert soal.kunci == "4000"
    assert soal.teks == "Nilai angka 4 pada bilangan 4.072 adalah ..."


# ── pembahasan ───────────────────────────────────────────────────────────

ISTILAH_GURU = ("malrule", "diagnosis", "miskonsepsi", "kode K", "hipotesis")


@pytest.mark.parametrize("level", LEVEL)
def test_pembahasan_kalimat_penuh_benar_dan_ramah_anak(level):
    for seed in SEED:
        soal = _soal(level, seed)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks.split(".")) >= 2 and len(teks) > 60, teks
        assert "None" not in teks and "{" not in teks
        assert not any(k in teks.lower() for k in ISTILAH_GURU)
        angka = {m.replace(".", "") for m in re.findall(r"\d[\d.]*\d|\d", teks)}
        assert soal.kunci in angka, ("kunci tidak muncul di pembahasan", teks)
        assert soal.bagian == "A"


def test_pembahasan_contoh_tangan():
    f = REGISTRI[TID]
    assert f(varian="nilai_angka", bilangan=4372, posisi=2).pembahasan == (
        "Pada 4.372, angka 3 berada di tempat ratusan, jadi nilainya 3 × 100 = 300. "
        "Jadi nilai angka 3 adalah 300.")
    assert f(varian="lengkapi_panjang", bilangan=4372, posisi=2).pembahasan == (
        "Setiap angka dikalikan nilai tempatnya: 4 × 1.000 = 4.000, 3 × 100 = 300, "
        "7 × 10 = 70, dan 2 × 1 = 2. Bagian yang hilang adalah angka 3 di tempat ratusan, "
        "yaitu 3 × 100 = 300. Cek: 4.000 + 300 + 70 + 2 = 4.372.")
    assert f(varian="susun_panjang", bilangan=4372).pembahasan == (
        "Jumlahkan semua bagian: 4.000 + 300 + 70 + 2 = 4.372. "
        "Jadi bilangan yang terbentuk adalah 4.372.")


# ── determinisme ─────────────────────────────────────────────────────────

def test_seed_sama_soal_sama_dan_seed_beda_bervariasi():
    for level in LEVEL:
        assert _soal(level, 5).tanda_tangan == _soal(level, 5).tanda_tangan
        assert len({_soal(level, s).tanda_tangan for s in range(60)}) >= 50


_PROSES = (
    "import os,sys,random\n"
    "sys.path.insert(0, %r)\n"
    "os.environ['OSN_BILANGAN_SEKOLAH']='1'\n"
    "import generator\n"
    "for lv in ('P3','P4','P5'):\n"
    "    for seed in range(25):\n"
    "        print(generator.buat_lembar(seed, level=lv, topik='bilangan-sekolah').tanda_tangan)\n"
)


def _jalankan(hashseed: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("OSN_BILANGAN")}
    env["PYTHONHASHSEED"] = hashseed
    hasil = subprocess.run([sys.executable, "-c", _PROSES % str(AKAR_MESIN)], env=env,
                           capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return hasil.stdout


def test_lembar_identik_lintas_pythonhashseed():
    keluaran = {_jalankan(h) for h in ("0", "1", "12345")}
    assert len(keluaran) == 1
    assert len(next(iter(keluaran)).splitlines()) == 75


def test_sumber_tidak_memakai_hash_bawaan():
    for nama in ("topic_school_numbers.py", "school_numbers_versions.py", "school_numbers_common.py",
                 "school_numbers_order.py", "school_numbers_column.py", "school_numbers_muldiv.py",
                 "school_numbers_equation.py"):
        sumber = (AKAR_MESIN / nama).read_text(encoding="utf-8")
        assert not re.search(r"(?<![\w.])hash\(", sumber), nama


# ── sapu seed x level lewat jalur resmi ──────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_sapu_seed_0_24_lembar_dan_render(level):
    paket = topics.ambil(TOPIK)
    for seed in SEED:
        lembar = generator.buat_lembar(seed, level=level, topik=TOPIK)
        assert len(lembar.soal) == len(paket.komposisi_untuk(level))
        milik_tahap_a = [s for s in lembar.soal if s.template_id == TID]
        assert len(milik_tahap_a) == 2
        for soal in milik_tahap_a:
            assert soal.level == level
            assert soal.malrule, (level, seed)
            assert soal.kunci == solver_dari_teks(soal.teks)
            ulang = replace(REGISTRI[TID](**soal.parameter), level=level)
            assert ulang.tanda_tangan == soal.tanda_tangan and ulang.kunci == soal.kunci
        assert generator.buat_lembar(seed, level=level, topik=TOPIK).tanda_tangan == lembar.tanda_tangan


def test_parameter_untuk_satu_pemilik_dan_level_asing_ditolak():
    paket = topics.ambil(TOPIK)
    rng = random.Random(1)
    with pytest.raises(KeyError):
        paket.parameter_untuk("template_lain", rng, "P3")
    with pytest.raises(ValueError):
        paket.parameter_untuk(TID, rng, "P6")
