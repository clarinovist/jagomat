"""Aturan murni tugas guru: tanpa I/O berkas, tanpa DB. Gerbang rilis, validasi tenggat, dan daftar topik tugas.

Tenggat berupa tanggal `YYYY-MM-DD` menurut kalender WIB. Pemanggil yang memberi `hari_ini` (tanggal WIB), karena
modul ini tidak membaca jam. Topik yang boleh ditugaskan adalah topik yang boleh dibuat sesinya
(`question_context.pastikan_materi_dibuka`), tanpa paket sintetis `campuran`.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import List, Optional, Tuple

import guru_pertemuan_aturan as pertemuan
import question_context
import topics

# Gerbang rilis tugas guru. MATI = rute tugas tidak ada (404 identik). Dinyalakan di commit rilis; tes yang butuh
# keadaan aktif menyalakannya lewat monkeypatch.
GURU_TUGAS_AKTIF = False

BATAS_TUGAS_AKTIF = 5
JENDELA_DUPLIKAT_DETIK = 60
TENGGAT_MAKS_HARI = 60

_POLA_TANGGAL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


# --- gerbang ----------------------------------------------------------------------------

def guru_tugas_aktif() -> bool:
    """Gerbang rilis. Konstanta dibaca saat dipanggil, bukan saat impor, supaya monkeypatch di tes berlaku."""
    return GURU_TUGAS_AKTIF is True


# --- tenggat ----------------------------------------------------------------------------

def _periksa_hari_ini(hari_ini) -> None:
    """`date` murni. `datetime` ditolak: perbandingannya dengan `date` akan melempar TypeError."""
    if type(hari_ini) is not date:
        raise ValueError("Tanggal hari ini harus berupa date.")


def _ke_tanggal(teks: str) -> date:
    """Tanggal dari `YYYY-MM-DD` ASCII yang ada di kalender. Selain itu ValueError tanpa menggemakan nilainya."""
    if _POLA_TANGGAL.fullmatch(teks) is None:
        raise ValueError("Tenggat harus format YYYY-MM-DD.")
    try:
        return date.fromisoformat(teks)
    except ValueError:
        raise ValueError("Tanggal tenggat tidak ada di kalender.") from None


def _periksa_jendela_tenggat(tanggal: date, hari_ini: date) -> None:
    """Batas bawah dan batas atas sama-sama inklusif: hari ini dan hari ini + TENGGAT_MAKS_HARI boleh."""
    if tanggal < hari_ini:
        raise ValueError("Tenggat tidak boleh sebelum hari ini.")
    if tanggal > hari_ini + timedelta(days=TENGGAT_MAKS_HARI):
        raise ValueError("Tenggat terlalu jauh ke depan.")


def baca_tenggat(teks, hari_ini: date) -> Optional[str]:
    """Tenggat dari form. Kosong atau spasi saja menjadi None; selain itu harus `YYYY-MM-DD` dalam jendela hari ini.

    Spasi di sekitar tanggal tidak dipangkas: masukan form tanggal sudah bersih, dan format yang tidak tepat ditolak.
    """
    _periksa_hari_ini(hari_ini)
    if teks is None:
        return None
    if type(teks) is not str:
        raise ValueError("Tenggat harus berupa teks.")
    if teks.strip() == "":
        return None
    tanggal = _ke_tanggal(teks)
    _periksa_jendela_tenggat(tanggal, hari_ini)
    return teks


TENGGAT_TANPA = "tanpa"
TENGGAT_BERJALAN = "berjalan"
TENGGAT_LEWAT = "lewat"


def status_tenggat(tenggat: Optional[str], hari_ini: date) -> str:
    """Status tenggat untuk label saja (keputusan Pemilik T4: tidak mengunci sesi).

    Tanpa tenggat -> `tanpa`. Hari tenggat itu sendiri masih `berjalan`; `lewat` baru mulai hari berikutnya.
    `tenggat` yang bukan None harus bentuk sah (dari penyimpanan); bentuk rusak -> ValueError.
    """
    _periksa_hari_ini(hari_ini)
    if tenggat is None:
        return TENGGAT_TANPA
    if type(tenggat) is not str:
        raise ValueError("Tenggat harus berupa teks.")
    return TENGGAT_LEWAT if _ke_tanggal(tenggat) < hari_ini else TENGGAT_BERJALAN


def tenggat_bentuk_sah(nilai) -> bool:
    """None, atau tanggal `YYYY-MM-DD` yang ada di kalender. Jendela hari ini tidak diperiksa di sini (lihat baca_tenggat)."""
    if nilai is None:
        return True
    if type(nilai) is not str:
        return False
    try:
        _ke_tanggal(nilai)
    except ValueError:
        return False
    return True


# --- topik ------------------------------------------------------------------------------

def _sesi_bisa_dibuat(id_topik: str) -> bool:
    """False bila palang pembuat sesi menolak topik ini (materi belum dibuka). Galat lain tidak ditangkap di sini."""
    try:
        question_context.pastikan_materi_dibuka([id_topik])
    except ValueError:
        return False
    return True


def _topik_bisa_ditugaskan() -> List[str]:
    """Id topik yang boleh ditugaskan, urut id. Env materi yang tidak sah melempar ValueError, tidak menjadi daftar kosong diam-diam."""
    question_context.materi_dasar_aktif()
    return [
        id_topik
        for id_topik in topics.daftar_topik()
        if id_topik != pertemuan.TOPIK_SINTETIS and _sesi_bisa_dibuat(id_topik)
    ]


def daftar_topik_tugas() -> List[Tuple[str, str]]:
    """Pasangan (id, label) topik yang boleh ditugaskan. Dihitung ulang tiap panggilan karena palang membaca env."""
    return [(id_topik, pertemuan.label_topik(id_topik)) for id_topik in _topik_bisa_ditugaskan()]


def topik_tugas_sah(nilai) -> bool:
    return type(nilai) is str and nilai in _topik_bisa_ditugaskan()
