"""Catatan batal/pulih tagihan kelas (`tagihan_catatan`): pembacaan dan satu penulisan per aksi.

Modul daun: hanya mengimpor `kelas_dasar` dan `schema_tagihan_catatan`, TIDAK mengimpor `kelas_status` (yang memanggil
modul ini). Tabel belum dipasang berarti tidak ada catatan, bukan galat, sehingga DB yang belum dimigrasikan tetap terbaca.
Jangan menangkap `OperationalError` di sini: "database locked" juga `OperationalError`, dan itu tidak boleh tampak sebagai
tagihan yang dibatalkan.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import kelas_dasar as k
import schema_tagihan_catatan as stc

AKSI_BATAL = stc.AKSI_BATAL
AKSI_PULIH = stc.AKSI_PULIH


def terpasang(kon) -> bool:
    return stc.terpasang(kon)


def terakhir_aksi(kon, order_id: str) -> Optional[str]:
    """Aksi terakhir pada tagihan ('batal' atau 'pulih'); None bila belum ada catatan atau tabel belum dipasang."""
    if not stc.terpasang(kon):
        return None
    baris = kon.execute("SELECT aksi FROM tagihan_catatan WHERE order_id=? ORDER BY id DESC LIMIT 1",
                        (order_id,)).fetchone()
    return None if baris is None else baris[0]


def dibatalkan(kon, order_id: str) -> bool:
    """True bila catatan terakhir tagihan ini `batal`; False bila tabel belum dipasang."""
    return terakhir_aksi(kon, order_id) == AKSI_BATAL


def catat(kon, order_id: str, aksi: str, kini: str) -> None:
    """Tambah satu catatan. Pelanggaran aturan trigger (atau aksi di luar daftar) -> KelasKonflik tanpa baris baru."""
    try:
        kon.execute("INSERT INTO tagihan_catatan(order_id,aksi,dibuat) VALUES(?,?,?)", (order_id, aksi, kini))
    except sqlite3.IntegrityError:
        raise k.KelasKonflik("perubahan status tagihan ditolak oleh aturan catatan") from None
