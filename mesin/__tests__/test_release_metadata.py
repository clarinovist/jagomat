"""Mode persiapan boleh membangun, tetapi tidak boleh memasang pasangan tak cocok."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

AKAR = Path(__file__).resolve().parents[2]
SPEK = importlib.util.spec_from_file_location("metadata_uji", AKAR / "scripts/release_metadata.py")
metadata = importlib.util.module_from_spec(SPEK)


@pytest.fixture(autouse=True)
def muat():
    SPEK.loader.exec_module(metadata)


def config(mode="persiapan"):
    return {"versi": 1, "mode": mode, "recovery_revision": "b" * 40, "recovery_contract": "e" * 64}


def artefak(huruf, kontrak):
    return {"revision": huruf * 40, "digest": "sha256:" + huruf * 64, "contract": kontrak}


@pytest.mark.parametrize("mode", ["persiapan", "migrasi", "rutin"])
def test_mode_dikenal_dan_readiness_diturunkan(mode):
    hasil = metadata.buat_manifest(config(mode), artefak("a", "e" * 64), artefak("b", "e" * 64),
                                   pasangan_teruji=mode != "persiapan")
    assert hasil["compatible"] is True
    assert hasil["siap_pasang"] is (mode == "rutin")
    assert hasil["pair_verified"] is (mode != "persiapan")
    assert hasil["requires_controlled_migration"] is (mode == "migrasi")
    assert hasil["candidate_contract"] == hasil["recovery_contract"] == "e" * 64


def test_persiapan_mismatch_bukan_compatible_atau_siap():
    hasil = metadata.buat_manifest(config(), artefak("a", "f" * 64), artefak("b", "e" * 64))
    assert hasil["compatible"] is False and hasil["siap_pasang"] is False


@pytest.mark.parametrize("mode", ["migrasi", "rutin"])
def test_mode_aktif_tidak_menerima_pair_mismatch(mode):
    with pytest.raises(ValueError):
        metadata.buat_manifest(config(mode), artefak("a", "f" * 64), artefak("b", "e" * 64), pasangan_teruji=True)


@pytest.mark.parametrize("ubah", [{"mode": ""}, {"mode": "RUTIN"}, {"mode": "rutin "}, {"mode": None},
                                  {"versi": True}, {"versi": 2}, {"siap_pasang": True},
                                  {"recovery_revision": "main"}, {"recovery_contract": "g" * 64}])
def test_config_tertutup(ubah):
    with pytest.raises(ValueError):
        metadata.validasi_config({**config(), **ubah})


def test_missing_dan_duplikat_ditolak(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"mode":"persiapan","mode":"rutin"}')
    with pytest.raises(ValueError):
        metadata.baca_config(p)
    p.write_text(json.dumps({"mode": "persiapan"}))
    with pytest.raises(ValueError):
        metadata.baca_config(p)


@pytest.mark.parametrize("salah", ["revision", "contract", "digest", "sama"])
def test_artefak_tidak_bisa_memalsukan_anchor(salah):
    kandidat, recovery = artefak("a", "e" * 64), artefak("b", "e" * 64)
    if salah == "sama":
        kandidat = recovery.copy()
    else:
        recovery[salah] = {"revision": "c" * 40, "contract": "f" * 64, "digest": "latest"}[salah]
    with pytest.raises(ValueError):
        metadata.buat_manifest(config(), kandidat, recovery)


def test_workflow_persiapan_literal_false_dan_pin_config():
    konfigurasi = metadata.baca_config(AKAR / "scripts/release-metadata.json")
    assert konfigurasi["mode"] == "persiapan"
    teks = (AKAR / ".github/workflows/deploy.yml").read_text()
    metadata.validasi_workflow(teks, konfigurasi)
    assert "    if: ${{ false }}" in teks
    rusak = teks.replace("    if: ${{ false }}", "    if: ${{ vars.OSN_DEPLOY_RUTIN_SIAP == '1' && github.ref == 'refs/heads/main' }}")
    with pytest.raises(ValueError):
        metadata.validasi_workflow(rusak, konfigurasi)
    with pytest.raises(ValueError):
        metadata.validasi_workflow(teks.replace(konfigurasi["recovery_revision"], "c" * 40, 1), konfigurasi)


def test_probe_artefak_memverifikasi_sebelum_fingerprint(monkeypatch):
    jejak = []
    def verifikasi(image, revision):
        jejak.append((image, revision))
        return {"ok": True}
    class Docker:
        def _panggil(self, argv):
            assert argv == ["image", "inspect", "--format", "{{.Id}}",
                            "ghcr.io/clarinovist/osn-mesin-latihan@sha256:" + "a" * 64]
            return "sha256:" + "c" * 64
        def kontrak_image(self, digest):
            assert jejak and digest == "sha256:" + "c" * 64
            return "e" * 64
    monkeypatch.setattr(metadata.verify_release_image, "verifikasi", verifikasi)
    monkeypatch.setattr(metadata.deploy, "Docker", Docker)
    hasil = metadata.probe_artefak("sha256:" + "a" * 64, "a" * 40)
    assert hasil == artefak("a", "e" * 64)
    assert jejak == [("ghcr.io/clarinovist/osn-mesin-latihan@sha256:" + "a" * 64, "a" * 40)]


def test_verifier_gagal_tidak_diteruskan_ke_fingerprint(monkeypatch):
    def gagal(*_):
        raise ValueError("gagal sintetis")
    class Docker:
        def kontrak_image(self, _):
            pytest.fail("Fingerprint tidak boleh menggantikan verifikasi image")
    monkeypatch.setattr(metadata.verify_release_image, "verifikasi", gagal)
    monkeypatch.setattr(metadata.deploy, "Docker", Docker)
    with pytest.raises(ValueError):
        metadata.probe_artefak("sha256:" + "a" * 64, "a" * 40)


@pytest.mark.parametrize("mode", ["persiapan", "migrasi", "rutin"])
def test_cli_manifest_terikat_semua_artefak_dan_proof(tmp_path, monkeypatch, mode):
    cfg = metadata.baca_config(AKAR / "scripts/release-metadata.json")
    cfg["mode"] = mode
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    teks = (AKAR / ".github/workflows/deploy.yml").read_text()
    if mode == "rutin":
        teks = teks.replace("    if: ${{ false }}", "    if: ${{ " + metadata.GATE_RUTIN + " }}")
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(teks)
    output = tmp_path / "manifest.json"
    argv = ["--config", str(p), "--workflow", str(workflow), "--output", str(output),
            "--candidate-revision", "a" * 40, "--candidate-digest", "sha256:" + "a" * 64,
            "--recovery-revision", cfg["recovery_revision"], "--recovery-digest", "sha256:" + "b" * 64]
    panggilan = []
    def probe(digest, revision):
        panggilan.append((digest, revision))
        return {"digest": digest, "revision": revision, "contract": cfg["recovery_contract"]}
    monkeypatch.setattr(metadata, "probe_artefak", probe)
    if mode != "persiapan":
        assert metadata.main(argv) == 1 and not output.exists()
        assert panggilan == []
        proof = tmp_path / "pair.json"
        bukti = {"ok": True, "candidate_revision": "a" * 40, "recovery_revision": cfg["recovery_revision"],
                 "candidate_digest": "sha256:" + "a" * 64, "recovery_digest": "sha256:" + "b" * 64,
                 "pengiriman_pair_checks": 6, "provider_calls": 0}
        argv += ["--pair-proof", str(proof)]
        proof.write_text(json.dumps({**bukti, "candidate_digest": "sha256:" + "c" * 64}))
        assert metadata.main(argv) == 1 and not output.exists()
        assert panggilan == []
        proof.write_text(json.dumps(bukti))
    assert metadata.main(argv) == 0
    hasil = json.loads(output.read_text())
    assert hasil["candidate_digest"] == "sha256:" + "a" * 64
    assert hasil["recovery_revision"] == cfg["recovery_revision"]
    assert hasil["pair_verified"] is (mode != "persiapan")
    assert hasil["siap_pasang"] is (mode == "rutin")
    assert len(panggilan) == 2
    lama = output.read_bytes()
    assert metadata.main(argv) == 1 and output.read_bytes() == lama
    assert len(panggilan) == 2


def test_cli_probe_gagal_tidak_menerbitkan_manifest(tmp_path, monkeypatch):
    def gagal(*_):
        raise ValueError("keluaran_sensitif_sintetis")
    monkeypatch.setattr(metadata, "probe_artefak", gagal)
    cfg = metadata.baca_config(AKAR / "scripts/release-metadata.json")
    output = tmp_path / "manifest.json"
    assert metadata.main(["--output", str(output),
                          "--candidate-revision", "a" * 40, "--candidate-digest", "sha256:" + "a" * 64,
                          "--recovery-revision", cfg["recovery_revision"], "--recovery-digest", "sha256:" + "b" * 64]) == 1
    assert not output.exists()


def test_cli_gagal_tidak_menerbitkan_manifest(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"mode":"salah"}')
    output = tmp_path / "manifest.json"
    r = subprocess.run([sys.executable, str(AKAR / "scripts/release_metadata.py"),
                        "--config", str(config_path), "--output", str(output),
                        "--candidate-revision", "a" * 40, "--candidate-digest", "sha256:" + "a" * 64,
                        "--recovery-revision", "b" * 40, "--recovery-digest", "sha256:" + "b" * 64],
                       capture_output=True, text=True)
    assert r.returncode != 0 and not output.exists()


@pytest.mark.parametrize("mode", ["migrasi", "rutin"])
def test_pair_harus_teruji_bukan_hanya_fingerprint_sama(mode):
    with pytest.raises(ValueError):
        metadata.buat_manifest(config(mode), artefak("a", "e" * 64), artefak("b", "e" * 64))


@pytest.mark.parametrize("field,nilai", [("ok", False), ("ok", 1),
    ("candidate_revision", "c" * 40), ("recovery_revision", "c" * 40),
    ("candidate_digest", "sha256:" + "c" * 64), ("recovery_digest", "sha256:" + "c" * 64),
    ("pengiriman_pair_checks", 0), ("provider_calls", False), ("tambahan", True)])
def test_bukti_pair_tertutup_dan_terikat_revision(field, nilai):
    bukti = {"ok": True, "candidate_revision": "a" * 40, "recovery_revision": "b" * 40,
             "candidate_digest": "sha256:" + "a" * 64, "recovery_digest": "sha256:" + "b" * 64,
             "pengiriman_pair_checks": 6, "provider_calls": 0}
    arg = ("a" * 40, "b" * 40, "sha256:" + "a" * 64, "sha256:" + "b" * 64)
    assert metadata.validasi_bukti_pasangan(bukti, *arg)
    with pytest.raises(ValueError):
        metadata.validasi_bukti_pasangan({**bukti, field: nilai}, *arg)


@pytest.mark.parametrize("mode", ["persiapan", "migrasi", "rutin"])
def test_gate_actual_semua_mode_dan_duplikat(mode):
    konfigurasi = metadata.baca_config(AKAR / "scripts/release-metadata.json")
    konfigurasi["mode"] = mode
    teks = (AKAR / ".github/workflows/deploy.yml").read_text()
    if mode == "rutin":
        teks = teks.replace("    if: ${{ false }}", "    if: ${{ " + metadata.GATE_RUTIN + " }}")
    metadata.validasi_workflow(teks, konfigurasi)
    with pytest.raises(ValueError):
        metadata.validasi_workflow(teks.replace("    if: ${{", "    if: true\n    if: ${{"), konfigurasi)
    with pytest.raises(ValueError):
        metadata.validasi_workflow(teks.replace("jobs:\n", "jobs:\n  # ${{ secrets.VPS_DEPLOY_KEY }}\n"), konfigurasi)
