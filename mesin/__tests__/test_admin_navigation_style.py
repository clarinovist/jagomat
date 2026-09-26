"""Regresi palet hangat dan hierarki navigasi admin, tanpa data nyata."""

from html.parser import HTMLParser
import re

import pytest

import admin_pages as P
import admin_style
import design_tokens as T


def _aturan(selector):
    pola = r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]+)\}"
    cocok = re.search(pola, admin_style.GAYA_ADMIN)
    assert cocok, selector
    return cocok.group(1)


class _Navigasi(HTMLParser):
    def __init__(self):
        super().__init__()
        self.kedalaman = 0
        self.kedalaman_maksimal = 0
        self.tautan = []
        self.grup = []

    def handle_starttag(self, tag, attrs):
        atribut = dict(attrs)
        if tag == "ul":
            self.kedalaman += 1
            self.kedalaman_maksimal = max(self.kedalaman_maksimal, self.kedalaman)
            if "admin-nav-anak" in atribut.get("class", ""):
                self.grup.append(atribut.get("aria-label"))
        if tag == "a":
            self.tautan.append((atribut["href"], atribut.get("aria-current")))

    def handle_endtag(self, tag):
        if tag == "ul":
            self.kedalaman -= 1


@pytest.mark.parametrize("section", [item[0] for item in P.SECTION])
def test_grup_dan_anak_semantik_dengan_satu_halaman_aktif(section):
    html = P.halaman_admin(section, "", pengguna="Pengelola Contoh").decode()
    navigasi = re.findall(r"<nav\b[^>]*>(.*?)</nav>", html, flags=re.S)
    assert len(navigasi) == 2
    for nav in navigasi:
        parser = _Navigasi()
        parser.feed(nav)
        assert parser.kedalaman_maksimal == 2
        assert parser.grup == ["Data pengguna", "Layanan", "Analitik", "Sistem"]
        assert len(parser.tautan) == len(P.SECTION)
        assert {href for href, _ in parser.tautan} == {href for _, _, href in P.SECTION}
        assert [href for href, aktif in parser.tautan if aktif == "page"] == [
            href for sid, _, href in P.SECTION if sid == section
        ]
        assert 'admin-nav-utama' in nav
        assert 'Menu utama' in nav
    assert '<script' not in html


def test_permukaan_admin_memakai_token_latar_bukan_token_teks():
    assert "background: " + T.LATAR_KARTU_MURID in _aturan(".admin-sidebar")
    assert "background: " + T.LATAR_KARTU_MURID in _aturan(".admin-kartu.admin-prioritas")
    assert "background: " + T.LATAR_CATATAN in _aturan(".admin-prioritas-kepala")
    assert "background: " + T.LATAR_KARTU_MURID in _aturan(".admin-nav-mobile > nav")
    for token in ("TEKS_JUDUL", "TEKS_VARIAN", "BORDER_VARIAN"):
        assert not re.search(r"background:\s*" + re.escape(getattr(T, token)) + r"[;}]", admin_style.GAYA_ADMIN)


def test_anak_menjorok_dan_aktif_punya_penanda_nonwarna():
    anak = _aturan(".admin-nav-anak")
    assert "margin-left: " + T.SP_3 in anak
    assert "border-left: 1px solid " + T.BORDER_VARIAN in anak
    assert 'font-weight: 800' in _aturan('.admin-menu a[aria-current="page"]')
    assert 'border-left-color: ' + T.AKSEN_TEAL_TUA in _aturan('.admin-menu a[aria-current="page"]')
    assert 'font-size: .875rem' in _aturan('.admin-nav-label')


def test_menu_hp_dapat_digulir_dan_tidak_tergantung_hover():
    menu = _aturan('.admin-nav-mobile > nav')
    assert 'max-height: calc(100vh - 8rem)' in menu
    assert 'max-height: calc(100dvh - 8rem)' in menu
    assert 'overflow-y: auto' in menu
    assert 'overscroll-behavior: contain' in menu
    html = P.halaman_admin('siswa', '', pengguna='Pengelola Contoh').decode()
    assert '<details class="admin-nav-mobile"><summary>' in html
    assert 'class="admin-menu" aria-label="Bagian panel pengelola seluler"' in html
