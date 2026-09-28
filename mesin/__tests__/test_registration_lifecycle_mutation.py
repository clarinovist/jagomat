"""Mutation backup registrasi pada salinan source dan fixture terisolasi."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR=Path(__file__).resolve().parents[2]
KASUS=(
 ('public_binding','row is None or public != harapan or account is None','row is None or account is None',
  'test_backup_tolak_pasangan_registrasi_rusak[public_hash]'),
 ('owner',"or profil[0] != account['pengguna']","or False",
  'test_backup_tolak_pasangan_registrasi_rusak[owner]'),
 ('pending_flag','or bool(registrasi_pending)','or False',
  'test_backup_registrasi_terkait_dan_pending[setelah_intent]'),
 ('orphan','if not db_ops <= set(intent):','if False:',
  'test_backup_tolak_pasangan_registrasi_rusak[tanpa_intent]'),
)


@pytest.mark.parametrize('nama,lama,baru,tes',KASUS,ids=[x[0] for x in KASUS])
def test_backup_registrasi_mutasi_merah_pulih(tmp_path,nama,lama,baru,tes):
    source=tmp_path/'mesin';source.mkdir()
    for f in (AKAR/'mesin').glob('*.py'):shutil.copy2(f,source/f.name)
    for name in ('test_registration_lifecycle.py','test_admin_backup.py'):
        shutil.copy2(Path(__file__).with_name(name),tmp_path/name)
    target=source/'admin_backup.py';asli=target.read_text();assert asli.count(lama)==1
    mutasi=asli.replace(lama,baru)
    if nama=='owner':
        guard="if profil is None or admin_registration._sidik_registrasi(profil[0].casefold()) != item['alias_sidik']:"
        assert mutasi.count(guard)==1
        mutasi=mutasi.replace(guard,'if profil is None:')
    target.write_text(mutasi)
    cmd=[sys.executable,'-B','-m','pytest','test_registration_lifecycle.py','-k',tes,'-q','-W','error','-p','no:cacheprovider']
    env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(source),'OSN_PBKDF2_ITERASI':'1000','PYTHONDONTWRITEBYTECODE':'1'}
    def run():return subprocess.run(cmd,cwd=tmp_path,env=env,capture_output=True,text=True,timeout=30)
    merah=run();assert merah.returncode==1 and ('AssertionError' in merah.stdout or 'DID NOT RAISE' in merah.stdout),merah.stdout+merah.stderr
    assert 'ImportError' not in merah.stdout
    target.write_text(asli);hijau=run();assert hijau.returncode==0,hijau.stdout+hijau.stderr
