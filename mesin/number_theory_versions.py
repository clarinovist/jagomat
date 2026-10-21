"""Reader semua jenis tetap tersedia; versi hanya memilih komposisi writer baru."""
from __future__ import annotations

import os

# Kandidat komposisi2; recovery katalog542dcd9 komposisi1, reader lengkap.
# Katalog perbaikan tetap default1 sampai tinjauan manusia/aktivasi terkontrol.
VERSI_TEORI_BILANGAN_BAWAAN = 2
LAMA = {
    "P4": ("keterbagian", "sisa_pembagian", "paritas") * 3 + ("keterbagian",),
    "P5": ("keterbagian", "prima_faktorisasi", "kpk_dua_bilangan",
           "sisa_pembagian", "paritas", "gauss_deret",
           "keterbagian", "prima_faktorisasi", "kpk_dua_bilangan", "gauss_deret"),
}


def versi_writer():
    mentah = os.environ.get("OSN_TEORI_BILANGAN_VERSI")
    if mentah is None:
        return VERSI_TEORI_BILANGAN_BAWAAN
    if mentah.strip() not in {"1", "2"}:
        raise ValueError("OSN_TEORI_BILANGAN_VERSI hanya menerima 1 atau 2")
    return int(mentah.strip())


def pilih_komposisi(baru):
    """Override writer saat registrasi; None mempertahankan komposisi kandidat."""
    return {**baru, **LAMA} if versi_writer() == 1 else None
