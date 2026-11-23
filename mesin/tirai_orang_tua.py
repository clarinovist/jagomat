"""Tirai halaman orang tua: status "terbuka" di memori proses, terikat sesi, akun, dan anak.

Pilihan penyimpanan: peta di memori proses (dikunci `threading.Lock`), BUKAN cookie dan BUKAN `sessions.py`.
Cookie bisa dipalsukan/diteruskan; `sessions.py` termasuk berkas kontrak rilis (PROBE_KONTRAK) sehingga menambah
field di sana mengubah sidik jari kontrak recovery. Konsekuensi memori: restart proses menutup semua tirai
(fail-closed, orang tua cukup memasukkan PIN lagi). Satu proses melayani semua permintaan.

Kunci = (sha256 token sesi, id_akun, siswa_id); token mentah tidak disimpan. Umur tetap 30 menit sejak PIN
benar (bukan menyegarkan diri). Logout menghapus entri sesi itu; token yang sudah mati juga tak bisa dipakai
lagi, sehingga entri sisa hanya makan memori sampai kedaluwarsa/dipangkas oleh plafon. PIN tirai bukan batas
keamanan data (keputusan pemilik 23 Nov 2026).
"""
from __future__ import annotations

import hashlib
import threading
import time

UMUR_TIRAI_DETIK = 30 * 60
BATAS_ENTRI = 4096  # plafon; lewat ini yang kedaluwarsa dibuang dulu, lalu yang paling cepat habis

_jam = time.time  # titik suntik tes
_KUNCI = threading.Lock()
_TERBUKA: dict = {}


def _sidik(token) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_sah(token) -> bool:
    return type(token) is str and token != ""


def _kunci(token, id_akun, siswa_id) -> tuple:
    return (_sidik(token), id_akun, siswa_id)


def _periksa_siswa(siswa_id) -> None:
    if type(siswa_id) is not int or siswa_id < 1:
        raise ValueError("siswa_id tidak sah")


def _kini(sekarang) -> float:
    return _jam() if sekarang is None else sekarang


def _pangkas(kini: float) -> None:
    """Jaga plafon; pemanggil memegang `_KUNCI`."""
    if len(_TERBUKA) <= BATAS_ENTRI:
        return
    for kunci in [k for k, habis in _TERBUKA.items() if habis <= kini]:
        del _TERBUKA[kunci]
    while len(_TERBUKA) > BATAS_ENTRI:
        del _TERBUKA[min(_TERBUKA, key=_TERBUKA.get)]


def buka(token, id_akun, siswa_id, sekarang=None) -> None:
    """Buka tirai anak ini untuk sesi ini sampai `UMUR_TIRAI_DETIK` ke depan."""
    if not _token_sah(token):
        raise ValueError("token sesi wajib")
    _periksa_siswa(siswa_id)
    kini = _kini(sekarang)
    with _KUNCI:
        _TERBUKA[_kunci(token, id_akun, siswa_id)] = kini + UMUR_TIRAI_DETIK
        _pangkas(kini)


def terbuka(token, id_akun, siswa_id, sekarang=None) -> bool:
    """True hanya bila sesi, akun, dan anak ini dibuka dan belum kedaluwarsa; selain itu tertutup."""
    if not _token_sah(token) or type(siswa_id) is not int:
        return False
    kini = _kini(sekarang)
    kunci = _kunci(token, id_akun, siswa_id)
    with _KUNCI:
        habis = _TERBUKA.get(kunci)
        if habis is None:
            return False
        if habis <= kini:
            del _TERBUKA[kunci]
            return False
        return True


def tutup(token, id_akun, siswa_id) -> None:
    if not _token_sah(token) or type(siswa_id) is not int:
        return
    with _KUNCI:
        _TERBUKA.pop(_kunci(token, id_akun, siswa_id), None)


def tutup_sesi(token) -> None:
    """Hapus semua entri milik sesi ini (dipanggil saat keluar)."""
    if not _token_sah(token):
        return
    sidik = _sidik(token)
    with _KUNCI:
        for kunci in [k for k in _TERBUKA if k[0] == sidik]:
            del _TERBUKA[kunci]


def _reset() -> None:  # khusus test
    with _KUNCI:
        _TERBUKA.clear()
