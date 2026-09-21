"""Kontrak pasangan diukur; mismatch hanya boleh pada artefak build-only."""

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
SPEK_METADATA = importlib.util.spec_from_file_location("metadata_kontrak_uji", AKAR / "scripts/release_metadata.py")
metadata = importlib.util.module_from_spec(SPEK_METADATA)
SPEK_METADATA.loader.exec_module(metadata)


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
    config = metadata.baca_config(AKAR / "scripts/release-metadata.json")
    metadata.validasi_workflow(ALUR.read_text(), config)
    assert recovery_sha == config["recovery_revision"]
    assert fingerprint_recovery == config["recovery_contract"]
    # SHA historical tetap anchor, bukan diganti agar mismatch source tampak hijau.
    if recovery_sha == "33e241c18024190f41ebca1986e35af26c0397fd":
        assert fingerprint_recovery == "2c96f5a7717d772dc6326eddd1fa393d9db2684d646dbe9c189ad97a08a43603"
    hasil = metadata.buat_manifest(config,
        {"revision": "a" * 40, "digest": "sha256:" + "a" * 64, "contract": fingerprint_candidate},
        {"revision": recovery_sha, "digest": "sha256:" + "b" * 64, "contract": fingerprint_recovery},
        pasangan_teruji=config["mode"] != "persiapan")
    assert hasil["compatible"] is (fingerprint_candidate == fingerprint_recovery)
    if config["mode"] == "persiapan":
        # Tidak mengaku compatible. Job pasang literal false wajib terbukti di atas.
        assert hasil["siap_pasang"] is False
        assert hasil["pair_verified"] is False
        assert hasil["candidate_contract"] == fingerprint_candidate
        assert hasil["recovery_contract"] == fingerprint_recovery
    else:
        assert fingerprint_candidate == fingerprint_recovery
        assert hasil["siap_pasang"] is (config["mode"] == "rutin")
