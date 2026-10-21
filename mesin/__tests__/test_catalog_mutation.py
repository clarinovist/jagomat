"""Mutation pedagogis pada salinan source terisolasi dan fixture sintetis."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

MESIN = Path(__file__).resolve().parents[1]
MUTASI = (
    ('konteks-umur', 'catalog_logic.py', 'if konteks_umur == "dua_orang_v1":', 'if False:',
     'test_catalog_age_context.py::test_umur_baru_dua_orang_tanpa_relasi_keluarga', 'AssertionError'),
    ('umur', 'catalog_logic.py', 'kunci = (a + n) // (b + n)', 'kunci = k * b',
     'test_catalog_keys.py::test_umur_dari_perjalanan_waktu', 'AssertionError'),
    ('ceiling', 'catalog_keys.py', 'kunci = F(p["q"] * p["n"], p["p"])',
     'kunci = F((p["q"] * p["n"] + p["p"] - 1) // p["p"])',
     'test_catalog_keys.py::test_konservasi_besaran_tanpa_pembulatan[P5-perbandingan_senilai]', 'AssertionError'),
    ('pi', 'catalog_keys.py', 'kunci = luas\n', 'kunci = F(round(float(luas), 1))\n',
     'test_catalog_keys.py::test_geometri_memenuhi_pi_dan_bagian_putaran[lingkaran_keliling_luas-P5]', 'AssertionError'),
    ('paritas', 'catalog_keys.py', 'akhir = a + 2 * (n - 1)', 'akhir = a + n - 1',
     'test_catalog_keys.py::test_paritas_teks_dan_persamaan_deret[P4]', 'AssertionError'),
    ('median', 'catalog_malrules.py', "('median.terkecil',min(d),'K'", "('median.terkecil',min(d)+1,'K'",
     'test_catalog_malrules.py::test_malrule_mengikuti_prosedur[statistika-median_modus-P4]', 'AssertionError'),
    ('fpb', 'catalog_malrules.py', 'kecil=next((d for d in range(terbesar//2,0,-1) if a%d==b%d==0),None)',
     'kecil=max(1,terbesar//2)',
     'test_catalog_malrules.py::test_malrule_mengikuti_prosedur[aritmetika-dasar-fpb_dua_bilangan-P5]', 'AssertionError'),
    ('prisma', 'catalog_malrules.py', "nilai=(F(p['V'],a*t),F(p['V'],a+t))", "nilai=(F(2*p['V'],a*t)+1,F(p['V'],a+t))",
     'test_catalog_malrules.py::test_malrule_mengikuti_prosedur[geometri-ruang-volume_prisma_tabung-P5]', 'AssertionError'),
    ('skala', 'catalog_malrules.py', "f'{b//g}:{a//g}'", "f'1:{a*b}'",
     'test_catalog_malrules.py::test_malrule_mengikuti_prosedur[pengukuran-skala_peta-P5]', 'AssertionError'),
    ('jaring', 'catalog_diagnosis.py', "m.jawaban,'K','memilih susunan", "m.jawaban,'H','memilih susunan",
     'test_catalog_diagnosis.py::test_jaring_kategori_stabil_terhadap_urutan', 'AssertionError'),
    ('pengandaian', 'catalog_diagnosis.py', "'ABCDE'[pos], 'K', alasan[i]", "'ABCDE'[pos], 'H', alasan[i]",
     'test_catalog_diagnosis.py::test_pengandaian_tidak_mengklaim_kesalahan_hitung[P5]', 'AssertionError'),
    ('identitas', 'catalog_versions.py', 'parameter={**soal.parameter, "versi_katalog": 2}',
     'parameter={k:v for k,v in soal.parameter.items() if k != "konteks_umur"}',
     'test_catalog_history.py::test_identitas_baru_tidak_meminjam_kunci_bank_lama', 'identitas konten baru bertabrakan'),
    ('reader', 'catalog_versions.py', 'if versi_katalog == 1:\n                return lama(*args, **kwargs)',
     'if versi_katalog == 1 or versi_writer() == 1:\n                return lama(*args, **{k:v for k,v in kwargs.items() if k != "konteks_umur"})',
     'test_catalog_history.py::test_reader_histori_tidak_mengikuti_flag_writer[1]', 'AssertionError'),
)


@pytest.mark.parametrize('nama,berkas,lama,baru,tes,pesan', MUTASI, ids=[m[0] for m in MUTASI])
def test_mutation_invariant(tmp_path,nama,berkas,lama,baru,tes,pesan):
    tujuan=tmp_path/'mesin'
    tujuan.mkdir()
    for sumber in MESIN.glob('*.py'):
        shutil.copy2(sumber,tujuan/sumber.name)
    tests=tujuan/'__tests__'
    tests.mkdir()
    for sumber in (MESIN/'__tests__').glob('test_catalog_*.py'):
        if sumber.name!='test_catalog_mutation.py': shutil.copy2(sumber,tests/sumber.name)
    shutil.copy2(MESIN/'__tests__/conftest.py',tests/'conftest.py')
    path=tujuan/berkas
    asli=path.read_text()
    assert asli.count(lama)==1,'target mutation wajib tepat dan unik'
    path.write_text(asli.replace(lama,baru))
    hasil=subprocess.run([sys.executable,'-B','-m','pytest',str(tests/tes),'-q','-W','error','-p','no:cacheprovider'],
        cwd=tmp_path,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OSN_KATALOG_VERSI='1'),
        text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
    assert hasil.returncode==1 and pesan in hasil.stdout, hasil.stdout
    assert 'ERROR collecting' not in hasil.stdout and 'ImportError' not in hasil.stdout, hasil.stdout
