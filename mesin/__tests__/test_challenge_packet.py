"""Enam soal cetak: solver enumeratif, solusi terpisah, tanpa jalur aplikasi."""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/challenge_packet.py"
# Modul skrip dataclass perlu terdaftar saat dimuat (Python 3.9).
import sys
spec = importlib.util.spec_from_file_location("challenge_packet", PATH)
paket = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = paket
spec.loader.exec_module(paket)


def _jam(menit):
    return f"{menit // 60:02d}.{menit % 60:02d}"


def test_solver_independen_enam_tantangan():
    jawaban = {s.id: s.jawaban for s in paket.PAKET}
    bersamaan = sorted(set(range(6, 200, 6)) & set(range(8, 200, 8)))
    assert jawaban["kpk-ketiga"] == _jam(8 * 60 + bersamaan[2])
    kejadian = set(range(12, 181, 12)) & set(range(18, 181, 18))
    assert jawaban["kpk-rentang"] == f"{len(kejadian)} kali"
    berikut = min(set(range(8, 100, 8)) & set(range(12, 100, 12)))
    assert jawaban["kpk-durasi"] == _jam(10 * 60 + berikut + 35)
    motif = ("bunga", "daun", "bintang", "bulan")
    warna = ("merah", "biru", "putih")
    sah = [(m, w) for m, w in itertools.product(motif, warna) if not (m in {"bunga", "daun"} and w == "merah")]
    assert jawaban["cacah-larangan"] == f"{len(sah)} paket"
    lama = set(itertools.combinations(range(6), 2))
    semua = set(itertools.combinations(range(8), 2))
    assert jawaban["cacah-peserta"] == f"{len(semua - lama)} jabat tangan"
    rute = [(a, b, c) for a, b, c in itertools.product(range(3), range(4), range(2)) if b != 0]
    assert jawaban["cacah-jalur"] == f"{len(rute)} rute"
    assert len(jawaban) == 6


def test_paket_soal_tidak_memuat_solusi_tersembunyi():
    soal = paket.render(False)
    solusi = paket.render(True)
    assert "Jawaban:" not in soal
    for item in paket.PAKET:
        assert all(langkah not in soal for langkah in item.langkah)
        assert len(item.langkah) == 2
        assert item.jawaban in solusi
    assert soal.count('<section class="lembar">') == 3
    assert soal.count('class="ruang"') == 6
    assert 'lang="id"' in soal
    assert "<script" not in soal and "<form" not in soal


def test_batas_arsitektur_tidak_memakai_aplikasi():
    tree = ast.parse(PATH.read_text())
    imports = {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports |= {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imports <= {"__future__", "argparse", "dataclasses", "hashlib", "html", "json", "pathlib"}
    import topics
    assert not {s.id for s in paket.PAKET} & {tid for nama in topics.daftar_topik() for tid in topics.ambil(nama).templates}


def test_ekspor_baru_saja_dan_hash(tmp_path):
    tujuan = tmp_path / "paket"
    manifest = paket.ekspor(tujuan)
    assert json.loads((tujuan / "manifest.json").read_text()) == manifest
    for nama, sidik in manifest["berkas_sha256"].items():
        assert hashlib.sha256((tujuan / nama).read_bytes()).hexdigest() == sidik
    before = (tujuan / "soal.html").read_bytes()
    with pytest.raises(FileExistsError):
        paket.ekspor(tujuan)
    assert (tujuan / "soal.html").read_bytes() == before


def test_mutation_kunci_paket_ditangkap(monkeypatch):
    from dataclasses import replace
    monkeypatch.setattr(paket, "PAKET", (replace(paket.PAKET[0], jawaban="09.13"), *paket.PAKET[1:]))
    with pytest.raises(AssertionError):
        test_solver_independen_enam_tantangan()
