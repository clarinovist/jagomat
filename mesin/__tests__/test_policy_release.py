"""Receipt policy lintas proses/recovery dan backup turunan."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import admin_backup
import ai_store
from test_admin_backup import _buat_bundle

ROOT=Path(__file__).resolve().parents[2]


def test_pair_policy_lintas_proses(tmp_path):
    spec=importlib.util.spec_from_file_location('pair',ROOT/'scripts/release_policy_pair.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    for source,marker in ((m.SUMBER_TULIS,'OSN_POLICY_WRITER_OK'),(m.SUMBER_BACA,'OSN_POLICY_RECOVERY_OK'),(m.SUMBER_KEMBALI,'OSN_POLICY_RETURN_OK')):
        script=tmp_path/'probe.py';script.write_text(source.replace('/data/',str(tmp_path)+'/'))
        r=subprocess.run([sys.executable,'-B',str(script)],env={**os.environ,'PYTHONPATH':str(ROOT/'mesin'),'OSN_PBKDF2_ITERASI':'1000'},capture_output=True,text=True,timeout=30)
        assert r.returncode==0,r.stdout+r.stderr
        assert r.stdout.strip()==marker


def test_backup_policy_optional(tmp_path):
    bundle=_buat_bundle(tmp_path)
    assert not admin_backup.validasi_bundle(bundle).skema_policy
    hasil=admin_backup.rehearsal_bundle(bundle,migrator_ai=ai_store.siapkan,target_policy=True)
    assert hasil.skema_policy and hasil.skema_sensor
    assert not admin_backup.validasi_bundle(bundle).skema_policy
