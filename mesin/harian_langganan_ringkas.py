"""Ringkasan langganan Latihan Harian satu anak untuk halaman orang tua dan halaman langganan (data saja).

Tanpa render dan tanpa tulis. Sumber akses = `akses_harian.akses` (langganan, les, atau gratis); tagihan terbuka dari
`harian_langganan_store`. Hanya data tak sensitif: tanpa nama berkas, tanpa kontak.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import akses_harian
import harian_langganan_dasar as h
import harian_langganan_store as store


@dataclass(frozen=True)
class Ringkasan:
    sumber: str
    berakhir: Optional[str]
    sisa_hari: int
    status_tagihan: Optional[str]
    alasan_tolak: Optional[str] = None

    @property
    def langganan_aktif(self) -> bool:
        return self.sumber == akses_harian.SUMBER_LANGGANAN

    @property
    def perlu_pengingat(self) -> bool:
        """Banner perpanjang: langganan aktif dan sisa <= `HARI_PENGINGAT` hari."""
        return self.langganan_aktif and 0 < self.sisa_hari <= h.HARI_PENGINGAT


def ringkasan(kon, siswa_id: int, kini) -> Ringkasan:
    """Ringkasan anak `siswa_id` pada `kini` (format `harian_langganan_dasar.ke_baku`)."""
    akses = akses_harian.akses(kon, siswa_id, kini)
    tampil = store.tampilan_terbuka(kon, siswa_id, kini)
    sisa = h.sisa_hari(akses.berakhir, kini) if akses.berakhir else 0
    if tampil is None:
        return Ringkasan(akses.sumber, akses.berakhir, sisa, None)
    alasan = tampil.alasan_tolak if tampil.status == h.STATUS_DITOLAK else None
    return Ringkasan(akses.sumber, akses.berakhir, sisa, tampil.status, alasan)
