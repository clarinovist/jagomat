"""Probe skema deploy untuk namespace harga_*: belum ada lulus, sudah ada harus persis DDL source.

Preflight berjalan SEBELUM migrasi, jadi tabel yang belum dibuat tidak boleh menggagalkannya; tabel yang sudah ada tetapi
menyimpang (trigger hilang, kolom berubah, tabel hilang sebagian) harus menggagalkan. Probe hanya membaca (mode=ro) dan image
lama tanpa modul skema tidak memeriksa tabel tambahan itu.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import harga_kit
import schema_harga

AKAR = Path(__file__).resolve().parents[2]
SUMBER_MESIN = AKAR / "mesin"
PREFIKS = "import sqlite3\nfrom pathlib import Path\n"


def _deployer():
    spec = importlib.util.spec_from_file_location("deploy_harga_uji", AKAR / "scripts/deploy.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _db_admin(tmp_path, *, harga=False):
    return harga_kit.siapkan_db_harga(tmp_path) if harga else harga_kit.siapkan_db_admin_saja(tmp_path)


def _jalankan(tmp_path, sumber_app=SUMBER_MESIN):
    skrip = PREFIKS + _deployer().PROBE_HARGA_SKEMA.replace(
        "/app/", str(sumber_app) + "/").replace("/data/", str(tmp_path) + "/")
    return subprocess.run([sys.executable, "-E", "-B", "-"], input=skrip,
                          cwd=str(SUMBER_MESIN), capture_output=True, text=True,
                          timeout=20, check=False, shell=False)


def _sidik(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_probe_skema_utuh_memuat_blok_harga_sebelum_penanda_sukses():
    skrip = _deployer().PROBE_SKEMA
    assert "PROBE_HARGA_SKEMA" not in skrip  # sudah digabung, bukan nama variabel
    assert "schema_harga.validasi" in skrip
    assert skrip.index("schema_harga.validasi") < skrip.index("print('OSN_SCHEMA_ADMIN9_AI2_OK')")
    assert skrip.index("schema_jadwal.validasi") < skrip.index("schema_harga.validasi")
    assert "mode=ro" in skrip


def test_namespace_utuh_lulus_dan_db_tidak_berubah(tmp_path):
    path = _db_admin(tmp_path, harga=True)
    sebelum = _sidik(path)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    assert _sidik(path) == sebelum


def test_namespace_belum_ada_lulus_karena_preflight_sebelum_migrasi(tmp_path):
    path = _db_admin(tmp_path)
    sebelum = _sidik(path)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    assert _sidik(path) == sebelum


@pytest.mark.parametrize("nama", ["harga_riwayat_tolak_update", "harga_riwayat_tolak_delete", "harga_riwayat_tolak_replace"])
def test_trigger_hilang_menggagalkan_probe(tmp_path, nama):
    path = _db_admin(tmp_path, harga=True)
    with sqlite3.connect(path) as kon:
        kon.execute('DROP TRIGGER "%s"' % nama)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur harga tidak lengkap" in hasil.stderr


def test_kolom_berubah_menggagalkan_probe(tmp_path):
    path = _db_admin(tmp_path, harga=True)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE harga_produk ADD COLUMN bocor TEXT")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur harga tidak lengkap" in hasil.stderr


def test_tabel_harga_hilang_sebagian_menggagalkan_probe(tmp_path):
    path = _db_admin(tmp_path, harga=True)
    with sqlite3.connect(path) as kon:
        kon.execute("DROP TABLE harga_riwayat")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur harga tidak lengkap" in hasil.stderr


def test_image_lama_tanpa_modul_skema_tidak_memeriksa_tabel_tambahan(tmp_path):
    path = _db_admin(tmp_path, harga=True)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE harga_produk ADD COLUMN bocor TEXT")
    kosong = tmp_path / "app-lama"
    kosong.mkdir()
    assert _jalankan(tmp_path, kosong).returncode == 0


def test_probe_image_memasang_harga_dua_kali_sebelum_rekening(tmp_path):
    sumber = _deployer().PROBE_IMAGE
    urutan = [sumber.index("import " + m) for m in ("schema_pesanan", "schema_jadwal", "schema_harga", "pesanan_rekening")]
    assert urutan == sorted(urutan)
    potongan = sumber[sumber.index("import schema_harga"):sumber.index("import pesanan_rekening")]
    assert "except ImportError" in potongan  # image lama tanpa modul tetap dapat diprobe
    assert "assert not schema_harga.validasi(kon)" in potongan
    assert "for _ in range(2):" in potongan
    assert "assert schema_harga.validasi(kon)" in potongan
    assert "PRAGMA foreign_key_check" in potongan
    skrip = ("import sys\nsys.path.insert(0, " + repr(str(SUMBER_MESIN)) + ")\n"
             + sumber.replace("/data/", str(tmp_path) + "/"))
    hasil = subprocess.run([sys.executable, "-E", "-B", "-"], input=skrip, cwd=str(tmp_path),
                           capture_output=True, text=True, timeout=60, check=False, shell=False)
    assert hasil.returncode == 0, hasil.stderr
    import admin_store
    with admin_store.buka_baca(tmp_path / "admin-control.db") as kon:
        assert schema_harga.validasi(kon)
