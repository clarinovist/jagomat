"""State UI lanjutan: detail pengelola, filter privat, retry foto dan pemulihan."""
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
import re

import pytest

import admin_pages
import admin_daftar_pages
import admin_queries as Q
import admin_research_pages
import admin_launch_pages
import sensor_pages
import attachments
import database
import student_pages
import teacher_print_pages
from test_admin_pages import _keluarga, _siswa
from test_submission_flow import server, _kirim
from test_murid_kirim_foto import kirim_foto
from http_test_kit import SANDI_MURID, SANDI_GURU


class Markup(HTMLParser):
    def __init__(self, h):
        super().__init__()
        self.tags = []
        self.feed(h)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def regions(h):
    wrappers = [a for t, a in Markup(h).tags if a.get('class') == 'admin-tabel-wrap']
    assert wrappers
    assert all(a.get('tabindex') == '0' and a.get('role') == 'region' and a.get('aria-label') for a in wrappers)


@pytest.mark.parametrize('kategori', ['pengelola', 'pemilik_tanpa_akun', 'pemilik_kosong'])
def test_detail_keluarga_baca_saja_tidak_gagal_dan_tanpa_mutasi(kategori):
    item = replace(_keluarga().item[0], kategori=kategori)
    h = admin_pages.render_detail_keluarga(Q.DetailKeluarga(item, _siswa()))
    assert 'Identitas keluarga' in h and 'Siswa dalam keluarga' in h
    assert 'account_password_reset' not in h and 'account_login_delete' not in h
    assert '<form' not in h
    regions(h)


def test_detail_pengelola_dapat_dibuka_dengan_cookie_admin(server):
    import auth
    import sessions
    auth.tambah_akun('admin-demo', 'sandi-admin-demo-123', 'admin')
    principal = auth.autentikasi('admin-demo', 'sandi-admin-demo-123')
    token = sessions.buat_dari_principal(principal)
    with server.buka() as c:
        database.tambah_siswa(c, 'Profil Demo', pemilik='admin-demo')
    code, h, _ = server.minta('/admin?section=keluarga&id='+principal.id_akun, cookie=token)
    assert code == 200 and 'Identitas keluarga' in h
    assert 'account_password_reset' not in h and 'account_login_delete' not in h
    regions(h)


def test_detail_siswa_mempunyai_region_bernama():
    h = admin_pages.render_detail_siswa(Q.DetailSiswa(_siswa().item[0], ()))
    regions(h)


@pytest.mark.parametrize('bagian', ['keluarga', 'siswa'])
def test_pencarian_privat_bisa_melepas_filter_tanpa_menaruh_nama_di_url(bagian):
    if bagian == 'keluarga':
        data = replace(_keluarga(cari='Demo <&>'), status='perlu_perhatian', memiliki_anak='tidak')
        h = admin_daftar_pages.render_keluarga(data, csrf='csrf-sintetis')
        nama = ('status', 'memiliki_anak')
    else:
        data = replace(_siswa(cari='Demo <&>'), status='student_without_login')
        h = admin_daftar_pages.render_siswa(data, (), csrf='csrf-sintetis')
        nama = ('status',)
    dom = Markup(h)
    assert '<details class="admin-filter-lanjutan" open>' in h
    assert 'Sesuai chip di atas' not in h
    assert 'name="cari" maxlength="80" value="Demo &lt;&amp;&gt;"' in h
    for n in nama:
        select = next(a for t, a in dom.tags if t == 'select' and a.get('name') == n)
        assert select['form'] == 'form-cari-' + bagian
        block = re.search(r'<select[^>]* name="'+n+r'">(.*?)</select>', h).group(1)
        assert 'value="semua"' in block
        assert f'value="{getattr(data, n)}" selected' in block
        pencarian = re.search(r'<form id="form-cari-'+bagian+r'".*?</form>', h, re.S).group(0)
        assert not [a for t, a in Markup(pencarian).tags if t == 'input' and a.get('name') == n]
    assert all('cari=' not in a.get('href', '') for t, a in dom.tags if t == 'a')
    assert all(a.get('method') == 'post' for t, a in dom.tags if t == 'form')


def test_seluruh_wrapper_admin_memiliki_region_fokus():
    # Cegah wrapper detail/rare state baru kembali melewatkan kontrak scroll.
    root = Path(__file__).resolve().parents[1]
    for name in ('admin_pages.py','admin_daftar_pages.py','admin_launch_pages.py','admin_research_pages.py','ai_pages.py','sensor_pages.py'):
        for attrs in re.findall(r'<div class="admin-tabel-wrap"([^>]*)>', (root/name).read_text()):
            assert 'tabindex="0"' in attrs and 'role="region"' in attrs and 'aria-label=' in attrs, name
    regions(admin_launch_pages.tabel(('Kolom',), [], label='Data sintetis'))
    regions(sensor_pages.dashboard(dict(status='siap_best_effort', tahap=(('Tahap demo',5),),hambatan=(),hasil=(),chat=())))


@pytest.fixture
def db(tmp_path, monkeypatch):
    import auth
    path = tmp_path/'rare-ui.db'
    database.siapkan(path)
    monkeypatch.setattr(database,'BAWAAN',path)
    monkeypatch.setattr(auth,'BERKAS_SANDI',tmp_path/'auth.json')
    with database.buka(path) as c:
        sid = database.tambah_siswa(c, 'Demo', pemilik='guru')
        sesi = database.buat_sesi(c,sid,seed=7,jumlah_soal=2)
        lid = database.simpan_lampiran(c,sesi,'demo.png')
        yield c,sid,sesi,lid


@pytest.mark.parametrize('penegakan', [False, True])
def test_retry_foto_memperingatkan_draf_dan_konfirmasi_native_tanpa_field_baru(db, monkeypatch, penegakan):
    monkeypatch.setattr(attachments, 'penegakan_foto', lambda: penegakan)
    c,_,_,lid=db
    awal=tuple(c.iterdump())
    h=attachments.halaman_konfirmasi(c,lid).decode()
    form=re.search(r'<form[^>]*class="baca-ulang-form">(.*?)</form>',h,re.S).group(1)
    assert 'Koreksi yang belum diterapkan akan hilang' in form
    assert 'termasuk jika pembacaan gagal' in form
    cek=next(a for t,a in Markup(form).tags if t=='input' and a.get('type')=='checkbox')
    assert 'required' in cek and 'name' not in cek
    assert cek['aria-describedby']=='peringatan-baca-ulang'
    assert 'jwb_' not in form and '/terapkan' not in form
    fields = [a['name'] for t,a in Markup(form).tags if t=='input' and 'name' in a]
    assert fields == (['operasi_foto'] if penegakan else [])
    assert 'baca-ulang-form' not in attachments.halaman_konfirmasi(c,lid,ai_aktif=False).decode().split('<body',1)[1]
    assert tuple(c.iterdump())==awal


def test_picker_guru_sesuai_format_yang_didukung(db):
    c,_,sesi,_=db
    h=teacher_print_pages.halaman_sesi_lampiran(c,sesi).decode()
    file=next(a for t,a in Markup(h).tags if t=='input' and a.get('type')=='file')
    assert file['accept']=='image/jpeg,image/png,image/webp'
    assert 'JPEG/PNG/WebP, maks 8 MB' in h


def test_feedback_foto_memiliki_target_status_galat_dan_tanpa_duplikasi(db):
    c,sid,sesi,_=db
    for galat in (False,True):
        h=student_pages.halaman_kerja_baru(c,sid,sesi,kabar_foto='Pesan <sintetis>',foto_galat=galat).decode()
        a=next(a for t,a in Markup(h).tags if a.get('id')=='kabar-foto')
        assert a['role']==('alert' if galat else 'status')
        assert ('galat' in a['class'].split())==galat
        assert a['tabindex']=='-1' and h.count('id="kabar-foto"')==1
        assert 'Pesan &lt;sintetis&gt;' in h


@pytest.mark.parametrize('tautan', [False,True])
def test_konflik_refleksi_punya_get_pemulihan_tanpa_menulis(server,tautan):
    import share_links
    with server.buka() as c:
        token=share_links.buat(c,server.sesi) if tautan else None
        # Satu perubahan nyata membuat revisi0 menjadi basi.
        database.simpan_jawaban(c,server.ids[0],'123','Cara sintetis')
        awal=tuple(c.iterdump())
    jalur=f'/mulai/{token}' if tautan else None
    status,h,_=_kirim(server,{'aksi':'kirim_latihan','revisi_pekerjaan':'0'},jalur)
    assert status==409
    url=jalur or f'/murid/kerjakan/{server.sesi}'
    assert f'<a href="{url}">Buka kembali latihan</a>' in h
    assert '<form' not in h
    with server.buka() as c:
        assert tuple(c.iterdump())==awal
        if token:
            share_links.cabut(c,server.sesi)
    if token:
        status,h,_=_kirim(server,{'aksi':'kirim_latihan','revisi_pekerjaan':'0'},jalur)
        assert status==404 and 'Buka kembali latihan' not in h


@pytest.mark.parametrize('berhasil', [False, True])
def test_redirect_foto_menuju_feedback_dengan_status_eksplisit(server, monkeypatch, berhasil):
    from urllib.parse import urlsplit, parse_qs
    from test_admin_http_c import _minta
    monkeypatch.setattr(attachments, 'penegakan_foto', lambda: False)
    monkeypatch.setattr(attachments, 'proses_upload_murid', lambda *a: (1 if berhasil else None, 'Pesan sintetis'))
    code, _, headers = _minta(server, f'/murid/foto/{server.sesi}', data={}, auth_basic=('feby',SANDI_MURID))
    assert code == 303
    target = urlsplit(headers['Location'])
    assert target.path == f'/murid/kerjakan/{server.sesi}' and target.fragment == 'kabar-foto'
    assert ('foto_galat' in parse_qs(target.query)) != berhasil


def test_penolakan_foto_anak_dibedakan_dari_sukses(server):
    code,h=kirim_foto(server,server.sesi,('feby',SANDI_MURID),isi=b'bukan foto',nama='demo.txt',mime='text/plain')
    assert code==200
    feedback=next(a for t,a in Markup(h).tags if a.get('id')=='kabar-foto')
    assert feedback['role']=='alert' and 'galat' in feedback['class'].split()
    with server.buka() as c:
        assert database.daftar_lampiran(c,server.sesi)==[]


def test_upload_guru_ditolak_punya_tautan_aman_ke_lampiran(server):
    code,h,_=server.minta(f'/lampiran/{server.sesi}',auth=('guru',SANDI_GURU),data={})
    assert code==400 and f'href="/sesi/{server.sesi}/lampiran"' in h
    code,h,_=server.minta('/lampiran/999999',auth=('guru',SANDI_GURU),data={})
    assert code==404 and 'Pilih foto lain' not in h
