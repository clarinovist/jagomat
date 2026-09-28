"""Probe kuota9 kandidat→recovery exact→kandidat; tanpa Docker lokal."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

from test_package_release_pair import jalankan, recovery
from test_release_image import jalankan_probe, ekstrak_tar_aman

AKAR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(AKAR/'scripts'))
import release_package_pair as paket
import release_quota_pair as kuota
import release_metadata
import verify_submission_pair
import verify_release_image


@pytest.fixture
def recovery9(tmp_path):
    """Arsip historical admin9: jangan mengikuti pin foto yang sudah lebih baru."""
    revision = 'd973bf8dc329374fc24e928a87f56e7a088ac623'
    tujuan = tmp_path/'recovery9'
    tujuan.mkdir()
    arsip = tmp_path/'recovery9.tar'
    with arsip.open('wb') as keluar:
        subprocess.run(['git','-C',str(AKAR),'archive',revision,'mesin'],stdout=keluar,check=True)
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar,tujuan)
    return tujuan/'mesin'


def siapkan(tmp_path, pembaca=None):
    for kode in (paket.SUMBER_TULIS, paket.SUMBER_BACA, paket.SUMBER_KEMBALI):
        sumber = pembaca if kode == paket.SUMBER_BACA and pembaca is not None else AKAR/'mesin'
        hasil = jalankan(sumber, kode, tmp_path)
        assert hasil.returncode == 0, hasil.stderr


def test_historical_admin9_source_exact_bukan_bukti_foto(tmp_path, recovery9):
    siapkan(tmp_path, recovery9)
    # Source binary baseline exact, bukan salinan kandidat. CI tetap membuktikan
    # image/digest dari build pasangan pada SHA final sebelum rilis.
    for sumber,kode,marker in (
        (AKAR/'mesin',kuota.LEGACY_TULIS,'OSN_QUOTA_WRITER_OK'),
        (recovery9,kuota.LEGACY_BACA,'OSN_QUOTA_RECOVERY_OK'),
        (AKAR/'mesin',kuota.LEGACY_KEMBALI,'OSN_QUOTA_RETURN_OK'),
    ):
        hasil = jalankan(sumber,kode,tmp_path)
        assert hasil.returncode == 0, hasil.stderr
        assert hasil.stdout.strip() == marker


def test_mutasi_unknown_recovery_ditangkap_pair_dan_pulih(tmp_path, recovery9):
    siapkan(tmp_path, recovery9)
    hasil = jalankan(AKAR/'mesin',kuota.LEGACY_TULIS,tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    salinan = recovery9
    target=salinan/'assistant_quota_store.py'
    asli=target.read_text()
    guard='if row["status"] == "unknown" and status != "unknown" and not rekonsiliasi:'
    assert asli.count(guard)==1
    target.write_text(asli.replace(guard,'if False:'))
    # Mutasi berjalan pada turunan fixture; jangan biarkan release rusak masuk
    # sumber hijau yang harus merekonsiliasi unknown yang sama.
    mutan=tmp_path/'mutan'
    mutan.mkdir()
    shutil.copytree(tmp_path/'package-pair',mutan/'package-pair')
    merah=jalankan(salinan,kuota.LEGACY_BACA,mutan)
    assert merah.returncode!=0 and 'unknown_dilepas_tanpa_rekonsiliasi' in merah.stderr
    target.write_text(asli)
    hijau=jalankan(salinan,kuota.LEGACY_BACA,tmp_path)
    assert hijau.returncode==0,hijau.stderr
    assert hijau.stdout.strip()=='OSN_QUOTA_RECOVERY_OK'


def test_recovery8_bukan_recovery9(tmp_path,recovery):
    siapkan(tmp_path)
    hasil = jalankan(AKAR/'mesin',kuota.SUMBER_TULIS,tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    # Reader8 existing menolak versi9; tidak memalsukan kompatibilitas/skip.
    kode = "import admin_store\nfrom pathlib import Path\ntry:\n    with admin_store.buka_baca(Path('/data/package-pair/admin.db')): pass\nexcept admin_store.StoreBelumSiap: pass\nelse: raise AssertionError('recovery8_menerima9')\n"
    hasil = jalankan(recovery,kode,tmp_path)
    assert hasil.returncode == 0, hasil.stderr


def test_probe_image_candidate_kuota9_dan_recovery8_dibedakan(tmp_path):
    assert verify_release_image.ringkasan_untuk_revision('b'*40)['quota_checks'] == 8
    assert verify_release_image.ringkasan_untuk_revision('6a18cc745b79d31aa6112270732fbbb5a63cbc27')['quota_checks'] == 0
    hasil = jalankan_probe(tmp_path)
    assert hasil.returncode == 0, hasil.stdout+hasil.stderr
    assert json.loads(hasil.stdout)['admin_quota_schema'] == 9


def test_probe_image_recovery9_exact_wajib_kuota(tmp_path, recovery9):
    revision = 'd973bf8dc329374fc24e928a87f56e7a088ac623'
    hasil = jalankan_probe(tmp_path, sumber=recovery9, revision=revision)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    assert json.loads(hasil.stdout) == verify_release_image.ringkasan_untuk_revision(revision)
    assert json.loads(hasil.stdout)['quota_checks'] == 8


def test_probe_manifest_kuota_tidak_boleh_dihilangkan():
    assert verify_submission_pair.KUOTA_BACA == kuota.SUMBER_BACA
    bukti = dict(ok=True,candidate_revision='a'*40,recovery_revision='b'*40,
                 candidate_digest='sha256:'+'a'*64,recovery_digest='sha256:'+'b'*64,
                 pengiriman_pair_checks=6,pilihan_pair_checks=8,learning_pair_checks=8,
                 subscription_pair_checks=4,admin_launch_pair_checks=4,package_pair_checks=8,
                 quota_pair_checks=8,photo_pair_checks=8,registration_pair_checks=8,provider_calls=0)
    args=('a'*40,'b'*40,'sha256:'+'a'*64,'sha256:'+'b'*64)
    assert release_metadata.validasi_bukti_pasangan(bukti,*args)
    for field in ('quota_pair_checks', 'photo_pair_checks'):
        for salah in (0, True, 7):
            with pytest.raises(ValueError):
                release_metadata.validasi_bukti_pasangan({**bukti, field: salah}, *args)
        tanpa = dict(bukti)
        del tanpa[field]
        with pytest.raises(ValueError):
            release_metadata.validasi_bukti_pasangan(tanpa, *args)
