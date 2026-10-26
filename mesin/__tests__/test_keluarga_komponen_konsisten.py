"""Halaman keluarga mengikuti acuan komponen yang sama dengan admin: tombol 10px, nav = Tab."""
import re

import account_pages
import account_style
import database
import design_tokens as T
import profile_workspace
import question_variants_ui
import style_stitch

SEDANG = r'border-radius:\s*' + re.escape(T.RADIUS_SEDANG)
KECIL = r'border-radius:\s*' + re.escape(T.RADIUS_KECIL)

# Kontrol tombol keluarga (tombol, tautan bergaya tombol, summary Kelola) — bukan catatan/input/menu.
TOMBOL = {
    'stitch': (style_stitch.GAYA_STITCH, (
        '.pendamping-editorial-st :is(button, .btn, .st-tombol-coral, .rencana-cta-utama-st)',
        '.guru-tambah-st',
        '.profil-editorial-st .aksi-bagikan-st button',
        '.kerja-editorial-st input[type=file]::file-selector-button',
    )),
    'sesi': (style_stitch.CSS_SESI, ('.btn-st',)),
    'akun': (account_style.GAYA_AKUN, (
        '.akun-editorial-st .akun-aksi-kepala-st .akun-form-keluar button',
        '.akun-editorial-st .akun-tombol-garis-st',
        '.akun-editorial-st .akun-kelola > summary',
        '.akun-editorial-st a.tombol',
        '.akun-editorial-st .tombol-bahaya-akun',
    )),
    'profil': (profile_workspace.GAYA_PROFIL, (
        '.profil-workspace-st .profil-pager-st > *',
        '.profil-workspace-st .riwayat-aksi-st > .riwayat-buka-st',
    )),
    'variasi': (question_variants_ui.GAYA_VARIASI, ('.profil-workspace-st .variasi-bandingkan',)),
}

NAV_AKUN = '.akun-editorial-st .nav-samping'
NAV_SESI = '.pendamping-editorial-st :is(.pil-sesi, .pil-sesi-st)'


def _aturan(css, selector):
    cocok = re.findall(r'(?:^|\n)\s*' + re.escape(selector) + r'\s*\{([^{}]+)\}', css)
    assert cocok, selector
    return ' '.join(cocok)


def test_tombol_keluarga_beradius_kontrol_bersama():
    for nama, (css, daftar) in TOMBOL.items():
        for selector in daftar:
            aturan = _aturan(css, selector)
            assert re.search(SEDANG, aturan), (nama, selector, aturan)
            assert not re.search(KECIL, aturan), (nama, selector)


def test_hover_tombol_garis_keluarga_berlatar_aksen_seperti_admin():
    assert T.ADMIN_AKSEN_LATAR_CERAH == T.ANAK_AKSEN_LATAR
    for css, selector in ((style_stitch.GAYA_STITCH, '.guru-tambah-st:hover'),
                          (account_style.GAYA_AKUN, '.akun-editorial-st .akun-aksi-kepala-st .akun-form-keluar button:hover'),
                          (account_style.GAYA_AKUN, '.akun-editorial-st .akun-tombol-garis-st:hover'),
                          (account_style.GAYA_AKUN, '.akun-editorial-st .akun-kelola > summary:hover')):
        assert 'background: ' + T.ANAK_AKSEN_LATAR in _aturan(css, selector), selector


def _tab(css, wadah):
    pasif = _aturan(css, wadah + ' a')
    assert 'border-bottom: 3px solid transparent' in pasif, wadah
    assert 'min-height: ' + T.TINGGI_KONTROL in pasif, wadah
    assert 'color: ' + T.TEKS_VARIAN in pasif, wadah
    assert 'border-radius: 0' in pasif and 'background: transparent' in pasif, wadah
    aktif = _aturan(css, wadah + ' a[aria-current="page"]')
    assert 'color: ' + T.AKSEN_TEAL_TUA in aktif and 'border-bottom-color: ' + T.AKSEN_TEAL_TUA in aktif, wadah
    assert 'background: transparent' in aktif and 'font-weight: 700' in aktif, wadah
    baris = _aturan(css, wadah)
    assert 'flex-wrap: wrap' in baris and 'overflow-x' not in baris, wadah
    assert 'border-bottom: 1px solid ' + T.ANAK_BORDER in baris, wadah  # garis tab profil/admin


def test_navigasi_akun_dan_alat_sesi_berpola_tab_bukan_blok():
    css = style_stitch.GAYA_STITCH
    _tab(css, NAV_AKUN)
    _tab(css, NAV_SESI)
    _tab(style_stitch.CSS_SESI, '.pil-sesi-st')  # dasar di luar wrapper editorial
    for daftar, isi in re.findall(r'([^{}]+)\{([^{}]+)\}', css + style_stitch.CSS_SESI):
        if 'nav-samping' in daftar or 'pil-sesi' in daftar:
            assert 'background: ' + T.AKSEN_TEAL_TUA not in isi, daftar.strip()


def test_navigasi_akun_satu_halaman_aktif_dan_tetap_baris(tmp_path):
    jalur = tmp_path / 'uji.db'
    database.siapkan(jalur)
    with database.buka(jalur) as kon:
        isi = account_pages.halaman_akun(kon, pengguna='guru-uji', section='siswa').decode()
    nav = re.search(r'<nav class="nav-samping" aria-label="Pengaturan akun">(.*?)</nav>', isi, re.S).group(1)
    assert nav.count('aria-current="page"') == 1
    assert re.search(r'<a href="/akun\?section=siswa"[^>]*aria-current="page">Anak</a>', nav)
    baris = _aturan(style_stitch.GAYA_STITCH, NAV_AKUN)
    assert 'position: static' in baris and 'flex-direction: row' in baris
