"""Jendela bayar ulang jalur transfer: domain (`buka_ulang`) dan tampilan guru (`boleh_ulang`).

Data sintetis; ledger sementara. Aturan: hanya order kedaluwarsa tanpa bukti menunggu/lunas, maksimal
MAKS_JENDELA jendela, kuota, kepemilikan 404 identik, tagihan baru per jendela, tabrakan nominal.
"""
import pytest

import pesanan
import pesanan_dasar
import pesanan_transfer as tf
import pesanan_transfer_tampil as tt
import pesanan_transfer_ulang as ul
from pesanan_kit import (AKUN_A, AKUN_B, SEKARANG, SESUDAH_KEDALUWARSA, buat, hitung, operasi,
                         terapkan)
from transfer_kit import (ADMIN, SESUDAH_UPLOAD, siapkan_db_transfer, tagihan, unggah)


@pytest.fixture
def db(tmp_path):
    return siapkan_db_transfer(tmp_path)


@pytest.fixture
def kon(db):
    with tf.buka(db, tulis_data=True) as sambungan:
        yield sambungan


def _ulang(kon, order, n=50, *, akun=AKUN_A, sekarang=SESUDAH_KEDALUWARSA):
    return ul.buka_ulang(kon, order["order_id"], akun, sekarang, operasi(n))


def _waktu(urutan):
    """Waktu 1 jam sesudah jendela ke-`urutan` kedaluwarsa (jendela masing-masing 24 jam dari SEKARANG)."""
    return pesanan_dasar.tambah_jam(SEKARANG, 24 * urutan + 1)


def _tampil(kon, order, sekarang=SESUDAH_KEDALUWARSA, akun=AKUN_A):
    return tt.baca(kon, order["order_id"], akun, sekarang)


def _isi(kon):
    return {t: hitung(kon, t) for t in ("pesanan_jendela", "transfer_tagihan", "transfer_bukti")}


# --- domain ---------------------------------------------------------------------

def test_kedaluwarsa_tanpa_bukti_membuka_jendela_baru_belum_bayar_tanpa_tagihan(kon):
    order, lama = tagihan(kon, 1)
    hasil = _ulang(kon, order)
    assert (hasil["urutan"], hasil["baru"]) == (2, True)
    assert pesanan.status_order(kon, order["order_id"], AKUN_A, SESUDAH_KEDALUWARSA)["status"] == "belum_bayar"
    assert tf.ambil_tagihan(kon, order["order_id"], AKUN_A) is None       # tagihan baru per jendela
    assert hitung(kon, "transfer_tagihan") == 1 and lama["urutan"] == 1


def test_tagihan_baru_untuk_jendela_baru_dan_tagihan_lama_tetap_ada(kon):
    order, lama = tagihan(kon, 1)
    _ulang(kon, order)
    baru = tf.buat_tagihan_transfer(kon, order["order_id"], AKUN_A, SESUDAH_KEDALUWARSA,
                                    acak=lambda bebas: bebas[-1])
    assert baru["urutan"] == 2 and baru["baru"] is True
    assert baru["nominal_transfer"] == pesanan.RUPIAH_PAKET + baru["kode_unik"]
    assert hitung(kon, "transfer_tagihan") == 2
    assert kon.execute("SELECT nominal_transfer FROM transfer_tagihan WHERE urutan=1").fetchone()[0] \
        == lama["nominal_transfer"]


def test_jendela_masih_terbuka_ditolak_tanpa_tulis(kon):
    order, _ = tagihan(kon, 1)
    sebelum = _isi(kon)
    with pytest.raises(pesanan.PesananKonflik):
        _ulang(kon, order, sekarang=SESUDAH_UPLOAD)
    assert _isi(kon) == sebelum


def test_ada_bukti_menunggu_ditolak_walau_jendela_lewat(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    sebelum = _isi(kon)
    with pytest.raises(pesanan.PesananKonflik):
        _ulang(kon, order)
    assert _isi(kon) == sebelum


def test_sudah_lunas_ditolak(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    with pytest.raises(pesanan.PesananKonflik):
        _ulang(kon, order)
    assert hitung(kon, "pesanan_jendela") == 1


def test_bukti_ditolak_lalu_jendela_lewat_boleh_dibuka_ulang(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    tf.tolak(kon, order["order_id"], ADMIN, "Nominal kurang", SESUDAH_UPLOAD)
    assert _ulang(kon, order)["urutan"] == 2


def test_hanya_kedaluwarsa_provider_mati_di_jendela_terbuka_tidak_membuka_jalur_transfer(kon):
    order, _ = tagihan(kon, 1)
    terapkan(kon, order, 2, sekarang=SESUDAH_UPLOAD, transaction_status="expire", status_code="407")
    sebelum = _isi(kon)
    with pytest.raises(pesanan.PesananKonflik):
        _ulang(kon, order, sekarang=SESUDAH_UPLOAD)
    assert _isi(kon) == sebelum


def test_batas_lima_jendela_total_empat_pembukaan_ulang_lalu_ditolak(kon):
    order, _ = tagihan(kon, 1)
    for urutan in range(1, 5):
        assert _ulang(kon, order, 50 + urutan, sekarang=_waktu(urutan))["urutan"] == urutan + 1
    assert hitung(kon, "pesanan_jendela") == 5
    with pytest.raises(pesanan.PesananBatasJendela):
        _ulang(kon, order, 60, sekarang=_waktu(5))
    assert hitung(kon, "pesanan_jendela") == 5


def test_kuota_habis_ditolak_tanpa_tulis(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 2)
    satu, _ = tagihan(kon, 1)
    buat(kon, 2, sekarang="2026-11-18T12:00:00")
    buat(kon, 3, sekarang=SESUDAH_KEDALUWARSA)
    sebelum = _isi(kon)
    with pytest.raises(pesanan.PesananKuotaHabis):
        _ulang(kon, satu)
    assert _isi(kon) == sebelum


def test_order_bukan_milik_akun_tidak_ditemukan_identik_tanpa_tulis(kon):
    order, _ = tagihan(kon, 1)
    sebelum = _isi(kon)
    with pytest.raises(pesanan.PesananTidakDitemukan) as lain:
        _ulang(kon, order, akun=AKUN_B)
    with pytest.raises(pesanan.PesananTidakDitemukan) as asing:
        ul.buka_ulang(kon, "ord_" + "0" * 32, AKUN_A, SESUDAH_KEDALUWARSA, operasi(50))
    assert str(lain.value) == str(asing.value) and _isi(kon) == sebelum


def test_operasi_yang_sama_idempoten_tidak_membuka_dua_jendela(kon):
    order, _ = tagihan(kon, 1)
    pertama = _ulang(kon, order, 50)
    ulang = _ulang(kon, order, 50)
    assert (pertama["baru"], ulang["baru"], ulang["urutan"]) == (True, False, 2)
    assert hitung(kon, "pesanan_jendela") == 2


def test_nominal_dipegang_order_lain_tidak_dipakai_tagihan_jendela_baru(kon):
    satu, lama = tagihan(kon, 1, acak=lambda bebas: bebas[0])          # kode 1
    _ulang(kon, satu)
    lain, tag_lain = tagihan(kon, 2, akun=AKUN_B, sekarang=SESUDAH_KEDALUWARSA,
                             acak=lambda bebas: bebas[0])
    assert tag_lain["kode_unik"] == 1                                    # nominal jendela lama dilepas
    baru = tf.buat_tagihan_transfer(kon, satu["order_id"], AKUN_A, SESUDAH_KEDALUWARSA,
                                    acak=lambda bebas: bebas[0])
    assert baru["kode_unik"] == 2 and baru["nominal_transfer"] != tag_lain["nominal_transfer"]
    assert lama["kode_unik"] == 1


def test_tagihan_baru_bentrok_seluruh_kode_habis_ditolak(kon, monkeypatch):
    monkeypatch.setattr(tf, "KODE_MAKS", 1)
    satu, _ = tagihan(kon, 1)
    _ulang(kon, satu)
    tagihan(kon, 2, akun=AKUN_B, sekarang=SESUDAH_KEDALUWARSA)           # memegang satu-satunya kode
    with pytest.raises(tf.PesananKodeUnikHabis):
        tf.buat_tagihan_transfer(kon, satu["order_id"], AKUN_A, SESUDAH_KEDALUWARSA)


# --- tampilan guru -----------------------------------------------------------------

def test_tampilan_boleh_ulang_hanya_saat_kedaluwarsa(kon):
    order, _ = tagihan(kon, 1)
    assert _tampil(kon, order, sekarang=SEKARANG).boleh_ulang is False
    assert _tampil(kon, order).boleh_ulang is True


def test_tampilan_tidak_boleh_ulang_bila_bukti_menunggu_atau_lunas(kon):
    order, _ = tagihan(kon, 1)
    unggah(kon, order, 1)
    assert _tampil(kon, order).boleh_ulang is False
    tf.setujui(kon, order["order_id"], ADMIN, SESUDAH_UPLOAD)
    assert _tampil(kon, order).boleh_ulang is False


def test_tampilan_tidak_boleh_ulang_pada_jendela_kelima(kon):
    order, _ = tagihan(kon, 1)
    for urutan in range(1, 4):
        _ulang(kon, order, 50 + urutan, sekarang=_waktu(urutan))
    assert _tampil(kon, order, sekarang=_waktu(4)).boleh_ulang is True        # jendela keempat habis
    _ulang(kon, order, 54, sekarang=_waktu(4))
    assert _tampil(kon, order, sekarang=_waktu(5)).boleh_ulang is False       # jendela kelima habis


def test_tampilan_tidak_boleh_ulang_bila_kuota_habis(kon, monkeypatch):
    monkeypatch.setattr(pesanan_dasar, "KUOTA_ORDER", 2)
    satu, _ = tagihan(kon, 1)
    buat(kon, 2, sekarang="2026-11-18T12:00:00")
    buat(kon, 3, sekarang=SESUDAH_KEDALUWARSA)
    assert _tampil(kon, satu).boleh_ulang is False


def test_tampilan_dibangun_tanpa_argumen_boleh_ulang_bawaan_false():
    t = tt.TampilanTransfer(status="belum_bayar", nominal=None, kedaluwarsa=SEKARANG, alasan_tolak=None,
                            jumlah_bukti=0, boleh_tagihan=True, boleh_unggah=False)
    assert t.boleh_ulang is False
