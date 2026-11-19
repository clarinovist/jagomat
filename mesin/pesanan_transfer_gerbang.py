"""Gerbang transfer rekening Paket Coba: terpisah dari gerbang Midtrans/QRIS, fail-closed.

Terbuka HANYA bila keempatnya terpenuhi:

1. env `PESANAN_TRANSFER_AKTIF` bernilai tepat "1" (tanpa trim: " 1", "true", "01" tetap tutup),
   dibaca hanya di sini lewat `transfer_aktif()`;
2. `funnel_flag.funnel_aktif()` True;
3. runtime pembayaran produksi terpasang di server (bukan sandbox) - dipakai sebagai satu-satunya
   penanda lingkungan produksi, sama dengan `pesanan_http._runtime`; pemanggil menyuntiknya;
4. rekening tujuan sudah diisi admin (`pesanan_rekening.baca_publik()` tidak None).

Sakelar/tahap pembayaran Midtrans TIDAK dibaca: membuka transfer tidak membuka QRIS, dan
menutup QRIS tidak menutup transfer. Galat apa pun = tertutup. Bawaan tertutup.
"""
from __future__ import annotations

import os
from typing import Optional

import funnel_flag
import pesanan_rekening

NAMA_SAKELAR = "PESANAN_TRANSFER_AKTIF"
_NILAI_AKTIF = "1"


def transfer_aktif() -> bool:
    """True hanya bila `PESANAN_TRANSFER_AKTIF` persis "1"."""
    return os.environ.get(NAMA_SAKELAR) == _NILAI_AKTIF


def rekening_bila_terbuka(runtime) -> Optional[pesanan_rekening.RekeningPublik]:
    """Rekening publik bila gerbang transfer terbuka; selain itu None (fail-closed)."""
    try:
        if not transfer_aktif() or not funnel_flag.funnel_aktif() or runtime is None:
            return None
        return pesanan_rekening.baca_publik()
    except Exception:
        return None
