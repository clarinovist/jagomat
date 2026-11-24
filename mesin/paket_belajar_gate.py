"""Gerbang Paket Belajar 1 Bulan (Private dan Mini Class): sakelar admin `PAKET_BELAJAR`.

Bawaan MATI (fail-closed): baris DB sakelar menang; env `PAKET_BELAJAR=1` hanya fallback sebelum sakelar diubah
admin, dan hanya nilai persis "1" menyalakan (nilai lain, kosong, atau tak ada = mati). Pola sama dengan
`akses_harian` (Latihan Harian). Gerbang ini hanya saklar: tidak membaca DB paket dan tidak menyentuh Latihan Harian.
"""
from __future__ import annotations

import os

import feature_switch

NAMA_SAKELAR = "PAKET_BELAJAR"


def dari_env() -> bool:
    """Nilai env saja: fallback sakelar dan nilai awal (seed) halaman admin."""
    return os.environ.get(NAMA_SAKELAR, "0").strip() == "1"


def aktif() -> bool:
    return feature_switch.aktif(NAMA_SAKELAR, dari_env)
