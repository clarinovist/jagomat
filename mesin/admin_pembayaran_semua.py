"""Pembaca read-only "Semua pembayaran": order Peta Kemampuan, Latihan Harian, dan Paket Belajar dalam satu daftar.

Ketiga jalur punya ledger dan halaman ACC sendiri. Modul ini hanya menyatukan tampilannya (tagihan belum dibayar,
bukti menunggu, lunas, ditolak, kedaluwarsa) supaya admin melihat riwayat pendaftar di satu tempat. Tanpa tulis, tanpa
kontak, nama berkas, atau sandi. Nama anak dan akun login murid (keputusan Pemilik 26 Nov 2026) diisi dari siswa_id
lewat `lengkapi_anak_akun`: baca-saja, satu bacaan siswa dan satu bacaan akun untuk seluruh halaman; kontak akun
(nomor WhatsApp, `kontak_akun`) tidak diambil. Status memakai turunan yang sama dengan halaman masing-masing
(`pesanan_admin`, `harian_langganan_store.status_dari`, `kelas_status.status_dari`); hanya namanya diseragamkan.

Tiap jenis dibaca terpisah dan paling banyak `BATAS_PER_JENIS` order terbaru. Jenis yang tidak terbaca dilaporkan di
`gagal` (bukan diam-diam kosong), supaya admin tahu daftarnya belum lengkap.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, replace
from typing import Mapping, Optional, Tuple

import admin_transfer_menunggu as menunggu
import auth
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
_log = logging.getLogger(__name__)
# Galat baca nama anak (DB) dan akun murid (auth). Hanya nama tipe yang dicatat, tanpa jalur atau isi berkas.
GALAT_BACA_ANAK = (sqlite3.Error, OSError)
GALAT_BACA_AKUN = (OSError, ValueError)  # muat_sandi sudah menelan galat JSON menjadi []; ValueError untuk jaga-jaga

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
    """Satu order. `dibuat` = waktu ledger (UTC naif); `nominal` None bila tagihan belum tercatat.

    `siswa_id` dibawa dari ledger untuk `lengkapi_anak_akun`, yang mengisi `nama_anak` dan `akun` (login murid).
    None pada `nama_anak`/`akun` berarti tampil "-" (tidak ditemukan, ambigu, atau galat baca).
    """

    jenis: str
    order_id: str
    nominal: Optional[int]
    status: str
    dibuat: str
    siswa_id: Optional[int] = None
    nama_anak: Optional[str] = None
    akun: Optional[str] = None

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
        ledger = _ledger_peta(kon, ids)
        rupiah = {b[0]: b[1] for b in ledger}
        siswa = {b[0]: b[2] for b in ledger}
    return tuple(BarisBayar(JENIS_PETA, i["order_id"],
                            ringkas.get(i["order_id"], {}).get("nominal") or rupiah.get(i["order_id"]),
                            _PETA.get(i["status"], i["status"]), i["dibuat"],
                            siswa_id=siswa.get(i["order_id"])) for i in item)


def _ledger_peta(kon, ids) -> list:
    """(order_id, rupiah, siswa_id) untuk order Peta di `ids`; kosong bila tidak ada id."""
    if not ids:
        return []
    return kon.execute("SELECT order_id,rupiah,siswa_id FROM pesanan_order WHERE order_id IN (%s)"
                       % ",".join("?" * len(ids)), ids).fetchall()


def _harian(kini: str) -> Tuple[BarisBayar, ...]:
    with database.buka() as kon:
        baris = kon.execute(
            "SELECT o.id,o.siswa_id,o.dibuat,o.kedaluwarsa,t.nominal_transfer AS nominal FROM harian_order o "
            "LEFT JOIN harian_tagihan t ON t.order_id=o.id ORDER BY o.dibuat DESC,o.id DESC LIMIT ?",
            (BATAS_PER_JENIS,)).fetchall()
        status = {b["id"]: harian_langganan_store.status_dari(
            b, harian_langganan_store.fakta_order(kon, b["id"]), kini) for b in baris}
    return tuple(BarisBayar(JENIS_HARIAN, b["id"], b["nominal"], _HARIAN.get(status[b["id"]], status[b["id"]]),
                            b["dibuat"], siswa_id=b["siswa_id"]) for b in baris)


def _kelas(path_admin, kini: str) -> Tuple[BarisBayar, ...]:
    with kelas_store.buka(path_admin) as kon:
        baris = kon.execute(
            "SELECT o.id,o.siswa_id,o.dibuat,o.kedaluwarsa,t.total_transfer AS nominal FROM kelas_order o "
            "LEFT JOIN kelas_tagihan t ON t.order_id=o.id ORDER BY o.dibuat DESC,o.id DESC LIMIT ?",
            (BATAS_PER_JENIS,)).fetchall()
        status = {b["id"]: kelas_status.status_dari(b, kelas_status.fakta_order(kon, b["id"]), kini) for b in baris}
    return tuple(BarisBayar(JENIS_KELAS, b["id"], b["nominal"], _KELAS.get(status[b["id"]], status[b["id"]]),
                            b["dibuat"], siswa_id=b["siswa_id"]) for b in baris)


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


def lengkapi_anak_akun(baris, path_auth) -> Tuple[BarisBayar, ...]:
    """Isi `nama_anak` dan `akun` (login murid) dari siswa_id: satu bacaan siswa dan satu bacaan akun per panggilan.

    Baca-saja; `path_auth` diberikan pemanggil. Galat baca, siswa tanpa baris, akun tidak ada, atau akun ambigu menjadi
    None (tampil "-"); tidak melempar. Dari berkas auth hanya `pengguna` yang keluar: tanpa sandi, hash, token,
    atau kontak.
    """
    siswa_ids = frozenset(b.siswa_id for b in baris if b.siswa_id is not None)
    nama = _nama_anak(siswa_ids)
    akun = _akun_murid(siswa_ids, nama, path_auth)
    return tuple(replace(b, nama_anak=nama.get(b.siswa_id), akun=akun.get(b.siswa_id)) for b in baris)


def _nama_anak(siswa_ids) -> dict:
    """{siswa_id: nama} untuk id yang ada; galat baca DB = kosong (semua nama tampil "-")."""
    if not siswa_ids:
        return {}
    try:
        with database.buka() as kon:
            baris = kon.execute("SELECT id,nama FROM siswa WHERE id IN (%s)" % ",".join("?" * len(siswa_ids)),
                                tuple(siswa_ids)).fetchall()
    except GALAT_BACA_ANAK as galat:
        _log.warning("nama anak tidak terbaca: %s", type(galat).__name__)
        return {}
    return {b["id"]: b["nama"] for b in baris}


def _akun_murid(siswa_ids, nama: Mapping, path_auth) -> dict:
    """{siswa_id: pengguna} hanya untuk akun murid yang tunggal; galat baca auth = kosong."""
    if not siswa_ids:
        return {}
    try:
        akun = auth.muat_akun(path_auth)
    except GALAT_BACA_AKUN as galat:
        _log.warning("akun murid tidak terbaca: %s", type(galat).__name__)
        return {}
    murid = [a for a in akun if a.get("peran") == "murid"]
    return {sid: _login_tunggal(murid, sid, nama.get(sid)) for sid in siswa_ids}


def _login_tunggal(murid: list, siswa_id: int, nama: Optional[str]) -> Optional[str]:
    """Pengguna akun murid yang bertaut ke `siswa_id`: tepat satu, dan tidak ada akun lama (tanpa siswa_id) bernama sama.

    Tanpa nama anak, akun lama tidak bisa diperiksa, maka None: tidak menebak.
    """
    if nama is None:
        return None
    bertaut = [a.get("pengguna") for a in murid if a.get("siswa_id") == siswa_id]
    lama = [a for a in murid if a.get("siswa_id") is None and _sama_nama(a.get("pengguna"), nama)]
    if lama or len(bertaut) != 1 or not _nama_sah(bertaut[0]):
        return None
    return bertaut[0]


def _sama_nama(pengguna, nama: str) -> bool:
    return _nama_sah(pengguna) and pengguna.strip().casefold() == nama.strip().casefold()


def _nama_sah(pengguna) -> bool:
    return isinstance(pengguna, str) and pengguna.strip() != ""
