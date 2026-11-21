"""Proyeksi keluarga visual `matematika-awal`: teks soal + descriptor `adegan_awal`.

Empat jenis: `baca_diagram_gambar` (deret_ikon), `turus_gambar_awal` (turus),
`ukur_satuan_tak_baku` (pita_ukur), dan `kenali_bangun_awal` (bentuk; proyektornya di
`topic_matematika_awal_bentuk_visual`, `benda_ruang` sengaja tetap teks). Kunci, pilihan ganda, dan malrule tetap milik
soal sumber; gambar menjadi satu-satunya sumber nilai, jadi teks proyeksi membuang
semua angka dan baris data. Kalimat pertanyaan DIAMBIL dari teks soal sumber,
tidak disalin; bila bentuk teks sumber berubah proyeksi gagal keras (ValueError).
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Callable, Optional, Tuple

import awal_baca_diagram_gambar as sumber
import awal_turus_gambar_awal as sumber_turus
import awal_kenali_bangun_awal as sumber_bangun
import awal_ukur_satuan_tak_baku as sumber_ukur
from adegan_awal_data import IKON_DIDUKUNG
from topic_matematika_awal_bentuk_visual import proyeksi_kenali_bangun
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
FIELD_SKALA = "skala"  # hanya soal P2; soal P1 tidak punya field ini sama sekali


def _field_parameter(parameter: Mapping[str, Any]) -> str:
    """Himpunan field persis: P1 tanpa `skala`, P2 dengan `skala` (nilainya diperiksa soal sumber)."""
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in _FIELD_TAMBAHAN:
        raise ValueError(f"varian baca diagram gambar tidak didukung: {varian!r}")
    field = _FIELD_DASAR | _FIELD_TAMBAHAN[varian]
    if FIELD_SKALA in parameter:
        field = field | {FIELD_SKALA}
    if set(parameter) != field:
        hilang = sorted(field - set(parameter))
        tambahan = sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter baca_diagram_gambar/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}"
        )
    return varian


def _benda_per_gambar(parameter: Mapping[str, Any]) -> int:
    """Skala soal (benda per gambar); 1 untuk soal P1 yang tanpa field skala."""
    return parameter.get(FIELD_SKALA, 1)


def _soal_sumber(parameter: Mapping[str, Any]):
    """Validasi domain lewat soal sumber (tipe int murni, tema, skala, jumlah berbeda)."""
    soal = sumber.baca_diagram_gambar(**dict(parameter))
    baris = soal.teks.split("\n")
    kata = sumber.TEMA[parameter["tema"]][1]
    kepala_harapan = f"Satu titik hitam mewakili {_benda_per_gambar(parameter)} {kata}."
    if len(baris) != BARIS_TEKS_SUMBER or not baris[0].endswith(kepala_harapan):
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
        "satuan_ikon": _benda_per_gambar(parameter),
        "tanya": _tanya(parameter, varian),
    }


def _teks(parameter: Mapping[str, Any], soal) -> str:
    kata = sumber.TEMA[parameter["tema"]][1]
    pertanyaan = soal.teks.split("\n")[-1]
    return (f"Perhatikan gambar. Satu gambar mewakili {_benda_per_gambar(parameter)} {kata}."
            f"\n{pertanyaan}")


# ── turus_gambar_awal ────────────────────────────────────────────────────

BARIS_TEKS_TURUS = 5  # pengantar + tiga baris turus + pertanyaan
_BARIS_DATA_TURUS = re.compile(r"[|\s]+")
_ANGKA_ATAU_TURUS = re.compile(r"[0-9|]")


def _periksa_field(parameter: Mapping[str, Any], per_varian: Mapping[str, tuple], nama: str) -> str:
    """Varian dikenal dan himpunan field persis sama dengan milik soal sumber."""
    varian = parameter.get("varian")
    if not isinstance(varian, str) or varian not in per_varian:
        raise ValueError(f"varian {nama} tidak didukung: {varian!r}")
    field = {"varian", *per_varian[varian]}
    if set(parameter) != field:
        hilang = sorted(field - set(parameter))
        tambahan = sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter {nama}/{varian} tidak tepat; hilang={hilang}, tambahan={tambahan}"
        )
    return varian


def _soal_turus(parameter: Mapping[str, Any]):
    """Validasi domain lewat soal sumber, lalu pastikan bentuk teksnya masih yang diketahui."""
    soal = sumber_turus.turus_gambar_awal(**dict(parameter))
    baris = soal.teks.split("\n")
    nama = sumber_turus.TEMA[parameter["tema"]].nama
    berubah = len(baris) != BARIS_TEKS_TURUS or any(
        not isinstance(isi, str) or not isi.startswith(f"{kategori}: ")
        or not _BARIS_DATA_TURUS.fullmatch(isi[len(kategori) + 2:])
        for isi, kategori in zip(baris[1:-1], nama)
    )
    if berubah:
        raise ValueError("bentuk teks soal sumber berubah; proyeksi perlu disesuaikan")
    return soal


def _tanya_turus(parameter: Mapping[str, Any], varian: str) -> dict:
    if varian == "baca":
        return {"varian": varian, "i": parameter["tanya"]}
    if varian == "selisih":
        return {"varian": varian, "x": parameter["besar"], "y": parameter["kecil"]}
    return {"varian": varian}


def _data_turus(parameter: Mapping[str, Any], varian: str) -> dict:
    nama = sumber_turus.TEMA[parameter["tema"]].nama
    return {
        "adegan": "turus",
        "baris": [{"nama": kategori, "jumlah": jumlah}
                  for kategori, jumlah in zip(nama, parameter["jumlah"])],
        "tanya": _tanya_turus(parameter, varian),
    }


def _teks_turus(parameter: Mapping[str, Any], soal) -> str:
    pertanyaan = soal.teks.split("\n")[-1]
    if _ANGKA_ATAU_TURUS.search(pertanyaan):
        raise ValueError("kalimat pertanyaan turus memuat angka atau garis; proyeksi perlu disesuaikan")
    satuan = sumber_turus.TEMA[parameter["tema"]].satuan
    return (f"Perhatikan gambar turus. Satu garis berarti satu {satuan}, tiap lima garis "
            f"dikelompokkan dengan coretan miring.\n{pertanyaan}")


def _proyeksi_turus(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _periksa_field(parameter, sumber_turus.FIELD, "turus_gambar_awal")
    soal = _soal_turus(parameter)
    descriptor = DescriptorVisual("adegan_awal", 1, _data_turus(parameter, varian))
    return _teks_turus(parameter, soal), descriptor


# ── ukur_satuan_tak_baku ─────────────────────────────────────────────────

_FIELD_UKUR = {
    "banding": ("satuan", "benda", "benda2", "p1", "p2"),
    "selisih": ("satuan", "benda", "benda2", "p1", "p2"),
    "sambung": ("satuan", "benda", "p1", "p2"),
}
_KALIMAT_DATA_UKUR = re.compile(
    r"([A-Z][a-z ]*) panjangnya ([0-9]+) (?:" + "|".join(sumber_ukur.SATUAN) + r")\. "
)
KALIMAT_DATA_UKUR = 2  # dua benda, masing-masing satu kalimat panjang


def _pecah_teks_ukur(teks: str) -> Tuple[tuple, str]:
    """Pisahkan dua kalimat data ((nama, panjang), ...) dari sisa teks (narasi + pertanyaan)."""
    sisa, data = teks, []
    for _ in range(KALIMAT_DATA_UKUR):
        cocok = _KALIMAT_DATA_UKUR.match(sisa)
        if cocok is None:
            raise ValueError("bentuk teks soal sumber berubah; proyeksi perlu disesuaikan")
        data.append((cocok[1], int(cocok[2])))
        sisa = sisa[cocok.end():]
    return tuple(data), sisa


def _batang_ukur(parameter: Mapping[str, Any], varian: str) -> list:
    if varian == "sambung":
        benda = sumber_ukur.BENDA_SAMBUNG[parameter["benda"]]
        nama = [f"{benda} {warna}" for warna in sumber_ukur.WARNA_SAMBUNG]
        return [{"nama": n, "ikon": None, "warna": warna, "jumlah": jumlah}
                for n, warna, jumlah in zip(nama, sumber_ukur.WARNA_SAMBUNG,
                                            (parameter["p1"], parameter["p2"]))]
    daftar = sumber_ukur.BENDA_BANDING[parameter["satuan"]]
    pasangan = ((daftar[parameter["benda"]], parameter["p1"]),
                (daftar[parameter["benda2"]], parameter["p2"]))
    return [{"nama": n, "ikon": _ikon_benda(n), "warna": "netral", "jumlah": jumlah}
            for n, jumlah in pasangan]


def _ikon_benda(nama: str) -> str:
    if nama not in IKON_DIDUKUNG:
        raise ValueError(f"benda tanpa ikon: {nama!r}")
    return nama


def _tanya_ukur(parameter: Mapping[str, Any], varian: str) -> dict:
    if varian == "selisih":
        panjang = 0 if parameter["p1"] > parameter["p2"] else 1
        return {"varian": varian, "x": panjang, "y": 1 - panjang}
    return {"varian": varian}


def _data_ukur(parameter: Mapping[str, Any], varian: str) -> dict:
    return {
        "adegan": "pita_ukur",
        "satuan": parameter["satuan"],
        "batang": _batang_ukur(parameter, varian),
        "susun": "sambung" if varian == "sambung" else "bertumpuk",
        "tanya": _tanya_ukur(parameter, varian),
    }


def _kapital(kata: str) -> str:
    return kata[:1].upper() + kata[1:]


def _pola_sisa_ukur(parameter: Mapping[str, Any], varian: str, data: dict) -> str:
    """Bentuk kalimat yang tersisa (narasi sumber + pertanyaan) per varian; nama dari data gambar."""
    satuan = re.escape(parameter["satuan"])
    if varian == "banding":
        return r"Mana yang lebih panjang\?"
    if varian == "sambung":
        benda = re.escape(sumber_ukur.BENDA_SAMBUNG[parameter["benda"]])
        return rf"Kedua {benda} disambung ujung ke ujung\. Berapa {satuan} panjang semuanya\?"
    nama = [isi["nama"] for isi in data["batang"]]
    panjang, pendek = nama[data["tanya"]["x"]], nama[data["tanya"]["y"]]
    return rf"{re.escape(_kapital(panjang))} lebih panjang berapa {satuan} daripada {re.escape(pendek)}\?"


def _teks_ukur(parameter: Mapping[str, Any], varian: str, soal, data: dict) -> str:
    """Narasi tanpa angka + sisa kalimat soal sumber; nama dan panjang di teks harus sama dengan gambar."""
    kalimat_data, sisa = _pecah_teks_ukur(soal.teks)
    harapan = tuple((_kapital(isi["nama"]), isi["jumlah"]) for isi in data["batang"])
    if kalimat_data != harapan or not re.fullmatch(_pola_sisa_ukur(parameter, varian, data), sisa):
        raise ValueError("bentuk teks soal sumber berubah; proyeksi perlu disesuaikan")
    return f"Perhatikan gambar. Benda diukur dengan {parameter['satuan']}.\n{sisa}"


def _proyeksi_ukur(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _periksa_field(parameter, _FIELD_UKUR, "ukur_satuan_tak_baku")
    soal = sumber_ukur.ukur_satuan_tak_baku(**dict(parameter))
    data = _data_ukur(parameter, varian)
    teks = _teks_ukur(parameter, varian, soal, data)
    return teks, DescriptorVisual("adegan_awal", 1, data)


# ── pintu masuk ──────────────────────────────────────────────────────────

def _proyeksi_diagram_gambar(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _field_parameter(parameter)
    soal = _soal_sumber(parameter)
    descriptor = DescriptorVisual("adegan_awal", 1, _data(parameter, varian))
    return _teks(parameter, soal), descriptor


_PROYEKTOR: dict = {
    TEMPLATE_DIDUKUNG: _proyeksi_diagram_gambar,
    sumber_turus.TEMPLATE_ID: _proyeksi_turus,
    sumber_ukur.TEMPLATE_ID: _proyeksi_ukur,
    sumber_bangun.TEMPLATE_ID: proyeksi_kenali_bangun,
}


def proyeksi_matematika_awal(
    template_id: str, parameter: Mapping[str, Any]
) -> Optional[Tuple[str, DescriptorVisual]]:
    """Proyeksikan jenis bergambar keluarga ini; None untuk jenis lain."""
    if not isinstance(template_id, str):
        raise ValueError("template_id wajib berupa teks")
    if not isinstance(parameter, Mapping):
        raise ValueError("parameter wajib berupa mapping")
    proyektor: Optional[Callable] = _PROYEKTOR.get(template_id)
    if proyektor is None:
        return None
    return proyektor(parameter)
