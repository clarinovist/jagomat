"""Bilangan dasar: seluruh domain sah, solver terpisah, dan arti kesalahan.

Keputusan pengguna 30 Okt 2026: domain kecil P1/P2 tidak diperlebar demi
variasi semu. Malrule adalah hipotesis; review guru tetap diperlukan.
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
JENIS = "tambah_dasar"


def _paket():
    assert TOPIK in topics.daftar_topik(), "topik bilangan-dasar belum terdaftar"
    return topics.ambil(TOPIK)


def _domain_independen(level):
    # Susun menurut jumlah, berbeda dari urutan enumerator aplikasi.
    jumlah = range(2, 11) if level == "P1" else range(11, 21)
    return {(a, total - a) for total in jumlah for a in range(1, total)}


def _domain(level):
    _paket()
    from topic_basic_numbers import domain_parameter
    return domain_parameter(JENIS, level)


def _solver(p):
    # Tidak memakai kunci, enumerator, atau fungsi hitung milik template.
    return p["a"] + p["b"]


@pytest.mark.parametrize("level,jumlah", (("P1", 45), ("P2", 145)))
def test_domain_dan_sampler(level, jumlah):
    paket = _paket()
    domain = _domain(level)
    assert isinstance(domain, tuple)
    assert all(set(p) == {"a", "b"} and all(type(v) is int for v in p.values()) for p in domain)
    pasangan = {(p["a"], p["b"]) for p in domain}
    assert len(domain) == len(pasangan) == jumlah
    assert pasangan == _domain_independen(level)
    sampel = set()
    for seed in range(500):
        p = paket.parameter_untuk(JENIS, random.Random(seed), level)
        assert set(p) == {"a", "b"}
        assert (p["a"], p["b"]) in pasangan, ("sampler keluar domain", level, seed, p)
        sampel.add((p["a"], p["b"]))
        assert p == paket.parameter_untuk(JENIS, random.Random(seed), level)
        assert generator.buat_soal(JENIS, seed, level, TOPIK) == generator.buat_soal(JENIS, seed, level, TOPIK)
    assert len(sampel) >= (9 * jumlah + 9) // 10
    # Dict publik tidak boleh menjadi state mutable yang merusak undian berikutnya.
    domain[0]["a"] = -1
    assert {(p["a"], p["b"]) for p in _domain(level)} == pasangan


@pytest.mark.parametrize("level", ("P1", "P2"))
def test_solver_seluruh_domain(level):
    fungsi = _paket().templates[JENIS]
    for a, b in sorted(_domain_independen(level)):
        p = {"a": a, "b": b}
        soal = fungsi(**p)
        assert soal.kunci == str(_solver(p)), ("kunci solver berbeda", level, p, soal.kunci)
        assert soal.parameter == p
        assert soal.teks == f"{a} + {b} = ..."


@pytest.mark.parametrize("level", ("P1", "P2"))
def test_malrule_seluruh_domain(level):
    fungsi = _paket().templates[JENIS]
    for a, b in sorted(_domain_independen(level)):
        total = a + b
        soal = fungsi(a=a, b=b)
        harapan = {
            JENIS + ".operasi_tertukar": (str(abs(a - b)), "K"),
            JENIS + ".hitung_maju_dari_awal": (str(total - 1), "H"),
        }
        # saring_malrule mempertahankan kandidat pertama saat nilainya sama.
        if total >= 10 and total - 10 != abs(a - b):
            harapan[JENIS + ".lupa_puluhan"] = (str(total - 10), "K")
        aktual = {m.id: (m.jawaban, m.kode) for m in soal.malrule}
        assert aktual == harapan, ("malrule tidak sesuai definisi", a, b, aktual, harapan)
        assert len({m.jawaban for m in soal.malrule}) == len(soal.malrule)
        assert all(m.jawaban != soal.kunci and len(m.alasan.split()) >= 8 for m in soal.malrule)
        assert any(m.kode == "K" for m in soal.malrule)


def test_benturan_dibuang_tanpa_angka_rekaan():
    fungsi = _paket().templates[JENIS]
    for a, b in ((5, 8), (8, 5), (5, 5)):
        soal = fungsi(a=a, b=b)
        assert [m.id for m in soal.malrule] == [JENIS + ".operasi_tertukar", JENIS + ".hitung_maju_dari_awal"]
        assert [m.jawaban for m in soal.malrule] == [str(abs(a - b)), str(a + b - 1)]


@pytest.mark.parametrize("a,b", ((0, 1), (1, 0), (-1, 4), (True, 2), (2, False),
                                (1.0, 3), ("2", 3), (None, 3), (19, 2), (20, 20)))
def test_parameter_tidak_sah_ditolak(a, b):
    with pytest.raises(ValueError, match="domain"):
        _paket().templates[JENIS](a=a, b=b)


def test_enumerator_dan_sampler_menolak_identitas_tidak_sah():
    paket = _paket()
    from topic_basic_numbers import domain_parameter
    for level in ("P3", "P4", "P5", "P6", "", "p1"):
        with pytest.raises(ValueError):
            domain_parameter(JENIS, level)
        with pytest.raises(ValueError):
            paket.parameter_untuk(JENIS, random.Random(0), level)
    with pytest.raises(KeyError):
        domain_parameter("jenis_tidak_ada", "P1")
    with pytest.raises(KeyError):
        paket.parameter_untuk("jenis_tidak_ada", random.Random(0), "P1")


@pytest.mark.parametrize("level", ("P1", "P2"))
def test_pembahasan_langkah_dan_hasil(level):
    fungsi = _paket().templates[JENIS]
    for a, b in sorted(_domain_independen(level)):
        soal = fungsi(a=a, b=b)
        pb = soal.pembahasan
        besar, kecil = max(a, b), min(a, b)
        assert not re.search(r"malrule|diagnos|miskonsepsi|hipotesis|operasi_tertukar|lupa_puluhan|\b[KH]\b", pb, re.I)
        assert 30 <= len(pb) <= 210
        assert pb.endswith("= " + str(a + b) + ".")
        if a + b <= 10:
            cocok = re.fullmatch(r"Mulai dari (\d+), hitung maju (\d+) langkah: ([\d, ]+)\. Jadi (\d+) \+ (\d+) = (\d+)\.", pb)
            assert cocok, (a, b, pb)
            awal, langkah, urut, kiri, kanan, hasil = cocok.groups()
            assert (int(awal), int(langkah)) == (besar, kecil)
            assert [int(n) for n in urut.split(", ")] == list(range(besar + 1, a + b + 1))
            assert (int(kiri), int(kanan), int(hasil)) == (a, b, a + b)
        elif besar < 10:
            cocok = re.fullmatch(r"(\d+) \+ (\d+): ambil (\d+) dari (\d+) supaya (\d+) menjadi 10\. Sisanya (\d+)\. 10 \+ (\d+) = (\d+)\.", pb)
            assert cocok, (a, b, pb)
            kiri, kanan, ambil, asal, awal, sisa, tambah, hasil = map(int, cocok.groups())
            assert (kiri, kanan) == (a, b)
            assert (awal, asal) == (besar, kecil)
            assert awal + ambil == 10 and asal - ambil == sisa == tambah
            assert 10 + tambah == hasil == a + b
        elif besar == 10:
            assert pb == f"{a} + {b}: mulai dari 10, tambah {kecil}. 10 + {kecil} = {a + b}."
        else:
            cocok = re.fullmatch(r"(\d+) \+ (\d+): (\d+) adalah 10 dan (\d+)\. (\d+) \+ (\d+) = (\d+)\. 10 \+ (\d+) = (\d+)\.", pb)
            assert cocok, (a, b, pb)
            kiri, kanan, awal, satuan, tambah1, tambah2, jumlah, akhir, hasil = map(int, cocok.groups())
            assert (kiri, kanan) == (a, b)
            assert awal == besar == 10 + satuan and tambah1 == satuan and tambah2 == kecil
            assert tambah1 + tambah2 == jumlah == akhir
            assert 10 + akhir == hasil == a + b


@pytest.mark.parametrize("level", ("P1", "P2"))
def test_pg_seluruh_domain(level):
    from choice_generation import pilihan_soal
    fungsi = _paket().templates[JENIS]
    for a, b in sorted(_domain_independen(level)):
        soal = replace(fungsi(a=a, b=b), level=level)
        pilihan = pilihan_soal(soal, 1, "a" * 64, 0, 1)
        assert len(pilihan.opsi) == 3
        assert {o.nilai for o in pilihan.opsi} == {soal.kunci, *(m.jawaban for m in soal.malrule[:2])}


def test_render_pg_dan_lembar_seed_0_sampai_24():
    import choice_pages
    from choice_generation import buat_lembar_pilihan, pilihan_soal
    from question_views import penyajian_dari_soal
    import worksheets
    paket = _paket()
    for level in ("P1", "P2"):
        for seed in range(25):
            p = paket.parameter_untuk(JENIS, random.Random(seed), level)
            soal = replace(REGISTRI[JENIS](**p), level=level)
            assert soal == generator.buat_soal(JENIS, seed, level, TOPIK)
            opsi = pilihan_soal(soal, 1, "a" * 64, seed, 1)
            assert len(opsi.opsi) == 3
            assert sum(o.nilai == soal.kunci for o in opsi.opsi) == 1
            assert choice_pages.pertanyaan(penyajian_dari_soal(soal), opsi, JENIS)
            for lembar in (generator.buat_lembar(seed, level=level, topik=TOPIK),
                           buat_lembar_pilihan(seed, level=level, topik=TOPIK)):
                assert len(lembar.soal) == 10
                html = worksheets.lembar_soal(lembar.soal, "Sintetis", "2026-10-30", topik_paket=paket)
                guru = worksheets.lembar_penilaian(lembar.soal, "Sintetis", "2026-10-30", seed, topik_paket=paket)
                assert all(s.teks in html and s.kunci in guru and s.level == level for s in lembar.soal)


def test_determinisme_lintas_proses_dan_writer():
    _paket()
    skrip = (
        "from dataclasses import asdict\n"
        "import json, generator, topics\n"
        "print(json.dumps([asdict(generator.buat_lembar(s, level=lv, topik='bilangan-dasar')) "
        "for lv in ('P1','P2') for s in range(25)], sort_keys=True))\n"
    )
    keluaran = []
    for hashseed, writer in (("1", "1"), ("997", "1"), ("1", "2"), ("997", "2")):
        env = dict(os.environ, PYTHONHASHSEED=hashseed, OSN_KATALOG_VERSI=writer,
                   OSN_MATEMATIKA_VERSI=writer, OSN_TEORI_BILANGAN_VERSI=writer)
        keluaran.append(subprocess.check_output([sys.executable, "-c", skrip],
                                               cwd=Path(__file__).resolve().parents[1], env=env))
    assert all(isi == keluaran[0] for isi in keluaran)
    assert len(json.loads(keluaran[0])) == 50


def test_topik_manual_dan_campuran():
    from question_context import profil_otomatis, validasi_pilihan
    paket = _paket()
    assert set(paket.komposisi) == set(paket.profil) == {"P1", "P2"}
    assert paket.nama == "Bilangan Dasar"
    assert paket.judul_lembar == "Latihan Bilangan Dasar"
    assert paket.judul_penilaian == "Penilaian — Bilangan Dasar"
    assert all(isi == (JENIS,) * 10 for isi in paket.komposisi.values())
    for level in ("P1", "P2"):
        validasi_pilihan([TOPIK], level)
    for level in ("P3", "P4", "P5", "P6"):
        with pytest.raises(ValueError, match="Materi tidak tersedia"):
            validasi_pilihan([TOPIK], level)
        with pytest.raises(ValueError, match="tidak tersedia"):
            generator.buat_lembar(0, level=level, topik=TOPIK)
    assert profil_otomatis([TOPIK], "P3") == "P2"
    campuran = topics.ambil("campuran")
    assert set(campuran.komposisi) == {"P3", "P4", "P5", "P6"}
    assert JENIS not in campuran.templates
    assert all(JENIS not in isi for isi in campuran.komposisi.values())
    assert all(JENIS not in campuran.komposisi_untuk(lv) for lv in campuran.komposisi)


def test_kartu_label_inventaris_tanpa_target_siklus():
    from rumus import kartu_untuk
    from template_labels import nama_tipe_soal
    from visual_inventory import inventaris_template
    from mastery_catalog import katalog_target
    _paket()
    kartu = kartu_untuk(JENIS)
    assert kartu.judul == "Menjumlah sampai 20"
    assert kartu.contoh == "8 + 5 = 8 + 2 + 3 = 13"
    assert nama_tipe_soal(JENIS) == "Penjumlahan sampai 20"
    baris = next(r for r in inventaris_template() if r["template_id"] == JENIS)
    assert baris["status"] == "sengaja_teks"
    for level in ("P3", "P4", "P5", "P6"):
        assert all(JENIS not in target.pola for target in katalog_target(level))
