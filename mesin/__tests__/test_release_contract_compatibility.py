"""Kontrak kandidat rutin harus tetap identik dengan recovery pinned."""

import importlib.util
import re
import subprocess
import sys
import tarfile
from pathlib import Path

from test_release_image import ekstrak_tar_aman


AKAR = Path(__file__).resolve().parents[2]
ALUR = AKAR / ".github/workflows/deploy.yml"
DEPLOY = AKAR / "scripts/deploy.py"
SPEK = importlib.util.spec_from_file_location("deploy_kontrak_uji", DEPLOY)
assert SPEK is not None and SPEK.loader is not None
deploy = importlib.util.module_from_spec(SPEK)
SPEK.loader.exec_module(deploy)


def _fingerprint(akar_mesin: Path) -> str:
    sumber = deploy.PROBE_KONTRAK.replace(
        "Path('/app')", "Path(" + repr(str(akar_mesin)) + ")"
    )
    hasil = subprocess.run(
        [sys.executable, "-E", "-B", "-"],
        input=sumber,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    fingerprint = hasil.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)
    return fingerprint


def test_kontrak_candidate_identik_dengan_recovery_pinned(tmp_path, monkeypatch):
    """Cegah deploy rutin mencapai VPS dengan fingerprint yang pasti ditolak."""
    cocok = re.search(
        r"^  RECOVERY_SHA: ([0-9a-f]{40})$", ALUR.read_text(), re.MULTILINE
    )
    assert cocok is not None
    recovery_sha = cocok.group(1)

    arsip = tmp_path / "recovery.tar"
    with arsip.open("wb") as keluaran:
        subprocess.run(
            ["git", "-C", str(AKAR), "archive", recovery_sha, "mesin"],
            stdout=keluaran,
            stderr=subprocess.PIPE,
            check=True,
            timeout=30,
        )
    recovery = tmp_path / "recovery"
    recovery.mkdir()

    def tolak_extractall(*args, **kwargs):
        raise AssertionError("Gunakan ekstraktor aman yang kompatibel Python 3.9.")

    monkeypatch.setattr(tarfile.TarFile, "extractall", tolak_extractall)
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, recovery)

    fingerprint_candidate = _fingerprint(AKAR / "mesin")
    fingerprint_recovery = _fingerprint(recovery / "mesin")
    assert fingerprint_candidate == fingerprint_recovery
    assert fingerprint_candidate == "2c96f5a7717d772dc6326eddd1fa393d9db2684d646dbe9c189ad97a08a43603"
