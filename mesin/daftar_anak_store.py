"""Persetujuan pendaftaran akun anak: satu baris per anak, ditulis di transaksi pemanggil (tanpa commit).

`versi_notice` adalah konstanta yang sama dengan yang dicatat `cek_gratis.mulai` (`cek_gratis_skor.VERSI_NOTICE`),
sehingga bukti persetujuan saat daftar dan saat memulai cek berbicara tentang notice yang sama.
"""
from __future__ import annotations

from datetime import datetime, timezone

from cek_gratis_skor import VERSI_NOTICE

_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"


def waktu_utc(kini: int) -> str:
    """Epoch detik -> teks ISO UTC (format yang sama dengan `kontak_akun`)."""
    if type(kini) is not int or kini < 0:
        raise ValueError("waktu tidak sah")
    return datetime.fromtimestamp(kini, timezone.utc).strftime(_FORMAT_WAKTU)


def catat_persetujuan(kon, siswa_id: int, kini: int) -> None:
    """Tulis persetujuan orang tua/wali untuk anak ini (INSERT; baris kedua menolak lewat PRIMARY KEY)."""
    if type(siswa_id) is not int or siswa_id <= 0:
        raise ValueError("siswa_id tidak sah")
    kon.execute(
        "INSERT INTO persetujuan_daftar_anak(siswa_id, versi_notice, setuju_pada) VALUES (?, ?, ?)",
        (siswa_id, VERSI_NOTICE, waktu_utc(kini)),
    )


def ambil_persetujuan(kon, siswa_id: int):
    """(versi_notice, setuju_pada) atau None."""
    baris = kon.execute(
        "SELECT versi_notice, setuju_pada FROM persetujuan_daftar_anak WHERE siswa_id = ?", (siswa_id,)
    ).fetchone()
    return None if baris is None else (baris[0], baris[1])
