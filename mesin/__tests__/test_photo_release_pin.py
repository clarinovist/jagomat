"""Baseline registrasi kosong exact, bukan source-copy atau kompatibilitas historis."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest
from test_release_image import ekstrak_tar_aman, jalankan_probe
from test_quota_release_pair import siapkan
from test_package_release_pair import jalankan

AKAR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(AKAR/'scripts'))
import release_metadata
import release_quota_pair as pair
import verify_release_image
import verify_submission_pair

REVISION='634e077830938dbd3ae20d17e5ac019004e97fc2'


@pytest.fixture
def recovery_foto(tmp_path):
    config=release_metadata.baca_config(AKAR/'scripts/release-metadata.json')
    assert config['recovery_revision']==REVISION
    arsip=tmp_path/'recovery-foto.tar';tujuan=tmp_path/'recovery-foto';tujuan.mkdir()
    with arsip.open('wb') as f:
        subprocess.run(['git','-C',str(AKAR),'archive',REVISION,'mesin'],stdout=f,check=True)
    with tarfile.open(arsip) as tar:ekstrak_tar_aman(tar,tujuan)
    return tujuan/'mesin'


def test_probe_baseline_foto_exact_delapan_checks(tmp_path,recovery_foto):
    hasil=jalankan_probe(tmp_path,sumber=recovery_foto,revision=REVISION)
    assert hasil.returncode==0,hasil.stdout+hasil.stderr
    data=json.loads(hasil.stdout)
    assert data==verify_release_image.ringkasan_untuk_revision(REVISION)
    assert data['photo_checks']==8 and data['quota_checks']==8 and data['provider_calls']==0


def test_pair_foto_candidate_baseline_exact_candidate(tmp_path,recovery_foto):
    siapkan(tmp_path,recovery_foto)
    assert verify_submission_pair.KUOTA_BACA==pair.SUMBER_BACA
    for source,kode in ((AKAR/'mesin',pair.SUMBER_TULIS),
                        (recovery_foto,pair.SUMBER_BACA),
                        (AKAR/'mesin',pair.SUMBER_KEMBALI)):
        hasil=jalankan(source,kode,tmp_path)
        assert hasil.returncode==0,hasil.stderr
    awal=json.loads((tmp_path/'package-pair/foto-awal.json').read_text())
    akhir=json.loads((tmp_path/'package-pair/foto-recovery.json').read_text())
    assert awal['belajar']==akhir['belajar']
    assert [r[10] for r in akhir['belajar']['operasi_foto_baca']]==['reserved','sent','unknown','result','no_output']


def test_pair_pin_foto_bukti_wajib_delapan_checks():
    bukti=dict(ok=True,candidate_revision='a'*40,recovery_revision=REVISION,
               candidate_digest='sha256:'+'a'*64,recovery_digest='sha256:'+'b'*64,
               pengiriman_pair_checks=6,pilihan_pair_checks=8,learning_pair_checks=8,
               subscription_pair_checks=4,admin_launch_pair_checks=4,package_pair_checks=8,
               quota_pair_checks=8,photo_pair_checks=8,registration_pair_checks=8,support_pair_checks=8,provider_calls=0)
    args=('a'*40,REVISION,'sha256:'+'a'*64,'sha256:'+'b'*64)
    assert release_metadata.validasi_bukti_pasangan(bukti,*args)
    for nilai in (None,0,True,7,9):
        salah=dict(bukti)
        if nilai is None:del salah['photo_pair_checks']
        else:salah['photo_pair_checks']=nilai
        with pytest.raises(ValueError):release_metadata.validasi_bukti_pasangan(salah,*args)


def test_mutasi_reader_baseline_exact_ditangkap_pair_dan_pulih(tmp_path,recovery_foto):
    siapkan(tmp_path,recovery_foto)
    awal=jalankan(AKAR/'mesin',pair.SUMBER_TULIS,tmp_path)
    assert awal.returncode==0,awal.stderr
    target=recovery_foto/'database.py';asli=target.read_text()
    guard='        validasi_operasi_foto(kon)\n        if kon.execute'
    assert asli.count(guard)==1
    target.write_text(asli.replace(guard,"        kon.execute(\"UPDATE operasi_foto_baca SET status='no_output' WHERE status='reserved'\")\n"+guard))
    mutan=tmp_path/'mutan';mutan.mkdir();shutil.copytree(tmp_path/'package-pair',mutan/'package-pair')
    merah=jalankan(recovery_foto,pair.SUMBER_BACA,mutan)
    assert merah.returncode!=0 and 'AssertionError' in merah.stderr
    assert 'ImportError' not in merah.stderr
    target.write_text(asli)
    hijau=jalankan(recovery_foto,pair.SUMBER_BACA,tmp_path)
    assert hijau.returncode==0,hijau.stderr
