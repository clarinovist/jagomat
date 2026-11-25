"""Langganan Latihan Harian dari akun anak mengikuti PIN tirai orang tua (butir QA 4, 25 Nov 2026; data sintetis, HTTP nyata)."""
from __future__ import annotations

import http.cookies

import pytest

import database
import pin_orang_tua_store as pin_store
import tirai_orang_tua as tirai
from harian_kit import SANDI, buat, buat_murid, hidup, jam, kirim, mati, minta_mentah, server, token  # noqa: F401

M = "/murid/langganan"


@pytest.fixture()
def murid(hidup):
    tirai._reset()
    yield buat_murid(hidup, "murid-harian-tirai", "Anak Sintetis")
    tirai._reset()


def _pasang_pin(murid):
    with database.buka() as kon:
        pin_store.simpan(kon, murid.siswa_id, "4821", 1_800_000_000)


def _jumlah_order() -> int:
    with database.buka() as kon:
        return kon.execute("SELECT COUNT(*) FROM harian_order").fetchone()[0]


def _cookie(server_uji, murid) -> str:
    kode, _isi, tajuk = minta_mentah(server_uji, "/masuk", None, {"nama": murid.akun[0], "sandi": SANDI})
    assert kode == 303
    return http.cookies.SimpleCookie(tajuk["Set-Cookie"])["osn_sesi"].value


def test_tanpa_pin_buat_tagihan_berjalan_seperti_biasa(hidup, murid):
    assert buat(hidup, murid)[0] == 303


def test_pin_terpasang_basic_tidak_bisa_buat_tagihan_dan_tanpa_efek(hidup, murid):
    _pasang_pin(murid)
    kode, isi, _ = buat(hidup, murid)
    assert kode == 403 and "PIN" in isi
    assert _jumlah_order() == 0


def test_unggah_bukti_juga_ditahan(hidup, murid):
    from harian_kit import unggah
    assert buat(hidup, murid)[0] == 303
    _pasang_pin(murid)
    assert unggah(hidup, murid)[0] == 403


def test_tirai_dibuka_sesi_cookie_mengizinkan_dan_sesi_lain_tidak(hidup, murid):
    _pasang_pin(murid)
    sesi, lain = _cookie(hidup, murid), _cookie(hidup, murid)
    data = {"paket": "bulanan"}
    kirim_cookie = lambda s: minta_mentah(hidup, M + "/buat", None, {**data, "token": token(murid.akun, "harian_buat:bulanan", s)},
                                          {"Cookie": "osn_sesi=" + s})
    assert kirim_cookie(sesi)[0] == 403
    tirai.buka(sesi, murid.id_akun, murid.siswa_id)
    assert kirim_cookie(sesi)[0] == 303
    assert kirim_cookie(lain)[0] == 403
