"""Jatah pendaftaran guru mandiri: per IP dan global dalam jendela 15 menit, terpisah dari `laju_masuk` (butir QA #5).

Pembatas login (`laju_masuk`) punya plafon 4096 kunci yang dibagi dengan semua nama pengguna acak di /masuk, jadi banjir /masuk bisa
mendorong kunci pendaftaran keluar. Di sini tabel sendiri: satu entri per IP (waktu pengambilan jatah dalam jendela), ditambah
hitungan GLOBAL yang tidak bergantung IP supaya banyak IP berbeda pun tidak bisa membuat akun tanpa batas. Pengambilan jatah = cek
dan catat dalam satu langkah di bawah kunci (atomik per proses; server satu proses). Plafon kunci membuang yang kedaluwarsa dulu,
lalu yang paling lama tidak dipakai; plafon global tetap berlaku walau kunci per-IP terbuang. State di memori: hilang saat restart.
"""
from __future__ import annotations

import ipaddress
import threading
import time
from typing import Dict, List, Optional

JENDELA_DETIK = 15 * 60
BATAS_PER_IP = 5
BATAS_GLOBAL = 30
BATAS_KUNCI = 4096

_KUNCI = threading.Lock()
_PER_IP: Dict[str, List[float]] = {}
_GLOBAL: List[float] = []


def kunci_ip(teks: str) -> str:
    """Kunci per-IP: IPv6 dinormalkan ke prefiks /64 (satu pelanggan memegang seluruh blok /64), IPv4-mapped jadi IPv4."""
    try:
        alamat = ipaddress.ip_address(teks)
    except ValueError:
        return teks
    if alamat.version == 6:
        if alamat.ipv4_mapped is not None:
            return str(alamat.ipv4_mapped)
        return str(ipaddress.ip_network((alamat, 64), strict=False))
    return str(alamat)


def _pangkas(daftar: List[float], kini: float) -> List[float]:
    return [t for t in daftar if kini - t < JENDELA_DETIK]


def _jaga_plafon(kini: float) -> None:
    if len(_PER_IP) <= BATAS_KUNCI:
        return
    for kunci in [k for k, waktu in _PER_IP.items() if not _pangkas(waktu, kini)]:
        del _PER_IP[kunci]
    while len(_PER_IP) > BATAS_KUNCI:
        del _PER_IP[min(_PER_IP, key=lambda k: _PER_IP[k][-1])]


def ambil(kunci_ip_teks: str, sekarang: Optional[float] = None) -> bool:
    """Ambil satu jatah untuk IP ini; False bila jatah IP atau jatah global jendela ini habis."""
    kini = time.time() if sekarang is None else sekarang
    kunci_ip_ = kunci_ip(kunci_ip_teks)
    with _KUNCI:
        global _GLOBAL
        _GLOBAL = _pangkas(_GLOBAL, kini)
        milik = _pangkas(_PER_IP.get(kunci_ip_, []), kini)
        if len(_GLOBAL) >= BATAS_GLOBAL or len(milik) >= BATAS_PER_IP:
            if milik:
                _PER_IP[kunci_ip_] = milik
            else:
                _PER_IP.pop(kunci_ip_, None)
            return False
        milik.append(kini)
        _PER_IP[kunci_ip_] = milik
        _GLOBAL.append(kini)
        _jaga_plafon(kini)
        return True


def _jumlah_kunci() -> int:  # khusus test
    with _KUNCI:
        return len(_PER_IP)


def _reset() -> None:  # khusus test
    global _GLOBAL
    with _KUNCI:
        _PER_IP.clear()
        _GLOBAL = []
