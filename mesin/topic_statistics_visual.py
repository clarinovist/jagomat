"""Proyeksi parameter template statistika ke teks dan descriptor visual."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Tuple

from statistics_visual_data import validasi_data
from visual_contract import DescriptorVisual


def _field_parameter(
    parameter: Mapping[str, Any], field: set[str], template_id: str, varian: str
) -> None:
    if set(parameter) != field:
        hilang = sorted(field - set(parameter))
        tambahan = sorted(set(parameter) - field)
        raise ValueError(
            f"field parameter {template_id}/{varian} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}"
        )


def _descriptor(jenis: str, data: dict[str, Any]) -> DescriptorVisual:
    validasi_data(jenis, data)
    return DescriptorVisual(jenis, 1, data)


def _proyeksi_batang(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = parameter.get("varian")
    if not isinstance(varian, str):
        raise ValueError("varian diagram batang wajib berupa teks")
    if varian == "baca":
        _field_parameter(parameter, {"varian", "data", "i"}, "diagram_batang_garis", varian)
        indeks = parameter["i"]
    elif varian == "jumlah":
        _field_parameter(parameter, {"varian", "data"}, "diagram_batang_garis", varian)
        indeks = 0
    elif varian == "selisih":
        _field_parameter(parameter, {"varian", "data", "i"}, "diagram_batang_garis", varian)
        indeks = parameter["i"]
    else:
        raise ValueError(f"varian diagram batang tidak didukung: {varian!r}")

    data = parameter["data"]
    if not isinstance(data, (list, tuple)):
        raise ValueError("data batang wajib berupa daftar")
    banyak = len(data)
    if not 3 <= banyak <= 6:
        raise ValueError("batang wajib memiliki 3..6 kategori sejajar")
    nama = tuple(f"B{i + 1}" for i in range(banyak))
    descriptor = _descriptor(
        "batang",
        {"nama": nama, "data": data, "varian": varian, "i": indeks},
    )
    if varian == "baca":
        teks = f"Perhatikan diagram batang. Berapa nilai {nama[indeks]}?"
    elif varian == "jumlah":
        teks = "Perhatikan diagram batang. Berapa jumlah seluruh nilai?"
    else:
        berikut = (indeks + 1) % banyak
        teks = (
            "Perhatikan diagram batang. Berapa selisih "
            f"{nama[indeks]} dan {nama[berikut]}?"
        )
    return teks, descriptor


def _proyeksi_turus(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = parameter.get("varian")
    if not isinstance(varian, str):
        raise ValueError("varian tabel turus wajib berupa teks")
    if varian == "baca":
        field = {"varian", "nama", "data", "i"}
        indeks = parameter.get("i")
    elif varian in {"terbanyak", "jumlah"}:
        field = {"varian", "nama", "data"}
        indeks = 0
    else:
        raise ValueError(f"varian tabel turus tidak didukung: {varian!r}")
    _field_parameter(parameter, field, "tabel_turus", varian)
    descriptor = _descriptor(
        "turus",
        {
            "nama": parameter["nama"],
            "data": parameter["data"],
            "varian": varian,
            "i": indeks,
        },
    )
    if varian == "baca":
        teks = f"Perhatikan tabel turus. Berapa banyak {parameter['nama'][indeks]}?"
    elif varian == "terbanyak":
        teks = "Perhatikan tabel turus. Yang paling banyak adalah?"
    else:
        teks = "Perhatikan tabel turus. Berapa jumlah seluruhnya?"
    return teks, descriptor


def _proyeksi_piktogram(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = parameter.get("varian")
    if not isinstance(varian, str):
        raise ValueError("varian piktogram wajib berupa teks")
    dasar = {"varian", "satuan", "gambar", "nama"}
    if varian in {"baca", "selisih"}:
        field = dasar | {"i"}
        indeks = parameter.get("i")
    elif varian == "total":
        field = dasar
        indeks = 0
    else:
        raise ValueError(f"varian piktogram tidak didukung: {varian!r}")
    _field_parameter(parameter, field, "piktogram", varian)
    descriptor = _descriptor(
        "piktogram",
        {
            "nama": parameter["nama"],
            "gambar": parameter["gambar"],
            "satuan": parameter["satuan"],
            "varian": varian,
            "i": indeks,
        },
    )
    awalan = "Perhatikan piktogram."
    if varian == "baca":
        teks = f"{awalan}\nBerapa buah {parameter['nama'][indeks]}?"
    elif varian == "total":
        teks = f"{awalan}\nBerapa buah seluruhnya?"
    else:
        berikut = (indeks + 1) % len(parameter["nama"])
        teks = (
            f"{awalan}\nBerapa selisih {parameter['nama'][indeks]} dan "
            f"{parameter['nama'][berikut]}?"
        )
    return teks, descriptor


def _proyeksi_lingkaran(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = parameter.get("varian")
    if not isinstance(varian, str):
        raise ValueError("varian diagram lingkaran wajib berupa teks")
    if varian == "cari_nilai":
        _field_parameter(
            parameter, {"varian", "s", "total"}, "diagram_lingkaran", varian
        )
        data = {
            "varian": varian,
            "total": parameter["total"],
            "sudut": parameter["s"],
        }
        descriptor = _descriptor("lingkaran", data)
        teks = (
            f"Diagram lingkaran menunjukkan data {parameter['total']} siswa.\n"
            "Berapa siswa pada bagian olahraga?"
        )
        return teks, descriptor
    if varian == "cari_sudut":
        _field_parameter(
            parameter,
            {"varian", "s", "total", "nilai"},
            "diagram_lingkaran",
            varian,
        )
        data = {
            "varian": varian,
            "total": parameter["total"],
            "nilai": parameter["nilai"],
        }
        descriptor = _descriptor("lingkaran", data)
        sudut = parameter["nilai"] * 360 // parameter["total"]
        if type(parameter["s"]) is not int or parameter["s"] != sudut:
            raise ValueError("parameter s cari_sudut tidak cocok dengan nilai dan total")
        teks = (
            f"Diagram lingkaran menunjukkan data {parameter['total']} siswa.\n"
            "Berapa sudut bagian membaca?"
        )
        return teks, descriptor
    raise ValueError(f"varian diagram lingkaran tidak didukung: {varian!r}")


_PROYEKTOR = {
    "diagram_batang_garis": _proyeksi_batang,
    "tabel_turus": _proyeksi_turus,
    "piktogram": _proyeksi_piktogram,
    "diagram_lingkaran": _proyeksi_lingkaran,
}


def proyeksi_statistika(
    template_id: str, parameter: Mapping[str, Any]
) -> Optional[Tuple[str, DescriptorVisual]]:
    """Proyeksikan template statistika visual; None untuk keluarga lain."""
    if not isinstance(template_id, str):
        raise ValueError("template_id wajib berupa teks")
    if not isinstance(parameter, Mapping):
        raise ValueError("parameter wajib berupa mapping")
    proyektor = _PROYEKTOR.get(template_id)
    if proyektor is None:
        return None
    from catalog_versions import parameter_visual
    parameter = parameter_visual(template_id, parameter, {"diagram_batang_garis", "tabel_turus", "piktogram"})
    return proyektor(parameter)
