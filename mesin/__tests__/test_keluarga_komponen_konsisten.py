"""Halaman keluarga mengikuti acuan komponen yang sama dengan admin: tombol 10px, nav = Tab."""
import re

import account_pages
import account_style
import attachments
import child_beranda_style
import child_latihan_style
import child_ringkasan_style
import child_style
import database
import design_tokens as T
import profile_workspace
import question_variants_ui
import report_dashboard
import style_stitch
import subscription_style
import teacher_style

SEDANG = r'border-radius:\s*' + re.escape(T.RADIUS_SEDANG)
KECIL = r'border-radius:\s*' + re.escape(T.RADIUS_KECIL)
KARTU = r'border-radius:\s*' + re.escape(T.RADIUS_KARTU)

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
    # Sisa penyimpangan yang dicatat 26 Okt 2026 (CTA 12px literal, Keluar murid tanpa radius).
    'beranda': (child_beranda_style.GAYA_BERANDA, (
        '.bungkus-st.profil-workspace-st.beranda-profil-st .beranda-aksi-st .rencana-cta-utama-st',)),
    'latihan': (child_latihan_style.GAYA_LATIHAN, ('.bungkus-st.profil-workspace-st .latihan-aksi-st button',)),
    'murid': (style_stitch.GAYA_STITCH, ('.murid-tombol-utama-st', '.kerja-topbar-st .cta-keluar')),
    # Sisa 1 Nov 2026: tombol dasar GAYA_GURU (9px/8px/6px), Langganan (8px), lampiran (9px).
    'guru-dasar': (teacher_style.GAYA_GURU, ('button', '.btn', 'button.tombol-kecil')),
    'langganan': (subscription_style.GAYA_LANGGANAN, ('.langganan-panel button,.langganan-panel .tombol',)),
    'lampiran': (attachments.GAYA_KONFIRMASI, ('button',)),
}

# Input/select keluarga: radius kontrol bersama, bukan campuran 8px/12px. `.input-sandi-kecil`
# sengaja tetap RADIUS_KECIL (input kecil menurut tabel radius).
INPUT = {
    # Aturan dasar shell editorial menang spesifisitas atas aturan input tersekop lain.
    'editorial-dasar': (style_stitch.GAYA_STITCH, re.escape(
        '.pendamping-editorial-st :is(input:not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea)')),
    'guru-dasar': (teacher_style.GAYA_GURU, r'input\[type=text\], input\[type=password\], input\[type=number\], '
                   r'input\[type=file\],\s*textarea, select'),
    'profil-filter': (profile_workspace.GAYA_PROFIL, re.escape(
        '.profil-workspace-st .profil-filter-st input,.profil-workspace-st .profil-filter-st select')),
    'latihan-select': (child_latihan_style.GAYA_LATIHAN, re.escape(
        '.bungkus-st.profil-workspace-st.pendamping-editorial-st .latihan-terpadu-st select')),
}
NAV_LAPORAN = '.laporan-editorial-st .laporan-navigasi'

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


def test_input_keluarga_beradius_kontrol_bersama():
    for nama, (css, pola) in INPUT.items():
        cocok = re.findall(r'(?:^|\n)\s*' + pola + r'\s*\{([^{}]+)\}', css)
        assert cocok, nama
        aturan = ' '.join(cocok)
        assert re.search(SEDANG, aturan) and not re.search(KECIL, aturan), (nama, aturan)
        assert not re.search(r'border-radius:\s*12px', aturan), nama


def test_banner_profil_beradius_kartu():
    for css, selector in ((child_style.GAYA_ANAK, '.anak-banner-st'),
                          (child_ringkasan_style.GAYA_RINGKASAN,
                           '.bungkus-st.profil-workspace-st .laporan-ke-beranda.anak-banner-st')):
        aturan = _aturan(css, selector)
        assert re.search(KARTU, aturan) and not re.search(r'border-radius:\s*14px', aturan), (selector, aturan)


def test_pemilih_ringkasan_per_materi_beradius_kontrol_bersama():
    # Sakelar segmen (mockup Perkembangan 19 Okt), sengaja beda dari tab profil di atasnya;
    # yang menyimpang hanya sudut 8px. Pola tenang dijaga test_laporan_ortu.
    for selector in (NAV_LAPORAN + ' a', NAV_LAPORAN + ' a[aria-current="page"]'):
        assert not re.search(KECIL, _aturan(report_dashboard.GAYA_LAPORAN, selector)), selector
    assert re.search(SEDANG, _aturan(report_dashboard.GAYA_LAPORAN, NAV_LAPORAN + ' a'))


def test_label_centang_filter_profil_setinggi_target_sentuh():
    # Checkbox "belum mengenal tugas" di Latihan berlabel 25px (desktop) / 43px (390px) sebelum 1 Nov 2026.
    aturan = _aturan(profile_workspace.GAYA_PROFIL,
                     '.profil-workspace-st .profil-filter-st label:has(> input[type=checkbox])')
    assert 'min-height:' + T.TARGET_SENTUH in aturan.replace(' ', ''), aturan
    assert 'align-items:center' in aturan.replace(' ', ''), aturan
