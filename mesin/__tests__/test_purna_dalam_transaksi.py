"""purna.catat_pakai_dalam_transaksi: logika catat_pakai di transaksi milik pemanggil (domain kelas).

Data sintetis. Fungsi ini TIDAK membuka, meng-commit, atau me-rollback transaksi: pemanggil (satu `d.tulis`)
yang memilikinya, supaya akses kelas dan pemakaian deposit atomik. Perilaku catat_pakai biasa dijaga
test_purna*.py (tidak diubah).
"""
import pytest

import pesanan_dasar as d
import purna
from purna_kit import (PELAKU, SEKARANG, WAKTU_SETUJU, baris, db, kon, kon_tanpa_purna,  # noqa: F401
                       operasi, order_belum_lunas, order_qris_lunas, order_transfer_lunas, refund_mentah)

SESUDAH_HINGGA = "2027-02-16T10:00:00"


def dalam(kon, oid, n=1, *, pelaku=PELAKU, catatan="kelas", sekarang=SEKARANG):
    return purna.catat_pakai_dalam_transaksi(kon, oid, operasi(n), pelaku, catatan, sekarang)


def test_ditolak_bila_koneksi_tidak_dalam_transaksi_tanpa_tulis(kon):
    oid = order_qris_lunas(kon, 1)
    with pytest.raises(d.PesananDataTidakSah):
        dalam(kon, oid)
    assert baris(kon, "purna_voucher_pakai") == []
    assert not kon.in_transaction


def test_menulis_di_transaksi_pemanggil_dan_tidak_commit_sendiri(kon):
    oid = order_qris_lunas(kon, 1)
    with d.tulis(kon):
        assert dalam(kon, oid) == {"baru": True}
        assert kon.in_transaction
        assert purna.keadaan(kon, oid, SEKARANG).voucher == "dipakai"
    assert baris(kon, "purna_voucher_pakai") == [(operasi(1), oid, PELAKU, "kelas", SEKARANG)]


def test_rollback_pemanggil_membatalkan_pemakaian(kon):
    oid = order_qris_lunas(kon, 1)
    with pytest.raises(RuntimeError):
        with d.tulis(kon):
            dalam(kon, oid)
            raise RuntimeError("gagal sesudah pakai")
    assert baris(kon, "purna_voucher_pakai") == []
    assert purna.keadaan(kon, oid, SEKARANG).voucher == "aktif"


def test_replay_identik_di_transaksi_tidak_menulis_lagi(kon):
    oid = order_qris_lunas(kon, 1)
    with d.tulis(kon):
        dalam(kon, oid)
        assert dalam(kon, oid, sekarang="2026-11-19T10:00:00") == {"baru": False}
    assert len(baris(kon, "purna_voucher_pakai")) == 1


@pytest.mark.parametrize("ganti", [dict(catatan="lainnya"), dict(pelaku="admin_lain")])
def test_operasi_sama_isi_beda_konflik(kon, ganti):
    oid = order_qris_lunas(kon, 1)
    with d.tulis(kon):
        dalam(kon, oid)
    sebelum = baris(kon, "purna_voucher_pakai")
    with pytest.raises(d.PesananKonflik):
        with d.tulis(kon):
            dalam(kon, oid, **ganti)
    assert baris(kon, "purna_voucher_pakai") == sebelum


def test_order_sudah_dipakai_operasi_lain_konflik(kon):
    oid = order_qris_lunas(kon, 1)
    with d.tulis(kon):
        dalam(kon, oid, 1)
    with pytest.raises(d.PesananKonflik):
        with d.tulis(kon):
            dalam(kon, oid, 2)
    assert len(baris(kon, "purna_voucher_pakai")) == 1


def test_voucher_tidak_aktif_konflik_belum_lunas_kedaluwarsa_dan_refund(kon):
    belum = order_belum_lunas(kon, 1)
    lunas = order_qris_lunas(kon, 2)
    direfund = order_transfer_lunas(kon, 3)
    refund_mentah(kon, direfund, 9, tabel="transfer_refund")
    for oid, kini in ((belum, SEKARANG), (lunas, SESUDAH_HINGGA), (direfund, WAKTU_SETUJU)):
        with pytest.raises(d.PesananKonflik):
            with d.tulis(kon):
                dalam(kon, oid, sekarang=kini)
    assert baris(kon, "purna_voucher_pakai") == []


def test_purna_belum_dipasang_konflik(kon_tanpa_purna):
    with pytest.raises(d.PesananKonflik):
        with d.tulis(kon_tanpa_purna):
            dalam(kon_tanpa_purna, "ord_" + "0" * 32)


@pytest.mark.parametrize("ganti", [dict(catatan="asing"), dict(pelaku="a b")])
def test_masukan_tidak_sah_ditolak_sebelum_menyentuh_db(kon, ganti):
    oid = order_qris_lunas(kon, 1)
    with pytest.raises(d.PesananDataTidakSah):
        dalam(kon, oid, **ganti)
    with pytest.raises(d.PesananDataTidakSah):
        purna.catat_pakai_dalam_transaksi(kon, "bukan-order", operasi(1), PELAKU, "kelas", SEKARANG)
    assert baris(kon, "purna_voucher_pakai") == []
