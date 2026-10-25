"""Regresi audit UI lintas halaman; seluruh identitas dan data sintetis."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from types import SimpleNamespace

import pytest

import account_pages
import admin_pages
import admin_research_pages
import admin_style
import assistant_components
import assistant_inline
import child_header
import child_latihan_style
import child_style
import competitive_research
import database
import design_tokens as T
import landing
import reports
import research_instrument
import style_stitch
import subscription_produksi_pages
import teacher_pages
import teacher_shell
from test_child_shared_layout import _lebar_efektif, LEBAR_ISI
from test_review_layout import sesi_contoh
from test_ai_pages_markup import render as render_ai


@pytest.fixture
def db(tmp_path, monkeypatch):
    import auth
    path = tmp_path / 'ui-sintetis.db'
    database.siapkan(path)
    monkeypatch.setattr(database, 'BAWAAN', path)
    monkeypatch.setattr(auth, 'BERKAS_SANDI', tmp_path / 'auth-sintetis.json')
    with database.buka(path) as kon:
        yield kon


class Markup(HTMLParser):
    def __init__(self, isi):
        super().__init__()
        self.tags = []
        self.label = None
        self.labels = []
        self.feed(isi)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if tag == 'label':
            self.label = [[], []]
        if tag == 'input' and self.label is not None:
            self.label[0].append(a)

    def handle_data(self, teks):
        if self.label is not None:
            self.label[1].append(teks)

    def handle_endtag(self, tag):
        if tag == 'label' and self.label is not None:
            self.labels.append((self.label[0], ''.join(self.label[1]).strip()))
            self.label = None


def _aturan(css, selector):
    return re.search(r'(?:^|\n)' + re.escape(selector) + r'\s*\{([^}]*)\}', css).group(1)


@pytest.mark.parametrize('section', ['akun', 'siswa', 'langganan', 'arsip-pendamping'])
@pytest.mark.parametrize('peran', ['guru', 'admin'])
def test_akun_satu_keluar_seluruh_body(db, section, peran):
    body = account_pages.halaman_akun(db, pengguna='guru-demo', peran=peran, section=section).decode()
    forms = [a for t, a in Markup(body).tags if t == 'form' and a.get('action') == '/keluar']
    assert len(forms) == 1
    assert forms[0].get('class') == 'akun-form-keluar'
    assert 'action="/keluar"' in teacher_shell._topbar_stitch('guru-demo', peran)


@pytest.mark.parametrize('belum_tersedia', [False, True])
def test_pendaftaran_tutup_satu_tujuan_masuk(belum_tersedia):
    h = landing.halaman_daftar(pendaftaran_dibuka=False, belum_tersedia=belum_tersedia).decode()
    assert h.count('href="/masuk"') == 1


@pytest.mark.parametrize('section', ['ringkasan', 'penguasaan', 'perjalanan'])
def test_laporan_lama_memakai_shell_profil_tanpa_mengubah_bukti(db, section):
    sid = database.tambah_siswa(db, 'Anak <Demo>', pemilik='guru')
    awal = tuple(db.iterdump())
    h = reports.halaman_laporan(db, sid, pengguna='guru', section=section).decode()
    assert _lebar_efektif(h) == LEBAR_ISI
    assert 'anak-header-st' in h.split('<body', 1)[1]
    assert 'class="anak-avatar-st"' in h
    assert h.count('<main ') == 1
    assert 'fonts.googleapis.com' not in h
    assert 'aria-labelledby="judul-profil-laporan"' in h
    assert f'href="/anak/{sid}?section=perkembangan" aria-current="page"' in h
    assert tuple(db.iterdump()) == awal
    admin = reports.halaman_laporan(db, sid, pengguna='admin-demo', peran='admin').decode()
    assert 'class="anak-avatar-st"' not in admin and 'href="/admin"' in admin


@pytest.mark.parametrize('query', [
    'bagian=penguasaan&rincian=catatan', 'rincian=tren', 'tampilan=tugas',
])
def test_css_rincian_laporan_tetap_ada_pada_kedua_url(db, query):
    sid = database.tambah_siswa(db, 'Anak Rincian', pemilik='guru')
    siswa = db.execute('SELECT * FROM siswa WHERE id=?', (sid,)).fetchone()
    for h in (
        reports.halaman_laporan(db, sid, pengguna='guru', query=query).decode(),
        teacher_pages.halaman_anak(db, siswa, pengguna='guru', query='section=perkembangan&'+query).decode(),
    ):
        assert '.sr-only {' in h and '.diagnosis-lis {' in h and '.dot.kuat {' in h
        assert '.kartu-st {' in h and '.tabel-tren td::before {' in h
        assert '.st-topbar, .koreksi-simpan-st' in h
        assert _lebar_efektif(h) == LEBAR_ISI
        assert 'fonts.googleapis.com' not in h


def test_laporan_admin_import_font_tetap_di_awal_stylesheet(db):
    sid = database.tambah_siswa(db, 'Anak Admin', pemilik='guru')
    h = reports.halaman_laporan(db, sid, pengguna='admin-demo', peran='admin').decode()
    blok = re.findall(r'<style>(.*?)</style>', h, re.S)
    font = next(css for css in blok if '@import' in css)
    tanpa_komentar = re.sub(r'/\*.*?\*/', '', font, flags=re.S).lstrip()
    assert tanpa_komentar.startswith('@import')
    assert '.laporan-editorial-st .st-topbar' in h


@pytest.mark.parametrize('status', ['batal', 'selesai', 'riwayat'])
def test_status_sesi_privat_memakai_svg_lokal(db, status):
    sesi, ids = sesi_contoh(db)
    if status == 'batal':
        database.batalkan_sesi(db, sesi, 'Uji UI')
    elif status == 'selesai':
        database.konfirmasi_hasil(db, sesi, guru='guru', dilewati=set(ids))
    else:
        sid = db.execute('SELECT siswa_id FROM sesi WHERE id=?', (sesi,)).fetchone()[0]
        putaran = database.buat_putaran_fokus(db, sid, 'P3')
        db.execute("UPDATE sesi SET tujuan='penguatan', putaran_id=?, selesai=NULL WHERE id=?", (putaran, sesi))
        db.execute("UPDATE siswa SET tingkat='P4' WHERE id=?", (sid,))
    awal = tuple(db.iterdump())
    h = teacher_pages.halaman_sesi_stitch(db, sesi, pengguna='guru').decode()
    status_html = h.split('<div class="status-sesi-st', 1)[1].split('</svg>', 1)[0]
    assert '<svg class="ikon-status-sesi-st"' in status_html
    assert 'aria-hidden="true" focusable="false"' in status_html
    assert not re.search(r'>(task_alt|cancel|history)</span>', h)
    assert tuple(db.iterdump()) == awal


@pytest.mark.parametrize('readonly', [False, True])
def test_kode_riset_mempunyai_nama_opsi_pada_setiap_kontrol(readonly):
    detail = dict(id='sintetis', instrumen=research_instrument.snapshot(), jawaban={}, revisi=0)
    h = admin_research_pages.formulir_pertanyaan(detail, 'Q1', csrf='sintetis', token='sintetis', readonly=readonly)
    labels = research_instrument.label_kode(detail['instrumen'])
    controls = [(a, teks) for champs, teks in Markup(h).labels for a in champs
                if a.get('name') in ('kode_utama', 'kode_tambahan')]
    assert len(controls) >= 4
    for a, teks in controls:
        assert labels[a['value']] in teks
        assert ('disabled' in a) == readonly
    assert len({teks for _, teks in controls}) == len(controls)


def test_area_tabel_ai_dan_daftar_bisa_difokuskan(render_ai):
    from admin_daftar_pages import kartu_tabel
    for h in (render_ai(), kartu_tabel('Daftar sintetis', ('<th>Nama</th>',), '<tr><td>Demo</td></tr>', '')):
        if isinstance(h, bytes):
            h = h.decode()
        wrappers = [a for t, a in Markup(h).tags if t == 'div' and 'admin-tabel-wrap' in a.get('class', '').split()]
        assert wrappers
        for a in wrappers:
            assert a.get('tabindex') == '0' and a.get('role') == 'region'
            assert a.get('aria-label')


def test_area_tabel_persaingan_bisa_difokuskan():
    h = competitive_research.halaman().decode()
    wrapper = next(a for t, a in Markup(h).tags if a.get('class') == 'riset-tabel-bungkus')
    assert wrapper.get('tabindex') == '0' and wrapper.get('role') == 'region'
    assert wrapper.get('aria-label')


def test_waktu_isi_ulang_mudah_dibaca_dalam_wib():
    saat = int(datetime(2026, 10, 24, 18, 30, tzinfo=timezone.utc).timestamp())
    def render(waktu):
        return assistant_components.panel_akses(assistant_inline.tujuan_anak(1),
            SimpleNamespace(status='kuota_habis', limit=10, digunakan=10, isi_ulang=waktu))
    h = render(saat)
    assert '25 Okt 2026, 01.30 WIB' in h and str(saat) not in h
    assert 'Kuota berikutnya' not in render(None)


def test_langganan_kosong_mengarahkan_ke_tab_anak():
    h = subscription_produksi_pages.isi_ringkasan([], None, '', merchant={}, aktif=False)
    assert 'tab Anak' in h and 'href="/akun?section=siswa"' in h
    assert 'menu Siswa' not in h and '<form' not in h


def test_kontrol_teks_tidak_mewarisi_label_kecil():
    selector = '.pendamping-editorial-st :is(input:not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea)'
    assert f'font-size: {T.UKURAN_BADAN_LAYAR}' in _aturan(style_stitch.GAYA_STITCH, selector)
    assert f'font-size: {T.UKURAN_BADAN_LAYAR}' in _aturan(admin_style.GAYA_ADMIN, 'input, select, textarea')
    assert T.AKSEN_KORAL_TUA in _aturan(style_stitch.GAYA_STITCH, '.st-topbar .cta')


def test_grid_dan_select_latihan_tidak_kalah_aturan_lama():
    selector = child_latihan_style._R + '.pendamping-editorial-st .latihan-terpadu-st select'
    # Batas kontrol profil disatukan ke BORDER_KONTROL (25 Okt 2026, >=3:1).
    assert T.BORDER_KONTROL in _aturan(child_latihan_style.GAYA_LATIHAN, selector)
    assert 'minmax(min(100%, 16.25rem), 1fr)' in child_latihan_style.GAYA_LATIHAN
    assert 'minmax(min(100%,14rem),1fr)' in admin_style.GAYA_ADMIN


def test_pil_dan_teks_meta_memakai_token_shared():
    from child_history_style import GAYA_RIWAYAT
    from profile_workspace import GAYA_PROFIL
    assert T.ANAK_TEKS_REDUP in _aturan(child_style.GAYA_ANAK, '.profil-workspace-st .anak-pil-st')
    assert 'padding-inline: calc(' in _aturan(child_style.GAYA_ANAK, '.profil-workspace-st .anak-pil-st[aria-current="true"]')
    assert f'font-size: {T.UKURAN_TEKS_LABEL}' in _aturan(GAYA_RIWAYAT, '.bungkus-st.profil-workspace-st .riwayat-ringkas-st .riwayat-kartu-kepala-st small')
    assert f'font-size:{T.UKURAN_TEKS_META}' not in _aturan(GAYA_PROFIL, '.beranda-profil-st .beranda-posisi-st .tahap-rencana-st')


def test_target_tema_consent_dan_tab_mobile():
    assert f'min-height: {T.TARGET_SENTUH}' in _aturan(admin_style.GAYA_ADMIN, '.menu-isi .admin-tema-pilihan button')
    assert f'min-height: {T.TARGET_SENTUH}' in _aturan(admin_style.GAYA_ADMIN, '.admin-kartu .riset-persetujuan label:has(input[type=checkbox])')
    hp = child_header.GAYA_HEADER_ANAK.split('@media (max-width: 36rem)', 1)[1]
    assert f'padding-inline: {T.SP_1}; font-size: {T.UKURAN_TEKS_LABEL}' in hp
