"""Validator ketat descriptor `adegan_awal` v1 (Matematika Awal).

Tiga sub-adegan, dipilih lewat field `adegan`: `deret_ikon` (baris ikon benda),
`turus` (garis turus per kategori), dan `pita_ukur` (batang ukur dari ikon satuan).
Descriptor hanya memuat data aman untuk menggambar: nama baris/batang, nama ikon
dari allow-list, banyak elemen, dan jenis pertanyaan. Kunci atau jawaban TIDAK
PERNAH masuk descriptor; banyak elemen adalah fakta gambar, bukan jawaban.
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
ADEGAN_DIDUKUNG = ("deret_ikon", "turus", "pita_ukur")
BARIS_MIN, BARIS_MAKS = 2, 4
JUMLAH_MIN, JUMLAH_MAKS = 0, 12
PANJANG_NAMA_MAKS = 24
SATUAN_IKON_V1 = 1
VARIAN_TANYA = ("baca", "terbanyak", "selisih", "jumlah")
TURUS_MIN, TURUS_MAKS = 1, 12
SATUAN_UKUR = ("klip", "ubin", "balok")
WARNA_BATANG = ("netral", "merah", "biru")
SUSUN_BATANG = ("bertumpuk", "sambung")
BATANG_BANYAK = 2
UKUR_MIN, UKUR_MAKS = 1, 12
# Susunan -> varian tanya yang sah: bertumpuk membandingkan, sambung menjumlah.
_TANYA_UKUR = {"bertumpuk": ("banding", "selisih"), "sambung": ("sambung",)}

_KURUNG_MARKUP = frozenset("<>")
_FIELD_ADEGAN = {"adegan", "baris", "satuan_ikon", "tanya"}
_FIELD_BARIS = {"nama", "ikon", "jumlah"}
_FIELD_TURUS = {"adegan", "baris", "tanya"}
_FIELD_BARIS_TURUS = {"nama", "jumlah"}
_FIELD_UKUR = {"adegan", "satuan", "batang", "susun", "tanya"}
_FIELD_BATANG = {"nama", "ikon", "warna", "jumlah"}


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


def _nama_unik(nama: tuple) -> None:
    if len({isi.strip().casefold() for isi in nama}) != len(nama):
        raise ValueError("nama baris adegan tidak boleh duplikat")


def _daftar_baris(nilai: Any, baris_fn=_baris_tunggal) -> int:
    """Validasi daftar baris; kembalikan banyaknya."""
    if not isinstance(nilai, (list, tuple)):
        raise ValueError("baris adegan wajib berupa daftar")
    if not BARIS_MIN <= len(nilai) <= BARIS_MAKS:
        raise ValueError(f"adegan wajib memiliki {BARIS_MIN}..{BARIS_MAKS} baris")
    nama = tuple(baris_fn(isi, i) for i, isi in enumerate(nilai))
    _nama_unik(nama)
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


def _validasi_deret_ikon(data: Mapping[str, Any]) -> None:
    _field_tepat(data, _FIELD_ADEGAN, "adegan_awal")
    banyak = _daftar_baris(data["baris"])
    if type(data["satuan_ikon"]) is not int or data["satuan_ikon"] != SATUAN_IKON_V1:
        raise ValueError(f"satuan_ikon v1 wajib {SATUAN_IKON_V1}")
    _validasi_tanya(data["tanya"], banyak)


# ── sub-adegan `turus` ───────────────────────────────────────────────────

def _baris_turus(isi: Any, indeks: int) -> str:
    if not isinstance(isi, Mapping):
        raise ValueError(f"baris[{indeks}] wajib berupa mapping")
    _field_tepat(isi, _FIELD_BARIS_TURUS, f"baris[{indeks}]")
    _bilangan_bulat(isi["jumlah"], f"baris[{indeks}].jumlah", TURUS_MIN, TURUS_MAKS)
    return _nama_sah(isi["nama"])


def _validasi_tanya_turus(tanya: Any, banyak: int) -> None:
    """`jumlah` pada turus berarti semua baris, jadi tanpa x/y (beda dengan deret_ikon)."""
    if isinstance(tanya, Mapping) and tanya.get("varian") == "jumlah":
        _field_tepat(tanya, {"varian"}, "tanya")
        return
    _validasi_tanya(tanya, banyak)


def _validasi_turus(data: Mapping[str, Any]) -> None:
    _field_tepat(data, _FIELD_TURUS, "adegan_awal/turus")
    banyak = _daftar_baris(data["baris"], _baris_turus)
    _validasi_tanya_turus(data["tanya"], banyak)


# ── sub-adegan `pita_ukur` ───────────────────────────────────────────────

def _batang_tunggal(isi: Any, indeks: int) -> tuple:
    """Validasi satu batang; kembalikan (nama, ikon, warna)."""
    if not isinstance(isi, Mapping):
        raise ValueError(f"batang[{indeks}] wajib berupa mapping")
    _field_tepat(isi, _FIELD_BATANG, f"batang[{indeks}]")
    nama = _nama_sah(isi["nama"])
    if isi["ikon"] is not None:
        _ikon_sah(isi["ikon"])
    warna = isi["warna"]
    if not isinstance(warna, str) or warna not in WARNA_BATANG:
        raise ValueError(f"warna batang tidak didukung: {warna!r}")
    _bilangan_bulat(isi["jumlah"], f"batang[{indeks}].jumlah", UKUR_MIN, UKUR_MAKS)
    return nama, isi["ikon"], warna


def _daftar_batang(nilai: Any) -> tuple:
    if not isinstance(nilai, (list, tuple)) or len(nilai) != BATANG_BANYAK:
        raise ValueError(f"pita_ukur wajib memiliki tepat {BATANG_BANYAK} batang")
    batang = tuple(_batang_tunggal(isi, i) for i, isi in enumerate(nilai))
    _nama_unik(tuple(nama for nama, _, _ in batang))
    return batang


def _validasi_tanya_ukur(tanya: Any, susun: str) -> None:
    if not isinstance(tanya, Mapping):
        raise ValueError("tanya adegan wajib berupa mapping")
    varian = tanya.get("varian")
    if not isinstance(varian, str) or varian not in _TANYA_UKUR[susun]:
        raise ValueError(f"varian tanya tidak cocok dengan susunan {susun!r}: {varian!r}")
    if varian != "selisih":
        _field_tepat(tanya, {"varian"}, "tanya")
        return
    _field_tepat(tanya, {"varian", "x", "y"}, "tanya")
    x = _indeks(tanya["x"], "tanya.x", BATANG_BANYAK)
    if x == _indeks(tanya["y"], "tanya.y", BATANG_BANYAK):
        raise ValueError("tanya.x dan tanya.y wajib berbeda")


def _validasi_susunan_batang(susun: str, batang: tuple) -> None:
    """Sambung: potongan berbeda warna (selain netral) dan tanpa ikon benda yang tak digambar."""
    if susun != "sambung":
        return
    warna = tuple(w for _, _, w in batang)
    if "netral" in warna or warna[0] == warna[1]:
        raise ValueError("susunan sambung wajib dua warna berbeda selain netral")
    if any(ikon is not None for _, ikon, _ in batang):
        raise ValueError("susunan sambung tidak memakai ikon benda")


def _validasi_pita_ukur(data: Mapping[str, Any]) -> None:
    _field_tepat(data, _FIELD_UKUR, "adegan_awal/pita_ukur")
    satuan, susun = data["satuan"], data["susun"]
    if not isinstance(satuan, str) or satuan not in SATUAN_UKUR:
        raise ValueError(f"satuan ukur tidak didukung: {satuan!r}")
    if not isinstance(susun, str) or susun not in SUSUN_BATANG:
        raise ValueError(f"susunan batang tidak didukung: {susun!r}")
    batang = _daftar_batang(data["batang"])
    _validasi_susunan_batang(susun, batang)
    _validasi_tanya_ukur(data["tanya"], susun)


_VALIDATOR = {
    "deret_ikon": _validasi_deret_ikon,
    "turus": _validasi_turus,
    "pita_ukur": _validasi_pita_ukur,
}


def validasi_adegan_awal(data: Mapping[str, Any]) -> None:
    """Validasi allow-list descriptor adegan awal v1; gagal tertutup."""
    if not isinstance(data, Mapping):
        raise ValueError("data descriptor wajib berupa mapping")
    adegan = data.get("adegan")
    if not isinstance(adegan, str) or adegan not in ADEGAN_DIDUKUNG:
        raise ValueError(f"adegan tidak didukung: {adegan!r}")
    _VALIDATOR[adegan](data)
