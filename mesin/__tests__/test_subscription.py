"""Kontrak domain murni dengan waktu/profil sintetis, bukan data akun nyata."""

from dataclasses import replace
from datetime import datetime

import pytest
import subscription as d

AKUN = "akun_" + "a" * 32
INVOICE = "inv_" + "b" * 32


def ts(tahun, bulan, hari, jam=10):
    return int(datetime(tahun, bulan, hari, jam, tzinfo=d.WIB).timestamp())


@pytest.mark.parametrize("n,promo,biasa", [(1, 15000, 35000), (2, 20000, 45000), (3, 25000, 55000)])
def test_harga_profil_bukan_login(n, promo, biasa):
    for i in range(3):
        assert d.harga(n, peserta_promo=True, periode_dibayar=i) == promo
    assert d.harga(n, peserta_promo=True, periode_dibayar=3) == biasa
    assert d.harga(n, peserta_promo=False, periode_dibayar=0) == biasa


@pytest.mark.parametrize("n", [0, -1, True, 1.0, "1", 10**20])
def test_harga_tolak_nol_float_negatif_overflow(n):
    with pytest.raises(ValueError):
        d.harga(n, peserta_promo=True, periode_dibayar=0)


def test_trial_deadline_eksklusif_dan_clock_salah():
    e = d.Enrollment(AKUN, ts(2027, 1, 1), True)
    assert e.akhir_trial - e.mulai == 30 * 24 * 3600
    assert d.akses(e, sekarang=e.akhir_trial - 1).status == "trial"
    assert d.akses(e, sekarang=e.akhir_trial).status == "expired"
    for clock in (e.mulai - 1, True, float("nan")):
        assert d.akses(e, sekarang=clock).status == "belum_terverifikasi"
    assert d.akses(None, sekarang=e.mulai).status == "belum_terverifikasi"
    assert d.akses(e, sekarang=e.mulai, terverifikasi=False).status == "belum_terverifikasi"


@pytest.mark.parametrize("tahun,hari", [(2027, 28), (2028, 29)])
def test_jangkar_31_tidak_hilang_pada_februari(tahun, hari):
    e = d.Enrollment(AKUN, ts(tahun, 1, 1), True)
    pertama = d.periode_baru(sekarang=ts(tahun, 1, 31), enrollment=e)
    assert pertama == d.Periode(ts(tahun, 1, 31), ts(tahun, 2, hari), 31)
    kedua = d.periode_baru(sekarang=ts(tahun, 2, 20), enrollment=e, sebelumnya=pertama)
    assert kedua == d.Periode(ts(tahun, 2, hari), ts(tahun, 3, 31), 31)
    ketiga = d.periode_baru(sekarang=kedua.akhir, enrollment=e, sebelumnya=kedua)
    assert ketiga.akhir == ts(tahun, 4, 30)
    jeda = d.periode_baru(sekarang=ts(tahun, 5, 7), enrollment=e, sebelumnya=ketiga)
    assert jeda == d.Periode(ts(tahun, 5, 7), ts(tahun, 6, 7), 7)


def test_trial_promo_paid_expired_dipisah_invoice():
    e = d.Enrollment(AKUN, ts(2027, 1, 1), True)
    grants = []
    sekarang = e.akhir_trial
    for i in range(1, 5):
        periode = d.periode_baru(sekarang=sekarang, enrollment=e, sebelumnya=grants[-1].periode if grants else None)
        grants.append(d.Grant(AKUN, "inv_" + str(i) * 32, i, periode, (1, 2), i <= 3))
        assert d.akses(e, grants, sekarang=periode.mulai).status == ("promo" if i <= 3 else "paid")
        assert d.akses(e, grants, sekarang=periode.akhir).status == "expired"
        sekarang = periode.akhir + 7 * 86400  # Jeda tidak reset promo.
    assert d.akses(e, grants, sekarang=e.mulai).status == "trial"
    assert d.akses(e, grants, sekarang=grants[-1].periode.mulai).profil == (1, 2)
    assert d.akses(e, grants + [grants[0]], sekarang=sekarang).status == "belum_terverifikasi"
    assert d.akses(e, [replace(grants[0], akun_id="akun_" + "c" * 32)], sekarang=e.mulai).status == "belum_terverifikasi"


def test_semua_sakelar_off_tanpa_env_override(monkeypatch):
    for nama in ("fondasi", "buat_pembayaran", "rekonsiliasi", "penegakan"):
        monkeypatch.setenv("LANGGANAN_" + nama.upper(), "1")
        with pytest.raises(d.FiturNonaktif):
            d.SAKELAR.wajib(nama)
    assert d.SAKELAR == d.Sakelar(False, False, False, False)
    with pytest.raises(d.FiturNonaktif):
        d.Sakelar(fondasi="1").wajib("fondasi")
