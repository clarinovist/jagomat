"""Mutasi terisolasi membuktikan form foto utuh dan GET tidak menerapkan."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
KASUS = (
    ('field_disabled',
     'name="jwb_{s["sesi_soal_id"]}" value="{jwb_u}"',
     'name="jwb_{s["sesi_soal_id"]}" disabled value="{jwb_u}"'),
    ('di_luar_form',
     "{''.join(kartu)}\n<div class=\"koreksi-simpan-st\">",
     "</form>{''.join(kartu)}\n<form><div class=\"koreksi-simpan-st\">"),
    ('get_otomatis_menerapkan',
     '    return isi.encode()\n\n\nGAYA_KONFIRMASI',
     "    terapkan(kon, lampiran_id, {f'jwb_{s[\"sesi_soal_id\"]}': s['kunci'] for s in _soal_konteks(kon, sesi_id)})\n    return isi.encode()\n\n\nGAYA_KONFIRMASI"),
)


@pytest.mark.parametrize('nama,lama,baru', KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_form_foto_merah_lalu_hijau(tmp_path, nama, lama, baru):
    del nama
    source = tmp_path / 'mesin'
    source.mkdir()
    for berkas in AKAR.glob('*.py'):
        shutil.copyfile(berkas, source / berkas.name)
    tes = source / '__tests__'
    tes.mkdir()
    for nama in ('conftest.py', 'http_test_kit.py', 'test_photo_workflow.py'):
        shutil.copyfile(AKAR / '__tests__' / nama, tes / nama)
    target = source / 'attachments.py'
    asli = target.read_text()
    assert asli.count(lama) == 1
    command = [sys.executable, '-m', 'pytest',
               str(tes / 'test_photo_workflow.py') + '::test_kartu_terlipat_tetap_terkirim_dan_get_tidak_menerapkan',
               '-q', '-W', 'error', '-p', 'no:cacheprovider']
    env = {**os.environ, 'PYTHONPATH': str(source),
           'PYTHONDONTWRITEBYTECODE': '1', 'OSN_PBKDF2_ITERASI': '1000'}
    target.write_text(asli.replace(lama, baru, 1))
    merah = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                           text=True, timeout=45)
    assert merah.returncode == 1, merah.stdout + merah.stderr
    assert '1 failed' in merah.stdout and 'ERROR collecting' not in merah.stdout
    assert 'ImportError' not in merah.stdout + merah.stderr
    target.write_text(asli)
    hijau = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                           text=True, timeout=45)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr
