"""Palang rilis PG: pasangan nyata, bukti wajib, dan tombol tidak menutupi opsi."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from choice_pages import gaya_pilihan
from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / 'scripts'))
import verify_submission_pair as pair
import release_metadata as metadata


def test_toolbar_pg_tidak_overlay_tetapi_isian_tidak_diubah():
    css = gaya_pilihan()
    assert '.kerja-editorial-st:has(.pg-pilihan) .kerja-simpan-strip-st { position: static; }' in css
    assert '.kerja-editorial-st .kerja-simpan-strip-st { position: static;' not in css


def test_bukti_lama_tanpa_pg_tidak_diterima():
    bukti = {'ok':True,'candidate_revision':'a'*40,'recovery_revision':'b'*40,
             'candidate_digest':'sha256:'+'a'*64,'recovery_digest':'sha256:'+'b'*64,
             'pengiriman_pair_checks':6,'provider_calls':0}
    with pytest.raises(ValueError):
        metadata.validasi_bukti_pasangan(bukti,'a'*40,'b'*40,'sha256:'+'a'*64,'sha256:'+'b'*64)


def test_candidate_menulis_dan_recovery_pinned_melanjutkan_pg(tmp_path):
    recovery = metadata.baca_config(AKAR/'scripts/release-metadata.json')['recovery_revision']
    arsip = tmp_path/'source.tar'
    with arsip.open('wb') as f:
        subprocess.run(['git','-C',str(AKAR),'archive',recovery,'mesin'],stdout=f,check=True)
    folder=tmp_path/'recovery';folder.mkdir()
    with tarfile.open(arsip) as t:ekstrak_tar_aman(t,folder)
    data=tmp_path/'data';data.mkdir()
    for akar,sumber,marker in ((AKAR/'mesin',pair.SUMBER_TULIS,'OSN_SUBMISSION_WRITER_OK'),
                              (folder/'mesin',pair.SUMBER_BACA,'OSN_SUBMISSION_RECOVERY_OK')):
        env={'PATH':os.environ.get('PATH',''),'PYTHONPATH':str(akar),'PYTHONDONTWRITEBYTECODE':'1'}
        r=subprocess.run([sys.executable,'-B','-'],cwd=akar,env=env,text=True,capture_output=True,
                         input=sumber.replace('/data/',str(data)+'/').replace("'/data'",repr(str(data))),timeout=30)
        assert r.returncode==0,r.stderr
        assert r.stdout.strip()==marker
