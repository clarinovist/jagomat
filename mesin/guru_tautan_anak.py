"""Pemeriksaan "anak masih ada" untuk tautan kode anak guru (aturan F, keputusan Pemilik 26 Nov 2026).

Anak dianggap masih ada bila dua lapis lolos:
1. Akun murid di `auth` dengan id_akun pemilik order, peran murid, `siswa_id` yang sama dengan anak, dan tidak
   dinonaktifkan (syarat sama dengan `auth.autentikasi` ditambah penanda nonaktif admin).
2. Baris `siswa` di latihan.db belum dianonimkan (nama tidak berawalan `Dihapus-`).

Gagal TERTUTUP: galat baca auth, berkas korup, atau galat tak terduga menghasilkan False, tidak pernah raise.
Modul ini hanya membaca; tidak membuat berkas dan tidak menulis apa pun.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Optional

import auth
import database
import guru_status

_log = logging.getLogger(__name__)

PERAN_MURID = "murid"
AWALAN_DIHAPUS = "Dihapus-"
ANAK_ADA = "ada"
ANAK_TIDAK_ADA = "tidak_ada"
ANAK_TIDAK_DIKETAHUI = "tidak_diketahui"


def _baca_akun(path_auth: Optional[Path]) -> list:
    """Seluruh akun dari berkas auth. Titik sambung tes untuk meniru auth yang tak terbaca."""
    return auth.muat_akun(path_auth)


def _akun_murid_aktif(akun: dict, akun_id, siswa_id) -> bool:
    return (
        akun.get("id_akun") == akun_id
        and akun.get("peran") == PERAN_MURID
        and akun.get("siswa_id") == siswa_id
        and akun.get("dinonaktifkan") is not True
        and not guru_status.nonaktif_admin(akun)
    )


def akun_murid_aktif(akun_id, siswa_id, *, path_auth: Optional[Path] = None) -> Optional[dict]:
    """Akun murid aktif milik anak itu, atau None. Galat baca naik ke pemanggil."""
    for akun in _baca_akun(path_auth):
        if _akun_murid_aktif(akun, akun_id, siswa_id):
            return akun
    return None


def nama_login(akun_id, *, path_auth: Optional[Path] = None) -> Optional[str]:
    """Nama login akun murid dengan id itu, atau None bila tidak ada atau auth tak terbaca. Hanya dibaca."""
    try:
        for akun in _baca_akun(path_auth):
            if akun.get("id_akun") == akun_id and akun.get("peran") == PERAN_MURID:
                return akun.get("pengguna")
    except Exception as galat:  # auth tak terbaca: nama tidak diketahui, pemanggil menganggapnya gagal
        _log.warning("nama login tidak terbaca: %s", type(galat).__name__)
    return None


def _nama_belum_dianonimkan(siswa_id, path_belajar: Optional[Path]) -> bool:
    """Baris siswa ada dan namanya belum berawalan `Dihapus-`. Dibuka mode ro: tidak pernah membuat berkas."""
    tujuan = Path(path_belajar if path_belajar is not None else database.BAWAAN).resolve()
    with closing(sqlite3.connect(tujuan.as_uri() + "?mode=ro", uri=True)) as kon:
        baris = kon.execute("SELECT nama FROM siswa WHERE id=?", (siswa_id,)).fetchone()
    return baris is not None and not str(baris[0]).startswith(AWALAN_DIHAPUS)


def status_anak(akun_id, siswa_id, *, path_auth: Optional[Path] = None,
                path_belajar: Optional[Path] = None) -> str:
    """`ANAK_ADA`, `ANAK_TIDAK_ADA` (terbaca dan memang tidak aktif), atau `ANAK_TIDAK_DIKETAHUI` (galat baca).
    Tidak pernah raise. Pemanggil yang butuh keputusan aman memperlakukan selain `ANAK_ADA` sebagai tidak ada."""
    try:
        if akun_murid_aktif(akun_id, siswa_id, path_auth=path_auth) is None:
            return ANAK_TIDAK_ADA
        ada = _nama_belum_dianonimkan(siswa_id, path_belajar)
    except Exception as galat:  # galat baca: bukan "tidak ada"; pemanggil memutuskan tampilan, tetap tertutup
        _log.warning("kepastian anak tidak bisa dibaca: %s", type(galat).__name__)
        return ANAK_TIDAK_DIKETAHUI
    return ANAK_ADA if ada else ANAK_TIDAK_ADA


def anak_masih_ada(akun_id, siswa_id, *, path_auth: Optional[Path] = None,
                   path_belajar: Optional[Path] = None) -> bool:
    """True bila akun murid pemilik order masih aktif DAN baris siswa belum dianonimkan. Gagal tertutup."""
    return status_anak(akun_id, siswa_id, path_auth=path_auth, path_belajar=path_belajar) == ANAK_ADA
