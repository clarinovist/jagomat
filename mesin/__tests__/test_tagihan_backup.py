"""Backup opt-in `tagihan_*`: deteksi, migrasi hanya turunan, tidak boleh turun, parsial ditolak.

Tagihan berdiri di atas kelas: prasyarat kelas dicek di deteksi dan rehearsal (sama seperti jadwal). Juga bukti bahwa DB
admin yang sudah memuat catatan batal `tagihan_*` lolos validasi bundle, rehearsal, dan backup operasional, dan validator
backup image lama (belum mengenal tagihan) tidak menolaknya.
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
import admin_backup_pesanan
import kelas_batal
import kelas_kit
import kelas_store
import schema_kelas
import schema_pesanan
import schema_purna
import schema_tagihan_catatan as stc
import schema_transfer
from test_admin_backup import _buat_ai_v2, _buat_bundle
from test_operational_backup import sumber  # noqa: F401  (fixture bersama)
from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
# Pohon lama yang validator backup-nya belum mengenal `kelas_*`/`tagihan_*` (sama seperti pin uji jadwal).
PIN_LAMA = ("85bbd528264b221148d522d958bcb31bb66ce907", "6142611adbc79a2a659e9adb764211856494f2ce")
SKRIP = AKAR / "scripts" / "operational_backup.py"
_spek = importlib.util.spec_from_file_location("operational_backup_tagihan_uji", SKRIP)
operasional = importlib.util.module_from_spec(_spek)
_spek.loader.exec_module(operasional)


def _bundle(tmp_path, *, kelas=False, tagihan=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    if kelas or tagihan:
        _pasang_kelas(admin)
    if tagihan:
        stc.migrasikan(admin)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-tagihan", cutoff=501)
    return bundle


def _pasang_kelas(admin):
    schema_pesanan.migrasikan(admin)
    schema_transfer.migrasikan(admin)
    schema_purna.migrasikan(admin)
    schema_kelas.migrasikan(admin)


def _isi_catatan_batal(admin):
    """Satu tagihan sintetis yang lalu dibatalkan (satu baris `tagihan_catatan`)."""
    with kelas_store.buka(admin, tulis_data=True) as kon:
        kelas_kit.tagih(kon, siswa=1, paket="mini")
        kelas_batal.batalkan_tagihan(kon, kelas_kit.AKUN_A, 1, "mini", kelas_kit.KINI)


def _ulang_manifest(bundle, bundle_id, cutoff):
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id=bundle_id, cutoff=cutoff)


def test_validasi_bundle_tanpa_tagihan_false(tmp_path):
    assert admin_backup.validasi_bundle(_buat_bundle(tmp_path)).skema_tagihan is False


def test_bundle_dengan_tagihan_lolos_dan_rehearsal_mempertahankan(tmp_path):
    bundle = _bundle(tmp_path, tagihan=True)
    ringkasan = admin_backup.validasi_bundle(bundle)
    assert ringkasan.skema_tagihan is True and ringkasan.skema_kelas is True
    assert admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2).skema_tagihan is True


def test_bundle_kelas_tanpa_tagihan_tetap_false_dan_rehearsal_mempertahankan(tmp_path):
    bundle = _bundle(tmp_path, kelas=True)
    assert admin_backup.validasi_bundle(bundle).skema_tagihan is False
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)
    assert akhir.skema_tagihan is False and akhir.skema_kelas is True


def test_bundle_tagihan_berisi_catatan_batal_lolos_validasi_dan_rehearsal(tmp_path):
    bundle = _bundle(tmp_path, tagihan=True)
    _isi_catatan_batal(bundle / "admin-control.db")
    _ulang_manifest(bundle, "backup-sintetis-tagihan-isi", 502)
    assert admin_backup.validasi_bundle(bundle).skema_tagihan is True
    assert admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2).skema_tagihan is True
    with sqlite3.connect(bundle / "admin-control.db") as kon:
        assert kon.execute("SELECT aksi FROM tagihan_catatan ORDER BY id").fetchall() == [("batal",)]


def test_rehearsal_target_tagihan_hanya_turunan_dan_menyeret_kelas_dan_pesanan(tmp_path):
    bundle = _buat_bundle(tmp_path)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_tagihan=True)
    assert akhir.skema_tagihan is True and akhir.skema_kelas is True
    assert akhir.skema_pesanan_transfer[0] is True
    sebelum = admin_backup.validasi_bundle(bundle)
    assert sebelum.skema_tagihan is False and sebelum.skema_kelas is False


def test_rehearsal_target_tagihan_di_atas_kelas_yang_ada(tmp_path):
    bundle = _bundle(tmp_path, kelas=True)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_tagihan=True)
    assert akhir.skema_tagihan is True
    assert admin_backup.validasi_bundle(bundle).skema_tagihan is False


def test_rehearsal_tagihan_tanpa_kelas_eksplisit_ditolak(tmp_path):
    bundle = _buat_bundle(tmp_path)
    with pytest.raises(admin_backup.BackupTidakSah, match="tagihan"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2,
                                      target_tagihan=True, target_kelas=False)


def test_rehearsal_tagihan_tidak_boleh_turun_dan_target_salah(tmp_path):
    bundle = _bundle(tmp_path / "a", tagihan=True)
    with pytest.raises(admin_backup.BackupTidakSah, match="tagihan"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_tagihan=False)
    kosong = _bundle(tmp_path / "b")
    with pytest.raises(admin_backup.BackupTidakSah, match="tagihan"):
        admin_backup.rehearsal_bundle(kosong, migrator_ai=_buat_ai_v2, target_tagihan="ya")


@pytest.mark.parametrize("rusak", [
    "DROP INDEX idx_tagihan_catatan_order",
    "DROP TRIGGER tagihan_catatan_tolak_update",
    "ALTER TABLE tagihan_catatan ADD COLUMN bocor TEXT",
])
def test_bundle_tagihan_parsial_ditolak_validasi_dan_rehearsal(tmp_path, rusak):
    bundle = _bundle(tmp_path, tagihan=True)
    with sqlite3.connect(bundle / "admin-control.db") as kon:
        kon.execute(rusak)
    _ulang_manifest(bundle, "backup-sintetis-tagihan-rusak", 503)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)


def test_deteksi_tagihan_tanpa_kelas_ditolak(tmp_path):
    """Tabel catatan yang ada tanpa `kelas_*` tidak sah: prasyarat kelas dicek (sama seperti deteksi_jadwal)."""
    path = tmp_path / "tanpa-kelas.db"
    with sqlite3.connect(path) as kon:
        kon.executescript(stc.DDL)
        with pytest.raises(ValueError, match="kelas"):
            admin_backup_pesanan.deteksi_tagihan(kon)


def test_deteksi_dan_migrasi_tagihan_di_atas_kelas(tmp_path):
    path = kelas_kit.siapkan_db_kelas(tmp_path)
    with sqlite3.connect(path) as kon:
        assert admin_backup_pesanan.deteksi_tagihan(kon) is False
    admin_backup_pesanan.migrasikan_tagihan(path)
    with sqlite3.connect(path) as kon:
        assert admin_backup_pesanan.deteksi_tagihan(kon) is True


def test_backup_operasional_menerima_db_admin_ber_tagihan(sumber, tmp_path):  # noqa: F811
    admin = sumber / "admin-control.db"
    _pasang_kelas(admin)
    stc.migrasikan(admin)
    _isi_catatan_batal(admin)
    target = tmp_path / "backup-tagihan"
    hasil = operasional.capture(sumber, target, "a" * 40, "sha256:" + "b" * 64, lambda: None)
    assert hasil["ok"]
    assert operasional.validate(target)["ok"]
    with sqlite3.connect(target / "bundle" / "admin-control.db") as kon:
        assert kon.execute("SELECT COUNT(*) FROM tagihan_catatan").fetchone()[0] == 1


@pytest.mark.parametrize("revisi", PIN_LAMA)
def test_validator_backup_lama_tidak_menolak_bundle_ber_tagihan(tmp_path, revisi):
    """Rollback/tool host lama: `admin_backup` tanpa kesadaran tagihan tetap meloloskan bundle berisi `tagihan_*`."""
    bundle = _bundle(tmp_path / "bundle-baru", tagihan=True)
    _isi_catatan_batal(bundle / "admin-control.db")
    _ulang_manifest(bundle, "backup-sintetis-tagihan-lama", 504)
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
