"""Proyeksi visual jenis `kenali_bangun_awal` (keluarga `matematika-awal`): teks + descriptor `bentuk`.

Tiga varian bergambar (`datar_gambar`, `ruang_gambar`, `hitung_bentuk`) memakai descriptor
`adegan_awal` v1 sub-adegan `bentuk`; teks proyeksi MEMBUANG semua ciri, daftar, dan nama
bangun jawaban ("Perhatikan gambar. Bangun datar apa ini?"). `benda_ruang` sengaja teks
saja: proyeksi hanya memvalidasi parameter lalu mengembalikan None (teks lama). Kunci,
pilihan ganda, dan malrule tetap milik soal sumber. Kalimat pertanyaan DIAMBIL dari teks soal
sumber dan diperiksa; bila bentuknya berubah proyeksi gagal keras (ValueError).
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Tuple

import awal_kenali_bangun_awal as sumber
import bentuk_katalog as K
from visual_contract import DescriptorVisual

_FIELD_GAMBAR = ("bangun", "ragam", "putar", "ukuran", "warna")
_FIELD = {
    "datar_gambar": _FIELD_GAMBAR, "ruang_gambar": _FIELD_GAMBAR,
    "benda_ruang": ("bangun", "benda"), "hitung_bentuk": ("banyak", "tanya", "tata"),
}
_PERTANYAAN = {"datar_gambar": "Bangun datar apa ini?", "ruang_gambar": "Bangun ruang apa ini?"}
_PENGANTAR = "Perhatikan gambar."
UKURAN_BARIS = "besar"  # semua bangun pada baris hitung berukuran sama agar hitungan jujur
PESAN_BERUBAH = "bentuk teks soal sumber berubah; proyeksi perlu disesuaikan"


def _periksa_field(parameter: Mapping[str, Any]) -> str:
    """Varian dikenal dan himpunan field persis sama dengan milik soal sumber."""
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in _FIELD:
        raise ValueError(f"varian kenali_bangun_awal tidak didukung: {varian!r}")
    field = {"varian", "himpunan", *_FIELD[varian]}
    if set(parameter) != field:
        hilang, tambahan = sorted(field - set(parameter)), sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter kenali_bangun_awal/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}")
    return varian


def _soal_sumber(parameter: Mapping[str, Any]):
    """Validasi domain lewat soal sumber (tipe murni, himpunan, jumlah, tanya)."""
    return sumber.kenali_bangun_awal(**dict(parameter))


def _item(parameter: Mapping[str, Any]) -> dict:
    return {"nama": parameter["bangun"], "ragam": parameter["ragam"],
            "putar": parameter["putar"], "ukuran": parameter["ukuran"],
            "warna": parameter["warna"]}


def _ragam_hitung(nama: str, kali: int, tata: int) -> tuple:
    """(ragam, putar) deterministik bangun ke-`kali` jenis itu pada tata tertentu (variasi gambar)."""
    ragam, putar = K.RAGAM[nama], K.PUTAR[nama]
    return ragam[(kali + tata) % len(ragam)], putar[(kali + 2 * tata) % len(putar)]


def _item_baris(parameter: Mapping[str, Any]) -> list:
    himpunan, tata = parameter["himpunan"], parameter["tata"]
    nama = sumber.nama_berurutan(himpunan, parameter["banyak"], tata)
    dilihat, hasil = {}, []
    for jenis in nama:
        kali = dilihat.get(jenis, 0)
        dilihat[jenis] = kali + 1
        ragam, putar = _ragam_hitung(jenis, kali, tata)
        hasil.append({"nama": jenis, "ragam": ragam, "putar": putar,
                      "ukuran": UKURAN_BARIS, "warna": K.WARNA[tata]})
    return hasil


def _pertanyaan_hitung(parameter: Mapping[str, Any]) -> str:
    return f"Berapa banyak {K.DATAR_HIMPUNAN[parameter['himpunan']][parameter['tanya']]}"


def _teks(varian: str, parameter: Mapping[str, Any], soal) -> str:
    """Pengantar + pertanyaan; baris pertanyaan sumber harus persis bentuk yang diketahui."""
    baris = soal.teks.split("\n")
    if varian == "hitung_bentuk":
        pertanyaan = _pertanyaan_hitung(parameter)
        if len(baris) != 2 or baris[-1] != f"{pertanyaan}?":
            raise ValueError(PESAN_BERUBAH)
        return f"{_PENGANTAR}\n{pertanyaan} pada gambar?"
    if len(baris) != 2 or baris[-1] != _PERTANYAAN[varian]:
        raise ValueError(PESAN_BERUBAH)
    return f"{_PENGANTAR}\n{_PERTANYAAN[varian]}"


def proyeksi_kenali_bangun(parameter: Mapping[str, Any]) -> Optional[Tuple[str, DescriptorVisual]]:
    """Teks + descriptor untuk varian bergambar; None untuk `benda_ruang` (teks lama)."""
    varian = _periksa_field(parameter)
    soal = _soal_sumber(parameter)
    if varian == "benda_ruang":
        return None
    if varian == "hitung_bentuk":
        data = {"adegan": "bentuk", "tampil": "baris", "bangun": _item_baris(parameter)}
    else:
        data = {"adegan": "bentuk", "tampil": "satu", "bangun": [_item(parameter)]}
    return _teks(varian, parameter, soal), DescriptorVisual("adegan_awal", 1, data)
