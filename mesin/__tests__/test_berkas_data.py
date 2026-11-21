"""Penguatan berkas data saat startup: mode 0600 dan jurnal WAL setelah restore.

Tidak membuat berkas, tidak DDL, tidak mengubah isi atau user_version.
"""
from __future__ import annotations

import os
import sqlite3
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import berkas_data  # noqa: E402
import serve  # noqa: E402


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def _jurnal(path):
    with sqlite3.connect(path) as kon:
        return kon.execute("PRAGMA journal_mode").fetchone()[0]


def _buat_db(path, mode_jurnal="delete", user_version=7):
    kon = sqlite3.connect(path)
    kon.execute("CREATE TABLE t (a INTEGER)")
    kon.execute("INSERT INTO t VALUES (1), (2)")
    kon.execute(f"PRAGMA user_version = {user_version}")
    kon.commit()
    kon.execute(f"PRAGMA journal_mode = {mode_jurnal}")
    kon.close()


def _isi(path):
    with sqlite3.connect(path) as kon:
        return (
            kon.execute("SELECT a FROM t ORDER BY a").fetchall(),
            kon.execute("PRAGMA user_version").fetchone()[0],
        )


# ---- mode berkas ----

def test_berkas_0644_dan_sidecar_menjadi_0600(tmp_path):
    db = tmp_path / "latihan.db"
    wal = tmp_path / "latihan.db-wal"
    shm = tmp_path / "latihan.db-shm"
    for p in (db, wal, shm):
        p.write_bytes(b"x")
        os.chmod(p, 0o644)

    ringkasan = berkas_data.kencangkan_data([db])

    assert [_mode(p) for p in (db, wal, shm)] == [0o600] * 3
    assert sorted(ringkasan["diubah"]) == sorted(str(p) for p in (db, wal, shm))
    assert ringkasan["galat"] == []


def test_berkas_sudah_0600_tidak_disentuh(tmp_path, monkeypatch):
    db = tmp_path / "admin-control.db"
    db.write_bytes(b"x")
    os.chmod(db, 0o600)
    panggilan = []
    monkeypatch.setattr(os, "chmod", lambda *a, **k: panggilan.append(a))

    ringkasan = berkas_data.kencangkan_data([db])

    assert panggilan == []
    assert ringkasan["diubah"] == []


def test_berkas_tak_ada_tidak_dibuat(tmp_path):
    db = tmp_path / "sakelar.db"

    ringkasan = berkas_data.kencangkan_data([db], wal=[db])

    assert list(tmp_path.iterdir()) == []
    assert ringkasan == {"diubah": [], "wal": [], "galat": []}


def test_chmod_gagal_dilaporkan_tanpa_melempar(tmp_path, monkeypatch):
    db = tmp_path / "latihan.db"
    db.write_bytes(b"x")
    os.chmod(db, 0o644)

    def gagal(*_a, **_k):
        raise PermissionError("ditolak")
    monkeypatch.setattr(os, "chmod", gagal)

    ringkasan = berkas_data.kencangkan_data([db])

    assert ringkasan["diubah"] == []
    assert len(ringkasan["galat"]) == 1
    assert str(db) in ringkasan["galat"][0]
    assert _mode(db) == 0o644


def test_berkas_bukan_milik_euid_dilewati_dan_dilaporkan(tmp_path, monkeypatch):
    db = tmp_path / "latihan.db"
    db.write_bytes(b"x")
    os.chmod(db, 0o644)
    monkeypatch.setattr(os, "geteuid", lambda: os.stat(db).st_uid + 1)

    ringkasan = berkas_data.kencangkan_data([db])

    assert _mode(db) == 0o644
    assert ringkasan["diubah"] == []
    assert len(ringkasan["galat"]) == 1


def test_symlink_tidak_diikuti(tmp_path):
    asli = tmp_path / "asli"
    asli.write_bytes(b"x")
    os.chmod(asli, 0o644)
    tautan = tmp_path / "latihan.db"
    tautan.symlink_to(asli)

    ringkasan = berkas_data.kencangkan_data([tautan])

    assert _mode(asli) == 0o644
    assert ringkasan["diubah"] == []


# ---- WAL ----

def test_pendamping_delete_menjadi_wal_tanpa_ubah_isi(tmp_path):
    db = tmp_path / "pendamping.db"
    _buat_db(db, "delete", user_version=7)
    sebelum = _isi(db)
    assert _jurnal(db) == "delete"

    ringkasan = berkas_data.kencangkan_data([db], wal=[db])

    assert _jurnal(db) == "wal"
    assert _isi(db) == sebelum
    assert ringkasan["wal"] == [str(db)]
    assert ringkasan["galat"] == []


def test_wal_berkas_tak_ada_tidak_dibuat(tmp_path):
    db = tmp_path / "pendamping.db"

    berkas_data.kencangkan_data([], wal=[db])

    assert not db.exists()


def test_wal_sudah_wal_tidak_diubah(tmp_path, monkeypatch):
    db = tmp_path / "pendamping.db"
    _buat_db(db, "wal")
    diaktifkan = []
    monkeypatch.setattr(
        berkas_data.jurnal_wal, "aktifkan", lambda kon: diaktifkan.append(kon),
    )

    ringkasan = berkas_data.kencangkan_data([], wal=[db])

    assert diaktifkan == []
    assert ringkasan["wal"] == []


def test_wal_berkas_kosong_dilewati(tmp_path):
    db = tmp_path / "pendamping.db"
    db.write_bytes(b"")

    berkas_data.kencangkan_data([], wal=[db])

    assert db.stat().st_size == 0


def test_wal_gagal_dilaporkan_tanpa_melempar(tmp_path):
    db = tmp_path / "pendamping.db"
    db.write_bytes(b"bukan sqlite" * 100)

    ringkasan = berkas_data.kencangkan_data([], wal=[db])

    assert len(ringkasan["galat"]) == 1
    assert str(db) in ringkasan["galat"][0]


def test_wal_lalu_mode_berkas_0600_dalam_satu_panggilan(tmp_path):
    db = tmp_path / "pendamping.db"
    _buat_db(db, "delete")
    os.chmod(db, 0o644)

    berkas_data.kencangkan_data([db], wal=[db])

    assert _jurnal(db) == "wal"
    assert _mode(db) == 0o600


# ---- jalur bawaan ----

def test_jalur_db_durable_menghormati_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "s.db"))
    monkeypatch.setenv("KURIKULUM_BERKAS_DB", str(tmp_path / "k.db"))
    monkeypatch.setenv("CETAKAN_BERKAS_DB", str(tmp_path / "c.db"))
    monkeypatch.setenv("CETAKAN_AI_BERKAS_DB", str(tmp_path / "ca.db"))

    jalur = berkas_data.jalur_db_durable()

    for nama in ("s.db", "k.db", "c.db", "ca.db"):
        assert tmp_path / nama in jalur
    assert len(jalur) == 9
    assert len(set(jalur)) == 9


def test_jalur_wal_hanya_empat_ditambah_pendamping(tmp_path, monkeypatch):
    for env in ("SAKELAR_BERKAS_DB", "KURIKULUM_BERKAS_DB",
                "CETAKAN_BERKAS_DB", "CETAKAN_AI_BERKAS_DB"):
        monkeypatch.setenv(env, str(tmp_path / env))

    jalur = berkas_data.jalur_wal()

    assert berkas_data.assistant_schema.BAWAAN in jalur
    assert tmp_path / "SAKELAR_BERKAS_DB" in jalur
    assert len(jalur) == 5


def test_kencangkan_saat_start_mencetak_galat_satu_baris(capsys, monkeypatch):
    monkeypatch.setattr(
        berkas_data, "kencangkan_data",
        lambda *a, **k: {"diubah": [], "wal": [], "galat": ["x.db: ditolak"]},
    )

    berkas_data.kencangkan_saat_start()

    err = capsys.readouterr().err
    assert "x.db: ditolak" in err
    assert len(err.strip().splitlines()) == 1


def test_kencangkan_saat_start_tak_melempar_bila_gagal_total(monkeypatch, capsys):
    def meledak(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(berkas_data, "kencangkan_data", meledak)

    berkas_data.kencangkan_saat_start()

    assert "boom" in capsys.readouterr().err


# ---- integrasi serve.main ----

class _Berhenti(Exception):
    pass


def test_serve_main_memanggil_penguatan_sesudah_semua_siapkan(monkeypatch):
    urutan = []

    def catat(nama):
        return lambda *a, **k: urutan.append(nama)

    monkeypatch.setattr(sys, "argv", ["serve.py"])
    monkeypatch.setattr(serve.database, "siapkan", catat("database"))
    monkeypatch.setattr(serve.ai_store, "siapkan", catat("ai"))
    monkeypatch.setattr(serve.ai_store, "purge", catat("ai_purge"))
    monkeypatch.setattr(serve.admin_store, "siapkan", catat("admin"))
    monkeypatch.setattr(serve.admin_students, "siapkan", catat("siswa"))
    monkeypatch.setattr(serve.research_store, "siapkan", catat("riset"))
    monkeypatch.setattr(serve.admin_bulk, "siapkan_transient", catat("transient"))
    monkeypatch.setattr(serve.sessions, "bersihkan", catat("sesi"))
    monkeypatch.setattr(
        serve, "siapkan_admin_dan_pemilik",
        lambda: urutan.append("pemilik"),
    )

    def kencangkan():
        urutan.append("kencangkan")
        raise _Berhenti()
    monkeypatch.setattr(serve.berkas_data, "kencangkan_saat_start", kencangkan)

    with pytest.raises(_Berhenti):
        serve.main()

    assert urutan[-1] == "kencangkan"
    assert urutan[:-1] == [
        "database", "ai", "ai_purge", "admin", "siswa", "riset",
        "transient", "sesi", "pemilik",
    ]
