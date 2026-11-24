"""Jalur rilis migrasi pesanan v1 + transfer_* + rekening: probe image, preview, rehearsal backup."""
import importlib.util
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

import admin_backup
import admin_store
import pesanan_rekening
import schema_pesanan
import schema_purna
import schema_transfer
from test_admin_backup import _buat_ai_v2, _buat_bundle

AKAR = Path(__file__).resolve().parents[2]
_SPEK = importlib.util.spec_from_file_location("deploy_wiring_uji", AKAR / "scripts" / "deploy.py")
deploy = importlib.util.module_from_spec(_SPEK)
_SPEK.loader.exec_module(deploy)


def _isi_bytes(bundle):
    return {p.name: p.read_bytes() for p in bundle.iterdir() if p.is_file()}


def _status_skema(path):
    with admin_store.buka_baca(path) as kon:
        return (schema_pesanan.validasi(kon), schema_transfer.validasi(kon),
                pesanan_rekening.validasi_schema(kon))


def _purna_terpasang(path):
    with admin_store.buka_baca(path) as kon:
        return schema_purna.validasi(kon)


# --- probe image ----------------------------------------------------------------

def test_probe_image_memasang_semua_skema_dua_kali_tanpa_data_nyata(tmp_path):
    script = ("import sys\nsys.path.insert(0, " + repr(str(AKAR / "mesin")) + ")\n" +
              deploy.PROBE_IMAGE.replace("/data/", str(tmp_path) + "/"))
    hasil = subprocess.run([sys.executable, "-E", "-B", "-"], input=script, cwd=tmp_path,
                           capture_output=True, text=True, timeout=60, check=False, shell=False)
    assert hasil.returncode == 0, hasil.stderr
    assert hasil.stdout.strip() == "OSN_IMAGE_ADMIN9_AI2_OK"
    assert _status_skema(tmp_path / "admin-control.db") == (True, True, True)
    assert _purna_terpasang(tmp_path / "admin-control.db") is True
    assert pesanan_rekening.baca(tmp_path / "admin-control.db") is None     # tanpa rekening bawaan


@pytest.mark.parametrize("modul", ["schema_pesanan", "schema_transfer", "schema_purna",
                                   "pesanan_rekening"])
def test_probe_image_mengimpor_modul_opsional_dengan_penjaga_importerror(modul):
    potongan = deploy.PROBE_IMAGE[deploy.PROBE_IMAGE.index("import " + modul):]
    assert potongan.splitlines()[1].strip().startswith("except ImportError")


def test_probe_image_purna_dipasang_setelah_transfer_dan_sebelum_rekening():
    urutan = [deploy.PROBE_IMAGE.index("import " + m)
              for m in ("schema_pesanan", "schema_transfer", "schema_purna", "pesanan_rekening")]
    assert urutan == sorted(urutan)
    potongan = deploy.PROBE_IMAGE[deploy.PROBE_IMAGE.index("import schema_purna"):
                                  deploy.PROBE_IMAGE.index("import pesanan_rekening")]
    assert "assert not schema_purna.validasi(kon)" in potongan
    assert "for _ in range(2):" in potongan
    assert "assert schema_purna.validasi(kon)" in potongan


# --- preview soft launch ------------------------------------------------------------

def test_preview_soft_launch_memasang_skema_pesanan_transfer_rekening(tmp_path, monkeypatch):
    import ai_store
    import assistant_schema
    import auth
    import database
    import launch_preview
    import research_store
    import sessions
    for modul, nama in ((admin_store, "BAWAAN"), (auth, "BERKAS_SANDI"), (database, "BAWAAN"),
                        (ai_store, "BAWAAN"), (assistant_schema, "BAWAAN"),
                        (research_store, "BAWAAN"), (sessions, "BERKAS_SESI")):
        monkeypatch.setattr(modul, nama, getattr(modul, nama))
    for env in ("ADMIN_TRANSIENT_DB", "AI_BERKAS_DB", "PENDAMPING_BERKAS_DB"):
        monkeypatch.setenv(env, "sementara")
    server, akar, _sandi = launch_preview.siapkan(akar=tmp_path / "preview")
    server.server_close()
    assert _status_skema(akar / "admin-control.db") == (True, True, True)
    assert pesanan_rekening.baca(akar / "admin-control.db") is None


# --- rehearsal backup ----------------------------------------------------------------

def test_validasi_bundle_baru_belum_memasang_skema_pesanan(tmp_path):
    hasil = admin_backup.validasi_bundle(_buat_bundle(tmp_path))
    assert hasil.skema_pesanan_transfer == (False, False, False, False)


def test_rehearsal_pesanan_transfer_rekening_opt_in_hanya_pada_turunan(tmp_path):
    bundle = _buat_bundle(tmp_path)
    sebelum = _isi_bytes(bundle)
    akhir = admin_backup.rehearsal_bundle(
        bundle, migrator_ai=_buat_ai_v2, target_pesanan=True, target_transfer=True,
        target_rekening=True)
    assert akhir.skema_pesanan_transfer == (True, True, True, False)
    assert _isi_bytes(bundle) == sebelum
    default = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)
    assert default.skema_pesanan_transfer == (False, False, False, False)


def test_rehearsal_sebagian_dan_transfer_menyeret_pesanan(tmp_path):
    bundle = _buat_bundle(tmp_path)
    hanya_rekening = admin_backup.rehearsal_bundle(
        bundle, migrator_ai=_buat_ai_v2, target_rekening=True)
    assert hanya_rekening.skema_pesanan_transfer == (False, False, True, False)
    transfer = admin_backup.rehearsal_bundle(
        bundle, migrator_ai=_buat_ai_v2, target_transfer=True)
    assert transfer.skema_pesanan_transfer == (True, True, False, False)


def test_rehearsal_menolak_target_tidak_sah(tmp_path):
    bundle = _buat_bundle(tmp_path)
    with pytest.raises(admin_backup.BackupTidakSah, match="pesanan"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_pesanan="ya")
    with pytest.raises(admin_backup.BackupTidakSah, match="pesanan"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_pesanan=False,
                                      target_transfer=True)


def test_bundle_yang_sudah_terpasang_divalidasi_dipertahankan_dan_tidak_boleh_turun(tmp_path):
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    schema_pesanan.migrasikan(admin)
    schema_transfer.migrasikan(admin)
    pesanan_rekening.migrasikan(admin, sekarang=101)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-pesanan", cutoff=101)
    assert admin_backup.validasi_bundle(bundle).skema_pesanan_transfer == (True, True, True, False)
    assert admin_backup.rehearsal_bundle(
        bundle, migrator_ai=_buat_ai_v2).skema_pesanan_transfer == (True, True, True, False)
    for turun in (dict(target_pesanan=False), dict(target_transfer=False),
                  dict(target_rekening=False)):
        with pytest.raises(admin_backup.BackupTidakSah):
            admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, **turun)


def test_bundle_dengan_transfer_parsial_ditolak_validator(tmp_path):
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    schema_pesanan.migrasikan(admin)
    schema_transfer.migrasikan(admin)
    with sqlite3.connect(admin) as kon:
        kon.execute("DROP TRIGGER transfer_refund_tolak_delete")
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-parsial", cutoff=102)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)


# --- purna_* pada backup/rehearsal ------------------------------------------------------

def _bundle_dengan(tmp_path, *, transfer=False, rekening=False, purna=False, cutoff=201):
    """Bundle sintetis yang adminnya sudah dipasang skema opsional (lewat migrator masing-masing)."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    if transfer or purna:
        schema_pesanan.migrasikan(admin)
        schema_transfer.migrasikan(admin)
    if rekening:
        pesanan_rekening.migrasikan(admin, sekarang=cutoff)
    if purna:
        schema_purna.migrasikan(admin)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-purna", cutoff=cutoff)
    return bundle


def _rusak_admin(bundle, sql):
    with sqlite3.connect(bundle / "admin-control.db") as kon:
        kon.execute("PRAGMA foreign_keys=OFF")
        kon.executescript(sql)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-rusak", cutoff=202)


def test_tentukan_target_purna_menyeret_transfer_dan_pesanan():
    import admin_backup_pesanan as abp
    assert abp.tentukan_target(abp.TIDAK_ADA, None, None, None, True) == (True, True, False, True)
    assert abp.tentukan_target((True, True, False, True), None, None, None) == (True, True, False, True)
    assert abp.tentukan_target(abp.TIDAK_ADA, None, None, None) == abp.TIDAK_ADA


def test_tentukan_target_menolak_purna_tanpa_transfer_atau_menurun():
    import admin_backup_pesanan as abp
    with pytest.raises(ValueError):
        abp.tentukan_target(abp.TIDAK_ADA, None, False, None, True)
    with pytest.raises(ValueError):
        abp.tentukan_target((True, True, False, True), None, None, None, False)
    with pytest.raises(ValueError):
        abp.tentukan_target(abp.TIDAK_ADA, None, None, None, "ya")


def test_bundle_berisi_purna_lolos_validasi_dan_rehearsal_tanpa_menulis_bundle(tmp_path):
    bundle = _bundle_dengan(tmp_path, purna=True, rekening=True)
    sebelum = _isi_bytes(bundle)
    assert admin_backup.validasi_bundle(bundle).skema_pesanan_transfer == (True, True, True, True)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)
    assert akhir.skema_pesanan_transfer == (True, True, True, True)
    assert _isi_bytes(bundle) == sebelum


def test_rehearsal_target_purna_hanya_pada_turunan(tmp_path):
    bundle = _bundle_dengan(tmp_path)
    sebelum = _isi_bytes(bundle)
    akhir = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_purna=True)
    assert akhir.skema_pesanan_transfer == (True, True, False, True)
    assert _isi_bytes(bundle) == sebelum
    assert _purna_terpasang(bundle / "admin-control.db") is False


def test_bundle_lama_tanpa_purna_tetap_lolos_dan_tidak_dipasangi_purna(tmp_path):
    lama = _bundle_dengan(tmp_path / "lama", transfer=True, rekening=True)
    hasil = admin_backup.rehearsal_bundle(lama, migrator_ai=_buat_ai_v2)
    assert hasil.skema_pesanan_transfer == (True, True, True, False)
    kosong = _bundle_dengan(tmp_path / "kosong")
    assert admin_backup.rehearsal_bundle(
        kosong, migrator_ai=_buat_ai_v2).skema_pesanan_transfer == (False, False, False, False)


def test_rehearsal_purna_tidak_boleh_turun_dan_menolak_transfer_dimatikan(tmp_path):
    bundle = _bundle_dengan(tmp_path / "a", purna=True)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2, target_purna=False)
    kosong = _bundle_dengan(tmp_path / "b")
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(kosong, migrator_ai=_buat_ai_v2, target_purna=True,
                                      target_transfer=False)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(kosong, migrator_ai=_buat_ai_v2, target_purna="ya")


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER purna_voucher_pakai_tolak_update",
    "DROP TRIGGER purna_laporan_terbit_lunas",
])
def test_bundle_dengan_purna_parsial_ditolak_validasi_dan_rehearsal(tmp_path, rusak):
    bundle = _bundle_dengan(tmp_path, purna=True)
    _rusak_admin(bundle, rusak)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)


def test_bundle_dengan_purna_tanpa_transfer_ditolak(tmp_path):
    bundle = _bundle_dengan(tmp_path)
    schema_pesanan.migrasikan(bundle / "admin-control.db")
    _rusak_admin(bundle, schema_purna.DDL)
    with pytest.raises(admin_backup.BackupTidakSah):
        admin_backup.validasi_bundle(bundle)
