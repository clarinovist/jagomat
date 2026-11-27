"""Katalog Paket Belajar 1 Bulan (Private dan Mini Class), aturan nominal, dan model data bersama.

Tanpa DB, jaringan, atau env. Harga katalog konstanta di sini (server); harga aktif admin masuk lewat argumen dari pemanggil yang membaca DB; tidak pernah dari form.
Keputusan Pemilik 24 Nov 2026 (plan `docs/plan/2026-11-24-paket-belajar-bulanan.md` §4a), direvisi
25 Nov 2026: harga Mini naik dan diskon anak kedua dihapus total.
- Private: Rp80.000 x 8 pertemuan, 60 menit, online. Mini Class: Rp300.000, 8 pertemuan, 60 menit,
  offline, kuota 5 anak.
- Deposit Peta (Rp49.000) memotong bulan pertama sekali, untuk semua paket. Tidak ada diskon lain.

Total transfer = nominal + kode unik 1..999, jadi semua nominal (termasuk produk lain: Peta Rp49.000,
Latihan Harian Rp39.000 dan Rp349.000) harus berjarak lebih dari 999 satu sama lain; dijaga tes.
Model di bagian bawah adalah kontrak antara store, halaman, dan HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Optional, Tuple

import pesanan_dasar as d

KODE_PRIVATE = "private"
KODE_MINI = "mini"
MODE_ONLINE = "online"
MODE_OFFLINE = "offline"

PERTEMUAN_PER_BULAN = 8
MENIT_PER_PERTEMUAN = 60
HARGA_PRIVATE_PER_PERTEMUAN = 80_000
HARGA_MINI = 300_000
KUOTA_MINI = 5
RUPIAH_DEPOSIT = d.RUPIAH_PAKET

STATUS_BELUM_BAYAR = "belum_bayar"
STATUS_MENUNGGU = "menunggu"
STATUS_AKTIF = "aktif"
STATUS_KEDALUWARSA = "kedaluwarsa"
STATUS_DITOLAK = "ditolak"
STATUS_DIBATALKAN = "dibatalkan"


@dataclass(frozen=True)
class PaketBelajar:
    kode: str
    nama: str
    mode: str
    pertemuan: int
    menit: int
    kuota: Optional[int]
    harga: int


@dataclass(frozen=True)
class Rincian:
    """Perincian nominal tagihan sebelum kode unik."""
    kode_paket: str
    harga_dasar: int
    potongan_deposit: int
    potongan_diskon: int
    nominal: int


@dataclass(frozen=True)
class KartuPaket:
    """Satu kartu di halaman "Pilih paket belajar" untuk pembeli tertentu."""
    paket: PaketBelajar
    rincian: Rincian
    ada_tagihan_terbuka: bool


@dataclass(frozen=True)
class TagihanKelas:
    order_id: str
    kode_paket: str
    rincian: Rincian
    kode_unik: int
    total: int
    status: str
    kedaluwarsa: Optional[str]
    jumlah_bukti: int
    berakhir: Optional[str]


@dataclass(frozen=True)
class ItemAntrean:
    """Satu baris antrean verifikasi admin (bukti belum diputuskan)."""
    order_id: str
    siswa_id: int
    kode_paket: str
    total: int
    bukti_terakhir: str


DAFTAR_PAKET: Tuple[PaketBelajar, ...] = (
    PaketBelajar(KODE_PRIVATE, "Private", MODE_ONLINE, PERTEMUAN_PER_BULAN, MENIT_PER_PERTEMUAN, None,
                 HARGA_PRIVATE_PER_PERTEMUAN * PERTEMUAN_PER_BULAN),
    PaketBelajar(KODE_MINI, "Mini Class", MODE_ONLINE, PERTEMUAN_PER_BULAN, MENIT_PER_PERTEMUAN, KUOTA_MINI,
                 HARGA_MINI),
)


def ambil(kode: str) -> PaketBelajar:
    for paket in DAFTAR_PAKET:
        if paket.kode == kode:
            return paket
    raise ValueError("kode paket belajar tidak dikenal")


def paket_dengan_harga(kode: str, harga_bulanan: int) -> PaketBelajar:
    """Salinan paket katalog dengan harga BULANAN dari harga aktif admin; katalog sendiri tidak berubah.

    Harga bulanan dipakai apa adanya (Private Rp640.000 per bulan, bukan dikali pertemuan). Fungsi murni: pemanggil
    yang membaca DB, bukan modul ini.
    """
    return replace(ambil(kode), harga=_periksa_harga(harga_bulanan))


def _periksa_harga(nilai) -> int:
    if type(nilai) is not int or nilai <= 0:
        raise ValueError("harga paket harus bilangan bulat positif")
    return nilai


def _periksa_potongan(nilai) -> int:
    if type(nilai) is not int or nilai < 0:
        raise ValueError("potongan deposit harus bilangan bulat tidak negatif")
    return nilai


def hitung_rincian(kode: str, *, potongan_deposit: int, harga_paket: Optional[int] = None) -> Rincian:
    """Nominal tagihan: harga paket dikurangi `potongan_deposit`; hasil selalu > 0.

    `potongan_deposit` = nominal bayar order Peta yang dipotong (0 = tanpa deposit), dibaca pemanggil dari
    `pesanan_order.rupiah`. Apakah nilai itu sah bagi CHECK tagihan dijaga `kelas_rincian`, bukan di sini.
    `harga_paket` None = harga katalog; selain itu harga bulanan aktif (wajib bilangan bulat positif asli).
    `potongan_diskon` selalu 0: diskon anak kedua sudah dihapus (25 Nov 2026). Kolomnya dipertahankan di
    `kelas_tagihan` agar skema dan tagihan lama tetap utuh.
    """
    paket = ambil(kode)
    potongan = _periksa_potongan(potongan_deposit)
    harga = paket.harga if harga_paket is None else _periksa_harga(harga_paket)
    nominal = harga - potongan
    if nominal <= 0:
        raise ValueError("nominal tagihan harus positif")
    return Rincian(paket.kode, harga, potongan, 0, nominal)
