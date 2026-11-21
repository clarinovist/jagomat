"""Matematika Awal, jenis waktu_berat_awal (P2): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (regex) dan memeriksa
sendiri batas domain yang dijanjikan (jam penuh 1..12 tanpa melewati tengah hari,
lama 1..6 jam, berat 1..10 kg dengan dua berat berbeda). Modul jenis diimpor
langsung; tes ini tidak bergantung pada registrasi topik. Malrule hanya HIPOTESIS
kesalahan umum untuk ditinjau guru: yang dijaga di sini bukan kunci, tidak kembar,
dan selalu ada jalur K.
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

import awal_waktu_berat_awal as jenis
import templates
from templates import Soal

TID = "waktu_berat_awal"
LEVEL = "P2"
SEED = range(200)
VARIAN = ("lama_kegiatan", "jam_penuh_setelah", "jumlah_berat", "banding_berat")
UKURAN_DOMAIN = {"lama_kegiatan": 204, "jam_penuh_setelah": 51,
                 "jumlah_berat": 180, "banding_berat": 180}
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|kunci|template|hipotesis", re.I)
KATA_ANGKA = {"Satu": 1, "Dua": 2, "Tiga": 3, "Empat": 4, "Lima": 5, "Enam": 6}


# ── solver terpisah: hanya membaca teks ──────────────────────────────────

def solver_dari_teks(teks: str) -> str:
    cocok = re.fullmatch(
        r"([A-Z][a-z]+) mulai ([a-z ]+) pukul (\d+) dan selesai pukul (\d+)\. "
        r"Berapa jam \1 \2\?", teks)
    if cocok:
        mulai, selesai = int(cocok.group(3)), int(cocok.group(4))
        assert 1 <= mulai < selesai <= 12, ("jam di luar 1..12 atau mundur", teks)
        assert selesai - mulai <= 6, ("lebih dari 6 jam", teks)
        return str(selesai - mulai)
    cocok = re.fullmatch(r"Sekarang pukul (\d+)\. (Satu|Dua|Tiga|Empat|Lima|Enam) jam lagi "
                         r"pukul berapa\?", teks)
    if cocok:
        sekarang, tambah = int(cocok.group(1)), KATA_ANGKA[cocok.group(2)]
        assert 1 <= sekarang and sekarang + tambah <= 12, ("hasil melewati pukul 12", teks)
        return str(sekarang + tambah)
    cocok = re.fullmatch(r"Satu kantong berisi (\d+) kg (\w+) dan kantong lain berisi "
                         r"(\d+) kg (\w+)\. Berapa kg semuanya\?", teks)
    if cocok:
        a, b = int(cocok.group(1)), int(cocok.group(3))
        assert 1 <= a <= 10 and 1 <= b <= 10 and a != b, ("berat di luar batas", teks)
        assert cocok.group(2) != cocok.group(4)
        assert a + b <= 20
        return str(a + b)
    cocok = re.fullmatch(r"([A-Z][a-z]+) (\d+) kg, (\w+) (\d+) kg\. Berapa kg lebih berat "
                         r"(\w+)\?", teks)
    if cocok:
        berat = {cocok.group(1).lower(): int(cocok.group(2)),
                 cocok.group(3): int(cocok.group(4))}
        assert len(berat) == 2 and all(1 <= v <= 10 for v in berat.values()), teks
        ditanya = cocok.group(5)
        assert ditanya in berat, ("benda yang ditanya tidak ada di soal", teks)
        (lain,) = [n for n in berat if n != ditanya]
        assert berat[ditanya] > berat[lain], ("yang ditanya harus lebih berat", teks)
        return str(berat[ditanya] - berat[lain])
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


def _soal(p: dict) -> Soal:
    return getattr(jenis, TID)(**p)


def _domain() -> tuple:
    return jenis.domain_parameter(LEVEL)


def _norm(teks: str) -> str:
    return re.sub(r"\s+", "", teks.strip().lower())


# ── kontrak modul ────────────────────────────────────────────────────────

def test_kontrak_modul_dan_level():
    assert jenis.TEMPLATE_ID == TID == getattr(jenis, TID).__name__
    assert jenis.LEVEL == ("P2",)
    with pytest.raises(ValueError):
        jenis.domain_parameter("P1")
    with pytest.raises(ValueError):
        jenis.parameter(random.Random(0), "P3")


# ── domain dan sampler ───────────────────────────────────────────────────

def test_domain_eksplisit_ukuran_per_varian_dan_tanpa_duplikat():
    domain = _domain()
    per_varian = {v: sum(1 for p in domain if p["varian"] == v) for v in VARIAN}
    assert per_varian == UKURAN_DOMAIN
    assert len(domain) == sum(UKURAN_DOMAIN.values()) == 615
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"
    for varian in VARIAN:
        assert UKURAN_DOMAIN[varian] >= 15


def test_domain_dict_baru_setiap_panggilan():
    _domain()[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] == "lama_kegiatan"


def test_sampler_selalu_di_dalam_domain_dan_menyentuh_semua_varian():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian = set()
    for seed in SEED:
        p = jenis.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
    assert varian == set(VARIAN)


def test_sampler_murni_dari_rng_seed_sama_hasil_sama():
    for seed in SEED:
        assert (jenis.parameter(random.Random(seed), LEVEL)
                == jenis.parameter(random.Random(seed), LEVEL))


# ── kunci lawan solver teks ──────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)
        assert soal.parameter == p
        assert soal.bagian == "A" and soal.template_id == TID
        assert re.fullmatch(r"[1-9][0-9]*", soal.kunci), soal.kunci


def test_sampel_seed_kunci_sama_dengan_solver():
    for seed in SEED:
        soal = _soal(jenis.parameter(random.Random(seed), LEVEL))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_kunci_contoh_tangan():
    f = getattr(jenis, TID)
    lama = f("lama_kegiatan", kegiatan=0, mulai=2, lama=3)
    assert lama.teks == "Rina mulai belajar pukul 2 dan selesai pukul 5. Berapa jam Rina belajar?"
    assert lama.kunci == "3"
    setelah = f("jam_penuh_setelah", sekarang=4, tambah=3)
    assert setelah.teks == "Sekarang pukul 4. Tiga jam lagi pukul berapa?"
    assert setelah.kunci == "7"
    assert f("jam_penuh_setelah", sekarang=6, tambah=6).kunci == "12"
    jumlah = f("jumlah_berat", barang=0, a=2, b=3)
    assert jumlah.teks == ("Satu kantong berisi 2 kg beras dan kantong lain berisi 3 kg gula. "
                           "Berapa kg semuanya?")
    assert jumlah.kunci == "5"
    banding = f("banding_berat", barang=0, a=5, b=3)
    assert banding.teks == "Beras 5 kg, gula 3 kg. Berapa kg lebih berat beras?"
    assert banding.kunci == "2"
    assert f("banding_berat", barang=0, a=3, b=5).teks.endswith("lebih berat gula?")
    assert f("banding_berat", barang=0, a=3, b=5).kunci == "2"


def test_soal_hanya_kg_dan_jam_penuh_tanpa_gram_atau_menit():
    for p in _domain():
        teks = _soal(p).teks
        assert not re.search(r"\bgram\b|\bg\b|menit|setengah|:\d\d", teks), teks


def test_domain_mencakup_batas_atas_dan_bawah():
    domain = _domain()
    lama = [p for p in domain if p["varian"] == "lama_kegiatan"]
    assert {p["lama"] for p in lama} == set(range(1, 7))
    assert max(p["mulai"] + p["lama"] for p in lama) == 12
    assert min(p["mulai"] for p in lama) == 1
    setelah = [p for p in domain if p["varian"] == "jam_penuh_setelah"]
    assert max(p["sekarang"] + p["tambah"] for p in setelah) == 12
    berat = [p for p in domain if p["varian"] in ("jumlah_berat", "banding_berat")]
    assert {p["a"] for p in berat} == set(range(1, 11))
    assert all(p["a"] != p["b"] for p in berat)


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        kunci = _norm(soal.kunci)
        jawaban = [_norm(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert all(re.fullmatch(r"[1-9][0-9]*", m.jawaban) for m in soal.malrule), p
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)


def test_setiap_parameter_punya_dua_pengecoh_berbeda_untuk_pilihan_ganda():
    for p in _domain():
        assert len(_soal(p).malrule) >= 2, p


def _malrule(p: dict) -> dict:
    return {m.id.split(".", 1)[1]: m for m in _soal(p).malrule}


def test_malrule_lama_kegiatan_jam_akhir_dijumlah_dan_hitung_dobel():
    m = _malrule(dict(varian="lama_kegiatan", kegiatan=0, mulai=2, lama=3))
    assert m["jam_akhir"].jawaban == "5" and m["jam_akhir"].kode == "K"
    assert m["dijumlah"].jawaban == "7" and m["dijumlah"].kode == "K"
    assert m["hitung_dobel"].jawaban == "4" and m["hitung_dobel"].kode == "H"


def test_malrule_jam_penuh_setelah_lama_saja_dan_dikurangi():
    m = _malrule(dict(varian="jam_penuh_setelah", sekarang=7, tambah=3))
    assert m["lama_saja"].jawaban == "3" and m["lama_saja"].kode == "K"
    assert m["dikurangi"].jawaban == "4" and m["dikurangi"].kode == "K"
    assert m["hitung_dobel"].jawaban == "9" and m["hitung_dobel"].kode == "H"
    assert m["lebih_satu"].jawaban == "11" and m["lebih_satu"].kode == "H"
    assert "lebih_satu" not in _malrule(dict(varian="jam_penuh_setelah", sekarang=6, tambah=6))
    # mengurang yang hasilnya bukan bilangan positif tidak dijadikan pengecoh
    rendah = _malrule(dict(varian="jam_penuh_setelah", sekarang=2, tambah=5))
    assert "dikurangi" not in rendah


def test_malrule_berat_menjumlah_lawan_mengurang():
    jumlah = _malrule(dict(varian="jumlah_berat", barang=0, a=2, b=7))
    assert jumlah["dikurangi"].jawaban == "5" and jumlah["dikurangi"].kode == "K"
    banding = _malrule(dict(varian="banding_berat", barang=0, a=2, b=7))
    assert banding["dijumlah"].jawaban == "9" and banding["dijumlah"].kode == "K"
    assert banding["berat_terberat"].jawaban == "7"
    assert {m.kode for m in _soal(dict(varian="jumlah_berat", barang=0, a=2, b=7)).malrule} == {"K", "H"}


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in re.findall(r"\d+", soal.pembahasan), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40
        assert soal.pembahasan.strip() != soal.kunci


def test_tanpa_nama_anak_nyata_hanya_nama_sintetis_umum():
    nama = {n for n, _ in jenis.KEGIATAN}
    assert nama == {"Rina", "Budi", "Dita", "Eko"}


# ── penolakan parameter di luar domain ───────────────────────────────────

@pytest.mark.parametrize("varian, isi", [
    ("tidak_ada", dict(a=1, b=2)),
    (None, dict(a=1, b=2)),
    ("lama_kegiatan", dict(kegiatan=0, mulai=2, lama=0)),
    ("lama_kegiatan", dict(kegiatan=0, mulai=2, lama=7)),
    ("lama_kegiatan", dict(kegiatan=0, mulai=0, lama=3)),
    ("lama_kegiatan", dict(kegiatan=0, mulai=10, lama=3)),   # selesai pukul 13
    ("lama_kegiatan", dict(kegiatan=4, mulai=2, lama=3)),
    ("lama_kegiatan", dict(kegiatan=-1, mulai=2, lama=3)),
    ("lama_kegiatan", dict(kegiatan=0, mulai="2", lama=3)),
    ("lama_kegiatan", dict(kegiatan=0, mulai=2.0, lama=3)),
    ("lama_kegiatan", dict(kegiatan=True, mulai=2, lama=3)),
    ("lama_kegiatan", dict(kegiatan=0, mulai=2)),
    ("lama_kegiatan", dict(kegiatan=0, mulai=2, lama=3, a=1)),
    ("jam_penuh_setelah", dict(sekarang=10, tambah=3)),      # hasil pukul 13
    ("jam_penuh_setelah", dict(sekarang=4, tambah=0)),
    ("jam_penuh_setelah", dict(sekarang=4, tambah=7)),
    ("jam_penuh_setelah", dict(sekarang=0, tambah=3)),
    ("jam_penuh_setelah", dict(sekarang=4)),
    ("jam_penuh_setelah", dict(sekarang=None, tambah=3)),
    ("jumlah_berat", dict(barang=0, a=3, b=3)),
    ("jumlah_berat", dict(barang=0, a=0, b=3)),
    ("jumlah_berat", dict(barang=0, a=11, b=3)),
    ("jumlah_berat", dict(barang=2, a=2, b=3)),
    ("jumlah_berat", dict(barang=0, a=2, b=11)),
    ("jumlah_berat", dict(barang=0, a=2)),
    ("banding_berat", dict(barang=0, a=4, b=4)),
    ("banding_berat", dict(barang=0, a=5, b=-3)),
    ("banding_berat", dict(barang=-1, a=5, b=3)),
    ("banding_berat", dict(barang=0, a=5, b=3, lama=1)),
])
def test_parameter_tidak_sah_ditolak(varian, isi):
    with pytest.raises(ValueError, match="di luar domain"):
        getattr(jenis, TID)(varian, **isi)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path[:0] = json.loads(sys.argv[1])
import awal_waktu_berat_awal as jenis
hasil = []
for seed in range(200):
    p = jenis.parameter(random.Random(seed), "P2")
    s = getattr(jenis, "waktu_berat_awal")(**p)
    hasil.append([p, s.tanda_tangan, s.teks, s.kunci, s.pembahasan,
                  [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    jalur = [str(Path(jenis.__file__).resolve().parent),
             str(Path(templates.__file__).resolve().parent)]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONHASHSEED"] = hash_seed
    hasil = subprocess.run([sys.executable, "-c", _KODE, json.dumps(jalur)],
                           env=env, capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == len(SEED)
