"""Admin adalah varian layout dari fondasi Jagomat, bukan palet/skala baru."""
import ast
from pathlib import Path
import re

import admin_pages as P
import admin_style
import brand
import design_tokens as T
from test_admin_pages import _keluarga

ROOT = Path(__file__).resolve().parent.parent


def _aturan(selector):
    cocok = re.search(r'(?:^|\n)' + re.escape(selector) + r'\s*\{([^}]+)\}', admin_style.GAYA_ADMIN)
    assert cocok, selector
    return cocok.group(1)


def test_seluruh_warna_admin_terang_adalah_alias_token_bersama():
    tree = ast.parse((ROOT / 'design_tokens.py').read_text())
    alias = {n.targets[0].id: n.value for n in tree.body
             if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id.startswith('ADMIN_') and n.targets[0].id.endswith('_CERAH')}
    assert len(alias) >= 31
    for nama, nilai in alias.items():
        assert isinstance(nilai, ast.Name), nama
        assert not nilai.id.startswith('ADMIN_'), nama
    assert T.ADMIN_LATAR_CERAH == T.LATAR_MURID
    assert T.ADMIN_AKSEN_CERAH == T.AKSEN_TEAL_TUA
    assert T.ADMIN_BORDER_KUAT_CERAH == T.BORDER_KONTROL


def test_admin_tidak_memiliki_skala_tipe_radius_sendiri():
    assert not [n for n in vars(T) if n.startswith(('ADMIN_UKURAN_', 'ADMIN_RADIUS'))]
    for selector, deklarasi in (
        ('body.admin-readonly', 'font-size: ' + T.UKURAN_BADAN_LAYAR),
        ('body.admin-readonly', 'line-height: ' + T.LINE_HEIGHT),
        ('.admin-kepala h1', 'font-size: ' + T.UKURAN_JUDUL_DEWASA),
        ('.admin-angka', 'font-size: ' + T.UKURAN_ANGKA_DEWASA),
        ('.admin-kartu, .admin-stat', 'border-radius: ' + T.RADIUS_KARTU_BESAR),
        ('.admin-cari input', 'border-radius: ' + T.RADIUS_SEDANG),
        ('.admin-cari input', 'min-height: ' + T.TINGGI_KONTROL),
        ('.admin-layanan-kartu', 'border-radius: ' + T.RADIUS_KARTU),
        (':focus-visible', 'outline: ' + T.TEBAL_FOKUS + ' solid ' + T.ADMIN_AKSEN),
    ):
        assert deklarasi in _aturan(selector)
    assert 'min-height: ' + T.TINGGI_KONTROL in _aturan('.admin-kartu button:not(.tombol-mata)')
    sumber = (ROOT / 'admin_style.py').read_text()
    assert not re.search(r'font-size:\s*[\d.]+(?:px|rem)', sumber)
    assert not re.search(r'border-radius:\s*[\d.]+(?:px|%)', sumber)


def test_logo_bersama_tersedia_di_sidebar_dan_mobile_tanpa_aset_eksternal():
    isi = P.halaman_admin('ringkasan', '', pengguna='Demo').decode()
    sidebar = isi.split('<aside class="admin-sidebar">', 1)[1].split('</aside>', 1)[0]
    topbar = isi.split('<header class="admin-topbar">', 1)[1].split('</header>', 1)[0]
    assert brand.mark('topbar') in sidebar
    assert brand.mark('topbar') in topbar
    assert 'admin-brand-mark' not in isi
    assert 'class="admin-brand admin-brand-mobile"' in topbar
    assert 'display: none' in _aturan('.admin-brand-mobile')
    mobile = admin_style.GAYA_ADMIN.split('@media (max-width: 51.25rem)', 1)[1]
    assert '.admin-brand-mobile { display: flex;' in mobile
    assert 'https://' not in isi and '@import' not in isi
    assert isi.count('action="/keluar"') == 1


def test_form_pendek_dibatasi_tanpa_mengubah_payload():
    isi = P.form_buat_keluarga('csrf-sintetis', 'token-sintetis')
    assert '<section class="admin-kartu admin-form-pendek">' in isi
    assert 'max-width: ' + T.LEBAR_KONTEN in _aturan('.admin-form-pendek')
    assert 'action="/admin/akun"' in isi
    for nama in ('aksi', 'csrf', 'tinjauan', 'alias', 'sandi_baru', 'reauth'):
        assert 'name="%s"' % nama in isi


def test_toolbar_membedakan_pencarian_dan_aksi_utama():
    isi = P.render_keluarga(_keluarga(), csrf='sintetis')
    assert '<button class="admin-tombol admin-tombol-sekunder" type="submit">Cari</button>' in isi
    assert '<button class="admin-tombol admin-tombol-sekunder" type="submit" form="form-cari-keluarga">Terapkan</button>' in isi
    assert '<a class="admin-tombol" href="/admin/tinjau?aksi=account_teacher_create">' in isi
    assert 'method="post" action="/admin"' in isi
