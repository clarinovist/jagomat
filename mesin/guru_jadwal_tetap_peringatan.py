"""Peringatan "di luar jam tetap guru" untuk halaman admin. Baca saja: tanpa tulis berkas, tanpa mengubah jadwal.

Jadwal tetap hanya ACUAN. Modul ini menandai pertemuan (kunci `luar_jam` pada dict sesi) dan slot Private yang
berada di luar jam tetap guru aktif. Tidak pernah menolak penyimpanan. Gerbang mati, guru tanpa jadwal aktif, dan
galat baca tidak menghasilkan tanda apa pun.
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional

import guru_jadwal_tetap_aturan as aturan
import guru_jadwal_tetap_dasar as dasar
import jadwal_dasar as jd

_log = logging.getLogger(__name__)

KUNCI_LUAR_JAM = "luar_jam"
# Durasi bawaan bila sesi tidak membawa kunci `menit`, dan durasi seluruh pertemuan slot Private (sesuai brief).
MENIT_PERTEMUAN_BAWAAN = 60


def blok_aktif(guru_akun) -> Optional[tuple]:
    """Blok jadwal tetap aktif guru sebagai tuple terurut. None bila tidak ada yang perlu diperingatkan.

    None: gerbang mati, guru kosong, guru belum punya jadwal aktif, atau galat baca (dicatat dengan nama tipe saja).
    Tuple kosong berarti jadwal aktif tanpa blok: semua pertemuan berada di luar jam.
    """
    if not aturan.guru_jadwal_tetap_aktif() or not guru_akun:
        return None
    try:
        aktif = dasar.aktif(guru_akun)
        if aktif is None:
            return None
        return aturan.urai_blok(aktif["blok"])
    except (dasar.GalatTetap, ValueError) as galat:
        _log.warning("jadwal tetap guru tidak bisa dibaca: %s", type(galat).__name__)
        return None


def _sesi_luar_jam(sesi: dict, blok: Optional[tuple]) -> bool:
    """Sesi dibatalkan tidak pernah ditandai; blok None berarti tidak ada peringatan."""
    if blok is None or bool(sesi.get("dibatalkan")):
        return False
    return aturan.luar_jam(blok, sesi["mulai"], sesi.get("menit", MENIT_PERTEMUAN_BAWAAN))


def tandai_dengan_blok(sesi: Iterable[dict], blok: Optional[tuple]) -> List[dict]:
    """Salinan dict sesi dengan kunci `luar_jam`. Tidak membaca jadwal; dipakai bila blok sudah dibaca sekali."""
    return [{**item, KUNCI_LUAR_JAM: _sesi_luar_jam(item, blok)} for item in sesi]


def tandai(sesi: Iterable[dict], guru_akun) -> List[dict]:
    """Tandai pertemuan milik guru. Membaca jadwal tetap aktif tepat sekali untuk seluruh daftar."""
    return tandai_dengan_blok(sesi, blok_aktif(guru_akun))


def slot_luar_jam_dengan_blok(blok: Optional[tuple], mulai_baku: str) -> bool:
    """True bila satu saja dari delapan pertemuan slot (dimulai `mulai_baku`) berada di luar blok."""
    if blok is None:
        return False
    return any(aturan.luar_jam(blok, waktu, MENIT_PERTEMUAN_BAWAAN)
               for waktu in jd.delapan_pertemuan(mulai_baku))


def slot_luar_jam(guru_akun, mulai_baku: str) -> bool:
    """True bila slot Private guru punya pertemuan di luar jam tetap aktif.

    False bila guru tanpa jadwal tetap aktif atau gerbang mati.
    """
    return slot_luar_jam_dengan_blok(blok_aktif(guru_akun), mulai_baku)
