"""Empat jenis terpilih: solver independen dan arti malrule dari data mentah."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest

import generator
import topics
from templates import REGISTRI

JENIS = ("banyak_kelipatan", "sisa_operasi", "banyak_prima", "jumlah_kelipatan")


def _fungsi(tid):
    paket = topics.ambil("teori-bilangan")
    assert tid in paket.templates, f"jenis terpilih belum terdaftar: {tid}"
    return paket.templates[tid]


def _prima_saringan(b):
    sah = [True] * (b + 1)
    sah[0] = False
    if b >= 1:
        sah[1] = False
    for x in range(2, b + 1):
        if sah[x]:
            for y in range(2 * x, b + 1, x):
                sah[y] = False
    return {x for x, prima in enumerate(sah) if prima}


def _solver(tid, p):
    if tid == "banyak_kelipatan":
        return len([x for x in range(p["a"], p["b"] + 1) if x % p["k"] == 0])
    if tid == "jumlah_kelipatan":
        return sum(range(p["k"], p["n"] + 1, p["k"]))
    if tid == "banyak_prima":
        return len(_prima_saringan(p["b"]) & set(range(p["a"], p["b"] + 1)))
    # Bangun bilangan utuh dari sisa; kurangi kelipatan pembagi tanpa %.
    a, b = 3 * p["d"] + p["r1"], 7 * p["d"] + p["r2"]
    hasil = a + b if p["varian"] == "jumlah" else a * b
    while hasil >= p["d"]:
        hasil -= p["d"]
    return hasil


def _harapan_malrule(tid, p, kunci):
    if tid == "banyak_kelipatan":
        return {"kelipatan.abaikan_awal": p["b"] // p["k"],
                "kelipatan.semua_bilangan": p["b"] - p["a"] + 1,
                "kelipatan.kurang_satu": kunci - 1}
    if tid == "jumlah_kelipatan":
        q = p["n"] // p["k"]
        return {"jumlah_kelipatan.hanya_banyak": q,
                "jumlah_kelipatan.tanpa_faktor": sum(range(1, q + 1)),
                "jumlah_kelipatan.kurang_satu": kunci - 1}
    if tid == "banyak_prima":
        prima = _prima_saringan(p["b"])
        return {"prima.semua_ganjil": sum(x % 2 for x in range(p["a"], p["b"] + 1)),
                "prima.komposit": sum(x > 1 and x not in prima for x in range(p["a"], p["b"] + 1)),
                "prima.lebih_satu": kunci + 1}
    r1, r2, d = p["r1"], p["r2"], p["d"]
    mentah = r1 + r2 if p["varian"] == "jumlah" else r1 * r2
    tertukar = r1 * r2 if p["varian"] == "jumlah" else r1 + r2
    return {"sisa_operasi.tanpa_modulo": mentah,
            "sisa_operasi.tertukar": tertukar % d, "sisa_operasi.lebih_satu": kunci + 1}


@pytest.mark.parametrize("tid", JENIS)
@pytest.mark.parametrize("level", ("P4", "P5"))
def test_solver_dan_malrule_600_seed(tid, level):
    _fungsi(tid)
    konsep = 0
    varian = set()
    for seed in range(600):
        soal = generator.buat_soal(tid, seed, level, "teori-bilangan")
        p = soal.parameter
        expected = _solver(tid, p)
        assert soal.kunci == str(expected), ("kunci solver berbeda", tid, level, seed, p)
        harapan = _harapan_malrule(tid, p, expected)
        assert len(soal.malrule) == 3, (tid, p, soal.malrule)
        for m in soal.malrule:
            assert m.jawaban == str(harapan[m.id]), ("arti malrule berbeda", m, p)
            assert m.kode == ("H" if m.id.endswith(("kurang_satu", "lebih_satu")) else "K")
        assert len({soal.kunci, *(m.jawaban for m in soal.malrule)}) == 4
        assert all(int(m.jawaban) >= 0 for m in soal.malrule)
        konsep += any(m.kode == "K" for m in soal.malrule)
        assert soal.pembahasan and soal.kunci in soal.pembahasan
        assert "malrule" not in soal.pembahasan.lower()
        varian.add(p.get("varian", "-"))
        assert replace(REGISTRI[tid](**p), level=level) == soal
    assert konsep / 600 >= 0.98
    if tid == "sisa_operasi":
        assert varian == {"jumlah", "kali"}


@pytest.mark.parametrize("tid,p,jawaban", (
    ("banyak_kelipatan", {"k": 3, "a": 10, "b": 25}, 5),
    ("banyak_kelipatan", {"k": 5, "a": 1, "b": 4}, 0),
    ("banyak_kelipatan", {"k": 5, "a": 5, "b": 5}, 1),
    ("sisa_operasi", {"d": 5, "r1": 3, "r2": 4, "varian": "jumlah"}, 2),
    ("sisa_operasi", {"d": 5, "r1": 0, "r2": 4, "varian": "kali"}, 0),
    ("sisa_operasi", {"d": 5, "r1": 1, "r2": 4, "varian": "jumlah"}, 0),
    ("banyak_prima", {"a": 10, "b": 20}, 4),
    ("banyak_prima", {"a": 1, "b": 1}, 0),
    ("banyak_prima", {"a": 1, "b": 2}, 1),
    ("banyak_prima", {"a": 24, "b": 28}, 0),
    ("jumlah_kelipatan", {"k": 3, "n": 14}, 30),
    ("jumlah_kelipatan", {"k": 5, "n": 4}, 0),
    ("jumlah_kelipatan", {"k": 5, "n": 5}, 5),
))
def test_batas_dan_contoh(tid, p, jawaban):
    soal = _fungsi(tid)(**p)
    assert soal.kunci == str(jawaban) == str(_solver(tid, p))
    assert all(m.jawaban != soal.kunci and int(m.jawaban) >= 0 for m in soal.malrule)


@pytest.mark.parametrize("tid,p", (
    ("banyak_kelipatan", {"k": 0, "a": 1, "b": 5}),
    ("banyak_kelipatan", {"k": 3, "a": 9, "b": 2}),
    ("banyak_prima", {"a": 0, "b": 5}),
    ("sisa_operasi", {"d": 5, "r1": 5, "r2": 1, "varian": "jumlah"}),
    ("sisa_operasi", {"d": 5, "r1": 1, "r2": 1, "varian": "bagi"}),
    ("jumlah_kelipatan", {"k": 3, "n": -1}),
))
def test_input_di_luar_domain_ditolak(tid, p):
    with pytest.raises(ValueError):
        _fungsi(tid)(**p)


def test_komposisi_baru_tidak_menghapus_jenis_lama():
    paket = topics.ambil("teori-bilangan")
    for level, lama in (("P4", {"keterbagian", "sisa_pembagian", "paritas"}),
                        ("P5", {"keterbagian", "sisa_pembagian", "paritas", "prima_faktorisasi", "kpk_dua_bilangan", "gauss_deret"})):
        komposisi = paket.komposisi[level]
        assert set(JENIS) | lama <= set(komposisi)
        assert len(komposisi) == 10
        assert max(komposisi.count(t) for t in komposisi) <= 2
    assert len(set(paket.komposisi["P6"])) == 7


def test_kartu_label_inventaris_dan_target_materi():
    from rumus import kartu_untuk
    from template_labels import nama_tipe_soal
    from visual_inventory import inventaris_template
    from mastery_catalog import katalog_target
    inventaris = {r["template_id"]: r for r in inventaris_template()}
    for tid in JENIS:
        _fungsi(tid)
        assert kartu_untuk(tid) is not None
        assert "_" not in nama_tipe_soal(tid)
        assert inventaris[tid]["status"] == "sengaja_teks"
        for level in ("P4", "P5"):
            assert any(tid in t.pola for t in katalog_target(level))


@pytest.mark.parametrize("tid", JENIS)
def test_mutation_solver_menangkap_kunci_salah(monkeypatch, tid):
    paket = topics.ambil("teori-bilangan")
    asli = _fungsi(tid)

    def rusak(**p):
        soal = asli(**p)
        return replace(soal, kunci=str(int(soal.kunci) + 1))

    monkeypatch.setitem(paket.templates, tid, rusak)
    with pytest.raises(AssertionError, match="kunci solver berbeda"):
        test_solver_dan_malrule_600_seed(tid, "P4")


@pytest.mark.parametrize("tid", JENIS)
def test_mutation_malrule_terdeteksi(monkeypatch, tid):
    paket = topics.ambil("teori-bilangan")
    asli = _fungsi(tid)

    def rusak(**p):
        soal = asli(**p)
        pertama = replace(soal.malrule[0], jawaban=str(int(soal.malrule[0].jawaban) + 17))
        return replace(soal, malrule=(pertama, *soal.malrule[1:]))

    monkeypatch.setitem(paket.templates, tid, rusak)
    with pytest.raises(AssertionError, match="arti malrule berbeda"):
        test_solver_dan_malrule_600_seed(tid, "P4")


def test_sampler_gagal_terbatas_tidak_menciptakan_malrule():
    import number_theory_expansion as tambahan

    class SelaluNol:
        def randint(self, a, b):
            return a

        def randrange(self, stop):
            return 0

        def choice(self, pilihan):
            return pilihan[0]

    with pytest.raises(RuntimeError, match="500"):
        tambahan.parameter("sisa_operasi", SelaluNol(), "P4")


def test_render_batch_lintas_seed_level():
    import worksheets
    paket = topics.ambil("teori-bilangan")
    for level in ("P4", "P5"):
        for tid in JENIS:
            for seed in range(25):
                soal = generator.buat_soal(tid, seed, level, paket.id)
                assert soal.teks in worksheets.lembar_soal([soal], "Fixture", "2026-10-20", topik_paket=paket)
                assert soal.kunci in worksheets.lembar_penilaian([soal], "Fixture", "2026-10-20", seed, topik_paket=paket)


def test_batch_deterministik_antar_proses():
    skrip = (
        "import json; from dataclasses import asdict; from generator import buat_lembar; "
        "print(json.dumps([asdict(buat_lembar(42,level=lv,topik='teori-bilangan')) "
        "for lv in ('P4','P5')],sort_keys=True))"
    )
    hasil = [subprocess.check_output(
        [sys.executable, "-c", skrip], cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, PYTHONHASHSEED=str(h), PYTHONDONTWRITEBYTECODE="1"),
    ) for h in (1, 97)]
    assert hasil[0] == hasil[1]
