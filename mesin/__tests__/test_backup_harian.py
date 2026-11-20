"""Backup harian online: salinan portabel per DB + sandi.json + manifest."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup_harian.py"
spec = importlib.util.spec_from_file_location("backup_harian", SCRIPT)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def _db(path, baris=3):
    kon = sqlite3.connect(path)
    kon.execute("PRAGMA journal_mode=WAL")
    kon.execute("CREATE TABLE t(x INTEGER)")
    kon.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(baris)])
    kon.commit()
    kon.close()


def _data(tmp_path):
    data = tmp_path / "data"
    data.mkdir(mode=0o700)
    _db(data / "latihan.db", 3)
    (data / "sandi.json").write_text('{"akun": []}', encoding="utf-8")
    (data / "sandi.json").chmod(0o600)
    return data


def test_cadangkan_membuat_salinan_portabel(tmp_path):
    data = _data(tmp_path)
    out = tmp_path / "backup"

    hasil = backup.cadangkan(data, out, wajib=("latihan.db",), sekarang=100)

    db = hasil / "latihan.db"
    assert db.stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(db) as kon:
        assert kon.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert kon.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 3
        assert kon.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not (hasil / "latihan.db-wal").exists()
    assert not (hasil / "latihan.db-shm").exists()


def test_manifest_memuat_hash_dan_penanda_rekonsiliasi(tmp_path):
    data = _data(tmp_path)
    out = tmp_path / "backup"

    hasil = backup.cadangkan(data, out, wajib=("latihan.db",), sekarang=100)

    manifest = json.loads((hasil / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["needs_reconciliation"] is True
    assert manifest["versi"] == 1
    nama = {item["nama"]: item for item in manifest["berkas"]}
    assert set(nama) == {"latihan.db", "sandi.json"}
    sidik = hashlib.sha256((hasil / "latihan.db").read_bytes()).hexdigest()
    assert nama["latihan.db"]["sha256"] == sidik
    assert backup.validasi(hasil)["id"] == manifest["id"]


def test_retensi_hanya_menyisakan_n_salinan(tmp_path):
    data = _data(tmp_path)
    out = tmp_path / "backup"
    for i in range(4):
        backup.cadangkan(data, out, wajib=("latihan.db",), sekarang=100 + i)

    backup.cadangkan(data, out, wajib=("latihan.db",), sekarang=200, retensi=2)

    tersisa = sorted(p.name for p in out.iterdir() if p.is_dir())
    assert len(tersisa) == 2


def test_menolak_output_di_dalam_data(tmp_path):
    data = _data(tmp_path)
    with pytest.raises(ValueError):
        backup.cadangkan(data, data / "backup", wajib=("latihan.db",), sekarang=100)


def test_db_wajib_hilang_ditolak(tmp_path):
    data = _data(tmp_path)
    with pytest.raises(FileNotFoundError):
        backup.cadangkan(data, tmp_path / "b", wajib=("hilang.db",), sekarang=100)
