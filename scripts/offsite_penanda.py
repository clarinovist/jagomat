"""Penanda keberhasilan off-site (`last-ok`, `retention-ok`) yang ditulis dengan aman.

Isi satu baris: `<stempel WIB> <id> kunci=nilai ...`. Dua token pertama tetap
(`stempel id`) agar pembaca lama tetap jalan; sisanya pasangan `kunci=nilai`
(untuk `last-ok`: `mac`, `sha256`, `kunci` = sidik jari kunci publik; `-` bila
tidak diketahui). Penanda adalah sumber TEPERCAYA nilai mac/sha256 untuk
`pulihkan_offsite.py --mac-harapan/--sha256-harapan`: hanya root VPS yang menulis.

Penulisan lewat `mkstemp` di direktori yang sama (O_EXCL, nama acak, jadi symlink
yang ditanam di nama sementara tidak diikuti), fsync, chmod 0644, lalu `os.replace`.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Dict, Optional

MODE_PENANDA = 0o644
TANPA_NILAI = "-"


def baris_penanda(stempel: str, id_bundle: str, bidang: Dict[str, str]) -> str:
    sisa = "".join(f" {k}={v}" for k, v in bidang.items())
    return f"{stempel} {id_bundle}{sisa}\n"


def baca_penanda(path) -> Optional[Dict[str, str]]:
    """Urai penanda; None bila tidak ada atau bentuknya tidak dikenali."""
    try:
        bagian = Path(path).read_text(encoding="utf-8").split()
    except (OSError, UnicodeDecodeError):
        return None
    if len(bagian) < 2:
        return None
    hasil = {"stempel": bagian[0], "id": bagian[1]}
    for item in bagian[2:]:
        kunci, pemisah, nilai = item.partition("=")
        if pemisah:
            hasil[kunci] = nilai
    return hasil


def tulis_penanda(path: Path, isi: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, sementara = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as keluar:
            keluar.write(isi)
            keluar.flush()
            os.fsync(keluar.fileno())
            os.fchmod(keluar.fileno(), MODE_PENANDA)
        os.replace(sementara, path)
    except BaseException:
        try:
            os.unlink(sementara)
        except FileNotFoundError:
            pass
        raise
