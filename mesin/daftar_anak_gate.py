"""Gerbang pendaftaran akun anak: sakelar admin `DAFTAR_AKUN_ANAK` + lembaga antrean (env hanya konfigurasi).

Dua syarat HARUS terpenuhi agar `/daftar` membuat akun anak:
1. sakelar `DAFTAR_AKUN_ANAK` hidup (baris DB sakelar menang; env `DAFTAR_AKUN_ANAK=1` hanya fallback;
   bawaan mati, hanya nilai persis "1" menyalakan); dan
2. lembaga antrean terkonfigurasi: env `OSN_LEMBAGA_ANTREAN` = id lembaga (bilangan bulat kanonis positif,
   dibaca tiap panggilan) yang baris lembaganya ada. Nilai kosong/tak sah/tak ada baris = tidak terkonfigurasi.

Hasil `keadaan()`: `LAMA` (sakelar mati: alur akun guru persis seperti sebelumnya), `ANAK` (alur baru, membawa id
lembaga), atau `BELUM_SIAP` (sakelar hidup tetapi antrean belum siap: pendaftaran ditolak jujur, TIDAK jatuh ke
alur lama dan tidak menulis apa pun). Pemilik lembaga antrean = akun koordinator yang memegang anak pendaftar.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
import re
import sqlite3
from typing import Optional

import feature_switch

NAMA_SAKELAR = "DAFTAR_AKUN_ANAK"
ENV_LEMBAGA_ANTREAN = "OSN_LEMBAGA_ANTREAN"
LAMA = "lama"
ANAK = "anak"
BELUM_SIAP = "belum_siap"
PESAN_BELUM_DIBUKA = "Pendaftaran sementara belum dibuka."
_POLA_ID = re.compile(r"[1-9][0-9]{0,9}")


@dataclass(frozen=True)
class Keadaan:
    mode: str
    lembaga_id: Optional[int] = None


def dari_env() -> bool:
    """Nilai env saja: fallback sakelar dan nilai awal (seed) halaman admin."""
    return os.environ.get(NAMA_SAKELAR, "0").strip() == "1"


def aktif() -> bool:
    return feature_switch.aktif(NAMA_SAKELAR, dari_env)


def id_lembaga_antrean() -> Optional[int]:
    """Id lembaga antrean dari env, atau None bila kosong/tidak kanonis (fail-closed)."""
    nilai = os.environ.get(ENV_LEMBAGA_ANTREAN, "")
    if type(nilai) is not str or _POLA_ID.fullmatch(nilai) is None:
        return None
    return int(nilai)


def koordinator_antrean(kon, lembaga_id) -> Optional[str]:
    """Nama akun koordinator (pemilik lembaga) untuk id itu, atau None bila lembaga tidak ada.

    Memakai `lembaga_store.daftar_lembaga` (satu-satunya SQL lembaga); `kon` harus ber-row_factory Row.
    """
    import lembaga_store
    for baris, _anggota in lembaga_store.daftar_lembaga(kon):
        if int(baris["id"]) == lembaga_id:
            return baris["pemilik"]
    return None


def _lembaga_ada(path_db, lembaga_id: int) -> bool:
    import database
    try:
        with database.buka(path_db) as kon:
            return koordinator_antrean(kon, lembaga_id) is not None
    except sqlite3.Error:
        return False


def keadaan(path_db=None) -> Keadaan:
    """Mode pendaftaran saat ini; `path_db` bawaan = database.BAWAAN (dibaca saat dipanggil)."""
    if not aktif():
        return Keadaan(LAMA)
    lembaga_id = id_lembaga_antrean()
    if lembaga_id is None or not _lembaga_ada(path_db, lembaga_id):
        return Keadaan(BELUM_SIAP)
    return Keadaan(ANAK, lembaga_id)
