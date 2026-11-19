"""CLI operator migrasi transfer_* + rekening: idempoten, urutan FK, gagal keras tanpa pesanan, tanpa DB nyata."""
import sqlite3

import pytest

import admin_store
import pesanan_rekening
import pesanan_transfer_migrasi as pm
import schema_pesanan
import schema_transfer


def _db(tmp_path, *, pesanan=True):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    if pesanan:
        schema_pesanan.migrasikan(path)
    return path


def _status(path):
    with admin_store.buka_baca(path) as kon:
        return (schema_pesanan.validasi(kon), schema_transfer.validasi(kon),
                pesanan_rekening.validasi_schema(kon))


def _versi(path):
    with sqlite3.connect(path) as kon:
        return kon.execute("PRAGMA user_version").fetchone()[0]


def test_memasang_transfer_dan_rekening_di_atas_pesanan(tmp_path, capsys):
    path = _db(tmp_path)
    awal = _versi(path)
    assert pm.main(["--database", str(path)]) == 0
    assert _status(path) == (True, True, True)
    assert _versi(path) == awal                             # tanpa bump user_version
    assert pesanan_rekening.baca(path) is None              # tanpa rekening bawaan
    assert "selesai" in capsys.readouterr().out


def test_idempoten_dijalankan_dua_kali_tanpa_mengubah_data(tmp_path):
    path = _db(tmp_path)
    pm.main(["--database", str(path)])
    with sqlite3.connect(path) as kon:
        pertama = tuple(kon.iterdump())
    assert pm.main(["--database", str(path)]) == 0
    with sqlite3.connect(path) as kon:
        assert tuple(kon.iterdump()) == pertama


def test_tanpa_pesanan_gagal_keras_dan_tidak_memasang_apa_pun(tmp_path, capsys):
    path = _db(tmp_path, pesanan=False)
    assert pm.main(["--database", str(path)]) == 2
    err = capsys.readouterr().err
    assert "pesanan" in err.lower() and "--termasuk-pesanan" in err and "Traceback" not in err
    assert _status(path) == (False, False, False)


def test_opsi_termasuk_pesanan_memasang_ketiganya_berurutan(tmp_path):
    path = _db(tmp_path, pesanan=False)
    assert pm.main(["--database", str(path), "--termasuk-pesanan"]) == 0
    assert _status(path) == (True, True, True)


def test_database_tidak_ada_gagal_ramah_tanpa_membuat_berkas(tmp_path, capsys):
    path = tmp_path / "tidak-ada.db"
    assert pm.main(["--database", str(path)]) == 2
    assert not path.exists() and "Traceback" not in capsys.readouterr().err


def test_database_wajib_diberikan_tanpa_bawaan_ke_db_nyata():
    with pytest.raises(SystemExit) as galat:
        pm.main([])
    assert galat.value.code == 2


def test_struktur_parsial_ditolak_dengan_pesan_ramah(tmp_path, capsys):
    path = _db(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE transfer_tagihan(x)")
    assert pm.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err
