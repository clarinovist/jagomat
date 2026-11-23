"""Pembaca transfer menunggu verifikasi: urutan terlama dulu, semua halaman terbaca, galat diteruskan."""
import pytest

import admin_store
import admin_transfer_menunggu as TM
import pesanan_admin
import pesanan_transfer as tf
from transfer_kit import akun_ke, siapkan_db, siapkan_db_transfer, tagihan, unggah

SEKARANG_ISO = "2026-11-18T13:00:00"


def _tiga_order(path):
    """n=1 diunggah paling baru, n=3 paling lama; n=4 belum punya bukti (bukan menunggu)."""
    with tf.buka(path, tulis_data=True) as kon:
        o1, _ = tagihan(kon, 1, akun=akun_ke(1))
        unggah(kon, o1, 1, akun=akun_ke(1), sekarang="2026-11-18T12:00:00")
        o2, _ = tagihan(kon, 2, akun=akun_ke(2))
        unggah(kon, o2, 2, akun=akun_ke(2), sekarang="2026-11-18T11:30:00")
        o3, _ = tagihan(kon, 3, akun=akun_ke(3))
        unggah(kon, o3, 3, akun=akun_ke(3), sekarang="2026-11-18T11:00:00")
        tagihan(kon, 4, akun=akun_ke(4))
    return o1["order_id"], o2["order_id"], o3["order_id"]


def test_baca_terurut_terlama_dulu_dengan_nominal_dan_waktu_unggah(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    o1, o2, o3 = _tiga_order(path)
    hasil = TM.baca(path, SEKARANG_ISO)
    assert [t.order_id for t in hasil] == [o3, o2, o1]
    assert hasil[0].diunggah == "2026-11-18T11:00:00" and 49000 < hasil[0].nominal < 50000


def test_baca_membaca_semua_halaman_bukan_hanya_halaman_pertama(tmp_path, monkeypatch):
    path = siapkan_db_transfer(tmp_path)
    o1, o2, o3 = _tiga_order(path)
    monkeypatch.setattr(pesanan_admin, "BATAS_PER_HALAMAN", 1)
    assert [t.order_id for t in TM.baca(path, SEKARANG_ISO)] == [o3, o2, o1]


def test_berikutnya_memilih_tertua_selain_yang_dikecualikan(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    o1, o2, o3 = _tiga_order(path)
    assert TM.berikutnya(path, SEKARANG_ISO, kecuali=o2) == o3
    assert TM.berikutnya(path, SEKARANG_ISO, kecuali=o3) == o2
    assert TM.berikutnya(path, SEKARANG_ISO, kecuali="ord_" + "0" * 32) == o3


def test_berikutnya_none_bila_hanya_order_itu_yang_menunggu(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    with tf.buka(path, tulis_data=True) as kon:
        order, _ = tagihan(kon, 1)
        unggah(kon, order, 1)
    assert TM.berikutnya(path, SEKARANG_ISO, kecuali=order["order_id"]) is None
    assert TM.baca(path, SEKARANG_ISO)[0].order_id == order["order_id"]


def test_order_sudah_diputuskan_tidak_lagi_menunggu(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    o1, o2, o3 = _tiga_order(path)
    with tf.buka(path, tulis_data=True) as kon:
        tf.tolak(kon, o3, "admin_sintetis_a", "Nominal kurang", "2026-11-18T12:30:00")
    assert [t.order_id for t in TM.baca(path, SEKARANG_ISO)] == [o2, o1]


def test_waktu_iso_utc_naif():
    assert TM.waktu_iso(0) == "1970-01-01T00:00:00+00:00"


def test_transfer_belum_dipasang_berarti_kosong_dan_path_hilang_meneruskan_galat(tmp_path):
    belum = siapkan_db(tmp_path)  # pesanan ada, namespace transfer belum
    assert TM.baca(belum, SEKARANG_ISO) == () and TM.berikutnya(belum, SEKARANG_ISO, kecuali="x") is None
    with pytest.raises(TM.GALAT_BACA):
        TM.baca(tmp_path / "tidak-ada.db", SEKARANG_ISO)
    assert admin_store.StoreBelumSiap in TM.GALAT_BACA
