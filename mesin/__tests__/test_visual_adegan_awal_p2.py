"""Keluarga visual `matematika-awal`: baca_diagram_gambar level P2 (skala, adegan_awal v1).

Solver mandiri HANYA membaca teks proyeksi + SVG hasil `render_pertanyaan`: hitung `<image>`
per `<g class="baris-adegan">`, ambil skala dari kalimat pengantar (dan legenda gambar),
tentukan varian dari kalimat pertanyaan; hasilnya dibandingkan dengan `soal.kunci` untuk
SELURUH `domain_parameter("P2")`. Legenda skala berada di luar grup baris, jadi kontrak
hitung lama (jumlah `<image>` per baris = banyak gambar) tidak berubah.
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
from adegan_awal_data import IKON_DIDUKUNG, validasi_adegan_awal
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import (
    DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian,
)
from visual_inventory import DENOMINATOR_KANONIS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, lokal, periksa_xml, teks_svg

TID = sumber.TEMPLATE_ID
SIMBOL = sumber.SIMBOL
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
SKALA_DUA = {"varian": "jumlah", "tema": "mainan", "n1": 5, "n2": 2, "n3": 8,
             "skala": 2, "x": 0, "y": 2}
SKALA_SATU = {"varian": "selisih", "tema": "buah", "n1": 12, "n2": 5, "n3": 7,
              "skala": 1, "x": 0, "y": 1}
KATA_TEMA = {"mainan": "mainan", "buah": "buah", "hewan": "hewan"}


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _soal(parameter):
    return replace(sumber.baca_diagram_gambar(**parameter), level="P2")


def _penyajian(parameter=SKALA_DUA):
    return penyajian_dari_soal(_soal(parameter))


def _svg(parameter=SKALA_DUA, *, namespace="uji-p2", gaya="cetak"):
    return periksa_xml(render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya))


# ── solver mandiri: hanya teks proyeksi + SVG ────────────────────────────

def _baris_svg(svg):
    """Daftar (label huruf kecil, banyak <image>) per baris, urut tampil."""
    hasil = []
    for baris in kelas(svg, "baris-adegan"):
        label = "".join("".join(t.itertext()) for t in elemen(baris, "text"))
        hasil.append((label.lower(), len(elemen(baris, "image"))))
    return tuple(hasil)


def _skala_dari_teks(teks):
    cocok = re.fullmatch(r"Perhatikan gambar\. Satu gambar mewakili ([12]) ([a-z]+)\.", teks.split("\n")[0])
    assert cocok, teks
    return int(cocok[1])


def _legenda(svg):
    """Teks legenda skala di luar grup baris, atau None bila tidak ada."""
    grup = kelas(svg, "legenda-adegan")
    assert len(grup) <= 1
    if not grup:
        return None
    return "".join("".join(t.itertext()) for t in elemen(grup[0], "text"))


def _jawab(teks, svg):
    skala = _skala_dari_teks(teks)
    legenda = _legenda(svg)
    # legenda (bila ada) wajib sejalan dengan skala di teks; tanpa legenda berarti skala 1
    assert legenda == (None if skala == 1 else f"Satu gambar mewakili {skala} benda."), (teks, legenda)
    banyak = {nama: n * skala for nama, n in _baris_svg(svg)}
    gambar = dict(_baris_svg(svg))
    tanya = teks.split("\n")[-1]
    if cocok := re.fullmatch(r"Berapa banyak ([a-z]+)\?", tanya):
        return str(banyak[cocok[1]])
    if tanya == "Mana yang paling banyak?":
        return max(gambar, key=gambar.get)
    if cocok := re.fullmatch(r"([A-Z][a-z]+) lebih banyak berapa daripada ([a-z]+)\?", tanya):
        return str(banyak[cocok[1].lower()] - banyak[cocok[2]])
    if cocok := re.fullmatch(r"Berapa jumlah ([a-z]+) dan ([a-z]+)\?", tanya):
        return str(banyak[cocok[1]] + banyak[cocok[2]])
    raise AssertionError(("pertanyaan tidak dikenal", tanya))


def _kelompok(varian, skala):
    return tuple(p for p in sumber.domain_parameter("P2")
                 if p["varian"] == varian and p["skala"] == skala)


@pytest.mark.parametrize("skala", (1, 2))
@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_solver_svg_sama_dengan_kunci_seluruh_domain_p2(varian, skala):
    anggota = _kelompok(varian, skala)
    assert anggota
    for parameter in anggota:
        soal = _soal(parameter)
        penyajian = penyajian_dari_soal(soal)
        svg = periksa_xml(render_pertanyaan(penyajian, namespace="sapuan"))
        harapan = tuple((k.lower(), parameter[n]) for k, n in
                        zip(sumber.TEMA[parameter["tema"]][2], sumber.KUNCI_JUMLAH))
        assert _baris_svg(svg) == harapan, parameter
        assert _jawab(penyajian.teks_soal, svg) == soal.kunci, parameter


# ── invarian 1: tanpa flag tidak berubah ─────────────────────────────────

@pytest.mark.parametrize("parameter", (SKALA_DUA, SKALA_SATU), ids=("skala2", "skala1"))
@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
def test_tanpa_keluarga_matematika_awal_p2_teks_lama_persis(monkeypatch, flag, parameter):
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
    assert SIMBOL in penyajian.teks_soal
    assert "<svg" not in render_pertanyaan(penyajian)


# ── invarian 2: teks, status, jumlah <image>, legenda ────────────────────

@pytest.mark.parametrize("parameter,skala", ((SKALA_DUA, 2), (SKALA_SATU, 1)), ids=("skala2", "skala1"))
def test_flag_aktif_p2_status_siap_teks_tanpa_simbol_dan_angka_data(parameter, skala):
    penyajian = _penyajian(parameter)
    assert penyajian.status_visual == "siap"
    assert penyajian.mode_representasi == "adegan_awal-v1"
    assert SIMBOL not in penyajian.teks_soal and "titik hitam" not in penyajian.teks_soal
    awal, tanya = penyajian.teks_soal.split("\n")
    kata = sumber.TEMA[parameter["tema"]][1]
    assert awal == f"Perhatikan gambar. Satu gambar mewakili {skala} {kata}."
    assert tanya == _soal(parameter).teks.split("\n")[-1]
    # satu-satunya angka di teks adalah skala di kalimat pengantar
    assert re.findall(r"\d+", penyajian.teks_soal) == [str(skala)]


@pytest.mark.parametrize("skala", (1, 2))
@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_teks_p2_tanpa_angka_data_dan_tidak_menyebut_kunci(varian, skala):
    for parameter in _kelompok(varian, skala)[::211]:
        teks = _penyajian(parameter).teks_soal
        assert re.findall(r"\d+", teks) == [str(skala)], teks
        kunci = _soal(parameter).kunci
        if not kunci.isdigit():
            assert kunci not in teks.lower().split("\n")[0], teks


def test_descriptor_p2_membawa_satuan_ikon_dan_tidak_kunci_atau_jawaban():
    data = _penyajian().descriptor.ke_dict()["data"]
    assert set(data) == {"adegan", "baris", "satuan_ikon", "tanya"}
    assert data["satuan_ikon"] == 2 and type(data["satuan_ikon"]) is int
    assert data["tanya"] == {"varian": "jumlah", "x": 0, "y": 2}
    assert _penyajian(SKALA_SATU).descriptor.ke_dict()["data"]["satuan_ikon"] == 1
    assert "kunci" not in serialisasi_penyajian(_penyajian())


@pytest.mark.parametrize("gaya", GAYA)
def test_jumlah_image_per_baris_sama_banyak_gambar_dan_legenda_tanpa_image(gaya):
    svg = _svg(gaya=gaya)
    assert tuple(n for _, n in _baris_svg(svg)) == (5, 2, 8)
    assert len(elemen(svg, "image")) == 15
    legenda, = kelas(svg, "legenda-adegan")
    assert not elemen(legenda, "image")
    assert _legenda(svg) == "Satu gambar mewakili 2 benda."


def test_legenda_di_luar_semua_grup_baris_dan_tidak_menjadi_label_baris():
    svg = _svg()
    legenda, = kelas(svg, "legenda-adegan")
    for baris in kelas(svg, "baris-adegan"):
        assert legenda not in list(baris.iter())
        assert "Satu gambar" not in "".join(baris.itertext())
    assert tuple(nama for nama, _ in _baris_svg(svg)) == ("bola", "mobil", "boneka")


def _bagian_svg(html_hasil):
    cocok = re.search(r"<svg.*</svg>", html_hasil, re.S)
    assert cocok
    return cocok.group(0)


def test_skala_satu_tanpa_legenda_dan_render_sama_persis_dengan_soal_p1():
    p1 = {"varian": "selisih", "tema": "buah", "n1": 7, "n2": 6, "n3": 5, "x": 0, "y": 1}
    p2 = {**p1, "skala": 1}
    assert not kelas(_svg(p2), "legenda-adegan")
    html_p1 = render_pertanyaan(penyajian_dari_soal(replace(sumber.baca_diagram_gambar(**p1), level="P1")),
                                namespace="sama")
    html_p2 = render_pertanyaan(_penyajian(p2), namespace="sama")
    # pembungkus memuat fingerprint (parameter berbeda); SVG-nya wajib sama persis
    assert _bagian_svg(html_p2) == _bagian_svg(html_p1)


def test_ringkasan_non_html_p2_menyebut_skala_dua():
    ringkasan = ringkasan_pertanyaan(_penyajian())
    assert "Bola memiliki 5 gambar" in ringkasan
    assert "satu gambar mewakili 2 benda" in ringkasan


# ── invarian 3: determinisme dan fingerprint ─────────────────────────────

def test_render_p2_dua_kali_identik_byte_per_byte():
    penyajian = _penyajian()
    assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
    assert _penyajian().fingerprint_penyajian == _penyajian().fingerprint_penyajian


def test_fingerprint_p2_dipatok_agar_perubahan_penyajian_disengaja():
    penyajian = _penyajian()
    assert penyajian.fingerprint_matematis == FINGERPRINT_MATEMATIS_SKALA_DUA
    assert penyajian.fingerprint_penyajian == FINGERPRINT_PENYAJIAN_SKALA_DUA


@pytest.mark.parametrize("parameter", (SKALA_DUA, SKALA_SATU), ids=("skala2", "skala1"))
def test_round_trip_serialisasi_dan_fingerprint_matematis_sama_antara_mode_teks_dan_visual(
        monkeypatch, parameter):
    penyajian = _penyajian(parameter)
    assert deserialisasi_penyajian(serialisasi_penyajian(penyajian)) == penyajian
    monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    teks = penyajian_dari_soal(_soal(parameter))
    assert teks.fingerprint_matematis == penyajian.fingerprint_matematis
    assert teks.fingerprint_penyajian != penyajian.fingerprint_penyajian


def test_fingerprint_matematis_beda_antara_skala_satu_dan_dua_pada_data_sama():
    a = {"varian": "baca", "tema": "hewan", "n1": 5, "n2": 6, "n3": 7, "tanya": 1, "skala": 1}
    b = {**a, "skala": 2}
    assert _penyajian(a).fingerprint_matematis != _penyajian(b).fingerprint_matematis


def test_snapshot_dan_html_p2_identik_antarproses():
    kode = (
        "import hashlib\n"
        "from dataclasses import replace\n"
        "import awal_baca_diagram_gambar as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P2')[::499]:\n"
        "    s = penyajian_dari_soal(replace(m.baca_diagram_gambar(**p), level='P2'))\n"
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
def test_xml_allowlist_p2_dan_satu_satunya_href_adalah_ikon_terdaftar(tema, gaya):
    parameter = {"varian": "terbanyak", "tema": tema, "n1": 1, "n2": 8, "n3": 4, "skala": 2}
    html_hasil = render_pertanyaan(_penyajian(parameter), gaya=gaya)
    svg = periksa_xml(html_hasil)
    tanpa_xmlns = html_hasil.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert not re.search(r"<script|foreignObject|javascript:|https?:|//|\son[a-z]+=", tanpa_xmlns, re.I)
    href = [e.get("href") for e in svg.iter() if "href" in e.attrib]
    assert len(href) == 8 + 1 + 4
    assert all(re.fullmatch(r"/aset/ikon-[a-z]+-v1\.webp", h) for h in href)
    assert {h.rsplit("/", 1)[1] for h in href} <= set(brand.ASET)
    assert all("href" not in e.attrib for e in svg.iter() if lokal(e) != "image")


def test_legenda_hanya_teks_polos_satu_warna_token():
    svg = _svg()
    legenda, = kelas(svg, "legenda-adegan")
    assert {e.get("fill") for e in legenda.iter() if e.get("fill")} == {T.TEKS_UTAMA}
    assert {lokal(e) for e in legenda.iter()} <= {"g", "text", "line"}


@pytest.mark.parametrize("satuan", (0, 3, -1, 2.0, "2", None, True, [2]))
def test_satuan_ikon_di_luar_satu_atau_dua_ditolak_validator_dan_renderer(satuan):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["satuan_ikon"] = satuan
    with pytest.raises(ValueError):
        validasi_adegan_awal(data)
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


@pytest.mark.parametrize("satuan", (1, 2))
def test_satuan_ikon_satu_dan_dua_diterima_validator(satuan):
    data = _penyajian(SKALA_SATU).descriptor.ke_dict()["data"]
    data["satuan_ikon"] = satuan
    validasi_adegan_awal(data)
    assert DescriptorVisual("adegan_awal", 1, data)


def _tolak(parameter):
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(TID, parameter)


def test_proyektor_menolak_skala_tak_sah_bentuk_p1_dan_p2_dan_field_tak_tepat():
    soal = _soal(SKALA_DUA)
    for skala in (0, 3, True, 2.0, "2", None, [2]):
        _tolak({**soal.parameter, "skala": skala})
    _tolak({**soal.parameter, "n1": 9})                       # skala 2 batas 8
    _tolak({**soal.parameter, "skala": 1, "n1": 13})          # skala 1 batas 12
    _tolak({k: v for k, v in soal.parameter.items() if k not in ("skala", "n3")})
    _tolak({k: v for k, v in soal.parameter.items() if k != "x"})
    _tolak({**soal.parameter, "kunci": "26"})
    _tolak({**soal.parameter, "versi_katalog": 2})
    _tolak({**soal.parameter, "tanya": 0})
    # bentuk P1 (tanpa skala) tidak boleh lolos dengan jumlah di atas batas P1 (8)
    _tolak({k: v for k, v in {**soal.parameter, "n1": 11}.items() if k != "skala"})
    _tolak({k: v for k, v in {**SKALA_SATU, "n3": 12}.items() if k != "skala"})


def test_proyektor_bentuk_p1_tanpa_skala_tetap_diterima_dan_p2_skala_satu_dua_diterima():
    p1 = {k: v for k, v in SKALA_SATU.items() if k != "skala"} | {"n1": 8, "n2": 6}
    teks, descriptor = proyeksi_matematika_awal(TID, p1)
    assert teks.startswith("Perhatikan gambar. Satu gambar mewakili 1 buah.")
    assert descriptor.ke_dict()["data"]["satuan_ikon"] == 1
    for parameter in (SKALA_SATU, SKALA_DUA):
        assert proyeksi_matematika_awal(TID, parameter) is not None


def test_bentuk_teks_sumber_berubah_gagal_keras(monkeypatch):
    monkeypatch.setattr(sumber, "_kepala", lambda tema, skala=None: "Kepala lain yang tidak dikenal.")
    with pytest.raises(ValueError, match="bentuk teks soal sumber berubah"):
        proyeksi_matematika_awal(TID, _soal(SKALA_DUA).parameter)
    monkeypatch.undo()
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
    assert proyeksi_matematika_awal(TID, _soal(SKALA_DUA).parameter) is not None


# ── invarian 5: batas viewBox dan tanpa tumpang tindih ───────────────────

def _kotak_image(svg):
    return tuple((float(e.get("x")), float(e.get("y")), float(e.get("width")), float(e.get("height")))
                 for e in elemen(svg, "image"))


def _tumpang_tindih(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _data_p2_penuh(nama, jumlah=12, satuan=2, banyak=3):
    return {
        "adegan": "deret_ikon",
        "baris": [{"nama": nama + str(i), "ikon": IKON_DIDUKUNG[i], "jumlah": jumlah}
                  for i in range(banyak)],
        "satuan_ikon": satuan, "tanya": {"varian": "terbanyak"},
    }


@pytest.mark.parametrize("nama", ("A", "Kelinci", "W" * 22))
@pytest.mark.parametrize("banyak", (3, 4))
def test_baris_dua_belas_ikon_dengan_legenda_muat_dan_tidak_tumpang_tindih(nama, banyak):
    html_svg = adegan_awal_svg.render_adegan_awal(_data_p2_penuh(nama, banyak=banyak), "batas")
    svg = periksa_xml("<div>" + html_svg + "</div>")
    periksa_batas_koordinat(svg)
    kotak = _kotak_image(svg)
    assert len(kotak) == 12 * banyak
    assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])
    lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
    assert lebar == T.ADEGAN_LEBAR
    assert all(x + w <= lebar and y + h <= tinggi for x, y, w, h in kotak)
    legenda, = kelas(svg, "legenda-adegan")
    atas_ikon = min(y for _, y, _, _ in kotak)
    garis = elemen(legenda, "line")[0]
    teks = elemen(legenda, "text")[0]
    assert float(teks.get("y")) < float(garis.get("y1")) <= atas_ikon
    assert float(teks.get("y")) <= atas_ikon


@pytest.mark.parametrize("skala", (1, 2))
@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_semua_soal_p2_sah_dalam_viewbox_dan_ikon_tidak_bertumpuk(varian, skala):
    for parameter in _kelompok(varian, skala)[::157]:
        svg = _svg(parameter)
        periksa_batas_koordinat(svg)
        kotak = _kotak_image(svg)
        assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])


def test_label_sejajar_dengan_ikon_pertama_barisnya_pada_skala_dua():
    svg = _svg()
    for baris in kelas(svg, "baris-adegan"):
        ys = [float(e.get("y")) for e in elemen(baris, "image")]
        label_y = float(elemen(baris, "text")[0].get("y"))
        assert min(ys) <= label_y <= min(ys) + T.ADEGAN_IKON + 1


# ── invarian 6: aksesibilitas ────────────────────────────────────────────

def test_desc_skala_dua_menyebut_skala_tanpa_jumlah_baris_atau_jawaban():
    svg = _svg()
    judul, = elemen(svg, "title")
    uraian, = elemen(svg, "desc")
    assert svg.get("role") == "img"
    assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
    isi = "".join(uraian.itertext())
    assert "satu gambar mewakili 2 benda" in isi.lower()
    # satu-satunya angka di desc dan judul adalah skala 2 (bukan jumlah gambar atau jawaban)
    assert re.findall(r"\d+", isi + "".join(judul.itertext())) == ["2"]
    for nama in ("Bola", "Mobil", "Boneka"):
        assert nama in isi
    assert str(_soal(SKALA_DUA).kunci) not in isi


def test_desc_skala_dua_hanya_bergantung_pada_nama_dan_skala_bukan_jumlah_atau_pertanyaan():
    a = {"varian": "baca", "tema": "buah", "n1": 1, "n2": 2, "n3": 3, "tanya": 0, "skala": 2}
    b = {"varian": "terbanyak", "tema": "buah", "n1": 8, "n2": 7, "n3": 6, "skala": 2}
    desc = ["".join(elemen(_svg(p), "desc")[0].itertext()) for p in (a, b)]
    assert desc[0] == desc[1]


def test_desc_skala_satu_tetap_tanpa_angka_seperti_p1():
    isi = "".join(elemen(_svg(SKALA_SATU), "desc")[0].itertext())
    assert not re.search(r"\d", isi)


def test_semua_teks_svg_p2_satu_warna_token_dan_tidak_kosong():
    svg = _svg()
    assert {e.get("fill") for e in svg.iter() if e.get("fill")} == {T.TEKS_UTAMA}
    assert all(t for t in teks_svg(svg))


def test_id_unik_pada_lembar_dengan_banyak_soal_p2_berulang():
    ids = []
    for i in range(6):
        ids += [e.get("id") for e in _svg(namespace=f"lembar-{i}").iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12


# ── invarian 7: inventaris dan generator ─────────────────────────────────

def test_inventaris_menandai_baca_diagram_gambar_wajib_visual_di_p1_dan_p2():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {(d["level"], d["varian"]) for d in baris} == {
        (lv, f"varian={v}") for lv in ("P1", "P2") for v in sumber.VARIAN}


def test_generator_p2_menghasilkan_soal_skala_yang_terproyeksi_siap():
    import generator
    ditemui = set()
    for seed in range(60):
        soal = generator.buat_soal(TID, seed, "P2", "matematika-awal")
        assert soal.parameter["skala"] in (1, 2)
        ditemui.add(soal.parameter["skala"])
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "siap"
        assert penyajian.descriptor.ke_dict()["data"]["satuan_ikon"] == soal.parameter["skala"]
    assert ditemui == {1, 2}


# Nilai beku, dihitung dari contoh SKALA_DUA saat P2 selesai dirancang.
FINGERPRINT_MATEMATIS_SKALA_DUA = "19a7f1f015abca0f992b0237f09df397276cd43ffb6da0baa599bfe217baeb06"
FINGERPRINT_PENYAJIAN_SKALA_DUA = "bd2983622f34fda251c8d5f88038cf46e8654990709d28945809992b12f498b7"
