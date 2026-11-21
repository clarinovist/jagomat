"""Keluarga visual `matematika-awal`: baca_jam_awal bergambar (adegan_awal v1, `jam_analog`).

Solver mandiri HANYA membaca teks proyeksi dan SVG hasil `render_pertanyaan` lewat
`penyajian_dari_soal`: waktu dibaca dari KOORDINAT kedua garis jarum (garis yang berpangkal di
titik pusat muka; jarum pendek dan panjang dibedakan dari PANJANG garis, bukan dari nama kelas),
lalu dibandingkan dengan `soal.kunci` untuk SELURUH domain P2 (sapuan penuh, tanpa stride).
Kebocoran diuji pada string HTML mentah: SVG tanpa kedua garis jarum harus identik byte per byte
untuk semua waktu, jadi kelas, id, judul, uraian, transform, dan atribut tidak memuat waktu.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adegan_awal_data
import adegan_awal_jam_svg
import adegan_awal_svg
import awal_baca_jam_awal as sumber
import design_tokens as T
from jam_solver_helpers import (BACA_PENUH, BACA_SETENGAH, KEMUDIAN, SELESAI, jawab_dari_waktu,
                                solver_dari_teks)
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian
from visual_inventory import DENOMINATOR_KANONIS, VARIAN_SENGAJA_TEKS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, kontras, lokal, periksa_xml

TID = sumber.TEMPLATE_ID
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
KELAS_BOLEH = {"jam-gambar", "muka-jam", "tanda-menit", "tanda-jam", "angka-jam",
               "jarum-panjang", "jarum-pendek", "pusat-jam"}
TAG_BOLEH = {"svg", "title", "desc", "g", "circle", "path", "line", "text"}
WAKTU = tuple((jam, menit) for jam in range(1, 13) for menit in (0, 30))
RASIO_PANJANG_MIN = 1.3
TOLERANSI_SUDUT = 1.0  # derajat; koordinat dibulatkan dua desimal
CONTOH_PENUH = dict(varian="baca_penuh", jam=12)
CONTOH_SETENGAH = dict(varian="baca_setengah", jam=6)
CONTOH_KEMUDIAN = dict(varian="jam_kemudian", jam=11, tambah=3)
CONTOH_SELESAI = dict(varian="kegiatan_selesai", kegiatan=1, jam=9, lama=4)
CONTOH = (CONTOH_PENUH, CONTOH_SETENGAH, CONTOH_KEMUDIAN, CONTOH_SELESAI)
PENGANTAR_BACA = "Perhatikan gambar jam."

FINGERPRINT_DIPATOK = {
    "penuh": ("b555d38366851bb00941dc5f117140389fbb917ad6b65cb090842cfadbe751b3",
              "f2ea495d45ca3f1f0f45ee63b300566ff9889577c0a6648d6c324363e72cf5ca"),
    "setengah": ("984225a69888e5088167fc21beb02d3f65be327d4caa8d2999045791f7ef9094",
                 "095dc96ab7b5d191fc8376a5cc398cebfaa12f1a2f47bce47ece30703396c31b"),
    "kemudian": ("d3bc92216029d7d6858a1831c913a69db320cb622a509759e3e104f82149ae74",
                 "f70923d08a66fdbff52cc3dbe8a9097bd43ebc25ee53c7d60257ff289b68d5e9"),
    "selesai": ("aeb0c06051242d3bce4f921475230952cd4c900f99eb3eee0b94de7fa20e85d1",
                "851f73cbab490141b7e23db1a5431af4ea6ccc9b710d62c5bbd070127525c4d3"),
}


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _soal(parameter):
    return replace(sumber.baca_jam_awal(**parameter), level="P2")


def _penyajian(parameter):
    return penyajian_dari_soal(_soal(parameter))


def _html(parameter, *, namespace="uji-jam", gaya="cetak"):
    return render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya)


def _svg(parameter, **kw):
    return periksa_xml(_html(parameter, **kw))


def _domain(*varian):
    return tuple(p for p in sumber.domain_parameter("P2") if p["varian"] in varian)


def _data(jam=3, menit=0):
    return {"adegan": "jam_analog", "jam": jam, "menit": menit}


def _svg_data(data, namespace="uji"):
    return periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, namespace) + "</div>")


def _raw_data(jam, menit, namespace="uji"):
    return adegan_awal_svg.render_adegan_awal(_data(jam, menit), namespace)


# ── solver mandiri dari koordinat jarum ──────────────────────────────────

def _garis(e):
    return tuple(float(e.get(k)) for k in ("x1", "y1", "x2", "y2"))


def _pusat(svg):
    (muka,) = [e for e in svg.iter() if lokal(e) == "circle" and "muka-jam" in e.get("class", "").split()]
    return float(muka.get("cx")), float(muka.get("cy"))


def _jarum_dari_pusat(svg):
    """Dua garis yang berpangkal di titik pusat muka, tanpa memakai nama kelas."""
    cx, cy = _pusat(svg)
    hasil = [g for g in (_garis(e) for e in svg.iter() if lokal(e) == "line")
             if abs(g[0] - cx) < 0.01 and abs(g[1] - cy) < 0.01]
    assert len(hasil) == 2, hasil
    return hasil


def _panjang(g):
    return math.dist((g[0], g[1]), (g[2], g[3]))


def _sudut(g):
    """Derajat dari arah atas searah jarum jam, 0 <= sudut < 360."""
    return math.degrees(math.atan2(g[2] - g[0], -(g[3] - g[1]))) % 360


def baca_waktu(svg):
    """(jam, menit) dari dua garis jarum: pendek/panjang dari panjang garis, sudut dengan pembulatan."""
    a, b = _jarum_dari_pusat(svg)
    pendek, panjang = sorted((a, b), key=_panjang)
    assert _panjang(panjang) / _panjang(pendek) >= RASIO_PANJANG_MIN, (a, b)
    menit = round(_sudut(panjang) / 6) % 60
    assert menit in (0, 30), menit
    assert abs((_sudut(panjang) - menit * 6 + 180) % 360 - 180) < TOLERANSI_SUDUT
    sudut_jam = _sudut(pendek)
    jam = round((sudut_jam - menit * 0.5) / 30) % 12 or 12
    harapan = ((jam % 12) * 30 + menit * 0.5) % 360
    assert abs((sudut_jam - harapan + 180) % 360 - 180) < TOLERANSI_SUDUT, (sudut_jam, harapan)
    return jam, menit


def jawab_visual(penyajian, svg):
    baris = penyajian.teks_soal.split("\n")
    assert len(baris) == 2 and baris[0].startswith(PENGANTAR_BACA), baris
    jam, menit = baca_waktu(svg)
    return jawab_dari_waktu(baris[1], jam, menit)


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_solver_geometri_sama_dengan_kunci_seluruh_domain(varian):
    domain = _domain(varian)
    assert domain
    for p in domain:
        soal = _soal(p)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "siap" and penyajian.mode_representasi == "adegan_awal-v1"
        svg = periksa_xml(render_pertanyaan(penyajian, namespace="sapuan"))
        assert jawab_visual(penyajian, svg) == soal.kunci, p


@pytest.mark.parametrize("jam, menit", WAKTU)
def test_baca_waktu_seluruh_24_waktu_dari_koordinat(jam, menit):
    assert baca_waktu(_svg_data(_data(jam, menit))) == (jam, menit)


@pytest.mark.parametrize("jam, menit", ((12, 0), (12, 30), (6, 0), (6, 30), (1, 0), (11, 30)))
def test_tepi_12_dan_6_dibaca_dengan_pembulatan_bukan_lantai(jam, menit):
    svg = _svg_data(_data(jam, menit))
    assert baca_waktu(svg) == (jam, menit)
    pendek, panjang = sorted(_jarum_dari_pusat(svg), key=_panjang)
    assert abs((_sudut(panjang) - menit * 6 + 180) % 360 - 180) < 0.1
    # arah atas bisa terbaca 359,99 derajat (bukan 0): solver wajib membulatkan, bukan memakai lantai
    sudut = _sudut(pendek)
    assert min(abs(sudut - ((jam % 12) * 30 + menit / 2)),
               360 - abs(sudut - ((jam % 12) * 30 + menit / 2))) < 0.1


def test_solver_geometri_menolak_gambar_yang_ambigu():
    """Mutasi gambar: tiga garis dari pusat, atau dua jarum sama panjang, harus gagal dibaca."""
    svg = _svg_data(_data(3, 0))
    pendek, panjang = sorted(_jarum_dari_pusat(svg), key=_panjang)
    for e in svg.iter():
        if lokal(e) == "line" and "jarum-pendek" in e.get("class", "").split():
            for k, v in zip(("x2", "y2"), (panjang[2], panjang[3])):
                e.set(k, str(v))
    with pytest.raises(AssertionError):
        baca_waktu(svg)


# ── varian: tanpa flag tetap teks yang bisa dijawab ──────────────────────

@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
def test_tanpa_flag_semua_varian_bisa_dijawab_dari_teks(monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    else:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", flag)
    for p in sumber.domain_parameter("P2"):
        soal = _soal(p)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "tanpa_visual" and penyajian.descriptor is None
        assert penyajian.teks_soal == soal.teks
        assert solver_dari_teks(penyajian.teks_soal) == soal.kunci, p
        assert "<svg" not in render_pertanyaan(penyajian)


# ── teks proyeksi dan kebocoran ──────────────────────────────────────────

def test_teks_proyeksi_tanpa_letak_jarum_dan_tanpa_kunci_di_seluruh_domain():
    for p in sumber.domain_parameter("P2"):
        soal = _soal(p)
        teks = penyajian_dari_soal(soal).teks_soal
        pengantar, tanya = teks.split("\n")
        assert pengantar.startswith(PENGANTAR_BACA)
        assert not re.search(r"jarum|menunjuk|di antara|angka \d", teks, re.I), teks
        assert soal.teks.split("\n")[-1] == tanya
        assert soal.kunci not in re.findall(r"\d+(?:\.\d+)?", teks), (p, teks, soal.kunci)
        if p["varian"] in ("baca_penuh", "baca_setengah"):
            assert not re.search(r"\d", teks), teks
        else:
            assert re.findall(r"\d+", teks) == [str(p.get("tambah", p.get("lama")))], teks


def test_pengantar_per_varian_dan_nama_kegiatan_di_teks():
    assert _penyajian(CONTOH_PENUH).teks_soal == f"{PENGANTAR_BACA}\n{BACA_PENUH}"
    assert _penyajian(CONTOH_SETENGAH).teks_soal == f"{PENGANTAR_BACA}\n{BACA_SETENGAH}"
    assert _penyajian(CONTOH_KEMUDIAN).teks_soal == (
        "Perhatikan gambar jam. Itu jam sekarang.\n3 jam lagi, pukul berapa? Tulis angka jamnya.")
    assert _penyajian(CONTOH_SELESAI).teks_soal == (
        "Perhatikan gambar jam. Itu jam ketika Tono mulai membuat layang-layang.\n"
        "Tono membuat layang-layang selama 4 jam. Pukul berapa Tono selesai? Tulis angka jamnya.")


def test_petunjuk_setengah_jam_tanpa_contoh_waktu_yang_bisa_jadi_kunci():
    for p in _domain("baca_setengah"):
        teks = _penyajian(p).teks_soal
        assert not re.search(r"\d", teks) and "2.30" not in teks


def test_svg_tanpa_dua_garis_jarum_identik_untuk_semua_24_waktu():
    """Muka, tanda, angka, judul, uraian: tidak bergantung pada waktu; hanya koordinat jarum yang berbeda."""
    jarum = re.compile(r'<line class="jarum-(?:pendek|panjang)"[^>]*/>')
    tanpa = {}
    for jam, menit in WAKTU:
        mentah = _raw_data(jam, menit)
        assert len(jarum.findall(mentah)) == 2
        tanpa[(jam, menit)] = jarum.sub("", mentah)
    assert len(set(tanpa.values())) == 1
    jarum_saja = {tuple(jarum.findall(_raw_data(j, m))) for j, m in WAKTU}
    assert len(jarum_saja) == len(WAKTU), "tiap waktu punya pasangan jarum sendiri"


def test_html_tanpa_dua_garis_jarum_identik_untuk_semua_waktu_dan_gaya():
    jarum = re.compile(r'<line class="jarum-(?:pendek|panjang)"[^>]*/>')
    for gaya in GAYA:
        bentuk = set()
        for p in _domain("baca_penuh", "baca_setengah"):
            html = _html(p, gaya=gaya, namespace="bocor")
            svg = re.search(r"<svg\b.*?</svg>", html, re.S).group(0)
            bentuk.add(jarum.sub("", svg))
        assert len(bentuk) == 1, gaya


def test_tanpa_transform_tanpa_data_atribut_tanpa_minus_nol_dan_kelas_netral():
    for parameter in CONTOH:
        for gaya in GAYA:
            html = _html(parameter, gaya=gaya)
            svg = periksa_xml(html)
            token = {t for e in svg.iter() for t in e.get("class", "").split()}
            assert token == KELAS_BOLEH
            assert not [a for e in svg.iter() for a in e.attrib if a.startswith("data-")]
            assert not [e for e in svg.iter() if "transform" in e.attrib]
            assert {lokal(e) for e in svg.iter()} <= TAG_BOLEH
            assert not elemen(svg, "image") and not [e for e in svg.iter() if "href" in e.attrib]
            assert not re.search(r"(?<![\d.])-0(?![\d.])", re.search(r"<svg\b.*?</svg>", html, re.S).group(0))
            assert "rotate" not in html


@pytest.mark.parametrize("jam, menit", WAKTU)
def test_tanpa_minus_nol_pada_koordinat_untuk_seluruh_waktu(jam, menit):
    mentah = _raw_data(jam, menit)
    assert not re.search(r'="-0"|[ ,ML]-0[ ,"LM]', mentah), mentah
    assert not re.search(r'[0-9]e[-+]?[0-9]', mentah)


def test_desc_dan_title_tetap_tanpa_waktu_nama_digit_atau_letak_jarum():
    judul_tetap, uraian_tetap = set(), set()
    for p in sumber.domain_parameter("P2")[::5]:
        svg = _svg(p, namespace="aks")
        (judul,), (uraian,) = elemen(svg, "title"), elemen(svg, "desc")
        isi_judul, isi_uraian = "".join(judul.itertext()), "".join(uraian.itertext())
        assert svg.get("role") == "img"
        assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
        assert not re.search(r"\d", isi_judul + isi_uraian)
        assert not re.search(r"pukul|setengah|menunjuk|di antara", isi_judul + isi_uraian, re.I)
        judul_tetap.add(isi_judul)
        uraian_tetap.add(isi_uraian)
    assert judul_tetap == {"Gambar jam"}
    assert uraian_tetap == {"Jam dinding berjarum. Perhatikan letak kedua jarumnya."}


def test_angka_di_muka_tetap_1_sampai_12_apa_pun_waktunya():
    for jam, menit in ((12, 0), (3, 30), (6, 0)):
        svg = _svg_data(_data(jam, menit))
        angka = [("".join(e.itertext()), e) for e in elemen(svg, "text")]
        assert [a for a, _ in angka] == [str(n) for n in range(1, 13)]
        assert all(e.get("class") == "angka-jam" for _, e in angka)


def test_descriptor_hanya_memuat_field_allowlist_tanpa_kunci():
    for p in sumber.domain_parameter("P2")[::9]:
        penyajian = _penyajian(p)
        data = penyajian.descriptor.ke_dict()["data"]
        assert set(data) == {"adegan", "jam", "menit"} and data["adegan"] == "jam_analog"
        assert data["menit"] == (30 if p["varian"] == "baca_setengah" else 0) and data["jam"] == p["jam"]
        assert "kunci" not in serialisasi_penyajian(penyajian)


# ── geometri: jarum jelas, tidak bertumpuk, di dalam muka ────────────────

def _hand_lines(svg):
    pendek = [e for e in elemen(svg, "line") if "jarum-pendek" in e.get("class", "").split()]
    panjang = [e for e in elemen(svg, "line") if "jarum-panjang" in e.get("class", "").split()]
    assert len(pendek) == len(panjang) == 1
    return pendek[0], panjang[0]


@pytest.mark.parametrize("jam, menit", WAKTU)
def test_jarum_beda_panjang_dan_tebal_dan_kelas_sesuai_panjang(jam, menit):
    pendek, panjang = _hand_lines(_svg_data(_data(jam, menit)))
    assert _panjang(_garis(panjang)) / _panjang(_garis(pendek)) >= RASIO_PANJANG_MIN
    assert float(pendek.get("stroke-width")) > float(panjang.get("stroke-width")) >= 4 - 1e-9
    assert pendek.get("stroke") == panjang.get("stroke") == T.TEKS_UTAMA


def test_jam_12_tepat_kedua_jarum_searah_jarum_pendek_lebih_tebal_dan_di_atas():
    svg = _svg_data(_data(12, 0))
    pendek, panjang = _hand_lines(svg)
    assert abs(_sudut(_garis(pendek))) < 0.1 or abs(_sudut(_garis(pendek)) - 360) < 0.1
    assert abs(_sudut(_garis(panjang))) < 0.1 or abs(_sudut(_garis(panjang)) - 360) < 0.1
    assert float(pendek.get("stroke-width")) > float(panjang.get("stroke-width"))
    urutan = [e for e in svg.iter() if e in (pendek, panjang)]
    assert urutan == [panjang, pendek], "jarum pendek digambar sesudah jarum panjang (di atasnya)"
    assert baca_waktu(svg) == (12, 0)


def test_jam_enam_tiga_puluh_jarum_pendek_tepat_di_tengah_enam_dan_tujuh():
    svg = _svg_data(_data(6, 30))
    pendek, panjang = _hand_lines(svg)
    assert abs(_sudut(_garis(panjang)) - 180) < 0.1
    assert abs(_sudut(_garis(pendek)) - 195) < 0.1
    assert 14.0 < abs(_sudut(_garis(pendek)) - _sudut(_garis(panjang))) < 16.0


def test_setengah_jam_jarum_pendek_tepat_di_tengah_dua_angka_di_semua_jam():
    for jam in range(1, 13):
        pendek, panjang = _hand_lines(_svg_data(_data(jam, 30)))
        assert abs(_sudut(_garis(panjang)) - 180) < 0.1
        tengah = (jam % 12) * 30 + 15
        assert abs(_sudut(_garis(pendek)) - tengah) < 0.1, jam


def test_jam_penuh_jarum_panjang_di_atas_dan_jarum_pendek_di_angka_tepat():
    for jam in range(1, 13):
        pendek, panjang = _hand_lines(_svg_data(_data(jam, 0)))
        assert abs((_sudut(_garis(panjang)) + 180) % 360 - 180) < 0.1
        assert abs(_sudut(_garis(pendek)) - (jam % 12) * 30) < 0.1, jam


def test_jarum_dan_angka_di_dalam_muka_dan_angka_tidak_saling_menimpa():
    for jam, menit in ((12, 0), (12, 30), (6, 30), (3, 0)):
        svg = _svg_data(_data(jam, menit))
        cx, cy = _pusat(svg)
        radius = float(next(e for e in svg.iter() if "muka-jam" in e.get("class", "")).get("r"))
        for e in elemen(svg, "line"):
            for x, y in ((float(e.get("x1")), float(e.get("y1"))), (float(e.get("x2")), float(e.get("y2")))):
                assert math.dist((x, y), (cx, cy)) <= radius, e.attrib
        angka = [(float(e.get("x")), float(e.get("y")), "".join(e.itertext())) for e in elemen(svg, "text")]
        for x, y, isi in angka:
            lebar_tengah = len(isi) * T.ADEGAN_JAM_ANGKA_FONT * 0.6 / 2
            assert math.dist((x, y), (cx, cy)) + lebar_tengah <= T.ADEGAN_JAM_TICK_JAM, isi
        for i, (x1, y1, _) in enumerate(angka):
            for x2, y2, _ in angka[i + 1:]:
                assert math.dist((x1, y1), (x2, y2)) > T.ADEGAN_JAM_ANGKA_FONT * 1.5
        pendek, panjang = _hand_lines(svg)
        assert _panjang(_garis(panjang)) < T.ADEGAN_JAM_ANGKA_JARI - T.ADEGAN_JAM_ANGKA_FONT * 0.5


def test_tanda_jam_12_dan_tanda_menit_48_tetap_untuk_semua_waktu():
    for jam, menit in ((1, 0), (12, 30)):
        svg = _svg_data(_data(jam, menit))
        tanda = [e for e in elemen(svg, "line") if "tanda-jam" in e.get("class", "").split()]
        assert len(tanda) == 12
        (menit_path,) = [e for e in elemen(svg, "path") if "tanda-menit" in e.get("class", "").split()]
        assert menit_path.get("d").count("M") == 48


# ── warna dan kontras ────────────────────────────────────────────────────

def test_stroke_gelap_token_dan_kontras_terhadap_latar_dan_muka():
    for parameter in CONTOH:
        svg = _svg(parameter)
        for e in svg.iter():
            if lokal(e) in ("line", "circle", "path", "text"):
                warna = e.get("stroke") if lokal(e) != "text" and e.get("fill") in (None, "none") else None
                for atribut in ("stroke", "fill"):
                    nilai = e.get(atribut)
                    assert nilai in (None, "none", T.TEKS_UTAMA, T.ADEGAN_JAM_MUKA), e.attrib
                assert warna in (None, T.TEKS_UTAMA)
    for latar in (T.LATAR_KARTU, T.LATAR_MURID, T.ADEGAN_JAM_MUKA):
        assert kontras(T.TEKS_UTAMA, latar) >= 4.5


def test_jarum_tebal_minimum_dan_angka_cukup_besar():
    svg = _svg(CONTOH_PENUH)
    pendek, panjang = _hand_lines(svg)
    assert float(pendek.get("stroke-width")) >= 6 and float(panjang.get("stroke-width")) >= 4
    assert all(float(e.get("font-size")) >= 16 for e in elemen(svg, "text"))


# ── invarian: determinisme, fingerprint, serialisasi ─────────────────────

def test_render_dua_kali_identik_byte_per_byte():
    for parameter in CONTOH:
        penyajian = _penyajian(parameter)
        assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
        assert penyajian.fingerprint_penyajian == _penyajian(parameter).fingerprint_penyajian


def test_fingerprint_dipatok_agar_perubahan_penyajian_disengaja():
    ringkas = {
        nama: (_penyajian(p).fingerprint_matematis, _penyajian(p).fingerprint_penyajian)
        for nama, p in (("penuh", CONTOH_PENUH), ("setengah", CONTOH_SETENGAH),
                        ("kemudian", CONTOH_KEMUDIAN), ("selesai", CONTOH_SELESAI))
    }
    assert ringkas == FINGERPRINT_DIPATOK


@pytest.mark.parametrize("parameter", CONTOH)
def test_round_trip_serialisasi_dan_fingerprint_matematis_sama_dengan_mode_teks(monkeypatch, parameter):
    penyajian = _penyajian(parameter)
    assert deserialisasi_penyajian(serialisasi_penyajian(penyajian)) == penyajian
    monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    teks = _penyajian(parameter)
    assert teks.fingerprint_matematis == penyajian.fingerprint_matematis
    assert teks.fingerprint_penyajian != penyajian.fingerprint_penyajian


def test_snapshot_dan_html_identik_antarproses():
    kode = (
        "import hashlib\n"
        "from dataclasses import replace\n"
        "import awal_baca_jam_awal as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P2')[::7]:\n"
        "    s = penyajian_dari_soal(replace(m.baca_jam_awal(**p), level='P2'))\n"
        "    h.update((serialisasi_penyajian(s) + render_pertanyaan(s, namespace='x')).encode())\n"
        "print(h.hexdigest())\n"
    )
    hasil = tuple(subprocess.check_output(
        [sys.executable, "-c", kode], cwd=AKAR, text=True, timeout=120,
        env={**os.environ, "OSN_VISUAL_KELUARGA": "matematika-awal",
             "PYTHONHASHSEED": str(seed)}) for seed in (1, 8191))
    assert hasil[0] == hasil[1] and len(hasil[0].strip()) == 64


# ── keamanan XML dan namespace ───────────────────────────────────────────

NAMESPACE = (
    "uji-normal", '" onload="uji', "<svg><script>uji</script></svg>",
    "url(https://contoh.invalid/gambar)", "../lain#judul", "uji\x00id",
    "uji‮id", "uji\ud800id", "N" * 10000,
)


@pytest.mark.parametrize("namespace", NAMESPACE, ids=lambda s: ascii(s[:30]))
def test_namespace_berbahaya_ditolak_atau_diisolasi(namespace):
    penyajian = _penyajian(CONTOH_SETENGAH)
    try:
        hasil = render_pertanyaan(penyajian, namespace=namespace)
    except ValueError:
        return
    svg = periksa_xml(hasil)
    pembanding = _svg(CONTOH_SETENGAH, namespace="pembanding")
    ids = {e.get("id") for e in svg.iter() if e.get("id")}
    assert ids and ids.isdisjoint(e.get("id") for e in pembanding.iter())
    assert not re.search(r"<script|javascript:|\son[a-z]+=",
                         hasil.replace('xmlns="http://www.w3.org/2000/svg"', ""), re.I)


@pytest.mark.parametrize("namespace", ("", None, 3))
def test_namespace_kosong_atau_bukan_teks_ditolak(namespace):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(_penyajian(CONTOH_PENUH).descriptor.data, namespace)


def test_id_unik_pada_lembar_dengan_banyak_soal_berulang():
    ids = []
    for i in range(6):
        ids += [e.get("id") for e in _svg(CONTOH_SETENGAH, namespace=f"lembar-{i}").iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12


# ── validator descriptor: allow-list ketat ───────────────────────────────

def _valid(data):
    DescriptorVisual("adegan_awal", 1, data)
    return adegan_awal_svg.render_adegan_awal(data, "uji")


def test_descriptor_sah_dua_puluh_empat_waktu_diterima():
    for jam, menit in WAKTU:
        assert _valid(_data(jam, menit))
    assert "jam_analog" in adegan_awal_data.ADEGAN_DIDUKUNG


@pytest.mark.parametrize("rusak", (
    {"adegan": "jam_analog", "jam": 3},
    {"adegan": "jam_analog", "menit": 0},
    {"adegan": "jam_analog"},
    {"adegan": "jam_analog", "jam": 3, "menit": 0, "kunci": "3"},
    {"adegan": "jam_analog", "jam": 3, "menit": 0, "class": "tiga"},
    {"adegan": "jam_analog", "jam": 3, "menit": 0, "tampil": "satu"},
    {"adegan": "jam_analog", "jam": 0, "menit": 0},
    {"adegan": "jam_analog", "jam": 13, "menit": 0},
    {"adegan": "jam_analog", "jam": -1, "menit": 0},
    {"adegan": "jam_analog", "jam": True, "menit": 0},
    {"adegan": "jam_analog", "jam": 3.0, "menit": 0},
    {"adegan": "jam_analog", "jam": "3", "menit": 0},
    {"adegan": "jam_analog", "jam": None, "menit": 0},
    {"adegan": "jam_analog", "jam": [3], "menit": 0},
    {"adegan": "jam_analog", "jam": 3, "menit": 15},
    {"adegan": "jam_analog", "jam": 3, "menit": 45},
    {"adegan": "jam_analog", "jam": 3, "menit": 60},
    {"adegan": "jam_analog", "jam": 3, "menit": -30},
    {"adegan": "jam_analog", "jam": 3, "menit": False},
    {"adegan": "jam_analog", "jam": 3, "menit": 30.0},
    {"adegan": "jam_analog", "jam": 3, "menit": "30"},
    {"adegan": "jam_analog", "jam": 3, "menit": None},
    {"adegan": "jam_dinding", "jam": 3, "menit": 0},
    {"jam": 3, "menit": 0},
    {1: "jam_analog", "jam": 3, "menit": 0},
))
def test_descriptor_rusak_ditolak_validator_dan_renderer(rusak):
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, rusak)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(rusak, "uji")


@pytest.mark.parametrize("bukan_mapping", (None, [], "jam_analog", 3))
def test_data_bukan_mapping_ditolak(bukan_mapping):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(bukan_mapping, "uji")


# ── proyektor: field persis dan bentuk teks sumber ───────────────────────

def test_field_parameter_tambahan_atau_hilang_ditolak_proyektor():
    for dasar in CONTOH:
        soal = _soal(dasar)
        for rusak in (
            {**soal.parameter, "kunci": "x"},
            {**soal.parameter, "menit": 30},
            {k: v for k, v in soal.parameter.items() if k != "varian"},
            {k: v for k, v in soal.parameter.items() if k != "jam"},
            {**soal.parameter, "varian": "lain"},
            {**soal.parameter, "jam": 13},
            {**soal.parameter, "jam": True},
        ):
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, rusak)
    kemudian = _soal(CONTOH_KEMUDIAN).parameter
    for rusak in ({**kemudian, "tambah": 5}, {**kemudian, "jam": 12}, {**kemudian, "lama": 1},
                  {k: v for k, v in kemudian.items() if k != "tambah"}):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)
    selesai = _soal(CONTOH_SELESAI).parameter
    for rusak in ({**selesai, "kegiatan": 4}, {**selesai, "lama": 0}, {**selesai, "jam": 12},
                  {k: v for k, v in selesai.items() if k != "kegiatan"}):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)


def test_proyeksi_gagal_keras_bila_bentuk_teks_sumber_berubah(monkeypatch):
    asli = sumber.baca_jam_awal
    for dasar in CONTOH:
        soal = _soal(dasar)
        for ubah in (
            lambda teks: teks.replace("\n", " "),
            lambda teks: teks + "\nCatatan.",
            lambda teks: teks.rsplit("\n", 1)[0] + "\nPukul berapa sekarang?",
            lambda teks: teks.replace("Tulis", "Tuliskan"),
        ):
            def palsu(varian, **isi):
                hasil = asli(varian, **isi)
                return replace(hasil, teks=ubah(hasil.teks))
            monkeypatch.setattr(sumber, "baca_jam_awal", palsu)
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, soal.parameter)
        monkeypatch.setattr(sumber, "baca_jam_awal", asli)


def test_proyeksi_jenis_lain_tetap_none_dan_jenis_lama_tidak_berubah():
    assert proyeksi_matematika_awal("waktu_berat_awal", {"apa": "saja"}) is None
    assert proyeksi_matematika_awal("kenali_bentuk", {"apa": "saja"}) is None


# ── batas viewBox ────────────────────────────────────────────────────────

@pytest.mark.parametrize("jam, menit", WAKTU)
def test_semua_waktu_dalam_viewbox(jam, menit):
    svg = _svg_data(_data(jam, menit), namespace="batas")
    periksa_batas_koordinat(svg)
    lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
    assert lebar == T.ADEGAN_LEBAR and tinggi == T.ADEGAN_JAM_TINGGI
    cx, cy = _pusat(svg)
    radius = float(next(e for e in svg.iter() if "muka-jam" in e.get("class", "")).get("r"))
    tepi = T.ADEGAN_JAM_TEBAL_MUKA / 2
    assert cx - radius - tepi >= 0 and cx + radius + tepi <= lebar
    assert cy - radius - tepi >= 0 and cy + radius + tepi <= tinggi
    assert abs(cx - lebar / 2) < 0.01 and abs(cy - tinggi / 2) < 0.01


# ── ringkasan non-HTML ───────────────────────────────────────────────────

def test_ringkasan_tanpa_waktu_dan_sama_untuk_semua_waktu():
    ringkasan = {ringkasan_pertanyaan(_penyajian(p)).split("\n")[-1]
                 for p in sumber.domain_parameter("P2")[::5]}
    assert len(ringkasan) == 1
    isi = next(iter(ringkasan))
    assert "Fakta visual: gambar jam dinding berjarum" in isi
    assert not re.search(r"\d|pukul|setengah", isi, re.I)


# ── inventaris ───────────────────────────────────────────────────────────

def test_inventaris_menandai_baca_jam_awal_wajib_visual_semua_varian_bergambar():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {d["varian"] for d in baris} == {f"varian={v}" for v in sumber.VARIAN}
    assert {d["level"] for d in baris} == {"P2"}
    assert TID not in VARIAN_SENGAJA_TEKS, "keempat varian memakai gambar jam"
    assert {d["bukti_klasifikasi"]["keluarga"] for d in baris} == {"jam_analog"}
    assert "tidak ada yang sengaja teks" in baris[0]["bukti_klasifikasi"]["observasi"]
