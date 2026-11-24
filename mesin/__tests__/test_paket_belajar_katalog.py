"""Katalog Paket Belajar 1 Bulan: harga, aturan deposit/diskon anak kedua, rentang kode unik."""
import itertools

import pytest

import paket_belajar_katalog as k

RENTANG_KODE = 999
HARGA_PRODUK_LAIN = (49_000, 39_000, 349_000)  # Peta (+kode 1..999), Latihan Harian bulanan, tahunan


def test_private_80rb_x_8_pertemuan_online_60_menit():
    p = k.ambil(k.KODE_PRIVATE)
    assert (p.harga, p.pertemuan, p.menit, p.mode, p.kuota) == (640_000, 8, 60, k.MODE_ONLINE, None)


def test_mini_250rb_offline_60_menit_kuota_5():
    p = k.ambil(k.KODE_MINI)
    assert (p.harga, p.pertemuan, p.menit, p.mode, p.kuota) == (250_000, 8, 60, k.MODE_OFFLINE, 5)


def test_kode_tak_dikenal_ditolak():
    with pytest.raises(ValueError):
        k.ambil("harian")


@pytest.mark.parametrize("kode,deposit,kedua,diharapkan", [
    (k.KODE_PRIVATE, False, False, 640_000),
    (k.KODE_PRIVATE, True, False, 591_000),
    (k.KODE_PRIVATE, False, True, 512_000),
    (k.KODE_MINI, False, False, 250_000),
    (k.KODE_MINI, True, False, 201_000),
    (k.KODE_MINI, False, True, 200_000),
])
def test_nominal_sesuai_keputusan_pemilik(kode, deposit, kedua, diharapkan):
    assert k.hitung_rincian(kode, deposit_aktif=deposit, anak_kedua=kedua).nominal == diharapkan


def test_deposit_menang_atas_anak_kedua_dan_tidak_menumpuk():
    r = k.hitung_rincian(k.KODE_MINI, deposit_aktif=True, anak_kedua=True)
    assert (r.potongan_deposit, r.potongan_diskon, r.nominal) == (49_000, 0, 201_000)


def test_rincian_konsisten_harga_dikurangi_potongan():
    for kode, dep, kedua in itertools.product((k.KODE_PRIVATE, k.KODE_MINI), (False, True), (False, True)):
        r = k.hitung_rincian(kode, deposit_aktif=dep, anak_kedua=kedua)
        assert r.nominal == r.harga_dasar - r.potongan_deposit - r.potongan_diskon > 0


@pytest.mark.parametrize("salah", [1, 0, None, "ya", ""])
def test_penanda_harus_bool_ketat(salah):
    with pytest.raises(ValueError):
        k.hitung_rincian(k.KODE_MINI, deposit_aktif=salah, anak_kedua=False)
    with pytest.raises(ValueError):
        k.hitung_rincian(k.KODE_MINI, deposit_aktif=False, anak_kedua=salah)


def test_rentang_nominal_tak_beririsan_lintas_produk():
    """Total transfer = nominal + kode unik 1..999: semua nominal harus berjarak >= 1000."""
    nominal = {
        k.hitung_rincian(kode, deposit_aktif=dep, anak_kedua=kedua).nominal
        for kode, dep, kedua in itertools.product((k.KODE_PRIVATE, k.KODE_MINI), (False, True), (False, True))
    }
    semua = sorted(nominal | set(HARGA_PRODUK_LAIN))
    for kecil, besar in zip(semua, semua[1:]):
        assert besar - kecil > RENTANG_KODE, (kecil, besar)
