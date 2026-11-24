"""Guard refund: voucher yang sudah dipakai tidak boleh direfund, di KEDUA jalur refund."""
import pytest

import pesanan
import pesanan_dasar as d
import pesanan_transfer as tf
import purna
from purna_kit import (PELAKU, SEKARANG, baris, db, hitung, kon, kon_pesanan_saja, kon_tanpa_purna,  # noqa: F401
                       operasi, order_belum_lunas, order_qris_lunas, order_transfer_lunas)

PESAN = "voucher sudah dipakai"
SESUDAH = "2026-11-19T10:00:00"


def pakai(kon, oid):
    return purna.catat_pakai(kon, oid, operasi(1), PELAKU, "kelas", SEKARANG)


def refund_lewat_admin(kon, oid, n=2):
    return pesanan.catat_refund(kon, oid, operasi(n), PELAKU, "kebijakan", SESUDAH)


def refund_langsung_transfer(kon, oid, n=2):
    return tf.catat_refund_transfer(kon, oid, operasi(n), PELAKU, "kebijakan", SESUDAH)


def test_refund_qris_ditolak_setelah_voucher_dipakai_tanpa_tulis(kon):
    oid = order_qris_lunas(kon, 1)
    pakai(kon, oid)
    with pytest.raises(d.PesananKonflik, match=PESAN):
        refund_lewat_admin(kon, oid)
    assert hitung(kon, "pesanan_refund") == 0 and hitung(kon, "transfer_refund") == 0
    assert not kon.in_transaction


@pytest.mark.parametrize("jalur", [refund_lewat_admin, refund_langsung_transfer], ids=["admin", "langsung"])
def test_refund_transfer_ditolak_setelah_voucher_dipakai_lewat_kedua_pintu(kon, jalur):
    oid = order_transfer_lunas(kon, 1)
    pakai(kon, oid)
    with pytest.raises(d.PesananKonflik, match=PESAN):
        jalur(kon, oid)
    assert hitung(kon, "pesanan_refund") == 0 and hitung(kon, "transfer_refund") == 0


def test_refund_voucher_lain_yang_belum_dipakai_tetap_lolos(kon):
    dipakai, bebas = order_qris_lunas(kon, 1), order_qris_lunas(kon, 2)
    pakai(kon, dipakai)
    assert refund_lewat_admin(kon, bebas)["baru"] is True
    assert hitung(kon, "pesanan_refund") == 1


@pytest.mark.parametrize("buat_order,tabel", [(order_qris_lunas, "pesanan_refund"),
                                              (order_transfer_lunas, "transfer_refund")])
def test_refund_tanpa_pemakaian_voucher_tetap_lolos_dan_replay_identik_dilayani(kon, buat_order, tabel):
    oid = buat_order(kon, 1)
    assert refund_lewat_admin(kon, oid) == {"status": "direfund", "baru": True}
    assert refund_lewat_admin(kon, oid) == {"status": "direfund", "baru": False}
    assert hitung(kon, tabel) == 1


def test_refund_transfer_langsung_tanpa_pemakaian_tetap_lolos_dan_replay_identik(kon):
    oid = order_transfer_lunas(kon, 1)
    assert refund_langsung_transfer(kon, oid)["baru"] is True
    assert refund_langsung_transfer(kon, oid)["baru"] is False
    assert hitung(kon, "transfer_refund") == 1


def test_refund_replay_identik_tidak_dihalangi_guard_voucher(kon):
    oid = order_qris_lunas(kon, 1)
    refund_lewat_admin(kon, oid)
    assert purna.voucher_dipakai(kon, oid) is False
    assert refund_lewat_admin(kon, oid)["baru"] is False


def test_refund_dengan_operasi_lain_pada_order_direfund_tetap_konflik_lama_bukan_pesan_voucher(kon):
    oid = order_qris_lunas(kon, 1)
    refund_lewat_admin(kon, oid, 2)
    with pytest.raises(d.PesananKonflik) as galat:
        refund_lewat_admin(kon, oid, 3)
    assert PESAN not in str(galat.value)


def test_refund_order_belum_lunas_tetap_ditolak_dengan_pesan_lama(kon):
    with pytest.raises(d.PesananKonflik, match="order belum punya receipt"):
        refund_lewat_admin(kon, order_belum_lunas(kon, 1))


def test_refund_tanpa_namespace_purna_tetap_bekerja_di_db_transfer(kon_tanpa_purna):
    oid = order_transfer_lunas(kon_tanpa_purna, 1)
    assert refund_lewat_admin(kon_tanpa_purna, oid)["baru"] is True
    qris = order_qris_lunas(kon_tanpa_purna, 2)
    assert refund_lewat_admin(kon_tanpa_purna, qris, 3)["baru"] is True


def test_refund_di_db_pesanan_saja_tetap_bekerja(kon_pesanan_saja):
    oid = order_qris_lunas(kon_pesanan_saja, 1)
    assert refund_lewat_admin(kon_pesanan_saja, oid)["baru"] is True
    assert hitung(kon_pesanan_saja, "pesanan_refund") == 1
