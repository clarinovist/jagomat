"""Keluarga visual `matematika-awal`: ukur_sudut_awal bergambar (adegan_awal v1, `busur`).

Solver mandiri HANYA membaca teks proyeksi dan SVG hasil `render_pertanyaan` lewat
`penyajian_dari_soal`: arah tiap `<line class="sinar-sudut">` dihitung dari koordinat pusat dan
ujungnya dengan atan2 (huruf sinar dicocokkan lewat posisi huruf, bukan urutan di berkas),
lalu besar sudut, golongan, perbandingan, atau selisih dihitung dan dibandingkan dengan
`soal.kunci` untuk SELURUH domain P5 (sapuan penuh, tanpa stride). Kebocoran diuji pada string
HTML mentah: SVG tanpa sinar dan huruf (huruf sinar dan huruf titik) harus identik byte per byte
untuk seluruh domain, jadi kelas, id, judul, uraian, transform, dan atribut tidak memuat besar sudut,
banyak sinar, arah alas, atau skala yang dipakai. Label kedua skala diuji konsisten dengan posisinya.
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

import adegan_awal_busur_data
import adegan_awal_data
import adegan_awal_svg
import awal_ukur_sudut_awal as sumber
import design_tokens as T
from question_views import penyajian_dari_soal
from sudut_solver_helpers import (GESER, KAKI, KAKI_NOL, TANYA_BANDING, TANYA_BESAR, TANYA_JENIS,
                                  TANYA_SELISIH, jawab_dari_sudut, solver_dari_teks)
from topic_matematika_awal_visual import proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian
from visual_inventory import DENOMINATOR_KANONIS, VARIAN_SENGAJA_TEKS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, kontras, lokal, periksa_xml

TID = sumber.TEMPLATE_ID
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
KELAS_BOLEH = {"busur-gambar", "badan-busur", "tanda-satuan", "tanda-lima", "tanda-sepuluh",
               "garis-alas", "angka-luar", "angka-dalam", "latar-angka", "sinar-sudut", "pusat-busur",
               "huruf-sinar", "huruf-titik"}
TAG_BOLEH = {"svg", "title", "desc", "g", "circle", "path", "line", "text", "rect"}
TOLERANSI_ARAH = 0.5  # derajat; koordinat dibulatkan dua desimal
TOLERANSI_ANGKA_PUSAT = 1.0
TOLERANSI_ANGKA_ALAS = 4.0  # angka 0 dan 180 sengaja naik dari garis alas
PENGANTAR = "Perhatikan gambar busur derajat."
CONTOH_NOL_KANAN = dict(varian="baca_dari_nol", arah="kanan", sudut=70)
CONTOH_NOL_KIRI = dict(varian="baca_dari_nol", arah="kiri", sudut=125)
CONTOH_GESER = dict(varian="baca_geser", a=30, b=110)
CONTOH_JENIS = dict(varian="jenis_sudut", arah="kiri", sudut=90)
CONTOH_BANDING = dict(varian="banding", arah="kanan", b=40, c=130)
CONTOH_SELISIH = dict(varian="selisih_dua", arah="kiri", b=150, c=60)
CONTOH = (CONTOH_NOL_KANAN, CONTOH_NOL_KIRI, CONTOH_GESER, CONTOH_JENIS, CONTOH_BANDING, CONTOH_SELISIH)
NAMA_CONTOH = ("nol_kanan", "nol_kiri", "geser", "jenis", "banding", "selisih")
SINAR_HURUF_TITIK = re.compile(
    r'<line class="sinar-sudut"[^>]*/>|<text class="huruf-(?:sinar|titik)"[^>]*>[^<]*</text>')

FINGERPRINT_DIPATOK = {
    "nol_kanan": ("087a02b3642e3c10b7a65fb6e682aaf207d193cb6cb71d25104f9986838606b0",
                  "25918b3adb6b34070e9f0293f6d08844e5d3dc040c1408c2086eddd73c43e193"),
    "nol_kiri": ("9f5aa4efb96089431d8a3accaaac532fa23915535b194dcdfd047f3e6005b3b4",
                 "582e1730ad3b390759a0f1caff17b80e97cff3f20f409ab5a2838951c1c70245"),
    "geser": ("c187535bee9fd342030435082756c88af500dd110c79974fedde0edc045b7244",
              "a42f61e1f713e34c6fce46f8127d11b0821362ce4e2d8ecd0f263a357b283807"),
    "jenis": ("4acb2021c733f54021cb00c1ad4c719e975fb6cc202690ec8376b7562db3de8d",
              "10075ae31c2798afe0e5412a108e2c6e38286e7a22ff87040edfe2eb651cf487"),
    "banding": ("b7247c92b0a8fe75b44b865fe92e9c90762071f10bfefeb641ec0d24b4afc335",
                "697c460800b37b5bf283362ac7afff5b694d27faeb3090c26d7a4090e6037eab"),
    "selisih": ("63dbade73a2079809f687cc1442cac3813d9458c77b170025e9319952015b265",
                "a58d2272ff62fefc7b0eafa6f2c7915b872262c978b4ac8a0d8e284f26c0e1bb"),
}


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _soal(parameter):
    return replace(sumber.ukur_sudut_awal(**parameter), level="P5")


def _penyajian(parameter):
    return penyajian_dari_soal(_soal(parameter))


def _html(parameter, *, namespace="uji-busur", gaya="cetak"):
    return render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya)


def _svg(parameter, **kw):
    return periksa_xml(_html(parameter, **kw))


def _domain(*varian):
    return tuple(p for p in sumber.domain_parameter("P5") if p["varian"] in varian)


def _data(sinar, pusat="B"):
    return {"adegan": "busur", "pusat": pusat,
            "sinar": [{"huruf": h, "sudut": s} for h, s in sinar]}


def _svg_data(data, namespace="uji"):
    return periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, namespace) + "</div>")


def _raw_param(parameter, namespace="uji"):
    _, descriptor = proyeksi_matematika_awal(TID, parameter)
    return adegan_awal_svg.render_adegan_awal(descriptor.data, namespace)


def _svg_param(parameter, namespace="uji"):
    return periksa_xml("<div>" + _raw_param(parameter, namespace) + "</div>")


# ── solver mandiri dari koordinat sinar ──────────────────────────────────

def _titik_pusat(svg):
    (pusat,) = kelas(svg, "pusat-busur")
    return float(pusat.get("cx")), float(pusat.get("cy"))


def _arah(x, y, pusat):
    """Derajat dari kanan berlawanan arah jarum jam (y layar menurun), 0 <= arah <= 180."""
    return math.degrees(math.atan2(pusat[1] - y, x - pusat[0]))


def _pusat_huruf(e):
    return float(e.get("x")), float(e.get("y")) - 0.35 * float(e.get("font-size"))


def baca_gambar(svg):
    """{huruf: arah} dari sinar dan huruf; arah dibulatkan ke kelipatan 5 dengan toleransi ketat."""
    pusat = _titik_pusat(svg)
    sinar = kelas(svg, "sinar-sudut")
    assert 2 <= len(sinar) <= 3, len(sinar)
    huruf = {"".join(e.itertext()): _arah(*_pusat_huruf(e), pusat) for e in kelas(svg, "huruf-sinar")}
    assert len(huruf) == len(sinar), huruf
    hasil = {}
    for e in sinar:
        assert math.dist((float(e.get("x1")), float(e.get("y1"))), pusat) < 0.01, e.attrib
        arah = _arah(float(e.get("x2")), float(e.get("y2")), pusat)
        bulat = round(arah / 5) * 5
        assert abs(arah - bulat) < TOLERANSI_ARAH, arah
        cocok = [h for h, a in huruf.items() if abs(a - arah) < TOLERANSI_ARAH]
        assert len(cocok) == 1, (arah, huruf)
        hasil[cocok[0]] = bulat
    assert set(hasil) == set(huruf)
    return hasil


def _huruf_titik(svg):
    (titik,) = kelas(svg, "huruf-titik")
    return "".join(titik.itertext())


def jawab_visual(penyajian, svg):
    baris = penyajian.teks_soal.split("\n")
    assert len(baris) == 2 and baris[0] == PENGANTAR, baris
    arah, titik = baca_gambar(svg), _huruf_titik(svg)
    tanya = baris[1]
    if tanya in (TANYA_BESAR, TANYA_JENIS):
        assert titik == "B" and set(arah) == {"A", "C"}, (titik, arah)
        return jawab_dari_sudut(tanya, abs(arah["A"] - arah["C"]))
    assert tanya in (TANYA_BANDING, TANYA_SELISIH), tanya
    assert titik == "O" and set(arah) == {"A", "B", "C"}, (titik, arah)
    return jawab_dari_sudut(tanya, abs(arah["A"] - arah["B"]), abs(arah["A"] - arah["C"]))


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


@pytest.mark.parametrize("sudut", range(0, 181, 5))
def test_baca_gambar_seluruh_arah_kelipatan_5_dari_koordinat(sudut):
    lain = 90 if abs(sudut - 90) >= 10 else 20
    svg = _svg_data(_data((("A", sudut), ("C", lain))))
    assert baca_gambar(svg) == {"A": sudut, "C": lain}


def test_solver_geometri_menolak_gambar_yang_ambigu():
    """Mutasi gambar: huruf dan sinar tidak sejajar, atau sinar tidak berpangkal di pusat."""
    svg = _svg_data(_data((("A", 0), ("C", 70))))
    (huruf_c,) = [e for e in kelas(svg, "huruf-sinar") if "".join(e.itertext()) == "C"]
    huruf_c.set("x", "100")
    with pytest.raises(AssertionError):
        baca_gambar(svg)
    svg = _svg_data(_data((("A", 0), ("C", 70))))
    kelas(svg, "sinar-sudut")[0].set("x1", "10")
    with pytest.raises(AssertionError):
        baca_gambar(svg)


# ── skala: label konsisten dengan posisi ─────────────────────────────────

def _sudut_label(e, pusat):
    x, y = _pusat_huruf(e)
    return _arah(x, y, pusat)


def test_label_skala_luar_dari_kanan_dan_skala_dalam_dari_kiri_konsisten_dengan_posisi():
    svg = _svg_data(_data((("A", 0), ("C", 70))))
    pusat = _titik_pusat(svg)
    for nama, hitung in (("angka-luar", lambda d: d), ("angka-dalam", lambda d: 180 - d)):
        label = kelas(svg, nama)
        assert len(label) == 19
        for e in label:
            sudut = _sudut_label(e, pusat)
            letak = round(sudut / 10) * 10
            toleransi = TOLERANSI_ANGKA_ALAS if letak in (0, 180) else TOLERANSI_ANGKA_PUSAT
            assert abs(sudut - letak) < toleransi, (nama, sudut)
            assert "".join(e.itertext()) == str(hitung(letak)), (nama, letak)
            jarak = math.dist(_pusat_huruf(e), pusat)
            assert abs(jarak - (T.ADEGAN_BUSUR_ANGKA_LUAR_JARI if nama == "angka-luar"
                                else T.ADEGAN_BUSUR_ANGKA_DALAM_JARI)) < 7, jarak


def test_skala_luar_nol_di_kanan_dan_skala_dalam_nol_di_kiri():
    svg = _svg_data(_data((("A", 0), ("C", 70))))
    pusat = _titik_pusat(svg)
    luar = {"".join(e.itertext()): _sudut_label(e, pusat) for e in kelas(svg, "angka-luar")}
    dalam = {"".join(e.itertext()): _sudut_label(e, pusat) for e in kelas(svg, "angka-dalam")}
    assert luar["0"] < 5 and luar["180"] > 175 and luar["90"] == pytest.approx(90, abs=1)
    assert dalam["0"] > 175 and dalam["180"] < 5 and dalam["90"] == pytest.approx(90, abs=1)
    for nilai in range(0, 181, 10):
        assert luar[str(nilai)] == pytest.approx(nilai, abs=TOLERANSI_ANGKA_ALAS)
        assert dalam[str(nilai)] == pytest.approx(180 - nilai, abs=TOLERANSI_ANGKA_ALAS)


def test_angka_skala_dan_tanda_tetap_sama_apa_pun_sinarnya():
    bentuk = set()
    for sinar in ((("A", 0), ("C", 70)), (("A", 180), ("C", 10)), (("A", 40), ("B", 90), ("C", 150))):
        mentah = adegan_awal_svg.render_adegan_awal(
            _data(sinar, "O" if len(sinar) == 3 else "B"), "uji")
        bentuk.add(SINAR_HURUF_TITIK.sub("", mentah))
    assert len(bentuk) == 1


def test_tanda_satuan_lima_dan_sepuluh_serta_garis_alas():
    svg = _svg_data(_data((("A", 0), ("C", 70))))
    banyak = {nama: kelas(svg, nama)[0].get("d").count("M")
              for nama in ("tanda-satuan", "tanda-lima", "tanda-sepuluh")}
    assert banyak == {"tanda-satuan": 144, "tanda-lima": 18, "tanda-sepuluh": 19}
    (alas,) = kelas(svg, "garis-alas")
    pusat = _titik_pusat(svg)
    lebih = T.ADEGAN_BUSUR_RADIUS + T.ADEGAN_BUSUR_ALAS_LEBIH
    assert float(alas.get("y1")) == float(alas.get("y2")) == pusat[1]
    assert float(alas.get("x1")) == pytest.approx(pusat[0] - lebih)
    assert float(alas.get("x2")) == pytest.approx(pusat[0] + lebih)


def _bacaan_gambar(sudut: int) -> dict:
    """Angka yang terbaca pada tiap skala di arah `sudut`: luar dari kanan, dalam dari kiri."""
    return {"luar": sudut, "dalam": 180 - sudut}


def test_teks_dan_gambar_sepakat_soal_skala_untuk_seluruh_domain():
    """Skala yang disebut teks dan angka bacaannya sama dengan yang terbaca pada gambar."""
    for p in sumber.domain_parameter("P5"):
        teks = _soal(p).teks.split("\n")[0]
        arah = baca_gambar(_svg_param(p, "silang"))
        nol = KAKI_NOL.search(teks)
        if nol:
            assert _bacaan_gambar(arah["A"])[nol.group(2)] == 0, (p, "kaki alas bukan di 0 pada skala itu")
            assert _bacaan_gambar(arah["A"])[{"luar": "dalam", "dalam": "luar"}[nol.group(2)]] == 180
        kaki = list(KAKI.finditer(teks))
        for m in kaki:
            _, huruf, angka1, skala1, angka2, skala2 = m.groups()
            assert {skala1: int(angka1), skala2: int(angka2)} == _bacaan_gambar(arah[huruf]), (p, huruf)
        geser = GESER.fullmatch(teks)
        if geser:
            assert _bacaan_gambar(arah["A"])["luar"] == int(geser.group(1)), p
            assert _bacaan_gambar(arah["C"])["luar"] == int(geser.group(2)), p
        assert bool(kaki) != bool(geser)


# ── varian: tanpa flag tetap teks yang bisa dijawab ──────────────────────

@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
def test_tanpa_flag_semua_varian_bisa_dijawab_dari_teks(monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    else:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", flag)
    for p in sumber.domain_parameter("P5"):
        soal = _soal(p)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "tanpa_visual" and penyajian.descriptor is None
        assert penyajian.teks_soal == soal.teks
        assert solver_dari_teks(penyajian.teks_soal) == soal.kunci, p
        assert "<svg" not in render_pertanyaan(penyajian)


# ── teks proyeksi dan kebocoran ──────────────────────────────────────────

def test_teks_proyeksi_tanpa_angka_tanpa_letak_kaki_dan_tanpa_kunci_di_seluruh_domain():
    for p in sumber.domain_parameter("P5"):
        soal = _soal(p)
        teks = penyajian_dari_soal(soal).teks_soal
        pengantar, tanya = teks.split("\n")
        assert pengantar == PENGANTAR
        assert not re.search(r"\d", teks), teks
        assert not re.search(r"menunjuk|skala|angka \d|kaki", teks, re.I), teks
        assert soal.teks.split("\n")[-1] == tanya
        if p["varian"] not in ("jenis_sudut", "banding"):
            assert soal.kunci not in re.findall(r"\d+", teks)


def test_pengantar_dan_pertanyaan_per_varian():
    assert _penyajian(CONTOH_NOL_KANAN).teks_soal == f"{PENGANTAR}\n{TANYA_BESAR}"
    assert _penyajian(CONTOH_GESER).teks_soal == f"{PENGANTAR}\n{TANYA_BESAR}"
    assert _penyajian(CONTOH_JENIS).teks_soal == f"{PENGANTAR}\n{TANYA_JENIS}"
    assert _penyajian(CONTOH_BANDING).teks_soal == f"{PENGANTAR}\n{TANYA_BANDING}"
    assert _penyajian(CONTOH_SELISIH).teks_soal == f"{PENGANTAR}\n{TANYA_SELISIH}"


def test_svg_tanpa_sinar_dan_huruf_identik_untuk_seluruh_domain():
    """Badan, tanda, angka skala, judul, uraian: tidak bergantung pada soal."""
    sisa = set()
    for p in sumber.domain_parameter("P5"):
        mentah = _raw_param(p)
        assert 2 <= len(re.findall(r'<line class="sinar-sudut"', mentah)) <= 3
        sisa.add(SINAR_HURUF_TITIK.sub("", mentah))
    assert len(sisa) == 1


def test_html_tanpa_sinar_dan_huruf_identik_untuk_semua_gaya_dan_varian():
    for gaya in GAYA:
        bentuk = set()
        for p in _domain("baca_dari_nol", "baca_geser")[::9] + _domain("banding", "selisih_dua")[::40]:
            html = _html(p, gaya=gaya, namespace="bocor")
            svg = re.search(r"<svg\b.*?</svg>", html, re.S).group(0)
            bentuk.add(SINAR_HURUF_TITIK.sub("", svg))
        assert len(bentuk) == 1, gaya


def test_tanpa_transform_tanpa_data_atribut_tanpa_minus_nol_dan_kelas_netral():
    for parameter in CONTOH:
        for gaya in GAYA:
            html = _html(parameter, gaya=gaya)
            svg = periksa_xml(html)
            token = {t for e in svg.iter() for t in e.get("class", "").split()}
            assert token <= KELAS_BOLEH and {"sinar-sudut", "huruf-sinar", "huruf-titik"} <= token
            assert not [a for e in svg.iter() for a in e.attrib if a.startswith("data-")]
            assert not [e for e in svg.iter() if "transform" in e.attrib]
            assert {lokal(e) for e in svg.iter()} <= TAG_BOLEH
            assert not elemen(svg, "image") and not [e for e in svg.iter() if "href" in e.attrib]
            gambar = re.search(r"<svg\b.*?</svg>", html, re.S).group(0)
            assert not re.search(r"(?<![\d.])-0(?![\d.])", gambar)
            assert "rotate" not in html


def test_tanpa_minus_nol_dan_notasi_ilmiah_pada_koordinat_untuk_seluruh_arah():
    for sudut in range(0, 181, 5):
        mentah = adegan_awal_svg.render_adegan_awal(
            _data((("A", sudut), ("C", 90 if abs(sudut - 90) >= 10 else 20))), "uji")
        # id berbasis hash dan kode warna heksadesimal bisa memuat "4e9": buang dulu
        gambar = re.sub(r"#[0-9a-fA-F]+", "", mentah.split("</desc>", 1)[1])
        assert not re.search(r'="-0"|[ ,ML]-0[ ,"LM]', gambar), (sudut, gambar)
        assert not re.search(r'[0-9]e[-+]?[0-9]', gambar)


def test_desc_dan_title_tetap_tanpa_angka_nama_sudut_banyak_sinar_atau_skala():
    judul_tetap, uraian_tetap = set(), set()
    for p in sumber.domain_parameter("P5")[::37]:
        svg = _svg(p, namespace="aks")
        (judul,), (uraian,) = elemen(svg, "title"), elemen(svg, "desc")
        isi_judul, isi_uraian = "".join(judul.itertext()), "".join(uraian.itertext())
        assert svg.get("role") == "img"
        assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
        assert not re.search(r"\d", isi_judul + isi_uraian)
        assert not re.search(r"lancip|siku|tumpul|derajat \d|dua sinar|tiga sinar|luar|dalam kanan",
                             isi_judul + isi_uraian, re.I)
        judul_tetap.add(isi_judul)
        uraian_tetap.add(isi_uraian)
    assert judul_tetap == {"Gambar busur derajat"}
    assert uraian_tetap == {"Busur derajat dengan dua skala dan sinar sudut. Perhatikan letak sinar pada skala."}


def test_latar_angka_menutup_angka_dan_digambar_sesudah_sinar_sebelum_angka():
    """Sinar yang lewat tidak boleh menimpa angka: kotak seisi busur di antara sinar dan angka."""
    svg = _svg(CONTOH_BANDING)
    urutan = list(svg.iter())
    sinar = [urutan.index(e) for e in kelas(svg, "sinar-sudut")]
    latar, angka = kelas(svg, "latar-angka"), kelas(svg, "angka-luar") + kelas(svg, "angka-dalam")
    assert len(latar) == len(angka) == 38
    assert max(sinar) < min(urutan.index(e) for e in latar)
    assert max(urutan.index(e) for e in latar) < min(urutan.index(e) for e in angka)
    assert {e.get("fill") for e in latar} == {T.ADEGAN_BUSUR_ISI}
    kotak = [(float(e.get("x")), float(e.get("y")), float(e.get("width")), float(e.get("height")))
             for e in latar]
    for e in angka:
        x, y = _pusat_huruf(e)
        lebar = len("".join(e.itertext())) * T.ADEGAN_BUSUR_LEBAR_HURUF * float(e.get("font-size"))
        assert any(kx <= x - lebar / 2 and x + lebar / 2 <= kx + kw and ky <= y - 4 and y + 4 <= ky + kh
                   for kx, ky, kw, kh in kotak), "".join(e.itertext())


def test_angka_skala_hanya_kelipatan_sepuluh_dan_sama_di_semua_soal():
    for parameter in CONTOH:
        svg = _svg(parameter)
        luar = [("".join(e.itertext())) for e in kelas(svg, "angka-luar")]
        dalam = [("".join(e.itertext())) for e in kelas(svg, "angka-dalam")]
        assert sorted(map(int, luar)) == list(range(0, 181, 10))
        assert sorted(map(int, dalam)) == list(range(0, 181, 10))
        assert all(e.tag.endswith("text") for e in kelas(svg, "angka-luar") + kelas(svg, "angka-dalam"))


def test_descriptor_hanya_memuat_field_allowlist_tanpa_kunci():
    for p in sumber.domain_parameter("P5")[::23]:
        penyajian = _penyajian(p)
        data = penyajian.descriptor.ke_dict()["data"]
        assert set(data) == {"adegan", "pusat", "sinar"} and data["adegan"] == "busur"
        assert data["pusat"] == ("O" if p["varian"] in ("banding", "selisih_dua") else "B")
        assert all(set(s) == {"huruf", "sudut"} for s in data["sinar"])
        assert "kunci" not in serialisasi_penyajian(penyajian)


# ── geometri: sinar jelas, huruf tidak bertumpuk, semuanya di dalam gambar

def _tepi_sinar(svg):
    return [(float(e.get("x2")), float(e.get("y2"))) for e in kelas(svg, "sinar-sudut")]


def test_sinar_sama_panjang_menembus_kedua_skala_dan_tidak_keluar_busur_terlalu_jauh():
    for p in sumber.domain_parameter("P5")[::11]:
        svg = _svg(p, namespace="geo")
        pusat = _titik_pusat(svg)
        for ujung in _tepi_sinar(svg):
            jarak = math.dist(ujung, pusat)
            assert jarak == pytest.approx(T.ADEGAN_BUSUR_PANJANG_SINAR, abs=0.02)
            assert T.ADEGAN_BUSUR_RADIUS < jarak < T.ADEGAN_BUSUR_HURUF_JARI
        for e in kelas(svg, "sinar-sudut"):
            assert float(e.get("stroke-width")) >= 2.5 and e.get("stroke") == T.ADEGAN_BUSUR_SINAR


def test_huruf_sinar_di_ujung_sinarnya_dan_tidak_bertumpuk_di_seluruh_domain():
    batas = T.ADEGAN_BUSUR_HURUF_FONT * 1.3
    for p in sumber.domain_parameter("P5"):
        svg = _svg_param(p, "tumpuk")
        pusat = _titik_pusat(svg)
        huruf = [_pusat_huruf(e) for e in kelas(svg, "huruf-sinar")]
        for x, y in huruf:
            assert math.dist((x, y), pusat) == pytest.approx(T.ADEGAN_BUSUR_HURUF_JARI, abs=0.05)
        for i, a in enumerate(huruf):
            for b in huruf[i + 1:]:
                assert math.dist(a, b) > batas, (p, a, b)
        titik = _pusat_huruf(kelas(svg, "huruf-titik")[0])
        assert all(math.dist(titik, h) > batas for h in huruf), p
        assert titik[1] > pusat[1] + T.ADEGAN_BUSUR_HURUF_FONT * 0.5


@pytest.mark.parametrize("parameter", CONTOH, ids=NAMA_CONTOH)
def test_semua_koordinat_dalam_viewbox_dan_gambar_tidak_terpotong(parameter):
    svg = _svg(parameter, namespace="batas")
    periksa_batas_koordinat(svg)
    lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
    assert (lebar, tinggi) == (T.ADEGAN_LEBAR, T.ADEGAN_BUSUR_TINGGI)
    pusat = _titik_pusat(svg)
    r = T.ADEGAN_BUSUR_RADIUS
    tepi = T.ADEGAN_BUSUR_TEBAL_TEPI / 2
    assert pusat[0] - r - tepi >= 0 and pusat[0] + r + tepi <= lebar and pusat[1] - r - tepi >= 0
    assert abs(pusat[0] - lebar / 2) < 0.01 and pusat[1] == T.ADEGAN_BUSUR_PUSAT_Y
    for e in elemen(svg, "text"):
        setengah = len(("".join(e.itertext()))) * float(e.get("font-size")) * 0.6 / 2
        x, y = float(e.get("x")), float(e.get("y"))
        assert x - setengah >= 0 and x + setengah <= lebar, "".join(e.itertext())
        assert float(e.get("font-size")) <= y <= tinggi


def test_semua_domain_ujung_sinar_dan_huruf_dalam_viewbox():
    for p in sumber.domain_parameter("P5"):
        svg = _svg_param(p, "semua")
        periksa_batas_koordinat(svg)
        for x, y in _tepi_sinar(svg):
            assert 0 <= x <= T.ADEGAN_LEBAR and 0 <= y <= T.ADEGAN_BUSUR_TINGGI
        for e in kelas(svg, "huruf-sinar"):
            x, y = _pusat_huruf(e)
            sisi = T.ADEGAN_BUSUR_HURUF_FONT * 0.6 / 2
            assert sisi <= x <= T.ADEGAN_LEBAR - sisi and T.ADEGAN_BUSUR_HURUF_FONT / 2 <= y, p


def test_badan_busur_setengah_lingkaran_di_dalam_gambar_dan_lengkung_ke_atas():
    svg = _svg_data(_data((("A", 0), ("C", 70))))
    (badan,) = kelas(svg, "badan-busur")
    r, pusat = T.ADEGAN_BUSUR_RADIUS, _titik_pusat(svg)
    d = badan.get("d")
    angka = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    assert re.fullmatch(r"M[\d. ]+A[\d. ]+Z", d)
    assert angka == [pusat[0] - r, pusat[1], r, r, 0, 0, 1, pusat[0] + r, pusat[1]]
    assert pusat[1] - r >= 0, "puncak busur masih di dalam gambar"


# ── warna dan kontras ────────────────────────────────────────────────────

def test_warna_token_dan_kontras_terhadap_isi_busur_dan_latar():
    sah = {None, "none", T.TEKS_UTAMA, T.ADEGAN_BUSUR_ISI, T.ADEGAN_BUSUR_SINAR, T.ADEGAN_BUSUR_ANGKA_DALAM}
    for parameter in CONTOH:
        svg = _svg(parameter)
        for e in svg.iter():
            if lokal(e) in ("line", "circle", "path", "text", "rect"):
                for atribut in ("stroke", "fill"):
                    assert e.get(atribut) in sah, e.attrib
    for depan in (T.TEKS_UTAMA, T.ADEGAN_BUSUR_SINAR, T.ADEGAN_BUSUR_ANGKA_DALAM):
        for latar in (T.ADEGAN_BUSUR_ISI, T.LATAR_KARTU, T.LATAR_MURID):
            assert kontras(depan, latar) >= 4.5, (depan, latar)


def test_skala_dalam_berwarna_beda_dari_skala_luar_dan_huruf_cukup_besar():
    svg = _svg(CONTOH_NOL_KANAN)
    assert {e.get("fill") for e in kelas(svg, "angka-luar")} == {T.TEKS_UTAMA}
    assert {e.get("fill") for e in kelas(svg, "angka-dalam")} == {T.ADEGAN_BUSUR_ANGKA_DALAM}
    assert all(float(e.get("font-size")) >= 11 for e in elemen(svg, "text"))
    assert all(float(e.get("font-size")) >= 16 for e in kelas(svg, "huruf-sinar") + kelas(svg, "huruf-titik"))


# ── invarian: determinisme, fingerprint, serialisasi ─────────────────────

def test_render_dua_kali_identik_byte_per_byte():
    for parameter in CONTOH:
        penyajian = _penyajian(parameter)
        assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
        assert penyajian.fingerprint_penyajian == _penyajian(parameter).fingerprint_penyajian


def test_fingerprint_dipatok_agar_perubahan_penyajian_disengaja():
    ringkas = {nama: (_penyajian(p).fingerprint_matematis, _penyajian(p).fingerprint_penyajian)
               for nama, p in zip(NAMA_CONTOH, CONTOH)}
    assert ringkas == FINGERPRINT_DIPATOK


@pytest.mark.parametrize("parameter", CONTOH, ids=NAMA_CONTOH)
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
        "import awal_ukur_sudut_awal as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P5')[::41]:\n"
        "    s = penyajian_dari_soal(replace(m.ukur_sudut_awal(**p), level='P5'))\n"
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
    penyajian = _penyajian(CONTOH_BANDING)
    try:
        hasil = render_pertanyaan(penyajian, namespace=namespace)
    except ValueError:
        return
    svg = periksa_xml(hasil)
    pembanding = _svg(CONTOH_BANDING, namespace="pembanding")
    ids = {e.get("id") for e in svg.iter() if e.get("id")}
    assert ids and ids.isdisjoint(e.get("id") for e in pembanding.iter())
    assert not re.search(r"<script|javascript:|\son[a-z]+=",
                         hasil.replace('xmlns="http://www.w3.org/2000/svg"', ""), re.I)


@pytest.mark.parametrize("namespace", ("", None, 3))
def test_namespace_kosong_atau_bukan_teks_ditolak(namespace):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(_penyajian(CONTOH_NOL_KANAN).descriptor.data, namespace)


def test_id_unik_pada_lembar_dengan_banyak_soal_berulang():
    ids = []
    for i in range(6):
        ids += [e.get("id") for e in _svg(CONTOH_GESER, namespace=f"lembar-{i}").iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12


# ── validator descriptor: allow-list ketat ───────────────────────────────

def _valid(data):
    DescriptorVisual("adegan_awal", 1, data)
    return adegan_awal_svg.render_adegan_awal(data, "uji")


def test_descriptor_sah_semua_arah_dan_komposisi_diterima():
    for sudut in range(0, 181, 5):
        assert _valid(_data((("A", sudut), ("C", 90 if abs(sudut - 90) >= 10 else 20))))
    assert _valid(_data((("A", 0), ("B", 60), ("C", 120)), "O"))
    assert _valid(_data((("C", 100), ("A", 20))))
    assert "busur" in adegan_awal_data.ADEGAN_DIDUKUNG


def _sinar(*pasangan):
    return [{"huruf": h, "sudut": s} for h, s in pasangan]


@pytest.mark.parametrize("rusak", (
    {"adegan": "busur", "pusat": "B"},
    {"adegan": "busur", "sinar": _sinar(("A", 0), ("C", 70))},
    {"adegan": "busur"},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 70)), "kunci": "70"},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 70)), "class": "tujuh"},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 70)), "tampil": "satu"},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 70)), "alas": "kanan"},
    {"adegan": "busur", "pusat": "D", "sinar": _sinar(("A", 0), ("C", 70))},
    {"adegan": "busur", "pusat": "b", "sinar": _sinar(("A", 0), ("C", 70))},
    {"adegan": "busur", "pusat": None, "sinar": _sinar(("A", 0), ("C", 70))},
    {"adegan": "busur", "pusat": 1, "sinar": _sinar(("A", 0), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": []},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 70), ("B", 130))},
    {"adegan": "busur", "pusat": "O", "sinar": _sinar(("A", 0), ("B", 40), ("C", 90), ("C", 140))},
    {"adegan": "busur", "pusat": "B", "sinar": "AC"},
    {"adegan": "busur", "pusat": "B", "sinar": None},
    {"adegan": "busur", "pusat": "B", "sinar": [("A", 0), ("C", 70)]},
    {"adegan": "busur", "pusat": "B", "sinar": [{"huruf": "A"}, {"huruf": "C", "sudut": 70}]},
    {"adegan": "busur", "pusat": "B", "sinar": [{"huruf": "A", "sudut": 0, "warna": "merah"},
                                                 {"huruf": "C", "sudut": 70}]},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("A", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("B", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("D", 0), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("a", 0), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar((None, 0), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 3), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", -5), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 185))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 360))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", True), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0.0), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", "0"), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", None), ("C", 70))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 0))},
    {"adegan": "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 5))},
    {"adegan": "busur", "pusat": "O", "sinar": _sinar(("A", 0), ("B", 60), ("C", 65))},
    {"adegan": "busur_derajat", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 70))},
    {"pusat": "B", "sinar": _sinar(("A", 0), ("C", 70))},
    {1: "busur", "pusat": "B", "sinar": _sinar(("A", 0), ("C", 70))},
))
def test_descriptor_rusak_ditolak_validator_dan_renderer(rusak):
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, rusak)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(rusak, "uji")


@pytest.mark.parametrize("bukan_mapping", (None, [], "busur", 3))
def test_data_bukan_mapping_ditolak(bukan_mapping):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(bukan_mapping, "uji")


def test_batas_validator_jarak_sinar_tepat_sepuluh_derajat_diterima():
    adegan_awal_busur_data.validasi_busur(_data((("A", 0), ("C", 10))))
    adegan_awal_busur_data.validasi_busur(_data((("A", 170), ("C", 180))))
    with pytest.raises(ValueError):
        adegan_awal_busur_data.validasi_busur(_data((("A", 170), ("C", 175))))


# ── proyektor: field persis dan bentuk teks sumber ───────────────────────

def test_field_parameter_tambahan_atau_hilang_ditolak_proyektor():
    for dasar in CONTOH:
        soal = _soal(dasar)
        kunci_isi = next(k for k in soal.parameter if k != "varian")
        for rusak in (
            {**soal.parameter, "kunci": "x"},
            {**soal.parameter, "menit": 30},
            {k: v for k, v in soal.parameter.items() if k != "varian"},
            {k: v for k, v in soal.parameter.items() if k != kunci_isi},
            {**soal.parameter, "varian": "lain"},
            {**soal.parameter, kunci_isi: True},
        ):
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, rusak)
    for rusak in ({"varian": "baca_dari_nol", "arah": "kanan", "sudut": 90},
                  {"varian": "baca_dari_nol", "arah": "atas", "sudut": 70},
                  {"varian": "baca_geser", "a": 30, "b": 30},
                  {"varian": "banding", "arah": "kanan", "b": 40, "c": 40},
                  {"varian": "selisih_dua", "arah": "kanan", "b": 45, "c": 100}):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)


def test_proyeksi_gagal_keras_bila_bentuk_teks_sumber_berubah(monkeypatch):
    asli = sumber.ukur_sudut_awal
    for dasar in CONTOH:
        soal = _soal(dasar)
        for ubah in (
            lambda teks: teks.replace("\n", " "),
            lambda teks: teks + "\nCatatan.",
            lambda teks: teks.rsplit("\n", 1)[0] + "\nBerapa sudutnya?",
            lambda teks: teks.replace("Tulis", "Tuliskan"),
        ):
            def palsu(varian, **isi):
                hasil = asli(varian, **isi)
                return replace(hasil, teks=ubah(hasil.teks))
            monkeypatch.setattr(sumber, "ukur_sudut_awal", palsu)
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, soal.parameter)
        monkeypatch.setattr(sumber, "ukur_sudut_awal", asli)


def test_proyeksi_jenis_lain_tetap_none_dan_jenis_geometri_datar_tidak_berubah():
    assert proyeksi_matematika_awal("waktu_berat_awal", {"apa": "saja"}) is None
    assert proyeksi_matematika_awal("kenali_bentuk", {"apa": "saja"}) is None
    assert proyeksi_matematika_awal("bandingkan_ciri_bangun", {"apa": "saja"}) is None


def test_arah_descriptor_kaki_alas_kanan_nol_kiri_180_dan_sudut_dari_alas():
    _, kanan = proyeksi_matematika_awal(TID, CONTOH_NOL_KANAN)
    _, kiri = proyeksi_matematika_awal(TID, CONTOH_NOL_KIRI)
    assert [(s["huruf"], s["sudut"]) for s in kanan.data["sinar"]] == [("A", 0), ("C", 70)]
    assert [(s["huruf"], s["sudut"]) for s in kiri.data["sinar"]] == [("A", 180), ("C", 55)]
    _, geser = proyeksi_matematika_awal(TID, CONTOH_GESER)
    assert [(s["huruf"], s["sudut"]) for s in geser.data["sinar"]] == [("A", 30), ("C", 110)]
    _, banding = proyeksi_matematika_awal(TID, CONTOH_BANDING)
    assert banding.data["pusat"] == "O"
    assert [(s["huruf"], s["sudut"]) for s in banding.data["sinar"]] == [("A", 0), ("B", 40), ("C", 130)]
    _, selisih = proyeksi_matematika_awal(TID, CONTOH_SELISIH)
    assert [(s["huruf"], s["sudut"]) for s in selisih.data["sinar"]] == [("A", 180), ("B", 30), ("C", 120)]


# ── ringkasan non-HTML ───────────────────────────────────────────────────

def test_ringkasan_tanpa_angka_sama_untuk_semua_soal():
    ringkasan = {ringkasan_pertanyaan(_penyajian(p)).split("\n")[-1]
                 for p in sumber.domain_parameter("P5")[::17]}
    assert len(ringkasan) == 1
    isi = next(iter(ringkasan))
    assert "Fakta visual: gambar busur derajat dengan skala luar dan skala dalam" in isi
    assert not re.search(r"\d|lancip|siku|tumpul|dua sinar|tiga sinar", isi, re.I)


# ── inventaris ───────────────────────────────────────────────────────────

def test_inventaris_menandai_ukur_sudut_awal_wajib_visual_semua_varian_bergambar():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {d["varian"] for d in baris} == {f"varian={v}" for v in sumber.VARIAN}
    assert {d["level"] for d in baris} == {"P5"}
    assert TID not in VARIAN_SENGAJA_TEKS, "kelima varian memakai gambar busur derajat"
    assert {d["bukti_klasifikasi"]["keluarga"] for d in baris} == {"busur_derajat"}
    assert "tidak ada yang sengaja teks" in baris[0]["bukti_klasifikasi"]["observasi"]
