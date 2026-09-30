"""Probe rilis dukungan: source sintetis dan klasifikasi recovery."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / "scripts"))
import release_support_pair as pair
import verify_release_image


def test_probe_dukungan_cbc_sintetis(tmp_path):
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(AKAR / "mesin"),
           "PYTHONDONTWRITEBYTECODE": "1", "OSN_PBKDF2_ITERASI": "1000"}
    for sumber, marker in (
        (pair.SUMBER_TULIS, "OSN_SUPPORT_WRITER_OK"),
        (pair.SUMBER_BACA, "OSN_SUPPORT_RECOVERY_OK"),
        (pair.SUMBER_KEMBALI, "OSN_SUPPORT_RETURN_OK"),
    ):
        hasil = subprocess.run(
            [sys.executable, "-B", "-"],
            input=sumber.replace("/data/", str(tmp_path) + "/"),
            capture_output=True, text=True, env=env, timeout=30,
        )
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


def test_recovery_lama_dinyatakan_tanpa_dukungan():
    lama = "634e077830938dbd3ae20d17e5ac019004e97fc2"
    assert verify_release_image.ringkasan_untuk_revision(lama)["support_checks"] == 0
    assert verify_release_image.ringkasan_untuk_revision("b" * 40)["support_checks"] == 8
