"""Panel admin memakai runtime checkout sandbox terisolasi yang sama."""

import auth
import admin_store
import admin_subscription
import subscription_store
from test_subscription_http import uji, buat, FormParser
from test_admin_http_c import _login, _minta


def test_admin_periksa_sandbox_settlement_dan_replay(uji):
    k=uji
    auth.tambah_akun('Admin-bridge','sandi-admin-bridge-123','admin')
    url,_=buat(k)
    token=_login(k.server,'Admin-bridge','sandi-admin-bridge-123')
    alamat='/admin?section=langganan&id='+k.p.id_akun
    kode,body,_=_minta(k.server,alamat,cookie=token)
    assert kode==200
    form=FormParser(body).forms['/admin/layanan/periksa']
    form['reauth']='sandi-admin-bridge-123'
    k.provider.status='settlement'
    awal=len(k.provider.panggilan)
    for _ in range(2):
        assert _minta(k.server,'/admin/layanan/periksa',cookie=token,data=form)[0]==303
    assert len(k.provider.panggilan)==awal+1
    assert k.provider.panggilan[-1].metode=='GET'
    assert len(subscription_store.baca(admin_store.BAWAAN,k.p.id_akun).grants)==1
    assert 'Pembayaran tercatat' in _minta(k.server,alamat,cookie=token)[1]


def test_runtime_produksi_mengikuti_sakelar_admin_bukan_auto_on(uji,monkeypatch):
    k=uji
    runtime=admin_subscription.RuntimePembayaran(
        __import__('midtrans_contract').Konfigurasi('production','key-sintetis','M_SINTETIS'),
        k.provider,__import__('subscription').Sakelar(True,True,True,True),
        dict(provider_produksi=True,callback=True,recovery=True,kebijakan=True))
    penangan=type('P',(),{'server':type('S',(),{'pembayaran_runtime':runtime})()})()
    monkeypatch.setattr(__import__('subscription_http'),'runtime',lambda _:None)
    hasil=admin_subscription.runtime_penangan(penangan)
    assert hasil.sakelar==__import__('subscription').Sakelar()
    assert admin_subscription.kesiapan_penangan(type('P',(),{'server':type('S',(),{})()})())=={
        'provider_produksi':False,'callback':False,'recovery':False,'kebijakan':False}


def test_admin_runtime_hilang_tidak_memanggil_provider(uji):
    k=uji
    auth.tambah_akun('Admin-bridge','sandi-admin-bridge-123','admin')
    buat(k)
    token=_login(k.server,'Admin-bridge','sandi-admin-bridge-123')
    alamat='/admin?section=langganan&id='+k.p.id_akun
    body=_minta(k.server,alamat,cookie=token)[1]
    form=FormParser(body).forms['/admin/layanan/periksa']
    form['reauth']='sandi-admin-bridge-123'
    del k.server.server.langganan_sandbox
    awal=len(k.provider.panggilan)
    assert _minta(k.server,'/admin/layanan/periksa',cookie=token,data=form)[0]==503
    assert len(k.provider.panggilan)==awal
    assert '/admin/layanan/periksa' not in _minta(k.server,alamat,cookie=token)[1]
