"""Pesanan Peta dari akun anak mengikuti PIN tirai orang tua (butir QA 4, 25 Nov 2026; data sintetis, HTTP nyata)."""
from __future__ import annotations

import http.cookies

import pytest

import database
import pin_orang_tua_store as pin_store
import tirai_orang_tua as tirai
from pesanan_http_kit import KOSONG, keadaan_ledger, kirim, minta_mentah, server, tertutup, token  # noqa: F401
from pesanan_murid_kit import M, NAMA_ANAK_A, SANDI, buat_murid, sakelar_hidup  # noqa: F401
from pesanan_transfer_http_kit import transfer  # noqa: F401
from cek_http_kit import keluarga  # noqa: F401
from pesanan_http_kit import jam  # noqa: F401


@pytest.fixture()
def murid(transfer, sakelar_hidup):
    tirai._reset()
    yield buat_murid(transfer, "murid-pesanan-tirai", NAMA_ANAK_A)
    tirai._reset()


def _pasang_pin(murid):
    with database.buka() as kon:
        pin_store.simpan(kon, murid.siswa_id, "4821", 1_800_000_000)


def _cookie(server_uji, murid) -> str:
    kode, _isi, tajuk = minta_mentah(server_uji, "/masuk", None, {"nama": murid.akun[0], "sandi": SANDI})
    assert kode == 303
    return http.cookies.SimpleCookie(tajuk["Set-Cookie"])["osn_sesi"].value


def test_tanpa_pin_pesan_berjalan_seperti_biasa(transfer, murid):
    assert kirim(transfer, M + "/pesan", murid.akun, aksi="pesan")[0] == 303


def test_pin_terpasang_basic_tidak_bisa_memesan_dan_ledger_tetap_kosong(transfer, murid):
    _pasang_pin(murid)
    kode, isi, _ = kirim(transfer, M + "/pesan", murid.akun, aksi="pesan")
    assert kode == 403 and "PIN" in isi
    assert keadaan_ledger() == KOSONG


@pytest.mark.parametrize("rute,aksi", [("/tagihan", "tagihan"), ("/periksa", "periksa"), ("/buat", "buat"), ("/ulang", "ulang")])
def test_rute_pembayaran_lain_juga_ditahan(transfer, murid, rute, aksi):
    _pasang_pin(murid)
    assert kirim(transfer, M + rute, murid.akun, aksi=aksi)[0] == 403
    assert keadaan_ledger() == KOSONG


def test_tirai_dibuka_untuk_sesi_cookie_mengizinkan_pesan(transfer, murid):
    _pasang_pin(murid)
    sesi = _cookie(transfer, murid)
    data = {"token": token(murid.akun, "pesan", sesi)}
    kode, _, _ = minta_mentah(transfer, M + "/pesan", None, data, {"Cookie": "osn_sesi=" + sesi})
    assert kode == 403
    tirai.buka(sesi, murid.id_akun, murid.siswa_id)
    kode, _, _ = minta_mentah(transfer, M + "/pesan", None, data, {"Cookie": "osn_sesi=" + sesi})
    assert kode == 303
