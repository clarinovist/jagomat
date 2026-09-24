"""Probe admin5 nyata sintetis: schema rusak ditolak tanpa membaca DB keluarga."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile

import pytest
from test_release_image import ekstrak_tar_aman, jalankan_probe

AKAR = Path(__file__).resolve().parents[2]


def _modul(nama):
    spek = importlib.util.spec_from_file_location('probe_uji_' + nama, AKAR / 'scripts' / (nama + '.py'))
    modul = importlib.util.module_from_spec(spek)
    spek.loader.exec_module(modul)
    return modul


def _python(sumber, cwd, source=None):
    awal = 'import sys\nsys.path.insert(0,' + repr(str(source or AKAR / 'mesin')) + ')\n'
    return subprocess.run([sys.executable, '-E', '-B', '-'], input=awal + sumber,
                          cwd=cwd, capture_output=True, text=True, timeout=45)


def _hash_db(akar):
    return {str(p.relative_to(akar)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in akar.rglob('*') if p.is_file()}


@pytest.fixture
def siap(tmp_path):
    deploy = _modul('deploy')
    data = tmp_path / 'data'
    data.mkdir()
    hasil = _python(deploy.PROBE_IMAGE.replace('/data/', str(data) + '/'), tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    shutil.copy2(data / 'probe-accounts.json', data / 'sandi.json')
    source = tmp_path / 'source'
    source.mkdir()
    for nama, versi in [('admin_store', 6), ('assistant_schema', 4), ('ai_store', 2)]:
        (source / (nama + '.py')).write_text('VERSI_SKEMA = %d\nraise RuntimeError("jangan import")\n' % versi)
    return deploy, data, source


@pytest.mark.parametrize('rusak', [None, 'admin4', 'admin7', 'source4', 'registry',
    'profil', 'receipt', 'konteks', 'kolom', 'trigger', 'admin_hilang', 'belajar_hilang',
    'pilot_tabel', 'pilot_kolom', 'pilot_trigger', 'pilot_sumber'])
def test_readiness_admin5_memeriksa_metadata_dan_tidak_menulis(siap, rusak, tmp_path):
    deploy, data, source = siap
    if rusak in ('admin4', 'admin7'):
        with sqlite3.connect(data / 'admin-control.db') as kon:
            kon.execute('PRAGMA user_version=' + ('4' if rusak == 'admin4' else '7'))
    elif rusak == 'source4':
        (source / 'admin_store.py').write_text('VERSI_SKEMA = 4\n')
    elif rusak == 'registry':
        import admin_store
        with sqlite3.connect(data / 'admin-control.db') as kon:
            kon.execute('DROP TABLE receipt_admin')
            ddl = admin_store._DDL.replace("'student_school_grade_update',", '').replace("'student_school_grade_updated',", '')
            admin_store._jalankan_ddl(kon, ddl)
    elif rusak in ('admin_hilang', 'belajar_hilang'):
        (data / ('admin-control.db' if rusak == 'admin_hilang' else 'latihan.db')).unlink()
    elif rusak:
        with sqlite3.connect(data / 'latihan.db') as kon:
            if rusak == 'pilot_tabel':
                kon.execute('DROP TABLE pilot_aksi')
            elif rusak == 'pilot_kolom':
                kon.execute('ALTER TABLE pilot_sesi RENAME COLUMN fingerprint TO salah')
            elif rusak == 'pilot_trigger':
                kon.execute('DROP TRIGGER pilot_konfirmasi_tolak_update')
            elif rusak == 'pilot_sumber':
                kon.execute('DROP TRIGGER pilot_konfirmasi_sumber')
            elif rusak == 'trigger':
                kon.execute('DROP TRIGGER konteks_konfirmasi_immutable_update')
            elif rusak == 'kolom':
                kon.execute('ALTER TABLE operasi_admin_profil RENAME COLUMN kelas_baru TO salah')
            else:
                tabel = {'profil': 'profil_belajar', 'receipt': 'operasi_admin_profil', 'konteks': 'konteks_butir'}[rusak]
                kon.execute('DROP TABLE ' + tabel)
    sebelum = _hash_db(data)
    skrip = deploy.PROBE_SKEMA.replace("akar_app = Path('/app')", 'akar_app = Path(' + repr(str(source)) + ')').replace('/data/', str(data) + '/')
    hasil = _python(skrip, tmp_path)
    assert (hasil.returncode == 0) is (rusak is None)
    if rusak is None:
        assert hasil.stdout.strip() == 'OSN_SCHEMA_ADMIN6_AI2_OK'
    else:
        assert 'OSN_SCHEMA_ADMIN6_AI2_OK' not in hasil.stdout
    assert _hash_db(data) == sebelum


def test_helper_profil_migrasi_receipt_dan_konteks_sintetis(tmp_path):
    helper = _modul('release_profile_probe')
    hasil = _python(helper.SUMBER_UJI_PROFIL + '\nassert uji_profil_konteks("uji") == 6\n', tmp_path)
    assert hasil.returncode == 0, hasil.stderr
    assert hasil.stdout == ''


@pytest.mark.parametrize('rusak', ['admin', 'receipt', 'konteks', 'reader'])
def test_helper_benar_benar_menggigit_guard_baru(tmp_path, rusak):
    source = tmp_path / 'source'
    source.mkdir()
    for p in (AKAR / 'mesin').glob('*.py'):
        shutil.copy2(p, source / p.name)
    nama, lama, baru = {
        'admin': ('admin_store.py', 'VERSI_SKEMA = 6', 'VERSI_SKEMA = 4'),
        'receipt': ('learning_profile_admin.py', "if not receipt_cocok(receipt, perintah) or baris['kelas_baru'] != kelas:", 'if False:'),
        'konteks': ('context_schema.py', "{tabel}_immutable_update BEFORE UPDATE", "{tabel}_immutable_update BEFORE UPDATE"),
        'reader': ('context_store.py', "if lama is None or lama['snapshot_json'] != serial:\n        raise ValueError('arsip konteks konfirmasi tidak cocok')", "if lama is None:\n        return"),
    }[rusak]
    p = source / nama
    teks = p.read_text()
    assert teks.count(lama) == 1
    if rusak == 'konteks':
        # Semua guard mutasi arsip dirusak agar test tidak merah karena SQL salah.
        teks = teks.replace("SELECT RAISE(ABORT, 'metadata konteks immutable');", 'SELECT 1;')
    else:
        teks = teks.replace(lama, baru)
    p.write_text(teks)
    helper = _modul('release_profile_probe')
    hasil = _python(helper.SUMBER_UJI_PROFIL + '\nuji_profil_konteks("uji")\n', tmp_path, source)
    assert hasil.returncode != 0
    assert 'AssertionError' in hasil.stderr
    assert 'ModuleNotFoundError' not in hasil.stderr


def test_recovery_pg_pinned_tetap_kontrak_historis_tanpa_klaim_profil5(tmp_path):
    revision = 'e38e2e150c514c54db5470820561e69654c699bf'
    arsip = tmp_path / 'recovery.tar'
    with arsip.open('wb') as output:
        subprocess.run(['git', '-C', str(AKAR), 'archive', revision, 'mesin'], stdout=output, check=True)
    tujuan = tmp_path / 'recovery'
    tujuan.mkdir()
    with tarfile.open(arsip) as tar:
        ekstrak_tar_aman(tar, tujuan)
    run = tmp_path / 'run'
    run.mkdir()
    hasil = jalankan_probe(run, tujuan / 'mesin', revision=revision)
    assert hasil.returncode == 0, hasil.stdout + hasil.stderr
    ringkas = json.loads(hasil.stdout)
    assert ringkas == _modul('verify_release_image').ringkasan_untuk_revision(revision)
    assert ringkas['profil_checks'] == 0 and ringkas['admin_schema'] is None
    # Image/source lama tidak boleh diberi kontrak kandidat hanya karena HTTP cocok.
    salah = jalankan_probe(run, tujuan / 'mesin', revision='b' * 40)
    assert salah.returncode != 0
    assert json.loads(salah.stdout)['ok'] is False


def test_verifier_candidate_tidak_boleh_melewati_probe_profil(tmp_path):
    hasil = jalankan_probe(tmp_path, injeksi=(
        'def gagal_profil(*args):\n'
        '    raise RuntimeError("profil_sintetis_tidak_sah")\n'
        'ruang["uji_profil_konteks"] = gagal_profil\n'
    ))
    assert hasil.returncode != 0
    assert json.loads(hasil.stdout) == {'ok': False, 'kode': 'probe_gagal'}


def test_ringkasan_candidate_wajib_mengaku_enam_probe_profil_dan_admin5():
    verifier = _modul('verify_release_image')
    hasil = verifier.ringkasan_untuk_revision('b' * 40)
    assert hasil['profil_checks'] == 6 and hasil['admin_schema'] == 6
    assert hasil['subscription_checks'] == 4
