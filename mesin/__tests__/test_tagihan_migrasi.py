"""CLI migrasi tagihan: idempoten, wajib kelas, ramah tanpa traceback, tanpa DB nyata."""
import sqlite3

import pytest

import kelas_kit
import schema_tagihan_catatan as stc
import tagihan_migrasi as tm


def _db(tmp_path, *, kelas=True):
    if kelas:
        return kelas_kit.siapkan_db_kelas(tmp_path)
    import admin_store
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    return path


def _dump(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def test_migrasi_di_atas_kelas_lulus_validasi(tmp_path, capsys):
    path = _db(tmp_path)
    assert tm.main(["--database", str(path)]) == 0
    assert "Traceback" not in capsys.readouterr().err
    with sqlite3.connect(path) as kon:
        assert stc.validasi(kon) is True


def test_idempoten(tmp_path):
    path = _db(tmp_path)
    assert tm.main(["--database", str(path)]) == 0
    sesudah_pertama = _dump(path)
    assert tm.main(["--database", str(path)]) == 0
    assert _dump(path) == sesudah_pertama


def test_tanpa_kelas_ditolak_tanpa_mengubah(tmp_path, capsys):
    path = _db(tmp_path, kelas=False)
    sebelum = _dump(path)
    assert tm.main(["--database", str(path)]) == 2
    err = capsys.readouterr().err
    assert "kelas" in err.lower() and "Traceback" not in err
    assert _dump(path) == sebelum


def test_struktur_parsial_ditolak(tmp_path, capsys):
    path = _db(tmp_path)
    tm.migrasikan(path)
    with sqlite3.connect(path) as kon:
        kon.execute("DROP TRIGGER tagihan_catatan_tolak_update")
    sebelum = _dump(path)
    assert tm.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert _dump(path) == sebelum


def test_database_hilang_dan_argumen_wajib(tmp_path, capsys):
    assert tm.main(["--database", str(tmp_path / "tidak-ada.db")]) == 2
    assert "Traceback" not in capsys.readouterr().err
    with pytest.raises(SystemExit) as galat:
        tm.main([])
    assert galat.value.code == 2


def test_berkas_bukan_database(tmp_path, capsys):
    path = tmp_path / "sampah.db"
    path.write_bytes(b"bukan sqlite" * 50)
    assert tm.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err


def test_nama_berkas_aman_dari_fingerprint_kontrak_rilis():
    nama = tm.__file__.rsplit("/", 1)[-1]
    assert not any(kata in nama for kata in ("migrat", "schema", "database", "store"))
