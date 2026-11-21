"""Penguatan berkas data saat startup (mode 0600 dan jurnal WAL).

Dua hal, keduanya hanya pada berkas yang SUDAH ada (tidak pernah membuat berkas,
tidak DDL, tidak menyentuh isi/user_version):

1. Mode: semua DB durable beserta sidecar `-wal`/`-shm` berakhir 0600.
   Hanya berkas biasa milik euid proses, hanya bila mode berbeda.
2. WAL: cadangan harian menormalkan salinan ke `journal_mode=DELETE`. Setelah
   restore, store yang `siapkan()`-nya dipanggil saat start mengembalikan WAL
   sendiri; DB yang tidak melewati `siapkan()` di startup (pendamping, sakelar,
   kurikulum, cetakan, cetakan_ai) dikembalikan di sini lewat `jurnal_wal.aktifkan`.

Galat tidak pernah menghentikan server: dikumpulkan di ringkasan lalu dicetak
satu baris ke stderr oleh `kencangkan_saat_start`.
"""
from __future__ import annotations

import os
import sqlite3
import stat
import sys
from contextlib import closing
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote

import admin_store
import ai_store
import assistant_schema
import cetakan_ai_store
import cetakan_store
import database
import feature_switch
import jurnal_wal
import kurikulum_override
import research_store

MODE_AMAN = 0o600
SUFIKS_SIDECAR = ("-wal", "-shm")
TIMEOUT_KUNCI_DETIK = 5.0


def _jalur_env(modul) -> Path:
    """Jalur DB store yang memakai ENV_BERKAS_DB/BERKAS_BAWAAN (env dibaca saat dipanggil)."""
    return Path(os.environ.get(modul.ENV_BERKAS_DB, modul.BERKAS_BAWAAN))


def _jalur_sakelar_dll() -> List[Path]:
    return [
        _jalur_env(feature_switch),
        _jalur_env(kurikulum_override),
        _jalur_env(cetakan_store),
        _jalur_env(cetakan_ai_store),
    ]


def jalur_db_durable() -> List[Path]:
    """Sembilan DB durable, jalurnya mengikuti env/bawaan masing-masing store."""
    return [
        Path(database.BAWAAN),
        Path(admin_store.BAWAAN),
        Path(ai_store.BAWAAN),
        Path(assistant_schema.BAWAAN),
        Path(research_store.BAWAAN),
    ] + _jalur_sakelar_dll()


def jalur_wal() -> List[Path]:
    """DB yang WAL-nya perlu dipulihkan di sini (tidak lewat siapkan() startup)."""
    return [Path(assistant_schema.BAWAAN)] + _jalur_sakelar_dll()


def _berkas_biasa(path: Path) -> Optional[os.stat_result]:
    """stat tanpa mengikuti symlink; None bila tak ada atau bukan berkas biasa."""
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return None
    return info if stat.S_ISREG(info.st_mode) else None


def _kencangkan_satu(path: Path, ringkasan: Dict[str, list]) -> None:
    info = _berkas_biasa(path)
    if info is None:
        return
    if stat.S_IMODE(info.st_mode) == MODE_AMAN:
        return
    if info.st_uid != os.geteuid():
        ringkasan["galat"].append(f"{path}: bukan milik proses ini, mode tidak diubah")
        return
    try:
        os.chmod(path, MODE_AMAN)
    except OSError as exc:
        ringkasan["galat"].append(f"{path}: chmod gagal ({exc})")
        return
    ringkasan["diubah"].append(str(path))


def _aktifkan_wal_satu(path: Path, ringkasan: Dict[str, list]) -> None:
    info = _berkas_biasa(path)
    if info is None or info.st_size == 0:
        return
    uri = f"file:{quote(str(path))}?mode=rw"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=TIMEOUT_KUNCI_DETIK)) as kon:
            mode = str(kon.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            if mode == "wal":
                return
            jurnal_wal.aktifkan(kon)
    except sqlite3.Error as exc:
        ringkasan["galat"].append(f"{path}: aktivasi WAL gagal ({exc})")
        return
    ringkasan["wal"].append(str(path))


def kencangkan_data(
    berkas: Optional[Iterable[Path]] = None,
    wal: Optional[Iterable[Path]] = None,
) -> Dict[str, list]:
    """Aktifkan WAL (bila perlu) lalu pastikan mode 0600; kembalikan ringkasan.

    WAL lebih dulu agar sidecar yang baru muncul ikut dikencangkan. Tidak melempar.
    """
    daftar_berkas = list(jalur_db_durable() if berkas is None else berkas)
    daftar_wal = list(jalur_wal() if wal is None else wal)
    ringkasan: Dict[str, list] = {"diubah": [], "wal": [], "galat": []}
    for path in daftar_wal:
        _aktifkan_wal_satu(Path(path), ringkasan)
    for path in daftar_berkas:
        for sufiks in ("",) + SUFIKS_SIDECAR:
            _kencangkan_satu(Path(str(path) + sufiks), ringkasan)
    return ringkasan


def kencangkan_saat_start() -> None:
    """Titik masuk startup: jalankan penguatan, laporkan galat satu baris, jangan melempar."""
    try:
        ringkasan = kencangkan_data()
    except Exception as exc:  # noqa: BLE001 - startup tidak boleh gagal karena penguatan
        print(f"berkas_data: penguatan gagal ({exc})", file=sys.stderr)
        return
    if ringkasan["galat"]:
        print("berkas_data: " + "; ".join(ringkasan["galat"]), file=sys.stderr)
