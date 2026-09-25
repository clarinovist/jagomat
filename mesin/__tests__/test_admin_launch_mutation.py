"""Mutation guard layanan pada source salinan temp; tidak memakai DB pengguna."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
KASUS = [
    ('admin_launch_service.py',"or auth.revisi_auth(cocok[0]) != principal.revisi_auth","or False",'test_otorisasi_admin_tolak_tanpa_tulis[stale]','DID NOT RAISE'),
    ('admin_launch_service.py',"if tujuan > awal + 1:","if False:",'test_sakelar_pembayaran_gate_urutan_revisi_dan_auth','DID NOT RAISE'),
    ('admin_launch_service.py',"if tujuan > awal:\n                if tujuan > 0 and not kesiapan['provider_produksi']:","if tujuan > awal:\n                if False:",'test_sakelar_pembayaran_gate_urutan_revisi_dan_auth','DID NOT RAISE'),
    ('admin_launch_service.py',"if revisi != lama['revisi']:","if False:",'test_sakelar_pembayaran_gate_urutan_revisi_dan_auth','DID NOT RAISE'),
    ('admin_launch_service.py',"tingkat = TAHAP_PEMBAYARAN.index(tahap)","tingkat = 3",'test_sakelar_pembayaran_bertahap_audit_dan_fail_closed','Sakelar'),
    ('product_analytics.py','kembali,len(matang),25','kembali,aktivasi,25','test_metrik_100_cohort_survei_dan_retensi','28, 65'),
    ('product_analytics.py','if not lengkap:', 'if False:', 'test_metrik_100_cohort_survei_dan_retensi','assert all'),
    ('product_analytics.py','sekarang >= p.t0 + 14 * HARI','sekarang >= p.t0 + 7 * HARI','test_maturity_jendela_dan_kelompok_kecil','matang'),
    ('product_analytics_store.py',"kon.execute('DELETE FROM kpi_peserta WHERE id=?',(r['id'],))","pass",'test_consent_dedup_cabut_tidak_menyentuh_belajar','assert not'),
    ('product_analytics_store.py',"if revisi != (lama[0] if lama else 0):","if False:",'test_biaya_replay_revisi_dan_negatif','audit biaya duplikat'),
    ('admin_subscription.py',"return guard.principal_hidup(auth.muat_akun(path_auth),principal)","return None",'test_otorisasi_admin_tolak_tanpa_tulis[guru]','DID NOT RAISE'),
]


@pytest.mark.parametrize('modul,lama,baru,test,marker',KASUS)
def test_mutasi_guard_aktual(tmp_path,modul,lama,baru,test,marker):
    target=tmp_path/'mesin'
    target.mkdir()
    for sumber in AKAR.glob('*.py'):
        shutil.copyfile(sumber,target/sumber.name)
    shutil.copytree(AKAR/'__tests__',target/'__tests__',ignore=shutil.ignore_patterns('__pycache__'))
    p=target/modul
    teks=p.read_text()
    assert teks.count(lama)==1
    p.write_text(teks.replace(lama,baru,1))
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    hasil=subprocess.run([sys.executable,'-m','pytest',str(target/'__tests__/test_admin_launch_domain.py')+'::'+test,'-q','-W','error','-p','no:cacheprovider'],capture_output=True,text=True,env=env,timeout=30)
    assert hasil.returncode==1,hasil.stdout+hasil.stderr
    assert marker in hasil.stdout,hasil.stdout
    p.write_text(teks)
    pulih=subprocess.run([sys.executable,'-m','pytest',str(target/'__tests__/test_admin_launch_domain.py')+'::'+test,'-q','-W','error','-p','no:cacheprovider'],capture_output=True,text=True,env=env,timeout=30)
    assert pulih.returncode==0,pulih.stdout+pulih.stderr
