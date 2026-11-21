"""Keluarga visual `matematika-awal`: piktogram_lima_awal (P5, deret_ikon berskala 2/5/10/20, adegan_awal v1).

Solver mandiri HANYA membaca teks proyeksi + SVG hasil `render_pertanyaan` (`piktogram_solver_helpers`):
hitung `<image>` per `<g class="baris-adegan">`, skala dari kalimat pengantar yang dicocokkan ke legenda
gambar, pertanyaan dari kalimat terakhir; hasilnya dibandingkan dengan `soal.kunci` untuk SELURUH
`domain_parameter("P5")`. Juga: perluasan validator `deret_ikon` (satuan_ikon 5/10/20, sampai lima baris,
jenis pertanyaan baru) tanpa mengubah satu byte pun keluaran jenis lama (sidik jari di bawah).
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adegan_awal_svg
import awal_baca_diagram_gambar as sumber_diagram
import awal_piktogram_lima_awal as sumber
import awal_turus_gambar_awal as sumber_turus
import awal_ukur_satuan_tak_baku as sumber_ukur
import brand
import design_tokens as T
from adegan_awal_data import IKON_DIDUKUNG, validasi_adegan_awal
from piktogram_solver_helpers import (SIMBOL, _svg_dari, baris_svg, legenda_svg, solver_dari_teks,
                                      solver_dari_visual)
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian
from visual_inventory import DENOMINATOR_KANONIS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, lokal, periksa_xml

TID = sumber.TEMPLATE_ID
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
# Sidik jari keluaran jenis LAMA (baca_diagram_gambar P1 dan P2, turus_gambar_awal, ukur_satuan_tak_baku):
# proyeksi, descriptor, SVG, ringkasan. Dihitung dari pohon SEBELUM `deret_ikon` diperluas (22 Nov 2026);
# berubah = keluaran lama berubah, jadi cari penyebabnya, jangan perbarui angkanya.
SIDIK_JENIS_LAMA = "cdf845ac32685ba4df1696bee09573c7894310705b48ac74c375159e3292b0d2"
BANYAK_ITEM_JENIS_LAMA = 4953


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _anggota(varian, **ciri):
    return tuple(p for p in sumber.domain_parameter("P5")
                 if p["varian"] == varian and all(p.get(k) == v for k, v in ciri.items()))


def _satu(varian, **ciri) -> dict:
    return _anggota(varian, **ciri)[0]


def _soal(parameter):
    return replace(sumber.piktogram_lima_awal(**parameter), level="P5")


def _penyajian(parameter):
    return penyajian_dari_soal(_soal(parameter))


def _html(parameter, *, namespace="uji-pikto", gaya="cetak"):
    return render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya)


def _svg(parameter, **kw):
    return periksa_xml(_html(parameter, **kw))


def _tampil(parameter) -> dict:
    """{nama: banyak gambar} yang harus tampil di gambar (semua, kecuali baris yang ditanya berapa_ikon)."""
    kategori = sumber.TEMA[parameter["tema"]].kategori
    lewat = parameter.get("tanya") if parameter["varian"] == "berapa_ikon" else None
    return {kategori[i][0]: n for i, n in enumerate(parameter["jumlah"]) if i != lewat}


# ── solver mandiri: hanya teks proyeksi + SVG ────────────────────────────

@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_solver_svg_sama_dengan_kunci_dan_baris_tepat_seluruh_domain(varian):
    anggota = _anggota(varian)
    assert anggota
    for parameter in anggota:
        soal = _soal(parameter)
        penyajian = penyajian_dari_soal(soal)
        html_hasil = render_pertanyaan(penyajian, namespace="sapuan")
        assert solver_dari_visual(penyajian.teks_soal, html_hasil) == soal.kunci, parameter
        assert baris_svg(_svg_dari(html_hasil)) == _tampil(parameter), parameter


# ── invarian 1: tanpa flag tidak berubah ─────────────────────────────────

@pytest.mark.parametrize("varian", sumber.VARIAN)
@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
def test_tanpa_keluarga_matematika_awal_teks_titik_hitam_persis_dan_bisa_dijawab(monkeypatch, flag, varian):
    if flag is None:
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    else:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", flag)
    for parameter in _anggota(varian)[::97]:
        soal = _soal(parameter)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "tanpa_visual"
        assert penyajian.mode_representasi == "teks-v1"
        assert penyajian.descriptor is None
        assert penyajian.teks_soal == soal.teks
        assert SIMBOL in penyajian.teks_soal and "<svg" not in render_pertanyaan(penyajian)
        assert solver_dari_teks(penyajian.teks_soal) == soal.kunci


# ── invarian 2: teks proyeksi, descriptor, jumlah <image>, legenda ───────

@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_flag_aktif_status_siap_teks_tanpa_simbol_titik_hitam_dan_angka_data(varian):
    for parameter in _anggota(varian)[::53]:
        penyajian = _penyajian(parameter)
        assert penyajian.status_visual == "siap" and penyajian.mode_representasi == "adegan_awal-v1"
        teks = penyajian.teks_soal
        assert SIMBOL not in teks and "titik hitam" not in teks
        kata = sumber.TEMA[parameter["tema"]].kata
        awal, tanya = teks.split("\n")
        assert awal == f"Perhatikan gambar. Satu gambar mewakili {parameter['skala']} {kata}."
        angka = re.findall(r"\d+", teks)
        if varian == "berapa_ikon":  # nilai benda yang diketahui ada di pertanyaan, bukan jawaban
            nilai = parameter["jumlah"][parameter["tanya"]] * parameter["skala"]
            assert angka == [str(parameter["skala"]), str(nilai)], teks
            assert "Berapa gambar yang harus digambar" in tanya
        else:
            assert angka == [str(parameter["skala"])], teks


def test_pertanyaan_visual_sama_dengan_teks_kecuali_kata_lambang_pada_berapa_ikon():
    for varian in sumber.VARIAN:
        for parameter in _anggota(varian)[::211]:
            visual = _penyajian(parameter).teks_soal.split("\n")[-1]
            teks = _soal(parameter).teks.split("\n")[-1]
            assert visual == (teks.replace("titik hitam", "gambar") if varian == "berapa_ikon" else teks)


def test_descriptor_membawa_satuan_ikon_dan_tidak_kunci_atau_jawaban():
    parameter = _satu("baca_nilai", skala=10)
    penyajian = _penyajian(parameter)
    data = penyajian.descriptor.ke_dict()["data"]
    assert set(data) == {"adegan", "baris", "satuan_ikon", "tanya"} and data["adegan"] == "deret_ikon"
    assert data["satuan_ikon"] == 10 and type(data["satuan_ikon"]) is int
    assert data["tanya"] == {"varian": "baca", "i": parameter["tanya"]}
    assert [b["jumlah"] for b in data["baris"]] == parameter["jumlah"]
    assert "kunci" not in serialisasi_penyajian(penyajian)


@pytest.mark.parametrize("varian,harapan", (
    ("terbanyak_selisih", {"varian": "terbanyak_selisih"}), ("total", {"varian": "total"}),
    ("rata_rata", {"varian": "rata_rata"}), ("berapa_ikon", {"varian": "berapa_ikon"})))
def test_descriptor_jenis_pertanyaan_tanpa_indeks_untuk_varian_lain(varian, harapan):
    data = _penyajian(_satu(varian)).descriptor.ke_dict()["data"]
    assert data["tanya"] == harapan


def test_berapa_ikon_tidak_menggambar_baris_yang_ditanya_di_descriptor_svg_dan_ringkasan():
    for parameter in _anggota("berapa_ikon")[::43]:
        nama = sumber.TEMA[parameter["tema"]].kategori[parameter["tanya"]][0]
        penyajian = _penyajian(parameter)
        data = penyajian.descriptor.ke_dict()["data"]
        assert nama not in [b["nama"] for b in data["baris"]]
        assert len(data["baris"]) == len(parameter["jumlah"]) - 1 >= 3
        html_hasil = render_pertanyaan(penyajian, namespace="ber")
        svg = periksa_xml(html_hasil)
        assert nama not in "".join("".join(t.itertext()) for t in elemen(svg, "text"))
        assert nama not in "".join(elemen(svg, "desc")[0].itertext())
        fakta = ringkasan_pertanyaan(penyajian).split("Fakta visual:")[1]
        assert nama not in fakta and fakta.count("memiliki") == len(parameter["jumlah"]) - 1
        assert int(_soal(parameter).kunci) not in baris_svg(svg).values(), (
            "banyak gambar yang dicari tidak boleh sama dengan baris lain yang tertampil")


@pytest.mark.parametrize("gaya", GAYA)
def test_jumlah_image_per_baris_sama_banyak_gambar_dan_legenda_tanpa_image(gaya):
    parameter = _satu("total", skala=5, tema="mainan")
    svg = _svg(parameter, gaya=gaya)
    assert tuple(baris_svg(svg).values()) == tuple(parameter["jumlah"])
    assert len(elemen(svg, "image")) == sum(parameter["jumlah"])
    legenda, = kelas(svg, "legenda-adegan")
    assert not elemen(legenda, "image")
    assert legenda_svg(svg) == "Satu gambar mewakili 5 benda."


@pytest.mark.parametrize("skala", sumber.SKALA)
def test_legenda_di_luar_semua_grup_baris_dan_tidak_menjadi_label_baris(skala):
    svg = _svg(_satu("total", skala=skala, tema="mainan"))
    legenda, = kelas(svg, "legenda-adegan")
    for baris in kelas(svg, "baris-adegan"):
        assert legenda not in list(baris.iter())
        assert "Satu gambar" not in "".join(baris.itertext())
    assert legenda_svg(svg) == f"Satu gambar mewakili {skala} benda."


def test_ringkasan_non_html_menyebut_skala_besar():
    parameter = _satu("baca_nilai", skala=20)
    ringkasan = ringkasan_pertanyaan(_penyajian(parameter))
    assert "satu gambar mewakili 20 benda" in ringkasan
    nama = sumber.TEMA[parameter["tema"]].kategori[0][0]
    assert f"{nama} memiliki {parameter['jumlah'][0]} gambar" in ringkasan


# ── invarian 3: determinisme dan fingerprint ─────────────────────────────

def test_render_dua_kali_identik_byte_per_byte_dan_fingerprint_stabil():
    parameter = _satu("rata_rata")
    penyajian = _penyajian(parameter)
    assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
    assert _penyajian(parameter).fingerprint_penyajian == _penyajian(parameter).fingerprint_penyajian


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_round_trip_serialisasi_dan_fingerprint_matematis_sama_antara_mode_teks_dan_visual(monkeypatch, varian):
    parameter = _satu(varian)
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
        "import awal_piktogram_lima_awal as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P5')[::97]:\n"
        "    s = penyajian_dari_soal(replace(m.piktogram_lima_awal(**p), level='P5'))\n"
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
    parameter = next(p for p in _anggota("total", tema=tema))
    html_hasil = _html(parameter, gaya=gaya)
    svg = periksa_xml(html_hasil)
    tanpa_xmlns = html_hasil.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert not re.search(r"<script|foreignObject|javascript:|https?:|//|\son[a-z]+=", tanpa_xmlns, re.I)
    href = [e.get("href") for e in svg.iter() if "href" in e.attrib]
    assert len(href) == sum(parameter["jumlah"])
    assert all(re.fullmatch(r"/aset/ikon-[a-z]+-v1\.webp", h) for h in href)
    assert {h.rsplit("/", 1)[1] for h in href} <= set(brand.ASET)
    assert all("href" not in e.attrib for e in svg.iter() if lokal(e) != "image")


def test_svg_tidak_memuat_kelas_atau_atribut_yang_menyebut_jawaban():
    for varian in sumber.VARIAN:
        for parameter in _anggota(varian)[::223]:
            html_hasil = _html(parameter)
            svg = periksa_xml(html_hasil)
            assert {e.get("class") for e in svg.iter() if e.get("class")} == {"baris-adegan", "legenda-adegan"}
            markup = re.search(r"<svg.*</svg>", html_hasil, re.S).group(0)
            assert not re.search(r"data-|kunci|jawaban|total|rata|selisih|terbanyak", markup, re.I)


# ── invarian 5: proyektor ────────────────────────────────────────────────

def _tolak(parameter):
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(TID, parameter)


def test_proyektor_menolak_parameter_tak_sah_dan_field_tak_tepat():
    sah = _satu("baca_nilai")
    for skala in (0, 3, True, 5.0, "5", None, [5], 40):
        _tolak({**sah, "skala": skala})
    _tolak({**sah, "jumlah": [*sah["jumlah"][:2]]})
    _tolak({**sah, "jumlah": [1, 1, 2]})
    _tolak({k: v for k, v in sah.items() if k != "tanya"})
    _tolak({k: v for k, v in sah.items() if k != "jumlah"})
    _tolak({**sah, "kunci": "20"})
    _tolak({**sah, "versi_katalog": 2})
    _tolak({**_satu("total"), "tanya": 0})
    _tolak({**sah, "varian": "tidak_ada"})
    _tolak({**sah, "varian": None})
    _tolak({k: v for k, v in sah.items() if k != "varian"})


def test_proyektor_menerima_seluruh_domain_dan_mengembalikan_descriptor_sah():
    for parameter in sumber.domain_parameter("P5")[::13]:
        teks, descriptor = proyeksi_matematika_awal(TID, parameter)
        assert isinstance(descriptor, DescriptorVisual) and teks.startswith("Perhatikan gambar.")


def test_bentuk_teks_sumber_berubah_gagal_keras(monkeypatch):
    parameter = _satu("total")
    asli = sumber._teks
    for rusak in ("Kepala lain yang tidak dikenal.\nBola: ●\nMobil: ●●\nBoneka: ●●●\nBerapa jumlah semua mainan?",
                  asli(*[parameter["varian"], parameter["tema"], parameter["skala"], tuple(parameter["jumlah"]),
                         None]) + "\nBaris tambahan?"):
        monkeypatch.setattr(sumber, "_teks", lambda *a, _r=rusak: _r)
        with pytest.raises(ValueError, match="bentuk teks soal sumber berubah"):
            proyeksi_matematika_awal(TID, parameter)
    monkeypatch.undo()
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")
    assert proyeksi_matematika_awal(TID, parameter) is not None


# ── invarian 6: batas viewBox dan tanpa tumpang tindih ───────────────────

def _kotak_image(svg):
    return tuple((float(e.get("x")), float(e.get("y")), float(e.get("width")), float(e.get("height")))
                 for e in elemen(svg, "image"))


def _tumpang_tindih(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def _data_penuh(*, banyak=5, jumlah=10, satuan=20, nama="Kelereng"):
    return {
        "adegan": "deret_ikon",
        "baris": [{"nama": f"{nama[:7]}{i}", "ikon": IKON_DIDUKUNG[i], "jumlah": jumlah} for i in range(banyak)],
        "satuan_ikon": satuan, "tanya": {"varian": "total"},
    }


@pytest.mark.parametrize("banyak", (3, 4, 5))
@pytest.mark.parametrize("nama", ("A", "Kelereng", "W" * 7))
def test_lima_baris_sepuluh_ikon_dengan_legenda_muat_dan_tidak_tumpang_tindih(banyak, nama):
    html_svg = adegan_awal_svg.render_adegan_awal(_data_penuh(banyak=banyak, nama=nama), "batas")
    svg = periksa_xml("<div>" + html_svg + "</div>")
    periksa_batas_koordinat(svg)
    kotak = _kotak_image(svg)
    assert len(kotak) == 10 * banyak
    assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])
    lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
    assert lebar == T.ADEGAN_LEBAR
    assert all(x + w <= lebar and y + h <= tinggi for x, y, w, h in kotak)
    legenda, = kelas(svg, "legenda-adegan")
    atas_ikon = min(y for _, y, _, _ in kotak)
    garis = elemen(legenda, "line")[0]
    assert float(elemen(legenda, "text")[0].get("y")) < float(garis.get("y1")) <= atas_ikon


def test_semua_soal_sah_dalam_viewbox_dan_ikon_tidak_bertumpuk():
    for varian in sumber.VARIAN:
        for parameter in _anggota(varian)[::59]:
            svg = _svg(parameter)
            periksa_batas_koordinat(svg)
            kotak = _kotak_image(svg)
            assert not any(_tumpang_tindih(a, b) for i, a in enumerate(kotak) for b in kotak[i + 1:])


# ── invarian 7: aksesibilitas ────────────────────────────────────────────

def test_desc_menyebut_skala_dan_nama_baris_tanpa_jumlah_atau_jawaban():
    for varian in sumber.VARIAN:
        for parameter in _anggota(varian)[::113]:
            svg = _svg(parameter)
            judul, = elemen(svg, "title")
            uraian, = elemen(svg, "desc")
            assert svg.get("role") == "img"
            assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
            isi = "".join(uraian.itertext())
            assert f"satu gambar mewakili {parameter['skala']} benda" in isi.lower()
            assert re.findall(r"\d+", isi + "".join(judul.itertext())) == [str(parameter["skala"])]
            for nama in _tampil(parameter):
                assert nama in isi


def test_desc_hanya_bergantung_pada_nama_dan_skala_bukan_jumlah_atau_pertanyaan():
    data = _penyajian(_satu("baca_nilai", tema="hewan", skala=10)).descriptor.ke_dict()["data"]
    lain = {**data, "tanya": {"varian": "total"},
            "baris": [{**b, "jumlah": n["jumlah"]} for b, n in zip(data["baris"], reversed(data["baris"]))]}
    assert [b["jumlah"] for b in lain["baris"]] != [b["jumlah"] for b in data["baris"]]
    desc = ["".join(elemen(periksa_xml(adegan_awal_svg.render_adegan_awal(d, "x")), "desc")[0].itertext())
            for d in (data, lain)]
    assert desc[0] == desc[1]


# ── invarian 8: perluasan validator tanpa mengubah jenis lama ────────────

def _data_sah(**ubah) -> dict:
    dasar = {"adegan": "deret_ikon",
             "baris": [{"nama": f"K{i}", "ikon": IKON_DIDUKUNG[i], "jumlah": 2 + i} for i in range(3)],
             "satuan_ikon": 5, "tanya": {"varian": "total"}}
    return {**dasar, **ubah}


@pytest.mark.parametrize("satuan", (1, 2, 5, 10, 20))
def test_satuan_ikon_himpunan_baru_diterima_validator_dan_renderer(satuan):
    data = _data_sah(satuan_ikon=satuan)
    validasi_adegan_awal(data)
    assert DescriptorVisual("adegan_awal", 1, data)
    assert adegan_awal_svg.render_adegan_awal(data, "uji")


@pytest.mark.parametrize("satuan", (0, 3, 4, 6, 15, 25, 50, -5, 5.0, "5", None, True, [5], 100))
def test_satuan_ikon_di_luar_himpunan_baru_ditolak_validator_dan_renderer(satuan):
    data = _data_sah(satuan_ikon=satuan)
    with pytest.raises(ValueError):
        validasi_adegan_awal(data)
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


@pytest.mark.parametrize("tanya", (
    {"varian": "terbanyak_selisih"}, {"varian": "total"}, {"varian": "rata_rata"}, {"varian": "berapa_ikon"},
    {"varian": "baca", "i": 1}, {"varian": "terbanyak"}, {"varian": "selisih", "x": 0, "y": 1},
    {"varian": "jumlah", "x": 0, "y": 1}))
def test_jenis_pertanyaan_deret_ikon_diterima(tanya):
    validasi_adegan_awal(_data_sah(tanya=tanya))


@pytest.mark.parametrize("tanya", (
    {"varian": "total", "i": 0}, {"varian": "rata_rata", "x": 0, "y": 1}, {"varian": "berapa_ikon", "x": 0},
    {"varian": "terbanyak_selisih", "kunci": 1}, {"varian": "Total"}, {"varian": "total "}, {"varian": ["total"]},
    {"varian": None}, {"varian": "median"}, {}, "total", None))
def test_jenis_pertanyaan_baru_tanpa_field_lain_dan_varian_asing_ditolak(tanya):
    with pytest.raises(ValueError):
        validasi_adegan_awal(_data_sah(tanya=tanya))


def test_lima_baris_diterima_deret_ikon_tetapi_turus_tetap_maksimal_empat_baris():
    contoh = [{"nama": f"K{i}", "ikon": IKON_DIDUKUNG[i], "jumlah": 1 + i} for i in range(6)]
    validasi_adegan_awal(_data_sah(baris=contoh[:5]))
    with pytest.raises(ValueError):
        validasi_adegan_awal(_data_sah(baris=contoh[:6]))
    turus = lambda n: {"adegan": "turus", "baris": [{"nama": b["nama"], "jumlah": b["jumlah"]} for b in contoh[:n]],
                       "tanya": {"varian": "terbanyak"}}
    validasi_adegan_awal(turus(4))
    for banyak in (1, 5, 6):
        with pytest.raises(ValueError):
            validasi_adegan_awal(turus(banyak))


def test_turus_tidak_menerima_jenis_pertanyaan_baru_piktogram():
    dasar = {"adegan": "turus", "baris": [{"nama": f"K{i}", "jumlah": 1 + i} for i in range(3)]}
    validasi_adegan_awal({**dasar, "tanya": {"varian": "jumlah"}})
    for varian in ("total", "rata_rata", "terbanyak_selisih", "berapa_ikon"):
        with pytest.raises(ValueError):
            validasi_adegan_awal({**dasar, "tanya": {"varian": varian}})


def test_deret_ikon_p1_p2_tetap_tertutup_untuk_jumlah_di_atas_dua_belas_dan_nama_kembar():
    baris = [{"nama": "A", "ikon": "bola", "jumlah": 13}, {"nama": "B", "ikon": "mobil", "jumlah": 1}]
    with pytest.raises(ValueError):
        validasi_adegan_awal(_data_sah(baris=baris))
    kembar = [{"nama": "A", "ikon": "bola", "jumlah": 3}, {"nama": "a", "ikon": "mobil", "jumlah": 1}]
    with pytest.raises(ValueError):
        validasi_adegan_awal(_data_sah(baris=kembar))


def _sidik_jenis_lama() -> tuple:
    h, n = hashlib.sha256(), 0

    def masuk(tid, parameter):
        nonlocal n
        teks, desc = proyeksi_matematika_awal(tid, parameter)
        data = desc.ke_dict()["data"]
        h.update(repr((tid, sorted(parameter.items(), key=lambda kv: kv[0]), teks, data)).encode())
        h.update(adegan_awal_svg.render_adegan_awal(data, "ns").encode())
        h.update(adegan_awal_svg.ringkasan_adegan_awal(data).encode())
        n += 1

    for level in ("P1", "P2"):
        domain = sumber_diagram.domain_parameter(level)
        for parameter in domain[::7]:
            masuk(sumber_diagram.TEMPLATE_ID, parameter)
        for parameter in domain[-5:]:
            masuk(sumber_diagram.TEMPLATE_ID, parameter)
        soal = sumber_diagram.baca_diagram_gambar(**domain[0])
        h.update(repr((soal.teks, soal.kunci, soal.pembahasan, soal.malrule)).encode())
    for modul in (sumber_turus, sumber_ukur):
        for level in modul.LEVEL:
            domain = modul.domain_parameter(level)
            for parameter in domain[::max(1, len(domain) // 300)]:
                masuk(modul.TEMPLATE_ID, parameter)
    return n, h.hexdigest()


def test_keluaran_jenis_lama_byte_identik_dengan_sebelum_perluasan_deret_ikon():
    """baca_diagram_gambar P1/P2, turus_gambar_awal, dan ukur_satuan_tak_baku: proyeksi + SVG + ringkasan."""
    assert _sidik_jenis_lama() == (BANYAK_ITEM_JENIS_LAMA, SIDIK_JENIS_LAMA)


# ── invarian 9: inventaris dan generator ─────────────────────────────────

def test_inventaris_menandai_piktogram_lima_awal_wajib_visual_di_p5():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {(d["level"], d["varian"]) for d in baris} == {("P5", f"varian={v}") for v in sumber.VARIAN}


def test_generator_p5_menghasilkan_soal_piktogram_yang_terproyeksi_siap():
    import generator
    ditemui = set()
    for seed in range(120):
        soal = generator.buat_soal(TID, seed, "P5", "matematika-awal")
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "siap"
        assert penyajian.descriptor.ke_dict()["data"]["satuan_ikon"] == soal.parameter["skala"]
        ditemui.add(soal.parameter["varian"])
    assert ditemui == set(sumber.VARIAN)
