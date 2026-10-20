"""Regresi posisi kunci dan arti malrule, bukan heuristik angka pada teks."""
from __future__ import annotations

import os
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import topic_statistics as statistika
from generator import buat_lembar, buat_soal


@pytest.mark.parametrize("level", ("P4", "P5", "P6"))
def test_keterbagian_posisi_seimbang_dengan_solver_independen(level):
    posisi = Counter()
    for seed in range(600):
        soal = buat_soal("keterbagian", seed, level, "teori-bilangan")
        p = soal.parameter
        pilihan = [p[k] for k in ("a", "b", "c")]
        benar = [i for i, nilai in enumerate(pilihan) if nilai % p["d"] == 0]
        assert len(benar) == 1, p
        assert p["jawab"] == benar[0], p
        assert soal.kunci == str(pilihan[benar[0]]), p
        posisi[benar[0]] += 1
        aturan = {m.id: m for m in soal.malrule}
        trap = {2: 3, 3: 2, 4: 2, 5: 3, 6: 2, 8: 4, 9: 3, 11: 9}[p["d"]]
        salah = int(aturan["keterbagian.pilih_tak_habis"].jawaban)
        jebakan = int(aturan["keterbagian.trap_divisor"].jawaban)
        assert salah in pilihan and salah % p["d"] and salah % trap
        assert jebakan in pilihan and jebakan % trap == 0 and jebakan % p["d"]
        assert aturan["keterbagian.pilih_tak_habis"].kode == "B"
        assert aturan["keterbagian.trap_divisor"].kode == "K"
        h = aturan.get("keterbagian.kurang_satu")
        if h is not None:
            assert h.jawaban == str(int(soal.kunci) - 1) and h.kode == "H"
        assert len({soal.kunci, *(m.jawaban for m in soal.malrule)}) == 1 + len(soal.malrule)
    assert all(0.25 <= posisi[i] / 600 <= 0.42 for i in range(3)), posisi


@pytest.mark.parametrize("level", ("P3", "P4", "P5", "P6"))
def test_modus_posisi_mengikuti_frekuensi_data(level):
    jumlah = pertama = 0
    ekspektasi = 0.0
    for seed in range(600):
        soal = buat_soal("median_modus", seed, level, "statistika")
        if soal.parameter["varian"] != "modus":
            continue
        data = soal.parameter["data"]
        # Solver terpisah: hitung kemunculan tiap nilai tanpa Counter/max milik template.
        pemenang = [x for x in set(data) if all(data.count(x) > data.count(y) for y in set(data) - {x})]
        assert len(pemenang) == 1, data
        modus = pemenang[0]
        assert soal.kunci == str(modus), data
        jumlah += 1
        pertama += data[0] == modus
        ekspektasi += data.count(modus) / len(data)
    assert jumlah >= 200
    assert pertama / jumlah <= ekspektasi / jumlah + 0.10, (level, pertama, jumlah, ekspektasi)


@pytest.mark.parametrize("data", (
    [5, 5, 3], [3, 5, 5], [4, 5, 5], [5, 5, 5], [2, 2, 4, 4, 4],
    [4, 5, 5, 5, 6, 6],
))
def test_modus_pertama_tidak_mengarang_jawaban(data):
    soal = statistika.median_modus("modus", data)
    aturan = {m.id: m for m in soal.malrule}
    pertama = aturan.get("modus.pertama")
    if str(data[0]) == soal.kunci:
        assert pertama is None, aturan
    else:
        assert pertama is not None and pertama.jawaban == str(data[0]) and pertama.kode == "K"
    for m in soal.malrule:
        if m.kode == "K":
            assert int(m.jawaban) in data and m.jawaban != soal.kunci, m
        elif m.kode == "H":
            assert abs(int(m.jawaban) - int(soal.kunci)) == 1, m
    assert len({soal.kunci, *(m.jawaban for m in soal.malrule)}) == len(soal.malrule) + 1


def test_modus_tanpa_h_jika_dua_tetangga_dipakai_k():
    soal = statistika.median_modus("modus", [4, 5, 5, 5, 6, 6])
    assert {(m.id, m.jawaban, m.kode) for m in soal.malrule} == {
        ("modus.pertama", "4", "K"), ("modus.kedua", "6", "K"),
    }


@pytest.mark.parametrize("level", ("P3", "P4", "P5", "P6"))
def test_modus_sampler_mempertahankan_k_yang_bermakna(level):
    jumlah = konsep = 0
    for seed in range(600):
        p = statistika._parameter("median_modus", random.Random(seed), level)
        if p["varian"] != "modus":
            continue
        soal = statistika.median_modus(**p)
        jumlah += 1
        data = p["data"]
        assert len(set(data)) > 1, p
        assert 3 <= len(data) <= (5 if level == "P3" else 8)
        assert all(1 <= x <= (12 if level == "P3" else 40) for x in data)
        k = [m for m in soal.malrule if m.kode == "K"]
        konsep += bool(k)
        assert all(int(m.jawaban) in data and m.jawaban != soal.kunci for m in k)
        assert all(abs(int(m.jawaban) - int(soal.kunci)) == 1 for m in soal.malrule if m.kode == "H")
        pertama = next((m for m in k if m.id == "modus.pertama"), None)
        assert (pertama.jawaban if pertama else None) == (str(data[0]) if str(data[0]) != soal.kunci else None)
    assert jumlah >= 200 and konsep / jumlah >= 0.98


def test_pg_modus_melengkapi_dari_data_tanpa_malrule_rekaan():
    from choice_generation import kandidat

    soal = statistika.median_modus("modus", [5, 5, 2, 8, 9])
    aturan = soal.malrule
    kebijakan, jenis, pengecoh = kandidat(soal)
    assert (kebijakan, jenis) == ("empat-v1", "angka")
    assert len(set(pengecoh)) == 3 and soal.kunci not in pengecoh
    assert set(pengecoh) <= {m.jawaban for m in aturan} | {str(x) for x in soal.parameter["data"]}
    assert soal.malrule == aturan
    assert "modus.pertama" not in {m.id for m in soal.malrule}


@pytest.mark.parametrize("topik", ("teori-bilangan", "statistika"))
def test_fix_posisi_deterministik_antar_proses(topik):
    skrip = (
        "from dataclasses import asdict; import json; from generator import buat_lembar; "
        "print(json.dumps(asdict(buat_lembar(42, level='P4', topik=" + repr(topik) + ")), sort_keys=True))"
    )
    keluaran = []
    for hashseed in ("1", "97"):
        env = dict(os.environ, PYTHONHASHSEED=hashseed, PYTHONDONTWRITEBYTECODE="1")
        keluaran.append(subprocess.check_output(
            [sys.executable, "-c", skrip], cwd=Path(__file__).resolve().parents[1], env=env,
        ))
    assert keluaran[0] == keluaran[1]
    assert buat_lembar(42, level="P4", topik=topik) == buat_lembar(42, level="P4", topik=topik)
