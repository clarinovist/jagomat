"""Mutasi guard consent memakai source dan akun sintetis saja."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[1]
CASES=(
    ('policy_store.py',"if revisi!=(row['revisi'] if row else 0):",'if False:','test_policy_consent.py','test_receipt_migrasi_idempoten_durable_dan_cabut'),
    ('policy_store.py',"row['epoch']==EPOCH",'True','test_policy_consent.py','test_epoch_missing_restore_tidak_mewarisi'),
    ('policy_http.py',"if not akun_baru.baru or not tersedia()",'if not tersedia()','test_policy_consent.py','test_replay_registrasi_tidak_mencoba_menulis'),
)

@pytest.mark.parametrize('file,old,new,test,name',CASES)
def test_guard_policy_merah_hijau(tmp_path,file,old,new,test,name):
    target=tmp_path/'mesin';target.mkdir()
    for p in ROOT.glob('*.py'):shutil.copyfile(p,target/p.name)
    shutil.copytree(ROOT/'__tests__',target/'__tests__',ignore=shutil.ignore_patterns('__pycache__'))
    p=target/file;source=p.read_text();assert source.count(old)==1
    command=[sys.executable,'-m','pytest',str(target/'__tests__'/test)+'::'+name,'-q','-W','error','-p','no:cacheprovider']
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    p.write_text(source.replace(old,new,1))
    red=subprocess.run(command,capture_output=True,text=True,env=env,timeout=30)
    assert red.returncode==1 and ('AssertionError' in red.stdout or 'DID NOT RAISE' in red.stdout),red.stdout+red.stderr
    p.write_text(source)
    green=subprocess.run(command,capture_output=True,text=True,env=env,timeout=30)
    assert green.returncode==0,green.stdout+green.stderr
