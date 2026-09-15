"""Uji penulis kandidat dan pembaca recovery memakai database sintetis bersama."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / 'scripts'))
import verify_submission_pair as pair


def test_probe_pasangan_subprocess_data_sintetis(tmp_path):
    env = {'PATH': os.environ.get('PATH',''), 'PYTHONPATH': str(AKAR/'mesin'),
           'PYTHONDONTWRITEBYTECODE': '1', 'OSN_PBKDF2_ITERASI': '1000'}
    for sumber, marker in ((pair.SUMBER_TULIS,'OSN_SUBMISSION_WRITER_OK'),
                           (pair.SUMBER_BACA,'OSN_SUBMISSION_RECOVERY_OK')):
        hasil = subprocess.run([sys.executable,'-B','-'],
            input=sumber.replace('/data/', str(tmp_path)+'/'),
            capture_output=True,text=True,env=env,timeout=30)
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


@pytest.fixture
def docker(monkeypatch):
    panggilan=[]
    images=['ghcr.io/clarinovist/osn-mesin-latihan@sha256:'+c*64 for c in 'ac']
    revisions=['b'*40,'d'*40]
    token='e'*32
    monkeypatch.setattr(pair.secrets,'token_hex',lambda n:token)
    def panggil(argv, masukan=None):
        panggilan.append((argv,masukan))
        if argv[:2]==['image','inspect']:
            i=images.index(argv[2])
            return json.dumps([{'Id':'sha256:'+str(i+1)*64,'RepoDigests':[images[i]],
                'Config':{'Labels':{'org.opencontainers.image.revision':revisions[i]},'Volumes':{'/data':{}}}}])
        if argv[:2]==['volume','inspect']: return token
        if argv[0]=='run':
            if masukan==pair.SUMBER_TULIS:return 'OSN_SUBMISSION_WRITER_OK'
            if masukan==pair.SUMBER_BACA:return 'OSN_SUBMISSION_RECOVERY_OK'
        return ''
    monkeypatch.setattr(pair,'_panggil',panggil)
    return images,revisions,panggilan,panggil


def test_volume_probe_sendiri_dan_urutan_write_read_cleanup(docker):
    images,revs,calls,_=docker
    hasil=pair.verifikasi(images[0],revs[0],images[1],revs[1])
    assert hasil['ok'] and hasil['provider_calls']==0
    assert hasil['candidate_digest']==images[0].split('@')[1]
    assert hasil['recovery_digest']==images[1].split('@')[1]
    runs=[(a,s) for a,s in calls if a[0]=='run']
    assert len(runs)==3
    for a,s in runs:
        assert '--network' in a and a[a.index('--network')+1]=='none'
        mount=a[a.index('--mount')+1]
        assert mount.startswith('type=volume,src=osn-submission-pair-')
        assert '/opt/osn' not in mount and 'type=bind' not in mount
    assert runs[0][0][runs[0][0].index('--user')+1]=='0:0'
    assert all(a[a.index('--user')+1]=='10001:10001' for a,_ in runs[1:])
    assert runs[1][1]==pair.SUMBER_TULIS and runs[2][1]==pair.SUMBER_BACA
    assert calls[-1][0][:2]==['volume','rm']


@pytest.mark.parametrize('fault',['writer','reader','owner'])
def test_gagal_probe_atau_owner_tidak_diklaim_lulus(docker,monkeypatch,fault):
    images,revs,calls,asli=docker
    def rusak(argv,masukan=None):
        if fault=='owner' and argv[:2]==['volume','inspect']: return 'asing'
        if argv[0]=='run' and masukan==(pair.SUMBER_TULIS if fault=='writer' else pair.SUMBER_BACA):
            return 'BUKAN_OK'
        return asli(argv,masukan)
    monkeypatch.setattr(pair,'_panggil',rusak)
    with pytest.raises(pair.GalatVerifikasi):
        pair.verifikasi(images[0],revs[0],images[1],revs[1])
    if fault=='owner': assert not any(a[:2]==['volume','rm'] for a,_ in calls)
    else: assert calls[-1][0][:2]==['volume','rm']


@pytest.mark.parametrize('owner', ['e'*32, 'milik-orang-lain'])
def test_timeout_hapus_hanya_container_dengan_label_sendiri(docker,monkeypatch,owner):
    images,revs,calls,asli=docker
    identitas='f'*64
    def timeout(argv,masukan=None):
        if argv[0]=='run': raise pair.GalatVerifikasi('timeout')
        if argv[:3]==['container','ls','-aq']: return identitas
        if argv[:2]==['container','inspect']: return owner
        return asli(argv,masukan)
    monkeypatch.setattr(pair,'_panggil',timeout)
    with pytest.raises(pair.GalatVerifikasi):
        pair.verifikasi(images[0],revs[0],images[1],revs[1])
    hapus=[a for a,_ in calls if a[:2]==['container','rm']]
    assert hapus==([['container','rm','--force',identitas]] if owner=='e'*32 else [])
