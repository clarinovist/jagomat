"""Bukti transfer menunggu di jalur Latihan Harian dan Paket Belajar, untuk antrean dan penanda sidebar admin.

Read-only. Kedua jalur punya ledger sendiri (Latihan Harian di DB belajar, Paket Belajar di DB admin) dan halaman ACC
sendiri, jadi tidak muncul di daftar Pesanan (Peta). Modul ini hanya menyatukan angkanya supaya admin melihat
penandanya di satu tempat. Bentuk hasil sama dengan `admin_transfer_menunggu` (order, nominal, waktu unggah terakhir),
tanpa nama anak, kontak, atau nama berkas. Galat baca (skema belum dipasang, DB tak terbaca) berarti "tidak ada":
penanda sidebar tidak boleh menjatuhkan halaman admin.
"""
from __future__ import annotations

from typing import Tuple

import admin_transfer_menunggu as menunggu
import database
import harian_langganan_putusan
import kelas_store

JUDUL_HARIAN = "Langganan Latihan Harian: transfer menunggu verifikasi"
JUDUL_KELAS = "Paket Belajar: transfer menunggu verifikasi"


def harian_menunggu(sekarang_iso: str) -> Tuple[menunggu.TransferMenunggu, ...]:
    """Order Latihan Harian dengan bukti belum diputuskan, terlama dulu; galat baca = ()."""
    try:
        with database.buka() as kon:
            baris = harian_langganan_putusan.antrean(kon, sekarang_iso)
    except menunggu.GALAT_BACA:
        return ()
    return tuple(menunggu.TransferMenunggu(b["order_id"], b["nominal"], b["diunggah"]) for b in baris)


def kelas_menunggu(path_admin) -> Tuple[menunggu.TransferMenunggu, ...]:
    """Order Paket Belajar dengan bukti belum diputuskan, terlama dulu; kelas belum dipasang/galat baca = ()."""
    try:
        with kelas_store.buka(path_admin) as kon:
            daftar = kelas_store.antrean(kon)
    except menunggu.GALAT_BACA:
        return ()
    return tuple(menunggu.TransferMenunggu(i.order_id, i.total, i.bukti_terakhir) for i in daftar)
