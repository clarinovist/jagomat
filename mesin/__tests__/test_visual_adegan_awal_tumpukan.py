"""Keluarga visual `matematika-awal`: tampak_kubus_awal bergambar (adegan_awal v1, `tumpukan_kubus`).

Solver mandiri HANYA membaca teks proyeksi dan SVG hasil `render_pertanyaan` lewat `penyajian_dari_soal`.
Cara solver memetakan `kolom-kubus` ke sel (tanpa atribut, kelas, atau id yang menyebut sel atau jawaban):
  1. (Lihat `tumpukan_svg_helpers`.) Dari kubus pertama gambar diukur tiga vektor proyeksi: `ex` (rusuk datar muka kiri, arah satu petak ke
     KANAN), `ey` (rusuk datar muka kanan, arah satu petak ke BELAKANG), `ez` (rusuk tegak). Semua kubus di
     seluruh gambar wajib memakai vektor yang sama (ukuran kubus konstan).
  2. Tiap `kolom-kubus` berisi tumpukan kubus; kubus diurut dari yang terendah di layar. Titik dasar kubus
     terbawah (sudut bawah terdekat muka kiri) menjadi jangkar kolom. Kubus ke-k wajib berjarak tepat
     k * ez di atas jangkar (tak ada kubus melayang atau bergeser); banyak kubus = tinggi tumpukan.
  3. Selisih jangkar tiap kolom terhadap kolom pertama dipecahkan sebagai dx * ex + dy * ey (sistem 2 x 2);
     dx dan dy wajib bilangan bulat dan sel tidak boleh kembar. Hanya selisih relatif yang dipakai: baris
     atau kolom kosong tidak mengubah hitungan tampak.
  4. Dari sel dan tinggi dihitung jawaban: banyak kubus, banyak sel (atas), jumlah tinggi tertinggi per
     kelompok dx (depan), jumlah tinggi tertinggi per kelompok dy (samping).
Hasilnya dibandingkan dengan `soal.kunci` untuk SELURUH domain P6 (sapuan penuh, tanpa stride). Kebocoran
diuji pada string HTML mentah: SVG tanpa elemen `kolom-kubus` harus identik byte per byte untuk semua soal
beralas sama (fakta gambar), jadi kelas, id, judul, uraian, transform, dan atribut tidak memuat tinggi,
banyak kubus, atau jawaban. Pembaca gambar ada di `tumpukan_svg_helpers`; keterbacaan anak dan geometri
(batas, ukuran, label, urutan lukis, puncak tidak tertimpa) di `test_visual_adegan_awal_tumpukan_geometri`.
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

import adegan_awal_data
import adegan_awal_svg
import adegan_awal_tumpukan_data
import awal_tampak_kubus_awal as sumber
from question_views import penyajian_dari_soal
from tampak_solver_helpers import (PENGANTAR_VISUAL, TANYA_ATAS, TANYA_DEPAN, TANYA_KUBUS, TANYA_SAMPING,
                                   jawab_dari_sel, solver_dari_teks)
from topic_matematika_awal_visual import proyeksi_matematika_awal
from tumpukan_svg_helpers import baca_gambar, data_adegan, lajur_dari, muka_path, svg_dari_data, titik_path
from visual_contract import DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian
from visual_inventory import DENOMINATOR_KANONIS, VARIAN_SENGAJA_TEKS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, lokal, periksa_xml

TID = sumber.TEMPLATE_ID
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
KELAS_BOLEH = {"tumpukan-gambar", "lantai-petak", "garis-lantai", "kolom-kubus", "kubus-satuan",
               "muka-atas", "muka-kiri", "muka-kanan", "arah-gambar"}
TAG_BOLEH = {"svg", "title", "desc", "g", "path", "text"}
CONTOH_KUBUS_3X3 = dict(varian="banyak_kubus", baris=3, kolom=3, tinggi=[0, 0, 0, 1, 1, 0, 3, 2, 1])
CONTOH_ATAS_2X3 = dict(varian="banyak_persegi_atas", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
CONTOH_DEPAN_3X3 = dict(varian="banyak_persegi_depan", baris=3, kolom=3, tinggi=[1, 0, 0, 2, 2, 1, 3, 3, 2])
CONTOH_SAMPING_2X3 = dict(varian="banyak_persegi_samping", baris=2, kolom=3, tinggi=[1, 1, 0, 3, 2, 2])
CONTOH_KUBUS_2X2 = dict(varian="banyak_kubus", baris=2, kolom=2, tinggi=[1, 0, 3, 2])
CONTOH_DEPAN_3X2 = dict(varian="banyak_persegi_depan", baris=3, kolom=2, tinggi=[0, 0, 1, 0, 3, 2])
CONTOH = (CONTOH_KUBUS_3X3, CONTOH_ATAS_2X3, CONTOH_DEPAN_3X3, CONTOH_SAMPING_2X3, CONTOH_KUBUS_2X2,
          CONTOH_DEPAN_3X2)
NAMA_CONTOH = ("kubus_3x3", "atas_2x3", "depan_3x3", "samping_2x3", "kubus_2x2", "depan_3x2")
KOLOM_KUBUS = re.compile(r'<g class="kolom-kubus">(?:<g class="kubus-satuan">.*?</g>)+</g>')

FINGERPRINT_DIPATOK = {
    "kubus_3x3": ("5523381a2c4611f27acd8f98d319ef8f77a5a1d57774f9d868ca2cb4819ae6e8",
                "950cfbf18dd9971c29cf296eb0770c796e406f3c141f729e0b7188b774143e0f"),
    "atas_2x3": ("63239074c3ba2f602bfbcc9faa1c29348f13460bdd3ea65a5a8428090c281b01",
               "142e01bd33e332064135ad2ceb569587bf2bc2aa6ebed479afc391bd8c4c4b00"),
    "depan_3x3": ("e2dd523394ac637ebc153116c12a6452665ee8bd6c582bb1136e74ea543e2906",
                "7a0893bc7427a75ea61874baa016a10c05186c5e3929e1698457f6bf1a541fe2"),
    "samping_2x3": ("cebb9f4d971d60b9016e72e4eb9aa6be833c7b97c5c17e91b0b57bfe80e74e06",
                  "aa0c6630fce84a7be72b27c83e62b3d0559095b64849b5df9685456771fa2131"),
    "kubus_2x2": ("d1656f32256726f7f17a9faca34e8b2261eb0211b3a839e5f3fcb645776868e8",
                "ba05fc8a0020ae524736784134d051612d4fdc2437e9280a0daceb88fad5c1a8"),
    "depan_3x2": ("00f842b42ea92053319dbd6f4804579856d6c6eae73a5be119f73f396870dffc",
                "e26978b1af1dfe7510e1bb4d99b8e4dfef4a3d9b6deae878c06183b4c2f7b9c1"),
}


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


def _domain(*varian):
    return tuple(p for p in sumber.domain_parameter("P6") if p["varian"] in varian)


def _susunan_unik():
    """Satu parameter per susunan (gambar hanya bergantung pada alas dan tinggi, bukan varian)."""
    terlihat = {}
    for p in sumber.domain_parameter("P6"):
        terlihat.setdefault((p["baris"], p["kolom"], tuple(p["tinggi"])), p)
    return list(terlihat.values())


def _raw_param(parameter, namespace="uji"):
    _, descriptor = proyeksi_matematika_awal(TID, parameter)
    return adegan_awal_svg.render_adegan_awal(descriptor.data, namespace)


def _svg_param(parameter, namespace="uji"):
    return periksa_xml("<div>" + _raw_param(parameter, namespace) + "</div>")


def jawab_visual(penyajian, svg):
    baris = penyajian.teks_soal.split("\n")
    assert len(baris) == 2 and baris[0] == PENGANTAR_VISUAL, baris
    return jawab_dari_sel(baris[1], baca_gambar(svg))


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


def test_solver_membaca_tinggi_dan_sel_sama_dengan_parameter_untuk_seluruh_susunan():
    for p in _susunan_unik():
        sel = baca_gambar(_svg_param(p, "peta"))
        banyak_kolom = p["kolom"]
        asli = {(x, y): h for y in range(p["baris"]) for x in range(banyak_kolom)
                if (h := p["tinggi"][y * banyak_kolom + x])}
        # gambar memberi (kolom, baris) relatif ke kolom pertama yang digambar (baris belakang dulu)
        awal = next((x, y) for y in range(p["baris"] - 1, -1, -1) for x in range(banyak_kolom) if (x, y) in asli)
        harapan = {(x - awal[0], y - awal[1]): h for (x, y), h in asli.items()}
        assert sel == harapan, p


def _geser_jalur(jalur, dx, dy):
    titik = titik_path(jalur.get("d"))
    jalur.set("d", "M" + "L".join(f"{x + dx:g} {y + dy:g}" for x, y in titik) + "Z")


def test_solver_geometri_menolak_gambar_yang_ambigu_atau_rusak():
    """Mutasi gambar: elemen asing, kubus melayang atau bergeser, dua kolom di sel yang sama."""
    dasar = data_adegan((1, 0, 3, 2), 2)
    assert baca_gambar(svg_dari_data(dasar)) == {(0, 0): 3, (1, 0): 2, (0, -1): 1}
    svg = svg_dari_data(dasar)
    kolom = kelas(svg, "kolom-kubus")
    kolom[0].append(kolom[0][0].makeelement("g", {"class": "lain"}))
    with pytest.raises(AssertionError):
        baca_gambar(svg)
    svg = svg_dari_data(dasar)
    for jalur in kelas(svg, "kolom-kubus")[0][1]:
        _geser_jalur(jalur, 0, -7)
    with pytest.raises(AssertionError, match="melayang"):
        baca_gambar(svg)
    svg = svg_dari_data(dasar)
    for jalur in elemen(kelas(svg, "kolom-kubus")[1], "path"):
        _geser_jalur(jalur, 9, 0)
    with pytest.raises(AssertionError):
        baca_gambar(svg)
    svg = svg_dari_data(dasar)
    kolom = kelas(svg, "kolom-kubus")
    kolom[1].clear()
    kolom[1].set("class", "kolom-kubus")
    for kubus in kolom[0]:
        kolom[1].append(kubus)
    with pytest.raises(AssertionError, match="sel yang sama"):
        baca_gambar(svg)


# ── kontrak hitung per kelas elemen ──────────────────────────────────────

def test_kontrak_kolom_kubus_dan_kubus_satuan_untuk_seluruh_domain():
    for p in _susunan_unik():
        svg = _svg_param(p, "kontrak")
        kolom = kelas(svg, "kolom-kubus")
        terisi = [h for h in p["tinggi"] if h]
        assert len(kolom) == len(terisi), p
        assert len(kelas(svg, "kubus-satuan")) == sum(p["tinggi"]), p
        assert sorted(len(list(k)) for k in kolom) == sorted(terisi), p
        for k in kolom:
            assert all(lokal(a) == "g" and a.get("class") == "kubus-satuan" for a in k)
        for kubus in kelas(svg, "kubus-satuan"):
            assert [e.get("class") for e in kubus] == ["muka-atas", "muka-kiri", "muka-kanan"]
        assert len(kelas(svg, "muka-atas")) == len(kelas(svg, "muka-kiri")) == len(kelas(svg, "muka-kanan")) \
            == sum(p["tinggi"])


def test_semua_kubus_termasuk_yang_tertutup_digambar():
    for parameter in CONTOH:
        svg = _svg(parameter)
        assert len(kelas(svg, "kubus-satuan")) == sum(parameter["tinggi"])
    # tumpukan tinggi 3 di belakang-kiri: kubus bawahnya tertutup, tetap digambar lengkap
    svg = _svg(CONTOH_KUBUS_2X2)
    assert sorted(len(list(k)) for k in kelas(svg, "kolom-kubus")) == [1, 2, 3]


def test_kolom_digambar_dari_baris_belakang_ke_depan_dan_kiri_ke_kanan_lalu_bawah_ke_atas():
    svg = _svg(CONTOH_DEPAN_3X3)
    urutan = [(b, k) for b in range(2, -1, -1) for k in range(3) if CONTOH_DEPAN_3X3["tinggi"][b * 3 + k]]
    tinggi = [len(list(e)) for e in kelas(svg, "kolom-kubus")]
    assert tinggi == [CONTOH_DEPAN_3X3["tinggi"][b * 3 + k] for b, k in urutan]
    for kolom in kelas(svg, "kolom-kubus"):
        dasar = [muka_path(k, "muka-kiri")[2][1] for k in kolom]
        assert dasar == sorted(dasar, reverse=True), "kubus digambar dari lapis bawah ke atas"


# ── varian: tanpa flag tetap teks yang bisa dijawab ──────────────────────

@pytest.mark.parametrize("flag", (None, "", "statistika", "pola-bilangan"))
def test_tanpa_flag_semua_varian_bisa_dijawab_dari_teks(monkeypatch, flag):
    if flag is None:
        monkeypatch.delenv("OSN_VISUAL_KELUARGA")
    else:
        monkeypatch.setenv("OSN_VISUAL_KELUARGA", flag)
    for p in sumber.domain_parameter("P6"):
        soal = _soal(p)
        penyajian = penyajian_dari_soal(soal)
        assert penyajian.status_visual == "tanpa_visual" and penyajian.descriptor is None
        assert penyajian.teks_soal == soal.teks
        assert solver_dari_teks(penyajian.teks_soal) == soal.kunci, p
        assert "<svg" not in render_pertanyaan(penyajian)


# ── teks proyeksi dan kebocoran ──────────────────────────────────────────

def test_teks_proyeksi_tanpa_angka_tanpa_tinggi_dan_tanpa_kunci_di_seluruh_domain():
    for p in sumber.domain_parameter("P6"):
        soal = _soal(p)
        teks = penyajian_dari_soal(soal).teks_soal
        pengantar, tanya = teks.split("\n")
        assert pengantar == PENGANTAR_VISUAL
        assert not re.search(r"\d", teks), teks
        assert not re.search(r"baris depan|baris belakang|baris tengah|kosong|kolom", teks, re.I), teks
        assert soal.teks.split("\n")[-1] == tanya


def test_pengantar_dan_pertanyaan_per_varian():
    assert _penyajian(CONTOH_KUBUS_3X3).teks_soal == f"{PENGANTAR_VISUAL}\n{TANYA_KUBUS}"
    assert _penyajian(CONTOH_ATAS_2X3).teks_soal == f"{PENGANTAR_VISUAL}\n{TANYA_ATAS}"
    assert _penyajian(CONTOH_DEPAN_3X3).teks_soal == f"{PENGANTAR_VISUAL}\n{TANYA_DEPAN}"
    assert _penyajian(CONTOH_SAMPING_2X3).teks_soal == f"{PENGANTAR_VISUAL}\n{TANYA_SAMPING}"


def test_svg_tanpa_kolom_kubus_identik_untuk_soal_beralas_sama_dan_beda_antar_alas():
    """Selain kolom-kubus: lantai, label, judul, uraian hanya bergantung pada banyak baris dan kolom."""
    sisa = {}
    for p in sumber.domain_parameter("P6"):
        mentah = _raw_param(p)
        assert KOLOM_KUBUS.search(mentah)
        sisa.setdefault((p["baris"], p["kolom"]), set()).add(KOLOM_KUBUS.sub("", mentah))
    assert set(sisa) == {(2, 2), (2, 3), (3, 2), (3, 3)}
    assert all(len(v) == 1 for v in sisa.values())
    assert len({next(iter(v)) for v in sisa.values()}) == 4


def test_html_tanpa_kolom_kubus_identik_untuk_semua_gaya_dan_varian():
    for gaya in GAYA:
        bentuk = {}
        for p in sumber.domain_parameter("P6")[::53]:
            html = _html(p, gaya=gaya, namespace="bocor")
            svg = re.search(r"<svg\b.*?</svg>", html, re.S).group(0)
            bentuk.setdefault((p["baris"], p["kolom"]), set()).add(KOLOM_KUBUS.sub("", svg))
        assert all(len(v) == 1 for v in bentuk.values()), gaya


def test_tanpa_transform_tanpa_data_atribut_tanpa_minus_nol_dan_kelas_netral():
    for parameter in CONTOH:
        for gaya in GAYA:
            html = _html(parameter, gaya=gaya)
            svg = periksa_xml(html)
            token = {t for e in svg.iter() for t in e.get("class", "").split()}
            assert token <= KELAS_BOLEH and {"kolom-kubus", "kubus-satuan", "arah-gambar"} <= token
            assert not [a for e in svg.iter() for a in e.attrib if a.startswith("data-")]
            assert not [e for e in svg.iter() if "transform" in e.attrib]
            assert {lokal(e) for e in svg.iter()} <= TAG_BOLEH
            assert not elemen(svg, "image") and not [e for e in svg.iter() if "href" in e.attrib]
            gambar = re.search(r"<svg\b.*?</svg>", html, re.S).group(0)
            assert not re.search(r"(?<![\d.])-0(?![\d.])", gambar)
            assert not re.search(r'[0-9]e[-+]?[0-9]', re.sub(r"#[0-9a-fA-F]+", "", gambar.split("</desc>")[1]))
            assert "rotate" not in html


def test_atribut_kelas_dan_id_tidak_menyebut_tinggi_banyak_kubus_atau_jawaban():
    for p in sumber.domain_parameter("P6")[::31]:
        svg = _svg(p, namespace="kls")
        for e in svg.iter():
            for nilai in e.attrib.values():
                assert not re.search(r"kubus\s*\d|tinggi|jawab|kunci|depan\d|atas\d|samping\d", nilai, re.I)
            if lokal(e) not in ("svg", "title", "desc"):
                assert "id" not in e.attrib
        kelas_semua = {t for e in svg.iter() for t in e.get("class", "").split()}
        assert kelas_semua <= KELAS_BOLEH


def test_desc_dan_title_tetap_tanpa_angka_tinggi_banyak_kubus_atau_jawaban():
    judul_tetap, uraian_tetap = set(), set()
    for p in sumber.domain_parameter("P6")[::37]:
        svg = _svg(p, namespace="aks")
        (judul,), (uraian,) = elemen(svg, "title"), elemen(svg, "desc")
        isi_judul, isi_uraian = "".join(judul.itertext()), "".join(uraian.itertext())
        assert svg.get("role") == "img"
        assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
        assert not re.search(r"\d", isi_judul + isi_uraian)
        assert not re.search(r"tertutup|tersembunyi|tumpuk|tinggi|banyak|jumlah|tampak", isi_judul + isi_uraian, re.I)
        judul_tetap.add(isi_judul)
        uraian_tetap.add(isi_uraian)
    assert judul_tetap == {"Gambar susunan kubus satuan"}
    assert uraian_tetap == {"Susunan kubus satuan di atas lantai berpetak, dilihat dari depan sedikit dari "
                            "kanan dan atas. Sisi depan dan sisi kanan diberi tanda."}


def test_descriptor_hanya_memuat_field_allowlist_tanpa_kunci():
    for p in sumber.domain_parameter("P6")[::23]:
        penyajian = _penyajian(p)
        data = penyajian.descriptor.ke_dict()["data"]
        assert set(data) == {"adegan", "tinggi"} and data["adegan"] == "tumpukan_kubus"
        assert data["tinggi"] == lajur_dari(p["tinggi"], p["kolom"])
        assert "kunci" not in serialisasi_penyajian(penyajian)


def test_descriptor_berurutan_baris_depan_dulu_dan_kolom_kiri_dulu():
    _, descriptor = proyeksi_matematika_awal(TID, CONTOH_DEPAN_3X3)
    assert [list(b) for b in descriptor.data["tinggi"]] == [[1, 0, 0], [2, 2, 1], [3, 3, 2]]
    _, descriptor = proyeksi_matematika_awal(TID, CONTOH_DEPAN_3X2)
    assert [list(b) for b in descriptor.data["tinggi"]] == [[0, 0], [1, 0], [3, 2]]


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
        "import awal_tampak_kubus_awal as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P6')[::97]:\n"
        "    s = penyajian_dari_soal(replace(m.tampak_kubus_awal(**p), level='P6'))\n"
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
    penyajian = _penyajian(CONTOH_DEPAN_3X3)
    try:
        hasil = render_pertanyaan(penyajian, namespace=namespace)
    except ValueError:
        return
    svg = periksa_xml(hasil)
    pembanding = _svg(CONTOH_DEPAN_3X3, namespace="pembanding")
    ids = {e.get("id") for e in svg.iter() if e.get("id")}
    assert ids and ids.isdisjoint(e.get("id") for e in pembanding.iter())
    assert not re.search(r"<script|javascript:|\son[a-z]+=",
                         hasil.replace('xmlns="http://www.w3.org/2000/svg"', ""), re.I)


@pytest.mark.parametrize("namespace", ("", None, 3))
def test_namespace_kosong_atau_bukan_teks_ditolak(namespace):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(_penyajian(CONTOH_KUBUS_2X2).descriptor.data, namespace)


def test_id_unik_pada_lembar_dengan_banyak_soal_berulang():
    ids = []
    for i in range(6):
        ids += [e.get("id") for e in _svg(CONTOH_ATAS_2X3, namespace=f"lembar-{i}").iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12


# ── validator descriptor: allow-list ketat ───────────────────────────────

def _valid(data):
    DescriptorVisual("adegan_awal", 1, data)
    return adegan_awal_svg.render_adegan_awal(data, "uji")


def test_descriptor_sah_semua_alas_tinggi_dan_komposisi_diterima():
    for baris in (1, 2, 3):
        for kolom in (1, 2, 3):
            assert _valid({"adegan": "tumpukan_kubus", "tinggi": [[1] * kolom for _ in range(baris)]})
    for tinggi in range(4):
        assert _valid({"adegan": "tumpukan_kubus", "tinggi": [[tinggi or 1, tinggi]]})
    assert _valid({"adegan": "tumpukan_kubus", "tinggi": ((0, 1), (3, 2))})  # tuple (bentuk beku) diterima
    assert "tumpukan_kubus" in adegan_awal_data.ADEGAN_DIDUKUNG
    beku = DescriptorVisual("adegan_awal", 1, {"adegan": "tumpukan_kubus", "tinggi": [[0, 1], [3, 2]]})
    assert adegan_awal_svg.render_adegan_awal(beku.data, "uji")


@pytest.mark.parametrize("rusak", (
    {"adegan": "tumpukan_kubus"},
    {"tinggi": [[1, 0], [3, 2]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0], [3, 2]], "kunci": "6"},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0], [3, 2]], "class": "tujuh"},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0], [3, 2]], "tampil": "satu"},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0], [3, 2]], "banyak": 6},
    {"adegan": "tumpukan_kubus", "tinggi": []},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0], [3, 2], [1, 1], [0, 1]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0, 0, 1], [3, 2, 1, 1]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0], [3]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[0, 0], [0, 0]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 4], [3, 2]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, -1], [3, 2]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0.0], [3, 2]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, True], [3, 2]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, "2"], [3, 2]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, None], [3, 2]]},
    {"adegan": "tumpukan_kubus", "tinggi": [[1, 0], "32"]},
    {"adegan": "tumpukan_kubus", "tinggi": [1, 0, 3, 2]},
    {"adegan": "tumpukan_kubus", "tinggi": "1032"},
    {"adegan": "tumpukan_kubus", "tinggi": None},
    {"adegan": "tumpukan_kubus", "tinggi": 4},
    {"adegan": "tumpukan_kubus", "tinggi": {"a": [1]}},
    {"adegan": "tumpukan", "tinggi": [[1, 0], [3, 2]]},
    {"adegan": "kubus", "tinggi": [[1, 0], [3, 2]]},
    {1: "tumpukan_kubus", "tinggi": [[1, 0], [3, 2]]},
))
def test_descriptor_rusak_ditolak_validator_dan_renderer(rusak):
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, rusak)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(rusak, "uji")


@pytest.mark.parametrize("bukan_mapping", (None, [], "tumpukan_kubus", 3))
def test_data_bukan_mapping_ditolak(bukan_mapping):
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(bukan_mapping, "uji")


def test_batas_validator_alas_dan_tinggi_tepat_diterima():
    adegan_awal_tumpukan_data.validasi_tumpukan({"adegan": "tumpukan_kubus", "tinggi": [[3] * 3] * 3})
    adegan_awal_tumpukan_data.validasi_tumpukan({"adegan": "tumpukan_kubus", "tinggi": [[1]]})
    with pytest.raises(ValueError):
        adegan_awal_tumpukan_data.validasi_tumpukan({"adegan": "tumpukan_kubus", "tinggi": [[3] * 4]})


# ── proyektor: field persis dan bentuk teks sumber ───────────────────────

def test_field_parameter_tambahan_atau_hilang_ditolak_proyektor():
    for dasar in CONTOH:
        soal = _soal(dasar)
        for rusak in (
            {**soal.parameter, "kunci": "x"},
            {**soal.parameter, "menit": 30},
            {k: v for k, v in soal.parameter.items() if k != "varian"},
            {k: v for k, v in soal.parameter.items() if k != "tinggi"},
            {k: v for k, v in soal.parameter.items() if k != "baris"},
            {**soal.parameter, "varian": "lain"},
            {**soal.parameter, "baris": True},
            {**soal.parameter, "tinggi": tuple(soal.parameter["tinggi"])},
        ):
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, rusak)
    for rusak in (dict(varian="banyak_kubus", baris=1, kolom=3, tinggi=[3, 2, 1]),
                  dict(varian="banyak_kubus", baris=2, kolom=2, tinggi=[2, 2, 2, 2]),
                  dict(varian="banyak_persegi_atas", baris=2, kolom=3, tinggi=[1, 1, 0, 2, 2, 0]),
                  dict(varian="banyak_kubus", baris=2, kolom=2, tinggi=[1, 2, 3, 0])):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)


def test_proyeksi_gagal_keras_bila_bentuk_teks_sumber_berubah(monkeypatch):
    asli = sumber.tampak_kubus_awal
    for dasar in CONTOH:
        soal = _soal(dasar)
        for ubah in (
            lambda teks: teks.replace("\n", " "),
            lambda teks: teks + "\nCatatan.",
            lambda teks: teks.rsplit("\n", 1)[0] + "\nBerapa kubusnya?",
            lambda teks: teks.replace("Tulis", "Tuliskan"),
        ):
            def palsu(varian, **isi):
                hasil = asli(varian, **isi)
                return replace(hasil, teks=ubah(hasil.teks))
            monkeypatch.setattr(sumber, "tampak_kubus_awal", palsu)
            with pytest.raises(ValueError):
                proyeksi_matematika_awal(TID, soal.parameter)
        monkeypatch.setattr(sumber, "tampak_kubus_awal", asli)


def test_proyektor_menolak_field_tambahan_sendiri_walau_soal_sumber_mengabaikannya(monkeypatch):
    """Pemeriksaan field persis dimiliki proyektor; tidak bergantung pada validasi soal sumber."""
    asli = sumber.tampak_kubus_awal
    monkeypatch.setattr(sumber, "tampak_kubus_awal",
                        lambda varian, **isi: asli(varian, **{k: v for k, v in isi.items() if k != "kunci"}))
    soal = _soal(CONTOH_KUBUS_3X3)
    with pytest.raises(ValueError, match="field parameter"):
        proyeksi_matematika_awal(TID, {**soal.parameter, "kunci": "8"})


def test_proyeksi_jenis_lain_tetap_none_dan_jenis_geometri_ruang_tidak_berubah():
    assert proyeksi_matematika_awal("waktu_berat_awal", {"apa": "saja"}) is None
    assert proyeksi_matematika_awal("peluang_dasar", {"apa": "saja"}) is None
    assert proyeksi_matematika_awal("keliling_gabungan", {"apa": "saja"}) is None


# ── ringkasan non-HTML ───────────────────────────────────────────────────

def test_ringkasan_tanpa_angka_sama_untuk_semua_soal():
    ringkasan = {ringkasan_pertanyaan(_penyajian(p)).split("\n")[-1]
                 for p in sumber.domain_parameter("P6")[::71]}
    assert len(ringkasan) == 1
    isi = next(iter(ringkasan))
    assert "Fakta visual: gambar susunan kubus satuan di atas lantai berpetak" in isi
    assert not re.search(r"\d|tinggi|tertutup|jawab", isi, re.I)


# ── inventaris ───────────────────────────────────────────────────────────

def test_inventaris_menandai_tampak_kubus_awal_wajib_visual_semua_varian_bergambar():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {d["varian"] for d in baris} == {f"varian={v}" for v in sumber.VARIAN}
    assert {d["level"] for d in baris} == {"P6"}
    assert TID not in VARIAN_SENGAJA_TEKS, "keempat varian memakai gambar susunan kubus"
    assert {d["bukti_klasifikasi"]["keluarga"] for d in baris} == {"kubus_satuan"}
    assert "tidak ada yang sengaja teks" in baris[0]["bukti_klasifikasi"]["observasi"]
