"""Kode anak bersama (buat, ganti, cabut) di atas penyimpanan tautan: aturan, tabrakan hash, dan rollback.

Data sepenuhnya sintetis: id akun dan anak buatan, DB tautan di tmp_path. `anak_masih_ada` diganti di tes ini; lapis
F yang nyata dibuktikan di `test_orang_tua_tautan_http.py` (anak dihapus lewat HTTP).
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import closing

import pytest

import guru_tautan_anak as anak
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import guru_tautan_kode as kode
from guru_tautan_kit import baris_tabel, keadaan_tautan

AKUN_ANAK_A = "akun_" + "a" * 32
AKUN_ANAK_C = "akun_" + "c" * 32
SIBLING_A = 1
SIBLING_C = 3
KINI = "2026-11-26T10:00:00"
SESUDAH = "2026-11-26T10:05:00"
KODE_X = "2345ABCD6789EFGH"
KODE_Y = "ABCD2345EFGH6789"
KODE_Z = "ZZZZ2345EFGH6789"
TIGA_UPAYA = 3
PEMBUAT_ORANG_TUA = {"oleh": AKUN_ANAK_A, "peran": aturan.PERAN_ORANG_TUA}


@pytest.fixture
def berkas(tmp_path, monkeypatch):
    tujuan = tmp_path / "guru-tautan-uji.db"
    monkeypatch.setenv(dasar.ENV_DB, str(tujuan))
    return tujuan


@pytest.fixture
def anak_hilang(monkeypatch):
    """Himpunan (akun_id, siswa_id) yang dianggap sudah tidak ada. Kosong = semua anak masih ada."""
    hilang = set()
    monkeypatch.setattr(anak, "anak_masih_ada", lambda akun_id, siswa_id: (akun_id, siswa_id) not in hilang)
    return hilang


def _id_aktif(akun_id: str, siswa_id: int) -> int:
    return kode.kode_aktif(akun_id, siswa_id)["id"]


def _simpan_lalu_cabut(kode_mentah: str, monkeypatch) -> None:
    """Anak C punya kode `kode_mentah` yang sudah dicabut: hash-nya ada di tabel walau tidak aktif."""
    monkeypatch.setattr(aturan, "buat_kode", lambda: kode_mentah)
    kode.buat_kode_baru(AKUN_ANAK_C, SIBLING_C, oleh=AKUN_ANAK_C, peran=aturan.PERAN_ORANG_TUA, pada=KINI)
    kode.cabut(AKUN_ANAK_C, SIBLING_C, kode_id_diharapkan=_id_aktif(AKUN_ANAK_C, SIBLING_C),
               oleh=AKUN_ANAK_C, peran=aturan.PERAN_ORANG_TUA, pada=KINI)


def test_buat_kode_baru_mengembalikan_kode_kanonik_dan_hanya_menyimpan_hash(berkas, anak_hilang):
    # Act
    mentah = kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)

    # Assert
    assert len(mentah) == aturan.PANJANG_KODE and aturan.normalkan(mentah) == mentah
    assert mentah.encode() not in berkas.read_bytes()
    assert aturan.tampilkan(mentah).encode() not in berkas.read_bytes()
    aktif = dasar.cari_kode_aktif(aturan.hash_kode(mentah))
    assert aktif is not None and aktif["akun_id"] == AKUN_ANAK_A


def test_buat_kode_baru_ditolak_bila_anak_masih_punya_kode_aktif(berkas, anak_hilang):
    kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)

    with pytest.raises(dasar.KodeSudahAda):
        kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    assert baris_tabel(berkas, "kode_anak") == 1


def test_buat_dan_ganti_ditolak_tanpa_tulis_saat_anak_sudah_tidak_ada(berkas, anak_hilang):
    kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)
    id_lama = _id_aktif(AKUN_ANAK_A, SIBLING_A)
    anak_hilang.add((AKUN_ANAK_A, SIBLING_A))

    with pytest.raises(kode.AnakTakAda):
        kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=SESUDAH, **PEMBUAT_ORANG_TUA)
    with pytest.raises(kode.AnakTakAda):
        kode.ganti_kode(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_lama, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    assert baris_tabel(berkas, "kode_anak") == 1
    assert baris_tabel(berkas, "kode_cabut") == 0


def test_cabut_tetap_bisa_saat_anak_sudah_tidak_ada(berkas, anak_hilang):
    kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)
    id_aktif = _id_aktif(AKUN_ANAK_A, SIBLING_A)
    anak_hilang.add((AKUN_ANAK_A, SIBLING_A))

    kode.cabut(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_aktif, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    assert kode.kode_aktif(AKUN_ANAK_A, SIBLING_A) is None
    assert baris_tabel(berkas, "kode_cabut") == 1


def test_ganti_mencabut_kode_lama_dan_membuat_kode_baru(berkas, anak_hilang):
    lama = kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)
    id_lama = _id_aktif(AKUN_ANAK_A, SIBLING_A)

    baru = kode.ganti_kode(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_lama, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    assert baru != lama
    assert dasar.cari_kode_aktif(aturan.hash_kode(lama)) is None
    assert dasar.cari_kode_aktif(aturan.hash_kode(baru))["akun_id"] == AKUN_ANAK_A
    assert baris_tabel(berkas, "kode_cabut") == 1


def test_ganti_dan_cabut_dengan_kode_id_basi_ditolak_tanpa_efek(berkas, anak_hilang):
    kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)
    id_lama = _id_aktif(AKUN_ANAK_A, SIBLING_A)
    kode.ganti_kode(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_lama, pada=SESUDAH, **PEMBUAT_ORANG_TUA)
    sebelum = keadaan_tautan(berkas)

    with pytest.raises(dasar.KodeBasi):
        kode.ganti_kode(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_lama, pada=SESUDAH, **PEMBUAT_ORANG_TUA)
    with pytest.raises(dasar.KodeBasi):
        kode.cabut(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_lama, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    assert keadaan_tautan(berkas) == sebelum


def test_cabut_kedua_kali_dengan_kode_id_sama_ditolak_dan_tidak_mencabut_dua_kali(berkas, anak_hilang):
    kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)
    id_aktif = _id_aktif(AKUN_ANAK_A, SIBLING_A)
    kode.cabut(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_aktif, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    with pytest.raises(dasar.KodeBasi):
        kode.cabut(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_aktif, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    assert baris_tabel(berkas, "kode_cabut") == 1


def test_tabrakan_hash_diulang_tepat_tiga_kali_lalu_galat_tertutup(berkas, anak_hilang, monkeypatch):
    # Arrange: hash KODE_X sudah ada untuk anak C (dicabut), sehingga tidak aktif tetapi tetap UNIQUE.
    _simpan_lalu_cabut(KODE_X, monkeypatch)
    panggilan = []

    def buat_kode_tabrakan():
        panggilan.append(KODE_X)
        return KODE_X

    monkeypatch.setattr(aturan, "buat_kode", buat_kode_tabrakan)

    # Act / Assert
    with pytest.raises(kode.KodeGagalDibuat):
        kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=SESUDAH, **PEMBUAT_ORANG_TUA)
    assert len(panggilan) == TIGA_UPAYA
    assert baris_tabel(berkas, "kode_anak") == 1


def test_tabrakan_lalu_kode_berikutnya_berhasil(berkas, anak_hilang, monkeypatch):
    _simpan_lalu_cabut(KODE_X, monkeypatch)
    urutan = iter([KODE_X, KODE_Y])
    panggilan = []

    def buat_kode_berurutan():
        panggilan.append(1)
        return next(urutan)

    monkeypatch.setattr(aturan, "buat_kode", buat_kode_berurutan)

    mentah = kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=SESUDAH, **PEMBUAT_ORANG_TUA)

    assert mentah == KODE_Y and len(panggilan) == 2
    assert baris_tabel(berkas, "kode_anak") == 2


def test_ganti_yang_bertabrakan_tidak_mencabut_kode_lama(berkas, anak_hilang, monkeypatch):
    # Arrange: kode A aktif; hash KODE_X sudah dipakai anak C (dicabut) sehingga ganti A akan bertabrakan.
    _simpan_lalu_cabut(KODE_X, monkeypatch)
    monkeypatch.setattr(aturan, "buat_kode", lambda: KODE_Z)
    kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)
    id_a = _id_aktif(AKUN_ANAK_A, SIBLING_A)
    monkeypatch.setattr(aturan, "buat_kode", lambda: KODE_X)

    # Act / Assert
    with pytest.raises(kode.KodeGagalDibuat):
        kode.ganti_kode(AKUN_ANAK_A, SIBLING_A, kode_id_diharapkan=id_a, pada=SESUDAH, **PEMBUAT_ORANG_TUA)
    assert _id_aktif(AKUN_ANAK_A, SIBLING_A) == id_a
    assert baris_tabel(berkas, "kode_cabut") == 1


def test_dua_buat_bersamaan_menghasilkan_tepat_satu_kode_aktif(berkas, anak_hilang):
    penghalang = threading.Barrier(2)
    hasil = []

    def pekerja():
        penghalang.wait(timeout=10)
        try:
            kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, pada=KINI, **PEMBUAT_ORANG_TUA)
            hasil.append("ok")
        except dasar.KodeSudahAda:
            hasil.append("sudah")

    utas = [threading.Thread(target=pekerja) for _ in range(2)]
    for pekerja_utas in utas:
        pekerja_utas.start()
    for pekerja_utas in utas:
        pekerja_utas.join(timeout=30)

    assert sorted(hasil) == ["ok", "sudah"]
    assert baris_tabel(berkas, "kode_anak") == 1


def test_kode_aktif_hanya_memuat_id_waktu_dan_peran(berkas, anak_hilang):
    kode.buat_kode_baru(AKUN_ANAK_A, SIBLING_A, oleh=AKUN_ANAK_A, peran=aturan.PERAN_ADMIN, pada=KINI)

    aktif = kode.kode_aktif(AKUN_ANAK_A, SIBLING_A)

    assert aktif == {"id": aktif["id"], "dibuat": KINI, "peran": aturan.PERAN_ADMIN}


def test_kode_aktif_tanpa_berkas_mengembalikan_none_dan_tidak_membuat_berkas(berkas, anak_hilang):
    assert kode.kode_aktif(AKUN_ANAK_A, SIBLING_A) is None
    assert not berkas.exists()
