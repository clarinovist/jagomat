"""Mutation source penilaian pada salinan sementara; tidak menyentuh working tree."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

MESIN=Path(__file__).resolve().parents[1]
MUTASI=(
 ('codec','diagnosis.py','if kontrak(soal) is not None:', 'if False:',
  'test_jawaban_ekuivalen_baru_diterima'),
 ('collision','diagnosis.py','if len(cocok) > 1:', 'if False:',
  'test_hasil_collision_tidak_dipilih_dari_urutan'),
 ('filter','assessment_revision.py','if v!=key and jumlah[v]==1','if v!=key',
  'test_filter_semantik_membuang_semua_collision'),
 ('windu','assessment_revision.py',"p['nilai'],'menyalin angka masukan tanpa konversi'","p['nilai']+2,'menyalin angka masukan tanpa konversi'",
  'test_windu_menyalin_input_tetap_input'),
 ('marker','assessment_revision.py',"parameter={**p,'revisi_penilaian':1}","parameter=p",
  'test_reader_lama_tetap_identik'),
)


@pytest.mark.parametrize('nama,file,old,new,tes',MUTASI,ids=[m[0] for m in MUTASI])
def test_mutation_penilaian(tmp_path,nama,file,old,new,tes):
    dst=tmp_path/'mesin';dst.mkdir()
    for p in MESIN.glob('*.py'):shutil.copy2(p,dst/p.name)
    tests=dst/'__tests__';tests.mkdir()
    for n in ('conftest.py','test_assessment_revision.py'):shutil.copy2(MESIN/'__tests__'/n,tests/n)
    p=dst/file;s=p.read_text()
    if nama=='codec':
        assert s.count(old)==2
        s=s.replace(old,new,1)
    else:
        assert s.count(old)==1
        s=s.replace(old,new)
    p.write_text(s)
    r=subprocess.run([sys.executable,'-B','-m','pytest',str(tests/'test_assessment_revision.py'),'-k',tes,'-q','-W','error','-p','no:cacheprovider'],
        cwd=tmp_path,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=30)
    assert r.returncode==1 and 'AssertionError' in r.stdout,r.stdout+r.stderr
    assert 'ERROR collecting' not in r.stdout
