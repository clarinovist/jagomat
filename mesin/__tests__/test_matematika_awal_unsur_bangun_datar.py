"""Matematika Awal, jenis unsur_bangun_datar (P3): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang hanya
membaca TEKS soal dengan tabel fakta yang ditulis ulang di tes ini (bukan diimpor dari
modul). Fakta geometri yang dipakai ditandai untuk ulasan Mutia di docstring modul.
Malrule hanya HIPOTESIS kesalahan umum; yang dijaga: bukan kunci, tidak kembar, selalu
ada jalur K, dan cukup pengecoh untuk pilihan ganda.
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

import awal_unsur_bangun_datar as modul
from diagnosis import normalisasi, setara
from multiple_choice import nilai_semantis

TID = "unsur_bangun_datar"
LEVEL = "P3"
SEED = range(200)
VARIAN = ("banyak_sisi", "banyak_sudut", "sudut_siku", "pasang_sejajar",
          "pasang_tegak_lurus", "istilah")
UKURAN_PER_VARIAN = {"banyak_sisi": 15, "banyak_sudut": 15, "sudut_siku": 9,
                     "pasang_sejajar": 6, "pasang_tegak_lurus": 6, "istilah": 6}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # mesin/, juga untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)
# Fakta tes (sengaja ditulis ulang, bukan diimpor).
SISI_SUDUT = {"segitiga": 3, "persegi": 4, "persegi panjang": 4, "segilima": 5, "segienam": 6}
SUDUT_SIKU = {"persegi": 4, "persegi panjang": 4, "segitiga siku-siku": 1}
# Bangun dicari dari yang terpanjang supaya "persegi panjang" tidak terbaca "persegi".
URUT_NAMA = sorted(set(SISI_SUDUT) | set(SUDUT_SIKU), key=len, reverse=True)
DILARANG_KELAS_4_5 = ("jajar genjang", "trapesium", "belah ketupat", "layang", "simetri",
                      "derajat", "diagonal")


def _soal(parameter: dict):
    return getattr(modul, TID)(**parameter)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _bangun_dalam(teks: str) -> str:
    for nama in URUT_NAMA:
        if nama in teks.lower():
            return nama
    raise AssertionError("tidak ada nama bangun: " + teks)


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; tidak memakai parameter atau konstanta modul."""
    if teks.endswith("garis ..."):
        return _istilah_dari_teks(teks)
    bangun = _bangun_dalam(teks)
    if "sudut siku-siku" in teks.replace("segitiga siku-siku", ""):
        assert bangun in SUDUT_SIKU, teks
        return str(SUDUT_SIKU[bangun])
    if "tegak lurus" in teks:
        assert bangun in ("persegi", "persegi panjang") and "bersebelahan" in teks, teks
        return "4"
    if "sejajar" in teks:
        assert bangun in ("persegi", "persegi panjang"), teks
        return "2"
    assert bangun in SISI_SUDUT, teks
    assert re.search(r"\bsisi\b|\bsudut\b", teks), teks
    return str(SISI_SUDUT[bangun])


def _istilah_dari_teks(teks: str) -> str:
    siku = "sudut siku-siku" in teks
    sejajar = re.search(r"tidak (pernah|akan) (berpotongan|bertemu)", teks) is not None
    assert siku != sejajar, ("teks istilah harus tepat satu ciri", teks)
    return "tegak lurus" if siku else "sejajar"


def _pengecoh(soal, jenis: str) -> set:
    benar = nilai_semantis(soal.kunci, jenis)
    hasil = set()
    for m in soal.malrule:
        n = nilai_semantis(m.jawaban, jenis)
        if n != benar:
            hasil.add(n)
    for tambahan in modul.pengecoh_tambahan(soal.parameter):
        n = nilai_semantis(tambahan, jenis)
        if n != benar:
            hasil.add(n)
    return hasil


def _jenis_kunci(soal) -> str:
    return "kategori" if soal.parameter["varian"] == "istilah" else "angka"


# ── kontrak modul dan domain ─────────────────────────────────────────────

def test_kontrak_modul_nama_dan_level():
    assert modul.TEMPLATE_ID == TID
    assert tuple(modul.LEVEL) == (LEVEL,)
    assert callable(getattr(modul, TID))
    assert modul.TEMPLATE_ID == getattr(modul, TID).__name__


def test_domain_ukuran_per_varian_tanpa_duplikat():
    domain = _domain()
    assert len(domain) == UKURAN_DOMAIN >= 40
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"
    for varian, ukuran in UKURAN_PER_VARIAN.items():
        assert sum(1 for p in domain if p["varian"] == varian) == ukuran, varian
    assert {p["varian"] for p in domain} == set(VARIAN)


def test_domain_hanya_bangun_sah_dan_tanpa_bangun_kelas_4_5():
    bangun = {p["bangun"] for p in _domain() if "bangun" in p}
    assert bangun == set(SISI_SUDUT) | set(SUDUT_SIKU)
    for p in _domain():
        teks = _soal(p).teks.lower() + " " + _soal(p).pembahasan.lower()
        assert not any(kata in teks for kata in DILARANG_KELAS_4_5), teks


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


def test_sampler_murni_dari_rng_seed_sama_hasil_sama_dan_beragam():
    a = [modul.parameter(random.Random(s), LEVEL) for s in SEED]
    b = [modul.parameter(random.Random(s), LEVEL) for s in SEED]
    assert a == b
    assert len({json.dumps(p, sort_keys=True) for p in a}) > 40


def test_sampler_membagi_varian_hampir_seragam():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(1200):
        hitung[modul.parameter(random.Random(seed), LEVEL)["varian"]] += 1
    assert all(150 < n < 250 for n in hitung.values()), hitung


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
        assert re.fullmatch(r"[1-9]\d?|sejajar|tegak lurus", soal.kunci), soal.kunci


def test_kunci_fakta_contoh_tangan_dan_teks_persis():
    f = modul.unsur_bangun_datar
    assert f(varian="banyak_sisi", bangun="segilima", gaya=0).teks == "Berapa banyak sisi segilima?"
    assert f(varian="banyak_sisi", bangun="segilima", gaya=0).kunci == "5"
    assert f(varian="banyak_sudut", bangun="segienam", gaya=1).teks == "Segienam mempunyai ... sudut."
    assert f(varian="banyak_sudut", bangun="segienam", gaya=1).kunci == "6"
    assert f(varian="banyak_sisi", bangun="segitiga", gaya=2).kunci == "3"
    assert f(varian="banyak_sisi", bangun="persegi panjang", gaya=0).kunci == "4"
    assert f(varian="sudut_siku", bangun="persegi", gaya=0).kunci == "4"
    assert f(varian="sudut_siku", bangun="segitiga siku-siku", gaya=1).teks == (
        "Segitiga siku-siku mempunyai ... sudut siku-siku.")
    assert f(varian="sudut_siku", bangun="segitiga siku-siku", gaya=1).kunci == "1"
    assert f(varian="pasang_sejajar", bangun="persegi panjang", gaya=0).kunci == "2"
    assert f(varian="pasang_tegak_lurus", bangun="persegi", gaya=0).kunci == "4"
    assert f(varian="istilah", istilah="sejajar", gaya=0).kunci == "sejajar"
    assert f(varian="istilah", istilah="tegak lurus", gaya=0).kunci == "tegak lurus"


def test_jawaban_istilah_huruf_besar_dan_spasi_berlebih_sama_tetapi_tanpa_spasi_salah():
    soal = modul.unsur_bangun_datar(varian="istilah", istilah="tegak lurus", gaya=0)
    assert setara("Tegak  Lurus", soal.kunci, soal=soal)
    assert not setara("tegaklurus", soal.kunci, soal=soal)
    assert not setara("sejajar", soal.kunci, soal=soal)


def test_sudut_sama_dengan_sisi_pada_semua_bangun_banyak_sisi():
    for p in _domain():
        if p["varian"] == "banyak_sudut":
            sisi = modul.unsur_bangun_datar("banyak_sisi", bangun=p["bangun"], gaya=p["gaya"])
            assert _soal(p).kunci == sisi.kunci, p


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


def test_tiap_parameter_punya_cukup_pengecoh_berbeda_nilai_untuk_pilihan_ganda():
    for p in _domain():
        soal = _soal(p)
        minimal = 2 if p["varian"] == "istilah" else 3
        pengecoh = _pengecoh(soal, _jenis_kunci(soal))
        assert len(pengecoh) >= minimal, (p, pengecoh)


def test_pengecoh_numerik_tidak_negatif_dan_hanya_nol_pada_persegi_panjang_siku():
    for p in _domain():
        if p["varian"] == "istilah":
            continue
        for m in _soal(p).malrule:
            n = int(m.jawaban)
            assert n >= 0, (p, m.jawaban)
            if n == 0:
                assert p["varian"] == "sudut_siku" and p["bangun"] == "persegi panjang", p


def test_malrule_contoh_tangan_sesuai_brief():
    f = modul.unsur_bangun_datar
    segilima = {m.jawaban: m.kode for m in f("banyak_sisi", bangun="segilima", gaya=0).malrule}
    assert segilima["6"] == "K"      # segilima dikira 6 sisi
    assert segilima["10"] == "K"     # sisi dan sudut dihitung bersama
    assert segilima["4"] == "H"      # kurang satu
    persegi_siku = {m.jawaban: m.kode for m in f("sudut_siku", bangun="persegi", gaya=0).malrule}
    assert persegi_siku["2"] == "K"  # persegi dikira 2 sudut siku-siku
    persegi_panjang = {m.jawaban: m.kode
                       for m in f("sudut_siku", bangun="persegi panjang", gaya=0).malrule}
    assert persegi_panjang["0"] == "K" and persegi_panjang["2"] == "K"
    sisi_pp = {m.jawaban: m.kode for m in f("banyak_sisi", bangun="persegi panjang", gaya=0).malrule}
    assert sisi_pp["2"] == "K" and sisi_pp["8"] == "K"
    segitiga_siku = {m.jawaban: m.kode
                     for m in f("sudut_siku", bangun="segitiga siku-siku", gaya=0).malrule}
    assert segitiga_siku["3"] == "K"  # semua sudut dihitung
    tegak = {m.jawaban: m.kode
             for m in f("pasang_tegak_lurus", bangun="persegi", gaya=0).malrule}
    assert tegak["2"] == "K" and tegak["8"] == "K"
    sejajar = {m.jawaban: m.kode for m in f("pasang_sejajar", bangun="persegi", gaya=0).malrule}
    assert sejajar["4"] == "K" and sejajar["1"] == "K"


def test_istilah_malrule_tertukar_dan_pengecoh_tambahan_miring():
    f = modul.unsur_bangun_datar
    sejajar = f("istilah", istilah="sejajar", gaya=0)
    assert {m.jawaban for m in sejajar.malrule} == {"tegak lurus", "berpotongan"}
    tegak = f("istilah", istilah="tegak lurus", gaya=0)
    assert {m.jawaban for m in tegak.malrule} == {"sejajar"}
    assert modul.pengecoh_tambahan(tegak.parameter) == ("miring",)
    assert modul.pengecoh_tambahan(f("banyak_sisi", bangun="persegi", gaya=0).parameter) == ()
    for soal in (sejajar, tegak):
        assert "miring" not in soal.teks and "miring" != soal.kunci


def test_malrule_h_hanya_lebih_atau_kurang_satu_dari_kunci_atau_dua_sejarak():
    for p in _domain():
        if p["varian"] == "istilah":
            continue
        soal = _soal(p)
        for m in soal.malrule:
            if m.kode == "H":
                assert abs(int(m.jawaban) - int(soal.kunci)) == 1, (p, m.jawaban)


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 40 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        if p["varian"] == "istilah":
            assert soal.kunci in teks, teks
        else:
            assert soal.kunci in set(re.findall(r"\d+", teks)), ("kunci tidak muncul", teks)


def test_pembahasan_menyebut_nama_bangun_yang_ditanya():
    for p in _domain():
        if "bangun" not in p:
            continue
        teks = _soal(p).pembahasan
        assert p["bangun"] in teks.lower(), (p, teks)


def test_teks_satu_pertanyaan_tanpa_gambar_dan_tanpa_nama_bangun_kelas_lain():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        assert teks.count("...") + teks.count("?") == 1, teks


def test_teks_pasang_tegak_lurus_selalu_menyebut_bersebelahan():
    for p in _domain():
        if p["varian"] == "pasang_tegak_lurus":
            assert "bersebelahan" in _soal(p).teks, p


def test_tiga_gaya_menghasilkan_teks_berbeda_untuk_satu_pokok():
    kelompok = {}
    for p in _domain():
        pokok = (p["varian"], p.get("bangun"), p.get("istilah"))
        kelompok.setdefault(pokok, set()).add(_soal(p).teks)
    assert all(len(teks) == 3 for teks in kelompok.values())


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", bangun="persegi", gaya=0),
    dict(varian="banyak_sisi", gaya=0),
    dict(varian="banyak_sisi", bangun="persegi"),
    dict(varian="banyak_sisi", bangun="lingkaran", gaya=0),
    dict(varian="banyak_sisi", bangun="jajar genjang", gaya=0),
    dict(varian="banyak_sisi", bangun="segitiga siku-siku", gaya=0),
    dict(varian="banyak_sisi", bangun="persegi", gaya=3),
    dict(varian="banyak_sisi", bangun="persegi", gaya=-1),
    dict(varian="banyak_sisi", bangun="persegi", gaya=True),
    dict(varian="banyak_sisi", bangun="persegi", gaya=0.0),
    dict(varian="banyak_sisi", bangun="persegi", gaya="0"),
    dict(varian="banyak_sisi", bangun=["persegi"], gaya=0),
    dict(varian="banyak_sisi", bangun="persegi", istilah="sejajar", gaya=0),
    dict(varian="sudut_siku", bangun="segilima", gaya=0),
    dict(varian="pasang_sejajar", bangun="segitiga", gaya=0),
    dict(varian="pasang_tegak_lurus", bangun="segienam", gaya=0),
    dict(varian="istilah", gaya=0),
    dict(varian="istilah", istilah="miring", gaya=0),
    dict(varian="istilah", istilah="sejajar", bangun="persegi", gaya=0),
    dict(varian="istilah", istilah="Sejajar", gaya=0),
    dict(varian=["istilah"], istilah="sejajar", gaya=0),
    dict(varian=None, bangun="persegi", gaya=0),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.unsur_bangun_datar(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_unsur_bangun_datar as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P3")
    s = m.unsur_bangun_datar(**p)
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
