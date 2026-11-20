"""Aturan server refund manual: status turunan layak dan satu catatan per order di KEDUA tabel refund.

Data sintetis, tanpa jaringan. Jaga: `pesanan_refund_aturan` (dipakai `pesanan.catat_refund` dan
`pesanan_transfer.catat_refund_transfer`); mutation di test_admin_pesanan_keamanan_mutation.py.
"""
import pytest

import pesanan
import pesanan_dasar as d
import pesanan_refund_aturan as ra
import pesanan_transfer as tf
from pesanan_kit import (SEKARANG, SESUDAH_KEDALUWARSA, buat, hitung, operasi, siapkan_db,
                         terapkan)
from transfer_kit import (ADMIN, ADMIN_B, SESUDAH_UPLOAD, menunggu, siapkan_db_transfer, tagihan,
                          unggah)

SESUDAH_JENDELA_TRANSFER = "2026-11-25T12:00:00"


@pytest.fixture
def kon(tmp_path):
    with tf.buka(siapkan_db_transfer(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


def lunas_transfer(kon, n=1):
    order, _ = menunggu(kon, n)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    return order


def refund_transfer(kon, order, n=3, pelaku=ADMIN, catatan="kebijakan"):
    return pesanan.catat_refund(kon, order["order_id"], operasi(n), pelaku, catatan, SESUDAH_UPLOAD)


def jumlah_refund(kon):
    return hitung(kon, "pesanan_refund"), hitung(kon, "transfer_refund")


def _siapkan_receipt_menyusul(kon):
    """Order transfer lunas -> refund tercatat di transfer_refund -> receipt Midtrans masuk belakangan."""
    order = lunas_transfer(kon, 1)
    assert refund_transfer(kon, order) == {"status": "direfund", "baru": True}
    terapkan(kon, order, 1, sekarang=SESUDAH_UPLOAD)
    assert pesanan.status_order(kon, order["order_id"], order["akun_id"], SESUDAH_UPLOAD)["status"] == "direfund"
    return order


# --- L1: satu catatan per order lintas tabel -----------------------------------

def test_replay_identik_setelah_receipt_menyusul_sudah_ada_tanpa_baris_di_tabel_lain(kon):
    order = _siapkan_receipt_menyusul(kon)
    hasil = refund_transfer(kon, order)
    assert hasil == {"status": "direfund", "baru": False}
    assert jumlah_refund(kon) == (0, 1)


def test_isi_beda_setelah_receipt_menyusul_konflik_tanpa_baris_di_tabel_lain(kon):
    order = _siapkan_receipt_menyusul(kon)
    with pytest.raises(pesanan.PesananKonflik):
        refund_transfer(kon, order, 3, ADMIN_B, "kebijakan")         # operasi sama, pelaku beda
    with pytest.raises(pesanan.PesananKonflik):
        refund_transfer(kon, order, 4, ADMIN, "kebijakan")           # operasi baru, order sudah punya catatan
    assert jumlah_refund(kon) == (0, 1)


def test_refund_jalur_penyedia_lalu_catat_transfer_langsung_ditolak_tanpa_baris_ganda(kon):
    order = buat(kon, 1)
    terapkan(kon, order, 1)
    pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "kebijakan", SEKARANG)
    with pytest.raises(pesanan.PesananKonflik):
        tf.catat_refund_transfer(kon, order["order_id"], operasi(4), ADMIN, "kebijakan", SEKARANG)
    assert tf.catat_refund_transfer(kon, order["order_id"], operasi(3), ADMIN, "kebijakan",
                                    SEKARANG)["baru"] is False
    assert jumlah_refund(kon) == (1, 0)


def test_db_tanpa_namespace_transfer_tetap_refund_jalur_penyedia(tmp_path):
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as v1:
        order = buat(v1, 1)
        terapkan(v1, order, 1)
        assert pesanan.catat_refund(v1, order["order_id"], operasi(3), ADMIN, "kebijakan",
                                    SEKARANG)["baru"] is True
        assert pesanan.catat_refund(v1, order["order_id"], operasi(3), ADMIN, "kebijakan",
                                    SEKARANG)["baru"] is False
        assert hitung(v1, "pesanan_refund") == 1


# --- L2: status turunan ditegakkan di server -------------------------------------

def _order_status(kon, nama):
    """(order, waktu) untuk tiap status turunan non-refundable yang bisa dibuat murni lewat domain."""
    if nama == "belum_bayar":
        return tagihan(kon, 1)[0], SEKARANG
    if nama == "kedaluwarsa":
        return buat(kon, 1), SESUDAH_KEDALUWARSA
    if nama == "menunggu_verifikasi":
        return menunggu(kon, 1)[0], SESUDAH_UPLOAD
    order, _ = menunggu(kon, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "buram", SESUDAH_UPLOAD)
    return order, SESUDAH_UPLOAD


@pytest.mark.parametrize("nama", ["belum_bayar", "kedaluwarsa", "menunggu_verifikasi", "ditolak"])
def test_refund_ditolak_untuk_status_tak_layak_tanpa_baris(kon, nama):
    order, waktu = _order_status(kon, nama)
    assert pesanan.status_order(kon, order["order_id"], order["akun_id"], waktu)["status"] == nama
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "kebijakan", waktu)
    assert jumlah_refund(kon) == (0, 0)


def test_refund_ditolak_untuk_order_yang_sudah_direfund_dengan_operasi_lain(kon):
    order = lunas_transfer(kon, 1)
    refund_transfer(kon, order, 3)
    with pytest.raises(pesanan.PesananKonflik):
        refund_transfer(kon, order, 4)
    assert jumlah_refund(kon) == (0, 1)


@pytest.mark.parametrize("hasil", ["lunas", "perlu_diperiksa"])
def test_refund_sah_untuk_status_sudah_dibayar_dan_perlu_diperiksa(kon, hasil):
    order = buat(kon, 1)
    if hasil == "lunas":
        terapkan(kon, order, 1)
    else:
        terapkan(kon, order, 1, gross_amount="1000.00")
    status = pesanan.status_order(kon, order["order_id"], order["akun_id"], SEKARANG)["status"]
    assert status == ("sudah_dibayar" if hasil == "lunas" else "perlu_diperiksa")
    assert pesanan.catat_refund(kon, order["order_id"], operasi(3), ADMIN, "kebijakan",
                                SEKARANG)["baru"] is True
    assert jumlah_refund(kon) == (1, 0)


def test_status_bisa_refund_satu_sumber_dengan_ui():
    import admin_pesanan_pages as ui
    assert d.STATUS_BISA_REFUND == ("sudah_dibayar", "perlu_diperiksa")
    assert ui.STATUS_REFUND is d.STATUS_BISA_REFUND


@pytest.mark.parametrize("nama", ["belum_bayar", "kedaluwarsa", "menunggu_verifikasi", "ditolak"])
def test_periksa_layak_refund_menolak_status_di_luar_allowlist(kon, nama):
    """Penjaga status berdiri sendiri: tidak bergantung pada prasyarat receipt/transfer_lunas."""
    order, waktu = _order_status(kon, nama)
    with pytest.raises(pesanan.PesananKonflik):
        ra.periksa_layak_refund(kon, order["order_id"], waktu)


def test_periksa_layak_refund_menolak_direfund_dan_menerima_dua_status_layak(kon):
    layak = lunas_transfer(kon, 1)
    ra.periksa_layak_refund(kon, layak["order_id"], SESUDAH_UPLOAD)          # sudah_dibayar: lolos
    diperiksa = buat(kon, 2)
    terapkan(kon, diperiksa, 2, gross_amount="1000.00")
    ra.periksa_layak_refund(kon, diperiksa["order_id"], SEKARANG)            # perlu_diperiksa: lolos
    refund_transfer(kon, layak)
    with pytest.raises(pesanan.PesananKonflik):
        ra.periksa_layak_refund(kon, layak["order_id"], SESUDAH_UPLOAD)      # direfund: ditolak
    with pytest.raises(pesanan.PesananTidakDitemukan):
        ra.periksa_layak_refund(kon, "ord_" + "0" * 32, SESUDAH_UPLOAD)
