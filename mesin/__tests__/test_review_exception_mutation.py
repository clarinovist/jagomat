"""Mutation terisolasi untuk fail-closed UI dan palang konfirmasi server."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[1]
KASUS = (
    (
        'kategori_fail_closed', 'review_navigation.py',
        "    if draf or masalah or sumber_perlu_diperiksa or tidak_konsisten:\n        return PERLU_DIPERIKSA",
        "    if False:\n        return PERLU_DIPERIKSA",
        'test_review_navigation.py::test_klasifikasi_tinjauan_fail_closed_untuk_error_draf_dan_nilai_asing',
    ),
    (
        'validasi_server', 'learning_cycle_service.py',
        '    """Simpan koreksi dan snapshot sebagai satu transaksi kecil atomik."""\n    validasi_form_konfirmasi(kon, sesi_id, data)',
        '    """Simpan koreksi dan snapshot sebagai satu transaksi kecil atomik."""\n    # mutasi: validasi form dinonaktifkan',
        'test_confirmation_recovery.py::test_validasi_payload_asing_sebelum_mutasi',
    ),
)


@pytest.mark.parametrize('nama,modul,lama,baru,node', KASUS, ids=[k[0] for k in KASUS])
def test_mutasi_exception_first_merah_lalu_hijau(tmp_path, nama, modul, lama, baru, node):
    del nama
    source = tmp_path / 'mesin'
    source.mkdir()
    for berkas in AKAR.glob('*.py'):
        shutil.copyfile(berkas, source / berkas.name)
    shutil.copytree(AKAR / '__tests__', source / '__tests__',
                    ignore=shutil.ignore_patterns('__pycache__'))
    target = source / modul
    asli = target.read_text()
    assert asli.count(lama) == 1
    command = [
        sys.executable, '-m', 'pytest', str(source / '__tests__' / node),
        '-q', '-W', 'error', '-p', 'no:cacheprovider',
    ]
    env = {**os.environ, 'PYTHONPATH': str(source),
           'PYTHONDONTWRITEBYTECODE': '1', 'OSN_PBKDF2_ITERASI': '1000'}

    target.write_text(asli.replace(lama, baru, 1))
    merah = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                           text=True, timeout=45)
    assert merah.returncode == 1, merah.stdout + merah.stderr
    assert 'ImportError' not in merah.stdout + merah.stderr

    target.write_text(asli)
    hijau = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True,
                           text=True, timeout=45)
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr
