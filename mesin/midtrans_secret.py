"""Berkas rahasia provider: dibaca hanya dari mount privat dengan kontrak ketat.

Tidak membuka jaringan, tidak membaca env, dan tidak mencatat nilai. Berkas wajib
regular file (bukan symlink), izin tanpa bit group/other, ukuran bounded, ASCII
printable, serta grammar dua baris eksplisit tanpa duplikat. Kunci sandbox ditolak
untuk lingkungan produksi; tidak ada fallback antar lingkungan.
"""

import os
import re
import stat as _stat

import midtrans_contract as m

BATAS_BERKAS = 4096
_BARIS = re.compile(r"(merchant|server_key)=([A-Za-z0-9_.-]{1,256})\Z")
_MERCHANT = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
_SANDBOX = re.compile(r"SB-")


class RahasiaTidakSah(RuntimeError):
    """Kontrak berkas dilanggar; pesan tidak memuat isi atau nilai rahasia."""


def baca_privat(path, batas=BATAS_BERKAS):
    """Baca teks ASCII bounded dari berkas privat; bentuk/izin/ukuran diperiksa ketat."""
    if type(batas) is not int or not 1 <= batas <= BATAS_BERKAS:
        raise RahasiaTidakSah("batas berkas privat tidak sah")
    try:
        fd = os.open(os.fspath(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except (OSError, TypeError, ValueError):
        raise RahasiaTidakSah("berkas privat tidak dapat dibuka") from None
    try:
        info = os.fstat(fd)
        if (not _stat.S_ISREG(info.st_mode) or info.st_mode & (0o077 | 0o7000)
                or info.st_uid != os.geteuid() or not 1 <= info.st_size <= batas):
            raise RahasiaTidakSah("bentuk berkas privat tidak sah")
        potongan, sisa = [], batas + 1
        while sisa > 0:
            bagian = os.read(fd, min(8192, sisa))
            if not bagian:
                break
            potongan.append(bagian)
            sisa -= len(bagian)
        mentah = b"".join(potongan)
    except OSError:
        raise RahasiaTidakSah("berkas privat tidak dapat dibaca") from None
    finally:
        os.close(fd)
    if not 1 <= len(mentah) <= batas:
        raise RahasiaTidakSah("ukuran berkas privat tidak sah")
    try:
        teks = mentah.decode("ascii")
    except UnicodeDecodeError:
        raise RahasiaTidakSah("berkas privat bukan ASCII") from None
    if any(satu != "\n" and not " " <= satu <= "~" for satu in teks):
        raise RahasiaTidakSah("karakter berkas privat tidak sah")
    return teks


def baca_berkas(path):
    """Kembalikan (merchant, server_key) hasil validasi ketat. Tanpa nilai default."""
    teks = baca_privat(path)
    baris = teks.split("\n")
    if baris and baris[-1] == "":
        baris.pop()
    nilai = {}
    for satu in baris:
        cocok = _BARIS.fullmatch(satu)
        if cocok is None or cocok.group(1) in nilai:
            raise RahasiaTidakSah("baris berkas rahasia tidak sah")
        nilai[cocok.group(1)] = cocok.group(2)
    if set(nilai) != {"merchant", "server_key"} or _MERCHANT.fullmatch(nilai["merchant"]) is None:
        raise RahasiaTidakSah("merchant/berkas rahasia tidak lengkap")
    return nilai["merchant"], nilai["server_key"]


def konfigurasi(path):
    """Konfigurasi produksi eksplisit dari berkas tepercaya; tanpa fallback."""
    merchant, kunci = baca_berkas(path)
    if _SANDBOX.match(kunci) is not None:
        raise RahasiaTidakSah("kunci sandbox tidak sah untuk produksi")
    return m.Konfigurasi("production", kunci, merchant)
