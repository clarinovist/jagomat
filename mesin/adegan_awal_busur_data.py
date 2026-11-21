"""Validator ketat sub-adegan `busur` dari descriptor `adegan_awal` v1 (Matematika Awal).

Descriptor menggambar busur derajat setengah lingkaran buatan kode (SVG, bukan raster) dengan dua
skala dan 2 sampai 3 sinar dari titik sudut di pusatnya:
`{"adegan": "busur", "pusat": "B" | "O", "sinar": [{"huruf": "A" | "B" | "C", "sudut": 0..180}, ...]}`.
`sudut` adalah arah sinar dalam derajat, dihitung dari sisi kanan garis alas berlawanan arah jarum
jam (0 = ujung kanan garis alas, 180 = ujung kiri). Itu FAKTA GAMBAR: besar sudut yang ditanya
(selisih dua arah) dan skala yang dipakai terbaca dari letak sinar, bukan tertulis di descriptor.
Arah kelipatan 5, huruf tidak kembar dan berbeda dari huruf pusat, dan tiap dua sinar berjarak
minimal 10 derajat supaya hurufnya tidak bertumpuk. Field tambahan ditolak.

Dipanggil lewat `adegan_awal_data.validasi_adegan_awal` (impor malas agar tidak melingkar).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from adegan_awal_data import _field_tepat

PUSAT_DIDUKUNG = ("B", "O")
HURUF_SINAR = ("A", "B", "C")
SINAR_MIN, SINAR_MAKS = 2, 3
SUDUT_MIN, SUDUT_MAKS, SUDUT_LANGKAH = 0, 180, 5
JARAK_SINAR_MIN = 10  # derajat antar dua sinar
_FIELD = {"adegan", "pusat", "sinar"}
_FIELD_SINAR = {"huruf", "sudut"}


def _sinar_tunggal(isi: Any, indeks: int) -> tuple:
    """Validasi satu sinar; kembalikan (huruf, sudut)."""
    if not isinstance(isi, Mapping):
        raise ValueError(f"sinar[{indeks}] wajib berupa mapping")
    _field_tepat(isi, _FIELD_SINAR, f"sinar[{indeks}]")
    huruf, sudut = isi["huruf"], isi["sudut"]
    if type(huruf) is not str or huruf not in HURUF_SINAR:
        raise ValueError(f"huruf sinar tidak ada di allow-list: {huruf!r}")
    if (type(sudut) is not int or not SUDUT_MIN <= sudut <= SUDUT_MAKS
            or sudut % SUDUT_LANGKAH):
        raise ValueError(
            f"sudut sinar wajib kelipatan {SUDUT_LANGKAH} antara {SUDUT_MIN}..{SUDUT_MAKS}: {sudut!r}")
    return huruf, sudut


def _daftar_sinar(nilai: Any, pusat: str) -> None:
    if not isinstance(nilai, (list, tuple)):
        raise ValueError("sinar adegan wajib berupa daftar")
    if not SINAR_MIN <= len(nilai) <= SINAR_MAKS:
        raise ValueError(f"adegan busur wajib memuat {SINAR_MIN}..{SINAR_MAKS} sinar")
    pasangan = tuple(_sinar_tunggal(isi, i) for i, isi in enumerate(nilai))
    huruf = [h for h, _ in pasangan]
    if len(set(huruf)) != len(huruf) or pusat in huruf:
        raise ValueError("huruf sinar tidak boleh kembar atau sama dengan huruf pusat")
    sudut = sorted(s for _, s in pasangan)
    if any(b - a < JARAK_SINAR_MIN for a, b in zip(sudut, sudut[1:])):
        raise ValueError(f"dua sinar wajib berjarak minimal {JARAK_SINAR_MIN} derajat")


def validasi_busur(data: Mapping[str, Any]) -> None:
    """Validasi allow-list descriptor `busur`; gagal tertutup (bool tidak lolos sebagai int)."""
    _field_tepat(data, _FIELD, "adegan_awal/busur")
    pusat = data["pusat"]
    if type(pusat) is not str or pusat not in PUSAT_DIDUKUNG:
        raise ValueError(f"pusat busur tidak didukung: {pusat!r}")
    _daftar_sinar(data["sinar"], pusat)
