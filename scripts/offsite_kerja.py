"""Direktori kerja dan tar bundle untuk off-site VPS.

- `buat_tar`: tar.gz HANYA dari berkas yang tercantum di manifest bundle, dibuka
  lewat `dir_fd` + `O_NOFOLLOW` lalu `fstat` harus berkas biasa. Tidak ada jendela
  antara pemeriksaan symlink dan pembukaan (TOCTOU), dan berkas liar di luar
  manifest tidak ikut terunggah.
- `hapus_kerja`: hapus direktori sementara; kegagalan dicatat ke stderr (tanpa
  rahasia), tidak ditelan.
- `sapu_sisa`: bersihkan sisa direktori `offsite-*` (plaintext/sandi sesi bila proses
  sebelumnya mati karena SIGKILL) yang milik uid root, mode 0700, berumur > 1 hari.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
from typing import List, Optional

import backup_harian
import offsite_kripto as kripto

POLA_KERJA = re.compile(r"offsite-[a-z0-9_]{8}")  # bentuk keluaran `tempfile.mkdtemp`
UMUR_SISA_DETIK = 86400
MODE_KERJA = 0o700
_BUKA_BERKAS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
_BUKA_DIREKTORI = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
PESAN_BUKAN_BIASA = "bundle memuat entri bukan berkas biasa atau berubah saat dibaca"


def _buka_berkas_biasa(nama: str, dir_fd: int):
    """Buka tanpa mengikuti symlink; tolak bila bukan berkas biasa. Kembalikan fileobj."""
    try:
        fd = os.open(nama, _BUKA_BERKAS, dir_fd=dir_fd)
    except OSError as galat:
        raise kripto.GalatOffsite(PESAN_BUKAN_BIASA) from galat
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise kripto.GalatOffsite(PESAN_BUKAN_BIASA)
    return os.fdopen(fd, "rb")


def _nama_manifest(dir_fd: int) -> List[str]:
    with _buka_berkas_biasa("manifest.json", dir_fd) as sumber:
        try:
            berkas = json.load(sumber)["berkas"]
            nama = [item["nama"] for item in berkas]
        except (ValueError, KeyError, TypeError) as galat:
            raise kripto.GalatOffsite("manifest bundle tidak terbaca") from galat
    try:
        for satu in nama:
            backup_harian.periksa_nama_berkas(satu)
    except ValueError as galat:
        raise kripto.GalatOffsite(f"manifest bundle: {galat}") from galat
    return ["manifest.json", *sorted(set(nama) - {"manifest.json"})]


def _info_direktori(nama: str, dir_fd: int) -> tarfile.TarInfo:
    info = tarfile.TarInfo(nama)
    info.type, info.mode = tarfile.DIRTYPE, 0o700
    info.mtime = os.fstat(dir_fd).st_mtime
    return info


def buat_tar(bundle: Path, tujuan: Path) -> None:
    """Tar.gz isi manifest bundle saja; symlink/perangkat/berkas di luar manifest ditolak atau diabaikan."""
    try:
        dir_fd = os.open(str(bundle), _BUKA_DIREKTORI)
    except OSError as galat:
        raise kripto.GalatOffsite("direktori bundle tidak bisa dibuka") from galat
    try:
        nama_berkas = _nama_manifest(dir_fd)
        with tarfile.open(str(tujuan), "w:gz") as tar:
            tar.addfile(_info_direktori(bundle.name, dir_fd))
            for nama in nama_berkas:
                with _buka_berkas_biasa(nama, dir_fd) as isi:
                    info = tar.gettarinfo(arcname=f"{bundle.name}/{nama}", fileobj=isi)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    tar.addfile(info, isi)
    finally:
        os.close(dir_fd)


def hapus_kerja(kerja: Path) -> None:
    try:
        shutil.rmtree(kerja)
    except FileNotFoundError:
        pass
    except OSError as galat:
        print(f"peringatan: direktori sementara tidak terhapus ({type(galat).__name__}); "
              "akan disapu pada run berikutnya", file=sys.stderr)


def _sisa_layak_disapu(info: os.stat_result, sekarang: float, uid: int) -> bool:
    return (stat.S_ISDIR(info.st_mode) and info.st_uid == uid
            and stat.S_IMODE(info.st_mode) == MODE_KERJA
            and sekarang - info.st_mtime > UMUR_SISA_DETIK)


def sapu_sisa(induk, sekarang: float, *, uid: Optional[int] = None) -> int:
    """Hapus sisa `offsite-*` lama milik `uid` (bawaan: euid; produksi root); kembalikan jumlahnya."""
    uid = os.geteuid() if uid is None else uid
    try:
        entri = [e for e in os.scandir(induk) if POLA_KERJA.fullmatch(e.name)]
    except OSError:
        return 0
    jumlah = 0
    for item in entri:
        try:
            layak = _sisa_layak_disapu(item.stat(follow_symlinks=False), sekarang, uid)
        except OSError:
            continue
        if layak:
            hapus_kerja(Path(item.path))
            jumlah += 1
    return jumlah
