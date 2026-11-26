"""Pemeriksaan "anak masih ada" untuk tautan kode anak guru (`guru_tautan_anak`): kecocokan akun dan siswa, gagal
tertutup saat auth atau DB rusak, dan skenario hapus keluarga yang nyata (siswa dianonimkan, akun dibuang).

Data sepenuhnya sintetis. Fixture `server` memberi auth dan latihan.db sementara di tmp_path.
"""
from __future__ import annotations

import json
import sqlite3

import auth
import database
import guru_tautan_anak as anak
from cek_http_kit import server, tambah_anak  # noqa: F401
from guru_tautan_kit import (
    LOGIN_ANAK,
    SANDI_ANAK,
    hapus_keluarga_sintetis,
    tambah_murid,
)

SANDI = "sandi-sintetis-anak-123"


def _berkas_auth(tmp_path):
    berkas = tmp_path / "sandi.json"
    auth.simpan_sandi(SANDI, "guru", path=berkas)
    return berkas


def _ubah_akun_mentah(berkas, pengguna: str, **kunci) -> None:
    """Ubah satu akun di berkas auth secara mentah (uji bentuk data yang tidak bisa dibuat lewat API)."""
    data = json.loads(berkas.read_text(encoding="utf-8"))
    for akun in data["akun"]:
        if akun["pengguna"] == pengguna:
            akun.update(kunci)
    berkas.write_text(json.dumps(data), encoding="utf-8")


def _siswa(tmp_path, nama="Anak Sintetis Alfa", pemilik="keluarga-uji") -> tuple:
    db = tmp_path / "latihan-uji.db"
    database.siapkan(db)
    with database.buka(db) as kon:
        siswa = database.tambah_siswa(kon, nama, "P3", pemilik=pemilik)
        kon.commit()
    return db, siswa


def _murid(berkas, siswa_id: int, login: str = LOGIN_ANAK) -> str:
    principal = auth.tambah_akun_dan_principal(login, SANDI_ANAK, "murid", path=berkas, siswa_id=siswa_id)
    return principal.id_akun


def test_anak_masih_ada_bila_akun_murid_dan_siswa_cocok(tmp_path):
    # Arrange
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    akun_id = _murid(berkas, siswa)

    # Act
    hasil = anak.anak_masih_ada(akun_id, siswa, path_auth=berkas, path_belajar=db)

    # Assert
    assert hasil is True


def test_anak_tidak_ada_bila_siswa_id_akun_berbeda(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    akun_id = _murid(berkas, siswa)

    assert anak.anak_masih_ada(akun_id, siswa + 1, path_auth=berkas, path_belajar=db) is False


def test_anak_tidak_ada_bila_id_akun_tidak_dikenal(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    _murid(berkas, siswa)

    assert anak.anak_masih_ada("akun_" + "f" * 32, siswa, path_auth=berkas, path_belajar=db) is False


def test_akun_guru_tidak_dihitung_sebagai_anak(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    principal = auth.tambah_akun_dan_principal("guru-lain", SANDI, "guru", path=berkas, siswa_id=siswa)

    assert anak.anak_masih_ada(principal.id_akun, siswa, path_auth=berkas, path_belajar=db) is False


def test_akun_murid_dinonaktifkan_tidak_dihitung(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    akun_id = _murid(berkas, siswa)
    _ubah_akun_mentah(berkas, LOGIN_ANAK, dinonaktifkan=True)

    assert anak.anak_masih_ada(akun_id, siswa, path_auth=berkas, path_belajar=db) is False


def test_siswa_yang_sudah_dianonimkan_tidak_dihitung(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    akun_id = _murid(berkas, siswa)
    with sqlite3.connect(db) as kon:
        kon.execute("UPDATE siswa SET nama='Dihapus-1' WHERE id=?", (siswa,))

    assert anak.anak_masih_ada(akun_id, siswa, path_auth=berkas, path_belajar=db) is False


def test_siswa_yang_barisnya_hilang_tidak_dihitung(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    akun_id = _murid(berkas, siswa)
    with sqlite3.connect(db) as kon:
        kon.execute("DELETE FROM siswa WHERE id=?", (siswa,))

    assert anak.anak_masih_ada(akun_id, siswa, path_auth=berkas, path_belajar=db) is False


def test_latihan_db_tak_ada_gagal_tertutup_dan_tidak_dibuat(tmp_path):
    berkas = _berkas_auth(tmp_path)
    akun_id = _murid(berkas, 1)
    db = tmp_path / "tidak-ada.db"

    assert anak.anak_masih_ada(akun_id, 1, path_auth=berkas, path_belajar=db) is False
    assert not db.exists()


def test_auth_korup_gagal_tertutup_tanpa_raise(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    akun_id = _murid(berkas, siswa)
    berkas.write_text("{ bukan json", encoding="utf-8")

    assert anak.anak_masih_ada(akun_id, siswa, path_auth=berkas, path_belajar=db) is False


def test_auth_tak_terbaca_gagal_tertutup(tmp_path, monkeypatch):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)

    def _rusak(_path):
        raise OSError("berkas tidak bisa dibuka")

    monkeypatch.setattr(anak, "_baca_akun", _rusak)

    assert anak.anak_masih_ada("akun_" + "a" * 32, siswa, path_auth=berkas, path_belajar=db) is False
    assert anak.nama_login("akun_" + "a" * 32, path_auth=berkas) is None


def test_nama_login_mengembalikan_nama_murid_saja(tmp_path):
    berkas = _berkas_auth(tmp_path)
    db, siswa = _siswa(tmp_path)
    akun_id = _murid(berkas, siswa)
    auth.tambah_akun("guru-uji", SANDI, "guru", path=berkas)

    assert anak.nama_login(akun_id, path_auth=berkas) == LOGIN_ANAK
    assert anak.nama_login("akun_" + "e" * 32, path_auth=berkas) is None


def test_hapus_keluarga_lewat_jalur_nyata_membuat_anak_tak_ada(server):
    """Skenario nyata: keluarga dihapus lewat `family_deletion` (siswa dianonimkan, akun murid dibuang)."""
    auth.tambah_akun("keluarga-lain", SANDI, "guru")
    siswa = tambah_anak(server, "Anak Sintetis Lain", "keluarga-lain", None)
    murid = tambah_murid(siswa_id=siswa)
    assert anak.anak_masih_ada(murid["id_akun"], siswa) is True

    hapus_keluarga_sintetis("keluarga-lain")

    assert auth.cari_akun(LOGIN_ANAK) is None
    assert anak.anak_masih_ada(murid["id_akun"], siswa) is False
    with server.buka() as kon:
        nama = kon.execute("SELECT nama FROM siswa WHERE id=?", (siswa,)).fetchone()[0]
    assert nama.startswith("Dihapus-")
