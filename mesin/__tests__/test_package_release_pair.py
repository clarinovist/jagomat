"""Recovery admin8 nyata pada proses/source terisolasi; tanpa Docker/DB pengguna."""
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / 'scripts'))
import release_package_pair as paket


@pytest.fixture
def recovery(tmp_path):
    arsip = tmp_path / 'recovery.tar'
    with arsip.open('wb') as keluar:
        subprocess.run(['git', '-C', str(AKAR), 'archive',
                        '6a18cc745b79d31aa6112270732fbbb5a63cbc27', 'mesin'],
                       stdout=keluar, check=True)
    tujuan = tmp_path / 'recovery'
    tujuan.mkdir()
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, tujuan)
    return tujuan / 'mesin'


def jalankan(sumber, kode, temp):
    return subprocess.run([sys.executable, '-B', '-'],
        input=kode.replace('/data/', str(temp) + '/'), capture_output=True, text=True,
        env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(sumber),
             'OSN_PBKDF2_ITERASI': '1000', 'PYTHONDONTWRITEBYTECODE': '1'}, timeout=40)


def test_candidate_recovery_candidate_admin8_lintas_source(tmp_path, recovery):
    for sumber, kode, marker in (
        (AKAR/'mesin', paket.SUMBER_TULIS, 'OSN_PACKAGE_WRITER_OK'),
        (recovery, paket.SUMBER_BACA, 'OSN_PACKAGE_RECOVERY_OK'),
        (AKAR/'mesin', paket.SUMBER_KEMBALI, 'OSN_PACKAGE_RETURN_OK'),
    ):
        hasil = jalankan(sumber, kode, tmp_path)
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


def test_probe_image_penuh_membaca_baseline_admin8(tmp_path, recovery):
    from test_release_image import jalankan_probe
    import verify_release_image
    hasil = jalankan_probe(tmp_path, sumber=recovery,
                           revision='6a18cc745b79d31aa6112270732fbbb5a63cbc27')
    assert hasil.returncode == 0, hasil.stderr
    import json
    assert json.loads(hasil.stdout) == verify_release_image.ringkasan_untuk_revision(
        '6a18cc745b79d31aa6112270732fbbb5a63cbc27')


def test_mutasi_fencing_recovery_ditangkap_probe(tmp_path, recovery):
    hasil = jalankan(AKAR/'mesin', paket.SUMBER_TULIS, tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    path = recovery/'subscription_worker.py'
    awal = path.read_text()
    guard = 'if baru != sidik:'
    assert awal.count(guard) == 1
    path.write_text(awal.replace(guard, 'if False:'))
    hasil = jalankan(recovery, paket.SUMBER_BACA, tmp_path)
    assert hasil.returncode != 0
    assert 'fencing_pair_dilewati' in hasil.stderr
    path.write_text(awal)


def test_probe_baru_wajib_di_orchestrator_dan_manifest():
    import verify_submission_pair as pair
    import release_metadata
    assert pair.PAKET_TULIS == paket.SUMBER_TULIS
    bukti = {'ok': True, 'candidate_revision': 'a'*40, 'recovery_revision': 'b'*40,
             'candidate_digest': 'sha256:'+'a'*64, 'recovery_digest': 'sha256:'+'b'*64,
             'pengiriman_pair_checks': 6, 'pilihan_pair_checks': 8,
             'learning_pair_checks': 8, 'subscription_pair_checks': 4,
             'admin_launch_pair_checks': 4, 'package_pair_checks': 8, 'quota_pair_checks': 8, 'photo_pair_checks': 8, 'registration_pair_checks': 8, 'support_pair_checks': 8, 'provider_calls': 0}
    args = ('a'*40, 'b'*40, 'sha256:'+'a'*64, 'sha256:'+'b'*64)
    assert release_metadata.validasi_bukti_pasangan(bukti, *args)
    for nilai in (0, True, 7):
        with pytest.raises(ValueError):
            release_metadata.validasi_bukti_pasangan({**bukti, 'package_pair_checks': nilai}, *args)
