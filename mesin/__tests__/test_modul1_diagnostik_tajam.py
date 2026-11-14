"""Regresi Modul 1: paket berhitung-sekolah (P3/P4) & Tes Diagnostik Baku berpasangan."""

from __future__ import annotations

import math
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database  # noqa: E402
import diagnostic_battery  # noqa: E402
import generator  # noqa: E402
import teacher_pages  # noqa: E402
import topics  # noqa: E402
from templates import LEVEL  # noqa: E402


@pytest.fixture()
def db(tmp_path, monkeypatch):
    p = tmp_path / "modul1.db"
    database.siapkan(p)
    monkeypatch.setattr(database, "BAWAAN", p)
    return p


@pytest.mark.parametrize("level", ("P3", "P4"))
def test_berhitung_sekolah_kunci_dan_malrule_independen(level):
    paket = topics.ambil("berhitung-sekolah")
    for tid in sorted(paket.templates):
        for seed in range(30):
            s = generator.buat_soal(tid, seed, level, "berhitung-sekolah")
            assert len(s.malrule) >= 3
            assert sum(1 for m in s.malrule if m.kode == "K") >= 2
            assert all(m.jawaban != s.kunci for m in s.malrule)
            p = s.parameter
            if tid == "perkalian_dasar":
                assert s.kunci == str(p["a"] * p["b"])
            elif tid == "pembagian_dasar":
                assert s.kunci == str(p["hasil"])
            elif tid == "pecahan_bagian_dasar":
                v, d, a, b = p["varian"], p["penyebut"], p["a"], p["b"]
                num = (d - a) if v == "sisa_bagian" else (a + b if v == "jumlah_sama_penyebut" else a - b)
                assert math.gcd(num, d) == 1
                assert s.kunci == f"{num}/{d}"
            elif tid == "nilai_tempat_ribuan":
                faktor = (1, 10, 100, 1000)[p["posisi_idx"]]
                digit = (p["angka"] // faktor) % 10
                if p["varian"] == "nilai_angka":
                    assert s.kunci == str(digit * faktor)
                else:
                    puluhan = ((p["angka"] // 10) % 10) * 10
                    assert s.kunci == str(digit * faktor - puluhan)


@pytest.mark.parametrize("level,harapan", [("P1", 10), ("P2", 10), ("P3", 20), ("P4", 24), ("P5", 24), ("P6", 24)])
def test_baterai_diagnostik_berpasangan_dan_unik_tiap_pasangan(level, harapan):
    paket, lembar, urutan = diagnostic_battery.bangun_lembar_diagnostik(seed=42, level=level)
    assert len(lembar.soal) == len(urutan) == harapan
    assert len({s.tanda_tangan for s in lembar.soal}) == harapan
    assert all(s.level == level for s in lembar.soal)
    # Setiap pasangan berturut-turut menguji template yang sama dengan dua butir berbeda.
    for i in range(0, len(lembar.soal), 2):
        assert lembar.soal[i].template_id == lembar.soal[i + 1].template_id
        assert lembar.soal[i].tanda_tangan != lembar.soal[i + 1].tanda_tangan
    assert paket.id.startswith("gabungan:") or paket.id in topics.PAKET


def test_buat_sesi_diagnostik_baku_di_db_dan_ui(db, monkeypatch):
    monkeypatch.setenv("OSN_MATERI_DASAR", "1")
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Alya Contoh", "P4", pemilik="guru")
        sesi_id = database.buat_sesi_diagnostik(kon, sid, seed=19)
        sesi = kon.execute("SELECT * FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
        isi = database.isi_sesi(kon, sesi_id)
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (sid,)).fetchone()
        html = teacher_pages.halaman_anak(
            kon, siswa, pengguna="guru", privat=True, query="section=latihan"
        ).decode()
    assert sesi["mode"] == "diagnostik"
    assert sesi["level"] == "P4"
    assert sesi["format_jawaban"] == "isian"
    assert len(isi) == 24
    assert Counter(b["template_id"] for b in isi)["perkalian_dasar"] == 2
    assert 'action="/sesi-diagnostik/' in html
    assert "Tes Diagnostik Baku" in html


def test_buat_sesi_diagnostik_menolak_level_asing(db):
    with database.buka(db) as kon:
        sid = database.tambah_siswa(kon, "Bima Contoh", "P3", pemilik="guru")
        with pytest.raises(ValueError, match="jenjang diagnostik"):
            database.buat_sesi_diagnostik(kon, sid, seed=5, level="SMA")
