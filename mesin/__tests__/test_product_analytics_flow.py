"""Alur opt-in→registrasi→cetak→survei→cabut dengan akun sintetis saja."""

import time
import pytest
import auth
import admin_store
import database
import product_analytics_http as h
import product_analytics_store as s
from test_admin_http_c import server, _login, _minta, SANDI_ADMIN
from test_subscription_http import FormParser


def test_registrasi_cetak_survei_cabut_dan_replay(server,monkeypatch):
    monkeypatch.setattr(h,'KOLEKSI_SIAP',True)
    monkeypatch.setattr(s,'PENCATATAN_GAGAL',False)
    now=int(time.time())
    admin=auth.autentikasi('Admin-C',SANDI_ADMIN)
    s.atur_eksperimen(admin_store.BAWAAN,auth.BERKAS_SANDI,admin,operasi='uji_flow_start',mulai=now,aktif=True,revisi=0,sekarang=now)
    body=_minta(server,'/daftar')[1]
    form=FormParser(body).forms['/daftar']
    form.update(nama='Keluarga-flow',sandi='sandi-flow-sintetis',setuju='1',analitik='1',sumber_analitik='rekomendasi')
    assert _minta(server,'/daftar',data=form)[0]==303
    p=auth.autentikasi('Keluarga-flow','sandi-flow-sintetis')
    token=_login(server,'Keluarga-flow','sandi-flow-sintetis')
    with database.buka() as c:
        sid=database.tambah_siswa(c,'Profil flow','P3',pemilik=p.pengguna)
        sesi=database.buat_sesi(c,sid,seed=7)
    assert _minta(server,'/lembar/'+str(sesi),cookie=token)[0]==200
    # Respons dikirim sebelum koleksi best-effort; tunggu tail request server.
    for _ in range(50):
        with admin_store.buka_baca() as c:
            tercatat=c.execute('SELECT COUNT(*) FROM kpi_aktivitas').fetchone()[0]
        if tercatat: break
        time.sleep(.01)
    assert tercatat==1
    body=_minta(server,'/guru',cookie=token)[1]
    sf=FormParser(body).forms['/analitik/survei']
    assert _minta(server,'/analitik/survei',cookie=token,data={**sf,'jawaban':'ya'})[0]==303
    body=_minta(server,'/akun?section=akun',cookie=token)[1]
    cf=FormParser(body).forms['/analitik/cabut']
    assert _minta(server,'/analitik/cabut',cookie=token,data={**cf,'konfirmasi':'1'})[0]==303
    assert s.status_peserta(admin_store.BAWAAN,auth.BERKAS_SANDI,p) is None
    # Receipt registrasi lama tidak menghidupkan consent yang dicabut.
    _minta(server,'/daftar',data=form)
    assert s.status_peserta(admin_store.BAWAAN,auth.BERKAS_SANDI,p) is None
    assert _minta(server,'/lembar/'+str(sesi),cookie=token)[0]==200
    with admin_store.buka_baca() as c:
        assert c.execute('SELECT COUNT(*) FROM kpi_aktivitas').fetchone()[0]==0


def test_gagal_sink_tidak_membatalkan_registrasi(server,monkeypatch):
    monkeypatch.setattr(h,'KOLEKSI_SIAP',True)
    monkeypatch.setattr(s,'PENCATATAN_GAGAL',False)
    now=int(time.time());admin=auth.autentikasi('Admin-C',SANDI_ADMIN)
    s.atur_eksperimen(admin_store.BAWAAN,auth.BERKAS_SANDI,admin,operasi='uji_flow_fail',mulai=now,aktif=True,revisi=0,sekarang=now)
    body=_minta(server,'/daftar')[1];form=FormParser(body).forms['/daftar']
    form.update(nama='Keluarga-fail',sandi='sandi-flow-sintetis',setuju='1',analitik='1')
    def gagal(*a,**kw):raise admin_store.StoreBelumSiap('gagal sintetis')
    monkeypatch.setattr(s,'setuju',gagal)
    assert _minta(server,'/daftar',data=form)[0]==303
    assert auth.autentikasi('Keluarga-fail','sandi-flow-sintetis')
    assert s.PENCATATAN_GAGAL
    assert not s.laporan(admin_store.BAWAAN,sekarang=now,bulan='2026-09')[1].kualitas
