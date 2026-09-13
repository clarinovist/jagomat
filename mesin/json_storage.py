"""Penyimpanan JSON privat dengan transaksi file lintas thread dan proses.

Lock memakai sidecar yang namanya stabil karena berkas data diganti secara atomik.
Runtime aplikasi adalah macOS/Linux; keduanya menyediakan ``fcntl.flock``.
"""
from __future__ import annotations

import errno
import fcntl
import json
import os
import stat
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class GalatPenyimpananJSON(ValueError):
    """Berkas JSON tidak dapat dibaca sebagai state yang aman."""


class _KeadaanKunci:
    def __init__(self) -> None:
        self.kunci_thread = threading.RLock()
        self.lokal = threading.local()


_KUNCI_REGISTRI = threading.Lock()
_KEADAAN_PER_PATH: dict[str, _KeadaanKunci] = {}
_FD_AKTIF: set[int] = set()
_WAJIB_ADA = object()
TIDAK_ADA = object()


def _reset_setelah_fork() -> None:
    """Tutup descriptor warisan dan reset lock bookkeeping di proses anak."""
    global _KUNCI_REGISTRI, _KEADAAN_PER_PATH, _FD_AKTIF
    for fd in tuple(_FD_AKTIF):
        try:
            os.close(fd)
        except OSError:
            pass
    _KUNCI_REGISTRI = threading.Lock()
    _KEADAAN_PER_PATH = {}
    _FD_AKTIF = set()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_reset_setelah_fork)


def jalur_kanonik(path: Path) -> Path:
    """Path absolut tanpa alias direktori atau symlink yang sudah ada."""
    return Path(path).expanduser().resolve(strict=False)


def jalur_lock(path: Path) -> Path:
    """Sidecar tetap; jangan pernah mengunci inode data yang di-replace."""
    tujuan = jalur_kanonik(path)
    return tujuan.with_name(f".{tujuan.name}.lock")


def _keadaan(path: Path) -> _KeadaanKunci:
    kunci = str(jalur_kanonik(path))
    with _KUNCI_REGISTRI:
        hasil = _KEADAAN_PER_PATH.get(kunci)
        if hasil is None:
            hasil = _KeadaanKunci()
            _KEADAAN_PER_PATH[kunci] = hasil
    return hasil


def _buka_sidecar(path: Path) -> int:
    try:
        info_path = path.lstat()
    except FileNotFoundError:
        info_path = None
    if info_path is not None and not stat.S_ISREG(info_path.st_mode):
        raise GalatPenyimpananJSON("sidecar lock bukan berkas biasa")
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise GalatPenyimpananJSON("sidecar lock bukan berkas biasa")
        if info_path is not None and (
            info.st_dev != info_path.st_dev or info.st_ino != info_path.st_ino
        ):
            raise GalatPenyimpananJSON("sidecar lock berubah saat dibuka")
        os.fchmod(fd, 0o600)
        return fd
    except Exception:
        os.close(fd)
        raise


@contextmanager
def transaksi_json(path: Path) -> Iterator[Path]:
    """Kunci eksklusif reentrant untuk satu path data kanonik.

    ``RLock`` menyerialkan thread satu proses. ``flock`` pada sidecar yang tidak
    ikut diganti menyerialkan proses. Nested call pada thread yang sama memakai
    descriptor yang sama agar tidak mencoba mengambil flock kedua.
    """
    tujuan = jalur_kanonik(path)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    keadaan = _keadaan(tujuan)
    with keadaan.kunci_thread:
        kedalaman = getattr(keadaan.lokal, "kedalaman", 0)
        if kedalaman == 0:
            fd = _buka_sidecar(jalur_lock(tujuan))
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
            except Exception:
                os.close(fd)
                raise
            keadaan.lokal.fd = fd
            _FD_AKTIF.add(fd)
        keadaan.lokal.kedalaman = kedalaman + 1
        try:
            yield tujuan
        finally:
            sisa = keadaan.lokal.kedalaman - 1
            keadaan.lokal.kedalaman = sisa
            if sisa == 0:
                fd = keadaan.lokal.fd
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    _FD_AKTIF.discard(fd)
                    os.close(fd)
                    del keadaan.lokal.fd
                    del keadaan.lokal.kedalaman


def _tolak_konstanta_json(nilai: str):
    raise ValueError(f"konstanta JSON tidak sah: {nilai}")


def _objek_tanpa_duplikat(pasangan):
    hasil = {}
    for kunci, nilai in pasangan:
        if kunci in hasil:
            raise ValueError("kunci JSON duplikat")
        hasil[kunci] = nilai
    return hasil


def baca_json_ketat(path: Path, *, bawaan: Any = _WAJIB_ADA) -> Any:
    """Baca JSON; bedakan berkas hilang dari JSON rusak atau ambigu."""
    tujuan = jalur_kanonik(path)
    try:
        with tujuan.open("r", encoding="utf-8") as berkas:
            return json.load(
                berkas,
                parse_constant=_tolak_konstanta_json,
                object_pairs_hook=_objek_tanpa_duplikat,
            )
    except FileNotFoundError:
        if bawaan is _WAJIB_ADA:
            raise
        return bawaan
    except (ValueError, UnicodeError, OSError) as galat:
        raise GalatPenyimpananJSON("berkas JSON tidak sah") from galat


def _sinkronkan_direktori(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    fd = os.open(str(path), flags)
    try:
        try:
            os.fsync(fd)
        except OSError as galat:
            if galat.errno not in (errno.EINVAL, errno.ENOTSUP, errno.EBADF):
                raise
    finally:
        os.close(fd)


def tulis_json_atomik(data: Any, path: Path, *, indent: int | None = None) -> None:
    """Tulis JSON privat, flush ke disk, lalu replace dan fsync direktori."""
    with transaksi_json(path) as tujuan:
        fd, nama_sementara = tempfile.mkstemp(
            dir=str(tujuan.parent), prefix=f".{tujuan.name}-"
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as berkas:
                fd = -1
                json.dump(data, berkas, indent=indent, allow_nan=False)
                berkas.flush()
                os.fsync(berkas.fileno())
            os.replace(nama_sementara, tujuan)
            nama_sementara = ""
            _sinkronkan_direktori(tujuan.parent)
        finally:
            if fd >= 0:
                os.close(fd)
            if nama_sementara:
                try:
                    os.unlink(nama_sementara)
                except FileNotFoundError:
                    pass
