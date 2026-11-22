"""Penugasan Mode Lomba per anak: simpan, ubah, validasi nilai, CHECK DB, dan CASCADE saat siswa dihapus."""
import dataclasses
import sqlite3

import pytest

import contest_assignment_store as A
import contest_paket as PK
import database

SEKARANG = 1_800_000_000


@pytest.fixture
def kon(tmp_path):
    path = tmp_path / "lomba.db"
    database.siapkan(path)
    with database.buka(path) as k:
        yield k


@pytest.fixture
def anak(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Satu", pemilik="guru")


@pytest.fixture
def anak_lain(kon):
    return database.tambah_siswa(kon, "Anak Sintetis Dua", pemilik="guru")


def _atur(kon, siswa_id, **ubah):
    nilai = dict(aktif=True, target_harian=None, tampil_hitung_mundur=None, sekarang=SEKARANG, oleh="guru1")
    nilai.update(ubah)
    return A.atur(kon, siswa_id, **nilai)


def test_ambil_mengembalikan_none_bila_belum_ada_penugasan(kon, anak):
    assert A.ambil(kon, anak) is None


def test_atur_pertama_menyimpan_baris_dengan_paket_aktif(kon, anak):
    hasil = _atur(kon, anak, target_harian=3, tampil_hitung_mundur=False)

    assert hasil == A.Penugasan(siswa_id=anak, paket_id=PK.PAKET_AKTIF.id, aktif=True, target_harian=3,
                                tampil_hitung_mundur=False, diubah_epoch=SEKARANG, diubah_oleh="guru1")
    assert A.ambil(kon, anak) == hasil


def test_nilai_none_berarti_ikut_paket_dan_tersimpan_sebagai_null(kon, anak):
    _atur(kon, anak)

    baris = kon.execute("SELECT target_harian, tampil_hitung_mundur FROM lomba_penugasan").fetchone()
    assert tuple(baris) == (None, None)
    ambil = A.ambil(kon, anak)
    assert ambil.target_harian is None and ambil.tampil_hitung_mundur is None


def test_atur_kedua_mengubah_baris_yang_sama_tanpa_menggandakan(kon, anak):
    _atur(kon, anak, target_harian=1)
    hasil = _atur(kon, anak, aktif=False, target_harian=0, tampil_hitung_mundur=True,
                  sekarang=SEKARANG + 60, oleh="admin")

    assert kon.execute("SELECT COUNT(*) FROM lomba_penugasan").fetchone()[0] == 1
    assert (hasil.aktif, hasil.target_harian, hasil.tampil_hitung_mundur) == (False, 0, True)
    assert (hasil.diubah_epoch, hasil.diubah_oleh) == (SEKARANG + 60, "admin")


def test_atur_satu_anak_tidak_mengubah_anak_lain(kon, anak, anak_lain):
    _atur(kon, anak_lain, target_harian=2)
    sebelum = A.ambil(kon, anak_lain)

    _atur(kon, anak, target_harian=3)

    assert A.ambil(kon, anak_lain) == sebelum


def test_penugasan_tidak_bisa_dimutasi(kon, anak):
    hasil = _atur(kon, anak)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hasil.aktif = False


@pytest.mark.parametrize("ubah", (
    {"aktif": 1}, {"aktif": None}, {"aktif": "ya"},
    {"target_harian": -1}, {"target_harian": 6}, {"target_harian": True}, {"target_harian": "2"},
    {"target_harian": 2.0},
    {"tampil_hitung_mundur": 1}, {"tampil_hitung_mundur": "ya"},
    {"sekarang": "1800000000"}, {"sekarang": True}, {"sekarang": 1.5},
    {"oleh": None}, {"oleh": "x" * 65},
))
def test_nilai_tidak_sah_ditolak_tanpa_menulis(kon, anak, ubah):
    with pytest.raises(ValueError):
        _atur(kon, anak, **ubah)

    assert A.ambil(kon, anak) is None


def test_nilai_tidak_sah_pada_update_tidak_mengubah_baris_lama(kon, anak):
    awal = _atur(kon, anak, target_harian=1)

    with pytest.raises(ValueError):
        _atur(kon, anak, target_harian=9)

    assert A.ambil(kon, anak) == awal


def test_batas_nilai_yang_sah_diterima(kon, anak):
    hasil = _atur(kon, anak, target_harian=PK.MAKS_TARGET_HARIAN, oleh="x" * 64)

    assert hasil.target_harian == PK.MAKS_TARGET_HARIAN and len(hasil.diubah_oleh) == 64


def test_oleh_kosong_diterima(kon, anak):
    assert _atur(kon, anak, oleh="").diubah_oleh == ""


@pytest.mark.parametrize("kolom,nilai", (
    ("aktif", 2), ("target_harian", 6), ("target_harian", -1), ("tampil_hitung_mundur", 2),
    ("paket_id", ""), ("paket_id", "p" * 65), ("diubah_oleh", "x" * 65),
))
def test_check_db_menolak_nilai_liar_walau_lewat_sql_langsung(kon, anak, kolom, nilai):
    dasar = {"siswa_id": anak, "paket_id": "p", "aktif": 1, "target_harian": None,
             "tampil_hitung_mundur": None, "diubah_epoch": SEKARANG, "diubah_oleh": ""}
    dasar[kolom] = nilai

    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO lomba_penugasan VALUES (:siswa_id, :paket_id, :aktif, :target_harian, "
                    ":tampil_hitung_mundur, :diubah_epoch, :diubah_oleh)", dasar)


def test_penugasan_untuk_siswa_yang_tidak_ada_ditolak_fk(kon):
    with pytest.raises(sqlite3.IntegrityError):
        _atur(kon, 9999)


def test_hapus_siswa_ikut_menghapus_penugasannya_saja(kon, anak, anak_lain):
    _atur(kon, anak)
    _atur(kon, anak_lain, target_harian=2)
    lain = A.ambil(kon, anak_lain)

    kon.execute("DELETE FROM siswa WHERE id = ?", (anak,))

    assert A.ambil(kon, anak_lain) == lain
    assert A.ambil(kon, anak) is None
