"""Rute HTTP guru/admin untuk riwayat Latihan Lomba satu anak (hanya GET, hanya-lihat).

Kontrak dengan `web.py`: `tangani_get(penangan, jalur)` dipanggil setelah `_lolos_sandi` dan sebelum
penangkap `/anak/...`; True bila jalur milik modul ini dan sudah dijawab, False bila bukan atau gerbang mati
(sehingga jawabannya identik dengan jalur `/anak/...` lain yang tidak dikenal).

Rute: ``/anak/<siswa_id>/lomba`` (progress) dan ``/anak/<siswa_id>/lomba/<sesi_id>`` (detail sesi selesai).
Id hanya angka ASCII 1-12 digit. Anak tidak ada, bukan milik pemanggil (`_bisa_lihat_siswa`), sesi bukan
milik anak itu, sesi masih berjalan, dan id tidak sah semuanya dijawab 404 yang sama dengan
`parent_report_http` (tubuh dan header identik). Satu-satunya tulisan DB adalah penutupan malas sesi yang
batas waktunya sudah lewat (lewat `contest_results`), yang juga terjadi saat anak membuka halamannya.
"""
from __future__ import annotations

import re
import time
from typing import Optional, Tuple

import contest_gate
import contest_guru_pages as H
import contest_results as R
import contest_store as K
import database
from support_pages import halaman_pesan

MAKS_DIGIT_ID = 12
_POLA_RUTE = re.compile(r"/anak/([^/]+)/lomba(?:/([^/]+))?")
_POLA_ID = re.compile(rf"[0-9]{{1,{MAKS_DIGIT_ID}}}")


class _TidakAda(Exception):
    """Rute dikenal tetapi sasarannya tidak boleh dilihat; dijawab 404 yang sama untuk semua sebabnya."""


def _sekarang() -> int:
    return int(time.time())


def _kenali(jalur: str) -> Optional[Tuple[str, Optional[str]]]:
    cocok = _POLA_RUTE.fullmatch(jalur)
    return None if cocok is None else (cocok.group(1), cocok.group(2))


def _angka_id(mentah: str) -> int:
    if _POLA_ID.fullmatch(mentah) is None:
        raise _TidakAda(mentah)
    return int(mentah)


def _kirim_tidak_ada(penangan) -> None:
    penangan._kirim(halaman_pesan("404", "<h1>Halaman tidak ada</h1>"), 404)


def tangani_get(penangan, jalur: str) -> bool:
    """GET ``/anak/<id>/lomba[/<sesi_id>]``; False bila bukan milik modul atau gerbang mati."""
    rute = _kenali(jalur)
    if rute is None or not contest_gate.aktif():
        return False
    try:
        isi = _bangun(penangan, *rute)
    except (_TidakAda, K.SesiTidakDitemukan, K.SesiBerjalan):
        _kirim_tidak_ada(penangan)
        return True
    penangan._kirim_tautan(isi)
    return True


def _bangun(penangan, siswa_mentah: str, sesi_mentah: Optional[str]) -> bytes:
    siswa_id = _angka_id(siswa_mentah)
    sesi_id = None if sesi_mentah is None else _angka_id(sesi_mentah)
    ident = penangan._identitas()
    with database.buka() as kon:
        siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (siswa_id,)).fetchone()
        if siswa is None or not penangan._bisa_lihat_siswa(kon, siswa_id):
            raise _TidakAda(siswa_id)
        if sesi_id is None:
            return _progres(kon, siswa, ident)
        return H.halaman_detail(siswa, R.hasil_rinci(kon, siswa_id, sesi_id, _sekarang()), ident)


def _progres(kon, siswa, ident) -> bytes:
    sekarang = _sekarang()
    siswa_id = int(siswa["id"])
    return H.halaman_progres(
        siswa, R.progres(kon, siswa_id, sekarang), R.jenis_sering_salah(kon, siswa_id, sekarang), ident)
