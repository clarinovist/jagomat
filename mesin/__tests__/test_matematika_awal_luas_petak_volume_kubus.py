"""Matematika Awal, jenis luas_petak_volume_kubus (P4): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang hanya
membaca TEKS soal; rumus luas (baris x petak) dan volume (lapis x baris x kolom) ditulis
ulang di tes ini, bukan diimpor dari modul. Malrule hanya HIPOTESIS kesalahan umum; yang
dijaga: bukan kunci, tidak kembar, positif, selalu ada jalur K, dan cukup pengecoh angka.
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

import awal_luas_petak_volume_kubus as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "luas_petak_volume_kubus"
LEVEL = "P4"
SEED = range(200)
VARIAN = ("luas_petak", "luas_bandingkan", "volume_kubus_satuan", "tambah_kubus")
UKURAN_PER_VARIAN = {"luas_petak": 56, "luas_bandingkan": 224, "volume_kubus_satuan": 80,
                     "tambah_kubus": 144}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # tetap benar untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)
BALOK = (r"(\d+) lapis, tiap lapis (\d+) baris dan tiap baris (\d+) kubus")


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; tidak memakai parameter atau konstanta modul."""
    cocok = re.fullmatch(
        r"Sebuah persegi panjang tersusun dari (\d+) baris petak satuan, tiap baris (\d+) petak\. "
        r"Luasnya \.\.\. petak satuan\.", teks)
    if cocok:
        baris, kolom = map(int, cocok.groups())
        assert 2 <= baris <= 9 and 2 <= kolom <= 9 and baris != kolom, teks
        return str(baris * kolom)
    cocok = re.fullmatch(
        r"Persegi panjang A tersusun dari (\d+) baris petak satuan, tiap baris (\d+) petak\. "
        r"Persegi panjang B tersusun dari (\d+) baris petak satuan, tiap baris (\d+) petak\. "
        r"Luas A lebih besar \.\.\. petak satuan daripada luas B\.", teks)
    if cocok:
        ba, ka, bb, kb = map(int, cocok.groups())
        assert ba * ka > bb * kb, ("A harus lebih luas", teks)
        return str(ba * ka - bb * kb)
    cocok = re.fullmatch(
        r"Sebuah balok tersusun dari kubus satuan: " + BALOK + r"\. Volumenya \.\.\. kubus satuan\.",
        teks)
    if cocok:
        lapis, baris, kolom = map(int, cocok.groups())
        assert 2 <= lapis <= 5 and 2 <= baris <= 5 and 2 <= kolom <= 6, teks
        return str(lapis * baris * kolom)
    cocok = re.fullmatch(
        r"(\w+) menyusun sebuah balok dari kubus satuan: " + BALOK + r"\. Kemudian \1 menambahkan "
        r"(\d+) kubus satuan pada balok itu\. Volume benda sekarang \.\.\. kubus satuan\.", teks)
    if cocok:
        lapis, baris, kolom, tambah = map(int, cocok.groups()[1:])
        assert lapis <= 4 and baris <= 4 and kolom <= 5 and 1 <= tambah <= 5, teks
        return str(lapis * baris * kolom + tambah)
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


def _per_id(soal) -> dict:
    return {m.id.split(".")[-1]: (m.jawaban, m.kode) for m in soal.malrule}


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
        if p["varian"] == "luas_petak":
            assert 2 <= p["baris"] <= 9 and 2 <= p["kolom"] <= 9 and p["baris"] != p["kolom"]
        if p["varian"] == "luas_bandingkan":
            assert 4 <= p["baris_a"] <= 8 and 4 <= p["kolom_a"] <= 8
            assert 2 <= p["baris_b"] <= 4 and 2 <= p["kolom_b"] <= 4
        if p["varian"] == "volume_kubus_satuan":
            assert 2 <= p["lapis"] <= 5 and 2 <= p["baris"] <= 5 and 2 <= p["kolom"] <= 6
        if p["varian"] == "tambah_kubus":
            assert p["lapis"] <= 4 and p["baris"] <= 4 and p["kolom"] <= 5
            assert p["tambah"] in (2, 3, 4, 5)


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
    assert len({json.dumps(p, sort_keys=True) for p in a}) > 100


def test_sampler_memilih_varian_dulu_bukan_menurut_ukuran_domain():
    hitung = {v: 0 for v in VARIAN}
    for s in range(1000):
        hitung[modul.parameter(random.Random(s), LEVEL)["varian"]] += 1
    assert all(150 < n < 350 for n in hitung.values()), hitung


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
        assert re.fullmatch(r"[1-9]\d*", soal.kunci), ("kunci angka polos", soal.kunci)


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.luas_petak_volume_kubus
    luas = f(varian="luas_petak", baris=3, kolom=5)
    assert luas.teks == ("Sebuah persegi panjang tersusun dari 3 baris petak satuan, tiap baris "
                         "5 petak. Luasnya ... petak satuan.")
    assert luas.kunci == "15"
    banding = f(varian="luas_bandingkan", baris_a=5, kolom_a=6, baris_b=3, kolom_b=4)
    assert banding.kunci == "18"
    assert banding.teks.endswith("Luas A lebih besar ... petak satuan daripada luas B.")
    vol = f(varian="volume_kubus_satuan", lapis=3, baris=2, kolom=4)
    assert vol.teks == ("Sebuah balok tersusun dari kubus satuan: 3 lapis, tiap lapis 2 baris "
                        "dan tiap baris 4 kubus. Volumenya ... kubus satuan.")
    assert vol.kunci == "24"
    tambah = f(varian="tambah_kubus", lapis=3, baris=2, kolom=4, tambah=2)
    assert "menambahkan 2 kubus satuan pada balok itu" in tambah.teks
    assert tambah.kunci == "26"


def test_kunci_bisa_diketik_dan_dinormalisasi_apa_adanya():
    for p in _domain():
        kunci = _soal(p).kunci
        assert normalisasi(kunci) == kunci


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
        assert all(re.fullmatch(r"[1-9]\d*", m.jawaban) for m in soal.malrule), (p, soal.malrule)


def test_tiap_parameter_punya_cukup_pengecoh_angka_untuk_pilihan_ganda():
    for p in _domain():
        soal = _soal(p)
        assert len(_pengecoh_angka(soal)) >= 2, (p, [m.jawaban for m in soal.malrule])


def test_malrule_bernilai_benar_untuk_hipotesisnya():
    f = modul.luas_petak_volume_kubus
    luas = _per_id(f(varian="luas_petak", baris=3, kolom=5))
    # keliling 16 kembar dengan lebih_satu (16): hanya yang pertama bertahan
    assert luas == {
        "dijumlah_bukan_dikali": ("8", "K"), "hanya_banyak_baris": ("3", "K"),
        "hanya_petak_satu_baris": ("5", "K"), "menghitung_keliling": ("16", "K"),
        "kurang_satu": ("14", "H")}
    band = _per_id(f(varian="luas_bandingkan", baris_a=5, kolom_a=6, baris_b=2, kolom_b=4))
    assert band == {"luas_dijumlah": ("38", "K"), "hanya_luas_a": ("30", "K"),
                    "selisih_dijumlah_bukan_dikali": ("5", "K"),
                    "baris_kolom_dikurangi_dulu": ("6", "K")}
    vol = _per_id(f(varian="volume_kubus_satuan", lapis=3, baris=2, kolom=4))
    assert vol == {"dijumlah_bukan_dikali": ("9", "K"), "tanpa_faktor_lapis": ("8", "K"),
                   "tanpa_faktor_kolom": ("6", "K"), "tanpa_faktor_baris": ("12", "K"),
                   "kurang_satu": ("23", "H"), "lebih_satu": ("25", "H")}
    tambah = _per_id(f(varian="tambah_kubus", lapis=3, baris=2, kolom=4, tambah=2))
    assert tambah == {"semua_dijumlah": ("11", "K"), "semua_dikali": ("48", "K"),
                      "tanpa_faktor_lapis_ditambah": ("10", "K"), "lupa_menambah": ("24", "H"),
                      "dikurangi_bukan_ditambah": ("22", "H")}


def _nilai_malrule(soal) -> set:
    return {int(m.jawaban) for m in soal.malrule}


def test_menjumlah_bukan_mengalikan_dan_faktor_terlewat_selalu_terwakili_dengan_k():
    """Nilai hipotesis selalu ada (kecuali sama dengan kunci); jalur K ikut bila tak kembar."""
    for p in _domain():
        soal = _soal(p)
        nilai, kunci = _nilai_malrule(soal), int(soal.kunci)
        k_nilai = {int(m.jawaban) for m in soal.malrule if m.kode == "K"}
        if p["varian"] == "luas_petak":
            harapan = {p["baris"] + p["kolom"], p["baris"], p["kolom"]}
        elif p["varian"] == "volume_kubus_satuan":
            harapan = {p["lapis"] + p["baris"] + p["kolom"], p["baris"] * p["kolom"],
                       p["lapis"] * p["baris"], p["lapis"] * p["kolom"]}
        elif p["varian"] == "tambah_kubus":
            harapan = {p["lapis"] + p["baris"] + p["kolom"] + p["tambah"],
                       p["baris"] * p["kolom"] + p["tambah"]}
        else:
            continue
        for h in harapan - {kunci}:
            assert h in nilai, (p, h, nilai)
        # penjumlahan selalu K (jika kembar dengan lainnya, lainnya pun K atau H yang sama nilainya)
        jumlah = {p.get("baris", 0) + p.get("kolom", 0)} if p["varian"] == "luas_petak" else None
        if jumlah:
            assert jumlah <= k_nilai or jumlah <= {kunci}, p


def test_kurang_atau_lebih_satu_dan_lupa_tambah_hanya_h():
    ada_lupa = 0
    for p in _domain():
        soal = _soal(p)
        for m in soal.malrule:
            nama = m.id.split(".")[-1]
            if nama in ("kurang_satu", "lebih_satu", "lupa_menambah", "dikurangi_bukan_ditambah"):
                assert m.kode == "H", (p, nama)
                if nama in ("kurang_satu", "lebih_satu"):
                    assert abs(int(m.jawaban) - int(soal.kunci)) == 1
                if nama == "lupa_menambah":
                    ada_lupa += 1
                    assert int(m.jawaban) == int(soal.kunci) - p["tambah"]
        if p["varian"] == "tambah_kubus":
            # lupa menambah kembar dengan jalur K hanya pada beberapa parameter; harus langka
            assert len(soal.malrule) >= 3
    assert ada_lupa >= UKURAN_PER_VARIAN["tambah_kubus"] - 10


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 40 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        angka = set(re.findall(r"\d+", teks))
        assert soal.kunci in angka, ("kunci tidak muncul di pembahasan", teks)


def test_pembahasan_menyebut_langkah_yang_benar():
    f = modul.luas_petak_volume_kubus
    assert "3 × 5 = 15 petak satuan" in f(varian="luas_petak", baris=3, kolom=5).pembahasan
    band = f(varian="luas_bandingkan", baris_a=5, kolom_a=6, baris_b=3, kolom_b=4).pembahasan
    assert "5 × 6 = 30" in band and "3 × 4 = 12" in band and "30 − 12 = 18" in band
    vol = f(varian="volume_kubus_satuan", lapis=3, baris=2, kolom=4).pembahasan
    assert "2 × 4 = 8 kubus" in vol and "3 × 8 = 24 kubus satuan" in vol
    tambah = f(varian="tambah_kubus", lapis=3, baris=2, kolom=4, tambah=2).pembahasan
    assert "24 + 2 = 26 kubus satuan" in tambah


def test_teks_tanpa_gambar_satu_pertanyaan_dan_nama_sintetis():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        assert teks.count("...") == 1 or p["varian"] == "luas_bandingkan" and teks.count("...") == 1
        assert "None" not in teks and "{" not in teks


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", baris=3, kolom=5),
    dict(varian="luas_petak"),
    dict(varian="luas_petak", baris=3),
    dict(varian="luas_petak", baris=1, kolom=5),
    dict(varian="luas_petak", baris=3, kolom=10),
    dict(varian="luas_petak", baris=4, kolom=4),
    dict(varian="luas_petak", baris=True, kolom=5),
    dict(varian="luas_petak", baris="3", kolom=5),
    dict(varian="luas_petak", baris=3.0, kolom=5),
    dict(varian="luas_petak", baris=3, kolom=5, lapis=2),
    dict(varian="luas_bandingkan", baris_a=5, kolom_a=6, baris_b=3),
    dict(varian="luas_bandingkan", baris_a=3, kolom_a=6, baris_b=3, kolom_b=4),
    dict(varian="luas_bandingkan", baris_a=9, kolom_a=6, baris_b=3, kolom_b=4),
    dict(varian="luas_bandingkan", baris_a=4, kolom_a=4, baris_b=4, kolom_b=4),
    dict(varian="luas_bandingkan", baris_a=5, kolom_a=6, baris_b=5, kolom_b=4),
    dict(varian="luas_bandingkan", baris_a=5, kolom_a=6, baris_b=1, kolom_b=4),
    dict(varian="volume_kubus_satuan", lapis=6, baris=2, kolom=4),
    dict(varian="volume_kubus_satuan", lapis=3, baris=6, kolom=4),
    dict(varian="volume_kubus_satuan", lapis=3, baris=2, kolom=7),
    dict(varian="volume_kubus_satuan", lapis=1, baris=2, kolom=4),
    dict(varian="volume_kubus_satuan", lapis=3, baris=2),
    dict(varian="volume_kubus_satuan", lapis=3, baris=2, kolom=4, tambah=2),
    dict(varian="tambah_kubus", lapis=5, baris=2, kolom=4, tambah=2),
    dict(varian="tambah_kubus", lapis=3, baris=2, kolom=6, tambah=2),
    dict(varian="tambah_kubus", lapis=3, baris=2, kolom=4, tambah=1),
    dict(varian="tambah_kubus", lapis=3, baris=2, kolom=4, tambah=6),
    dict(varian="tambah_kubus", lapis=3, baris=2, kolom=4),
    dict(varian=["luas_petak"], baris=3, kolom=5),
    dict(varian=None, baris=3, kolom=5),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.luas_petak_volume_kubus(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_luas_petak_volume_kubus as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P4")
    s = m.luas_petak_volume_kubus(**p)
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
