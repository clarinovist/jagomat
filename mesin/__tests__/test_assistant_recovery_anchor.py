"""Anchor recovery mempertahankan writer soal konservatif dan retirement AI."""
import os
from pathlib import Path
import subprocess
import sys


def test_default_recovery_konservatif_tanpa_menghapus_reader_atau_retirement():
    mesin = Path(__file__).resolve().parents[1]
    hasil = subprocess.run([sys.executable, '-B', '-'], input='''
from number_theory_versions import versi_writer
assert versi_writer() == 1, 'recovery_writer_bukan_konservatif'
import topics
from templates import REGISTRI
paket = topics.ambil('teori-bilangan')
assert len(set(paket.komposisi['P4'])) == 7
assert len(set(paket.komposisi_untuk('P4'))) == 3
assert REGISTRI['banyak_prima'](a=10,b=20).kunci == '4'
import assistant_policy as policy
assert policy.VERSI_KONTRAK == 'pendamping-jawaban-v2'
assert set(vars(policy.validasi_respons({'jawaban':'Sintetis.','butuh_klarifikasi':False}))) == {'jawaban','butuh_klarifikasi'}
try: policy.validasi_respons({'jawaban':'Sintetis.','butuh_klarifikasi':False,'draft_memori':None,'usulan_latihan':None})
except ValueError: pass
else: raise AssertionError('retirement_hilang')
''', env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(mesin),
          'PYTHONDONTWRITEBYTECODE': '1'}, text=True, capture_output=True, timeout=20)
    assert hasil.returncode == 0, hasil.stderr
