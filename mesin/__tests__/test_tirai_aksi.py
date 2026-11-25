"""Gerbang tirai PIN untuk tindakan murid (butir QA 4, 25 Nov 2026; data sintetis, tingkat domain)."""
import sqlite3
from types import SimpleNamespace

import pytest

import database
import pin_orang_tua_store as pin_store
import tirai_aksi
import tirai_orang_tua as tirai

PIN = "4821"
AKUN = "akun_" + "1" * 32


@pytest.fixture()
def anak(tmp_path, monkeypatch):
    jalur = tmp_path / "belajar.db"
    database.siapkan(jalur)
    monkeypatch.setattr(database, "BAWAAN", jalur)
    with database.buka(jalur) as kon:
        siswa = database.tambah_siswa(kon, "Anak Sintetis", "P3", pemilik="koordinator-sintetis")
        kon.commit()
    tirai._reset()
    yield siswa
    tirai._reset()


def _pasang_pin(siswa):
    with database.buka() as kon:
        pin_store.simpan(kon, siswa, PIN, 1_800_000_000)


def _penangan(token):
    return SimpleNamespace(_ambil_token=lambda: token)


def _principal(metode="cookie"):
    return SimpleNamespace(id_akun=AKUN, metode=metode)


def test_tanpa_pin_tidak_tertutup(anak):
    assert tirai_aksi.tertutup(_penangan("sesi"), _principal(), anak) is False


def test_pin_dan_tirai_tertutup_menolak(anak):
    _pasang_pin(anak)
    assert tirai_aksi.tertutup(_penangan("sesi"), _principal(), anak) is True
    assert tirai_aksi.tertutup(_penangan(None), _principal(), anak) is True


def test_tirai_terbuka_untuk_sesi_cookie_yang_sama_saja(anak):
    _pasang_pin(anak)
    tirai.buka("sesi-a", AKUN, anak)
    assert tirai_aksi.tertutup(_penangan("sesi-a"), _principal(), anak) is False
    assert tirai_aksi.tertutup(_penangan("sesi-lain"), _principal(), anak) is True


def test_principal_basic_tidak_memakai_token_cookie_yang_terbuka(anak):
    _pasang_pin(anak)
    tirai.buka("sesi-mati", AKUN, anak)
    assert tirai_aksi.tertutup(_penangan("sesi-mati"), _principal("basic"), anak) is True


def test_pin_tak_terbaca_gagal_tertutup(anak, monkeypatch):
    def rusak(*a, **k):
        raise sqlite3.OperationalError("db rusak")

    monkeypatch.setattr(pin_store, "ada_pin", rusak)
    assert tirai_aksi.tertutup(_penangan("sesi"), _principal(), anak) is True
