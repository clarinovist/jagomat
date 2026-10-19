"""Regresi navigasi datar, token scoped dan aksesibilitas admin sintetis."""
import re
import pytest
import admin_pages as P
import admin_style
import design_tokens as T


def _aturan(selector):
    cocok = re.search(r'(?:^|\n)' + re.escape(selector) + r'\s*\{([^}]+)\}', admin_style.GAYA_ADMIN)
    assert cocok, selector
    return cocok.group(1)


@pytest.mark.parametrize('section', [item[0] for item in P.SECTION])
def test_menu_datar_dua_permukaan_satu_aktif(section):
    html = P.halaman_admin(section, '', pengguna='Pengelola Contoh').decode()
    navs = re.findall(r'<nav\b[^>]*>(.*?)</nav>', html, re.S)
    assert len(navs) == 2
    for nav in navs:
        assert '<details' not in nav
        assert nav.count('aria-current="page"') == 1
        assert {href for href in re.findall(r'href="([^"]+)"', nav)} == {href for sid, _, href in P.SECTION if sid != 'perhatian'}
        for label in ('Pengguna', 'Layanan', 'Analitik', 'Sistem'):
            assert '<p class="admin-nav-label">%s</p>' % label in nav
    assert html.count('Tampilan privat · Data operasional') == 1
    assert '<script' not in html
    assert 'Lewati navigasi' in html


def test_permukaan_admin_memakai_token_scoped():
    for selector in ('.admin-sidebar', '.admin-kartu.admin-prioritas', '.admin-nav-mobile > nav'):
        assert 'background: ' + T.ADMIN_PERMUKAAN in _aturan(selector)
    assert 'font-weight: 600' in _aturan('.admin-menu a[aria-current="page"]')
    assert 'background: ' + T.ADMIN_AKSEN_LATAR in _aturan('.admin-menu a[aria-current="page"]')
    assert 'font-size: 12px' in _aturan('.admin-nav-label')
    assert 'white-space: nowrap' in _aturan('.admin-tabel th')


def test_menu_hp_disclosure_dapat_digulir():
    menu = _aturan('.admin-nav-mobile > nav')
    for isi in ('max-height: calc(100vh - 8rem)', 'max-height: calc(100dvh - 8rem)', 'overflow-y: auto', 'overscroll-behavior: contain'):
        assert isi in menu
    html = P.halaman_admin('siswa', '', pengguna='Pengelola Contoh').decode()
    assert '<details class="admin-nav-mobile"><summary>' in html
    assert 'aria-label="Bagian panel pengelola seluler"' in html
    assert '@media (prefers-reduced-motion: reduce)' in admin_style.GAYA_ADMIN
