"""Probe sensor C→B→C dengan data sintetis, tanpa provider."""
SUMBER_TULIS = '''
from pathlib import Path
import auth, admin_store, sensor_schema, sensor_store as s, sensor_domain as d
p=Path('/data/sensor-admin.db');a=Path('/data/sensor-auth.json')
admin_store.siapkan(p)
sensor_schema.migrasikan(p);sensor_schema.migrasikan(p)
auth.tambah_akun('Sensor-probe','sensor-sandi-sintetis','guru',a)
u=auth.autentikasi('Sensor-probe','sensor-sandi-sintetis',a)
s.setuju(p,a,u,hasil=True,chat=True,sekarang=100)
i=s.izin(p,u.id_akun,sekarang=101)
assert s.catat_sesi(p,i,1,kode='disiapkan',dibuat=101,jalur='terpandu',sekarang=102)
assert not s.catat_sesi(p,i,1,kode='disiapkan',dibuat=101,jalur='terpandu',sekarang=102)
assert s.catat_sesi(p,i,1,kode='dikonfirmasi',dibuat=101,jalur='terpandu',sekarang=103,
                    hasil=d.ringkas_hasil([dict(benar=True,kode_final=None,dilewati=False)]))
assert s.catat_chat(p,i,'request',dibuat=101,sekarang=102,kategori='penjelasan')
print('OSN_SENSOR_WRITER_OK')
'''
SUMBER_BACA = '''
from pathlib import Path
import auth, sensor_schema, sensor_store as s
p=Path('/data/sensor-admin.db');a=Path('/data/sensor-auth.json')
u=auth.autentikasi('Sensor-probe','sensor-sandi-sintetis',a)
with s.buka(p) as c:
    assert sensor_schema.validasi(c)
    assert c.execute('SELECT COUNT(*) FROM sensor_event').fetchone()[0]==2
    assert c.execute('SELECT COUNT(*) FROM sensor_hasil').fetchone()[0]==1
    assert c.execute('SELECT COUNT(*) FROM sensor_chat').fetchone()[0]==1
assert s.izin(p,u.id_akun,sekarang=104) is None
s.setuju(p,a,u,hasil=False,chat=False,sekarang=104)
with s.buka(p) as c:
    assert not c.execute('SELECT 1 FROM sensor_event').fetchone()
    assert not c.execute('SELECT 1 FROM sensor_hasil').fetchone()
    assert not c.execute('SELECT 1 FROM sensor_chat').fetchone()
i=s.izin(p,u.id_akun,sekarang=105)
assert not s.catat_sesi(p,i,1,kode='disiapkan',dibuat=101,jalur='terpandu',sekarang=105)
assert s.catat_sesi(p,i,2,kode='disiapkan',dibuat=105,jalur='manual',sekarang=106)
print('OSN_SENSOR_RECOVERY_OK')
'''
SUMBER_KEMBALI = '''
from pathlib import Path
import auth, sensor_store as s, sensor_domain as d
p=Path('/data/sensor-admin.db');a=Path('/data/sensor-auth.json')
u=auth.autentikasi('Sensor-probe','sensor-sandi-sintetis',a)
assert s.izin(p,u.id_akun,sekarang=107) is None
s.retensi(p,sekarang=106+d.RETENSI_DETAIL)
with s.buka(p) as c:
    assert not c.execute('SELECT 1 FROM sensor_episode').fetchone()
s.cabut(p,a,u)
with s.buka(p) as c:
    assert not c.execute('SELECT 1 FROM sensor_peserta').fetchone()
    assert not c.execute('PRAGMA foreign_key_check').fetchone()
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print('OSN_SENSOR_RETURN_OK')
'''
