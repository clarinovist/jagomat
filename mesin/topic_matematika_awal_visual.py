"""Proyeksi keluarga visual `matematika-awal`: teks soal + descriptor `adegan_awal`.

Saat ini hanya `baca_diagram_gambar`. Kunci, pilihan ganda, dan malrule tetap
milik soal sumber; proyeksi ini hanya mengganti baris simbol "●" dengan gambar.
Kalimat pertanyaan DIAMBIL dari teks soal sumber (baris terakhir), tidak disalin.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Tuple

import awal_baca_diagram_gambar as sumber
from visual_contract import DescriptorVisual

TEMPLATE_DIDUKUNG = sumber.TEMPLATE_ID
BARIS_TEKS_SUMBER = 5  # kepala + tiga baris data + pertanyaan
# Kategori soal sumber (huruf kecil) -> nama ikon di allow-list.
IKON_KATEGORI = {
    "bola": "bola", "mobil": "mobil", "boneka": "boneka",
    "apel": "apel", "jeruk": "jeruk", "pisang": "pisang",
    "ayam": "ayam", "bebek": "bebek", "kelinci": "kelinci",
}
_FIELD_DASAR = {"varian", "tema", *sumber.KUNCI_JUMLAH}
_FIELD_TAMBAHAN = {
    "baca": {"tanya"}, "terbanyak": set(), "selisih": {"x", "y"}, "jumlah": {"x", "y"},
}


def _field_parameter(parameter: Mapping[str, Any]) -> str:
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in _FIELD_TAMBAHAN:
        raise ValueError(f"varian baca diagram gambar tidak didukung: {varian!r}")
    field = _FIELD_DASAR | _FIELD_TAMBAHAN[varian]
    if set(parameter) != field:
        hilang = sorted(field - set(parameter))
        tambahan = sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter baca_diagram_gambar/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}"
        )
    return varian


def _soal_sumber(parameter: Mapping[str, Any]):
    """Validasi domain lewat soal sumber (tipe int murni, tema, jumlah berbeda)."""
    soal = sumber.baca_diagram_gambar(**dict(parameter))
    if len(soal.teks.split("\n")) != BARIS_TEKS_SUMBER:
        raise ValueError("bentuk teks soal sumber berubah; proyeksi perlu disesuaikan")
    return soal


def _ikon(kategori: str) -> str:
    try:
        return IKON_KATEGORI[kategori.lower()]
    except KeyError as galat:
        raise ValueError(f"kategori tanpa ikon: {kategori!r}") from galat


def _tanya(parameter: Mapping[str, Any], varian: str) -> dict:
    if varian == "baca":
        return {"varian": varian, "i": parameter["tanya"]}
    if varian == "terbanyak":
        return {"varian": varian}
    return {"varian": varian, "x": parameter["x"], "y": parameter["y"]}


def _data(parameter: Mapping[str, Any], varian: str) -> dict:
    nama = sumber.TEMA[parameter["tema"]][2]
    return {
        "adegan": "deret_ikon",
        "baris": [
            {"nama": kategori, "ikon": _ikon(kategori), "jumlah": parameter[kunci]}
            for kategori, kunci in zip(nama, sumber.KUNCI_JUMLAH)
        ],
        "satuan_ikon": 1,
        "tanya": _tanya(parameter, varian),
    }


def _teks(parameter: Mapping[str, Any], soal) -> str:
    kata = sumber.TEMA[parameter["tema"]][1]
    pertanyaan = soal.teks.split("\n")[-1]
    return f"Perhatikan gambar. Satu gambar mewakili 1 {kata}.\n{pertanyaan}"


def proyeksi_matematika_awal(
    template_id: str, parameter: Mapping[str, Any]
) -> Optional[Tuple[str, DescriptorVisual]]:
    """Proyeksikan `baca_diagram_gambar`; None untuk jenis lain keluarga ini."""
    if not isinstance(template_id, str):
        raise ValueError("template_id wajib berupa teks")
    if not isinstance(parameter, Mapping):
        raise ValueError("parameter wajib berupa mapping")
    if template_id != TEMPLATE_DIDUKUNG:
        return None
    varian = _field_parameter(parameter)
    soal = _soal_sumber(parameter)
    descriptor = DescriptorVisual("adegan_awal", 1, _data(parameter, varian))
    return _teks(parameter, soal), descriptor
