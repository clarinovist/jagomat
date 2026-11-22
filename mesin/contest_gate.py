"""Gerbang fitur Latihan Lomba: sakelar admin `OSN_LOMBA` (env hanya fallback).

Sakelar ini saklar INDUK: Mode Lomba baru tampil untuk satu anak bila sakelar hidup DAN Guru sudah
mengaktifkannya untuk anak itu (`aktif_untuk`, baris `lomba_penugasan` dengan `aktif=1`; tanpa baris = mati).

Urutan (lihat `feature_switch.aktif`): baris DB sakelar menang; berkas DB atau barisnya belum ada ->
env `OSN_LOMBA` (bawaan mati; hanya nilai persis "1" menyalakan); DB rusak atau skema tak dikenal ->
mati tanpa menyentuh env. Saat mati, semua rute `/murid/lomba/...` dan `/anak/<id>/lomba` tidak dikenali
(404 yang identik dengan jalur lain yang tidak ada).
"""
from __future__ import annotations

import os
import sqlite3

import contest_assignment_store
import feature_switch

NAMA_SAKELAR = "OSN_LOMBA"
ENV_LOMBA = NAMA_SAKELAR


def dari_env() -> bool:
    """Nilai env saja: fallback sakelar dan nilai awal (seed) halaman admin."""
    return os.environ.get(ENV_LOMBA, "0").strip() == "1"


def aktif() -> bool:
    return feature_switch.aktif(NAMA_SAKELAR, dari_env)


def penugasan_aktif(kon, siswa_id: int) -> bool:
    """Guru mengaktifkan Mode Lomba untuk anak ini. Fail-closed: tabel atau baris tidak ada -> False."""
    try:
        penugasan = contest_assignment_store.ambil(kon, siswa_id)
    except sqlite3.OperationalError as galat:
        if "no such table" in str(galat):
            return False
        raise
    return penugasan is not None and penugasan.aktif


def aktif_untuk(kon, siswa_id: int) -> bool:
    """Sakelar induk hidup DAN penugasan anak aktif; gerbang tunggal sisi murid."""
    return aktif() and penugasan_aktif(kon, siswa_id)
