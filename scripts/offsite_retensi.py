"""Retensi set `vps/<id>/` di R2 dengan pagar pengaman terhadap jam salah.

Dua pagar: (1) `simpan_minimal` set lengkap TERBARU (menurut id) selalu dijaga
apa pun umurnya; (2) bila kandidat hapus lebih dari `hapus_maks` set, tidak ada
yang dihapus dan `GalatRetensi` dilempar (jam VPS salah, bukan retensi biasa).
Set yang baru diunggah tidak pernah dihapus.
"""
from __future__ import annotations

import re
from typing import Dict, List, Set

import offsite_kripto as kripto

POLA_KUNCI_OBJEK = re.compile(r"vps/([0-9]{8}-[0-9]{6})/(data\.enc|kunci\.enc|meta\.json)")
SIMPAN_MINIMAL = 7
HAPUS_MAKS = 5
DETIK_PER_HARI = 86400


class GalatRetensi(kripto.GalatOffsite):
    """Retensi dibatalkan (melebihi batas) tanpa menghapus apa pun."""


def kelompokkan_set(objek) -> Dict[str, list]:
    kelompok: Dict[str, list] = {}
    for item in objek:
        cocok = POLA_KUNCI_OBJEK.fullmatch(item.kunci)
        if cocok:
            kelompok.setdefault(cocok.group(1), []).append(item)
    return kelompok


def _id_terjaga(kelompok: Dict[str, list], simpan_minimal: int) -> Set[str]:
    lengkap = sorted((i for i, isi in kelompok.items() if len(isi) == len(kripto.NAMA_OBJEK)),
                     reverse=True)
    return set(lengkap[:simpan_minimal])


def pilih_kedaluwarsa(objek, batas: float, id_baru: str, simpan_minimal: int) -> Dict[str, List[str]]:
    """{id set: kunci objeknya} untuk set yang boleh dihapus."""
    kelompok = kelompokkan_set(objek)
    terjaga = _id_terjaga(kelompok, simpan_minimal) | {id_baru}
    return {i: sorted(o.kunci for o in isi) for i, isi in kelompok.items()
            if i not in terjaga and max(o.diubah for o in isi) < batas}


def terapkan_retensi(klien, id_baru: str, sekarang: float, hari: int,
                     simpan_minimal: int = SIMPAN_MINIMAL, hapus_maks: int = HAPUS_MAKS) -> int:
    """Hapus set kedaluwarsa; kembalikan jumlah OBJEK terhapus."""
    objek = klien.daftar_objek(kripto.PREFIKS)
    kandidat = pilih_kedaluwarsa(objek, sekarang - hari * DETIK_PER_HARI, id_baru, simpan_minimal)
    if len(kandidat) > hapus_maks:
        raise GalatRetensi(f"{len(kandidat)} set kedaluwarsa melebihi --hapus-maks {hapus_maks}; "
                           "tidak ada yang dihapus (periksa jam VPS)")
    hapus = sorted(kunci for kunci_set in kandidat.values() for kunci in kunci_set)
    for kunci in hapus:
        klien.hapus_objek(kunci)
    return len(hapus)
