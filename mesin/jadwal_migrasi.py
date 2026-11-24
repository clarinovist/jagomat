"""CLI operator: pasang skema jadwal Paket Belajar (`jadwal_*`: kelompok, penempatan, pertemuan).

Tidak dipanggil startup/GET/rilis otomatis. Jalankan terhadap SALINAN dulu, lalu DB live setelah hold dan backup:

    mesin/.venv/bin/python mesin/jadwal_migrasi.py --database <admin-control.db>

Prasyarat: `kelas_*` (dan karena itu `pesanan_*`/`transfer_*`) sudah terpasang. Bila belum, perintah ditolak
(exit 2) tanpa mengubah apa pun. Idempoten, tanpa seed, tanpa bump `user_version`.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

import admin_store_core
import schema_jadwal
import schema_kelas

_GALAT = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError)


class PrasyaratBelumAda(Exception):
    """Kelas belum terpasang; tidak ada yang diubah."""


def _buka_ro(path: Path) -> sqlite3.Connection:
    kon = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    kon.execute("PRAGMA query_only=ON")
    return kon


def periksa_prasyarat(path: Path) -> None:
    kon = _buka_ro(path)
    try:
        if not schema_kelas.validasi(kon):
            raise PrasyaratBelumAda("kelas belum dipasang")
    finally:
        kon.close()


def _pastikan_terpasang(path: Path) -> None:
    kon = _buka_ro(path)
    try:
        if not schema_jadwal.validasi(kon):
            raise ValueError("jadwal tidak terpasang setelah migrasi")
    finally:
        kon.close()


def migrasikan(path: Path) -> None:
    periksa_prasyarat(path)
    schema_jadwal.migrasikan(path)
    _pastikan_terpasang(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Pasang schema jadwal Paket Belajar (kelompok/pertemuan)")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    args = parser.parse_args(argv)
    path = Path(args.database)
    if not path.exists():
        print("Database tidak ditemukan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    try:
        migrasikan(path)
    except PrasyaratBelumAda:
        print("Paket belajar (kelas_*) harus sudah terpasang sebelum jadwal. Tidak ada yang diubah.",
              file=sys.stderr)
        return 2
    except _GALAT:
        print("Migrasi ditolak: struktur tidak sah atau database tidak bisa dibuka. "
              "Periksa salinan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    print("Migrasi jadwal selesai dan tervalidasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
