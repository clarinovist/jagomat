"""Tirai halaman orang tua: status terbuka di memori proses, terikat sesi + akun + anak, umur 30 menit.

Unit murni (tanpa HTTP); perilaku lewat HTTP ada di test_orang_tua_http.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import tirai_orang_tua as tirai

TOKEN = "token-sesi-sintetis-1"
TOKEN_LAIN = "token-sesi-sintetis-2"
AKUN = "akun_" + "a1" * 16
AKUN_LAIN = "akun_" + "b2" * 16
T0 = 1_800_000_000.0


@pytest.fixture(autouse=True)
def bersih():
    tirai._reset()
    yield
    tirai._reset()


def test_umur_tirai_tiga_puluh_menit():
    assert tirai.UMUR_TIRAI_DETIK == 30 * 60


def test_tertutup_sebelum_dibuka():
    assert tirai.terbuka(TOKEN, AKUN, 1, sekarang=T0) is False


def test_terbuka_untuk_sesi_akun_dan_anak_yang_sama():
    tirai.buka(TOKEN, AKUN, 1, sekarang=T0)
    assert tirai.terbuka(TOKEN, AKUN, 1, sekarang=T0 + 1) is True


@pytest.mark.parametrize("token,akun,siswa", [
    (TOKEN_LAIN, AKUN, 1), (TOKEN, AKUN_LAIN, 1), (TOKEN, AKUN, 2),
])
def test_tidak_berlaku_untuk_sesi_akun_atau_anak_lain(token, akun, siswa):
    tirai.buka(TOKEN, AKUN, 1, sekarang=T0)
    assert tirai.terbuka(token, akun, siswa, sekarang=T0 + 1) is False


def test_kedaluwarsa_tepat_pada_batas_umur():
    tirai.buka(TOKEN, AKUN, 1, sekarang=T0)
    assert tirai.terbuka(TOKEN, AKUN, 1, sekarang=T0 + tirai.UMUR_TIRAI_DETIK - 1) is True
    assert tirai.terbuka(TOKEN, AKUN, 1, sekarang=T0 + tirai.UMUR_TIRAI_DETIK) is False


def test_jam_modul_dipakai_bila_waktu_tidak_disuntik(monkeypatch):
    monkeypatch.setattr(tirai, "_jam", lambda: T0)
    tirai.buka(TOKEN, AKUN, 1)
    monkeypatch.setattr(tirai, "_jam", lambda: T0 + tirai.UMUR_TIRAI_DETIK)
    assert tirai.terbuka(TOKEN, AKUN, 1) is False


def test_tutup_menutup_hanya_anak_itu():
    tirai.buka(TOKEN, AKUN, 1, sekarang=T0)
    tirai.buka(TOKEN, AKUN, 2, sekarang=T0)
    tirai.tutup(TOKEN, AKUN, 1)
    assert tirai.terbuka(TOKEN, AKUN, 1, sekarang=T0) is False
    assert tirai.terbuka(TOKEN, AKUN, 2, sekarang=T0) is True


def test_tutup_sesi_menutup_semua_milik_token_itu_saja():
    tirai.buka(TOKEN, AKUN, 1, sekarang=T0)
    tirai.buka(TOKEN_LAIN, AKUN, 1, sekarang=T0)
    tirai.tutup_sesi(TOKEN)
    assert tirai.terbuka(TOKEN, AKUN, 1, sekarang=T0) is False
    assert tirai.terbuka(TOKEN_LAIN, AKUN, 1, sekarang=T0) is True


@pytest.mark.parametrize("token", [None, "", 123])
def test_tanpa_token_sesi_tidak_bisa_dibuka_dan_selalu_tertutup(token):
    with pytest.raises(ValueError):
        tirai.buka(token, AKUN, 1, sekarang=T0)
    assert tirai.terbuka(token, AKUN, 1, sekarang=T0) is False


@pytest.mark.parametrize("siswa", [0, -1, "1", None, True])
def test_siswa_id_tidak_sah_ditolak(siswa):
    with pytest.raises(ValueError):
        tirai.buka(TOKEN, AKUN, siswa, sekarang=T0)


def test_token_mentah_tidak_disimpan():
    tirai.buka(TOKEN, AKUN, 1, sekarang=T0)
    assert TOKEN not in repr(tirai._TERBUKA)


def test_plafon_entri_membuang_yang_kedaluwarsa_lalu_yang_tertua(monkeypatch):
    monkeypatch.setattr(tirai, "BATAS_ENTRI", 3)
    for n in range(1, 4):
        tirai.buka(TOKEN, AKUN, n, sekarang=T0 + n)
    tirai.buka(TOKEN, AKUN, 4, sekarang=T0 + 4)
    assert len(tirai._TERBUKA) == 3
    assert tirai.terbuka(TOKEN, AKUN, 1, sekarang=T0 + 5) is False
    assert tirai.terbuka(TOKEN, AKUN, 4, sekarang=T0 + 5) is True
    tirai.buka(TOKEN, AKUN, 5, sekarang=T0 + tirai.UMUR_TIRAI_DETIK + 100)
    assert len(tirai._TERBUKA) == 1
