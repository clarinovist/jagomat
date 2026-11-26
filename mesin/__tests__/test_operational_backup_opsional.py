"""DB opsional (sakelar.db/kurikulum.db) di backup operasional v2; data sintetis."""
import json
import shutil
import sqlite3

import pytest
from test_operational_backup import backup, sumber, buat, REV, IMAGE

import feature_switch
import cetakan_ai_store
import cetakan_store
import guru_pertemuan_bentuk
import guru_pertemuan_dasar
import guru_tautan_bentuk
import guru_tautan_dasar
import kurikulum_override

SEED = {nama: False for nama in feature_switch.NAMA_SAKELAR}


def buat_sakelar(data):
    feature_switch.ubah('FUNNEL_AKTIF', True, actor_id='uji', revisi_diharapkan=1,
                        seed=SEED, path=data / 'sakelar.db')
    return data / 'sakelar.db'


def buat_kurikulum(data):
    kurikulum_override.ubah_label('pengukuran', 'Ukur-ukur', actor_id='uji', revisi_diharapkan=0,
                                  path=data / 'kurikulum.db')
    return data / 'kurikulum.db'


ISI_CETAKAN = {
    'kelas': 2, 'bab': 2, 'judul': 'Penjumlahan sintetis', 'teks': '{a} ditambah {b}',
    'variabel': {'a': [10, 50], 'b': [1, 40]}, 'syarat': ['a + b <= 99'], 'kunci': 'a + b',
}


def buat_cetakan(data):
    cetakan_store.buat_draf(ISI_CETAKAN, sumber='manual', actor_id='uji', path=data / 'cetakan.db')
    return data / 'cetakan.db'


def buat_kuota_ai(data):
    cetakan_ai_store.reservasi(2, 2, 'uji', path=data / 'cetakan_ai.db')
    return data / 'cetakan_ai.db'


def buat_catatan_pertemuan(data):
    """DB catatan pertemuan sintetis lewat jalur tulis yang sama dengan aplikasi (berkas dibuat 0600, skema v1)."""
    guru_pertemuan_dasar.catat(
        kunci='klp_' + 'c' * 32 + ':1', pertemuan_id=1, mulai='2026-11-21T02:00:00', topik='lainnya',
        hadir={'kor_' + 'a' * 32: 'hadir'}, oleh='akun_' + 'd' * 32, peran='guru',
        pada='2026-11-27T01:00:00', path=data / 'guru-pertemuan.db')
    return data / 'guru-pertemuan.db'


def buat_kode_tautan(data):
    """DB tautan kode anak sintetis lewat jalur tulis yang sama dengan aplikasi (berkas dibuat 0600, skema v1)."""
    guru_tautan_dasar.buat_kode(
        akun_id='akun_' + 'e' * 32, siswa_id=7, kode_hash='a' * 64, oleh='akun_' + 'c' * 32,
        peran='orang_tua', pada='2026-11-10T10:00:00', path=data / 'guru-tautan.db')
    return data / 'guru-tautan.db'


def sahkan_ulang(target, **manifest):
    """Perbarui inventaris/hash manifest sesudah isi bundle sengaja diubah (simulasi bundle rusak)."""
    m = backup.read_json(target / backup.MANIFEST)
    m['files'], m['directories'] = backup.inventory(target)
    m.update(manifest)
    (target / backup.MANIFEST).write_text(json.dumps(m))


def ubah_sqlite(path, *sql):
    with sqlite3.connect(path) as c:
        for s in sql:
            c.execute(s)
    c.close()


def turunkan_ke_v1(target):
    """Bentuk bundle lama: tanpa opsional/ dan key optional, version 1."""
    shutil.rmtree(target / 'opsional')
    m = backup.read_json(target / backup.MANIFEST)
    del m['optional']
    m['version'] = 1
    m['files'], m['directories'] = backup.inventory(target)
    (target / backup.MANIFEST).write_text(json.dumps(m))


def test_capture_dengan_sakelar_v2_tercatat_dan_roundtrip(sumber, tmp_path):
    buat_sakelar(sumber)
    target = tmp_path / 'backup-uji'
    result = backup.capture(sumber, target, REV, IMAGE, lambda: None)
    m = backup.read_json(target / backup.MANIFEST)
    assert m['version'] == 2 and m['optional'] == ['sakelar.db']
    assert result['ok'] and result['optional'] == ('sakelar.db',)
    entri = m['files']['opsional/sakelar.db']
    assert entri['sha256'] == backup.hash_file(target / 'opsional/sakelar.db')
    with sqlite3.connect(target / 'opsional/sakelar.db') as c:
        assert c.execute("SELECT aktif FROM sakelar WHERE nama='FUNNEL_AKTIF'").fetchone() == (1,)
    assert not list(target.rglob('*-wal')) and not list(target.rglob('*-shm'))
    archive = tmp_path / 'privat.tar'
    with archive.open('wb') as f:
        backup.export(target, f)
    (tmp_path / 'restore').mkdir(mode=0o700)
    restored = tmp_path / 'restore' / 'backup-uji'
    assert backup.unpack(archive, restored) == result
    assert (restored / 'opsional/sakelar.db').read_bytes() == (target / 'opsional/sakelar.db').read_bytes()


def test_capture_kurikulum_v2_tercatat_dan_skema_lolos(sumber, tmp_path):
    buat_kurikulum(sumber)
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['optional'] == ('kurikulum.db',)
    with sqlite3.connect(target / 'opsional/kurikulum.db') as c:
        assert c.execute("SELECT label FROM label_awam WHERE topik_id='pengukuran'").fetchone() == ('Ukur-ukur',)
    c.close()


def test_capture_kedua_opsional_terurut(sumber, tmp_path):
    buat_sakelar(sumber)
    buat_kurikulum(sumber)
    target = buat(sumber, tmp_path)
    assert backup.read_json(target / backup.MANIFEST)['optional'] == ['kurikulum.db', 'sakelar.db']


def test_capture_cetakan_v2_tercatat_dan_skema_lolos(sumber, tmp_path):
    buat_cetakan(sumber)
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['optional'] == ('cetakan.db',)
    with sqlite3.connect(target / 'opsional/cetakan.db') as c:
        assert c.execute('SELECT status, revisi FROM cetakan').fetchone() == ('draf', 1)
    c.close()


def test_capture_keenam_opsional_terurut(sumber, tmp_path):
    buat_sakelar(sumber)
    buat_kurikulum(sumber)
    buat_cetakan(sumber)
    buat_kuota_ai(sumber)
    buat_catatan_pertemuan(sumber)
    buat_kode_tautan(sumber)
    target = buat(sumber, tmp_path)
    assert backup.OPSIONAL == (
        'sakelar.db', 'kurikulum.db', 'cetakan.db', 'cetakan_ai.db', 'guru-pertemuan.db', 'guru-tautan.db')
    assert backup.read_json(target / backup.MANIFEST)['optional'] == [
        'cetakan.db', 'cetakan_ai.db', 'guru-pertemuan.db', 'guru-tautan.db', 'kurikulum.db', 'sakelar.db']
    assert backup.validate(target)['optional'] == (
        'cetakan.db', 'cetakan_ai.db', 'guru-pertemuan.db', 'guru-tautan.db', 'kurikulum.db', 'sakelar.db')


def test_capture_tanpa_catatan_pertemuan_tetap_valid_seperti_empat_opsional_lama(sumber, tmp_path):
    buat_sakelar(sumber)
    buat_cetakan(sumber)
    buat_kuota_ai(sumber)
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['optional'] == ('cetakan.db', 'cetakan_ai.db', 'sakelar.db')


def test_nama_opsional_catatan_pertemuan_sama_dengan_nama_berkas_aplikasi():
    """Daftar OPSIONAL (literal) dan modul bentuk harus menyebut berkas yang sama."""
    assert guru_pertemuan_bentuk.NAMA_BERKAS in backup.OPSIONAL
    assert guru_pertemuan_dasar.BERKAS_BAWAAN == '/data/' + guru_pertemuan_bentuk.NAMA_BERKAS


def test_capture_catatan_pertemuan_tercatat_dan_skema_lolos(sumber, tmp_path):
    buat_catatan_pertemuan(sumber)
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['optional'] == ('guru-pertemuan.db',)
    with sqlite3.connect(target / 'opsional/guru-pertemuan.db') as c:
        assert c.execute('SELECT topik, peran FROM pertemuan_jurnal').fetchone() == ('lainnya', 'guru')
        assert c.execute('SELECT status FROM pertemuan_hadir').fetchone() == ('hadir',)
    c.close()


def test_capture_tolak_catatan_pertemuan_skema_asing_dan_tidak_meninggalkan_bundle(sumber, tmp_path):
    ubah_sqlite(sumber / 'guru-pertemuan.db', 'CREATE TABLE sementara(id INTEGER)')
    with pytest.raises(backup.Ditolak, match='schema catatan pertemuan'):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_catatan_pertemuan_user_version_salah_ditolak(sumber, tmp_path):
    buat_catatan_pertemuan(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/guru-pertemuan.db', 'PRAGMA user_version = 2')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema catatan pertemuan'):
        backup.validate(target)


@pytest.mark.parametrize('tabel', guru_pertemuan_bentuk.TABEL_SKEMA)
def test_catatan_pertemuan_tabel_hilang_ditolak(sumber, tmp_path, tabel):
    buat_catatan_pertemuan(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/guru-pertemuan.db',
                'DROP TRIGGER IF EXISTS %s_tolak_ubah' % tabel,
                'DROP TRIGGER IF EXISTS %s_tolak_hapus' % tabel,
                'DROP TABLE %s' % tabel)
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema catatan pertemuan'):
        backup.validate(target)


def test_capture_tanpa_kode_tautan_tetap_valid_seperti_lima_opsional_lama(sumber, tmp_path):
    buat_sakelar(sumber)
    buat_catatan_pertemuan(sumber)
    buat_kuota_ai(sumber)
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['optional'] == ('cetakan_ai.db', 'guru-pertemuan.db', 'sakelar.db')


def test_nama_opsional_kode_tautan_sama_dengan_nama_berkas_aplikasi():
    """Daftar OPSIONAL (literal) dan modul bentuk harus menyebut berkas yang sama."""
    assert guru_tautan_bentuk.NAMA_BERKAS in backup.OPSIONAL
    assert guru_tautan_dasar.BERKAS_BAWAAN == '/data/' + guru_tautan_bentuk.NAMA_BERKAS


def test_capture_kode_tautan_tercatat_dan_skema_lolos(sumber, tmp_path):
    buat_kode_tautan(sumber)
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['optional'] == ('guru-tautan.db',)
    with sqlite3.connect(target / 'opsional/guru-tautan.db') as c:
        assert c.execute('SELECT siswa_id, peran FROM kode_anak').fetchone() == (7, 'orang_tua')
    c.close()


def test_capture_tolak_kode_tautan_skema_asing_dan_tidak_meninggalkan_bundle(sumber, tmp_path):
    ubah_sqlite(sumber / 'guru-tautan.db', 'CREATE TABLE sementara(id INTEGER)')
    with pytest.raises(backup.Ditolak, match='schema tautan'):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_kode_tautan_user_version_salah_ditolak(sumber, tmp_path):
    buat_kode_tautan(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/guru-tautan.db', 'PRAGMA user_version = 2')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema tautan'):
        backup.validate(target)


@pytest.mark.parametrize('tabel', guru_tautan_bentuk.TABEL_SKEMA)
def test_kode_tautan_tabel_hilang_ditolak(sumber, tmp_path, tabel):
    buat_kode_tautan(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/guru-tautan.db',
                'DROP TRIGGER IF EXISTS %s_tolak_ubah' % tabel,
                'DROP TRIGGER IF EXISTS %s_tolak_hapus' % tabel,
                'DROP TABLE %s' % tabel)
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema tautan'):
        backup.validate(target)


def test_capture_kuota_cetakan_ai_tercatat_dan_skema_lolos(sumber, tmp_path):
    buat_kuota_ai(sumber)
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['optional'] == ('cetakan_ai.db',)
    with sqlite3.connect(target / 'opsional/cetakan_ai.db') as c:
        assert c.execute('SELECT status, kelas, bab FROM permintaan').fetchone() == ('berjalan', 2, 2)
    c.close()


def test_capture_tolak_kuota_cetakan_ai_skema_asing_dan_tidak_meninggalkan_bundle(sumber, tmp_path):
    ubah_sqlite(sumber / 'cetakan_ai.db', 'CREATE TABLE sementara(id INTEGER)')
    with pytest.raises(backup.Ditolak, match='schema kuota cetakan ai'):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_kuota_cetakan_ai_user_version_salah_ditolak(sumber, tmp_path):
    buat_kuota_ai(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/cetakan_ai.db', 'PRAGMA user_version = 2')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema kuota cetakan ai'):
        backup.validate(target)


def test_kuota_cetakan_ai_tabel_hilang_ditolak(sumber, tmp_path):
    assert 'permintaan' in cetakan_ai_store.TABEL_SKEMA
    buat_kuota_ai(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/cetakan_ai.db', 'DROP TABLE permintaan')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema kuota cetakan ai'):
        backup.validate(target)


def test_capture_tolak_cetakan_skema_asing_dan_tidak_meninggalkan_bundle(sumber, tmp_path):
    ubah_sqlite(sumber / 'cetakan.db', 'CREATE TABLE sementara(id INTEGER)')
    with pytest.raises(backup.Ditolak, match='schema cetakan'):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_cetakan_user_version_salah_ditolak(sumber, tmp_path):
    buat_cetakan(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/cetakan.db', 'PRAGMA user_version = 2')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema cetakan'):
        backup.validate(target)


@pytest.mark.parametrize('tabel', ['audit_cetakan', 'cetakan'])
def test_cetakan_tabel_hilang_ditolak(sumber, tmp_path, tabel):
    assert tabel in cetakan_store.TABEL_SKEMA
    buat_cetakan(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/cetakan.db', 'PRAGMA foreign_keys = OFF', f'DROP TABLE {tabel}')
    sahkan_ulang(target)
    # Tabel induk yang hilang tertangkap lebih dulu oleh cek FK (audit_cetakan merujuknya).
    with pytest.raises(backup.Ditolak, match='schema cetakan|integrity/FK'):
        backup.validate(target)


def test_capture_tolak_kurikulum_skema_asing_dan_tidak_meninggalkan_bundle(sumber, tmp_path):
    ubah_sqlite(sumber / 'kurikulum.db', 'CREATE TABLE sementara(id INTEGER)')
    with pytest.raises(backup.Ditolak, match='schema kurikulum'):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_kurikulum_user_version_salah_ditolak(sumber, tmp_path):
    buat_kurikulum(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/kurikulum.db', 'PRAGMA user_version = 2')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema kurikulum'):
        backup.validate(target)


@pytest.mark.parametrize('tabel', kurikulum_override.TABEL_SKEMA)
def test_kurikulum_tabel_hilang_ditolak(sumber, tmp_path, tabel):
    buat_kurikulum(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/kurikulum.db', f'DROP TABLE {tabel}')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema kurikulum'):
        backup.validate(target)


def test_capture_tanpa_opsional_v2_kosong(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    m = backup.read_json(target / backup.MANIFEST)
    assert m['version'] == 2 and m['optional'] == []
    assert (target / 'opsional').is_dir() and not list((target / 'opsional').iterdir())
    assert backup.validate(target)['optional'] == ()
    archive = tmp_path / 'privat.tar'
    with archive.open('wb') as f:
        backup.export(target, f)
    (tmp_path / 'restore').mkdir(mode=0o700)
    assert backup.unpack(archive, tmp_path / 'restore' / 'backup-uji')['optional'] == ()


def test_bundle_v1_lama_tetap_valid(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    turunkan_ke_v1(target)
    result = backup.validate(target)
    assert result['ok'] and result['optional'] == ()


def test_v1_tidak_boleh_membawa_opsional(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    turunkan_ke_v1(target)
    (target / 'opsional').mkdir(mode=0o700)
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='root'):
        backup.validate(target)


def test_v2_tanpa_key_optional_atau_dir_ditolak(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    m = backup.read_json(target / backup.MANIFEST)
    del m['optional']
    (target / backup.MANIFEST).write_text(json.dumps(m))
    with pytest.raises(backup.Ditolak, match='manifest'):
        backup.validate(target)
    target2 = tmp_path / 'backup-dua'
    backup.capture(sumber, target2, REV, IMAGE, lambda: None)
    shutil.rmtree(target2 / 'opsional')
    sahkan_ulang(target2)
    with pytest.raises(backup.Ditolak, match='root'):
        backup.validate(target2)


def test_version_3_ditolak(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    sahkan_ulang(target, version=3)
    with pytest.raises(backup.Ditolak, match='manifest'):
        backup.validate(target)


def test_berkas_di_opsional_tidak_tercantum_ditolak(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    shutil.copy2(sumber / 'riset-konsumen.db', target / 'opsional/sakelar.db')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='opsional'):
        backup.validate(target)


def test_nama_optional_tanpa_berkas_ditolak(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    sahkan_ulang(target, optional=['sakelar.db'])
    with pytest.raises(backup.Ditolak, match='opsional'):
        backup.validate(target)


@pytest.mark.parametrize('names', (['asing.db'], ['sakelar.db', 'sakelar.db'], ['sakelar.db', 'kurikulum.db'], 'sakelar.db', [1]))
def test_daftar_optional_invalid_ditolak(sumber, tmp_path, names):
    target = buat(sumber, tmp_path)
    sahkan_ulang(target, optional=names)
    with pytest.raises(backup.Ditolak, match='daftar opsional'):
        backup.validate(target)


def test_sakelar_user_version_salah_ditolak(sumber, tmp_path):
    buat_sakelar(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/sakelar.db', 'PRAGMA user_version = 2')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema sakelar'):
        backup.validate(target)


def test_sakelar_tabel_hilang_ditolak(sumber, tmp_path):
    buat_sakelar(sumber)
    target = buat(sumber, tmp_path)
    ubah_sqlite(target / 'opsional/sakelar.db', 'DROP TABLE audit_sakelar')
    sahkan_ulang(target)
    with pytest.raises(backup.Ditolak, match='schema sakelar'):
        backup.validate(target)


def test_sakelar_rusak_bytes_acak_ditolak(sumber, tmp_path):
    buat_sakelar(sumber)
    target = buat(sumber, tmp_path)
    (target / 'opsional/sakelar.db').write_bytes(bytes(range(256)) * 64)
    sahkan_ulang(target)
    with pytest.raises((backup.Ditolak, sqlite3.DatabaseError)):
        backup.validate(target)


def test_hash_opsional_berubah_ditolak(sumber, tmp_path):
    buat_sakelar(sumber)
    target = buat(sumber, tmp_path)
    with (target / 'opsional/sakelar.db').open('ab') as f:
        f.write(b'x')
    with pytest.raises(backup.Ditolak, match='hash'):
        backup.validate(target)


def test_capture_tolak_opsional_symlink(sumber, tmp_path):
    asli = buat_sakelar(sumber)
    tujuan = sumber / 'asli-sakelar.db'
    asli.rename(tujuan)
    asli.symlink_to(tujuan)
    with pytest.raises(backup.Ditolak, match='biasa'):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_capture_tolak_opsional_symlink_menggantung(sumber, tmp_path):
    (sumber / 'kurikulum.db').symlink_to(sumber / 'tidak-ada.db')
    with pytest.raises(backup.Ditolak, match='biasa'):
        buat(sumber, tmp_path)


def test_capture_opsional_dikunci_writer_ditolak(sumber, tmp_path):
    buat_sakelar(sumber)
    with sqlite3.connect(sumber / 'sakelar.db', timeout=0.1, isolation_level=None) as pemegang:
        pemegang.execute('BEGIN IMMEDIATE')
        with pytest.raises(sqlite3.OperationalError):
            buat(sumber, tmp_path)
    pemegang.close()
    assert not (tmp_path / 'backup-uji').exists()
