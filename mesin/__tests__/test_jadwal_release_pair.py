"""Recovery jadwal nyata pada proses/source terisolasi; tanpa Docker/DB pengguna, jam tetap sintetis."""
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest

from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / 'scripts'))
import release_jadwal_pair as jadwal

RECOVERY = '6142611adbc79a2a659e9adb764211856494f2ce'
RECOVERY_KELAS_LAMA = '85bbd528264b221148d522d958bcb31bb66ce907'


def _ekstrak(tmp_path, revisi):
    arsip = tmp_path / ('recovery-%s.tar' % revisi[:7])
    with arsip.open('wb') as keluar:
        subprocess.run(['git', '-C', str(AKAR), 'archive', revisi, 'mesin'],
                       stdout=keluar, check=True)
    tujuan = tmp_path / ('recovery-' + revisi[:7])
    tujuan.mkdir()
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, tujuan)
    return tujuan / 'mesin'


@pytest.fixture
def recovery(tmp_path):
    return _ekstrak(tmp_path, RECOVERY)


def jalankan(sumber, kode, temp):
    return subprocess.run([sys.executable, '-B', '-'],
        input=kode.replace('/data/', str(temp) + '/'), capture_output=True, text=True,
        env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(sumber),
             'PYTHONDONTWRITEBYTECODE': '1'}, timeout=60)


def test_candidate_recovery_candidate_jadwal_lintas_source(tmp_path, recovery):
    for sumber, kode, marker in (
        (AKAR/'mesin', jadwal.SUMBER_TULIS, 'OSN_JADWAL_WRITER_OK'),
        (recovery, jadwal.SUMBER_BACA, 'OSN_JADWAL_RECOVERY_OK'),
        (AKAR/'mesin', jadwal.SUMBER_KEMBALI, 'OSN_JADWAL_RETURN_OK'),
    ):
        hasil = jalankan(sumber, kode, tmp_path)
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


def test_recovery_kelas_lama_tetap_membuka_db_berisi_jadwal(tmp_path):
    """Rollback ke pin kelas sebelumnya aman: `jadwal_*` terpisah dari `kelas_*`, jadi tidak ditolak."""
    lama = _ekstrak(tmp_path, RECOVERY_KELAS_LAMA)
    hasil = jalankan(AKAR/'mesin', jadwal.SUMBER_TULIS, tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    baca = jadwal.BERSAMA + r'''
import kelas_store, schema_pesanan, schema_transfer
meta = baca('awal.json')
assert rows(pa) == meta['admin']
with kelas_store.buka(pa) as kon:
    assert kelas_store.tagihan_dari(kon, AKUN, meta['mini'], UNGGAH).status == 'aktif'
with admin_store.buka_baca(pa) as kon:
    assert schema_pesanan.validasi(kon) and schema_transfer.validasi(kon)
assert rows(pa) == meta['admin']
print('BACA_KELAS_LAMA_OK')
'''
    hasil = jalankan(lama, baca, tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    assert hasil.stdout.strip() == 'BACA_KELAS_LAMA_OK'


def test_probe_tidak_memakai_jam_nyata():
    for sumber in (jadwal.SUMBER_TULIS, jadwal.SUMBER_BACA, jadwal.SUMBER_KEMBALI):
        assert 'datetime' not in sumber and 'time.time' not in sumber and 'now(' not in sumber


def test_probe_baru_wajib_di_orchestrator_dan_manifest():
    import verify_submission_pair as pair
    import release_metadata
    assert pair.JADWAL_TULIS == jadwal.SUMBER_TULIS
    assert pair.JADWAL_BACA == jadwal.SUMBER_BACA
    assert pair.JADWAL_KEMBALI == jadwal.SUMBER_KEMBALI
    bukti = {'ok': True, 'candidate_revision': 'a'*40, 'recovery_revision': 'b'*40,
             'candidate_digest': 'sha256:'+'a'*64, 'recovery_digest': 'sha256:'+'b'*64,
             'pengiriman_pair_checks': 6, 'pilihan_pair_checks': 8,
             'learning_pair_checks': 8, 'subscription_pair_checks': 4,
             'admin_launch_pair_checks': 4, 'package_pair_checks': 8, 'quota_pair_checks': 8,
             'photo_pair_checks': 8, 'registration_pair_checks': 8, 'support_pair_checks': 8,
             'sensor_pair_checks': 8, 'policy_pair_checks': 6, 'question_pair_checks': 8,
             'kelas_pair_checks': 8, 'jadwal_pair_checks': 8, 'provider_calls': 0}
    args = ('a'*40, 'b'*40, 'sha256:'+'a'*64, 'sha256:'+'b'*64)
    assert release_metadata.validasi_bukti_pasangan(bukti, *args)
    for nilai in (0, True, 7):
        with pytest.raises(ValueError):
            release_metadata.validasi_bukti_pasangan({**bukti, 'jadwal_pair_checks': nilai}, *args)
    tanpa = {k: v for k, v in bukti.items() if k != 'jadwal_pair_checks'}
    with pytest.raises(ValueError):
        release_metadata.validasi_bukti_pasangan(tanpa, *args)
