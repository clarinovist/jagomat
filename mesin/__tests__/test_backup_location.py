"""Entry point backup mengikuti repo/alias; tidak diam-diam membuat snapshot parsial."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

AKAR = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('lewat_alias', [False, True])
def test_cadangan_mengikuti_folder_baru_bukan_home_atau_cwd(tmp_path, lewat_alias):
    lama = tmp_path / 'osn lama'
    (lama / 'mesin/.venv/bin').mkdir(parents=True)
    shutil.copyfile(AKAR / 'mesin/cadangkan.sh', lama / 'mesin/cadangkan.sh')
    # Double interpreter mencatat argv, tidak pernah mengakses jaringan/data.
    program = lama / 'mesin/.venv/bin/python'
    program.write_text('#!/bin/bash\nset -euo pipefail\nprintf "%s\\n" "$@" > "$ARG_LOG"\n')
    program.chmod(0o700)
    baru = tmp_path / 'jagomat baru'
    lama.rename(baru)
    lama.symlink_to(baru, target_is_directory=True)
    script = (lama if lewat_alias else baru) / 'mesin/cadangkan.sh'
    cwd = tmp_path / 'cwd lain'
    cwd.mkdir()
    log = tmp_path / 'args.txt'
    r = subprocess.run(['bash', str(script), 'backup-sintetis'], cwd=cwd,
                       env={**os.environ, 'ARG_LOG': str(log), 'OSN_HOST_VPS': 'host-sintetis.invalid'},
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stdout + r.stderr
    args = log.read_text().splitlines()
    assert args == ['-B', str(baru / 'mesin/../scripts/operational_backup.py'), 'fetch',
                    '--id', 'backup-sintetis', '--host', 'host-sintetis.invalid',
                    '--destination', str(baru / 'mesin/cadangan/operasional')]
    assert not list(cwd.rglob('*.db'))


def test_entrypoint_tanpa_id_gagal_tanpa_jaringan(tmp_path):
    r = subprocess.run(['bash', str(AKAR / 'mesin/cadangkan.sh')], cwd=tmp_path,
                       capture_output=True, text=True, timeout=10)
    assert r.returncode == 2 and 'id-bundle-operasional' in r.stderr
    assert not list(tmp_path.iterdir())


def test_tidak_ada_prune_dan_backup_live_tiga_db():
    text = (AKAR / 'mesin/cadangkan.sh').read_text()
    assert 'SIMPAN_HARI' not in text and '-delete' not in text
    assert 'docker exec' not in text and 'cadangan-sementara.db' not in text
