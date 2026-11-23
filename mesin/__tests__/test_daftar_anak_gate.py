"""Gerbang pendaftaran akun anak: sakelar DAFTAR_AKUN_ANAK + lembaga antrean dari env (fail-closed)."""
import pytest

import daftar_anak_gate as gate
import database
import lembaga_store


@pytest.fixture
def db(tmp_path, monkeypatch):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.delenv("DAFTAR_AKUN_ANAK", raising=False)
    monkeypatch.delenv("OSN_LEMBAGA_ANTREAN", raising=False)
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada.db"))
    with database.buka(jalur) as kon:
        lembaga_store.buat_lembaga(kon, nama="Jagomat", pemilik="koordinator-uji")
    return jalur


def test_sakelar_bawaan_mati_dan_mode_lama(db):
    assert gate.aktif() is False
    assert gate.keadaan(db) == gate.Keadaan(gate.LAMA)


@pytest.mark.parametrize("nilai,hasil", [("1", True), (" 1 ", True), ("0", False), ("", False), ("true", False)])
def test_hanya_nilai_satu_menyalakan_sakelar(db, monkeypatch, nilai, hasil):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", nilai)
    assert gate.aktif() is hasil


def test_sakelar_mati_mengabaikan_lembaga_antrean(db, monkeypatch):
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "1")
    assert gate.keadaan(db).mode == gate.LAMA


def test_sakelar_hidup_lembaga_valid_mode_anak(db, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "1")
    assert gate.keadaan(db) == gate.Keadaan(gate.ANAK, 1)


@pytest.mark.parametrize("nilai", [None, "", " ", "0", "-1", "01", "1.0", "abc", "1 ", " 1", "99999999999", "2",
                                   chr(0x661)])
def test_sakelar_hidup_lembaga_tidak_sah_atau_tidak_ada_belum_siap(db, monkeypatch, nilai):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    if nilai is not None:
        monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", nilai)
    assert gate.keadaan(db) == gate.Keadaan(gate.BELUM_SIAP)


def test_db_tidak_terbaca_belum_siap(tmp_path, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "1")
    monkeypatch.setenv("SAKELAR_BERKAS_DB", str(tmp_path / "tidak-ada.db"))
    rusak = tmp_path / "rusak.db"
    rusak.write_bytes(b"bukan sqlite" * 50)
    assert gate.keadaan(rusak).mode == gate.BELUM_SIAP


def test_env_dibaca_tiap_panggilan(db, monkeypatch):
    monkeypatch.setenv("DAFTAR_AKUN_ANAK", "1")
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "1")
    assert gate.keadaan(db).mode == gate.ANAK
    monkeypatch.setenv("OSN_LEMBAGA_ANTREAN", "7")
    assert gate.keadaan(db).mode == gate.BELUM_SIAP


def test_koordinator_antrean_nama_pemilik_atau_none(db):
    with database.buka(db) as kon:
        assert gate.koordinator_antrean(kon, 1) == "koordinator-uji"
        assert gate.koordinator_antrean(kon, 2) is None
