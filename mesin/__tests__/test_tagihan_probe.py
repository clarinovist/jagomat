"""Probe skema deploy untuk namespace tagihan_*: belum ada lulus, sudah ada harus persis DDL source.

Preflight berjalan SEBELUM migrasi, jadi tabel yang belum dibuat tidak boleh menggagalkannya; tabel yang sudah ada tetapi
menyimpang (trigger hilang, indeks hilang, kolom berubah, kelas_* rusak) harus menggagalkan. Probe hanya membaca
(mode=ro, query_only) dan image lama tanpa modul skema tidak memeriksa tabel tambahan itu.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import kelas_kit
import schema_tagihan_catatan as stc
import tagihan_kit

AKAR = Path(__file__).resolve().parents[2]
SUMBER_MESIN = AKAR / "mesin"
PREFIKS = "import sqlite3\nfrom pathlib import Path\n"


def _deployer():
    spec = importlib.util.spec_from_file_location("deploy_tagihan_uji", AKAR / "scripts/deploy.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _db_admin(tmp_path, *, tagihan=False):
    return tagihan_kit.siapkan_db_tagihan(tmp_path) if tagihan else kelas_kit.siapkan_db_kelas(tmp_path)


def _jalankan(tmp_path, sumber_app=SUMBER_MESIN):
    skrip = PREFIKS + _deployer().PROBE_TAGIHAN_SKEMA.replace(
        "/app/", str(sumber_app) + "/").replace("/data/", str(tmp_path) + "/")
    return subprocess.run([sys.executable, "-E", "-B", "-"], input=skrip,
                          cwd=str(SUMBER_MESIN), capture_output=True, text=True,
                          timeout=20, check=False, shell=False)


def _sidik(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_probe_skema_utuh_memuat_blok_tagihan_sebelum_penanda_sukses():
    skrip = _deployer().PROBE_SKEMA
    assert "PROBE_TAGIHAN_SKEMA" not in skrip  # sudah digabung, bukan nama variabel
    assert "schema_tagihan_catatan.validasi" in skrip
    assert skrip.index("schema_harga.validasi") < skrip.index("schema_tagihan_catatan.validasi")
    assert skrip.index("schema_tagihan_catatan.validasi") < skrip.index("print('OSN_SCHEMA_ADMIN9_AI2_OK')")


def test_blok_probe_tagihan_hanya_baca_mode_ro_dan_query_only():
    blok = _deployer().PROBE_TAGIHAN_SKEMA
    assert "mode=ro" in blok and "PRAGMA query_only=ON" in blok
    assert "GLOB 'tagihan_*'" in blok


def test_namespace_utuh_lulus_dan_db_tidak_berubah(tmp_path):
    path = _db_admin(tmp_path, tagihan=True)
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


@pytest.mark.parametrize("nama", [
    "tagihan_catatan_tolak_update", "tagihan_catatan_tolak_delete", "tagihan_catatan_tolak_replace",
    "tagihan_catatan_batal_bukti", "tagihan_catatan_pulih_jendela",
])
def test_trigger_hilang_menggagalkan_probe(tmp_path, nama):
    path = _db_admin(tmp_path, tagihan=True)
    with sqlite3.connect(path) as kon:
        kon.execute('DROP TRIGGER "%s"' % nama)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur tagihan tidak lengkap" in hasil.stderr


def test_indeks_hilang_menggagalkan_probe(tmp_path):
    path = _db_admin(tmp_path, tagihan=True)
    with sqlite3.connect(path) as kon:
        kon.execute("DROP INDEX idx_tagihan_catatan_order")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur tagihan tidak lengkap" in hasil.stderr


def test_kolom_berubah_menggagalkan_probe(tmp_path):
    path = _db_admin(tmp_path, tagihan=True)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE tagihan_catatan ADD COLUMN bocor TEXT")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur tagihan tidak lengkap" in hasil.stderr


def test_kelas_rusak_di_bawah_tagihan_menggagalkan_probe(tmp_path):
    path = _db_admin(tmp_path, tagihan=True)
    with sqlite3.connect(path) as kon:
        kon.execute("DROP TRIGGER kelas_akses_verifikasi")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur kelas tidak lengkap" in hasil.stderr


def test_image_lama_tanpa_modul_skema_tidak_memeriksa_tabel_tambahan(tmp_path):
    path = _db_admin(tmp_path, tagihan=True)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE tagihan_catatan ADD COLUMN bocor TEXT")
    kosong = tmp_path / "app-lama"
    kosong.mkdir()
    assert _jalankan(tmp_path, kosong).returncode == 0


def test_probe_image_memasang_tagihan_dua_kali_setelah_kelas_dan_harga(tmp_path):
    sumber = _deployer().PROBE_IMAGE
    urutan = [sumber.index("import " + m) for m in
              ("schema_kelas", "schema_harga", "schema_tagihan_catatan", "pesanan_rekening")]
    assert urutan == sorted(urutan)
    potongan = sumber[sumber.index("import schema_tagihan_catatan"):sumber.index("import pesanan_rekening")]
    assert "except ImportError" in potongan  # image lama tanpa modul tetap dapat diprobe
    assert "assert not schema_tagihan_catatan.validasi(kon)" in potongan
    assert "for _ in range(2):" in potongan
    assert "assert schema_tagihan_catatan.validasi(kon)" in potongan
    assert "PRAGMA foreign_key_check" in potongan
    skrip = ("import sys\nsys.path.insert(0, " + repr(str(SUMBER_MESIN)) + ")\n"
             + sumber.replace("/data/", str(tmp_path) + "/"))
    hasil = subprocess.run([sys.executable, "-E", "-B", "-"], input=skrip, cwd=str(tmp_path),
                           capture_output=True, text=True, timeout=60, check=False, shell=False)
    assert hasil.returncode == 0, hasil.stderr
    import admin_store
    with admin_store.buka_baca(tmp_path / "admin-control.db") as kon:
        assert stc.validasi(kon)
