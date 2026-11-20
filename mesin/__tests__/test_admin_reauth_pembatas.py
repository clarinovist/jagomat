"""Pembatas sandi ulang aksi berisiko (`admin_http._reauth`): 5 gagal / 15 menit per akun admin.

Memakai `laju_masuk` (pembatas login) pada ruang kunci tersendiri. Jam disuntik lewat argumen `sekarang`.
Data sintetis; mutation di test_admin_pesanan_keamanan_mutation.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import admin_http  # noqa: E402
import admin_pesanan_http as ap  # noqa: E402
import auth  # noqa: E402
import laju_masuk  # noqa: E402
import sessions  # noqa: E402
from admin_pesanan_kit import (  # noqa: E402
    REFUND, baris_refund, login_admin, minta_admin, order_lunas, token_langsung,
)
from cek_http_kit import AKUN_ADMIN, SANDI_ADMIN, server  # noqa: E402,F401
from pesanan_http_kit import bayar, jam, keluarga, tertutup  # noqa: E402,F401

SANDI_DUA = "sandi-pengelola-dua-456"
T0 = 1_000_000.0
SALAH = "sandi-yang-salah"


@pytest.fixture()
def dua_admin(server):
    auth.tambah_akun("pengelola-dua", SANDI_DUA, "admin")
    satu = sessions.principal_basic(*AKUN_ADMIN)
    dua = sessions.principal_basic("pengelola-dua", SANDI_DUA)
    assert satu is not None and dua is not None
    return satu, dua


def _gagal(principal, kali, sekarang=T0):
    for _ in range(kali):
        assert admin_http._reauth(principal, SALAH, sekarang) is False


def test_sandi_benar_diterima_selama_belum_mencapai_batas(dua_admin):
    satu, _ = dua_admin
    _gagal(satu, laju_masuk.BATAS_GAGAL - 1)
    assert admin_http._reauth(satu, SANDI_ADMIN, T0) is True


def test_percobaan_keenam_ditolak_walau_sandi_benar_dan_pbkdf2_tidak_dijalankan(dua_admin, monkeypatch):
    satu, _ = dua_admin
    _gagal(satu, laju_masuk.BATAS_GAGAL)
    panggilan = []
    asli = auth.autentikasi
    monkeypatch.setattr(auth, "autentikasi", lambda *a, **k: panggilan.append(a) or asli(*a, **k))
    assert admin_http._reauth(satu, SANDI_ADMIN, T0 + 1) is False
    assert panggilan == []


def test_setelah_jendela_lewat_sandi_benar_diterima_lagi(dua_admin):
    satu, _ = dua_admin
    _gagal(satu, laju_masuk.BATAS_GAGAL)
    assert admin_http._reauth(satu, SANDI_ADMIN, T0 + laju_masuk.BATAS_JENDELA - 1) is False
    assert admin_http._reauth(satu, SANDI_ADMIN, T0 + laju_masuk.BATAS_JENDELA + 1) is True


def test_sukses_mengosongkan_hitungan_gagal(dua_admin):
    satu, _ = dua_admin
    _gagal(satu, laju_masuk.BATAS_GAGAL - 1)
    assert admin_http._reauth(satu, SANDI_ADMIN, T0) is True
    _gagal(satu, laju_masuk.BATAS_GAGAL - 1, T0 + 1)          # tanpa reset ini sudah melewati batas
    assert admin_http._reauth(satu, SANDI_ADMIN, T0 + 2) is True


def test_akun_admin_lain_tidak_terpengaruh(dua_admin):
    satu, dua = dua_admin
    _gagal(satu, laju_masuk.BATAS_GAGAL)
    assert admin_http._reauth(satu, SANDI_ADMIN, T0) is False
    assert admin_http._reauth(dua, SANDI_DUA, T0) is True


def test_sandi_milik_akun_lain_dihitung_gagal_pada_akun_pemanggil(dua_admin):
    satu, _ = dua_admin
    for _ in range(laju_masuk.BATAS_GAGAL):
        assert admin_http._reauth(satu, SANDI_DUA, T0) is False      # sandi sah, tapi bukan akun ini
    assert admin_http._reauth(satu, SANDI_ADMIN, T0) is False


def test_kunci_reauth_tidak_menabrak_kunci_login_nama_yang_sama(dua_admin):
    satu, _ = dua_admin
    _gagal(satu, laju_masuk.BATAS_GAGAL)
    assert laju_masuk.sedang_diblokir(satu.pengguna, "127.0.0.1", T0) is False


def test_http_refund_ditolak_403_tanpa_efek_setelah_lima_sandi_ulang_gagal(bayar):
    admin = login_admin(bayar)
    order, _trx = order_lunas(bayar, admin)
    laju_masuk._reset()
    for _ in range(laju_masuk.BATAS_GAGAL):
        data = {**token_langsung(admin, ap.AKSI_REFUND, order["order_id"]), "catatan_kode": "kebijakan",
                "reauth": SALAH}
        assert minta_admin(bayar, REFUND, admin, data)[0] == 403
    data = {**token_langsung(admin, ap.AKSI_REFUND, order["order_id"]), "catatan_kode": "kebijakan"}
    assert minta_admin(bayar, REFUND, admin, data)[0] == 403         # sandi benar, tetap diblokir
    assert baris_refund() == []
    laju_masuk._reset()                                              # jendela lewat (state in-memory dibuang)
    assert minta_admin(bayar, REFUND, admin, data)[0] == 303
    assert len(baris_refund()) == 1
