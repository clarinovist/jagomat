"""Jurnal status guru: catatan nonaktifkan / aktifkan kembali oleh admin, append-only, di DB SQLite terpisah.

Hanya id akun guru dan id pengelola yang disimpan, bukan nama pengguna: tombstone penghapusan keluarga
tidak boleh meninggalkan data pribadi di jurnal, dan nama diselesaikan saat tampil dari akun yang masih ada.
catat() membuat berkas (privat 0600) dan skema pada pemakaian pertama; daftar() tidak pernah membuat berkas.
Trigger menolak UPDATE dan DELETE. Tanpa WAL, supaya seluruh isi ada di berkas utama.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import os
from pathlib import Path
import sqlite3
from typing import Tuple

import auth

ENV_BERKAS_DB = "GURU_STATUS_JURNAL_DB"
BERKAS_BAWAAN = "/data/guru-status-jurnal.db"
VERSI_SKEMA = 1
AKSI_NONAKTIFKAN = "nonaktifkan"
AKSI_AKTIFKAN = "aktifkan"
AKSI_SAH = (AKSI_NONAKTIFKAN, AKSI_AKTIFKAN)
PER_HALAMAN_BAWAAN = 25
MAKS_PANJANG_OLEH = 80
TIMEOUT_DETIK = 5.0
_KOLOM = "id, aksi, id_akun, oleh, pada, revisi"
_PESAN_TOLAK_UBAH = "jurnal status guru hanya boleh ditambah"
_DDL_TABEL = (
    "CREATE TABLE IF NOT EXISTS guru_status_jurnal (\n"
    "    id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
    "    aksi TEXT NOT NULL CHECK (aksi IN ('nonaktifkan', 'aktifkan')),\n"
    "    id_akun TEXT NOT NULL,\n"
    "    oleh TEXT NOT NULL,\n"
    "    pada INTEGER NOT NULL,\n"
    "    revisi INTEGER NOT NULL\n"
    ")"
)
_DDL_TRIGGER = (
    "CREATE TRIGGER IF NOT EXISTS guru_status_jurnal_tolak_ubah BEFORE UPDATE ON guru_status_jurnal "
    f"BEGIN SELECT RAISE(ABORT, '{_PESAN_TOLAK_UBAH}'); END",
    "CREATE TRIGGER IF NOT EXISTS guru_status_jurnal_tolak_hapus BEFORE DELETE ON guru_status_jurnal "
    f"BEGIN SELECT RAISE(ABORT, '{_PESAN_TOLAK_UBAH}'); END",
)


class GalatJurnal(Exception):
    """Berkas jurnal rusak, skemanya tak dikenali, atau tidak bisa dibaca / ditulis."""


@dataclass(frozen=True)
class EntriJurnal:
    """Satu jejak: id_akun = guru yang diubah, oleh = ID pengelola yang mengubah, revisi = revisi_auth baru."""

    id: int
    aksi: str
    id_akun: str
    oleh: str
    pada: int
    revisi: int


@dataclass(frozen=True)
class HalamanJurnal:
    """Satu halaman jurnal terbaru dulu; urutan field sama dengan HalamanRiwayat admin."""

    item: Tuple[EntriJurnal, ...]
    total: int
    halaman: int
    per_halaman: int
    jumlah_halaman: int


def _path_db(path) -> Path:
    """Tujuan DB: parameter, lalu env (dibaca saat dipanggil), lalu bawaan."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_BERKAS_DB, BERKAS_BAWAAN))


def _bilangan_positif(nilai, nama: str) -> None:
    if type(nilai) is not int or nilai < 1:
        raise ValueError(f"{nama} jurnal status guru harus bilangan bulat positif.")


def _validasi_catatan(aksi, id_akun, oleh, pada, revisi) -> None:
    if aksi not in AKSI_SAH:
        raise ValueError("Aksi jurnal status guru tidak sah.")
    if not auth.id_akun_sah(id_akun):
        raise ValueError("ID akun jurnal status guru tidak sah.")
    if type(oleh) is not str or not oleh.strip() or len(oleh) > MAKS_PANJANG_OLEH:
        raise ValueError("ID pengelola jurnal status guru tidak sah.")
    _bilangan_positif(pada, "Waktu")
    _bilangan_positif(revisi, "Revisi")


def _validasi_daftar(halaman, id_akun, per_halaman) -> None:
    if type(halaman) is not int:
        raise ValueError("Halaman jurnal status guru harus bilangan bulat.")
    _bilangan_positif(per_halaman, "Jumlah per halaman")
    if id_akun != "" and not auth.id_akun_sah(id_akun):
        raise ValueError("ID akun jurnal status guru tidak sah.")


def _pastikan_skema(kon) -> None:
    """Buat tabel dan trigger bila DB masih kosong (versi 0); versi lain selain VERSI_SKEMA ditolak."""
    versi = kon.execute("PRAGMA user_version").fetchone()[0]
    if versi == VERSI_SKEMA:
        return
    if versi != 0:
        raise GalatJurnal("Skema jurnal status guru tidak dikenali.")
    kon.execute(_DDL_TABEL)
    for ddl in _DDL_TRIGGER:
        kon.execute(ddl)
    kon.execute(f"PRAGMA user_version = {VERSI_SKEMA}")


def _siapkan_berkas(tujuan: Path) -> None:
    """Berkas baru dibuat 0600 sebelum SQLite membukanya; berkas yang sudah ada tidak diubah."""
    try:
        os.close(os.open(tujuan, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600))
    except FileExistsError:
        pass  # berkas sudah ada (atau dibuat proses lain): tidak diubah


def catat(aksi: str, id_akun: str, oleh: str, pada: int, revisi: int, path=None) -> None:
    """Tambah satu entri dalam satu transaksi. Argumen tidak sah ditolak sebelum berkas disentuh."""
    _validasi_catatan(aksi, id_akun, oleh, pada, revisi)
    tujuan = _path_db(path)
    try:
        _siapkan_berkas(tujuan)
        with closing(sqlite3.connect(str(tujuan), timeout=TIMEOUT_DETIK)) as kon, kon:
            kon.execute("BEGIN IMMEDIATE")
            _pastikan_skema(kon)
            kon.execute(
                "INSERT INTO guru_status_jurnal (aksi, id_akun, oleh, pada, revisi) VALUES (?, ?, ?, ?, ?)",
                (aksi, id_akun, oleh, pada, revisi),
            )
    except (OSError, sqlite3.Error) as err:
        raise GalatJurnal("Jurnal status guru tidak bisa ditulis.") from err


def _rentang_halaman(total: int, halaman: int, per_halaman: int) -> Tuple[int, int]:
    """Halaman yang dijepit ke rentang sah, dan jumlah halaman (minimal 1)."""
    jumlah = max(1, (total + per_halaman - 1) // per_halaman)
    return min(max(halaman, 1), jumlah), jumlah


def _halaman_kosong(halaman: int, per_halaman: int) -> HalamanJurnal:
    dijepit, jumlah = _rentang_halaman(0, halaman, per_halaman)
    return HalamanJurnal((), 0, dijepit, per_halaman, jumlah)


def _filter_id(id_akun: str) -> Tuple[str, tuple]:
    if id_akun == "":
        return "", ()
    return " WHERE id_akun = ?", (id_akun,)


def _baca_halaman(kon, halaman: int, id_akun: str, per_halaman: int) -> HalamanJurnal:
    versi = kon.execute("PRAGMA user_version").fetchone()[0]
    if versi == 0:
        return _halaman_kosong(halaman, per_halaman)
    if versi != VERSI_SKEMA:
        raise GalatJurnal("Skema jurnal status guru tidak dikenali.")
    filter_sql, parameter = _filter_id(id_akun)
    total = kon.execute(f"SELECT COUNT(*) FROM guru_status_jurnal{filter_sql}", parameter).fetchone()[0]
    dijepit, jumlah = _rentang_halaman(total, halaman, per_halaman)
    baris = kon.execute(
        f"SELECT {_KOLOM} FROM guru_status_jurnal{filter_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*parameter, per_halaman, (dijepit - 1) * per_halaman),
    ).fetchall()
    return HalamanJurnal(tuple(EntriJurnal(*b) for b in baris), total, dijepit, per_halaman, jumlah)


def daftar(halaman: int = 1, id_akun: str = "", per_halaman: int = PER_HALAMAN_BAWAAN, path=None) -> HalamanJurnal:
    """Entri terbaru dulu, dipaginasi. Berkas belum ada = halaman kosong; berkas tidak pernah dibuat di sini."""
    _validasi_daftar(halaman, id_akun, per_halaman)
    tujuan = _path_db(path)
    if not tujuan.exists():
        return _halaman_kosong(halaman, per_halaman)
    try:
        with closing(sqlite3.connect(tujuan.resolve().as_uri() + "?mode=ro", uri=True, timeout=TIMEOUT_DETIK)) as kon:
            return _baca_halaman(kon, halaman, id_akun, per_halaman)
    except sqlite3.Error as err:
        raise GalatJurnal("Jurnal status guru tidak bisa dibaca.") from err