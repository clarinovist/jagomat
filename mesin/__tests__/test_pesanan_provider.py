"""Hasil provider (transport palsu): receipt sekali, kecocokan ketat, status tak mundur."""
import sqlite3

import pytest

import pesanan
from pesanan_kit import (AKUN_A, MERCHANT, SEKARANG, SESUDAH_KEDALUWARSA, TRANSAKSI, buat,
                         hasil_status, hitung, operasi, ord_id, siapkan_db, terapkan)


@pytest.fixture
def kon(tmp_path):
    with pesanan.buka(siapkan_db(tmp_path), tulis_data=True) as k:
        yield k


@pytest.fixture
def order(kon):
    return buat(kon, 1)


def status(kon, order, sekarang=SEKARANG):
    return pesanan.status_order(kon, order["order_id"], AKUN_A, sekarang)["status"]


def receipt(kon):
    return [tuple(r) for r in kon.execute(
        "SELECT provider,transaksi_id,order_id,hasil,rupiah,alasan_kode FROM pesanan_receipt")]


def test_settlement_benar_menjadi_lunas_dan_sudah_dibayar(kon, order):
    assert status(kon, order) == "belum_bayar"
    hasil = terapkan(kon, order, 1)
    assert hasil == {"status": "sudah_dibayar", "receipt": "lunas", "pengamatan_baru": True}
    assert receipt(kon) == [("midtrans", TRANSAKSI, order["order_id"], "lunas", 49000, "ok")]
    assert status(kon, order) == "sudah_dibayar"


@pytest.mark.parametrize("nominal", ["49000", "49000.00", 49000])
def test_format_nominal_sah_setara_kontrak(kon, order, nominal):
    assert terapkan(kon, order, 1, gross_amount=nominal)["receipt"] == "lunas"


@pytest.mark.parametrize("status_provider", ["pending", "expire", "cancel", "deny", "capture",
                                             "authorize", "failure", "Settlement", "tak-dikenal"])
def test_status_bukan_settlement_hanya_pengamatan_tanpa_receipt(kon, order, status_provider):
    hasil = terapkan(kon, order, 1, transaction_status=status_provider,
                     status_code="201" if status_provider == "pending" else "407")
    assert hasil["receipt"] is None and hasil["status"] == "belum_bayar"
    assert receipt(kon) == [] and hitung(kon, "pesanan_pengamatan") == 1
    assert status(kon, order) == "belum_bayar"


@pytest.mark.parametrize("status_provider", ["pending", "expire", "cancel", "deny", "capture",
                                             "authorize", "refund_x", "Settlement"])
def test_status_bukan_settlement_walau_semua_field_lain_cocok_tanpa_receipt(kon, order, status_provider):
    hasil = terapkan(kon, order, 1, transaction_status=status_provider, status_code="200")
    assert hasil["receipt"] is None and receipt(kon) == []
    assert status(kon, order) == "belum_bayar"


@pytest.mark.parametrize("ganti", [
    dict(status_code="201"), dict(status_code=None), dict(fraud_status="challenge"),
    dict(fraud_status="deny"), dict(transaction_id=None), dict(transaction_id="bad id"),
])
def test_settlement_tanpa_syarat_kontrak_tidak_membuat_receipt(kon, order, ganti):
    assert terapkan(kon, order, 1, **ganti)["receipt"] is None
    assert receipt(kon) == [] and status(kon, order) == "belum_bayar"


def test_fraud_status_kosong_diterima_seperti_kontrak(kon, order):
    assert terapkan(kon, order, 1, fraud_status=None)["receipt"] == "lunas"


@pytest.mark.parametrize("ganti,alasan,rupiah", [
    (dict(gross_amount="48000"), "nominal", 48000),
    (dict(gross_amount="50000.00"), "nominal", 50000),
    (dict(gross_amount="49000.50"), "nominal", 0),
    (dict(gross_amount=49000.0), "nominal", 0),
    (dict(gross_amount=None), "nominal", 0),
    (dict(merchant_id="M_LAIN"), "merchant", 49000),
    (dict(merchant_id=None), "merchant", 49000),
    (dict(currency="USD"), "mata_uang", 49000),
    (dict(payment_type="gopay"), "kanal", 49000),
    (dict(payment_type=None), "kanal", 49000),
])
def test_ketidakcocokan_settlement_menjadi_perlu_diperiksa_bukan_lunas(kon, order, ganti, alasan, rupiah):
    hasil = terapkan(kon, order, 1, **ganti)
    assert hasil["receipt"] == "perlu_diperiksa" and hasil["status"] == "perlu_diperiksa"
    assert receipt(kon) == [("midtrans", TRANSAKSI, order["order_id"], "perlu_diperiksa", rupiah, alasan)]
    assert status(kon, order) == "perlu_diperiksa"


@pytest.mark.parametrize("status_refund", ["refund", "partial_refund", "chargeback"])
def test_refund_provider_tanpa_receipt_menjadi_perlu_diperiksa(kon, order, status_refund):
    hasil = terapkan(kon, order, 1, transaction_status=status_refund)
    assert hasil["receipt"] == "perlu_diperiksa"
    assert receipt(kon)[0][3:] == ("perlu_diperiksa", 49000, "refund")


def test_order_id_hasil_provider_harus_terikat_ke_order(kon, order):
    for data in (hasil_status(order, order_id=ord_id(99)), hasil_status(order, order_id=None),
                 "bukan dict", None):
        with pytest.raises(pesanan.PesananDataTidakSah):
            pesanan.terapkan_hasil_provider(kon, order["order_id"], data, SEKARANG, operasi(1))
    assert hitung(kon, "pesanan_pengamatan") == 0 and receipt(kon) == []


def test_order_tak_dikenal_tidak_menulis_apa_pun(kon):
    hantu = {"order_id": ord_id(404)}
    with pytest.raises(pesanan.PesananTidakDitemukan):
        pesanan.terapkan_hasil_provider(kon, ord_id(404), hasil_status(hantu), SEKARANG, operasi(1))
    assert hitung(kon, "pesanan_pengamatan") == 0 and receipt(kon) == []


def test_panggilan_ganda_operasi_sama_tepat_satu_receipt_dan_satu_pengamatan(kon, order):
    pertama = terapkan(kon, order, 1)
    ulang = terapkan(kon, order, 1)
    assert pertama["pengamatan_baru"] is True and ulang["pengamatan_baru"] is False
    assert ulang["status"] == "sudah_dibayar" and ulang["receipt"] is None
    assert len(receipt(kon)) == 1 and hitung(kon, "pesanan_pengamatan") == 1


def test_operasi_sama_isi_beda_adalah_konflik_tanpa_efek(kon, order):
    terapkan(kon, order, 1)
    with pytest.raises(pesanan.PesananKonflik):
        terapkan(kon, order, 1, gross_amount="1")
    assert len(receipt(kon)) == 1 and hitung(kon, "pesanan_pengamatan") == 1


def test_operasi_baru_data_sama_tetap_satu_receipt(kon, order):
    terapkan(kon, order, 1)
    ulang = terapkan(kon, order, 2)
    assert ulang["receipt"] is None and ulang["pengamatan_baru"] is True
    assert len(receipt(kon)) == 1 and status(kon, order) == "sudah_dibayar"


def test_transaksi_lain_setelah_receipt_hanya_pengamatan_status_tidak_berubah(kon, order):
    terapkan(kon, order, 1)
    ulang = terapkan(kon, order, 2, transaction_id="trx-lain", gross_amount="1")
    assert ulang["receipt"] is None and len(receipt(kon)) == 1
    assert receipt(kon)[0][1] == TRANSAKSI and status(kon, order) == "sudah_dibayar"


@pytest.mark.parametrize("susulan", ["pending", "expire", "cancel", "deny"])
def test_status_tidak_mundur_setelah_lunas(kon, order, susulan):
    terapkan(kon, order, 1)
    terapkan(kon, order, 2, transaction_status=susulan, status_code="201")
    assert receipt(kon)[0][3] == "lunas"
    assert status(kon, order) == "sudah_dibayar"
    assert status(kon, order, SESUDAH_KEDALUWARSA) == "sudah_dibayar"


def test_receipt_perlu_diperiksa_tidak_berubah_menjadi_lunas_oleh_settlement_benar(kon, order):
    terapkan(kon, order, 1, gross_amount="48000")
    terapkan(kon, order, 2)
    assert receipt(kon)[0][3] == "perlu_diperiksa" and receipt(kon)[0][5] == "nominal"
    assert status(kon, order) == "perlu_diperiksa"


def test_settlement_terlambat_setelah_kedaluwarsa_lokal_tetap_lunas(kon, order):
    assert status(kon, order, SESUDAH_KEDALUWARSA) == "kedaluwarsa"
    terapkan(kon, order, 1, sekarang=SESUDAH_KEDALUWARSA)
    assert status(kon, order, SESUDAH_KEDALUWARSA) == "sudah_dibayar"


def test_kedaluwarsa_hanya_bila_sekarang_mencapai_batas_dan_tanpa_receipt(kon, order):
    assert status(kon, order, "2026-11-19T09:59:59") == "belum_bayar"
    assert status(kon, order, order["kedaluwarsa"]) == "kedaluwarsa"
    terapkan(kon, order, 1, gross_amount="48000")
    assert status(kon, order, SESUDAH_KEDALUWARSA) == "perlu_diperiksa"


def test_refund_teramati_setelah_lunas_gagal_aman_menjadi_perlu_diperiksa(kon, order):
    terapkan(kon, order, 1)
    terapkan(kon, order, 2, transaction_status="partial_refund")
    assert len(receipt(kon)) == 1 and receipt(kon)[0][3] == "lunas"
    assert status(kon, order) == "perlu_diperiksa"


def test_transaksi_sama_untuk_order_lain_adalah_konflik_tanpa_efek(kon, order):
    lain = buat(kon, 2)
    terapkan(kon, order, 1)
    with pytest.raises(pesanan.PesananKonflik):
        terapkan(kon, lain, 2)
    assert len(receipt(kon)) == 1 and hitung(kon, "pesanan_pengamatan") == 1
    assert status(kon, lain) == "belum_bayar"


def test_sudah_dibayar_tidak_pernah_ada_sebelum_receipt(kon, order):
    for n, kondisi in enumerate(("pending", "expire", "deny", "cancel", "capture"), start=1):
        terapkan(kon, order, n, transaction_status=kondisi, status_code="201")
        assert status(kon, order) != "sudah_dibayar"
    petunjuk = pesanan.catat_petunjuk(kon, order["order_id"], hasil_status(order), SEKARANG, operasi(50))
    assert petunjuk["status"] == "belum_bayar"
    assert status(kon, order) == "belum_bayar" and receipt(kon) == []


def test_petunjuk_callback_settlement_tidak_pernah_membuat_receipt_atau_lunas(kon, order):
    hasil = pesanan.catat_petunjuk(kon, order["order_id"], hasil_status(order), SEKARANG, operasi(1))
    assert hasil == {"status": "belum_bayar", "pengamatan_baru": True}
    assert receipt(kon) == [] and hitung(kon, "pesanan_receipt") == 0
    row = kon.execute("SELECT sumber,transaction_status FROM pesanan_pengamatan").fetchone()
    assert tuple(row) == ("callback", "settlement")


def test_petunjuk_callback_refund_tidak_menurunkan_status_lunas(kon, order):
    terapkan(kon, order, 1)
    pesanan.catat_petunjuk(kon, order["order_id"], hasil_status(order, transaction_status="refund"),
                           SEKARANG, operasi(2))
    assert status(kon, order) == "sudah_dibayar"


def test_petunjuk_idempoten_konflik_dan_order_tak_dikenal(kon, order):
    data = hasil_status(order, transaction_status="pending", status_code="201")
    assert pesanan.catat_petunjuk(kon, order["order_id"], data, SEKARANG, operasi(1))["pengamatan_baru"]
    assert not pesanan.catat_petunjuk(kon, order["order_id"], data, SEKARANG, operasi(1))["pengamatan_baru"]
    with pytest.raises(pesanan.PesananKonflik):
        pesanan.catat_petunjuk(kon, order["order_id"], hasil_status(order), SEKARANG, operasi(1))
    with pytest.raises(pesanan.PesananTidakDitemukan):
        pesanan.catat_petunjuk(kon, ord_id(404), data, SEKARANG, operasi(2))
    assert hitung(kon, "pesanan_pengamatan") == 1


def test_pengamatan_tidak_menyimpan_payload_mentah(kon, order):
    terapkan(kon, order, 1, transaction_status="<script>x</script>", gross_amount="rahasia-sekali",
             merchant_id="NAMA ANAK", status_code="abc", extra="payload mentah")
    isi = tuple(kon.execute("SELECT * FROM pesanan_pengamatan").fetchone())
    assert "tidak_dikenal" in isi
    teks = " ".join(str(x) for x in isi)
    for terlarang in ("script", "rahasia", "NAMA", "payload", MERCHANT):
        assert terlarang not in teks


def test_penerapan_atomik_receipt_gagal_membatalkan_pengamatan(kon, order, monkeypatch):
    import pesanan_provider

    def rusak(*a, **k):
        raise sqlite3.OperationalError("disk penuh")
    monkeypatch.setattr(pesanan_provider, "_tulis_receipt", rusak)
    with pytest.raises(sqlite3.OperationalError):
        terapkan(kon, order, 1)
    assert hitung(kon, "pesanan_pengamatan") == 0 and receipt(kon) == []
    assert not kon.in_transaction
