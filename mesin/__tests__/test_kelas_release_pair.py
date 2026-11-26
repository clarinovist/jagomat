"""Recovery kelas-paket nyata pada proses/source terisolasi; tanpa Docker/DB pengguna."""
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / 'scripts'))
import release_kelas_pair as kelas

RECOVERY = '85bbd528264b221148d522d958bcb31bb66ce907'


@pytest.fixture
def recovery(tmp_path):
    arsip = tmp_path / 'recovery.tar'
    with arsip.open('wb') as keluar:
        subprocess.run(['git', '-C', str(AKAR), 'archive', RECOVERY, 'mesin'],
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
             'PYTHONDONTWRITEBYTECODE': '1'}, timeout=60)


def test_candidate_recovery_candidate_kelas_lintas_source(tmp_path, recovery):
    for sumber, kode, marker in (
        (AKAR/'mesin', kelas.SUMBER_TULIS, 'OSN_KELAS_WRITER_OK'),
        (recovery, kelas.SUMBER_BACA, 'OSN_KELAS_RECOVERY_OK'),
        (AKAR/'mesin', kelas.SUMBER_KEMBALI, 'OSN_KELAS_RETURN_OK'),
    ):
        hasil = jalankan(sumber, kode, tmp_path)
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


def test_probe_baru_wajib_di_orchestrator_dan_manifest():
    import verify_submission_pair as pair
    import release_metadata
    assert pair.KELAS_TULIS == kelas.SUMBER_TULIS
    bukti = {'ok': True, 'candidate_revision': 'a'*40, 'recovery_revision': 'b'*40,
             'candidate_digest': 'sha256:'+'a'*64, 'recovery_digest': 'sha256:'+'b'*64,
             'pengiriman_pair_checks': 6, 'pilihan_pair_checks': 8,
             'learning_pair_checks': 8, 'subscription_pair_checks': 4,
             'admin_launch_pair_checks': 4, 'package_pair_checks': 8, 'quota_pair_checks': 8,
             'photo_pair_checks': 8, 'registration_pair_checks': 8, 'support_pair_checks': 8,
             'sensor_pair_checks': 8, 'policy_pair_checks': 6, 'question_pair_checks': 8,
             'kelas_pair_checks': 8, 'jadwal_pair_checks': 8, 'harga_pair_checks': 8, 'tagihan_pair_checks': 8, 'provider_calls': 0}
    args = ('a'*40, 'b'*40, 'sha256:'+'a'*64, 'sha256:'+'b'*64)
    assert release_metadata.validasi_bukti_pasangan(bukti, *args)
    for nilai in (0, True, 7):
        with pytest.raises(ValueError):
            release_metadata.validasi_bukti_pasangan({**bukti, 'kelas_pair_checks': nilai}, *args)
