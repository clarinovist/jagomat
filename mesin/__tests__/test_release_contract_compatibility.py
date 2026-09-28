"""Kontrak pasangan diukur; mismatch hanya boleh pada artefak build-only."""

import importlib.util
import re
import subprocess
import pytest
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
    kandidat = {
        "revision": "a" * 40, "digest": "sha256:" + "a" * 64,
        "contract": fingerprint_candidate,
    }
    recovery_artifact = {
        "revision": recovery_sha, "digest": "sha256:" + "b" * 64,
        "contract": fingerprint_recovery,
    }
    kompatibel = fingerprint_candidate == fingerprint_recovery
    if config["mode"] == "persiapan":
        hasil = metadata.buat_manifest(
            config, kandidat, recovery_artifact, pasangan_teruji=False,
        )
        # Tidak mengaku compatible. Job pasang literal false wajib terbukti di atas.
        assert hasil["siap_pasang"] is False
        assert hasil["pair_verified"] is False
        assert hasil["candidate_contract"] == fingerprint_candidate
        assert hasil["recovery_contract"] == fingerprint_recovery
    else:
        # Mode migrasi/rutin wajib benar-benar punya pasangan kompatibel;
        # penolakan manifest bukan hasil hijau untuk pin yang sedang dirilis.
        assert kompatibel, 'Pin recovery belum kompatibel dengan kandidat.'
        hasil = metadata.buat_manifest(
            config, kandidat, recovery_artifact, pasangan_teruji=True,
        )
        assert hasil["compatible"] is True
        assert hasil["siap_pasang"] is (config["mode"] == "rutin")


def test_bootstrap_registrasi_persiapan_tidak_mengaku_pair_lama():
    """Kontrak e03 dihitung ulang oleh probe baru; pair registrasi belum diklaim."""
    config = metadata.baca_config(AKAR / 'scripts/release-metadata.json')
    assert config == {
        'versi': 1, 'mode': 'persiapan',
        'recovery_revision': 'e03fbd0c782b309705f0e5d6297b1d47ae4e0f54',
        'recovery_contract': '6019fbe9a2fa467e8eb0793cfe292525fc0381eef0ddc5a899c41023187118f9',
    }
    metadata.validasi_workflow(ALUR.read_text(), config)
    b = {'revision': config['recovery_revision'], 'digest': 'sha256:'+'b'*64,
         'contract': config['recovery_contract']}
    c = {'revision': 'a'*40, 'digest': 'sha256:'+'a'*64, 'contract': 'c'*64}
    hasil = metadata.buat_manifest(config, c, b)
    assert not hasil['compatible'] and not hasil['pair_verified']
    assert not hasil['requires_controlled_migration'] and not hasil['siap_pasang']
    with pytest.raises(ValueError, match='Bukti pasangan'):
        metadata.buat_manifest(config, c, b, pasangan_teruji=True)
    # Pin tidak bebas: artefak recovery wajib membawa kontrak hasil rekalkulasi
    # probe baru, bukan angka lama maupun angka sembarang.
    with pytest.raises(ValueError, match='Artefak tidak cocok'):
        metadata.buat_manifest(config, c, {**b, 'contract': '9'*64})
