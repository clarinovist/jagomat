"""Recovery tagihan nyata pada proses/source terisolasi; tanpa Docker/DB pengguna, waktu tetap sintetis.

Recovery lama = pin d91a1c5 (sudah mengenal `kelas_*`, belum mengenal `tagihan_*`). Perilaku rollback (tagihan batal tampak
terbuka di image lama) tidak diasersi: bergantung pada pin recovery yang dipilih saat rilis.
"""
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / 'scripts'))
import release_tagihan_pair as tagihan

RECOVERY = 'd91a1c50e8a3458c17a35635542307bd43aaa5a0'      # pin kelas, sebelum tagihan_*


def _ekstrak(tmp_path, revisi):
    arsip = tmp_path / ('recovery-%s.tar' % revisi[:7])
    with arsip.open('wb') as keluar:
        subprocess.run(['git', '-C', str(AKAR), 'archive', revisi, 'mesin'], stdout=keluar, check=True)
    tujuan = tmp_path / ('recovery-' + revisi[:7])
    tujuan.mkdir()
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, tujuan)
    return tujuan / 'mesin'


@pytest.fixture
def recovery_lama(tmp_path):
    return _ekstrak(tmp_path, RECOVERY)


def jalankan(sumber, kode, temp):
    return subprocess.run([sys.executable, '-B', '-'],
        input=kode.replace('/data/', str(temp) + '/'), capture_output=True, text=True,
        env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(sumber),
             'PYTHONDONTWRITEBYTECODE': '1'}, timeout=60)


def test_candidate_recovery_lama_candidate_tagihan_lintas_source(tmp_path, recovery_lama):
    for sumber, kode, marker in (
        (AKAR/'mesin', tagihan.SUMBER_TULIS, 'OSN_TAGIHAN_WRITER_OK'),
        (recovery_lama, tagihan.SUMBER_BACA, 'OSN_TAGIHAN_RECOVERY_OK'),
        (AKAR/'mesin', tagihan.SUMBER_KEMBALI, 'OSN_TAGIHAN_RETURN_OK'),
    ):
        hasil = jalankan(sumber, kode, tmp_path)
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


def test_probe_tidak_memakai_jam_nyata():
    for sumber in (tagihan.SUMBER_TULIS, tagihan.SUMBER_BACA, tagihan.SUMBER_KEMBALI):
        assert 'datetime' not in sumber and 'time.time' not in sumber and 'now(' not in sumber


def test_probe_baru_wajib_di_orchestrator_dan_manifest():
    import verify_submission_pair as pair
    import release_metadata
    assert pair.TAGIHAN_TULIS == tagihan.SUMBER_TULIS
    assert pair.TAGIHAN_BACA == tagihan.SUMBER_BACA
    assert pair.TAGIHAN_KEMBALI == tagihan.SUMBER_KEMBALI
    bukti = {'ok': True, 'candidate_revision': 'a'*40, 'recovery_revision': 'b'*40,
             'candidate_digest': 'sha256:'+'a'*64, 'recovery_digest': 'sha256:'+'b'*64,
             'pengiriman_pair_checks': 6, 'pilihan_pair_checks': 8,
             'learning_pair_checks': 8, 'subscription_pair_checks': 4,
             'admin_launch_pair_checks': 4, 'package_pair_checks': 8, 'quota_pair_checks': 8,
             'photo_pair_checks': 8, 'registration_pair_checks': 8, 'support_pair_checks': 8,
             'sensor_pair_checks': 8, 'policy_pair_checks': 6, 'question_pair_checks': 8,
             'kelas_pair_checks': 8, 'jadwal_pair_checks': 8, 'harga_pair_checks': 8,
             'tagihan_pair_checks': 8, 'provider_calls': 0}
    args = ('a'*40, 'b'*40, 'sha256:'+'a'*64, 'sha256:'+'b'*64)
    assert release_metadata.validasi_bukti_pasangan(bukti, *args)
    for nilai in (0, True, 7):
        with pytest.raises(ValueError):
            release_metadata.validasi_bukti_pasangan({**bukti, 'tagihan_pair_checks': nilai}, *args)
    tanpa = {k: v for k, v in bukti.items() if k != 'tagihan_pair_checks'}
    with pytest.raises(ValueError):
        release_metadata.validasi_bukti_pasangan(tanpa, *args)
