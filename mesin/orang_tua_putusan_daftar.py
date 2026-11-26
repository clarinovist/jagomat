"""Daftar permintaan guru yang MENUNGGU untuk satu anak, untuk kartu orang tua (Fase 3b-3). Baca-saja.

Anak diidentifikasi HANYA lewat `akun_id` + `siswa_id` dari sesi murid (dikirim pemanggil). Tiap baris memuat nama
login guru (dari auth, tanpa akun_id), nama kelompok dan tanggal pertemuan pertama (dari admin-control, mode baca),
serta waktu pengajuan dan batas berlaku. Tidak memuat kode, hash, kelompok_id, atau id akun/anak.

Galat baca data kelompok hanya mengosongkan detail kelompok di baris itu (bukan galat halaman). Galat baca tautan
atau auth dibiarkan naik ke pemanggil, yang menampilkan bagian "belum bisa ditampilkan".
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Dict, List, Optional, Tuple

import admin_store
import admin_store_core
import auth
import guru_tautan_aturan as aturan
import guru_tautan_dasar as dasar
import jadwal_store as js

_log = logging.getLogger(__name__)
PERAN_GURU = "guru"
PLACEHOLDER_GURU = "Guru"
PLACEHOLDER_KELOMPOK = "kelompok Mini"
GALAT_KELOMPOK = (admin_store_core.StoreBelumSiap, sqlite3.Error, ValueError, OSError)
_SQL_NAMA_KELOMPOK = "SELECT nama FROM jadwal_kelompok WHERE id=?"
_SQL_MULAI_KELOMPOK = "SELECT MIN(mulai) FROM jadwal_pertemuan WHERE kelompok_id=? AND dibatalkan=0"


def _nama_guru(guru_id: str) -> Optional[str]:
    """Nama login guru aktif (peran guru, tidak dinonaktifkan) atau None. Elemen auth yang rusak dilewati."""
    for akun in auth.muat_akun():
        if not isinstance(akun, dict):
            continue
        if akun.get("id_akun") == guru_id and akun.get("peran") == PERAN_GURU and not akun.get("dinonaktifkan"):
            return akun.get("pengguna")
    return None


def _detail_kelompok(kelompok_id: str) -> Tuple[Optional[str], Optional[str]]:
    """(nama, mulai) kelompok dari admin-control, atau (None, None) bila tidak terbaca."""
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            nama = kon.execute(_SQL_NAMA_KELOMPOK, (kelompok_id,)).fetchone()
            mulai = kon.execute(_SQL_MULAI_KELOMPOK, (kelompok_id,)).fetchone()
    except GALAT_KELOMPOK as galat:
        _log.warning("detail kelompok untuk kartu tidak terbaca: %s", type(galat).__name__)
        return None, None
    return (None if nama is None else nama[0]), (None if mulai is None else mulai[0])


def _baris(bentuk: Dict[str, object]) -> Dict[str, object]:
    nama_kelompok, mulai = _detail_kelompok(bentuk["kelompok_id"])
    return {
        "id": bentuk["id"],
        "guru": _nama_guru(bentuk["guru_id"]) or PLACEHOLDER_GURU,
        "kelompok": nama_kelompok or PLACEHOLDER_KELOMPOK,
        "mulai": mulai,
        "dibuat": bentuk["dibuat"],
        "kedaluwarsa": bentuk["kedaluwarsa"],
    }


def baris_menunggu(akun_id: str, siswa_id: int, kini: str) -> List[Dict[str, object]]:
    """Permintaan berstatus `menunggu` untuk anak ini, terbaru dulu. Tidak ada tulis; berkas tautan tak dibuat."""
    bentuk_anak = dasar.daftar_untuk_anak(akun_id, siswa_id, kini)
    return [_baris(b) for b in bentuk_anak if b["status"] == aturan.STATUS_MENUNGGU]
