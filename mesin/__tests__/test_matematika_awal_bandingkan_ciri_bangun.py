"""Matematika Awal, jenis bandingkan_ciri_bangun (P5): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Fakta bangun datar ditulis ulang di
tes ini (sumber independen, definisi umum buku siswa Matematika SD Kelas V) dan
dibaca solver yang HANYA melihat teks soal. Nama bangun yang bisa tumpang-tindih
(persegi panjang vs persegi, belah ketupat vs persegi, layang-layang vs belah ketupat,
trapesium vs jajar genjang) wajib berkualifikasi di soal sumbu simetri/pasang sejajar,
supaya jawabannya tidak ambigu; solver menolak nama tanpa kualifikasi itu.
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

import awal_bandingkan_ciri_bangun as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "bandingkan_ciri_bangun"
LEVEL = "P5"
SEED = range(200)
VARIAN = ("sumbu_simetri", "pasang_sejajar", "banyak_sudut_siku", "selisih_ciri")
UKURAN_PER_VARIAN = {"sumbu_simetri": 5, "pasang_sejajar": 6, "banyak_sudut_siku": 4,
                     "selisih_ciri": 23}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent  # mesin/, tetap benar untuk salinan mutasi
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)

# ── fakta tes (nama persis seperti yang boleh muncul di teks soal) ───────

SUMBU = {
    "persegi": 4,
    "persegi panjang yang bukan persegi": 2,
    "segitiga sama sisi": 3,
    "belah ketupat yang bukan persegi": 2,
    "layang-layang yang bukan belah ketupat": 1,
}
PASANG = {
    "persegi": 2, "persegi panjang": 2, "jajar genjang": 2, "belah ketupat": 2,
    "trapesium yang bukan jajar genjang": 1, "segitiga": 0,
}
SIKU = {"persegi": 4, "persegi panjang": 4, "segitiga siku-siku": 1, "segitiga sama sisi": 0}
FRASA = {"sumbu simetri": SUMBU, "pasang sisi sejajar": PASANG, "sudut siku-siku": SIKU}


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; nama di luar tabel (termasuk tanpa kualifikasi) ditolak."""
    cocok = re.fullmatch(r"Berapa banyak sumbu simetri (.+)\?", teks)
    if cocok:
        return str(SUMBU[cocok.group(1)])
    cocok = re.fullmatch(r"Berapa pasang sisi sejajar yang dimiliki (.+)\?", teks)
    if cocok:
        return str(PASANG[cocok.group(1)])
    cocok = re.fullmatch(r"Berapa banyak sudut siku-siku yang dimiliki (.+)\?", teks)
    if cocok:
        return str(SIKU[cocok.group(1)])
    cocok = re.fullmatch(
        r"(.+) punya \.\.\. (sumbu simetri|pasang sisi sejajar|sudut siku-siku) "
        r"lebih banyak daripada (.+)\.", teks)
    if cocok:
        tabel = FRASA[cocok.group(2)]
        a = tabel[cocok.group(1)[0].lower() + cocok.group(1)[1:]]
        b = tabel[cocok.group(3)]
        assert a > b, ("selisih harus positif", teks)
        return str(a - b)
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


def test_level_selain_p5_ditolak():
    for level in ("P1", "P3", "P4", "P6", "", None):
        with pytest.raises(ValueError):
            modul.domain_parameter(level)
        with pytest.raises(ValueError):
            modul.parameter(random.Random(0), level)


def test_domain_hanya_fakta_aman_tanpa_lingkaran_dan_bangun_ambigu():
    for p in _domain():
        teks = _soal(p).teks
        assert "lingkaran" not in teks
        if p["varian"] == "sumbu_simetri" or (p["varian"] == "selisih_ciri"
                                              and p["ciri"] == "sumbu_simetri"):
            assert "jajar genjang" not in teks and "trapesium" not in teks
            assert "persegi panjang" not in teks or "yang bukan persegi" in teks
            polos = teks.replace("belah ketupat yang bukan persegi", "").replace(
                "layang-layang yang bukan belah ketupat", "")
            assert "belah ketupat" not in polos.replace("bukan belah ketupat", "")
            assert "layang-layang" not in teks or "yang bukan belah ketupat" in teks
        if p["varian"] == "banyak_sudut_siku" or (p["varian"] == "selisih_ciri"
                                                  and p["ciri"] == "banyak_sudut_siku"):
            assert "jajar genjang" not in teks and "belah ketupat" not in teks
            assert "trapesium" not in teks and "layang-layang" not in teks


# ── kunci ────────────────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.parameter == p
        assert soal.template_id == TID and soal.bagian == "A"
        assert re.fullmatch(r"\d+", soal.kunci), soal.kunci


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.bandingkan_ciri_bangun
    s = f(varian="sumbu_simetri", bangun="persegi")
    assert (s.teks, s.kunci) == ("Berapa banyak sumbu simetri persegi?", "4")
    s = f(varian="sumbu_simetri", bangun="persegi panjang")
    assert (s.teks, s.kunci) == (
        "Berapa banyak sumbu simetri persegi panjang yang bukan persegi?", "2")
    s = f(varian="pasang_sejajar", bangun="trapesium")
    assert (s.teks, s.kunci) == (
        "Berapa pasang sisi sejajar yang dimiliki trapesium yang bukan jajar genjang?", "1")
    s = f(varian="banyak_sudut_siku", bangun="segitiga siku-siku")
    assert (s.teks, s.kunci) == (
        "Berapa banyak sudut siku-siku yang dimiliki segitiga siku-siku?", "1")
    s = f(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi", b="persegi panjang")
    assert (s.teks, s.kunci) == (
        "Persegi punya ... sumbu simetri lebih banyak daripada persegi panjang yang bukan persegi.",
        "2")


def test_selisih_selalu_positif_dan_pasangan_unik():
    pasangan = set()
    for p in _domain():
        if p["varian"] != "selisih_ciri":
            continue
        assert int(_soal(p).kunci) >= 1
        pasangan.add((p["ciri"], p["a"], p["b"]))
    assert len(pasangan) == UKURAN_PER_VARIAN["selisih_ciri"]


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
    """Minimal 2 pengecoh (kebijakan tiga-v1); yang hanya 2 cuma boleh di selisih_ciri."""
    for p in _domain():
        soal = _soal(p)
        jumlah = len(_pengecoh_angka(soal))
        assert jumlah >= 2, (p, [m.jawaban for m in soal.malrule])
        if p["varian"] != "selisih_ciri":
            assert jumlah >= 3, (p, [m.jawaban for m in soal.malrule])


def test_malrule_tertukar_memakai_nilai_bangun_lain_yang_benar():
    f = modul.bandingkan_ciri_bangun
    soal = f(varian="sumbu_simetri", bangun="persegi panjang")
    jawaban = {m.jawaban for m in soal.malrule if m.kode == "K"}
    assert {"4", "3", "1"} <= jawaban
    soal = f(varian="pasang_sejajar", bangun="trapesium")
    assert {"2", "0"} <= {m.jawaban for m in soal.malrule if m.kode == "K"}


def test_selisih_h_dibalik_dan_k_menyebut_nilai_salah_satu_bangun():
    f = modul.bandingkan_ciri_bangun
    soal = f(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi", b="persegi panjang")
    per_kode = {}
    for m in soal.malrule:
        per_kode.setdefault(m.kode, set()).add(m.jawaban)
    assert "-2" in per_kode["H"] and "6" in per_kode["H"]
    assert per_kode["K"] == {"4"} or {"4"} <= per_kode["K"]
    soal = f(varian="selisih_ciri", ciri="pasang_sejajar", a="persegi", b="segitiga")
    assert "0" in {m.jawaban for m in soal.malrule if m.kode == "K"}


def test_sudut_siku_h_salah_hitung_satu_dan_k_hitung_semua_sudut():
    f = modul.bandingkan_ciri_bangun
    soal = f(varian="banyak_sudut_siku", bangun="segitiga sama sisi")
    assert "3" in {m.jawaban for m in soal.malrule if m.kode == "K"}
    soal = f(varian="banyak_sudut_siku", bangun="persegi")
    assert {"3", "5"} <= {m.jawaban for m in soal.malrule if m.kode == "H"}


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 60 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        angka = set(re.findall(r"\d+", teks))
        assert soal.kunci in angka, ("kunci tidak muncul di pembahasan", teks)


def test_pembahasan_konsisten_dengan_kunci_dan_fakta_tiap_bangun():
    for p in _domain():
        soal = _soal(p)
        disebut = [int(x) for x in re.findall(r"punya (\d+) ", soal.pembahasan)]
        if p["varian"] != "selisih_ciri":
            assert disebut == [int(soal.kunci)], (p, soal.pembahasan)
            continue
        a, b, hasil = re.search(r"Selisihnya (\d+) − (\d+) = (\d+)\.", soal.pembahasan).groups()
        assert disebut == [int(a), int(b)], (p, soal.pembahasan)
        assert int(a) - int(b) == int(hasil) == int(soal.kunci), (p, soal.pembahasan)


def test_pembahasan_mendefinisikan_istilah_dan_menyebut_alasan():
    f = modul.bandingkan_ciri_bangun
    assert "garis lipat" in f(varian="sumbu_simetri", bangun="layang-layang").pembahasan
    assert "tidak akan bertemu" in f(varian="pasang_sejajar", bangun="segitiga").pembahasan
    assert "90 derajat" in f(varian="banyak_sudut_siku", bangun="persegi").pembahasan
    selisih = f(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi", b="persegi panjang")
    assert "4 − 2 = 2" in selisih.pembahasan


def test_teks_tanpa_gambar_dan_satu_pertanyaan():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada", bangun="persegi"),
    dict(varian="sumbu_simetri"),
    dict(varian="sumbu_simetri", bangun="lingkaran"),
    dict(varian="sumbu_simetri", bangun="jajar genjang"),
    dict(varian="sumbu_simetri", bangun="trapesium"),
    dict(varian="sumbu_simetri", bangun="segitiga"),
    dict(varian="sumbu_simetri", bangun=["persegi"]),
    dict(varian="sumbu_simetri", bangun="persegi", a="persegi"),
    dict(varian="pasang_sejajar", bangun="layang-layang"),
    dict(varian="pasang_sejajar", bangun="segitiga siku-siku"),
    dict(varian="banyak_sudut_siku", bangun="jajar genjang"),
    dict(varian="banyak_sudut_siku", bangun="belah ketupat"),
    dict(varian="banyak_sudut_siku", bangun="trapesium"),
    dict(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi", b="persegi"),
    dict(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi panjang", b="belah ketupat"),
    dict(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi panjang", b="persegi"),
    dict(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi", b="lingkaran"),
    dict(varian="selisih_ciri", ciri="pasang_sejajar", a="persegi", b="persegi panjang"),
    dict(varian="selisih_ciri", ciri="banyak_sudut_siku", a="persegi", b="persegi panjang"),
    dict(varian="selisih_ciri", ciri="entah", a="persegi", b="segitiga"),
    dict(varian="selisih_ciri", a="persegi", b="segitiga"),
    dict(varian="selisih_ciri", ciri="sumbu_simetri", a="persegi"),
    dict(varian="selisih_ciri", ciri="sumbu_simetri", bangun="persegi", a="persegi", b="layang-layang"),
    dict(varian="selisih_ciri", ciri=None, a=None, b=None),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.bandingkan_ciri_bangun(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_bandingkan_ciri_bangun as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P5")
    s = m.bandingkan_ciri_bangun(**p)
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
