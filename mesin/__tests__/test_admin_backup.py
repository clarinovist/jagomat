"""Validator dan rehearsal backup admin-control memakai data sintetis saja."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import stat

import pytest

import admin_backup
import ai_store
import admin_bulk
import admin_store
import admin_students
import assistant_schema
import auth
import database


ACTOR = "akun_" + "a" * 32
OWNER = "akun_" + "b" * 32


def _buat_ai_v2(path):
    """Migrator AI2 sintetis untuk menguji kontrak callback helper F."""
    import ai_store

    with ai_store.buka(path) as kon:
        versi = int(kon.execute("PRAGMA user_version").fetchone()[0])
        if versi > 2:
            raise RuntimeError("skema pengaturan AI lebih baru dari candidate")
        kon.execute(
            """CREATE TABLE IF NOT EXISTS audit_uji_admin (
                operasi_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL,
                status TEXT NOT NULL, dibuat INTEGER NOT NULL, selesai INTEGER
            )"""
        )
        kon.execute(
            """CREATE TABLE IF NOT EXISTS operasi_pengaturan_admin (
                operasi_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL,
                sidik TEXT NOT NULL, revisi_awal INTEGER NOT NULL,
                revisi_hasil INTEGER NOT NULL UNIQUE, dibuat INTEGER NOT NULL
            )"""
        )
        kon.execute("PRAGMA user_version=2")


def _buat_bundle(tmp_path, *, ai_v2=False):
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    belajar = bundle / "latihan.db"
    admin = bundle / "admin-control.db"
    ai = bundle / "ai-control.db"
    pendamping = bundle / "pendamping.db"
    akun = bundle / "sandi.json"
    database.siapkan(belajar)
    admin_students.siapkan(belajar)
    admin_store.siapkan(admin, sekarang=1)
    if ai_v2:
        _buat_ai_v2(ai)
    else:
        import ai_store
        ai_store.siapkan(ai, sekarang=1)
    assistant_schema.siapkan(pendamping)
    akun.write_text(json.dumps({"akun": [
        {"pengguna": "pengelola", "peran": "admin", "id_akun": ACTOR,
         "revisi_auth": 3, **auth.buat_hash("admin-sintetis")},
        {"pengguna": "keluarga", "peran": "guru", "id_akun": OWNER,
         "revisi_auth": 1, **auth.buat_hash("guru-sintetis")},
    ]}), encoding="utf-8")
    for path in (belajar, admin, ai, pendamping, akun):
        path.chmod(0o600)
    admin_backup.buat_manifest(bundle, bundle_id="backup-sintetis-001", cutoff=100)
    return bundle


def test_manifest_dan_validator_bundle_sintetis(tmp_path):
    bundle = _buat_bundle(tmp_path)
    hasil = admin_backup.validasi_bundle(
        bundle, bundle_id="backup-sintetis-001"
    )
    assert hasil.bundle_id == "backup-sintetis-001"
    assert hasil.berkas == ("belajar", "auth", "admin", "ai", "pendamping")
    assert hasil.versi_admin == admin_store.VERSI_SKEMA
    assert hasil.versi_ai == ai_store.VERSI_SKEMA
    assert hasil.versi_pendamping == 4
    assert (hasil.revisi_auth_min, hasil.revisi_auth_max) == (1, 3)
    assert (hasil.operasi_admin_pending, hasil.operasi_admin_uncertain) == (0, 0)
    manifest = json.loads((bundle / "manifest.json").read_text())
    dump = json.dumps(manifest)
    assert "pengelola" not in dump and "keluarga" not in dump
    assert "kunci" not in dump and "garam" not in dump
    assert manifest["sessions_included"] is False
    assert manifest["transient_included"] is False
    assert stat.S_IMODE((bundle / "manifest.json").stat().st_mode) == 0o600


def test_validator_tolak_hash_berubah_dan_tidak_memperbaiki_backup(tmp_path):
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    sebelum_manifest = (bundle / "manifest.json").read_bytes()
    rusak = bytearray(admin.read_bytes())
    rusak[-1] ^= 1
    admin.write_bytes(bytes(rusak))
    sebelum_admin = admin.read_bytes()

    with pytest.raises(admin_backup.BackupTidakSah, match="hash/ukuran"):
        admin_backup.validasi_bundle(bundle)

    assert admin.read_bytes() == sebelum_admin
    assert (bundle / "manifest.json").read_bytes() == sebelum_manifest


@pytest.mark.parametrize("nama", ["sesi.json", "admin-drafts.db"])
def test_manifest_dan_validator_tolak_state_session_transient(tmp_path, nama):
    bundle = _buat_bundle(tmp_path)
    (bundle / nama).write_text("{}", encoding="utf-8")
    (bundle / nama).chmod(0o600)
    with pytest.raises(admin_backup.BackupTidakSah, match="transient/sesi"):
        admin_backup.validasi_bundle(bundle)

    (bundle / "manifest.json").unlink()
    with pytest.raises(admin_backup.BackupTidakSah, match="transient/sesi"):
        admin_backup.buat_manifest(
            bundle, bundle_id="backup-sintetis-002", cutoff=101
        )


def test_validator_tolak_file_asing_dalam_bundle(tmp_path):
    bundle = _buat_bundle(tmp_path)
    asing = bundle / "catatan.txt"
    asing.write_text("bukan bagian bundle", encoding="utf-8")
    asing.chmod(0o600)
    with pytest.raises(admin_backup.BackupTidakSah, match="inventaris"):
        admin_backup.validasi_bundle(bundle)


def test_validator_tolak_metadata_auth_hash_cacat(tmp_path):
    bundle = _buat_bundle(tmp_path)
    akun = bundle / "sandi.json"
    data = json.loads(akun.read_text(encoding="utf-8"))
    data["akun"][0]["kunci"] = "bukan-hex"
    akun.write_text(json.dumps(data), encoding="utf-8")
    akun.chmod(0o600)
    (bundle / "manifest.json").unlink()
    admin_backup.buat_manifest(
        bundle, bundle_id="backup-sintetis-auth-cacat", cutoff=103
    )
    with pytest.raises(admin_backup.BackupTidakSah, match="auth backup"):
        admin_backup.validasi_bundle(bundle)


def test_validator_tolak_symlink_hardlink_dan_izin_longgar(tmp_path):
    bundle = _buat_bundle(tmp_path)
    admin = bundle / "admin-control.db"
    admin.chmod(0o644)
    with pytest.raises(admin_backup.BackupTidakSah, match="izin"):
        admin_backup.validasi_bundle(bundle)
    admin.chmod(0o600)
    bundle.chmod(0o755)
    with pytest.raises(admin_backup.BackupTidakSah, match="izin"):
        admin_backup.validasi_bundle(bundle)
    bundle.chmod(0o700)

    manifest = bundle / "manifest.json"
    manifest.unlink()
    os.symlink("sandi.json", manifest)
    with pytest.raises(admin_backup.BackupTidakSah, match="file privat biasa"):
        admin_backup.validasi_bundle(bundle)
    manifest.unlink()

    hardlink = tmp_path / "hardlink-auth.json"
    os.link(bundle / "sandi.json", hardlink)
    with pytest.raises(admin_backup.BackupTidakSah, match="file privat biasa"):
        admin_backup.buat_manifest(
            bundle, bundle_id="backup-sintetis-003", cutoff=102
        )


def test_rehearsal_wajib_ai2_dan_tidak_mutasi_backup_induk(tmp_path):
    bundle = _buat_bundle(tmp_path)
    sebelum = {
        path.name: path.read_bytes()
        for path in bundle.iterdir() if path.is_file()
    }
    with pytest.raises(admin_backup.BackupTidakSah, match="AI2"):
        admin_backup.rehearsal_bundle(bundle)

    hasil = admin_backup.rehearsal_bundle(bundle, migrator_ai=_buat_ai_v2)

    assert hasil.versi_admin == admin_store.VERSI_SKEMA
    assert hasil.versi_ai == 2
    assert {
        path.name: path.read_bytes()
        for path in bundle.iterdir() if path.is_file()
    } == sebelum


def test_rehearsal_gagal_migrasi_tidak_mutasi_backup_induk(tmp_path):
    bundle = _buat_bundle(tmp_path)
    sebelum = {
        path.name: path.read_bytes()
        for path in bundle.iterdir() if path.is_file()
    }

    def gagal(_path):
        raise RuntimeError("gagal sintetis")

    with pytest.raises(RuntimeError, match="gagal sintetis"):
        admin_backup.rehearsal_bundle(bundle, migrator_ai=gagal)
    assert {
        path.name: path.read_bytes()
        for path in bundle.iterdir() if path.is_file()
    } == sebelum


def test_setup_receipt_dan_transient_eksplisit_idempoten(tmp_path):
    belajar = tmp_path / "belajar.db"
    transient = tmp_path / "transient" / "admin-drafts.db"
    database.siapkan(belajar)
    with sqlite3.connect(str(belajar)) as kon:
        assert kon.execute(
            "SELECT 1 FROM sqlite_master WHERE name='operasi_admin_siswa'"
        ).fetchone() is None
    import sessions
    akun = tmp_path / 'akun.json'
    sesi = tmp_path / 'sesi.json'
    admin = tmp_path / 'admin-control.db'
    auth.tambah_akun('pengelola', 'sandi-sintetis-123', 'admin', akun)
    principal = auth.autentikasi('pengelola', 'sandi-sintetis-123', akun)
    token = sessions.buat_dari_principal(principal, path=sesi, path_akun=akun, sekarang=1)
    admin_store.siapkan(admin, sekarang=1)
    with pytest.raises(LookupError):
        admin_bulk.baca_batch(
            admin, transient, batch_id="batch_missing", actor_id=principal.id_akun,
            actor_revisi=principal.revisi_auth, path_auth=akun, path_sesi=sesi,
            token_sesi=token, sekarang=1,
        )
    assert not transient.exists()

    admin_students.siapkan(belajar)
    admin_students.siapkan(belajar)
    admin_bulk.siapkan_transient(transient)
    admin_bulk.siapkan_transient(transient)

    with sqlite3.connect(str(belajar)) as kon:
        assert kon.execute(
            "SELECT 1 FROM sqlite_master WHERE name='operasi_admin_siswa'"
        ).fetchone() is not None
    with sqlite3.connect(str(transient)) as kon:
        assert kon.execute("PRAGMA user_version").fetchone()[0] == 2
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_image_wildcard_mencakup_admin_backup_tanpa_data():
    root = Path(__file__).resolve().parent.parent
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY --chown=osn:osn *.py /app/" in dockerfile
    assert (root / "admin_backup.py").is_file()
    assert "sandi.json" not in dockerfile.split("COPY --chown=osn:osn *.py /app/")[0]
    sumber_copy = [baris for baris in dockerfile.splitlines()
                   if baris.strip().startswith(("COPY ", "ADD "))]
    assert not any(nama in baris for baris in sumber_copy
                   for nama in (".db", ".sqlite", "sandi.json", "sesi.json"))
