"""Probe rilis wajib memeriksa schema pengiriman, tanpa membaca data keluarga."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import sqlite3

import pytest

import database

AKAR = Path(__file__).resolve().parents[2]


def _deployer():
    spec = importlib.util.spec_from_file_location('deploy_submission_uji', AKAR / 'scripts/deploy.py')
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_probe_image_dan_readiness_menyebut_seluruh_arsip_dan_guard():
    modul = _deployer()
    for nama in ('refleksi_jawaban', 'versi_pekerjaan', 'pengiriman_sesi',
                 'pengiriman_butir', 'tinjauan_guru', 'tinjauan_outcome',
                 'pengiriman_butir_validasi'):
        assert nama in modul.PROBE_IMAGE
        assert nama in modul.PROBE_SKEMA
    assert 'mode=ro' in modul.PROBE_SKEMA
    assert 'import database' not in modul.PROBE_SKEMA


def test_verifier_memeriksa_pengiriman_sintetis():
    spec = importlib.util.spec_from_file_location('verify_submission_uji', AKAR / 'scripts/verify_release_image.py')
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    assert 'uji_pengiriman' in modul.SUMBER_PROBE
    assert 'pengiriman_checks' in modul.ringkasan_untuk_revision('b' * 40)
    assert modul.ringkasan_untuk_revision('33e241c18024190f41ebca1986e35af26c0397fd')['pengiriman_checks'] == 0


@pytest.mark.parametrize('rusak', [None, 'tabel', 'trigger', 'kolom'])
def test_readiness_pengiriman_hilang_gagal_tanpa_migrasi(tmp_path, rusak):
    modul = _deployer()
    path = tmp_path / 'latihan.db'
    database.siapkan(path)
    with sqlite3.connect(path) as kon:
        if rusak == 'tabel':
            kon.execute('DROP TABLE refleksi_jawaban')
        elif rusak == 'trigger':
            kon.execute('DROP TRIGGER pengiriman_butir_tolak_update')
        elif rusak == 'kolom':
            kon.execute('ALTER TABLE tinjauan_guru RENAME COLUMN provenance TO rusak')
    sebelum = path.read_bytes()
    # Jalankan fragmen SQL metadata yang sama dengan readiness live.
    script = "import sqlite3\nfrom pathlib import Path\n" + modul.PROBE_PENGIRIMAN_SKEMA.replace('/data/', str(tmp_path) + '/')
    hasil = subprocess.run([sys.executable, '-E', '-B', '-'], input=script, capture_output=True, text=True)
    assert hasil.returncode == (0 if rusak is None else 1)
    assert path.read_bytes() == sebelum


@pytest.mark.parametrize('rusak', ['migrasi', 'immutable', 'bantuan'])
def test_probe_image_menolak_guard_pengiriman_yang_dimatikan(tmp_path, rusak):
    from test_release_image import jalankan_probe
    if rusak == 'migrasi':
        injeksi = '''
import database
asli=database.siapkan
def rusak(path):
    import sqlite3
    asli(path)
    with sqlite3.connect(path) as kon:
        kon.execute('DROP TABLE refleksi_jawaban')
database.siapkan=rusak
'''
    elif rusak == 'immutable':
        injeksi = '''
import student_submissions
asli=student_submissions.arsipkan
def rusak(kon,*args):
    asli(kon,*args)
    kon.execute('DROP TRIGGER pengiriman_butir_tolak_update')
student_submissions.arsipkan=rusak
'''
    else:
        injeksi = '''
import review_store
review_store.validasi_bukti=lambda kon,sesi,outcome,dilewati: []
'''
    hasil = jalankan_probe(tmp_path, injeksi=injeksi)
    assert hasil.returncode == 1
    assert hasil.stdout.strip() == '{"ok": false, "kode": "probe_gagal"}'
    assert hasil.stderr == ''
