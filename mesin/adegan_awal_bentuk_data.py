"""Validator ketat sub-adegan `bentuk` dari descriptor `adegan_awal` v1 (Matematika Awal).

Descriptor menggambar bangun datar atau bangun ruang buatan kode (SVG, bukan raster):
`{"adegan": "bentuk", "tampil": "satu" | "baris", "bangun": [ {nama, ragam, putar, ukuran,
warna}, ... ]}`. `satu` = tepat satu bangun, datar atau ruang. `baris` = 1 sampai 10 bangun,
SEMUANYA datar (bangun ruang tidak dihitung per elemen). Semua nilai berasal dari allow-list
di `bentuk_katalog`; field tambahan ditolak. Jawaban TIDAK PERNAH ada di descriptor selain
bangun yang memang harus digambar; banyak elemen adalah fakta gambar, bukan jawaban.

Dipanggil lewat `adegan_awal_data.validasi_adegan_awal` (impor malas agar tidak melingkar).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import bentuk_katalog as K
from adegan_awal_data import _field_tepat

TAMPIL_DIDUKUNG = ("satu", "baris")
BANGUN_MIN, BANGUN_MAKS = 1, 10
_FIELD = {"adegan", "tampil", "bangun"}
_FIELD_BANGUN = {"nama", "ragam", "putar", "ukuran", "warna"}


def _pilihan(nilai: Any, pilihan: tuple, nama: str) -> None:
    """Nilai harus bertipe sama dengan allow-list (bool tidak lolos sebagai int) dan ada di dalamnya."""
    if type(nilai) is not type(pilihan[0]) or nilai not in pilihan:
        raise ValueError(f"{nama} bangun tidak ada di allow-list: {nilai!r}")


def _bangun_tunggal(isi: Any, indeks: int) -> str:
    """Validasi satu bangun; kembalikan jenisnya (`datar` atau `ruang`)."""
    if not isinstance(isi, Mapping):
        raise ValueError(f"bangun[{indeks}] wajib berupa mapping")
    _field_tepat(isi, _FIELD_BANGUN, f"bangun[{indeks}]")
    nama = isi["nama"]
    if type(nama) is not str or nama not in K.SEMUA_NAMA:
        raise ValueError(f"nama bangun tidak ada di allow-list: {nama!r}")
    _pilihan(isi["ragam"], K.RAGAM[nama], "ragam")
    _pilihan(isi["putar"], K.PUTAR[nama], "putar")
    _pilihan(isi["ukuran"], K.UKURAN, "ukuran")
    _pilihan(isi["warna"], K.WARNA, "warna")
    return K.jenis_bangun(nama)


def _daftar_bangun(nilai: Any, tampil: str) -> None:
    if not isinstance(nilai, (list, tuple)):
        raise ValueError("bangun adegan wajib berupa daftar")
    banyak = len(nilai)
    if tampil == "satu" and banyak != 1:
        raise ValueError("tampil satu wajib memuat tepat satu bangun")
    if not BANGUN_MIN <= banyak <= BANGUN_MAKS:
        raise ValueError(f"adegan bentuk wajib memuat {BANGUN_MIN}..{BANGUN_MAKS} bangun")
    jenis = tuple(_bangun_tunggal(isi, i) for i, isi in enumerate(nilai))
    if tampil == "baris" and K.JENIS_RUANG in jenis:
        raise ValueError("baris bangun hanya boleh memuat bangun datar")


def validasi_bentuk(data: Mapping[str, Any]) -> None:
    """Validasi allow-list descriptor `bentuk`; gagal tertutup."""
    _field_tepat(data, _FIELD, "adegan_awal/bentuk")
    tampil = data["tampil"]
    if type(tampil) is not str or tampil not in TAMPIL_DIDUKUNG:
        raise ValueError(f"tampil bentuk tidak didukung: {tampil!r}")
    _daftar_bangun(data["bangun"], tampil)
