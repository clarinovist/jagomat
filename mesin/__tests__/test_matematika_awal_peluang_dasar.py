"""Matematika Awal, jenis peluang_dasar (P6): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (regex), tanpa
memakai parameter atau tabel dari modul jenis. Malrule hanya HIPOTESIS kesalahan
umum yang ditinjau guru; yang dijaga di sini: bukan kunci (secara nilai, bukan
hanya string), tidak kembar, dan selalu ada jalur K di SETIAP parameter sah.
Tes ini sengaja tidak bergantung pada registrasi topik: ia memanggil modul jenis
langsung.
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

import awal_peluang_dasar as modul
import diagnosis
from multiple_choice import nilai_semantis
from templates import Soal

TID = "peluang_dasar"
LEVEL = "P6"
SEED = range(200)
VARIAN = ("lebih_mungkin", "kepastian", "banyak_hasil", "peluang_pecahan")
UKURAN_VARIAN = {"lebih_mungkin": 36, "kepastian": 24, "banyak_hasil": 21, "peluang_pecahan": 28}
AKAR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"\b(malrule|diagnosis|kode|template|kunci|hipotesis|guru)\b", re.I)
WARNA = ("merah", "biru", "hijau", "kuning")
# Banyak pengecoh yang disyaratkan kebijakan PG yang diusulkan per varian.
PENGECOH_PERLU = {"lebih_mungkin": 2, "kepastian": 2, "banyak_hasil": 2, "peluang_pecahan": 3}
JENIS_PG = {"lebih_mungkin": "kategori", "kepastian": "kategori",
            "banyak_hasil": "angka", "peluang_pecahan": "angka"}


# ── solver terpisah: hanya membaca teks ──────────────────────────────────

def _jumlah_warna(teks: str) -> dict:
    return {w: int(n) for n, w in re.findall(r"(\d+) bola (\w+)", teks)}


def _cocok(syarat: str, x: int) -> bool:
    if syarat == "genap":
        return x % 2 == 0
    if syarat == "ganjil":
        return x % 2 == 1
    cocok = re.fullmatch(r"(lebih dari|kurang dari|kelipatan) (\d+)", syarat)
    assert cocok, ("syarat tidak dikenal", syarat)
    k = int(cocok.group(2))
    return {"lebih dari": x > k, "kurang dari": x < k, "kelipatan": x % k == 0}[cocok.group(1)]


def _solver_lebih_mungkin(teks: str) -> str:
    cocok = re.fullmatch(
        r"Dalam kantong ada \d+ bola merah, \d+ bola biru, dan \d+ bola hijau\. "
        r"Satu bola diambil tanpa melihat\. (.+)\?", teks)
    assert cocok, teks
    jumlah = _jumlah_warna(teks)
    assert set(jumlah) == {"merah", "biru", "hijau"} and len(set(jumlah.values())) == 3
    pertanyaan = cocok.group(1)
    if pertanyaan == "Bola warna apa yang paling mungkin terambil":
        return max(jumlah, key=jumlah.get)
    assert pertanyaan == "Bola warna apa yang paling kecil kemungkinan terambilnya", teks
    return min(jumlah, key=jumlah.get)


def _solver_kepastian(teks: str) -> str:
    cocok = re.fullmatch(
        r"Kantong berisi (\d+) bola (\w+) saja\. Satu bola diambil tanpa melihat\. "
        r"Kejadian terambil bola (\w+) itu pasti, mungkin, atau mustahil\?", teks)
    assert cocok, teks
    return "pasti" if cocok.group(2) == cocok.group(3) else "mustahil"


def _solver_banyak_hasil(teks: str) -> str:
    dadu = re.fullmatch(
        r"Sebuah dadu bersisi (\d+) dilempar\. Ada berapa kemungkinan muncul angka (.+)\?", teks)
    if dadu:
        batas, syarat = int(dadu.group(1)), dadu.group(2)
    else:
        kartu = re.fullmatch(
            r"Satu kartu diambil dari (\d+) kartu yang bernomor 1 sampai (\d+)\. "
            r"Ada berapa kemungkinan kartu itu bernomor (.+)\?", teks)
        assert kartu and kartu.group(1) == kartu.group(2), teks
        batas, syarat = int(kartu.group(1)), kartu.group(3)
    return str(sum(1 for x in range(1, batas + 1) if _cocok(syarat, x)))


def _solver_peluang_pecahan(teks: str) -> str:
    cocok = re.fullmatch(
        r"Dalam kantong ada (\d+) bola merah dan (\d+) bola biru\. "
        r"Satu bola diambil tanpa melihat\. Peluang terambil bola (merah|biru) adalah \.\.\. "
        r"\(tulis dalam bentuk pecahan, contoh 1/4\)", teks)
    assert cocok, teks
    merah, biru = int(cocok.group(1)), int(cocok.group(2))
    diminta = merah if cocok.group(3) == "merah" else biru
    return f"{diminta}/{merah + biru}"  # sengaja TIDAK disederhanakan


def solver_dari_teks(teks: str) -> str:
    if teks.startswith("Dalam kantong ada") and " bola hijau" in teks:
        return _solver_lebih_mungkin(teks)
    if teks.startswith("Dalam kantong ada"):
        return _solver_peluang_pecahan(teks)
    if teks.startswith("Kantong berisi"):
        return _solver_kepastian(teks)
    if teks.startswith(("Sebuah dadu", "Satu kartu")):
        return _solver_banyak_hasil(teks)
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


# ── pembantu ─────────────────────────────────────────────────────────────

def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(p: dict) -> Soal:
    return modul.peluang_dasar(**p)


def _nilai(teks: str):
    """Nilai jawaban: bilangan/pecahan jadi Fraction, selebihnya teks ternormalisasi."""
    try:
        return nilai_semantis(teks, "angka")
    except ValueError:
        return diagnosis.normalisasi(teks)


def _kanon(p: dict) -> str:
    return json.dumps(p, sort_keys=True)


# ── domain dan sampler ───────────────────────────────────────────────────

def test_ukuran_domain_per_varian_tidak_kembar_dan_cukup():
    domain = _domain()
    assert len({_kanon(p) for p in domain}) == len(domain), "domain berisi duplikat"
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_VARIAN
    assert len(domain) >= 30
    assert all(n >= 15 for n in per_varian.values())


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
        hitung[p["varian"]] += 1
    assert all(n >= 30 for n in hitung.values()), hitung


def test_sampler_murni_dari_rng_seed_sama_hasil_sama():
    for seed in range(50):
        assert modul.parameter(random.Random(seed), LEVEL) == modul.parameter(random.Random(seed), LEVEL)


def test_tanda_tangan_dan_teks_unik_di_seluruh_domain():
    from dataclasses import replace
    soal = [replace(_soal(p), level=LEVEL) for p in _domain()]
    assert len({s.tanda_tangan for s in soal}) == len(soal)
    assert len({s.teks for s in soal}) == len(soal), "dua parameter berbeda menghasilkan teks sama"
    assert all(s.parameter == p for s, p in zip(soal, _domain()))


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


def test_bentuk_kunci_per_varian():
    for p in _domain():
        kunci = _soal(p).kunci
        assert kunci == kunci.strip() and " " not in kunci
        if p["varian"] in ("lebih_mungkin", "kepastian"):
            assert re.fullmatch(r"[a-z]+", kunci), kunci
        if p["varian"] == "kepastian":
            assert kunci in ("pasti", "mustahil")
        if p["varian"] == "lebih_mungkin":
            assert kunci in ("merah", "biru", "hijau")
        if p["varian"] == "banyak_hasil":
            assert re.fullmatch(r"[1-9][0-9]*", kunci)
        if p["varian"] == "peluang_pecahan":
            cocok = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", kunci)
            assert cocok, kunci
            pembilang, penyebut = int(cocok.group(1)), int(cocok.group(2))
            assert math.gcd(pembilang, penyebut) == 1, ("pecahan harus sudah sederhana", kunci)
            assert pembilang < penyebut


def test_kunci_contoh_tangan():
    f = modul.peluang_dasar
    assert f(varian="peluang_pecahan", merah=3, biru=2, tanya="merah").kunci == "3/5"
    assert f(varian="peluang_pecahan", merah=3, biru=2, tanya="biru").kunci == "2/5"
    assert f(varian="kepastian", isi="merah", n=4, tanya="biru").kunci == "mustahil"
    assert f(varian="kepastian", isi="merah", n=4, tanya="merah").kunci == "pasti"
    assert f(varian="banyak_hasil", objek="dadu", syarat="genap").kunci == "3"
    assert f(varian="banyak_hasil", objek="dadu", syarat="lebih_dari", k=4).kunci == "2"
    assert f(varian="banyak_hasil", objek="kartu", syarat="kelipatan", k=5).kunci == "2"
    assert f(varian="lebih_mungkin", merah=2, biru=7, hijau=4, arah="terbanyak").kunci == "biru"
    assert f(varian="lebih_mungkin", merah=2, biru=7, hijau=4, arah="tersedikit").kunci == "merah"
    assert f(varian="banyak_hasil", objek="dadu", syarat="kurang_dari", k=3).teks == (
        "Sebuah dadu bersisi 6 dilempar. Ada berapa kemungkinan muncul angka kurang dari 3?")


def test_lebih_mungkin_tiga_jumlah_berbeda_dan_kunci_tunggal():
    for p in _domain():
        if p["varian"] != "lebih_mungkin":
            continue
        jumlah = [p["merah"], p["biru"], p["hijau"]]
        assert len(set(jumlah)) == 3 and min(jumlah) >= 1 and max(jumlah) <= 9, p


def test_peluang_pecahan_syarat_pasangan_jumlah_bola():
    for p in _domain():
        if p["varian"] != "peluang_pecahan":
            continue
        m, b = p["merah"], p["biru"]
        assert m >= 2 and b >= 2 and m != b and math.gcd(m, b) == 1 and 5 <= m + b <= 10, p


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        nilai = [_nilai(m.jawaban) for m in soal.malrule]
        assert _nilai(soal.kunci) not in nilai, (p, "malrule sama dengan kunci")
        assert len(set(nilai)) == len(nilai), (p, "malrule kembar menurut nilai")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert all(m.alasan.strip() and m.alasan[0].isupper() and m.alasan.endswith(".")
                   for m in soal.malrule), (p, [m.alasan for m in soal.malrule])


def test_malrule_cukup_untuk_pengecoh_pilihan_ganda_seluruh_domain():
    """Proksi kebijakan PG: nilai pengecoh beda secara tipe-semantis dari kunci dan satu sama lain."""
    for p in _domain():
        soal = _soal(p)
        jenis = JENIS_PG[p["varian"]]
        benar = nilai_semantis(soal.kunci, jenis)
        pengecoh = {nilai_semantis(m.jawaban, jenis) for m in soal.malrule} - {benar}
        assert len(pengecoh) >= PENGECOH_PERLU[p["varian"]], (p, [m.jawaban for m in soal.malrule])


def test_malrule_lebih_mungkin_berupa_dua_warna_lain():
    for p in _domain():
        if p["varian"] != "lebih_mungkin":
            continue
        soal = _soal(p)
        assert {m.jawaban for m in soal.malrule} == {"merah", "biru", "hijau"} - {soal.kunci}
        assert all(m.kode == "K" for m in soal.malrule)


def test_malrule_kepastian_memuat_kata_lawan_dan_mungkin():
    for p in _domain():
        if p["varian"] != "kepastian":
            continue
        soal = _soal(p)
        lawan = "pasti" if soal.kunci == "mustahil" else "mustahil"
        assert {m.jawaban for m in soal.malrule} == {lawan, "mungkin"}


def test_malrule_peluang_pecahan_empat_hipotesis_jalur_k():
    for p in _domain():
        if p["varian"] != "peluang_pecahan":
            continue
        soal = _soal(p)
        m, b = p["merah"], p["biru"]
        x, y = (m, b) if p["tanya"] == "merah" else (b, m)
        harapan = {str(x), f"{m + b}/{x}", f"{x}/{y}", f"{y}/{m + b}"}
        assert {m_.jawaban for m_ in soal.malrule} == harapan, p
        assert all(m_.kode == "K" for m_ in soal.malrule)


def test_malrule_banyak_hasil_menyertakan_total_dan_salah_hitung_satu():
    for p in _domain():
        if p["varian"] != "banyak_hasil":
            continue
        soal = _soal(p)
        jawaban = {m.jawaban: m.kode for m in soal.malrule}
        total = "6" if p["objek"] == "dadu" else "10"
        assert jawaban.get(total) == "K", p
        key = int(soal.kunci)
        h = {int(j) for j, kode in jawaban.items() if kode == "H"}
        assert h <= {key - 1, key + 1}


# ── pembahasan dan bahasa ────────────────────────────────────────────────

def test_pembahasan_dan_teks_bahasa_anak_tanpa_istilah_guru_dan_memuat_kunci():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert re.search(r"(?<![\w/])" + re.escape(soal.kunci) + r"(?![\w/])",
                         soal.pembahasan.lower()), (p, soal.pembahasan)
        assert soal.pembahasan.strip() != soal.kunci and len(soal.pembahasan) > 40
        assert "Cocokkan dengan caramu" not in soal.pembahasan
        assert soal.teks.endswith(("?", ")")) and "\n" not in soal.teks


def test_tanpa_nama_orang_dan_data_anak():
    nama = re.compile(r"\b(Rina|Budi|Dita|Ani|Andi)\b")
    for p in _domain():
        soal = _soal(p)
        assert not nama.search(soal.teks + soal.pembahasan)


# ── penolakan parameter di luar domain ───────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada"),
    dict(varian="peluang_pecahan", merah=2, biru=4, tanya="merah"),          # tidak sederhana
    dict(varian="peluang_pecahan", merah=1, biru=4, tanya="merah"),          # pembilang 1
    dict(varian="peluang_pecahan", merah=4, biru=1, tanya="biru"),
    dict(varian="peluang_pecahan", merah=3, biru=3, tanya="merah"),          # jumlah sama
    dict(varian="peluang_pecahan", merah=5, biru=7, tanya="merah"),          # total > 10
    dict(varian="peluang_pecahan", merah=3, biru=2, tanya="hijau"),
    dict(varian="peluang_pecahan", merah=3, biru=2),
    dict(varian="peluang_pecahan", merah=3, biru=2, tanya="merah", hijau=1),
    dict(varian="peluang_pecahan", merah=True, biru=2, tanya="merah"),
    dict(varian="peluang_pecahan", merah="3", biru=2, tanya="merah"),
    dict(varian="peluang_pecahan", merah=3.0, biru=2, tanya="merah"),
    dict(varian="peluang_pecahan", merah=-3, biru=2, tanya="merah"),
    dict(varian="kepastian", isi="merah", n=4, tanya="ungu"),
    dict(varian="kepastian", isi="merah", n=7, tanya="biru"),
    dict(varian="kepastian", isi="merah", n=4, tanya="hijau"),               # bukan pasangan sah
    dict(varian="kepastian", isi="merah", n=4),
    dict(varian="kepastian", isi=None, n=4, tanya="biru"),
    dict(varian="lebih_mungkin", merah=3, biru=3, hijau=7, arah="terbanyak"),  # tak tunggal
    dict(varian="lebih_mungkin", merah=2, biru=4, hijau=7, arah="paling"),
    dict(varian="lebih_mungkin", merah=0, biru=4, hijau=7, arah="terbanyak"),
    dict(varian="lebih_mungkin", merah=2, biru=4, hijau=7),
    dict(varian="lebih_mungkin", merah=2, biru=4, hijau=8, arah="terbanyak"),  # pola tak terdaftar
    dict(varian="banyak_hasil", objek="dadu", syarat="lebih_dari", k=5),     # hanya satu hasil
    dict(varian="banyak_hasil", objek="dadu", syarat="lebih_dari", k=6),     # nol hasil
    dict(varian="banyak_hasil", objek="dadu", syarat="lebih_dari", k=0),     # semua hasil
    dict(varian="banyak_hasil", objek="dadu", syarat="genap", k=2),
    dict(varian="banyak_hasil", objek="dadu", syarat="lebih_dari"),
    dict(varian="banyak_hasil", objek="koin", syarat="genap"),
    dict(varian="banyak_hasil", objek="kartu", syarat="prima"),
    dict(varian="banyak_hasil", objek="kartu", syarat="kelipatan", k=10),
    dict(varian="banyak_hasil", objek="kartu", syarat="kelipatan", k=1),
    dict(varian="banyak_hasil", objek="kartu", syarat="kurang_dari", k=True),
    dict(varian="banyak_hasil", objek="kartu", syarat="kurang_dari", k=2),   # satu hasil
])
def test_parameter_tidak_sah_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.peluang_dasar(**parameter)


def test_parameter_tanpa_varian_ditolak():
    with pytest.raises(TypeError):
        modul.peluang_dasar()
    with pytest.raises(ValueError, match="di luar domain"):
        modul.peluang_dasar(varian=None)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
import awal_peluang_dasar as m
hasil = []
for seed in range(120):
    p = m.parameter(random.Random(seed), "P6")
    s = m.peluang_dasar(**p)
    hasil.append([p, s.teks, s.kunci, s.pembahasan,
                  [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
hasil.append([[d, m.peluang_dasar(**d).teks] for d in m.domain_parameter("P6")])
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
        s = modul.peluang_dasar(**p)
        hasil.append([p, s.teks, s.kunci, s.pembahasan,
                      [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
    hasil.append([[d, modul.peluang_dasar(**d).teks] for d in modul.domain_parameter(LEVEL)])
    return json.loads(json.dumps(hasil, sort_keys=True))


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert a == _dalam_proses(), "proses anak harus memuat modul yang sama dengan tes"
