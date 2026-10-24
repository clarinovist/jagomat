"""Mutation terisolasi guard dan prosedur revisi2; bukan workspace utama."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

MESIN = Path(__file__).resolve().parents[1]
MUTASI = (
    ('cabang-typo', 'catalog_followup.py',
     "return parameter.get('varian') in ('cari_rata', 'cari_data_ke_n')",
     'return True', 'test_cabang_typo_ditolak_registry_kontrak_dan_visual'),
    ('floor-kuantitas', 'catalog_followup.py', "else F(p['nilai'], faktor))",
     "else F(p['nilai'] // faktor))", 'test_prosedur_tidak_dipotong'),
    ('floor-rata', 'catalog_followup.py', 'F(sum(data), len(data) + 1)',
     'F(sum(data) // (len(data) + 1))', 'test_prosedur_tidak_dipotong'),
    ('bulat-arsiran', 'catalog_followup.py', '(2*r)**2 - F(314, 100)*r*r',
     'F(round(((2*r)**2 - F(314, 100)*r*r)*10), 10)', 'test_prosedur_tidak_dipotong'),
    ('kunci-plus-satu', 'catalog_followup.py', "p['rata'] * len(data) - sum(data[:-2])",
     'kunci + 1', 'test_data_terakhir_bukan_kunci_tambah_satu'),
    ('collision', 'assessment_revision.py', 'if v!=key and jumlah[v]==1',
     'if v!=key', 'test_collision_dibuang_bukan_digeser'),
    ('default-aktif', 'catalog_followup.py', "os.environ.get('OSN_KATALOG_LANJUTAN', '0')",
     "os.environ.get('OSN_KATALOG_LANJUTAN', '1')", 'test_default_dan_reader_histori_identik'),
    ('marker-hilang', 'catalog_followup.py', "parameter={**soal.parameter, 'revisi_penilaian': 2}",
     'parameter=soal.parameter', 'test_default_dan_reader_histori_identik'),
)


@pytest.mark.parametrize('nama,berkas,lokal,rusak,tes', MUTASI, ids=[m[0] for m in MUTASI])
def test_guard_dan_prosedur_merah_saat_dimutasi(tmp_path, nama, berkas, lokal, rusak, tes):
    dst = tmp_path / 'mesin'
    dst.mkdir()
    for p in MESIN.glob('*.py'):
        shutil.copy2(p, dst / p.name)
    tests = dst / '__tests__'
    tests.mkdir()
    for nama_test in ('conftest.py', 'test_catalog_followup.py'):
        shutil.copy2(MESIN / '__tests__' / nama_test, tests / nama_test)
    target = dst / berkas
    isi = target.read_text()
    assert isi.count(lokal) == 1
    target.write_text(isi.replace(lokal, rusak))
    r = subprocess.run([sys.executable, '-B', '-m', 'pytest', str(tests / 'test_catalog_followup.py'),
                        '-k', tes, '-q', '-W', 'error', '-p', 'no:cacheprovider'],
                       cwd=tmp_path, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                       capture_output=True, text=True, timeout=30)
    pesan = 'DID NOT RAISE' if nama == 'cabang-typo' else 'AssertionError'
    assert r.returncode == 1 and pesan in r.stdout, r.stdout + r.stderr
    assert 'ERROR collecting' not in r.stdout
