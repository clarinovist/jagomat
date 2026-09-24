"""Pasangan source kandidat→B menjalankan probe sebenarnya, tanpa Docker/DB nyata."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest
from test_submission_pair import pair, AKAR
from test_release_image import ekstrak_tar_aman


@pytest.fixture(scope='module')
def source_pinned(tmp_path_factory):
    akar = tmp_path_factory.mktemp('pilot-recovery-b')
    arsip = akar / 'b.tar'
    revision = json.loads((AKAR / 'scripts/release-metadata.json').read_text())['recovery_revision']
    with arsip.open('wb') as output:
        subprocess.run(['git', '-C', str(AKAR), 'archive', revision, 'mesin'], stdout=output, check=True)
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, akar)
    return akar / 'mesin'


@pytest.fixture(scope='module')
def source_b(tmp_path_factory):
    # Salinan reader admin6 membuktikan kontrak fungsi, bukan pair image rilis.
    akar = tmp_path_factory.mktemp('reader-admin6')
    for p in (AKAR / 'mesin').glob('*.py'):
        shutil.copy2(p, akar / p.name)
    return akar


def test_recovery_pinned_admin5_ditolak_untuk_ledger_admin6(tmp_path, source_pinned):
    tulis = jalankan(pair.TULIS_PILOT, tmp_path, AKAR / 'mesin')
    assert tulis.returncode == 0, tulis.stderr
    baca = jalankan(pair.BACA_PILOT, tmp_path, source_pinned)
    assert baca.returncode != 0
    assert 'OSN_LEARNING_RECOVERY_OK' not in baca.stdout
    # Tolak tepat karena reader langganan belum ada, bukan mengaku compatible.
    assert "No module named 'subscription'" in baca.stderr


def jalankan(sumber, data, source):
    env = {'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(source),
           'PYTHONDONTWRITEBYTECODE': '1', 'OSN_PBKDF2_ITERASI': '1000',
           'TMPDIR': str(data)}
    skrip = sumber.replace('/data/', str(data) + '/').replace("'/data'", repr(str(data)))
    return subprocess.run([sys.executable, '-B', '-'], input=skrip, env=env,
                          cwd=data, capture_output=True, text=True, timeout=45)


def test_candidate_menulis_lalu_reader_admin6_memulihkan(tmp_path, source_b):
    tulis = jalankan(pair.TULIS_PILOT, tmp_path, AKAR / 'mesin')
    assert tulis.returncode == 0, tulis.stderr
    assert tulis.stdout.strip() == 'OSN_LEARNING_WRITER_OK'
    baca = jalankan(pair.BACA_PILOT, tmp_path, source_b)
    assert baca.returncode == 0, baca.stderr
    assert baca.stdout.strip() == 'OSN_LEARNING_RECOVERY_OK'
    # Positif wajib: receipt sah dipertahankan, bukan hanya ditolak saat rusak.
    assert (tmp_path / 'admin-pair-positive.json').is_file()


@pytest.mark.parametrize('rusak', ['arsip', 'kelas', 'tanggal', 'variasi', 'receipt'])
def test_probe_recovery_menolak_data_pasangan_yang_berubah(tmp_path, source_b, rusak):
    tulis = jalankan(pair.TULIS_PILOT, tmp_path, AKAR / 'mesin')
    assert tulis.returncode == 0, tulis.stderr
    sql = {
        'arsip': "DROP TRIGGER pilot_konfirmasi_tolak_update; UPDATE pilot_konfirmasi SET fingerprint='" + 'f'*64 + "';",
        'kelas': 'UPDATE profil_belajar SET kelas_sekolah=6;',
        'tanggal': "UPDATE sesi SET tanggal='2026-09-07';",
        'variasi': "DROP TRIGGER pilot_sesi_tolak_update; UPDATE pilot_sesi SET kontrak_json='{}';",
        'receipt': "UPDATE operasi_admin_profil SET sidik_perintah='" + 'f'*64 + "';",
    }[rusak]
    db = 'admin-pair/belajar.db' if rusak == 'receipt' else 'learning-pair.db'
    injeksi = "import sqlite3\nwith sqlite3.connect('/data/" + db + "') as kon:\n    kon.executescript(" + repr(sql) + ")\n"
    baca = jalankan(injeksi + pair.BACA_PILOT, tmp_path, source_b)
    assert baca.returncode != 0
    assert 'OSN_LEARNING_RECOVERY_OK' not in baca.stdout
    assert 'OperationalError' not in baca.stderr, baca.stderr


@pytest.mark.parametrize('rusak', ['receipt_guard', 'arsip_guard', 'owner_guard'])
def test_mutation_probe_menangkap_guard_yang_dilemahkan(tmp_path, source_b, rusak):
    source = tmp_path / 'mutant'
    source.mkdir()
    for p in source_b.glob('*.py'):
        shutil.copy2(p, source / p.name)
    perubahan = {
        'receipt_guard': ('learning_profile_admin.py', (("if not receipt_cocok(receipt, perintah) or baris['kelas_baru'] != kelas:", 'if False:'),)),
        'arsip_guard': ('skill_pilot_schema.py', (("SELECT RAISE(ABORT,'konfirmasi pilot append-only');", 'SELECT 1;'),)),
        'owner_guard': ('skill_pilot_store.py', (
            ('if sesi is None or sesi["siswa_id"]!=siswa_id:', 'if sesi is None:'),
            (' or kontrak.siswa_id!=siswa_id', ''),
            ("if asal is None or asal['siswa_id']!=siswa_id:", 'if asal is None:'))),
    }
    nama, daftar = perubahan[rusak]
    p = source / nama
    asli = p.read_text()
    teks = asli
    for lama, baru in daftar:
        assert lama in teks
        teks = teks.replace(lama, baru)
    p.write_text(teks)
    # Mutasi DDL harus dipasang saat create; guard reader diuji pada hasil C asli.
    penulis = source if rusak == 'arsip_guard' else AKAR / 'mesin'
    tulis = jalankan(pair.TULIS_PILOT, tmp_path, penulis)
    assert tulis.returncode == 0, tulis.stderr
    baca = jalankan(pair.BACA_PILOT, tmp_path, source)
    assert baca.returncode != 0
    pesan = {'receipt_guard': 'receipt_rusak_diterima_recovery',
             'arsip_guard': 'arsip_pilot_mutable', 'owner_guard': 'owner_pilot_hilang'}[rusak]
    assert pesan in baca.stderr, baca.stderr
    p.write_text(asli)
    pulih = tmp_path / 'pulih'
    pulih.mkdir()
    assert jalankan(pair.TULIS_PILOT, pulih, source).returncode == 0
    hasil = jalankan(pair.BACA_PILOT, pulih, source)
    assert hasil.returncode == 0, hasil.stderr
