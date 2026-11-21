"""Keluarga visual `matematika-awal`: ukur_satuan_tak_baku bergambar (adegan_awal v1, `pita_ukur`).

Solver mandiri HANYA membaca teks proyeksi dan SVG hasil `render_pertanyaan`
(banyak `<image class="unit-ukur">` per `<g class="batang-ukur">`, label batang, dan
varian dari kalimat pertanyaan), lewat `penyajian_dari_soal`, lalu dibandingkan dengan
`soal.kunci` untuk seluruh domain P1.
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
import awal_ukur_satuan_tak_baku as sumber
import brand
import design_tokens as T
from adegan_awal_data import IKON_DIDUKUNG
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import (
    DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian,
)
from visual_inventory import DENOMINATOR_KANONIS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import (
    elemen, kelas, kontras, lokal, luminansi, periksa_xml, teks_svg,
)

TID = sumber.TEMPLATE_ID
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
CONTOH = {"varian": "banding", "satuan": "klip", "benda": 0, "benda2": 1, "p1": 9, "p2": 7}
CONTOH_SAMBUNG = {"varian": "sambung", "satuan": "ubin", "benda": 0, "p1": 10, "p2": 9}
CONTOH_SELISIH = {"varian": "selisih", "satuan": "balok", "benda": 0, "benda2": 1, "p1": 10, "p2": 6}
NARASI = "Perhatikan gambar. Benda diukur dengan {satuan}."
UNIT = "unit-ukur"
UKURAN_DOMAIN = {"banding": 504, "selisih": 504, "sambung": 504}


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _soal(parameter=None):
    return replace(sumber.ukur_satuan_tak_baku(**(parameter or CONTOH)), level="P1")


def _penyajian(parameter=None):
    return penyajian_dari_soal(_soal(parameter))


def _svg(parameter=None, *, namespace="uji-ukur", gaya="cetak"):
    return periksa_xml(render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya))


def _semua_parameter(varian):
    return tuple(p for p in sumber.domain_parameter("P1") if p["varian"] == varian)


def _batang(nama, jumlah, *, ikon="pensil", warna="netral"):
    return {"nama": nama, "ikon": ikon, "warna": warna, "jumlah": jumlah}


def _data_tumpuk(jumlah=(9, 6), satuan="klip"):
    return {"adegan": "pita_ukur", "satuan": satuan, "susun": "bertumpuk",
            "batang": [_batang("pensil", jumlah[0]), _batang("buku", jumlah[1], ikon="buku")],
            "tanya": {"varian": "banding"}}


def _data_sambung(jumlah=(7, 5), satuan="ubin", nama=("pita merah", "pita biru")):
    return {"adegan": "pita_ukur", "satuan": satuan, "susun": "sambung",
            "batang": [_batang(nama[0], jumlah[0], ikon=None, warna="merah"),
                       _batang(nama[1], jumlah[1], ikon=None, warna="biru")],
            "tanya": {"varian": "sambung"}}


def _svg_data(data, namespace="uji"):
    return periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, namespace) + "</div>")


# ── solver mandiri: hanya teks proyeksi + SVG ────────────────────────────

def _unit_dalam(batang):
    return [e for e in elemen(batang, "image") if UNIT in e.get("class", "").split()]


def _batang_svg(svg):
    """Daftar (label, banyak <image class=unit-ukur>) per batang, urut tampil."""
    hasil = []
    for batang in kelas(svg, "batang-ukur"):
        label = "".join("".join(t.itertext()) for t in elemen(batang, "text"))
        hasil.append((label, len(_unit_dalam(batang))))
    return tuple(hasil)


def _jawab(teks, svg):
    banyak = dict(_batang_svg(svg))
    if cocok := re.search(r"([A-Z][a-z]+) lebih panjang berapa [a-z]+ daripada ([a-z]+)\?$", teks):
        return str(banyak[cocok[1].lower()] - banyak[cocok[2]])
    if re.search(r"Berapa [a-z]+ panjang semuanya\?$", teks):
        return str(sum(banyak.values()))
    if teks.endswith("Mana yang lebih panjang?"):
        return max(banyak, key=banyak.get)
    raise AssertionError(("pertanyaan tidak dikenal", teks))


def _label_dan_jumlah(parameter):
    satuan, p1, p2 = parameter["satuan"], parameter["p1"], parameter["p2"]
    if parameter["varian"] == "sambung":
        benda = sumber.BENDA_SAMBUNG[parameter["benda"]]
        return ((f"{benda} merah", p1), (f"{benda} biru", p2))
    daftar = sumber.BENDA_BANDING[satuan]
    return ((daftar[parameter["benda"]], p1), (daftar[parameter["benda2"]], p2))


def test_domain_p1_utuh_seperti_semula():
    ukuran = {v: len(_semua_parameter(v)) for v in sumber.VARIAN}
    assert ukuran == UKURAN_DOMAIN


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_solver_svg_sama_dengan_kunci_seluruh_domain_p1(varian):
    for parameter in _semua_parameter(varian):
        soal = _soal(parameter)
        penyajian = penyajian_dari_soal(soal)
        svg = periksa_xml(render_pertanyaan(penyajian, namespace="sapuan"))
        assert _batang_svg(svg) == _label_dan_jumlah(parameter), parameter
        assert _jawab(penyajian.teks_soal, svg) == soal.kunci, parameter


def test_label_gambar_sama_dengan_nama_pada_kunci_banding():
    for parameter in _semua_parameter("banding")[::7]:
        soal = _soal(parameter)
        assert soal.kunci in dict(_batang_svg(_svg(parameter)))


# ── invarian 1: tanpa flag tidak berubah ─────────────────────────────────

@pytest.mark.parametrize("parameter", (CONTOH, CONTOH_SAMBUNG, CONTOH_SELISIH),
                         ids=lambda p: p["varian"])
@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
def test_tanpa_keluarga_matematika_awal_teks_lama_persis(monkeypatch, flag, parameter):
    if flag is None:
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    else:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", flag)
    soal = _soal(parameter)
    penyajian = penyajian_dari_soal(soal)
    assert penyajian.status_visual == "tanpa_visual"
    assert penyajian.mode_representasi == "teks-v1"
    assert penyajian.descriptor is None
    assert penyajian.teks_soal == soal.teks
    assert "panjangnya" in penyajian.teks_soal and re.search(r"\d", penyajian.teks_soal)
    assert "<svg" not in render_pertanyaan(penyajian)


# ── invarian 2: teks, status, kontrak hitung ─────────────────────────────

def test_flag_aktif_banding_teks_hanya_narasi_dan_pertanyaan():
    penyajian = _penyajian()
    assert penyajian.status_visual == "siap"
    assert penyajian.mode_representasi == "adegan_awal-v1"
    assert penyajian.teks_soal == NARASI.format(satuan="klip") + "\nMana yang lebih panjang?"


def test_flag_aktif_selisih_dan_sambung_memuat_kalimat_pertanyaan_sumber():
    selisih = _penyajian(CONTOH_SELISIH).teks_soal
    assert selisih == NARASI.format(satuan="balok") + "\nSapu lebih panjang berapa balok daripada tongkat?"
    sambung = _penyajian(CONTOH_SAMBUNG).teks_soal
    assert sambung == (NARASI.format(satuan="ubin")
                       + "\nKedua pita disambung ujung ke ujung. Berapa ubin panjang semuanya?")


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_teks_tanpa_angka_panjang_dan_tidak_menyebut_kunci_angka(varian):
    for parameter in _semua_parameter(varian)[::11]:
        soal = _soal(parameter)
        teks = _penyajian(parameter).teks_soal
        assert not re.search(r"[0-9]|panjangnya", teks), teks
        assert teks.startswith(NARASI.format(satuan=parameter["satuan"]) + "\n")
        sisa = teks.split("\n", 1)[1]
        assert sisa in soal.teks and soal.teks.endswith(sisa)
        if not soal.kunci.isdigit():
            assert f"jawab {soal.kunci}" not in teks.lower()


def test_descriptor_tidak_membawa_kunci_atau_jawaban():
    for parameter, susun in ((CONTOH, "bertumpuk"), (CONTOH_SAMBUNG, "sambung"),
                             (CONTOH_SELISIH, "bertumpuk")):
        penyajian = _penyajian(parameter)
        data = penyajian.descriptor.ke_dict()["data"]
        assert set(data) == {"adegan", "satuan", "batang", "susun", "tanya"}
        assert data["susun"] == susun and data["adegan"] == "pita_ukur"
        assert all(set(b) == {"nama", "ikon", "warna", "jumlah"} for b in data["batang"])
        assert "kunci" not in serialisasi_penyajian(penyajian)
    banding = _penyajian(CONTOH).descriptor.ke_dict()["data"]
    assert banding["tanya"] == {"varian": "banding"}


@pytest.mark.parametrize("jumlah", range(1, 13))
def test_kontrak_hitung_unit_per_batang_sama_jumlah_dan_ikon_benda_bukan_unit(jumlah):
    svg = _svg_data(_data_tumpuk((jumlah, 12)))
    (_, a), (_, b) = _batang_svg(svg)
    assert (a, b) == (jumlah, 12)
    for batang in kelas(svg, "batang-ukur"):
        semua = elemen(batang, "image")
        benda = [e for e in semua if "ikon-benda" in e.get("class", "").split()]
        assert len(benda) == 1 and len(semua) == len(_unit_dalam(batang)) + 1
        assert benda[0] not in _unit_dalam(batang)


@pytest.mark.parametrize("satuan", sumber.SATUAN)
def test_unit_adalah_ikon_satuan_dan_menutup_pita_tanpa_celah(satuan):
    svg = _svg_data(_data_tumpuk((9, 6), satuan))
    for batang, n in zip(kelas(svg, "batang-ukur"), (9, 6)):
        pita, = [e for e in elemen(batang, "rect") if "pita" in e.get("class", "").split()]
        unit = _unit_dalam(batang)
        assert len(unit) == n
        assert all(u.get("href") == f"/aset/ikon-{satuan}-v1.png" for u in unit)
        sel = float(pita.get("height"))
        assert float(pita.get("width")) == n * sel
        xs = [float(u.get("x")) for u in unit]
        assert xs[0] == float(pita.get("x"))
        assert all(b - a == sel for a, b in zip(xs, xs[1:]))
        assert all(float(u.get("width")) == float(u.get("height")) == sel for u in unit)
        assert all(float(u.get("y")) == float(pita.get("y")) for u in unit)


def test_klip_direbahkan_90_derajat_di_pusat_selnya_ubin_dan_balok_apa_adanya():
    for satuan, putar in (("klip", True), ("ubin", False), ("balok", False)):
        svg = _svg_data(_data_tumpuk((4, 3), satuan))
        for u in elemen(svg, "image"):
            if UNIT not in u.get("class", "").split():
                assert "transform" not in u.attrib
                continue
            if not putar:
                assert "transform" not in u.attrib
                continue
            x, y, sisi = float(u.get("x")), float(u.get("y")), float(u.get("width"))
            assert u.get("transform") == f"rotate(90 {x + sisi / 2:g} {y + sisi / 2:g})"


def test_dua_batang_bertumpuk_rata_kiri_dengan_sel_sama_agar_panjang_jujur():
    for jumlah in ((9, 6), (3, 10), (12, 1), (5, 5)):
        svg = _svg_data(_data_tumpuk(jumlah))
        pita = kelas(svg, "pita")
        assert len(pita) == 2
        assert pita[0].get("x") == pita[1].get("x") == str(T.ADEGAN_IKON_X)
        assert pita[0].get("height") == pita[1].get("height")
        sel = float(pita[0].get("height"))
        assert [float(p.get("width")) for p in pita] == [n * sel for n in jumlah]
        assert float(pita[0].get("y")) < float(pita[1].get("y"))


def test_sambung_dua_potong_satu_deret_ujung_ke_ujung():
    for jumlah in ((7, 5), (3, 10), (10, 9), (12, 12), (1, 1)):
        svg = _svg_data(_data_sambung(jumlah))
        satu, dua = kelas(svg, "pita")
        sel = float(satu.get("height"))
        assert satu.get("y") == dua.get("y") and satu.get("height") == dua.get("height")
        assert float(dua.get("x")) == float(satu.get("x")) + jumlah[0] * sel
        assert [float(p.get("width")) for p in (satu, dua)] == [n * sel for n in jumlah]
        assert float(dua.get("x")) + jumlah[1] * sel <= T.ADEGAN_LEBAR - T.ADEGAN_MARGIN
        assert not elemen(svg, "image") or all(
            UNIT in e.get("class", "").split() for e in elemen(svg, "image"))


def test_sambung_label_teks_dan_warna_berbeda_label_tidak_bergantung_warna():
    svg = _svg_data(_data_sambung())
    (a, _), (b, _) = _batang_svg(svg)
    assert (a, b) == ("pita merah", "pita biru")
    satu, dua = kelas(svg, "pita")
    assert satu.get("fill") != dua.get("fill") and satu.get("stroke") != dua.get("stroke")
    assert {satu.get("fill"), dua.get("fill")} == {T.ADEGAN_PITA_ISI_MERAH, T.ADEGAN_PITA_ISI_BIRU}


def test_sambung_label_pertama_di_atas_dan_kedua_di_bawah_tanpa_tumpang_tindih():
    for jumlah in ((3, 3), (7, 5), (12, 12), (10, 9)):
        svg = _svg_data(_data_sambung(jumlah))
        pita = kelas(svg, "pita")[0]
        atas, bawah = float(pita.get("y")), float(pita.get("y")) + float(pita.get("height"))
        label = elemen(svg, "text")
        assert len(label) == 2
        y1, y2 = float(label[0].get("y")), float(label[1].get("y"))
        assert y1 < atas and y2 > bawah + T.ADEGAN_UKUR_JARAK
        assert label[0].get("text-anchor") is None and label[1].get("text-anchor") == "end"
        lebar_label = len("pita merah") * 0.6 * T.ADEGAN_FONT
        assert float(label[0].get("x")) + lebar_label <= T.ADEGAN_LEBAR
        assert float(label[1].get("x")) - len("pita biru") * 0.6 * T.ADEGAN_FONT >= 0


def test_ringkasan_non_html_menyebut_fakta_batang():
    assert "pensil sepanjang 9 klip" in ringkasan_pertanyaan(_penyajian())
    sambung = ringkasan_pertanyaan(_penyajian(CONTOH_SAMBUNG))
    assert "disambung ujung ke ujung" in sambung and "pita merah sepanjang 10 ubin" in sambung


# ── invarian 3: determinisme dan fingerprint ─────────────────────────────

def test_render_dua_kali_identik_byte_per_byte():
    penyajian = _penyajian()
    assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
    assert _penyajian().fingerprint_penyajian == _penyajian().fingerprint_penyajian


def test_fingerprint_dipatok_agar_perubahan_penyajian_disengaja():
    penyajian = _penyajian()
    assert penyajian.fingerprint_matematis == (
        "4411073cc2c7f2584c9964ca277b1e4e128b7fa39460c7d7521b31d8918312d0")
    assert penyajian.fingerprint_penyajian == (
        "a09e2b59cec287b2db7a768fdf99a39036f0a1c34f757b54391b96e61698214e")


@pytest.mark.parametrize("parameter", (CONTOH, CONTOH_SAMBUNG, CONTOH_SELISIH),
                         ids=lambda p: p["varian"])
def test_round_trip_serialisasi_dan_fingerprint_matematis_sama_dengan_mode_teks(monkeypatch, parameter):
    penyajian = _penyajian(parameter)
    assert deserialisasi_penyajian(serialisasi_penyajian(penyajian)) == penyajian
    monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    teks = penyajian_dari_soal(_soal(parameter))
    assert teks.fingerprint_matematis == penyajian.fingerprint_matematis
    assert teks.fingerprint_penyajian != penyajian.fingerprint_penyajian


def test_snapshot_dan_html_identik_antarproses():
    kode = (
        "import hashlib\n"
        "from dataclasses import replace\n"
        "import awal_ukur_satuan_tak_baku as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P1')[::37]:\n"
        "    s = penyajian_dari_soal(replace(m.ukur_satuan_tak_baku(**p), level='P1'))\n"
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
@pytest.mark.parametrize("parameter", (CONTOH, CONTOH_SAMBUNG, CONTOH_SELISIH),
                         ids=lambda p: p["varian"])
def test_xml_allowlist_dan_satu_satunya_href_adalah_ikon_terdaftar(parameter, gaya):
    hasil = render_pertanyaan(_penyajian(parameter), gaya=gaya)
    svg = periksa_xml(hasil)
    tanpa_xmlns = hasil.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert not re.search(r"<script|foreignObject|javascript:|https?:|//|\son[a-z]+=", tanpa_xmlns, re.I)
    href = [e.get("href") for e in svg.iter() if "href" in e.attrib]
    assert href and all(re.fullmatch(r"/aset/ikon-[a-z]+-v1\.png", h) for h in href)
    assert {h.rsplit("/", 1)[1] for h in href} <= set(brand.ASET)
    assert all("href" not in e.attrib for e in svg.iter() if lokal(e) != "image")
    assert all(("transform" not in e.attrib) or lokal(e) == "image" for e in svg.iter())


def test_semua_href_domain_adalah_ikon_di_allow_list():
    for parameter in sumber.domain_parameter("P1")[::29]:
        svg = _svg(parameter)
        nama = {e.get("href")[len("/aset/ikon-"):-len("-v1.png")] for e in elemen(svg, "image")}
        assert nama <= set(IKON_DIDUKUNG)


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


@pytest.mark.parametrize("ikon", (
    "../pensil", "pensil.png", "/aset/ikon-pensil-v1.png", "https://contoh.invalid/x.png",
    'pensil" onload="x',
))
def test_ikon_liar_atau_traversal_ditolak_validator_dan_renderer(ikon):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["batang"][0]["ikon"] = ikon
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


def test_satuan_liar_ditolak_renderer():
    for satuan in ("cm", "klip/../x", '" onload="x', "maskot", None):
        data = _penyajian().descriptor.ke_dict()["data"]
        data["satuan"] = satuan
        with pytest.raises(ValueError):
            adegan_awal_svg.render_adegan_awal(data, "uji")


@pytest.mark.parametrize("nama", ("<script>x</script>", '<image href="//x.invalid/a"/>', "A<", "onload=x>"))
def test_markup_pada_nama_batang_ditolak(nama):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["batang"][1]["nama"] = nama
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


def test_nama_duplikat_ditolak_validator_dan_renderer():
    data = _penyajian().descriptor.ke_dict()["data"]
    data["batang"][1]["nama"] = data["batang"][0]["nama"].upper()
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


@pytest.mark.parametrize("nama", ("A & B", "'kutip' \"ganda\"", "Ａ＆Ｂ"))
def test_nama_batang_berkarakter_khusus_hanya_menjadi_teks(nama):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["batang"][1]["nama"] = nama
    svg = _svg_data(data)
    assert nama in teks_svg(svg)


@pytest.mark.parametrize("jumlah", (0, 13, -1, 2.0, True, "3"))
def test_jumlah_di_luar_batas_ditolak_renderer(jumlah):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["batang"][0]["jumlah"] = jumlah
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


def test_field_parameter_tambahan_atau_hilang_ditolak_proyektor():
    for dasar in (_soal(CONTOH).parameter, _soal(CONTOH_SAMBUNG).parameter):
        rusak = [
            {**dasar, "kunci": "pensil"}, {**dasar, "versi_katalog": 2},
            {k: v for k, v in dasar.items() if k != "p2"},
            {k: v for k, v in dasar.items() if k != "satuan"},
            {**dasar, "varian": "lain"}, {**dasar, "satuan": "cm"},
            {**dasar, "p1": True}, {**dasar, "p1": 6.0}, {**dasar, "p1": 2}, {**dasar, "p1": 11},
            {**dasar, "benda": 9}, {**dasar, "p2": dasar["p1"]},
        ]
        for isi in rusak:
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, isi)
    banding = _soal(CONTOH).parameter
    for isi in ({k: v for k, v in banding.items() if k != "benda2"},
                {**banding, "benda2": banding["benda"]}, {**banding, "benda2": None}):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, isi)
    sambung = _soal(CONTOH_SAMBUNG).parameter
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(TID, {**sambung, "benda2": 1})


def _ubahan_teks(satuan):
    return (
        lambda teks: teks.replace("panjangnya", "ukurannya"),            # kalimat data berubah
        lambda teks: teks.replace(" panjangnya", " panjang nya"),
        lambda teks: "Info 3. " + teks,                                  # kalimat tambahan di depan
        lambda teks: teks + " Jelaskan 2 alasan?",                       # kalimat tambahan di akhir
        lambda teks: teks.replace(f"{satuan}.", f"{satuan}, ya.", 1),    # akhiran kalimat data
        lambda teks: teks.replace("?", "!"),                             # bukan pertanyaan
        lambda teks: re.sub(r"\.\s", ". Catatan 9. ", teks, count=1),    # angka lolos ke sisa
        lambda teks: teks.replace("Berapa", "Berapa banyak", 1).replace("Mana", "Apa", 1)
        if "Berapa" in teks or "Mana" in teks else teks + "x",           # sisa kalimat berubah bentuk
    )


def test_proyeksi_gagal_keras_bila_bentuk_teks_sumber_berubah(monkeypatch):
    asli = sumber.ukur_satuan_tak_baku
    kasus = 0
    for parameter in (CONTOH, CONTOH_SAMBUNG, CONTOH_SELISIH):
        soal = _soal(parameter)
        for ubah in _ubahan_teks(parameter["satuan"]):
            def palsu(**isi):
                hasil = asli(**isi)
                baru = ubah(hasil.teks)
                assert baru != hasil.teks  # setiap ubahan benar-benar mengubah teks
                return replace(hasil, teks=baru)
            monkeypatch.setattr(sumber, "ukur_satuan_tak_baku", palsu)
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, soal.parameter)
            kasus += 1
        monkeypatch.setattr(sumber, "ukur_satuan_tak_baku", asli)
    assert kasus == 3 * 8


def test_proyeksi_gagal_keras_bila_nama_benda_di_teks_tak_sama_dengan_struktur_sumber(monkeypatch):
    asli = sumber.ukur_satuan_tak_baku
    soal = _soal(CONTOH)

    def palsu(**isi):
        hasil = asli(**isi)
        return replace(hasil, teks=hasil.teks.replace("Pensil", "Buku", 1))
    monkeypatch.setattr(sumber, "ukur_satuan_tak_baku", palsu)
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(TID, soal.parameter)


def test_proyeksi_gagal_keras_untuk_benda_tanpa_ikon(monkeypatch):
    monkeypatch.setitem(sumber.BENDA_BANDING, "klip", ("hantu", "buku", "sendok"))
    with pytest.raises(ValueError, match="tanpa ikon"):
        proyeksi_matematika_awal(TID, _soal(CONTOH).parameter)


# ── invarian 5: batas viewBox dan tanpa tumpang tindih ───────────────────

def _kotak(e):
    return (float(e.get("x")), float(e.get("y")), float(e.get("width")), float(e.get("height")))


def _tumpang_tindih(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


@pytest.mark.parametrize("satuan", sumber.SATUAN)
@pytest.mark.parametrize("jumlah", ((12, 12), (12, 1), (3, 10), (1, 1)))
def test_batas_ekstrem_bertumpuk_dan_sambung_muat_dan_unit_tidak_bertumpuk(satuan, jumlah):
    for data in (_data_tumpuk(jumlah, satuan), _data_sambung(jumlah, satuan)):
        svg = _svg_data(data, "batas")
        periksa_batas_koordinat(svg)
        lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
        assert lebar == T.ADEGAN_LEBAR
        kotak = [_kotak(e) for e in elemen(svg, "image")]
        assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])
        assert all(x >= 0 and y >= 0 and x + w <= lebar and y + h <= tinggi for x, y, w, h in kotak)
        for pita in kelas(svg, "pita"):
            x, y, w, h = _kotak(pita)
            assert x >= 0 and y >= 0 and x + w <= lebar and y + h <= tinggi


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_semua_soal_sah_dalam_viewbox_dan_elemen_tidak_bertumpuk(varian):
    for parameter in _semua_parameter(varian)[::17]:
        svg = _svg(parameter)
        periksa_batas_koordinat(svg)
        kotak = [_kotak(e) for e in elemen(svg, "image")]
        assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])


@pytest.mark.parametrize("nama", ("tongkat", "w" * 8, "w" * 24))
def test_kolom_kiri_bertumpuk_label_dan_ikon_benda_tidak_menimpa_pita(nama):
    data = _data_tumpuk()
    lain = nama[:-1] + ("q" if nama[-1] != "q" else "z")
    data["batang"] = [_batang(nama, 12), _batang(lain, 12, ikon="buku")]
    svg = _svg_data(data)
    ruang = T.ADEGAN_IKON_X - T.ADEGAN_MARGIN
    for batang in kelas(svg, "batang-ukur"):
        benda, = [e for e in elemen(batang, "image") if "ikon-benda" in e.get("class", "").split()]
        assert float(benda.get("x")) + float(benda.get("width")) <= T.ADEGAN_IKON_X
        for teks in elemen(batang, "text"):
            potongan = [("".join(t.itertext())) for t in elemen(teks, "tspan")] or ["".join(teks.itertext())]
            assert max(len(p) for p in potongan) <= T.ADEGAN_LABEL_PER_BARIS
            assert max(len(p) for p in potongan) * 0.6 * T.ADEGAN_FONT <= ruang
        pita, = elemen(batang, "rect")
        # ikon benda dan label di kolom kiri; pita mulai di kanan kolom itu
        assert float(pita.get("x")) >= T.ADEGAN_IKON_X


def test_batang_bertumpuk_tidak_tumpang_tindih_secara_vertikal():
    svg = _svg_data(_data_tumpuk((12, 12)))
    atas, bawah = kelas(svg, "batang-ukur")
    y_atas = [float(e.get("y")) + float(e.get("height")) for e in elemen(atas, "image")]
    y_bawah = [float(e.get("y")) for e in elemen(bawah, "image")]
    assert max(y_atas) < min(y_bawah)


# ── invarian 6: aksesibilitas ────────────────────────────────────────────

@pytest.mark.parametrize("parameter", (CONTOH, CONTOH_SAMBUNG, CONTOH_SELISIH),
                         ids=lambda p: p["varian"])
def test_role_title_desc_terhubung_dan_tidak_memuat_jumlah(parameter):
    svg = _svg(parameter)
    judul, = elemen(svg, "title")
    uraian, = elemen(svg, "desc")
    assert svg.get("role") == "img"
    assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
    isi = "".join(uraian.itertext())
    assert len(isi.split()) >= 4 and "".join(judul.itertext()).strip()
    assert not re.search(r"\d", isi + "".join(judul.itertext()))
    assert parameter["satuan"] in isi


def test_uraian_tidak_bergantung_pada_panjang_atau_pertanyaan():
    a = {**CONTOH, "p1": 9, "p2": 7}
    b = {**CONTOH, "p1": 3, "p2": 10}
    c = {**CONTOH, "varian": "selisih", "p1": 8, "p2": 4}
    desc = ["".join(elemen(_svg(p), "desc")[0].itertext()) for p in (a, b, c)]
    assert desc[0] == desc[1] == desc[2]
    sambung = ["".join(elemen(_svg({**CONTOH_SAMBUNG, "p1": x, "p2": y}), "desc")[0].itertext())
               for x, y in ((10, 9), (3, 4))]
    assert sambung[0] == sambung[1]


def test_teks_svg_satu_warna_token_kontras_dan_semua_paint_adalah_token():
    token = {v.casefold() for v in vars(T).values() if isinstance(v, str) and v.startswith("#")}
    for parameter in (CONTOH, CONTOH_SAMBUNG):
        svg = _svg(parameter)
        assert {e.get("fill") for e in elemen(svg, "text")} == {T.TEKS_UTAMA}
        for e in svg.iter():
            for atribut in ("fill", "stroke"):
                if e.get(atribut, "").startswith("#"):
                    assert e.get(atribut).casefold() in token
        assert all(t for t in teks_svg(svg))
    for garis in (T.ADEGAN_PITA_GARIS_NETRAL, T.ADEGAN_PITA_GARIS_MERAH, T.ADEGAN_PITA_GARIS_BIRU):
        assert kontras(garis, T.LATAR_KARTU) >= 3


def test_pita_merah_dan_biru_berbeda_terang_agar_terbaca_hitam_putih():
    garis = [luminansi(c) for c in (T.ADEGAN_PITA_GARIS_MERAH, T.ADEGAN_PITA_GARIS_BIRU)]
    isi = [luminansi(c) for c in (T.ADEGAN_PITA_ISI_MERAH, T.ADEGAN_PITA_ISI_BIRU)]
    assert abs(garis[0] - garis[1]) > 0.02 or abs(isi[0] - isi[1]) > 0.02
    # pembeda utama tetap label teks, bukan warna
    assert {a for a, _ in _batang_svg(_svg_data(_data_sambung()))} == {"pita merah", "pita biru"}


def test_id_unik_pada_lembar_dengan_banyak_soal_berulang():
    ids = []
    for i in range(6):
        ids += [e.get("id") for e in _svg(namespace=f"lembar-{i}").iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12


# ── invarian 7: inventaris dan cakupan benda ─────────────────────────────

def test_inventaris_menandai_ukur_satuan_tak_baku_wajib_visual_untuk_semua_varian():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {d["varian"] for d in baris} == {f"varian={v}" for v in sumber.VARIAN}
    assert {d["level"] for d in baris} == {"P1"}


def test_semua_benda_dan_satuan_sumber_punya_ikon_di_allow_list():
    for satuan, daftar in sumber.BENDA_BANDING.items():
        assert satuan in IKON_DIDUKUNG
        assert all(benda in IKON_DIDUKUNG for benda in daftar), satuan
    assert all(satuan in IKON_DIDUKUNG for satuan in sumber.SATUAN)
