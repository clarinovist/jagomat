"""CLI operator migrasi kelas_*: idempoten, mensyaratkan pesanan + transfer, ramah tanpa traceback, tanpa DB nyata."""
import sqlite3

import pytest

import admin_store
import kelas_migrasi as km
import schema_kelas
import schema_pesanan
import schema_transfer


def _db(tmp_path, *, pesanan=True, transfer=True):
    path = tmp_path / "admin-control.db"
    admin_store.siapkan(path, sekarang=1)
    if pesanan:
        schema_pesanan.migrasikan(path)
    if transfer:
        schema_transfer.migrasikan(path)
    return path


def _status(path):
    with admin_store.buka_baca(path) as kon:
        return (schema_pesanan.validasi(kon), schema_transfer.validasi(kon),
                schema_kelas.validasi(kon))


def _versi(path):
    with sqlite3.connect(path) as kon:
        return kon.execute("PRAGMA user_version").fetchone()[0]


def _dump(path):
    with sqlite3.connect(path) as kon:
        return tuple(kon.iterdump())


def test_memasang_kelas_di_atas_pesanan_dan_transfer(tmp_path, capsys):
    path = _db(tmp_path)
    awal = _versi(path)
    assert km.main(["--database", str(path)]) == 0
    assert _status(path) == (True, True, True)
    assert _versi(path) == awal                              # tanpa bump user_version
    with sqlite3.connect(path) as kon:                        # tanpa seed
        for tabel in schema_kelas.TABEL:
            assert kon.execute("SELECT COUNT(*) FROM %s" % tabel).fetchone()[0] == 0
    assert "selesai" in capsys.readouterr().out


def test_idempoten_dijalankan_dua_kali_tanpa_mengubah_data(tmp_path):
    path = _db(tmp_path)
    km.main(["--database", str(path)])
    pertama = _dump(path)
    assert km.main(["--database", str(path)]) == 0
    assert _dump(path) == pertama


def test_tanpa_pesanan_ditolak_dan_tidak_mengubah_apa_pun(tmp_path, capsys):
    path = _db(tmp_path, pesanan=False, transfer=False)
    sebelum = _dump(path)
    assert km.main(["--database", str(path)]) == 2
    err = capsys.readouterr().err
    assert "pesanan" in err.lower() and "transfer" in err.lower() and "Traceback" not in err
    assert _dump(path) == sebelum
    assert _status(path) == (False, False, False)


def test_tanpa_transfer_ditolak_dan_tidak_mengubah_apa_pun(tmp_path, capsys):
    path = _db(tmp_path, transfer=False)
    sebelum = _dump(path)
    assert km.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert _dump(path) == sebelum
    assert _status(path) == (True, False, False)


def test_tidak_ada_opsi_memasang_pesanan_atau_transfer(tmp_path):
    path = _db(tmp_path, pesanan=False, transfer=False)
    sebelum = _dump(path)
    with pytest.raises(SystemExit) as galat:
        km.main(["--database", str(path), "--termasuk-pesanan"])
    assert galat.value.code == 2
    assert km.main(["--database", str(path)]) == 2
    assert _dump(path) == sebelum


def test_database_tidak_ada_gagal_ramah_tanpa_membuat_berkas(tmp_path, capsys):
    path = tmp_path / "tidak-ada.db"
    assert km.main(["--database", str(path)]) == 2
    assert not path.exists() and "Traceback" not in capsys.readouterr().err


def test_database_wajib_diberikan_tanpa_bawaan_ke_db_nyata():
    with pytest.raises(SystemExit) as galat:
        km.main([])
    assert galat.value.code == 2


def test_berkas_bukan_database_ditolak_ramah(tmp_path, capsys):
    path = tmp_path / "sampah.db"
    path.write_bytes(b"bukan sqlite" * 100)
    assert km.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("rusak", [
    "DROP TRIGGER kelas_order_satu_terbuka",
    "DROP TRIGGER kelas_akses_verifikasi",
])
def test_struktur_kelas_parsial_ditolak_tanpa_mengubah(tmp_path, capsys, rusak):
    path = _db(tmp_path)
    schema_kelas.migrasikan(path)
    with sqlite3.connect(path) as kon:
        kon.execute(rusak)
    sebelum = _dump(path)
    assert km.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert _dump(path) == sebelum


def test_tabel_kelas_liar_tanpa_ledger_ditolak(tmp_path, capsys):
    path = _db(tmp_path)
    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TABLE kelas_order(x)")
    sebelum = _dump(path)
    assert km.main(["--database", str(path)]) == 2
    assert "Traceback" not in capsys.readouterr().err
    assert _dump(path) == sebelum


def test_nama_berkas_aman_dari_fingerprint_kontrak_rilis():
    nama = km.__file__.rsplit("/", 1)[-1]
    assert not any(kata in nama for kata in ("migrat", "schema", "database", "store"))
