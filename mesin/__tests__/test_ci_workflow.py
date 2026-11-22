"""CI: push hanya palang, dispatch build tanpa suite test (22 Nov 2026)."""
from pathlib import Path
import os
import json
import re
import shlex
import subprocess
import sys
import textwrap

import pytest

JALUR_BANGUN = "${{ github.event_name == 'workflow_dispatch' && needs.periksa.outputs.lengkap == 'true' }}"
JOB_SAH = ["periksa", "bangun", "pasang", "status"]

ALUR = Path(__file__).resolve().parents[2] / ".github/workflows/deploy.yml"


def _job(teks, nama):
    cocok = re.search(r"^  " + nama + r":\n(.*?)(?=^  [a-z_]+:\n|\Z)", teks, re.M | re.S)
    assert cocok, f"Job {nama} harus tersedia"
    return cocok.group(1)


def test_ci_tidak_lagi_menjalankan_suite_test():
    # Keputusan pemilik 22 Nov 2026: test cepat, kandidat, dan recovery dihapus dari CI.
    teks = ALUR.read_text()
    assert re.findall(r"^  ([a-z_]+):\n", teks.split("\njobs:\n", 1)[1], re.M) == JOB_SAH
    for jejak in ("uji_cepat", "uji_kandidat", "uji_recovery", "scripts/ci_fast_tests.py",
                  "pytest_shard.py", "verify_pytest_shards.py", "inputs.audit", "schedule"):
        assert jejak not in teks


def test_preset_lengkap_tetap_serial_dengan_palang_dan_kompilasi():
    preset = json.loads((ALUR.parents[2] / ".project-gate.json").read_text())
    perintah = preset["commands"]
    assert [p["name"] for p in perintah] == [
        "palang-codebase-dan-privasi", "pytest-semua-dan-warning-error",
        "kompilasi-python",
    ]
    assert perintah[0]["argv"] == ["mesin/.venv/bin/python", "scripts/check_repo.py"]
    assert perintah[1]["argv"] == [
        "mesin/.venv/bin/python", "-m", "pytest", "mesin/__tests__/",
        "-q", "-W", "error", "-p", "no:cacheprovider",
    ]
    assert perintah[2]["argv"][:-1] == [
        "mesin/.venv/bin/python", "-W", "error", "-B", "-c",
    ]
    kompilasi = perintah[2]["argv"][-1]
    for direktori in ("mesin", "mesin/__tests__", "scripts"):
        assert "Path('{}').glob('*.py')".format(direktori) in kompilasi
    assert "compile(p.read_text(),str(p),'exec')" in kompilasi


def test_build_dispatch_hanya_setelah_palang_dan_memasang_digest_yang_sama():
    teks = ALUR.read_text()
    assert teks.index("run: python scripts/check_repo.py") < teks.index("  bangun:\n")
    # Keputusan pemilik 22 Nov 2026: dispatch rilis tidak menunggu suite test,
    # tetapi palang privasi/kompilasi (periksa) tetap wajib sukses lebih dulu.
    bangun = _job(teks, "bangun")
    assert bangun.startswith("    name: Build & Push\n")
    assert "\n    needs: periksa\n    if: " + JALUR_BANGUN + "\n" in bangun
    assert "  pasang:\n    name: Deploy ke VPS\n    needs: bangun\n" in teks
    assert "digest: ${{ steps.dorong.outputs.digest }}" in teks
    assert '"deploy-rutin-v1 ${{ needs.bangun.outputs.digest }} ${{ needs.bangun.outputs.recovery_digest }}"' in teks
    assert "cancel-in-progress: ${{ github.event_name == 'push' }}" in teks
    assert "github.event_name == 'push' && github.ref || 'release'" in teks
    assert "- name: Pastikan situs hidup dari luar" in teks


def test_periksa_selalu_aktif_dan_gagal_tidak_boleh_diabaikan():
    teks = ALUR.read_text()
    pemicu = teks.split("concurrency:", 1)[0]
    assert "  push:\n    branches: [main]\n" in pemicu
    assert pemicu.rstrip().endswith("\n  workflow_dispatch:")
    assert "inputs:" not in pemicu and "schedule:" not in pemicu  # Tanpa input bypass.
    assert not re.search(r"^\s+(paths|paths-ignore):", pemicu, re.M)
    job = _job(teks, "periksa")
    assert not re.search(r"^\s+(needs|if|continue-on-error):", job, re.M)
    assert "fetch-depth: 0" in job
    assert 'python-version: "3.12"' in job
    assert "      lengkap: ${{ steps.perubahan.outputs.lengkap }}" in job
    assert "        id: perubahan\n        run: python scripts/ci_changes.py\n" in job
    assert job.index("scripts/check_repo.py") < job.index("scripts/ci_changes.py")
    assert "test_ci_changes.py" in job and "test_ci_workflow.py" in job
    assert "test_ci_fast_tests.py" in job and "test_repo_hygiene.py" in job
    assert "-q -W error -p no:cacheprovider" in job
    assert "compile(path.read_text(), str(path), 'exec')" in job
    assert "secrets." not in job
    assert "continue-on-error:" not in teks
    bangun = _job(teks, "bangun")
    assert re.findall(r"^    if: (.+)$", bangun, re.M) == [JALUR_BANGUN]
    assert "always()" not in bangun


def _skrip_status():
    job = _job(ALUR.read_text(), "status")
    assert "    name: Status CI\n" in job
    assert "    if: ${{ always() }}\n" in job
    assert "    needs: [periksa, bangun, pasang]\n" in job
    assert "          HASIL_JOB: ${{ toJSON(needs) }}\n" in job
    assert 'python-version: "3.12"' in job
    return textwrap.dedent(job.split("        run: |\n", 1)[1]).strip()


JALUR_SAH = [("push", "true"), ("push", "false"), ("workflow_dispatch", "true")]


def _hasil_job(event, lengkap="true"):
    bangun = "success" if event == "workflow_dispatch" else "skipped"
    return {
        "periksa": {"result": "success", "outputs": {"lengkap": lengkap}},
        "bangun": {"result": bangun},
        "pasang": {"result": "skipped"},
    }


def _jalankan_status(hasil, event):
    # Python runner berasal dari interpreter test, bukan Python lokal lain.
    skrip = _skrip_status().replace("python -", shlex.quote(sys.executable) + " -", 1)
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", skrip],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "HASIL_JOB": json.dumps(hasil), "GITHUB_EVENT_NAME": event},
    )


@pytest.mark.parametrize("event,lengkap", JALUR_SAH)
def test_status_menerima_hanya_jalur_sah(event, lengkap):
    hasil = _jalankan_status(_hasil_job(event, lengkap), event)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert "Status CI lulus" in hasil.stdout


@pytest.mark.parametrize("event,lengkap", JALUR_SAH)
@pytest.mark.parametrize("nama", ["periksa", "bangun", "pasang"])
@pytest.mark.parametrize("status", ["failure", "cancelled", "skipped", "success"])
def test_status_menolak_kegagalan_dan_skip_tak_sah(event, lengkap, nama, status):
    hasil = _hasil_job(event, lengkap)
    sah = hasil[nama]["result"] == status
    hasil[nama]["result"] = status
    keluaran = _jalankan_status(hasil, event)
    assert (keluaran.returncode == 0) is sah, keluaran.stdout + keluaran.stderr


def test_status_dispatch_dengan_klasifikasi_dokumen_ditolak():
    hasil = _hasil_job("workflow_dispatch", "false")
    hasil["bangun"]["result"] = "skipped"
    assert _jalankan_status(hasil, "workflow_dispatch").returncode != 0


@pytest.mark.parametrize("lengkap", ["", None, "True", "FALSE", True, False])
def test_status_output_hilang_atau_invalid_bukan_jalur_ringan(lengkap):
    hasil = _hasil_job("push", "false")
    hasil["periksa"]["outputs"] = {} if lengkap is None else {"lengkap": lengkap}
    assert _jalankan_status(hasil, "push").returncode != 0


@pytest.mark.parametrize("event", ["schedule", "workflow_dispatch", "pull_request", ""])
def test_status_event_nonpush_tidak_menerima_klasifikasi_dokumen(event):
    hasil = _hasil_job("push", "false")
    assert _jalankan_status(hasil, event).returncode != 0
