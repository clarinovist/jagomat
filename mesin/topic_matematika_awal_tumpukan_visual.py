"""Proyeksi visual jenis `tampak_kubus_awal` (keluarga `matematika-awal`): teks + descriptor `tumpukan_kubus`.

Keempat varian memakai satu gambar susunan kubus satuan (descriptor `adegan_awal` v1 sub-adegan
`tumpukan_kubus`): teks proyeksi MEMBUANG tinggi tiap tumpukan ("Perhatikan gambar kubus-kubus satuan.
Tiap tumpukan berdiri di lantai.") dan tidak memuat angka apa pun. Teks hanya membawa yang tidak terbaca
dari gambar (tampak yang ditanya dan bentuk penulisan jawaban). Kunci, pilihan ganda, dan malrule tetap
milik soal sumber. Baris pertanyaan DIHITUNG ULANG dari varian dan dibandingkan dengan baris terakhir
teks soal sumber; bila bentuknya berubah proyeksi gagal keras (ValueError).

Descriptor: `tinggi` = daftar baris dari baris depan, tiap baris tinggi tumpukan dari kiri ke kanan,
persis seperti parameter `tinggi` soal sumber dipotong per baris.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Tuple

import awal_tampak_kubus_awal as sumber
from visual_contract import DescriptorVisual

PENGANTAR = f"Perhatikan gambar kubus-kubus satuan. {sumber.KALIMAT_LANTAI}"
PESAN_BERUBAH = "bentuk teks soal sumber berubah; proyeksi perlu disesuaikan"


def _periksa_field(parameter: Mapping[str, Any]) -> str:
    """Varian dikenal dan himpunan field persis sama dengan milik soal sumber."""
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in sumber.VARIAN:
        raise ValueError(f"varian tampak_kubus_awal tidak didukung: {varian!r}")
    field = {"varian", *sumber.FIELD}
    if set(parameter) != field:
        hilang, tambahan = sorted(field - set(parameter)), sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter tampak_kubus_awal/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}")
    return varian


def _teks(varian: str, soal) -> str:
    """Pengantar + baris pertanyaan; baris terakhir teks sumber harus persis bentuk yang diketahui."""
    baris = soal.teks.split("\n")
    tanya = sumber.pertanyaan(varian)
    if len(baris) != 2 or baris[-1] != tanya:
        raise ValueError(PESAN_BERUBAH)
    return f"{PENGANTAR}\n{tanya}"


def proyeksi_tampak_kubus(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    """Teks + descriptor tumpukan kubus untuk keempat varian (parameter divalidasi soal sumber)."""
    varian = _periksa_field(parameter)
    soal = sumber.tampak_kubus_awal(**dict(parameter))
    baris, kolom, tinggi = parameter["baris"], parameter["kolom"], parameter["tinggi"]
    lajur = [list(tinggi[y * kolom:(y + 1) * kolom]) for y in range(baris)]
    data = {"adegan": "tumpukan_kubus", "tinggi": lajur}
    return _teks(varian, soal), DescriptorVisual("adegan_awal", 1, data)
