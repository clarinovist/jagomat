"""Sumber hilang tidak bertahan sebagai episode hambatan."""
import auth
import database
import sensor_cleanup
import sensor_schema
import sensor_store as s
from test_subscription_service import keluarga
from test_subscription_store import T0


def test_cleanup_batch_melewati_501(keluarga):
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    with s.buka(k.admin,tulis=True) as c:
        for i in range(501):
            gen=format(i,'032x')
            c.execute('INSERT INTO sensor_peserta VALUES(?,?,?,?,?,?,?,?,?)',
                      ('akun_'+gen,gen,'f'*64,s.BOOT,T0,T0+7776000,'sensor-keluarga-v1',0,0))
            c.execute('INSERT INTO sensor_episode VALUES(?,?,?,?)',(gen,'e'*64,'manual',T0+1))
    for _ in range(6):
        sensor_cleanup.bersihkan(k.admin,k.db,k.admin.parent/'missing.db',k.auth,sekarang=T0+3)
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_episode').fetchone()


def test_cleanup_memegang_lock_sebelum_snapshot(keluarga,monkeypatch):
    import sqlite3
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    s.setuju(k.admin,k.auth,k.principal,hasil=False,chat=False,sekarang=T0)
    connect=sqlite3.connect
    checked=[]
    def buka(path,*args,**kw):
        if str(path).startswith(k.db.resolve().as_uri()):
            with connect(k.admin,timeout=0) as sink:
                try:
                    sink.execute('BEGIN IMMEDIATE')
                except sqlite3.OperationalError:
                    checked.append(True)
                else:
                    raise AssertionError('snapshot sumber dibaca tanpa lock sink')
        return connect(path,*args,**kw)
    monkeypatch.setattr(sqlite3,'connect',buka)
    sensor_cleanup.bersihkan(k.admin,k.db,k.admin.parent/'missing.db',k.auth,sekarang=T0+3)
    assert checked


def test_cleanup_sumber_hilang_tanpa_isi(keluarga,monkeypatch):
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    s.setuju(k.admin,k.auth,k.principal,hasil=True,chat=True,sekarang=T0)
    izin=s.izin(k.admin,k.principal.id_akun,sekarang=T0)
    s.catat_sesi(k.admin,izin,999,kode='disiapkan',dibuat=T0+1,jalur='manual',sekarang=T0+2)
    s.catat_chat(k.admin,izin,'q',dibuat=T0+1,sekarang=T0+2,kategori='hasil')
    sensor_cleanup.bersihkan(k.admin,k.db,k.admin.parent/'missing-chat.db',k.auth,sekarang=T0+3)
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_episode').fetchone()
        assert not c.execute('SELECT 1 FROM sensor_chat').fetchone()
        assert c.execute('SELECT 1 FROM sensor_peserta').fetchone()
