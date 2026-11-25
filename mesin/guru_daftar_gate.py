"""Gerbang pendaftaran guru mandiri (`/daftar?peran=guru`): env `DAFTAR_GURU`, bawaan MATI, hanya nilai persis "1" menyalakan.

Sengaja env (dibaca tiap panggilan), bukan sakelar admin: sakelar baru mengubah daftar nama di `feature_switch` dan CHECK tabel
`sakelar.db`, yang perlu rilis terkontrol sendiri. Naikkan jadi sakelar admin bila Pemilik memutuskan fitur ini permanen.
"""
from __future__ import annotations

import os

NAMA_ENV = "DAFTAR_GURU"
PESAN_BELUM_DIBUKA = "Pendaftaran guru belum dibuka."


def aktif() -> bool:
    return os.environ.get(NAMA_ENV, "0") == "1"
