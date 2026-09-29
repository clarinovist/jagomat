"""Pair registrasi lintas source; historical bukan baseline registrasi palsu."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest
from test_package_release_pair import jalankan
from test_release_image import ekstrak_tar_aman, jalankan_probe
AKAR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(AKAR/'scripts'))
import deploy
import release_registration_pair as pair
import verify_release_image
import verify_submission_pair


def salin(tmp_path):
    source=tmp_path/'recovery';source.mkdir()
    for p in (AKAR/'mesin').glob('*.py'):shutil.copy2(p,source/p.name)
    return source


def test_pair_registrasi_c_b_c_pending_selesai_dan_replay(tmp_path):
    source=salin(tmp_path)
    for src,kode in ((AKAR/'mesin',pair.SUMBER_TULIS),(source,pair.SUMBER_BACA),(AKAR/'mesin',pair.SUMBER_KEMBALI)):
        hasil=jalankan(src,kode,tmp_path)
        assert hasil.returncode==0,hasil.stderr
    data=json.loads((tmp_path/'registration-pair/recovery.json').read_text())
    assert len(data['belajar']['siswa'])==len(data['belajar']['registrasi_profil_anak'])==6
    assert verify_submission_pair.REGISTRASI_BACA==pair.SUMBER_BACA


def test_pair_registrasi_kosong_memakai_source_recovery_pinned(tmp_path):
    sha=json.loads((AKAR/'scripts/release-metadata.json').read_text())['recovery_revision']
    source=tmp_path/'pinned';source.mkdir();arsip=tmp_path/'pinned.tar'
    with arsip.open('wb') as out:
        subprocess.run(['git','-C',str(AKAR),'archive',sha,'mesin'],stdout=out,check=True)
    with tarfile.open(arsip) as t:ekstrak_tar_aman(t,source)
    for src,kode in ((AKAR/'mesin',pair.SUMBER_TULIS),(source/'mesin',pair.SUMBER_BACA),(AKAR/'mesin',pair.SUMBER_KEMBALI)):
        hasil=jalankan(src,kode,tmp_path)
        assert hasil.returncode==0,hasil.stderr


def test_recovery_foto_historical_tidak_mengenal_registrasi(tmp_path):
    sha='e03fbd0c782b309705f0e5d6297b1d47ae4e0f54'
    source=tmp_path/'old';source.mkdir();arsip=tmp_path/'old.tar'
    with arsip.open('wb') as out:subprocess.run(['git','-C',str(AKAR),'archive',sha,'mesin'],stdout=out,check=True)
    with tarfile.open(arsip) as t:ekstrak_tar_aman(t,source)
    assert jalankan(AKAR/'mesin',pair.SUMBER_TULIS,tmp_path).returncode==0
    hasil=jalankan(source/'mesin',pair.SUMBER_BACA,tmp_path)
    assert hasil.returncode!=0 and 'migrasikan_profil_registrasi' in hasil.stderr
    assert verify_release_image.ringkasan_untuk_revision(sha)['registration_checks']==0


def test_image_registrasi_checks_delapan(tmp_path):
    hasil=jalankan_probe(tmp_path)
    assert hasil.returncode==0,hasil.stdout+hasil.stderr
    assert json.loads(hasil.stdout)['registration_checks']==8


def test_mutasi_recovery_pending_auth_ditangkap_pair(tmp_path):
    source=salin(tmp_path);assert jalankan(AKAR/'mesin',pair.SUMBER_TULIS,tmp_path).returncode==0
    target=source/'admin_registration.py';asli=target.read_text()
    guard='        validasi_schema_profil(kon)\n        kon.commit()'
    assert asli.count(guard)==1
    target.write_text(asli.replace(guard, "        kon.execute('DELETE FROM siswa WHERE id IN (SELECT siswa_id FROM registrasi_profil_anak)')\n"+guard))
    mutan=tmp_path/'mutan';mutan.mkdir();shutil.copytree(tmp_path/'registration-pair',mutan/'registration-pair')
    merah=jalankan(source,pair.SUMBER_BACA,mutan)
    assert merah.returncode!=0 and 'AssertionError' in merah.stderr
    target.write_text(asli)
    hijau=jalankan(source,pair.SUMBER_BACA,tmp_path)
    assert hijau.returncode==0,hijau.stderr


def test_fingerprint_mencakup_writer_registrasi():
    assert "'admin_registration.py'" in deploy.PROBE_KONTRAK


def test_probe_schema_registrasi_readonly(tmp_path):
    import sqlite3, database, admin_registration
    p=tmp_path/'latihan.db';database.siapkan(p)
    code='akar_app=Path('+repr(str(AKAR/'mesin'))+')\n'+deploy.PROBE_REGISTRASI_SKEMA.replace('/data/',str(tmp_path)+'/')
    exec(code,{'Path':Path,'sqlite3':sqlite3})
    admin_registration.migrasikan_profil_registrasi(p);awal=p.read_bytes()
    exec(code,{'Path':Path,'sqlite3':sqlite3});assert p.read_bytes()==awal
    with database.buka(p) as kon:kon.execute('DROP TRIGGER registrasi_profil_anak_tolak_update')
    with pytest.raises(AssertionError,match='schema_registrasi_parsial'):exec(code,{'Path':Path,'sqlite3':sqlite3})
