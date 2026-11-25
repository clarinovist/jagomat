"""CLI operator migrasi harga: idempoten, exit 2 tanpa mengubah apa pun bila ditolak."""
import sqlite3

import harga_migrasi
import schema_harga
from harga_kit import siapkan_db_admin_saja


def _ada_objek_harga(path):
    kon = sqlite3.connect(str(path))
    try:
        return kon.execute("SELECT COUNT(*) FROM sqlite_master WHERE tbl_name GLOB 'harga_*'").fetchone()[0]
    finally:
        kon.close()


def test_cli_pasang_lalu_idempoten(tmp_path):
    path = siapkan_db_admin_saja(tmp_path)
    assert harga_migrasi.main(["--database", str(path)]) == 0
    assert harga_migrasi.main(["--database", str(path)]) == 0
    assert _ada_objek_harga(path) > 0


def test_cli_database_tidak_ada_keluar_2_tanpa_membuat_berkas(tmp_path):
    path = tmp_path / "tidak-ada.db"
    assert harga_migrasi.main(["--database", str(path)]) == 2
    assert not path.exists()


def test_cli_store_tak_sah_keluar_2_tanpa_objek_harga(tmp_path):
    path = tmp_path / "kosong.db"
    sqlite3.connect(str(path)).close()
    assert harga_migrasi.main(["--database", str(path)]) == 2
    assert _ada_objek_harga(path) == 0


def test_cli_hasil_tervalidasi_setelah_migrasi(tmp_path):
    path = siapkan_db_admin_saja(tmp_path)
    harga_migrasi.migrasikan(path)
    kon = sqlite3.connect(str(path))
    try:
        assert schema_harga.validasi(kon) is True
    finally:
        kon.close()
