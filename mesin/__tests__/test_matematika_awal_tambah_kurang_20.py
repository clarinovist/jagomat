"""Matematika Awal, jenis tambah_kurang_20 (P1): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Kunci dicek solver TERPISAH yang hanya
membaca TEKS soal; bentuk kalimat cerita ditulis ulang di tes ini, bukan diimpor dari
modul. Malrule hanya HIPOTESIS kesalahan umum; yang dijaga: bukan kunci, tidak kembar,
selalu ada jalur K, tidak negatif, dan cukup pengecoh angka.
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

import awal_tambah_kurang_20 as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "tambah_kurang_20"
LEVEL = "P1"
SEED = range(200)
VARIAN = ("tambah", "kurang", "cerita_tambah", "cerita_kurang", "lengkapi")
UKURAN_PER_VARIAN = {"tambah": 60, "kurang": 90, "cerita_tambah": 180,
                     "cerita_kurang": 270, "lengkapi": 150}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # tetap benar untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis|intervensi", re.I)
MINUS = "−"
BATAS = 20

# Bentuk cerita ditulis ulang di sini (operasi ditentukan kalimatnya, bukan modul).
CERITA = (
    (r"Rina punya (\d+) kelereng\. Budi memberinya (\d+) kelereng lagi\. "
     r"Berapa kelereng Rina sekarang\?", "+"),
    (r"Di dalam keranjang ada (\d+) apel\. Dita memasukkan (\d+) apel lagi\. "
     r"Berapa apel di dalam keranjang sekarang\?", "+"),
    (r"Eko menempel (\d+) stiker di bukunya\. Lalu ia menempel (\d+) stiker lagi\. "
     r"Berapa stiker Eko sekarang\?", "+"),
    (r"Budi punya (\d+) kelereng\. Ia memberikan (\d+) kelereng kepada Rina\. "
     r"Berapa kelereng Budi sekarang\?", "-"),
    (r"Di atas piring ada (\d+) kue\. Dita memakan (\d+) kue\. "
     r"Berapa kue yang tersisa\?", "-"),
    (r"Eko punya (\d+) balon\. Lalu (\d+) balon terbang lepas\. "
     r"Berapa balon Eko sekarang\?", "-"),
)


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; tidak memakai parameter atau konstanta modul."""
    cocok = re.fullmatch(r"(\d+) \+ (\d+) = \.\.\.", teks)
    if cocok:
        return str(int(cocok.group(1)) + int(cocok.group(2)))
    cocok = re.fullmatch(rf"(\d+) {MINUS} (\d+) = \.\.\.", teks)
    if cocok:
        hasil = int(cocok.group(1)) - int(cocok.group(2))
        assert hasil >= 0, ("hasil negatif", teks)
        return str(hasil)
    for pola, operasi in CERITA:
        cocok = re.fullmatch(pola, teks)
        if cocok:
            a, b = int(cocok.group(1)), int(cocok.group(2))
            assert operasi == "+" or a >= b, ("hasil negatif", teks)
            return str(a + b if operasi == "+" else a - b)
    cocok = re.fullmatch(r"(\d+) \+ \.\.\. = (\d+)", teks)
    if cocok:
        hasil = int(cocok.group(2)) - int(cocok.group(1))
        assert hasil > 0, ("bilangan hilang harus positif", teks)
        return str(hasil)
    cocok = re.fullmatch(rf"(\d+) {MINUS} \.\.\. = (\d+)", teks)
    if cocok:
        hasil = int(cocok.group(1)) - int(cocok.group(2))
        assert hasil > 0, ("bilangan hilang harus positif", teks)
        return str(hasil)
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(parameter: dict):
    return getattr(modul, TID)(**parameter)


def _pengecoh_angka(soal) -> set:
    """Cermin choice_generation.kandidat: nilai bertipe angka, buang kunci/negatif/duplikat."""
    benar = nilai_semantis(soal.kunci, "angka")
    hasil = set()
    for m in soal.malrule:
        n = nilai_semantis(m.jawaban, "angka")
        if n >= 0 and n != benar:
            hasil.add(n)
    return hasil


def _melewati_sepuluh(a: int, b: int) -> bool:
    return a < 10 and a + b > 10


def _meminjam(a: int, b: int) -> bool:
    return a % 10 < b


def _bilangan_teks(teks: str) -> list:
    return [int(x) for x in re.findall(r"\d+", teks)]


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
    assert len({json.dumps(p, sort_keys=True) for p in a}) > 100


def test_level_selain_p1_ditolak():
    for level in ("P2", "P3", "P4", "P5", "P6", "", None):
        with pytest.raises(ValueError):
            modul.domain_parameter(level)
        with pytest.raises(ValueError):
            modul.parameter(random.Random(0), level)


def test_tambah_minimal_separuh_domain_melewati_sepuluh():
    pasangan = [(p["a"], p["b"]) for p in _domain() if p["varian"] == "tambah"]
    lewat = [x for x in pasangan if _melewati_sepuluh(*x)]
    assert len(lewat) * 2 >= len(pasangan), (len(lewat), len(pasangan))
    assert (8, 5) in pasangan
    assert all(11 <= a + b <= BATAS for a, b in pasangan)


def test_kurang_memuat_kasus_meminjam_dan_tanpa_meminjam():
    pasangan = [(p["a"], p["b"]) for p in _domain() if p["varian"] == "kurang"]
    pinjam = [x for x in pasangan if _meminjam(*x)]
    assert (15, 7) in pasangan
    assert 0 < len(pinjam) < len(pasangan) and len(pinjam) * 2 >= len(pasangan) - 1
    assert all(11 <= a <= BATAS and 1 <= b <= 9 for a, b in pasangan)


# ── kunci ────────────────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.parameter == p
        assert soal.template_id == TID and soal.bagian == "A"
        assert re.fullmatch(r"[1-9]\d*", soal.kunci), soal.kunci


def test_semua_bilangan_dalam_soal_dan_kunci_sampai_20_tanpa_negatif():
    for p in _domain():
        soal = _soal(p)
        angka = _bilangan_teks(soal.teks)
        assert all(0 < x <= BATAS for x in angka), (p, soal.teks)
        assert 1 <= int(soal.kunci) <= BATAS
        assert "-" not in soal.teks


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.tambah_kurang_20
    assert f(varian="tambah", a=8, b=5).teks == "8 + 5 = ..."
    assert f(varian="tambah", a=8, b=5).kunci == "13"
    assert f(varian="kurang", a=15, b=7).teks == "15 − 7 = ..."
    assert f(varian="kurang", a=15, b=7).kunci == "8"
    assert f(varian="lengkapi", bentuk="tambah", a=9, b=6).teks == "9 + ... = 15"
    assert f(varian="lengkapi", bentuk="tambah", a=9, b=6).kunci == "6"
    assert f(varian="lengkapi", bentuk="kurang", a=15, b=7).teks == "15 − ... = 8"
    assert f(varian="lengkapi", bentuk="kurang", a=15, b=7).kunci == "7"
    assert f(varian="cerita_tambah", a=8, b=5, konteks=0).teks == (
        "Rina punya 8 kelereng. Budi memberinya 5 kelereng lagi. "
        "Berapa kelereng Rina sekarang?")
    assert f(varian="cerita_kurang", a=15, b=7, konteks=1).teks == (
        "Di atas piring ada 15 kue. Dita memakan 7 kue. Berapa kue yang tersisa?")
    assert f(varian="cerita_kurang", a=15, b=7, konteks=1).kunci == "8"


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


def test_jawaban_malrule_bilangan_cacah_dan_h_tetap_sampai_20():
    for p in _domain():
        soal = _soal(p)
        for m in soal.malrule:
            assert re.fullmatch(r"(0|[1-9]\d*)", m.jawaban), (p, m.jawaban)
            if m.kode == "H":
                assert 0 <= int(m.jawaban) <= BATAS, (p, m.id)


def test_tiap_parameter_punya_cukup_pengecoh_untuk_pilihan_ganda_empat_v1():
    for p in _domain():
        soal = _soal(p)
        assert len(_pengecoh_angka(soal)) >= 3, (p, [m.jawaban for m in soal.malrule])


def test_tiga_pengecoh_pertama_sampai_20_kecuali_kasus_20_dikurang_5():
    di_atas = [p for p in _domain()
               if any(int(m.jawaban) > BATAS for m in _soal(p).malrule[:3])]
    assert {(p["a"], p["b"]) for p in di_atas} <= {(20, 5)}, di_atas


def test_malrule_tambah_dan_kurang_bernilai_benar_untuk_hipotesisnya():
    f = modul.tambah_kurang_20
    tambah = {m.id.split(".")[-1]: (m.jawaban, m.kode)
              for m in f(varian="tambah", a=9, b=6).malrule}
    assert tambah == {"lupa_puluhan": ("5", "K"), "dikurang_bukan_dijumlah": ("3", "K"),
                      "kurang_satu": ("14", "H"), "lebih_satu": ("16", "H")}
    kurang = {m.id.split(".")[-1]: (m.jawaban, m.kode)
              for m in f(varian="kurang", a=15, b=7).malrule}
    assert kurang == {"satuan_dikurang_terbalik": ("12", "K"),
                      "lupa_kurangi_puluhan": ("18", "K"), "kurang_satu": ("7", "H"),
                      "lebih_satu": ("9", "H"), "dijumlah_bukan_dikurang": ("22", "K")}


def test_pengurangan_tanpa_meminjam_tidak_dituduh_salah_pinjam():
    f = modul.tambah_kurang_20
    tanpa = {m.id.split(".")[-1]: m.jawaban for m in f(varian="kurang", a=15, b=3).malrule}
    assert "satuan_dikurang_terbalik" not in tanpa and "lupa_kurangi_puluhan" not in tanpa
    assert tanpa["puluhan_hilang"] == "2" and tanpa["dijumlah_bukan_dikurang"] == "18"
    dua_puluh = {m.id.split(".")[-1]: m.jawaban for m in f(varian="kurang", a=20, b=7).malrule}
    assert "lupa_kurangi_puluhan" not in dua_puluh, "20 tidak punya puluhan sisa untuk dilupakan"
    assert dua_puluh["satuan_dikurang_terbalik"] == "17"


def test_setiap_jalur_k_brief_muncul_untuk_parameter_yang_berlaku():
    for p in _domain():
        soal = _soal(p)
        ids = {m.id.split(".")[-1] for m in soal.malrule}
        v = p["varian"]
        if v in ("tambah", "cerita_tambah"):
            assert {"dikurang_bukan_dijumlah", "lupa_puluhan"} & ids, p
        if v in ("kurang", "cerita_kurang"):
            jawaban_k = {int(m.jawaban) for m in soal.malrule if m.kode == "K"}
            assert p["a"] + p["b"] in jawaban_k, ("operasi dibalik harus tetap terwakili", p)
            if _meminjam(p["a"], p["b"]):
                terbalik = 10 + (p["b"] - p["a"] % 10)
                assert "satuan_dikurang_terbalik" in ids or terbalik == int(soal.kunci), p
        if v in ("tambah", "cerita_tambah", "kurang", "cerita_kurang"):
            kunci = int(soal.kunci)
            h = {int(m.jawaban) for m in soal.malrule if m.kode == "H"}
            assert h <= {kunci - 1, kunci + 1}, (p, h)
            assert {x for x in (kunci - 1, kunci + 1) if 0 <= x <= BATAS} == h, (p, h)


def test_malrule_lengkapi_bernilai_benar():
    f = modul.tambah_kurang_20
    tambah = {m.id.split(".")[-1]: (m.jawaban, m.kode)
              for m in f(varian="lengkapi", bentuk="tambah", a=7, b=9).malrule}
    assert tambah == {"hasil_ditulis": ("16", "K"), "kurang_satu": ("8", "H"),
                      "lebih_satu": ("10", "H"), "dijumlah_dua_bilangan": ("23", "K")}
    kurang = {m.id.split(".")[-1]: (m.jawaban, m.kode)
              for m in f(varian="lengkapi", bentuk="kurang", a=15, b=7).malrule}
    assert kurang["hasil_ditulis"] == ("8", "K") and kurang["bilangan_awal_diulang"] == ("15", "K")
    assert kurang["dijumlah_dua_bilangan"] == ("23", "K")


def test_jawaban_di_luar_20_selalu_paling_akhir_dalam_daftar():
    for p in _domain():
        soal = _soal(p)
        nilai = [int(m.jawaban) for m in soal.malrule]
        for i, x in enumerate(nilai):
            if x > BATAS:
                assert all(y > BATAS for y in nilai[i:]), (p, nilai)


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 40 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        assert soal.kunci in re.findall(r"\d+", teks), ("kunci tidak muncul", teks)


def test_pembahasan_hitungan_antara_benar():
    f = modul.tambah_kurang_20
    assert "genapkan 8 menjadi 10 dengan mengambil 2 dari 5. Sisanya 3. Jadi 10 + 3 = 13." in (
        f(varian="tambah", a=8, b=5).pembahasan)
    assert "10 − 2 = 8" in f(varian="kurang", a=15, b=7).pembahasan
    assert "10 + 3 = 13" in f(varian="kurang", a=20, b=7).pembahasan
    assert "10 + 2 = 12" in f(varian="kurang", a=15, b=3).pembahasan


def test_pembahasan_langkah_hitung_konsisten_dengan_kunci_seluruh_domain():
    for p in _domain():
        if p["varian"] not in ("tambah", "kurang"):
            continue
        teks = _soal(p).pembahasan
        persamaan = re.findall(rf"(\d+) ([+{MINUS}]) (\d+) = (\d+)", teks)
        assert persamaan, teks
        for x, op, y, hasil in persamaan:
            x, y, hasil = int(x), int(y), int(hasil)
            assert hasil == (x + y if op == "+" else x - y), (teks, x, op, y, hasil)


def test_teks_satu_baris_satu_pertanyaan_dan_nama_sintetis():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        if p["varian"] in ("cerita_tambah", "cerita_kurang"):
            assert teks.count("?") == 1 and "..." not in teks and teks.count(".") == 2
        else:
            assert teks.count("...") == 1


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", a=8, b=5),
    dict(varian="tambah"),
    dict(varian="tambah", a=8),
    dict(varian="tambah", a=5, b=5),
    dict(varian="tambah", a=9, b=1),
    dict(varian="tambah", a=13, b=5),
    dict(varian="tambah", a=12, b=8),
    dict(varian="tambah", a=0, b=11),
    dict(varian="tambah", a=8, b=5.0),
    dict(varian="tambah", a=True, b=5),
    dict(varian="tambah", a="8", b=5),
    dict(varian="tambah", a=8, b=5, konteks=0),
    dict(varian="kurang", a=10, b=3),
    dict(varian="kurang", a=21, b=3),
    dict(varian="kurang", a=15, b=10),
    dict(varian="kurang", a=15, b=0),
    dict(varian="kurang", a=15, b=-7),
    dict(varian="cerita_tambah", a=8, b=5),
    dict(varian="cerita_tambah", a=8, b=5, konteks=3),
    dict(varian="cerita_tambah", a=8, b=5, konteks=-1),
    dict(varian="cerita_tambah", a=8, b=5, konteks=True),
    dict(varian="cerita_kurang", a=15, b=7, konteks=3),
    dict(varian="cerita_kurang", a=15, b=7),
    dict(varian="lengkapi", a=8, b=5),
    dict(varian="lengkapi", bentuk="bagi", a=8, b=5),
    dict(varian="lengkapi", bentuk="tambah", a=15, b=7),
    dict(varian="lengkapi", bentuk="kurang", a=8, b=5),
    dict(varian="lengkapi", bentuk=None, a=8, b=5),
    dict(varian=["tambah"], a=8, b=5),
    dict(varian=None, a=8, b=5),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.tambah_kurang_20(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_tambah_kurang_20 as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P1")
    s = m.tambah_kurang_20(**p)
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
