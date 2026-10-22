"""Mutasi pencarian dan palang pada snapshot source terisolasi, tanpa DB nyata."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
TES = 'mesin/__tests__/test_teacher_home_filter.py'


@pytest.mark.parametrize('berkas,lama,baru,tes', [
    ('teacher_home_priority.py', 'return cocok_kelompok and cocok_nama', 'return cocok_kelompok',
     'test_cari_nama_siswa_atau_login_terhubung'),
    ('teacher_home_priority.py', 'return cocok_kelompok and cocok_nama', 'return cocok_nama',
     'test_filter_kelompok_menjaga_sumber_dan_urutan'),
    ('guru_beranda_pages.py', 'html.escape(cari, quote=True)', 'cari',
     'test_form_get_native_tanpa_js_dan_nilai_escape'),
    ('guru_beranda_pages.py', 'siswa_milik = database.daftar_siswa(kon, pemilik)',
     'siswa_milik = database.daftar_siswa(kon, None)', 'test_akun_asing_tidak_dicari_atau_dihitung'),
    ('teacher_http.py', 'if not penangan._lolos_sandi():', 'if False:',
     'test_palang_murid_share_dan_404_asing_tetap'),
    ('web.py', 'return database.siswa_milik(kon, siswa_id, ident[0])', 'return True',
     'test_palang_murid_share_dan_404_asing_tetap'),
    ('web.py', 'return database.sesi_milik(kon, sesi_id, ident[0])', 'return True',
     'test_palang_murid_share_dan_404_asing_tetap'),
    ('teacher_http.py', '    penangan._kirim_privat(isi, beranda_guru=True)\n    return True',
     '    penangan._kirim(isi)\n    return True', 'test_cari_nama_siswa_atau_login_terhubung'),
    ('web.py', '        if beranda_guru:', '        if False:',
     'test_csp_beranda_mengizinkan_dua_skrip_dan_font_existing_saja'),
])
def test_mutasi_filter_dan_akses_merah_lalu_pulih(tmp_path, monkeypatch, berkas, lama, baru, tes):
    def extractall_terlarang(*a, **kw):
        raise AssertionError('Snapshot wajib memakai ekstraktor aman lintas versi')
    monkeypatch.setattr(tarfile.TarFile, 'extractall', extractall_terlarang)
    arsip = tmp_path / 'source.tar'
    with arsip.open('wb') as f:
        subprocess.run(['git', '-C', str(AKAR), 'archive', 'HEAD'], stdout=f, check=True)
    salinan = tmp_path / 'repo'
    salinan.mkdir()
    with tarfile.open(arsip) as t:
        ekstrak_tar_aman(t, salinan)
    for nama in ('guru_beranda_pages.py', 'teacher_pages.py', 'teacher_home_priority.py',
                 'teacher_http.py', 'web.py'):
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
