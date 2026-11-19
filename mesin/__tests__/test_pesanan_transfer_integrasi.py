"""Integrasi transfer rekening dengan status turunan, kuota, jendela ulang, refund, dan daftar admin."""
import pytest

import pesanan
import pesanan_jendela as jd
import pesanan_status as st
import pesanan_transfer as tf
import pesanan_transfer_baca as tb
from pesanan_kit import (AKUN_A, SEKARANG, SESUDAH_KEDALUWARSA, buat, hitung, operasi, siapkan_db,
                         terapkan)
from transfer_kit import (ADMIN, SESUDAH_UPLOAD, menunggu, siapkan_db_transfer, tagihan, unggah)


@pytest.fixture
def kon(tmp_path):
    with tf.buka(siapkan_db_transfer(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


def lunas(kon, n=1):
    order, _ = menunggu(kon, n)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    return order


@pytest.mark.parametrize("kwargs,harapan", [
    ({}, "belum_bayar"),
    ({"transfer_bukti": "menunggu"}, "menunggu_verifikasi"),
    ({"transfer_bukti": "ditolak"}, "ditolak"),
    ({"transfer_lunas": True}, "sudah_dibayar"),
    ({"transfer_lunas": True, "transfer_direfund": True}, "direfund"),
    ({"transfer_lunas": True, "receipt_hasil": "lunas"}, "perlu_diperiksa"),
    ({"transfer_bukti": "menunggu", "receipt_hasil": "lunas"}, "sudah_dibayar"),
])
def test_turunkan_status_dengan_fakta_transfer_sebelum_kedaluwarsa(kwargs, harapan):
    dasar = dict(kedaluwarsa="2026-11-19T10:00:00", sekarang=SEKARANG, receipt_hasil=None,
                 direfund=False, refund_teramati=False)
    dasar.update(kwargs)
    assert st.turunkan_status(**dasar) == harapan


@pytest.mark.parametrize("kwargs,harapan", [
    ({}, "kedaluwarsa"),
    ({"transfer_bukti": "ditolak"}, "kedaluwarsa"),
    ({"transfer_bukti": "menunggu"}, "menunggu_verifikasi"),
    ({"transfer_lunas": True}, "sudah_dibayar"),
])
def test_turunkan_status_sesudah_kedaluwarsa(kwargs, harapan):
    dasar = dict(kedaluwarsa="2026-11-19T10:00:00", sekarang=SESUDAH_KEDALUWARSA, receipt_hasil=None,
                 direfund=False, refund_teramati=False)
    dasar.update(kwargs)
    assert st.turunkan_status(**dasar) == harapan


def test_status_turunan_memuat_dua_status_baru():
    assert {"menunggu_verifikasi", "ditolak"} <= set(pesanan.STATUS_TURUNAN)


def test_fakta_default_pada_db_tanpa_namespace_transfer(tmp_path):
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as v1:
        order = buat(v1, 1)
        assert tb.terpasang(v1) is False
        assert tb.fakta(v1, order["order_id"]) == {"lunas": False, "direfund": False, "bukti": None}
        assert pesanan.status_order(v1, order["order_id"], AKUN_A, SEKARANG)["status"] == "belum_bayar"
        assert jd.jumlah_aktif(v1, SEKARANG) == 1
        assert pesanan.daftar_admin(v1, halaman=1, per_halaman=5, sekarang=SEKARANG)["total"] == 1


def test_kuota_menghitung_lunas_transfer_dan_bukti_menunggu_walau_jendela_habis(kon):
    lunas(kon, 1)
    menunggu(kon, 2)
    tagihan(kon, 3)                                   # tanpa bukti: lepas dari kuota sesudah jendela
    assert jd.jumlah_aktif(kon, SEKARANG) == 3
    assert jd.jumlah_aktif(kon, SESUDAH_KEDALUWARSA) == 2


def test_jendela_ulang_ditolak_untuk_lunas_transfer_dan_menunggu_verifikasi(kon):
    order_lunas = lunas(kon, 1)
    order_tunggu, _ = menunggu(kon, 2)
    for order in (order_lunas, order_tunggu):
        with pytest.raises(pesanan.PesananKonflik):
            pesanan.buka_jendela_ulang(kon, order["order_id"], AKUN_A, SESUDAH_KEDALUWARSA,
                                       operasi(7))
    assert hitung(kon, "pesanan_jendela") == 2


def test_refund_pada_lunas_transfer_menjadi_direfund(kon):
    order = lunas(kon, 1)
    hasil = pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "kebijakan",
                                 SESUDAH_UPLOAD)
    assert hasil == {"status": "direfund", "baru": True}
    ulang = pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "kebijakan",
                                 SESUDAH_UPLOAD)
    assert ulang == {"status": "direfund", "baru": False}
    assert hitung(kon, "transfer_refund") == 1 and hitung(kon, "pesanan_refund") == 0
    assert pesanan.status_order(kon, order["order_id"], AKUN_A, SESUDAH_UPLOAD)["status"] == "direfund"


def test_refund_transfer_menolak_replay_beda_isi_dan_refund_kedua(kon):
    order = lunas(kon, 1)
    pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "kebijakan", SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "lainnya", SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_refund(kon, order["order_id"], operasi(4), ADMIN, "kebijakan", SESUDAH_UPLOAD)
    assert hitung(kon, "transfer_refund") == 1


@pytest.mark.parametrize("siapkan", ["menunggu", "belum_ada_bukti", "tanpa_tagihan"])
def test_refund_transfer_menolak_order_yang_belum_lunas(kon, siapkan):
    order = {"menunggu": lambda: menunggu(kon, 1)[0], "belum_ada_bukti": lambda: tagihan(kon, 1)[0],
             "tanpa_tagihan": lambda: buat(kon, 1)}[siapkan]()
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "kebijakan", SESUDAH_UPLOAD)
    assert hitung(kon, "transfer_refund") == 0


def test_refund_transfer_menolak_kode_catatan_tak_sah_dan_order_tak_dikenal(kon):
    order = lunas(kon, 1)
    with pytest.raises(pesanan.PesananDataTidakSah):
        tf.catat_refund_transfer(kon, order["order_id"], operasi(3), ADMIN, "ngawur", SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananTidakDitemukan):
        pesanan.catat_refund(kon, "ord_" + "0" * 32, operasi(3), ADMIN, "kebijakan", SESUDAH_UPLOAD)


def test_daftar_admin_menampilkan_status_transfer(kon):
    order_lunas = lunas(kon, 1)
    order_tunggu, _ = menunggu(kon, 2)
    order_polos = buat(kon, 3)
    hasil = pesanan.daftar_admin(kon, halaman=1, per_halaman=10, sekarang=SESUDAH_KEDALUWARSA)
    status = {item["order_id"]: item["status"] for item in hasil["items"]}
    assert status == {order_lunas["order_id"]: "sudah_dibayar",
                      order_tunggu["order_id"]: "menunggu_verifikasi",
                      order_polos["order_id"]: "kedaluwarsa"}


def test_receipt_midtrans_sesudah_lunas_transfer_fail_closed_perlu_diperiksa(kon):
    order = lunas(kon, 1)
    terapkan(kon, order, 1)          # jalur QRIS menyala lagi: blocker QRIS, bukan diam-diam lunas ganda
    hasil = pesanan.status_order(kon, order["order_id"], AKUN_A, SESUDAH_UPLOAD)
    assert hasil["status"] == "perlu_diperiksa"
    assert pesanan.daftar_admin(kon, halaman=1, per_halaman=5,
                                sekarang=SESUDAH_UPLOAD)["items"][0]["status"] == "perlu_diperiksa"


def test_alur_midtrans_tidak_berubah_dengan_namespace_transfer_terpasang(kon):
    order = buat(kon, 1)
    assert terapkan(kon, order, 1)["status"] == "sudah_dibayar"
    assert jd.jumlah_aktif(kon, SESUDAH_KEDALUWARSA) == 1
    lain = buat(kon, 2)
    assert pesanan.buka_jendela_ulang(kon, lain["order_id"], AKUN_A, SESUDAH_KEDALUWARSA,
                                      operasi(9))["urutan"] == 2
