"""Bukti transfer menunggu di jalur Latihan Harian dan Paket Belajar, untuk antrean dan penanda sidebar admin.

Read-only. Kedua jalur punya ledger sendiri (Latihan Harian di DB belajar, Paket Belajar di DB admin) dan halaman ACC
sendiri, jadi tidak muncul di daftar Pesanan (Peta). Modul ini hanya menyatukan angkanya supaya admin melihat
penandanya di satu tempat. Bentuk hasil sama dengan `admin_transfer_menunggu` (order, nominal, waktu unggah terakhir),
tanpa nama anak, kontak, atau nama berkas. Galat baca (skema belum dipasang, DB tak terbaca) berarti "tidak ada":
penanda sidebar tidak boleh menjatuhkan halaman admin. Paket yang habis dan belum diperpanjang
(`kelas_tunggakan`) juga dibaca dari DB kelas yang sama.
"""
from __future__ import annotations

from typing import Tuple

import admin_pembayaran_semua
import admin_transfer_menunggu as menunggu
import database
import harian_langganan_putusan
import kelas_store
import kelas_tunggakan as kt

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


def belum_bayar(path_admin, sekarang_iso: str) -> int:
    """Order tiga jalur yang sudah dibuat tetapi belum ada bukti transfer, jendela 24 jam belum lewat; galat baca = 0.

    Sumbernya pembaca "Semua pembayaran" (status turunan yang sama, jadi order kedaluwarsa tidak ikut), terbatas pada
    order terbaru per jalur. Hanya angka: tanpa nama anak atau kontak.
    """
    try:
        baris, _gagal = admin_pembayaran_semua.baca(path_admin, sekarang_iso)
    except menunggu.GALAT_BACA:
        return 0
    return admin_pembayaran_semua.hitung(baris)["belum_bayar"]


def kelas_tunggakan(path_admin, sekarang_iso: str) -> Tuple[kt.Tunggakan, ...]:
    """Paket kelas habis dan belum diperpanjang untuk antrean admin; kelas belum dipasang/galat baca = ()."""
    try:
        with kelas_store.buka(path_admin) as kon:
            return kt.daftar_tunggakan(kon, sekarang_iso)
    except menunggu.GALAT_BACA:
        return ()
