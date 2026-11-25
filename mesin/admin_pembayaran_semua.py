"""Pembaca read-only "Semua pembayaran": order Peta Kemampuan, Latihan Harian, dan Paket Belajar dalam satu daftar.

Ketiga jalur punya ledger dan halaman ACC sendiri. Modul ini hanya menyatukan tampilannya (tagihan belum dibayar,
bukti menunggu, lunas, ditolak, kedaluwarsa) supaya admin melihat riwayat pendaftar di satu tempat. Tanpa tulis, tanpa
nama anak, kontak, siswa_id, nama berkas, atau akun. Status memakai turunan yang sama dengan halaman masing-masing
(`pesanan_admin`, `harian_langganan_store.status_dari`, `kelas_status.status_dari`); hanya namanya diseragamkan.

Tiap jenis dibaca terpisah dan paling banyak `BATAS_PER_JENIS` order terbaru. Jenis yang tidak terbaca dilaporkan di
`gagal` (bukan diam-diam kosong), supaya admin tahu daftarnya belum lengkap.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import admin_transfer_menunggu as menunggu
import database
import harian_langganan_dasar as hd
import harian_langganan_store
import kelas_dasar
import kelas_status
import kelas_store
import pesanan
import pesanan_admin
import pesanan_admin_transfer
import pesanan_dasar as d

JENIS_PETA = "peta"
JENIS_HARIAN = "harian"
JENIS_KELAS = "kelas"
BATAS_PER_JENIS = pesanan_admin.BATAS_PER_HALAMAN
BATAS_BARIS = 100

S_MENUNGGU = d.STATUS_MENUNGGU_VERIFIKASI
S_BELUM_BAYAR = d.STATUS_BELUM_BAYAR
S_LUNAS = "lunas"
S_DITOLAK = d.STATUS_DITOLAK
S_KEDALUWARSA = d.STATUS_KEDALUWARSA
S_PERLU_DIPERIKSA = d.STATUS_PERLU_DIPERIKSA
S_DIREFUND = d.STATUS_DIREFUND

# Kelompok saringan = kunci `?status=`; tiap status ada di tepat satu kelompok (sama dengan daftar Pesanan).
KELOMPOK = {
    "menunggu": (S_MENUNGGU,),
    "belum_bayar": (S_BELUM_BAYAR,),
    "dibayar": (S_LUNAS, S_PERLU_DIPERIKSA, S_DIREFUND),
    "ditolak": (S_DITOLAK, S_KEDALUWARSA),
}

_PETA = {d.STATUS_SUDAH_DIBAYAR: S_LUNAS}
_HARIAN = {hd.STATUS_AKTIF: S_LUNAS}
_KELAS = {kelas_dasar.STATUS_MENUNGGU: S_MENUNGGU, kelas_dasar.STATUS_AKTIF: S_LUNAS}

RUTE_PETA = "/admin/pesanan"
RUTE_HARIAN = "/admin/langganan"
RUTE_KELAS = "/admin/kelas"


@dataclass(frozen=True)
class BarisBayar:
    """Satu order. `dibuat` = waktu ledger (UTC naif); `nominal` None bila tagihan belum tercatat."""

    jenis: str
    order_id: str
    nominal: Optional[int]
    status: str
    dibuat: str

    @property
    def jalur(self) -> str:
        """Halaman detail/ACC order ini: verifikasi bila menunggu (Peta: detail order selain itu)."""
        if self.jenis == JENIS_HARIAN:
            return "%s/verifikasi?order=%s" % (RUTE_HARIAN, self.order_id)
        if self.jenis == JENIS_KELAS:
            return "%s/verifikasi?order=%s" % (RUTE_KELAS, self.order_id)
        if self.status == S_MENUNGGU:
            return "%s/verifikasi?order=%s" % (RUTE_PETA, self.order_id)
        return "%s/order?id=%s" % (RUTE_PETA, self.order_id)


def _peta(path_admin, kini: str) -> Tuple[BarisBayar, ...]:
    with pesanan.buka(path_admin) as kon:
        item = pesanan.daftar_admin(kon, halaman=1, per_halaman=BATAS_PER_JENIS, sekarang=kini)["items"]
        ids = tuple(i["order_id"] for i in item)
        ringkas = pesanan_admin_transfer.ringkasan(kon, ids)
        rupiah = {}
        if ids:
            rupiah = {b[0]: b[1] for b in kon.execute(
                "SELECT order_id,rupiah FROM pesanan_order WHERE order_id IN (%s)" % ",".join("?" * len(ids)), ids)}
    return tuple(BarisBayar(JENIS_PETA, i["order_id"],
                            ringkas.get(i["order_id"], {}).get("nominal") or rupiah.get(i["order_id"]),
                            _PETA.get(i["status"], i["status"]), i["dibuat"]) for i in item)


def _harian(kini: str) -> Tuple[BarisBayar, ...]:
    with database.buka() as kon:
        baris = kon.execute(
            "SELECT o.id,o.dibuat,o.kedaluwarsa,t.nominal_transfer AS nominal FROM harian_order o "
            "LEFT JOIN harian_tagihan t ON t.order_id=o.id ORDER BY o.dibuat DESC,o.id DESC LIMIT ?",
            (BATAS_PER_JENIS,)).fetchall()
        status = {b["id"]: harian_langganan_store.status_dari(
            b, harian_langganan_store.fakta_order(kon, b["id"]), kini) for b in baris}
    return tuple(BarisBayar(JENIS_HARIAN, b["id"], b["nominal"], _HARIAN.get(status[b["id"]], status[b["id"]]),
                            b["dibuat"]) for b in baris)


def _kelas(path_admin, kini: str) -> Tuple[BarisBayar, ...]:
    with kelas_store.buka(path_admin) as kon:
        baris = kon.execute(
            "SELECT o.id,o.dibuat,o.kedaluwarsa,t.total_transfer AS nominal FROM kelas_order o "
            "LEFT JOIN kelas_tagihan t ON t.order_id=o.id ORDER BY o.dibuat DESC,o.id DESC LIMIT ?",
            (BATAS_PER_JENIS,)).fetchall()
        status = {b["id"]: kelas_status.status_dari(b, kelas_status.fakta_order(kon, b["id"]), kini) for b in baris}
    return tuple(BarisBayar(JENIS_KELAS, b["id"], b["nominal"], _KELAS.get(status[b["id"]], status[b["id"]]),
                            b["dibuat"]) for b in baris)


def baca(path_admin, sekarang_iso: str):
    """(baris terbaru dulu, jenis yang tidak terbaca). Galat baca satu jenis tidak menggagalkan jenis lain."""
    hasil, gagal = [], []
    for jenis, ambil in ((JENIS_PETA, lambda: _peta(path_admin, sekarang_iso)),
                         (JENIS_HARIAN, lambda: _harian(sekarang_iso)),
                         (JENIS_KELAS, lambda: _kelas(path_admin, sekarang_iso))):
        try:
            hasil.extend(ambil())
        except menunggu.GALAT_BACA:
            gagal.append(jenis)
    urut = sorted(hasil, key=lambda b: (b.dibuat, b.order_id), reverse=True)
    return tuple(urut), tuple(gagal)


def hitung(baris) -> dict:
    """{kelompok: n, 'semua': n} atas seluruh baris (sebelum saringan)."""
    jumlah = {k: sum(1 for b in baris if b.status in status) for k, status in KELOMPOK.items()}
    jumlah["semua"] = len(baris)
    return jumlah


def saring(baris, kelompok: Optional[str]):
    """Baris dalam kelompok (None = semua), dipotong `BATAS_BARIS`. Kelompok tak dikenal = ValueError."""
    if kelompok is None:
        return tuple(baris[:BATAS_BARIS])
    if kelompok not in KELOMPOK:
        raise ValueError("kelompok tidak sah")
    return tuple(b for b in baris if b.status in KELOMPOK[kelompok])[:BATAS_BARIS]
