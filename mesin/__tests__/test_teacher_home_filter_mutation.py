"""Mutasi pencarian dan palang pada snapshot source terisolasi, tanpa DB nyata."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

AKAR = Path(__file__).resolve().parents[2]
TES = 'mesin/__tests__/test_teacher_home_filter.py'


@pytest.mark.parametrize('berkas,lama,baru,tes', [
    ('teacher_home_priority.py', 'return cocok_kelompok and cocok_nama', 'return cocok_kelompok',
     'test_cari_nama_siswa_atau_login_terhubung'),
    ('teacher_home_priority.py', 'return cocok_kelompok and cocok_nama', 'return cocok_nama',
     'test_filter_kelompok_menjaga_sumber_dan_urutan'),
    ('teacher_pages.py', 'html.escape(cari, quote=True)', 'cari',
     'test_form_get_native_tanpa_js_dan_nilai_escape'),
    ('teacher_pages.py', 'siswa_sendiri = database.daftar_siswa(kon, pemilik)',
     'siswa_sendiri = database.daftar_siswa(kon, None)', 'test_akun_asing_tidak_dicari_atau_dihitung'),
    ('teacher_http.py', 'if not penangan._lolos_sandi():', 'if False:',
     'test_palang_murid_share_dan_404_asing_tetap'),
    ('web.py', 'return database.siswa_milik(kon, siswa_id, ident[0])', 'return True',
     'test_palang_murid_share_dan_404_asing_tetap'),
    ('web.py', 'return database.sesi_milik(kon, sesi_id, ident[0])', 'return True',
     'test_palang_murid_share_dan_404_asing_tetap'),
    ('teacher_http.py', '    penangan._kirim_privat(isi)\n    return True',
     '    penangan._kirim(isi)\n    return True', 'test_cari_nama_siswa_atau_login_terhubung'),
])
def test_mutasi_filter_dan_akses_merah_lalu_pulih(tmp_path, berkas, lama, baru, tes):
    arsip = tmp_path / 'source.tar'
    with arsip.open('wb') as f:
        subprocess.run(['git', '-C', str(AKAR), 'archive', 'HEAD'], stdout=f, check=True)
    salinan = tmp_path / 'repo'
    salinan.mkdir()
    with tarfile.open(arsip) as t:
        # Arsip Git repo sendiri; bukan upload/arsip eksternal.
        t.extractall(salinan)
    for nama in ('teacher_pages.py', 'teacher_home_priority.py', 'teacher_http.py'):
        shutil.copyfile(AKAR / 'mesin' / nama, salinan / 'mesin' / nama)
    shutil.copyfile(AKAR / TES, salinan / TES)
    target = salinan / 'mesin' / berkas
    source = target.read_text()
    assert source.count(lama) == 1
    command = [sys.executable, '-B', '-m', 'pytest', str(salinan / TES) + '::' + tes,
               '-q', '-W', 'error', '-p', 'no:cacheprovider']
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for label, isi, kode in [('baseline', source, 0), ('mutasi', source.replace(lama, baru), 1),
                             ('pulih', source, 0)]:
        target.write_text(isi)
        r = subprocess.run(command, cwd=salinan, env=env, capture_output=True, text=True, timeout=45)
        assert r.returncode == kode, label + '\n' + r.stdout + r.stderr
        if kode:
            assert 'FAILED' in r.stdout and 'ERROR collecting' not in r.stdout
