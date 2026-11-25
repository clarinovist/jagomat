"""Katalog Paket Belajar 1 Bulan (Private dan Mini Class), aturan nominal, dan model data bersama.

Tanpa DB, jaringan, atau env. Semua harga HANYA konstanta di sini (server); tidak pernah dari form.
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

from dataclasses import dataclass
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
    PaketBelajar(KODE_MINI, "Mini Class", MODE_OFFLINE, PERTEMUAN_PER_BULAN, MENIT_PER_PERTEMUAN, KUOTA_MINI,
                 HARGA_MINI),
)


def ambil(kode: str) -> PaketBelajar:
    for paket in DAFTAR_PAKET:
        if paket.kode == kode:
            return paket
    raise ValueError("kode paket belajar tidak dikenal")


def _periksa_bool(nama: str, nilai) -> bool:
    if not isinstance(nilai, bool):
        raise ValueError(f"{nama} harus bool")
    return nilai


def hitung_rincian(kode: str, *, deposit_aktif: bool) -> Rincian:
    """Nominal tagihan: harga paket dikurangi deposit Peta bila aktif; hasil selalu > 0.

    `potongan_diskon` selalu 0: diskon anak kedua sudah dihapus (25 Nov 2026). Kolomnya dipertahankan di
    `kelas_tagihan` agar skema dan tagihan lama tetap utuh.
    """
    paket = ambil(kode)
    deposit = _periksa_bool("deposit_aktif", deposit_aktif)
    potongan_deposit = RUPIAH_DEPOSIT if deposit else 0
    nominal = paket.harga - potongan_deposit
    if nominal <= 0:
        raise ValueError("nominal tagihan harus positif")
    return Rincian(paket.kode, paket.harga, potongan_deposit, 0, nominal)
