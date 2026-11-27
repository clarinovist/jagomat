"""Potongan deposit tagihan kelas = nominal bayar order Peta (`pesanan_order.rupiah`); selain nilai CHECK -> fail-closed.

K4 (keputusan Pemilik 27 Nov 2026). Data sintetis (kelas_kit, pesanan_kit). Mutasi guard `nominal_deposit` dijalankan SEKALI
di salinan source terisolasi (harian_mutasi_kit): merah saat guard mati, hijau setelah dipulihkan.
"""
from pathlib import Path

import pytest

import kelas_dasar as k
import kelas_rincian
import kelas_store
import pesanan_dasar
import pesanan_kit
from harian_mutasi_kit import uji_mutasi
from kelas_kit import AKUN_A, KINI, db_kelas, kon_kelas, peta_lunas, tagih  # noqa: F401

TES_INI = "test_kelas_tagihan_nominal.py"
SALIN_TES = tuple(sorted(p.name for p in Path(__file__).parent.glob("*_kit.py"))) + ("conftest.py", TES_INI)
NOMINAL_TAK_SESUAI = 59_000
TES_GUARD = "test_nominal_order_peta_tak_sesuai_gagal_tertutup_tanpa_tagihan"


def _peta_lunas_dengan_nominal(kon, monkeypatch, rupiah: int) -> str:
    """Order Peta lunas untuk anak 1 dengan `pesanan_order.rupiah` = `rupiah`. Hanya di tes ini (katalog tidak berubah)."""
    monkeypatch.setattr(pesanan_dasar, "RUPIAH_PAKET", rupiah)
    order = pesanan_kit.buat(kon, 1, akun=AKUN_A, siswa=1)
    pesanan_kit.terapkan(kon, order, 1, transaction_id="trx-sintetis-0001", gross_amount="%d.00" % rupiah)
    return order["order_id"]


def _jumlah_tagihan(kon) -> tuple:
    return (kon.execute("SELECT COUNT(*) FROM kelas_order").fetchone()[0],
            kon.execute("SELECT COUNT(*) FROM kelas_tagihan").fetchone()[0])


def test_mini_dan_private_dipotong_nominal_deposit_peta(kon_kelas):
    order = peta_lunas(kon_kelas, 1)
    peta_lunas(kon_kelas, 2)
    mini, private = tagih(kon_kelas, 1, "mini"), tagih(kon_kelas, 2, "private")
    assert (mini.rincian.harga_dasar, mini.rincian.potongan_deposit, mini.rincian.nominal) == (300_000, 49_000, 251_000)
    assert (private.rincian.harga_dasar, private.rincian.potongan_deposit, private.rincian.nominal) == (
        640_000, 49_000, 591_000)
    assert mini.total == 251_000 + mini.kode_unik
    deposit = kon_kelas.execute("SELECT deposit_order_id FROM kelas_tagihan WHERE order_id=?",
                                (mini.order_id,)).fetchone()[0]
    assert deposit == order


def test_nominal_order_peta_tak_sesuai_gagal_tertutup_tanpa_tagihan(kon_kelas, monkeypatch):
    order = _peta_lunas_dengan_nominal(kon_kelas, monkeypatch, NOMINAL_TAK_SESUAI)
    sebelum = _jumlah_tagihan(kon_kelas)
    with pytest.raises(k.DepositTidakSah):
        kelas_rincian.nominal_deposit(kon_kelas, order)
    with pytest.raises(k.DepositTidakSah):
        tagih(kon_kelas, 1, "mini")
    with pytest.raises(k.DepositTidakSah):
        kelas_store.kartu_paket(kon_kelas, AKUN_A, 1, KINI)
    assert _jumlah_tagihan(kon_kelas) == sebelum


def test_nominal_order_peta_sama_dengan_nilai_check_diterima(kon_kelas, monkeypatch):
    order = _peta_lunas_dengan_nominal(kon_kelas, monkeypatch, pesanan_dasar.RUPIAH_PAKET)
    assert kelas_rincian.nominal_deposit(kon_kelas, order) == pesanan_dasar.RUPIAH_PAKET


@pytest.mark.parametrize("nominal", [48_999, 49_001, NOMINAL_TAK_SESUAI])
def test_nominal_selain_nilai_check_selalu_gagal_tertutup(kon_kelas, monkeypatch, nominal):
    _peta_lunas_dengan_nominal(kon_kelas, monkeypatch, nominal)
    with pytest.raises(k.DepositTidakSah):
        tagih(kon_kelas, 1, "mini")


def test_mutasi_guard_nominal_deposit_merah_lalu_pulih(tmp_path):
    """Guard fail-closed dimatikan di salinan: tes gagal karena perilaku (bukan impor rusak), lalu hijau setelah pulih."""
    uji_mutasi(tmp_path, "kelas_rincian.py", [
        ("    if type(nominal) is not int or nominal != katalog.RUPIAH_DEPOSIT:\n", "    if False:\n"),
    ], TES_INI, TES_GUARD, SALIN_TES)
