"""Aturan murni tautan kode anak guru: tanpa I/O, tanpa DB.

Kode anak 16 karakter Crockford base32 (80 bit) yang tampil `XXXX-XXXX-XXXX-XXXX`. Yang disimpan hanya hash SHA-256
dari bentuk kanonik kode. Waktu berupa string baku UTC naif `YYYY-MM-DDTHH:MM:SS`, sama dengan
`guru_pertemuan_aturan`. Semua batas waktu dan batas laju berupa konstanta bernama di sini.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

KEDALUWARSA = timedelta(days=7)
JEDA_TOLAK = timedelta(days=7)
GAGAL_PER_GURU = 5
JENDELA_GURU = timedelta(hours=1)
PERMINTAAN_PER_KODE = 10
JENDELA_KODE = timedelta(days=1)
GAGAL_PER_IP = 20
JENDELA_IP_DETIK = 3600
AKSI_PER_AKUN = 10
JENDELA_AKSI_DETIK = 3600
PANJANG_KODE = 16
PANJANG_BLOK_TAMPIL = 4
PANJANG_MENTAH_MAKS = 64
ALFABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_PEMISAH = frozenset("- \t\r\n")
_TERJEMAHAN = str.maketrans({"I": "1", "L": "1", "O": "0"})

STATUS_MENUNGGU = "menunggu"
STATUS_SETUJU = "setuju"
STATUS_TOLAK = "tolak"
STATUS_KEDALUWARSA = "kedaluwarsa"
STATUS_BATAL = "batal"
HASIL_SETUJU = "setuju"
HASIL_TOLAK = "tolak"
HASIL_SAH = (HASIL_SETUJU, HASIL_TOLAK)
PERAN_ORANG_TUA = "orang_tua"
PERAN_ADMIN = "admin"
PERAN_SAH = (PERAN_ORANG_TUA, PERAN_ADMIN)

FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_POLA_WAKTU = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")

# Gerbang fitur kode anak (syarat rilis L6). MATI = ketiga permukaan (guru, orang tua, admin) tidak ada: 404
# identik, tanpa efek, tanpa membuat `guru-tautan.db`. Hanya dinyalakan di commit rilis, SETELAH backup
# `guru-tautan.db` dan tool backup HOST terpasang. Tes menyalakannya lewat monkeypatch atau fixture.
KODE_ANAK_AKTIF = False


# --- kode -------------------------------------------------------------------------------

def buat_kode() -> str:
    """16 karakter acak dari `secrets` (80 bit), bentuk kanonik tanpa pemisah."""
    return "".join(secrets.choice(ALFABET) for _ in range(PANJANG_KODE))


def tampilkan(kode: str) -> str:
    """Bentuk tampil `XXXX-XXXX-XXXX-XXXX`. Masukan yang bukan kode kanonik ditolak."""
    if type(kode) is not str or normalkan(kode) != kode:
        raise ValueError("Kode tidak kanonik.")
    blok = [kode[i:i + PANJANG_BLOK_TAMPIL] for i in range(0, PANJANG_KODE, PANJANG_BLOK_TAMPIL)]
    return "-".join(blok)


def normalkan(kode: Any) -> Optional[str]:
    """Bentuk kanonik 16 karakter, atau None bila masukan bukan kode sah. Untuk masukan apa pun tidak pernah raise."""
    if type(kode) is not str:
        return None
    mentah = kode.strip()
    if len(mentah) > PANJANG_MENTAH_MAKS or not mentah.isascii():
        return None
    bersih = _buang_pemisah(mentah.upper()).translate(_TERJEMAHAN)
    if len(bersih) != PANJANG_KODE or any(ch not in ALFABET for ch in bersih):
        return None
    return bersih


def _buang_pemisah(teks: str) -> str:
    return "".join(ch for ch in teks if ch not in _PEMISAH)


def hash_kode(kode: Any) -> Optional[str]:
    """SHA-256 hex dari bentuk kanonik; None bila masukan bukan kode sah. Tidak pernah raise."""
    kanonik = normalkan(kode)
    if kanonik is None:
        return None
    return hashlib.sha256(kanonik.encode("ascii")).hexdigest()


# --- waktu ------------------------------------------------------------------------------

def _ke_datetime(baku: Any) -> datetime:
    """Waktu baku ke datetime naif. Format lain ditolak tanpa menggemakan nilainya."""
    if type(baku) is not str or _POLA_WAKTU.fullmatch(baku) is None:
        raise ValueError("Waktu harus format baku UTC YYYY-MM-DDTHH:MM:SS.")
    try:
        return datetime.strptime(baku, FORMAT_WAKTU)
    except ValueError:
        raise ValueError("Waktu tidak valid.") from None


def _ke_baku(waktu: datetime) -> str:
    return waktu.strftime(FORMAT_WAKTU)


def waktu_sah(nilai: Any) -> bool:
    try:
        _ke_datetime(nilai)
    except ValueError:
        return False
    return True


def hitung_kedaluwarsa(dibuat: str) -> str:
    """Batas kedaluwarsa permintaan: `dibuat` ditambah tepat tujuh hari."""
    return _ke_baku(_ke_datetime(dibuat) + KEDALUWARSA)


def waktu_mundur(waktu: str, durasi: timedelta) -> str:
    """`waktu` dikurangi `durasi`, dalam format baku."""
    return _ke_baku(_ke_datetime(waktu) - durasi)


def dalam_jeda_tolak(pada_tolak: str, kini: str) -> bool:
    """True bila `kini` belum mencapai tujuh hari sejak penolakan. Tepat di batas = jeda sudah habis."""
    return _ke_datetime(kini) < _ke_datetime(pada_tolak) + JEDA_TOLAK


# --- status dan batas -------------------------------------------------------------------

def status_permintaan(*, kedaluwarsa: str, hasil_putusan: Optional[str], kode_dicabut: bool, kini: str) -> str:
    """Status turunan. Urutan: putusan, lalu batal (kode dicabut/diganti), lalu kedaluwarsa (kini >= batas), lalu menunggu.

    `batal` mengalahkan `kedaluwarsa` secara retroaktif: kode yang dicabut SETELAH batas kedaluwarsa tampil batal,
    bukan kedaluwarsa. Ini status turunan saat dibaca, BUKAN fakta audit; jejak waktu asli ada di `kode_cabut`.
    """
    if hasil_putusan is not None and hasil_putusan not in HASIL_SAH:
        raise ValueError("Hasil putusan tidak sah.")
    if type(kode_dicabut) is not bool:
        raise ValueError("Penanda kode dicabut harus bool.")
    batas = _ke_datetime(kedaluwarsa)
    waktu_kini = _ke_datetime(kini)
    if hasil_putusan is not None:
        return hasil_putusan
    if kode_dicabut:
        return STATUS_BATAL
    if waktu_kini >= batas:
        return STATUS_KEDALUWARSA
    return STATUS_MENUNGGU


def guru_diblokir(jumlah_gagal: int) -> bool:
    return jumlah_gagal >= GAGAL_PER_GURU


def kode_penuh(jumlah_permintaan: int) -> bool:
    return jumlah_permintaan >= PERMINTAAN_PER_KODE


# --- gerbang -----------------------------------------------------------------------------

def kode_anak_aktif() -> bool:
    """Gerbang fitur kode anak. Konstanta dibaca saat dipanggil, bukan saat impor, supaya monkeypatch di tes berlaku."""
    return KODE_ANAK_AKTIF is True
