"""Proyeksi visual jenis `baca_jam_awal` (keluarga `matematika-awal`): teks + descriptor `jam_analog`.

Keempat varian memakai satu gambar jam (descriptor `adegan_awal` v1 sub-adegan `jam_analog`):
teks proyeksi MEMBUANG letak jarum ("Perhatikan gambar jam.") dan tidak memuat jam yang
digambar. Teks hanya membawa yang tidak terbaca dari gambar (lamanya, nama kegiatan, bentuk
penulisan jawaban). Kunci, pilihan ganda, dan malrule tetap milik soal sumber. Baris
pertanyaan DIHITUNG ULANG dari parameter dan dibandingkan dengan baris terakhir teks soal sumber;
bila bentuknya berubah proyeksi gagal keras (ValueError).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Tuple

import awal_baca_jam_awal as sumber
from visual_contract import DescriptorVisual

PENGANTAR = "Perhatikan gambar jam."
PENGANTAR_SEKARANG = f"{PENGANTAR} Itu jam sekarang."
PESAN_BERUBAH = "bentuk teks soal sumber berubah; proyeksi perlu disesuaikan"
MENIT_PER_VARIAN = {"baca_penuh": 0, "baca_setengah": sumber.MENIT_SETENGAH,
                    "jam_kemudian": 0, "kegiatan_selesai": 0}


def _periksa_field(parameter: Mapping[str, Any]) -> str:
    """Varian dikenal dan himpunan field persis sama dengan milik soal sumber."""
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in sumber.FIELD:
        raise ValueError(f"varian baca_jam_awal tidak didukung: {varian!r}")
    field = {"varian", *sumber.FIELD[varian]}
    if set(parameter) != field:
        hilang, tambahan = sorted(field - set(parameter)), sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter baca_jam_awal/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}")
    return varian


def _isi(parameter: Mapping[str, Any]) -> dict:
    return {nama: nilai for nama, nilai in parameter.items() if nama != "varian"}


def _pengantar(varian: str, isi: dict) -> str:
    if varian == "jam_kemudian":
        return PENGANTAR_SEKARANG
    if varian == "kegiatan_selesai":
        nama, kerja = sumber.KEGIATAN[isi["kegiatan"]]
        return f"{PENGANTAR} Itu jam ketika {nama} mulai {kerja}."
    return PENGANTAR


def _teks(varian: str, isi: dict, soal) -> str:
    """Pengantar + baris pertanyaan; baris terakhir teks sumber harus persis bentuk yang diketahui."""
    baris = soal.teks.split("\n")
    tanya = sumber.pertanyaan(varian, isi)
    if len(baris) != 2 or baris[-1] != tanya:
        raise ValueError(PESAN_BERUBAH)
    return f"{_pengantar(varian, isi)}\n{tanya}"


def proyeksi_baca_jam(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    """Teks + descriptor jam analog untuk keempat varian (parameter divalidasi soal sumber)."""
    varian = _periksa_field(parameter)
    soal = sumber.baca_jam_awal(**dict(parameter))
    isi = _isi(parameter)
    data = {"adegan": "jam_analog", "jam": isi["jam"], "menit": MENIT_PER_VARIAN[varian]}
    return _teks(varian, isi, soal), DescriptorVisual("adegan_awal", 1, data)
