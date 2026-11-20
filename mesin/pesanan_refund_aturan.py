"""Aturan server untuk catatan refund manual: satu catatan per order di KEDUA tabel, dan status layak.

Refund tercatat di `pesanan_refund` (jalur penyedia, order ber-receipt) atau `transfer_refund` (jalur transfer
rekening). Tabel dipilih dari ada-tidaknya receipt, jadi receipt penyedia yang masuk belakangan pada order
transfer bisa mengarahkan refund kedua ke tabel lain. Karena itu replay dan konflik selalu diperiksa di kedua
tabel sebelum INSERT. Status turunan juga ditegakkan di sini (bukan hanya disembunyikan tombolnya di UI).

Dipanggil di dalam transaksi tulis pemanggil. Tanpa impor selain domain pesanan; bukan modul kontrak rilis.
"""
from __future__ import annotations

import pesanan_dasar as d
import pesanan_status as st
import pesanan_transfer_baca as tb

_SQL_REFUND = {
    "pesanan_refund": "SELECT operasi_id,order_id,dicatat_oleh,catatan_kode FROM pesanan_refund "
                      "WHERE operasi_id=? OR order_id=?",
    "transfer_refund": "SELECT operasi_id,order_id,dicatat_oleh,catatan_kode FROM transfer_refund "
                       "WHERE operasi_id=? OR order_id=?",
}


def _catatan_ada(kon, operasi_id, order_id):
    """Semua baris refund (kedua tabel) yang memakai `operasi_id` atau `order_id` ini."""
    tabel = ("pesanan_refund", "transfer_refund") if tb.terpasang(kon) else ("pesanan_refund",)
    return [tuple(b) for t in tabel for b in kon.execute(_SQL_REFUND[t], (operasi_id, order_id))]


def refund_sudah_ada(kon, operasi_id, isi):
    """True = replay identik (tanpa tulis), False = belum ada catatan refund apa pun untuk operasi/order.

    `isi` = (order_id, dicatat_oleh, catatan_kode). Baris apa pun (di tabel mana pun) yang bukan replay
    identik -> PesananKonflik: operasi sama isi beda, atau order sudah punya catatan dengan operasi lain.
    """
    ada = _catatan_ada(kon, operasi_id, isi[0])
    if any(b[0] != operasi_id or b[1:] != isi for b in ada):
        raise d.PesananKonflik("order atau operasi refund sudah punya catatan lain")
    return bool(ada)


def periksa_layak_refund(kon, order_id, kini):
    """Tolak (PesananKonflik) bila status turunan order tidak termasuk `STATUS_BISA_REFUND`."""
    baris = st.baris_order(kon, order_id)
    if baris is None:
        raise d.PesananTidakDitemukan()
    if st.status_dari_db(kon, st.dict_order(baris), kini) not in d.STATUS_BISA_REFUND:
        raise d.PesananKonflik("status order tidak layak refund")


def siapkan_refund(kon, operasi_id, isi, kini):
    """True bila replay identik (lewati tulis); False bila boleh INSERT; selain itu PesananKonflik."""
    if refund_sudah_ada(kon, operasi_id, isi):
        return True
    periksa_layak_refund(kon, isi[0], kini)
    return False
