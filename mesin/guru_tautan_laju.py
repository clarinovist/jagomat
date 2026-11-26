"""Pembatas laju tautan kode anak guru di memori proses: hitung gagal per (nama, kunci) dalam jendela parameter.

Pola `laju_masuk`, dengan dua perbedaan: jendela dan batas dikirim pemanggil (bukan konstanta modul), dan plafon
kunci (`BATAS_KUNCI`) beserta riwayatnya sendiri, sehingga tidak berbagi state dengan login atau PIN. IP tidak
pernah disimpan ke disk. Aman dipakai beberapa thread lewat satu Lock.

Batas per-IP BUKAN satu-satunya pagar: batas gagal per guru di DB (`percobaan_gagal`, lihat `guru_tautan_dasar`)
tetap menahan. Penyerang yang memakai banyak IP dapat menggusur kunci IP lain lewat plafon `BATAS_KUNCI`; akibatnya
dibatasi oleh pagar per guru, bukan oleh modul ini.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, Tuple

BATAS_KUNCI = 4096

_GEMBOK = threading.Lock()
_RIWAYAT: Dict[Tuple[str, str], List[float]] = {}


def _kunci_baku(nama: str, kunci: str) -> Tuple[str, str]:
    """Nama tidak peka huruf besar/kecil dan spasi tepi, seperti login."""
    if type(nama) is not str or type(kunci) is not str:
        raise ValueError("Nama dan kunci harus teks.")
    return (nama.strip().lower(), kunci)


def _periksa_jendela(jendela: float) -> None:
    if type(jendela) not in (int, float) or jendela <= 0:
        raise ValueError("Jendela laju harus bilangan positif (detik).")


def _periksa_batas(batas: int) -> None:
    if type(batas) is not int or batas < 1:
        raise ValueError("Batas laju harus bilangan bulat minimal 1.")


def _waktu_kini(sekarang: Optional[float]) -> float:
    return time.time() if sekarang is None else float(sekarang)


def _pangkas(kunci: Tuple[str, str], kini: float, jendela: float) -> List[float]:
    """Buang waktu gagal di luar jendela. Pemanggil sudah memegang `_GEMBOK`."""
    segar = [t for t in _RIWAYAT.get(kunci, ()) if kini - t < jendela]
    if segar:
        _RIWAYAT[kunci] = segar
    else:
        _RIWAYAT.pop(kunci, None)
    return segar


def _jaga_plafon(kunci_baru: Tuple[str, str]) -> None:
    """Kembalikan jumlah kunci ke plafon dengan membuang kunci yang gagal terakhirnya paling tua.

    Kunci yang baru dicatat tidak pernah ikut dibuang. Pemanggil sudah memegang `_GEMBOK`.
    """
    kelebihan = len(_RIWAYAT) - BATAS_KUNCI
    for _ in range(max(kelebihan, 0)):
        kandidat = [kunci for kunci in _RIWAYAT if kunci != kunci_baru]
        if not kandidat:
            return
        del _RIWAYAT[min(kandidat, key=lambda kunci: _RIWAYAT[kunci][-1])]


def diblokir(nama: str, kunci: str, *, jendela: float, batas: int, sekarang: Optional[float] = None) -> bool:
    """True bila jumlah gagal untuk (nama, kunci) dalam jendela berjalan sudah mencapai batas."""
    _periksa_jendela(jendela)
    _periksa_batas(batas)
    kini = _waktu_kini(sekarang)
    baku = _kunci_baku(nama, kunci)
    with _GEMBOK:
        return len(_pangkas(baku, kini, jendela)) >= batas


def catat_gagal(nama: str, kunci: str, *, jendela: float, sekarang: Optional[float] = None) -> None:
    """Catat satu percobaan gagal, lalu jaga plafon kunci."""
    _periksa_jendela(jendela)
    kini = _waktu_kini(sekarang)
    baku = _kunci_baku(nama, kunci)
    with _GEMBOK:
        segar = _pangkas(baku, kini, jendela)
        _RIWAYAT[baku] = segar + [kini]
        _jaga_plafon(baku)


def _reset() -> None:
    """Kosongkan seluruh riwayat. Khusus tes: tes tidak boleh mewarisi riwayat tes lain."""
    with _GEMBOK:
        _RIWAYAT.clear()
