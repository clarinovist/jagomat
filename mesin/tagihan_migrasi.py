"""CLI operator: pasang skema tagihan (`tagihan_catatan`: catatan batal/pulih) di admin-control.db.

Tidak pernah dipanggil startup, GET, atau rilis otomatis; operator menjalankannya terhadap SALINAN terverifikasi dulu,
baru DB live setelah hold dan backup (lihat `docs/production-release.md`):

    mesin/.venv/bin/python mesin/tagihan_migrasi.py --database <admin-control.db>

Prasyarat: `kelas_*` (dan karena itu `pesanan_*`/`transfer_*`/`purna_*`) sudah terpasang, karena `tagihan_catatan` mereferensi
`kelas_order`. Bila belum, perintah ditolak (exit 2) tanpa mengubah apa pun. Idempoten, tanpa seed, tanpa bump `user_version`.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

import admin_store_core
import schema_kelas
import schema_tagihan_catatan

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
        if not schema_tagihan_catatan.validasi(kon):
            raise ValueError("tagihan tidak terpasang setelah migrasi")
    finally:
        kon.close()


def migrasikan(path: Path) -> None:
    periksa_prasyarat(path)
    schema_tagihan_catatan.migrasikan(path)
    _pastikan_terpasang(path)


def main(argv=None) -> int:
    """Migrator operator eksplisit; mengembalikan 0 bila sukses, 2 bila ditolak (tanpa traceback)."""
    parser = argparse.ArgumentParser(description="Pasang skema tagihan (catatan batal/pulih Paket Belajar)")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    args = parser.parse_args(argv)
    path = Path(args.database)
    if not path.exists():
        print("Database tidak ditemukan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    try:
        migrasikan(path)
    except PrasyaratBelumAda:
        print("Paket belajar (kelas_*) harus sudah terpasang sebelum tagihan. Tidak ada yang diubah.",
              file=sys.stderr)
        return 2
    except _GALAT:
        print("Migrasi ditolak: struktur tidak sah atau database tidak bisa dibuka. "
              "Periksa salinan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    print("Migrasi tagihan selesai dan tervalidasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
