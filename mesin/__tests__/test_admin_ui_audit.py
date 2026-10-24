"""Regresi audit admin: affordance, akses keyboard, dan kontrak form sintetis."""
import re
from types import SimpleNamespace as NS

import admin_pages as P
import admin_research_pages as R
import admin_style
import design_tokens as T
from test_admin_navigation_style import _kontras


def _aturan(selector):
    cocok = re.search(r'(?:^|\n)' + re.escape(selector) + r'\s*\{([^}]+)\}', admin_style.GAYA_ADMIN)
    assert cocok, selector
    return cocok.group(1)


def test_target_lewati_navigasi_dapat_menerima_fokus_tanpa_tab_stop_tambahan():
    html = P.halaman_admin('ringkasan', '', pengguna='Demo').decode()
    main = re.search(r'<main\b[^>]*>', html).group()
    assert 'id="konten-admin"' in main
    assert 'tabindex="-1"' in main
    assert 'aria-labelledby="judul-admin"' in main


def test_print_menimpa_spesifisitas_tema_manual():
    cetak = admin_style.GAYA_ADMIN.split('@media print', 1)[1]
    assert 'body.admin-readonly[data-tema] {' in cetak
    assert '--admin-latar: ' + T.ADMIN_LATAR_CERAH in cetak
    assert '--admin-teks: ' + T.ADMIN_TEKS_CERAH in cetak


def test_batas_kontrol_terlihat_di_kedua_tema():
    for tema in ('CERAH', 'GELAP'):
        border = getattr(T, 'ADMIN_BORDER_KUAT_' + tema)
        for permukaan in ('ADMIN_PERMUKAAN_', 'ADMIN_LATAR_'):
            assert _kontras(border, getattr(T, permukaan + tema)) >= 3


def test_disabled_dan_readonly_tidak_menyerupai_tindakan_aktif():
    css = _aturan('button:disabled, button:disabled:hover')
    assert 'cursor: not-allowed' in css
    assert 'background: ' + T.ADMIN_NETRAL_LATAR in css
    assert 'color: ' + T.ADMIN_REDUP in css
    assert 'background: ' + T.ADMIN_NETRAL_LATAR in _aturan('.admin-kartu input[readonly]:not([type=hidden]):not([type=checkbox]):not([type=radio]), .admin-kartu textarea[readonly]')


def test_tabel_semua_kolom_dan_disclosure_punya_target_fokus():
    css = _aturan('.admin-tabel a')
    assert 'min-height: ' + T.TARGET_SENTUH in css
    assert 'min-width: ' + T.TARGET_SENTUH in css
    assert 'outline-offset: -3px' in _aturan('.admin-tabel-wrap:focus-visible')
    assert 'flex: none' in _aturan('.riset-daftar-pertanyaan > li > a')


def test_pager_riset_memakai_kontrol_yang_sama_tanpa_mengubah_query():
    isi = R._pager(NS(halaman=2, total=61, per_halaman=20), 'final')
    assert isi.count('class="admin-tautan"') == 2
    assert 'status=final&amp;halaman=1' in isi
    assert 'status=final&amp;halaman=3' in isi


def test_aksi_riset_memiliki_label_konteks_dan_hierarki_tetap_native():
    detail = dict(id='rw_demo', status='draf', jawaban={}, kode_responden='DEMO',
                  kode_versi='v1', sumber='internal', diwawancarai=1, retensi_hingga=2,
                  instrumen={'pertanyaan': [{'kode':'Q1','judul':'Konteks sintetis'}]})
    isi = R.ringkasan_wawancara(detail, csrf='c', token_aksi={'finalisasi':'f','redaksi':'r','tarik':'t'})
    assert 'class="admin-tautan" aria-label="Isi topik: Konteks sintetis"' in isi
    assert 'class="admin-tombol admin-tombol-sekunder" type="submit">Tandai perlu redaksi' in isi
    assert 'class="admin-zona-bahaya"' in isi
    assert 'data-konfirmasi="Tarik consent dan hapus seluruh jawaban serta kutipan responden ini?"' in isi
    assert 'type="submit" disabled>Selesaikan wawancara' in isi
    assert isi.count('<form') == 3
    assert '<script' not in isi


def test_hapus_profil_kosong_memakai_konfirmasi_existing_tanpa_mengubah_field():
    isi = P.form_hapus_siswa('c', 't')
    assert 'data-konfirmasi="Hapus login dan profil siswa kosong ini? Tindakan tidak dapat dibatalkan."' in isi
    assert 'name="konfirmasi" value="1" required' in isi
    assert 'name="aksi" value="student_delete"' in isi
    assert 'action="/admin/siswa"' in isi


def test_pemilihan_bulk_semua_tombol_memakai_komponen_tanpa_ubah_kontrak(tmp_path, monkeypatch):
    from http_test_kit import ServerUji
    from test_admin_http_c import _login, _minta, SANDI_ADMIN
    from test_admin_form_contract import KontrakForm
    import auth

    server = ServerUji(tmp_path, monkeypatch)
    try:
        auth.tambah_akun('Admin-C', SANDI_ADMIN, 'admin')
        token = _login(server, 'Admin-C', SANDI_ADMIN)
        code, isi, _ = _minta(server, '/admin/bulk/pilih?peran=guru', cookie=token)
        assert code == 200
        main = isi.split('<main ', 1)[1].split('</main>', 1)[0]
        tombol = re.findall(r'<button\b[^>]*>', main)
        assert len(tombol) == 6
        assert all('class="admin-' in t for t in tombol)
        p = KontrakForm()
        p.feed(main)
        assert len(p.forms) == 4
        assert all(f['action'] == '/admin/bulk/pilih' and f['method'] == 'post' for f in p.forms)
        assert all('csrf' in {x['name'] for x in f['fields']} for f in p.forms)
    finally:
        server.berhenti()
