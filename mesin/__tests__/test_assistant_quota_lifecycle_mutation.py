"""Mutasi lifecycle/recovery9 di salinan source privat, tanpa produksi."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
KASUS = (
    ('optin','mesin/admin_store.py','kon.execute("PRAGMA user_version=8")',
     'kon.execute("PRAGMA user_version=9")\n                _jalankan_ddl(kon, kuota_schema.DDL)',
     'test_startup_paket8_tidak_otomatis_mengaktifkan9', 'AssertionError'),
    ('partial','mesin/admin_store_core.py','elif kuota_schema.struktur(kon):',
     'elif False:', 'test_reader_partial8_tolak_tanpa_migrasi', 'DID NOT RAISE'),
    ('sumber','mesin/assistant_quota_store.py','or (hak.jendela_id, hak.entitlement_sidik, hak.limit, hak.sumber,',
     'or False and (hak.jendela_id, hak.entitlement_sidik, hak.limit, hak.sumber,',
     'test_sumber_pro_tidak_boleh_invoice_asing_pada_metadata_window', 'AssertionError'),
    ('unknown','mesin/admin_backup.py','or kuota_pending or kuota_unknown)',
     'or False)', 'test_backup9_unknown_pending_wajib_rekonsiliasi[unknown]', 'AssertionError'),
    ('pair','scripts/release_metadata.py','if (type(data) is not dict or data != harapan\n            or any(type(data[k]) is not type(v) for k, v in harapan.items())):',
     'if False:', 'test_probe_manifest_kuota_tidak_boleh_dihilangkan', 'DID NOT RAISE'),
)


@pytest.mark.parametrize('nama,berkas,lama,baru,tes,pesan',KASUS,ids=[k[0] for k in KASUS])
def test_mutasi_lifecycle_merah_pulih(tmp_path,nama,berkas,lama,baru,tes,pesan):
    repo=tmp_path/'repo'
    for folder in ('mesin','scripts'):
        (repo/folder).mkdir(parents=True)
        for p in (AKAR/folder).glob('*.py'):
            shutil.copy2(p,repo/folder/p.name)
    tests=repo/'mesin'/'__tests__'
    tests.mkdir()
    for nama_test in ('test_assistant_quota_lifecycle.py','test_admin_backup.py',
                      'test_quota_release_pair.py','test_package_release_pair.py','test_release_image.py'):
        shutil.copy2(AKAR/'mesin'/'__tests__'/nama_test,tests/nama_test)
    target=repo/berkas
    asli=target.read_text()
    assert asli.count(lama)==1
    target.write_text(asli.replace(lama,baru))
    argv=[sys.executable,'-B','-m','pytest',str(tests/'test_assistant_quota_lifecycle.py'),
          str(tests/'test_quota_release_pair.py'),'-k',tes,'-q','-W','error','-p','no:cacheprovider']
    env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(repo/'mesin'),
         'PYTHONDONTWRITEBYTECODE':'1','OSN_PBKDF2_ITERASI':'1000'}
    merah=subprocess.run(argv,cwd=repo,env=env,capture_output=True,text=True,timeout=30)
    assert merah.returncode==1 and pesan in merah.stdout,merah.stdout+merah.stderr
    assert 'ImportError' not in merah.stdout and 'ModuleNotFoundError' not in merah.stdout
    assert 'OperationalError' not in merah.stdout
    target.write_text(asli)
    hijau=subprocess.run(argv,cwd=repo,env=env,capture_output=True,text=True,timeout=30)
    assert hijau.returncode==0,hijau.stdout+hijau.stderr
