"""Bundle backup riset terpisah memakai data sintetis tanpa identitas keluarga."""
import json
from pathlib import Path
import sqlite3

import pytest

import research_backup as backup
import research_store as store


ACTOR = "akun_" + "a" * 32


def _db(tmp_path):
    path = tmp_path / "riset-konsumen.db"
    store.siapkan(path, sekarang=1)
    store.buat_wawancara(
        path, actor_id=ACTOR, operasi_id="op_" + "1" * 32, kode_responden="R01",
        sumber="internal", consent_rekaman=False, diwawancarai=1, sekarang=1,
    )
    return path


def test_salin_manifest_validasi_dan_replay(tmp_path):
    sumber = _db(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    backup.salin(sumber, bundle)
    assert (bundle / backup.NAMA_DB).stat().st_mode & 0o777 == 0o600
    asli = (bundle / backup.NAMA_DB).read_bytes()
    backup.buat_manifest(bundle, bundle_id="riset-20261014", cutoff=10)
    ringkas = backup.validasi(bundle, bundle_id="riset-20261014")
    assert ringkas == {"bundle_id": "riset-20261014", "cutoff": 10, "wawancara": 1}
    # Sumber live tidak pernah berubah oleh helper.
    assert sumber.read_bytes() != asli


def test_backup_rusak_ditolak_tanpa_memperbaiki(tmp_path):
    sumber = _db(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    backup.salin(sumber, bundle)
    backup.buat_manifest(bundle, bundle_id="riset-uji", cutoff=10)
    db = bundle / backup.NAMA_DB
    manifest_path = bundle / backup.NAMA_MANIFEST
    data = json.loads(manifest_path.read_text())
    data["berkas"]["ukuran"] = 1
    manifest_path.write_text(json.dumps(data))
    sebelum = db.read_bytes()
    manifest = manifest_path.read_bytes()
    with pytest.raises(backup.BackupRisetTidakSah, match="hash/ukuran"):
        backup.validasi(bundle)
    assert db.read_bytes() == sebelum
    assert manifest_path.read_bytes() == manifest


def test_backup_hash_berubah_ditolak(tmp_path):
    """Isi SQLite tetap valid, tetapi hash tidak lagi cocok dengan manifest."""
    sumber = _db(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    backup.salin(sumber, bundle)
    backup.buat_manifest(bundle, bundle_id="riset-uji", cutoff=10)
    db = bundle / backup.NAMA_DB
    with sqlite3.connect(db) as kon:
        kon.execute("UPDATE wawancara_riset SET kode_responden='R99'")
    sebelum = db.read_bytes()
    with pytest.raises(backup.BackupRisetTidakSah, match="hash/ukuran"):
        backup.validasi(bundle)
    assert db.read_bytes() == sebelum


def test_inventaris_asing_dan_izin_longgar_ditolak(tmp_path):
    sumber = _db(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    backup.salin(sumber, bundle)
    (bundle / "sesi.json").write_text("{}")
    with pytest.raises(backup.BackupRisetTidakSah, match="inventaris"):
        backup.buat_manifest(bundle, bundle_id="riset-uji", cutoff=1)
    (bundle / "sesi.json").unlink()
    backup.buat_manifest(bundle, bundle_id="riset-uji", cutoff=1)
    (bundle / backup.NAMA_MANIFEST).chmod(0o644)
    with pytest.raises(backup.BackupRisetTidakSah, match="izin"):
        backup.validasi(bundle)


def test_manifest_tidak_lengkap_ditolak(tmp_path):
    sumber = _db(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    backup.salin(sumber, bundle)
    backup.buat_manifest(bundle, bundle_id="riset-uji", cutoff=1)
    data = json.loads((bundle / backup.NAMA_MANIFEST).read_text())
    data["berkas"]["ukuran"] = 1
    (bundle / backup.NAMA_MANIFEST).write_text(json.dumps(data))
    with pytest.raises(backup.BackupRisetTidakSah, match="hash/ukuran"):
        backup.validasi(bundle)


def test_schema_parsial_dalam_bundle_ditolak(tmp_path):
    sumber = _db(tmp_path)
    bundle = tmp_path / "bundle"
    bundle.mkdir(mode=0o700)
    backup.salin(sumber, bundle)
    db = bundle / backup.NAMA_DB
    with sqlite3.connect(db) as kon:
        kon.execute("DROP TABLE audit_riset")
    backup.buat_manifest(bundle, bundle_id="riset-uji", cutoff=1)
    with pytest.raises(backup.BackupRisetTidakSah, match="schema"):
        backup.validasi(bundle)
