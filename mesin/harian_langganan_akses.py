"""Pembaca akses langganan Latihan Harian: kait `akses_harian._langganan_aktif` dan ringkasan halaman orang tua.

Modul kecil tanpa impor domain lain supaya `akses_harian` dan `orang_tua_data` memakainya tanpa siklus impor.
Tabel `harian_akses` absen (DB lama) = tidak ada langganan, bukan galat.
"""
from __future__ import annotations

from typing import Optional

import harian_langganan_dasar as h


def _tabel_ada(kon) -> bool:
    return kon.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='harian_akses'").fetchone() is not None


def berakhir_aktif(kon, siswa_id: int, kini) -> Optional[str]:
    """Akhir masa langganan (UTC naif baku) bila anak sedang aktif pada `kini`, selain itu None.

    Aktif = ada baris dengan mulai <= kini < berakhir. Nilainya akhir rantai: perpanjangan yang sudah disetujui
    tetapi belum mulai (mulai = akhir baris sebelumnya) ikut dihitung, jadi tanggalnya akhir yang benar-benar dibayar.
    `kini` boleh str ISO, date, datetime, atau epoch (`harian_langganan_dasar.ke_baku`).
    """
    if not _tabel_ada(kon):
        return None
    waktu = h.ke_baku(kini)
    baris = kon.execute(
        "SELECT MAX(berakhir) FROM harian_akses WHERE siswa_id=? AND berakhir>? AND EXISTS("
        "SELECT 1 FROM harian_akses WHERE siswa_id=? AND mulai<=? AND berakhir>?)",
        (siswa_id, waktu, siswa_id, waktu, waktu)).fetchone()
    return baris[0]
