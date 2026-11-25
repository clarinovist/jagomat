"""Katalog Paket Belajar 1 Bulan: harga, deposit Peta (tanpa diskon anak kedua), rentang kode unik."""
import itertools

import pytest

import kelas_dasar as kd
import paket_belajar_katalog as k

RENTANG_KODE = 999
HARGA_PRODUK_LAIN = (49_000, 39_000, 349_000)  # Peta (+kode 1..999), Latihan Harian bulanan, tahunan
DEPOSIT_PETA = 49_000
PAKET_DAN_DEPOSIT = tuple(itertools.product((k.KODE_PRIVATE, k.KODE_MINI), (False, True)))


def _rentang_total(nominal):
    return set(range(nominal + kd.KODE_MIN, nominal + kd.KODE_MAKS + 1))


def _nominal_semua_kombinasi():
    return {k.hitung_rincian(kode, deposit_aktif=dep).nominal for kode, dep in PAKET_DAN_DEPOSIT}


def test_private_80rb_x_8_pertemuan_online_60_menit():
    p = k.ambil(k.KODE_PRIVATE)
    assert (p.harga, p.pertemuan, p.menit, p.mode, p.kuota) == (640_000, 8, 60, k.MODE_ONLINE, None)


def test_mini_300rb_offline_60_menit_kuota_5():
    p = k.ambil(k.KODE_MINI)
    assert (p.harga, p.pertemuan, p.menit, p.mode, p.kuota) == (300_000, 8, 60, k.MODE_OFFLINE, 5)


def test_kode_tak_dikenal_ditolak():
    with pytest.raises(ValueError):
        k.ambil("harian")


@pytest.mark.parametrize("kode,deposit,diharapkan", [
    (k.KODE_PRIVATE, False, 640_000),
    (k.KODE_PRIVATE, True, 591_000),
    (k.KODE_MINI, False, 300_000),
    (k.KODE_MINI, True, 251_000),
])
def test_nominal_sesuai_keputusan_pemilik(kode, deposit, diharapkan):
    assert k.hitung_rincian(kode, deposit_aktif=deposit).nominal == diharapkan


def test_deposit_memotong_bulan_pertama_mini_tanpa_diskon():
    r = k.hitung_rincian(k.KODE_MINI, deposit_aktif=True)
    assert (r.potongan_deposit, r.potongan_diskon, r.nominal) == (DEPOSIT_PETA, 0, 251_000)


def test_rincian_konsisten_harga_dikurangi_deposit_tanpa_diskon():
    for kode, dep in PAKET_DAN_DEPOSIT:
        r = k.hitung_rincian(kode, deposit_aktif=dep)
        assert r.potongan_diskon == 0
        assert r.nominal == r.harga_dasar - r.potongan_deposit - r.potongan_diskon > 0


def test_diskon_anak_kedua_sudah_dihapus_dari_katalog():
    assert not hasattr(k, "DISKON_ANAK_KEDUA_PERSEN")
    with pytest.raises(TypeError):
        k.hitung_rincian(k.KODE_MINI, deposit_aktif=False, anak_kedua=True)


@pytest.mark.parametrize("salah", [1, 0, None, "ya", ""])
def test_penanda_deposit_harus_bool_ketat(salah):
    with pytest.raises(ValueError):
        k.hitung_rincian(k.KODE_MINI, deposit_aktif=salah)


def test_rentang_nominal_tak_beririsan_lintas_produk():
    """Total transfer = nominal + kode unik 1..999: semua nominal harus berjarak >= 1000."""
    nominal = _nominal_semua_kombinasi()
    semua = sorted(nominal | set(HARGA_PRODUK_LAIN))
    for kecil, besar in zip(semua, semua[1:]):
        assert besar - kecil > RENTANG_KODE, (kecil, besar)


def test_kode_unik_mini_tepat_di_300rb_dan_251rb():
    """Regression: total Mini tanpa deposit 300.001-300.999, dengan deposit 251.001-251.999."""
    assert _rentang_total(300_000) == set(range(300_001, 300_999 + 1))
    assert _rentang_total(251_000) == set(range(251_001, 251_999 + 1))


def test_kode_unik_mini_tidak_tumpang_tindih_produk_lain():
    """Gabungan rentang total semua nominal tidak boleh bertabrakan: jumlahnya sama dengan nominal x 999."""
    semua = _nominal_semua_kombinasi() | set(HARGA_PRODUK_LAIN)
    gabungan = set().union(*(_rentang_total(n) for n in semua))
    assert len(gabungan) == len(semua) * RENTANG_KODE
