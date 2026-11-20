"""Bilangan Sekolah Tahap B: urutkan_bilangan, tambah_kurang_bersusun,
kali_bagi_sekolah, kalimat_matematika (P3-P5, teks angka saja).

Kunci dicek oleh solver TERPISAH yang hanya membaca teks (regex, penelusuran
brute force); malrule dicek oleh oracle bertulis ulang di sini (string kolom,
bukan kode topik). Malrule hanya HIPOTESIS kesalahan umum: yang dijaga adalah
bukan kunci, tidak kembar, dan jalur K selalu ada.
"""
from __future__ import annotations

from dataclasses import replace
import random
import re

import pytest

import generator
import topics
from templates import REGISTRI, Soal

TOPIK = "bilangan-sekolah"
LEVEL = ("P3", "P4", "P5")
SEED = range(25)
SAPU = range(300)
URUTKAN, SUSUN, KALIBAGI, KALIMAT = (
    "urutkan_bilangan", "tambah_kurang_bersusun", "kali_bagi_sekolah", "kalimat_matematika")
KURANG, KALI, BAGI = "−", "×", "÷"


@pytest.fixture(autouse=True)
def sakelar_hidup(monkeypatch):
    monkeypatch.setenv("OSN_BILANGAN_SEKOLAH", "1")


def _angka(teks: str) -> int:
    return int(teks.replace(".", ""))


def _soal(template_id: str, level: str, seed: int) -> Soal:
    return generator._soal_layak(topics.ambil(TOPIK), template_id, random.Random(seed), level)


def _jawaban(soal: Soal) -> dict:
    return {m.id.split(".", 1)[1]: (m.kode, m.jawaban) for m in soal.malrule}


def _kolom(n: int) -> list:
    return [int(c) for c in str(n)[::-1]]


def _dari_kolom(isi: list) -> int:
    return int("".join(str(d) for d in reversed(isi)))


def _tanpa_malrule_kembar(soal: Soal) -> None:
    jawaban = [m.jawaban for m in soal.malrule]
    assert soal.kunci not in jawaban, soal.teks
    assert len(set(jawaban)) == len(jawaban), (soal.teks, jawaban)
    assert len({m.id for m in soal.malrule}) == len(soal.malrule)
    assert all(m.alasan.strip() for m in soal.malrule)
    assert any(m.kode == "K" for m in soal.malrule), soal.teks


# ── solver terpisah (hanya membaca teks) ─────────────────────────────────

def solver_urutkan(teks: str) -> str:
    cocok = re.fullmatch(r"Bilangan (terbesar|terkecil) di antara (.+) adalah \.\.\.", teks)
    assert cocok, teks
    nilai = [_angka(x) for x in re.findall(r"\d[\d.]*", cocok.group(2))]
    assert len(nilai) == 4
    return str(max(nilai) if cocok.group(1) == "terbesar" else min(nilai))


def solver_susun(teks: str) -> str:
    cocok = re.fullmatch(r"Hitung dengan cara bersusun: ([\d.]+) ([+−]) ([\d.]+) = \.\.\.", teks)
    assert cocok, teks
    a, b = _angka(cocok.group(1)), _angka(cocok.group(3))
    return str(a + b if cocok.group(2) == "+" else a - b)


def solver_kalibagi(teks: str) -> str:
    cocok = re.fullmatch(r"Hitung: ([\d.]+) ([×÷]) ([\d.]+) = \.\.\.", teks)
    assert cocok, teks
    a, b = _angka(cocok.group(1)), _angka(cocok.group(3))
    if cocok.group(2) == KALI:
        return str(a * b)
    assert a % b == 0
    return str(a // b)


def solver_kalimat(teks: str) -> str:
    cocok = re.fullmatch(
        r"Isi bilangan yang hilang: (\.\.\.|[\d.]+) ([+−×÷]) (\.\.\.|[\d.]+) = ([\d.]+)", teks)
    assert cocok, teks
    kiri, tanda, kanan, hasil = cocok.groups()
    hasil = _angka(hasil)
    ketemu = []
    for x in range(1, 1001):
        a = x if kiri == "..." else _angka(kiri)
        b = x if kanan == "..." else _angka(kanan)
        nilai = {"+": a + b, KURANG: a - b, KALI: a * b,
                 BAGI: a / b if b else None}[tanda]
        if nilai == hasil:
            ketemu.append(x)
    assert len(ketemu) == 1, (teks, ketemu)
    return str(ketemu[0])


SOLVER = {URUTKAN: solver_urutkan, SUSUN: solver_susun,
          KALIBAGI: solver_kalibagi, KALIMAT: solver_kalimat}


@pytest.mark.parametrize("template_id", sorted(SOLVER))
@pytest.mark.parametrize("level", LEVEL)
def test_kunci_sama_dengan_solver_dari_teks_dan_malrule_sehat(template_id, level):
    for seed in SAPU:
        soal = _soal(template_id, level, seed)
        assert soal.kunci == SOLVER[template_id](soal.teks), (template_id, level, seed, soal.teks)
        assert soal.kunci.isdigit() and not soal.kunci.startswith("0")
        _tanpa_malrule_kembar(soal)
        assert soal.template_id == template_id
        ulang = replace(REGISTRI[template_id](**soal.parameter), level=level)
        assert ulang.tanda_tangan == soal.tanda_tangan and ulang.kunci == soal.kunci


def test_topik_memuat_lima_jenis_dan_komposisi_penuh():
    paket = topics.ambil(TOPIK)
    lima = {"nilai_tempat_besar", URUTKAN, SUSUN, KALIBAGI, KALIMAT}
    assert set(paket.templates) == lima
    for level in LEVEL:
        assert set(paket.komposisi[level]) == lima
        assert len(paket.komposisi[level]) == 10
    assert paket.hanya_manual is True
    from school_numbers_versions import TEMPLATE_BARU
    assert TEMPLATE_BARU == lima


# ═══ urutkan_bilangan ════════════════════════════════════════════════════

PANJANG_URUT = {"P3": (2, 3), "P4": (3, 4), "P5": (5, 6)}


def _depan_unik(varian, nilai):
    depan = [int(str(n)[0]) for n in nilai]
    target = max(depan) if varian == "terbesar" else min(depan)
    return nilai[depan.index(target)] if depan.count(target) == 1 else None


@pytest.mark.parametrize("level", LEVEL)
def test_urutkan_domain_empat_bilangan_beda_panjang(level):
    pendek, panjang = PANJANG_URUT[level]
    for seed in SAPU:
        p = _soal(URUTKAN, level, seed).parameter
        nilai = p["bilangan"]
        assert type(nilai) is list and len(nilai) == 4 and len(set(nilai)) == 4
        assert {len(str(n)) for n in nilai} <= {pendek, panjang}
        assert len({len(str(n)) for n in nilai}) == 2, "perlu pengecoh beda panjang angka"
        assert all(10 ** (pendek - 1) <= n < 10 ** panjang for n in nilai)
        assert p["varian"] in ("terbesar", "terkecil")


def test_urutkan_batas_atas_sama_dengan_tahap_a():
    atas = {lv: max(max(_soal(URUTKAN, lv, s).parameter["bilangan"]) for s in SAPU) for lv in LEVEL}
    assert atas["P3"] <= 999 and atas["P4"] <= 9999 and atas["P5"] <= 999999
    assert atas["P5"] >= 100000, "enam angka harus muncul pada P5"


@pytest.mark.parametrize("level", LEVEL)
def test_urutkan_kedua_varian_dan_posisi_kunci_tersebar(level):
    varian, posisi = set(), set()
    for seed in SAPU:
        soal = _soal(URUTKAN, level, seed)
        varian.add(soal.parameter["varian"])
        posisi.add(soal.parameter["bilangan"].index(int(soal.kunci)))
    assert varian == {"terbesar", "terkecil"} and posisi == {0, 1, 2, 3}


@pytest.mark.parametrize("level", LEVEL)
def test_urutkan_malrule_angka_depan_selalu_ada_dan_terbalik_sah(level):
    ada_terbalik = False
    for seed in SAPU:
        soal = _soal(URUTKAN, level, seed)
        v, nilai = soal.parameter["varian"], soal.parameter["bilangan"]
        peta = _jawaban(soal)
        pilih = _depan_unik(v, nilai)
        assert pilih is not None and pilih != int(soal.kunci)
        assert peta["angka_depan_saja"] == ("K", str(pilih))
        lawan = min(nilai) if v == "terbesar" else max(nilai)
        if lawan != pilih:
            assert peta["terbalik"] == ("H", str(lawan))
            ada_terbalik = True
        else:
            assert "terbalik" not in peta
        assert set(peta) <= {"angka_depan_saja", "terbalik"}
    assert ada_terbalik


def test_urutkan_contoh_tangan():
    f = REGISTRI[URUTKAN]
    besar = f(varian="terbesar", bilangan=[4372, 87, 5210, 4099])
    assert besar.teks == "Bilangan terbesar di antara 4.372, 87, 5.210, dan 4.099 adalah ..."
    assert besar.kunci == "5210"
    assert _jawaban(besar) == {"angka_depan_saja": ("K", "87")}
    assert besar.pembahasan == (
        "Hitung banyak angka tiap bilangan: 4.372 ada 4 angka, 87 ada 2 angka, "
        "5.210 ada 4 angka, 4.099 ada 4 angka. Bilangan yang angkanya paling banyak lebih besar. "
        "Bilangan yang punya 4 angka: 4.372, 5.210, dan 4.099. "
        "Di tempat ribuan, angkanya 4, 5, dan 4; yang terbesar 5. "
        "Jadi bilangan terbesar adalah 5.210.")
    kecil = f(varian="terkecil", bilangan=[372, 87, 4210, 900])
    assert kecil.kunci == "87"
    assert _jawaban(kecil) == {"angka_depan_saja": ("K", "372"), "terbalik": ("H", "4210")}
    assert kecil.pembahasan == (
        "Hitung banyak angka tiap bilangan: 372 ada 3 angka, 87 ada 2 angka, "
        "4.210 ada 4 angka, 900 ada 3 angka. Bilangan yang angkanya paling sedikit lebih kecil. "
        "Hanya 87 yang punya 2 angka, jadi bilangan terkecil adalah 87.")


def test_urutkan_pembahasan_lanjut_ke_angka_berikutnya_saat_seri():
    soal = REGISTRI[URUTKAN](varian="terbesar", bilangan=[4372, 4299, 87, 3000])
    assert soal.kunci == "4372"
    assert soal.pembahasan == (
        "Hitung banyak angka tiap bilangan: 4.372 ada 4 angka, 4.299 ada 4 angka, "
        "87 ada 2 angka, 3.000 ada 4 angka. Bilangan yang angkanya paling banyak lebih besar. "
        "Bilangan yang punya 4 angka: 4.372, 4.299, dan 3.000. "
        "Di tempat ribuan, angkanya 4, 4, dan 3; yang terbesar 4. "
        "Di tempat ratusan, angkanya 3 dan 2; yang terbesar 3. "
        "Jadi bilangan terbesar adalah 4.372.")


@pytest.mark.parametrize("kwargs", [
    dict(varian="terbesar", bilangan=[4372, 87, 5210]),                 # kurang dari empat
    dict(varian="terbesar", bilangan=[4372, 87, 5210, 4099, 12]),
    dict(varian="terbesar", bilangan=[4372, 87, 87, 4099]),             # kembar
    dict(varian="terbesar", bilangan=(4372, 87, 5210, 4099)),           # bukan list
    dict(varian="terbesar", bilangan=[4372, 4299, 5210, 4099]),         # panjang sama
    dict(varian="terbesar", bilangan=[4372, 87, 5210, True]),
    dict(varian="terbesar", bilangan=[4372, 87, 5210, "4099"]),
    dict(varian="terbesar", bilangan=[4372, 87, 5210, 4099.0]),
    dict(varian="terbesar", bilangan=[4372, 87, 5210, 1000000]),        # terlalu besar
    dict(varian="terbesar", bilangan=[4372, 8, 5210, 4099]),            # terlalu kecil
    dict(varian="terbesar", bilangan=[4372, 57, 5210, 4099]),           # angka depan tertinggi seri (57, 5210)
    dict(varian="terbesar", bilangan=[4372, 37, 5210, 4099]),           # angka depan tertinggi = kunci
    dict(varian="terkecil", bilangan=[4372, 87, 5210, 4099]),           # angka depan terendah seri
    dict(varian="terkecil", bilangan=[12, 4372, 5210, 4099]),           # angka depan terendah = kunci
    dict(varian="tertinggi", bilangan=[4372, 87, 5210, 4099]),
    dict(varian=None, bilangan=[4372, 87, 5210, 4099]),
])
def test_urutkan_parameter_tidak_sah_ditolak(kwargs):
    with pytest.raises(ValueError):
        REGISTRI[URUTKAN](**kwargs)


# ═══ tambah_kurang_bersusun ══════════════════════════════════════════════

RENTANG_SUSUN = {"P3": ((100, 999), (10, 999), 1000),
                 "P4": ((1000, 9999), (100, 9999), 10000),
                 "P5": ((10000, 99999), (1000, 99999), 100000)}


def oracle_lupa_menyimpan(a, b):
    n = max(len(str(a)), len(str(b)))
    x, y = str(a).zfill(n), str(b).zfill(n)
    return int("".join(str((int(p) + int(q)) % 10) for p, q in zip(x, y)))


def oracle_tulis_kolom(a, b):
    n = max(len(str(a)), len(str(b)))
    x, y = str(a).zfill(n), str(b).zfill(n)
    return int("".join(str(int(p) + int(q)) for p, q in zip(x, y)))


def oracle_besar_kurang_kecil(a, b):
    n = len(str(a))
    x, y = str(a).zfill(n), str(b).zfill(n)
    return int("".join(str(abs(int(p) - int(q))) for p, q in zip(x, y)))


def oracle_lupa_meminjam(a, b):
    kolom_a, kolom_b = _kolom(a), _kolom(b) + [0] * (len(str(a)) - len(str(b)))
    return _dari_kolom([x + 10 - y if x < y else x - y for x, y in zip(kolom_a, kolom_b)])


def _ada_pinjaman_sebenarnya(a, b):
    kolom_a, kolom_b = _kolom(a), _kolom(b) + [0] * (len(str(a)) - len(str(b)))
    pinjam = 0
    pernah = False
    for x, y in zip(kolom_a, kolom_b):
        if x - pinjam < y:
            pinjam, pernah = 1, True
        else:
            pinjam = 0
    return pernah


def _ada_simpanan_sebenarnya(a, b):
    simpan, pernah = 0, False
    for x, y in zip(_kolom(a) + [0] * 8, _kolom(b) + [0] * 8):
        simpan = 1 if x + y + simpan >= 10 else 0
        pernah = pernah or bool(simpan)
    return pernah


@pytest.mark.parametrize("level", LEVEL)
def test_susun_domain_rentang_dan_wajib_simpan_atau_pinjam(level):
    (alo, ahi), (blo, bhi), batas = RENTANG_SUSUN[level]
    ada = set()
    for seed in SAPU:
        p = _soal(SUSUN, level, seed).parameter
        a, b, v = p["a"], p["b"], p["varian"]
        ada.add(v)
        assert alo <= a <= ahi and blo <= b <= bhi
        if v == "tambah":
            assert a + b <= batas and _ada_simpanan_sebenarnya(a, b)
        else:
            assert v == "kurang" and a > b and _ada_pinjaman_sebenarnya(a, b)
            assert a - b >= 1
    assert ada == {"tambah", "kurang"}


@pytest.mark.parametrize("level", LEVEL)
def test_susun_malrule_cocok_oracle_dan_dua_jalur_k(level):
    for seed in SAPU:
        soal = _soal(SUSUN, level, seed)
        a, b, v = soal.parameter["a"], soal.parameter["b"], soal.parameter["varian"]
        peta = _jawaban(soal)
        if v == "tambah":
            assert peta == {
                "lupa_menyimpan": ("K", str(oracle_lupa_menyimpan(a, b))),
                "tulis_hasil_kolom": ("K", str(oracle_tulis_kolom(a, b)))}, (a, b)
        else:
            assert peta == {
                "besar_kurang_kecil": ("K", str(oracle_besar_kurang_kecil(a, b))),
                "lupa_meminjam": ("K", str(oracle_lupa_meminjam(a, b)))}, (a, b)


def test_susun_contoh_tangan():
    f = REGISTRI[SUSUN]
    tambah = f(varian="tambah", a=468, b=357)
    assert tambah.teks == "Hitung dengan cara bersusun: 468 + 357 = ..."
    assert tambah.kunci == "825"
    assert _jawaban(tambah) == {"lupa_menyimpan": ("K", "715"), "tulis_hasil_kolom": ("K", "71115")}
    assert tambah.pembahasan == (
        "Jumlahkan kolom dari kanan. Satuan: 8 + 7 = 15, tulis 5 dan simpan 1. "
        "Puluhan: 6 + 5 + 1 (simpanan) = 12, tulis 2 dan simpan 1. "
        "Ratusan: 4 + 3 + 1 (simpanan) = 8, tulis 8. Jadi 468 + 357 = 825.")
    kurang = f(varian="kurang", a=953, b=357)
    assert kurang.teks == "Hitung dengan cara bersusun: 953 − 357 = ..."
    assert kurang.kunci == "596"
    assert _jawaban(kurang) == {"besar_kurang_kecil": ("K", "604"), "lupa_meminjam": ("K", "606")}
    assert kurang.pembahasan == (
        "Kurangkan kolom dari kanan. Satuan: 3 tidak cukup dikurangi 7, pinjam 1 puluhan "
        "sehingga 13 − 7 = 6. Puluhan: 5 sudah dipinjam 1 jadi 4, 4 tidak cukup dikurangi 5, "
        "pinjam 1 ratusan sehingga 14 − 5 = 9. Ratusan: 9 sudah dipinjam 1 jadi 8, 8 − 3 = 5. "
        "Jadi 953 − 357 = 596.")


def test_susun_pembahasan_simpanan_terakhir_dan_kolom_tanpa_pasangan():
    soal = REGISTRI[SUSUN](varian="tambah", a=980, b=75)
    assert soal.kunci == "1055"
    assert _jawaban(soal) == {"lupa_menyimpan": ("K", "955"), "tulis_hasil_kolom": ("K", "9155")}
    assert soal.pembahasan == (
        "Jumlahkan kolom dari kanan. Satuan: 0 + 5 = 5, tulis 5. "
        "Puluhan: 8 + 7 = 15, tulis 5 dan simpan 1. "
        "Ratusan: 9 + 1 (simpanan) = 10, tulis 0 dan simpan 1. "
        "Simpanan 1 ditulis di tempat ribuan. Jadi 980 + 75 = 1.055.")


def test_susun_pembahasan_pinjam_lewat_angka_nol():
    soal = REGISTRI[SUSUN](varian="kurang", a=4003, b=59)
    assert soal.kunci == "3944"
    assert _jawaban(soal) == {"besar_kurang_kecil": ("K", "4056"), "lupa_meminjam": ("K", "4054")}
    assert soal.pembahasan == (
        "Kurangkan kolom dari kanan. Satuan: 3 tidak cukup dikurangi 9, pinjam 1 puluhan "
        "sehingga 13 − 9 = 4. Puluhan: 0 sudah dipinjam 1, jadi harus pinjam 1 ratusan dulu: "
        "10 − 1 = 9. Lalu 9 − 5 = 4. Ratusan: 0 sudah dipinjam 1, jadi harus pinjam 1 ribuan dulu: "
        "10 − 1 = 9, tulis 9. Ribuan: 4 sudah dipinjam 1 jadi 3, tulis 3. Jadi 4.003 − 59 = 3.944.")


@pytest.mark.parametrize("kwargs", [
    dict(varian="tambah", a=111, b=222),            # tanpa simpanan
    dict(varian="kurang", a=987, b=654),            # tanpa pinjaman
    dict(varian="kurang", a=357, b=953),            # a <= b
    dict(varian="kurang", a=357, b=357),
    dict(varian="tambah", a=99999, b=99999),        # hasil lebih dari 100.000
    dict(varian="tambah", a=5, b=7),                # operan terlalu kecil
    dict(varian="tambah", a=100000, b=1),
    dict(varian="tambah", a="468", b=357),
    dict(varian="tambah", a=468.0, b=357),
    dict(varian="tambah", a=True, b=357),
    dict(varian="kali", a=468, b=357),
    dict(varian=None, a=468, b=357),
    dict(varian="tambah", a=90, b=10),              # tulis_hasil_kolom sama dengan kunci
])
def test_susun_parameter_tidak_sah_ditolak(kwargs):
    with pytest.raises(ValueError):
        REGISTRI[SUSUN](**kwargs)


# ═══ kali_bagi_sekolah ═══════════════════════════════════════════════════

def oracle_lupa_kali_satu(a, m):
    kolom = _kolom(a)
    atas = len(kolom) - 1
    return sum((d * m % 10) * 10 ** i for i, d in enumerate(kolom[:atas])) + kolom[atas] * m * 10 ** atas


def oracle_lupa_menyimpan_kali(a, b):
    return sum(oracle_lupa_kali_satu(a, m) * 10 ** j for j, m in enumerate(_kolom(b)))


def oracle_lupa_geser(a, b):
    return sum(a * m for m in _kolom(b))


def _jenis_kali(a, b):
    if 2 <= a <= 10 and 2 <= b <= 10:
        return "fakta"
    if 11 <= a <= 99 and 2 <= b <= 9:
        return "2x1"
    if 100 <= a <= 999 and 11 <= b <= 99:
        return "3x2"
    return None


@pytest.mark.parametrize("level,jenis", [("P3", "fakta"), ("P4", "2x1"), ("P5", "3x2")])
def test_kalibagi_domain_per_level(level, jenis):
    ada = set()
    for seed in SAPU:
        p = _soal(KALIBAGI, level, seed).parameter
        a, b, v = p["a"], p["b"], p["varian"]
        ada.add(v)
        if v == "kali":
            assert _jenis_kali(a, b) == jenis, (a, b)
            if jenis == "2x1":
                assert a % 10 != 0
            if jenis == "3x2":
                assert b % 10 != 0
        else:
            assert v == "bagi" and a % b == 0
            q = a // b
            if jenis == "fakta":
                assert 2 <= b <= 10 and 2 <= q <= 10
            elif jenis == "2x1":
                assert 2 <= b <= 9 and 11 <= q <= 99
            else:
                assert 11 <= b <= 99 and 12 <= q <= 999 and a <= 100000
    assert ada == {"kali", "bagi"}


def test_kalibagi_p5_mungkin_menghasilkan_contoh_koordinator():
    f = REGISTRI[KALIBAGI]
    assert f(varian="kali", a=348, b=25).kunci == "8700"
    assert f(varian="bagi", a=7200, b=36).kunci == "200"
    besar = [_soal(KALIBAGI, "P5", seed).parameter for seed in SAPU]
    assert any(p["varian"] == "bagi" and p["a"] >= 5000 for p in besar)
    assert any(p["varian"] == "kali" and p["a"] * p["b"] >= 10000 for p in besar)


@pytest.mark.parametrize("level", LEVEL)
def test_kalibagi_malrule_cocok_oracle(level):
    for seed in SAPU:
        soal = _soal(KALIBAGI, level, seed)
        a, b, v = soal.parameter["a"], soal.parameter["b"], soal.parameter["varian"]
        peta = _jawaban(soal)
        if v == "kali":
            kunci = a * b
            urut = [("dijumlahkan", "K", a + b)]
            jenis = _jenis_kali(a, b)
            if jenis != "fakta":
                urut.append(("lupa_menyimpan", "K", oracle_lupa_menyimpan_kali(a, b)))
            if b >= 10:
                urut.append(("lupa_geser", "K", oracle_lupa_geser(a, b)))
            if jenis != "3x2":
                urut.append(("kali_kurang_satu_kelompok", "H", kunci - b))
                urut.append(("kali_lebih_satu_kelompok", "H", kunci + b))
            harapan = _dedupe(urut, kunci)
            assert peta == harapan, (a, b, peta, harapan)
            if jenis != "fakta":
                assert "lupa_menyimpan" in peta
        else:
            q = a // b
            urut = [("dikalikan", "K", a * b),
                    ("salah_letak_nol", "K", q // 10 if q % 10 == 0 else q * 10)]
            sisa = str(q).replace("0", "")
            if "0" in str(q) and sisa:
                urut.append(("nol_terlewat", "K", sisa))
            urut += [("bagi_kurang_satu", "H", q - 1), ("bagi_lebih_satu", "H", q + 1)]
            harapan = _dedupe(urut, q)
            assert peta == harapan, (a, b, peta, harapan)


def test_kalibagi_contoh_tangan():
    f = REGISTRI[KALIBAGI]
    p5 = f(varian="kali", a=348, b=25)
    assert p5.teks == "Hitung: 348 × 25 = ..."
    assert _jawaban(p5) == {"dijumlahkan": ("K", "373"), "lupa_menyimpan": ("K", "8360"),
                            "lupa_geser": ("K", "2436")}
    assert p5.pembahasan == (
        "Pecah 25 menjadi 20 dan 5: 348 × 25 = (348 × 20) + (348 × 5) = 6.960 + 1.740 = 8.700.")
    p4 = f(varian="kali", a=47, b=6)
    assert p4.kunci == "282"
    assert _jawaban(p4) == {"dijumlahkan": ("K", "53"), "lupa_menyimpan": ("K", "242"),
                            "kali_kurang_satu_kelompok": ("H", "276"),
                            "kali_lebih_satu_kelompok": ("H", "288")}
    assert p4.pembahasan == "Pecah 47 menjadi 40 dan 7: 47 × 6 = (40 × 6) + (7 × 6) = 240 + 42 = 282."
    p3 = f(varian="kali", a=7, b=8)
    assert p3.kunci == "56"
    assert _jawaban(p3) == {"dijumlahkan": ("K", "15"), "kali_kurang_satu_kelompok": ("H", "48"),
                            "kali_lebih_satu_kelompok": ("H", "64")}
    assert p3.pembahasan == "7 × 8 berarti 7 kelompok yang masing-masing berisi 8. Jumlahnya 56, jadi 7 × 8 = 56."
    bagi = f(varian="bagi", a=7200, b=36)
    assert bagi.teks == "Hitung: 7.200 ÷ 36 = ..."
    assert _jawaban(bagi) == {"dikalikan": ("K", "259200"), "salah_letak_nol": ("K", "20"),
                              "nol_terlewat": ("K", "2"), "bagi_kurang_satu": ("H", "199"),
                              "bagi_lebih_satu": ("H", "201")}
    assert bagi.pembahasan == (
        "Cari bilangan yang jika dikali 36 hasilnya 7.200. Karena 36 × 200 = 7.200, maka 7.200 ÷ 36 = 200.")
    kecil = f(varian="bagi", a=56, b=7)
    assert kecil.kunci == "8"
    assert _jawaban(kecil) == {"dikalikan": ("K", "392"), "salah_letak_nol": ("K", "80"),
                               "bagi_kurang_satu": ("H", "7"), "bagi_lebih_satu": ("H", "9")}


def test_kalibagi_domain_p3_enumerasi_161_dan_sampler_di_dalamnya():
    paket = topics.ambil(TOPIK)
    domain = paket.domain_parameter(KALIBAGI, "P3")
    kunci = {tuple(sorted(d.items())) for d in domain}
    assert len(domain) == len(kunci) == 161
    for seed in range(500):
        p = _soal(KALIBAGI, "P3", seed).parameter
        assert tuple(sorted(p.items())) in kunci
    for level in ("P4", "P5"):
        with pytest.raises(KeyError):
            paket.domain_parameter(KALIBAGI, level)
    with pytest.raises(KeyError):
        paket.domain_parameter(URUTKAN, "P3")


@pytest.mark.parametrize("kwargs", [
    dict(varian="kali", a=2, b=2),                  # a+b sama dengan a x b, jalur K hilang
    dict(varian="kali", a=11, b=10),
    dict(varian="kali", a=1, b=5),
    dict(varian="kali", a=40, b=6),                 # puluhan bulat tanpa satuan
    dict(varian="kali", a=41, b=6),                 # satuan x pengali < 10: lupa menyimpan tak ada
    dict(varian="kali", a=348, b=30),
    dict(varian="kali", a=1000, b=25),
    dict(varian="kali", a=348, b=100),
    dict(varian="kali", a="348", b=25),
    dict(varian="kali", a=348.0, b=25),
    dict(varian="kali", a=True, b=25),
    dict(varian="bagi", a=7201, b=36),              # tidak habis
    dict(varian="bagi", a=7200, b=1),
    dict(varian="bagi", a=7200, b=0),
    dict(varian="bagi", a=100100, b=11),            # dividen lebih dari 100.000
    dict(varian="bagi", a=36, b=36),                # hasil 1
    dict(varian="bagi", a=360, b=11),               # tidak habis
    dict(varian="bagi", a=7200, b=1000),
    dict(varian="jumlah", a=3, b=4),
    dict(varian=None, a=3, b=4),
])
def test_kalibagi_parameter_tidak_sah_ditolak(kwargs):
    with pytest.raises(ValueError):
        REGISTRI[KALIBAGI](**kwargs)


# ═══ kalimat_matematika ══════════════════════════════════════════════════

TAMBAH_KURANG = ("tambah_akhir", "tambah_awal", "kurang_akhir", "kurang_awal")
KALI_BAGI = ("kali_akhir", "kali_awal", "bagi_akhir", "bagi_awal")
BENTUK_LEVEL = {"P3": TAMBAH_KURANG, "P4": TAMBAH_KURANG, "P5": KALI_BAGI}
BATAS_LEVEL = {"P3": 100, "P4": 1000, "P5": 1000}


def _dedupe(urut, kunci):
    """Urutan kandidat = prioritas; jawaban kembar atau sama dengan kunci dibuang (saring_malrule)."""
    pakai, hasil = {str(kunci)}, {}
    for nama, kode, jawaban in urut:
        if str(jawaban) in pakai:
            continue
        pakai.add(str(jawaban))
        hasil[nama] = (kode, str(jawaban))
    return hasil


def oracle_malrule_kalimat(varian, t, h, kunci):
    sama_atau_kebalikan = {
        "tambah_akhir": ("operasi_sama_bukan_kebalikan", t + h),
        "tambah_awal": ("operasi_sama_bukan_kebalikan", t + h),
        "kurang_akhir": ("operasi_kebalikan_bukan_sama", t + h),
        "kurang_awal": ("operasi_sama_bukan_kebalikan", abs(h - t)),
        "kali_akhir": ("operasi_sama_bukan_kebalikan", t * h),
        "kali_awal": ("operasi_sama_bukan_kebalikan", t * h),
        "bagi_akhir": ("operasi_kebalikan_bukan_sama", t * h),
        "bagi_awal": ("operasi_sama_bukan_kebalikan", h // t),
    }[varian]
    return _dedupe([(sama_atau_kebalikan[0], "K", sama_atau_kebalikan[1]),
                    ("salin_dekat", "H", t), ("salin_hasil", "H", h)], kunci)


@pytest.mark.parametrize("level", LEVEL)
def test_kalimat_domain_bentuk_dan_batas_per_level(level):
    ada, batas = set(), BATAS_LEVEL[level]
    for seed in SAPU:
        soal = _soal(KALIMAT, level, seed)
        p = soal.parameter
        ada.add(p["varian"])
        assert p["varian"] in BENTUK_LEVEL[level]
        assert max(p["tampak"], p["hasil"], int(soal.kunci)) <= batas
        assert min(p["tampak"], p["hasil"], int(soal.kunci)) >= 2
    assert ada == set(BENTUK_LEVEL[level])


@pytest.mark.parametrize("level", LEVEL)
def test_kalimat_malrule_cocok_oracle_dan_ada_k(level):
    for seed in SAPU:
        soal = _soal(KALIMAT, level, seed)
        p = soal.parameter
        harapan = oracle_malrule_kalimat(p["varian"], p["tampak"], p["hasil"], soal.kunci)
        assert _jawaban(soal) == harapan, (soal.teks, _jawaban(soal), harapan)
        assert len(soal.malrule) >= 2
        assert [m.kode for m in soal.malrule][0] == "K"


def test_kalimat_semua_bentuk_punya_k_pada_sapu_besar():
    for level in LEVEL:
        lihat = {}
        for seed in range(800):
            soal = _soal(KALIMAT, level, seed)
            lihat.setdefault(soal.parameter["varian"], []).append(
                {m.kode for m in soal.malrule})
        assert set(lihat) == set(BENTUK_LEVEL[level])
        assert all("K" in kode for daftar in lihat.values() for kode in daftar)


def test_kalimat_contoh_tangan():
    f = REGISTRI[KALIMAT]
    kasus = {
        ("tambah_akhir", 45, 120): ("Isi bilangan yang hilang: 45 + ... = 120", "75",
                                    "Bilangan yang hilang dicari dengan operasi kebalikan, yaitu pengurangan: 120 − 45 = 75. Cek: 45 + 75 = 120."),
        ("tambah_awal", 45, 120): ("Isi bilangan yang hilang: ... + 45 = 120", "75",
                                   "Bilangan yang hilang dicari dengan operasi kebalikan, yaitu pengurangan: 120 − 45 = 75. Cek: 75 + 45 = 120."),
        ("kurang_akhir", 120, 45): ("Isi bilangan yang hilang: 120 − ... = 45", "75",
                                    "120 dikurangi berapa supaya hasilnya 45? Kurangkan: 120 − 45 = 75. Cek: 120 − 75 = 45."),
        ("kurang_awal", 45, 75): ("Isi bilangan yang hilang: ... − 45 = 75", "120",
                                  "Setelah dikurangi 45, hasilnya 75. Bilangan awalnya dicari dengan penjumlahan: 75 + 45 = 120. Cek: 120 − 45 = 75."),
        ("kali_akhir", 12, 360): ("Isi bilangan yang hilang: 12 × ... = 360", "30",
                                  "Bilangan yang hilang dicari dengan operasi kebalikan, yaitu pembagian: 360 ÷ 12 = 30. Cek: 12 × 30 = 360."),
        ("kali_awal", 12, 360): ("Isi bilangan yang hilang: ... × 12 = 360", "30",
                                 "Bilangan yang hilang dicari dengan operasi kebalikan, yaitu pembagian: 360 ÷ 12 = 30. Cek: 30 × 12 = 360."),
        ("bagi_akhir", 360, 12): ("Isi bilangan yang hilang: 360 ÷ ... = 12", "30",
                                  "360 dibagi berapa supaya hasilnya 12? Bagilah: 360 ÷ 12 = 30. Cek: 360 ÷ 30 = 12."),
        ("bagi_awal", 12, 36): ("Isi bilangan yang hilang: ... ÷ 12 = 36", "432",
                                "Bilangan itu dibagi 12 hasilnya 36. Bilangan awalnya dicari dengan perkalian: 36 × 12 = 432. Cek: 432 ÷ 12 = 36."),
    }
    for (varian, t, h), (teks, kunci, pembahasan) in kasus.items():
        soal = f(varian=varian, tampak=t, hasil=h)
        assert (soal.teks, soal.kunci, soal.pembahasan) == (teks, kunci, pembahasan), varian
        assert soal.teks == teks
        assert solver_kalimat(soal.teks) == kunci
    k = f(varian="tambah_akhir", tampak=45, hasil=120)
    assert _jawaban(k) == {"operasi_sama_bukan_kebalikan": ("K", "165"),
                           "salin_dekat": ("H", "45"), "salin_hasil": ("H", "120")}
    k = f(varian="bagi_awal", tampak=12, hasil=36)
    assert _jawaban(k) == {"operasi_sama_bukan_kebalikan": ("K", "3"),
                           "salin_dekat": ("H", "12"), "salin_hasil": ("H", "36")}
    k = f(varian="kurang_akhir", tampak=120, hasil=45)
    assert _jawaban(k)["operasi_kebalikan_bukan_sama"] == ("K", "165")


@pytest.mark.parametrize("kwargs", [
    dict(varian="tambah_akhir", tampak=1, hasil=120),        # tampak terlalu kecil
    dict(varian="tambah_akhir", tampak=45, hasil=46),        # kunci 1
    dict(varian="tambah_akhir", tampak=45, hasil=45),        # kunci 0
    dict(varian="tambah_akhir", tampak=45, hasil=1001),
    dict(varian="kurang_awal", tampak=700, hasil=500),       # kunci 1200 > 1000
    dict(varian="kali_akhir", tampak=12, hasil=361),         # tidak habis
    dict(varian="kali_akhir", tampak=12, hasil=12),          # kunci 1
    dict(varian="bagi_akhir", tampak=360, hasil=7),          # tidak habis
    dict(varian="bagi_akhir", tampak=24, hasil=24),
    dict(varian="bagi_awal", tampak=12, hasil=37),           # h tidak habis dibagi t
    dict(varian="bagi_awal", tampak=40, hasil=80),           # kunci 3200
    dict(varian="kurang_akhir", tampak=45, hasil=120),       # hasil lebih besar dari tampak
    dict(varian="kurang_awal", tampak=45, hasil=45),         # pengecoh |h - t| = 0
    dict(varian="tambah_akhir", tampak="45", hasil=120),
    dict(varian="tambah_akhir", tampak=45.0, hasil=120),
    dict(varian="tambah_akhir", tampak=True, hasil=120),
    dict(varian="pangkat", tampak=2, hasil=4),
    dict(varian=None, tampak=2, hasil=4),
])
def test_kalimat_parameter_tidak_sah_ditolak(kwargs):
    with pytest.raises(ValueError):
        REGISTRI[KALIMAT](**kwargs)


# ═══ umum: pembahasan, determinisme, sapu resmi ══════════════════════════

ISTILAH_GURU = ("malrule", "diagnosis", "miskonsepsi", "kode k", "hipotesis")


@pytest.mark.parametrize("template_id", sorted(SOLVER))
@pytest.mark.parametrize("level", LEVEL)
def test_pembahasan_kalimat_penuh_benar_dan_ramah_anak(template_id, level):
    for seed in SEED:
        soal = _soal(template_id, level, seed)
        teks = soal.pembahasan
        assert teks.strip().endswith("."), teks
        assert len(teks) > 40 and teks.count(".") >= 1 and "None" not in teks and "{" not in teks
        assert not any(k in teks.lower() for k in ISTILAH_GURU)
        angka = {m.replace(".", "") for m in re.findall(r"\d[\d.]*\d|\d", teks)}
        assert soal.kunci in angka, ("kunci tidak muncul di pembahasan", teks)


def _hitungan_dalam_pembahasan_benar(teks: str) -> None:
    """Setiap persamaan 'x op y = z' tunggal di pembahasan wajib benar secara hitungan."""
    for kiri, tanda, kanan, hasil in re.findall(
            r"(?<![\d.(])(\d[\d.]*) ([+−×÷]) (\d[\d.]*) = (\d[\d.]*)(?![\d.]*\s*[+−×÷])", teks):
        a, b, z = _angka(kiri), _angka(kanan), _angka(hasil)
        hitung = {"+": lambda: a + b, "−": lambda: a - b, "×": lambda: a * b, "÷": lambda: a / b}
        assert hitung[tanda]() == z, (teks, kiri, tanda, kanan, hasil)


@pytest.mark.parametrize("template_id", sorted(SOLVER))
@pytest.mark.parametrize("level", LEVEL)
def test_persamaan_tunggal_di_pembahasan_benar(template_id, level):
    for seed in SEED:
        _hitungan_dalam_pembahasan_benar(_soal(template_id, level, seed).pembahasan)


@pytest.mark.parametrize("level", LEVEL)
def test_sapu_seed_0_24_lembar_lima_jenis_lewat_jalur_resmi(level):
    for seed in SEED:
        lembar = generator.buat_lembar(seed, level=level, topik=TOPIK)
        assert len(lembar.soal) == 10
        assert {s.template_id for s in lembar.soal} == {
            "nilai_tempat_besar", URUTKAN, SUSUN, KALIBAGI, KALIMAT}
        for soal in lembar.soal:
            assert soal.level == level and soal.malrule
            if soal.template_id in SOLVER:
                assert soal.kunci == SOLVER[soal.template_id](soal.teks)
        assert generator.buat_lembar(seed, level=level, topik=TOPIK).tanda_tangan == lembar.tanda_tangan


@pytest.mark.parametrize("template_id", sorted(SOLVER))
def test_seed_beda_bervariasi_dan_level_asing_ditolak(template_id):
    paket = topics.ambil(TOPIK)
    for level in LEVEL:
        assert len({_soal(template_id, level, s).tanda_tangan for s in range(60)}) >= 40
    with pytest.raises(ValueError):
        paket.parameter_untuk(template_id, random.Random(1), "P6")
    with pytest.raises(KeyError):
        paket.parameter_untuk("template_lain", random.Random(1), "P3")
