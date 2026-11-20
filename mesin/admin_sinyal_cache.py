"""Cache proses untuk penanda sidebar admin (`SinyalNav`), berlaku untuk semua halaman admin.

`admin_http.sinyal_nav()` dipanggil di setiap halaman admin dan menjalankan antrean penuh; terukur
sekitar 7 ms per halaman pada 300 siswa, 100 akun, 20 order, dan 5 transfer menunggu (belum termasuk
membaca berkas akun). Nilainya hanya angka agregat yang sama untuk semua admin, jadi satu cache global
cukup. Dua pengaman menjaga angka tetap segar:

- TTL pendek (``TTL_DETIK``) membatasi umur data yang berubah di luar POST admin (mis. pelanggan
  mengunggah bukti transfer).
- ``kosongkan()`` dipanggil setiap POST admin diproses, sehingga badge langsung segar setelah admin
  bertindak. Penghitung generasi mencegah hasil hitungan yang dimulai SEBELUM kosongkan() tersimpan
  sesudahnya.

Galat (nilai ``None``) tidak pernah disimpan.
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

TTL_DETIK = 15.0

_kunci = threading.Lock()
_isi = None  # (nilai, kedaluwarsa_monotonic) atau None
_generasi = 0


def generasi() -> int:
    """Penanda versi cache; tangkap sebelum menghitung, berikan ke ``simpan``."""
    with _kunci:
        return _generasi


def kosongkan() -> None:
    global _isi, _generasi
    with _kunci:
        _isi = None
        _generasi += 1


def simpan(nilai, generasi_awal: int, *, jam: Callable[[], float] = time.monotonic) -> None:
    """Simpan ``nilai`` hanya bila bukan None dan tidak ada kosongkan() sejak ``generasi_awal``."""
    global _isi
    if nilai is None:
        return
    with _kunci:
        if generasi_awal == _generasi:
            _isi = (nilai, jam() + TTL_DETIK)


def ambil(hitung: Callable[[], Optional[object]], *, jam: Callable[[], float] = time.monotonic):
    """Nilai cache bila masih berlaku, selain itu ``hitung()`` (di luar kunci) lalu simpan."""
    with _kunci:
        if _isi is not None and jam() < _isi[1]:
            return _isi[0]
        awal = _generasi
    nilai = hitung()
    simpan(nilai, awal, jam=jam)
    return nilai
