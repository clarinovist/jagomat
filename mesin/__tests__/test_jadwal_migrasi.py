"""CLI migrasi jadwal: idempoten, wajib kelas, ramah tanpa traceback, tanpa DB nyata."""
import sqlite3

import pytest

import jadwal_migrasi as jm
import kelas_kit
import schema_jadwal


def _db(tmp_path, *, kelas=True):
    if kelas:
        return kelas_kit.siapkan_db_kelas(tmp_path)
    path = tmp_path / "admin-control.db"
    import admin_store
    admin_store.siapkan(path, sekarang=1)
    return path


def _versi(path):
    with sqlite3.connect(path) as kon:
        return kon.execute("PRAGMA user_version").fetchone()[0]


def _dump(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def test_migrasi_di_atas_kelas(tmp_path, capsys):
    path = _db(tmp_path)
    awal = _versi(path)
    assert jm.main(["--database", str(path)]) == 0
    with sqlite3.connect(path) as kon:
        for tabel in schema_jadwal.TABEL:
            assert kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0] == 0
    assert _versi(path) == awal
    assert "selesai" in capsys.readouterr().out


def test_idempoten(tmp_path):
    path = _db(tmp_path)
    jm.main(["--database", str(path)])
    pertama = _dump(path)
    assert jm.main(["--database", str(path)]) == 0
    assert _dump(path) == pertama


def test_tanpa_kelas_ditolak_tanpa_mengubah(tmp_path, capsys):
    path = _db(tmp_path, kelas=False)
    sebelum = _dump(path)
    assert jm.main(["--database", str(path)]) == 2
    err = capsys.readouterr().err
    assert "kelas" in err.lower() and "Traceback" not in err
    assert _dump(path) == sebelum


def test_struktur_parsial_ditolak(tmp_path, capsys):
    path = _db(tmp_path)
    schema_jadwal.migrasikan(path)
    with sqlite3.connect(path) as kon:
        kon.execute("DROP TRIGGER jadwal_penempatan_kuota")
    sebelum = _dump(path)
    assert jm.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert _dump(path) == sebelum


def test_database_hilang_dan_argumen_wajib(tmp_path, capsys):
    assert jm.main(["--database", str(tmp_path / "tidak-ada.db")]) == 2
    assert "Traceback" not in capsys.readouterr().err
    with pytest.raises(SystemExit) as galat:
        jm.main([])
    assert galat.value.code == 2


def test_berkas_bukan_database(tmp_path, capsys):
    path = tmp_path / "sampah.db"
    path.write_bytes(b"bukan sqlite" * 50)
    assert jm.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_nama_berkas_aman_dari_fingerprint_kontrak_rilis():
    nama = jm.__file__.rsplit("/", 1)[-1]
    assert not any(kata in nama for kata in ("migrat", "schema", "database", "store"))
