"""Perilaku cek anak per soal (F1b): berapa kali jawaban diganti.

Satu tabel aditif, satu baris per soal, hanya `sesi_soal_id` dan `jumlah`; isi jawaban dan
kunci tidak pernah masuk ke sini. Tabel dipasang oleh `catat_ganti` di transaksi tulis
(IF NOT EXISTS), bukan di skema utama. Pembaca tidak pernah menulis atau membuat tabel.
Baris ikut hilang lewat cascade saat sesi soal atau sesinya dihapus.
"""
from __future__ import annotations

import sqlite3

TABEL = "cek_ganti_jawaban"
DDL_GANTI = """
CREATE TABLE IF NOT EXISTS cek_ganti_jawaban (
    sesi_soal_id INTEGER PRIMARY KEY REFERENCES sesi_soal(id) ON DELETE CASCADE,
    jumlah       INTEGER NOT NULL CHECK (jumlah >= 0)
)
"""


def pasang(kon: sqlite3.Connection) -> None:
    """Pasang tabel ganti. Idempoten; dipanggil di dalam transaksi tulis."""
    kon.execute(DDL_GANTI)


def baca_jawaban(kon: sqlite3.Connection, sesi_soal_id: int) -> str | None:
    """Nilai jawaban yang tersimpan untuk satu soal, None bila belum ada baris."""
    baris = kon.execute(
        "SELECT jawaban FROM jawaban WHERE sesi_soal_id = ?", (sesi_soal_id,)
    ).fetchone()
    return baris[0] if baris else None


def catat_ganti(
    kon: sqlite3.Connection,
    sesi_soal_id: int,
    jawaban_lama: str | None,
    jawaban_baru: str | None,
) -> bool:
    """Naikkan jumlah ganti bila soal sudah punya jawaban dan nilainya berbeda. True bila naik."""
    if not jawaban_lama or jawaban_lama == jawaban_baru:
        return False
    pasang(kon)
    kon.execute(
        """INSERT INTO cek_ganti_jawaban (sesi_soal_id, jumlah) VALUES (?, 1)
           ON CONFLICT(sesi_soal_id) DO UPDATE SET jumlah = jumlah + 1""",
        (sesi_soal_id,),
    )
    return True


def _ada_tabel(kon: sqlite3.Connection) -> bool:
    return kon.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABEL,)
    ).fetchone() is not None


def jumlah_ganti_per_sesi(kon: sqlite3.Connection, sesi_id: int) -> dict:
    """{sesi_soal_id: jumlah} untuk satu sesi. Kosong bila tabel belum pernah dipasang; tidak menulis."""
    if not _ada_tabel(kon):
        return {}
    return {
        int(baris[0]): int(baris[1])
        for baris in kon.execute(
            """SELECT g.sesi_soal_id, g.jumlah
               FROM cek_ganti_jawaban g JOIN sesi_soal ss ON ss.id = g.sesi_soal_id
               WHERE ss.sesi_id = ?""",
            (sesi_id,),
        )
    }
