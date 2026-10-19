"""Kontrak skala judul dewasa; ukuran anak dan kontrol tidak ikut mengecil."""

import re

import admin_style
import assistant_style
import design_tokens as T
import mastery_report
import report_dashboard
import style_stitch
import subscription_pages
import subscription_produksi_pages
import teacher_style


def _aturan(css, selector):
    hasil = re.findall(re.escape(selector) + r"\s*\{([^}]+)\}", css)
    assert hasil, selector
    return "\n".join(hasil)


def test_judul_dewasa_seragam_dan_override_hp_tidak_membesar():
    for css, selector in (
        (style_stitch.GAYA_STITCH, '.guru-sapaan-st h1'),
        (style_stitch.GAYA_STITCH, '.pendamping-editorial-st h1'),
        (assistant_style.GAYA_PENDAMPING, '.pendamping-halaman h1'),
    ):
        aturan = _aturan(css, selector)
        assert T.UKURAN_JUDUL_DEWASA in aturan
        assert all(T.UKURAN_JUDUL_DEWASA in deklarasi for deklarasi in
                   re.findall(r'font(?:-size)?:\s*([^;]+);', aturan))


def test_angka_ringkasan_dan_bagian_dewasa_memakai_token():
    for css, selector in (
        (mastery_report.GAYA_PETA, '.peta-materi-st .peta-angka'),
        (report_dashboard.GAYA_LAPORAN, '.laporan-editorial-st .laporan-metrik strong'),
        (teacher_style.GAYA_GURU, '.stat .angka-besar'),
        (subscription_pages.GAYA, '.langganan-panel .nominal'),
        (subscription_produksi_pages.GAYA, '.langganan-panel .nominal'),
    ):
        assert T.UKURAN_ANGKA_DEWASA in _aturan(css, selector)
    for selector in ('.guru-kepala-daftar-st h2', '.guru-kosong-st h2',
                     '.pendamping-editorial-st h2', '.profil-editorial-st #judul-rencana-belajar'):
        assert T.UKURAN_BAGIAN_DEWASA in _aturan(style_stitch.GAYA_STITCH, selector)


def test_skala_admin_scoped_tanpa_override_hp():
    for selector, token in (
        ('.admin-kepala h1', T.ADMIN_UKURAN_JUDUL),
        ('.admin-angka', T.ADMIN_UKURAN_KPI),
    ):
        aturan = _aturan(admin_style.GAYA_ADMIN, selector)
        assert 'font-size: ' + token in aturan
        assert all(nilai.strip() == token for nilai in re.findall(r'font-size:\s*([^;]+);', aturan))


def test_body_anak_dan_input_tetap_dengan_target_sentuh():
    css = style_stitch.GAYA_STITCH
    assert T.UKURAN_BADAN_LAYAR == '16px'
    assert 'font-size: 16px' in _aturan(css, 'body.st')
    assert '2.4rem' in _aturan(css, '.murid-sapaan-st h1')
    assert '2.65rem' in _aturan(css, '.murid-judul-sampul-st')
    assert 'font-size: 1rem' in _aturan(css, '.st-input')
    assert 'min-height: ' + T.TINGGI_KONTROL in _aturan(css, '.st-input')
    assert 'min-height: ' + T.TARGET_SENTUH in _aturan(admin_style.GAYA_ADMIN, '.admin-menu a')
    # Deklarasi baru hanya pada selector dewasa; jangan mengganti body/html global.
    for selector, aturan in re.findall(r'([^{}]+)\{([^{}]+)\}', css):
        if T.UKURAN_JUDUL_DEWASA in aturan:
            assert '.guru-sapaan-st h1' in selector or '.pendamping-editorial-st h1' in selector
