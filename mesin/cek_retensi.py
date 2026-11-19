"""Sapuan retensi cek gratis (30/7 hari) untuk penjadwal/cron.

Dijalankan operator atau cron di dalam container, misalnya:

    docker exec osn-mesin python cek_retensi.py --database /data/latihan.db

Aturan retensi ada di `cek_gratis_sapu`; modul ini hanya menyiapkan target,
daftar akun hidup, dan waktu, lalu mencetak agregat jumlah (tanpa nama anak,
id akun, atau isi jawaban). Aman diulang: sapuan kedua tanpa perubahan = nol.

Fail-closed: berkas akun tidak terbaca/daftar akun kosong, DB tidak ada, atau
tabel cek belum siap -> exit 2 tanpa menghapus apa pun. Cron dijalankan saat
aplikasi hidup; backup operasional menahan cron writer sebelum menyalin DB.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import sys
from typing import Optional

import auth
import cek_gratis_sapu
import database

FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
EXIT_SIAP = 2


def akun_hidup(path_sandi: Optional[str] = None) -> frozenset:
    """Id akun yang masih ada di berkas akun; kosong/tidak sah -> ValueError."""
    akun = auth.muat_akun(Path(path_sandi) if path_sandi else None)
    ids = {a.get("id_akun") for a in akun if isinstance(a, dict)}
    ids.discard(None)
    if not ids:
        raise ValueError("daftar akun hidup kosong atau tidak terbaca")
    return frozenset(ids)


def _sekarang_utc() -> str:
    return datetime.now(timezone.utc).strftime(FORMAT_WAKTU)


def _ringkasan(hasil: dict) -> str:
    return ("Sapu retensi cek selesai: %d bahan dihapus, %d belum selesai, "
            "%d tak terhitung, %d yatim, %d terlindungi bukti belajar."
            % (hasil["bahan_dihapus"], hasil["belum_selesai"], hasil["tak_terhitung"],
               hasil["yatim"], hasil["terlindungi"]))


def main(argv=None, *, sekarang: Optional[str] = None) -> int:
    """Satu sapuan retensi; `sekarang` hanya untuk uji (UTC naif)."""
    parser = argparse.ArgumentParser(description="Sapu retensi cek kemampuan gratis")
    parser.add_argument("--database", required=True, help="Path latihan.db yang sudah diverifikasi")
    parser.add_argument("--sandi", help="Path berkas akun (bawaan: OSN_BERKAS_SANDI)")
    args = parser.parse_args(argv)
    path_db = Path(args.database)
    if not path_db.exists():
        print("Database tidak ditemukan; tidak ada yang diubah.", file=sys.stderr)
        return EXIT_SIAP
    try:
        hidup = akun_hidup(args.sandi)
        with database.buka(path_db) as kon:
            hasil = cek_gratis_sapu.sapu_cek_gratis(kon, sekarang or _sekarang_utc(), hidup)
    except ValueError as galat:
        print("Target retensi tidak siap: %s. Tidak ada yang diubah." % galat, file=sys.stderr)
        return EXIT_SIAP
    except (sqlite3.Error, OSError) as galat:
        print("Database/akun tidak bisa dibuka: %s. Tidak ada yang diubah." % galat, file=sys.stderr)
        return EXIT_SIAP
    print(_ringkasan(hasil))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
