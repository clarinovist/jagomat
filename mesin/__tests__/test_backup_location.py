"""Cadangan sintetis mengikuti skrip yang dipindah, tanpa SSH atau DB nyata."""
from pathlib import Path
import os
import shutil
import subprocess

import pytest

AKAR = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("basis_opsional", [False, True])
@pytest.mark.parametrize("lewat_alias", [False, True])
def test_cadangan_mengikuti_folder_baru_bukan_home_atau_cwd(tmp_path, basis_opsional, lewat_alias):
    lama = tmp_path / "osn lama"
    (lama / "mesin").mkdir(parents=True)
    shutil.copyfile(AKAR / "mesin/cadangkan.sh", lama / "mesin/cadangkan.sh")
    baru = tmp_path / "jagomat baru"
    lama.rename(baru)
    lama.symlink_to(baru, target_is_directory=True)
    skrip = (lama if lewat_alias else baru) / "mesin/cadangkan.sh"
    home = tmp_path / "home sintetis"
    cwd = tmp_path / "cwd lain"
    binari = tmp_path / "bin"
    for direktori in (home, cwd, binari):
        direktori.mkdir()
    # Double shell tidak pernah meneruskan panggilan ke jaringan/SQLite asli.
    (binari / "ssh").write_text('''#!/bin/bash
set -euo pipefail
case "${*: -1}" in
  *"test -f"*) printf '%s\\n' "$BASIS_OPSIONAL" ;;
  *"sudo -n cat "*) printf 'basis sintetis\\n' ;;
  *"docker exec "*|*"sudo -n rm -f "*) : ;;
  *) exit 97 ;;
esac
''')
    (binari / "sqlite3").write_text('''#!/bin/bash
set -euo pipefail
test -s "$1"
case "$2" in
  "PRAGMA integrity_check;") printf 'ok\\n' ;;
  "SELECT COUNT(*) FROM "*) printf '0\\n' ;;
  *) exit 98 ;;
esac
''')
    for berkas in binari.iterdir():
        berkas.chmod(0o700)
    hasil = subprocess.run(
        ["bash", str(skrip)], cwd=cwd, capture_output=True, text=True, timeout=10,
        env={**os.environ, "HOME": str(home), "PATH": str(binari) + ":/usr/bin:/bin",
             "OSN_HOST_VPS": "host-sintetis.invalid", "BASIS_OPSIONAL": str(int(basis_opsional))},
    )
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    tujuan = baru / "mesin/cadangan"
    for jenis in ("latihan", "pendamping", "ai-control"):
        berkas = list(tujuan.glob(jenis + "-*.db"))
        assert len(berkas) == (1 if jenis == "latihan" or basis_opsional else 0)
        assert all(p.read_text() == "basis sintetis\n" for p in berkas)
    assert not list(home.rglob("*.db"))
    assert not list(cwd.rglob("*.db"))
