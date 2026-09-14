"""Fixture murni lintas bank untuk gate visual; tidak membuka DB aplikasi."""
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import replace

import topics
from templates import REGISTRI

KELUARGA = ("statistika", "geometri-datar", "geometri-ruang", "pengukuran",
            "kombinatorik", "pola-bilangan")
SEMUA_KELUARGA = ",".join(KELUARGA)
NS = {"s": "http://www.w3.org/2000/svg"}


def pasangan_aktif():
    return tuple((nama, level, tid) for nama in topics.daftar_topik()
                 for level, urutan in topics.ambil(nama).komposisi.items()
                 for tid in sorted(set(urutan)))


def buat_soal(nama, level, tid, seed):
    paket = topics.ambil(nama)
    assert paket.parameter_untuk is not None
    parameter = paket.parameter_untuk(tid, random.Random(seed), level)
    return replace(REGISTRI[tid](**parameter), level=level)


def gambar(badan):
    return tuple(ET.fromstring(s) for s in re.findall(r"<svg\b.*?</svg>", badan, re.S))


def id_dan_referensi(akar):
    ids = tuple(e.attrib["id"] for e in akar.iter() if "id" in e.attrib)
    assert len(ids) == len(set(ids)), "ID SVG duplikat"
    referensi = tuple(r for e in akar.iter() for k, v in e.attrib.items()
                      for r in (v.split() if k == "aria-labelledby" else
                                re.findall(r"url\(#([^\)]+)\)", v)))
    assert set(referensi) <= set(ids), "referensi SVG menggantung"
    return ids
