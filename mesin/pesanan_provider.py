"""Penerapan hasil provider ke ledger pesanan (tanpa jaringan).

Dua pintu yang sengaja terpisah:

* :func:`terapkan_hasil_provider` menerima hasil query status server-ke-server
  (bukan callback) dan SATU-SATUNYA jalur yang boleh membuat receipt.
* :func:`catat_petunjuk` mencatat petunjuk callback sebagai pengamatan saja;
  tidak pernah membuat receipt dan tidak memengaruhi status turunan.

Aturan lunas mengikuti `midtrans_contract`: `transaction_status=='settlement'`,
`status_code=='200'`, `fraud_status` kosong/`accept`; QRIS tidak punya jalur
`capture`. Pengurai nominal meniru `midtrans_contract.nominal_provider`
(kesetaraan dijaga tes) tanpa mengimpor modul langganan.
"""
from __future__ import annotations

import re
import sqlite3

import pesanan_dasar as d
import pesanan_status as st

_POLA_NOMINAL = re.compile(r"(?:0|[1-9][0-9]{0,7})(?:\.00)?")
_POLA_KODE = re.compile(r"[0-9]{1,8}")
_FRAUD_TERIMA = (None, "accept")
BATAS_NOMINAL = 10_000_000  # sama dengan subscription.BATAS_RUPIAH dipakai kontrak


def nominal_provider(nilai):
    """Nominal bulat dari `gross_amount` (str/int, opsional '.00'); selain itu None."""
    if type(nilai) not in (str, int) or _POLA_NOMINAL.fullmatch(str(nilai)) is None:
        return None
    hasil = int(str(nilai).split(".")[0])
    return hasil if hasil <= BATAS_NOMINAL else None


def _teks_nominal(nilai):
    teks = str(nilai) if type(nilai) in (str, int) else ""
    return teks if re.fullmatch(r"[0-9.]{0,20}", teks) else ""


def _kode(nilai):
    return nilai if type(nilai) is str and _POLA_KODE.fullmatch(nilai) else ""


def _transaksi_id(nilai):
    try:
        return d.periksa_referensi(nilai, "transaksi_id")
    except d.PesananDataTidakSah:
        return None


def _jejak(order_id, sumber, data):
    """Tuple pengamatan tersanitasi (tanpa gema payload) untuk dicatat/dibandingkan."""
    if type(data) is not dict:
        raise d.PesananDataTidakSah("hasil provider tidak sah")
    return (order_id, sumber, d.status_aman(data.get("transaction_status")),
            _kode(data.get("status_code")), _transaksi_id(data.get("transaction_id")),
            _teks_nominal(data.get("gross_amount")))


def _catat_pengamatan(kon, jejak, operasi_id, kini):
    """True bila baris baru; False bila replay identik; PesananKonflik bila isi beda."""
    lama = kon.execute(
        "SELECT order_id,sumber,transaction_status,status_code,transaksi_id,gross_amount_teks "
        "FROM pesanan_pengamatan WHERE operasi_id=?", (operasi_id,)).fetchone()
    if lama is not None:
        if tuple(lama) != jejak:
            raise d.PesananKonflik("operasi pengamatan sama dengan isi berbeda")
        return False
    kon.execute(
        """INSERT INTO pesanan_pengamatan(operasi_id,order_id,sumber,transaction_status,
               status_code,transaksi_id,gross_amount_teks,dibuat) VALUES(?,?,?,?,?,?,?,?)""",
        (operasi_id,) + jejak + (kini,))
    return True


def _alasan_tak_cocok(order, data):
    """Alasan_kode pertama yang gagal (nominal, merchant, mata_uang, kanal) atau None."""
    if nominal_provider(data.get("gross_amount")) != order["rupiah"]:
        return "nominal"
    if data.get("merchant_id") != order["merchant"]:
        return "merchant"
    if data.get("currency") != order["currency"]:
        return "mata_uang"
    if data.get("payment_type") != order["channel"]:
        return "kanal"
    return None


def _putusan(order, data, jejak):
    """(hasil, alasan_kode, rupiah) untuk receipt, atau None bila hanya pengamatan."""
    _, _, status, kode, transaksi, _ = jejak
    if transaksi is None:
        return None
    nominal = nominal_provider(data.get("gross_amount"))
    rupiah = 0 if nominal is None else nominal
    if status in d.STATUS_REFUND_PROVIDER:
        return "perlu_diperiksa", "refund", rupiah
    if status != "settlement" or kode != "200" or data.get("fraud_status") not in _FRAUD_TERIMA:
        return None
    alasan = _alasan_tak_cocok(order, data)
    if alasan is not None:
        return "perlu_diperiksa", alasan, rupiah
    return "lunas", "ok", rupiah


def _tulis_receipt(kon, order, transaksi_id, putusan, kini):
    """Receipt sekali per order; transaksi yang sama untuk order lain = konflik."""
    if st.receipt_order(kon, order["order_id"]) is not None:
        return None
    milik = kon.execute("SELECT order_id FROM pesanan_receipt WHERE provider=? AND transaksi_id=?",
                        (d.PROVIDER, transaksi_id)).fetchone()
    if milik is not None:
        raise d.PesananKonflik("transaksi sudah terikat ke order lain")
    hasil, alasan, rupiah = putusan
    kon.execute(
        """INSERT INTO pesanan_receipt(provider,transaksi_id,order_id,hasil,rupiah,alasan_kode,dibuat)
           VALUES(?,?,?,?,?,?,?)""",
        (d.PROVIDER, transaksi_id, order["order_id"], hasil, rupiah, alasan, kini))
    return hasil


def _siapkan(kon, order_id, data, sekarang, operasi_id, sumber):
    d.periksa_order_id(order_id)
    d.periksa_operasi_id(operasi_id)
    kini = d.waktu_baku(sekarang)
    return kini, _jejak(order_id, sumber, data)


def _order_ada(kon, order_id):
    baris = st.baris_order(kon, order_id)
    if baris is None:
        raise d.PesananTidakDitemukan()
    return st.dict_order(baris)


def terapkan_hasil_provider(kon, order_id, hasil_provider, sekarang, operasi_id):
    """Terapkan hasil status server-ke-server satu order (atomik, idempoten).

    `hasil_provider` memakai kunci respons status Midtrans: order_id,
    transaction_status, status_code, transaction_id, gross_amount, merchant_id,
    currency, payment_type, fraud_status. `order_id` di dalamnya wajib sama
    dengan `order_id` argumen (binding), selain itu PesananDataTidakSah tanpa
    tulis. Selalu menulis pengamatan; membuat receipt hanya untuk settlement
    (lunas bila semua cocok, selain itu `perlu_diperiksa`) atau status
    refund/chargeback. Pending/expire/cancel/deny/capture hanya pengamatan.
    Mengembalikan {status, receipt, pengamatan_baru}.
    """
    d.periksa_koneksi(kon)
    kini, jejak = _siapkan(kon, order_id, hasil_provider, sekarang, operasi_id, "status")
    if hasil_provider.get("order_id") != order_id:
        raise d.PesananDataTidakSah("hasil provider tidak terikat ke order")
    with d.tulis(kon):
        order = _order_ada(kon, order_id)
        baru = _catat_pengamatan(kon, jejak, operasi_id, kini)
        receipt = None
        putusan = _putusan(order, hasil_provider, jejak) if baru else None
        if putusan is not None:
            receipt = _tulis_receipt(kon, order, jejak[4], putusan, kini)
        return {"status": st.status_dari_db(kon, order, kini), "receipt": receipt,
                "pengamatan_baru": baru}


def catat_petunjuk(kon, order_id, petunjuk, sekarang, operasi_id):
    """Catat petunjuk callback sebagai pengamatan; TIDAK pernah membuat receipt.

    Order tak dikenal -> PesananTidakDitemukan (pemanggil mengalihkan ke yatim).
    Mengembalikan {status, pengamatan_baru}; status tidak dipengaruhi petunjuk.
    """
    d.periksa_koneksi(kon)
    kini, jejak = _siapkan(kon, order_id, petunjuk, sekarang, operasi_id, "callback")
    with d.tulis(kon):
        order = _order_ada(kon, order_id)
        baru = _catat_pengamatan(kon, jejak, operasi_id, kini)
        return {"status": st.status_dari_db(kon, order, kini), "pengamatan_baru": baru}
