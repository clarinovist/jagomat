"""Pembaca tampilan transfer sisi guru (ledger saja, tanpa HTTP)."""
from __future__ import annotations

import pytest

import pesanan_dasar as d
import pesanan_transfer as tf
import pesanan_transfer_tampil as tt
from transfer_kit import (ADMIN, AKUN_A, AKUN_B, SEKARANG, SESUDAH_KEDALUWARSA, SESUDAH_UPLOAD, buat,
                          siapkan_db_transfer, tagihan, unggah)


@pytest.fixture()
def kon(tmp_path):
    path = siapkan_db_transfer(tmp_path)
    with tf.buka(path, tulis_data=True) as kon:
        yield kon


def _baca(kon, order, *, akun=AKUN_A, sekarang=SESUDAH_UPLOAD):
    return tt.baca(kon, order["order_id"], akun, sekarang)


def test_order_baru_belum_ada_tagihan_boleh_buat_tagihan(kon):
    order = buat(kon, 1)
    t = _baca(kon, order, sekarang=SEKARANG)
    assert (t.status, t.nominal, t.boleh_tagihan, t.boleh_unggah) == (d.STATUS_BELUM_BAYAR, None, True, False)
    assert t.jumlah_bukti == 0 and t.alasan_tolak is None


def test_setelah_tagihan_nominal_persis_dan_boleh_unggah(kon):
    order, tag = tagihan(kon, 1)
    t = _baca(kon, order, sekarang=SEKARANG)
    assert t.nominal == tag["nominal_transfer"] == d.RUPIAH_PAKET + tag["kode_unik"]
    assert (t.boleh_tagihan, t.boleh_unggah) == (False, True)
    assert t.kedaluwarsa == "2026-11-19T10:00:00"


def test_setelah_bukti_menunggu_verifikasi_tanpa_form(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    t = _baca(kon, order)
    assert (t.status, t.jumlah_bukti, t.boleh_tagihan, t.boleh_unggah) == (
        d.STATUS_MENUNGGU_VERIFIKASI, 1, False, False)


def test_ditolak_membawa_alasan_dan_boleh_unggah_ulang(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "Nominal tidak sesuai", SESUDAH_UPLOAD)
    t = _baca(kon, order)
    assert (t.status, t.alasan_tolak, t.boleh_unggah, t.jumlah_bukti) == (
        d.STATUS_DITOLAK, "Nominal tidak sesuai", True, 1)


def test_alasan_terbaru_yang_dipakai(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "Alasan pertama", SESUDAH_UPLOAD)
    unggah(kon, order, 2)
    tf.tolak(kon, order["order_id"], ADMIN, "Alasan kedua", SESUDAH_UPLOAD)
    assert _baca(kon, order).alasan_tolak == "Alasan kedua"


def test_batas_lima_bukti_menutup_unggah(kon):
    order, _ = tagihan(kon, 1)
    for n in range(1, 6):
        unggah(kon, order, n)
        tf.tolak(kon, order["order_id"], ADMIN, "Belum sesuai", SESUDAH_UPLOAD)
    t = _baca(kon, order)
    assert (t.status, t.jumlah_bukti, t.boleh_unggah) == (d.STATUS_DITOLAK, 5, False)


def test_jendela_lewat_menutup_unggah_dan_tagihan(kon):
    order, _ = tagihan(kon, 1)
    t = _baca(kon, order, sekarang=SESUDAH_KEDALUWARSA)
    assert (t.status, t.boleh_unggah, t.boleh_tagihan) == (d.STATUS_KEDALUWARSA, False, False)


def test_lunas_tidak_boleh_apa_apa(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    t = _baca(kon, order)
    assert (t.status, t.boleh_tagihan, t.boleh_unggah) == (d.STATUS_SUDAH_DIBAYAR, False, False)


def test_order_akun_lain_tidak_ditemukan(kon):
    order, _ = tagihan(kon, 1)
    with pytest.raises(d.PesananTidakDitemukan):
        _baca(kon, order, akun=AKUN_B)


# --- hambatan unggah (pesan ramah sebelum menulis berkas) -----------------------------------

def test_hambatan_tanpa_tagihan(kon):
    order = buat(kon, 1)
    assert tt.hambatan_unggah(_baca(kon, order, sekarang=SEKARANG), SEKARANG) == tt.HAMBATAN_TAGIHAN


def test_hambatan_none_bila_boleh_dicoba(kon):
    order, _ = tagihan(kon, 1)
    assert tt.hambatan_unggah(_baca(kon, order, sekarang=SEKARANG), SEKARANG) is None


def test_hambatan_jendela_lewat(kon):
    order, _ = tagihan(kon, 1)
    t = _baca(kon, order, sekarang=SEKARANG)
    assert tt.hambatan_unggah(t, SESUDAH_KEDALUWARSA) == tt.HAMBATAN_JENDELA


def test_hambatan_status_lunas(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    assert tt.hambatan_unggah(_baca(kon, order), SESUDAH_UPLOAD) == tt.HAMBATAN_STATUS


def test_hambatan_batas_lima_bukti(kon):
    order, _ = tagihan(kon, 1)
    for n in range(1, 6):
        unggah(kon, order, n)
    assert tt.hambatan_unggah(_baca(kon, order), SESUDAH_UPLOAD) == tt.HAMBATAN_BATAS


def test_menunggu_verifikasi_masih_boleh_dicoba_mengikuti_domain(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    assert tt.hambatan_unggah(_baca(kon, order), SESUDAH_UPLOAD) is None
