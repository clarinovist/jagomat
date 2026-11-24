"""Probe skema deploy untuk namespace kelas_*: belum ada lulus, sudah ada harus persis DDL source.

Preflight berjalan SEBELUM migrasi, jadi tabel yang belum dibuat tidak boleh menggagalkannya; tabel
yang sudah ada tetapi menyimpang (trigger hilang, kolom berubah) harus menggagalkan. Probe hanya
membaca (mode=ro) dan image lama tanpa modul skema tidak memeriksa tabel tambahan itu.
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
PREFIKS = "import sqlite3\nfrom pathlib import Path\n"


def _deployer():
    spec = importlib.util.spec_from_file_location("deploy_kelas_uji", AKAR / "scripts/deploy.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _db_admin(tmp_path, *, kelas=False):
    import admin_store
    import schema_pesanan
    import schema_kelas

    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    schema_pesanan.migrasikan(path)
    if kelas:
        schema_kelas.migrasikan(path)
    return path


def _jalankan(tmp_path, sumber_app=SUMBER_MESIN):
    skrip = PREFIKS + _deployer().PROBE_KELAS_SKEMA.replace(
        "/app/", str(sumber_app) + "/").replace("/data/", str(tmp_path) + "/")
    return subprocess.run([sys.executable, "-E", "-B", "-"], input=skrip,
                          cwd=str(SUMBER_MESIN), capture_output=True, text=True,
                          timeout=20, check=False, shell=False)


def _sidik(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_probe_skema_utuh_memuat_blok_kelas_sebelum_penanda_sukses():
    skrip = _deployer().PROBE_SKEMA
    assert "PROBE_KELAS_SKEMA" not in skrip  # sudah digabung, bukan nama variabel
    assert "schema_kelas.validasi" in skrip
    assert skrip.index("schema_kelas.validasi") < skrip.index("print('OSN_SCHEMA_ADMIN9_AI2_OK')")
    assert "mode=ro" in skrip


def test_namespace_utuh_lulus_dan_db_tidak_berubah(tmp_path):
    path = _db_admin(tmp_path, kelas=True)
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
    "kelas_order_satu_terbuka", "kelas_bukti_sha_baru", "kelas_akses_verifikasi",
    "kelas_order_tolak_update",
])
def test_trigger_hilang_menggagalkan_probe(tmp_path, nama):
    path = _db_admin(tmp_path, kelas=True)
    with sqlite3.connect(path) as kon:
        kon.execute('DROP TRIGGER "%s"' % nama)
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur kelas tidak lengkap" in hasil.stderr


def test_kolom_berubah_menggagalkan_probe(tmp_path):
    path = _db_admin(tmp_path, kelas=True)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE kelas_order ADD COLUMN bocor TEXT")
    hasil = _jalankan(tmp_path)
    assert hasil.returncode == 1 and "struktur kelas tidak lengkap" in hasil.stderr


def test_image_lama_tanpa_modul_skema_tidak_memeriksa_tabel_tambahan(tmp_path):
    path = _db_admin(tmp_path, kelas=True)
    with sqlite3.connect(path) as kon:
        kon.execute("ALTER TABLE kelas_order ADD COLUMN bocor TEXT")
    kosong = tmp_path / "app-lama"
    kosong.mkdir()
    assert _jalankan(tmp_path, kosong).returncode == 0


def test_probe_image_memasang_kelas_dua_kali_setelah_purna(tmp_path):
    sumber = _deployer().PROBE_IMAGE
    urutan = [sumber.index("import " + m) for m in
              ("schema_pesanan", "schema_transfer", "schema_purna", "schema_kelas",
               "pesanan_rekening")]
    assert urutan == sorted(urutan)
    potongan = sumber[sumber.index("import schema_kelas"):
                      sumber.index("import pesanan_rekening")]
    assert "assert not schema_kelas.validasi(kon)" in potongan
    assert "for _ in range(2):" in potongan
    assert "assert schema_kelas.validasi(kon)" in potongan
    skrip = ("import sys\nsys.path.insert(0, " + repr(str(SUMBER_MESIN)) + ")\n"
             + sumber.replace("/data/", str(tmp_path) + "/"))
    hasil = subprocess.run([sys.executable, "-E", "-B", "-"], input=skrip, cwd=str(tmp_path),
                           capture_output=True, text=True, timeout=60, check=False, shell=False)
    assert hasil.returncode == 0, hasil.stderr
    import admin_store
    import schema_kelas
    with admin_store.buka_baca(tmp_path / "admin-control.db") as kon:
        assert schema_kelas.validasi(kon)
