"""Proyeksi parameter template geometri datar ke descriptor visual."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Tuple

from plane_geometry_visual_data import validasi_data
from visual_contract import DescriptorVisual


def _field_parameter(
    parameter: Mapping[str, Any], wajib: set[str], opsional: set[str], template_id: str
) -> None:
    kunci = set(parameter)
    if any(not isinstance(nama, str) for nama in kunci):
        raise ValueError(f"field parameter {template_id} wajib memakai kunci teks")
    if not wajib <= kunci or kunci - wajib - opsional:
        hilang = sorted(wajib - kunci)
        tambahan = sorted(kunci - wajib - opsional)
        raise ValueError(
            f"field parameter {template_id} tidak tepat; "
            f"hilang={hilang}, tambahan={tambahan}"
        )


def _varian(parameter: Mapping[str, Any], template_id: str) -> str:
    nilai = parameter.get("varian")
    if not isinstance(nilai, str):
        raise ValueError(f"varian {template_id} wajib berupa teks")
    return nilai


def _hasil(teks: str, data: dict[str, Any]) -> Tuple[str, DescriptorVisual]:
    validasi_data(data)
    return teks, DescriptorVisual("geometri_datar", 1, data)


def _sudut(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "sudut_pelurus_berpenyiku")
    if varian == "tiga_kali":
        _field_parameter(parameter, {"varian", "kali"}, set(), "sudut_pelurus_berpenyiku")
        return _hasil(
            "Perhatikan pasangan sudut pada diagram. Berapa besar sudut yang kecil?",
            {"model": "sudut_rasio", "kali": parameter["kali"]},
        )
    if varian not in {"pelurus", "penyiku", "balik_pelurus", "balik_penyiku"}:
        raise ValueError(f"varian sudut tidak didukung: {varian!r}")
    _field_parameter(parameter, {"varian", "x"}, set(), "sudut_pelurus_berpenyiku")
    total = 180 if "pelurus" in varian else 90
    teks = (
        "Perhatikan pasangan sudut pada diagram. Berapa besar sudut pelurusnya?"
        if varian == "pelurus"
        else "Perhatikan pasangan sudut pada diagram. Berapa besar sudut penyikunya?"
        if varian == "penyiku"
        else "Perhatikan pasangan sudut pada diagram. Berapa besar sudut yang belum diketahui?"
    )
    return _hasil(
        teks,
        {"model": "sudut_pasangan", "total": total, "diketahui": parameter["x"]},
    )


def _jumlah_sudut(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "jumlah_sudut_segitiga")
    if varian == "dua_sudut":
        _field_parameter(parameter, {"varian", "a", "b"}, set(), "jumlah_sudut_segitiga")
        data = {"model": "segitiga_sudut", "a": parameter["a"], "b": parameter["b"]}
        return _hasil("Perhatikan segitiga pada diagram. Berapa besar sudut yang ketiga?", data)
    if varian == "perbandingan":
        _field_parameter(parameter, {"varian", "p", "q", "r"}, set(), "jumlah_sudut_segitiga")
        data = {
            "model": "segitiga_rasio",
            "p": parameter["p"], "q": parameter["q"], "r": parameter["r"],
        }
        return _hasil("Perhatikan perbandingan sudut segitiga pada diagram. Berapa besar sudut terkecil?", data)
    raise ValueError(f"varian jumlah sudut tidak didukung: {varian!r}")


def _sudut_luar(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    _field_parameter(parameter, {"a", "b"}, set(), "sudut_luar_segitiga")
    return _hasil(
        "Perhatikan segitiga pada diagram. Berapa besar sudut luarnya?",
        {"model": "segitiga_luar", "a": parameter["a"], "b": parameter["b"]},
    )


def _persegi_panjang(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "keliling_luas_datar")
    if varian == "keliling":
        _field_parameter(parameter, {"varian", "p", "l"}, set(), "keliling_luas_datar")
        data = {"model": "persegi_panjang", "p": parameter["p"], "l": parameter["l"]}
        return _hasil("Perhatikan persegi panjang pada diagram. Berapa kelilingnya?", data)
    if varian == "balik_luas":
        _field_parameter(parameter, {"varian", "p", "K"}, set(), "keliling_luas_datar")
        data = {"model": "persegi_panjang_balik", "p": parameter["p"], "K": parameter["K"]}
        return _hasil("Perhatikan persegi panjang pada diagram. Berapa luasnya?", data)
    raise ValueError(f"varian persegi panjang tidak didukung: {varian!r}")


def _alas_tinggi(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "luas_segitiga_jajargenjang")
    _field_parameter(parameter, {"varian", "a", "t", "s"}, set(), "luas_segitiga_jajargenjang")
    if varian not in {"segitiga", "jajargenjang"}:
        raise ValueError(f"varian alas tinggi tidak didukung: {varian!r}")
    model = "segitiga_tinggi" if varian == "segitiga" else "jajargenjang"
    nama = "segitiga" if varian == "segitiga" else "jajargenjang"
    data = {
        "model": model, "a": parameter["a"], "t": parameter["t"], "s": parameter["s"],
    }
    return _hasil(f"Perhatikan {nama} pada diagram. Berapa luasnya?", data)


def _segiempat(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "luas_segiempat_lain")
    if varian == "trapesium":
        _field_parameter(parameter, {"varian", "a", "b", "t"}, set(), "luas_segiempat_lain")
        data = {"model": "trapesium", "a": parameter["a"], "b": parameter["b"], "t": parameter["t"]}
        return _hasil("Perhatikan trapesium pada diagram. Berapa luasnya?", data)
    if varian == "ketupat_layang":
        _field_parameter(parameter, {"varian", "d1", "d2"}, set(), "luas_segiempat_lain")
        data = {"model": "ketupat", "d1": parameter["d1"], "d2": parameter["d2"]}
        return _hasil("Perhatikan belah ketupat pada diagram. Berapa luasnya?", data)
    if varian == "balik_diagonal":
        _field_parameter(parameter, {"varian", "L", "d1"}, set(), "luas_segiempat_lain")
        data = {"model": "ketupat_balik", "L": parameter["L"], "d1": parameter["d1"]}
        return _hasil("Perhatikan belah ketupat pada diagram. Berapa panjang diagonal yang belum diketahui?", data)
    raise ValueError(f"varian segiempat tidak didukung: {varian!r}")


def _lingkaran(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "lingkaran_keliling_luas")
    _field_parameter(parameter, {"varian", "r"}, set(), "lingkaran_keliling_luas")
    if varian not in {"keliling", "luas"}:
        raise ValueError(f"varian lingkaran tidak didukung: {varian!r}")
    pi = "22/7" if type(parameter["r"]) is int and parameter["r"] % 7 == 0 else "3,14"
    return _hasil(
        f"Perhatikan lingkaran pada diagram (π = {pi}). Berapa {varian}nya?",
        {"model": "lingkaran", "r": parameter["r"]},
    )


def _juring(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "juring")
    _field_parameter(parameter, {"varian", "s", "r"}, set(), "juring")
    if varian not in {"luas_juring", "keliling_juring"}:
        raise ValueError(f"varian juring tidak didukung: {varian!r}")
    pi = "22/7" if type(parameter["r"]) is int and parameter["r"] % 7 == 0 else "3,14"
    target = "luas" if varian == "luas_juring" else "keliling"
    return _hasil(
        f"Perhatikan juring pada diagram (π = {pi}). Berapa {target} juring itu?",
        {"model": "juring", "s": parameter["s"], "r": parameter["r"]},
    )


def _arsiran(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    varian = _varian(parameter, "luas_arsiran")
    if varian == "persegi_titik_tengah":
        _field_parameter(parameter, {"varian", "r"}, set(), "luas_arsiran")
        return _hasil(
            "Perhatikan daerah yang diarsir pada diagram (π = 22/7). Berapa luasnya?",
            {"model": "arsiran_pojok", "r": parameter["r"]},
        )
    if varian == "jalan_pinggir":
        _field_parameter(parameter, {"varian", "luar", "dalam"}, set(), "luas_arsiran")
        return _hasil(
            "Perhatikan jalan yang mengelilingi taman pada diagram. Berapa luas jalan itu?",
            {"model": "jalan", "luar": parameter["luar"], "dalam": parameter["dalam"]},
        )
    raise ValueError(f"varian arsiran tidak didukung: {varian!r}")


def _kisi(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    _field_parameter(parameter, {"p", "l", "satuan", "konteks"}, set(), "luas_kotak_satuan")
    data = {
        "model": "kisi", "p": parameter["p"], "l": parameter["l"],
        "satuan": parameter["satuan"],
    }
    return _hasil("Hitung seluruh kotak satuan pada diagram. Berapa luas persegi panjang itu?", data)


def _simetri(parameter: Mapping[str, Any]) -> Tuple[str, DescriptorVisual]:
    _field_parameter(
        parameter,
        {"bangun", "ukuran", "satuan", "warna", "lebar"},
        set(),
        "simetri_bangun",
    )
    bangun = parameter["bangun"]
    model = {
        "persegi": "simetri_persegi",
        "segitiga_sama_sisi": "simetri_segitiga",
        "belah_ketupat": "simetri_ketupat",
        "persegi_panjang": "simetri_persegi_panjang",
    }.get(bangun) if isinstance(bangun, str) else None
    if model is None:
        raise ValueError(f"bangun simetri tidak didukung: {bangun!r}")
    data = {"model": model, "ukuran": parameter["ukuran"], "satuan": parameter["satuan"]}
    if bangun == "persegi_panjang":
        lebar = parameter.get("lebar")
        if lebar is None:
            ukuran = parameter["ukuran"]
            if type(ukuran) is not int:
                raise ValueError("ukuran persegi panjang wajib bilangan bulat")
            lebar = max(2, ukuran // 2)
        data = {**data, "lebar": lebar}
    nama = bangun.replace("_", " ")
    return _hasil(f"Perhatikan {nama} pada diagram. Berapa banyak sumbu simetrinya?", data)


_PROYEKTOR = {
    "sudut_pelurus_berpenyiku": _sudut,
    "jumlah_sudut_segitiga": _jumlah_sudut,
    "sudut_luar_segitiga": _sudut_luar,
    "keliling_luas_datar": _persegi_panjang,
    "luas_segitiga_jajargenjang": _alas_tinggi,
    "luas_segiempat_lain": _segiempat,
    "lingkaran_keliling_luas": _lingkaran,
    "juring": _juring,
    "luas_arsiran": _arsiran,
    "luas_kotak_satuan": _kisi,
    "simetri_bangun": _simetri,
}


def proyeksi_geometri_datar(
    template_id: str, parameter: Mapping[str, Any]
) -> Optional[Tuple[str, DescriptorVisual]]:
    """Proyeksikan 11 template visual; keluarga lain tetap memakai teks."""
    if not isinstance(template_id, str):
        raise ValueError("template_id wajib berupa teks")
    if not isinstance(parameter, Mapping):
        raise ValueError("parameter wajib berupa mapping")
    proyektor = _PROYEKTOR.get(template_id)
    if proyektor is None:
        return None
    if "versi_katalog" in parameter:
        if type(parameter["versi_katalog"]) is not int or parameter["versi_katalog"] != 2:
            raise ValueError("versi katalog visual tidak didukung")
        if template_id not in {"lingkaran_keliling_luas", "juring", "luas_kotak_satuan"}:
            raise ValueError("template tidak mendukung versi katalog")
        parameter = {k: v for k, v in parameter.items() if k != "versi_katalog"}
        teks, descriptor = proyektor(parameter)
        if template_id in {"lingkaran_keliling_luas", "juring"}:
            from catalog_exact import PETUNJUK_EKSAK
            teks += PETUNJUK_EKSAK
        return teks, descriptor
    return proyektor(parameter)
