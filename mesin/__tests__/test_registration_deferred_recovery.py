"""Bukti batas recovery lama terhadap registrasi yang belum memilih variasi."""
from pathlib import Path
import subprocess
import tarfile

from test_package_release_pair import jalankan
from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
BASELINE_LAMA = 'dc79c82d0546602cdd354244eea872f27a03dc95'
BERSAMA = '''
from pathlib import Path
import admin_registration as reg, admin_store, auth, database
p = Path('/data/deferred'); p.mkdir(exist_ok=True)
paths = p/'admin.db', p/'auth.json', p/'belajar.db'
kw = dict(operasi_id='register_deferred_01', alias='keluarga-sintetis',
          sandi='sandi-sintetis-panjang', token_form='x'*64,
          nama_anak='Profil Sintetis', kelas_sekolah=6, profil_parameter=None, sekarang=1800000000)
'''


def test_recovery_lama_menolak_replay_tanpa_variasi_tanpa_merusak(tmp_path):
    arsip = tmp_path / 'recovery.tar'
    with arsip.open('wb') as keluar:
        subprocess.run(['git', '-C', str(AKAR), 'archive', BASELINE_LAMA, 'mesin'],
                       stdout=keluar, check=True)
    source = tmp_path / 'recovery'
    source.mkdir()
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, source)
    tulis = BERSAMA + '''
admin_store.siapkan(paths[0]); database.siapkan(paths[2]); reg.migrasikan_profil_registrasi(paths[2])
auth.tambah_akun('admin-sintetis','sandi-admin-sintetis','admin',paths[1])
try: reg.daftar_dengan_profil(*paths, **kw, failpoint='setelah_db')
except reg.RegistrasiBelumSelesai: pass
else: raise AssertionError('failpoint tidak berjalan')
'''
    hasil = jalankan(AKAR / 'mesin', tulis, tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    baca_lama = BERSAMA + '''
awal = paths[1].read_bytes()
with database.buka(paths[2]) as kon: db_awal = tuple(kon.iterdump())
try: reg.daftar_dengan_profil(*paths, **kw)
except ValueError as e: assert 'variasi' in str(e)
else: raise AssertionError('baseline historis ternyata menerima profil kosong')
assert paths[1].read_bytes() == awal
with database.buka(paths[2]) as kon: assert tuple(kon.iterdump()) == db_awal
assert auth.cari_akun(kw['alias'], paths[1]) is None
'''
    hasil = jalankan(source / 'mesin', baca_lama, tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    pulih = BERSAMA + '''
satu = reg.daftar_dengan_profil(*paths, **kw)
assert reg.daftar_dengan_profil(*paths, **kw).siswa_id == satu.siswa_id
with database.buka(paths[2]) as kon:
    assert [tuple(b) for b in kon.execute('SELECT tingkat FROM siswa')] == [('',)]
    assert kon.execute('SELECT COUNT(*) FROM registrasi_profil_anak').fetchone()[0] == 1
'''
    hasil = jalankan(AKAR / 'mesin', pulih, tmp_path)
    assert hasil.returncode == 0, hasil.stderr
