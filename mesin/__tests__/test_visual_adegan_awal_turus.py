"""Keluarga visual `matematika-awal`: turus_gambar_awal bergambar (adegan_awal v1, `turus`).

Solver mandiri HANYA membaca teks proyeksi dan SVG hasil `render_pertanyaan`
(banyak `<line class="turus-garis">` per `<g class="baris-turus">` + label), lewat
`penyajian_dari_soal`, lalu dibandingkan dengan `soal.kunci` untuk seluruh domain P2.
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
import awal_turus_gambar_awal as sumber
import design_tokens as T
from question_views import penyajian_dari_soal
from topic_matematika_awal_visual import proyeksi_matematika_awal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import (
    DescriptorVisual, deserialisasi_penyajian, serialisasi_penyajian,
)
from visual_inventory import DENOMINATOR_KANONIS
from visual_renderer import render_pertanyaan, ringkasan_pertanyaan
from visual_security_helpers import elemen, kelas, kontras, lokal, periksa_xml, teks_svg

TID = sumber.TEMPLATE_ID
GAYA = ("cetak", "murid", "stitch", "guru")
AKAR = Path(__file__).resolve().parent.parent
CONTOH = {"varian": "terbanyak", "tema": 0, "jumlah": [12, 5, 8]}
NARASI = "Perhatikan gambar turus. Satu garis berarti satu {satuan}, tiap lima garis dikelompokkan dengan coretan miring."
GARIS = "turus-garis"
UKURAN_DOMAIN = {"baca": 1320, "terbanyak": 440, "selisih": 1320, "jumlah": 440}


@pytest.fixture(autouse=True)
def keluarga_aktif(monkeypatch):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", "matematika-awal")


def _soal(parameter=None):
    return replace(sumber.turus_gambar_awal(**(parameter or CONTOH)), level="P2")


def _penyajian(parameter=None):
    return penyajian_dari_soal(_soal(parameter))


def _svg(parameter=None, *, namespace="uji-turus", gaya="cetak"):
    return periksa_xml(render_pertanyaan(_penyajian(parameter), namespace=namespace, gaya=gaya))


def _semua_parameter(varian):
    return tuple(p for p in sumber.domain_parameter("P2") if p["varian"] == varian)


def _data(jumlah, nama=("Apel", "Jeruk", "Pisang")):
    return {"adegan": "turus", "baris": [{"nama": n, "jumlah": j} for n, j in zip(nama, jumlah)],
            "tanya": {"varian": "terbanyak"}}


def _svg_data(data, namespace="uji"):
    return periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, namespace) + "</div>")


# ── solver mandiri: hanya teks proyeksi + SVG ────────────────────────────

def _baris_svg(svg):
    """Daftar (label huruf kecil, banyak <line class=turus-garis>) per baris, urut tampil."""
    hasil = []
    for baris in kelas(svg, "baris-turus"):
        label = "".join("".join(t.itertext()) for t in elemen(baris, "text"))
        garis = [e for e in elemen(baris, "line") if GARIS in e.get("class", "").split()]
        hasil.append((label.lower(), len(garis)))
    return tuple(hasil)


def _jawab(teks, svg):
    banyak = dict(_baris_svg(svg))
    tanya = teks.split("\n")[-1]
    if re.fullmatch(r"Berapa [a-z]+ semuanya\?", tanya):
        return str(sum(banyak.values()))
    if cocok := re.fullmatch(r"Berapa [a-z]+ lebih banyak ([a-z]+) daripada ([a-z]+)\?", tanya):
        return str(banyak[cocok[1]] - banyak[cocok[2]])
    if cocok := re.fullmatch(r"Berapa [a-z]+ ([a-z]+)\?", tanya):
        return str(banyak[cocok[1]])
    if re.fullmatch(r"[A-Z][a-z]+ apa yang paling banyak\?", tanya):
        return max(banyak, key=banyak.get)
    raise AssertionError(("pertanyaan tidak dikenal", tanya))


def test_domain_p2_utuh_seperti_semula():
    ukuran = {v: len(_semua_parameter(v)) for v in sumber.VARIAN}
    assert ukuran == UKURAN_DOMAIN


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_solver_svg_sama_dengan_kunci_seluruh_domain_p2(varian):
    for parameter in _semua_parameter(varian):
        soal = _soal(parameter)
        penyajian = penyajian_dari_soal(soal)
        svg = periksa_xml(render_pertanyaan(penyajian, namespace="sapuan"))
        harapan = tuple((k.lower(), n) for k, n in
                        zip(sumber.TEMA[parameter["tema"]].nama, parameter["jumlah"]))
        assert _baris_svg(svg) == harapan, parameter
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
    assert "|" in penyajian.teks_soal
    assert "<svg" not in render_pertanyaan(penyajian)


# ── invarian 2: teks, status, kontrak hitung ─────────────────────────────

def test_flag_aktif_status_siap_dan_teks_tanpa_garis_atau_angka():
    penyajian = _penyajian()
    assert penyajian.status_visual == "siap"
    assert penyajian.mode_representasi == "adegan_awal-v1"
    narasi, tanya = penyajian.teks_soal.split("\n")
    assert narasi == NARASI.format(satuan="buah")
    assert tanya == _soal().teks.split("\n")[-1]
    assert "|" not in penyajian.teks_soal


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_teks_tanpa_garis_angka_dan_kunci_seluruh_sampel(varian):
    for parameter in _semua_parameter(varian)[::13]:
        soal = _soal(parameter)
        teks = _penyajian(parameter).teks_soal
        assert not re.search(r"[0-9|]", teks), teks
        assert teks.split("\n")[-1] == soal.teks.split("\n")[-1]
        assert teks.split("\n")[0] == NARASI.format(satuan=sumber.TEMA[parameter["tema"]].satuan)
        if not soal.kunci.isdigit():
            assert soal.kunci not in teks.lower(), teks


def test_kata_satuan_diambil_dari_struktur_sumber_untuk_semua_tema():
    for tema, isi in enumerate(sumber.TEMA):
        parameter = {"varian": "jumlah", "tema": tema, "jumlah": [2, 4, 6]}
        assert f"satu {isi.satuan}," in _penyajian(parameter).teks_soal


def test_descriptor_tidak_membawa_kunci_atau_jawaban():
    penyajian = _penyajian()
    data = penyajian.descriptor.ke_dict()["data"]
    assert set(data) == {"adegan", "baris", "tanya"}
    assert data["adegan"] == "turus"
    assert data["tanya"] == {"varian": "terbanyak"}
    assert all(set(b) == {"nama", "jumlah"} for b in data["baris"])
    assert _soal().kunci not in str(data["tanya"])
    assert "kunci" not in serialisasi_penyajian(penyajian)


@pytest.mark.parametrize("jumlah", range(1, 13))
def test_kontrak_hitung_satu_unit_satu_elemen_garis_per_baris(jumlah):
    svg = _svg_data(_data((jumlah, 1, 12)))
    (_, a), (_, b), (_, c) = _baris_svg(svg)
    assert (a, b, c) == (jumlah, 1, 12)
    for baris, n in zip(kelas(svg, "baris-turus"), (jumlah, 1, 12)):
        garis = [e for e in elemen(baris, "line") if GARIS in e.get("class", "").split()]
        miring = [e for e in garis if e.get("x1") != e.get("x2")]
        assert len(miring) == n // 5, (n, len(miring))
        assert len(garis) - len(miring) == n - n // 5


def test_garis_kelima_memotong_empat_garis_tegak_sebelumnya():
    svg = _svg_data(_data((12, 5, 10)))
    for baris, n in zip(kelas(svg, "baris-turus"), (12, 5, 10)):
        garis = [e for e in elemen(baris, "line") if GARIS in e.get("class", "").split()]
        tegak = [e for e in garis if e.get("x1") == e.get("x2")]
        miring = [e for e in garis if e.get("x1") != e.get("x2")]
        for k, coret in enumerate(miring):
            kiri, kanan = float(coret.get("x1")), float(coret.get("x2"))
            atas, bawah = sorted((float(coret.get("y1")), float(coret.get("y2"))))
            empat = tegak[4 * k:4 * k + 4]
            assert len(empat) == 4
            for t in empat:
                x = float(t.get("x1"))
                y_atas, y_bawah = sorted((float(t.get("y1")), float(t.get("y2"))))
                assert kiri < x < kanan, (n, k)
                assert y_atas <= atas and bawah <= y_bawah
            # miring dari kiri-bawah ke kanan-atas, jadi terlihat sebagai coretan
            assert float(coret.get("y1")) > float(coret.get("y2"))


def test_kelompok_dipisah_lebih_lebar_daripada_jarak_antar_garis():
    svg = _svg_data(_data((12, 11, 10)))
    for baris in kelas(svg, "baris-turus"):
        garis = [e for e in elemen(baris, "line") if GARIS in e.get("class", "").split()]
        tegak = sorted({float(e.get("x1")) for e in garis if e.get("x1") == e.get("x2")})
        selisih = [b - a for a, b in zip(tegak, tegak[1:])]
        dalam, luar = min(selisih), max(selisih)
        assert dalam == T.ADEGAN_TURUS_JARAK
        assert luar >= 2 * dalam


def test_pemisah_baris_memakai_kelas_lain_dan_di_luar_grup_hitung():
    svg = _svg()
    pemisah = kelas(svg, "pemisah-baris")
    assert len(pemisah) == 3
    for baris in kelas(svg, "baris-turus"):
        assert not [e for e in elemen(baris, "line") if "pemisah-baris" in e.get("class", "")]
    assert all(GARIS not in e.get("class", "").split() for e in pemisah)


@pytest.mark.parametrize("gaya", GAYA)
def test_jumlah_garis_per_baris_sama_parameter_semua_gaya(gaya):
    svg = _svg(gaya=gaya)
    assert tuple(n for _, n in _baris_svg(svg)) == (12, 5, 8)
    assert len(kelas(svg, GARIS)) == 25


def test_stroke_tebal_satu_warna_token_terbaca_hitam_putih():
    svg = _svg()
    for e in kelas(svg, GARIS):
        assert e.get("stroke") == T.TEKS_UTAMA
        assert float(e.get("stroke-width")) >= 3
        assert kontras(e.get("stroke"), T.LATAR_KARTU) >= 3
    assert not elemen(svg, "image")


def test_ringkasan_non_html_menyebut_fakta_garis():
    ringkasan = ringkasan_pertanyaan(_penyajian())
    assert "Apel memiliki 12 garis" in ringkasan
    assert "tiap lima garis dikelompokkan" in ringkasan


# ── invarian 3: determinisme dan fingerprint ─────────────────────────────

def test_render_dua_kali_identik_byte_per_byte():
    penyajian = _penyajian()
    assert render_pertanyaan(penyajian, namespace="n") == render_pertanyaan(penyajian, namespace="n")
    assert _penyajian().fingerprint_penyajian == _penyajian().fingerprint_penyajian


def test_fingerprint_dipatok_agar_perubahan_penyajian_disengaja():
    penyajian = _penyajian()
    assert penyajian.fingerprint_matematis == (
        "dca1c4987cc3b65e602dc04a002b9e8bbe0e0a4486d9a06d057747a350c3ee06")
    assert penyajian.fingerprint_penyajian == (
        "9f737d3f27f6b220abe2f5dc05e6ac5966d17cc4d276638e8544f29fc30b11e9")


def test_round_trip_serialisasi_dan_fingerprint_matematis_sama_dengan_mode_teks(monkeypatch):
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
        "import awal_turus_gambar_awal as m\n"
        "from question_views import penyajian_dari_soal\n"
        "from visual_contract import serialisasi_penyajian\n"
        "from visual_renderer import render_pertanyaan\n"
        "h = hashlib.sha256()\n"
        "for p in m.domain_parameter('P2')[::89]:\n"
        "    s = penyajian_dari_soal(replace(m.turus_gambar_awal(**p), level='P2'))\n"
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
@pytest.mark.parametrize("tema", range(len(sumber.TEMA)))
def test_xml_allowlist_tanpa_script_url_atau_href(tema, gaya):
    parameter = {"varian": "terbanyak", "tema": tema, "jumlah": [1, 8, 4]}
    hasil = render_pertanyaan(_penyajian(parameter), gaya=gaya)
    svg = periksa_xml(hasil)
    tanpa_xmlns = hasil.replace('xmlns="http://www.w3.org/2000/svg"', "")
    assert not re.search(r"<script|foreignObject|javascript:|https?:|//|\son[a-z]+=", tanpa_xmlns, re.I)
    assert not [e for e in svg.iter() if "href" in e.attrib]
    assert {lokal(e) for e in svg.iter()} <= {"svg", "title", "desc", "g", "text", "tspan", "line"}


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


@pytest.mark.parametrize("nama", ("<script>x</script>", '<image href="//x.invalid/a"/>', "A<", "onload=x>"))
def test_markup_pada_nama_baris_ditolak(nama):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["baris"][1]["nama"] = nama
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


def test_nama_duplikat_ditolak_validator_dan_renderer():
    data = _penyajian().descriptor.ke_dict()["data"]
    data["baris"][1]["nama"] = data["baris"][0]["nama"].lower()
    with pytest.raises(ValueError):
        DescriptorVisual("adegan_awal", 1, data)
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


@pytest.mark.parametrize("nama", ("A & B", "'kutip' \"ganda\"", "Ａ＆Ｂ"))
def test_nama_baris_berkarakter_khusus_hanya_menjadi_teks(nama):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["baris"][1]["nama"] = nama
    svg = periksa_xml("<div>" + adegan_awal_svg.render_adegan_awal(data, "uji") + "</div>")
    assert nama in teks_svg(svg)


@pytest.mark.parametrize("jumlah", (0, 13, -1, 2.0, True, "3"))
def test_jumlah_di_luar_batas_ditolak_renderer(jumlah):
    data = _penyajian().descriptor.ke_dict()["data"]
    data["baris"][0]["jumlah"] = jumlah
    with pytest.raises(ValueError):
        adegan_awal_svg.render_adegan_awal(data, "uji")


def test_field_parameter_tambahan_atau_hilang_ditolak_proyektor():
    soal = _soal({"varian": "selisih", "tema": 0, "jumlah": [9, 3, 6], "besar": 0, "kecil": 1})
    for rusak in (
        {**soal.parameter, "kunci": "6"},
        {**soal.parameter, "versi_katalog": 2},
        {k: v for k, v in soal.parameter.items() if k != "kecil"},
        {k: v for k, v in soal.parameter.items() if k != "jumlah"},
        {**soal.parameter, "tanya": 0},
        {**soal.parameter, "varian": "lain"},
        {**soal.parameter, "tema": 7},
        {**soal.parameter, "tema": True},
        {**soal.parameter, "jumlah": [9, 9, 6]},
        {**soal.parameter, "jumlah": [9, 3]},
        {**soal.parameter, "jumlah": [9, 3, 13]},
        {**soal.parameter, "jumlah": [9, 3, 6.0]},
        {**soal.parameter, "besar": 1, "kecil": 0},
    ):
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, rusak)


def test_proyeksi_gagal_keras_bila_bentuk_teks_sumber_berubah(monkeypatch):
    soal = _soal()
    asli = sumber.turus_gambar_awal
    for ubah in (
        lambda teks: teks.replace("\n", " "),                       # baris data digabung
        lambda teks: teks.replace("Apel: ", "Apel ", 1),            # label baris berubah
        lambda teks: teks + "\nCatatan.",                           # baris tambahan
        lambda teks: teks.replace("Berapa", "Berapa 3", 1) if "Berapa" in teks else teks + "1",
        lambda teks: teks.rsplit("\n", 1)[0] + "\nAda 4 | di sini?",  # pertanyaan memuat angka dan garis
    ):
        def palsu(varian, **isi):
            hasil = asli(varian, **isi)
            return replace(hasil, teks=ubah(hasil.teks))
        monkeypatch.setattr(sumber, "turus_gambar_awal", palsu)
        with pytest.raises(ValueError):
            proyeksi_matematika_awal(TID, soal.parameter)


# ── invarian 5: batas viewBox dan tanpa tumpang tindih ───────────────────

def _kotak_garis(e):
    x1, x2 = sorted((float(e.get("x1")), float(e.get("x2"))))
    y1, y2 = sorted((float(e.get("y1")), float(e.get("y2"))))
    return x1, y1, x2, y2


@pytest.mark.parametrize("nama", ("A", "Kucing", "W" * 8, "W" * 23))
def test_empat_baris_dua_belas_garis_muat_dan_baris_tidak_saling_menimpa(nama):
    data = {"adegan": "turus", "tanya": {"varian": "terbanyak"},
            "baris": [{"nama": nama + str(i), "jumlah": 12} for i in range(4)]}
    svg = _svg_data(data, "batas")
    periksa_batas_koordinat(svg)
    lebar, tinggi = map(float, svg.get("viewBox").split()[2:])
    assert lebar == T.ADEGAN_LEBAR
    rentang = []
    for baris in kelas(svg, "baris-turus"):
        kotak = [_kotak_garis(e) for e in elemen(baris, "line")]
        assert len(kotak) == 12
        assert all(0 <= x1 and x2 <= lebar and 0 <= y1 and y2 <= tinggi for x1, y1, x2, y2 in kotak)
        rentang.append((min(k[1] for k in kotak), max(k[3] for k in kotak)))
    assert all(a[1] < b[0] for a, b in zip(rentang, rentang[1:]))


@pytest.mark.parametrize("varian", sumber.VARIAN)
def test_semua_soal_sah_dalam_viewbox(varian):
    for parameter in _semua_parameter(varian)[::31]:
        periksa_batas_koordinat(_svg(parameter))


def test_label_muat_di_kolom_kiri_dan_tidak_menyentuh_garis():
    """Perkiraan lebar teks (0,6 x font) per potongan label; oracle koordinat hanya memeriksa anchor."""
    data = _data((12, 12, 12), nama=("W" * 8, "Kucing", "M" * 24))
    svg = _svg_data(data)
    ruang = T.ADEGAN_IKON_X - T.ADEGAN_MARGIN
    for baris in kelas(svg, "baris-turus"):
        for teks in elemen(baris, "text"):
            potongan = [("".join(t.itertext())) for t in elemen(teks, "tspan")] or ["".join(teks.itertext())]
            assert all(len(p) <= T.ADEGAN_LABEL_PER_BARIS for p in potongan)
            assert max(len(p) for p in potongan) * 0.6 * T.ADEGAN_FONT <= ruang
        garis_kiri = min(_kotak_garis(e)[0] for e in elemen(baris, "line"))
        assert garis_kiri >= T.ADEGAN_IKON_X


def test_label_sejajar_dengan_garis_barisnya():
    svg = _svg()
    for baris in kelas(svg, "baris-turus"):
        ys = [y for e in elemen(baris, "line") for y in (float(e.get("y1")), float(e.get("y2")))]
        label_y = float(elemen(baris, "text")[0].get("y"))
        assert min(ys) <= label_y <= max(ys)


# ── invarian 6: aksesibilitas ────────────────────────────────────────────

def test_role_title_desc_terhubung_dan_tidak_memuat_jumlah():
    svg = _svg()
    judul, = elemen(svg, "title")
    uraian, = elemen(svg, "desc")
    assert svg.get("role") == "img"
    assert svg.get("aria-labelledby").split() == [judul.get("id"), uraian.get("id")]
    isi = "".join(uraian.itertext())
    assert len(isi.split()) >= 4 and "".join(judul.itertext()).strip()
    assert not re.search(r"\d", isi + "".join(judul.itertext()))
    for nama in ("Apel", "Jeruk", "Pisang"):
        assert nama in isi


def test_uraian_tidak_bergantung_pada_jumlah_atau_pertanyaan():
    a = {"varian": "baca", "tema": 0, "jumlah": [1, 2, 3], "tanya": 0}
    b = {"varian": "terbanyak", "tema": 0, "jumlah": [12, 11, 10]}
    desc = ["".join(elemen(_svg(p), "desc")[0].itertext()) for p in (a, b)]
    assert desc[0] == desc[1]


def test_semua_teks_svg_satu_warna_token_kontras_dan_tidak_kosong():
    svg = _svg()
    warna = {e.get("fill") for e in svg.iter() if e.get("fill")}
    assert warna == {T.TEKS_UTAMA}
    assert kontras(T.TEKS_UTAMA, T.LATAR_KARTU) >= 4.5
    assert kontras(T.TEKS_UTAMA, T.LATAR_MURID) >= 4.5
    assert all(t for t in teks_svg(svg))


def test_id_unik_pada_lembar_dengan_banyak_soal_berulang():
    ids = []
    for i in range(6):
        ids += [e.get("id") for e in _svg(namespace=f"lembar-{i}").iter() if e.get("id")]
    assert len(ids) == len(set(ids)) == 12


# ── invarian 7: inventaris ───────────────────────────────────────────────

def test_inventaris_menandai_turus_gambar_awal_wajib_visual_untuk_semua_varian():
    baris = [d for d in DENOMINATOR_KANONIS if d["template_id"] == TID]
    assert {d["status"] for d in baris} == {"wajib_visual"}
    assert {d["varian"] for d in baris} == {f"varian={v}" for v in sumber.VARIAN}
    assert {d["level"] for d in baris} == {"P2"}
