"""Ringkasan harian tunggakan paket kelas untuk ADMIN lewat Resend (CLI; belum dipasang di produksi).

Hanya agregat yang dikirim: total, jumlah per paket, dan jumlah per rentang hari. Tanpa id anak, nama, atau
tanggal berakhir per anak. Satu email per tanggal WIB (`Idempotency-Key` `tunggakan-kelas-YYYY-MM-DD`).
DB dibuka baca-saja dan CLI tidak menulis apa pun.

Urutan gagal tertutup: alamat admin dan kunci API diperiksa lebih dulu, sehingga konfigurasi yang belum diatur
keluar 2 walau hari itu tidak ada tunggakan. Lalu DB dan tabel kelas harus siap (keluar 2), baru tunggakan
dihitung. Tanpa tunggakan keluar 0 tanpa mengirim. Kode keluar: 0 terkirim atau tidak ada yang dikirim,
1 gagal kirim, 2 ditahan (konfigurasi, DB, atau tabel kelas). Pemasangan cron di host adalah tindakan terpisah.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping, Optional, Sequence, Tuple

import kelas_dasar as k
import kelas_tunggakan as kt
import schema_kelas
import surel_resend as sr

URL_ADMIN = "https://jagomat.id/admin"
ENV_ADMIN = "SUREL_ADMIN"
AWALAN_KUNCI = "tunggakan-kelas-"
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
SELISIH_WIB = timedelta(hours=7)
EXIT_TERKIRIM = 0
EXIT_GAGAL = 1
EXIT_TERTAHAN = 2
PESAN_KOSONG = "surel tunggakan: tidak ada tunggakan, tidak ada yang dikirim"


def _sekarang_utc() -> str:
    return datetime.now(timezone.utc).strftime(FORMAT_WAKTU)


def kunci_idempotensi(sekarang: str) -> str:
    """Kunci per tanggal WIB dari waktu UTC naif `sekarang` (format `YYYY-MM-DDTHH:MM:SS`)."""
    waktu_utc = datetime.strptime(k.ke_baku(sekarang), FORMAT_WAKTU)
    return AWALAN_KUNCI + (waktu_utc + SELISIH_WIB).strftime("%Y-%m-%d")


def _baris_per_paket(daftar) -> list:
    jumlah = Counter(t.nama_paket for t in daftar)
    return ["- %s: %d" % (nama, jumlah[nama]) for nama in sorted(jumlah)]


def _baris_per_rentang(daftar) -> list:
    sedang = sum(1 for t in daftar if kt.HARI_TUNGGAKAN_MIN <= t.hari_lewat < kt.HARI_TUNGGAKAN_PENTING)
    lama = sum(1 for t in daftar if t.hari_lewat >= kt.HARI_TUNGGAKAN_PENTING)
    return [
        "- %d sampai %d hari: %d" % (kt.HARI_TUNGGAKAN_MIN, kt.HARI_TUNGGAKAN_PENTING - 1, sedang),
        "- %d hari atau lebih: %d" % (kt.HARI_TUNGGAKAN_PENTING, lama),
    ]


def susun_ringkasan(tunggakan, *, url_admin: str = URL_ADMIN) -> Optional[Tuple[str, str]]:
    """(subjek, teks) yang hanya memuat agregat; None bila tidak ada tunggakan."""
    daftar = tuple(tunggakan)
    if not daftar:
        return None
    total = len(daftar)
    subjek = "Jagomat: %d tunggakan paket kelas" % total
    teks = "\n".join([
        "Ringkasan harian tunggakan paket kelas (agregat, tanpa data anak).",
        "",
        "Total: %d tunggakan" % total,
        "",
        "Per paket:",
        *_baris_per_paket(daftar),
        "",
        "Berdasarkan hari sejak paket berakhir:",
        *_baris_per_rentang(daftar),
        "",
        "Buka antrean admin: " + url_admin,
    ])
    return subjek, teks


def buka_baca_saja(path) -> sqlite3.Connection:
    """Koneksi baca-saja (mode=ro, query_only) dengan kolom bernama, untuk membaca tunggakan."""
    kon = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    kon.row_factory = sqlite3.Row
    kon.execute("PRAGMA query_only = ON")
    return kon


def _tunggakan_dari_db(path: Path, waktu: str):
    """Tunggakan dari DB baca-saja; None bila DB atau tabel kelas belum siap (gagal tertutup)."""
    if not path.is_file():
        return None
    try:
        with closing(buka_baca_saja(path)) as kon:
            if not schema_kelas.validasi(kon):
                return None
            return kt.daftar_tunggakan(kon, waktu)
    except (sqlite3.Error, ValueError):
        return None


def _masalah_konfigurasi(alamat: str, kunci: str) -> Optional[str]:
    if not sr.alamat_sah(alamat):
        return "alamat admin belum diatur atau tidak sah"
    if not kunci:
        return "kunci API belum diatur"
    return None


def _cetak_hasil(hasil: sr.HasilKirim, jumlah: int) -> int:
    if hasil.status == sr.STATUS_TERKIRIM:
        print("surel tunggakan: terkirim, %d tunggakan" % jumlah)
        return EXIT_TERKIRIM
    if hasil.status == sr.STATUS_DITAHAN:
        print("surel tunggakan: ditahan, %s" % hasil.alasan)
        return EXIT_TERTAHAN
    kode = "" if hasil.kode_http is None else " (kode %d)" % hasil.kode_http
    print("surel tunggakan: gagal, %s%s" % (hasil.alasan, kode))
    return EXIT_GAGAL


def _jalankan(path: Path, waktu: str, alamat: str, kunci: str, pengirim: str,
              transport: Optional[sr.Transport]) -> int:
    daftar = _tunggakan_dari_db(path, waktu)
    if daftar is None:
        print("surel tunggakan: ditahan, database atau tabel kelas belum siap")
        return EXIT_TERTAHAN
    ringkasan = susun_ringkasan(daftar)
    if ringkasan is None:
        print(PESAN_KOSONG)
        return EXIT_TERKIRIM
    subjek, teks = ringkasan
    hasil = sr.kirim(alamat, subjek, teks, kunci_idempotensi=kunci_idempotensi(waktu), kunci_api=kunci,
                     pengirim=pengirim, transport=transport)
    return _cetak_hasil(hasil, len(daftar))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kirim ringkasan harian tunggakan paket kelas ke admin")
    parser.add_argument("--database", required=True, help="Path admin-control.db (dibuka baca-saja)")
    return parser


def main(argv: Optional[Sequence[str]] = None, *, sekarang: Optional[str] = None,
         transport: Optional[sr.Transport] = None, env: Optional[Mapping[str, str]] = None) -> int:
    """Satu sapuan ringkasan. `sekarang` (UTC naif) dan `transport` hanya untuk uji."""
    args = _parser().parse_args(argv)
    lingkungan = os.environ if env is None else env
    alamat = (lingkungan.get(ENV_ADMIN) or "").strip()
    kunci = (lingkungan.get(sr.ENV_KUNCI) or "").strip()
    masalah = _masalah_konfigurasi(alamat, kunci)
    if masalah is not None:
        print("surel tunggakan: ditahan, %s" % masalah)
        return EXIT_TERTAHAN
    pengirim = (lingkungan.get(sr.ENV_PENGIRIM) or "").strip() or sr.PENGIRIM_BAWAAN
    return _jalankan(Path(args.database), sekarang or _sekarang_utc(), alamat, kunci, pengirim, transport)


if __name__ == "__main__":
    sys.exit(main())
