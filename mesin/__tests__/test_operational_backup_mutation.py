"""Mutation guard backup pada salinan sintetis terisolasi, tanpa jaringan."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
MUTASI = (
    ('wal', "dst.execute('PRAGMA journal_mode=DELETE').fetchone()[0] != 'delete'",
     "False", 'test_sumber_wal_menjadi_snapshot_portabel_tanpa_sidecar'),
    ('hash', "if m['files'] != actual or m['directories'] != dirs:", 'if False:',
     'test_hash_berubah_dan_file_tambahan_ditolak'),
    ('linkage', "    attachment_links(root / 'bundle' / 'latihan.db', root / 'lampiran')", '    pass',
     'test_validator_tolak_referensi_hilang_meski_manifest_diperbarui'),
    ('riset', "        with research_store.buka_baca(root / 'riset-separate.db'):\n            pass", '        pass',
     'test_riset_schema_parsial_ditolak'),
    ('opsional-isi', "    if {p.name for p in folder.iterdir()} != set(names):", '    if False:',
     'test_berkas_di_opsional_tidak_tercantum_ditolak'),
    ('opsional-skema', "if version != feature_switch.VERSI_SKEMA or not {'sakelar', 'audit_sakelar'} <= tables:",
     'if False:', 'test_sakelar_user_version_salah_ditolak'),
    ('opsional-skema-kurikulum', "if version != kurikulum_override.VERSI_SKEMA or not set(kurikulum_override.TABEL_SKEMA) <= tables:",
     'if False:', 'test_kurikulum_user_version_salah_ditolak'),
    ('opsional-skema-cetakan', "if version != cetakan_store.VERSI_SKEMA or not set(cetakan_store.TABEL_SKEMA) <= tables:",
     'if False:', 'test_cetakan_user_version_salah_ditolak'),
    ('writer', "if info['State']['Running'] or info['State']['Status'] != 'exited':", 'if False:',
     'test_host_tolak_state_tidak_pasti'),
    ('traversal', "any(x in ('', '.', '..') for x in parts)", 'False',
     'test_arsip_traversal_dan_link_ditolak'),
)


@pytest.mark.parametrize('name,old,new,test', MUTASI, ids=[x[0] for x in MUTASI])
def test_mutation_backup(tmp_path, name, old, new, test):
    mesin = tmp_path / 'mesin'
    mesin.mkdir()
    for p in (ROOT / 'mesin').glob('*.py'):
        shutil.copy2(p, mesin / p.name)
    # Instrumen riset memuat konten internal kanonis, bukan data responden.
    shutil.copytree(ROOT / 'mesin/konten', mesin / 'konten')
    tests = mesin / '__tests__'
    tests.mkdir()
    for n in ('conftest.py', 'test_admin_backup.py', 'test_operational_backup.py', 'test_operational_backup_host.py',
              'test_operational_backup_opsional.py'):
        shutil.copy2(ROOT / 'mesin/__tests__' / n, tests / n)
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    source = (ROOT / 'scripts/operational_backup.py').read_text()
    assert source.count(old) == 1
    (scripts / 'operational_backup.py').write_text(source.replace(old, new))
    r = subprocess.run([sys.executable, '-B', '-m', 'pytest', str(tests / 'test_operational_backup.py'),
                        str(tests / 'test_operational_backup_host.py'),
                        str(tests / 'test_operational_backup_opsional.py'), '-k', test, '-q', '-W', 'error', '-p', 'no:cacheprovider'],
                       cwd=tmp_path, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 1, r.stdout + r.stderr
    assert ('DID NOT RAISE' in r.stdout or 'AssertionError' in r.stdout
            or name == 'wal' and 'header snapshot bukan rollback journal' in r.stdout), r.stdout + r.stderr
    assert 'ERROR collecting' not in r.stdout
