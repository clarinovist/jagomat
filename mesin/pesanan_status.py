"""Baca order dan status turunan pesanan (SELECT saja, tanpa tulis).

Status tidak pernah disimpan: selalu diturunkan dari receipt, catatan refund,
pengamatan status server-ke-server, dan waktu. Kedaluwarsa memakai jendela bayar
TERBARU (`pesanan_jendela`), bukan `pesanan_order.kedaluwarsa` (jendela #1). Jadi `sudah_dibayar` mustahil
ada sebelum receipt lunas terverifikasi.
"""
from __future__ import annotations

import pesanan_dasar as d
import pesanan_transfer_baca as tb

KOLOM_ORDER = ("order_id", "akun_id", "siswa_id", "cek_id", "rupiah", "currency",
               "provider", "channel", "merchant", "idempotency_key", "dibuat",
               "kedaluwarsa")

_SQL_REFUND_TERAMATI = (
    "SELECT 1 FROM pesanan_pengamatan WHERE order_id=? AND sumber='status' "
    "AND transaction_status IN (%s) LIMIT 1"
    % ",".join("'%s'" % s for s in d.STATUS_REFUND_PROVIDER))


# Fragmen SQL: kedaluwarsa jendela terbaru (urutan tertinggi) sebuah order alias `o`.
SQL_KEDALUWARSA_TERBARU = (
    "(SELECT j.kedaluwarsa FROM pesanan_jendela j WHERE j.order_id=o.order_id "
    "ORDER BY j.urutan DESC LIMIT 1)")

_KOLOM_JENDELA = ("urutan", "idempotency_key", "dibuat", "kedaluwarsa")


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


def jendela_terbaru(kon, order_id):
    """Jendela bayar terbaru satu order (dict baru) tanpa data sensitif.

    Kunci: urutan, idempotency_key, dibuat, kedaluwarsa. Order tanpa jendela
    (tidak ada / format salah) -> PesananTidakDitemukan. Kepemilikan diperiksa
    pemanggil lewat :func:`ambil_order`.
    """
    d.periksa_koneksi(kon)
    try:
        d.periksa_order_id(order_id)
    except d.PesananDataTidakSah:
        raise d.PesananTidakDitemukan() from None
    baris = kon.execute(
        "SELECT %s FROM pesanan_jendela WHERE order_id=? ORDER BY urutan DESC LIMIT 1"
        % ",".join(_KOLOM_JENDELA), (order_id,)).fetchone()
    if baris is None:
        raise d.PesananTidakDitemukan()
    return {k: baris[k] for k in _KOLOM_JENDELA}


def dua_jalur(receipt_hasil, transfer_lunas, transfer_bukti):
    """True bila receipt provider lunas DAN jejak transfer aktif (lunas atau bukti menunggu).

    Uang berpotensi masuk dua kali (QRIS dan rekening): status dipaksa `perlu_diperiksa` dan admin
    diberi penanda untuk memeriksa refund. Bukti ditolak tidak dihitung (tidak ada klaim transfer aktif).
    """
    return receipt_hasil == "lunas" and (bool(transfer_lunas) or transfer_bukti == tb.BUKTI_MENUNGGU)


def turunkan_status(*, kedaluwarsa, sekarang, receipt_hasil, direfund, refund_teramati,
                    transfer_lunas=False, transfer_direfund=False, transfer_bukti=None):
    """Fungsi murni: status turunan dari fakta.

    Refund tercatat menang. Receipt lunas menjadi `perlu_diperiksa` bila status
    server-ke-server kemudian menyatakan refund/chargeback (fail-closed, bukan
    mundur ke belum_bayar). `kedaluwarsa` hanya untuk order tanpa receipt.

    Jalur transfer rekening (argumen bernama berbawaan, pemanggil lama tak berubah):
    `transfer_lunas` -> sudah_dibayar (receipt provider ikut ada = anomali ->
    perlu_diperiksa); `transfer_bukti='menunggu'` -> menunggu_verifikasi dan TIDAK
    kedaluwarsa (bukti diunggah di dalam jendela bayar, keputusan admin yang menentukan);
    `'ditolak'` -> ditolak selama jendela masih terbuka, sesudahnya kedaluwarsa.
    Receipt provider lunas bersama bukti transfer menunggu (atau transfer lunas) = dua jalur
    (:func:`dua_jalur`) -> perlu_diperiksa, bukan sudah_dibayar.
    """
    if direfund or transfer_direfund:
        return d.STATUS_DIREFUND
    if dua_jalur(receipt_hasil, transfer_lunas, transfer_bukti):
        return d.STATUS_PERLU_DIPERIKSA
    if transfer_lunas:
        return d.STATUS_PERLU_DIPERIKSA if receipt_hasil is not None else d.STATUS_SUDAH_DIBAYAR
    if receipt_hasil == "lunas":
        return d.STATUS_PERLU_DIPERIKSA if refund_teramati else d.STATUS_SUDAH_DIBAYAR
    if receipt_hasil == "perlu_diperiksa":
        return d.STATUS_PERLU_DIPERIKSA
    if transfer_bukti == tb.BUKTI_MENUNGGU:
        return d.STATUS_MENUNGGU_VERIFIKASI
    if sekarang >= kedaluwarsa:
        return d.STATUS_KEDALUWARSA
    return d.STATUS_DITOLAK if transfer_bukti == tb.BUKTI_DITOLAK else d.STATUS_BELUM_BAYAR


def status_dari_db(kon, order, sekarang_baku):
    """Status turunan satu order (dict/Row dengan order_id); jendela terbaru menentukan kedaluwarsa."""
    receipt = receipt_order(kon, order["order_id"])
    direfund = kon.execute("SELECT 1 FROM pesanan_refund WHERE order_id=?",
                           (order["order_id"],)).fetchone() is not None
    teramati = kon.execute(_SQL_REFUND_TERAMATI, (order["order_id"],)).fetchone() is not None
    transfer = tb.fakta(kon, order["order_id"])
    return turunkan_status(
        kedaluwarsa=jendela_terbaru(kon, order["order_id"])["kedaluwarsa"],
        sekarang=sekarang_baku, receipt_hasil=None if receipt is None else receipt["hasil"],
        direfund=direfund, refund_teramati=teramati, transfer_lunas=transfer["lunas"],
        transfer_direfund=transfer["direfund"], transfer_bukti=transfer["bukti"])


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
            "dibuat": order["dibuat"],
            "kedaluwarsa": jendela_terbaru(kon, order["order_id"])["kedaluwarsa"],
            "status": status_dari_db(kon, order, kini)}
