"""Matematika Awal, jenis baca_diagram_gambar (P1): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal: banyak titik "●" dihitung
per baris data, dan tes menjaga bahwa seluruh "●" di teks sama dengan jumlah baris data
(tidak ada simbol yang terhitung dua kali). Daftar kategori per tema ditulis ulang di tes
ini (bukan diimpor dari modul). Malrule hanya HIPOTESIS kesalahan umum yang ditinjau guru;
yang dijaga di sini: bukan kunci (setelah normalisasi jawaban aplikasi), tidak kembar, dan
selalu ada K.

Tes ini memanggil modul jenis langsung, tanpa bergantung pada registrasi topik.
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
import random
import re
import subprocess
import sys

import pytest

import awal_baca_diagram_gambar as modul
import diagnosis
from templates import Soal

TID = "baca_diagram_gambar"
LEVEL = "P1"
SEED = range(200)
VARIAN = ("baca", "terbanyak", "selisih", "jumlah")
SIMBOL = "●"
# 3 tema x 336 triple jumlah berbeda (8*7*6) x (3 pertanyaan | 1 | 3 pasangan | 3 pasangan).
UKURAN_PER_VARIAN = {"baca": 3024, "terbanyak": 1008, "selisih": 3024, "jumlah": 3024}
KATEGORI_TES = {
    "mainan": ("bola", "mobil", "boneka"),
    "buah": ("apel", "jeruk", "pisang"),
    "hewan": ("ayam", "bebek", "kelinci"),
}
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis|intervensi", re.I)

# ── solver terpisah: hanya membaca teks ──────────────────────────────────

POLA_KEPALA = re.compile(r"Diagram gambar ([a-z]+) di ([a-z]+)\. Satu titik hitam mewakili 1 ([a-z]+)\.")
POLA_BARIS = re.compile(rf"([A-Z][a-z]+): ({SIMBOL}+)")


def _baca(teks: str):
    baris = teks.split("\n")
    assert len(baris) == 5, ("harus 1 kepala + 3 baris data + 1 pertanyaan", teks)
    kepala = POLA_KEPALA.fullmatch(baris[0])
    assert kepala, ("kepala tidak dikenal", baris[0])
    banyak = {}
    for isi in baris[1:4]:
        cocok = POLA_BARIS.fullmatch(isi)
        assert cocok, ("baris data tidak dikenal", isi)
        banyak[cocok.group(1).lower()] = len(cocok.group(2))
    assert teks.count(SIMBOL) == sum(banyak.values()), ("simbol terhitung ganda", teks)
    assert SIMBOL not in baris[0] and SIMBOL not in baris[4]
    assert tuple(banyak) in KATEGORI_TES.values(), ("kategori bukan satu tema", banyak)
    assert kepala.group(1) in KATEGORI_TES and tuple(banyak) == KATEGORI_TES[kepala.group(1)]
    assert len(set(banyak.values())) == 3 and all(1 <= n <= 8 for n in banyak.values())
    return banyak, baris[4]


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; sengaja tidak memakai parameter atau isi modul."""
    banyak, tanya = _baca(teks)
    cocok = re.fullmatch(r"Berapa banyak ([a-z]+)\?", tanya)
    if cocok:
        return str(banyak[cocok.group(1)])
    if tanya == "Mana yang paling banyak?":
        terbesar = max(banyak.values())
        pemenang = [k for k, n in banyak.items() if n == terbesar]
        assert len(pemenang) == 1, ("terbanyak harus tunggal", teks)
        return pemenang[0]
    cocok = re.fullmatch(r"([A-Z][a-z]+) lebih banyak berapa daripada ([a-z]+)\?", tanya)
    if cocok:
        atas, bawah = cocok.group(1).lower(), cocok.group(2)
        assert banyak[atas] > banyak[bawah], ("yang ditanya harus yang lebih banyak", teks)
        return str(banyak[atas] - banyak[bawah])
    cocok = re.fullmatch(r"Berapa jumlah ([a-z]+) dan ([a-z]+)\?", tanya)
    assert cocok, ("pertanyaan tidak dikenal", teks)
    pertama, kedua = cocok.group(1), cocok.group(2)
    assert pertama != kedua
    return str(banyak[pertama] + banyak[kedua])


def _soal(parameter: dict) -> Soal:
    return replace(modul.baca_diagram_gambar(**parameter), level=LEVEL)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


# ── domain dan sampler ───────────────────────────────────────────────────

def test_domain_enumerator_eksplisit_tanpa_duplikat_dan_ukuran_per_varian():
    domain = _domain()
    kanon = {json.dumps(p, sort_keys=True) for p in domain}
    assert len(kanon) == len(domain), "domain berisi duplikat"
    for varian, ukuran in UKURAN_PER_VARIAN.items():
        assert sum(p["varian"] == varian for p in domain) == ukuran, varian
    assert len(domain) == sum(UKURAN_PER_VARIAN.values())
    assert {p["tema"] for p in domain} == set(KATEGORI_TES)
    _domain()[0]["tema"] = "rusak"
    assert _domain()[0]["tema"] != "rusak"


def test_jumlah_titik_domain_satu_sampai_delapan_dan_berbeda_tiap_kategori():
    for p in _domain():
        n = (p["n1"], p["n2"], p["n3"])
        assert all(1 <= x <= 8 for x in n) and len(set(n)) == 3, p


def test_sapuan_sampler_seed_semua_anggota_domain():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    dilihat = set()
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        dilihat.add(p["varian"])
    assert dilihat == set(VARIAN)


def test_level_di_luar_p1_ditolak():
    for level in ("P2", "P3", "", "p1", None):
        with pytest.raises(ValueError, match="harus P1"):
            modul.domain_parameter(level)
        with pytest.raises(ValueError, match="harus P1"):
            modul.parameter(random.Random(0), level)
    assert modul.LEVEL == ("P1",)


# ── kunci dan solver ─────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks)
        assert soal.parameter == p
        assert soal.template_id == TID and soal.bagian == "A"
        assert soal.kunci == soal.kunci.strip().lower() and " " not in soal.kunci


def test_sapuan_seed_kunci_sama_dengan_solver_teks():
    for seed in SEED:
        soal = _soal(modul.parameter(random.Random(seed), LEVEL))
        assert soal.kunci == solver_dari_teks(soal.teks), (seed, soal.teks)


def test_jawaban_angka_paling_besar_lima_belas():
    for p in _domain():
        if p["varian"] != "terbanyak":
            assert 1 <= int(_soal(p).kunci) <= 15, p


def test_terbanyak_selalu_tunggal_dan_berupa_nama_kategori_tema_itu():
    for p in _domain():
        if p["varian"] == "terbanyak":
            assert _soal(p).kunci in KATEGORI_TES[p["tema"]], p


def test_kunci_contoh_tangan():
    f = modul.baca_diagram_gambar
    soal = f(varian="baca", tema="mainan", n1=3, n2=5, n3=2, tanya=1)
    assert soal.teks == (
        "Diagram gambar mainan di rak. Satu titik hitam mewakili 1 mainan.\n"
        f"Bola: {SIMBOL * 3}\nMobil: {SIMBOL * 5}\nBoneka: {SIMBOL * 2}\n"
        "Berapa banyak mobil?")
    assert soal.kunci == "5"
    assert f(varian="terbanyak", tema="buah", n1=2, n2=7, n3=4).kunci == "jeruk"
    selisih = f(varian="selisih", tema="hewan", n1=6, n2=1, n3=4, x=0, y=2)
    assert selisih.kunci == "2" and selisih.teks.endswith("Ayam lebih banyak berapa daripada kelinci?")
    assert f(varian="jumlah", tema="mainan", n1=3, n2=5, n3=2, x=0, y=1).kunci == "8"


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_dan_selalu_ada_jalur_k():
    for p in _domain():
        soal = _soal(p)
        kunci = _norm(soal.kunci)
        jawaban = [_norm(m.jawaban) for m in soal.malrule]
        assert kunci not in jawaban, (p, "malrule sama dengan kunci")
        assert len(set(jawaban)) == len(jawaban), (p, "malrule kembar")
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), (p, "tanpa jalur K")
        assert all(m.alasan.strip() and m.alasan[0].isupper() for m in soal.malrule)
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert not any(TERLARANG.search(m.alasan) for m in soal.malrule)


def test_terbanyak_malrule_hanya_k_dua_kategori_lain():
    for p in _domain():
        if p["varian"] != "terbanyak":
            continue
        soal = _soal(p)
        assert {m.kode for m in soal.malrule} == {"K"}, p
        assert {m.jawaban for m in soal.malrule} == set(KATEGORI_TES[p["tema"]]) - {soal.kunci}


def test_baca_malrule_k_baris_lain_dan_h_satu_lebih_kurang():
    for p in _domain():
        if p["varian"] != "baca":
            continue
        soal = _soal(p)
        n = (p["n1"], p["n2"], p["n3"])
        lain = {str(x) for i, x in enumerate(n) if i != p["tanya"]}
        k = {m.jawaban for m in soal.malrule if m.kode == "K"}
        assert k == lain, p
        kunci = int(soal.kunci)
        h = {int(m.jawaban) for m in soal.malrule if m.kode == "H"}
        assert h <= {kunci - 1, kunci + 1} and all(x >= 1 for x in h), p


def test_selisih_dan_jumlah_k_operasi_terbalik_dan_h_valid():
    for p in _domain():
        if p["varian"] not in ("selisih", "jumlah"):
            continue
        soal = _soal(p)
        n = (p["n1"], p["n2"], p["n3"])
        a, b = n[p["x"]], n[p["y"]]
        terbalik = a + b if p["varian"] == "selisih" else abs(a - b)
        k = {int(m.jawaban) for m in soal.malrule if m.kode == "K"}
        assert k == {terbalik}, p
        kunci = int(soal.kunci)
        h = {int(m.jawaban) for m in soal.malrule if m.kode == "H"}
        assert h <= {kunci - 1, kunci + 1} and all(x >= 1 for x in h), p


def test_pembahasan_bahasa_anak_tanpa_istilah_guru_dan_memuat_kunci():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan.lower(), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40


# ── penolakan parameter di luar domain ───────────────────────────────────

BAIK = dict(varian="baca", tema="mainan", n1=3, n2=5, n3=2, tanya=1)
BAIK_SELISIH = dict(varian="selisih", tema="mainan", n1=3, n2=5, n3=2, x=1, y=0)
BAIK_JUMLAH = dict(varian="jumlah", tema="mainan", n1=3, n2=5, n3=2, x=0, y=1)
BAIK_TERBANYAK = dict(varian="terbanyak", tema="mainan", n1=3, n2=5, n3=2)


@pytest.mark.parametrize("dasar,ubah", [
    (BAIK, dict(varian="tidak_ada")),
    (BAIK, dict(varian=None)),
    (BAIK, dict(tema="olahraga")),
    (BAIK, dict(tema=None)),
    (BAIK, dict(n1=0)),
    (BAIK, dict(n1=9)),
    (BAIK, dict(n1=5)),            # dua jumlah sama
    (BAIK, dict(n3=3)),
    (BAIK, dict(n1=True)),
    (BAIK, dict(n1=3.0)),
    (BAIK, dict(n2="5")),
    (BAIK, dict(tanya=3)),
    (BAIK, dict(tanya=-1)),
    (BAIK, dict(tanya=None)),
    (BAIK, dict(tanya="1")),
    (BAIK, dict(x=0)),
    (BAIK_TERBANYAK, dict(tanya=0)),
    (BAIK_TERBANYAK, dict(x=0, y=1)),
    (BAIK_SELISIH, dict(x=0, y=1)),     # yang pertama harus lebih banyak
    (BAIK_SELISIH, dict(x=1, y=1)),
    (BAIK_SELISIH, dict(y=None)),
    (BAIK_SELISIH, dict(tanya=0)),
    (BAIK_SELISIH, dict(x=3)),
    (BAIK_JUMLAH, dict(x=1, y=0)),      # pasangan jumlah berurut naik
    (BAIK_JUMLAH, dict(x=1, y=1)),
    (BAIK_JUMLAH, dict(y=3)),
    (BAIK_JUMLAH, dict(tanya=0)),
])
def test_parameter_tidak_sah_ditolak(dasar, ubah):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.baca_diagram_gambar(**{**dasar, **ubah})


def test_parameter_sah_pembanding_tidak_ditolak():
    for dasar in (BAIK, BAIK_SELISIH, BAIK_JUMLAH, BAIK_TERBANYAK):
        assert modul.baca_diagram_gambar(**dasar).kunci


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, sys
sys.path[:0] = json.loads(sys.argv[1])
import random
import awal_baca_diagram_gambar as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P1")
    s = m.baca_diagram_gambar(**p)
    hasil.append([p, s.teks, s.kunci, s.pembahasan,
                  [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
hasil.append([len(m.domain_parameter("P1")), m.domain_parameter("P1")[::97]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    env = {k: v for k, v in os.environ.items() if k != "PYTHONHASHSEED"}
    env["PYTHONHASHSEED"] = hash_seed
    hasil = subprocess.run([sys.executable, "-c", _KODE, json.dumps(sys.path)],
                           env=env, capture_output=True, text=True, timeout=180)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == 151
