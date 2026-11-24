"""Berkas bukti transfer paket belajar (kelas): subfolder SENDIRI `kelas` di dalam folder bukti.

Sapuan yatim `pesanan_retensi` membuang berkas 32-hex di folder bukti yang tidak dirujuk `transfer_bukti`, dan sapuan
Latihan Harian hanya menyentuh subfolder `harian/`. Bukti kelas dirujuk `kelas_bukti` (admin-control.db), jadi ia
disimpan di subfolder `kelas/` yang tidak disentuh sapuan lain (direktori tidak dihapus dan tidak dipindai
rekursif). Fungsi tipis di atas `bukti_berkas` (nama acak server, tulis atomik, nama divalidasi, symlink ditolak).
Retensi berkas kelas BELUM ada (di luar cakupan lapisan data): berkas dipertahankan sampai sapuan khusus dibuat.
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import bukti_berkas

SUBFOLDER = "kelas"


def folder() -> Path:
    return bukti_berkas.direktori_bukti() / SUBFOLDER


def simpan(isi: bytes) -> str:
    return bukti_berkas.simpan_berkas(isi, folder())


def buka(nama) -> BinaryIO:
    return bukti_berkas.buka_berkas(nama, folder())


def hapus(nama) -> bool:
    return bukti_berkas.hapus_berkas(nama, folder())
