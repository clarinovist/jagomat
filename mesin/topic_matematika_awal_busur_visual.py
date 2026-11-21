"""Proyeksi visual jenis `ukur_sudut_awal` (keluarga `matematika-awal`): teks + descriptor `busur`.

Kelima varian memakai satu gambar busur derajat (descriptor `adegan_awal` v1 sub-adegan `busur`):
teks proyeksi MEMBUANG letak kaki sudut pada skala ("Perhatikan gambar busur derajat.") dan tidak
memuat angka apa pun. Teks hanya membawa yang tidak terbaca dari gambar (nama sudut yang ditanya
dan bentuk penulisan jawaban). Kunci, pilihan ganda, dan malrule tetap milik soal sumber. Baris
pertanyaan DIHITUNG ULANG dari varian dan dibandingkan dengan baris terakhir teks soal sumber;
bila bentuknya berubah proyeksi gagal keras (ValueError).

Arah sinar pada descriptor dihitung dari kanan berlawanan arah jarum jam: kaki alas di kanan
berarah 0, di kiri berarah 180; sudut x dari kaki alas kanan berarah x, dari kaki alas kiri
berarah 180 - x. `baca_geser` tidak punya kaki alas: kedua kaki berarah a dan b.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Tuple

import awal_ukur_sudut_awal as sumber
from visual_contract import DescriptorVisual

PENGANTAR = "Perhatikan gambar busur derajat."
PESAN_BERUBAH = "bentuk teks soal sumber berubah; proyeksi perlu disesuaikan"
PUSAT_VARIAN = {"baca_dari_nol": "B", "baca_geser": "B", "jenis_sudut": "B",
                "banding": "O", "selisih_dua": "O"}
ARAH_ALAS = {"kanan": 0, "kiri": sumber.SUDUT_LURUS}


def _periksa_field(parameter: Mapping[str, Any]) -> str:
    """Varian dikenal dan himpunan field persis sama dengan milik soal sumber."""
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in sumber.FIELD:
        raise ValueError(f"varian ukur_sudut_awal tidak didukung: {varian!r}")
    field = {"varian", *sumber.FIELD[varian]}
    if set(parameter) != field:
        hilang, tambahan = sorted(field - set(parameter)), sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter ukur_sudut_awal/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}")
    return varian


def _dari_alas(arah: str, sudut: int) -> int:
    """Arah sinar untuk sudut `sudut` yang diukur dari kaki alas di sisi `arah`."""
    return sudut if arah == "kanan" else sumber.SUDUT_LURUS - sudut


def _sinar(varian: str, isi: dict) -> list:
    if varian == "baca_geser":
        return [{"huruf": "A", "sudut": isi["a"]}, {"huruf": "C", "sudut": isi["b"]}]
    alas = {"huruf": "A", "sudut": ARAH_ALAS[isi["arah"]]}
    if varian in ("baca_dari_nol", "jenis_sudut"):
        return [alas, {"huruf": "C", "sudut": _dari_alas(isi["arah"], isi["sudut"])}]
    return [alas, {"huruf": "B", "sudut": _dari_alas(isi["arah"], isi["b"])},
            {"huruf": "C", "sudut": _dari_alas(isi["arah"], isi["c"])}]


def _teks(varian: str, soal) -> str:
    """Pengantar + baris pertanyaan; baris terakhir teks sumber harus persis bentuk yang diketahui."""
    baris = soal.teks.split("\n")
    tanya = sumber.pertanyaan(varian)
    if len(baris) != 2 or baris[-1] != tanya:
        raise ValueError(PESAN_BERUBAH)
    return f"{PENGANTAR}\n{tanya}"


def proyeksi_ukur_sudut(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    """Teks + descriptor busur derajat untuk kelima varian (parameter divalidasi soal sumber)."""
    varian = _periksa_field(parameter)
    soal = sumber.ukur_sudut_awal(**dict(parameter))
    isi = {nama: nilai for nama, nilai in parameter.items() if nama != "varian"}
    data = {"adegan": "busur", "pusat": PUSAT_VARIAN[varian], "sinar": _sinar(varian, isi)}
    return _teks(varian, soal), DescriptorVisual("adegan_awal", 1, data)
