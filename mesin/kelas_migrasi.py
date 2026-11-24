"""CLI operator: pasang skema Paket Belajar (`kelas_*`: tagihan, bukti, keputusan, akses, keluarga).

Tidak pernah dipanggil startup, GET, atau rilis otomatis; operator menjalankannya terhadap SALINAN
terverifikasi dulu, baru DB live setelah hold dan backup (lihat `docs/production-release.md`):

    mesin/.venv/bin/python mesin/kelas_migrasi.py --database <admin-control.db>

`kelas_*` bergantung pada ledger `pesanan_*` (kunci asing deposit) dan namespace `transfer_*` (jalur bukti
yang dibuka `kelas_store`), jadi keduanya wajib sudah terpasang. Bila belum, perintah ditolak (exit 2)
tanpa mengubah apa pun; tidak ada opsi memasang keduanya dari sini. `purna_*` opsional: tanpa purna tidak
ada potongan deposit. Idempoten, tanpa seed, tanpa bump `user_version`.

Sapuan retensi bukti subfolder `kelas/` BELUM ada (di luar cakupan migrasi ini); berkas dipertahankan
sampai sapuan khusus dibuat.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

import admin_store_core
import schema_kelas
import schema_pesanan
import schema_transfer

_GALAT = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError)


class PrasyaratBelumAda(Exception):
    """Ledger pesanan atau transfer belum terpasang; tidak ada yang diubah."""


def _buka_ro(path: Path) -> sqlite3.Connection:
    kon = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5.0)
    kon.execute("PRAGMA query_only=ON")
    return kon


def periksa_prasyarat(path: Path) -> None:
    """Pastikan pesanan dan transfer terpasang dan sah (hanya baca); ValueError bila parsial."""
    kon = _buka_ro(path)
    try:
        if not schema_pesanan.validasi(kon):
            raise PrasyaratBelumAda("pesanan belum dipasang")
        if not schema_transfer.validasi(kon):
            raise PrasyaratBelumAda("transfer belum dipasang")
    finally:
        kon.close()


def _pastikan_terpasang(path: Path) -> None:
    kon = _buka_ro(path)
    try:
        if not schema_kelas.validasi(kon):
            raise ValueError("kelas tidak terpasang setelah migrasi")
    finally:
        kon.close()


def migrasikan(path: Path) -> None:
    """Pasang (idempoten) kelas_* di atas pesanan + transfer; galat dilempar apa adanya."""
    periksa_prasyarat(path)
    schema_kelas.migrasikan(path)
    _pastikan_terpasang(path)


def main(argv=None) -> int:
    """Migrator operator eksplisit; mengembalikan 0 bila sukses, 2 bila ditolak (tanpa traceback)."""
    parser = argparse.ArgumentParser(description="Pasang schema Paket Belajar (kelas_*)")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    args = parser.parse_args(argv)
    path = Path(args.database)
    if not path.exists():
        print("Database tidak ditemukan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    try:
        migrasikan(path)
    except PrasyaratBelumAda:
        print("Ledger pesanan dan transfer harus sudah terpasang sebelum kelas; pasang dulu lewat "
              "langkah rilis transfer. Tidak ada yang diubah.", file=sys.stderr)
        return 2
    except _GALAT:
        print("Migrasi ditolak: struktur tidak sah atau database tidak bisa dibuka. "
              "Periksa salinan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    print("Migrasi Paket Belajar selesai dan tervalidasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
