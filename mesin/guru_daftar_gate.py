"""Gerbang pendaftaran guru mandiri (`/daftar?peran=guru`): sakelar admin `DAFTAR_GURU`, bawaan MATI.

Baris DB sakelar menang; env `DAFTAR_GURU=1` hanya fallback sebelum admin pertama kali mengubah sakelar (hanya nilai persis "1"
menyalakan; nilai lain, DB rusak, atau skema salah = mati). Tabel `sakelar.db` diperlebar otomatis oleh `feature_switch.ubah`
(versi skema tidak naik, kode lama tetap bisa membaca), seperti sakelar sebelumnya.
"""
from __future__ import annotations

import os

import feature_switch

NAMA_SAKELAR = "DAFTAR_GURU"
PESAN_BELUM_DIBUKA = "Pendaftaran guru belum dibuka."


def dari_env() -> bool:
    """Nilai env saja: fallback sakelar dan nilai awal (seed) halaman admin."""
    return os.environ.get(NAMA_SAKELAR, "0") == "1"


def aktif() -> bool:
    return feature_switch.aktif(NAMA_SAKELAR, dari_env)
