"""Pembantu SVG Latihan Lomba: jam analog yang tepat, pembungkus aman, tanpa warna hex literal."""
import re
from pathlib import Path

import pytest

import contest_core as C
import contest_svg_common as S


def test_sudut_jarum_pendek_ada_di_antara_dua_angka_saat_menit_bukan_nol():
    # 08.30: jarum pendek tepat di tengah angka 8 dan 9 (255 derajat), jarum panjang di angka 6.
    assert S.sudut_jarum(8, 30) == (255.0, 180.0)


@pytest.mark.parametrize("jam,menit,sudut_jam,sudut_menit", [
    (12, 0, 0.0, 0.0),
    (0, 0, 0.0, 0.0),
    (3, 0, 90.0, 0.0),
    (9, 0, 270.0, 0.0),
    (15, 30, 105.0, 180.0),
    (11, 30, 345.0, 180.0),
    (5, 15, 157.5, 90.0),
    (6, 40, 200.0, 240.0),
])
def test_sudut_jarum_tabel(jam, menit, sudut_jam, sudut_menit):
    assert S.sudut_jarum(jam, menit) == (sudut_jam, sudut_menit)


@pytest.mark.parametrize("jam,menit", [(-1, 0), (24, 0), (1, -1), (1, 60), (1.5, 0)])
def test_sudut_jarum_menolak_waktu_tidak_sah(jam, menit):
    with pytest.raises(ValueError):
        S.sudut_jarum(jam, menit)


def test_bungkus_menghasilkan_svg_yang_lolos_validasi_inti():
    svg = S.bungkus(S.garis(0, 0, 10, 10), 100, 50, "Gambar garis")
    C.validasi_svg(svg)
    assert 'viewBox="0 0 100 50"' in svg


def test_bungkus_meloloskan_alt_berangka_ke_validasi_inti_yang_menolaknya():
    svg = S.bungkus("", 100, 50, "Ada 15 benda")
    with pytest.raises(ValueError):
        C.validasi_svg(svg)


def test_teks_di_svg_di_escape():
    hasil = S.teks(5, 5, "a<b & c")
    assert "<b" not in hasil and "&lt;" in hasil and "&amp;" in hasil


def test_jam_analog_memuat_dua_jarum_dua_belas_angka_dan_lolos_validasi():
    svg = S.bungkus(S.jam_analog(100, 100, 80, 8, 30), 200, 200, "Jam analog")
    C.validasi_svg(svg)
    assert svg.count('data-jarum="jam"') == 1 and svg.count('data-jarum="menit"') == 1
    for angka in range(1, 13):
        assert f">{angka}</text>" in svg


def test_jam_analog_jarum_pendek_lebih_pendek_dari_jarum_panjang():
    svg = S.jam_analog(100, 100, 80, 3, 0)
    pendek = re.search(r'data-jarum="jam"[^>]*?x2="([\d.]+)" y2="([\d.]+)"', svg)
    panjang = re.search(r'data-jarum="menit"[^>]*?x2="([\d.]+)" y2="([\d.]+)"', svg)
    jarak = lambda m: ((float(m.group(1)) - 100) ** 2 + (float(m.group(2)) - 100) ** 2) ** 0.5
    assert jarak(pendek) < jarak(panjang)


def test_kartu_angka_memuat_teksnya():
    assert ">407<" in S.kartu_angka(0, 0, "407")


def test_grid_titik_menata_baris_demi_baris():
    titik = S.grid_titik(5, 3, 10, 20, 30, 40)
    assert titik == [(10, 20), (40, 20), (70, 20), (10, 60), (40, 60)]


def test_modul_svg_bersama_tanpa_warna_hex_literal():
    sumber = (Path(__file__).resolve().parent.parent / "contest_svg_common.py").read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", sumber)
