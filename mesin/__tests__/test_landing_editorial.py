"""Kontrak presentasi landing editorial; tidak menyentuh DB atau alur latihan."""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import design_tokens as T
from landing import (
    halaman_daftar,
    halaman_kebijakan,
    halaman_landing,
    halaman_lupa_sandi,
)
from style_stitch import GAYA_STITCH
from teacher_style import SKRIP_CEGAH_KIRIM_GANDA, SKRIP_MATA_SANDI


class _Markup(HTMLParser):
    """Kumpulkan atribut elemen tanpa tergantung spasi/urutan atribut HTML."""

    def __init__(self, sumber):
        super().__init__()
        self.elemen = []
        self.feed(sumber)

    def handle_starttag(self, tag, attrs):
        self.elemen.append((tag, dict(attrs)))

    def cari(self, tag):
        return [atribut for nama, atribut in self.elemen if nama == tag]


@pytest.fixture
def markup():
    return _Markup(halaman_landing().decode())


def test_kanvas_landing_terpisah_dari_padding_form(markup):
    kelas = [atribut.get("class", "") for _, atribut in markup.elemen]
    assert "landing-halaman-st" in kelas
    assert "publik-badan-st" not in kelas
    assert "publik-bungkus-st" not in kelas
    assert markup.cari("main") == [{
        "class": "landing-bungkus-st", "id": "konten", "tabindex": "-1",
    }]


@pytest.mark.parametrize("halaman", [halaman_daftar, halaman_kebijakan, halaman_lupa_sandi])
def test_form_publik_tetap_memakai_kanvas_lama(halaman):
    markup = _Markup(halaman().decode())
    kelas = [atribut.get("class", "") for _, atribut in markup.elemen]
    assert "publik-badan-st" in kelas
    assert "landing-halaman-st" not in kelas


def test_hierarki_heading_dan_tujuan_jangkar_unik(markup):
    assert len(markup.cari("h1")) == 1
    assert markup.cari("h1")[0]["id"] == "judul-landing"
    sumber = halaman_landing().decode()
    assert "Bukan sekadar<br>benar." in sumber
    assert "<span>Paham caranya.</span>" in sumber
    daftar_id = [atribut["id"] for _, atribut in markup.elemen if "id" in atribut]
    assert len(daftar_id) == len(set(daftar_id))
    jangkar = [atribut["href"][1:] for atribut in markup.cari("a")
               if atribut.get("href", "").startswith("#")]
    assert set(jangkar) == {"konten", "cara-kerja", "contoh", "harga"}
    assert set(jangkar) <= set(daftar_id)
    for _, atribut in markup.elemen:
        if "aria-labelledby" in atribut:
            assert atribut["aria-labelledby"] in daftar_id


def test_harga_ada_sebelum_faq_dan_menu_tetap_tersedia_di_hp(markup):
    sumber = halaman_landing().decode()
    assert sumber.index('id="harga"') < sumber.index('class="landing-faq-st"')
    nav = sumber.split('<nav ', 1)[1].split('</nav>', 1)[0]
    assert 'class="landing-nav-st landing-nav-harga-st" href="#harga">Harga</a>' in nav
    assert any(atribut.get("id") == "harga" and atribut.get("aria-labelledby") == "judul-harga"
               for atribut in markup.cari("section"))
    hp = GAYA_STITCH.split("/* ══ Landing editorial", 1)[1].split("/* Halaman hasil murid", 1)[0]
    hp = hp.split("@media (max-width: 40rem)", 1)[1]
    assert ".landing-nav-harga-st { display: inline-flex; }" in hp


def test_maskot_lokal_dekoratif_berukuran_tetap(markup):
    maskot = [atribut for atribut in markup.cari("img")
              if atribut.get("class") == "landing-maskot-st"]
    assert len(maskot) == 1
    assert maskot[0]["src"] == "/aset/maskot-menunjuk-v3-240.png"
    assert maskot[0]["alt"] == ""
    assert maskot[0]["aria-hidden"] == "true"
    assert maskot[0]["width"] == maskot[0]["height"] == "240"


def test_faq_native_dan_tidak_ada_skrip_baru(markup):
    sumber = halaman_landing().decode()
    assert len(markup.cari("details")) == len(markup.cari("summary")) == 7
    assert re.findall(r"<script>(.*?)</script>", sumber, re.S) == [
        SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA,
    ]
    assert not any(nama.startswith("on") for _, atribut in markup.elemen for nama in atribut)
    assert not markup.cari("button")
    radio = markup.cari("input")
    assert len(radio) == 2
    assert all(r.get("type") == "radio" and r.get("name") == "periode-harga" for r in radio)
    assert {r["id"] for r in radio} == {"harga-bulanan", "harga-tahunan"}
    assert [r["id"] for r in radio if "checked" in r] == ["harga-bulanan"]
    assert {l["for"] for l in markup.cari("label")} == {r["id"] for r in radio}
    assert len(markup.cari("fieldset")) == len(markup.cari("legend")) == 1
    assert ':checked ~ .landing-paket-bulanan-st' in GAYA_STITCH
    assert ':checked ~ .landing-paket-tahunan-st' in GAYA_STITCH
    assert '.landing-periode-radio-st:focus-visible + .landing-periode-label-st' in GAYA_STITCH


def test_aksi_daftar_dan_masuk_tetap_tunggal(markup):
    href = [atribut.get("href") for atribut in markup.cari("a")]
    assert href.count("/daftar") == href.count("/masuk") == 1
    assert "/kebijakan-privasi" in href
    assert "/lupa-sandi" in href
    assert any(atribut.get("class") == "landing-lewati-st" for atribut in markup.cari("a"))


def test_aturan_editorial_hanya_mengenai_landing():
    """Cegah selector baru merembes ke form/halaman guru dan murid."""
    blok = GAYA_STITCH.split("/* ══ Landing editorial", 1)[1].split(
        "/* Halaman hasil murid", 1
    )[0]
    tanpa_komentar = re.sub(r"/\*.*?\*/", "", "/*" + blok, flags=re.S)
    for selector in re.findall(r"([^{}]+)\{", tanpa_komentar):
        if selector.strip().startswith("@media"):
            continue
        # Koma dalam :is() bukan pemisah selector tingkat atas.
        selector = re.sub(r":is\([^)]*\)", "", selector)
        assert all(bagian.strip().startswith(".landing-") for bagian in selector.split(","))
    assert "minmax(0, 1fr)" in blok
    assert ".landing-halaman-st :is(a, summary):focus-visible" in blok
    assert f"outline: 3px solid {T.AKSEN_TEAL_TUA}" in blok
    assert ".landing-faq-st details[open] summary::after" in blok


def test_css_landing_memakai_token_warna():
    sumber = (Path(__file__).resolve().parent.parent / "style_stitch.py").read_text()
    blok = sumber.split("/* ══ Landing editorial", 1)[1].split("/* Halaman hasil murid", 1)[0]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", blok)
    assert "background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}" in blok
