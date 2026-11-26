"""Kode anak untuk orang tua dan admin: buat, ganti, dan cabut di atas penyimpanan tautan (Fase 3b-3B; dipakai 3b-5).

Kode mentah dibuat di sini sekali (`aturan.buat_kode`), hanya hash-nya yang ditulis lewat `guru_tautan_dasar`, dan kode
mentah dikembalikan kepada pemanggil yang langsung menampilkannya. Kode mentah tidak pernah masuk log.

Aturan di lapisan ini (di atas pemeriksaan transaksi `guru_tautan_dasar`):
- `buat` dan `ganti` menolak anak yang tidak lagi ada (`anak.anak_masih_ada`, lapis F) sebelum menulis apa pun.
  `cabut` TIDAK memeriksanya: mencabut kode anak yang sudah dihapus tidak berbahaya dan membersihkan.
- Tabrakan UNIQUE pada `kode_hash` (termasuk dengan baris yang sudah dicabut) diulang dengan kode mentah baru,
  paling banyak `MAKS_UPAYA_TULIS` percobaan TOTAL (percobaan pertama ikut dihitung). Galat domain (`KodeSudahAda`,
  `KodeBasi`) dan galat lain (kunci, disk) TIDAK diulang.
"""

from __future__ import annotations

import sqlite3
from typing import Callable, Dict, Optional

import guru_tautan_aturan as aturan
import guru_tautan_anak as anak
import guru_tautan_dasar as dasar

MAKS_UPAYA_TULIS = 3
_PENANDA_TABRAKAN = "kode_anak.kode_hash"
_PESAN_ANAK = "Anak tidak lagi ada, jadi kode tidak bisa dibuat."
_PESAN_GAGAL = "Kode anak tidak bisa dibuat sekarang."


class AnakTakAda(dasar.GalatTautan):
    """Anak tidak lagi ada (akun murid atau baris siswa hilang/dianonimkan); buat dan ganti ditolak tanpa tulis."""


class KodeGagalDibuat(dasar.GalatTautan):
    """Penulisan kode baru gagal setelah `MAKS_UPAYA_TULIS` percobaan (tabrakan berulang atau galat tulis)."""


def _pastikan_anak(akun_id: str, siswa_id: int) -> None:
    if not anak.anak_masih_ada(akun_id, siswa_id):
        raise AnakTakAda(_PESAN_ANAK)


def _tabrakan_hash(galat: dasar.GalatTautan) -> bool:
    """True hanya untuk galat tulis generik yang disebabkan UNIQUE `kode_hash` (bukan galat domain, bukan kunci)."""
    sebab = galat.__cause__
    return (type(galat) is dasar.GalatTautan and isinstance(sebab, sqlite3.IntegrityError)
            and _PENANDA_TABRAKAN in str(sebab))


def _tulis_kode_baru(tulis: Callable[[str], object]) -> str:
    """Buat kode mentah, serahkan hash-nya ke `tulis`, dan kembalikan kode mentah bila berhasil.

    Hanya tabrakan hash yang diulang, dengan kode mentah baru. Galat lain dilempar apa adanya.
    """
    for _ in range(MAKS_UPAYA_TULIS):
        kode_mentah = aturan.buat_kode()
        try:
            tulis(aturan.hash_kode(kode_mentah))
        except dasar.GalatTautan as galat:
            if not _tabrakan_hash(galat):
                raise
            continue
        return kode_mentah
    raise KodeGagalDibuat(_PESAN_GAGAL)


def buat_kode_baru(akun_id: str, siswa_id: int, *, oleh: str, peran: str, pada: str, path=None) -> str:
    """Kode baru untuk anak; mengembalikan kode mentah SEKALI. Ditolak bila anak punya kode aktif (`KodeSudahAda`)."""
    _pastikan_anak(akun_id, siswa_id)
    return _tulis_kode_baru(lambda kode_hash: dasar.buat_kode(
        akun_id=akun_id, siswa_id=siswa_id, kode_hash=kode_hash, oleh=oleh, peran=peran, pada=pada, path=path))


def ganti_kode(akun_id: str, siswa_id: int, *, kode_id_diharapkan: int, oleh: str, peran: str, pada: str,
               path=None) -> str:
    """Cabut kode aktif (harus `kode_id_diharapkan`) dan buat kode baru dalam satu transaksi. Mengembalikan kode mentah.

    Kode lama yang basi ditolak (`KodeBasi`) tanpa tulis. Kegagalan tabrakan membatalkan pencabutan juga.
    """
    _pastikan_anak(akun_id, siswa_id)
    return _tulis_kode_baru(lambda kode_hash: dasar.ganti_kode(
        akun_id=akun_id, siswa_id=siswa_id, kode_id_aktif=kode_id_diharapkan, kode_hash_baru=kode_hash,
        oleh=oleh, peran=peran, pada=pada, path=path))


def cabut(akun_id: str, siswa_id: int, *, kode_id_diharapkan: int, oleh: str, peran: str, pada: str,
          path=None) -> None:
    """Cabut kode aktif anak. `kode_id_diharapkan` yang basi ditolak (`KodeBasi`) tanpa tulis."""
    dasar.cabut_kode(akun_id=akun_id, siswa_id=siswa_id, kode_id_aktif=kode_id_diharapkan,
                     oleh=oleh, peran=peran, pada=pada, path=path)


def kode_aktif(akun_id: str, siswa_id: int, *, path=None) -> Optional[Dict[str, object]]:
    """{"id", "dibuat", "peran"} kode aktif anak, atau None. Tanpa kode mentah, hash, dan id akun pembuat."""
    aktif = dasar.kode_aktif(akun_id, siswa_id, path=path)
    if aktif is None:
        return None
    return {"id": aktif["id"], "dibuat": aktif["dibuat"], "peran": aktif["peran"]}
