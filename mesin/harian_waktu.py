"""Waktu Latihan Harian: hari kalender WIB (UTC+7 tetap) dari epoch detik. Murni; waktu selalu parameter."""
from __future__ import annotations

import datetime
from typing import Tuple

OFFSET_WIB_DETIK = 7 * 3600
DETIK_PER_HARI = 24 * 3600
FORMAT_KINI = "%Y-%m-%dT%H:%M:%S"
_NOL_UTC = datetime.datetime(1970, 1, 1)


def awal_hari_wib(epoch: int) -> int:
    """Epoch detik 00:00 WIB dari hari kalender WIB yang memuat `epoch`."""
    lokal = int(epoch) + OFFSET_WIB_DETIK
    return lokal - lokal % DETIK_PER_HARI - OFFSET_WIB_DETIK


def batas_hari_wib(epoch: int) -> Tuple[int, int]:
    """[awal, akhir) epoch untuk hari WIB yang memuat `epoch`."""
    awal = awal_hari_wib(epoch)
    return awal, awal + DETIK_PER_HARI


def tanggal_wib(epoch: int) -> str:
    """`YYYY-MM-DD` hari WIB yang memuat `epoch`."""
    return (_NOL_UTC + datetime.timedelta(seconds=int(epoch) + OFFSET_WIB_DETIK)).strftime("%Y-%m-%d")


def kini_baku(epoch: int) -> str:
    """Waktu UTC `%Y-%m-%dT%H:%M:%S` (format baku waktu repo) untuk argumen `kini` `akses_harian.akses`."""
    return (_NOL_UTC + datetime.timedelta(seconds=int(epoch))).strftime(FORMAT_KINI)


def tujuh_hari_hingga(epoch: int) -> Tuple[str, ...]:
    """Tujuh tanggal WIB berurutan, terlama dulu, berakhir pada hari WIB `epoch`."""
    return tuple(tanggal_wib(epoch - n * DETIK_PER_HARI) for n in range(6, -1, -1))


def pekan_wib(epoch: int) -> Tuple[str, ...]:
    """Tujuh tanggal WIB Senin sampai Minggu pada pekan yang memuat `epoch`."""
    hari_ini = _NOL_UTC + datetime.timedelta(seconds=int(epoch) + OFFSET_WIB_DETIK)
    senin = hari_ini - datetime.timedelta(days=hari_ini.weekday())
    return tuple((senin + datetime.timedelta(days=n)).strftime("%Y-%m-%d") for n in range(7))
