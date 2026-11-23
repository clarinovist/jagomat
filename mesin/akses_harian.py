"""Kontrak akses Latihan Harian: sakelar admin `LATIHAN_HARIAN` dan siapa yang boleh berlatih tanpa batas.

Sakelar `LATIHAN_HARIAN` (bawaan mati; baris DB sakelar menang, env `LATIHAN_HARIAN=1` hanya fallback).
Urutan aturan `akses()`:
1. langganan aktif (kait `_langganan_aktif`, diisi F5) -> tanpa batas, sumber `langganan`;
2. murid les: anak dipegang guru ANGGOTA lembaga antrean (`OSN_LEMBAGA_ANTREAN`) -> tanpa batas, sumber `les`.
   Pemilik lembaga (koordinator) sendiri bukan murid les; lembaga antrean tak terkonfigurasi -> bukan les;
3. selain itu -> sumber `gratis`, dibatasi `BATAS_GRATIS_PER_HARI` sesi per hari (WIB; ditegakkan pemanggil).
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import sqlite3
from typing import Optional

import daftar_anak_gate
import feature_switch

NAMA_SAKELAR = "LATIHAN_HARIAN"
BATAS_GRATIS_PER_HARI = 1
SUMBER_LANGGANAN = "langganan"
SUMBER_LES = "les"
SUMBER_GRATIS = "gratis"


@dataclass(frozen=True)
class Akses:
    tanpa_batas: bool
    sumber: str
    berakhir: Optional[str] = None


def dari_env() -> bool:
    """Nilai env saja: fallback sakelar dan nilai awal (seed) halaman admin."""
    return os.environ.get(NAMA_SAKELAR, "0").strip() == "1"


def aktif() -> bool:
    return feature_switch.aktif(NAMA_SAKELAR, dari_env)


def _langganan_aktif(kon: sqlite3.Connection, siswa_id: int, kini) -> Optional[str]:
    """KAIT untuk F5: tanggal berakhir langganan yang masih aktif pada `kini`, atau None bila tidak ada.

    Sekarang selalu None: tabel `harian_akses` belum ada dan F5 yang mengisinya. Tidak boleh error
    saat tabel absen.
    """
    return None


def _murid_les(kon: sqlite3.Connection, siswa_id: int) -> bool:
    lembaga_id = daftar_anak_gate.id_lembaga_antrean()
    if lembaga_id is None:
        return False
    baris = kon.execute(
        "SELECT 1 FROM siswa s JOIN anggota_lembaga a ON a.guru = s.pemilik "
        "JOIN lembaga l ON l.id = a.lembaga_id "
        "WHERE s.id = ? AND a.lembaga_id = ? AND s.pemilik <> l.pemilik",
        (siswa_id, lembaga_id)).fetchone()
    return baris is not None


def akses(kon: sqlite3.Connection, siswa_id: int, kini) -> Akses:
    berakhir = _langganan_aktif(kon, siswa_id, kini)
    if berakhir is not None:
        return Akses(True, SUMBER_LANGGANAN, berakhir)
    if _murid_les(kon, siswa_id):
        return Akses(True, SUMBER_LES, None)
    return Akses(False, SUMBER_GRATIS, None)
