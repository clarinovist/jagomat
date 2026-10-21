"""Mutasi palang pada salinan modul sendiri; bukan workspace atau DB nyata."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('lama,baru,tes', [
    ("if e['status'] != 'disahkan':", 'if False:', 'test_draf_tidak_tampil_walau_metadata_review_lengkap'),
    ("if peran != 'guru':", 'if False:', 'test_peran_lain_tidak_membaca_berkas'),
    ('if validasi_entri(e) or not _review_sah(e):', 'if validasi_entri(e):',
     'test_edit_isi_membatalkan_review_tanpa_perlu_ganti_versi'),
    ('if validasi_entri(e) or not _review_sah(e):', 'if not _review_sah(e):',
     'test_validasi_skema_gagal_sebelum_render'),
    ('if _identitas(e) == identitas]', 'if True]', 'test_kecocokan_tepat_tanpa_fallback'),
    ('if not _cocok_domain(e):', 'if False:', 'test_pasangan_malrule_kode_rekaan_ditolak'),
    ('if not _cocok_domain(e):', 'if False:', 'test_profil_template_tidak_didukung_meski_request_cocok'),
    ("        nilai.encode('utf-8')", '        pass', 'test_surrogate_json_gagal_tertutup'),
    ('if len(cocok) != 1:', 'if not cocok:', 'test_duplikat_identitas_ditolak_bukan_ambil_pertama'),
    ('if k in hasil:', 'if False:', 'test_kunci_json_ganda_pada_entri_valid_ditolak'),
])
def test_mutasi_guard_merah_dan_pulih(tmp_path, lama, baru, tes):
    target = tmp_path / 'teaching_playbook.py'
    source = (ROOT / 'teaching_playbook.py').read_text()
    assert source.count(lama) == 1
    folder = tmp_path / '__tests__'
    folder.mkdir()
    for nama in ('conftest.py', 'test_teaching_playbook.py'):
        shutil.copyfile(ROOT / '__tests__' / nama, folder / nama)
    env = dict(os.environ, PYTHONPATH=str(tmp_path) + os.pathsep + str(ROOT),
               PYTHONDONTWRITEBYTECODE='1')
    command = [sys.executable, '-B', '-m', 'pytest',
               str(folder / 'test_teaching_playbook.py') + '::' + tes,
               '-q', '-W', 'error', '-p', 'no:cacheprovider']
    target.write_text(source)
    sehat = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert sehat.returncode == 0, sehat.stdout + sehat.stderr
    target.write_text(source.replace(lama, baru))
    rusak = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert rusak.returncode == 1, rusak.stdout + rusak.stderr
    assert 'FAILED' in rusak.stdout and 'ERROR collecting' not in rusak.stdout
    target.write_text(source)
    pulih = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30)
    assert pulih.returncode == 0, pulih.stdout + pulih.stderr
