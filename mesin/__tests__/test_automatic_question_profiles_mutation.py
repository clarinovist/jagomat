"""Mutasi terisolasi untuk profil fondasi dan rollback sesi pertama."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
KASUS = (
    (
        'learning_cycle_service.py',
        "profil = 'P3'",
        "profil = 'P6'",
        'test_pemetaan_pertama_satu_aksi_memakai_fondasi_dan_idempoten',
        'AssertionError',
    ),
    (
        'learning_cycle_service.py',
        "kon.execute('ROLLBACK TO SAVEPOINT mulai_fondasi')",
        'pass',
        'test_pemetaan_fondasi_gagal_rollback_semua',
        'AssertionError',
    ),
)


@pytest.mark.parametrize('modul,lama,baru,tes,pesan', KASUS)
def test_guard_profil_otomatis_merah_pulih(tmp_path, modul, lama, baru, tes, pesan):
    source = tmp_path / 'mesin'
    source.mkdir()
    for path in (AKAR / 'mesin').glob('*.py'):
        shutil.copy2(path, source / path.name)
    for nama in ('test_automatic_question_profiles.py', 'http_test_kit.py', 'conftest.py'):
        shutil.copy2(Path(__file__).with_name(nama), tmp_path / nama)
    target = source / modul
    asli = target.read_text()
    assert asli.count(lama) == 1
    target.write_text(asli.replace(lama, baru))
    argv = [
        sys.executable, '-B', '-m', 'pytest',
        str(tmp_path / 'test_automatic_question_profiles.py'), '-k', tes,
        '-q', '-W', 'error', '-p', 'no:cacheprovider',
    ]
    env = {
        'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(source),
        'PYTHONDONTWRITEBYTECODE': '1', 'OSN_PBKDF2_ITERASI': '1000',
    }

    def jalankan():
        return subprocess.run(
            argv, env=env, cwd=tmp_path, capture_output=True, text=True, timeout=45,
        )

    merah = jalankan()
    assert merah.returncode == 1 and pesan in merah.stdout, merah.stdout + merah.stderr
    assert 'ImportError' not in merah.stdout + merah.stderr
    target.write_text(asli)
    hijau = jalankan()
    assert hijau.returncode == 0, hijau.stdout + hijau.stderr
