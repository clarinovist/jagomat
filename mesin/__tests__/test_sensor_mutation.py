"""Guard sensor harus gagal saat dimutasi di salinan source sintetis."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR=Path(__file__).resolve().parents[1]
KASUS=(
    ('sensor_store.py',"row['boot'] != BOOT",'False','test_sensor_store.py','test_consent_race_reconsent_boot_cabut'),
    ('sensor_store.py',"return _izin(row, sekarang) == sumber",'return True','test_sensor_store.py','test_snapshot_izin_berubah_ditolak_sebelum_tulis'),
    ('sensor_store.py',"dibuat <= sumber.mulai or dibuat > sekarang or sekarang >= dibuat + d.RETENSI_DETAIL",'False','test_sensor_store.py','test_sumber_lama_dan_payload_asing_ditolak'),
    ('sensor_store.py',"and hasil is not None and sumber.hasil",'and hasil is not None','test_sensor_store.py','test_izin_opsional_tidak_boleh_menyimpan_hasil'),
    ('sensor_http.py',"(peran == 'guru' and pengguna != row['pemilik'])",'False','test_sensor_http.py','test_adapter_kepemilikan_dan_sink_gagal'),
    ('sensor_report.py','if keluarga < 5:','if keluarga < 1:','test_sensor_report.py','test_sampel_kecil_tidak_terlihat_dari_total'),
)


@pytest.mark.parametrize('modul,lama,baru,berkas,nama',KASUS)
def test_guard_sensor_merah_hijau(tmp_path,modul,lama,baru,berkas,nama):
    target=tmp_path/'mesin';target.mkdir()
    for source in AKAR.glob('*.py'):
        shutil.copyfile(source,target/source.name)
    shutil.copytree(AKAR/'__tests__',target/'__tests__',ignore=shutil.ignore_patterns('__pycache__'))
    path=target/modul;teks=path.read_text()
    assert teks.count(lama)==1
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    node=str(target/'__tests__'/berkas)+'::'+nama
    command=[sys.executable,'-m','pytest',node,'-q','-W','error','-p','no:cacheprovider']
    path.write_text(teks.replace(lama,baru,1))
    merah=subprocess.run(command,capture_output=True,text=True,env=env,timeout=30)
    assert merah.returncode==1 and 'AssertionError' in merah.stdout,merah.stdout+merah.stderr
    path.write_text(teks)
    hijau=subprocess.run(command,capture_output=True,text=True,env=env,timeout=30)
    assert hijau.returncode==0,hijau.stdout+hijau.stderr
