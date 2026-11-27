"""Aturan murni pola Private (2 hari + 1 jam, disetujui tim): isian, tanggal 8 pertemuan, dan tanggal mulai default.

Tanpa DB/HTTP. Hari: 0=Senin..5=Sabtu (Minggu tidak dibuka). Jam: WIB dari `dsr.JAM_BOLEH`. Pertemuan bergantian dua
hari pola, urut kalender, dengan offset dari pertemuan pertama 0, g, 7, 7+g, 14, 14+g, 21, 21+g (g = jarak ke hari
kedua dalam pekan). Sengaja TIDAK memakai `jd.delapan_pertemuan`: offset Mini dan Private lama tidak boleh berubah.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Mapping, Optional, Sequence, Tuple

import jadwal_dasar as jd
import jadwal_private_dasar as dsr
import paket_belajar_katalog as katalog

NAMA_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
JUMLAH_PERTEMUAN = katalog.ambil(dsr.PAKET).pertemuan
MAKS_CARI_HARI = 14
PESAN_POLA = "Pilih dua hari yang berbeda (Senin sampai Sabtu) dan satu jam dari daftar."
PESAN_TANGGAL_POLA = "Tanggal mulai harus jatuh pada salah satu hari pilihan."
KUNCI_JAM_FORM = "jam"
AWALAN_HARI_FORM = "hari_"
NILAI_DICENTANG = "1"
_KUNCI_HARI_FORM = {"%s%d" % (AWALAN_HARI_FORM, hari): hari for hari in sorted(dsr.HARI_BOLEH)}


@dataclass(frozen=True)
class Pola:
    """Satu baris `private_pola_pengajuan`. Tanpa nama anak, orang tua, atau guru."""

    id: int
    order_id: str
    hari_a: int
    hari_b: int
    jam: str
    status: str
    dibuat: str


def periksa_pola(hari: Sequence, jam) -> Tuple[int, int, str]:
    """Dua hari berbeda dari Senin..Sabtu (urut naik) dan jam dari daftar. Selain itu JadwalTidakSah tanpa gema isian."""
    if type(hari) not in (list, tuple) or len(hari) != 2:
        raise jd.JadwalTidakSah(PESAN_POLA)
    if any(type(nilai) is not int or nilai not in dsr.HARI_BOLEH for nilai in hari) or len(set(hari)) != 2:
        raise jd.JadwalTidakSah(PESAN_POLA)
    if type(jam) is not str or jam not in dsr.JAM_BOLEH:
        raise jd.JadwalTidakSah(PESAN_POLA)
    hari_a, hari_b = sorted(hari)
    return hari_a, hari_b, jam


def hari_dan_jam_dari_form(isian: Mapping[str, str]) -> Tuple[List[int], Optional[str]]:
    """Isian form pola tanpa token: `hari_N=1` per hari yang dicentang (N = 0..5) dan `jam`. Kunci lain = tidak sah."""
    hari: List[int] = []
    for kunci, nilai in isian.items():
        if kunci == KUNCI_JAM_FORM:
            continue
        if kunci not in _KUNCI_HARI_FORM or nilai != NILAI_DICENTANG:
            raise jd.JadwalTidakSah(PESAN_POLA)
        hari.append(_KUNCI_HARI_FORM[kunci])
    return hari, isian.get(KUNCI_JAM_FORM)


def tanggal_pertemuan(mulai: date, hari_a: int, hari_b: int, jumlah: int = JUMLAH_PERTEMUAN) -> Tuple[date, ...]:
    """`jumlah` tanggal berurutan kalender mulai dari `mulai`, hanya pada hari_a/hari_b. `mulai` harus jatuh pada salah satunya."""
    if mulai.weekday() not in (hari_a, hari_b):
        raise jd.JadwalTidakSah(PESAN_TANGGAL_POLA)
    hasil: List[date] = []
    kandidat = mulai
    while len(hasil) < jumlah:
        if kandidat.weekday() in (hari_a, hari_b):
            hasil.append(kandidat)
        kandidat += timedelta(days=1)
    return tuple(hasil)


def rencana_pertemuan(tanggal: str, jam: str, hari_a: int, hari_b: int, kini_baku: str) -> Tuple[str, ...]:
    """Waktu baku UTC semua pertemuan pola, dari tanggal mulai WIB. Tanggal/jam tidak sah atau lewat = JadwalTidakSah."""
    mulai = jd.pertemuan_pertama(tanggal, jam, kini_baku)
    hari_mulai = jd.tanggal_wib(mulai)
    return tuple(jd.pertemuan_pertama(hari.isoformat(), jam, kini_baku)
                 for hari in tanggal_pertemuan(hari_mulai, hari_a, hari_b))


def tanggal_mulai_default(kini_baku: str, hari_a: int, hari_b: int, jam: str) -> str:
    """Tanggal WIB terdekat yang jatuh pada hari pola dan pertemuan pertamanya >= 24 jam dari sekarang."""
    batas = dsr.batas_pesan(kini_baku)
    hari_ini = jd.tanggal_wib(kini_baku)
    for tambah in range(MAKS_CARI_HARI):
        kandidat = hari_ini + timedelta(days=tambah)
        if kandidat.weekday() not in (hari_a, hari_b):
            continue
        if jd.pertemuan_pertama(kandidat.isoformat(), jam, kini_baku, izinkan_lampau=True) >= batas:
            return kandidat.isoformat()
    raise jd.JadwalTidakSah(PESAN_TANGGAL_POLA)


def teks_pola(hari_a: int, hari_b: int, jam: str) -> str:
    """'Selasa & Kamis pukul 16.00 WIB' (titik sebagai pemisah jam, sesuai copy aplikasi)."""
    return "%s & %s pukul %s WIB" % (NAMA_HARI[hari_a], NAMA_HARI[hari_b], jam.replace(":", "."))
