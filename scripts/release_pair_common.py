"""Kontrak modul probe pasangan rilis (`release_*_pair.py`).

Modul pasangan adalah **data**: string sumber Python yang dijalankan di dalam
image kandidat/recovery oleh `verify_submission_pair.py` dan
`verify_release_image.py`. Karena isinya berbeda per paket, kontrak yang bisa
dijaga bersama hanya bentuknya:

- `SUMBER_TULIS` dan `SUMBER_BACA` wajib ada, berupa string tidak kosong;
- `SUMBER_KEMBALI` opsional, tetapi bila ada juga wajib string tidak kosong;
- penanda `OSN_*_OK` tidak boleh ganda di dalam maupun antar-modul, supaya
  kegagalan probe tidak tertukar dengan paket lain.

Modul ini tidak menjalankan sumber probe. Validasi hanya membaca atribut.
"""
from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence

WAJIB = ("SUMBER_TULIS", "SUMBER_BACA")
OPSIONAL = ("SUMBER_KEMBALI",)
POLA_PENANDA = re.compile(r"OSN_[A-Z0-9_]*_OK")


class KontrakPairTidakSah(ValueError):
    """Modul pasangan tidak memenuhi bentuk minimum yang dipakai verifier."""


def validasi_modul(modul, *, nama: str | None = None) -> tuple[str, ...]:
    """Validasi satu modul pasangan; kembalikan penanda yang ditemukan.

    `nama` hanya dipakai untuk pesan galat agar operator tahu modul mana yang
    rusak tanpa membuka log panjang.
    """
    label = nama or getattr(modul, "__name__", "modul-pasangan")
    for kunci in WAJIB:
        nilai = getattr(modul, kunci, None)
        if not isinstance(nilai, str) or not nilai.strip():
            raise KontrakPairTidakSah(
                f"{label}.{kunci} wajib berupa string sumber tidak kosong"
            )
    for kunci in OPSIONAL:
        nilai = getattr(modul, kunci, None)
        if nilai is None:
            continue
        if not isinstance(nilai, str) or not nilai.strip():
            raise KontrakPairTidakSah(
                f"{label}.{kunci} bila ada wajib string sumber tidak kosong"
            )

    penanda: list[str] = []
    for kunci in WAJIB + OPSIONAL:
        nilai = getattr(modul, kunci, None)
        if isinstance(nilai, str):
            penanda.extend(POLA_PENANDA.findall(nilai))
    if len(penanda) != len(set(penanda)):
        raise KontrakPairTidakSah(f"{label} memakai penanda OSN_*_OK ganda")
    return tuple(dict.fromkeys(penanda))


def pastikan_penanda_unik(modul_penanda: Mapping[str, Sequence[str]]) -> None:
    """Tolak penanda yang sama dipakai dua modul pasangan berbeda."""
    pemilik: dict[str, str] = {}
    for nama, daftar in modul_penanda.items():
        for penanda in daftar:
            lain = pemilik.get(penanda)
            if lain is not None and lain != nama:
                raise KontrakPairTidakSah(
                    f"penanda {penanda} dipakai {lain} dan {nama}"
                )
            pemilik[penanda] = nama


def daftar_modul(path_scripts: Iterable) -> tuple:
    """Modul pasangan yang dapat divalidasi dari direktori skrip.

    Hanya nama `release_*_pair.py`; probe tunggal (`release_*_probe.py`) dan
    metadata rilis tidak memakai kontrak ini.
    """
    import importlib.util
    from pathlib import Path

    hasil = []
    for path in sorted(Path(p).resolve() for p in path_scripts):
        if not path.name.startswith("release_") or not path.name.endswith("_pair.py"):
            continue
        nama = path.stem
        spesifikasi = importlib.util.spec_from_file_location(nama, path)
        if spesifikasi is None or spesifikasi.loader is None:
            raise KontrakPairTidakSah(f"modul pasangan tidak dapat dimuat: {nama}")
        modul = importlib.util.module_from_spec(spesifikasi)
        spesifikasi.loader.exec_module(modul)
        hasil.append((nama, modul))
    return tuple(hasil)
