"""Sub-adegan `tumpukan_kubus`: geometri gambar (batas, ukuran, label, lantai), keterbacaan anak, dan warna.

Keterbacaan diuji tanpa melihat jawaban: puncak tiap tumpukan tidak boleh tertimpa muka yang digambar
sesudahnya (jadi tak ada tumpukan yang hilang dari gambar), dan urutan lukis harus mengikuti kedalaman
untuk setiap dua kubus yang mukanya bertampalan. Pembaca gambar ada di `tumpukan_svg_helpers`.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import awal_tampak_kubus_awal as sumber
import design_tokens as T
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import proyeksi_matematika_awal
from tumpukan_svg_helpers import (data_adegan, kubus_berposisi, puncak_tertimpa, semua_titik, svg_dari_data,
                                  titik_path, tumpang_tindih, vektor_kubus)
from visual_renderer import render_pertanyaan
from visual_security_helpers import elemen, kelas, kontras, lokal, periksa_xml

TID = sumber.TEMPLATE_ID
CONTOH_KUBUS_3X3 = dict(varian="banyak_kubus", baris=3, kolom=3, tinggi=[0, 0, 0, 1, 1, 0, 3, 2, 1])
CONTOH_ATAS_2X3 = dict(varian="banyak_persegi_atas", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
CONTOH_DEPAN_3X3 = dict(varian="banyak_persegi_depan", baris=3, kolom=3, tinggi=[1, 0, 0, 2, 2, 1, 3, 3, 2])
CONTOH_SAMPING_2X3 = dict(varian="banyak_persegi_samping", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
CONTOH_KUBUS_2X2 = dict(varian="banyak_kubus", baris=2, kolom=2, tinggi=[1, 0, 3, 2])
CONTOH_DEPAN_3X2 = dict(varian="banyak_persegi_depan", baris=3, kolom=2, tinggi=[0, 0, 1, 0, 3, 2])
CONTOH = (CONTOH_KUBUS_3X3, CONTOH_ATAS_2X3, CONTOH_DEPAN_3X3, CONTOH_SAMPING_2X3, CONTOH_KUBUS_2X2,
          CONTOH_DEPAN_3X2)
NAMA_CONTOH = ("kubus_3x3", "atas_2x3", "depan_3x3", "samping_2x3", "kubus_2x2", "depan_3x2")


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _soal(parameter):
    return replace(sumber.tampak_kubus_awal(**parameter), level="P6")


def _penyajian(parameter):
    return penyajian_dari_soal(_soal(parameter))


def _html(parameter, *, namespace="uji-tumpukan", gaya="cetak"):
    return render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya)


def _svg(parameter, **kw):
    return periksa_xml(_html(parameter, **kw))


def _susunan_unik():
    """Satu parameter per susunan (gambar hanya bergantung pada alas dan tinggi, bukan varian)."""
    terlihat = {}
    for p in sumber.domain_parameter("P6"):
        terlihat.setdefault((p["baris"], p["kolom"], tuple(p["tinggi"])), p)
    return list(terlihat.values())


def _raw_param(parameter, namespace="uji"):
    import adegan_awal_svg
    _, descriptor = proyeksi_matematika_awal(TID, parameter)
    return adegan_awal_svg.render_adegan_awal(descriptor.data, namespace)


def _svg_param(parameter, namespace="uji"):
    return periksa_xml("<div>" + _raw_param(parameter, namespace) + "</div>")


def _viewbox(svg):
    return tuple(map(float, svg.get("viewBox").split()))


@pytest.mark.parametrize("parameter", CONTOH, ids=NAMA_CONTOH)
def test_semua_koordinat_dalam_viewbox_dan_label_tidak_terpotong(parameter):
    svg = _svg(parameter, namespace="batas")
    x0, y0, lebar, tinggi = _viewbox(svg)
    assert (x0, y0, lebar, tinggi) == (0, 0, T.ADEGAN_LEBAR, T.ADEGAN_TUMPUKAN_TINGGI)
    tepi = T.ADEGAN_TUMPUKAN_TEBAL / 2
    for x, y in semua_titik(svg):
        assert tepi <= x <= lebar - tepi and tepi <= y <= tinggi - tepi, (x, y)
    for e in elemen(svg, "text"):
        setengah = len("".join(e.itertext())) * float(e.get("font-size")) * 0.6 / 2
        x, y = float(e.get("x")), float(e.get("y"))
        assert x - setengah >= 0 and x + setengah <= lebar, "".join(e.itertext())
        assert float(e.get("font-size")) <= y <= tinggi


def test_seluruh_susunan_domain_dan_susunan_terbesar_muat_dalam_viewbox():
    kasus = [(p["baris"], p["kolom"], p["tinggi"]) for p in _susunan_unik()]
    kasus += [(3, 3, [3] * 9), (3, 3, [3, 0, 0, 3, 0, 0, 3, 0, 0]), (3, 3, [0, 0, 3, 0, 0, 3, 0, 0, 3]),
              (1, 3, [3, 3, 3]), (3, 1, [3, 3, 3]), (1, 1, [3])]
    tepi = T.ADEGAN_TUMPUKAN_TEBAL / 2
    for baris, kolom, tinggi in kasus:
        svg = svg_dari_data(data_adegan(tinggi, kolom), "muat")
        lebar, tinggi_vb = T.ADEGAN_LEBAR, T.ADEGAN_TUMPUKAN_TINGGI
        for x, y in semua_titik(svg):
            assert tepi <= x <= lebar - tepi and tepi <= y <= tinggi_vb - tepi, (baris, kolom, x, y)


def test_ukuran_kubus_konstan_untuk_semua_soal_dan_vektor_sesuai_token():
    for p in _susunan_unik()[::17]:
        svg = _svg_param(p, "ukuran")
        for kubus in kelas(svg, "kubus-satuan"):
            ex, ey, ez = vektor_kubus(kubus)
            assert ex == (T.ADEGAN_TUMPUKAN_LEBAR_MUKA, T.ADEGAN_TUMPUKAN_MIRING)
            assert ey == (T.ADEGAN_TUMPUKAN_LEBAR_MUKA, -T.ADEGAN_TUMPUKAN_MIRING)
            assert ez == (0, T.ADEGAN_TUMPUKAN_RUSUK)
    assert T.ADEGAN_TUMPUKAN_RUSUK == 2 * T.ADEGAN_TUMPUKAN_MIRING


def test_kubus_dirender_cukup_besar_dan_gambar_terpusat_menurut_alas():
    for baris, kolom in ((2, 2), (2, 3), (3, 2), (3, 3)):
        tinggi = [3] * (baris * kolom)
        svg = svg_dari_data(data_adegan(tinggi, kolom), "pusat")
        xs = [x for x, _ in semua_titik(svg)]
        assert abs((min(xs) + max(xs)) / 2 - T.ADEGAN_LEBAR / 2) < 1, (baris, kolom)
    assert T.ADEGAN_TUMPUKAN_LEBAR_MUKA >= 30 and T.ADEGAN_TUMPUKAN_RUSUK >= 36


def test_label_depan_dan_kanan_tepat_di_bawah_tepi_lantai_masing_masing_dan_tidak_bertumpuk():
    for baris, kolom in ((2, 2), (2, 3), (3, 2), (3, 3)):
        svg = svg_dari_data(data_adegan([3] * (baris * kolom), kolom), "label")
        label = {"".join(e.itertext()): e for e in kelas(svg, "arah-gambar")}
        assert set(label) == {"depan", "kanan"} and len(kelas(svg, "arah-gambar")) == 2
        kiri, bawah, kanan_sudut, _ = titik_path(kelas(svg, "lantai-petak")[0].get("d"))
        tengah_depan = ((kiri[0] + bawah[0]) / 2, (kiri[1] + bawah[1]) / 2)
        tengah_kanan = ((bawah[0] + kanan_sudut[0]) / 2, (bawah[1] + kanan_sudut[1]) / 2)
        for nama, tengah, geser in (("depan", tengah_depan, -T.ADEGAN_TUMPUKAN_LABEL_GESER),
                                    ("kanan", tengah_kanan, T.ADEGAN_TUMPUKAN_LABEL_GESER)):
            e = label[nama]
            assert float(e.get("x")) == pytest.approx(tengah[0] + geser, abs=0.01), (baris, kolom, nama)
            assert float(e.get("y")) == pytest.approx(tengah[1] + T.ADEGAN_TUMPUKAN_LABEL_TURUN, abs=0.01)
            assert float(e.get("font-size")) >= 16 and e.get("fill") == T.TEKS_UTAMA
        assert float(label["kanan"].get("x")) - float(label["depan"].get("x")) > 60, (baris, kolom)


def test_lantai_berpetak_sesuai_alas_dan_digambar_sebelum_kolom_kubus():
    svg = svg_dari_data(data_adegan([1, 0, 0, 2, 2, 1, 3, 3, 2], 3), "lantai")
    urutan = list(svg.iter())
    (lantai,) = kelas(svg, "lantai-petak")
    (garis,) = kelas(svg, "garis-lantai")
    assert urutan.index(lantai) < urutan.index(garis) < urutan.index(kelas(svg, "kolom-kubus")[0])
    assert len(titik_path(lantai.get("d"))) == 4
    assert garis.get("d").count("M") == 2 + 2, "tiga baris dan tiga kolom: dua garis dalam tiap arah"
    svg2 = svg_dari_data(data_adegan([1, 0, 3, 2], 2), "lantai2")
    assert kelas(svg2, "garis-lantai")[0].get("d").count("M") == 1 + 1


def test_puncak_tiap_tumpukan_tidak_tertimpa_muka_lain_di_seluruh_domain():
    """Tak ada tumpukan yang hilang dari gambar: muka atas puncak tetap terlihat penuh di semua susunan."""
    for p in _susunan_unik():
        assert puncak_tertimpa(_svg_param(p, "lihat")) == [], p


def test_penguji_puncak_mengenali_tumpukan_tersembunyi_pada_susunan_di_luar_domain():
    """Baris depan [1, 2], belakang [1, 0]: tumpukan belakang-kiri persis tertutup tumpukan di depan-kanan."""
    svg = svg_dari_data(data_adegan((1, 2, 1, 0), 2))
    assert puncak_tertimpa(svg) != []


def test_urutan_lukis_mengikuti_kedalaman_bagi_setiap_dua_kubus_yang_saling_menutup():
    """Dua kubus yang mukanya bertampalan: yang lebih dekat ke penonton (x - y + z lebih besar) digambar belakangan."""
    periksa = 0
    for p in _susunan_unik()[::6] + [{"baris": 3, "kolom": 3, "tinggi": [3] * 9}]:
        svg = svg_dari_data(data_adegan(p["tinggi"], p["kolom"]), "urut")
        kubus = kubus_berposisi(svg)
        for i, (xa, ya, za, muka_a) in enumerate(kubus):
            for xb, yb, zb, muka_b in kubus[i + 1:]:
                if abs(xa - xb) > 2 or abs(ya - yb) > 2:
                    continue
                if any(tumpang_tindih(ma, mb) for ma in muka_a for mb in muka_b):
                    periksa += 1
                    assert (xa - ya + za) < (xb - yb + zb), ("kubus lebih dekat digambar lebih dulu", i)
    assert periksa > 500


def test_kubus_atas_digambar_sesudah_kubus_bawah_dan_menutup_sebagian_mukanya():
    svg = svg_dari_data(data_adegan((3, 0, 0, 0), 2))
    kubus = kubus_berposisi(svg)
    assert [z for _, _, z, _ in kubus] == [0, 1, 2]
    assert not tumpang_tindih(kubus[0][3][1], kubus[1][3][1])  # muka kiri bawah dan atas hanya bersebelahan
    assert any(tumpang_tindih(a, b) for a in kubus[0][3] for b in kubus[1][3])  # muka atas bawah tertutup kubus atas


def test_muka_atas_kiri_kanan_memakai_token_terang_sedang_gelap():
    atas, kiri, kanan = T.ADEGAN_TUMPUKAN_MUKA
    svg = _svg(CONTOH_KUBUS_3X3)
    assert {e.get("fill") for e in kelas(svg, "muka-atas")} == {atas}
    assert {e.get("fill") for e in kelas(svg, "muka-kiri")} == {kiri}
    assert {e.get("fill") for e in kelas(svg, "muka-kanan")} == {kanan}
    assert len({atas, kiri, kanan}) == 3
    from visual_security_helpers import luminansi
    assert luminansi(atas) > luminansi(kiri) > luminansi(kanan)
    for e in elemen(svg, "path"):
        if "muka" in e.get("class", ""):
            assert e.get("stroke") == T.TEKS_UTAMA and float(e.get("stroke-width")) >= 2


def test_warna_token_dan_kontras_gelap_pada_semua_muka_dan_lantai():
    sah = {None, "none", T.TEKS_UTAMA, *T.ADEGAN_TUMPUKAN_MUKA, T.ADEGAN_TUMPUKAN_LANTAI_ISI,
           T.ADEGAN_TUMPUKAN_LANTAI_GARIS}
    for parameter in CONTOH:
        svg = _svg(parameter)
        for e in svg.iter():
            if lokal(e) in ("path", "text"):
                for atribut in ("stroke", "fill"):
                    assert e.get(atribut) in sah, e.attrib
    for latar in (*T.ADEGAN_TUMPUKAN_MUKA, T.ADEGAN_TUMPUKAN_LANTAI_ISI, T.LATAR_KARTU, T.LATAR_MURID):
        assert kontras(T.TEKS_UTAMA, latar) >= 4.5, latar
    for a, b in zip(T.ADEGAN_TUMPUKAN_MUKA, T.ADEGAN_TUMPUKAN_MUKA[1:]):
        assert kontras(a, b) > 1.15, (a, b)
