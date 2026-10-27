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
    assert "Pahami cara berpikir anak." in sumber
    assert "<span>Dampingi langkah berikutnya.</span>" in sumber
    daftar_id = [atribut["id"] for _, atribut in markup.elemen if "id" in atribut]
    assert len(daftar_id) == len(set(daftar_id))
    jangkar = [atribut["href"][1:] for atribut in markup.cari("a")
               if atribut.get("href", "").startswith("#")]
    assert set(jangkar) == {"konten", "cara-kerja", "contoh"}
    assert set(jangkar) <= set(daftar_id)
    for _, atribut in markup.elemen:
        if "aria-labelledby" in atribut:
            assert atribut["aria-labelledby"] in daftar_id


def test_status_akses_awal_ada_sebelum_faq_tanpa_menu_harga(markup):
    sumber = halaman_landing().decode()
    assert sumber.index('id="akses-awal"') < sumber.index('class="landing-faq-st"')
    nav = sumber.split('<nav ', 1)[1].split('</nav>', 1)[0]
    assert 'href="#harga"' not in nav and '>Harga</a>' not in nav
    assert any(atribut.get("id") == "akses-awal" and atribut.get("aria-labelledby") == "judul-akses-awal"
               for atribut in markup.cari("section"))


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
    assert len(markup.cari("details")) == len(markup.cari("summary")) == 8
    assert re.findall(r"<script>(.*?)</script>", sumber, re.S) == [
        SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA,
    ]
    assert not any(nama.startswith("on") for _, atribut in markup.elemen for nama in atribut)
    assert not markup.cari("button")
    assert not markup.cari("input")
    assert not markup.cari("fieldset") and not markup.cari("legend")


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


def _blok_landing():
    return GAYA_STITCH.split("/* ══ Landing editorial", 1)[1].split("/* Halaman hasil murid", 1)[0]


def _aturan(selector, css):
    """Isi blok selector tepat, termasuk deklarasi ulang di media query."""
    return re.findall(r"(?:^|\n)\s*" + re.escape(selector) + r"\s*\{([^{}]*)\}", css)


def _hero_teks():
    sumber = halaman_landing().decode()
    return sumber.split('class="landing-hero-teks-st"', 1)[1].split('class="landing-panggung-st"', 1)[0]


@pytest.mark.parametrize("selector, batas_em", [
    (".landing-judul-st", -0.04),
    (".landing-bagian-kepala-st h2, .landing-contoh-judul-st", -0.035),
])
def test_tracking_judul_tidak_menelan_spasi_antarkata(selector, batas_em):
    blok = _aturan(selector, _blok_landing())
    assert blok, selector
    tracking = re.search(r"letter-spacing:\s*(-?\d*\.?\d+)em", blok[0])
    assert float(tracking.group(1)) >= batas_em


def test_hero_cukup_satu_baris_status_dekat_cta():
    hero = _hero_teks()
    assert hero.count('class="landing-penawaran-st"') == 1
    assert hero.index("landing-cta-baris-st") < hero.index("landing-penawaran-st")
    teks = " ".join(re.sub(r"<[^>]+>", " ", hero).split())
    assert "Akses awal nonkomersial · pendaftaran tidak mengaktifkan paket atau pembayaran." in teks
    # Rincian status cukup di bagian #akses-awal dan FAQ.
    assert "Jago/Jago Pro sedang disiapkan" not in teks
    assert "Fokus utama" not in teks


def test_eyebrow_hero_tidak_memisahkan_jenjang():
    # Eyebrow memakai flex: teks sesudah ✳ harus satu item agar tidak terbelah kolom.
    assert ('<span>Pendampingan matematika · '
            '<span class="landing-jenjang-st">Kelas 3–6 SD</span></span>') in _hero_teks()
    assert "white-space: nowrap" in _aturan(".landing-jenjang-st", _blok_landing())[0]


def test_hp_menampilkan_demo_sebelum_paragraf_pengantar():
    hp = _blok_landing().split("@media (max-width: 40rem) {", 1)[1].split("\n}", 1)[0]
    assert "display: contents" in _aturan(".landing-hero-teks-st", hp)[0]
    urutan = {
        selector: int(re.search(r"order:\s*(\d+)", _aturan(selector, hp)[0]).group(1))
        for selector in (".landing-panggung-st", ".landing-sub-st")
    }
    assert urutan[".landing-panggung-st"] < urutan[".landing-sub-st"]


def test_nomor_soal_demo_sesuai_jumlah_latihan_pertama():
    sumber = halaman_landing().decode()
    jumlah = re.search(r"Latihan pertama berisi (\d+) soal", sumber).group(1)
    assert f"<span>Soal 4/{jumlah}</span>" in sumber


def test_blok_pendamping_tidak_lebih_menonjol_dari_alur_inti():
    blok = _blok_landing()
    pilot = "".join(re.findall(r"(?:^|\n)\s*\.landing-pilot-st[^{}]*\{([^{}]*)\}", blok))
    assert f"background: {T.TEKS_JUDUL}" not in pilot
    assert f"color: {T.TEKS_PUTIH}" not in pilot
    # Navy tetap satu aksen: kartu Cara kerja.
    assert f"background: {T.TEKS_JUDUL}" in _aturan(".landing-cara-st", blok)[0]


def test_css_landing_memakai_token_warna():
    sumber = (Path(__file__).resolve().parent.parent / "style_stitch.py").read_text()
    blok = sumber.split("/* ══ Landing editorial", 1)[1].split("/* Halaman hasil murid", 1)[0]
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", blok)
    assert "background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}" in blok
