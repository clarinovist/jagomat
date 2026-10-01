"""Mutation guard primitive penghapusan keluarga pada salinan repo terisolasi."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


AKAR = Path(__file__).resolve().parents[2]
SUMBER = AKAR / "mesin" / "family_deletion.py"
TEST = AKAR / "mesin" / "__tests__" / "test_family_deletion.py"


@pytest.mark.parametrize("nama,lama,baru,test", (
    ("verifikasi", 'if perintah.verifikasi_independen is not True:', 'if False:',
     "test_verifikasi_independen_dan_backup_exact_wajib"),
    ("snapshot", 'or awal.sidik != perintah.inventaris_sidik', 'or False',
     "test_verifikasi_independen_dan_backup_exact_wajib"),
    ("arsip", 'if sesi_id not in terlindungi:', 'if True:',
     "test_bundle_hasil_memutus_data_aktif_menjaga_arsip_dan_isolasi"),
), ids=("verifikasi", "snapshot", "arsip"))
def test_guard_penghapusan_menangkap_mutasi(tmp_path, nama, lama, baru, test):
    del nama
    salinan = tmp_path / "repo"
    shutil.copytree(AKAR / "mesin", salinan / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    target = salinan / "mesin" / "family_deletion.py"
    sumber = target.read_text(encoding="utf-8")
    assert sumber.count(lama) == 1
    target.write_text(sumber.replace(lama, baru), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(salinan / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    hasil = subprocess.run([
        sys.executable, "-m", "pytest",
        str(salinan / "mesin" / "__tests__" / TEST.name) + "::" + test,
        "-q", "-W", "error", "-p", "no:cacheprovider",
    ], cwd=salinan, env=env, text=True, capture_output=True, timeout=90)
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert "failed" in hasil.stdout.lower()
