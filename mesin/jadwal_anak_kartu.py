"""Kartu "Sesi berikutnya" di beranda anak (`/murid`): waktu WIB, durasi, nama login guru; tanpa tautan atau id.

Gerbang sakelar `paket_belajar_gate.aktif()`. Baca-saja: DB admin lewat `jadwal_store.buka` (mode ro) dan daftar akun
lewat `auth.muat_akun` (hanya nama login guru aktif). Galat baca = tanpa kartu (fail-silent, log tanpa data), supaya
beranda tidak pernah rusak karena fitur tambahan ini.
"""
from __future__ import annotations

import html
import logging
import sqlite3
from typing import Optional

import admin_store
import admin_store_core
import auth
import jadwal_anak_baca as baca
import jadwal_store
import paket_belajar_gate
import pesanan_alur
from pesanan_transfer_pages import waktu_wib

_log = logging.getLogger(__name__)
GALAT_BACA = (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError, OSError)
PERAN_GURU = "guru"
JUDUL = "Sesi berikutnya"
TEKS_BERLANGSUNG = "Sedang berlangsung"
ID_JUDUL = "judul-jadwal-anak"


def _nama_guru(guru_id: str) -> Optional[str]:
    """Nama login guru aktif (peran guru, tidak dinonaktifkan) atau None; id guru tidak pernah dikembalikan."""
    for akun in auth.muat_akun():
        if akun.get("id_akun") == guru_id and akun.get("peran") == PERAN_GURU and not akun.get("dinonaktifkan"):
            return akun.get("pengguna")
    return None


def kartu_html(sesi: dict, nama_guru: Optional[str]) -> str:
    """Kartu satu sesi: waktu WIB, durasi, baris guru bila ada, dan penanda berlangsung. Semua teks di-escape."""
    baris = [f"<p>{html.escape(waktu_wib(sesi['mulai']))}</p>", f"<p>Durasi: {sesi['menit']} menit</p>"]
    if nama_guru is not None:
        baris.append(f"<p>Guru: {html.escape(nama_guru)}</p>")
    if sesi["berlangsung"]:
        baris.append(f"<p><b>{TEKS_BERLANGSUNG}</b></p>")
    return (f'<section class="murid-latihan-lain-st" aria-labelledby="{ID_JUDUL}" style="margin-block-end: 1rem">'
            f'<div class="murid-kepala-bagian-st"><h2 id="{ID_JUDUL}">{JUDUL}</h2></div>'
            f'<div class="st-kartu">{"".join(baris)}</div></section>')


def _kartu_dari_db(akun_id: str, siswa_id: int, kini: str) -> str:
    with jadwal_store.buka(admin_store.BAWAAN) as kon:
        sesi = baca.sesi_berikutnya_murid(kon, akun_id, siswa_id, kini)
    if sesi is None:
        return ""
    return kartu_html(sesi, _nama_guru(sesi["guru_id"]))


def kartu_beranda_untuk(akun_id, siswa_id, *, sekarang=None) -> str:
    """Kartu "Sesi berikutnya" untuk beranda anak; "" (tanpa kartu) bila sakelar mati, akun tidak ada, atau galat baca."""
    if akun_id is None or not paket_belajar_gate.aktif():
        return ""
    kini = pesanan_alur.waktu_sekarang() if sekarang is None else sekarang
    try:
        return _kartu_dari_db(akun_id, siswa_id, kini)
    except GALAT_BACA as galat:
        _log.warning("kartu sesi anak dilewati: %s", type(galat).__name__)
        return ""
