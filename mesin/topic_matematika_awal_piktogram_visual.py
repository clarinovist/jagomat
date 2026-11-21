"""Proyeksi visual jenis `piktogram_lima_awal` (keluarga `matematika-awal`): teks + descriptor `deret_ikon`.

Kelima varian memakai sub-adegan `deret_ikon` (descriptor `adegan_awal` v1) dengan skala besar: satu baris
gambar untuk tiap kategori yang TERTAMPIL, `satuan_ikon` = skala. Teks proyeksi membuang baris data "●"
dan hanya memuat skala serta kalimat pertanyaan ("Perhatikan gambar. Satu gambar mewakili 5 mainan."),
jadi banyak gambar per baris hanya terbaca dari gambar. Pada `berapa_ikon` baris kategori yang ditanya
TIDAK digambar (descriptor hanya memuat baris lain) dan nilainya ada di kalimat pertanyaan; banyak gambar
yang dicari tidak ada di gambar maupun di descriptor. Kunci, pilihan ganda, dan malrule tetap milik soal
sumber. Kepala dan baris pertanyaan DIHITUNG ULANG dari parameter dan dibandingkan dengan teks soal sumber;
bila bentuknya berubah proyeksi gagal keras (ValueError).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Tuple

import awal_piktogram_lima_awal as sumber
from visual_contract import DescriptorVisual

PESAN_BERUBAH = "bentuk teks soal sumber berubah; proyeksi perlu disesuaikan"
# Varian sumber -> jenis pertanyaan descriptor (deret_ikon); baca_nilai membawa indeks baris.
_TANYA_DESCRIPTOR = {
    "baca_nilai": "baca", "terbanyak_selisih": "terbanyak_selisih", "total": "total",
    "rata_rata": "rata_rata", "berapa_ikon": "berapa_ikon",
}


def _periksa_field(parameter: Mapping[str, Any]) -> str:
    """Varian dikenal dan himpunan field persis sama dengan milik soal sumber."""
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in sumber.VARIAN:
        raise ValueError(f"varian piktogram_lima_awal tidak didukung: {varian!r}")
    field = {"varian", *sumber.FIELD_DASAR}
    if varian in sumber.VARIAN_BERTANYA:
        field = field | {"tanya"}
    if set(parameter) != field:
        hilang, tambahan = sorted(field - set(parameter)), sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter piktogram_lima_awal/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}")
    return varian


def _teks(varian: str, parameter: Mapping[str, Any], soal) -> str:
    """Skala + pertanyaan versi gambar; kepala dan baris terakhir teks sumber harus persis yang diketahui."""
    tema, skala = parameter["tema"], parameter["skala"]
    jumlah, tanya = parameter["jumlah"], parameter.get("tanya")
    baris = soal.teks.split("\n")
    if baris[0] != sumber.kepala(tema, skala) or baris[-1] != sumber.pertanyaan(varian, tema, skala, jumlah, tanya):
        raise ValueError(PESAN_BERUBAH)
    gambar = sumber.pertanyaan(varian, tema, skala, jumlah, tanya, sumber.LAMBANG_VISUAL)
    return f"Perhatikan gambar. Satu gambar mewakili {skala} {sumber.TEMA[tema].kata}.\n{gambar}"


def _tanya(varian: str, parameter: Mapping[str, Any]) -> dict:
    dasar = {"varian": _TANYA_DESCRIPTOR[varian]}
    return {**dasar, "i": parameter["tanya"]} if varian == "baca_nilai" else dasar


def _data(varian: str, parameter: Mapping[str, Any]) -> dict:
    kategori = sumber.TEMA[parameter["tema"]].kategori
    jumlah = parameter["jumlah"]
    tampil = sumber.indeks_digambar(varian, len(jumlah), parameter.get("tanya"))
    return {
        "adegan": "deret_ikon",
        "baris": [{"nama": kategori[i][0], "ikon": kategori[i][1], "jumlah": jumlah[i]} for i in tampil],
        "satuan_ikon": parameter["skala"],
        "tanya": _tanya(varian, parameter),
    }


def proyeksi_piktogram(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    """Teks + descriptor deret_ikon untuk kelima varian (parameter divalidasi soal sumber)."""
    varian = _periksa_field(parameter)
    soal = sumber.piktogram_lima_awal(**dict(parameter))
    return _teks(varian, parameter, soal), DescriptorVisual("adegan_awal", 1, _data(varian, parameter))
