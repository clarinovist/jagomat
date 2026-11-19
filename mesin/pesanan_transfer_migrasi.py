"""CLI operator: pasang skema transfer rekening (`transfer_*`) dan rekening tujuan (`rekening_*`).

Tidak pernah dipanggil startup, GET, atau rilis otomatis; operator menjalankannya terhadap SALINAN
terverifikasi dulu, baru DB live setelah hold dan backup (lihat `docs/production-release.md`):

    mesin/.venv/bin/python mesin/pesanan_transfer_migrasi.py --database <admin-control.db>

Urutan mengikuti kunci asing: `transfer_*` bergantung pada `pesanan_*`, jadi ledger pesanan wajib sudah
terpasang. Bila belum, perintah gagal keras tanpa mengubah apa pun; `--termasuk-pesanan` memasangnya
lebih dulu (keputusan operator, langkah rilis tersendiri). Semua langkah idempoten, tanpa seed (rekening
tetap kosong sampai admin mengisinya), tanpa bump `user_version`.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
import time

import admin_store
import admin_store_core
import pesanan_rekening
import schema_pesanan
import schema_transfer

_GALAT = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError)


def _pesanan_terpasang(path: Path) -> bool:
    with admin_store.buka_baca(path) as kon:
        return bool(schema_pesanan.validasi(kon))


def migrasikan(path: Path, *, sekarang: int, termasuk_pesanan: bool = False) -> None:
    """Pasang (idempoten) pesanan [opsional] -> transfer_* -> rekening_*; galat dilempar apa adanya."""
    if termasuk_pesanan:
        schema_pesanan.migrasikan(path)
    elif not _pesanan_terpasang(path):
        raise admin_store_core.StoreBelumSiap("pesanan belum dipasang")
    schema_transfer.migrasikan(path)
    pesanan_rekening.migrasikan(path, sekarang=sekarang)


def main(argv=None) -> int:
    """Migrator operator eksplisit; mengembalikan 0 bila sukses, 2 bila ditolak (tanpa traceback)."""
    parser = argparse.ArgumentParser(description="Pasang schema transfer rekening dan rekening tujuan")
    parser.add_argument("--database", required=True, help="Path admin-control.db yang sudah diverifikasi")
    parser.add_argument("--termasuk-pesanan", action="store_true",
                        help="pasang juga ledger pesanan_* bila belum ada (langkah rilis tersendiri)")
    args = parser.parse_args(argv)
    path = Path(args.database)
    if not path.exists():
        print("Database tidak ditemukan; tidak ada yang diubah.", file=sys.stderr)
        return 2
    try:
        migrasikan(path, sekarang=int(time.time()), termasuk_pesanan=args.termasuk_pesanan)
    except admin_store_core.StoreBelumSiap:
        print("Ledger pesanan belum terpasang; pasang dulu atau ulangi dengan --termasuk-pesanan. "
              "Tidak ada yang diubah.", file=sys.stderr)
        return 2
    except _GALAT:
        print("Migrasi ditolak: struktur tidak sah atau database tidak bisa dibuka. "
              "Periksa salinan; tidak ada yang diubah di luar langkah yang sudah selesai.", file=sys.stderr)
        return 2
    print("Migrasi transfer rekening selesai dan tervalidasi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
