"""Model baca halaman Harga admin: nilai aktif, sumber, riwayat, dan status skema (tanpa HTML, tanpa tulis).

Dipakai `admin_harga_http` (GET) dan tes. Harga Latihan Harian dibaca dari katalog harian (bukan tabel harga_*).
Skema harga_* yang rusak melempar ValueError dari `schema_harga.validasi`; pemanggil yang memetakannya ke galat layanan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

import admin_store
import harga
import harga_aturan as a
import harian_langganan_dasar as harian
import schema_harga

LABEL_PRODUK = {"private": "Private", "mini": "Mini Class", "peta": "Peta Kemampuan"}


@dataclass(frozen=True)
class BarisProduk:
    kode: str
    label: str
    rupiah: int
    bisa_diubah: bool
    diubah: str = ""  # waktu UTC perubahan terakhir oleh admin; "" = nilai awal
    setelah_deposit: Optional[int] = None  # info: tagihan setelah potongan deposit Peta (hanya Private/Mini)


@dataclass(frozen=True)
class BarisHarian:
    kode: str
    label: str
    rupiah: int


@dataclass(frozen=True)
class Tampilan:
    terpasang: bool
    produk: Tuple[BarisProduk, ...]
    harian: Tuple[BarisHarian, ...]
    riwayat: Tuple[harga.RiwayatHarga, ...]


def muat(path) -> Tampilan:
    """Baca halaman dari DB admin (read-only, tanpa membuat file atau migrasi)."""
    with admin_store.buka_baca(path) as kon:
        return baca(kon)


def baca(kon) -> Tampilan:
    terpasang = schema_harga.validasi(kon)
    aktif = harga.harga_semua(kon)
    diubah = _waktu_ubah(kon) if terpasang else {}
    return Tampilan(
        terpasang=terpasang,
        produk=tuple(_baris_produk(kode, aktif[kode], diubah.get(kode, "")) for kode in a.KODE_PRODUK),
        harian=_baris_harian(),
        riwayat=harga.riwayat(kon, harga.BATAS_RIWAYAT_BAWAAN) if terpasang else (),
    )


def _waktu_ubah(kon) -> Mapping[str, str]:
    return {kode: waktu for kode, waktu in kon.execute("SELECT kode, diubah FROM harga_produk")}


def _baris_produk(kode: str, rupiah: int, diubah: str) -> BarisProduk:
    bisa_diubah = kode in a.ALLOW_UBAH
    return BarisProduk(
        kode=kode, label=LABEL_PRODUK[kode], rupiah=rupiah, bisa_diubah=bisa_diubah, diubah=diubah,
        setelah_deposit=rupiah - a.RUPIAH_DEPOSIT if bisa_diubah else None,
    )


def _baris_harian() -> Tuple[BarisHarian, ...]:
    return tuple(BarisHarian(paket.kode, paket.nama, paket.rupiah) for paket in harian.PAKET.values())
