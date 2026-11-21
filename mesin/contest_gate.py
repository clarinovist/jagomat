"""Gerbang fitur Latihan Lomba: sakelar admin `OSN_LOMBA` (env hanya fallback).

Urutan (lihat `feature_switch.aktif`): baris DB sakelar menang; berkas DB atau barisnya belum ada ->
env `OSN_LOMBA` (bawaan mati; hanya nilai persis "1" menyalakan); DB rusak atau skema tak dikenal ->
mati tanpa menyentuh env. Saat mati, semua rute `/murid/lomba/...` dan `/anak/<id>/lomba` tidak dikenali
(404 yang identik dengan jalur lain yang tidak ada).
"""
from __future__ import annotations

import os

import feature_switch

NAMA_SAKELAR = "OSN_LOMBA"
ENV_LOMBA = NAMA_SAKELAR


def dari_env() -> bool:
    """Nilai env saja: fallback sakelar dan nilai awal (seed) halaman admin."""
    return os.environ.get(ENV_LOMBA, "0").strip() == "1"


def aktif() -> bool:
    return feature_switch.aktif(NAMA_SAKELAR, dari_env)
