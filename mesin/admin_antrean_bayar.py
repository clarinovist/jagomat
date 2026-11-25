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
import kelas_peserta
import kelas_store
import pesanan
import purna
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


def belum_ditempatkan(path_admin, sekarang_iso: str) -> int:
    """Paket belajar yang sudah disetujui dan masih aktif tetapi belum ditempatkan (jadwal belum ada); galat baca = 0.

    Penempatan yang tidak diketahui (tabel `jadwal_*` belum ada) tidak dihitung. Hanya angka, tanpa nama anak atau kontak.
    """
    try:
        with kelas_store.buka(path_admin) as kon:
            daftar = kelas_peserta.daftar_peserta_aktif(kon, sekarang_iso)
    except menunggu.GALAT_BACA:
        return 0
    return sum(1 for p in daftar if p.ditempatkan is False)


BATAS_KANDIDAT_PETA = 200
_SQL_PETA_LUNAS_TANPA_LAPORAN = (
    "SELECT o.order_id FROM pesanan_order o "
    "WHERE NOT EXISTS (SELECT 1 FROM purna_laporan_terbit t WHERE t.order_id=o.order_id) "
    "AND (EXISTS (SELECT 1 FROM pesanan_receipt r WHERE r.order_id=o.order_id AND r.hasil='lunas')%s) "
    "ORDER BY o.dibuat LIMIT ?")
_ATAU_TRANSFER_LUNAS = " OR EXISTS (SELECT 1 FROM transfer_lunas l WHERE l.order_id=o.order_id)"


def peta_belum_terbit(path_admin, sekarang_iso: str) -> Tuple[int, int]:
    """(Peta lunas tanpa laporan terbit, dari itu yang sudah lewat janji 48 jam); galat baca atau purna belum dipasang = (0, 0).

    Keadaan (lunas, ditahan, direfund, terbit, terlambat) dari domain `purna`, jadi order yang direfund atau pembayarannya perlu
    diperiksa tidak ikut. Hanya angka: tanpa nama anak, akun, atau id.
    """
    try:
        with pesanan.buka(path_admin) as kon:
            if not purna.terpasang(kon):
                return 0, 0
            transfer = _ATAU_TRANSFER_LUNAS if purna._ada_tabel(kon, "transfer_lunas") else ""
            ids = [b[0] for b in kon.execute(_SQL_PETA_LUNAS_TANPA_LAPORAN % transfer, (BATAS_KANDIDAT_PETA,))]
            keadaan = [purna.keadaan(kon, i, sekarang_iso) for i in ids]
    except menunggu.GALAT_BACA:
        return 0, 0
    menanti = [k for k in keadaan if k.lunas and not k.direfund and not k.ditahan and k.terbit is None]
    return len(menanti), sum(1 for k in menanti if k.terlambat)


def kelas_tunggakan(path_admin, sekarang_iso: str) -> Tuple[kt.Tunggakan, ...]:
    """Paket kelas habis dan belum diperpanjang untuk antrean admin; kelas belum dipasang/galat baca = ()."""
    try:
        with kelas_store.buka(path_admin) as kon:
            return kt.daftar_tunggakan(kon, sekarang_iso)
    except menunggu.GALAT_BACA:
        return ()
