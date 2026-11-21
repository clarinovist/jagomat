"""Matematika Awal, jenis ukur_konversi_awal (P3): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang
hanya membaca TEKS soal; hubungan satuan (1 m = 100 cm, 1 kg = 1.000 g) ditulis ulang
di tes ini, bukan diimpor dari modul. Malrule hanya HIPOTESIS kesalahan umum; yang
dijaga: bukan kunci, tidak kembar, selalu ada jalur K, dan cukup pengecoh angka.
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

import awal_ukur_konversi_awal as modul
from diagnosis import normalisasi, setara
from multiple_choice import nilai_semantis

TID = "ukur_konversi_awal"
LEVEL = "P3"
SEED = range(200)
VARIAN = ("m_ke_cm", "cm_ke_m", "kg_ke_g", "g_ke_kg", "sisa_potong", "jumlah_campur")
UKURAN_PER_VARIAN = {"m_ke_cm": 9, "cm_ke_m": 9, "kg_ke_g": 9, "g_ke_kg": 9,
                     "sisa_potong": 27, "jumlah_campur": 135}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # mesin/, tetap benar untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)
CM_PER_M = 100  # fakta tes, sengaja ditulis ulang
G_PER_KG = 1000


def _angka(teks: str) -> int:
    return int(teks.replace(".", ""))


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; tidak memakai parameter atau konstanta modul."""
    cocok = re.fullmatch(r"(\d+) m = \.\.\. cm", teks)
    if cocok:
        return str(int(cocok.group(1)) * CM_PER_M)
    cocok = re.fullmatch(r"([\d.]+) cm = \.\.\. m", teks)
    if cocok:
        cm = _angka(cocok.group(1))
        assert cm % CM_PER_M == 0, ("cm harus kelipatan 100", teks)
        return str(cm // CM_PER_M)
    cocok = re.fullmatch(r"(\d+) kg = \.\.\. g", teks)
    if cocok:
        return str(int(cocok.group(1)) * G_PER_KG)
    cocok = re.fullmatch(r"([\d.]+) g = \.\.\. kg", teks)
    if cocok:
        g = _angka(cocok.group(1))
        assert g % G_PER_KG == 0, ("g harus kelipatan 1.000", teks)
        return str(g // G_PER_KG)
    cocok = re.fullmatch(r"(\w+) 1 m dipotong (\d+) cm\. Sisa \1 ada \.\.\. cm\.", teks,
                         re.IGNORECASE)
    if cocok:
        sisa = CM_PER_M - int(cocok.group(2))
        assert sisa > 0, ("tali habis atau minus", teks)
        return str(sisa)
    cocok = re.fullmatch(r"(.+) beratnya (\d+) kg (\d+) g\. Berapa gram semuanya\?", teks)
    if cocok:
        assert 0 < int(cocok.group(3)) < G_PER_KG, ("g harus kurang dari 1 kg", teks)
        return str(int(cocok.group(2)) * G_PER_KG + int(cocok.group(3)))
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


def test_level_selain_p3_ditolak():
    for level in ("P1", "P2", "P4", "P5", "P6", "", None):
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
        assert re.fullmatch(r"[1-9]\d*", soal.kunci), ("kunci angka polos tanpa spasi/titik", soal.kunci)


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.ukur_konversi_awal
    assert f(varian="m_ke_cm", m=2).teks == "2 m = ... cm"
    assert f(varian="m_ke_cm", m=2).kunci == "200"
    assert f(varian="cm_ke_m", cm=700).teks == "700 cm = ... m"
    assert f(varian="cm_ke_m", cm=700).kunci == "7"
    assert f(varian="kg_ke_g", kg=3).teks == "3 kg = ... g"
    assert f(varian="kg_ke_g", kg=3).kunci == "3000"
    assert f(varian="g_ke_kg", gram=4000).teks == "4.000 g = ... kg"
    assert f(varian="g_ke_kg", gram=4000).kunci == "4"
    sisa = f(varian="sisa_potong", potong=40, benda=0)
    assert sisa.teks == "Tali 1 m dipotong 40 cm. Sisa tali ada ... cm."
    assert sisa.kunci == "60"
    campur = f(varian="jumlah_campur", kg=2, sisa_g=500, benda=0)
    assert campur.teks == "Sebuah kardus beratnya 2 kg 500 g. Berapa gram semuanya?"
    assert campur.kunci == "2500"


def test_jawaban_ribuan_bertitik_dan_polos_sama_sama_benar():
    soal = modul.ukur_konversi_awal(varian="kg_ke_g", kg=3)
    for ketikan in ("3000", "3.000", " 3 000 ", "3000 g"):
        assert setara(ketikan, soal.kunci, soal=soal) or normalisasi(ketikan) == "3000 g", ketikan
    assert setara("3.000", soal.kunci, soal=soal)
    assert not setara("300", soal.kunci, soal=soal)


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


def test_tiap_parameter_punya_cukup_pengecoh_angka_untuk_pilihan_ganda():
    for p in _domain():
        soal = _soal(p)
        assert len(_pengecoh_angka(soal)) >= 3, (p, [m.jawaban for m in soal.malrule])


def test_malrule_bernilai_benar_untuk_hipotesisnya():
    f = modul.ukur_konversi_awal
    jawaban = {m.id.split(".")[-1]: (m.jawaban, m.kode)
               for m in f(varian="m_ke_cm", m=3).malrule}
    assert ("30", "K") in jawaban.values() and ("3000", "K") in jawaban.values()
    assert ("3", "K") in jawaban.values()
    h = {m.jawaban for m in f(varian="jumlah_campur", kg=2, sisa_g=500, benda=0).malrule
         if m.kode == "H"}
    assert "2000" in h, "lupa menambah bagian gram"
    sisa = {m.jawaban: m.kode for m in f(varian="sisa_potong", potong=40, benda=0).malrule}
    assert sisa["960"] == "K" and sisa["140"] == "H"


def test_bagian_gram_terlupa_hanya_h_dan_bukan_satu_satunya_jalur():
    for p in _domain():
        if p["varian"] != "jumlah_campur":
            continue
        soal = _soal(p)
        h = {m.jawaban for m in soal.malrule if m.kode == "H"}
        assert h <= {str(p["kg"] * 1000)}, (p, h)
        assert len([m for m in soal.malrule if m.kode == "K"]) >= 2


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 40 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        angka = {m.replace(".", "") for m in re.findall(r"\d[\d.]*\d|\d", teks)}
        assert soal.kunci in angka, ("kunci tidak muncul di pembahasan", teks)


def test_pembahasan_menyebut_hubungan_satuan_yang_benar():
    f = modul.ukur_konversi_awal
    assert "1 m sama dengan 100 cm" in f(varian="m_ke_cm", m=2).pembahasan
    assert "1 kg sama dengan 1.000 g" in f(varian="kg_ke_g", kg=2).pembahasan
    assert "1 m sama dengan 100 cm" in f(varian="sisa_potong", potong=40, benda=1).pembahasan
    assert "1 kg sama dengan 1.000 g" in f(
        varian="jumlah_campur", kg=2, sisa_g=500, benda=2).pembahasan


def test_teks_tanpa_gambar_nama_anak_dan_satu_pertanyaan():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        assert teks.count("...") <= 1


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", m=2),
    dict(varian="m_ke_cm"),
    dict(varian="m_ke_cm", m=0),
    dict(varian="m_ke_cm", m=10),
    dict(varian="m_ke_cm", m=True),
    dict(varian="m_ke_cm", m="2"),
    dict(varian="m_ke_cm", m=2.0),
    dict(varian="m_ke_cm", m=2, cm=200),
    dict(varian="cm_ke_m", cm=150),
    dict(varian="cm_ke_m", cm=1000),
    dict(varian="cm_ke_m", cm=0),
    dict(varian="kg_ke_g", kg=10),
    dict(varian="kg_ke_g", kg=-1),
    dict(varian="g_ke_kg", gram=1500),
    dict(varian="g_ke_kg", gram=10000),
    dict(varian="sisa_potong", potong=100, benda=0),
    dict(varian="sisa_potong", potong=45, benda=0),
    dict(varian="sisa_potong", potong=40, benda=3),
    dict(varian="sisa_potong", potong=40),
    dict(varian="jumlah_campur", kg=6, sisa_g=500, benda=0),
    dict(varian="jumlah_campur", kg=2, sisa_g=1000, benda=0),
    dict(varian="jumlah_campur", kg=2, sisa_g=550, benda=0),
    dict(varian="jumlah_campur", kg=2, sisa_g=500, benda=-1),
    dict(varian="jumlah_campur", kg=2, sisa_g=500),
    dict(varian=["m_ke_cm"], m=2),
    dict(varian=None, m=2),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.ukur_konversi_awal(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_ukur_konversi_awal as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P3")
    s = m.ukur_konversi_awal(**p)
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
