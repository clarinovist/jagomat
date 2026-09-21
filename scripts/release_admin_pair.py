"""Receipt admin sah lintas image, termasuk crash sebelum finalisasi jurnal."""
SUMBER_BANTU = r'''
import json, sqlite3
from pathlib import Path
from contextlib import closing
import admin_store, admin_students, admin_service, admin_contracts, auth
import database, learning_profile, learning_profile_admin
akar_admin=Path('/data/admin-pair')
admin=akar_admin/'admin.db'; belajar=akar_admin/'belajar.db'; sandi=akar_admin/'sandi.json'
def perintah_admin():
    akun=auth.cari_akun('probe-pair-admin',path=sandi)
    return admin_contracts.PerintahProfilSiswa('op_pair_profil',akun['id_akun'],
        auth.revisi_auth(akun),admin_contracts.AKSI_UBAH_KELAS_SEKOLAH,1,0,5,'t'*64)
def arsip_admin(path):
    with closing(sqlite3.connect(str(path))) as kon:
        return {r[0]:[list(b) for b in kon.execute('SELECT * FROM "'+r[0]+'" ORDER BY rowid')]
                for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()}
'''
SUMBER_TULIS = SUMBER_BANTU + r'''
akar_admin.mkdir()
admin_store.siapkan(admin,sekarang=1)
database.siapkan(belajar);admin_students.siapkan(belajar)
auth.tambah_akun('probe-pair-admin','sandi-pair-sintetis-123','admin',sandi)
with database.buka(belajar) as kon:
    assert database.tambah_siswa(kon,'Siswa Sintetis Pair','P3',pemilik='guru')==1
try:
    admin_service.ubah_kelas_sekolah(admin,sandi,belajar,perintah_admin(),sekarang=3,failpoint='setelah_commit')
except admin_service.CrashSebelumFinalisasi: pass
else: raise AssertionError('crash_receipt_tidak_tercapai')
receipt=learning_profile_admin.baca_receipt(belajar,sandi,perintah_admin())
assert receipt is not None
Path('/data/admin-pair-before.json').write_text(json.dumps(arsip_admin(belajar),sort_keys=True))
'''
SUMBER_BACA = SUMBER_BANTU + r'''
awal_admin=json.loads(Path('/data/admin-pair-before.json').read_text())
assert arsip_admin(belajar)==awal_admin, 'receipt_admin_berubah'
for _ in range(2):
    admin_store.siapkan(admin,sekarang=4)
    hasil=admin_service.ubah_kelas_sekolah(admin,sandi,belajar,perintah_admin(),sekarang=4)
    assert hasil.hasil.status=='succeeded' and not hasil.baru_dieksekusi
assert arsip_admin(belajar)==awal_admin, 'replay_receipt_menulis_ulang'
with database.buka(belajar) as kon:
    profil=learning_profile.baca(kon,1,pemilik='guru')
    assert profil.kelas_sekolah==5 and profil.revisi==1
    assert kon.execute('SELECT COUNT(*) FROM operasi_admin_profil').fetchone()[0]==1
with admin_store.buka_baca(admin) as kon:
    assert kon.execute('PRAGMA user_version').fetchone()[0]==5
    assert kon.execute("SELECT status FROM operasi_admin WHERE operasi_id='op_pair_profil'").fetchone()[0]=='succeeded'
    assert kon.execute("SELECT COUNT(*) FROM receipt_admin WHERE operasi_id='op_pair_profil'").fetchone()[0]==1
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
Path('/data/admin-pair-positive.json').write_text(json.dumps({'replay':2,'receipt':1,'revisi':1},sort_keys=True))
'''
