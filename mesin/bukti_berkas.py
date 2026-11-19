"""Penyimpanan berkas bukti transfer di folder KHUSUS (bukan folder lampiran/aset).

Berkas hanya dibaca server (pratinjau admin) dan dihapus oleh retensi; tidak pernah disajikan
lewat rute publik/murid. Aturan yang ditegakkan di sini:

- Nama tersimpan acak 32 hex, dibuat server; nama/ekstensi dari klien tidak pernah dipakai.
  Setiap fungsi yang menerima nama memvalidasinya (`POLA_NAMA`) SEBELUM menyentuh cakram,
  jadi path traversal (`..`, `/`, nama panjang/pendek, null) tidak pernah sampai ke OS.
- Tulis atomik: berkas sementara di folder yang sama (`O_EXCL|O_NOFOLLOW`, 0600, fsync),
  lalu `rename` ke nama akhir acak 128 bit (tabrakan nama diabaikan). Gagal -> sementara dibuang.
- Folder 0700 dan diperketat bila sudah ada dengan izin longgar. Env `OSN_DIREKTORI_BUKTI`
  dibaca saat dipanggil; bawaannya `bukti-transfer` di samping DB admin (tempat ledger transfer).
- Tipe berkas diputuskan dari magic bytes (`mime_dari_isi`), bukan Content-Type atau nama klien.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
from typing import BinaryIO, Optional

NAMA_ENV = "OSN_DIREKTORI_BUKTI"
NAMA_FOLDER = "bukti-transfer"
MODE_FOLDER = 0o700
MODE_BERKAS = 0o600
PANJANG_NAMA_BYTE = 16
POLA_NAMA = re.compile(r"[0-9a-f]{32}")
AWALAN_SEMENTARA = ".tmp-"
_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"
_PDF = b"%PDF-"
_TIPE_MAGIC = ((_JPEG, "image/jpeg"), (_PNG, "image/png"), (_PDF, "application/pdf"))


class BuktiBerkasError(Exception):
    """Dasar galat penyimpanan bukti; pesan tetap tanpa path."""


class NamaBerkasTidakSah(BuktiBerkasError, ValueError):
    def __init__(self):
        super().__init__("nama berkas bukti tidak sah")


def mime_dari_isi(isi: bytes) -> Optional[str]:
    """MIME dari magic bytes lengkap (JPEG, PNG 8 byte, PDF); selain itu None."""
    if type(isi) is not bytes:
        return None
    for awalan, mime in _TIPE_MAGIC:
        if isi.startswith(awalan):
            return mime
    return None


def direktori_bukti() -> Path:
    """Folder bukti: env `OSN_DIREKTORI_BUKTI`, atau `bukti-transfer` di samping DB admin."""
    ling = os.environ.get(NAMA_ENV, "").strip()
    if ling:
        return Path(ling)
    import admin_store  # impor lambat: BAWAAN bisa diganti saat uji
    return Path(admin_store.BAWAAN).resolve().parent / NAMA_FOLDER


def _periksa_nama(nama) -> str:
    if type(nama) is not str or POLA_NAMA.fullmatch(nama) is None:
        raise NamaBerkasTidakSah()
    return nama


def jalur_berkas(nama, folder=None) -> Path:
    """Path berkas bukti untuk nama sah (di dalam `folder`, bawaan folder bukti); nama tidak sah -> galat."""
    return (direktori_bukti() if folder is None else Path(folder)) / _periksa_nama(nama)


def _siapkan_folder() -> Path:
    folder = direktori_bukti()
    os.makedirs(folder, mode=MODE_FOLDER, exist_ok=True)
    os.chmod(folder, MODE_FOLDER)
    return folder


def _tulis_sementara(folder: Path, isi: bytes) -> Path:
    jalur = folder / (AWALAN_SEMENTARA + secrets.token_hex(PANJANG_NAMA_BYTE))
    bendera = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(jalur, bendera, MODE_BERKAS)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(isi)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        jalur.unlink(missing_ok=True)
        raise
    return jalur


def simpan_berkas(isi: bytes) -> str:
    """Simpan `isi` sebagai berkas baru bernama acak; kembalikan nama (32 hex).

    Atomik: berkas akhir tidak pernah tampak setengah ditulis. Galat OS diteruskan setelah
    berkas sementara dibersihkan.
    """
    if type(isi) is not bytes:
        raise BuktiBerkasError("isi bukti harus bytes")
    folder = _siapkan_folder()
    sementara = _tulis_sementara(folder, isi)
    nama = secrets.token_hex(PANJANG_NAMA_BYTE)
    try:
        os.replace(sementara, folder / nama)
    except BaseException:
        sementara.unlink(missing_ok=True)
        raise
    return nama


def buka_berkas(nama) -> BinaryIO:
    """Buka berkas bukti untuk dibaca (biner); nama tidak sah ditolak, symlink ditolak."""
    jalur = jalur_berkas(nama)
    fd = os.open(jalur, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    return os.fdopen(fd, "rb")


def hapus_berkas(nama, folder=None) -> bool:
    """Hapus berkas bukti; idempoten (True bila ada dan terhapus, False bila sudah tiada).

    `folder` opsional (retensi memakai folder yang ditunjuk operator); bawaannya folder bukti aplikasi.
    """
    jalur = jalur_berkas(nama, folder)
    try:
        jalur.unlink()
    except FileNotFoundError:
        return False
    return True
