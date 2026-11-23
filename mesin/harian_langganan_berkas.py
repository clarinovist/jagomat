"""Berkas bukti transfer langganan Latihan Harian: subfolder SENDIRI di dalam folder bukti Paket Coba.

Sapuan yatim `pesanan_retensi` membuang berkas 32-hex di folder bukti yang tidak dirujuk `transfer_bukti`; bukti
langganan dirujuk `harian_bukti` (DB lain), jadi ia disimpan di subfolder `harian/` yang tidak pernah disentuh
sapuan itu (direktori tidak dihapus dan tidak dipindai rekursif). Fungsi tipis di atas `bukti_berkas` (nama acak
server, tulis atomik, nama divalidasi, symlink ditolak). Retensi 30 hari untuk bukti langganan BELUM ada (celah).
"""
from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import bukti_berkas

SUBFOLDER = "harian"


def folder() -> Path:
    return bukti_berkas.direktori_bukti() / SUBFOLDER


def simpan(isi: bytes) -> str:
    return bukti_berkas.simpan_berkas(isi, folder())


def buka(nama) -> BinaryIO:
    return bukti_berkas.buka_berkas(nama, folder())


def hapus(nama) -> bool:
    return bukti_berkas.hapus_berkas(nama, folder())
