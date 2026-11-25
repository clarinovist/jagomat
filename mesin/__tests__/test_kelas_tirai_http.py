"""Tindakan di /murid/paket mengikuti PIN tirai orang tua (butir QA #4, 25 Nov 2026; data sintetis, HTTP nyata).

Daftar paket, ganti paket, pilih jadwal, dan unggah bukti adalah keputusan orang tua. Bila anak punya PIN tirai dan tirai tertutup untuk
sesi itu (termasuk sesi Basic, yang tidak pernah membuka tirai), tindakan ditolak 403 tanpa efek. Tanpa PIN perilaku tidak berubah.
"""
from __future__ import annotations

import http.cookies

import pytest

import admin_store
import database
import jadwal_store as js
import kelas_murid_http as KM
import pin_orang_tua_store as pin_store
import schema_jadwal
import tirai_orang_tua as tirai
from bukti_kit import JPEG
from kelas_http_kit import (ADMIN, AWAL, M, baca_admin, buat, buat_dan_unggah, buat_murid, halaman, hitung, jam,  # noqa: F401
                            kidup, kirim, kmati, minta_mentah, server, token, unggah)
from harian_kit import SANDI

PIN = "4821"


@pytest.fixture()
def murid(kidup):
    schema_jadwal.migrasikan(admin_store.BAWAAN)
    tirai._reset()
    yield buat_murid(kidup, "murid-tirai", "Anak Sintetis")
    tirai._reset()


def _pasang_pin(murid):
    with database.buka() as kon:
        pin_store.simpan(kon, murid.siswa_id, PIN, 1_800_000_000)


def _cookie(server_uji, murid) -> str:
    kode, _isi, tajuk = minta_mentah(server_uji, "/masuk", None, {"nama": murid.akun[0], "sandi": SANDI})
    assert kode == 303
    return http.cookies.SimpleCookie(tajuk["Set-Cookie"])["osn_sesi"].value


def _kirim_cookie(server_uji, murid, sesi, jalur, aksi, data):
    data = {**data, "token": token(murid.akun, aksi, sesi)}
    return minta_mentah(server_uji, jalur, None, data, {"Cookie": "osn_sesi=" + sesi})


def test_tanpa_pin_tindakan_berjalan_seperti_biasa(kidup, murid):
    assert buat(kidup, murid, "mini")[0] == 303


def test_pin_terpasang_basic_tidak_bisa_daftar_paket_dan_tanpa_efek(kidup, murid):
    _pasang_pin(murid)
    sebelum = hitung()
    kode, isi, _ = buat(kidup, murid, "mini")
    assert kode == 403 and "PIN" in isi
    assert hitung() == sebelum


def test_halaman_paket_memberi_kabar_terkunci_dan_menyembunyikan_pilihan_jadwal(kidup, murid):
    _pasang_pin(murid)
    isi = halaman(kidup, murid)
    assert "terkunci PIN" in isi and "Pilih jadwal kelas" not in isi


def test_ganti_jadwal_dan_bukti_juga_ditahan_saat_tirai_tertutup(kidup, murid, jam):
    assert buat(kidup, murid, "mini")[0] == 303
    _pasang_pin(murid)
    jam.maju_jam(1)
    sebelum = hitung()
    assert kirim(kidup, M + "/ganti", murid, {"token": token(murid.akun, "kelas_ganti:private"), "kode": "private"})[0] == 403
    assert kirim(kidup, M + "/jadwal", murid, {"token": token(murid.akun, "jadwal_pilih:klp_" + "0" * 32),
                                               "kelompok": "klp_" + "0" * 32})[0] == 403
    assert unggah(kidup, murid)[0] == 403
    assert hitung() == sebelum


def test_tirai_dibuka_untuk_sesi_cookie_mengizinkan_tindakan_dan_tidak_untuk_sesi_lain(kidup, murid):
    _pasang_pin(murid)
    sesi = _cookie(kidup, murid)
    assert _kirim_cookie(kidup, murid, sesi, M + "/buat", "kelas_buat:mini", {"kode": "mini"})[0] == 403   # belum dibuka
    tirai.buka(sesi, murid.id_akun, murid.siswa_id)
    assert _kirim_cookie(kidup, murid, sesi, M + "/buat", "kelas_buat:mini", {"kode": "mini"})[0] == 303   # dibuka
    lain = _cookie(kidup, murid)
    assert _kirim_cookie(kidup, murid, lain, M + "/ganti", "kelas_ganti:private", {"kode": "private"})[0] == 403


def test_cookie_mati_bersama_basic_tidak_mewarisi_tirai_yang_terbuka(kidup, murid):
    _pasang_pin(murid)
    tirai.buka("kuki-sesi-yang-sudah-dicabut", murid.id_akun, murid.siswa_id)
    mati = "kuki-sesi-yang-sudah-dicabut"
    data = {"token": token(murid.akun, "kelas_buat:mini", mati), "kode": "mini"}      # token form sah: yang menolak harus tirai
    kode, isi, _ = minta_mentah(kidup, M + "/buat", murid.akun, data, {"Cookie": "osn_sesi=" + mati})
    assert kode == 403 and "PIN" in isi


def test_pin_tidak_terbaca_gagal_tertutup(kidup, murid, monkeypatch):
    import sqlite3

    def rusak(*a, **k):
        raise sqlite3.OperationalError("db rusak")

    monkeypatch.setattr(KM.pin_store, "ada_pin", rusak)
    assert buat(kidup, murid, "mini")[0] == 403
