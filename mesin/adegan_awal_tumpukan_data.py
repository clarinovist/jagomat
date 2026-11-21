"""Validator ketat sub-adegan `tumpukan_kubus` dari descriptor `adegan_awal` v1 (Matematika Awal).

Descriptor menggambar susunan kubus satuan isometrik buatan kode (SVG, bukan raster) di atas lantai
berpetak: `{"adegan": "tumpukan_kubus", "tinggi": [[...], ...]}`. `tinggi` adalah daftar baris dari
baris DEPAN (terdekat dengan anak) ke belakang; tiap baris daftar tinggi tumpukan dari kiri ke kanan
(bilangan bulat 0..3, 0 = petak kosong). Alas 1..3 baris x 1..3 kolom, semua baris sama panjang,
sedikitnya satu petak terisi. Tinggi tiap tumpukan adalah FAKTA GAMBAR: banyak kubus, persegi pada
tampak depan, atas, atau samping terbaca dari gambar, bukan tertulis di descriptor. Validator hanya
menjaga bentuk yang aman digambar; jenis soal yang memakainya membatasi susunan agar gambarnya tidak
ambigu. Field tambahan ditolak.

Dipanggil lewat `adegan_awal_data.validasi_adegan_awal` (impor malas agar tidak melingkar).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from adegan_awal_data import _field_tepat

ALAS_MIN, ALAS_MAKS = 1, 3
TINGGI_MIN, TINGGI_MAKS = 0, 3
_FIELD = {"adegan", "tinggi"}


def _baris_tunggal(isi: Any, indeks: int) -> tuple:
    if not isinstance(isi, (list, tuple)):
        raise ValueError(f"tinggi[{indeks}] wajib berupa daftar")
    if not ALAS_MIN <= len(isi) <= ALAS_MAKS:
        raise ValueError(f"tiap baris wajib memuat {ALAS_MIN}..{ALAS_MAKS} kolom")
    for h in isi:
        if type(h) is not int or not TINGGI_MIN <= h <= TINGGI_MAKS:
            raise ValueError(f"tinggi tumpukan wajib bilangan bulat {TINGGI_MIN}..{TINGGI_MAKS}: {h!r}")
    return tuple(isi)


def validasi_tumpukan(data: Mapping[str, Any]) -> None:
    """Validasi allow-list descriptor `tumpukan_kubus`; gagal tertutup (bool tidak lolos sebagai int)."""
    _field_tepat(data, _FIELD, "adegan_awal/tumpukan_kubus")
    nilai = data["tinggi"]
    if not isinstance(nilai, (list, tuple)):
        raise ValueError("tinggi adegan wajib berupa daftar baris")
    if not ALAS_MIN <= len(nilai) <= ALAS_MAKS:
        raise ValueError(f"adegan tumpukan_kubus wajib memuat {ALAS_MIN}..{ALAS_MAKS} baris")
    baris = [_baris_tunggal(isi, i) for i, isi in enumerate(nilai)]
    if len({len(isi) for isi in baris}) != 1:
        raise ValueError("semua baris wajib sama banyak kolom")
    if not any(h for isi in baris for h in isi):
        raise ValueError("sedikitnya satu petak wajib terisi")
