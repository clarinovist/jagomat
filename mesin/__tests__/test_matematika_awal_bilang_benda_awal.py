"""Matematika Awal, jenis bilang_benda_awal (P1): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang hanya
membaca TEKS soal; kata bilangan 1..10 dan bentuk kalimat ditulis ulang di tes ini,
bukan diimpor dari modul. Simbol "●" dihitung dari teks. Malrule hanya HIPOTESIS
kesalahan umum; yang dijaga: bukan kunci, tidak kembar, selalu ada jalur K, dan
cukup pengecoh untuk pilihan ganda.
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

import awal_bilang_benda_awal as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "bilang_benda_awal"
LEVEL = "P1"
SEED = range(200)
VARIAN = ("hitung", "sama_banyak", "kata_ke_angka", "angka_ke_kata",
          "antara", "satu_lebih", "satu_kurang")
UKURAN_PER_VARIAN = {"hitung": 40, "sama_banyak": 80, "kata_ke_angka": 10,
                     "angka_ke_kata": 10, "antara": 8, "satu_lebih": 9, "satu_kurang": 9}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # tetap benar untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis|intervensi", re.I)
SIMBOL = "●"
KATA_TES = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6,
            "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10}  # fakta tes, ditulis ulang
KATA_DARI_ANGKA = {v: k for k, v in KATA_TES.items()}
BENDA_TES = ("kelereng", "kancing", "bunga", "apel")


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; tidak memakai parameter atau konstanta modul."""
    cocok = re.fullmatch(r"Ada ((?:● )*●) (\w+) (.+)\. Berapa banyak \2\?", teks)
    if cocok:
        assert cocok.group(2) in BENDA_TES, teks
        return str(teks.count(SIMBOL))
    cocok = re.fullmatch(r"(\w+) punya ((?:● )*●) (\w+)\. (\w+) punya \3 sama banyak "
                         r"dengan \1\. Berapa \3 milik \4\?", teks)
    if cocok:
        assert cocok.group(1) != cocok.group(4), teks
        return str(teks.count(SIMBOL))
    cocok = re.fullmatch(r"(\w+) ditulis dengan angka \.\.\.", teks)
    if cocok:
        return str(KATA_TES[cocok.group(1).lower()])
    cocok = re.fullmatch(r"Angka (\d+) ditulis dengan kata \.\.\.", teks)
    if cocok:
        return KATA_DARI_ANGKA[int(cocok.group(1))]
    cocok = re.fullmatch(r"Bilangan yang lebih dari (\d+) dan kurang dari (\d+) adalah \.\.\.", teks)
    if cocok:
        a, b = int(cocok.group(1)), int(cocok.group(2))
        assert b - a == 2, ("tepat satu bilangan di antara batas", teks)
        return str(a + 1)
    cocok = re.fullmatch(r"Bilangan satu lebih banyak dari (\d+) adalah \.\.\.", teks)
    if cocok:
        return str(int(cocok.group(1)) + 1)
    cocok = re.fullmatch(r"Bilangan satu lebih sedikit dari (\d+) adalah \.\.\.", teks)
    if cocok:
        n = int(cocok.group(1))
        assert n >= 2, ("hasil harus >= 1", teks)
        return str(n - 1)
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(parameter: dict):
    return getattr(modul, TID)(**parameter)


def _jenis_kunci(soal) -> str:
    return "kategori" if soal.parameter["varian"] == "angka_ke_kata" else "angka"


def _pengecoh(soal) -> set:
    """Cermin choice_generation.kandidat: nilai bertipe, buang kunci, duplikat, negatif."""
    jenis = _jenis_kunci(soal)
    benar = nilai_semantis(soal.kunci, jenis)
    hasil = set()
    for m in soal.malrule:
        n = nilai_semantis(m.jawaban, jenis)
        if jenis == "angka" and n < 0:
            continue
        if n != benar:
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


def test_level_selain_p1_ditolak():
    for level in ("P2", "P3", "P4", "P5", "P6", "", None):
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
        if p["varian"] == "angka_ke_kata":
            assert soal.kunci in KATA_TES, soal.kunci
        else:
            assert re.fullmatch(r"[1-9]\d*", soal.kunci), soal.kunci
            assert 1 <= int(soal.kunci) <= 10


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.bilang_benda_awal
    hitung = f(varian="hitung", n=4, benda=0)
    assert hitung.teks == "Ada ● ● ● ● kelereng di dalam kotak. Berapa banyak kelereng?"
    assert hitung.kunci == "4"
    sama = f(varian="sama_banyak", n=3, anak=0, benda=1)
    assert sama.teks == ("Rina punya ● ● ● kancing. Budi punya kancing sama banyak "
                         "dengan Rina. Berapa kancing milik Budi?")
    assert sama.kunci == "3"
    assert f(varian="kata_ke_angka", n=7).teks == "Tujuh ditulis dengan angka ..."
    assert f(varian="kata_ke_angka", n=7).kunci == "7"
    assert f(varian="angka_ke_kata", n=7).teks == "Angka 7 ditulis dengan kata ..."
    assert f(varian="angka_ke_kata", n=7).kunci == "tujuh"
    assert f(varian="antara", a=6).teks == (
        "Bilangan yang lebih dari 6 dan kurang dari 8 adalah ...")
    assert f(varian="antara", a=6).kunci == "7"
    assert f(varian="satu_lebih", n=4).teks == "Bilangan satu lebih banyak dari 4 adalah ..."
    assert f(varian="satu_lebih", n=4).kunci == "5"
    assert f(varian="satu_kurang", n=4).teks == "Bilangan satu lebih sedikit dari 4 adalah ..."
    assert f(varian="satu_kurang", n=4).kunci == "3"


def test_simbol_dihitung_dari_teks_dan_tidak_dobel_di_keterangan():
    for p in _domain():
        soal = _soal(p)
        jumlah = soal.teks.count(SIMBOL)
        if p["varian"] in ("hitung", "sama_banyak"):
            assert jumlah == p["n"] == int(soal.kunci), (p, soal.teks)
            assert len(re.findall(r"●", soal.teks.split(".")[0])) == jumlah, "simbol hanya di kalimat pertama"
            assert not re.search(r"[●] (adalah|=|mewakili|berarti)", soal.teks)
        else:
            assert jumlah == 0, (p, soal.teks)
        assert SIMBOL not in soal.pembahasan, soal.pembahasan


def test_semua_tiga_sub_materi_bab_tertutup_oleh_varian():
    teks = [_soal(p).teks for p in _domain()]
    assert any(t.startswith("Ada ●") for t in teks), "membilang banyak benda"
    assert any("ditulis dengan angka" in t for t in teks), "membaca lambang bilangan"
    assert any("ditulis dengan kata" in t for t in teks), "menulis lambang bilangan"
    assert any("lebih dari" in t and "kurang dari" in t for t in teks), "lebih dari, kurang dari"
    assert any("lebih banyak" in t or "lebih sedikit" in t for t in teks)
    assert any("sama banyak" in t for t in teks), "sama dengan"


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


def test_jawaban_malrule_bertipe_sama_dengan_kunci_dan_tidak_negatif():
    for p in _domain():
        soal = _soal(p)
        for m in soal.malrule:
            if p["varian"] == "angka_ke_kata":
                assert m.jawaban in KATA_TES, (p, m.jawaban)
            else:
                assert re.fullmatch(r"(0|[1-9]\d*)", m.jawaban), (p, m.jawaban)
                batas = 20 if m.id.endswith("dua_anak_dijumlah") else 10
                assert int(m.jawaban) <= batas, (p, m.id, m.jawaban)
            if m.kode == "H" and p["varian"] != "angka_ke_kata":
                assert 0 <= int(m.jawaban) <= 10, (p, m.id)


def test_tiap_parameter_punya_cukup_pengecoh_untuk_pilihan_ganda_tiga_v1():
    for p in _domain():
        soal = _soal(p)
        assert len(_pengecoh(soal)) >= 2, (p, [m.jawaban for m in soal.malrule])


def test_dua_pengecoh_pertama_tidak_melewati_sepuluh_kecuali_jumlah_dua_anak():
    for p in _domain():
        soal = _soal(p)
        if p["varian"] == "angka_ke_kata":
            continue
        for m in soal.malrule[:2]:
            if not m.id.endswith("dua_anak_dijumlah"):
                assert int(m.jawaban) <= 10, (p, m.id)
            else:
                assert 2 * p["n"] <= 10, (p, "jumlah dua anak di atas 10 harus di urutan akhir")


def test_malrule_bernilai_benar_untuk_hipotesisnya():
    f = modul.bilang_benda_awal
    hitung = {m.id.split(".")[-1]: (m.jawaban, m.kode)
              for m in f(varian="hitung", n=5, benda=2).malrule}
    assert hitung == {"mulai_dari_nol": ("4", "K"), "terhitung_dua_kali": ("6", "H"),
                      "terlewat_dua_benda": ("3", "H"), "terhitung_dua_dua_kali": ("7", "H")}
    sama = {m.id.split(".")[-1]: (m.jawaban, m.kode)
            for m in f(varian="sama_banyak", n=4, anak=1, benda=0).malrule}
    assert sama["dua_anak_dijumlah"] == ("8", "K")
    kata = {m.jawaban: m.kode for m in f(varian="kata_ke_angka", n=6).malrule}
    assert kata == {"9": "K", "5": "H", "7": "H"}
    ke_kata = {m.jawaban: m.kode for m in f(varian="angka_ke_kata", n=6).malrule}
    assert ke_kata == {"sembilan": "K", "lima": "H", "tujuh": "H"}
    sepuluh = {m.jawaban: m.kode for m in f(varian="kata_ke_angka", n=10).malrule}
    assert sepuluh == {"1": "K", "9": "H"}
    antara = {m.jawaban: m.kode for m in f(varian="antara", a=6).malrule}
    assert antara == {"6": "K", "8": "K"}
    lebih = {m.jawaban: m.kode for m in f(varian="satu_lebih", n=4).malrule}
    assert lebih == {"3": "K", "4": "K", "6": "H"}
    kurang = {m.jawaban: m.kode for m in f(varian="satu_kurang", n=4).malrule}
    assert kurang == {"5": "K", "4": "K", "2": "H"}


def test_jumlah_dua_anak_di_depan_hanya_bila_masih_sampai_sepuluh():
    f = modul.bilang_benda_awal
    kecil = f(varian="sama_banyak", n=5, anak=0, benda=0).malrule
    besar = f(varian="sama_banyak", n=6, anak=0, benda=0).malrule
    assert kecil[0].id.endswith("dua_anak_dijumlah")
    assert besar[-1].id.endswith("dua_anak_dijumlah")


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 30 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        if p["varian"] == "angka_ke_kata":
            assert re.search(rf"\b{soal.kunci}\b", teks), teks
        else:
            assert soal.kunci in re.findall(r"\d+", teks), ("kunci tak muncul", teks)


def test_pembahasan_kata_bilangan_benar_untuk_kata_ke_angka():
    f = modul.bilang_benda_awal
    assert "tujuh ditulis dengan angka 7" in f(varian="kata_ke_angka", n=7).pembahasan
    assert "Angka 10 dibaca sepuluh" in f(varian="angka_ke_kata", n=10).pembahasan


def test_teks_satu_baris_satu_pertanyaan_dan_nama_sintetis():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        assert teks.count("...") <= 1
        assert (teks.count("...") + teks.count("?")) == 1, teks


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", n=2),
    dict(varian="hitung"),
    dict(varian="hitung", n=0, benda=0),
    dict(varian="hitung", n=11, benda=0),
    dict(varian="hitung", n=True, benda=0),
    dict(varian="hitung", n="3", benda=0),
    dict(varian="hitung", n=3.0, benda=0),
    dict(varian="hitung", n=3, benda=4),
    dict(varian="hitung", n=3, benda=-1),
    dict(varian="hitung", n=3),
    dict(varian="hitung", n=3, benda=0, anak=0),
    dict(varian="sama_banyak", n=3, anak=2, benda=0),
    dict(varian="sama_banyak", n=3, benda=0),
    dict(varian="kata_ke_angka", n=0),
    dict(varian="kata_ke_angka", n=11),
    dict(varian="angka_ke_kata", n=11),
    dict(varian="antara", a=0),
    dict(varian="antara", a=9),
    dict(varian="satu_lebih", n=10),
    dict(varian="satu_lebih", n=0),
    dict(varian="satu_kurang", n=1),
    dict(varian="satu_kurang", n=11),
    dict(varian=["hitung"], n=2, benda=0),
    dict(varian=None, n=2),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.bilang_benda_awal(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_bilang_benda_awal as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P1")
    s = m.bilang_benda_awal(**p)
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
