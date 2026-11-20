"""Aktivasi jurnal WAL di luar transaksi.

`PRAGMA journal_mode = WAL` di dalam transaksi diabaikan SQLite tanpa error:
mode yang dikembalikan tetap mode lama. Karena itu WAL harus disetel pada
koneksi yang belum membuka transaksi, sekali saja per berkas — mode tersimpan
di header basis data, bukan di koneksi.
"""
from __future__ import annotations

import sqlite3


def aktifkan(kon: sqlite3.Connection) -> str:
    """Setel jurnal WAL dan pastikan benar-benar berlaku."""
    mode = str(kon.execute("PRAGMA journal_mode = WAL").fetchone()[0]).lower()
    if mode != "wal":
        raise sqlite3.OperationalError(f"jurnal SQLite bukan WAL: {mode}")
    return mode
