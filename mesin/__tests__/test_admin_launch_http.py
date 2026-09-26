"""Rute panel layanan dan pengaman form melalui server sintetis."""

import pytest
import auth
import admin_store
import admin_operations
import admin_launch_http
import admin_launch_service
import admin_subscription
import midtrans_contract
import subscription
import product_analytics_store
from test_admin_http_c import server, _login, _minta, _hidden, SANDI_ADMIN, SANDI_ORANG_TUA
from test_subscription_store import dump


@pytest.mark.parametrize('section',['langganan','perhatian','operasional','kpi'])
def test_admin_panel_terbuka_dan_privat(server,section):
    token=_login(server,'Admin-C',SANDI_ADMIN)
    code,body,headers=_minta(server,'/admin?section='+section,cookie=token)
    assert code==200
    assert 'aria-current="page"' in body and 'Panel Pengelola' in body
    assert headers['Cache-Control']=='no-store' and headers['Referrer-Policy']=='no-referrer'
    assert '/admin?section=kpi' in body


@pytest.mark.parametrize('section',['langganan','perhatian','operasional','kpi'])
def test_nonadmin_tidak_membaca_layanan(server,section,monkeypatch):
    def tolak(*a,**kw): pytest.fail('lookup layanan sebelum guard')
    monkeypatch.setattr(admin_operations,'ringkasan',tolak)
    monkeypatch.setattr(product_analytics_store,'laporan',tolak)
    path='/admin?section='+section
    a=_minta(server,path)[:2]
    b=_minta(server,path,auth_basic=('Ortu-C',SANDI_ORANG_TUA))[:2]
    assert a==b and a[0]==404


def test_biaya_http_csrf_reauth_replay(server):
    token=_login(server,'Admin-C',SANDI_ADMIN)
    code,body,_=_minta(server,'/admin?section=kpi&bulan=2026-09',cookie=token)
    assert code==200
    data=dict(csrf=_hidden(body,'csrf'),tinjauan=_hidden(body,'tinjauan'),reauth=SANDI_ADMIN,
              anggaran='475000',server='200000',domain='25000',ai='10000',pendukung='0',lengkap='1')
    awal=dump(admin_store.BAWAAN)
    assert _minta(server,'/admin/layanan/biaya',cookie=token,data={**data,'csrf':'rusak'})[0]==403
    assert _minta(server,'/admin/layanan/biaya',cookie=token,data={**data,'reauth':'salah'})[0]==403
    assert dump(admin_store.BAWAAN)==awal
    for _ in range(2):
        assert _minta(server,'/admin/layanan/biaya',cookie=token,data=data)[0]==303
    with admin_store.buka_baca() as c:
        assert c.execute('SELECT COUNT(*) FROM kpi_audit_biaya').fetchone()[0]==1
    body=_minta(server,'/admin?section=kpi&bulan=2026-09',cookie=token)[1]
    assert 'Rp235.000' in body
    assert '<summary aria-label="Info Memakai kembali">' in body
    assert 'Belum ada eksperimen' in body


def test_sakelar_pembayaran_http_gate_reauth_csrf_dan_tahap(server,monkeypatch):
    token=_login(server,'Admin-C',SANDI_ADMIN)
    body=_minta(server,'/admin?section=operasional',cookie=token)[1]
    assert 'Tahap saat ini: <strong>nonaktif</strong>' in body
    assert 'Tidak membuat atau memeriksa pembayaran.' in body
    assert 'Tahap tujuan' in body and 'Terapkan perubahan tahap' in body
    form=dict(csrf=_hidden(body,'csrf'),tinjauan=_hidden(body,'tinjauan'),
              reauth=SANDI_ADMIN,tahap='rekonsiliasi',konfirmasi='1')
    awal=dump(admin_store.BAWAAN)
    assert _minta(server,'/admin/layanan/pembayaran',cookie=token,data={**form,'csrf':'rusak'})[0]==403
    assert _minta(server,'/admin/layanan/pembayaran',cookie=token,data={**form,'reauth':'salah'})[0]==403
    assert dump(admin_store.BAWAAN)==awal
    # Default readiness false: panel tidak bisa mengaktifkan hanya lewat UI.
    assert _minta(server,'/admin/layanan/pembayaran',cookie=token,data=form)[0]==400
    with admin_store.buka_baca() as c:
        assert admin_launch_service.konfigurasi_pembayaran(c)['tahap']=='nonaktif'
        assert not c.execute('SELECT 1 FROM pembayaran_audit').fetchone()
    siap=dict(provider_produksi=True,callback=True,recovery=True,kebijakan=True)
    server.server.pembayaran_runtime=admin_subscription.RuntimePembayaran(
        midtrans_contract.Konfigurasi('production','kunci-produksi-sintetis','M_SINTETIS'),
        lambda *a,**kw:None,subscription.SAKELAR,siap)
    for _ in range(2):
        assert _minta(server,'/admin/layanan/pembayaran',cookie=token,data=form)[0]==303
    with admin_store.buka_baca() as c:
        cfg=admin_launch_service.konfigurasi_pembayaran(c)
        assert cfg['tahap']=='rekonsiliasi' and cfg['revisi']==2
        assert c.execute('SELECT COUNT(*) FROM pembayaran_audit').fetchone()[0]==1
    body=_minta(server,'/admin?section=operasional',cookie=token)[1]
    assert 'Tahap saat ini: <strong>rekonsiliasi</strong>' in body
    assert 'Key/provider produksi: <strong>Siap</strong>' in body
    assert 'kunci-sintetis' not in body and 'Server Key' not in body


def test_periksa_http_meneruskan_clock_selesai(server,monkeypatch):
    token=_login(server,'Admin-C',SANDI_ADMIN)
    tertangkap={}
    monkeypatch.setattr(admin_launch_http.billing,'runtime_penangan',lambda _:object())
    monkeypatch.setattr(admin_launch_http.billing,'periksa',lambda *a,**kw: tertangkap.update(kw) or 'belum_terverifikasi')
    akun=auth.cari_akun('Ortu-C')
    admin=auth.cari_akun('Admin-C')
    tinjauan=admin_launch_http.admin_security.buat_tinjauan(
        admin,token,'periksa_pembayaran',{'akun':akun['id_akun'],'invoice':'inv_'+'a'*32,'revisi':auth.revisi_auth(akun)})
    csrf=admin_launch_http.h._csrf(admin,token)
    data=dict(csrf=csrf,tinjauan=tinjauan,reauth=SANDI_ADMIN)
    assert _minta(server,'/admin/layanan/periksa',cookie=token,data=data)[0]==303
    assert tertangkap['jam'] is admin_launch_http.time.time


def test_nonadmin_post_tidak_mutasi(server):
    awal=dump(admin_store.BAWAAN)
    for endpoint in ['biaya','eksperimen','periksa','pembayaran','cari','transisi']:
        a=_minta(server,'/admin/layanan/'+endpoint,data={})[:2]
        b=_minta(server,'/admin/layanan/'+endpoint,data={},auth_basic=('Ortu-C',SANDI_ORANG_TUA))[:2]
        assert a==b and a[0]==404
    assert dump(admin_store.BAWAAN)==awal


def test_transisi_http_aktivasi_idempoten_dan_guard(server):
    token=_login(server,'Admin-C',SANDI_ADMIN)
    with admin_store._transaksi(admin_store.BAWAAN) as c:
        c.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    code,body,_=_minta(server,'/admin?section=langganan',cookie=token)
    assert code==200
    csrf=_hidden(body,'csrf')
    code,body,_=_minta(server,'/admin/layanan/cari',cookie=token,data=dict(csrf=csrf,cari='Ortu-C'))
    assert code==200
    assert 'Belum terdaftar di langganan' in body and 'Aktifkan langganan' in body
    form=dict(csrf=_hidden(body,'csrf'),tinjauan=_hidden(body,'tinjauan'),
              reauth=SANDI_ADMIN,konfirmasi='1')
    awal=dump(admin_store.BAWAAN)
    assert _minta(server,'/admin/layanan/transisi',cookie=token,data={**form,'csrf':'rusak'})[0]==403
    assert _minta(server,'/admin/layanan/transisi',cookie=token,data={**form,'reauth':'salah'})[0]==403
    assert _minta(server,'/admin/layanan/transisi',cookie=token,data={**form,'konfirmasi':'0'})[0]==400
    assert dump(admin_store.BAWAAN)==awal
    for _ in range(2):
        assert _minta(server,'/admin/layanan/transisi',cookie=token,data=form)[0]==303
    akun=auth.cari_akun('Ortu-C')
    with admin_store.buka_baca(admin_store.BAWAAN) as c:
        baris=c.execute("SELECT asal FROM langganan_enrollment WHERE akun_id=?",(akun['id_akun'],)).fetchone()
        assert baris['asal']=='transisi'
        assert c.execute("SELECT COUNT(*) FROM langganan_enrollment WHERE akun_id=?",
                         (akun['id_akun'],)).fetchone()[0]==1
    code,body,_=_minta(server,'/admin/layanan/cari',cookie=token,data=dict(csrf=csrf,cari='Ortu-C'))
    assert 'Belum terdaftar di langganan' not in body


def test_transisi_http_akun_legacy_revisi_nol(server):
    token=_login(server,'Admin-C',SANDI_ADMIN)
    with admin_store._transaksi(admin_store.BAWAAN) as c:
        c.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    import json as _json
    auth.tambah_akun('Ortu-Legacy',SANDI_ORANG_TUA,'guru')
    raw=_json.loads(auth.BERKAS_SANDI.read_text())
    daftar=raw['akun'] if isinstance(raw,dict) else raw
    for a in daftar:
        if a.get('pengguna')=='Ortu-Legacy':
            a.pop('revisi_auth',None)
    auth.BERKAS_SANDI.write_text(_json.dumps(raw))
    legacy=auth.cari_akun('Ortu-Legacy')
    assert auth.revisi_auth(legacy)==0
    code,body,_=_minta(server,'/admin?section=langganan',cookie=token)
    csrf=_hidden(body,'csrf')
    code,body,_=_minta(server,'/admin/layanan/cari',cookie=token,
                       data=dict(csrf=csrf,cari='Ortu-Legacy'))
    assert code==200 and 'Aktifkan langganan' in body
    form=dict(csrf=_hidden(body,'csrf'),tinjauan=_hidden(body,'tinjauan'),
              reauth=SANDI_ADMIN,konfirmasi='1')
    assert _minta(server,'/admin/layanan/transisi',cookie=token,data=form)[0]==303,'akun legacy revisi nol'
    with admin_store.buka_baca(admin_store.BAWAAN) as c:
        baris=c.execute("SELECT asal FROM langganan_enrollment WHERE akun_id=?",
                        (legacy['id_akun'],)).fetchone()
    assert baris is not None and baris['asal']=='transisi'
