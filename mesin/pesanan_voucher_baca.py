"""Baca keadaan voucher/laporan untuk kartu di halaman status pembeli (V4a): SELECT saja, gagal = tanpa kartu.

Kartu hanya untuk order LUNAS dan hanya bila skema `purna_*` terpasang; selain itu fungsi ini mengembalikan None
dan halaman tampil seperti sebelumnya. Penyimpanan yang belum siap atau tak terbaca menyembunyikan kartu (dicatat
tanpa data), bukan membuat halaman status yang sudah berfungsi menjadi 503: kartu hanya informasi tambahan.
Kepemilikan: order selalu diturunkan dari akun sesi lalu divalidasi ulang lewat `pesanan_status.ambil_order`.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Optional

import admin_store
import admin_store_core
import pesanan_alur as alur
import pesanan_dasar as dasar
import pesanan_status
import pesanan_transfer
import purna

_LOG = logging.getLogger(__name__)


def keadaan_kartu(principal, status) -> Optional[purna.KeadaanPurna]:
    """Keadaan purna order milik akun sesi bila status `sudah_dibayar`, lunas, dan purna terpasang; selain itu None."""
    if status != dasar.STATUS_SUDAH_DIBAYAR:
        return None
    order_id = alur.order_id_akun(admin_store.BAWAAN, principal)
    if order_id is None:
        return None
    return keadaan_order(order_id, principal.id_akun)


def keadaan_order(order_id, akun_id, sekarang=None) -> Optional[purna.KeadaanPurna]:
    """Keadaan purna order milik `akun_id` (kepemilikan divalidasi ulang) bila lunas dan purna terpasang; selain itu None."""
    try:
        with pesanan_transfer.buka(admin_store.BAWAAN) as kon:
            if not purna.terpasang(kon):
                return None
            order = pesanan_status.ambil_order(kon, order_id, akun_id)
            k = purna.keadaan(kon, order["order_id"], alur.waktu_sekarang() if sekarang is None else sekarang)
    except (admin_store_core.StoreBelumSiap, dasar.PesananError, sqlite3.Error) as galat:
        _LOG.warning("kartu voucher pembeli tidak terbaca: %s", type(galat).__name__)
        return None
    return k if k.lunas else None
