"""Pembaca detail order admin (`pesanan_admin_order`) dan daftar tersaring (`pesanan_admin.daftar_tersaring`).

Data sintetis; ledger sementara di tmp_path (tanpa HTTP).
"""
import pytest

import pesanan
import pesanan_admin
import pesanan_admin_order as po
import pesanan_transfer as tf
from pesanan_kit import (AKUN_A, MERCHANT, SEKARANG, SESUDAH_KEDALUWARSA, TRANSAKSI, buat, operasi,
                         ord_id, siapkan_db, terapkan)
from transfer_kit import ADMIN, SESUDAH_UPLOAD, menunggu, siapkan_db_transfer, tagihan

SESUDAH = "2026-11-18T13:00:00"
KUNCI_DETAIL = {"order_id", "akun", "status", "dibuat", "kedaluwarsa", "cara", "nominal", "jumlah_bukti", "langkah"}


@pytest.fixture
def kon(tmp_path):
    with tf.buka(siapkan_db_transfer(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


@pytest.fixture
def kon_qris(tmp_path):
    """DB hanya dengan skema pesanan v1 (tanpa namespace transfer_*)."""
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as sambungan:
        yield sambungan


def _kode(detail):
    return [x["kode"] for x in detail["langkah"]]


# --- detail_order -----------------------------------------------------------------

def test_order_tak_dikenal_none_dan_id_tak_sah_ditolak(kon):
    assert po.detail_order(kon, ord_id(404), SEKARANG) is None
    with pytest.raises(pesanan.PesananDataTidakSah):
        po.detail_order(kon, "bukan-order", SEKARANG)


def test_order_qris_belum_bayar_hanya_langkah_dibuat_dan_kunci_minimal(kon_qris):
    order = buat(kon_qris, 1)
    detail = po.detail_order(kon_qris, order["order_id"], SEKARANG)
    assert set(detail) == KUNCI_DETAIL
    assert (detail["status"], detail["cara"], detail["nominal"], detail["jumlah_bukti"]) == (
        "belum_bayar", "qris", None, 0)
    assert detail["akun"] == AKUN_A[:13] and detail["dibuat"] == SEKARANG
    assert _kode(detail) == ["dibuat"]


def test_detail_tidak_memuat_transaksi_merchant_atau_akun_penuh(kon_qris):
    order = buat(kon_qris, 1)
    terapkan(kon_qris, order, 1)
    teks = repr(po.detail_order(kon_qris, order["order_id"], SEKARANG))
    assert TRANSAKSI not in teks and MERCHANT not in teks and AKUN_A not in teks


def test_order_qris_lunas_lalu_refund_menambah_langkah_berurutan(kon_qris):
    order = buat(kon_qris, 1)
    terapkan(kon_qris, order, 1, sekarang="2026-11-18T10:05:00")
    assert _kode(po.detail_order(kon_qris, order["order_id"], SEKARANG)) == ["dibuat", "lunas"]
    pesanan.catat_refund(kon_qris, order["order_id"], operasi(2), "admin_a", "kebijakan", "2026-11-18T11:00:00")
    detail = po.detail_order(kon_qris, order["order_id"], SEKARANG)
    assert detail["status"] == "direfund" and _kode(detail) == ["dibuat", "lunas", "refund"]


def test_order_kedaluwarsa_menambah_langkah_waktu_bayar_habis(kon_qris):
    order = buat(kon_qris, 1)
    detail = po.detail_order(kon_qris, order["order_id"], SESUDAH_KEDALUWARSA)
    assert detail["status"] == "kedaluwarsa" and _kode(detail) == ["dibuat", "kedaluwarsa"]
    assert detail["langkah"][-1]["waktu"] == detail["kedaluwarsa"]


def test_order_transfer_menunggu_nominal_cara_dan_bukti(kon):
    order, tag = menunggu(kon, 1)
    detail = po.detail_order(kon, order["order_id"], SESUDAH_UPLOAD)
    assert (detail["status"], detail["cara"], detail["jumlah_bukti"]) == ("menunggu_verifikasi", "transfer", 1)
    assert detail["nominal"] == tag["nominal_transfer"]
    assert _kode(detail) == ["dibuat", "bukti"]
    assert detail["langkah"][1]["jumlah"] == 1 and detail["langkah"][1]["waktu"] == SESUDAH_UPLOAD


def test_order_transfer_disetujui_lalu_direfund_langkah_lengkap(kon):
    order, _tag = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, "2026-11-18T12:30:00")
    assert _kode(po.detail_order(kon, order["order_id"], SESUDAH)) == ["dibuat", "bukti", "setuju"]
    pesanan.catat_refund(kon, order["order_id"], operasi(5), "admin_a", "kebijakan", "2026-11-18T12:45:00")
    detail = po.detail_order(kon, order["order_id"], SESUDAH)
    assert detail["status"] == "direfund" and _kode(detail) == ["dibuat", "bukti", "setuju", "refund"]


def test_order_transfer_ditolak_langkah_tolak_dan_bukan_data_alasan(kon):
    order, _tag = menunggu(kon, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "Nominal kurang", "2026-11-18T12:30:00")
    detail = po.detail_order(kon, order["order_id"], SESUDAH)
    assert detail["status"] == "ditolak" and _kode(detail) == ["dibuat", "bukti", "tolak"]
    assert "Nominal kurang" not in repr(detail)


def test_order_qris_pada_db_dengan_transfer_tetap_qris_tanpa_nominal(kon):
    order = buat(kon, 1)
    detail = po.detail_order(kon, order["order_id"], SEKARANG)
    assert (detail["cara"], detail["nominal"], detail["jumlah_bukti"]) == ("qris", None, 0)


def test_langkah_terurut_menurut_waktu(kon):
    order, _tag = menunggu(kon, 1)
    tf.setujui(kon, order["order_id"], ADMIN, "2026-11-18T12:30:00")
    waktu = [x["waktu"] for x in po.detail_order(kon, order["order_id"], SESUDAH)["langkah"]]
    assert waktu == sorted(waktu)


# --- daftar_tersaring ----------------------------------------------------------------

def _isi_status_beragam(kon):
    """Satu order per kelompok: belum bayar, menunggu, dibayar (transfer), direfund, ditolak, kedaluwarsa."""
    belum, _ = tagihan(kon, 1, sekarang="2026-11-18T09:00:00")
    tunggu, _ = menunggu(kon, 2)
    lunas, _ = menunggu(kon, 3)
    tf.setujui(kon, lunas["order_id"], ADMIN, SESUDAH_UPLOAD)
    refund, _ = menunggu(kon, 4)
    tf.setujui(kon, refund["order_id"], ADMIN, SESUDAH_UPLOAD)
    pesanan.catat_refund(kon, refund["order_id"], operasi(9), "admin_a", "kebijakan", SESUDAH_UPLOAD)
    tolak, _ = menunggu(kon, 5)
    tf.tolak(kon, tolak["order_id"], ADMIN, "Tidak jelas", SESUDAH_UPLOAD)
    lama = buat(kon, 6, sekarang="2026-11-10T09:00:00")
    return {"belum": belum, "tunggu": tunggu, "lunas": lunas, "refund": refund, "tolak": tolak, "lama": lama}


def _ids(daftar):
    return {i["order_id"] for i in daftar["items"]}


def _tersaring(kon, kelompok=None, halaman=1, per_halaman=25):
    return pesanan_admin.daftar_tersaring(
        kon, halaman=halaman, per_halaman=per_halaman, sekarang=SESUDAH_UPLOAD, kelompok=kelompok)


def test_kelompok_status_menyekat_semua_status_turunan_tepat_satu_kali():
    semua = [s for status in pesanan_admin.KELOMPOK_STATUS.values() for s in status]
    assert sorted(semua) == sorted(pesanan.STATUS_TURUNAN) and len(semua) == len(set(semua))


def test_tersaring_per_kelompok_hanya_status_anggota_dan_total_sesudah_saring(kon):
    o = _isi_status_beragam(kon)
    harap = {
        "menunggu": {o["tunggu"]["order_id"]},
        "belum_bayar": {o["belum"]["order_id"]},
        "dibayar": {o["lunas"]["order_id"], o["refund"]["order_id"]},
        "ditolak": {o["tolak"]["order_id"], o["lama"]["order_id"]},
    }
    for kelompok, ids in harap.items():
        daftar = _tersaring(kon, kelompok)
        assert _ids(daftar) == ids and daftar["total"] == len(ids)
        assert all(i["status"] in pesanan_admin.KELOMPOK_STATUS[kelompok] for i in daftar["items"])


def test_tersaring_hitungan_semua_kelompok_konsisten_dengan_status_yang_tampil(kon):
    _isi_status_beragam(kon)
    semua = _tersaring(kon)
    assert semua["total"] == 6 and semua["hitungan"] == {
        "menunggu": 1, "belum_bayar": 1, "dibayar": 2, "ditolak": 2, "semua": 6}
    assert _tersaring(kon, "dibayar")["hitungan"] == semua["hitungan"]
    assert semua["hitungan"]["semua"] == sum(v for k, v in semua["hitungan"].items() if k != "semua")


def test_tersaring_semua_sama_dengan_daftar_admin_lama(kon):
    _isi_status_beragam(kon)
    lama = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SESUDAH_UPLOAD)
    baru = _tersaring(kon)
    assert baru["items"] == lama["items"] and baru["total"] == lama["total"]


def test_tersaring_menunggu_sama_dengan_hanya_menunggu_lama(kon):
    _isi_status_beragam(kon)
    lama = pesanan.daftar_admin(kon, halaman=1, per_halaman=25, sekarang=SESUDAH_UPLOAD, hanya_menunggu=True)
    assert _tersaring(kon, "menunggu")["items"] == lama["items"]


def test_tersaring_paginasi_memotong_setelah_saring(kon):
    for n in range(1, 8):
        menunggu(kon, n)
    h1 = _tersaring(kon, "menunggu", 1, 3)
    h3 = _tersaring(kon, "menunggu", 3, 3)
    assert (len(h1["items"]), len(h3["items"]), h1["total"]) == (3, 1, 7)
    assert _tersaring(kon, "menunggu", 4, 3)["items"] == ()


@pytest.mark.parametrize("kelompok", ["sembarang", "", "MENUNGGU", "semua", 1])
def test_tersaring_kelompok_asing_ditolak(kon, kelompok):
    with pytest.raises(pesanan.PesananDataTidakSah):
        _tersaring(kon, kelompok)


def test_tersaring_per_halaman_tak_sah_ditolak(kon):
    for nilai in (0, 101, "25", True):
        with pytest.raises(pesanan.PesananDataTidakSah):
            _tersaring(kon, None, 1, nilai)


def test_tersaring_pada_db_tanpa_transfer_tetap_jalan(kon_qris):
    order = buat(kon_qris, 1)
    daftar = pesanan_admin.daftar_tersaring(kon_qris, halaman=1, per_halaman=25, sekarang=SEKARANG,
                                            kelompok="belum_bayar")
    assert _ids(daftar) == {order["order_id"]} and daftar["hitungan"]["belum_bayar"] == 1
