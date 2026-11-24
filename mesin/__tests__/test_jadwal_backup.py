"""Backup opt-in `jadwal_*`: deteksi, migrasi hanya turunan, tidak boleh turun, parsial ditolak.

Juga bukti bahwa DB admin yang sudah memuat `jadwal_*` (dengan data) lolos validasi bundle, rehearsal, dan
backup operasional: tidak ada validator yang menolak tabel/trigger `jadwal_*`.
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
import jadwal_store
import kelas_kit
import schema_jadwal
import schema_kelas
import schema_pesanan
import schema_transfer
from test_admin_backup import _buat_ai_v2, _buat_bundle
from test_operational_backup import sumber  # noqa: F401  (fixture bersama)
from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
# Pohon lama yang validator backup-nya belum mengenal `kelas_*`/`jadwal_*` (admin_backup recovery tidak diubah lapisan data).
PIN_LAMA = ("85bbd528264b221148d522d958bcb31bb66ce907", "6142611adbc79a2a659e9adb764211856494f2ce")
SKRIP = Path(__file__).resolve().parents[2] / "scripts" / "operational_backup.py"
_spek = importlib.util.spec_from_file_location("operational_backup_jadwal_uji", SKRIP)
operasional = importlib.util.module_from_spec(_spek)
_spek.loader.exec_module(operasional)


def _bundle(tmp_path, *, kelas=False, jadwal=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    if kelas or jadwal:
        schema_pesanan.migrasikan(admin)
        schema_transfer.migrasikan(admin)
        import schema_purna
        schema_purna.migrasikan(admin)
        schema_kelas.migrasikan(admin)
    if jadwal:
        schema_jadwal.migrasikan(admin)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-jadwal", cutoff=301)
    return bundle


def _isi_jadwal(admin):
    """Satu kelompok + satu penempatan Mini nyata-sintetis di DB admin."""
    with jadwal_store.buka(admin, tulis_data=True) as kon:
        kid = jadwal_store.buat_kelompok(
            kon, "admin_sintetis", nama="Mini A", lokasi="Ruang 1", guru_id="akun_" + "9" * 32,
            kuota=3, tanggal="2026-11-21", jam="09:00", sekarang=kelas_kit.KINI)
        tagihan = kelas_kit.lunas(kon, 1, "mini")
        jadwal_store.tempatkan(kon, "admin_sintetis", tagihan.order_id, kelompok_id=kid,
                               sekarang=kelas_kit.SESUDAH_UPLOAD)


def test_validasi_bundle_tanpa_jadwal_false(tmp_path):
    ringkasan = admin_backup.validasi_bundle(_buat_bundle(tmp_path))
    assert ringkasan.skema_jadwal is False and ringkasan.skema_kelas is False


def test_bundle_dengan_jadwal_lolos_dan_rehearsal_mempertahankan(tmp_path):
    bundle = _bundle(tmp_path, jadwal=True)
    ringkasan = admin_backup.validasi_bundle(bundle)
    assert ringkasan.skema_jadwal is True and ringkasan.skema_kelas is True
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)
    assert akhir.skema_jadwal is True and akhir.skema_kelas is True


def test_bundle_kelas_tanpa_jadwal_tetap_false_dan_rehearsal_mempertahankan(tmp_path):
    bundle = _bundle(tmp_path, kelas=True)
    assert admin_backup.validasi_bundle(bundle).skema_jadwal is False
    assert admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2).skema_jadwal is False


def test_bundle_jadwal_berisi_data_lolos_validasi_dan_rehearsal(tmp_path):
    bundle = _bundle(tmp_path, jadwal=True)
    admin = bundle / "admin-control.db"
    _isi_jadwal(admin)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-jadwal-isi", cutoff=303)
    assert admin_backup.validasi_bundle(bundle).skema_jadwal is True
    assert admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2).skema_jadwal is True
    with sqlite3.connect(admin) as kon:
        assert kon.execute("SELECT COUNT(*) FROM jadwal_penempatan").fetchone()[0] == 1
        assert kon.execute("SELECT COUNT(*) FROM jadwal_pertemuan").fetchone()[0] == 8


def test_rehearsal_target_jadwal_hanya_turunan_dan_menyeret_kelas_dan_pesanan(tmp_path):
    bundle = _buat_bundle(tmp_path)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_jadwal=True)
    assert akhir.skema_jadwal is True and akhir.skema_kelas is True
    assert akhir.skema_pesanan_transfer[0] is True
    sebelum = admin_backup.validasi_bundle(bundle)
    assert sebelum.skema_jadwal is False and sebelum.skema_kelas is False


def test_rehearsal_target_jadwal_di_atas_kelas_yang_ada(tmp_path):
    bundle = _bundle(tmp_path, kelas=True)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_jadwal=True)
    assert akhir.skema_jadwal is True
    assert admin_backup.validasi_bundle(bundle).skema_jadwal is False


def test_rehearsal_jadwal_tanpa_kelas_eksplisit_ditolak(tmp_path):
    bundle = _buat_bundle(tmp_path)
    with pytest.raises(admin_backup.BackupTidakSah, match="jadwal"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2,
                                      target_jadwal=True, target_kelas=False)


def test_rehearsal_jadwal_tidak_boleh_turun_dan_target_salah(tmp_path):
    bundle = _bundle(tmp_path / "a", jadwal=True)
    with pytest.raises(admin_backup.BackupTidakSah, match="jadwal"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_jadwal=False)
    kosong = _bundle(tmp_path / "b")
    with pytest.raises(admin_backup.BackupTidakSah, match="jadwal"):
        admin_backup.rehearsal_bundle(kosong, migrator_ai=_buat_ai_v2, target_jadwal="ya")


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER jadwal_penempatan_kuota",
    "DROP TABLE jadwal_pertemuan",
    "ALTER TABLE jadwal_kelompok ADD COLUMN bocor TEXT",
])
def test_bundle_jadwal_parsial_ditolak_validasi_dan_rehearsal(tmp_path, rusak):
    bundle = _bundle(tmp_path, jadwal=True)
    with sqlite3.connect(bundle / "admin-control.db") as kon:
        kon.execute(rusak)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-jadwal-rusak", cutoff=302)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)


def test_backup_operasional_menerima_db_admin_ber_jadwal(sumber, tmp_path):  # noqa: F811
    admin = sumber / "admin-control.db"
    import schema_purna
    schema_pesanan.migrasikan(admin)
    schema_transfer.migrasikan(admin)
    schema_purna.migrasikan(admin)
    schema_kelas.migrasikan(admin)
    schema_jadwal.migrasikan(admin)
    _isi_jadwal(admin)
    target = tmp_path / "backup-jadwal"
    hasil = operasional.capture(sumber, target, "a" * 40, "sha256:" + "b" * 64, lambda: None)
    assert hasil["ok"]
    assert operasional.validate(target)["ok"]
    with sqlite3.connect(target / "bundle" / "admin-control.db") as kon:
        assert kon.execute("SELECT COUNT(*) FROM jadwal_pertemuan").fetchone()[0] == 8


@pytest.mark.parametrize("revisi", PIN_LAMA)
def test_validator_backup_lama_tidak_menolak_bundle_ber_jadwal(tmp_path, revisi):
    """Rollback/tool host lama: `admin_backup` tanpa kesadaran jadwal tetap meloloskan bundle berisi `jadwal_*`."""
    bundle = _bundle(tmp_path / "bundle-baru", jadwal=True)
    _isi_jadwal(bundle / "admin-control.db")
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-jadwal-lama", cutoff=304)
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
