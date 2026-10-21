"""Gate pasangan retirement memakai source exact dan DB sintetis, tanpa Docker."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest
from test_release_image import ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR / 'scripts'))
import release_assistant_pair as probe

ANCHOR = json.loads((AKAR / 'scripts/release-metadata.json').read_text())['recovery_revision']
LAMA = 'c228749faef8acf29b7d6895173ead6aa5bc9e66'


def ekstrak(tmp_path, revision):
    arsip = tmp_path / (revision + '.tar')
    with arsip.open('wb') as f:
        subprocess.run(['git', '-C', str(AKAR), 'archive', revision, 'mesin'], stdout=f, check=True)
    tujuan = tmp_path / revision
    tujuan.mkdir()
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, tujuan)
    return tujuan / 'mesin'


def jalankan(source, kode, tmp_path):
    return subprocess.run([sys.executable, '-B', '-'],
        input=kode.replace('/data/', str(tmp_path) + '/'), text=True, capture_output=True,
        cwd=tmp_path, env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(source),
                          'PYTHONDONTWRITEBYTECODE': '1'}, timeout=40)


def mulai(tmp_path):
    result = jalankan(AKAR / 'mesin', probe.SUMBER_TULIS, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'OSN_ASSISTANT_WRITER_OK'


def test_pair_candidate_recovery_candidate(tmp_path):
    recovery = ekstrak(tmp_path, ANCHOR)
    mulai(tmp_path)
    for source, code, marker in (
        (recovery, probe.SUMBER_BACA, 'OSN_ASSISTANT_RECOVERY_OK'),
        (AKAR / 'mesin', probe.SUMBER_KEMBALI, 'OSN_ASSISTANT_RETURN_OK'),
    ):
        result = jalankan(source, code, tmp_path)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == marker


def test_pin_lama_ditolak_karena_payload_retired(tmp_path):
    recovery = ekstrak(tmp_path, LAMA)
    mulai(tmp_path)
    result = jalankan(recovery, probe.SUMBER_BACA, tmp_path)
    assert result.returncode != 0
    assert 'payload_retired_kembali' in result.stderr


@pytest.mark.parametrize('nama,lama,baru,alasan', [
    ('assistant_inline_http.py', 'if aksi in ("konfirmasi-memori", "ubah-memori"):',
     'if False:', 'endpoint_inline_retired_hidup'),
    ('assistant_http.py', "if aksi in ('konfirmasi', 'ubah'):",
     'if False:', 'endpoint_legacy_retired_hidup'),
    ('assistant_service.py', 'if pagar is not None:', 'if False:', 'fence_client_dilewati'),
])
@pytest.mark.parametrize('fase', ['candidate', 'recovery'])
def test_mutasi_probe_retirement_menangkap_guard(tmp_path, nama, lama, baru, alasan, fase):
    recovery = ekstrak(tmp_path, ANCHOR)
    if fase == 'recovery':
        mulai(tmp_path)
    path = recovery / nama
    awal = path.read_text()
    assert awal.count(lama) == 1
    path.write_text(awal.replace(lama, baru))
    # Fence network ada di fase reader; mutasi candidate fence dibuktikan dengan
    # menjalankan fase reader terhadap snapshot yang ditulis source termutasi.
    if fase == 'candidate':
        result = jalankan(recovery, probe.SUMBER_TULIS, tmp_path)
        if nama == 'assistant_service.py':
            assert result.returncode == 0, result.stderr
            result = jalankan(recovery, probe.SUMBER_BACA, tmp_path)
    else:
        result = jalankan(recovery, probe.SUMBER_BACA, tmp_path)
    assert result.returncode != 0
    assert alasan in result.stderr
    path.write_text(awal)
    # Mutation/DB hanya di tmp milik test; baseline hijau dibuktikan test pair.
