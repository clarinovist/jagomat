"""Descriptor `adegan_awal` v1: sub-adegan `turus` dan `pita_ukur` (validator) + oracle helper.

Validator menolak field tambahan/hilang, ikon di luar allow-list, markup, nama
duplikat, angka di luar batas, dan pasangan susunan-tanya yang tidak konsisten.
Bagian akhir membuktikan perluasan helper keamanan/batas (`image` + rotate) tidak
melonggarkan elemen atau putaran lain.
"""
from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adegan_awal_data as data_modul
from adegan_awal_data import IKON_DIDUKUNG, validasi_adegan_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import DescriptorVisual
from visual_security_helpers import periksa_xml


def _turus(**ubah):
    dasar = {
        "adegan": "turus",
        "baris": [{"nama": "Apel", "jumlah": 7}, {"nama": "Jeruk", "jumlah": 3},
                  {"nama": "Pisang", "jumlah": 12}],
        "tanya": {"varian": "baca", "i": 1},
    }
    return {**dasar, **ubah}


def _ukur(**ubah):
    dasar = {
        "adegan": "pita_ukur", "satuan": "klip", "susun": "bertumpuk",
        "batang": [{"nama": "pensil", "ikon": "pensil", "warna": "netral", "jumlah": 9},
                   {"nama": "buku", "ikon": "buku", "warna": "netral", "jumlah": 6}],
        "tanya": {"varian": "banding"},
    }
    return {**dasar, **ubah}


def _sambung(**ubah):
    dasar = {
        "adegan": "pita_ukur", "satuan": "ubin", "susun": "sambung",
        "batang": [{"nama": "pita merah", "ikon": None, "warna": "merah", "jumlah": 7},
                   {"nama": "pita biru", "ikon": None, "warna": "biru", "jumlah": 5}],
        "tanya": {"varian": "sambung"},
    }
    return {**dasar, **ubah}


def _dengan(data, bagian, indeks, **ubah):
    daftar = [dict(isi) for isi in data[bagian]]
    daftar[indeks] = {**daftar[indeks], **ubah}
    return daftar


def _tolak(data):
    with pytest.raises(ValueError):
        validasi_adegan_awal(data)
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)


# ── dispatcher ───────────────────────────────────────────────────────────

def test_tiga_adegan_terdaftar_dan_masing_masing_sah():
    assert data_modul.ADEGAN_DIDUKUNG == ("deret_ikon", "turus", "pita_ukur")
    for data in (_turus(), _ukur(), _sambung()):
        validasi_adegan_awal(data)
        DescriptorVisual("adegan_awal", 1, data)


@pytest.mark.parametrize("adegan", ("deret_titik", "Turus", "pita", None, 3, ["turus"], ""))
def test_nama_adegan_tak_dikenal_ditolak(adegan):
    _tolak(_turus(adegan=adegan))


def test_field_antar_adegan_tidak_boleh_tercampur():
    _tolak({**_turus(), "satuan_ikon": 1})
    _tolak({**_turus(), "satuan": "klip"})
    _tolak({**_ukur(), "baris": []})
    _tolak({**_ukur(), "satuan_ikon": 1})


def test_bentuk_beku_juga_lolos_jalur_renderer():
    for data in (_turus(), _ukur(), _sambung()):
        validasi_adegan_awal(DescriptorVisual("adegan_awal", 1, data).data)


# ── turus ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("tanya", (
    {"varian": "baca", "i": 2}, {"varian": "terbanyak"}, {"varian": "jumlah"},
    {"varian": "selisih", "x": 2, "y": 0},
))
def test_turus_semua_bentuk_tanya_sah(tanya):
    validasi_adegan_awal(_turus(tanya=tanya))


@pytest.mark.parametrize("tanya", (
    {"varian": "jumlah", "x": 0, "y": 1}, {"varian": "jumlah", "x": 0},
    {"varian": "baca"}, {"varian": "baca", "i": 3}, {"varian": "terbanyak", "i": 0},
    {"varian": "selisih", "x": 1, "y": 1}, {"varian": "selisih", "x": 0},
    {"varian": "lain"}, {"varian": None}, {}, None, "baca",
))
def test_turus_tanya_tidak_sah_ditolak(tanya):
    _tolak(_turus(tanya=tanya))


@pytest.mark.parametrize("jumlah", (1, 2, 5, 11, 12))
def test_turus_jumlah_dalam_rentang_diterima(jumlah):
    validasi_adegan_awal(_turus(baris=_dengan(_turus(), "baris", 0, jumlah=jumlah)))


@pytest.mark.parametrize("jumlah", (0, -1, 13, 100, 3.0, "3", True, None))
def test_turus_jumlah_di_luar_satu_sampai_dua_belas_atau_bukan_int_murni_ditolak(jumlah):
    _tolak(_turus(baris=_dengan(_turus(), "baris", 0, jumlah=jumlah)))


@pytest.mark.parametrize("nama", (
    "<b>Apel</b>", "Apel<", "", "  ", "W" * 25, "Ap\x00el", "Ap‮el", "Ap​el", None, 3,
))
def test_turus_nama_markup_kontrol_atau_terlalu_panjang_ditolak(nama):
    _tolak(_turus(baris=_dengan(_turus(), "baris", 0, nama=nama)))


def test_turus_nama_duplikat_ditolak_termasuk_beda_huruf_besar():
    _tolak(_turus(baris=_dengan(_turus(), "baris", 1, nama="apel")))


@pytest.mark.parametrize("banyak", (0, 1, 5))
def test_turus_banyak_baris_di_luar_dua_sampai_empat_ditolak(banyak):
    baris = [{"nama": f"K{i}", "jumlah": 1} for i in range(5)]
    _tolak(_turus(baris=baris[:banyak], tanya={"varian": "terbanyak"}))


@pytest.mark.parametrize("field", ("kunci", "jawaban", "ikon", "satuan_ikon", "svg", "extra"))
def test_turus_field_tambahan_apa_pun_ditolak_termasuk_ikon(field):
    _tolak({**_turus(), field: "uji"})
    _tolak(_turus(baris=_dengan(_turus(), "baris", 0, **{field: "uji"})))
    _tolak(_turus(tanya={"varian": "terbanyak", field: "uji"}))


@pytest.mark.parametrize("hapus", ("adegan", "baris", "tanya"))
def test_turus_field_hilang_ditolak(hapus):
    _tolak({k: v for k, v in _turus().items() if k != hapus})


@pytest.mark.parametrize("hapus", ("nama", "jumlah"))
def test_turus_field_baris_hilang_ditolak(hapus):
    baris = _turus()["baris"]
    baris[0] = {k: v for k, v in baris[0].items() if k != hapus}
    _tolak(_turus(baris=baris))


def test_turus_baris_bukan_daftar_atau_bukan_mapping_ditolak():
    _tolak(_turus(baris="Apel"))
    _tolak(_turus(baris=None))
    _tolak(_turus(baris=[["Apel", 3], ["Jeruk", 4]]))


# ── pita_ukur ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("satuan", data_modul.SATUAN_UKUR)
def test_ukur_tiga_satuan_sah_dan_punya_ikon(satuan):
    validasi_adegan_awal(_ukur(satuan=satuan))
    assert satuan in IKON_DIDUKUNG


@pytest.mark.parametrize("satuan", ("cm", "Klip", "klip ", "", None, 3, ["klip"], "maskot"))
def test_ukur_satuan_di_luar_tiga_ditolak(satuan):
    _tolak(_ukur(satuan=satuan))


@pytest.mark.parametrize("tanya", (
    {"varian": "banding"}, {"varian": "selisih", "x": 0, "y": 1},
    {"varian": "selisih", "x": 1, "y": 0},
))
def test_ukur_tanya_sah_untuk_bertumpuk(tanya):
    validasi_adegan_awal(_ukur(tanya=tanya))


@pytest.mark.parametrize("tanya", (
    {"varian": "sambung"}, {"varian": "jumlah"}, {"varian": "banding", "x": 0},
    {"varian": "selisih"}, {"varian": "selisih", "x": 0, "y": 0},
    {"varian": "selisih", "x": 0, "y": 2}, {"varian": "selisih", "x": True, "y": 1},
    {"varian": "selisih", "x": "0", "y": 1}, {}, None, "banding",
))
def test_ukur_tanya_tidak_sah_untuk_bertumpuk_ditolak(tanya):
    _tolak(_ukur(tanya=tanya))


@pytest.mark.parametrize("tanya", (
    {"varian": "banding"}, {"varian": "selisih", "x": 0, "y": 1}, {"varian": "sambung", "x": 0},
    {"varian": "sambung", "extra": 1}, {},
))
def test_ukur_tanya_tidak_sah_untuk_sambung_ditolak(tanya):
    _tolak(_sambung(tanya=tanya))


def test_ukur_susunan_dan_banyak_batang_diperiksa():
    _tolak(_ukur(susun="berjajar"))
    _tolak(_ukur(susun=None))
    _tolak(_ukur(batang=_ukur()["batang"][:1]))
    _tolak(_ukur(batang=_ukur()["batang"] * 2))
    _tolak(_ukur(batang=[]))
    _tolak(_ukur(batang="pensil"))


@pytest.mark.parametrize("jumlah", (1, 3, 12))
def test_ukur_jumlah_dalam_rentang_diterima(jumlah):
    validasi_adegan_awal(_ukur(batang=_dengan(_ukur(), "batang", 0, jumlah=jumlah)))


@pytest.mark.parametrize("jumlah", (0, -1, 13, 2.0, "3", True, None))
def test_ukur_jumlah_di_luar_satu_sampai_dua_belas_ditolak(jumlah):
    _tolak(_ukur(batang=_dengan(_ukur(), "batang", 1, jumlah=jumlah)))


@pytest.mark.parametrize("ikon", (
    "../pensil", "pensil.png", "/aset/ikon-pensil-v1.webp", "PENSIL", "pensil ", "",
    "maskot", "http://contoh.invalid/a", 3, ["pensil"], "pe\x00nsil",
))
def test_ukur_ikon_benda_di_luar_allow_list_ditolak_tetapi_none_boleh(ikon):
    _tolak(_ukur(batang=_dengan(_ukur(), "batang", 0, ikon=ikon)))
    validasi_adegan_awal(_ukur(batang=_dengan(_ukur(), "batang", 0, ikon=None)))


@pytest.mark.parametrize("warna", ("hijau", "Merah", "", None, 1, ["biru"]))
def test_ukur_warna_di_luar_tiga_ditolak(warna):
    _tolak(_ukur(batang=_dengan(_ukur(), "batang", 0, warna=warna)))


@pytest.mark.parametrize("nama", ("<b>x</b>", "pensil<", "", "  ", "w" * 25, "pe\x00", None, 3))
def test_ukur_nama_markup_kontrol_atau_terlalu_panjang_ditolak(nama):
    _tolak(_ukur(batang=_dengan(_ukur(), "batang", 0, nama=nama)))


def test_ukur_nama_duplikat_ditolak_termasuk_beda_huruf_besar():
    _tolak(_ukur(batang=_dengan(_ukur(), "batang", 1, nama="PENSIL")))


@pytest.mark.parametrize("field", ("kunci", "jawaban", "label", "satuan_ikon", "extra"))
def test_ukur_field_tambahan_ditolak(field):
    _tolak({**_ukur(), field: "uji"})
    _tolak(_ukur(batang=_dengan(_ukur(), "batang", 0, **{field: "uji"})))


@pytest.mark.parametrize("hapus", ("adegan", "satuan", "batang", "susun", "tanya"))
def test_ukur_field_hilang_ditolak(hapus):
    _tolak({k: v for k, v in _ukur().items() if k != hapus})


@pytest.mark.parametrize("hapus", ("nama", "ikon", "warna", "jumlah"))
def test_ukur_field_batang_hilang_ditolak(hapus):
    batang = _ukur()["batang"]
    batang[0] = {k: v for k, v in batang[0].items() if k != hapus}
    _tolak(_ukur(batang=batang))


def test_sambung_wajib_dua_warna_berbeda_selain_netral_dan_tanpa_ikon_benda():
    _tolak(_sambung(batang=_dengan(_sambung(), "batang", 1, warna="merah")))
    _tolak(_sambung(batang=_dengan(_sambung(), "batang", 0, warna="netral")))
    _tolak(_sambung(batang=_dengan(_sambung(), "batang", 0, ikon="pensil")))
    validasi_adegan_awal(_sambung(batang=[
        {"nama": "pita biru", "ikon": None, "warna": "biru", "jumlah": 2},
        {"nama": "pita merah", "ikon": None, "warna": "merah", "jumlah": 3}]))


def test_bertumpuk_boleh_berwarna_atau_tanpa_ikon_benda():
    batang = [{"nama": "a", "ikon": None, "warna": "merah", "jumlah": 2},
              {"nama": "b", "ikon": None, "warna": "biru", "jumlah": 3}]
    validasi_adegan_awal(_ukur(batang=batang))


# ── oracle helper: perluasan `image` + rotate tidak melonggarkan hal lain ─

def _svg_ikon(isi, kotak="0 0 100 100"):
    """Lewat oracle keamanan penuh (`periksa_xml`)."""
    teks = f'<div><svg xmlns="http://www.w3.org/2000/svg" viewBox="{kotak}">{isi}</svg></div>'
    return periksa_xml(teks)


def _svg_mentah(isi, kotak="0 0 100 100"):
    """Hanya parse XML: untuk menguji oracle batas tanpa disaring oracle keamanan lebih dulu."""
    return ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{kotak}">{isi}</svg>')


def _image(transform="", x=10, y=10, lebar=20, tinggi=20, href="/aset/ikon-klip-v1.webp"):
    putar = f' transform="{transform}"' if transform else ""
    return (f'<image href="{href}" x="{x}" y="{y}" width="{lebar}" height="{tinggi}"{putar}/>')


def test_oracle_rotate_90_di_pusat_image_persegi_diterima():
    for sudut in (90, -90, 180, 270):
        periksa_batas_koordinat(_svg_ikon(_image(f"rotate({sudut} 20 20)")))


@pytest.mark.parametrize("isi", (
    _image("rotate(45 20 20)"),                       # sudut bukan kelipatan 90
    _image("rotate(90 25 20)"),                       # pusat bukan pusat ikon
    _image("rotate(90 20 20)", lebar=20, tinggi=10),  # bukan persegi
    _image("rotate(90 20 20) translate(2)"),          # rotasi dicampur transform lain
    _image("rotate(90)"),                             # tanpa pusat
))
def test_oracle_putaran_image_lain_tetap_gagal_di_oracle_batas(isi):
    with pytest.raises(AssertionError):
        periksa_batas_koordinat(_svg_mentah(isi))


@pytest.mark.parametrize("isi", (
    '<rect x="10" y="10" width="20" height="20" transform="rotate(90 20 20)"/>',
    '<g transform="rotate(90 20 20)"><rect x="10" y="10" width="20" height="20"/></g>',
    '<line x1="10" y1="10" x2="30" y2="30" transform="rotate(90 20 20)"/>',
    '<text x="10" y="10" transform="rotate(90 20 20)">A</text>',
))
def test_oracle_rotate_pada_elemen_selain_image_tetap_gagal(isi):
    with pytest.raises(AssertionError):
        periksa_batas_koordinat(_svg_mentah(isi))


def test_oracle_image_persegi_diputar_tetap_dicek_batas_viewbox():
    akar = _svg_mentah(_image("rotate(90 95 20)", x=85, y=10))
    with pytest.raises(AssertionError, match="di luar viewBox"):
        periksa_batas_koordinat(akar)


@pytest.mark.parametrize("transform", (
    "rotate(45 20 20)", "scale(2)", "translate(2)", "rotate(90)",
    "rotate(90 20 20) rotate(90 20 20)", "rotate(90 20 20);", "rotate(91 20 20)",
))
def test_oracle_keamanan_menolak_transform_image_selain_putar_kelipatan_90(transform):
    with pytest.raises(AssertionError):
        _svg_ikon(_image(transform))


def test_oracle_keamanan_menerima_putar_90_dan_menolak_transform_pada_elemen_lain():
    _svg_ikon(_image("rotate(90 20 20)"))
    _svg_ikon(_image("rotate(90 20.5 20.5)", x=10, y=10, lebar=21, tinggi=21))
    with pytest.raises(AssertionError):
        _svg_ikon('<rect width="3" height="3" transform="rotate(90 1 1)"/>')


def test_oracle_keamanan_image_tetap_hanya_href_ikon_terdaftar():
    with pytest.raises(AssertionError):
        _svg_ikon(_image(href="https://contoh.invalid/a.png"))
    with pytest.raises(AssertionError):
        _svg_ikon(_image(href="/aset/ikon-hantu-v1.webp"))
