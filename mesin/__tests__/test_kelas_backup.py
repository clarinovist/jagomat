"""Backup opt-in `kelas_*`: deteksi, migrasi hanya turunan, tidak boleh turun, parsial ditolak."""
import sqlite3

import pytest

import admin_backup
import schema_kelas
import schema_pesanan
import schema_purna
import schema_transfer
from test_admin_backup import _buat_ai_v2, _buat_bundle


def _bundle(tmp_path, *, kelas=False, purna=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    if purna or kelas:
        schema_pesanan.migrasikan(admin)
        schema_transfer.migrasikan(admin)
    if purna:
        schema_purna.migrasikan(admin)
    if kelas:
        schema_kelas.migrasikan(admin)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-kelas", cutoff=301)
    return bundle


def test_validasi_bundle_tanpa_kelas_false(tmp_path):
    assert admin_backup.validasi_bundle(_buat_bundle(tmp_path)).skema_kelas is False


def test_bundle_dengan_kelas_lolos_dan_rehearsal_mempertahankan(tmp_path):
    bundle = _bundle(tmp_path, kelas=True)
    assert admin_backup.validasi_bundle(bundle).skema_kelas is True
    assert admin_backup.rehearsal_bundle(
        bundle, migrator_ai=_buat_ai_v2).skema_kelas is True


def test_rehearsal_target_kelas_hanya_turunan_dan_menyeret_pesanan(tmp_path):
    bundle = _buat_bundle(tmp_path)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_kelas=True)
    assert akhir.skema_kelas is True and akhir.skema_pesanan_transfer[0] is True
    assert admin_backup.validasi_bundle(bundle).skema_kelas is False
    with pytest.raises(admin_backup.BackupTidakSah, match="kelas"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2,
                                      target_kelas=True, target_pesanan=False)


def test_rehearsal_kelas_tidak_boleh_turun_dan_target_salah(tmp_path):
    bundle = _bundle(tmp_path / "a", kelas=True)
    with pytest.raises(admin_backup.BackupTidakSah, match="kelas"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_kelas=False)
    kosong = _bundle(tmp_path / "b")
    with pytest.raises(admin_backup.BackupTidakSah, match="kelas"):
        admin_backup.rehearsal_bundle(kosong, migrator_ai=_buat_ai_v2, target_kelas="ya")


def test_bundle_kelas_parsial_ditolak_validasi_dan_rehearsal(tmp_path):
    bundle = _bundle(tmp_path, kelas=True)
    with sqlite3.connect(bundle / "admin-control.db") as kon:
        kon.execute("DROP TRIGGER kelas_akses_verifikasi")
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-kelas-rusak", cutoff=302)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)
