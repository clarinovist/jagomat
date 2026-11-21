"""Keluarga visual `matematika-awal`: kenali_bangun_awal bergambar (adegan_awal v1, `bentuk`).

Solver mandiri HANYA membaca teks proyeksi dan SVG hasil `render_pertanyaan` (jenis bangun
dari GEOMETRI: jumlah titik polygon, rasio sisi sisi-depan, circle, ellipse) lewat
`penyajian_dari_soal`, lalu dibandingkan dengan `soal.kunci` untuk SELURUH domain P1 dan P2
(sapuan penuh, tanpa stride). Kebocoran diuji pada string HTML mentah (kelas, id, judul,
uraian, atribut), bukan hanya pada SVG yang sudah di-parse.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import adegan_awal_data
import adegan_awal_svg
import awal_kenali_bangun_awal as sumber
import bentuk_katalog as katalog
import design_tokens as T
from bentuk_solver_helpers import DATAR_TES, RUANG_TES, solver_dari_teks
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian
from visual_inventory import DENOMINATOR_KANONIS, VARIAN_SENGAJA_TEKS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, kontras, lokal, periksa_xml, teks_svg

TID = sumber.TEMPLATE_ID
LEVEL = ("P1", "P2")
GAMBAR = ("datar_gambar", "ruang_gambar", "hitung_bentuk")
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
BENTUK_ELEMEN = {"polygon", "circle", "ellipse", "line"}
TAG_BOLEH = {"svg", "title", "desc", "g"} | BENTUK_ELEMEN
KELAS_BOLEH = {"baris-bangun", "bangun-gambar"}
NAMA_BANGUN = katalog.SEMUA_NAMA
TOLERANSI = 0.05  # koordinat dibulatkan dua desimal
RASIO_BEDA_JELAS = 1.5
CONTOH_DATAR = dict(varian="datar_gambar", himpunan="lengkap", bangun="persegi panjang", ragam="mendatar",
                    putar=0, ukuran="besar", warna="biru")
CONTOH_RUANG = dict(varian="ruang_gambar", himpunan="lengkap", bangun="kerucut", ragam="tegak",
                    putar=0, ukuran="besar", warna="kuning")
CONTOH_KUBUS = dict(varian="ruang_gambar", himpunan="dasar", bangun="kubus", ragam="biasa",
                    putar=0, ukuran="besar", warna="hijau")
CONTOH_HITUNG = dict(varian="hitung_bentuk", himpunan="lengkap", banyak=[2, 3, 1, 4], tanya=1, tata=1)


FINGERPRINT_DIPATOK = {
    "datar": ("4fc9b6008144b79756269646a5ef3f4c6728668bfcf318f2238f22e757f89e8a",
              "570e401289cede895b40f194b44a4970c71683f3e6bb60390ba2f043f9d0a6cb"),
    "ruang": ("fc4801a870ebe65bb3d825995d55c06e0d3ea10653f74e617cbd5f1923a9ba84",
              "0606411aa8bf8a62b6f96385977a5d5bb6275c52e9ff97420e707ce2f1626a88"),
    "kubus": ("15ef7ee91bb79714d6e144aa8eb9331a6820a3976e8ab16a38f085b58f07f8b8",
              "36d8fc835784beec42f6d13f71ca6bf2cf27aa7108232ce1c19fa10d77b68c12"),
    "hitung": ("5fec0bc8cc339e61e3d2518d85590718fd97453f85058990dc94a30ee6838572",
               "8a6482848fd95cebba1b1cd2f2067ec3e396754ccab0406152f7cc39b847c07f"),
}


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _level(himpunan: str) -> str:
    return "P1" if himpunan == "dasar" else "P2"


def _soal(parameter, level=None):
    level = level or _level(parameter["himpunan"])
    return replace(sumber.kenali_bangun_awal(**parameter), level=level)


def _penyajian(parameter, level=None):
    return penyajian_dari_soal(_soal(parameter, level))


def _html(parameter, *, namespace="uji-bentuk", gaya="cetak"):
    return render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya)


def _svg(parameter, **kw):
    return periksa_xml(_html(parameter, **kw))


def _domain(level, *varian):
    return tuple(p for p in sumber.domain_parameter(level) if p["varian"] in varian)


def _data(daftar, tampil=None):
    tampil = tampil or ("satu" if len(daftar) == 1 else "baris")
    return {"adegan": "bentuk", "tampil": tampil, "bangun": list(daftar)}


def _bangun(nama="segitiga", ragam=None, putar=0, ukuran="besar", warna="biru"):
    return {"nama": nama, "ragam": ragam or katalog.RAGAM[nama][0], "putar": putar,
            "ukuran": ukuran, "warna": warna}


def _svg_data(data, namespace="uji"):
    return periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, namespace) + "</div>")


# ── solver mandiri dari geometri SVG ─────────────────────────────────────

def _titik(e):
    angka = [float(v) for v in e.get("points").replace(",", " ").split()]
    return list(zip(angka[::2], angka[1::2]))


def _sisi(titik):
    return [math.dist(a, b) for a, b in zip(titik, titik[1:] + titik[:1])]


def _sejajar_sumbu(titik):
    return all(abs(a[0] - b[0]) < TOLERANSI or abs(a[1] - b[1]) < TOLERANSI
               for a, b in zip(titik, titik[1:] + titik[:1]))


def _bentuk(g):
    return [e for e in g.iter() if lokal(e) in BENTUK_ELEMEN]


def _klasifikasi_empat_titik(titik):
    """Persegi, persegi panjang (rasio >= 1,5), atau None bila bukan segiempat sejajar sumbu."""
    if not _sejajar_sumbu(titik):
        return None
    lebar = max(x for x, _ in titik) - min(x for x, _ in titik)
    tinggi = max(y for _, y in titik) - min(y for _, y in titik)
    rasio = max(lebar, tinggi) / min(lebar, tinggi)
    if rasio < 1 + TOLERANSI:
        return "persegi"
    assert rasio >= RASIO_BEDA_JELAS, ("segiempat ambigu: bukan persegi dan bukan jelas panjang", rasio)
    return "persegi panjang"


def klasifikasi_datar(g):
    (bentuk,) = _bentuk(g)
    if lokal(bentuk) == "circle":
        return "lingkaran"
    assert lokal(bentuk) == "polygon", lokal(bentuk)
    titik = _titik(bentuk)
    if len(titik) == 3:
        return "segitiga"
    assert len(titik) == 4
    hasil = _klasifikasi_empat_titik(titik)
    assert hasil, ("segiempat datar harus sejajar sumbu (persegi miring dilarang)", titik)
    return hasil


def klasifikasi_ruang(g):
    hitung = Counter(lokal(e) for e in _bentuk(g))
    poligon = [_titik(e) for e in _bentuk(g) if lokal(e) == "polygon"]
    if hitung["circle"] >= 2 and not hitung["ellipse"] and not poligon:
        return "bola"
    if hitung["ellipse"] >= 2:
        return "tabung"
    if hitung["ellipse"] == 1 and [len(t) for t in poligon] == [3]:
        return "kerucut"
    assert len(poligon) == 3 and all(len(t) == 4 for t in poligon) and not hitung["ellipse"], hitung
    (depan,) = [t for t in poligon if _sejajar_sumbu(t)]
    return {"persegi": "kubus", "persegi panjang": "balok"}[_klasifikasi_empat_titik(depan)]


def _bangun_gambar(svg):
    (baris,) = kelas(svg, "baris-bangun")
    return [e for e in baris if "bangun-gambar" in e.get("class", "").split()]


def jawab_visual(penyajian, svg, level):
    baris = penyajian.teks_soal.split("\n")
    assert len(baris) == 2 and baris[0] == "Perhatikan gambar.", baris
    g = _bangun_gambar(svg)
    if baris[1] == "Bangun datar apa ini?":
        (satu,) = g
        hasil = klasifikasi_datar(satu)
        assert hasil in DATAR_TES[level]
        return hasil
    if baris[1] == "Bangun ruang apa ini?":
        (satu,) = g
        hasil = klasifikasi_ruang(satu)
        assert hasil in RUANG_TES[level]
        return hasil
    cocok = re.fullmatch(r"Berapa banyak ([a-z ]+) pada gambar\?", baris[1])
    assert cocok and cocok.group(1) in DATAR_TES[level], baris
    jenis = [klasifikasi_datar(x) for x in g]
    assert set(jenis) <= set(DATAR_TES[level])
    return str(jenis.count(cocok.group(1)))


@pytest.mark.parametrize("level", LEVEL)
@pytest.mark.parametrize("varian", GAMBAR)
def test_solver_geometri_sama_dengan_kunci_seluruh_domain(level, varian):
    domain = _domain(level, varian)
    assert domain
    for p in domain:
        soal = _soal(p, level)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "siap" and penyajian.mode_representasi == "adegan_awal-v1"
        svg = periksa_xml(render_pertanyaan(penyajian, namespace="sapuan"))
        assert jawab_visual(penyajian, svg, level) == soal.kunci, p


@pytest.mark.parametrize("level", LEVEL)
def test_hitung_kontrak_satu_bangun_satu_elemen_dan_jumlah_sama_parameter(level):
    for p in _domain(level, "hitung_bentuk"):
        svg = _svg(p, namespace="hitung")
        g = _bangun_gambar(svg)
        assert len(g) == sum(p["banyak"]), p
        for bangun in g:
            (satu,) = [e for e in bangun.iter() if e is not bangun]
            assert lokal(satu) in ("polygon", "circle")
        jenis = Counter(klasifikasi_datar(b) for b in g)
        nama = katalog.DATAR_HIMPUNAN[p["himpunan"]]
        assert [jenis[n] for n in nama] == p["banyak"], p
        assert len(kelas(svg, "baris-bangun")) == 1
        assert not [e for e in kelas(svg, "baris-bangun")[0] if "bangun-gambar" not in e.get("class", "")]


def test_p1_persegi_dan_persegi_panjang_dibedakan_dari_geometri_pada_gambar_dan_hitung():
    """P1 memuat persegi panjang (kelas 1): solver geometri membedakannya dari persegi di seluruh sapuan P1."""
    terlihat = set()
    for p in _domain("P1", "datar_gambar"):
        if p["bangun"] not in ("persegi", "persegi panjang"):
            continue
        soal = _soal(p, "P1")
        penyajian = penyajian_dari_soal(soal)
        svg = periksa_xml(render_pertanyaan(penyajian, namespace="p1-segiempat"))
        assert jawab_visual(penyajian, svg, "P1") == soal.kunci == p["bangun"], p
        terlihat.add(p["bangun"])
    assert terlihat == {"persegi", "persegi panjang"}
    hitung = [p for p in _domain("P1", "hitung_bentuk") if p["banyak"][2] and p["banyak"][1]]
    assert hitung, "P1 harus punya deretan yang memuat persegi dan persegi panjang sekaligus"
    for p in hitung[::97]:
        svg = _svg(p, namespace="p1-hitung")
        jenis = Counter(klasifikasi_datar(b) for b in _bangun_gambar(svg))
        assert jenis["persegi"] == p["banyak"][1] and jenis["persegi panjang"] == p["banyak"][2], p


# ── varian benda_ruang dan tanpa flag tetap teks ─────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_benda_ruang_tetap_teks_walau_flag_menyala(level):
    for p in _domain(level, "benda_ruang"):
        soal = _soal(p, level)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "tanpa_visual" and penyajian.mode_representasi == "teks-v1"
        assert penyajian.descriptor is None and penyajian.teks_soal == soal.teks
        assert "<svg" not in render_pertanyaan(penyajian)


@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
@pytest.mark.parametrize("level", LEVEL)
def test_tanpa_flag_semua_varian_bisa_dijawab_dari_teks(monkeypatch, flag, level):
    if flag is None:
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    else:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", flag)
    for p in sumber.domain_parameter(level)[::5]:
        soal = _soal(p, level)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "tanpa_visual" and penyajian.descriptor is None
        assert penyajian.teks_soal == soal.teks
        assert solver_dari_teks(penyajian.teks_soal, level) == soal.kunci, p
        assert "<svg" not in render_pertanyaan(penyajian)


# ── teks proyeksi dan kebocoran ──────────────────────────────────────────

@pytest.mark.parametrize("level", LEVEL)
def test_teks_proyeksi_tanpa_ciri_nama_jawaban_daftar_atau_angka(level):
    for p in _domain(level, *GAMBAR):
        soal = _soal(p, level)
        teks = penyajian_dari_soal(soal).teks_soal
        pengantar, tanya = teks.split("\n")
        assert pengantar == "Perhatikan gambar."
        assert not re.search(r"\d", teks) and "," not in teks
        if p["varian"] == "hitung_bentuk":
            nama = katalog.DATAR_HIMPUNAN[p["himpunan"]][p["tanya"]]
            assert tanya == f"Berapa banyak {nama} pada gambar?"
            assert soal.teks.split("\n")[-1] == f"Berapa banyak {nama}?"
        else:
            assert tanya == soal.teks.split("\n")[-1]
            assert not any(re.search(rf"\b{n}\b", teks) for n in NAMA_BANGUN)
            assert not re.search(r"sisi|sudut|menggelinding|puncak|bulat|alas", teks)


@pytest.mark.parametrize("level", LEVEL)
def test_html_mentah_tidak_membocorkan_nama_bangun_pada_gambar_tunggal(level):
    """Kelas, id, judul, uraian, dan atribut: tidak ada nama bangun mana pun di string HTML."""
    for p in _domain(level, "datar_gambar", "ruang_gambar"):
        for gaya in ("cetak", "guru"):
            html = _html(p, gaya=gaya, namespace="bocor")
            ditemukan = [n for n in NAMA_BANGUN if re.search(rf"(?i){n}", html)]
            assert not ditemukan, (p, ditemukan)


@pytest.mark.parametrize("level", LEVEL)
def test_svg_hitung_tidak_memuat_nama_bangun_pertanyaan_boleh(level):
    for p in _domain(level, "hitung_bentuk")[::3]:
        html = _html(p, namespace="hitung")
        bagian_svg = re.search(r"<svg\b.*?</svg>", html, re.S).group(0)
        assert not [n for n in NAMA_BANGUN if re.search(rf"(?i){n}", bagian_svg)], p
        sisa = html.replace(bagian_svg, "")
        assert "Perhatikan gambar." in sisa and "pada gambar?" in sisa


@pytest.mark.parametrize("parameter", (CONTOH_DATAR, CONTOH_RUANG, CONTOH_KUBUS, CONTOH_HITUNG))
@pytest.mark.parametrize("gaya", GAYA)
def test_kelas_dan_atribut_netral_tanpa_data_atribut(parameter, gaya):
    svg = _svg(parameter, gaya=gaya)
    token = {t for e in svg.iter() for t in e.get("class", "").split()}
    assert token == KELAS_BOLEH
    assert not [a for e in svg.iter() for a in e.attrib if a.startswith("data-")]
    assert {lokal(e) for e in svg.iter()} <= TAG_BOLEH
    assert not elemen(svg, "image") and not [e for e in svg.iter() if "href" in e.attrib]
    assert not elemen(svg, "text")


@pytest.mark.parametrize("level", LEVEL)
def test_desc_dan_title_tanpa_nama_digit_atau_ciri(level):
    judul_tetap, satu, banyak = set(), set(), set()
    for p in _domain(level, *GAMBAR)[::7]:
        svg = _svg(p, namespace="aks")
        (judul,), (uraian,) = elemen(svg, "title"), elemen(svg, "desc")
        isi_judul, isi_uraian = "".join(judul.itertext()), "".join(uraian.itertext())
        assert svg.get("role") == "img"
        assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
        assert not re.search(r"\d", isi_judul + isi_uraian)
        assert not [n for n in NAMA_BANGUN if n in (isi_judul + isi_uraian).lower()]
        assert not re.search(r"sisi|sudut|menggelinding|puncak|bulat", isi_uraian)
        judul_tetap.add(isi_judul)
        (banyak if p["varian"] == "hitung_bentuk" else satu).add(isi_uraian)
    assert judul_tetap == {"Gambar bangun"}
    assert len(satu) == 1 and len(banyak) == 1  # uraian tidak bergantung pada bangun atau jumlah
    assert next(iter(satu)).startswith("Satu bangun") and next(iter(banyak)).startswith("Beberapa bangun")


@pytest.mark.parametrize("level", LEVEL)
def test_descriptor_hanya_memuat_field_allowlist(level):
    for p in _domain(level, *GAMBAR)[::11]:
        data = _penyajian(p, level).descriptor.ke_dict()["data"]
        assert set(data) == {"adegan", "tampil", "bangun"} and data["adegan"] == "bentuk"
        assert data["tampil"] == ("baris" if p["varian"] == "hitung_bentuk" else "satu")
        assert all(set(b) == {"nama", "ragam", "putar", "ukuran", "warna"} for b in data["bangun"])
        assert "kunci" not in serialisasi_penyajian(_penyajian(p, level))


# ── geometri: bentuk benar, jelas, dan tidak ambigu ──────────────────────

def _sudut_siku(titik):
    for i in range(3):
        a, b, c = titik[i], titik[(i + 1) % 3], titik[(i + 2) % 3]
        dot = (a[0] - b[0]) * (c[0] - b[0]) + (a[1] - b[1]) * (c[1] - b[1])
        if abs(dot) < 0.5:
            return True
    return False


def test_segitiga_samasisi_siku_sembarang_punya_sifat_masing_masing_di_semua_putaran():
    for ragam in katalog.RAGAM["segitiga"]:
        for putar in katalog.PUTAR["segitiga"]:
            for ukuran in katalog.UKURAN:
                data = _data([_bangun("segitiga", ragam, putar, ukuran)])
                titik = _titik(_bentuk(_bangun_gambar(_svg_data(data))[0])[0])
                sisi = sorted(_sisi(titik))
                if ragam == "samasisi":
                    assert sisi[2] - sisi[0] < 0.1, (putar, sisi)
                elif ragam == "siku":
                    assert _sudut_siku(titik) and sisi[0] / sisi[2] < 0.9
                else:
                    assert not _sudut_siku(titik)
                    assert sisi[1] / sisi[0] > 1.05 and sisi[2] / sisi[1] > 1.05, sisi
                assert len(set(titik)) == 3


def test_persegi_sama_sisi_dan_persegi_panjang_rasio_jelas_tanpa_persegi_miring():
    for putar in (0,):
        persegi = _titik(_bentuk(_bangun_gambar(_svg_data(_data([_bangun("persegi")])))[0])[0])
        assert max(_sisi(persegi)) - min(_sisi(persegi)) < 0.1 and _sejajar_sumbu(persegi)
    for ragam in ("mendatar", "tegak"):
        pp = _titik(_bentuk(_bangun_gambar(_svg_data(_data([_bangun("persegi panjang", ragam)])))[0])[0])
        lebar = max(x for x, _ in pp) - min(x for x, _ in pp)
        tinggi = max(y for _, y in pp) - min(y for _, y in pp)
        assert _sejajar_sumbu(pp)
        assert (lebar / tinggi if ragam == "mendatar" else tinggi / lebar) >= RASIO_BEDA_JELAS
    # sapuan seluruh domain: setiap persegi dan persegi panjang sejajar sumbu
    for level in LEVEL:
        for p in _domain(level, "datar_gambar"):
            if p["bangun"] in ("persegi", "persegi panjang"):
                assert _sejajar_sumbu(_titik(_bentuk(_bangun_gambar(_svg(p))[0])[0])), p


def test_lingkaran_memakai_circle_dan_bola_berbeda_dari_lingkaran():
    lingkaran = _bentuk(_bangun_gambar(_svg_data(_data([_bangun("lingkaran")])))[0])
    bola = _bentuk(_bangun_gambar(_svg_data(_data([_bangun("bola")])))[0])
    assert [lokal(e) for e in lingkaran] == ["circle"]
    assert [lokal(e) for e in bola] == ["circle"] * 3
    assert not elemen(_svg_data(_data([_bangun("bola")])), "ellipse")


def test_balok_dan_kubus_dibedakan_jelas_dan_balok_tanpa_sisi_yang_tampak_persegi():
    kubus = [_titik(e) for e in _bentuk(_bangun_gambar(_svg_data(_data([_bangun("kubus")])))[0])]
    assert len(kubus) == 3 and all(len(t) == 4 for t in kubus)
    depan_kubus, = [t for t in kubus if _sejajar_sumbu(t)]
    a, b, *_ = _sisi(depan_kubus)
    assert abs(a - b) < 0.1, "sisi depan kubus harus persegi"
    for ragam in ("mendatar", "tegak"):
        balok = [_titik(e) for e in _bentuk(_bangun_gambar(_svg_data(_data([_bangun("balok", ragam)])))[0])]
        depan, = [t for t in balok if _sejajar_sumbu(t)]
        lebar = max(x for x, _ in depan) - min(x for x, _ in depan)
        tinggi = max(y for _, y in depan) - min(y for _, y in depan)
        assert max(lebar, tinggi) / min(lebar, tinggi) >= RASIO_BEDA_JELAS
        for t in balok:  # tak satu pun sisi balok yang tampak persegi atau belah ketupat
            a, b, *_ = _sisi(t)
            assert abs(a - b) > 1.0, (ragam, t)


def test_tabung_dua_elips_dan_kerucut_satu_elips_dengan_segitiga_badan():
    tabung = Counter(lokal(e) for e in _bentuk(_bangun_gambar(_svg_data(_data([_bangun("tabung")])))[0]))
    kerucut = _bentuk(_bangun_gambar(_svg_data(_data([_bangun("kerucut")])))[0])
    assert tabung == Counter({"ellipse": 2, "polygon": 1, "line": 2})
    assert Counter(lokal(e) for e in kerucut) == Counter({"ellipse": 1, "polygon": 1, "line": 2})
    assert [len(_titik(e)) for e in kerucut if lokal(e) == "polygon"] == [3]
    for e in elemen(_svg_data(_data([_bangun("kerucut")])), "ellipse"):
        assert float(e.get("rx")) / float(e.get("ry")) >= 2  # elips alas terlihat pipih dan jelas


def test_ukuran_kecil_lebih_kecil_dari_besar_pada_semua_bangun():
    for nama in katalog.SEMUA_NAMA:
        lebar = {}
        for ukuran in katalog.UKURAN:
            g = _bangun_gambar(_svg_data(_data([_bangun(nama, ukuran=ukuran)])))[0]
            xs = [x for e in _bentuk(g) if lokal(e) in ("polygon",) for x, _ in _titik(e)]
            xs += [float(e.get("cx")) + s * float(e.get("r", e.get("rx", 0)))
                   for e in _bentuk(g) if lokal(e) in ("circle", "ellipse") for s in (-1, 1)]
            lebar[ukuran] = max(xs) - min(xs)
        assert lebar["kecil"] < lebar["besar"] * 0.9, (nama, lebar)


# ── warna dan kontras ────────────────────────────────────────────────────

def test_stroke_gelap_token_tebal_dan_fill_dari_token():
    tokens = {*T.ADEGAN_BANGUN_BIRU, *T.ADEGAN_BANGUN_KUNING, *T.ADEGAN_BANGUN_HIJAU}
    for parameter in (CONTOH_DATAR, CONTOH_RUANG, CONTOH_KUBUS, CONTOH_HITUNG):
        svg = _svg(parameter)
        for e in svg.iter():
            if lokal(e) not in BENTUK_ELEMEN:
                continue
            assert e.get("fill", "none") == "none" or e.get("fill") in tokens, e.attrib
            if lokal(e) == "line":
                assert e.get("stroke") == T.TEKS_UTAMA
            elif e.get("stroke") != "none":
                assert e.get("stroke") == T.TEKS_UTAMA
            if e.get("stroke") == T.TEKS_UTAMA:
                assert float(e.get("stroke-width")) >= 3
                assert kontras(e.get("stroke"), T.LATAR_KARTU) >= 4.5
                assert kontras(e.get("stroke"), T.LATAR_MURID) >= 4.5


def test_bentuk_datar_selalu_bertepi_gelap_jadi_warna_bukan_pembeda():
    for level in LEVEL:
        for p in _domain(level, "datar_gambar", "hitung_bentuk")[::9]:
            for e in _bentuk(_svg(p)):
                assert e.get("stroke") == T.TEKS_UTAMA and float(e.get("stroke-width")) >= 3


# ── invarian: determinisme, fingerprint, serialisasi ─────────────────────

def test_render_dua_kali_identik_byte_per_byte():
    for parameter in (CONTOH_DATAR, CONTOH_RUANG, CONTOH_KUBUS, CONTOH_HITUNG):
        penyajian = _penyajian(parameter)
        assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
        assert penyajian.fingerprint_penyajian == _penyajian(parameter).fingerprint_penyajian


def test_fingerprint_dipatok_agar_perubahan_penyajian_disengaja():
    ringkas = {
        nama: (_penyajian(p).fingerprint_matematis, _penyajian(p).fingerprint_penyajian)
        for nama, p in (("datar", CONTOH_DATAR), ("ruang", CONTOH_RUANG), ("kubus", CONTOH_KUBUS),
                        ("hitung", CONTOH_HITUNG))
    }
    assert ringkas == FINGERPRINT_DIPATOK


@pytest.mark.parametrize("parameter", (CONTOH_DATAR, CONTOH_RUANG, CONTOH_HITUNG))
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
        "import awal_kenali_bangun_awal as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for lv in ('P1', 'P2'):\n"
        "    for p in m.domain_parameter(lv)[::37]:\n"
        "        s = penyajian_dari_soal(replace(m.kenali_bangun_awal(**p), level=lv))\n"
        "        h.update((serialisasi_penyajian(s) + render_pertanyaan(s, namespace='x')).encode())\n"
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
    penyajian = _penyajian(CONTOH_HITUNG)
    try:
        hasil = render_pertanyaan(penyajian, namespace=namespace)
    except ValueError:
        return
    svg = periksa_xml(hasil)
    pembanding = _svg(CONTOH_HITUNG, namespace="pembanding")
    ids = {e.get("id") for e in svg.iter() if e.get("id")}
    assert ids and ids.isdisjoint(e.get("id") for e in pembanding.iter())
    assert not re.search(r"<script|javascript:|\son[a-z]+=",
                         hasil.replace('xmlns="http://www.w3.org/2000/svg"', ""), re.I)


@pytest.mark.parametrize("namespace", ("", None, 3))
def test_namespace_kosong_atau_bukan_teks_ditolak(namespace):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(_penyajian(CONTOH_DATAR).descriptor.data, namespace)


def test_id_unik_pada_lembar_dengan_banyak_soal_berulang():
    ids = []
    for i in range(6):
        ids += [e.get("id") for e in _svg(CONTOH_HITUNG, namespace=f"lembar-{i}").iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12


# ── validator descriptor: allow-list ketat ───────────────────────────────

def _valid(data):
    DescriptorVisual("adegan_awal", 1, data)
    return adegan_awal_svg.render_adegan_awal(data, "uji")


def test_descriptor_sah_satu_dan_baris_diterima():
    assert _valid(_data([_bangun("kubus")]))
    assert _valid(_data([_bangun("lingkaran")] * 10))
    assert _valid(_data([_bangun("segitiga")], tampil="baris"))
    assert "bentuk" in adegan_awal_data.ADEGAN_DIDUKUNG


@pytest.mark.parametrize("rusak", (
    {"adegan": "bentuk", "tampil": "satu"},
    {"adegan": "bentuk", "bangun": []},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [_bangun("kubus")], "tanya": {"varian": "nama"}},
    {"adegan": "bentuk", "tampil": "tiga", "bangun": [_bangun("kubus")]},
    {"adegan": "bentuk", "tampil": 1, "bangun": [_bangun("kubus")]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": []},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [_bangun("kubus"), _bangun("bola")]},
    {"adegan": "bentuk", "tampil": "baris", "bangun": []},
    {"adegan": "bentuk", "tampil": "baris", "bangun": [_bangun("lingkaran")] * 11},
    {"adegan": "bentuk", "tampil": "baris", "bangun": [_bangun("lingkaran"), _bangun("kubus")]},
    {"adegan": "bentuk", "tampil": "baris", "bangun": [_bangun("bola")] * 2},
    {"adegan": "bentuk", "tampil": "satu", "bangun": "kubus"},
    {"adegan": "bentuk", "tampil": "satu", "bangun": ["kubus"]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "kunci": "kubus"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "class": "kubus"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{k: v for k, v in _bangun("kubus").items() if k != "warna"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "nama": "belah ketupat"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "nama": "<kubus>"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "nama": ["kubus"]}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "nama": "Kubus"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "ragam": "mendatar"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("persegi"), "putar": 45}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("persegi"), "putar": 90}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("persegi"), "putar": False}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "putar": 0.0}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("segitiga"), "putar": 45}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("segitiga"), "putar": 90.0}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("segitiga"), "putar": True}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("segitiga"), "putar": "90"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "ukuran": "raksasa"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "warna": "#ff0000"}]},
    {"adegan": "bentuk", "tampil": "satu", "bangun": [{**_bangun("kubus"), "warna": "merah"}]},
))
def test_descriptor_rusak_ditolak_validator_dan_renderer(rusak):
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, rusak)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(rusak, "uji")


@pytest.mark.parametrize("bukan_mapping", (None, [], "bentuk", 3))
def test_data_bukan_mapping_ditolak(bukan_mapping):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(bukan_mapping, "uji")


# ── proyektor: field persis dan bentuk teks sumber ───────────────────────

def test_field_parameter_tambahan_atau_hilang_ditolak_proyektor():
    for dasar in (CONTOH_DATAR, CONTOH_HITUNG):
        soal = _soal(dasar)
        for rusak in (
            {**soal.parameter, "kunci": "x"},
            {**soal.parameter, "versi_katalog": 2},
            {k: v for k, v in soal.parameter.items() if k not in ("varian",)},
            {k: v for k, v in soal.parameter.items() if k != "himpunan"},
            {**soal.parameter, "varian": "lain"},
            {**soal.parameter, "himpunan": "luas"},
            {**soal.parameter, "benda": 0},
        ):
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, rusak)
    datar = _soal(CONTOH_DATAR).parameter
    for rusak in ({**datar, "putar": 45}, {**datar, "warna": "merah"}, {**datar, "bangun": "kubus"},
                  {k: v for k, v in datar.items() if k != "ragam"}):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)
    hitung = _soal(CONTOH_HITUNG).parameter
    for rusak in ({**hitung, "banyak": [2, 2, 1, 4]}, {**hitung, "banyak": [2, 3, 1]},
                  {**hitung, "tanya": 9}, {**hitung, "tata": 5}, {**hitung, "banyak": [9, 0, 0, 0]}):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)


def test_benda_ruang_diproyeksikan_none_tetapi_parameter_tetap_divalidasi():
    soal = _soal(dict(varian="benda_ruang", himpunan="dasar", bangun="bola", benda=1))
    assert proyeksi_matematika_awal(TID, soal.parameter) is None
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(TID, {**soal.parameter, "benda": 7})
    with pytest.raises(ValueError):
        proyeksi_matematika_awal(TID, {**soal.parameter, "bangun": "kerucut"})


def test_proyeksi_gagal_keras_bila_bentuk_teks_sumber_berubah(monkeypatch):
    asli = sumber.kenali_bangun_awal
    for dasar in (CONTOH_DATAR, CONTOH_RUANG, CONTOH_HITUNG):
        soal = _soal(dasar)
        for ubah in (
            lambda teks: teks.replace("\n", " "),
            lambda teks: teks + "\nCatatan.",
            lambda teks: teks.rsplit("\n", 1)[0] + "\nBangun apa ini?",
            lambda teks: teks.replace("Berapa banyak", "Hitung berapa banyak") if "Berapa" in teks
            else teks.replace("apa ini?", "apa itu?"),
        ):
            def palsu(varian, himpunan, **isi):
                hasil = asli(varian, himpunan, **isi)
                return replace(hasil, teks=ubah(hasil.teks))
            monkeypatch.setattr(sumber, "kenali_bangun_awal", palsu)
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, soal.parameter)
        monkeypatch.setattr(sumber, "kenali_bangun_awal", asli)


def test_proyeksi_jenis_lain_tetap_none_dan_jenis_lama_tidak_berubah():
    assert proyeksi_matematika_awal("kenali_bentuk", {"apa": "saja"}) is None
    assert proyeksi_matematika_awal("tidak_dikenal", {}) is None


# ── batas viewBox dan tanpa tumpang tindih ───────────────────────────────

def _kotak_bangun(g):
    xs, ys = [], []
    for e in _bentuk(g):
        if lokal(e) in ("polygon", "polyline"):
            xs += [x for x, _ in _titik(e)]
            ys += [y for _, y in _titik(e)]
        elif lokal(e) == "line":
            xs += [float(e.get("x1")), float(e.get("x2"))]
            ys += [float(e.get("y1")), float(e.get("y2"))]
        else:
            cx, cy = float(e.get("cx")), float(e.get("cy"))
            rx, ry = float(e.get("rx", e.get("r", 0))), float(e.get("ry", e.get("r", 0)))
            xs += [cx - rx, cx + rx]
            ys += [cy - ry, cy + ry]
    return min(xs), min(ys), max(xs), max(ys)


@pytest.mark.parametrize("level", LEVEL)
def test_semua_soal_sah_dalam_viewbox_dan_bangun_tidak_saling_menimpa(level):
    for p in _domain(level, *GAMBAR):
        svg = _svg(p, namespace="batas")
        periksa_batas_koordinat(svg)
        lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
        assert lebar == T.ADEGAN_LEBAR
        kotak = [_kotak_bangun(g) for g in _bangun_gambar(svg)]
        for x1, y1, x2, y2 in kotak:
            assert 0 <= x1 and x2 <= lebar and 0 <= y1 and y2 <= tinggi, (p, (x1, y1, x2, y2))
        for i, a in enumerate(kotak):
            for b in kotak[i + 1:]:
                assert a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1], (p, a, b)


def test_sepuluh_bangun_ukuran_terbesar_muat_dua_baris_lima_dan_terpusat():
    data = _data([_bangun("persegi panjang", "mendatar")] * 5 + [_bangun("lingkaran")] * 5)
    svg = _svg_data(data, "sepuluh")
    periksa_batas_koordinat(svg)
    kotak = [_kotak_bangun(g) for g in _bangun_gambar(svg)]
    assert len(kotak) == 10
    assert len({round(k[1]) for k in kotak[:5]}) == 1 and kotak[5][1] > kotak[0][3]
    kiri, kanan = min(k[0] for k in kotak[:5]), max(k[2] for k in kotak[:5])
    assert abs(kiri - (T.ADEGAN_LEBAR - kanan)) < 1
    tiga = _svg_data(_data([_bangun("lingkaran")] * 3), "tiga")
    k3 = [_kotak_bangun(g) for g in _bangun_gambar(tiga)]
    assert abs(min(k[0] for k in k3) - (T.ADEGAN_LEBAR - max(k[2] for k in k3))) < 1


def test_bangun_tunggal_terpusat_dan_urutan_kiri_ke_kanan_pada_baris():
    kotak = _kotak_bangun(_bangun_gambar(_svg(CONTOH_RUANG))[0])
    assert abs((kotak[0] + kotak[2]) / 2 - T.ADEGAN_LEBAR / 2) < 1
    svg = _svg(CONTOH_HITUNG)
    xs = [(_kotak_bangun(g)[0] + _kotak_bangun(g)[2]) / 2 for g in _bangun_gambar(svg)[:5]]
    assert xs == sorted(xs)


# ── ringkasan non-HTML ───────────────────────────────────────────────────

def test_ringkasan_bangun_tunggal_lewat_ciri_tanpa_nama_jawaban_dan_baris_lewat_urutan():
    for parameter in (CONTOH_DATAR, CONTOH_RUANG, CONTOH_KUBUS):
        ringkasan = ringkasan_pertanyaan(_penyajian(parameter))
        assert "Fakta visual: satu bangun " in ringkasan
        assert not re.search(rf"\b{parameter['bangun']}\b", ringkasan), ringkasan
        assert "dengan ciri: punya" in ringkasan
    assert "dengan ciri: punya 4 sisi lurus; sisi yang berhadapan" in ringkasan_pertanyaan(
        _penyajian(CONTOH_DATAR))
    baris = ringkasan_pertanyaan(_penyajian(CONTOH_HITUNG))
    assert "Fakta visual: satu baris bangun datar dari kiri ke kanan: " in baris
    nama = katalog.DATAR_HIMPUNAN["lengkap"]
    urutan = sumber.nama_berurutan("lengkap", [2, 3, 1, 4], 1)
    assert all(n in baris for n in set(urutan)) and len(urutan) == 10 and set(urutan) <= set(nama)


# ── inventaris ───────────────────────────────────────────────────────────

def test_inventaris_menandai_kenali_bangun_awal_wajib_visual_dengan_benda_ruang_sengaja_teks():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {d["varian"] for d in baris} == {f"varian={v}" for v in sumber.VARIAN}
    assert {d["level"] for d in baris} == {"P1", "P2"}
    assert VARIAN_SENGAJA_TEKS == {TID: ("varian=benda_ruang",)}
    assert "benda_ruang" in baris[0]["bukti_klasifikasi"]["observasi"]
