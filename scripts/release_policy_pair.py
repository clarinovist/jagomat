"""Probe persetujuan durable dan restore, tanpa sumber keluarga/provider."""
SUMBER_TULIS = '''
import os
os.environ['SENSOR_CONSENT_EPOCH']='1234567890abcdef1234567890abcdef'
from pathlib import Path
import auth,admin_store,policy_schema,policy_store as p,sensor_store as s
path=Path('/data/policy.db');a=Path('/data/policy-auth.json')
admin_store.siapkan(path);policy_schema.migrasikan(path);policy_schema.migrasikan(path)
auth.tambah_akun('Policy-probe','sandi-policy-sintetis','guru',a)
u=auth.autentikasi('Policy-probe','sandi-policy-sintetis',a)
p.simpan(path,a,u,revisi=0,operasi='policy_probe_00001',pilihan=(True,True,True),sekarang=100,versi=p.VERSI)
assert s.izin(path,u.id_akun,sekarang=101)
print('OSN_POLICY_WRITER_OK')
'''
SUMBER_BACA = '''
import os
os.environ['SENSOR_CONSENT_EPOCH']='1234567890abcdef1234567890abcdef'
from pathlib import Path
import auth,policy_store as p,sensor_store as s
path=Path('/data/policy.db');a=Path('/data/policy-auth.json')
u=auth.autentikasi('Policy-probe','sandi-policy-sintetis',a)
assert s.izin(path,u.id_akun,sekarang=102)
assert p.berlaku(p.baca(path,u.id_akun))
s.cabut(path,a,u)
assert not s.izin(path,u.id_akun,sekarang=103)
assert p.berlaku(p.baca(path,u.id_akun))
try:p.simpan(path,a,u,revisi=0,operasi='policy_probe_00001',pilihan=(True,True,True),sekarang=104,versi=p.VERSI)
except RuntimeError:pass
else:raise AssertionError('stale consent revived')
print('OSN_POLICY_RECOVERY_OK')
'''
SUMBER_KEMBALI = '''
import os
os.environ['SENSOR_CONSENT_EPOCH']='eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee'
from pathlib import Path
import auth,policy_store as p,sensor_store as s
path=Path('/data/policy.db');a=Path('/data/policy-auth.json')
u=auth.autentikasi('Policy-probe','sandi-policy-sintetis',a)
assert not p.berlaku(p.baca(path,u.id_akun))
assert not s.izin(path,u.id_akun,sekarang=105)
with s.buka(path) as c:
    assert not c.execute('PRAGMA foreign_key_check').fetchone()
print('OSN_POLICY_RETURN_OK')
'''
