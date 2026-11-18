"""Baca order dan status turunan pesanan (SELECT saja, tanpa tulis).

Status tidak pernah disimpan: selalu diturunkan dari receipt, catatan refund,
pengamatan status server-ke-server, dan waktu. Jadi `sudah_dibayar` mustahil
ada sebelum receipt lunas terverifikasi.
"""
from __future__ import annotations

import pesanan_dasar as d

KOLOM_ORDER = ("order_id", "akun_id", "siswa_id", "cek_id", "rupiah", "currency",
               "provider", "channel", "merchant", "idempotency_key", "dibuat",
               "kedaluwarsa")

_SQL_REFUND_TERAMATI = (
    "SELECT 1 FROM pesanan_pengamatan WHERE order_id=? AND sumber='status' "
    "AND transaction_status IN (%s) LIMIT 1"
    % ",".join("'%s'" % s for s in d.STATUS_REFUND_PROVIDER))


def dict_order(baris):
    """Baris order menjadi dict baru berkunci tetap."""
    return {k: baris[k] for k in KOLOM_ORDER}


def baris_order(kon, order_id):
    return kon.execute(
        "SELECT %s FROM pesanan_order WHERE order_id=?" % ",".join(KOLOM_ORDER),
        (order_id,)).fetchone()


def receipt_order(kon, order_id):
    return kon.execute(
        "SELECT provider,transaksi_id,hasil,rupiah,alasan_kode FROM pesanan_receipt "
        "WHERE order_id=?", (order_id,)).fetchone()


def turunkan_status(*, kedaluwarsa, sekarang, receipt_hasil, direfund, refund_teramati):
    """Fungsi murni: status turunan dari fakta.

    Refund tercatat menang. Receipt lunas menjadi `perlu_diperiksa` bila status
    server-ke-server kemudian menyatakan refund/chargeback (fail-closed, bukan
    mundur ke belum_bayar). `kedaluwarsa` hanya untuk order tanpa receipt.
    """
    if direfund:
        return d.STATUS_DIREFUND
    if receipt_hasil == "lunas":
        return d.STATUS_PERLU_DIPERIKSA if refund_teramati else d.STATUS_SUDAH_DIBAYAR
    if receipt_hasil == "perlu_diperiksa":
        return d.STATUS_PERLU_DIPERIKSA
    return d.STATUS_KEDALUWARSA if sekarang >= kedaluwarsa else d.STATUS_BELUM_BAYAR


def status_dari_db(kon, order, sekarang_baku):
    """Status turunan satu order (dict/Row dengan order_id & kedaluwarsa)."""
    receipt = receipt_order(kon, order["order_id"])
    direfund = kon.execute("SELECT 1 FROM pesanan_refund WHERE order_id=?",
                           (order["order_id"],)).fetchone() is not None
    teramati = kon.execute(_SQL_REFUND_TERAMATI, (order["order_id"],)).fetchone() is not None
    return turunkan_status(
        kedaluwarsa=order["kedaluwarsa"], sekarang=sekarang_baku,
        receipt_hasil=None if receipt is None else receipt["hasil"],
        direfund=direfund, refund_teramati=teramati)


def ambil_order(kon, order_id, akun_id):
    """Order milik akun ini sebagai dict baru; selain itu PesananTidakDitemukan.

    Format id salah, order tak ada, dan order milik akun lain menghasilkan galat
    yang identik (tanpa membedakan). Kepemilikan lewat `akun_id`, bukan id klien.
    """
    d.periksa_koneksi(kon)
    try:
        d.periksa_order_id(order_id)
        d.periksa_akun_id(akun_id)
    except d.PesananDataTidakSah:
        raise d.PesananTidakDitemukan() from None
    baris = baris_order(kon, order_id)
    if baris is None or baris["akun_id"] != akun_id:
        raise d.PesananTidakDitemukan()
    return dict_order(baris)


def status_order(kon, order_id, akun_id, sekarang):
    """Status turunan order milik akun; data minimal untuk halaman status."""
    order = ambil_order(kon, order_id, akun_id)
    kini = d.waktu_baku(sekarang)
    return {"order_id": order["order_id"], "rupiah": order["rupiah"],
            "dibuat": order["dibuat"], "kedaluwarsa": order["kedaluwarsa"],
            "status": status_dari_db(kon, order, kini)}
