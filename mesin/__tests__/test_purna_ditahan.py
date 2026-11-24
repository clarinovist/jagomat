"""Domain purna: voucher 'ditahan' bila order lunas tetapi status turunannya bukan sudah_dibayar (H-1), dan
penolakan laporan terbit sesudah keluarga meminta uang kembali (L-1). Data sintetis, QRIS dan transfer.

Tiga cara membuat order 'perlu_diperiksa' tetapi lunas: (1) dua jalur bayar (transfer disetujui lalu settlement QRIS),
(2) QRIS lunas lalu penyedia menyatakan refund, (3) QRIS lunas lalu chargeback. Tiap tes membuat ditahan satu-satunya
syarat yang gagal (sudah terlambat, belum kedaluwarsa, belum dipakai, belum direfund) supaya mutation terlihat.
"""
import pytest

import pesanan
import pesanan_dasar as d
import pesanan_status as st
import purna
from pesanan_kit import terapkan
from purna_kit import (PELAKU, SEKARANG, baris, db, hitung, kon, operasi, order_belum_lunas,  # noqa: F401
                       order_qris_lunas, order_transfer_lunas)

PESAN_DITAHAN = "pembayaran order perlu diperiksa"
PESAN_UANG_KEMBALI = "keluarga sudah meminta uang kembali"
SESUDAH_BATAS = "2026-11-24T00:00:00"      # lewat batas pilihan semua jalur (maks 23 Nov 13:00), sebelum kedaluwarsa
SESUDAH_HINGGA = "2027-03-01T00:00:00"     # lewat 90 hari voucher
SESUDAH_LUNAS = "2026-11-19T00:00:00"      # sesudah waktu lunas semua jalur, belum terlambat
JAM_SETTLEMENT_KEDUA = "2026-11-18T13:00:00"


def _dua_jalur(kon):
    oid = order_transfer_lunas(kon, 1)
    terapkan(kon, {"order_id": oid}, 7, sekarang=JAM_SETTLEMENT_KEDUA, transaction_id="trx-sintetis-0007")
    return oid


def _qris_dengan_observasi(status_provider):
    def buat(kon):
        oid = order_qris_lunas(kon, 1)
        terapkan(kon, {"order_id": oid}, 8, sekarang="2026-11-18T14:00:00", transaction_status=status_provider,
                 transaction_id="trx-sintetis-0001")
        return oid
    return buat


JALUR = {"dua_jalur": _dua_jalur, "qris_refund": _qris_dengan_observasi("refund"),
         "qris_chargeback": _qris_dengan_observasi("chargeback")}


@pytest.fixture(params=sorted(JALUR))
def ditahan(request, kon):
    """Order lunas yang status turunannya perlu_diperiksa (lihat docstring modul)."""
    oid = JALUR[request.param](kon)
    assert st.status_dari_db(kon, st.dict_order(st.baris_order(kon, oid)), SESUDAH_BATAS) == d.STATUS_PERLU_DIPERIKSA
    return oid


def _tabel_efek(kon):
    return {t: baris(kon, t) for t in ("purna_voucher_pakai", "purna_pilihan_terlambat", "purna_laporan_terbit",
                                       "pesanan_refund", "transfer_refund")}


# --- keadaan ---------------------------------------------------------------------------------

def test_order_perlu_diperiksa_tetap_lunas_tetapi_voucher_ditahan_dan_tidak_bisa_pilih(kon, ditahan):
    k = purna.keadaan(kon, ditahan, SESUDAH_BATAS)
    assert (k.lunas, k.direfund, k.dipakai, k.terbit, k.terlambat) == (True, False, False, None, True)
    assert k.ditahan is True
    assert k.voucher == purna.VOUCHER_DITAHAN == "ditahan"
    assert k.bisa_pilih is False


@pytest.mark.parametrize("buat_order", [order_qris_lunas, order_transfer_lunas])
def test_order_lunas_normal_tidak_ditahan_dan_voucher_aktif(kon, buat_order):
    oid = buat_order(kon, 1)
    k = purna.keadaan(kon, oid, SESUDAH_BATAS)
    assert k.ditahan is False and k.voucher == purna.VOUCHER_AKTIF and k.bisa_pilih is True


def test_order_belum_lunas_bukan_ditahan(kon):
    k = purna.keadaan(kon, order_belum_lunas(kon, 1), SESUDAH_BATAS)
    assert k.ditahan is False and k.voucher == purna.VOUCHER_BELUM_LUNAS


def test_ditahan_didahulukan_dari_kedaluwarsa_dan_aktif(kon, ditahan):
    assert purna.keadaan(kon, ditahan, SESUDAH_LUNAS).voucher == purna.VOUCHER_DITAHAN
    assert purna.keadaan(kon, ditahan, SESUDAH_HINGGA).voucher == purna.VOUCHER_DITAHAN


def test_dipakai_didahulukan_dari_ditahan(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pakai(kon, oid, operasi(1), PELAKU, "kelas", SEKARANG)
    terapkan(kon, {"order_id": oid}, 8, sekarang="2026-11-18T14:00:00", transaction_status="refund",
             transaction_id="trx-sintetis-0001")
    k = purna.keadaan(kon, oid, SESUDAH_LUNAS)
    assert k.ditahan is True and k.voucher == purna.VOUCHER_DIPAKAI


def test_batal_didahulukan_dari_ditahan(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, purna.PILIHAN_UANG_KEMBALI, SESUDAH_BATAS)
    terapkan(kon, {"order_id": oid}, 8, sekarang="2026-11-23T14:00:00", transaction_status="chargeback",
             transaction_id="trx-sintetis-0001")
    k = purna.keadaan(kon, oid, SESUDAH_BATAS)
    assert k.ditahan is True and k.voucher == purna.VOUCHER_BATAL


# --- tulis: voucher, terbit, pilihan ditolak pada order ditahan ----------------------------------

def test_pakai_ditolak_pada_order_ditahan_tanpa_tulis(kon, ditahan):
    sebelum = _tabel_efek(kon)
    with pytest.raises(d.PesananKonflik, match=PESAN_DITAHAN):
        purna.catat_pakai(kon, ditahan, operasi(1), PELAKU, "kelas", SESUDAH_LUNAS)
    assert _tabel_efek(kon) == sebelum and not kon.in_transaction


def test_terbit_ditolak_pada_order_ditahan_tanpa_tulis(kon, ditahan):
    sebelum = _tabel_efek(kon)
    with pytest.raises(d.PesananKonflik, match=PESAN_DITAHAN):
        purna.catat_terbit(kon, ditahan, PELAKU, SESUDAH_LUNAS)
    assert _tabel_efek(kon) == sebelum and not kon.in_transaction


@pytest.mark.parametrize("pilihan", list(purna.sk.PILIHAN_TERLAMBAT))
def test_pilihan_ditolak_pada_order_ditahan_tanpa_tulis(kon, ditahan, pilihan):
    sebelum = _tabel_efek(kon)
    with pytest.raises(d.PesananKonflik, match=PESAN_DITAHAN):
        purna.catat_pilihan(kon, ditahan, pilihan, SESUDAH_BATAS)
    assert _tabel_efek(kon) == sebelum and not kon.in_transaction


# --- refund tetap bisa dicatat pada order ditahan -------------------------------------------------

def test_refund_tetap_bisa_dicatat_pada_order_ditahan_lalu_voucher_batal(kon, ditahan):
    hasil = pesanan.catat_refund(kon, ditahan, operasi(50), PELAKU, "kebijakan", SESUDAH_BATAS)
    assert hasil == {"status": d.STATUS_DIREFUND, "baru": True}
    k = purna.keadaan(kon, ditahan, SESUDAH_BATAS)
    assert (k.direfund, k.ditahan, k.voucher) == (True, False, purna.VOUCHER_BATAL)
    assert hitung(kon, "pesanan_refund") + hitung(kon, "transfer_refund") >= 1
    with pytest.raises(d.PesananKonflik):
        purna.catat_pakai(kon, ditahan, operasi(51), PELAKU, "kelas", SESUDAH_BATAS)


# --- L-1: terbit ditolak sesudah keluarga minta uang kembali ---------------------------------------

def test_terbit_ditolak_sesudah_keluarga_minta_uang_kembali_tanpa_tulis(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, purna.PILIHAN_UANG_KEMBALI, SESUDAH_BATAS)
    sebelum = _tabel_efek(kon)
    with pytest.raises(d.PesananKonflik, match=PESAN_UANG_KEMBALI):
        purna.catat_terbit(kon, oid, PELAKU, SESUDAH_BATAS)
    assert _tabel_efek(kon) == sebelum and not kon.in_transaction


def test_terbit_ditolak_walau_keluarga_memilih_menunggu_lalu_uang_kembali(kon):
    oid = order_transfer_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, purna.PILIHAN_MENUNGGU, SESUDAH_BATAS)
    purna.catat_pilihan(kon, oid, purna.PILIHAN_UANG_KEMBALI, SESUDAH_BATAS)
    with pytest.raises(d.PesananKonflik, match=PESAN_UANG_KEMBALI):
        purna.catat_terbit(kon, oid, PELAKU, SESUDAH_BATAS)


def test_terbit_tetap_boleh_bila_keluarga_hanya_memilih_menunggu(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_pilihan(kon, oid, purna.PILIHAN_MENUNGGU, SESUDAH_BATAS)
    assert purna.catat_terbit(kon, oid, PELAKU, SESUDAH_BATAS) == {"baru": True}
    assert purna.keadaan(kon, oid, SESUDAH_BATAS).terbit == SESUDAH_BATAS


def test_terbit_replay_sesudah_tercatat_tetap_dilayani_walau_kini_ditahan(kon):
    oid = order_qris_lunas(kon, 1)
    purna.catat_terbit(kon, oid, PELAKU, SEKARANG)
    terapkan(kon, {"order_id": oid}, 8, sekarang="2026-11-18T14:00:00", transaction_status="refund",
             transaction_id="trx-sintetis-0001")
    assert purna.catat_terbit(kon, oid, PELAKU, SESUDAH_LUNAS) == {"baru": False}
