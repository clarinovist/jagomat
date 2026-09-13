"""Pendaftaran editorial: kontrak form, pesan aman, dan respons pembatasan."""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import auth
import sessions
import landing
import style_stitch
import design_tokens as T
from http_test_kit import ServerUji
from teacher_style import SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.elemen = []; self.feed(html)
    def handle_starttag(self, tag, attrs):
        self.elemen.append((tag, dict(attrs)))
    def cari(self, tag):
        return [a for t, a in self.elemen if t == tag]


def test_kerangka_editorial_dan_satu_aksi():
    h = landing.halaman_daftar().decode()
    m = Markup(h)
    assert len(m.cari('main')) == len(m.cari('h1')) == 1
    assert m.cari('main')[0]['aria-labelledby'] == m.cari('h1')[0]['id']
    assert 'daftar-editorial-st' in h
    assert 'Buat akun orang tua' in h
    assert [a['href'] for a in m.cari('a')].count('/masuk') == 1
    assert [a['href'] for a in m.cari('a')].count('/') == 1
    assert [a['href'] for a in m.cari('a')].count('/kebijakan-privasi') == 1
    assert len(m.cari('form')) == len(m.cari('button')) == 1


@pytest.mark.parametrize('pesan,galat', [('',False),('Nama sudah dipakai.',True),('Coba kembali.',False)])
def test_form_sandi_dan_persetujuan_tetap(pesan, galat):
    h = landing.halaman_daftar(pesan, galat, 'pendamping-demo').decode()
    m = Markup(h)
    assert m.cari('form')[0]['method'] == 'post'
    assert m.cari('form')[0]['action'] == '/daftar'
    assert 'novalidate' not in m.cari('form')[0]
    kolom = {a['name']: a for a in m.cari('input')}
    assert set(kolom) == {'nama','sandi','setuju'}
    assert kolom['nama']['autocomplete'] == 'username'
    assert kolom['nama']['value'] == 'pendamping-demo'
    assert kolom['sandi']['autocomplete'] == 'new-password'
    assert kolom['sandi']['type'] == 'password'
    assert kolom['sandi']['minlength'] == '8'
    assert 'value' not in kolom['sandi']
    assert 'checked' not in kolom['setuju']
    assert kolom['setuju']['value'] == '1'
    assert all('required' in a for a in kolom.values())
    assert all('autofocus' not in a for a in kolom.values())
    assert re.findall(r'<script>(.*?)</script>', h, re.S) == [SKRIP_MATA_SANDI, SKRIP_CEGAH_KIRIM_GANDA]
    assert not any(k.startswith('on') for _, a in m.elemen for k in a)


def test_petunjuk_terkait_label_bukan_placeholder():
    m = Markup(landing.halaman_daftar().decode())
    ids = {a['id'] for _,a in m.elemen if 'id' in a}
    for a in m.cari('input'):
        assert a['id'] in {label['for'] for label in m.cari('label')}
        if a['name'] != 'setuju':
            assert a['aria-describedby'] in ids
    assert not any(a.get('type') in {'email','tel'} for a in m.cari('input'))


@pytest.mark.parametrize('galat,peran', [(True,'alert'),(False,'status')])
def test_pesan_escaped_dan_terhubung_ke_form(galat,peran):
    h = landing.halaman_daftar('<b data-uji="jahat">Pesan & contoh</b>',galat,'"><img src=x onerror=alert(1)>').decode()
    m = Markup(h)
    kotak = [a for _,a in m.elemen if a.get('role') == peran]
    assert len(kotak) == 1
    assert kotak[0]['aria-atomic'] == 'true'
    assert m.cari('form')[0]['aria-describedby'] == kotak[0]['id']
    assert '&lt;b data-uji=&quot;jahat&quot;&gt;' in h
    assert '&lt;img src=x onerror=alert(1)&gt;' in h
    assert not any('data-uji' in a or 'onerror' in a for _,a in m.elemen)
    assert not any(a.get('role') in {'alert','status'} for _,a in Markup(landing.halaman_daftar().decode()).elemen)


def test_maskot_existing_dekoratif():
    m = Markup(landing.halaman_daftar().decode())
    gambar = [a for a in m.cari('img') if a.get('class') == 'daftar-maskot-st']
    assert len(gambar) == 1
    assert gambar[0]['src'] == '/aset/maskot-menyapa-v3-240.png'
    assert gambar[0]['alt'] == ''
    assert gambar[0]['width'] == gambar[0]['height'] == '240'


def test_style_scoped_tidak_mengubah_login_dan_form_publik_lain():
    sumber = Path(style_stitch.__file__).read_text()
    blok = sumber.split('/* ── Pendaftaran editorial',1)[1].split('/* ── Halaman masuk editorial',1)[0]
    assert not re.search(r'#[0-9a-fA-F]{3,8}\b',blok)
    css = style_stitch.GAYA_STITCH.split('/* ── Pendaftaran editorial',1)[1].split('/* ── Halaman masuk editorial',1)[0]
    for selector in re.findall(r'([^{}]+)\{',re.sub(r'/\*.*?\*/','', '/*' + css,flags=re.S)):
        if selector.strip().startswith('@'): continue
        selector = re.sub(r':is\([^)]*\)','',selector)
        assert all(s.strip().startswith('.daftar-editorial-st') for s in selector.split(',')), selector
    assert T.AKSEN_KORAL_TUA in css and T.AKSEN_TEAL_TUA in css
    assert 'outline: 3px' in css
    assert '.daftar-editorial-st .masuk-field-st input:focus-visible' in css
    def luminansi(warna):
        nilai = warna.lstrip('#')
        if len(nilai) == 3:
            nilai = ''.join(c * 2 for c in nilai)
        rgb = [int(nilai[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * b
                   for v, b in zip(rgb, (.2126, .7152, .0722)))
    for teks, latar in ((T.TEKS_PUTIH, T.AKSEN_KORAL_TUA),
                        (T.AKSEN_TEAL_TUA, T.LATAR_CATATAN),
                        (T.TEKS_VARIAN, T.LATAR_KARTU)):
        gelap, terang = sorted((luminansi(teks), luminansi(latar)))
        assert (terang + .05) / (gelap + .05) >= 4.5
    for fungsi in (landing.halaman_lupa_sandi,landing.halaman_kebijakan):
        assert not any('daftar-editorial-st' in a.get('class','').split() for _,a in Markup(fungsi().decode()).elemen)


@pytest.fixture()
def server(tmp_path,monkeypatch):
    monkeypatch.setattr(sessions,'BERKAS_SESI',tmp_path/'sessions.json')
    monkeypatch.setattr(sessions,'_jalur_dari_kunci_ip',{})
    s=ServerUji(tmp_path,monkeypatch)
    auth.tambah_akun('admin-register','sandi-admin-register-123','admin')
    try: yield s
    finally: s.berhenti()


def _keadaan(server):
    with server.buka() as kon:
        db=tuple(kon.iterdump())
    return auth.BERKAS_SANDI.read_bytes(), (sessions.BERKAS_SESI.read_bytes() if sessions.BERKAS_SESI.exists() else None),db


def _token_form(server):
    import re
    isi = server.minta('/daftar')[1]
    return re.search(r'name="token_form" value="([^"]+)"', isi).group(1)


def test_pendaftaran_diblokir_mengembalikan_429_tanpa_akun_sesi(server):
    for _ in range(5): sessions.catat_gagal('pendamping-demo','127.0.0.1')
    token_form = _token_form(server)
    sebelum=_keadaan(server)
    kode,isi,header=server.minta('/daftar',data={'nama':'pendamping-demo','sandi':'sandi-sintetis-jangan-pantulkan','setuju':'1','token_form':token_form})
    assert kode == 429
    assert 'Terlalu banyak percobaan' in isi
    assert 'role="alert"' in isi
    assert 'value="pendamping-demo"' in isi
    assert 'sandi-sintetis-jangan-pantulkan' not in isi
    assert 'Set-Cookie' not in header
    assert _keadaan(server) == sebelum


@pytest.mark.parametrize('data,pesan', [
    ({'nama':'','sandi':'sandi-sintetis-123','setuju':'1'},'Nama wajib diisi.'),
    ({'nama':'pendamping-demo','sandi':'pendek','setuju':'1'},'Kata sandi minimal 8 karakter.'),
    ({'nama':'pendamping-demo','sandi':'sandi-sintetis-123'},'Centang persetujuan'),
    ({'nama':'guru','sandi':'sandi-sintetis-123','setuju':'1'},'sudah dipakai'),
])
def test_galat_http_tidak_membuat_akun_atau_memantulkan_sandi(server,data,pesan):
    sebelum=_keadaan(server)
    data = {**data, 'token_form': _token_form(server)}
    kode,isi,header=server.minta('/daftar',data=data)
    assert kode == 200 and pesan in isi
    m=Markup(isi)
    assert m.cari('form')[0]['aria-describedby']=='pesan-daftar'
    assert any(a.get('role')=='alert' for _,a in m.elemen)
    if len(data['sandi']) > 8:
        assert data['sandi'] not in isi
    assert 'value' not in next(a for a in m.cari('input') if a['name'] == 'sandi')
    assert 'Set-Cookie' not in header
    assert _keadaan(server)==sebelum
