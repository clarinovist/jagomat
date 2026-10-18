"""Alur consent/hook HTTP sensor dengan sumber sintetis."""
import sqlite3
import time

import pytest
import auth
import admin_store
import database
import sensor_http as h
import sensor_store as s
import sensor_schema
from test_admin_http_c import server, _login, _minta, SANDI_ADMIN
from test_subscription_http import FormParser
from test_subscription_service import keluarga
from test_subscription_store import T0


def test_consent_form_tidak_dicentang_dan_cabut(server,monkeypatch):
    sensor_schema.migrasikan(admin_store.BAWAAN)
    monkeypatch.setattr(h,'SIAP',True)
    auth.tambah_akun('Sensor-keluarga','sensor-sandi-123','guru')
    token=_login(server,'Sensor-keluarga','sensor-sandi-123')
    body=_minta(server,'/akun?section=akun',cookie=token)[1]
    forms=FormParser(body).forms
    form=forms['/analitik/sensor-setuju']
    markup=body.split('action="/analitik/sensor-setuju"',1)[1].split('</form>',1)[0]
    assert ' checked' not in markup
    assert _minta(server,'/analitik/sensor-setuju',cookie=token,data={**form,'alur':'1','hasil':'1','chat':'1'})[0]==303
    p=auth.autentikasi('Sensor-keluarga','sensor-sandi-123')
    assert s.izin(admin_store.BAWAAN,p.id_akun,sekarang=int(time.time())).hasil
    body=_minta(server,'/akun?section=akun',cookie=token)[1]
    form=FormParser(body).forms['/analitik/sensor-cabut']
    monkeypatch.setattr(h,'SIAP',False)
    assert _minta(server,'/analitik/sensor-cabut',cookie=token,data={**form,'konfirmasi':'1'})[0]==303
    assert s.izin(admin_store.BAWAAN,p.id_akun,sekarang=int(time.time())) is None


def test_consent_admin_anonim_dan_tamper_ditolak(server,monkeypatch):
    sensor_schema.migrasikan(admin_store.BAWAAN)
    monkeypatch.setattr(h,'SIAP',True)
    assert _minta(server,'/analitik/sensor-setuju',data={'alur':'1'})[0]==404
    token=_login(server,'Admin-C',SANDI_ADMIN)
    assert _minta(server,'/analitik/sensor-setuju',cookie=token,data={'alur':'1'})[0]==404
    with s.buka(admin_store.BAWAAN) as c:
        assert not c.execute('SELECT 1 FROM sensor_peserta').fetchone()


def test_adapter_off_tidak_membuka_data(monkeypatch):
    monkeypatch.setattr(h,'SIAP',False)
    def tolak(*a,**kw): raise AssertionError('sumber dibaca saat OFF')
    monkeypatch.setattr(sqlite3,'connect',tolak)
    h.sesi(1,'dikonfirmasi')
    h.chat_selesai(None,'request','teks',dibuat=T0)


def test_adapter_kepemilikan_dan_sink_gagal(keluarga,monkeypatch):
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    monkeypatch.setattr(h,'SIAP',True)
    monkeypatch.setattr(auth,'BERKAS_SANDI',k.auth)
    monkeypatch.setattr(admin_store,'BAWAAN',k.admin)
    monkeypatch.setattr(database,'BAWAAN',k.db)
    monkeypatch.setattr(time,'time',lambda:T0+20)
    s.setuju(k.admin,k.auth,k.principal,hasil=True,chat=True,sekarang=T0)
    with database.buka(k.db) as c:
        sid=database.tambah_siswa(c,'Anak Sensor','P3',pemilik=k.principal.pengguna)
        sesi=database.buat_sesi(c,sid,seed=1)
        c.execute("UPDATE sesi SET dibuat=datetime(?,'unixepoch','+7 hours') WHERE id=?",(T0+1,sesi))
    h.sesi(sesi,'disiapkan',pengguna='asing',peran='guru')
    h.sesi(sesi,'disiapkan',pengguna=k.principal.pengguna,peran='admin')
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_episode').fetchone()
    h.sesi(sesi,'disiapkan',pengguna=k.principal.pengguna,peran='guru')
    with s.buka(k.admin) as c:
        assert c.execute('SELECT COUNT(*) FROM sensor_episode').fetchone()[0]==1
    def gagal(*a,**kw): raise sqlite3.OperationalError('sink sintetis')
    monkeypatch.setattr(s,'catat_sesi',gagal)
    monkeypatch.setattr(s,'GAGAL',False)
    h.sesi(sesi,'disiapkan',pengguna=k.principal.pengguna,peran='guru')
    assert s.GAGAL
