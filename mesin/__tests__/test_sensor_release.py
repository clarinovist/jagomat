"""Probe pair sensor dijalankan lintas proses terhadap fixture sintetis."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

AKAR=Path(__file__).resolve().parents[2]


def test_pair_sensor_lintas_proses(tmp_path):
    spek=importlib.util.spec_from_file_location('sensor_pair',AKAR/'scripts/release_sensor_pair.py')
    m=importlib.util.module_from_spec(spek);spek.loader.exec_module(m)
    env={**os.environ,'PYTHONPATH':str(AKAR/'mesin'),'PYTHONDONTWRITEBYTECODE':'1','OSN_PBKDF2_ITERASI':'1000'}
    for source,marker in ((m.SUMBER_TULIS,'OSN_SENSOR_WRITER_OK'),
                          (m.SUMBER_BACA,'OSN_SENSOR_RECOVERY_OK'),
                          (m.SUMBER_KEMBALI,'OSN_SENSOR_RETURN_OK')):
        script=tmp_path/'probe.py'
        script.write_text(source.replace('/data/',str(tmp_path)+'/'))
        p=subprocess.run([sys.executable,'-B',str(script)],env=env,capture_output=True,text=True,timeout=30)
        assert p.returncode==0,p.stdout+p.stderr
        assert p.stdout.strip()==marker
