"""Solver MANDIRI `piktogram_lima_awal` (tanpa memakai kode jenis): dari teks (titik hitam) dan dari gambar.

Dua bentuk soal, dua pembaca:
  - `solver_dari_teks`: membaca teks tanpa flag (baris "Nama: ●●●"), menghitung "●" per baris;
  - `solver_dari_visual`: membaca teks proyeksi (skala + pertanyaan) dan banyak `<image>` per
    `<g class="baris-adegan">` pada SVG, skala dari legenda gambar di luar grup baris.
Keduanya memakai rumus yang ditulis ulang di sini.
"""
from __future__ import annotations

import re
from xml.etree import ElementTree

SIMBOL = "●"
KEPALA = re.compile(r"Piktogram (.+)\. Satu titik hitam mewakili (\d+) ([a-z ]+)\.")
BARIS = re.compile(r"([A-Z][a-z]+): (●+)")
KEPALA_VISUAL = re.compile(r"Perhatikan gambar\. Satu gambar mewakili (\d+) ([a-z ]+)\.")
TANYA_BACA = re.compile(r"Berapa banyak ([a-z]+)\?")
TANYA_SELISIH = re.compile(
    r"Kategori yang paling banyak lebih banyak berapa ([a-z ]+) daripada kategori yang paling sedikit\?")
TANYA_TOTAL = re.compile(r"Berapa jumlah semua ([a-z ]+)\?")
TANYA_RATA = re.compile(r"Berapa rata-rata banyak ([a-z ]+) untuk tiap jenis\?")
TANYA_BALIK = re.compile(
    r"([A-Z][a-z]+) ada (\d+) ([a-z ]+), tetapi barisnya belum digambar\. "
    r"Berapa (titik hitam|gambar) yang harus digambar pada baris ([a-z]+)\?")
NAMESPACE_SVG = "{http://www.w3.org/2000/svg}"


def hitung(tanya: str, banyak: dict, skala: int, kata: str, urutan: list) -> str:
    """Jawaban dari kalimat pertanyaan, banyak gambar per kategori, dan skala."""
    nilai = list(banyak.values())
    if (cocok := TANYA_BACA.fullmatch(tanya)):
        asal = [n for n in banyak if n.lower() == cocok[1]]
        assert len(asal) == 1, (tanya, list(banyak))
        return str(banyak[asal[0]] * skala)
    if (cocok := TANYA_SELISIH.fullmatch(tanya)):
        assert cocok[1] == kata, (tanya, kata)
        assert nilai.count(max(nilai)) == 1 and nilai.count(min(nilai)) == 1, "terbanyak/tersedikit harus tunggal"
        return str((max(nilai) - min(nilai)) * skala)
    if (cocok := TANYA_TOTAL.fullmatch(tanya)):
        assert cocok[1] == kata, (tanya, kata)
        return str(sum(nilai) * skala)
    if (cocok := TANYA_RATA.fullmatch(tanya)):
        assert cocok[1] == kata and sum(nilai) % len(nilai) == 0, (tanya, nilai)
        return str(sum(nilai) // len(nilai) * skala)
    if (cocok := TANYA_BALIK.fullmatch(tanya)):
        nama, besar, satuan, _, baris = cocok.groups()
        assert satuan == kata and nama.lower() == baris and nama not in banyak, (tanya, list(banyak))
        assert int(besar) % skala == 0, (tanya, skala)
        return str(int(besar) // skala)
    raise AssertionError(("pertanyaan tidak dikenal", tanya))


def _periksa_bentuk_banyak(banyak: dict, tanya: str) -> None:
    jumlah = list(banyak.values())
    assert 3 <= len(jumlah) + (1 if TANYA_BALIK.fullmatch(tanya) else 0) <= 5, banyak
    assert len(jumlah) >= 3 and all(1 <= n <= 10 for n in jumlah), banyak
    assert len(set(jumlah)) == len(jumlah), ("jumlah gambar tiap baris harus berbeda", banyak)


def solver_dari_teks(teks: str) -> str:
    """Kunci dari teks tanpa flag saja: skala dari kepala, titik per baris, rumus pertanyaan."""
    baris = teks.split("\n")
    assert len(baris) >= 5, teks
    kepala = KEPALA.fullmatch(baris[0])
    assert kepala, baris[0]
    skala, kata = int(kepala[2]), kepala[3]
    assert skala in (2, 5, 10, 20), skala
    banyak = {}
    for isi in baris[1:-1]:
        cocok = BARIS.fullmatch(isi)
        assert cocok, isi
        assert cocok[1] not in banyak, ("baris kembar", isi)
        banyak[cocok[1]] = len(cocok[2])
    assert teks.count(SIMBOL) == sum(banyak.values()), "simbol hanya boleh ada pada baris data"
    assert SIMBOL not in baris[0] and SIMBOL not in baris[-1]
    _periksa_bentuk_banyak(banyak, baris[-1])
    return hitung(baris[-1], banyak, skala, kata, list(banyak))


def _tag(elemen) -> str:
    return elemen.tag.replace(NAMESPACE_SVG, "")


def _svg_dari(html_hasil: str):
    awal = html_hasil.index("<svg")
    return ElementTree.fromstring(html_hasil[awal:html_hasil.rindex("</svg>") + len("</svg>")])


def baris_svg(svg) -> dict:
    """{label: banyak <image>} per `<g class="baris-adegan">`, urut tampil; label kosong ditolak."""
    hasil = {}
    for grup in svg.iter(NAMESPACE_SVG + "g"):
        if grup.get("class") != "baris-adegan":
            continue
        label = "".join("".join(t.itertext()) for t in grup if _tag(t) == "text")
        assert label and label not in hasil, (label, list(hasil))
        hasil[label] = sum(1 for e in grup.iter() if _tag(e) == "image")
    return hasil


def legenda_svg(svg):
    """Teks legenda skala di luar grup baris, atau None."""
    grup = [g for g in svg.iter(NAMESPACE_SVG + "g") if g.get("class") == "legenda-adegan"]
    assert len(grup) <= 1
    if not grup:
        return None
    return "".join("".join(t.itertext()) for t in grup[0] if _tag(t) == "text")


def solver_dari_visual(teks_proyeksi: str, html_hasil: str) -> str:
    """Kunci dari teks proyeksi + SVG hasil render: skala dari teks (dicocokkan ke legenda)."""
    awal, tanya = teks_proyeksi.split("\n")
    kepala = KEPALA_VISUAL.fullmatch(awal)
    assert kepala, awal
    skala, kata = int(kepala[1]), kepala[2]
    svg = _svg_dari(html_hasil)
    assert legenda_svg(svg) == f"Satu gambar mewakili {skala} benda.", (awal, legenda_svg(svg))
    banyak = baris_svg(svg)
    assert svg.get("viewBox") is not None
    _periksa_bentuk_banyak(banyak, tanya)
    return hitung(tanya, banyak, skala, kata, list(banyak))
