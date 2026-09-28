"""Mutation guard receipt registrasi vs hapus siswa/login pada salinan isolasi.

Tiga guard fail-closed (siswa via saga, siswa via halaman akun, login guru via
panel admin) dimatikan satu per satu; test jalur nyata wajib merah lalu hijau.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
KASUS = (
    ('siswa_saga', 'admin_students.py',
     '("registrasi_profil_anak", "siswa_id"),',
     '',
     'test_admin_student_delete_saga.py',
     'test_receipt_registrasi_terlindungi_ditolak_effect_zero'),
    ('siswa_halaman', 'account_pages.py',
     'SELECT 1 FROM registrasi_profil_anak WHERE siswa_id = ? LIMIT 1',
     'SELECT 1 FROM registrasi_profil_anak WHERE siswa_id = ? AND 0 LIMIT 1',
     'test_akun.py',
     'test_hapus_siswa_ber_receipt_registrasi_ditolak'),
    ('login_registrasi', 'admin_accounts.py',
     'if _akun_terikat_registrasi(mentah, perintah.target_id):',
     'if False:',
     'test_admin_accounts_actual.py',
     'test_hapus_login_guru_terikat_registrasi_ditolak_effect_zero'),
    ('login_intent_rusak', 'admin_accounts.py',
     'if type(intent) is not dict:\n        return True',
     'if type(intent) is not dict:\n        return False',
     'test_admin_accounts_actual.py',
     'test_hapus_login_guru_metadata_registrasi_rusak_fail_closed'),
    ('login_item_rusak', 'admin_accounts.py',
     'if type(item) is not dict or type(item.get("akun_id")) is not str:\n            return True',
     'if type(item) is not dict or type(item.get("akun_id")) is not str:\n            return False',
     'test_admin_accounts_actual.py',
     'test_hapus_login_guru_metadata_registrasi_rusak_fail_closed'),
)
BERKAS_UJI = ('test_admin_student_delete_saga.py', 'test_akun.py',
              'test_admin_accounts_actual.py')


@pytest.mark.parametrize('nama,modul,lama,baru,berkas,tes', KASUS, ids=[k[0] for k in KASUS])
def test_guard_receipt_merah_pulih(tmp_path, nama, modul, lama, baru, berkas, tes):
    source = tmp_path / 'mesin'
    source.mkdir()
    for f in (AKAR / 'mesin').glob('*.py'):
        shutil.copy2(f, source / f.name)
    for b in BERKAS_UJI:
        shutil.copy2(Path(__file__).with_name(b), tmp_path / b)
    target = source / modul
    asli = target.read_text()
    assert asli.count(lama) == 1
    target.write_text(asli.replace(lama, baru))
    argv = [sys.executable, '-B', '-m', 'pytest', berkas, '-k', tes,
            '-q', '-W', 'error', '-p', 'no:cacheprovider']
    env = {'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(source),
           'PYTHONDONTWRITEBYTECODE': '1', 'OSN_PBKDF2_ITERASI': '1000'}

    def run():
        return subprocess.run(argv, env=env, cwd=tmp_path, capture_output=True,
                              text=True, timeout=60)

    merah = run()
    assert merah.returncode == 1 and ('AssertionError' in merah.stdout
                                      or 'DID NOT RAISE' in merah.stdout), merah.stdout + merah.stderr
    assert 'ImportError' not in merah.stdout
    target.write_text(asli)
    hijau = run()
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr
