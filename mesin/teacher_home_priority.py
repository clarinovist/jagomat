"""Kelompok dan urutan anak di beranda guru, murni turunan reducer siklus belajar.

Tidak ada penilaian baru: ``tindakan`` berasal dari ``rencana_berikutnya`` (atau
rencana pilot aktif, sama seperti kartu di profil anak). Modul ini hanya
menaruh tindakan itu ke tiga kelompok kerja guru dan mengurutkannya.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Optional

import database
import domain_clock
import skill_pilot_ui
from cycle_report import TINDAKAN
from learning_cycle import rencana_berikutnya

PERLU_TINDAKAN = 0
SIAP = 1
MENUNGGU = 2

JUDUL_KELOMPOK = {
    PERLU_TINDAKAN: "Perlu tindakan Anda",
    SIAP: "Siap dilanjutkan",
    MENUNGGU: "Menunggu",
}

_KELOMPOK_TINDAKAN = {
    "konfirmasi_hasil": PERLU_TINDAKAN,
    "eskalasi": PERLU_TINDAKAN,
    "lanjutkan_sesi": MENUNGGU,
    "tunggu_pemetaan": MENUNGGU,
    "tunggu_evaluasi": MENUNGGU,
    "tunggu_checkpoint": MENUNGGU,
}

LABEL_TIDAK_TERBACA = "Rencana belum dapat dibaca — buka profil"
LABEL_BAWAAN = "Tinjau rencana bersama"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LangkahAnak:
    siswa_id: int
    nama: str
    tindakan: Optional[str]
    kelompok: int
    label: str


def kelompok_untuk(tindakan: Optional[str]) -> int:
    """Tindakan tak dikenal jatuh ke SIAP: tampil, tidak disembunyikan."""
    return _KELOMPOK_TINDAKAN.get(tindakan, SIAP)


def _rencana(kon, siswa_id: int):
    """Sumber yang sama dengan kartu profil: pilot aktif, selain itu reducer utama."""
    _paket, daftar, aktif, warisan = skill_pilot_ui.keadaan(
        kon, siswa_id, domain_clock.hari_wib()
    )
    if daftar and warisan is None and aktif is not None:
        return aktif[2]
    bukti = database.muat_bukti_siklus(kon, siswa_id)
    return rencana_berikutnya(bukti, siswa_id)


def _punya_sesi(kon, siswa_id: int) -> bool:
    return kon.execute(
        "SELECT 1 FROM sesi WHERE siswa_id = ? LIMIT 1", (siswa_id,)
    ).fetchone() is not None


def langkah_anak(kon, siswa) -> LangkahAnak:
    """Langkah berikutnya satu anak; kegagalan baca tidak merusak beranda."""
    siswa_id, nama = int(siswa["id"]), str(siswa["nama"])
    try:
        tindakan = _rencana(kon, siswa_id).tindakan
    except (ValueError, sqlite3.Error) as galat:
        _log.warning(
            "beranda: rencana siswa %s tidak terbaca (%s)", siswa_id, type(galat).__name__
        )
        return LangkahAnak(siswa_id, nama, None, SIAP, LABEL_TIDAK_TERBACA)
    label = TINDAKAN.get(tindakan, LABEL_BAWAAN)
    if tindakan == "pemetaan" and not _punya_sesi(kon, siswa_id):
        # Anak baru belum "melanjutkan" apa pun; tampilan saja, tindakan tetap reducer.
        label = TINDAKAN["pilih_variasi"]
    return LangkahAnak(siswa_id, nama, tindakan, kelompok_untuk(tindakan), label)


def urutkan(daftar) -> list[LangkahAnak]:
    """Kelompok kerja dulu, lalu nama tanpa membedakan huruf besar-kecil."""
    return sorted(daftar, key=lambda a: (a.kelompok, a.nama.casefold(), a.siswa_id))
