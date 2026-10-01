"""Mutation guard verifikasi independen reset melalui HTTP nyata."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


AKAR = Path(__file__).resolve().parents[2]


def _mutasi_gagal(tmp_path, relatif, lama, baru, target_test):
    salinan = tmp_path / "repo"
    shutil.copytree(AKAR / "mesin", salinan / "mesin", ignore=shutil.ignore_patterns(
        ".venv", "__pycache__", ".pytest_cache", "cadangan", "*.db", "*.json"))
    target = salinan / "mesin" / relatif
    sumber = target.read_text(encoding="utf-8")
    assert sumber.count(lama) == 1
    target.write_text(sumber.replace(lama, baru), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(salinan / "mesin"),
               PYTHONDONTWRITEBYTECODE="1", OSN_PBKDF2_ITERASI="1000")
    hasil = subprocess.run([
        str(AKAR / "mesin" / ".venv" / "bin" / "python"), "-m", "pytest",
        str(salinan / "mesin" / "__tests__" / target_test.split("::", 1)[0])
        + "::" + target_test.split("::", 1)[1],
        "-q", "-W", "error", "-p", "no:cacheprovider",
    ], cwd=salinan, env=env, text=True, capture_output=True, timeout=120)
    assert hasil.returncode == 1, hasil.stdout + hasil.stderr
    assert "failed" in hasil.stdout.lower()


def test_guard_verifikasi_reset_individual_menangkap_mutasi(tmp_path):
    _mutasi_gagal(
        tmp_path, "admin_http.py",
        'if aksi == AKSI_RESET_SANDI and data.pop("verifikasi_independen", None) != "1":',
        "if False:",
        "test_admin_http_c.py::test_reset_tanpa_verifikasi_ditahan_tanpa_enumerasi_atau_efek",
    )


def test_guard_verifikasi_reset_batch_menangkap_mutasi(tmp_path):
    _mutasi_gagal(
        tmp_path, "admin_bulk_http.py",
        "if aksi == AKSI_RESET_SANDI and terverifikasi != '1':",
        "if False:",
        "test_admin_http_d.py::test_bulk_reset_tanpa_verifikasi_independen_ditahan_tanpa_write",
    )
