"""Matematika Awal, jenis ciri_komposisi_bangun (P4): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Fakta bangun datar ditulis ulang di
tes ini (sumber independen, definisi umum buku siswa Matematika SD Kelas IV) dan dibaca
solver yang HANYA melihat teks soal. Nama bangun yang bisa tumpang-tindih (layang-layang
vs belah ketupat) wajib berkualifikasi di soal sisi sejajar; pilihan tertutup pada soal
bernama menutup jawaban lain yang kebetulan benar di bawah definisi inklusif.
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

import awal_ciri_komposisi_bangun as modul
from diagnosis import normalisasi
from multiple_choice import nilai_semantis

TID = "ciri_komposisi_bangun"
LEVEL = "P4"
SEED = range(200)
VARIAN = ("ciri", "dua_persegi", "susun_persegi", "susun_gabung", "uraikan_banyak",
          "uraikan_nama")
UKURAN_PER_VARIAN = {"ciri": 25, "dua_persegi": 16, "susun_persegi": 26,
                     "susun_gabung": 144, "uraikan_banyak": 8, "uraikan_nama": 15}
UKURAN_DOMAIN = sum(UKURAN_PER_VARIAN.values())
CIRI = ("banyak_sisi", "banyak_sudut", "pasang_sejajar", "sudut_siku", "sisi_sama")
UKURAN_CIRI = {"banyak_sisi": 6, "banyak_sudut": 6, "pasang_sejajar": 6, "sudut_siku": 4,
               "sisi_sama": 3}
AKAR_MESIN = Path(sys.modules["diagnosis"].__file__).resolve().parent
DIR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"malrule|diagnosis|kode|guru|template|kunci|hipotesis", re.I)
NAMA_ANAK = ("Rina", "Budi", "Dita", "Eko")
DIAGONAL = "(diagonal: garis lurus dari satu sudut ke sudut yang berhadapan)"

# ── fakta tes (nama persis seperti yang boleh muncul di teks soal) ───────

JUMLAH_SISI = {"persegi": 4, "persegi panjang": 4, "segitiga": 3, "jajar genjang": 4,
               "belah ketupat": 4, "layang-layang": 4}
PASANG = {"persegi": 2, "persegi panjang": 2, "jajar genjang": 2, "belah ketupat": 2,
          "layang-layang yang bukan belah ketupat": 0, "segitiga": 0}
SIKU = {"persegi": 4, "persegi panjang": 4, "segitiga siku-siku": 1,
        "segitiga sama sisi": 0}
SAMA = {"persegi": 4, "belah ketupat": 4, "segitiga sama sisi": 3}
SEGIEMPAT_CEMBUNG = ("persegi panjang", "persegi", "jajar genjang", "belah ketupat")


def _anak(nama: str) -> None:
    assert nama in NAMA_ANAK, nama


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; nama di luar tabel (termasuk tanpa kualifikasi) ditolak."""
    cocok = re.fullmatch(r"Berapa banyak sisi yang sama panjang pada (.+)\?", teks)
    if cocok:
        return str(SAMA[cocok.group(1)])
    cocok = re.fullmatch(r"Berapa banyak sisi (.+)\?", teks)
    if cocok:
        return str(JUMLAH_SISI[cocok.group(1)])
    cocok = re.fullmatch(r"Berapa banyak sudut (.+)\?", teks)
    if cocok and not cocok.group(1).startswith("siku-siku"):
        return str(JUMLAH_SISI[cocok.group(1)])
    cocok = re.fullmatch(r"Berapa pasang sisi sejajar yang dimiliki (.+)\?", teks)
    if cocok:
        return str(PASANG[cocok.group(1)])
    cocok = re.fullmatch(r"Berapa banyak sudut siku-siku yang dimiliki (.+)\?", teks)
    if cocok:
        return str(SIKU[cocok.group(1)])
    cocok = re.fullmatch(
        r"Dua persegi yang sama besar, masing-masing bersisi (\d+) cm, dirapatkan pada satu "
        r"sisi penuh tanpa saling menumpuk\. Bangun apa yang terbentuk\? Pilih: persegi, "
        r"persegi panjang, atau belah ketupat\.", teks)
    if cocok:
        sisi = int(cocok.group(1))
        panjang, lebar = 2 * sisi, sisi  # dua persegi rapat satu sisi penuh
        return "persegi" if panjang == lebar else "persegi panjang"
    cocok = re.fullmatch(
        r"Dua persegi yang sama besar, masing-masing bersisi (\d+) cm, dirapatkan pada satu "
        r"sisi penuh tanpa saling menumpuk sehingga membentuk sebuah persegi panjang\. "
        r"Berapa cm panjang sisi terpanjang bangun itu\?", teks)
    if cocok:
        return str(int(cocok.group(1)) * 2)
    cocok = re.fullmatch(
        r"(\w+) menyusun persegi-persegi kecil yang sama besar menjadi sebuah persegi "
        r"panjang\. Susunannya ada (\d+) baris, dan tiap baris berisi (\d+) persegi kecil\. "
        r"Berapa banyak persegi kecil yang dipakai \1\?", teks)
    if cocok:
        _anak(cocok.group(1))
        baris, kolom = int(cocok.group(2)), int(cocok.group(3))
        assert baris != kolom, ("persegi panjang yang bukan persegi", teks)
        return str(sum(kolom for _ in range(baris)))
    cocok = re.fullmatch(
        r"(\w+) menyusun dua kelompok persegi kecil yang sama besar tanpa saling menumpuk\. "
        r"Kelompok pertama berisi (\d+) baris dengan (\d+) persegi kecil tiap baris\. "
        r"Kelompok kedua berisi (\d+) baris dengan (\d+) persegi kecil tiap baris\. "
        r"Berapa banyak persegi kecil semuanya\?", teks)
    if cocok:
        _anak(cocok.group(1))
        b1, k1, b2, k2 = (int(x) for x in cocok.groups()[1:])
        return str(sum(k1 for _ in range(b1)) + sum(k2 for _ in range(b2)))
    cocok = re.fullmatch(
        r"Sebuah (.+) dipotong lurus menurut (salah satu|kedua) diagonalnya "
        + re.escape(DIAGONAL) + r"\. Berapa banyak bagian yang terbentuk\?", teks)
    if cocok:
        assert cocok.group(1) in SEGIEMPAT_CEMBUNG, teks
        return "2" if cocok.group(2) == "salah satu" else "4"
    cocok = re.fullmatch(
        r"Sebuah persegi panjang dengan panjang (\d+) cm dan lebar (\d+) cm dipotong lurus "
        r"menurut salah satu diagonalnya " + re.escape(DIAGONAL) + r"\. Dua bagian yang "
        r"terbentuk berbentuk bangun apa\? Pilih: segitiga siku-siku, segitiga sama sisi, "
        r"atau persegi\.", teks)
    if cocok:
        assert int(cocok.group(1)) > int(cocok.group(2)), teks
        return "segitiga siku-siku"  # pojok persegi panjang siku-siku, sisi tak sama
    raise AssertionError("bentuk teks tidak dikenal: " + teks)


def _domain() -> tuple:
    return modul.domain_parameter(LEVEL)


def _soal(parameter: dict):
    return getattr(modul, TID)(**parameter)


def _jenis(kunci: str) -> str:
    return "angka" if re.fullmatch(r"\d+", kunci) else "kategori"


def _pengecoh(soal) -> set:
    jenis = _jenis(soal.kunci)
    benar = nilai_semantis(soal.kunci, jenis)
    hasil = set()
    for m in soal.malrule:
        n = nilai_semantis(m.jawaban, jenis)
        if n != benar and (jenis == "kategori" or n >= 0):
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
    for ciri, ukuran in UKURAN_CIRI.items():
        assert sum(1 for p in domain if p.get("ciri") == ciri) == ukuran, ciri
    assert {p["varian"] for p in domain} == set(VARIAN)


def test_domain_dict_baru_tiap_panggilan_dan_tuple_beku():
    domain = _domain()
    assert isinstance(domain, tuple)
    domain[0]["varian"] = "rusak"
    assert _domain()[0]["varian"] != "rusak"


def test_sampel_selalu_di_dalam_domain_dan_menyentuh_semua_varian_dan_ciri():
    kanon = {json.dumps(p, sort_keys=True) for p in _domain()}
    varian, ciri, tanya, potong = set(), set(), set(), set()
    for seed in SEED:
        p = modul.parameter(random.Random(seed), LEVEL)
        assert json.dumps(p, sort_keys=True) in kanon, (seed, p)
        varian.add(p["varian"])
        ciri.add(p.get("ciri"))
        tanya.add(p.get("tanya"))
        potong.add(p.get("potong"))
    assert varian == set(VARIAN)
    assert set(CIRI) <= ciri
    assert {"nama", "panjang"} <= tanya and {"satu", "dua"} <= potong


def test_sampler_memilih_varian_seragam_bukan_menurut_ukuran_domain():
    hitung = {v: 0 for v in VARIAN}
    for seed in range(1200):
        hitung[modul.parameter(random.Random(seed), LEVEL)["varian"]] += 1
    # susun_gabung = 144 dari 234 parameter; undian seragam menjaganya ~1/6, bukan ~62%.
    assert max(hitung.values()) < 330 and min(hitung.values()) > 110, hitung


def test_level_selain_p4_ditolak():
    for level in ("P1", "P3", "P5", "P6", "", None):
        with pytest.raises(ValueError):
            modul.domain_parameter(level)
        with pytest.raises(ValueError):
            modul.parameter(random.Random(0), level)


def test_domain_hanya_fakta_aman_dan_nama_berkualifikasi():
    for p in _domain():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        if p["varian"] != "ciri":
            continue
        if p["ciri"] == "sudut_siku":
            for terlarang in ("jajar genjang", "belah ketupat", "layang-layang", "trapesium"):
                assert terlarang not in teks, teks
            assert "segitiga" not in teks.replace("segitiga siku-siku", "").replace(
                "segitiga sama sisi", ""), teks
        if p["ciri"] == "sisi_sama":
            assert "persegi panjang" not in teks and "layang-layang" not in teks, teks
        if p["ciri"] == "pasang_sejajar" and "layang-layang" in teks:
            assert "layang-layang yang bukan belah ketupat" in teks
        assert "lingkaran" not in teks and "trapesium" not in teks


# ── kunci ────────────────────────────────────────────────────────────────

def test_seluruh_domain_kunci_sama_dengan_solver_teks():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci == solver_dari_teks(soal.teks), (p, soal.teks, soal.kunci)
        assert soal.parameter == p
        assert soal.template_id == TID and soal.bagian == "A"
        assert soal.kunci == soal.kunci.strip() and soal.kunci == soal.kunci.lower()
        assert re.fullmatch(r"\d+|[a-z]+(?:[ -][a-z]+)*", soal.kunci), soal.kunci


def test_kunci_contoh_tangan_dan_teks_persis():
    f = modul.ciri_komposisi_bangun
    s = f(varian="ciri", ciri="banyak_sisi", bangun="segitiga")
    assert (s.teks, s.kunci) == ("Berapa banyak sisi segitiga?", "3")
    s = f(varian="ciri", ciri="pasang_sejajar", bangun="layang-layang")
    assert (s.teks, s.kunci) == (
        "Berapa pasang sisi sejajar yang dimiliki layang-layang yang bukan belah ketupat?", "0")
    s = f(varian="ciri", ciri="sudut_siku", bangun="segitiga siku-siku")
    assert (s.teks, s.kunci) == (
        "Berapa banyak sudut siku-siku yang dimiliki segitiga siku-siku?", "1")
    s = f(varian="dua_persegi", tanya="nama", sisi=4)
    assert s.kunci == "persegi panjang"
    s = f(varian="dua_persegi", tanya="panjang", sisi=7)
    assert s.kunci == "14"
    s = f(varian="susun_persegi", baris=3, kolom=5)
    assert s.kunci == "15" and "3 baris" in s.teks and "5 persegi kecil" in s.teks
    s = f(varian="susun_gabung", baris1=3, kolom1=4, baris2=2, kolom2=3)
    assert s.kunci == "18"
    s = f(varian="uraikan_banyak", bangun="belah ketupat", potong="dua")
    assert s.kunci == "4"
    s = f(varian="uraikan_banyak", bangun="persegi", potong="satu")
    assert s.kunci == "2"
    s = f(varian="uraikan_nama", panjang=8, lebar=5)
    assert s.kunci == "segitiga siku-siku"


def test_susunan_persegi_panjang_tidak_pernah_persegi():
    for p in _domain():
        if p["varian"] == "susun_persegi":
            assert p["baris"] != p["kolom"], p


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
        assert not TERLARANG.search(" ".join(m.alasan for m in soal.malrule)), p


def test_tiap_parameter_punya_cukup_pengecoh_berbeda_nilai_untuk_pilihan_ganda():
    for p in _domain():
        soal = _soal(p)
        assert len(_pengecoh(soal)) >= 2, (p, [m.jawaban for m in soal.malrule])


def test_pengecoh_kunci_nama_tidak_pernah_jawaban_yang_juga_benar():
    """Kunci nama: pengecoh hanya nama yang pasti salah (inklusif maupun eksklusif)."""
    aman = {"persegi panjang": {"persegi", "belah ketupat"},
            "segitiga siku-siku": {"segitiga sama sisi", "persegi"}}
    for p in _domain():
        soal = _soal(p)
        if _jenis(soal.kunci) == "angka":
            continue
        assert {m.jawaban for m in soal.malrule} <= aman[soal.kunci], (p, soal.malrule)


def test_malrule_tertukar_dan_salah_hitung_memakai_nilai_benar_bangun_lain():
    f = modul.ciri_komposisi_bangun
    soal = f(varian="ciri", ciri="banyak_sisi", bangun="jajar genjang")
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["3"] == "K" and per["2"] == "K" and per["8"] == "K" and per["5"] == "H"
    soal = f(varian="ciri", ciri="pasang_sejajar", bangun="jajar genjang")
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["4"] == "K" and per["1"] == "K"
    soal = f(varian="ciri", ciri="pasang_sejajar", bangun="persegi")
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["4"] == "K" and per["1"] == "H"
    soal = f(varian="ciri", ciri="sudut_siku", bangun="segitiga siku-siku")
    assert {"3", "4", "2", "0"} <= {m.jawaban for m in soal.malrule}
    soal = f(varian="susun_gabung", baris1=3, kolom1=4, baris2=2, kolom2=3)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["12"] == "K" and per["6"] == "K" and per["72"] == "K"
    soal = f(varian="susun_persegi", baris=3, kolom=5)
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["8"] == "K" and per["12"] == "K" and per["10"] == "H" and per["20"] == "H"
    soal = f(varian="uraikan_banyak", bangun="persegi", potong="dua")
    per = {m.jawaban: m.kode for m in soal.malrule}
    assert per["2"] == "K" and per["3"] == "H"


# ── pembahasan dan teks ──────────────────────────────────────────────────

def test_pembahasan_bahasa_anak_memuat_kunci_dan_tanpa_istilah_guru():
    for p in _domain():
        soal = _soal(p)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 60 and "None" not in teks and "{" not in teks
        assert not TERLARANG.search(teks), teks
        assert not TERLARANG.search(soal.teks), soal.teks
        if _jenis(soal.kunci) == "angka":
            assert soal.kunci in set(re.findall(r"\d+", teks)), ("kunci tak ada", teks)
        else:
            assert soal.kunci in teks, ("kunci tak ada", teks)


def test_pembahasan_ciri_konsisten_dengan_fakta():
    for p in _domain():
        if p["varian"] != "ciri":
            continue
        soal = _soal(p)
        disebut = [int(x) for x in re.findall(r"punya (\d+) ", soal.pembahasan)]
        assert disebut == [int(soal.kunci)], (p, soal.pembahasan)


def test_pembahasan_menunjukkan_hitungan_dan_mendefinisikan_istilah():
    f = modul.ciri_komposisi_bangun
    assert "tidak akan bertemu" in f(varian="ciri", ciri="pasang_sejajar",
                                     bangun="segitiga").pembahasan
    assert "90 derajat" in f(varian="ciri", ciri="sudut_siku", bangun="persegi").pembahasan
    assert "3 × 5 = 15" in f(varian="susun_persegi", baris=3, kolom=5).pembahasan
    gabung = f(varian="susun_gabung", baris1=3, kolom1=4, baris2=2, kolom2=3).pembahasan
    assert "3 × 4 = 12" in gabung and "2 × 3 = 6" in gabung and "12 + 6 = 18" in gabung
    assert "2s" not in f(varian="dua_persegi", tanya="panjang", sisi=7).pembahasan
    assert "7 + 7 = 14" in f(varian="dua_persegi", tanya="panjang", sisi=7).pembahasan
    assert "segitiga" in f(varian="uraikan_banyak", bangun="persegi", potong="dua").pembahasan


# ── parameter di luar domain ─────────────────────────────────────────────

@pytest.mark.parametrize("parameter", [
    dict(varian="tidak_ada"),
    dict(varian="ciri", ciri="banyak_sisi"),
    dict(varian="ciri", ciri="banyak_sisi", bangun="lingkaran"),
    dict(varian="ciri", ciri="banyak_sisi", bangun="trapesium"),
    dict(varian="ciri", ciri="banyak_sisi", bangun="segitiga siku-siku"),
    dict(varian="ciri", ciri="pasang_sejajar", bangun="trapesium"),
    dict(varian="ciri", ciri="pasang_sejajar", bangun="layang-layang yang bukan belah ketupat"),
    dict(varian="ciri", ciri="sudut_siku", bangun="jajar genjang"),
    dict(varian="ciri", ciri="sudut_siku", bangun="belah ketupat"),
    dict(varian="ciri", ciri="sudut_siku", bangun="layang-layang"),
    dict(varian="ciri", ciri="sudut_siku", bangun="segitiga"),
    dict(varian="ciri", ciri="sisi_sama", bangun="persegi panjang"),
    dict(varian="ciri", ciri="sisi_sama", bangun="layang-layang"),
    dict(varian="ciri", ciri="entah", bangun="persegi"),
    dict(varian="ciri", ciri="banyak_sisi", bangun="persegi", sisi=3),
    dict(varian="ciri", ciri=["banyak_sisi"], bangun="persegi"),
    dict(varian="dua_persegi", tanya="nama", sisi=1),
    dict(varian="dua_persegi", tanya="nama", sisi=10),
    dict(varian="dua_persegi", tanya="nama", sisi=4.0),
    dict(varian="dua_persegi", tanya="nama", sisi=True),
    dict(varian="dua_persegi", tanya="nama", sisi="4"),
    dict(varian="dua_persegi", tanya="lebar", sisi=4),
    dict(varian="dua_persegi", tanya="nama"),
    dict(varian="susun_persegi", baris=4, kolom=4),
    dict(varian="susun_persegi", baris=1, kolom=5),
    dict(varian="susun_persegi", baris=7, kolom=5),
    dict(varian="susun_persegi", baris=3, kolom=9),
    dict(varian="susun_persegi", baris=3.0, kolom=5),
    dict(varian="susun_persegi", baris=3, kolom=5, benda=0),
    dict(varian="susun_gabung", baris1=6, kolom1=3, baris2=2, kolom2=2),
    dict(varian="susun_gabung", baris1=3, kolom1=3, baris2=5, kolom2=2),
    dict(varian="susun_gabung", baris1=3, kolom1=3, baris2=2),
    dict(varian="uraikan_banyak", bangun="layang-layang", potong="satu"),
    dict(varian="uraikan_banyak", bangun="trapesium", potong="satu"),
    dict(varian="uraikan_banyak", bangun="persegi", potong="tiga"),
    dict(varian="uraikan_nama", panjang=5, lebar=5),
    dict(varian="uraikan_nama", panjang=5, lebar=8),
    dict(varian="uraikan_nama", panjang=11, lebar=3),
    dict(varian="uraikan_nama", panjang=8, lebar=2),
    dict(varian="uraikan_nama", bangun="persegi"),
])
def test_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.ciri_komposisi_bangun(**parameter)


# ── determinisme lintas proses ───────────────────────────────────────────

_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
sys.path.insert(0, %(dir)r)
import awal_ciri_komposisi_bangun as m
hasil = []
for seed in range(150):
    p = m.parameter(random.Random(seed), "P4")
    s = m.ciri_komposisi_bangun(**p)
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
