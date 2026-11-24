"""Probe skema deploy untuk tabel laporan Peta (D1-1): tabel belum ada lulus, sudah ada harus persis DDL source.

Preflight berjalan SEBELUM migrasi startup kandidat, jadi tabel yang belum dibuat tidak boleh menggagalkannya; tabel
yang sudah ada tetapi menyimpang (trigger hilang, kolom berubah) harus menggagalkan. Probe hanya membaca (mode=ro).
"""
from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

AKAR = Path(__file__).resolve().parents[2]
SUMBER_MESIN = AKAR / "mesin"
PREFIKS = "import sqlite3\n"


def _deployer():
    spec = importlib.util.spec_from_file_location("deploy_peta_laporan_uji", AKAR / "scripts/deploy.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _db_belajar(tmp_path):
    import database

    path = tmp_path / "latihan.db"
    database.siapkan(path)
    return path


def _jalankan(tmp_path, sumber_app=SUMBER_MESIN):
    skrip = PREFIKS + _deployer().PROBE_PETA_LAPORAN_SKEMA.replace(
        "/app/", str(sumber_app) + "/").replace("/data/", str(tmp_path) + "/")
    return subprocess.run([sys.executable, "-E", "-B", "-"], input=skrip, capture_output=True,
                          text=True, timeout=20, check=False, shell=False)


def _sidik(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hapus_objek_peta(path):
    with sqlite3.connect(path) as kon:
        for (nama,) in kon.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='peta_laporan'").fetchall():
            kon.execute('DROP TRIGGER "%s"' % nama)
        kon.execute("DROP TABLE peta_laporan")


def test_probe_skema_utuh_memuat_blok_peta_laporan_sebelum_penanda_sukses():
    skrip = _deployer().PROBE_SKEMA
    assert "SKEMA_PETA_LAPORAN" in skrip
    assert skrip.index("SKEMA_PETA_LAPORAN") < skrip.index("print('OSN_SCHEMA_ADMIN9_AI2_OK')")
    assert "mode=ro" in skrip and "siapkan" not in skrip


def test_tabel_sehat_lulus_dan_db_tidak_berubah(tmp_path):
    path = _db_belajar(tmp_path)
    sebelum = _sidik(path)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    assert _sidik(path) == sebelum


def test_tabel_belum_ada_lulus_karena_preflight_sebelum_migrasi(tmp_path):
    path = _db_belajar(tmp_path)
    _hapus_objek_peta(path)
    sebelum = _sidik(path)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    assert _sidik(path) == sebelum


@pytest.mark.parametrize("nama", [
    "peta_laporan_insert_draf", "peta_laporan_terbit_tetap", "peta_laporan_isi_tetap",
    "peta_laporan_terbit_butuh_catatan",
])
def test_trigger_hilang_menggagalkan_probe(tmp_path, nama):
    path = _db_belajar(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute('DROP TRIGGER "%s"' % nama)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "AssertionError" in hasil.stderr


def test_kolom_berubah_menggagalkan_probe(tmp_path):
    path = _db_belajar(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE peta_laporan ADD COLUMN bocor TEXT")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "AssertionError" in hasil.stderr


def test_trigger_dilemahkan_menggagalkan_probe(tmp_path):
    path = _db_belajar(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("DROP TRIGGER peta_laporan_terbit_tetap")
        kon.execute("CREATE TRIGGER peta_laporan_terbit_tetap BEFORE UPDATE ON peta_laporan WHEN 0 "
                    "BEGIN SELECT RAISE(ABORT, 'x'); END")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "AssertionError" in hasil.stderr


def test_image_lama_tanpa_modul_skema_tidak_memeriksa_tabel_tambahan(tmp_path):
    """Recovery (image lama) boleh membuka DB yang sudah memuat tabel baru; probe tidak menggagalkannya."""
    path = _db_belajar(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE peta_laporan ADD COLUMN bocor TEXT")
    kosong = tmp_path / "app-lama"
    kosong.mkdir()
    assert _jalankan(tmp_path, kosong).returncode == 0
