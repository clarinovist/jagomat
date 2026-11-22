"""Penugasan Mode Lomba per anak: Guru mengaktifkan, anak tanpa baris (atau `aktif=0`) tidak melihat Lomba.

Satu baris per anak di `lomba_penugasan`. `target_harian`, `tampil_hitung_mundur`, dan durasi per mode
(`durasi_latihan_detik`, `durasi_simulasi_detik`; 300-10800 detik = 5-180 menit) bernilai None bila mengikuti
nilai paket. `atur` mewajibkan semua nilai (tanpa bawaan) supaya pemanggil yang hanya mengubah satu hal harus
meneruskan nilai lama secara eksplisit, bukan menghapusnya tanpa sengaja. Modul ini satu-satunya pemilik SQL tabel itu dan tidak melakukan commit sendiri
(pemanggil memegang transaksi, seperti `contest_store`). Nilai divalidasi di Python sebelum menyentuh DB;
CHECK pada tabel tetap menjadi sabuk pengaman kedua.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import contest_paket as PK

MAKS_PANJANG_OLEH = 64
DURASI_MIN_DETIK = PK.DURASI_MIN_MENIT * PK.DETIK_PER_MENIT
DURASI_MAKS_DETIK = PK.DURASI_MAKS_MENIT * PK.DETIK_PER_MENIT
_KOLOM = ("siswa_id, paket_id, aktif, target_harian, tampil_hitung_mundur, diubah_epoch, diubah_oleh, "
          "durasi_latihan_detik, durasi_simulasi_detik")


@dataclass(frozen=True)
class Penugasan:
    siswa_id: int
    paket_id: str
    aktif: bool
    target_harian: Optional[int]
    tampil_hitung_mundur: Optional[bool]
    diubah_epoch: int
    diubah_oleh: str
    durasi_latihan_detik: Optional[int] = None
    durasi_simulasi_detik: Optional[int] = None


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
        diubah_epoch=baris["diubah_epoch"], diubah_oleh=baris["diubah_oleh"],
        durasi_latihan_detik=baris["durasi_latihan_detik"], durasi_simulasi_detik=baris["durasi_simulasi_detik"])


def _periksa_durasi(nama: str, detik: Optional[int]) -> None:
    if detik is None:
        return
    if (isinstance(detik, bool) or not isinstance(detik, int) or detik % PK.DETIK_PER_MENIT
            or not DURASI_MIN_DETIK <= detik <= DURASI_MAKS_DETIK):
        raise ValueError(f"{nama} harus kosong atau {PK.DURASI_MIN_MENIT}-{PK.DURASI_MAKS_MENIT} menit bulat")


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
         tampil_hitung_mundur: Optional[bool], durasi_latihan_detik: Optional[int],
         durasi_simulasi_detik: Optional[int], sekarang: int, oleh: str) -> Penugasan:
    """Simpan (upsert, satu pernyataan atomik) lalu kembalikan keadaan tersimpan. Paket = paket aktif kode."""
    _periksa(aktif, target_harian, tampil_hitung_mundur, sekarang, oleh)
    _periksa_durasi("durasi latihan", durasi_latihan_detik)
    _periksa_durasi("durasi simulasi", durasi_simulasi_detik)
    kon.execute(
        f"INSERT INTO lomba_penugasan({_KOLOM}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(siswa_id) DO UPDATE SET paket_id = excluded.paket_id, aktif = excluded.aktif, "
        "target_harian = excluded.target_harian, tampil_hitung_mundur = excluded.tampil_hitung_mundur, "
        "diubah_epoch = excluded.diubah_epoch, diubah_oleh = excluded.diubah_oleh, "
        "durasi_latihan_detik = excluded.durasi_latihan_detik, durasi_simulasi_detik = excluded.durasi_simulasi_detik",
        (siswa_id, PK.PAKET_AKTIF.id, int(aktif), target_harian,
         None if tampil_hitung_mundur is None else int(tampil_hitung_mundur), sekarang, oleh,
         durasi_latihan_detik, durasi_simulasi_detik))
    return ambil(kon, siswa_id)
