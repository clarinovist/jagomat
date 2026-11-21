"""Gate seluruh bank, bukan hanya contoh renderer terpilih."""
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import topics
from question_views import penyajian_dari_soal
from visual_bounds_helpers import periksa_batas_koordinat
from visual_contract import deserialisasi_penyajian, serialisasi_penyajian
from visual_inventory import DENOMINATOR_KANONIS, VARIAN_SENGAJA_TEKS, identitas_varian
from visual_renderer import render_pertanyaan
from visual_test_support import (SEMUA_KELUARGA, buat_soal, gambar,
                                 id_dan_referensi, pasangan_aktif)

ANGKA = frozenset(("x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx",
                   "ry", "width", "height", "stroke-width", "font-size"))
KOMPOSIT = frozenset(("d", "points", "transform", "viewBox"))


def periksa_geometri(akar):
    kotak = tuple(map(float, akar.attrib["viewBox"].split()))
    assert len(kotak) == 4 and kotak[2] > 0 and kotak[3] > 0
    for elemen in akar.iter():
        for nama, nilai in elemen.attrib.items():
            if nama in ANGKA and not nilai.endswith(("%", "px", "rem", "em")):
                assert math.isfinite(float(nilai)), (nama, nilai)
            if nama in KOMPOSIT:
                assert not re.search(r"(?i)(?:nan|inf)", nilai), (nama, nilai)
                angka = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", nilai)
                assert all(math.isfinite(float(n)) for n in angka)
    periksa_batas_koordinat(akar)
    return id_dan_referensi(akar)


def _svg_sintetis(isi, kotak="0 0 100 100"):
    return gambar(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{kotak}">{isi}</svg>')[0]


@pytest.mark.parametrize("tag", ("text", "tspan"))
@pytest.mark.parametrize("x,y", ((-1, 50), (101, 50), (50, -1), (50, 101)))
def test_oracle_mutasi_anchor_keluar_viewbox(tag, x, y):
    def label(a, b):
        isi = f'<{tag} x="{a}" y="{b}">Ukuran</{tag}>'
        return f'<text>{isi}</text>' if tag == "tspan" else isi
    periksa_geometri(_svg_sintetis(label(50, 50)))
    with pytest.raises(AssertionError, match="di luar viewBox"):
        periksa_geometri(_svg_sintetis(label(x, y)))


@pytest.mark.parametrize("isi,kotak", (
    ('<g transform="translate(40 20)"><g transform="scale(2 3)">'
     '<text x="-10" y="5">A</text></g></g>', "0 0 100 100"),
    ('<text transform="translate(40,20) scale(2,3)" x="-10" y="5">A</text>', "0 0 100 100"),
    ('<g transform="scale(.5)"><g transform="translate(40)">'
     '<text x="110" y="50">A</text></g></g>', "0 0 100 100"),
    ('<text transform="translate(100 100) scale(-1 -2)" x="20" y="30">A</text>', "0 0 100 100"),
    ('<text x="-15" y="-25">A</text>', "-20 -30 100 100"),
    ('<text x="109" y="119">A</text>', "10 20 100 100"),
    ('<text x="100" y="100">Teks panjang boleh melampaui anchor</text>', "0 0 100 100"),
))
def test_oracle_anchor_transform_sah_bukan_font_bbox(isi, kotak):
    periksa_geometri(_svg_sintetis(isi, kotak))


@pytest.mark.parametrize("isi,kotak", (
    ('<g transform="translate(40)"><g transform="scale(2)">'
     '<text x="40" y="20">A</text></g></g>', "0 0 100 100"),
    ('<text transform="scale(2) translate(40)" x="20" y="20">A</text>', "0 0 100 100"),
    ('<g transform="translate(10)"><text transform="scale(-2)" x="10" y="0">A</text></g>', "0 0 100 100"),
    ('<text x="0" y="50">A</text>', "10 20 100 100"),
    ('<text x="90" y="50">A</text>', "-20 -30 100 100"),
))
def test_oracle_mutasi_nested_transform_dan_asal_viewbox(isi, kotak):
    with pytest.raises(AssertionError, match="di luar viewBox"):
        periksa_geometri(_svg_sintetis(isi, kotak))


@pytest.mark.parametrize("isi", (
    '<polygon points="10,10 101,20 20,30"/>',
    '<polyline points="10 10 20 -1"/>',
    '<line x1="10" y1="20" x2="101" y2="20"/>',
    '<circle cx="95" cy="50" r="6"/>',
    '<ellipse cx="50" cy="5" rx="2" ry="6"/>',
    '<rect x="90" y="10" width="11" height="20"/>',
    '<g transform="translate(50) scale(2 3)"><circle cx="20" cy="20" r="6"/></g>',
    '<g transform="translate(100 100) scale(-2)"><line x1="0" y1="0" x2="51" y2="0"/></g>',
))
def test_oracle_mutasi_geometri_keluar_viewbox(isi):
    with pytest.raises(AssertionError, match="di luar viewBox"):
        periksa_geometri(_svg_sintetis(isi))


@pytest.mark.parametrize("isi", (
    '<polygon points="0,0 100,0 100,100"/><polyline points="0 0 100 100"/>',
    '<g transform="translate(100 100) scale(-2)"><circle cx="25" cy="25" r="25"/></g>',
    '<g transform="translate(10 20) scale(2 3)"><ellipse cx="20" cy="10" rx="20" ry="10"/></g>',
    '<rect width="100" height="100"/><line x2="100" y2="100"/>',
))
def test_oracle_geometri_sah_termasuk_skala_negatif(isi):
    periksa_geometri(_svg_sintetis(isi))


@pytest.mark.parametrize("isi", (
    '<text transform="rotate(45)" x="10" y="20">A</text>',
    '<text transform="translate(2) sampah" x="10" y="20">A</text>',
    '<circle cx="50" cy="50" r="-1"/>',
    '<rect width="-1" height="20"/>',
    '<polygon points="1,2 3"/>',
))
def test_oracle_tidak_meloloskan_bentuk_tak_didukung(isi):
    with pytest.raises(AssertionError):
        periksa_geometri(_svg_sintetis(isi))


def test_oracle_definisi_hatch_dan_clip_bukan_geometri_di_layar():
    definisi = ('<defs><pattern id="arsir" width="8" height="8">'
                '<line x1="-8" y1="0" x2="108" y2="8"/></pattern>'
                '<clipPath id="potong"><rect x="-10" y="-10" width="120" height="120"/>'
                '</clipPath></defs>')
    bentuk = '<rect width="100" height="100" fill="url(#arsir)" clip-path="url(#potong)"/>'
    assert periksa_geometri(_svg_sintetis(definisi + bentuk)) == ("arsir", "potong")
    with pytest.raises(AssertionError, match="di luar viewBox"):
        periksa_geometri(_svg_sintetis(definisi + bentuk + '<text x="-1" y="20">A</text>'))


@pytest.mark.parametrize("topik", topics.daftar_topik())
def test_seluruh_bank_minimal_100_seed(topik, monkeypatch, tmp_path):
    monkeypatch.setenv("OSN_VISUAL_KELUARGA", SEMUA_KELUARGA)
    cakupan = frozenset()
    jumlah = 0
    for nama, level, tid in pasangan_aktif():
        if nama != topik:
            continue
        awal = penyajian_dari_soal(buat_soal(nama, level, tid, 0))
        for seed in range(500 if awal.descriptor is not None else 100):
            soal = buat_soal(nama, level, tid, seed)
            penyajian = penyajian_dari_soal(soal)
            varian = identitas_varian(tid, soal.parameter)
            cakupan = cakupan | {(nama, level, tid, varian)}
            wajib = (varian not in VARIAN_SENGAJA_TEKS.get(tid, ())
                     and any(d["template_id"] == tid and d["status"] == "wajib_visual"
                             for d in DENOMINATOR_KANONIS))
            assert not wajib or penyajian.status_visual == "siap", (nama, level, tid, seed)
            serial = serialisasi_penyajian(penyajian)
            assert deserialisasi_penyajian(serial) == penyajian
            badan = render_pertanyaan(penyajian, namespace=f"{nama}-{level}-{tid}-{seed}")
            akar = gambar(badan)
            assert len(akar) == int(penyajian.descriptor is not None)
            for svg in akar:
                periksa_geometri(svg)
            jumlah += 1
    harapan = frozenset((d["topik_id"], d["level"], d["template_id"], d["varian"])
                       for d in DENOMINATOR_KANONIS if d["topik_id"] == topik)
    assert harapan <= cakupan
    assert jumlah >= 100
    (tmp_path / f"sweep-{topik}.json").write_text(json.dumps({
        "jumlah": jumlah, "cakupan": sorted(cakupan)}), encoding="utf-8")


def test_snapshot_dan_html_seluruh_bank_identik_antarproses():
    kode = '''import hashlib,json
from visual_test_support import pasangan_aktif,buat_soal
from question_views import penyajian_dari_soal
from visual_contract import serialisasi_penyajian
from visual_renderer import render_pertanyaan
hasil=tuple((n,l,t,hashlib.sha256((serialisasi_penyajian(p)+render_pertanyaan(p,namespace=f"{n}-{l}-{t}")).encode()).hexdigest())
 for n,l,t in pasangan_aktif() for p in (penyajian_dari_soal(buat_soal(n,l,t,73)),))
print(json.dumps(hasil))'''
    akar = Path(__file__).resolve().parent.parent
    hasil = tuple(subprocess.check_output([sys.executable, "-c", kode], cwd=akar,
        env={**os.environ, "PYTHONPATH": str(akar / "__tests__"),
             "OSN_VISUAL_KELUARGA": SEMUA_KELUARGA, "PYTHONHASHSEED": str(seed)},
        text=True, timeout=90) for seed in (1, 8191))
    assert hasil[0] == hasil[1]
    assert len(json.loads(hasil[0])) == len(pasangan_aktif())
