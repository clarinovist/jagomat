"""Probe registrasi profil C→B→C, fixture privat sintetis tanpa provider."""
BERSAMA = r'''
import contextlib, hashlib, json, os, sqlite3
from pathlib import Path
import admin_registration as reg, admin_store, database, auth, admin_backup
root = Path('/data/registration-pair')
pa, ph, pd = root/'admin.db', root/'sandi.json', root/'belajar.db'
now = 1800000000

def rows(path):
    with contextlib.closing(sqlite3.connect(path)) as c:
        assert c.execute('PRAGMA integrity_check').fetchall()==[('ok',)]
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        return {t:[list(r) for r in c.execute('SELECT * FROM "'+t+'" ORDER BY rowid')]
                for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
def snapshot():
    return dict(belajar=rows(pd),admin=rows(pa),auth=hashlib.sha256(ph.read_bytes()).hexdigest())
def simpan(nama,x): (root/nama).write_text(json.dumps(x,sort_keys=True))
def baca(nama): return json.loads((root/nama).read_text())
def migrasi():
    for _ in range(2):
        reg.migrasikan_profil_registrasi(pd)
        database.siapkan(pd)
    with database.buka(pd) as c:reg.validasi_schema_profil(c)
def kw(n):
    return dict(operasi_id='register_pair_'+str(n),alias='keluarga-pair-reg-'+str(n),
        sandi='sandi-pair-sintetis',token_form=str(n)*64,nama_anak='Profil Sintetis '+str(n),
        kelas_sekolah=4,profil_parameter='P4',sekarang=now)
def daftar(n,**lain): return reg.daftar_dengan_profil(pa,ph,pd,**kw(n),**lain)
def status(pending):
    assert admin_backup._validasi_registrasi_profil(pd,ph)==(True,pending), 'status_registrasi_pair'
'''
SUMBER_TULIS = BERSAMA + r'''
root.mkdir()
database.siapkan(pd);admin_store.siapkan(pa,sekarang=now)
auth.tambah_akun('admin-pair-reg','sandi-admin-sintetis','admin',ph)
with database.buka(pd) as c:
    assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='registrasi_profil_anak'").fetchone(), 'startup_migrasi_registrasi'
awal=snapshot();migrasi()
assert rows(pa)==awal['admin'] and hashlib.sha256(ph.read_bytes()).hexdigest()==awal['auth']
assert all(rows(pd).get(t)==r for t,r in awal['belajar'].items()), 'migrasi_registrasi_mengubah_histori'
assert rows(pd)['registrasi_profil_anak']==[], 'migrasi_registrasi_membuat_receipt'
daftar(1)
for n,titik in ((2,'setelah_intent'),(3,'setelah_db')):
    try: daftar(n,failpoint=titik)
    except reg.RegistrasiBelumSelesai: pass
    else: raise AssertionError('failpoint_registrasi_tidak_jalan')
status(2);simpan('awal.json',snapshot())
print('OSN_REGISTRATION_WRITER_OK')
'''
SUMBER_BACA = BERSAMA + r'''
awal=baca('awal.json');migrasi()
assert snapshot()==awal, 'recovery_mengubah_intent_receipt'
status(2)
for n in (1,2,3):
    satu=daftar(n);snap=snapshot();dua=daftar(n)
    assert satu.id_akun==dua.id_akun and satu.siswa_id==dua.siswa_id
    assert snapshot()==snap, 'replay_registrasi_duplikat'
status(0)
with database.buka(pd) as c:
    assert c.execute('SELECT COUNT(*) FROM siswa').fetchone()[0]==3
    assert c.execute('SELECT COUNT(*) FROM registrasi_profil_anak').fetchone()[0]==3
    for sql in ('DELETE FROM registrasi_profil_anak','UPDATE registrasi_profil_anak SET siswa_id=siswa_id',
                'INSERT OR REPLACE INTO registrasi_profil_anak SELECT * FROM registrasi_profil_anak'):
        try:c.execute(sql)
        except sqlite3.IntegrityError:pass
        else:raise AssertionError('receipt_registrasi_mutable')
assert rows(pa)==awal['admin'], 'registrasi_mengaktifkan_billing'
simpan('recovery.json',snapshot())
print('OSN_REGISTRATION_RECOVERY_OK')
'''
SUMBER_KEMBALI = BERSAMA + r'''
akhir=baca('recovery.json');migrasi();status(0)
assert snapshot()==akhir, 'return_registrasi_berubah'
for n in (1,2,3):daftar(n)
assert snapshot()==akhir, 'return_registrasi_duplikat'
print('OSN_REGISTRATION_RETURN_OK')
'''
