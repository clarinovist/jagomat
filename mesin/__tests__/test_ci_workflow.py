"""Optimasi penjadwalan CI tidak mengurangi test atau melewati gate deploy."""
from pathlib import Path
import os
import json
import re
import shlex
import subprocess
import sys
import textwrap

import pytest

UJI_SHARD = "3"

ALUR = Path(__file__).resolve().parents[2] / ".github/workflows/deploy.yml"


def _job(teks, nama):
    cocok = re.search(r"^  " + nama + r":\n(.*?)(?=^  [a-z_]+:\n|\Z)", teks, re.M | re.S)
    assert cocok, f"Job {nama} harus tersedia"
    return cocok.group(1)


def _skrip_recovery(teks):
    job = _job(teks, "uji_recovery")
    assert "      - name: Palang dan shard recovery terisolasi\n" in job
    assert "        working-directory: recovery\n" in job
    assert "        shell: bash\n" in job
    skrip = job.split("        run: |\n", 1)[1]
    return textwrap.dedent(skrip).strip()


def test_ci_menjalankan_seluruh_test_secara_stabil():
    teks = _job(ALUR.read_text(), "uji_kandidat")
    bagian = teks.split("- name: Jalankan shard kandidat dan catat manifest\n", 1)[1]
    blok = bagian.split("        run: |\n", 1)[1].split("      - name:", 1)[0]
    perintah = " ".join(baris.strip().rstrip("\\").strip() for baris in blok.splitlines())
    assert shlex.split(perintah) == [
        "python", "scripts/pytest_shard.py", "--shard", "${{ matrix.shard }}",
        "--total", "4", "--manifest", "shard-manifests/kandidat-${{ matrix.shard }}.json",
        "--revision", "$GITHUB_SHA", "--", "--rootdir", ".", "mesin/__tests__/",
        "-q", "-W", "error", "-p", "no:cacheprovider", "--durations=20",
    ]


def test_checkout_candidate_menyediakan_history_untuk_probe_recovery_pinned():
    teks = ALUR.read_text()
    bagian_uji = _job(teks, "uji_kandidat")
    checkout = bagian_uji.split("- uses: actions/checkout@v7", 1)[1].split(
        "- uses: actions/setup-python@v7", 1
    )[0]
    assert "fetch-depth: 0" in checkout


def test_ci_tetap_menguji_sebelum_build_dan_memasang_digest_yang_sama():
    teks = ALUR.read_text()
    assert teks.index("run: python scripts/check_repo.py") < teks.index(
        "- name: Jalankan shard kandidat dan catat manifest"
    )
    assert "  bangun:\n    name: Build & Push\n    needs: [uji, uji_recovery]\n" in teks
    agregat = _job(teks, "uji")
    assert "    needs: uji_kandidat\n" in agregat
    assert not re.search(r"^\s+(if|continue-on-error):", agregat, re.M)
    assert "always()" not in agregat
    assert 'python scripts/verify_pytest_shards.py' in agregat
    assert '--directory shard-manifests --total 4 --revision "$GITHUB_SHA"' in agregat
    assert "actions/download-artifact@v4" in agregat
    assert "pattern: kandidat-shard-*" in agregat
    assert "merge-multiple: true" in agregat
    assert "  pasang:\n    name: Deploy ke VPS\n    needs: bangun\n" in teks
    assert "digest: ${{ steps.dorong.outputs.digest }}" in teks
    assert '"deploy-rutin-v1 ${{ needs.bangun.outputs.digest }} ${{ needs.bangun.outputs.recovery_digest }}"' in teks
    assert "cancel-in-progress: false" in teks
    assert "- name: Pastikan situs hidup dari luar" in teks


@pytest.mark.parametrize("nama", ["uji_kandidat", "uji_recovery"])
def test_suite_independen_dengan_runtime_sendiri(nama):
    job = _job(ALUR.read_text(), nama)
    assert "    runs-on: ubuntu-latest\n" in job
    assert '          python-version: "3.12"\n' in job
    assert "        run: pip install --quiet pytest pytest-xdist\n" in job
    assert job.index("actions/checkout@v7") < job.index("actions/setup-python@v7")
    assert job.index("actions/setup-python@v7") < job.index("pip install")
    assert job.index("pip install") < job.index("python scripts/check_repo.py")
    assert "    needs: periksa\n" in job
    assert "    if: ${{ needs.periksa.outputs.lengkap == 'true' }}\n" in job
    assert not re.search(r"^\s+continue-on-error:", job, re.M)
    assert "secrets." not in job
    assert "PYTEST_ADDOPTS" not in job
    assert "-n " not in job  # Paralel antar-runner, bukan antarsocket satu runner.
    assert "      fail-fast: false\n" in job
    assert "        shard: [1, 2, 3, 4]\n" in job
    if nama == "uji_kandidat":
        assert "    name: Test kandidat ${{ matrix.shard }}/4\n" in job
        assert job.count("uses: actions/checkout@v7") == 1
        assert "          ref:" not in job
        assert "          path: shard-manifests/kandidat-${{ matrix.shard }}.json" in job
        assert "working-directory:" not in job
        assert "name: kandidat-shard-${{ matrix.shard }}" in job
        assert "if-no-files-found: error" in job
        assert "retention-days: 7" in job
        assert job.index("scripts/check_repo.py") < job.index("scripts/pytest_shard.py")
        assert job.index("scripts/pytest_shard.py") < job.index("actions/upload-artifact@v4")
    else:
        assert "    name: Test recovery ${{ matrix.shard }}/4\n" in job
        assert "      fail-fast: false\n" in job
        assert "        shard: [1, 2, 3, 4]\n" in job
        assert job.count("uses: actions/checkout@v7") == 2


def test_recovery_tetap_full_suite_dan_canary_isolasi():
    skrip = _skrip_recovery(ALUR.read_text())
    assert skrip.splitlines()[0] == "python scripts/check_repo.py"
    assert "assert pathlib.Path.cwd().name == 'recovery'" in skrip
    assert "sys.path.insert(0, str(pathlib.Path('mesin').resolve()))" in skrip
    assert "assert pathlib.Path(assistant_schema.__file__).resolve().parent == pathlib.Path('mesin').resolve()" in skrip
    assert "assert assistant_schema.VERSI_SKEMA == 4" in skrip
    assert skrip.index("python scripts/check_repo.py") < skrip.index("import assistant_schema")
    assert skrip.index("assert assistant_schema.VERSI_SKEMA == 4") < skrip.index("pytest_shard.py")
    perintah = " ".join(
        baris.strip().rstrip("\\").strip() for baris in skrip.splitlines()[-3:]
    )
    assert shlex.split(perintah) == [
        "python", "../scripts/pytest_shard.py", "--shard", "${{ matrix.shard }}",
        "--total", "4", "--", "--rootdir", ".", "mesin/__tests__/",
        "-q", "-W", "error", "-p", "no:cacheprovider", "--durations=20",
    ]
    assert "-n" not in shlex.split(perintah)


@pytest.mark.parametrize("gagal,urutan", [
    ("palang", ["palang"]),
    ("canary", ["palang", "canary"]),
    ("suite", ["palang", "canary", "suite"]),
    ("", ["palang", "canary", "suite"]),
])
def test_shell_recovery_berhenti_pada_kegagalan(tmp_path, gagal, urutan):
    """Jalankan blok shell aktual dengan Python palsu, tanpa DB atau provider."""
    skrip = _skrip_recovery(ALUR.read_text())
    binari = tmp_path / "bin"
    binari.mkdir()
    python = binari / "python"
    python.write_text("#!" + sys.executable + "\n" + textwrap.dedent('''\
        import os
        import sys
        from pathlib import Path
        argumen = sys.argv[1:]
        if argumen == ["scripts/check_repo.py"]:
            tahap = "palang"
        elif argumen == ["-"]:
            sys.stdin.read()
            tahap = "canary"
        elif argumen[:1] == ["../scripts/pytest_shard.py"]:
            tahap = "suite"
        else:
            raise SystemExit(99)
        with Path(os.environ["JEJAK_UJI"]).open("a") as jejak:
            jejak.write(tahap + "\\n")
        raise SystemExit(7 if os.environ["GAGAL_UJI"] == tahap else 0)
    '''))
    python.chmod(0o700)
    jejak = tmp_path / "jejak.txt"
    # Tiru substitusi GitHub Actions: blok run menerima shard konkret, bukan ekspresi.
    skrip_siap = skrip.replace("${{ matrix.shard }}", UJI_SHARD)
    assert "${{" not in skrip_siap
    hasil = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", skrip_siap],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PATH": str(binari) + os.pathsep + os.environ["PATH"],
             "GAGAL_UJI": gagal, "JEJAK_UJI": str(jejak)},
        timeout=10,
    )
    assert hasil.returncode == (7 if gagal else 0), hasil.stdout + hasil.stderr
    assert jejak.read_text().splitlines() == urutan


def test_periksa_selalu_aktif_dan_gagal_tidak_boleh_diabaikan():
    teks = ALUR.read_text()
    pemicu = teks.split("concurrency:", 1)[0]
    assert "  push:\n    branches: [main]\n" in pemicu
    assert "  workflow_dispatch:\n" in pemicu
    assert not re.search(r"^\s+(paths|paths-ignore|inputs):", pemicu, re.M)
    job = _job(teks, "periksa")
    assert not re.search(r"^\s+(needs|if|continue-on-error):", job, re.M)
    assert "fetch-depth: 0" in job
    assert 'python-version: "3.12"' in job
    assert "      lengkap: ${{ steps.perubahan.outputs.lengkap }}" in job
    assert "        id: perubahan\n        run: python scripts/ci_changes.py\n" in job
    assert job.index("scripts/check_repo.py") < job.index("scripts/ci_changes.py")
    assert "test_ci_changes.py" in job and "test_ci_workflow.py" in job
    assert "test_repo_hygiene.py" in job
    assert "-q -W error -p no:cacheprovider" in job
    assert "compile(path.read_text(), str(path), 'exec')" in job
    assert "secrets." not in job
    assert "continue-on-error:" not in teks
    bangun = _job(teks, "bangun")
    assert not re.search(r"^    if:", bangun, re.M)
    assert "always()" not in bangun


def _skrip_status():
    job = _job(ALUR.read_text(), "status")
    assert "    name: Status CI\n" in job
    assert "    if: ${{ always() }}\n" in job
    assert "    needs: [periksa, uji_kandidat, uji, uji_recovery, bangun, pasang]\n" in job
    assert "          HASIL_JOB: ${{ toJSON(needs) }}\n" in job
    assert 'python-version: "3.12"' in job
    return textwrap.dedent(job.split("        run: |\n", 1)[1]).strip()


def _hasil_job(lengkap):
    harapan = "success" if lengkap == "true" else "skipped"
    hasil = {nama: {"result": harapan} for nama in
             ("uji_kandidat", "uji", "uji_recovery", "bangun")}
    hasil["periksa"] = {"result": "success", "outputs": {"lengkap": lengkap}}
    hasil["pasang"] = {"result": "skipped"}
    return hasil


def _jalankan_status(hasil):
    # Python runner berasal dari interpreter test, bukan Python lokal lain.
    skrip = _skrip_status().replace("python -", shlex.quote(sys.executable) + " -", 1)
    return subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", skrip],
        capture_output=True, text=True, timeout=10,
        env={**os.environ, "HASIL_JOB": json.dumps(hasil)},
    )


@pytest.mark.parametrize("lengkap", ["true", "false"])
def test_status_menerima_hanya_jalur_sah(lengkap):
    hasil = _jalankan_status(_hasil_job(lengkap))
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert "Status CI lulus" in hasil.stdout


@pytest.mark.parametrize("lengkap", ["true", "false"])
@pytest.mark.parametrize("nama", ["periksa", "uji_kandidat", "uji", "uji_recovery", "bangun", "pasang"])
@pytest.mark.parametrize("status", ["failure", "cancelled", "skipped", "success"])
def test_status_menolak_kegagalan_dan_skip_tak_sah(lengkap, nama, status):
    hasil = _hasil_job(lengkap)
    sah = hasil[nama]["result"] == status
    hasil[nama]["result"] = status
    keluaran = _jalankan_status(hasil)
    assert (keluaran.returncode == 0) is sah, keluaran.stdout + keluaran.stderr


@pytest.mark.parametrize("lengkap", ["", None, "True", "FALSE", True, False])
def test_status_output_hilang_atau_invalid_bukan_jalur_ringan(lengkap):
    hasil = _hasil_job("false")
    hasil["periksa"]["outputs"] = {} if lengkap is None else {"lengkap": lengkap}
    assert _jalankan_status(hasil).returncode != 0
