"""Kontrak paket v2 tanpa DB, provider, clock sistem atau perubahan tarif v1."""
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

import subscription as lama
import subscription_packages as paket


def waktu(tahun=2028, bulan=1, hari=31):
    return int(datetime(tahun, bulan, hari, 12, 30, tzinfo=paket.WIB).timestamp())


@pytest.mark.parametrize("kode,penagihan,normal,promo", [
    ("jago", "bulanan", 29000, 25000),
    ("jago_pro", "bulanan", 59000, 49000),
    ("jago", "tahunan", 290000, 250000),
    ("jago_pro", "tahunan", 590000, 490000),
])
@pytest.mark.parametrize("jumlah", [1, 2, 3])
def test_harga_normal_promo_tambahan_profil(kode, penagihan, normal, promo, jumlah):
    tambahan = (jumlah - 1) * (10000 if penagihan == "bulanan" else 100000)
    hasil = paket.penawaran(kode, penagihan, jumlah, peserta_promo=True, periode_dibayar=0)
    assert hasil.rupiah == promo + tambahan
    assert hasil.normal == normal + tambahan
    assert hasil.promo is True and hasil.versi == paket.VERSI
    tanpa = paket.penawaran(kode, penagihan, jumlah, peserta_promo=False, periode_dibayar=0)
    assert tanpa.rupiah == normal + tambahan and tanpa.promo is False
    assert hasil == paket.penawaran(kode, penagihan, jumlah, peserta_promo=True, periode_dibayar=0)


@pytest.mark.parametrize("kode", ["jago", "jago_pro"])
@pytest.mark.parametrize("penagihan,batas", [("bulanan", 3), ("tahunan", 1)])
def test_promo_tepat_jatah_periode_dibayar(kode, penagihan, batas):
    for urutan in range(6):
        h = paket.penawaran(kode, penagihan, 1, peserta_promo=True, periode_dibayar=urutan)
        assert h.promo is (urutan < batas)
        assert (h.rupiah < h.normal) is (urutan < batas)


@pytest.mark.parametrize("ubah", [
    {"kode": "pro"}, {"kode": None}, {"kode": True},
    {"penagihan": "yearly"}, {"penagihan": True},
    {"jumlah_profil": 0}, {"jumlah_profil": -1}, {"jumlah_profil": True},
    {"jumlah_profil": "2"}, {"jumlah_profil": 2.0}, {"jumlah_profil": 1000},
    {"peserta_promo": 1}, {"peserta_promo": "true"},
    {"periode_dibayar": -1}, {"periode_dibayar": True}, {"periode_dibayar": 0.0},
    {"versi": "langganan-v1"}, {"versi": None},
])
def test_input_harga_tidak_sah_ditolak(ubah):
    args = dict(kode="jago", penagihan="bulanan", jumlah_profil=1,
                peserta_promo=True, periode_dibayar=0)
    args.update(ubah)
    with pytest.raises(ValueError):
        paket.penawaran(**args)


def test_katalog_dan_penawaran_immutable():
    with pytest.raises(FrozenInstanceError):
        paket.PAKET[0].bulanan = 1
    with pytest.raises(FrozenInstanceError):
        paket.PAKET[1].kuota.foto = 999
    h = paket.penawaran("jago", "bulanan", 1, peserta_promo=False, periode_dibayar=0)
    with pytest.raises(FrozenInstanceError):
        h.rupiah = 1


def test_tarif_v1_tetap_identik():
    assert lama.VERSI_ATURAN == "langganan-v1"
    for jumlah, promo, normal in ((1, 15000, 35000), (2, 20000, 45000), (3, 25000, 55000)):
        assert lama.harga(jumlah, peserta_promo=True, periode_dibayar=0) == promo
        assert lama.harga(jumlah, peserta_promo=True, periode_dibayar=3) == normal


def test_kalender_jangkar_bulanan_dan_tahunan():
    assert paket.akhir_periode(waktu(), "bulanan") == waktu(2028, 2, 29)
    assert paket.akhir_periode(waktu(), "bulanan", urutan=2) == waktu(2028, 3, 31)
    mulai = waktu(2028, 2, 29)
    assert paket.akhir_periode(mulai, "tahunan") == waktu(2029, 2, 28)
    assert paket.akhir_periode(mulai, "tahunan", urutan=4) == waktu(2032, 2, 29)
    assert paket.akhir_periode(waktu(2026, 12, 31), "bulanan") == waktu(2027, 1, 31)


@pytest.mark.parametrize("mulai,urutan", [(True, 1), (-1, 1), (0, True), (0, -1),
                                          (paket.BATAS_WAKTU, 1), (0, 120001)])
def test_kalender_menolak_waktu_rusak_dan_overflow(mulai, urutan):
    with pytest.raises(ValueError):
        paket.batas_bulan(mulai, urutan)


@pytest.mark.parametrize("penagihan", ["bulanan", "tahunan"])
@pytest.mark.parametrize("kode,balasan,foto", [("jago", 0, 0), ("jago_pro", 50, 5)])
def test_kuota_perbulan_bukan_sekaligus_tahunan(kode, balasan, foto, penagihan):
    mulai = waktu()
    for i in range(paket.jumlah_bulan(penagihan)):
        kiri = paket.batas_bulan(mulai, i)
        kanan = paket.batas_bulan(mulai, i + 1)
        for kini in (kiri, kanan - 1):
            j = paket.jendela_kuota(kode, penagihan, mulai, sekarang=kini)
            assert (j.mulai, j.akhir) == (kiri, kanan)
            assert (j.kuota.balasan, j.kuota.foto) == (balasan, foto)
    assert paket.jendela_kuota(kode, penagihan, mulai, sekarang=mulai-1) is None
    assert paket.jendela_kuota(kode, penagihan, mulai,
                               sekarang=paket.akhir_periode(mulai, penagihan)) is None


def test_kuota_perpanjangan_menjaga_jangkar_asli():
    mulai = waktu()
    j = paket.jendela_kuota("jago_pro", "bulanan", mulai, urutan=2, sekarang=waktu(2028, 3, 30))
    assert (j.mulai, j.akhir) == (waktu(2028, 2, 29), waktu(2028, 3, 31))
    mulai = waktu(2028, 2, 29)
    j = paket.jendela_kuota("jago_pro", "tahunan", mulai, urutan=4, sekarang=waktu(2032, 2, 28))
    assert j.akhir == waktu(2032, 2, 29)
    assert paket.jendela_kuota("jago_pro", "tahunan", mulai, urutan=4,
                                sekarang=waktu(2032, 2, 29)) is None
    for urutan in (0, -1, True):
        with pytest.raises(ValueError):
            paket.jendela_kuota("jago_pro", "bulanan", mulai, urutan=urutan, sekarang=mulai)


def test_trial_tepat30hari_bukan_bulan_kalender():
    mulai = waktu(2028, 2, 1)
    akhir = mulai + 30 * 86400
    assert paket.akhir_coba(mulai) == akhir
    for kini in (mulai, akhir-1):
        j = paket.jendela_coba(mulai, sekarang=kini)
        assert j.kuota == paket.Kuota(10, 2)
        assert (j.mulai, j.akhir) == (mulai, akhir)
    assert paket.jendela_coba(mulai, sekarang=mulai-1) is None
    assert paket.jendela_coba(mulai, sekarang=akhir) is None


@pytest.mark.parametrize("delta,status", [(0, "dalam_jendela"), (7*86400-1, "dalam_jendela"),
                                         (7*86400, "di_luar_jendela"), (-1, "perlu_diperiksa")])
def test_refund_tahunan_deadline_eksklusif(delta, status):
    mulai = waktu()
    assert paket.status_refund("tahunan", mulai, diajukan_pada=mulai+delta) == status


def test_refund_bukan_pembayaran_atau_timestamp_buatan():
    assert paket.status_refund("tahunan", None, diajukan_pada=waktu()) == "perlu_diperiksa"
    assert paket.status_refund("bulanan", waktu(), diajukan_pada=waktu()) == "bukan_tahunan"
    for nilai in (True, -1, "0"):
        with pytest.raises(ValueError):
            paket.status_refund("tahunan", nilai, diajukan_pada=waktu())
        with pytest.raises(ValueError):
            paket.status_refund("tahunan", waktu(), diajukan_pada=nilai)
    with pytest.raises(ValueError):
        paket.status_refund("tahunan", paket.BATAS_WAKTU, diajukan_pada=paket.BATAS_WAKTU)
