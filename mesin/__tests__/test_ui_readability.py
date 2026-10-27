"""Regresi keterbacaan/target audit lanjutan; tanpa data atau akses produksi."""
import re

import pytest

import account_style
import admin_style
import auth_http
import design_tokens as T
import landing
import style_stitch


TEKS = (
    '.landing-nav-st', '.landing-topbar-st .tombol-putih',
    '.landing-alis-st', '.landing-penawaran-st',
    '.landing-catatan-kertas-st', '.landing-demo-kepala-st',
    '.landing-demo-label-st', '.landing-kode-st', '.landing-demo-catatan-st',
    '.landing-demo-keterangan-st', '.landing-nomor-st',
    '.landing-contoh-kode-st', '.landing-resep-st', '.landing-footer-isi-st',
    '.masuk-beranda-st', '.masuk-alis-st', '.masuk-catatan-kecil-st',
    '.masuk-badan-st .masuk-field-st label', '.masuk-badan-st .masuk-petunjuk-st',
    '.masuk-badan-st .masuk-link-st a', '.masuk-badan-st .masuk-galat-st',
    '.murid-kepala-st button', '.murid-alis-st', '.murid-akun-hint-st',
    '.murid-label-utama-st', '.murid-tahap-st', '.murid-sub-sampul-st',
    '.murid-meta-st', '.murid-jumlah-st', 'body.st.murid-beranda-st .st-badge',
    'body.st.murid-beranda-st .st-progres-label', '.murid-aksi-st', '.murid-aman-st',
    '.murid-kepala-bagian-st > span', '.murid-riwayat-st summary span span',
    '.murid-kaki-st', '.kerja-btn-sekunder-st',
    '.daftar-editorial-st label', '.daftar-editorial-st .daftar-petunjuk-st',
    '.daftar-editorial-st .koreksi-centang-st', '.daftar-editorial-st .masuk-galat-st',
    '.daftar-alis-st', '.daftar-bawah-st', '.daftar-kaki-st',
    '.daftar-editorial-st .daftar-pengantar-st',
    '.daftar-editorial-st .daftar-langkah-st li > span',
    '.daftar-editorial-st .daftar-langkah-st b',
    '.daftar-editorial-st .daftar-langkah-st p',
    '.guru-kosong-st > p:not(.guru-alis-st)',
    '.dukungan-editorial-st .dukungan-topbar-catatan-st',
    '.dukungan-editorial-st .dukungan-alis-st',
    '.koreksi-editorial-st .editorial-alis-st',
)


def aturan(css, selector):
    """Blok selector tepat, termasuk deklarasi ulang pada media query."""
    pola = r'(?:^|\n)\s*' + re.escape(selector) + r'\s*\{([^{}]*)\}'
    return re.findall(pola, css)


@pytest.mark.parametrize('selector', TEKS)
def test_teks_informatif_memakai_batas_shared(selector):
    penuh = selector if selector.startswith('body') else 'body.st ' + selector
    blok = aturan(style_stitch.GAYA_STITCH, penuh)
    assert blok, selector
    assert f'font-size: {T.UKURAN_TEKS_LABEL}' in blok[-1]


def test_pemilih_foto_murid_memakai_ukuran_input():
    blok = aturan(style_stitch.GAYA_STITCH,
                  '.kerja-editorial-st .kerja-foto-form-st input[type=file]')[-1]
    assert f'font-size: {T.UKURAN_BADAN_LAYAR}' in blok


def test_css_keterbacaan_sampai_ke_halaman_publik():
    for html in (landing.halaman_landing(), auth_http.halaman_masuk()):
        assert style_stitch.GAYA_TEKS_MIN.encode() in html


@pytest.mark.parametrize('selector', [
    '.admin-brand small', '.admin-nav-badge', '.admin-tema > span',
    '.menu-isi .admin-tema-pilihan button',
    '.admin-meta, .admin-footer, .admin-kartu small', '.admin-bilah-skala',
    '.admin-tahap-hint', '.admin-cnt', '.admin-badge', '.admin-tabel th',
    '.admin-stat span', '.admin-alis', '.admin-urgensi', '.admin-ref',
    '.admin-antrean-catatan, .admin-antrean-kosong', '.admin-pil',
    '.riset-sesi-meta', '.riset-matriks q',
])
def test_teks_admin_informatif_minimal_label(selector):
    assert f'font-size: {T.UKURAN_TEKS_LABEL}' in aturan(admin_style.GAYA_ADMIN, selector)[-1]


@pytest.mark.parametrize('selector', [
    '.akun-editorial-st .akun-anak-login a',
    '.akun-editorial-st a[href="/kebijakan-privasi"]',
])
def test_tautan_akun_punya_area_sentuh(selector):
    blok = aturan(account_style.GAYA_AKUN, selector)
    assert blok
    assert f'min-height: {T.TARGET_SENTUH}' in blok[-1]
    assert 'display: inline-flex' in blok[-1]


@pytest.mark.parametrize('selector', [
    '.koreksi-editorial-st .koreksi-catatan-st a',
    '.koreksi-editorial-st .koreksi-centang-st label',
    '.koreksi-editorial-st .koreksi-persetujuan-st',
    '.koreksi-editorial-st .koreksi-lewati-native-st label',
])
def test_label_dan_tautan_tinjauan_punya_area_sentuh(selector):
    blok = aturan(style_stitch.GAYA_STITCH, selector)
    assert blok
    assert f'min-height: {T.TARGET_SENTUH}' in blok[-1]
    assert 'display: inline-flex' in blok[-1]


def test_tautan_nama_pendek_admin_tetap_lebar_sentuh():
    blok = aturan(admin_style.GAYA_ADMIN, '.admin-aktivitas a')[-1]
    assert f'min-width: {T.TARGET_SENTUH}' in blok


@pytest.mark.parametrize('selector', [
    '.daftar-editorial-st .koreksi-centang-st a',
    '.dukungan-editorial-st .publik-kartu-st a',
])
def test_tautan_legal_terjangkau(selector):
    blok = aturan(style_stitch.GAYA_STITCH, selector)
    assert blok and f'min-height: {T.TARGET_SENTUH}' in blok[-1]


def test_tautan_pendamping_pendek_tetap_lebar_sentuh():
    blok = aturan(account_style.GAYA_AKUN, '.akun-editorial-st .akun-tautan-st')[-1]
    assert f'min-width: {T.TARGET_SENTUH}' in blok
