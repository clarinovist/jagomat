"""Consent dan survei sintetis; koleksi live tidak otomatis diaktifkan."""

import time

import pytest
import auth
import admin_store
import product_analytics_http as h
import product_analytics_store as s
from test_admin_http_c import server, _login, _minta, _hidden, SANDI_ADMIN
from test_admin_launch_domain import layanan, aktif
from test_subscription_store import T0, dump
from test_subscription_service import keluarga


def test_koleksi_default_off():
    assert not h.KOLEKSI_SIAP and not h.aktif()
    assert h.form_daftar()==''


def test_aktivasi_http_ditahan_sebelum_gate(server):
    t=_login(server,'Admin-C',SANDI_ADMIN)
    body=_minta(server,'/admin?section=kpi',cookie=t)[1]
    potong=body.split('action="/admin/layanan/eksperimen"',1)[1]
    data=dict(csrf=_hidden(potong,'csrf'),tinjauan=_hidden(potong,'tinjauan'),reauth=SANDI_ADMIN,aktif='1',konfirmasi='1')
    assert _minta(server,'/admin/layanan/eksperimen',cookie=t,data=data)[0]==503
    assert s.baca_config(admin_store.BAWAAN) is None


def test_consent_late_tidak_mengarang_cohort(layanan):
    k=layanan;aktif(k)
    s.setuju(k.admin,k.auth,k.principal,sumber='tidak_diketahui',sekarang=T0+86400,saat_daftar=False)
    row=s.status_peserta(k.admin,k.auth,k.principal)
    assert row['terlambat']==1 and row['t0']==T0


def test_retensi_hapus_tepat_90_hari(layanan):
    k=layanan;aktif(k)
    s.setuju(k.admin,k.auth,k.principal,sumber='tidak_diketahui',sekarang=T0,saat_daftar=True)
    s.catat(k.admin,k.principal.id_akun,kode='latihan_dikirim',sekarang=T0+1)
    s.retensi(k.admin,sekarang=T0+90*86400-1)
    assert s.status_peserta(k.admin,k.auth,k.principal)
    s.retensi(k.admin,sekarang=T0+90*86400)
    assert s.status_peserta(k.admin,k.auth,k.principal) is None
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute('SELECT COUNT(*) FROM kpi_aktivitas').fetchone()[0]==0


def test_token_terikat_akun_sesi_aksi_dan_expiry(layanan,monkeypatch):
    k=layanan
    monkeypatch.setattr(auth,'BERKAS_SANDI',k.auth)
    monkeypatch.setattr(time,'time',lambda:T0)
    token=h._token(k.principal,'sesi-sintetis','cabut')
    h._cek(k.principal,'sesi-sintetis','cabut',token)
    for sesi,aksi in [('sesi-lain','cabut'),('sesi-sintetis','survei')]:
        with pytest.raises(PermissionError):h._cek(k.principal,sesi,aksi,token)
    with pytest.raises(PermissionError):h._cek(k.principal,'sesi-sintetis','cabut',token[:-1]+'x')
    monkeypatch.setattr(time,'time',lambda:T0+900)
    with pytest.raises(PermissionError):h._cek(k.principal,'sesi-sintetis','cabut',token)
