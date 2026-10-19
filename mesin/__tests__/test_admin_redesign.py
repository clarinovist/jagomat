"""Kontrak presentasi redesain, menggunakan DTO dan nilai sintetis saja."""
from dataclasses import replace
from datetime import datetime
from urllib.parse import urlsplit, parse_qs
from html.parser import HTMLParser

import admin_labels as L
import admin_pages as P
import admin_queries as Q
from test_admin_pages import _ringkasan, _keluarga, _siswa


class Tautan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.append(dict(attrs).get('href', ''))


def test_aktivitas_hanya_mengelompokkan_berurutan_dengan_hari_status_sama():
    a = _ringkasan().aktivitas_terbaru[0]
    items = (a, replace(a, sesi_id=8, waktu_aktivitas='2026-09-13 08:00:00'), replace(a, sesi_id=7, dibatalkan=True), replace(a, sesi_id=6, waktu_aktivitas='2026-09-12 09:00:00'))
    isi = P._aktivitas_ringkasan(items)
    assert isi.count('<li class="admin-aktivitas-baris">') == 3
    assert '2 sesi' in isi and 'Dibatalkan' in isi
    for n in (9, 8, 7, 6):
        assert 'href="/sesi/%d"' % n in isi
    assert 'Ari &lt;b&gt;' in isi
    assert '2026-09-' not in isi


def test_tanggal_wib_eksplisit_dan_umur_tidak_direka():
    assert L.tanggal('2026-10-02 15:51:00') == '2 Okt 2026, 15.51 WIB'
    assert L.tanggal('2026-10-02T23:51:00Z') == '3 Okt 2026, 06.51 WIB'
    assert L.tanggal('tidak-sah') == L.tanggal(None) == '—'
    assert L.hari_ini(datetime(2026, 10, 19, tzinfo=L.WIB)) == 'Senin, 19 Oktober 2026'


def test_chip_tidak_membocorkan_pencarian_dan_mempertahankan_filter_lain():
    data = replace(_siswa(), tingkat='P4', keluarga_id='akun_demo', total=126)
    isi = P.render_siswa(data, (), csrf='sintetis')
    parser = Tautan(); parser.feed(isi)
    chips = [parse_qs(urlsplit(h).query) for h in parser.hrefs if 'tingkat=' in h]
    assert chips
    assert all(c['tingkat'] == ['P4'] and c['keluarga_id'] == ['akun_demo'] for c in chips)
    assert 'Semua · 126' in isi
    cari = P.render_siswa(replace(data, cari='Nama Rahasia'), (), csrf='sintetis')
    parser = Tautan(); parser.feed(cari)
    assert all('Rahasia' not in href and 'cari=' not in href for href in parser.hrefs)
    assert 'Filter lanjutan' in cari and 'method="post"' in cari


def test_rute_perhatian_tetap_dikenali_tetapi_menu_tidak_ganda():
    isi = P.halaman_admin('perhatian', '', pengguna='Demo').decode()
    assert '<h1 id="judul-admin">Perlu ditangani</h1>' in isi
    assert 'href="/admin?section=perhatian"' not in isi
    assert isi.count('href="/admin" aria-current="page"') == 2


def test_id_panjang_tetap_dapat_disalin_utuh_untuk_filter():
    import re
    from admin_contracts import validasi_id
    identitas = 'akun_' + 'a' * 32
    markup = L.referensi(identitas)
    teks = re.sub('<[^>]+>', '', markup)
    assert teks == identitas and '…' not in teks
    validasi_id(teks, 'akun')


def test_login_warisan_tidak_dinyatakan_tanpa_akses():
    data = _siswa()
    item = replace(data.item[0], status=('student_without_login', 'legacy_login_unverified'))
    isi = P.render_siswa(replace(data, item=(item,)), (), csrf='sintetis')
    assert 'Belum ada login tertaut' in isi
    assert 'Akun lama yang belum tertaut mungkin masih bisa masuk' in isi
    assert 'Login lama belum terverifikasi' in isi
    assert 'Belum punya login<' not in isi


def test_hover_bahaya_mempertahankan_kontras():
    import admin_style
    import design_tokens as T
    aturan = admin_style.GAYA_ADMIN.split('.admin-tautan.admin-bahaya:hover, .admin-tombol.admin-bahaya:hover {', 1)[1].split('}', 1)[0]
    assert 'background: ' + T.ADMIN_BAHAYA_TEKS in aturan
    assert 'color: ' + T.ADMIN_PERMUKAAN in aturan
