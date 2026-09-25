"""Rute checkout lewat HTTP loopback, seluruh akun/ledger/provider sintetis."""

from dataclasses import replace
from html.parser import HTMLParser
import json
from pathlib import Path
import time
from types import SimpleNamespace
import urllib.request

import pytest
import admin_store
import auth
import database
import sessions
import subscription as d
import subscription_checkout as checkout
import subscription_http as h
import subscription_store as store
from http_test_kit import ServerUji, SANDI_GURU
from test_midtrans_contract import CFG, Respons
from test_subscription_store import dump


class FormParser(HTMLParser):
    def __init__(self, isi):
        super().__init__(); self.forms = {}; self.aktif = None; self.feed(isi)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.aktif = a['action']; self.forms[self.aktif] = {}
        if tag == 'input' and self.aktif and a.get('type') == 'hidden':
            self.forms[self.aktif][a['name']] = a.get('value', '')
    def handle_endtag(self, tag):
        if tag == 'form': self.aktif = None


class Provider:
    def __init__(self):
        self.panggilan = []; self.status = 'pending'; self.nominal = 15000
        self.hook = None; self.gambar_hook = None; self.url_gambar = []
    def __call__(self, req, **kw):
        self.panggilan.append(req)
        if self.hook: self.hook()
        if req.metode == 'POST':
            isi = json.loads(req.body); invoice = isi['transaction_details']['order_id']
            self.nominal = isi['transaction_details']['gross_amount']
        else: invoice = req.url.split('/')[-2]
        data = dict(order_id=invoice, transaction_id='trx_sintetis', gross_amount=str(self.nominal)+'.00',
            currency='IDR', payment_type='qris', merchant_id=CFG.merchant,
            status_code='200' if self.status == 'settlement' else '201', transaction_status=self.status)
        return Respons(data, url=req.url)
    def gambar(self, url):
        self.url_gambar.append(url)
        if self.gambar_hook: self.gambar_hook()
        return b'PNG-SINTETIS'


@pytest.fixture
def uji(tmp_path, monkeypatch):
    server = ServerUji(tmp_path, monkeypatch)
    with server.buka() as kon:
        sid = database.tambah_siswa(kon, 'Profil Sintetis', 'P3', pemilik='guru')
        asing = database.tambah_siswa(kon, 'Profil Asing', 'P4', pemilik='guru-lain')
    # Runtime hanya menerima seluruh path yang eksplisit sama dengan preview.
    # DB test existing dipindahkan ke nama preview setelah koneksi setup ditutup.
    db = tmp_path / 'belajar.db'; server.db.rename(db); server.db = db
    monkeypatch.setattr(database, 'BAWAAN', db)
    p = auth.autentikasi('guru', SANDI_GURU, auth.BERKAS_SANDI)
    cookie = sessions.buat_dari_principal(p)
    kini = int(time.time())
    store.buat_kampanye(admin_store.BAWAAN, 'kampanye_uji', mulai=kini, sakelar=h.ON)
    store.enroll(admin_store.BAWAAN, p.id_akun, sumber_id='enroll_sintetis', asal='publik',
                 mulai=kini, peran='guru', sakelar=h.ON)
    provider = Provider()
    r = h.RuntimeSandbox(tmp_path, CFG, provider, provider.gambar)
    server.server.langganan_sandbox = r
    k = SimpleNamespace(server=server, p=p, cookie=cookie, sid=sid, asing=asing, r=r, provider=provider)
    try: yield k
    finally: server.berhenti()


def minta(k, url='/langganan', **kw):
    kw.setdefault('cookie', k.cookie)
    if 'data' in kw: kw.setdefault('headers', {'Origin': k.server.alamat})
    return k.server.minta(url, **kw)


def siapkan(k):
    kode, isi, _ = minta(k)
    assert kode == 200
    form = FormParser(isi).forms['/langganan/siapkan']
    kode, isi, _ = minta(k, '/langganan/siapkan', data=dict(form, profil=str(k.sid)))
    assert kode == 200, isi
    aksi = next(a for a in FormParser(isi).forms if a.endswith('/buat'))
    return aksi[:-5], FormParser(isi).forms[aksi]


def buat(k):
    url, form = siapkan(k)
    kode, isi, _ = minta(k, url+'/buat', data=form)
    assert kode == 200, isi
    return url, isi


def test_alur_quote_pending_qr_lunas_replay_dan_get_readonly(uji):
    k=uji; awal=dump(admin_store.BAWAAN)
    kode, isi, headers=minta(k)
    assert kode==200 and 'Profil Asing' not in isi
    assert dump(admin_store.BAWAAN)==awal and k.provider.panggilan==[]
    assert headers['Cache-Control']=='no-store' and "img-src 'self'" in headers['Content-Security-Policy']
    assert '<script' not in isi and 'fonts.googleapis.com' not in isi
    url, form=siapkan(k)
    assert k.provider.panggilan==[]
    sebelum=dump(admin_store.BAWAAN)
    assert minta(k,url)[0]==200 and dump(admin_store.BAWAAN)==sebelum
    kode, isi, _=minta(k,url+'/buat',data=form)
    assert kode==200 and 'Menunggu pembayaran' in isi and url+'/qr' in isi
    assert 'https://api.sandbox.midtrans.com/v2/qris/trx_sintetis/qr-code' in isi
    assert 'simulator.sandbox.midtrans.com/v2/qris/index' in isi
    kode, gambar, headers=minta(k,url+'/qr',biner=True)
    assert kode==200 and gambar==b'PNG-SINTETIS' and headers['Content-Type']=='image/png'
    assert k.provider.url_gambar==['https://api.sandbox.midtrans.com/v2/qris/trx_sintetis/qr-code']
    sebelum=dump(admin_store.BAWAAN)
    assert minta(k,url)[0]==200 and dump(admin_store.BAWAAN)==sebelum
    assert minta(k,url+'/buat',data=form)[0]==200
    assert sum(req.metode=='POST' for req in k.provider.panggilan)==1
    k.provider.status='settlement'
    isi=minta(k,url)[1]
    assert 'LUNAS · SANDBOX.' not in isi  # GET tidak menulis/grant
    form=FormParser(isi).forms[url+'/periksa']
    sebelum_grant = dump(admin_store.BAWAAN)
    kode,isi,_=minta(k,url+'/periksa',data=form)
    assert kode==200 and 'LUNAS · SANDBOX.' in isi
    assert dump(admin_store.BAWAAN) != sebelum_grant and url+'/qr' not in isi
    assert len(store.baca(admin_store.BAWAAN,k.p.id_akun).grants)==1
    assert minta(k,url+'/qr')[0] == 404
    assert minta(k,url+'/periksa',data=form)[0]==200
    assert len(store.baca(admin_store.BAWAAN,k.p.id_akun).grants)==1
    for key in ('kunci-sintetis', 'Authorization', k.p.id_akun, k.cookie):
        assert key not in isi


def test_anon_basic_murid_admin_dan_asing_404_identik_tanpa_efek(uji):
    k=uji; url,_=siapkan(k)
    auth.tambah_akun('guru-lain','sandi-guru-lain-123','guru')
    auth.tambah_akun('pengelola-sintetis','sandi-pengelola-123','admin')
    cookies=[None]
    for nama,sandi in [('feby','sandi-feby-12345'),('guru-lain','sandi-guru-lain-123'),('pengelola-sintetis','sandi-pengelola-123')]:
        cookies.append(sessions.buat_dari_principal(auth.autentikasi(nama,sandi)))
    awal=dump(admin_store.BAWAAN); bodies=[]
    for cookie in cookies:
        for suffix in ('','/qr','/buat','/periksa'):
            kw={'data':{'token':'palsu'}} if suffix in ('/buat','/periksa') else {}
            kode,isi,_=minta(k,url+suffix,cookie=cookie,**kw)
            assert kode==404; bodies.append(isi)
    kode,isi,_=minta(k,url,cookie=None,auth=('guru',SANDI_GURU))
    assert kode==404; bodies.append(isi)
    kode,isi,_=minta(k,'/langganan/inv_'+'f'*32)
    assert kode==404; bodies.append(isi)
    assert len(set(bodies))==1 and dump(admin_store.BAWAAN)==awal and not k.provider.panggilan


@pytest.mark.parametrize('jenis',['palsu','sesi','aksi','invoice','expiry','field','origin','profil_asing','profil_duplikat','profil_empat'])
def test_form_tidak_sah_tanpa_invoice_atau_jaringan(uji,jenis):
    k=uji; form=FormParser(minta(k)[1]).forms['/langganan/siapkan']; form['profil']=str(k.sid)
    headers={'Origin':k.server.alamat}
    if jenis=='palsu': form['token']=form['token'][:-1]+('0' if form['token'][-1]!='0' else '1')
    if jenis=='sesi': form['token']=h._token(k.r,'sesi-asing',k.p,'siapkan')
    if jenis=='aksi': form['token']=h._token(k.r,k.cookie,k.p,'periksa')
    if jenis=='invoice': form['token']=h._token(k.r,k.cookie,k.p,'siapkan','inv_'+'a'*32)
    if jenis=='expiry': form['token']=h._token(k.r,k.cookie,k.p,'siapkan',sekarang=int(time.time())-901)
    if jenis=='field': form['rupiah']='1'
    if jenis=='origin': headers={'Origin':'https://evil.test'}
    if jenis=='profil_asing': form['profil']=str(k.asing)
    if jenis=='profil_duplikat': form['profil']=[str(k.sid),str(k.sid)]
    if jenis=='profil_empat': form['profil']=[str(k.sid)]*4
    awal=dump(admin_store.BAWAAN)
    assert minta(k,'/langganan/siapkan',data=form,headers=headers)[0] in (400,403,404)
    assert dump(admin_store.BAWAAN)==awal and not k.provider.panggilan


def test_post_http_host_nonloopback_ditolak(uji):
    k=uji; form=FormParser(minta(k)[1]).forms['/langganan/siapkan']; form['profil']=str(k.sid)
    awal=dump(admin_store.BAWAAN)
    kode,_,_=minta(k,'/langganan/siapkan',data=form,headers={'Origin':'http://contoh.test','Host':'contoh.test'})
    assert kode==403 and dump(admin_store.BAWAAN)==awal and not k.provider.panggilan


def test_runtime_nonloopback_ditolak(uji, monkeypatch):
    k = uji
    awal = dump(admin_store.BAWAAN)
    monkeypatch.setattr(k.server.server, 'server_address', ('0.0.0.0', 8080))
    assert minta(k)[0] == 404
    assert dump(admin_store.BAWAAN) == awal and not k.provider.panggilan


def test_default_off_dan_path_runtime_salah_tolak(uji,monkeypatch):
    k=uji
    awal=dump(admin_store.BAWAAN)
    del k.server.server.langganan_sandbox
    assert minta(k)[0]==404
    k.server.server.langganan_sandbox=k.r
    monkeypatch.setattr(database,'BAWAAN',k.r.akar/'bukan-db.db')
    assert minta(k)[0]==404 and not (k.r.akar/'bukan-db.db').exists()
    assert dump(admin_store.BAWAAN)==awal and not k.provider.panggilan


@pytest.mark.parametrize('jenis',['logout','sandi','owner'])
def test_perubahan_saat_query_tidak_grant(uji,jenis):
    k=uji; url,_=buat(k); form=FormParser(minta(k,url)[1]).forms[url+'/periksa']
    k.provider.status='settlement'
    def ubah():
        if jenis=='logout': sessions.hapus(k.cookie)
        elif jenis=='sandi': auth.setel_sandi_guru(k.p.pengguna,'sandi-baru-123456')
        else:
            with k.server.buka() as kon: kon.execute('UPDATE siswa SET pemilik=? WHERE id=?',('guru-lain',k.sid))
    k.provider.hook=ubah
    assert minta(k,url+'/periksa',data=form)[0]==404
    assert not store.baca(admin_store.BAWAAN,k.p.id_akun).grants


def test_status_lunas_dengan_qr_tetap_menolak_gambar(uji, monkeypatch):
    k=uji; url,_=buat(k)
    asli=h._status
    def palsu(*args):
        inv, _ = asli(*args)
        return inv, h.midtrans.Hasil('lunas', qr='https://api.sandbox.midtrans.com/v2/qris/trx_sintetis/qr-code')
    monkeypatch.setattr(h,'_status',palsu)
    assert minta(k,url+'/qr')[0] == 404
    assert not k.provider.url_gambar


def test_qr_recheck_owner_sesudah_fetch(uji):
    k=uji; url,_=buat(k)
    def ubah():
        with k.server.buka() as kon: kon.execute('UPDATE siswa SET pemilik=? WHERE id=?',('guru-lain',k.sid))
    k.provider.gambar_hook=ubah
    kode,isi,_=minta(k,url+'/qr')
    assert kode==404 and 'PNG-SINTETIS' not in isi


def test_batas_laju_sebelum_provider(uji):
    k=uji; url,_=buat(k)
    k.r.permintaan=[time.monotonic()]*30
    sebelum=len(k.provider.panggilan)
    kode,isi,_=minta(k,url)
    assert kode==429 and 'Terlalu banyak permintaan' in isi
    assert len(k.provider.panggilan)==sebelum


def test_account_link_hanya_saat_runtime_preview(uji):
    k=uji
    kode,isi,_=minta(k,'/akun')
    assert kode==200 and '<a href="/langganan">Langganan sandbox</a>' in isi
    del k.server.server.langganan_sandbox
    kode,isi,_=minta(k,'/akun')
    assert kode==200 and '/langganan' not in isi


def test_timeout_tidak_create_kedua_dan_error_tidak_bocor(uji):
    k=uji; url,form=siapkan(k)
    def gagal(): raise TimeoutError('kunci-sintetis-jangan-bocor')
    k.provider.hook=gagal
    kode,isi,_=minta(k,url+'/buat',data=form)
    assert kode==200 and 'belum terverifikasi' in isi and 'kunci-sintetis' not in isi
    assert minta(k,url+'/buat',data=form)[0]==200
    assert sum(req.metode=='POST' for req in k.provider.panggilan)==1


def test_token_lama_sesudah_lunas_tidak_invoice_periode_kedua(uji):
    k=uji; form=FormParser(minta(k)[1]).forms['/langganan/siapkan']; form['profil']=str(k.sid)
    isi=minta(k,'/langganan/siapkan',data=form)[1]
    aksi=next(a for a in FormParser(isi).forms if a.endswith('/buat')); url=aksi[:-5]
    assert minta(k,aksi,data=FormParser(isi).forms[aksi])[0]==200
    k.provider.status='settlement'
    isi=minta(k,url)[1]
    periksa=FormParser(isi).forms[url+'/periksa']
    assert minta(k,url+'/periksa',data=periksa)[0]==200
    assert minta(k,'/langganan/siapkan',data=form)[0]==200
    with admin_store.buka_baca(admin_store.BAWAAN) as kon:
        assert kon.execute('SELECT COUNT(*) FROM langganan_invoice').fetchone()[0]==1
