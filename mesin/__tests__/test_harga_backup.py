"""Backup opt-in `harga_*`: deteksi, migrasi hanya turunan, tidak boleh turun, parsial ditolak.

Juga bukti bahwa DB admin yang sudah memuat `harga_*` (dengan data) lolos validasi bundle, rehearsal, dan backup operasional, dan
validator backup image lama (belum mengenal harga) tidak menolaknya.
"""
import importlib.util
import os
import sqlite3
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

import admin_backup
import harga
import schema_harga
from test_admin_backup import _buat_ai_v2, _buat_bundle
from test_operational_backup import sumber  # noqa: F401  (fixture bersama)
from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
PIN_LAMA = ("85bbd528264b221148d522d958bcb31bb66ce907", "37307ed58f93d766f90225d1075169b1b91b867e")
SKRIP = AKAR / "scripts" / "operational_backup.py"
_spek = importlib.util.spec_from_file_location("operational_backup_harga_uji", SKRIP)
operasional = importlib.util.module_from_spec(_spek)
_spek.loader.exec_module(operasional)


def _bundle(tmp_path, *, harga_terpasang=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bundle = _buat_bundle(tmp_path)
    if harga_terpasang:
        schema_harga.migrasikan(bundle / "admin-control.db")
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-harga", cutoff=401)
    return bundle


def _isi_harga(admin):
    harga.ubah_harga(admin, "private", 700000, 640000, "admin_sintetis", "2026-11-25T08:00:00")


def test_validasi_bundle_tanpa_harga_false(tmp_path):
    assert admin_backup.validasi_bundle(_buat_bundle(tmp_path)).skema_harga is False


def test_bundle_dengan_harga_lolos_dan_rehearsal_mempertahankan(tmp_path):
    bundle = _bundle(tmp_path, harga_terpasang=True)
    assert admin_backup.validasi_bundle(bundle).skema_harga is True
    assert admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2).skema_harga is True


def test_bundle_harga_berisi_data_lolos_validasi_dan_rehearsal(tmp_path):
    bundle = _bundle(tmp_path, harga_terpasang=True)
    admin = bundle / "admin-control.db"
    _isi_harga(admin)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-harga-isi", cutoff=403)
    assert admin_backup.validasi_bundle(bundle).skema_harga is True
    assert admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2).skema_harga is True
    with sqlite3.connect(admin) as kon:
        assert kon.execute("SELECT rupiah FROM harga_produk WHERE kode='private'").fetchone()[0] == 700000
        assert kon.execute("SELECT COUNT(*) FROM harga_riwayat").fetchone()[0] == 1


def test_rehearsal_target_harga_hanya_turunan_tanpa_menyeret_ledger_lain(tmp_path):
    bundle = _buat_bundle(tmp_path)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_harga=True)
    assert akhir.skema_harga is True and akhir.skema_kelas is False and akhir.skema_jadwal is False
    assert admin_backup.validasi_bundle(bundle).skema_harga is False


def test_rehearsal_harga_tidak_boleh_turun_dan_target_salah(tmp_path):
    bundle = _bundle(tmp_path / "a", harga_terpasang=True)
    with pytest.raises(admin_backup.BackupTidakSah, match="harga"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_harga=False)
    kosong = _bundle(tmp_path / "b")
    with pytest.raises(admin_backup.BackupTidakSah, match="harga"):
        admin_backup.rehearsal_bundle(kosong, migrator_ai=_buat_ai_v2, target_harga="ya")


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER harga_riwayat_tolak_update",
    "DROP TABLE harga_riwayat",
    "ALTER TABLE harga_produk ADD COLUMN bocor TEXT",
])
def test_bundle_harga_parsial_ditolak_validasi_dan_rehearsal(tmp_path, rusak):
    bundle = _bundle(tmp_path, harga_terpasang=True)
    with sqlite3.connect(bundle / "admin-control.db") as kon:
        kon.execute(rusak)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-harga-rusak", cutoff=402)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)


def test_backup_operasional_menerima_db_admin_ber_harga(sumber, tmp_path):  # noqa: F811
    admin = sumber / "admin-control.db"
    schema_harga.migrasikan(admin)
    _isi_harga(admin)
    target = tmp_path / "backup-harga"
    hasil = operasional.capture(sumber, target, "a" * 40, "sha256:" + "b" * 64, lambda: None)
    assert hasil["ok"]
    assert operasional.validate(target)["ok"]
    with sqlite3.connect(target / "bundle" / "admin-control.db") as kon:
        assert kon.execute("SELECT COUNT(*) FROM harga_riwayat").fetchone()[0] == 1


@pytest.mark.parametrize("revisi", PIN_LAMA)
def test_validator_backup_lama_tidak_menolak_bundle_ber_harga(tmp_path, revisi):
    """Rollback/tool host lama: `admin_backup` tanpa kesadaran harga tetap meloloskan bundle berisi `harga_*`."""
    bundle = _bundle(tmp_path / "bundle-baru", harga_terpasang=True)
    _isi_harga(bundle / "admin-control.db")
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-harga-lama", cutoff=404)
    arsip = tmp_path / "lama.tar"
    with arsip.open("wb") as keluar:
        subprocess.run(["git", "-C", str(AKAR), "archive", revisi, "mesin"], stdout=keluar, check=True)
    lama = tmp_path / "lama"
    lama.mkdir()
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, lama)
    kode = ("import admin_backup, sys\n"
            "r = admin_backup.validasi_bundle(sys.argv[1])\n"
            "print('LAMA_OK', r.versi_admin)\n")
    hasil = subprocess.run([sys.executable, "-B", "-c", kode, str(bundle)], capture_output=True, text=True,
                           env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(lama / "mesin"),
                                "PYTHONDONTWRITEBYTECODE": "1"}, timeout=60)
    assert hasil.returncode == 0, hasil.stderr
    assert hasil.stdout.split()[0] == "LAMA_OK"
