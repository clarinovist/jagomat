"""Validator ketat descriptor `adegan_awal` v1 (Matematika Awal, sub-adegan `deret_ikon`).

Descriptor hanya memuat data aman untuk menggambar: nama baris, nama ikon dari
allow-list, banyak ikon, dan jenis pertanyaan. Kunci atau jawaban TIDAK PERNAH
masuk descriptor; banyak ikon adalah fakta gambar, bukan jawaban.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from typing import Any

# Nama ikon = berkas `mesin/aset/ikon-<nama>-v1.png`; APPEND-ONLY.
# Tambahan 21 Nov 2026 (buku, karpet, lemari, meja, payung, sapu, sendok, tongkat) dibuat dengan model gambar lain.
IKON_DIDUKUNG = (
    "apel", "ayam", "balok", "bebek", "bola", "boneka", "buku", "bunga", "jeruk",
    "kancing", "karpet", "kelereng", "kelinci", "klip", "kue", "lemari", "meja",
    "mobil", "payung", "pensil", "permen", "pisang", "pizza", "roti", "sapu",
    "sendok", "stiker", "tongkat", "ubin",
)
ADEGAN_DIDUKUNG = ("deret_ikon",)
BARIS_MIN, BARIS_MAKS = 2, 4
JUMLAH_MIN, JUMLAH_MAKS = 0, 12
PANJANG_NAMA_MAKS = 24
SATUAN_IKON_V1 = 1
VARIAN_TANYA = ("baca", "terbanyak", "selisih", "jumlah")

_KURUNG_MARKUP = frozenset("<>")
_FIELD_ADEGAN = {"adegan", "baris", "satuan_ikon", "tanya"}
_FIELD_BARIS = {"nama", "ikon", "jumlah"}


def _field_tepat(data: Mapping[str, Any], field: set, jenis: str) -> None:
    kunci = set(data)
    if any(not isinstance(nama, str) for nama in kunci):
        raise ValueError(f"field {jenis} wajib memakai kunci teks")
    if kunci != field:
        hilang = sorted(field - kunci)
        tambahan = sorted(kunci - field)
        raise ValueError(
            f"field {jenis} tidak tepat; hilang={hilang}, tambahan={tambahan}"
        )


def _bilangan_bulat(nilai: Any, nama: str, minimum: int, maksimum: int) -> int:
    if type(nilai) is not int or not minimum <= nilai <= maksimum:
        raise ValueError(f"{nama} wajib bilangan bulat {minimum}..{maksimum}")
    return nilai


def _nama_sah(nilai: Any) -> str:
    if (
        not isinstance(nilai, str)
        or not nilai.strip()
        or len(nilai) > PANJANG_NAMA_MAKS
        or any(huruf in _KURUNG_MARKUP for huruf in nilai)
        or any(unicodedata.category(huruf).startswith("C") for huruf in nilai)
    ):
        raise ValueError("nama baris adegan tidak valid")
    return nilai


def _ikon_sah(nilai: Any) -> str:
    if not isinstance(nilai, str) or nilai not in IKON_DIDUKUNG:
        raise ValueError("ikon adegan tidak ada di allow-list")
    return nilai


def _baris_tunggal(isi: Any, indeks: int) -> tuple:
    if not isinstance(isi, Mapping):
        raise ValueError(f"baris[{indeks}] wajib berupa mapping")
    _field_tepat(isi, _FIELD_BARIS, f"baris[{indeks}]")
    nama = _nama_sah(isi["nama"])
    _ikon_sah(isi["ikon"])
    _bilangan_bulat(isi["jumlah"], f"baris[{indeks}].jumlah", JUMLAH_MIN, JUMLAH_MAKS)
    return nama


def _daftar_baris(nilai: Any) -> int:
    """Validasi daftar baris; kembalikan banyaknya."""
    if not isinstance(nilai, (list, tuple)):
        raise ValueError("baris adegan wajib berupa daftar")
    if not BARIS_MIN <= len(nilai) <= BARIS_MAKS:
        raise ValueError(f"adegan wajib memiliki {BARIS_MIN}..{BARIS_MAKS} baris")
    nama = tuple(_baris_tunggal(isi, i) for i, isi in enumerate(nilai))
    if len({isi.strip().casefold() for isi in nama}) != len(nama):
        raise ValueError("nama baris adegan tidak boleh duplikat")
    return len(nama)


def _indeks(nilai: Any, nama: str, banyak: int) -> int:
    return _bilangan_bulat(nilai, nama, 0, banyak - 1)


def _validasi_tanya(tanya: Any, banyak: int) -> None:
    if not isinstance(tanya, Mapping):
        raise ValueError("tanya adegan wajib berupa mapping")
    varian = tanya.get("varian")
    if not isinstance(varian, str) or varian not in VARIAN_TANYA:
        raise ValueError(f"varian tanya tidak didukung: {varian!r}")
    if varian == "terbanyak":
        _field_tepat(tanya, {"varian"}, "tanya")
    elif varian == "baca":
        _field_tepat(tanya, {"varian", "i"}, "tanya")
        _indeks(tanya["i"], "tanya.i", banyak)
    else:
        _field_tepat(tanya, {"varian", "x", "y"}, "tanya")
        x = _indeks(tanya["x"], "tanya.x", banyak)
        y = _indeks(tanya["y"], "tanya.y", banyak)
        if x == y:
            raise ValueError("tanya.x dan tanya.y wajib berbeda")


def validasi_adegan_awal(data: Mapping[str, Any]) -> None:
    """Validasi allow-list descriptor adegan awal v1; gagal tertutup."""
    if not isinstance(data, Mapping):
        raise ValueError("data descriptor wajib berupa mapping")
    _field_tepat(data, _FIELD_ADEGAN, "adegan_awal")
    adegan = data["adegan"]
    if not isinstance(adegan, str) or adegan not in ADEGAN_DIDUKUNG:
        raise ValueError(f"adegan tidak didukung: {adegan!r}")
    banyak = _daftar_baris(data["baris"])
    if type(data["satuan_ikon"]) is not int or data["satuan_ikon"] != SATUAN_IKON_V1:
        raise ValueError(f"satuan_ikon v1 wajib {SATUAN_IKON_V1}")
    _validasi_tanya(data["tanya"], banyak)
