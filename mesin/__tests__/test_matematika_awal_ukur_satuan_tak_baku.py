"""Matematika Awal, jenis ukur_satuan_tak_baku (P1): domain, solver teks, malrule, determinisme.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (regex): panjang tiap benda
dan satuannya dibaca dari kalimat "X panjangnya N satuan.", lalu kunci dihitung ulang dari
pertanyaannya. Daftar benda yang masuk akal per satuan ditulis ulang di tes ini (bukan
diimpor dari modul). Malrule hanya HIPOTESIS kesalahan umum yang ditinjau guru; yang dijaga
di sini: bukan kunci (setelah normalisasi jawaban aplikasi), tidak kembar, dan selalu ada K.

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

import awal_ukur_satuan_tak_baku as modul
import diagnosis
from templates import Soal

TID = "ukur_satuan_tak_baku"
LEVEL = "P1"
SEED = range(200)
VARIAN = ("banding", "selisih", "sambung")
SATUAN_TES = ("klip", "ubin", "balok")
# Dua panjang berbeda 3..10: 8 x 7 pasangan; 3 satuan x 3 pasangan benda (banding/selisih)
# atau 3 jenis benda (sambung). Ditulis ulang di sini, bukan diimpor.
UKURAN_PER_VARIAN = {"banding": 504, "selisih": 504, "sambung": 504}
PANJANG_MAKS_TES = 10
BENDA_BANDING_TES = {
    "klip": {"pensil", "buku", "sendok"},
    "ubin": {"meja", "lemari", "karpet"},
    "balok": {"sapu", "tongkat", "payung"},
}
BENDA_SAMBUNG_TES = {"pita", "tali", "kain"}
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis|intervensi", re.I)

# ── solver terpisah: hanya membaca teks ──────────────────────────────────

NAMA = r"[A-Z][a-z]+(?: [a-z]+)?"
POLA_DATA = re.compile(
    rf"({NAMA}) panjangnya (\d+) ([a-z]+)\. ({NAMA}) panjangnya (\d+) ([a-z]+)\. (.+)", re.S)


def _baca_data(teks: str):
    cocok = POLA_DATA.fullmatch(teks)
    assert cocok, ("bentuk teks tidak dikenal", teks)
    n1, p1, s1, n2, p2, s2, tanya = cocok.groups()
    assert s1 == s2 and s1 in SATUAN_TES, ("satuan harus sama dan tak baku", teks)
    assert n1 != n2, ("dua benda harus berbeda", teks)
    p1, p2 = int(p1), int(p2)
    assert 1 <= p1 <= 20 and 1 <= p2 <= 20 and p1 != p2, ("panjang di luar batas", teks)
    return {n1.lower(): p1, n2.lower(): p2}, s1, tanya


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; sengaja tidak memakai parameter atau isi modul."""
    panjang, satuan, tanya = _baca_data(teks)
    if tanya == "Mana yang lebih panjang?":
        return max(panjang, key=panjang.get)
    cocok = re.fullmatch(rf"({NAMA}) lebih panjang berapa ([a-z]+) daripada ([a-z]+)\?", tanya)
    if cocok:
        atas, satuan_tanya, bawah = cocok.group(1).lower(), cocok.group(2), cocok.group(3)
        assert satuan_tanya == satuan and {atas, bawah} == set(panjang)
        assert panjang[atas] > panjang[bawah], ("yang ditanya harus yang lebih panjang", teks)
        return str(panjang[atas] - panjang[bawah])
    cocok = re.fullmatch(r"Kedua ([a-z]+) disambung ujung ke ujung\. Berapa ([a-z]+) panjang semuanya\?", tanya)
    assert cocok, ("pertanyaan tidak dikenal", teks)
    assert cocok.group(2) == satuan
    assert all(nama.split()[0] == cocok.group(1) for nama in panjang)
    return str(sum(panjang.values()))


def _soal(parameter: dict) -> Soal:
    return replace(modul.ukur_satuan_tak_baku(**parameter), level=LEVEL)


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
    assert {p["varian"] for p in domain} == set(VARIAN)
    assert {p["satuan"] for p in domain} == set(SATUAN_TES)
    # dict baru tiap panggilan: pemanggil tidak boleh bisa menodai domain
    _domain()[0]["satuan"] = "rusak"
    assert _domain()[0]["satuan"] != "rusak"


def test_semua_panjang_domain_di_antara_tiga_dan_sepuluh_dan_berbeda():
    for p in _domain():
        assert 3 <= p["p1"] <= PANJANG_MAKS_TES and 3 <= p["p2"] <= PANJANG_MAKS_TES, p
        assert p["p1"] != p["p2"], p


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


def test_banding_tidak_pernah_sama_panjang_dan_benda_cocok_satuan():
    for p in _domain():
        soal = _soal(p)
        panjang, satuan, _ = _baca_data(soal.teks)
        if p["varian"] == "sambung":
            assert {n.split()[0] for n in panjang} <= BENDA_SAMBUNG_TES, soal.teks
            assert {n.split()[1] for n in panjang} == {"merah", "biru"}
        else:
            assert set(panjang) <= BENDA_BANDING_TES[satuan], (soal.teks, satuan)
        assert len(set(panjang.values())) == 2


def test_selisih_dan_jumlah_tetap_di_bawah_dua_puluh():
    for p in _domain():
        if p["varian"] != "banding":
            assert 1 <= int(_soal(p).kunci) <= 20, p


def test_tak_ada_satuan_baku_di_teks_dan_pembahasan():
    baku = re.compile(r"\b(cm|m|mm|km|meter|sentimeter|kilometer|inci)\b", re.I)
    for p in _domain():
        soal = _soal(p)
        assert not baku.search(soal.teks), soal.teks
        assert not baku.search(soal.pembahasan), soal.pembahasan


def test_kunci_contoh_tangan():
    f = modul.ukur_satuan_tak_baku
    soal = f(varian="banding", satuan="klip", benda=0, benda2=1, p1=6, p2=9)
    assert soal.teks == ("Pensil panjangnya 6 klip. Buku panjangnya 9 klip. "
                         "Mana yang lebih panjang?")
    assert soal.kunci == "buku"
    soal = f(varian="selisih", satuan="ubin", benda=0, benda2=2, p1=9, p2=4)
    assert soal.kunci == "5" and soal.teks.endswith("Meja lebih panjang berapa ubin daripada karpet?")
    soal = f(varian="sambung", satuan="balok", benda=0, p1=7, p2=5)
    assert soal.kunci == "12"
    assert soal.teks == ("Pita merah panjangnya 7 balok. Pita biru panjangnya 5 balok. "
                         "Kedua pita disambung ujung ke ujung. Berapa balok panjang semuanya?")


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


def test_banding_malrule_adalah_benda_yang_lebih_pendek_dan_tanpa_h():
    for p in _domain():
        if p["varian"] != "banding":
            continue
        soal = _soal(p)
        panjang, _, _ = _baca_data(soal.teks)
        pendek = min(panjang, key=panjang.get)
        assert [(m.jawaban, m.kode) for m in soal.malrule] == [(pendek, "K")], p


def test_pengecoh_tambahan_sama_panjang_hanya_untuk_banding_dan_bukan_malrule():
    for p in _domain():
        soal = _soal(p)
        tambahan = modul.pengecoh_tambahan(p)
        if p["varian"] != "banding":
            assert tambahan == (), p
            continue
        assert tambahan == ("sama panjang",), p
        # Tidak pernah jadi kunci, dan sengaja bukan malrule (bukan hipotesis kesalahan murid).
        assert _norm(soal.kunci) != _norm(tambahan[0])
        assert tambahan[0] not in {m.jawaban for m in soal.malrule}


def test_pilihan_ganda_banding_punya_dua_pengecoh_berbeda_seluruh_domain():
    from choice_generation import kandidat, kebijakan_soal
    import multiple_choice
    jumlah = 0
    for p in _domain():
        soal = _soal(p)
        kebijakan, jenis, pengecoh = kandidat(soal)
        assert kebijakan == "tiga-v1" and len(pengecoh) == 2, p
        assert kebijakan_soal(soal) == ("tiga-v1", "kategori" if p["varian"] == "banding" else "angka")
        nilai = {multiple_choice.nilai_semantis(x, jenis) for x in pengecoh}
        assert len(nilai) == 2 and multiple_choice.nilai_semantis(soal.kunci, jenis) not in nilai
        if p["varian"] == "banding":
            assert "sama panjang" in pengecoh and pengecoh.count("sama panjang") == 1
        jumlah += 1
    assert jumlah == len(_domain())


def test_selisih_dan_sambung_punya_jalur_k_operasi_terbalik_dan_h_satu_lebih_kurang():
    for p in _domain():
        if p["varian"] == "banding":
            continue
        soal = _soal(p)
        kunci = int(soal.kunci)
        k = {int(m.jawaban) for m in soal.malrule if m.kode == "K"}
        h = {int(m.jawaban) for m in soal.malrule if m.kode == "H"}
        terbalik = p["p1"] + p["p2"] if p["varian"] == "selisih" else abs(p["p1"] - p["p2"])
        assert k == {terbalik}, p
        assert h and h <= {kunci - 1, kunci + 1} and all(x >= 1 for x in h), p
        assert (kunci + 1) in h


def test_pembahasan_bahasa_anak_tanpa_istilah_guru_dan_memuat_kunci():
    for p in _domain():
        soal = _soal(p)
        assert not TERLARANG.search(soal.teks), soal.teks
        assert not TERLARANG.search(soal.pembahasan), soal.pembahasan
        assert soal.kunci in soal.pembahasan.lower(), (p, soal.pembahasan)
        assert len(soal.pembahasan) > 40
        assert not any(TERLARANG.search(m.alasan) for m in soal.malrule)


# ── penolakan parameter di luar domain ───────────────────────────────────

BAIK = dict(varian="banding", satuan="klip", benda=0, benda2=1, p1=6, p2=9)


@pytest.mark.parametrize("ubah", [
    dict(varian="tidak_ada"),
    dict(varian=None),
    dict(satuan="cm"),
    dict(satuan=None),
    dict(satuan=["klip"]),
    dict(p1=2),
    dict(p2=11),
    dict(p1=6, p2=6),
    dict(p1=True),
    dict(p1=6.0),
    dict(p2="9"),
    dict(benda=3),
    dict(benda=-1),
    dict(benda=1, benda2=0),
    dict(benda=1, benda2=1),
    dict(benda="0"),
    dict(benda2=None),
    dict(benda2=3),
    dict(varian="sambung"),
    dict(varian="sambung", benda2=None, benda=3),
    dict(varian="selisih", benda2=None),
])
def test_parameter_tidak_sah_ditolak(ubah):
    parameter = {**BAIK, **ubah}
    with pytest.raises(ValueError, match="di luar domain"):
        modul.ukur_satuan_tak_baku(**parameter)


def test_parameter_sah_pembanding_tidak_ditolak():
    assert modul.ukur_satuan_tak_baku(**BAIK).kunci == "buku"
    sambung = {**BAIK, "varian": "sambung", "benda2": None}
    assert modul.ukur_satuan_tak_baku(**sambung).kunci == "15"


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, sys
sys.path[:0] = json.loads(sys.argv[1])
import random
import awal_ukur_satuan_tak_baku as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P1")
    s = m.ukur_satuan_tak_baku(**p)
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
