"""Penghapusan HTTP tidak meninggalkan episode hantu saat koleksi OFF."""
import time

import auth
import admin_store
import database
import sensor_http as h
import sensor_store as s
import sensor_schema
from test_admin_http_c import server,_login,_minta
from http_test_kit import SANDI_GURU


def test_hapus_http_membersihkan_episode(server,monkeypatch):
    sensor_schema.migrasikan(admin_store.BAWAAN)
    monkeypatch.setattr(h,'SIAP',True)
    p=auth.autentikasi('guru',SANDI_GURU)
    now=int(time.time())
    s.setuju(admin_store.BAWAAN,auth.BERKAS_SANDI,p,hasil=True,chat=False,sekarang=now-2)
    with server.buka() as c:
        siswa=database.tambah_siswa(c,'Sumber-hapus','P3',pemilik='guru')
        sid=database.buat_sesi(c,siswa,seed=6)
    h.sesi(sid,'disiapkan',pengguna='guru',peran='guru')
    with s.buka(admin_store.BAWAAN) as c:
        assert c.execute('SELECT 1 FROM sensor_episode').fetchone()
    token=_login(server,'guru',SANDI_GURU)
    monkeypatch.setattr(h,'SIAP',False)
    assert _minta(server,'/sesi/%d/hapus'%sid,cookie=token,data={'konfirmasi':'1'})[0]==303
    with s.buka(admin_store.BAWAAN) as c:
        assert not c.execute('SELECT 1 FROM sensor_episode').fetchone()
