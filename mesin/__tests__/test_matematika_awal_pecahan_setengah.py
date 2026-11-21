"""Matematika Awal, jenis pecahan_setengah (P2): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal: arti kata pecahan
(separuh/setengah = 2 bagian sama besar, seperempat = 4) dan nama anak/benda ditulis
ulang di tes ini, bukan diimpor dari modul. Solver juga memeriksa ulang aturan domain
dari teks (jumlah benda <= 40, genap untuk separuh, kelipatan 4 untuk seperempat,
hasil bagi bilangan bulat), jadi domain yang dilebarkan ke nilai tak sah merah.
Malrule hanya HIPOTESIS kesalahan umum yang ditinjau guru; yang dijaga di sini:
bukan kunci, tidak kembar, selalu ada jalur K, dan pengecoh pilihan ganda cukup.
Tes ini tidak bergantung pada pendaftaran topik: modul diimpor langsung.
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

AKAR_MESIN = Path(__file__).resolve().parents[1]
if str(AKAR_MESIN) not in sys.path:
    sys.path.insert(0, str(AKAR_MESIN))

import awal_pecahan_setengah as modul  # noqa: E402
import diagnosis  # noqa: E402
from templates import Soal  # noqa: E402

TID = "pecahan_setengah"
LEVEL = "P2"
SEED = range(200)
VARIAN = ("separuh", "seperempat", "potong_sama", "sisa")
UKURAN_DOMAIN = {"P2": 84}
UKURAN_PER_VARIAN = {"separuh": 24, "seperempat": 24, "potong_sama": 6, "sisa": 30}
MINIMAL_DOMAIN = 15
BATAS_BENDA = 40
TERLARANG = re.compile(r"malrule|diagnosis|kode|template|kunci|hipotesis|guru", re.I)

# ── fakta ditulis ulang di tes (sumber independen) ───────────────────────

NAMA_TES = {"dita", "budi", "rina", "eko", "sari", "tono"}
BENDA_JAMAK_TES = {"kelereng", "permen", "stiker"}
BENDA_UTUH_TES = {"roti", "pizza", "kue"}
PENYEBUT_TES = {"setengah": 2, "separuh": 2, "seperempat": 4}


def _solver_cerita(teks: str) -> str:
    cocok = re.fullmatch(
        r"(\w+) punya (\d+) (\w+)\. (Separuhnya|Seperempat dari \3 itu) diberikan kepada (\w+)\. "
        r"Berapa \3 yang (diberikan kepada \5|masih dimiliki \1)\?", teks)
    assert cocok, ("bentuk teks cerita tidak dikenal", teks)
    pemilik, n, benda, bagian, penerima, tanya = cocok.groups()
    n = int(n)
    assert pemilik.lower() in NAMA_TES and penerima.lower() in NAMA_TES and pemilik != penerima, teks
    assert benda in BENDA_JAMAK_TES, teks
    penyebut = PENYEBUT_TES["separuh" if bagian == "Separuhnya" else "seperempat"]
    assert 0 < n <= BATAS_BENDA, ("jumlah benda di luar batas kelas 2", teks)
    assert n % penyebut == 0, ("jumlah benda tidak habis dibagi", teks)
    diberikan = n // penyebut
    if penyebut == 4:
        assert n >= 8, ("seperempat n=4 hanya 1 benda; di luar domain", teks)
    return str(diberikan if tanya.startswith("diberikan") else n - diberikan)


def _solver_potong(teks: str) -> str:
    cocok = re.fullmatch(
        r"Sebuah (\w+) dipotong menjadi bagian-bagian yang sama besar\. Satu bagian besarnya "
        r"(setengah|seperempat) \1\. Berapa bagian sama besar itu yang menyusun satu \1 utuh\?", teks)
    assert cocok, ("bentuk teks potong tidak dikenal", teks)
    assert cocok.group(1) in BENDA_UTUH_TES, teks
    return str(PENYEBUT_TES[cocok.group(2)])


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; sengaja tidak memakai parameter atau tabel modul."""
    if teks.startswith("Sebuah "):
        return _solver_potong(teks)
    return _solver_cerita(teks)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(p: dict) -> Soal:
    return modul.pecahan_setengah(**p)


def _norm(teks: str) -> str:
    return diagnosis.normalisasi(teks)


def _per_varian(varian: str) -> list:
    return [p for p in _domain() if p["varian"] == varian]


def _n_teks(soal: Soal) -> int:
    return int(re.search(r"punya (\d+) ", soal.teks).group(1))


# ── modul, domain, sampler ───────────────────────────────────────────────

def test_kontrak_modul():
    assert modul.TEMPLATE_ID == TID
    assert modul.LEVEL == ("P2",)
    assert callable(modul.pecahan_setengah) and callable(modul.parameter)
    assert callable(modul.domain_parameter)


def test_domain_eksplisit_unik_skalar_dan_cukup_besar():
    domain = _domain()
    assert len(domain) == UKURAN_DOMAIN[LEVEL]
    assert len(domain) >= MINIMAL_DOMAIN
    assert len({json.dumps(p, sort_keys=True) for p in domain}) == len(domain), "domain berisi duplikat"
    for p in domain:
        assert all(type(v) in (str, int) for v in p.values()), p
        assert json.loads(json.dumps(p)) == p
    assert {p["varian"] for p in domain} == set(VARIAN)
    for varian, ukuran in UKURAN_PER_VARIAN.items():
        assert len(_per_varian(varian)) == ukuran, varian
    _domain()[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] != "rusak"


def test_domain_mencakup_semua_cabang_dan_angka_kecil():
    assert {p["n"] for p in _per_varian("separuh")} == {6, 8, 10, 12, 14, 16, 18, 20}
    assert {p["n"] for p in _per_varian("seperempat")} == {8, 12, 16, 20, 24, 28, 32, 40}
    sisa = _per_varian("sisa")
    assert {p["bagian"] for p in sisa} == {"separuh", "seperempat"}
    assert {p["n"] for p in sisa if p["bagian"] == "separuh"} == {8, 12, 16, 20}
    assert {p["n"] for p in sisa if p["bagian"] == "seperempat"} == {8, 12, 16, 20, 24, 32}
    assert {(p["pecahan"], p["benda"]) for p in _per_varian("potong_sama")} == {
        (f, b) for f in ("setengah", "seperempat") for b in range(3)}
    assert {p["cerita"] for p in _domain() if "cerita" in p} == {0, 1, 2}
    assert all(p["n"] <= BATAS_BENDA for p in _domain() if "n" in p)


def test_domain_hanya_level_p2():
    for level in ("P1", "P3", "P6", "", None, "p2"):
        with pytest.raises(ValueError, match="level"):
            modul.domain_parameter(level)
        with pytest.raises(ValueError, match="level"):
            modul.parameter(random.Random(0), level)


def test_sampel_seed_selalu_di_domain_dan_menutup_domain():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    terambil = set()
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        terambil.add(json.dumps(p, sort_keys=True))
    for seed in range(200, 1500):
        terambil.add(json.dumps(modul.parameter(random.Random(seed), LEVEL), sort_keys=True))
    assert len(terambil) >= 0.95 * len(kanon), (len(terambil), len(kanon))


def test_sampler_sama_untuk_seed_sama_dan_tidak_menodai_domain():
    a = modul.parameter(random.Random(7), LEVEL)
    assert a == modul.parameter(random.Random(7), LEVEL)
    a["varian"] = "rusak"
    assert modul.parameter(random.Random(7), LEVEL)["varian"] != "rusak"


# ── kunci, solver ────────────────────────────────────────────────────────

def test_seluruh_domain_menghasilkan_soal_sah_dengan_kunci_solver():
    for p in _domain():
        soal = _soal(p)
        assert isinstance(soal, Soal) and soal.template_id == TID and soal.bagian == "A"
        assert soal.parameter == p
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert re.fullmatch(r"[1-9][0-9]*", soal.kunci), soal.kunci
        assert "\n" not in soal.teks and soal.teks.endswith("?")


def test_teks_unik_di_seluruh_domain():
    teks = [_soal(p).teks for p in _domain()]
    assert len(set(teks)) == len(teks), "dua parameter berbeda menghasilkan teks yang sama"


def test_kunci_contoh_tangan():
    f = modul.pecahan_setengah
    soal = f(varian="separuh", n=12, cerita=0)
    assert soal.teks == ("Dita punya 12 kelereng. Separuhnya diberikan kepada Budi. "
                         "Berapa kelereng yang diberikan kepada Budi?")
    assert soal.kunci == "6"
    soal = f(varian="seperempat", n=40, cerita=1)
    assert soal.teks == ("Rina punya 40 permen. Seperempat dari permen itu diberikan kepada Eko. "
                         "Berapa permen yang diberikan kepada Eko?")
    assert soal.kunci == "10"
    soal = f(varian="sisa", bagian="seperempat", n=12, cerita=2)
    assert soal.teks == ("Sari punya 12 stiker. Seperempat dari stiker itu diberikan kepada Tono. "
                         "Berapa stiker yang masih dimiliki Sari?")
    assert soal.kunci == "9"
    assert f(varian="sisa", bagian="separuh", n=8, cerita=0).kunci == "4"
    assert f(varian="potong_sama", pecahan="setengah", benda=0).kunci == "2"
    soal = f(varian="potong_sama", pecahan="seperempat", benda=1)
    assert soal.kunci == "4" and "pizza" in soal.teks


def test_seperempat_dan_sisa_seperempat_selalu_beda_dari_separuh():
    for n in (8, 12, 16, 20, 24, 32):
        seperempat = _soal(dict(varian="seperempat", n=n, cerita=0)).kunci
        sisa = _soal(dict(varian="sisa", bagian="seperempat", n=n, cerita=0)).kunci
        assert int(seperempat) + int(sisa) == n
        assert int(sisa) == 3 * int(seperempat)


# ── malrule dan pilihan ganda ────────────────────────────────────────────

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
        assert all(m.alasan.strip() and m.alasan[0].isupper() and m.alasan.endswith(".")
                   for m in soal.malrule)
        assert all(re.fullmatch(r"[1-9][0-9]*", m.jawaban) for m in soal.malrule), p


def test_pengecoh_pilihan_ganda_cukup_dari_malrule_saja():
    for p in _domain():
        soal = _soal(p)
        beda = {_norm(m.jawaban) for m in soal.malrule} - {_norm(soal.kunci)}
        assert len(beda) >= 2, (p, beda)


def _jawaban(soal: Soal) -> dict:
    return {m.jawaban: m.kode for m in soal.malrule}


def test_malrule_separuh_tidak_dibagi_dan_kurang_satu():
    for p in _per_varian("separuh"):
        soal = _soal(p)
        n, k = p["n"], p["n"] // 2
        harapan = {str(n): "K", str(k - 1): "H"}
        if n % 4 == 0:
            harapan[str(n // 4)] = "K"
        assert _jawaban(soal) == harapan, (p, _jawaban(soal))


def test_malrule_seperempat_dibagi_dua_sisa_dan_kurang_satu():
    for p in _per_varian("seperempat"):
        n, k = p["n"], p["n"] // 4
        assert _jawaban(_soal(p)) == {str(n // 2): "K", str(3 * k): "K", str(k - 1): "H"}, p


def test_malrule_sisa_per_bagian():
    for p in _per_varian("sisa"):
        n = p["n"]
        if p["bagian"] == "separuh":
            harapan = {str(3 * n // 4): "K", str(n): "K", str(n // 2 - 1): "H"}
        else:
            harapan = {str(n // 4): "K", str(n // 2): "K", str(n): "K", str(3 * n // 4 - 1): "H"}
        assert _jawaban(_soal(p)) == harapan, (p, _jawaban(_soal(p)))


def test_malrule_potong_sama_mencampur_setengah_dan_seperempat():
    for p in _per_varian("potong_sama"):
        jawaban = _jawaban(_soal(p))
        if p["pecahan"] == "seperempat":
            assert jawaban == {"2": "K", "1": "K", "3": "H"}, p
        else:
            assert jawaban == {"4": "K", "1": "K"}, p


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_tanpa_istilah_guru_dan_memuat_jawaban():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert re.search(r"(?<![0-9])%s(?![0-9])" % soal.kunci, soal.pembahasan), (p, soal.pembahasan)
        assert soal.pembahasan.strip() != soal.kunci and len(soal.pembahasan) > 40
        assert "Cocokkan dengan caramu" not in soal.pembahasan


def test_pembahasan_menunjukkan_hitungan_yang_benar():
    for p in _per_varian("separuh"):
        n = p["n"]
        assert f"{n} ÷ 2 = {n // 2}" in _soal(p).pembahasan
    for p in _per_varian("seperempat"):
        n = p["n"]
        assert f"{n} ÷ 4 = {n // 4}" in _soal(p).pembahasan
    for p in _per_varian("sisa"):
        n, d = p["n"], 2 if p["bagian"] == "separuh" else 4
        bahas = _soal(p).pembahasan
        assert f"{n} ÷ {d} = {n // d}" in bahas and f"{n} − {n // d} = {n - n // d}" in bahas
    for p in _per_varian("potong_sama"):
        d = 2 if p["pecahan"] == "setengah" else 4
        assert re.search(r"\b%d bagian" % d, _soal(p).pembahasan)


# ── penolakan parameter di luar domain ───────────────────────────────────

_SEP = dict(varian="separuh", n=12, cerita=0)
_PER = dict(varian="seperempat", n=16, cerita=0)
_POT = dict(varian="potong_sama", pecahan="setengah", benda=0)
_SIS = dict(varian="sisa", bagian="separuh", n=8, cerita=0)


def _ubah(dasar: dict, **perubahan) -> dict:
    hasil = {**dasar, **perubahan}
    return {k: v for k, v in hasil.items() if v is not ...}


@pytest.mark.parametrize("parameter", [
    _ubah(_SEP, n=22), _ubah(_SEP, n=4), _ubah(_SEP, n=5), _ubah(_SEP, n=0), _ubah(_SEP, n=-6),
    _ubah(_SEP, n=42), _ubah(_SEP, n=100), _ubah(_SEP, n="12"), _ubah(_SEP, n=12.0),
    _ubah(_SEP, n=True), _ubah(_SEP, n=...), _ubah(_SEP, cerita=3), _ubah(_SEP, cerita=-1),
    _ubah(_SEP, cerita="0"), _ubah(_SEP, cerita=...), _ubah(_SEP, bagian="separuh"),
    _ubah(_SEP, extra=1),
    _ubah(_PER, n=4), _ubah(_PER, n=10), _ubah(_PER, n=36), _ubah(_PER, n=44), _ubah(_PER, n=6),
    _ubah(_PER, n=0), _ubah(_PER, cerita=5),
    _ubah(_POT, pecahan="sepertiga"), _ubah(_POT, pecahan="separuh"), _ubah(_POT, pecahan=...),
    _ubah(_POT, benda=3), _ubah(_POT, benda=-1), _ubah(_POT, benda="0"), _ubah(_POT, benda=...),
    _ubah(_POT, n=4), _ubah(_POT, cerita=0),
    _ubah(_SIS, n=10), _ubah(_SIS, n=24), _ubah(_SIS, n=4), _ubah(_SIS, n=40),
    _ubah(_SIS, bagian="seperempat", n=28), _ubah(_SIS, bagian="seperempat", n=40),
    _ubah(_SIS, bagian="sepertiga"), _ubah(_SIS, bagian=...), _ubah(_SIS, bagian=["separuh"]),
    _ubah(_SIS, cerita=3),
    dict(varian="tidak_ada"), dict(varian=None), dict(varian=["separuh"]),
])
def test_parameter_tidak_sah_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.pecahan_setengah(**parameter)


def test_parameter_sah_tidak_ditolak():
    for dasar in (_SEP, _PER, _POT, _SIS):
        assert isinstance(modul.pecahan_setengah(**dasar), Soal)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
import awal_pecahan_setengah as m
def ringkas(p):
    s = m.pecahan_setengah(**p)
    return [p, s.teks, s.kunci, s.pembahasan,
            [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]]
hasil = [ringkas(m.parameter(random.Random(seed), "P2")) for seed in range(80)]
hasil += [ringkas(p) for p in m.domain_parameter("P2")]
print(json.dumps(hasil))
"""


def _proses(hash_seed: str):
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    hasil = subprocess.run([sys.executable, "-c", _KODE % {"akar": str(AKAR_MESIN)}],
                           env=env, capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    a, b, c = _proses("1"), _proses("2"), _proses("random")
    assert a == b == c
    assert len(a) == 80 + UKURAN_DOMAIN[LEVEL]
    domain_ini = [[p, _soal(p).teks, _soal(p).kunci] for p in _domain()]
    assert [x[:3] for x in a[80:]] == json.loads(json.dumps(domain_ini))
