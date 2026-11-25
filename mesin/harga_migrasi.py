"""CLI operator: pasang skema harga (`harga_*`: nilai aktif dan riwayat) di admin-control.db.

Tidak pernah dipanggil startup, GET, atau rilis otomatis; operator menjalankannya terhadap SALINAN terverifikasi
dulu, baru DB live setelah hold dan backup (lihat `docs/production-release.md`):

    mesin/.venv/bin/python mesin/harga_migrasi.py --database <admin-control.db>

Idempoten, tanpa seed (baris tak ada = nilai awal), tanpa bump `user_version`, dan tanpa prasyarat ledger lain
karena harga tidak punya kunci asing.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

import admin_store_core
import schema_harga

_GALAT = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError)


def _pastikan_terpasang(path: Path) -> None:
    kon = admin_store_core.koneksi(path, "ro")
    try:
        if not schema_harga.validasi(kon):
            raise ValueError("harga tidak terpasang setelah migrasi")
    finally:
        kon.close()


def migrasikan(path: Path) -> None:
    """Pasang (idempoten) harga_*; galat dilempar apa adanya."""
    schema_harga.migrasikan(path)
    _pastikan_terpasang(path)


def main(argv=None) -> int:
    """Migrator operator eksplisit; mengembalikan 0 bila sukses, 2 bila ditolak (tanpa traceback)."""
    parser = argparse.ArgumentParser(description="Pasang skema harga (nilai aktif dan riwayat)")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    args = parser.parse_args(argv)
    path = Path(args.database)
    if not path.exists():
        print("Database tidak ditemukan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    try:
        migrasikan(path)
    except _GALAT:
        print("Migrasi ditolak: struktur tidak sah atau database tidak bisa dibuka. "
              "Periksa salinan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    print("Migrasi harga selesai dan tervalidasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
