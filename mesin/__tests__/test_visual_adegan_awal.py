"""Keluarga visual `matematika-awal`: baca_diagram_gambar bergambar (adegan_awal v1).

Solver mandiri HANYA membaca teks soal dan SVG hasil render (elemen `<image>` per
baris + label), lewat jalur `penyajian_dari_soal` + `render_pertanyaan`, lalu
dibandingkan dengan `soal.kunci` untuk seluruh domain P1 jenis ini.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adegan_awal_svg
import awal_baca_diagram_gambar as sumber
import brand
import design_tokens as T
from adegan_awal_data import IKON_DIDUKUNG
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import IKON_KATEGORI, proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import (
    DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian,
)
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, lokal, periksa_xml, teks_svg
from visual_test_support import buat_soal, pasangan_aktif

TID = sumber.TEMPLATE_ID
# Jenis keluarga ini yang bergambar; sisanya tetap teks walau flag aktif (turus dan ukur: test_visual_adegan_awal_*).
TEMPLATE_BERGAMBAR = frozenset({TID, "turus_gambar_awal", "ukur_satuan_tak_baku"})
GAYA = ("cetak", "murid", "stitch", "guru")
SIMBOL = sumber.SIMBOL
AKAR = Path(__file__).resolve().parent.parent
CONTOH = {"varian": "selisih", "tema": "mainan", "n1": 5, "n2": 2, "n3": 8, "x": 0, "y": 1}


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _soal(parameter=None):
    return replace(sumber.baca_diagram_gambar(**(parameter or CONTOH)), level="P1")


def _penyajian(parameter=None):
    return penyajian_dari_soal(_soal(parameter))


def _svg(parameter=None, *, namespace="uji-adegan", gaya="cetak"):
    return periksa_xml(render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya))


# ── solver mandiri: hanya teks soal + SVG ────────────────────────────────

def _baris_svg(svg):
    """Daftar (label huruf kecil, banyak <image>) per baris, urut tampil."""
    hasil = []
    for baris in kelas(svg, "baris-adegan"):
        label = "".join("".join(t.itertext()) for t in elemen(baris, "text"))
        hasil.append((label.lower(), len(elemen(baris, "image"))))
    return tuple(hasil)


def _jawab(teks, svg):
    banyak = dict(_baris_svg(svg))
    tanya = teks.split("\n")[-1]
    if cocok := re.fullmatch(r"Berapa banyak ([a-z]+)\?", tanya):
        return str(banyak[cocok[1]])
    if tanya == "Mana yang paling banyak?":
        return max(banyak, key=banyak.get)
    if cocok := re.fullmatch(r"([A-Z][a-z]+) lebih banyak berapa daripada ([a-z]+)\?", tanya):
        return str(banyak[cocok[1].lower()] - banyak[cocok[2]])
    if cocok := re.fullmatch(r"Berapa jumlah ([a-z]+) dan ([a-z]+)\?", tanya):
        return str(banyak[cocok[1]] + banyak[cocok[2]])
    raise AssertionError(("pertanyaan tidak dikenal", tanya))


def _semua_parameter(varian):
    return tuple(p for p in sumber.domain_parameter("P1") if p["varian"] == varian)


def test_domain_p1_utuh_seperti_semula():
    ukuran = {v: len(_semua_parameter(v)) for v in sumber.VARIAN}
    assert ukuran == {"baca": 3024, "terbanyak": 1008, "selisih": 3024, "jumlah": 3024}


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_solver_svg_sama_dengan_kunci_seluruh_domain_p1(varian):
    for parameter in _semua_parameter(varian):
        soal = _soal(parameter)
        penyajian = penyajian_dari_soal(soal)
        svg = periksa_xml(render_pertanyaan(penyajian, namespace="sapuan"))
        baris = _baris_svg(svg)
        harapan = tuple((k.lower(), parameter[n]) for k, n in
                        zip(sumber.TEMA[parameter["tema"]][2], sumber.KUNCI_JUMLAH))
        assert baris == harapan, parameter
        assert _jawab(penyajian.teks_soal, svg) == soal.kunci, parameter


# ── invarian 1: tanpa flag tidak berubah ─────────────────────────────────

@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
def test_tanpa_keluarga_matematika_awal_teks_lama_persis(monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    else:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", flag)
    soal = _soal()
    penyajian = penyajian_dari_soal(soal)
    assert penyajian.status_visual == "tanpa_visual"
    assert penyajian.mode_representasi == "teks-v1"
    assert penyajian.descriptor is None
    assert penyajian.teks_soal == soal.teks
    assert SIMBOL in penyajian.teks_soal
    assert "<svg" not in render_pertanyaan(penyajian)


def test_nama_keluarga_tak_dikenal_tetap_value_error(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal,matematika-awall")
    with pytest.raises(ValueError, match="tidak dikenal"):
        penyajian_dari_soal(_soal())


def test_jenis_lain_matematika_awal_tetap_teks_saat_keluarga_aktif(monkeypatch):
    lain = [(n, lv, t) for n, lv, t in pasangan_aktif()
            if n == "matematika-awal" and t not in TEMPLATE_BERGAMBAR]
    assert len(lain) >= 15
    for nama, level, tid in lain:
        soal = buat_soal(nama, level, tid, 7)
        aktif = penyajian_dari_soal(soal)
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
        awal = penyajian_dari_soal(soal)
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
        assert aktif == awal, tid
        assert aktif.status_visual == "tanpa_visual", tid


def test_proyektor_template_lain_none_dan_masukan_tak_sah_value_error():
    assert proyeksi_matematika_awal("kenali_bentuk", {"apa": "saja"}) is None
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(3, CONTOH)
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(TID, [("varian", "baca")])


# ── invarian 2: teks, status, jumlah <image> ─────────────────────────────

def test_flag_aktif_status_siap_dan_teks_tanpa_simbol_atau_jawaban():
    penyajian = _penyajian()
    assert penyajian.status_visual == "siap"
    assert penyajian.mode_representasi == "adegan_awal-v1"
    assert SIMBOL not in penyajian.teks_soal
    assert "titik hitam" not in penyajian.teks_soal
    awal, tanya = penyajian.teks_soal.split("\n")
    assert awal == "Perhatikan gambar. Satu gambar mewakili 1 mainan."
    assert tanya == _soal().teks.split("\n")[-1]


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_teks_tidak_memuat_angka_selain_satuan_dan_tidak_menyebut_kunci(varian):
    for parameter in _semua_parameter(varian)[::37]:
        teks = _penyajian(parameter).teks_soal
        tanpa_satuan = teks.replace("mewakili 1 ", "mewakili ")
        assert not re.search(r"\d", tanpa_satuan), teks
        kunci = _soal(parameter).kunci
        if not kunci.isdigit():
            assert kunci not in teks.lower(), teks


def test_pertanyaan_diturunkan_dari_soal_sumber_untuk_seluruh_varian_dan_tema():
    for parameter in sumber.domain_parameter("P1")[::53]:
        soal = _soal(parameter)
        teks, descriptor = proyeksi_matematika_awal(TID, soal.parameter)
        assert teks.split("\n")[-1] == soal.teks.split("\n")[-1]
        assert descriptor.jenis == "adegan_awal"


def test_teks_sumber_tetap_lima_baris_dan_kunci_milik_sumber():
    soal = _soal()
    assert len(soal.teks.split("\n")) == 5
    assert soal.kunci == "3"


def test_setiap_kategori_semua_tema_punya_ikon_di_allow_list():
    for tema, (_, _, kategori) in sumber.TEMA.items():
        for nama in kategori:
            assert IKON_KATEGORI[nama.lower()] in IKON_DIDUKUNG, (tema, nama)


def test_descriptor_tidak_membawa_kunci_atau_jawaban():
    data = _penyajian().descriptor.ke_dict()["data"]
    assert set(data) == {"adegan", "baris", "satuan_ikon", "tanya"}
    assert data["tanya"] == {"varian": "selisih", "x": 0, "y": 1}
    assert "kunci" not in serialisasi_penyajian(_penyajian())


@pytest.mark.parametrize("gaya", GAYA)
def test_jumlah_image_per_baris_sama_parameter_semua_gaya(gaya):
    svg = _svg(gaya=gaya)
    assert tuple(n for _, n in _baris_svg(svg)) == (5, 2, 8)
    assert len(elemen(svg, "image")) == 15


def test_ringkasan_non_html_menyebut_fakta_gambar_tanpa_kunci_pertanyaan():
    ringkasan = ringkasan_pertanyaan(_penyajian())
    assert "Bola memiliki 5 gambar" in ringkasan
    assert "satu gambar mewakili 1 benda" in ringkasan


# ── invarian 3: determinisme dan fingerprint ─────────────────────────────

def test_render_dua_kali_identik_byte_per_byte():
    penyajian = _penyajian()
    assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
    assert _penyajian().fingerprint_penyajian == _penyajian().fingerprint_penyajian


def test_fingerprint_dipatok_agar_perubahan_penyajian_disengaja():
    penyajian = _penyajian()
    assert penyajian.fingerprint_matematis == (
        "44d98420837402e23bb7f067c98035625245c5ff9d5711073977ce938db9c58a")
    assert penyajian.fingerprint_penyajian == (
        "7b6872067334d379867747f5eee038ebab44661d33aff5541fdca9d1812d3fb5")


def test_round_trip_serialisasi_dan_fingerprint_beda_dengan_snapshot_teks(monkeypatch):
    penyajian = _penyajian()
    assert deserialisasi_penyajian(serialisasi_penyajian(penyajian)) == penyajian
    monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    teks = penyajian_dari_soal(_soal())
    assert teks.fingerprint_matematis == penyajian.fingerprint_matematis
    assert teks.fingerprint_penyajian != penyajian.fingerprint_penyajian


def test_snapshot_dan_html_identik_antarproses():
    kode = (
        "import hashlib\n"
        "from dataclasses import replace\n"
        "import awal_baca_diagram_gambar as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P1')[::97]:\n"
        "    s = penyajian_dari_soal(replace(m.baca_diagram_gambar(**p), level='P1'))\n"
        "    h.update((serialisasi_penyajian(s) + render_pertanyaan(s, namespace='x')).encode())\n"
        "print(h.hexdigest())\n"
    )
    hasil = tuple(subprocess.check_output(
        [sys.executable, "-c", kode], cwd=AKAR, text=True, timeout=120,
        env={**os.environ, "OSN_VISUAL_KELUARGA": "matematika-awal",
             "PYTHONHASHSEED": str(seed)}) for seed in (1, 8191))
    assert hasil[0] == hasil[1] and len(hasil[0].strip()) == 64


# ── invarian 4: keamanan ─────────────────────────────────────────────────

@pytest.mark.parametrize("gaya", GAYA)
@pytest.mark.parametrize("tema", tuple(sumber.TEMA))
def test_xml_allowlist_dan_satu_satunya_href_adalah_ikon_terdaftar(tema, gaya):
    parameter = {"varian": "terbanyak", "tema": tema, "n1": 1, "n2": 8, "n3": 4}
    html_hasil = render_pertanyaan(_penyajian(parameter), gaya=gaya)
    svg = periksa_xml(html_hasil)
    tanpa_xmlns = html_hasil.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert not re.search(r"<script|foreignObject|javascript:|https?:|//|\son[a-z]+=", tanpa_xmlns, re.I)
    href = [e.get("href") for e in svg.iter() if "href" in e.attrib]
    assert len(href) == 8 + 1 + 4
    assert all(re.fullmatch(r"/aset/ikon-[a-z]+-v1\.png", h) for h in href)
    assert {h.rsplit("/", 1)[1] for h in href} <= set(brand.ASET)
    assert all("href" not in e.attrib for e in svg.iter() if lokal(e) != "image")


NAMESPACE = (
    "uji-normal", '" onload="uji', "<svg><script>uji</script></svg>",
    "url(https://contoh.invalid/gambar)", "../lain#judul", "uji\x00id",
    "uji‮id", "uji\ud800id", "N" * 10000,
)


@pytest.mark.parametrize("namespace", NAMESPACE, ids=lambda s: ascii(s[:30]))
def test_namespace_berbahaya_ditolak_atau_diisolasi(namespace):
    penyajian = _penyajian()
    try:
        hasil = render_pertanyaan(penyajian, namespace=namespace)
    except ValueError:
        return
    svg = periksa_xml(hasil)
    lain = _svg(namespace="pembanding")
    ids = {e.get("id") for e in svg.iter() if e.get("id")}
    assert ids and ids.isdisjoint(e.get("id") for e in lain.iter())


@pytest.mark.parametrize("namespace", ("", None, 3))
def test_namespace_kosong_atau_bukan_teks_ditolak(namespace):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(_penyajian().descriptor.data, namespace)


@pytest.mark.parametrize("nama", (
    "../bola", "bola.png", "/aset/ikon-bola-v1.png", "https://contoh.invalid/x.png",
    "bola\" onload=\"x",
))
def test_ikon_liar_atau_traversal_ditolak_validator_dan_renderer(nama):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["baris"][0]["ikon"] = nama
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


@pytest.mark.parametrize("nama", ("<script>x</script>", '<image href="//x.invalid/a"/>', "A<", "onload=x>"))
def test_markup_pada_nama_baris_ditolak(nama):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["baris"][1]["nama"] = nama
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)


@pytest.mark.parametrize("nama", ("A & B", "'kutip' \"ganda\"", "Ａ＆Ｂ"))
def test_nama_baris_berkarakter_khusus_hanya_menjadi_teks(nama):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["baris"][1]["nama"] = nama
    svg = periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, "uji") + "</div>")
    assert nama in teks_svg(svg)


def test_field_parameter_tambahan_atau_hilang_ditolak_proyektor():
    soal = _soal()
    for rusak in (
        {**soal.parameter, "kunci": "3"},
        {**soal.parameter, "versi_katalog": 2},
        {k: v for k, v in soal.parameter.items() if k != "x"},
        {k: v for k, v in soal.parameter.items() if k != "n3"},
        {**soal.parameter, "tanya": 0},
        {**soal.parameter, "varian": "lain"},
        {**soal.parameter, "n1": True},
        {**soal.parameter, "n1": 5.0},
        {**soal.parameter, "tema": "kendaraan"},
        {**soal.parameter, "n2": 5},
        {**soal.parameter, "x": 1, "y": 0},
    ):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)


# ── invarian 5: batas viewBox dan tanpa tumpang tindih ───────────────────

def _kotak_image(svg):
    return tuple((float(e.get("x")), float(e.get("y")), float(e.get("width")), float(e.get("height")))
                 for e in elemen(svg, "image"))


def _tumpang_tindih(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _data_penuh(nama):
    return {
        "adegan": "deret_ikon",
        "baris": [{"nama": nama + str(i), "ikon": IKON_DIDUKUNG[i], "jumlah": 12} for i in range(4)],
        "satuan_ikon": 1, "tanya": {"varian": "terbanyak"},
    }


@pytest.mark.parametrize("nama", ("A", "Kelinci", "W" * 23))
def test_empat_baris_dua_belas_ikon_muat_dan_tidak_tumpang_tindih(nama):
    html_svg = adegan_awal_svg.render_adegan_awal(_data_penuh(nama), "batas")
    svg = periksa_xml("<div>" + html_svg + "</div>")
    periksa_batas_koordinat(svg)
    kotak = _kotak_image(svg)
    assert len(kotak) == 48
    assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])
    lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
    assert lebar == T.ADEGAN_LEBAR
    assert all(x + w <= lebar and y + h <= tinggi for x, y, w, h in kotak)


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_semua_soal_sah_dalam_viewbox_dan_ikon_tidak_bertumpuk(varian):
    for parameter in _semua_parameter(varian)[::41]:
        svg = _svg(parameter)
        periksa_batas_koordinat(svg)
        kotak = _kotak_image(svg)
        assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])


def test_label_sejajar_dengan_ikon_pertama_barisnya():
    svg = _svg()
    for baris in kelas(svg, "baris-adegan"):
        ys = [float(e.get("y")) for e in elemen(baris, "image")]
        label_y = float(elemen(baris, "text")[0].get("y"))
        assert min(ys) <= label_y <= min(ys) + T.ADEGAN_IKON + 1


def test_label_panjang_dipecah_tanpa_mengubah_isi():
    data = _data_penuh("W" * 23)
    svg = periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, "x") + "</div>")
    nama = tuple(label for label, _ in _baris_svg(svg))
    assert nama == tuple(("W" * 23 + str(i)).lower() for i in range(4))


# ── invarian 6: aksesibilitas ────────────────────────────────────────────

def test_role_title_desc_terhubung_dan_tidak_memuat_jumlah():
    svg = _svg()
    judul, = elemen(svg, "title")
    uraian, = elemen(svg, "desc")
    assert svg.get("role") == "img"
    label = svg.get("aria-labelledby").split()
    assert label == [judul.get("id"), uraian.get("id")]
    isi = "".join(uraian.itertext())
    assert len(isi.split()) >= 4
    assert "".join(judul.itertext()).strip()
    assert not re.search(r"\d", isi + "".join(judul.itertext()))
    for nama in ("Bola", "Mobil", "Boneka"):
        assert nama in isi


def test_uraian_hanya_bergantung_pada_nama_bukan_jumlah_atau_pertanyaan():
    a = {"varian": "baca", "tema": "buah", "n1": 1, "n2": 2, "n3": 3, "tanya": 0}
    b = {"varian": "terbanyak", "tema": "buah", "n1": 8, "n2": 7, "n3": 6}
    desc = [("".join(elemen(_svg(p), "desc")[0].itertext())) for p in (a, b)]
    assert desc[0] == desc[1]


def test_semua_teks_svg_satu_warna_token_dan_tidak_kosong():
    svg = _svg()
    warna = {e.get("fill") for e in svg.iter() if e.get("fill")}
    assert warna == {T.TEKS_UTAMA}
    assert all(t for t in teks_svg(svg))


def test_id_unik_pada_lembar_dengan_banyak_soal_berulang():
    ids = []
    for i in range(6):
        svg = _svg(namespace=f"lembar-{i}")
        ids += [e.get("id") for e in svg.iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12
