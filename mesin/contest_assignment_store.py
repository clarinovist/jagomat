"""Penugasan Mode Lomba per anak: Guru mengaktifkan, anak tanpa baris (atau `aktif=0`) tidak melihat Lomba.

Satu baris per anak di `lomba_penugasan`. `target_harian` dan `tampil_hitung_mundur` bernilai None bila
mengikuti nilai paket. Modul ini satu-satunya pemilik SQL tabel itu dan tidak melakukan commit sendiri
(pemanggil memegang transaksi, seperti `contest_store`). Nilai divalidasi di Python sebelum menyentuh DB;
CHECK pada tabel tetap menjadi sabuk pengaman kedua.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import contest_paket as PK

MAKS_PANJANG_OLEH = 64
_KOLOM = "siswa_id, paket_id, aktif, target_harian, tampil_hitung_mundur, diubah_epoch, diubah_oleh"


@dataclass(frozen=True)
class Penugasan:
    siswa_id: int
    paket_id: str
    aktif: bool
    target_harian: Optional[int]
    tampil_hitung_mundur: Optional[bool]
    diubah_epoch: int
    diubah_oleh: str


def _bool_atau_none(nilai: Optional[int]) -> Optional[bool]:
    return None if nilai is None else bool(nilai)


def ambil(kon, siswa_id: int) -> Optional[Penugasan]:
    """Penugasan anak, atau None bila Guru belum pernah mengaturnya."""
    baris = kon.execute(f"SELECT {_KOLOM} FROM lomba_penugasan WHERE siswa_id = ?", (siswa_id,)).fetchone()
    if baris is None:
        return None
    return Penugasan(
        siswa_id=baris["siswa_id"], paket_id=baris["paket_id"], aktif=bool(baris["aktif"]),
        target_harian=baris["target_harian"],
        tampil_hitung_mundur=_bool_atau_none(baris["tampil_hitung_mundur"]),
        diubah_epoch=baris["diubah_epoch"], diubah_oleh=baris["diubah_oleh"])


def _periksa(aktif, target_harian, tampil_hitung_mundur, sekarang, oleh) -> None:
    if not isinstance(aktif, bool):
        raise ValueError("aktif harus True atau False")
    if target_harian is not None and (
            isinstance(target_harian, bool) or not isinstance(target_harian, int)
            or not 0 <= target_harian <= PK.MAKS_TARGET_HARIAN):
        raise ValueError(f"target harian harus kosong atau 0 sampai {PK.MAKS_TARGET_HARIAN}")
    if tampil_hitung_mundur is not None and not isinstance(tampil_hitung_mundur, bool):
        raise ValueError("hitung mundur harus kosong, True, atau False")
    if isinstance(sekarang, bool) or not isinstance(sekarang, int):
        raise ValueError("waktu harus bilangan bulat epoch")
    if not isinstance(oleh, str) or len(oleh) > MAKS_PANJANG_OLEH:
        raise ValueError(f"pengubah harus teks paling panjang {MAKS_PANJANG_OLEH} karakter")


def atur(kon, siswa_id: int, *, aktif: bool, target_harian: Optional[int],
         tampil_hitung_mundur: Optional[bool], sekarang: int, oleh: str) -> Penugasan:
    """Simpan (upsert, satu pernyataan atomik) lalu kembalikan keadaan tersimpan. Paket = paket aktif kode."""
    _periksa(aktif, target_harian, tampil_hitung_mundur, sekarang, oleh)
    kon.execute(
        f"INSERT INTO lomba_penugasan({_KOLOM}) VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(siswa_id) DO UPDATE SET paket_id = excluded.paket_id, aktif = excluded.aktif, "
        "target_harian = excluded.target_harian, tampil_hitung_mundur = excluded.tampil_hitung_mundur, "
        "diubah_epoch = excluded.diubah_epoch, diubah_oleh = excluded.diubah_oleh",
        (siswa_id, PK.PAKET_AKTIF.id, int(aktif), target_harian,
         None if tampil_hitung_mundur is None else int(tampil_hitung_mundur), sekarang, oleh))
    return ambil(kon, siswa_id)
