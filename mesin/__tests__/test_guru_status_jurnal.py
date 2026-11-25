"""Jurnal status guru: catat dan daftar di DB terpisah, append-only, tanpa nama pengguna (data sintetis)."""
import stat
import sqlite3
from contextlib import closing

import pytest

import guru_status_jurnal as J

ID_ADMIN = "akun_" + "a" * 32
ID_GURU = "akun_" + "b" * 32
ID_GURU_LAIN = "akun_" + "c" * 32
NAMA_PENGGUNA_UJI = "Ortu-Jurnal-Uji"
PADA_UJI = 1_700_000_000


def _catat(path, *, aksi=J.AKSI_NONAKTIFKAN, id_akun=ID_GURU, oleh=ID_ADMIN, pada=PADA_UJI, revisi=2):
    J.catat(aksi, id_akun, oleh, pada, revisi, path=path)


def _jumlah_baris(path) -> int:
    with closing(sqlite3.connect(str(path))) as kon:
        return kon.execute("SELECT COUNT(*) FROM guru_status_jurnal").fetchone()[0]


def _user_version(path) -> int:
    with closing(sqlite3.connect(str(path))) as kon:
        return kon.execute("PRAGMA user_version").fetchone()[0]


def test_catat_lalu_daftar_mengurutkan_entri_terbaru_dulu(tmp_path):
    # Arrange: dua entri dengan waktu sama; urutan memakai id, bukan waktu
    berkas = tmp_path / "jurnal.db"
    _catat(berkas, aksi=J.AKSI_NONAKTIFKAN, revisi=2)
    _catat(berkas, aksi=J.AKSI_AKTIFKAN, revisi=3)

    # Act
    halaman = J.daftar(path=berkas)

    # Assert
    assert halaman.total == 2
    assert [(x.aksi, x.revisi) for x in halaman.item] == [(J.AKSI_AKTIFKAN, 3), (J.AKSI_NONAKTIFKAN, 2)]
    assert halaman.halaman == 1 and halaman.jumlah_halaman == 1


def test_daftar_memaginasi_dua_puluh_lima_entri_per_halaman(tmp_path):
    # Arrange
    berkas = tmp_path / "jurnal.db"
    for revisi in range(1, 27):
        _catat(berkas, revisi=revisi)

    # Act
    halaman_1 = J.daftar(path=berkas)
    halaman_2 = J.daftar(halaman=2, path=berkas)
    halaman_luar = J.daftar(halaman=99, path=berkas)

    # Assert
    assert halaman_1.total == 26 and halaman_1.per_halaman == 25 and halaman_1.jumlah_halaman == 2
    assert len(halaman_1.item) == 25 and halaman_1.item[0].revisi == 26
    assert [x.revisi for x in halaman_2.item] == [1]
    assert halaman_luar.halaman == 2 and [x.revisi for x in halaman_luar.item] == [1]


def test_daftar_memfilter_satu_id_akun(tmp_path):
    # Arrange
    berkas = tmp_path / "jurnal.db"
    _catat(berkas, id_akun=ID_GURU)
    _catat(berkas, id_akun=ID_GURU_LAIN)

    # Act
    halaman = J.daftar(id_akun=ID_GURU, path=berkas)

    # Assert
    assert halaman.total == 1
    assert [x.id_akun for x in halaman.item] == [ID_GURU]


def test_daftar_berkas_belum_ada_mengembalikan_kosong_tanpa_membuat_berkas(tmp_path):
    # Arrange
    berkas = tmp_path / "belum-ada.db"

    # Act
    halaman = J.daftar(path=berkas)

    # Assert
    assert halaman.item == () and halaman.total == 0 and halaman.jumlah_halaman == 1
    assert not berkas.exists()


def test_catat_membuat_berkas_privat_dengan_skema_versi_satu(tmp_path):
    # Arrange
    berkas = tmp_path / "jurnal.db"

    # Act
    _catat(berkas)

    # Assert
    assert stat.S_IMODE(berkas.stat().st_mode) == 0o600
    assert _user_version(berkas) == 1 == J.VERSI_SKEMA


@pytest.mark.parametrize("sql", [
    "UPDATE guru_status_jurnal SET oleh = 'pengelola-lain'",
    "DELETE FROM guru_status_jurnal",
])
def test_update_dan_delete_langsung_ke_tabel_ditolak_trigger(tmp_path, sql):
    # Arrange
    berkas = tmp_path / "jurnal.db"
    _catat(berkas)

    # Act
    with closing(sqlite3.connect(str(berkas))) as kon:
        with pytest.raises(sqlite3.Error):
            kon.execute(sql)

    # Assert
    assert _jumlah_baris(berkas) == 1


@pytest.mark.parametrize("argumen", [
    {"aksi": "hapus"},
    {"id_akun": "bukan-id"},
    {"oleh": ""},
    {"oleh": "x" * 81},
    {"pada": 0},
    {"pada": -5},
    {"revisi": True},
    {"revisi": "2"},
])
def test_argumen_tidak_sah_ditolak_tanpa_menulis_apa_pun(tmp_path, argumen):
    # Arrange
    berkas = tmp_path / "jurnal.db"

    # Act
    with pytest.raises(ValueError):
        _catat(berkas, **argumen)

    # Assert
    assert not berkas.exists()


def test_berkas_rusak_menghasilkan_galat_jurnal(tmp_path):
    # Arrange
    berkas = tmp_path / "jurnal.db"
    berkas.write_bytes(b"bukan sqlite " * 300)

    # Act and Assert
    with pytest.raises(J.GalatJurnal):
        J.daftar(path=berkas)
    with pytest.raises(J.GalatJurnal):
        _catat(berkas)


def test_skema_versi_lain_ditolak_galat_jurnal(tmp_path):
    # Arrange
    berkas = tmp_path / "jurnal.db"
    with closing(sqlite3.connect(str(berkas))) as kon:
        kon.execute("PRAGMA user_version = 99")

    # Act and Assert
    with pytest.raises(J.GalatJurnal):
        J.daftar(path=berkas)
    with pytest.raises(J.GalatJurnal):
        _catat(berkas)


def test_berkas_hanya_menyimpan_id_akun_tanpa_nama_pengguna(tmp_path):
    # Arrange
    berkas = tmp_path / "jurnal.db"

    # Act
    _catat(berkas, oleh=ID_ADMIN)

    # Assert
    with closing(sqlite3.connect(str(berkas))) as kon:
        kolom = {baris[1] for baris in kon.execute("PRAGMA table_info(guru_status_jurnal)")}
    assert kolom == {"id", "aksi", "id_akun", "oleh", "pada", "revisi"}
    assert NAMA_PENGGUNA_UJI.encode() not in berkas.read_bytes()


def test_path_parameter_mengalahkan_env_yang_dibaca_saat_dipanggil(tmp_path, monkeypatch):
    # Arrange
    dari_env = tmp_path / "env.db"
    dari_parameter = tmp_path / "parameter.db"
    monkeypatch.setenv(J.ENV_BERKAS_DB, str(dari_env))

    # Act
    J.catat(J.AKSI_AKTIFKAN, ID_GURU, ID_ADMIN, PADA_UJI, 3)
    _catat(dari_parameter)

    # Assert
    assert J.daftar(path=dari_env).total == 1
    assert J.daftar(path=dari_parameter).total == 1


def test_daftar_id_akun_tak_sah_ditolak_dengan_valueerror(tmp_path):
    with pytest.raises(ValueError):
        J.daftar(id_akun="bukan-id", path=tmp_path / "jurnal.db")
