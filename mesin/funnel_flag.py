"""Sakelar jalur funnel Cek Kemampuan: satu-satunya tempat membaca `FUNNEL_AKTIF`.

Bawaan MATI. Hanya nilai "1" yang menghidupkan; nilai lain (kosong, "0", salah
ketik) tetap mati, jadi salah konfigurasi tidak pernah membuka jalur funnel.
Fase lain yang butuh sakelar ini wajib memanggil `funnel_aktif()`, bukan membaca
env sendiri.
"""
from __future__ import annotations

import os

import feature_switch

NAMA_SAKELAR = "FUNNEL_AKTIF"


def _dari_env() -> bool:
    return os.environ.get(NAMA_SAKELAR, "0").strip() == "1"


def funnel_aktif() -> bool:
    """DB sakelar (admin) menang; env `FUNNEL_AKTIF=1` (spasi tepi diabaikan)
    hanya fallback bila DB/baris belum ada."""
    return feature_switch.aktif(NAMA_SAKELAR, _dari_env)
