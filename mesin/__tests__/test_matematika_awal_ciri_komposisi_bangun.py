"""Matematika Awal, jenis ciri_komposisi_bangun (P4): domain, solver teks, malrule, determinisme.

Modul diimpor langsung (tanpa registrasi topik). Fakta bangun datar ditulis ulang di
tes ini (sumber independen, definisi umum buku siswa Matematika SD Kelas IV) dan dibaca
solver yang HANYA melihat teks soal. Nama bangun yang bisa tumpang-tindih (layang-layang
vs belah ketupat) wajib berkualifikasi di soal sisi sejajar; pilihan tertutup pada soal
bernama menutup jawaban lain yang kebetulan benar di bawah definisi inklusif.
"""
from __future__ import annotations

from collections import Counter
import hashlib
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
VARIAN_LAMA = ("ciri", "dua_persegi", "susun_persegi", "susun_gabung", "uraikan_banyak",
               "uraikan_nama")
VARIAN_BARU = ("ciri_segitiga", "ciri_trapesium", "ciri_empat_sisi_lain", "susun_dua_cara",
               "uraikan_segi_banyak")
VARIAN = VARIAN_LAMA + VARIAN_BARU
UKURAN_LAMA = 234
UKURAN_PER_VARIAN = {"ciri": 25, "dua_persegi": 16, "susun_persegi": 26,
                     "susun_gabung": 144, "uraikan_banyak": 8, "uraikan_nama": 15,
                     "ciri_segitiga": 91, "ciri_trapesium": 48, "ciri_empat_sisi_lain": 73,
                     "susun_dua_cara": 121, "uraikan_segi_banyak": 6}
# Dihitung tangan dari rentang di docstring modul (bukan dari modul).
UKURAN_TANYA_BARU = {
    "jenis_tiga_sama": 7, "jenis_dua_sama": 31, "jenis_siku": 15, "banyak_sama_kaki": 31,
    "banyak_sama_sisi": 7, "trapesium_sejajar": 1, "trapesium_sisi": 1,
    "trapesium_sudut": 1, "trapesium_kaki": 45, "layang_pasang": 1, "jajar_pasang": 1,
    "jajar_siku": 1, "belah_siku": 1, "belah_sisi": 7, "layang_sisi": 30, "jajar_sisi": 32,
    "tutup_persegi": 36, "tutup_panjang": 33, "luas_persegi": 28, "luas_keping": 24,
    "segitiga": 3, "garis": 3}
# Hash isi 234 soal LAMA (parameter, teks, kunci, pembahasan, malrule) dari modul v1 (HEAD 2f3e0b4):
# varian lama harus tetap persis (append-only).
HASH_PARAMETER_LAMA = "9c8c5a3de65d3287dcd3b09c4815cf32fd9cc924da4411b9509f547bee83c4cc"
HASH_ISI_LAMA = "987041b7626e75951ff5d7c4369d0ce33b9c773aeacddab4fe0f229bf88d5204"
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


# ── solver varian baru (v2): hanya membaca TEKS, geometri ditulis ulang di sini ──

SEMBARANG = r"sembarang \(ketiga sisinya berbeda panjang\)"
LANCIP = r"lancip \(ketiga sudutnya lebih kecil dari sudut siku-siku\)"
NAMA_SEGI_TES = {"segiempat": 4, "segilima": 5, "segienam": 6}


def _segitiga_ada(sisi) -> None:
    a, b, c = sorted(sisi)
    assert a > 0 and a + b > c, ("bukan segitiga", sisi)


def _siku_mungkin(sisi) -> bool:
    a, b, c = sorted(sisi)
    return a * a + b * b == c * c


def _jenis_dari_sisi(sisi) -> str:
    banyak_beda = len(set(sisi))
    return {1: "sama sisi", 2: "sama kaki", 3: "sembarang"}[banyak_beda]


def _sisi_sama_terbanyak(sisi) -> int:
    return max(Counter(sisi).values())


def _layang_layang(sisi) -> bool:
    """Empat sisi berurutan: dua pasang sisi berdekatan sama panjang, bukan belah ketupat."""
    s0, s1, s2, s3 = sisi
    dua_pasang = (s0 == s1 and s2 == s3) or (s1 == s2 and s3 == s0)
    return dua_pasang and len(set(sisi)) > 1


def _pasang_berdekatan_sama(sisi) -> int:
    """Banyak pasangan sisi berdekatan (terpisah) yang sama panjang pada empat sisi berurutan."""
    for mulai in (0, 1):
        pasangan = [(sisi[(mulai + i) % 4], sisi[(mulai + i + 1) % 4]) for i in (0, 2)]
        if all(x == y for x, y in pasangan):
            return len(pasangan)
    return 0


def _solver_segitiga(teks: str):
    cocok = re.fullmatch(
        r"Sebuah segitiga mempunyai tiga sisi yang sama panjang, yaitu (\d+) cm tiap sisinya\. "
        r"Segitiga itu disebut segitiga apa\? Pilih: sama sisi, siku-siku, atau "
        + SEMBARANG + r"\.", teks)
    if cocok:
        s = int(cocok.group(1))
        sisi = (s, s, s)
        _segitiga_ada(sisi)
        assert not _siku_mungkin(sisi)  # "siku-siku" pasti salah
        return _jenis_dari_sisi(sisi)
    cocok = re.fullmatch(
        r"Sebuah segitiga mempunyai tepat dua sisi yang sama panjang, masing-masing (\d+) cm, "
        r"dan sisi ketiganya (\d+) cm\. Segitiga itu disebut segitiga apa\? "
        r"Pilih: sama kaki, sama sisi, atau " + SEMBARANG + r"\.", teks)
    if cocok:
        a, b = int(cocok.group(1)), int(cocok.group(2))
        assert a != b, teks  # "tepat dua"
        _segitiga_ada((a, a, b))
        return _jenis_dari_sisi((a, a, b))
    cocok = re.fullmatch(
        r"Sebuah segitiga mempunyai satu sudut siku-siku, dan dua sisi yang mengapit sudut itu "
        r"panjangnya (\d+) cm dan (\d+) cm\. Segitiga itu disebut segitiga apa\? "
        r"Pilih: siku-siku, sama sisi, atau " + LANCIP + r"\.", teks)
    if cocok:
        assert int(cocok.group(1)) > 0 and int(cocok.group(2)) > 0
        return "siku-siku"  # ada sudut siku-siku: bukan lancip, bukan sama sisi
    cocok = re.fullmatch(
        r"Sebuah segitiga sama kaki yang bukan segitiga sama sisi mempunyai sisi (\d+) cm, "
        r"(\d+) cm, dan (\d+) cm\. Berapa banyak sisinya yang sama panjang\?", teks)
    if cocok:
        sisi = tuple(int(x) for x in cocok.groups())
        _segitiga_ada(sisi)
        assert len(set(sisi)) == 2, teks  # sama kaki yang bukan sama sisi
        return str(_sisi_sama_terbanyak(sisi))
    cocok = re.fullmatch(
        r"Sebuah segitiga sama sisi mempunyai sisi (\d+) cm tiap sisinya\. Berapa banyak "
        r"sisinya yang sama panjang\?", teks)
    if cocok:
        s = int(cocok.group(1))
        return str(_sisi_sama_terbanyak((s, s, s)))
    return None


def _solver_trapesium(teks: str):
    if teks == "Berapa pasang sisi sejajar yang dimiliki trapesium yang bukan jajar genjang?":
        return "1"  # eksklusif maupun inklusif: tepat satu pasang
    if teks in ("Berapa banyak sisi trapesium?", "Berapa banyak sudut trapesium?"):
        return "4"
    cocok = re.fullmatch(
        r"Sebuah trapesium sama kaki mempunyai sisi sejajar (\d+) cm dan (\d+) cm, dan salah "
        r"satu kakinya \(sisi miring yang tidak sejajar\) (\d+) cm\. Berapa cm panjang kaki "
        r"yang satunya\?", teks)
    if cocok:
        a, b, k = (int(x) for x in cocok.groups())
        assert a < b, teks  # bukan jajar genjang
        assert 2 * k > b - a, ("trapesium tak mungkin", teks)  # kaki lebih panjang dari setengah selisih
        return str(k)  # kedua kaki sama panjang
    return None


def _solver_empat_sisi_lain(teks: str):
    if teks == ("Dua sisi berdekatan adalah dua sisi yang bertemu di satu sudut. Berapa pasang "
                "sisi berdekatan yang sama panjang pada layang-layang yang bukan belah "
                "ketupat?"):
        contoh = (3, 3, 5, 5)
        assert _layang_layang(contoh)
        return str(_pasang_berdekatan_sama(contoh))
    if teks == "Berapa pasang sisi berhadapan yang sama panjang pada jajar genjang?":
        contoh = (4, 6, 4, 6)
        return str(sum(1 for i in range(2) if contoh[i] == contoh[i + 2]))
    if teks == "Berapa banyak sudut siku-siku pada jajar genjang yang bukan persegi panjang?":
        return "0"
    if teks == "Berapa banyak sudut siku-siku pada belah ketupat yang bukan persegi?":
        return "0"
    cocok = re.fullmatch(
        r"Sebuah belah ketupat ABCD mempunyai sisi AB = (\d+) cm\. Berapa cm panjang sisi "
        r"BC\?", teks)
    if cocok:
        return cocok.group(1)  # keempat sisi sama panjang
    cocok = re.fullmatch(
        r"Pada layang-layang ABCD yang bukan belah ketupat, AB = AD = (\d+) cm dan "
        r"BC = (\d+) cm\. Berapa cm panjang CD\?", teks)
    if cocok:
        a, b = int(cocok.group(1)), int(cocok.group(2))
        assert a != b, teks
        cocok_cd = [x for x in range(1, 40) if _layang_layang((a, b, x, a))]
        assert cocok_cd == [b], (cocok_cd, teks)
        return str(cocok_cd[0])
    cocok = re.fullmatch(
        r"Pada jajar genjang ABCD, sisi AB = (\d+) cm dan sisi BC = (\d+) cm\. Berapa cm "
        r"panjang sisi CD\?", teks)
    if cocok:
        a, b = int(cocok.group(1)), int(cocok.group(2))
        cd = [x for x in range(1, 40) if x == a]  # sisi berhadapan AB dan CD sama panjang
        return str(cd[0])
    return None


def _banyak_keping_grid(panjang: int, lebar: int, kp: int, kq: int) -> int:
    """Banyak keping kp x kq pada grid dalam salah satu dari dua arah yang muat habis."""
    for a, b in ((kp, kq), (kq, kp)):
        if panjang % a == 0 and lebar % b == 0:
            return sum(1 for _ in range(0, panjang, a) for _ in range(0, lebar, b))
    raise AssertionError(("tidak habis dibagi", panjang, lebar, kp, kq))


def _solver_susun(teks: str):
    cocok = re.fullmatch(
        r"(\w+) akan menutup penuh sebuah persegi panjang berukuran (\d+) cm × (\d+) cm dengan "
        r"keping persegi berukuran (\d+) cm × (\d+) cm, tanpa celah dan tidak saling "
        r"menumpuk\. Berapa banyak keping persegi yang diperlukan\?", teks)
    if cocok:
        _anak(cocok.group(1))
        pj, lb, s1, s2 = (int(x) for x in cocok.groups()[1:])
        assert s1 == s2 and pj != lb, teks
        return str(_banyak_keping_grid(pj, lb, s1, s2))
    cocok = re.fullmatch(
        r"(\w+) akan menutup penuh sebuah persegi panjang berukuran (\d+) cm × (\d+) cm dengan "
        r"keping persegi panjang berukuran (\d+) cm × (\d+) cm, tanpa celah dan tidak saling "
        r"menumpuk\. Berapa banyak keping yang diperlukan\?", teks)
    if cocok:
        _anak(cocok.group(1))
        pj, lb, kp, kq = (int(x) for x in cocok.groups()[1:])
        assert pj != lb and kp != kq, teks
        banyak = _banyak_keping_grid(pj, lb, kp, kq)
        assert banyak * kp * kq == pj * lb  # sama dengan luas : luas
        return str(banyak)
    cocok = re.fullmatch(
        r"(\w+) menyusun (\d+) keping persegi yang sama besar, tiap keping bersisi (\d+) cm\. "
        r"Keping-keping itu dirapatkan tanpa celah dan tidak saling menumpuk menjadi satu "
        r"bangun\. Berapa cm² luas bangun itu\?", teks)
    if cocok:
        _anak(cocok.group(1))
        n, s = int(cocok.group(2)), int(cocok.group(3))
        return str(sum(s * s for _ in range(n)))
    cocok = re.fullmatch(
        r"(\w+) menyusun (\d+) keping persegi panjang yang sama besar, tiap keping berukuran "
        r"(\d+) cm × (\d+) cm\. Keping-keping itu dirapatkan tanpa celah dan tidak saling "
        r"menumpuk menjadi satu bangun\. Berapa cm² luas bangun itu\?", teks)
    if cocok:
        _anak(cocok.group(1))
        n, kp, kq = (int(x) for x in cocok.groups()[1:])
        assert kp != kq, teks
        return str(sum(kp * kq for _ in range(n)))
    return None


def _garis_potong_kipas(n: int) -> list:
    """Titik sudut 0 dihubungkan ke titik sudut yang BUKAN dirinya dan bukan tetangganya."""
    return [v for v in range(n) if v not in (0, 1, n - 1)]


def _solver_segi(teks: str):
    cocok = re.fullmatch(
        r"Sebuah (segi\w+) \(bangun datar dengan (\d+) sisi, tidak ada sudutnya yang menjorok "
        r"ke dalam\) dipotong dengan garis lurus dari satu titik sudut ke semua titik sudut "
        r"lain yang tidak bersebelahan dengan titik sudut itu\. Semua garis potong keluar dari "
        r"titik sudut yang sama, jadi tidak saling berpotongan di dalam bangun\. "
        r"Berapa banyak (segitiga yang terbentuk|garis potong yang dibuat)\?", teks)
    if not cocok:
        return None
    n = NAMA_SEGI_TES[cocok.group(1)]
    assert int(cocok.group(2)) == n, teks
    garis = len(_garis_potong_kipas(n))
    return str(garis + 1) if cocok.group(3).startswith("segitiga") else str(garis)


def solver_varian_baru(teks: str):
    """Kunci varian v2 dari teks saja; None bila teks bukan milik varian v2."""
    for solver in (_solver_segitiga, _solver_trapesium, _solver_empat_sisi_lain,
                   _solver_susun, _solver_segi):
        hasil = solver(teks)
        if hasil is not None:
            return hasil
    return None


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks saja; nama di luar tabel (termasuk tanpa kualifikasi) ditolak."""
    baru = solver_varian_baru(teks)
    if baru is not None:
        return baru
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
    # susun_gabung = 144 dari 573 parameter; undian seragam menjaganya ~1/11 (109), bukan ~25%.
    assert max(hitung.values()) < 180 and min(hitung.values()) > 60, hitung


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
            "segitiga siku-siku": {"segitiga sama sisi", "persegi"},
            # varian baru: "sama kaki" tak pernah pengecoh "sama sisi" (inklusif: juga benar)
            "sama sisi": {"siku-siku", "sembarang"},
            "sama kaki": {"sama sisi", "sembarang"},
            "siku-siku": {"sama sisi", "lancip"}}
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


# ── varian baru v2 (segitiga, trapesium, empat sisi lain, susun dua cara, segi banyak) ──

def _baru() -> list:
    return [p for p in _domain() if p["varian"] in VARIAN_BARU]


def test_domain_lama_tetap_persis_append_only():
    domain = _domain()
    lama = [p for p in domain if p["varian"] in VARIAN_LAMA]
    assert len(lama) == UKURAN_LAMA and list(domain[:UKURAN_LAMA]) == lama
    assert hashlib.sha256(json.dumps(lama, sort_keys=True).encode()).hexdigest() == (
        HASH_PARAMETER_LAMA)
    isi = []
    for p in lama:
        s = _soal(p)
        isi.append([p, s.teks, s.kunci, s.pembahasan,
                    [[m.id, m.jawaban, m.kode, m.alasan] for m in s.malrule]])
    assert hashlib.sha256(json.dumps(isi, sort_keys=True).encode()).hexdigest() == HASH_ISI_LAMA


def test_domain_baru_ukuran_per_kelompok_tanya():
    hitung = Counter(p["tanya"] for p in _baru())
    assert dict(hitung) == UKURAN_TANYA_BARU
    assert sum(UKURAN_TANYA_BARU.values()) == len(_baru())
    assert "ciri" not in {k for p in _baru() for k in p}  # kunci "ciri" milik varian lama


def test_sampler_menyentuh_semua_kelompok_baru():
    tanya = {modul.parameter(random.Random(s), LEVEL).get("tanya") for s in range(4000)}
    assert set(UKURAN_TANYA_BARU) <= tanya


def test_varian_baru_kalimat_berkualifikasi_dan_tanpa_gambar():
    for p in _baru():
        teks = _soal(p).teks
        assert "\n" not in teks and "[gambar" not in teks.lower()
        if p["tanya"] == "trapesium_sejajar":
            assert "trapesium yang bukan jajar genjang" in teks
        if p["tanya"] in ("layang_pasang", "layang_sisi"):
            assert re.search(r"layang-layang( ABCD)? yang bukan belah ketupat", teks)
        if p["tanya"] == "jajar_siku":
            assert "jajar genjang yang bukan persegi panjang" in teks
        if p["tanya"] == "belah_siku":
            assert "belah ketupat yang bukan persegi" in teks
        if p["tanya"] == "banyak_sama_kaki":
            assert "sama kaki yang bukan segitiga sama sisi" in teks
        if p["tanya"] == "jenis_dua_sama":
            assert "tepat dua sisi yang sama panjang" in teks
        if p["tanya"].startswith("jenis_"):
            assert "Pilih: " in teks


def test_kunci_baru_contoh_tangan_dan_teks_persis():
    f = modul.ciri_komposisi_bangun
    s = f(varian="ciri_segitiga", tanya="jenis_tiga_sama", sisi=5)
    assert s.kunci == "sama sisi" and s.teks.endswith(
        "Pilih: sama sisi, siku-siku, atau sembarang (ketiga sisinya berbeda panjang).")
    s = f(varian="ciri_segitiga", tanya="jenis_dua_sama", kaki=5, alas=8)
    assert s.kunci == "sama kaki"
    s = f(varian="ciri_segitiga", tanya="jenis_siku", tegak_a=3, tegak_b=4)
    assert s.kunci == "siku-siku"
    s = f(varian="ciri_segitiga", tanya="banyak_sama_kaki", kaki=5, alas=8)
    assert s.kunci == "2" and "5 cm, 5 cm, dan 8 cm" in s.teks
    s = f(varian="ciri_segitiga", tanya="banyak_sama_sisi", sisi=6)
    assert s.kunci == "3"
    s = f(varian="ciri_trapesium", tanya="trapesium_sejajar")
    assert (s.teks, s.kunci) == (
        "Berapa pasang sisi sejajar yang dimiliki trapesium yang bukan jajar genjang?", "1")
    s = f(varian="ciri_trapesium", tanya="trapesium_kaki", atas=4, bawah=8, kaki=5)
    assert s.kunci == "5"
    s = f(varian="ciri_empat_sisi_lain", tanya="layang_pasang")
    assert s.kunci == "2"
    s = f(varian="ciri_empat_sisi_lain", tanya="layang_sisi", ab=3, bc=7)
    assert s.kunci == "7" and "AB = AD = 3 cm dan BC = 7 cm" in s.teks
    s = f(varian="ciri_empat_sisi_lain", tanya="jajar_sisi", ab=8, bc=5)
    assert s.kunci == "8"
    s = f(varian="ciri_empat_sisi_lain", tanya="belah_sisi", sisi=6)
    assert s.kunci == "6"
    s = f(varian="ciri_empat_sisi_lain", tanya="jajar_siku")
    assert s.kunci == "0"
    s = f(varian="susun_dua_cara", tanya="tutup_persegi", panjang=6, lebar=4, sisi=2)
    assert s.kunci == "6" and "6 cm × 4 cm" in s.teks and "2 cm × 2 cm" in s.teks
    s = f(varian="susun_dua_cara", tanya="tutup_panjang", panjang=6, lebar=4, keping_p=3,
          keping_q=2)
    assert s.kunci == "4"
    s = f(varian="susun_dua_cara", tanya="luas_persegi", banyak=5, sisi=3)
    assert s.kunci == "45"
    s = f(varian="susun_dua_cara", tanya="luas_keping", banyak=4, keping_p=4, keping_q=3)
    assert s.kunci == "48"
    assert f(varian="uraikan_segi_banyak", tanya="segitiga", n=4).kunci == "2"
    assert f(varian="uraikan_segi_banyak", tanya="segitiga", n=5).kunci == "3"
    assert f(varian="uraikan_segi_banyak", tanya="segitiga", n=6).kunci == "4"
    assert f(varian="uraikan_segi_banyak", tanya="garis", n=6).kunci == "3"


def test_baru_nama_pilihan_tertutup_pengecoh_pasti_salah_di_semua_definisi():
    """Kunci nama: pengecoh tepat sama dengan pilihan lain di kalimat soal."""
    dibaca = 0
    for p in _baru():
        soal = _soal(p)
        if _jenis(soal.kunci) == "angka":
            continue
        dibaca += 1
        pilihan = re.search(r"Pilih: (.+)\.$", soal.teks).group(1)
        pilihan = re.sub(r" \(.*?\)", "", pilihan)
        nama = {x.strip().removeprefix("atau ") for x in pilihan.split(",")}
        assert soal.kunci in nama and len(nama) == 3, (p, nama)
        assert {m.jawaban for m in soal.malrule} == nama - {soal.kunci}, (p, soal.malrule)
    assert dibaca == 7 + 31 + 15


def test_baru_kunci_angka_punya_minimal_tiga_pengecoh_berbeda_nilai():
    for p in _baru():
        soal = _soal(p)
        if _jenis(soal.kunci) == "angka":
            assert len(_pengecoh(soal)) >= 3, (p, [m.jawaban for m in soal.malrule])


def test_baru_malrule_nilai_jalur_k_dan_h_sesuai_hipotesis():
    f = modul.ciri_komposisi_bangun

    def peta(**p):
        return {m.jawaban: m.kode for m in f(**p).malrule}

    # n bukan n-2 (K), kurang/lebih satu (H)
    per = peta(varian="uraikan_segi_banyak", tanya="segitiga", n=5)
    assert per == {"5": "K", "2": "K", "4": "H"}
    per = peta(varian="uraikan_segi_banyak", tanya="garis", n=5)
    assert per == {"3": "K", "5": "K", "4": "K", "1": "H"}
    # tertukar dengan bangun sebelah (K)
    per = peta(varian="ciri_segitiga", tanya="banyak_sama_kaki", kaki=5, alas=8)
    assert per["3"] == "K" and per["4"] == "K" and per["6"] == "K"
    per = peta(varian="ciri_trapesium", tanya="trapesium_sejajar")
    assert per == {"2": "K", "0": "K", "4": "K"}
    # menghitung sisi vs sudut (K)
    per = peta(varian="ciri_trapesium", tanya="trapesium_sudut")
    assert per["8"] == "K" and per["2"] == "K" and per["5"] == "H"
    per = peta(varian="ciri_trapesium", tanya="trapesium_kaki", atas=3, bawah=9, kaki=5)
    assert per["3"] == "K" and per["9"] == "K" and per["12"] == "K" and per["6"] == "K"
    assert per["6"] == "K" and per["4"] == "H"
    per = peta(varian="susun_dua_cara", tanya="tutup_persegi", panjang=6, lebar=4, sisi=2)
    assert per["5"] == "K" and per["24"] == "K" and per["12"] == "K"
    assert per["3"] == "H" and per["9"] == "H"
    per = peta(varian="susun_dua_cara", tanya="luas_persegi", banyak=5, sisi=3)
    assert per["9"] == "K" and per["15"] == "K" and per["60"] == "K"
    assert per["36"] == "H" and per["54"] == "H"
    per = peta(varian="ciri_empat_sisi_lain", tanya="jajar_sisi", ab=8, bc=5)
    assert per["5"] == "K" and per["13"] == "K" and per["26"] == "K"


def test_baru_pembahasan_menunjukkan_hitungan_dan_dua_cara():
    f = modul.ciri_komposisi_bangun
    t = f(varian="susun_dua_cara", tanya="tutup_persegi", panjang=6, lebar=4,
          sisi=2).pembahasan
    assert "3 × 2 = 6" in t and "6 × 4 = 24 cm²" in t and "2 × 2 = 4 cm²" in t
    t = f(varian="susun_dua_cara", tanya="tutup_panjang", panjang=6, lebar=4, keping_p=3,
          keping_q=2).pembahasan
    assert "6 × 4 = 24 cm²" in t and "3 × 2 = 6 cm²" in t and "2 × 2 = 4" in t
    t = f(varian="susun_dua_cara", tanya="luas_persegi", banyak=5, sisi=3).pembahasan
    assert "3 × 3 = 9 cm²" in t and "5 × 9 = 45 cm²" in t
    t = f(varian="uraikan_segi_banyak", tanya="segitiga", n=6).pembahasan
    assert "6 − 3 = 3" in t and "3 + 1 = 4" in t
    assert "90 derajat" in f(varian="ciri_empat_sisi_lain", tanya="jajar_siku").pembahasan
    assert "tidak akan bertemu" in f(varian="ciri_trapesium",
                                     tanya="trapesium_sejajar").pembahasan


@pytest.mark.parametrize("parameter", [
    dict(varian="ciri_segitiga", tanya="jenis_tiga_sama", sisi=2),
    dict(varian="ciri_segitiga", tanya="jenis_tiga_sama", sisi=10),
    dict(varian="ciri_segitiga", tanya="jenis_tiga_sama", sisi=4.0),
    dict(varian="ciri_segitiga", tanya="jenis_tiga_sama", sisi=True),
    dict(varian="ciri_segitiga", tanya="jenis_dua_sama", kaki=5, alas=5),
    dict(varian="ciri_segitiga", tanya="jenis_dua_sama", kaki=3, alas=6),
    dict(varian="ciri_segitiga", tanya="jenis_dua_sama", kaki=3, alas=7),
    dict(varian="ciri_segitiga", tanya="banyak_sama_kaki", kaki=5, alas=5),
    dict(varian="ciri_segitiga", tanya="jenis_siku", tegak_a=4, tegak_b=3),
    dict(varian="ciri_segitiga", tanya="jenis_siku", tegak_a=3, tegak_b=3),
    dict(varian="ciri_segitiga", tanya="jenis_sembarang", sisi=4),
    dict(varian="ciri_segitiga", tanya="banyak_sama_sisi"),
    dict(varian="ciri_trapesium", tanya="trapesium_sejajar", atas=3),
    dict(varian="ciri_trapesium", tanya="trapesium_kaki", atas=8, bawah=4, kaki=5),
    dict(varian="ciri_trapesium", tanya="trapesium_kaki", atas=4, bawah=8, kaki=3),
    dict(varian="ciri_trapesium", tanya="trapesium_kaki", atas=4, bawah=8, kaki=9),
    dict(varian="ciri_trapesium", tanya="trapesium_kaki", atas=4, bawah=8),
    dict(varian="ciri_empat_sisi_lain", tanya="layang_sisi", ab=5, bc=5),
    dict(varian="ciri_empat_sisi_lain", tanya="jajar_sisi", ab=2, bc=5),
    dict(varian="ciri_empat_sisi_lain", tanya="belah_sisi", sisi=2),
    dict(varian="ciri_empat_sisi_lain", tanya="layang_siku"),
    dict(varian="susun_dua_cara", tanya="tutup_persegi", panjang=6, lebar=6, sisi=2),
    dict(varian="susun_dua_cara", tanya="tutup_persegi", panjang=7, lebar=4, sisi=2),
    dict(varian="susun_dua_cara", tanya="tutup_persegi", panjang=6, lebar=4, sisi=1),
    dict(varian="susun_dua_cara", tanya="tutup_panjang", panjang=6, lebar=6, keping_p=3,
         keping_q=2),
    dict(varian="susun_dua_cara", tanya="tutup_panjang", panjang=7, lebar=4, keping_p=3,
         keping_q=2),
    dict(varian="susun_dua_cara", tanya="tutup_panjang", panjang=6, lebar=4, keping_p=2,
         keping_q=3),
    dict(varian="susun_dua_cara", tanya="luas_persegi", banyak=2, sisi=3),
    dict(varian="susun_dua_cara", tanya="luas_persegi", banyak=5, sisi=6),
    dict(varian="susun_dua_cara", tanya="luas_keping", banyak=4, keping_p=2, keping_q=3),
    dict(varian="uraikan_segi_banyak", tanya="segitiga", n=3),
    dict(varian="uraikan_segi_banyak", tanya="segitiga", n=7),
    dict(varian="uraikan_segi_banyak", tanya="garis", n="5"),
    dict(varian="uraikan_segi_banyak", tanya="cabang", n=5),
    dict(varian="uraikan_segi_banyak", n=5),
])
def test_baru_parameter_di_luar_domain_ditolak(parameter):
    with pytest.raises(ValueError, match="di luar domain"):
        modul.ciri_komposisi_bangun(**parameter)
