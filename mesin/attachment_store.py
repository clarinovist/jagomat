"""Metadata lampiran foto; transaksi tetap dimiliki pemanggil."""
from __future__ import annotations

import sqlite3


def simpan_lampiran(
    kon: sqlite3.Connection,
    sesi_id: int,
    nama_berkas: str,
    mime: str = "image/jpeg",
    hasil_json: str = "",
) -> int:
    """Simpan metadata lampiran; berkas di cakram diurus pemanggil."""
    cur = kon.execute(
        """INSERT INTO lampiran (sesi_id, nama_berkas, mime, hasil_json)
           VALUES (?, ?, ?, ?)""",
        (sesi_id, nama_berkas, mime, hasil_json),
    )
    return int(cur.lastrowid)


def daftar_lampiran(
    kon: sqlite3.Connection, sesi_id: int,
) -> list[sqlite3.Row]:
    return kon.execute(
        "SELECT * FROM lampiran WHERE sesi_id = ? ORDER BY id DESC", (sesi_id,)
    ).fetchall()


def ambil_lampiran(
    kon: sqlite3.Connection, lampiran_id: int,
) -> sqlite3.Row | None:
    return kon.execute(
        "SELECT * FROM lampiran WHERE id = ?", (lampiran_id,)
    ).fetchone()


def tandai_lampiran(
    kon: sqlite3.Connection, lampiran_id: int, status: str,
) -> None:
    """Ubah status lampiran: ``baru`` atau ``diterapkan``."""
    kon.execute(
        "UPDATE lampiran SET status = ? WHERE id = ?", (status, lampiran_id)
    )
