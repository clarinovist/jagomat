"""Oracle XML dan kasus sintetis Fase 8; tidak membuka DB atau harness parent."""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable
from xml.etree import ElementTree as ET

import topic_combinatorics as kombinatorik
import topic_measurement as pengukuran
import topic_number_patterns as pola
import topic_plane_geometry as datar
import topic_solid_geometry as ruang
import topic_statistics as statistika
from question_views import penyajian_dari_soal
from visual_contract import buat_penyajian
from visual_renderer import render_pertanyaan

NS = "http://www.w3.org/2000/svg"
KELUARGA = (
    "statistika", "geometri-datar", "geometri-ruang", "pengukuran",
    "kombinatorik", "pola-bilangan",
)
GAYA = ("cetak", "murid", "stitch", "guru")


@dataclass(frozen=True)
class Kasus:
    keluarga: str
    nama: str
    pembuat: Callable


KASUS = (
    Kasus("statistika", "batang", lambda: statistika.diagram_batang_garis("baca", [7, 13, 21], 1)),
    Kasus("statistika", "turus", lambda: statistika.tabel_turus("baca", ["Apel", "Jeruk", "Mangga"], [7, 13, 21], 1)),
    Kasus("statistika", "piktogram", lambda: statistika.piktogram("total", 5, [2, 3, 4], ["Apel", "Jeruk", "Mangga"])),
    Kasus("statistika", "lingkaran", lambda: statistika.diagram_lingkaran("cari_sudut", 90, 120, 30)),
    Kasus("geometri-datar", "datar-balik", lambda: datar.keliling_luas_datar("balik_luas", p=12, K=38)),
    Kasus("geometri-datar", "arsiran", lambda: datar.luas_arsiran("persegi_titik_tengah", r=7)),
    Kasus("geometri-ruang", "ruang-balik", lambda: ruang.volume_kubus_balok("kubus_cari_s", s=4, V=64)),
    Kasus("geometri-ruang", "tabung", lambda: ruang.volume_prisma_tabung("tabung_balik", r=2, V="37,68", versi=2)),
    Kasus("pengukuran", "waktu", lambda: pengukuran.jam_selesai("cari_selesai", 21, 47, 4, 38)),
    Kasus("pengukuran", "peta", lambda: pengukuran.skala_peta("cari_peta", 45, 18, 250000, **{"versi": 2})),
    Kasus("kombinatorik", "petak", lambda: kombinatorik.jalur_petak(3, 4)),
    Kasus("kombinatorik", "venn", lambda: kombinatorik.inklusi_eksklusi_2(19, 23, 7)),
    Kasus("kombinatorik", "susunan", lambda: kombinatorik.permutasi_urutan(5, 3, ["A", "B", "C", "D", "E"])),
    Kasus("pola-bilangan", "korek", lambda: pola.korek_api(4, 3, 20)),
    Kasus("pola-bilangan", "titik", lambda: pola.titik_segitiga(12)),
)


def snapshot(kasus):
    hasil = penyajian_dari_soal(kasus.pembuat())
    assert hasil.status_visual == "siap", kasus.nama
    assert hasil.descriptor is not None
    return hasil


def bangun_ulang(asal, *, descriptor=None, teks=None):
    """Buat snapshot baru sah tanpa mengubah dataclass atau descriptor asal."""
    baru = descriptor if descriptor is not None else asal.descriptor
    return buat_penyajian(
        template_id="korek_api", level="P4", parameter={},
        teks_soal=asal.teks_soal if teks is None else teks,
        status_visual="siap", mode_representasi=f"{baru.jenis}-v{baru.versi}",
        descriptor=baru,
    )


def lokal(elemen):
    return elemen.tag.rsplit("}", 1)[-1]


def elemen(svg, tag):
    return tuple(e for e in svg.iter() if lokal(e) == tag)


def teks_svg(svg):
    """Node teks/alternatif saja: angka koordinat bukan kebocoran jawaban."""
    return tuple("".join(e.itertext()) for e in svg.iter()
                 if lokal(e) in {"text", "title", "desc"})


def kelas(svg, nama):
    return tuple(e for e in svg.iter() if nama in e.get("class", "").split())


def gambar(kasus, *, namespace="uji-visual", gaya="cetak"):
    return periksa_xml(render_pertanyaan(snapshot(kasus), namespace=namespace, gaya=gaya))


_ATRIBUT = {
    "svg": "viewBox role aria-labelledby aria-describedby style",
    "title": "", "desc": "", "defs": "", "g": "transform data-gambar",
    "text": "x y text-anchor font-size fill dominant-baseline data-vertex",
    "tspan": "x y",
    "line": "x1 y1 x2 y2 stroke stroke-width stroke-dasharray",
    "circle": "cx cy r fill stroke stroke-width",
    "ellipse": "cx cy rx ry fill stroke stroke-width",
    "rect": "x y width height fill stroke stroke-width",
    "path": "d fill stroke stroke-width stroke-dasharray",
    "polygon": "points fill stroke stroke-width",
    "polyline": "points fill stroke stroke-width stroke-dasharray",
    "pattern": "width height patternUnits",
}
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}")
_WARNA = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?")
_URL_LOKAL = re.compile(r"url\(#([A-Za-z][A-Za-z0-9_.-]{0,127})\)")
_CSS = {
    "display": r"block", "width": r"100%", "height": r"auto",
    "max-width": r"[0-9.]+rem", "margin": r"[0-9.]+rem auto",
}


def _periksa_style(nilai):
    bagian = tuple(p.strip().split(":", 1) for p in nilai.split(";") if p.strip())
    assert all(len(p) == 2 for p in bagian), nilai
    assert len({p[0] for p in bagian}) == len(bagian), nilai
    for nama, isi in bagian:
        assert nama in _CSS, nama
        assert re.fullmatch(_CSS[nama], isi.strip()), (nama, isi)


def _periksa_atribut(e, ids):
    izin = frozenset(_ATRIBUT[lokal(e)].split()) | {"class", "id"}
    assert set(e.attrib) <= izin, (e.tag, set(e.attrib) - izin)
    for nama, isi in e.attrib.items():
        assert not any(unicodedata.category(c).startswith("C") for c in isi)
        if nama == "id":
            assert _ID.fullmatch(isi), isi
        elif nama == "style":
            _periksa_style(isi)
        elif nama in {"fill", "stroke"}:
            tautan = _URL_LOKAL.fullmatch(isi)
            assert isi == "none" or _WARNA.fullmatch(isi) or tautan, isi
            if tautan:
                assert tautan[1] in ids, isi
                assert lokal(ids[tautan[1]]) == "pattern", isi
        elif nama in {"aria-labelledby", "aria-describedby"}:
            assert isi.split() and all(i in ids for i in isi.split()), isi


_KELAS_PECAHAN = frozenset({"pecahan", "pecahan-angka"})
_LABEL_PECAHAN = re.compile(r"\d{1,3} per \d{1,3}")


def _periksa_pecahan(e):
    """Markup pecahan adalah satu-satunya elemen non-div/non-SVG yang diizinkan."""
    kelas = (e.get("class") or "").split()
    assert kelas and set(kelas) <= _KELAS_PECAHAN, kelas
    assert set(e.attrib) <= {"class", "role", "aria-label", "aria-hidden"}, e.attrib
    if e.get("role") is not None:
        assert e.get("role") == "math" and kelas == ["pecahan"]
    if e.get("aria-label") is not None:
        assert _LABEL_PECAHAN.fullmatch(e.get("aria-label")), e.get("aria-label")
    if e.get("aria-hidden") is not None:
        assert e.get("aria-hidden") == "true" and kelas == ["pecahan-angka"]
    for isi in (e.text or "", e.tail or ""):
        assert not any(unicodedata.category(c).startswith("C")
                       and c not in "\n\r\t" for c in isi), repr(isi)


def periksa_xml(hasil):
    """Parse seluruh fragmen, bukan potongan SVG yang dapat menutupi injeksi."""
    assert not re.search(r"<!DOCTYPE|<!ENTITY|<\?", hasil, re.I)
    akar = ET.fromstring(hasil)
    svg_semua = tuple(e for e in akar.iter() if e.tag == "{" + NS + "}svg")
    assert len(svg_semua) == 1
    svg, = svg_semua
    assert all(e.tag == "{" + NS + "}" + lokal(e) for e in svg.iter()), "Namespace subtree SVG asing"
    id_semua = tuple(e.get("id") for e in akar.iter() if "id" in e.attrib)
    assert len(id_semua) == len(set(id_semua)), "ID SVG duplikat"
    ids = {e.get("id"): e for e in svg.iter() if "id" in e.attrib}
    for e in akar.iter():
        if e.tag == "div":
            assert set(e.attrib) <= {"class", "data-fingerprint-penyajian"}
            continue
        if e.tag == "span":
            _periksa_pecahan(e)
            continue
        assert e.tag == "{" + NS + "}" + lokal(e), e.tag
        assert lokal(e) in _ATRIBUT, e.tag
        _periksa_atribut(e, ids)
        for isi in (e.text or "", e.tail or ""):
            assert not any(unicodedata.category(c).startswith("C")
                           and c not in "\n\r\t" for c in isi), repr(isi)
    return svg


def luminansi(warna):
    """Luminansi relatif sRGB sesuai rumus WCAG, termasuk hex tiga digit."""
    assert _WARNA.fullmatch(warna), warna
    heksa = warna[1:]
    penuh = "".join(c * 2 for c in heksa) if len(heksa) == 3 else heksa
    kanal = tuple(int(penuh[i:i + 2], 16) / 255 for i in (0, 2, 4))
    linear = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in kanal)
    return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))


def kontras(depan, belakang):
    a, b = sorted((luminansi(depan), luminansi(belakang)))
    return (b + 0.05) / (a + 0.05)


def panjang_garis(e):
    return math.hypot(float(e.get("x2")) - float(e.get("x1")),
                      float(e.get("y2")) - float(e.get("y1")))
