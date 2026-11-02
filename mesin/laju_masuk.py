"""Pembatas laju percobaan masuk: hitung gagal per (nama, IP) dalam 15 menit.

Dipisah dari ``sessions.py`` karena berkas itu termasuk berkas kontrak rilis
(`PROBE_KONTRAK` di ``scripts/deploy.py``): menambah lock atau pemangkasan di
sana mengubah sidik jari kontrak recovery tanpa perubahan format data. Logika
lama tetap berada di ``sessions`` sampai tidak ada pemanggil warisannya.

Plafon ``BATAS_KUNCI`` ada karena kunci tumbuh dari masukan anonim: satu POST
``/masuk`` dengan nama acak menambah satu kunci, jadi tanpa plafon penyerang
bisa menumbuhkan state tanpa batas. Saat plafon terlampaui, kunci kedaluwarsa
dibuang lebih dulu, lalu kunci dengan percobaan tertua — entri lain tetap
hidup supaya pemblokiran yang sedang berjalan tidak ikut hilang.

Resolusi IP tetap di ``ip_klien`` (di-re-export di sini agar pemanggil
pembatas laju mendapat kunci IP dari satu modul); logikanya tidak diduplikasi.
"""
from __future__ import annotations

import threading
import time

from ip_klien import ip_klien

BATAS_JENDELA = 15 * 60  # hitung gagal dalam 15 menit
BATAS_GAGAL = 5  # gagal ke-5 menutup keran
BATAS_KUNCI = 4096  # plafon jumlah kunci; lewat ini kunci tertua dibuang

__all__ = [
    "BATAS_GAGAL",
    "BATAS_JENDELA",
    "BATAS_KUNCI",
    "catat_berhasil",
    "catat_gagal",
    "ip_klien",
    "sedang_diblokir",
]

_KUNCI = threading.Lock()
_RIWAYAT: dict[tuple[str, str], list[float]] = {}


def _baku(nama: str, kunci_ip: str) -> tuple[str, str]:
    """Nama tidak peka huruf besar/kecil dan spasi tepi, seperti login."""
    return (nama.strip().lower(), kunci_ip)


def _pangkas(kunci: tuple[str, str], kini: float) -> list[float]:
    """Buang waktu gagal di luar jendela; pemanggil sudah memegang ``_KUNCI``."""
    lst = [t for t in _RIWAYAT.get(kunci, ()) if kini - t < BATAS_JENDELA]
    if lst:
        _RIWAYAT[kunci] = lst
    else:
        _RIWAYAT.pop(kunci, None)
    return lst


def _jaga_batas(kini: float) -> None:
    """Kembalikan jumlah kunci ke plafon; pemanggil sudah memegang ``_KUNCI``."""
    if len(_RIWAYAT) <= BATAS_KUNCI:
        return
    for kunci in [
        k for k, waktu in _RIWAYAT.items()
        if not waktu or kini - waktu[-1] >= BATAS_JENDELA
    ]:
        del _RIWAYAT[kunci]
    while len(_RIWAYAT) > BATAS_KUNCI:
        tertua = min(_RIWAYAT, key=lambda k: _RIWAYAT[k][-1])
        del _RIWAYAT[tertua]


def sedang_diblokir(nama: str, kunci_ip: str, sekarang: float | None = None) -> bool:
    """Benar bila gagal untuk (nama, IP) di jendela berjalan mencapai batas."""
    kini = time.time() if sekarang is None else sekarang
    kunci = _baku(nama, kunci_ip)
    with _KUNCI:
        return len(_pangkas(kunci, kini)) >= BATAS_GAGAL


def catat_gagal(nama: str, kunci_ip: str, sekarang: float | None = None) -> None:
    """Catat satu percobaan gagal, lalu jaga plafon kunci."""
    kini = time.time() if sekarang is None else sekarang
    kunci = _baku(nama, kunci_ip)
    with _KUNCI:
        lst = _pangkas(kunci, kini)
        lst.append(kini)
        _RIWAYAT[kunci] = lst
        _jaga_batas(kini)


def catat_berhasil(nama: str, kunci_ip: str) -> None:
    """Masuk yang berhasil mengosongkan riwayat gagal kunci itu."""
    kunci = _baku(nama, kunci_ip)
    with _KUNCI:
        _RIWAYAT.pop(kunci, None)


def _reset() -> None:  # khusus test
    """Kosongkan state; test tidak boleh mewarisi riwayat test lain."""
    with _KUNCI:
        _RIWAYAT.clear()
