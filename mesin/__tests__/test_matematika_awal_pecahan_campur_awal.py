"""Matematika Awal, jenis pecahan_campur_awal (P6): domain, solver teks, bentuk jawaban, malrule, PG.

Kunci dicek oleh solver TERPISAH yang hanya membaca TEKS soal (regex) dan menghitung dengan
`fractions.Fraction`, tanpa memakai parameter atau fungsi penulisan modul jenis. Yang dikunci
sebagai KONTRAK: bentuk jawaban dituntut ("1 1/5" benar, "6/5" yang bernilai sama salah di isian,
karena `diagnosis.setara` membandingkan teks ternormalisasi) dan kalimat soal selalu menyebut
bentuk itu. Jenis lama `pecahan_bilangan_asli_desimal` tidak boleh berubah: domain dan 200 undian
seed tetap dikunci lewat sidik jari yang direkam SEBELUM jenis ini ada.
"""
from __future__ import annotations

from fractions import Fraction
from html import unescape
import hashlib
import json
from math import gcd
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import awal_pecahan_bilangan_asli_desimal as lama
import awal_pecahan_campur_awal as modul
import diagnosis
import render
import topics
from choice_generation import kandidat, kebijakan_soal
from multiple_choice import nilai_semantis
from templates import Soal

TID = "pecahan_campur_awal"
LEVEL = "P6"
VARIAN = ("tak_wajar_ke_campur", "campur_ke_tak_wajar", "kali_asli_campur",
          "campur_kali_asli", "bagi_campur_asli")
UKURAN_VARIAN = {"tak_wajar_ke_campur": 388, "campur_ke_tak_wajar": 388, "kali_asli_campur": 504,
                 "campur_kali_asli": 872, "bagi_campur_asli": 1610}
AKAR_MODUL = Path(modul.__file__).resolve().parent
TERLARANG = re.compile(r"\b(malrule|diagnosis|kode|template|kunci|hipotesis|guru)\b", re.I)
# Sidik jari jenis LAMA, direkam dari pohon sebelum pecahan_campur_awal ada (5101 anggota domain P6).
UKURAN_DOMAIN_LAMA = 5101
SIDIK_DOMAIN_LAMA = "fc73eddc93f624c2fc5a6ff32a6ed6e57be0dd3ca1199fcfeefc5a62b72569bc"
SIDIK_ISI_LAMA = "83a2bf0ffc0af745ba34fd45beae94c585359dbd528b5ce8e4c5c06d3532972e"
POLA_CAMPUR = re.compile(r"([1-9][0-9]*) ([1-9][0-9]*)/([1-9][0-9]*)")


def _domain() -> list:
    return list(modul.domain_parameter(LEVEL))


def _soal(p: dict) -> Soal:
    return modul.pecahan_campur_awal(**p)


# ── solver terpisah: hanya membaca teks ──────────────────────────────────

def _tulis_campur(x: Fraction) -> str:
    bulat, sisa = divmod(x.numerator, x.denominator)
    assert bulat >= 1 and sisa >= 1, x
    return f"{bulat} {sisa}/{x.denominator}"


def _frak(bulat: str | None, atas: str, bawah: str) -> Fraction:
    return Fraction(int(bulat or 0)) + Fraction(int(atas), int(bawah))


def solver_dari_teks(teks: str) -> str:
    """Baca soal dari kalimatnya saja; hitung dengan Fraction; tulis dalam bentuk yang diminta."""
    if (m := re.match(r"Ubah pecahan tak wajar (\d+)/(\d+) menjadi bilangan campur\.", teks)):
        return _tulis_campur(Fraction(int(m[1]), int(m[2])))
    if (m := re.match(r"Ubah bilangan campur (\d+) (\d+)/(\d+) menjadi pecahan tak wajar paling "
                      r"sederhana\.", teks)):
        x = _frak(m[1], m[2], m[3])
        return f"{x.numerator}/{x.denominator}"
    if (m := re.match(r"Hitung: (\d+)/(\d+) ÷ (\d+) = ", teks)):
        return _tulis_campur(Fraction(int(m[1]), int(m[2])) / int(m[3]))
    if (m := re.match(r"Hitung: (\d+) (\d+)/(\d+) ÷ (\d+) = ", teks)):
        return _tulis_campur(_frak(m[1], m[2], m[3]) / int(m[4]))
    if (m := re.match(r"Hitung: (\d+)/(\d+) × (\d+) = ", teks)):
        return _tulis_campur(Fraction(int(m[1]), int(m[2])) * int(m[3]))
    if (m := re.match(r"Hitung: (\d+) × (\d+)/(\d+) = ", teks)):
        return _tulis_campur(Fraction(int(m[2]), int(m[3])) * int(m[1]))
    if (m := re.match(r"Hitung: (\d+) (\d+)/(\d+) × (\d+) = ", teks)):
        return _tulis_campur(_frak(m[1], m[2], m[3]) * int(m[4]))
    if (m := re.match(r"Hitung: (\d+) × (\d+) (\d+)/(\d+) = ", teks)):
        return _tulis_campur(_frak(m[2], m[3], m[4]) * int(m[1]))
    raise AssertionError(f"soal tak dikenali: {teks!r}")


def _nilai(teks: str) -> Fraction:
    m = re.fullmatch(r"(?:(\d+) )?(\d+)(?:/(\d+))?", teks)
    assert m, teks
    if m[3] is None:
        return Fraction(int(m[2]))
    return _frak(m[1], m[2], m[3])


# ── domain ───────────────────────────────────────────────────────────────

def test_domain_p6_eksplisit_tanpa_duplikat_dan_ukuran_per_varian_terkunci():
    dom = _domain()
    assert len({json.dumps(p, sort_keys=True) for p in dom}) == len(dom) == sum(UKURAN_VARIAN.values())
    for varian, ukuran in UKURAN_VARIAN.items():
        assert sum(1 for p in dom if p["varian"] == varian) == ukuran, varian
    assert tuple(modul.VARIAN) == VARIAN and modul.LEVEL == (LEVEL,)


def test_domain_urutan_terdokumentasi_dan_dict_baru_tiap_panggilan():
    a, b = modul.domain_parameter(LEVEL), modul.domain_parameter(LEVEL)
    assert a == b and a[0] is not b[0]
    a[0]["varian"] = "diubah"
    assert modul.domain_parameter(LEVEL)[0]["varian"] == VARIAN[0]
    urutan = [p["varian"] for p in modul.domain_parameter(LEVEL)]
    assert [v for i, v in enumerate(urutan) if i == 0 or urutan[i - 1] != v] == list(VARIAN)


@pytest.mark.parametrize("level", ["P1", "P2", "P3", "P4", "P5", "P7", "p6", ""])
def test_level_selain_p6_ditolak(level):
    with pytest.raises(ValueError, match="P6"):
        modul.domain_parameter(level)
    with pytest.raises(ValueError, match="P6"):
        modul.parameter(random.Random(0), level)


def test_seluruh_domain_membentuk_soal_dan_solver_teks_sama_dengan_kunci():
    for p in _domain():
        soal = _soal(p)
        assert soal.template_id == TID and soal.parameter == p and soal.bagian == "A"
        assert solver_dari_teks(soal.teks) == soal.kunci, (p, soal.teks, soal.kunci)


def test_batas_domain_penyebut_bilangan_asli_dan_hasil():
    for p in _domain():
        assert 2 <= p["b"] <= 12, p
        if "n" in p:
            assert 2 <= p["n"] <= 9, p
        if p["varian"] in ("tak_wajar_ke_campur", "bagi_campur_asli"):
            assert p["a"] <= 99 and p["a"] > p["b"] and gcd(p["a"], p["b"]) == 1, p
        else:
            assert 0 < p["a"] < p["b"] and gcd(p["a"], p["b"]) == 1, p


def test_kunci_campur_sah_di_semua_varian_kecuali_tak_wajar():
    for p in _domain():
        soal = _soal(p)
        if p["varian"] == "campur_ke_tak_wajar":
            m = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", soal.kunci)
            assert m and int(m[1]) > int(m[2]) and gcd(int(m[1]), int(m[2])) == 1, soal.kunci
            continue
        m = POLA_CAMPUR.fullmatch(soal.kunci)
        assert m, (p, soal.kunci)
        bulat, atas, bawah = map(int, m.groups())
        assert 1 <= bulat <= 9 and 0 < atas < bawah <= 12 and gcd(atas, bawah) == 1, soal.kunci
        assert len(soal.kunci) <= len("9 11/12")


def test_kunci_tidak_pernah_muncul_sebagai_angka_di_kalimat_soal():
    for p in _domain():
        soal = _soal(p)
        pola = r"(?<![\d/])" + re.escape(soal.kunci) + r"(?![\d/])"
        assert re.search(pola, soal.teks) is None, (p, soal.teks)


def test_parameter_di_luar_domain_ditolak():
    salah = [
        {"varian": "tak_wajar_ke_campur", "a": 10, "b": 5},      # kelipatan: hasil bulat
        {"varian": "tak_wajar_ke_campur", "a": 3, "b": 5},       # bukan tak wajar
        {"varian": "tak_wajar_ke_campur", "a": 100, "b": 7},     # pembilang di atas 99
        {"varian": "campur_ke_tak_wajar", "w": 1, "a": 2, "b": 4},   # sisa belum sederhana
        {"varian": "kali_asli_campur", "a": 1, "b": 4, "n": 4, "urut": 0},  # hasil bulat
        {"varian": "kali_asli_campur", "a": 1, "b": 4, "n": 2, "urut": 0},  # hasil kurang dari 1
        {"varian": "kali_asli_campur", "a": 1, "b": 4, "n": 3, "urut": 2},
        {"varian": "campur_kali_asli", "w": 2, "a": 1, "b": 2, "n": 4, "urut": 0},  # hasil bulat
        {"varian": "bagi_campur_asli", "a": 5, "b": 2, "n": 5, "bentuk": "biasa"},  # hasil kurang dari 1
        {"varian": "bagi_campur_asli", "a": 5, "b": 2, "n": 2, "bentuk": "pecahan"},
        {"varian": "tidak_ada", "a": 5, "b": 2},
        {"varian": "tak_wajar_ke_campur", "a": 7.0, "b": 2},
        {"varian": "tak_wajar_ke_campur", "a": True, "b": 2},
        {"varian": "tak_wajar_ke_campur", "a": 7, "b": 2, "n": 3},   # kunci parameter asing
    ]
    for p in salah:
        with pytest.raises(ValueError, match="di luar domain"):
            modul.pecahan_campur_awal(**p)


# ── sampler ──────────────────────────────────────────────────────────────

def test_sampler_hanya_memilih_anggota_domain_dan_varian_seragam():
    anggota = {json.dumps(p, sort_keys=True) for p in _domain()}
    rng = random.Random(7)
    cacah = {v: 0 for v in VARIAN}
    for _ in range(2000):
        p = modul.parameter(rng, LEVEL)
        assert json.dumps(p, sort_keys=True) in anggota
        cacah[p["varian"]] += 1
    assert all(300 <= c <= 500 for c in cacah.values()), cacah  # rata-rata 400 per varian


def test_sampler_deterministik_untuk_seed_sama():
    a = [modul.parameter(random.Random(s), LEVEL) for s in range(100)]
    b = [modul.parameter(random.Random(s), LEVEL) for s in range(100)]
    assert a == b and len({json.dumps(p, sort_keys=True) for p in a}) > 50


_KODE = r"""
import json, random, sys
sys.path.insert(0, %(akar)r)
import awal_pecahan_campur_awal as m
hasil = []
for seed in range(200):
    p = m.parameter(random.Random(seed), "P6")
    s = m.pecahan_campur_awal(**p)
    hasil.append([p, s.teks, s.kunci, s.pembahasan, [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule]])
print(json.dumps(hasil, sort_keys=True))
"""


def _proses(hash_seed: str):
    env = {k: v for k, v in os.environ.items()}
    env["PYTHONHASHSEED"] = hash_seed
    hasil = subprocess.run([sys.executable, "-c", _KODE % {"akar": str(AKAR_MODUL)}], env=env,
                           capture_output=True, text=True, timeout=120)
    assert hasil.returncode == 0, hasil.stderr
    return json.loads(hasil.stdout)


def test_deterministik_lintas_proses_dengan_hashseed_berbeda():
    assert _proses("1") == _proses("random")


# ── bentuk jawaban dituntut (kontrak diagnosis.setara) ───────────────────

def test_kunci_setara_dirinya_dan_toleran_spasi_ganda():
    for p in _domain():
        soal = _soal(p)
        assert diagnosis.setara(soal.kunci, soal.kunci)
        assert diagnosis.setara(soal.kunci, soal.kunci, soal=soal)
        assert diagnosis.setara("  " + soal.kunci.replace(" ", "   ") + " ", soal.kunci)


def test_bentuk_tak_wajar_yang_bernilai_sama_salah_untuk_kunci_campur():
    """Kontrak 'bentuk dituntut': 6/5 bukan jawaban benar untuk kunci '1 1/5'."""
    assert diagnosis.setara("1 1/5", "1 1/5") is True
    assert diagnosis.setara("6/5", "1 1/5") is False
    jumlah = 0
    for p in _domain():
        soal = _soal(p)
        if p["varian"] == "campur_ke_tak_wajar":
            continue
        nilai = _nilai(soal.kunci)
        tak_wajar = f"{nilai.numerator}/{nilai.denominator}"
        assert not diagnosis.setara(tak_wajar, soal.kunci), (p, tak_wajar, soal.kunci)
        assert not diagnosis.setara(tak_wajar, soal.kunci, soal=soal)
        jumlah += 1
    assert jumlah == len(_domain()) - UKURAN_VARIAN["campur_ke_tak_wajar"]


def test_kalimat_soal_menyebut_bentuk_yang_diminta_dengan_contoh_beda_dari_kunci():
    for p in _domain():
        soal = _soal(p)
        if p["varian"] == "campur_ke_tak_wajar":
            assert "pecahan tak wajar paling sederhana" in soal.teks
            contoh = re.search(r"contoh (\d+/\d+)\)", soal.teks)
        elif p["varian"] == "tak_wajar_ke_campur":
            assert "bilangan campur" in soal.teks
            contoh = re.search(r"contoh (\d+ \d+/\d+)\)", soal.teks)
        else:
            assert "bilangan campur paling sederhana" in soal.teks
            contoh = re.search(r"contoh bentuknya (\d+ \d+/\d+)\)", soal.teks)
        assert contoh and contoh[1] != soal.kunci, (p, soal.teks)
        assert not TERLARANG.search(soal.teks), soal.teks


# ── malrule ──────────────────────────────────────────────────────────────

def test_malrule_bukan_kunci_tidak_kembar_dan_punya_jalur_k_di_seluruh_domain():
    for p in _domain():
        soal = _soal(p)
        jawaban = [m.jawaban for m in soal.malrule]
        assert soal.kunci not in jawaban and len(set(jawaban)) == len(jawaban), p
        assert len({m.id for m in soal.malrule}) == len(soal.malrule)
        assert {m.kode for m in soal.malrule} <= {"K", "H"}
        assert any(m.kode == "K" for m in soal.malrule), p
        assert all(m.id.startswith(TID + ".") for m in soal.malrule)
        assert all(m.alasan[0].isupper() and m.alasan.endswith(".")
                   and m.alasan.startswith(f"Menjawab {m.jawaban}: kemungkinan ")
                   for m in soal.malrule), (p, [m.alasan for m in soal.malrule])
        assert not TERLARANG.search(" ".join(m.alasan for m in soal.malrule))


def test_semua_jawaban_malrule_berbentuk_campur_sah_bagian_pecahannya_kurang_dari_satu():
    """Pengecoh yang memakai spasi harus bilangan campur sah: 'w n/d', w >= 1, 0 < n < d."""
    jumlah = 0
    for p in _domain():
        for m in _soal(p).malrule:
            if " " not in m.jawaban:
                continue
            cocok = POLA_CAMPUR.fullmatch(m.jawaban)
            assert cocok, (p, m.id, m.jawaban)
            bulat, atas, bawah = map(int, cocok.groups())
            assert bulat >= 1 and 0 < atas < bawah, (p, m.id, m.jawaban)
            jumlah += 1
    assert jumlah > 10000


def test_malrule_dua_pengecoh_campur_dibuang_bila_bagian_pecahannya_tak_sah():
    """17/2: hasil bagi 8 dan sisa 1 bila ditukar menjadi '1 8/2' (tak sah), jadi tidak dipakai."""
    soal = modul.pecahan_campur_awal(varian="tak_wajar_ke_campur", a=17, b=2)
    assert soal.kunci == "8 1/2"
    assert "bulat_dan_sisa_tertukar" not in {m.id.split(".")[1] for m in soal.malrule}
    kali = modul.pecahan_campur_awal(varian="campur_kali_asli", w=2, a=3, b=4, n=3, urut=0)
    assert kali.kunci == "8 1/4"
    assert "bulat_tidak_ikut_dikali" not in {m.id.split(".")[1] for m in kali.malrule}


def test_malrule_hasil_tak_diubah_adalah_salah_bentuk_bernilai_sama_dengan_kunci():
    """'6/5' untuk kunci '1 1/5': nilainya benar, bentuknya salah; malrule K bernama jelas."""
    soal = modul.pecahan_campur_awal(varian="kali_asli_campur", a=2, b=5, n=3, urut=0)
    assert soal.kunci == "1 1/5"
    mal = {m.id.split(".")[1]: m for m in soal.malrule}
    tak_diubah = mal["hasil_tak_diubah_ke_campur"]
    assert tak_diubah.jawaban == "6/5" and tak_diubah.kode == "K"
    assert _nilai(tak_diubah.jawaban) == _nilai(soal.kunci)
    assert "bilangan campur" in tak_diubah.alasan
    assert not diagnosis.setara(tak_diubah.jawaban, soal.kunci)
    for varian, parameter in (("campur_kali_asli", {"w": 2, "a": 1, "b": 4, "n": 3, "urut": 0}),
                              ("bagi_campur_asli", {"a": 11, "b": 2, "n": 2, "bentuk": "biasa"})):
        lain = modul.pecahan_campur_awal(varian=varian, **parameter)
        assert any(m.id.endswith("hasil_tak_diubah_ke_campur") and m.kode == "K"
                   for m in lain.malrule)


def test_malrule_contoh_nilai_yang_dikunci():
    soal = modul.pecahan_campur_awal(varian="tak_wajar_ke_campur", a=17, b=5)
    assert soal.kunci == "3 2/5"
    jawaban = {m.id.split(".")[1]: m.jawaban for m in soal.malrule}
    assert jawaban == {"bulat_dan_sisa_tertukar": "2 3/5", "sisa_per_pembilang": "3 2/17",
                       "sisa_terlupa": "3", "bulat_lebih_satu": "4 2/5",
                       "bulat_kurang_satu": "2 2/5", "sisa_lebih_satu": "3 3/5",
                       "sisa_kurang_satu": "3 1/5"}
    assert {m.kode for m in soal.malrule if m.id.endswith(("lebih_satu", "kurang_satu"))} == {"H"}
    kebalikan = modul.pecahan_campur_awal(varian="campur_ke_tak_wajar", w=3, a=2, b=5)
    assert kebalikan.kunci == "17/5"
    assert {m.jawaban for m in kebalikan.malrule} == {"5/5", "6/5", "32/5", "15/5", "5/17"}


# ── pembahasan ───────────────────────────────────────────────────────────

def test_pembahasan_ramah_anak_memuat_langkah_dan_hasil_akhir():
    for p in _domain():
        soal = _soal(p)
        assert soal.kunci in soal.pembahasan, p
        assert soal.pembahasan.strip().endswith("."), p
        assert not TERLARANG.search(soal.pembahasan), (p, soal.pembahasan)
        assert "sisa" in soal.pembahasan or p["varian"] == "campur_ke_tak_wajar"


# ── pilihan ganda ────────────────────────────────────────────────────────

def test_nilai_semantis_pecahan_campur_membaca_campur_biasa_dan_bulat():
    assert nilai_semantis("1 1/5", "pecahan_campur") == Fraction(6, 5)
    assert nilai_semantis("6/5", "pecahan_campur") == Fraction(6, 5)
    assert nilai_semantis("3", "pecahan_campur") == 3
    assert nilai_semantis(" 12 11/12 ", "pecahan_campur") == Fraction(155, 12)
    for salah in ("1 6/5", "1 5/5", "1 1/0", "1 5", "1  1/5", "-1 1/5", "1,5", "a b/c", "1/2/3", ""):
        with pytest.raises(ValueError):
            nilai_semantis(salah, "pecahan_campur")


def test_jenis_angka_lama_tetap_menolak_bilangan_campur():
    """Pembaca 'angka' tidak dilonggarkan: template lain tidak boleh berubah perilakunya."""
    with pytest.raises(ValueError):
        nilai_semantis("1 1/5", "angka")


def test_pilihan_ganda_seluruh_domain_tiga_pengecoh_berbeda_nilai_dari_kunci():
    for p in _domain():
        soal = _soal(p)
        kebijakan, jenis, pengecoh = kandidat(soal)
        assert (kebijakan, jenis) == ("empat-v1", "pecahan_campur") == kebijakan_soal(soal)
        assert len(pengecoh) == 3, (p, pengecoh)
        nilai = {nilai_semantis(x, jenis) for x in pengecoh}
        assert len(nilai) == 3 and nilai_semantis(soal.kunci, jenis) not in nilai, (p, pengecoh)


def test_pilihan_ganda_membuang_bentuk_tak_diubah_karena_bernilai_sama_dengan_kunci():
    soal = modul.pecahan_campur_awal(varian="kali_asli_campur", a=2, b=5, n=3, urut=0)
    assert "6/5" in [m.jawaban for m in soal.malrule]
    _, _, pengecoh = kandidat(soal)
    assert "6/5" not in pengecoh


# ── jenis lama tidak berubah ─────────────────────────────────────────────

def test_jenis_lama_domain_dan_dua_ratus_undian_byte_identik():
    dom = lama.domain_parameter(LEVEL)
    assert len(dom) == UKURAN_DOMAIN_LAMA
    assert hashlib.sha256(json.dumps(dom, sort_keys=True, ensure_ascii=False).encode()).hexdigest() \
        == SIDIK_DOMAIN_LAMA
    isi = []
    for seed in range(200):
        p = lama.parameter(random.Random(seed), LEVEL)
        s = lama.pecahan_bilangan_asli_desimal(**p)
        isi.append([p, s.teks, s.kunci, [[x.id, x.jawaban, x.kode, x.alasan] for x in s.malrule],
                    s.pembahasan])
    assert hashlib.sha256(json.dumps(isi, sort_keys=True, ensure_ascii=False).encode()).hexdigest() \
        == SIDIK_ISI_LAMA


def test_modul_baru_tidak_mengimpor_diagnosis_atau_modul_jenis_lama():
    sumber = (AKAR_MODUL / "awal_pecahan_campur_awal.py").read_text(encoding="utf-8")
    impor = re.findall(r"^(?:from|import) (\w+)", sumber, re.M)
    assert set(impor) <= {"__future__", "fractions", "functools", "math", "random", "templates"}
    assert re.search(r"(?<!`)\bhash\(", sumber) is None  # docstring boleh menyebut `hash()`


# ── lembar cetak dan jawab-tulis ─────────────────────────────────────────

def test_lembar_cetak_dan_penilaian_memakai_teks_yang_bisa_dijawab_dari_kalimat():
    """Jenis ini teks saja (tanpa gambar, tanpa flag visual): lembar soal memuat kalimat utuh."""
    paket = topics.ambil("matematika-awal")
    contoh = _domain()[::37]
    assert len(contoh) > 90 and {p["varian"] for p in contoh} == set(VARIAN)
    for p in contoh:
        soal = _soal(p)
        assert solver_dari_teks(soal.teks) == soal.kunci
        halaman = unescape(render.lembar_soal([soal], topik_paket=paket))
        assert soal.teks in halaman and "<svg" not in halaman, p
        penilaian = unescape(render.lembar_penilaian([soal], topik_paket=paket))
        assert soal.kunci in penilaian and soal.malrule[0].jawaban in penilaian, p
