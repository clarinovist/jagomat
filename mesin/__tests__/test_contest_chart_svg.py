"""Grafik SVG Latihan Lomba: bentuk, batas nilai, determinisme, dan tanpa skrip/tautan/hex."""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import contest_chart_svg as G  # noqa: E402
import design_tokens as T  # noqa: E402

MESIN = Path(__file__).resolve().parent.parent


def _akar(isi):
    return ET.fromstring(isi)


def _anak(akar, nama):
    return [e for e in akar.iter() if e.tag == nama]


def test_grafik_sepuluh_nilai_adalah_svg_well_formed_dengan_peran_img_dan_label_netral():
    isi = G.grafik_nilai([3, 5, 7, 6, 8, 9, 4, 10, 0, 5])

    akar = _akar(isi)
    assert akar.tag == "svg" and akar.get("role") == "img"
    assert akar.get("aria-label") == "Grafik garis nilai 10 sesi latihan, skala 0 sampai 10, dari sesi 1 sampai sesi 10"


def test_setiap_titik_membawa_data_nilai_sesuai_urutan_masuk():
    akar = _akar(G.grafik_nilai([3, 5, 7]))

    titik = _anak(akar, "circle")

    assert [t.get("data-nilai") for t in titik] == ["3", "5", "7"]
    assert [t.find("title").text for t in titik] == ["Sesi 1: nilai 3", "Sesi 2: nilai 5", "Sesi 3: nilai 7"]


def test_garis_menghubungkan_semua_titik_dan_nilai_tinggi_berada_di_atas():
    akar = _akar(G.grafik_nilai([0, 10]))

    garis = _anak(akar, "polyline")[0].get("points").split()
    y_awal, y_akhir = (float(p.split(",")[1]) for p in garis)

    assert len(garis) == 2 and y_akhir < y_awal


def test_nilai_nol_berada_di_garis_dasar_dan_sepuluh_di_garis_atas_sumbu():
    akar = _akar(G.grafik_nilai([0, 10]))

    pusat_y = [float(c.get("cy")) for c in _anak(akar, "circle")]
    garis_y = sorted(float(g.get("y1")) for g in _anak(akar, "line"))

    assert pusat_y == [garis_y[-1], garis_y[0]]


def test_sumbu_punya_label_nol_lima_sepuluh_dan_label_nomor_sesi():
    akar = _akar(G.grafik_nilai([1, 2, 3]))

    teks = [t.text for t in _anak(akar, "text")]

    assert teks[:3] == ["0", "5", "10"] and teks[3:] == ["1", "2", "3"]
    assert len(_anak(akar, "line")) == 3


def test_satu_titik_digambar_di_tengah_tanpa_garis():
    akar = _akar(G.grafik_nilai([7]))

    titik = _anak(akar, "circle")

    assert len(titik) == 1 and not _anak(akar, "polyline")
    assert float(titik[0].get("cx")) == pytest.approx((G._KIRI + G._KANAN) / 2)


def test_tiga_puluh_titik_label_sesi_dijarangkan_agar_tidak_bertumpuk():
    akar = _akar(G.grafik_nilai([i % 11 for i in range(30)]))

    label_sesi = [t.text for t in _anak(akar, "text")][3:]

    assert len(_anak(akar, "circle")) == 30 and label_sesi == ["1", "4", "7", "10", "13", "16", "19", "22", "25", "28"]


def test_nomor_awal_menggeser_label_dan_judul_titik():
    akar = _akar(G.grafik_nilai([4, 6], nomor_awal=41))

    assert [t.text for t in _anak(akar, "text")][3:] == ["41", "42"]
    assert _anak(akar, "circle")[0].find("title").text == "Sesi 41: nilai 4"
    assert "dari sesi 41 sampai sesi 42" in akar.get("aria-label")


def test_tanpa_titik_menghasilkan_pesan_kosong_bukan_svg():
    isi = G.grafik_nilai([])

    assert "<svg" not in isi and G.PESAN_KOSONG in isi


@pytest.mark.parametrize("nilai", [[-1], [11], [3, 12], [2.5], ["5"], [True]])
def test_nilai_di_luar_nol_sampai_sepuluh_atau_bukan_bilangan_bulat_ditolak(nilai):
    with pytest.raises(ValueError):
        G.grafik_nilai(nilai)


@pytest.mark.parametrize("maks", [0, -3, True, 2.5])
def test_maks_tidak_sah_ditolak(maks):
    with pytest.raises(ValueError):
        G.grafik_nilai([1], maks)


def test_nilai_di_batas_maks_khusus_diterima_dan_label_sumbu_mengikuti():
    akar = _akar(G.grafik_nilai([20, 0], maks=20))

    assert [t.text for t in _anak(akar, "text")][:3] == ["0", "10", "20"]


def test_keluaran_deterministik_untuk_masukan_sama():
    assert G.grafik_nilai([3, 8, 5]) == G.grafik_nilai([3, 8, 5])


def test_grafik_tanpa_skrip_tautan_penangan_kejadian_atau_hex_literal():
    isi = G.grafik_nilai([3, 8, 5]) + G.bar_persen(2, 3, "Bilangan: 2 dari 3 benar")

    assert "<script" not in isi and "<a " not in isi and "href" not in isi and "http" not in isi
    assert not re.search(r"\son[a-z]+\s*=", isi, re.I)
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b(?!;)", re.sub(r"fill=\"#[0-9a-fA-F]+\"|stroke=\"#[0-9a-fA-F]+\"", "", isi))


def test_warna_grafik_berasal_dari_token_desain():
    isi = G.grafik_nilai([3, 8])

    assert f'stroke="{T.ANAK_AKSEN}"' in isi and f'fill="{T.ANAK_AKSEN}"' in isi and f'stroke="{T.ANAK_BORDER_PIL}"' in isi


def test_bar_persen_lebar_isi_sebanding_dan_label_di_escape():
    akar = _akar(G.bar_persen(2, 3, 'A "<b>" & B'))

    isi_bar = [r for r in _anak(akar, "rect") if r.get("data-benar")][0]

    assert isi_bar.get("width") == "66" and isi_bar.get("data-total") == "3"
    assert akar.get("aria-label") == 'A "<b>" & B' and akar.get("role") == "img"


@pytest.mark.parametrize("benar,total,lebar", [(0, 3, "0"), (3, 3, "100"), (0, 0, "0")])
def test_bar_persen_batas_nol_penuh_dan_total_nol(benar, total, lebar):
    akar = _akar(G.bar_persen(benar, total, "x"))

    assert [r for r in _anak(akar, "rect") if r.get("data-benar")][0].get("width") == lebar


@pytest.mark.parametrize("benar,total", [(4, 3), (-1, 3), (1, -1)])
def test_bar_persen_nilai_tidak_masuk_akal_ditolak(benar, total):
    with pytest.raises(ValueError):
        G.bar_persen(benar, total, "x")


def test_sumber_grafik_tanpa_hex_literal():
    sumber = (MESIN / "contest_chart_svg.py").read_text(encoding="utf-8")

    assert not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", sumber)
