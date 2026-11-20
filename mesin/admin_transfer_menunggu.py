"""Pembaca read-only transfer yang menunggu verifikasi, dari ledger pesanan.

Dipakai antrean "Perlu ditangani" (item mendesak) dan alur setelah keputusan verifikasi (lanjut ke transfer
berikutnya). Hasil terurut paling lama menunggu dulu. Tanpa nama anak, kontak, atau nama berkas; tanpa tulis.
Galat baca (`GALAT_BACA`) diteruskan: pemanggil memutuskan apakah ini berarti "tidak ada" atau fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
from typing import Optional, Tuple

import admin_store
import pesanan
import pesanan_admin
import pesanan_admin_transfer

GALAT_BACA = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)
BATAS_HALAMAN_BACA = 20
_URUT_TANPA_WAKTU = "9999-12-31T23:59:59"


@dataclass(frozen=True)
class TransferMenunggu:
    """Satu order `menunggu_verifikasi`. `diunggah` = waktu bukti terakhir (UTC naif ledger) atau None."""

    order_id: str
    nominal: Optional[int]
    diunggah: Optional[str]


def waktu_iso(sekarang: float) -> str:
    """Detik epoch menjadi waktu baku ledger (UTC naif) untuk `pesanan.daftar_admin`."""
    return datetime.fromtimestamp(sekarang, timezone.utc).isoformat(timespec="seconds")


def _semua_id(kon, sekarang_iso: str) -> Tuple[str, ...]:
    """Semua order menunggu (bukan hanya satu halaman), supaya urutan terlama tidak terpotong."""
    ids = []
    halaman, total = 1, 0
    while halaman <= BATAS_HALAMAN_BACA:
        daftar = pesanan.daftar_admin(
            kon, halaman=halaman, per_halaman=pesanan_admin.BATAS_PER_HALAMAN,
            sekarang=sekarang_iso, hanya_menunggu=True)
        ids.extend(item["order_id"] for item in daftar["items"])
        total = daftar["total"]
        if len(ids) >= total or not daftar["items"]:
            break
        halaman += 1
    return tuple(ids)


def baca(path_admin, sekarang_iso: str) -> Tuple[TransferMenunggu, ...]:
    """Transfer menunggu verifikasi, paling lama menunggu dulu."""
    with pesanan.buka(path_admin) as kon:
        ids = _semua_id(kon, sekarang_iso)
        ringkas = pesanan_admin_transfer.ringkasan(kon, ids)
    baris = tuple(
        TransferMenunggu(i, ringkas.get(i, {}).get("nominal"), ringkas.get(i, {}).get("diunggah"))
        for i in ids)
    return tuple(sorted(baris, key=lambda b: (b.diunggah or _URUT_TANPA_WAKTU, b.order_id)))


def berikutnya(path_admin, sekarang_iso: str, kecuali: str) -> Optional[str]:
    """Order menunggu tertua selain `kecuali`, atau None bila tidak ada lagi."""
    for transfer in baca(path_admin, sekarang_iso):
        if transfer.order_id != kecuali:
            return transfer.order_id
    return None
