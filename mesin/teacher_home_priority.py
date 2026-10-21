"""Kelompok dan urutan anak di beranda guru, murni turunan reducer siklus belajar.

Tidak ada penilaian baru: ``tindakan`` berasal dari ``rencana_berikutnya`` (atau
rencana pilot aktif, sama seperti kartu di profil anak). Modul ini hanya
menaruh tindakan itu ke tiga kelompok kerja guru dan mengurutkannya.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
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
    menunggu_sejak: Optional[date] = None


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


def _tanggal_sesi(kon, sesi_id: Optional[int]) -> Optional[date]:
    """Tanggal sesi yang menunggu konfirmasi; sama dengan dasar chip di profil anak."""
    if sesi_id is None:
        return None
    baris = kon.execute("SELECT tanggal FROM sesi WHERE id = ?", (sesi_id,)).fetchone()
    try:
        return date.fromisoformat(str(baris["tanggal"])[:10]) if baris else None
    except ValueError:
        return None


def _punya_sesi(kon, siswa_id: int) -> bool:
    return kon.execute(
        "SELECT 1 FROM sesi WHERE siswa_id = ? LIMIT 1", (siswa_id,)
    ).fetchone() is not None


def langkah_anak(kon, siswa) -> LangkahAnak:
    """Langkah berikutnya satu anak; kegagalan baca tidak merusak beranda."""
    siswa_id, nama = int(siswa["id"]), str(siswa["nama"])
    try:
        rencana = _rencana(kon, siswa_id)
        tindakan = rencana.tindakan
    except (ValueError, sqlite3.Error) as galat:
        _log.warning(
            "beranda: rencana siswa %s tidak terbaca (%s)", siswa_id, type(galat).__name__
        )
        return LangkahAnak(siswa_id, nama, None, SIAP, LABEL_TIDAK_TERBACA)
    label = TINDAKAN.get(tindakan, LABEL_BAWAAN)
    if tindakan == "pemetaan" and not _punya_sesi(kon, siswa_id):
        # Anak baru belum "melanjutkan" apa pun; tampilan saja, tindakan tetap reducer.
        label = TINDAKAN["pilih_variasi"]
    sejak = _tanggal_sesi(kon, rencana.sesi_id) if tindakan == "konfirmasi_hasil" else None
    return LangkahAnak(siswa_id, nama, tindakan, kelompok_untuk(tindakan), label, sejak)


def hari_menunggu(langkah: LangkahAnak, hari_ini: date) -> Optional[int]:
    """Hari sejak sesi menunggu konfirmasi; None bila langkahnya bukan menunggu hasil."""
    if langkah.menunggu_sejak is None:
        return None
    return (hari_ini - langkah.menunggu_sejak).days


def keterangan_langkah(langkah: LangkahAnak, hari_ini: date) -> str:
    """Label langkah, ditambah lama menunggu hanya bila sudah sehari atau lebih."""
    hari = hari_menunggu(langkah, hari_ini)
    if hari is not None and hari >= 1:
        return f"{langkah.label} · menunggu {hari} hari"
    return langkah.label


def urutkan(daftar) -> list[LangkahAnak]:
    """Kelompok kerja, lalu yang terlama menunggu, lalu nama (tanpa beda huruf)."""
    return sorted(daftar, key=lambda a: (
        a.kelompok, a.menunggu_sejak or date.max, a.nama.casefold(), a.siswa_id,
    ))
