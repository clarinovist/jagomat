"""Peserta Paket Belajar yang aktif: paket sudah dibayar dan disetujui admin, akses belum habis (baca-saja, tanpa tulis).

Untuk halaman admin `/admin/kelas`. Setelah bukti disetujui, order keluar dari antrean "Menunggu verifikasi"; tanpa daftar
ini admin tidak punya tempat untuk menemukan anak yang sudah bayar tetapi belum ditempatkan. Hanya `siswa_id`, tanpa
nama anak, akun pembeli, atau kontak. Status penempatan dibaca dari `jadwal_penempatan`; bila tabel itu belum ada (image
lama atau rollback), penempatan = None (tidak diketahui) dan peserta tetap tampil.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional, Tuple

import kelas_dasar as k
import paket_belajar_katalog as katalog

BATAS_PESERTA = 200
_SQL_DENGAN_PENEMPATAN = (
    "SELECT a.order_id AS order_id, a.siswa_id AS siswa_id, o.paket AS paket, a.berakhir AS berakhir, "
    "(p.order_id IS NOT NULL) AS ditempatkan "
    "FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
    "LEFT JOIN jadwal_penempatan p ON p.order_id=a.order_id "
    "WHERE a.mulai<=? AND a.berakhir>? ORDER BY ditempatkan, a.berakhir, a.order_id LIMIT ?")
_SQL_TANPA_PENEMPATAN = (
    "SELECT a.order_id AS order_id, a.siswa_id AS siswa_id, o.paket AS paket, a.berakhir AS berakhir, "
    "NULL AS ditempatkan "
    "FROM kelas_akses a JOIN kelas_order o ON o.id=a.order_id "
    "WHERE a.mulai<=? AND a.berakhir>? ORDER BY a.berakhir, a.order_id LIMIT ?")


@dataclass(frozen=True)
class PesertaAktif:
    order_id: str
    siswa_id: int
    kode_paket: str
    nama_paket: str
    berakhir: str
    ditempatkan: Optional[bool]


def _peserta(baris) -> PesertaAktif:
    ditempatkan = None if baris["ditempatkan"] is None else bool(baris["ditempatkan"])
    return PesertaAktif(baris["order_id"], baris["siswa_id"], baris["paket"], katalog.ambil(baris["paket"]).nama,
                        baris["berakhir"], ditempatkan)


def daftar_peserta_aktif(kon, sekarang: str) -> Tuple[PesertaAktif, ...]:
    """Akses yang sedang berjalan pada `sekarang`: belum ditempatkan dulu, lalu yang paling cepat habis.

    `sekarang` waktu baku UTC naif (atau str ISO yang dinormalkan `kelas_dasar.ke_baku`). Dipotong `BATAS_PESERTA`.
    """
    kini = k.ke_baku(sekarang)
    try:
        baris = kon.execute(_SQL_DENGAN_PENEMPATAN, (kini, kini, BATAS_PESERTA)).fetchall()
    except sqlite3.OperationalError:
        baris = kon.execute(_SQL_TANPA_PENEMPATAN, (kini, kini, BATAS_PESERTA)).fetchall()
    return tuple(_peserta(b) for b in baris)
