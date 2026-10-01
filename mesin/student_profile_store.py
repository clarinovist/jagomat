"""Penyimpanan profil siswa dan query kepemilikan keluarga."""
from __future__ import annotations

import sqlite3


def tambah_siswa(
    kon: sqlite3.Connection, nama: str, tingkat: str = "P3", pemilik: str = "",
) -> int:
    """Tambahkan siswa secara idempoten dalam lingkup satu keluarga."""
    kon.execute(
        "INSERT OR IGNORE INTO siswa (nama, tingkat, pemilik) VALUES (?, ?, ?)",
        (nama, tingkat, pemilik),
    )
    baris = kon.execute(
        "SELECT id FROM siswa WHERE nama = ? AND pemilik = ?", (nama, pemilik)
    ).fetchone()
    return int(baris["id"])


def daftar_siswa(
    kon: sqlite3.Connection, pemilik: str | None = None,
) -> list[sqlite3.Row]:
    """Daftar siswa; ``None`` mempertahankan permukaan lintas keluarga admin."""
    if pemilik is None:
        return kon.execute("SELECT * FROM siswa ORDER BY nama").fetchall()
    return kon.execute(
        "SELECT * FROM siswa WHERE pemilik = ? ORDER BY nama", (pemilik,)
    ).fetchall()


def siswa_milik(
    kon: sqlite3.Connection, siswa_id: int, pemilik: str,
) -> bool:
    """Benar bila siswa dimiliki keluarga yang diminta."""
    baris = kon.execute(
        "SELECT 1 FROM siswa WHERE id = ? AND pemilik = ?", (siswa_id, pemilik)
    ).fetchone()
    return baris is not None


def sesi_milik(
    kon: sqlite3.Connection, sesi_id: int, pemilik: str,
) -> bool:
    """Benar bila sesi terkait siswa milik keluarga yang diminta."""
    baris = kon.execute(
        """SELECT 1
           FROM sesi s JOIN siswa w ON w.id = s.siswa_id
           WHERE s.id = ? AND w.pemilik = ?""",
        (sesi_id, pemilik),
    ).fetchone()
    return baris is not None
