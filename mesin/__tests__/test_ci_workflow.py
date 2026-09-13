"""Optimasi penjadwalan CI tidak mengurangi test atau melewati gate deploy."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import sys
import textwrap

import pytest


ALUR = Path(__file__).resolve().parents[2] / ".github/workflows/deploy.yml"


def _job(teks, nama):
    cocok = re.search(r"^  " + nama + r":\n(.*?)(?=^  [a-z_]+:\n|\Z)", teks, re.M | re.S)
    assert cocok, f"Job {nama} harus tersedia"
    return cocok.group(1)


def _skrip_recovery(teks):
    job = _job(teks, "uji_recovery")
    assert "      - name: Palang dan seluruh test recovery terisolasi\n" in job
    assert "        working-directory: recovery\n" in job
    assert "        shell: bash\n" in job
    skrip = job.split("        run: |\n", 1)[1]
    return textwrap.dedent(skrip).strip()


def test_ci_menjalankan_seluruh_test_secara_stabil():
    teks = _job(ALUR.read_text(), "uji")
    bagian = teks.split("- name: Jalankan seluruh test\n", 1)[1]
    baris = bagian.splitlines()[0].strip()
    assert baris.startswith("run: ")
    assert shlex.split(baris[len("run: "):]) == [
        "python", "-m", "pytest", "mesin/__tests__/", "-q", "-W", "error",
        "--durations=20",
    ]


def test_checkout_candidate_menyediakan_history_untuk_probe_recovery_pinned():
    teks = ALUR.read_text()
    bagian_uji = _job(teks, "uji")
    checkout = bagian_uji.split("- uses: actions/checkout@v7", 1)[1].split(
        "- uses: actions/setup-python@v7", 1
    )[0]
    assert "fetch-depth: 0" in checkout


def test_ci_tetap_menguji_sebelum_build_dan_memasang_digest_yang_sama():
    teks = ALUR.read_text()
    assert teks.index("run: python scripts/check_repo.py") < teks.index(
        "- name: Jalankan seluruh test"
    )
    assert "  bangun:\n    name: Build & Push\n    needs: [uji, uji_recovery]\n" in teks
    assert "  pasang:\n    name: Deploy ke VPS\n    needs: bangun\n" in teks
    assert "digest: ${{ steps.dorong.outputs.digest }}" in teks
    assert '"deploy-rutin-v1 ${{ needs.bangun.outputs.digest }} ${{ needs.bangun.outputs.recovery_digest }}"' in teks
    assert "cancel-in-progress: false" in teks
    assert "- name: Pastikan situs hidup dari luar" in teks


@pytest.mark.parametrize("nama", ["uji", "uji_recovery"])
def test_dua_suite_independen_dengan_runtime_sendiri(nama):
    job = _job(ALUR.read_text(), nama)
    assert "    runs-on: ubuntu-latest\n" in job
    assert '          python-version: "3.12"\n' in job
    assert "        run: pip install --quiet pytest pytest-xdist\n" in job
    assert job.index("actions/checkout@v7") < job.index("actions/setup-python@v7")
    assert job.index("actions/setup-python@v7") < job.index("pip install")
    assert job.index("pip install") < job.index("python scripts/check_repo.py")
    assert not re.search(r"^\s+(needs|if|continue-on-error|strategy):", job, re.M)
    assert "secrets." not in job
    assert "PYTEST_ADDOPTS" not in job
    assert "-n " not in job  # Paralel antar-runner, bukan antarsocket satu runner.
    assert job.count("uses: actions/checkout@v7") == 1
    if nama == "uji":
        assert "          ref:" not in job
        assert "          path:" not in job
        assert "working-directory:" not in job


def test_recovery_tetap_full_suite_dan_canary_isolasi():
    skrip = _skrip_recovery(ALUR.read_text())
    assert skrip.splitlines()[0] == "python scripts/check_repo.py"
    assert "assert pathlib.Path.cwd().name == 'recovery'" in skrip
    assert "sys.path.insert(0, str(pathlib.Path('mesin').resolve()))" in skrip
    assert "assert pathlib.Path(assistant_schema.__file__).resolve().parent == pathlib.Path('mesin').resolve()" in skrip
    assert "assert assistant_schema.VERSI_SKEMA == 4" in skrip
    assert skrip.index("python scripts/check_repo.py") < skrip.index("import assistant_schema")
    assert skrip.index("assert assistant_schema.VERSI_SKEMA == 4") < skrip.index("python -m pytest")
    assert shlex.split(skrip.splitlines()[-1]) == [
        "python", "-m", "pytest", "--rootdir", ".", "mesin/__tests__/",
        "-q", "-W", "error", "-p", "no:cacheprovider", "--durations=20",
    ]


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
        elif argumen[:2] == ["-m", "pytest"]:
            tahap = "suite"
        else:
            raise SystemExit(99)
        with Path(os.environ["JEJAK_UJI"]).open("a") as jejak:
            jejak.write(tahap + "\\n")
        raise SystemExit(7 if os.environ["GAGAL_UJI"] == tahap else 0)
    '''))
    python.chmod(0o700)
    jejak = tmp_path / "jejak.txt"
    hasil = subprocess.run(
        ["bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", skrip],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PATH": str(binari) + os.pathsep + os.environ["PATH"],
             "GAGAL_UJI": gagal, "JEJAK_UJI": str(jejak)},
        timeout=10,
    )
    assert hasil.returncode == (7 if gagal else 0), hasil.stdout + hasil.stderr
    assert jejak.read_text().splitlines() == urutan
