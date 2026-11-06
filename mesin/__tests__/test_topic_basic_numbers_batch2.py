"""Bilangan dasar batch 2 (6 Nov 2026): kurang_dasar dan bilangan_hilang.

Domain dan solver ditulis ulang di sini secara terpisah dari kode aplikasi
(enumerasi brute force dan penyelesaian persamaan dari teks soal). Malrule
adalah hipotesis untuk ditinjau guru; test mengunci definisi yang dipilih.
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

import generator
import topics
from templates import REGISTRI

TOPIK = "bilangan-dasar"
KURANG = "kurang_dasar"
HILANG = "bilangan_hilang"
LEVEL = ("P1", "P2")
FORM = ("tambah_akhir", "tambah_awal", "kurang_akhir", "kurang_awal")
KATA_TERLARANG = re.compile(r"malrule|diagnos|miskonsepsi|hipotesis|kunci|\b[KH]\b", re.I)
PERSAMAAN = re.compile(r"(\d+) ([+−]) (\d+) = (\d+)")
AKAR_MESIN = Path(__file__).resolve().parents[1]


def _paket():
    return topics.ambil(TOPIK)


def _domain_kurang(level):
    if level == "P1":
        return {(b + h, b) for b in range(1, 11) for h in range(0, 10) if b + h <= 10}
    return {(a, a - h) for a in range(11, 21) for h in range(0, 20) if 1 <= a - h <= 10}


def _selesaikan(teks):
    """Selesaikan persamaan satu kotak langsung dari teks soal (brute force)."""
    cocok = re.fullmatch(r"(\.\.\.|\d+) ([+−]) (\.\.\.|\d+) = (\d+)", teks)
    assert cocok, teks
    kiri, op, kanan, hasil = cocok.groups()
    solusi = []
    for n in range(0, 41):
        a = n if kiri == "..." else int(kiri)
        b = n if kanan == "..." else int(kanan)
        if (a + b if op == "+" else a - b) == int(hasil):
            solusi.append(n)
    assert len(solusi) == 1, teks
    return solusi[0]


def _teks_bentuk(bentuk, tampak, hasil):
    return {
        "tambah_akhir": f"{tampak} + ... = {hasil}",
        "tambah_awal": f"... + {tampak} = {hasil}",
        "kurang_akhir": f"{tampak} − ... = {hasil}",
        "kurang_awal": f"... − {tampak} = {hasil}",
    }[bentuk]


def _domain_hilang(level):
    """Semua persamaan satu kotak; bilangan 0 tidak dipakai (sepele)."""
    batas = 10 if level == "P1" else 20
    hasil = set()
    for bentuk in FORM:
        for tampak in range(1, batas + 1):
            for sesudah in range(1, batas + 1):
                try:
                    dicari = _selesaikan(_teks_bentuk(bentuk, tampak, sesudah))
                except AssertionError:
                    continue
                angka = (tampak, sesudah, dicari)
                if dicari >= 1 and max(angka) <= batas and (level == "P1" or max(angka) >= 11):
                    hasil.add((bentuk, tampak, sesudah))
    return hasil


def _param_hilang(p):
    return (p["bentuk"], p["tampak"], p["hasil"])


@pytest.mark.parametrize("level,jumlah", (("P1", 55), ("P2", 100)))
def test_domain_dan_solver_kurang(level, jumlah):
    from topic_basic_numbers import domain_parameter
    domain = domain_parameter(KURANG, level)
    pasangan = {(p["a"], p["b"]) for p in domain}
    assert len(domain) == len(pasangan) == jumlah
    assert pasangan == _domain_kurang(level)
    assert all(set(p) == {"a", "b"} and all(type(v) is int for v in p.values()) for p in domain)
    fungsi = _paket().templates[KURANG]
    for a, b in sorted(pasangan):
        soal = fungsi(a=a, b=b)
        assert soal.teks == f"{a} − {b} = ..."
        assert soal.kunci == str(a - b) and soal.parameter == {"a": a, "b": b}
        assert soal.bagian == "B"
        assert int(soal.kunci) >= (0 if level == "P1" else 1)


@pytest.mark.parametrize("level,jumlah", (("P1", 180), ("P2", 580)))
def test_domain_dan_solver_hilang(level, jumlah):
    from topic_basic_numbers import domain_parameter
    domain = domain_parameter(HILANG, level)
    kunci = {_param_hilang(p) for p in domain}
    assert len(domain) == len(kunci) == jumlah
    assert kunci == _domain_hilang(level)
    fungsi = _paket().templates[HILANG]
    for p in domain:
        assert set(p) == {"bentuk", "tampak", "hasil"}
        json.dumps(p)  # parameter JSON murni
        soal = fungsi(**p)
        assert soal.parameter == p and soal.bagian == "C"
        assert soal.kunci == str(_selesaikan(soal.teks)), soal.teks
        assert int(soal.kunci) >= 1


@pytest.mark.parametrize("tid", (KURANG, HILANG))
def test_domain_tidak_menjadi_state_dan_menolak_identitas_tidak_sah(tid):
    from topic_basic_numbers import domain_parameter
    paket = _paket()
    domain = domain_parameter(tid, "P1")
    domain[0]["tampak" if tid == HILANG else "a"] = -1
    assert domain_parameter(tid, "P1")[0] != domain[0]
    for level in ("P3", "P6", "", "p1"):
        with pytest.raises(ValueError):
            domain_parameter(tid, level)
        with pytest.raises(ValueError):
            paket.parameter_untuk(tid, random.Random(0), level)
    with pytest.raises(KeyError):
        domain_parameter("jenis_tidak_ada", "P1")


@pytest.mark.parametrize("a,b", ((0, 0), (0, 1), (5, 6), (11, 11), (21, 1), (11, 0), (-1, 1),
                                (True, 1), (5, False), (5.0, 2), ("7", 2), (None, 1), (10, 11)))
def test_parameter_kurang_tidak_sah(a, b):
    with pytest.raises(ValueError, match="domain"):
        _paket().templates[KURANG](a=a, b=b)


@pytest.mark.parametrize("bentuk,tampak,hasil", (
    ("tambah_akhir", 5, 5), ("tambah_akhir", 0, 5), ("tambah_awal", 9, 3), ("kurang_akhir", 3, 3),
    ("kurang_akhir", 5, 0), ("kurang_awal", 1, 20), ("tambah_akhir", 1, 21), ("diagonal", 1, 3),
    ("tambah_akhir", True, 3), ("tambah_akhir", 1.0, 3), ("kurang_awal", "2", 3), ("tambah_awal", 1, None),
))
def test_parameter_hilang_tidak_sah(bentuk, tampak, hasil):
    with pytest.raises(ValueError, match="domain"):
        _paket().templates[HILANG](bentuk=bentuk, tampak=tampak, hasil=hasil)


def _harapan_kurang(a, b):
    kunci = a - b
    kandidat = [("operasi_tertukar", a + b, "K"), ("hitung_mundur_dari_awal", kunci + 1, "H")]
    if a >= 11 and a % 10 < b < 10:
        kandidat.append(("satuan_dibalik", (a // 10) * 10 + (b - a % 10), "K"))
    hasil, terpakai = {}, {kunci}
    for nama, nilai, kode in kandidat:  # urutan = prioritas; tabrakan gugur
        if nilai not in terpakai:
            terpakai.add(nilai)
            hasil[KURANG + "." + nama] = (str(nilai), kode)
    return hasil


@pytest.mark.parametrize("level", LEVEL)
def test_malrule_kurang_seluruh_domain(level):
    fungsi = _paket().templates[KURANG]
    for a, b in sorted(_domain_kurang(level)):
        soal = fungsi(a=a, b=b)
        aktual = {m.id: (m.jawaban, m.kode) for m in soal.malrule}
        assert aktual == _harapan_kurang(a, b), (a, b, aktual)
        assert len({m.jawaban for m in soal.malrule}) == len(soal.malrule)
        assert all(m.jawaban != soal.kunci and len(m.alasan.split()) >= 8 for m in soal.malrule)
        assert len(soal.malrule) >= 2 and any(m.kode == "K" for m in soal.malrule)


def test_satuan_dibalik_pada_a_20_gugur_oleh_operasi_tertukar():
    """a = 20 membuat 'satuan dibalik' = 20 + b, sama dengan a + b: kandidat pertama menang."""
    for b in range(1, 10):
        ids = {m.id for m in _paket().templates[KURANG](a=20, b=b).malrule}
        assert ids == {KURANG + ".operasi_tertukar", KURANG + ".hitung_mundur_dari_awal"}
    ids = {m.id for m in _paket().templates[KURANG](a=13, b=5).malrule}
    assert KURANG + ".satuan_dibalik" in ids
    assert _paket().templates[KURANG](a=13, b=5).malrule[2].jawaban == "12"
    assert KURANG + ".satuan_dibalik" not in {m.id for m in _paket().templates[KURANG](a=17, b=5).malrule}
    assert KURANG + ".satuan_dibalik" not in {m.id for m in _paket().templates[KURANG](a=15, b=10).malrule}


def _harapan_hilang(bentuk, tampak, hasil):
    dicari = _selesaikan(_teks_bentuk(bentuk, tampak, hasil))
    if bentuk == "kurang_akhir":
        utama = ("menjumlah_tampak", tampak + hasil)
    elif bentuk == "kurang_awal":
        utama = ("operasi_terlihat", abs(hasil - tampak))
    else:
        utama = ("operasi_terlihat", tampak + hasil)
    return {
        HILANG + "." + utama[0]: (str(utama[1]), "K"),
        HILANG + ".meleset_satu": (str(dicari + 1), "H"),
    }


@pytest.mark.parametrize("level", LEVEL)
def test_malrule_hilang_seluruh_domain(level):
    fungsi = _paket().templates[HILANG]
    for bentuk, tampak, hasil in sorted(_domain_hilang(level)):
        soal = fungsi(bentuk=bentuk, tampak=tampak, hasil=hasil)
        aktual = {m.id: (m.jawaban, m.kode) for m in soal.malrule}
        assert aktual == _harapan_hilang(bentuk, tampak, hasil), (bentuk, tampak, hasil, aktual)
        assert len({m.jawaban for m in soal.malrule}) == len(soal.malrule) == 2
        assert all(m.jawaban != soal.kunci and len(m.alasan.split()) >= 8 for m in soal.malrule)


def _periksa_kalimat_pembahasan(soal):
    pb = soal.pembahasan
    assert not KATA_TERLARANG.search(pb), pb
    assert 30 <= len(pb) <= 230, (len(pb), pb)
    assert pb.endswith(".") and "..." not in pb
    persamaan = PERSAMAAN.findall(pb)
    assert persamaan, pb
    for a, op, b, c in persamaan:
        assert (int(a) + int(b) if op == "+" else int(a) - int(b)) == int(c), (pb, a, op, b, c)
    return persamaan


@pytest.mark.parametrize("level", LEVEL)
def test_pembahasan_kurang_benar_dan_tidak_berbelit(level):
    fungsi = _paket().templates[KURANG]
    for a, b in sorted(_domain_kurang(level)):
        soal = fungsi(a=a, b=b)
        persamaan = _periksa_kalimat_pembahasan(soal)
        assert persamaan[-1][3] == soal.kunci, (a, b, soal.pembahasan)
        assert len(persamaan) <= 3 and soal.pembahasan.count(".") <= 4
        if a <= 10 and a - b == 1 and b > 1:
            assert "hanya satu langkah maju" in soal.pembahasan, soal.pembahasan
        elif a <= 10 and b < a:
            cocok = re.fullmatch(r"Mulai dari (\d+), hitung (mundur|maju) .*", soal.pembahasan)
            assert cocok, soal.pembahasan
            urut = [int(n) for n in re.findall(r"\d+", soal.pembahasan.split(":")[1].split(".")[0])]
            assert len(urut) == (b if cocok.group(2) == "mundur" else a - b)
        if a > 10 and b < 10 and a - 10 < b:
            assert f"{a} − {a - 10} = 10" in soal.pembahasan  # kurangi dulu sampai 10
        if a > 10 and b < 10 and a - 10 >= b:
            assert "pecah" in soal.pembahasan and "10 +" in soal.pembahasan


@pytest.mark.parametrize("level", LEVEL)
def test_pembahasan_hilang_operasi_kebalikan_dan_cek(level):
    fungsi = _paket().templates[HILANG]
    for bentuk, tampak, hasil in sorted(_domain_hilang(level)):
        soal = fungsi(bentuk=bentuk, tampak=tampak, hasil=hasil)
        persamaan = _periksa_kalimat_pembahasan(soal)
        assert "Cek:" in soal.pembahasan and len(persamaan) == 2
        assert soal.pembahasan.count(soal.kunci) >= 2
        if bentuk.startswith("tambah"):
            assert persamaan[0][1] == "−" and persamaan[1][1] == "+"
        elif bentuk == "kurang_akhir":
            assert persamaan[0][1] == "−" and persamaan[1][1] == "−"
        else:
            assert persamaan[0][1] == "+" and persamaan[1][1] == "−"
        # Cek terakhir adalah soal asli dengan kotak terisi jawabannya.
        isi = soal.teks.replace("...", soal.kunci)
        assert isi.replace(" ", "") in soal.pembahasan.replace(" ", "")


@pytest.mark.parametrize("tid", (KURANG, HILANG))
@pytest.mark.parametrize("level", LEVEL)
def test_seed_0_sampai_24_kunci_solver_dan_malrule(tid, level):
    paket = _paket()
    for seed in range(25):
        soal = generator.buat_soal(tid, seed, level, TOPIK)
        assert soal == generator.buat_soal(tid, seed, level, TOPIK)
        p = paket.parameter_untuk(tid, random.Random(seed), level)
        assert soal == replace(REGISTRI[tid](**p), level=level)
        if tid == KURANG:
            a, b = soal.parameter["a"], soal.parameter["b"]
            assert soal.kunci == str(a - b)
            assert (a, b) in _domain_kurang(level)
        else:
            assert soal.kunci == str(_selesaikan(soal.teks))
            assert _param_hilang(soal.parameter) in _domain_hilang(level)
        assert soal.malrule and all(m.jawaban != soal.kunci for m in soal.malrule)
        assert soal.level == level


@pytest.mark.parametrize("tid", (KURANG, HILANG))
@pytest.mark.parametrize("level", LEVEL)
def test_pg_seluruh_domain_tiga_opsi(tid, level):
    from choice_generation import pilihan_soal
    from topic_basic_numbers import domain_parameter
    fungsi = _paket().templates[tid]
    for p in domain_parameter(tid, level):
        soal = replace(fungsi(**p), level=level)
        pilihan = pilihan_soal(soal, 1, "a" * 64, 0, 1)
        assert len(pilihan.opsi) == 3
        assert {o.nilai for o in pilihan.opsi} == {soal.kunci, *(m.jawaban for m in soal.malrule[:2])}


@pytest.mark.parametrize("tid", (KURANG, HILANG))
@pytest.mark.parametrize("level", LEVEL)
def test_render_lembar_cetak_dan_penilaian(tid, level):
    import worksheets
    paket = _paket()
    soal = tuple(generator.buat_soal(tid, seed, level, TOPIK) for seed in range(10))
    html = worksheets.lembar_soal(soal, "Sintetis", "2026-11-06", topik_paket=paket)
    guru = worksheets.lembar_penilaian(soal, "Sintetis", "2026-11-06", 0, topik_paket=paket)
    assert all(s.teks in html and s.kunci in guru for s in soal)
    judul = {"kurang_dasar": "Pengurangan", "bilangan_hilang": "Bilangan yang hilang"}[tid]
    assert judul in html


def test_registrasi_semua_titik_dan_bukan_target_siklus():
    from mastery_catalog import katalog_target
    from rumus import kartu_untuk
    from template_labels import nama_tipe_soal
    from visual_inventory import inventaris_template
    baris = {r["template_id"]: r for r in inventaris_template()}
    assert nama_tipe_soal(KURANG) == "Pengurangan sampai 20"
    assert nama_tipe_soal(HILANG) == "Bilangan yang hilang"
    for tid in (KURANG, HILANG):
        assert baris[tid]["status"] == "sengaja_teks" and kartu_untuk(tid)
        assert _paket().judul_bagian
    assert _paket().judul_bagian == {"A": "Penjumlahan", "B": "Pengurangan", "C": "Bilangan yang hilang",
                                     "D": "Nilai tempat", "E": "Membandingkan bilangan"}
    for level in ("P3", "P4", "P5", "P6"):
        assert all(not {KURANG, HILANG} & set(t.pola) for t in katalog_target(level))


def test_determinisme_lintas_hashseed():
    skrip = (
        "import json, generator\n"
        "from dataclasses import asdict\n"
        "print(json.dumps([asdict(generator.buat_soal(t, s, lv, 'bilangan-dasar'))\n"
        "  for t in ('kurang_dasar', 'bilangan_hilang') for lv in ('P1', 'P2') for s in range(50)],\n"
        "  sort_keys=True))\n"
    )
    keluaran = []
    for hashseed in ("1", "997"):
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        keluaran.append(subprocess.check_output([sys.executable, "-c", skrip], cwd=AKAR_MESIN, env=env))
    assert keluaran[0] == keluaran[1]
    assert len(json.loads(keluaran[0])) == 200
