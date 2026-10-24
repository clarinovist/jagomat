"""Backup operasional memakai sumber sintetis, tidak SSH/produksi."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tarfile

import pytest
from test_admin_backup import _buat_bundle

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'operational_backup.py'
spec = importlib.util.spec_from_file_location('operational_backup', SCRIPT)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
REV = 'a' * 40
IMAGE = 'sha256:' + 'b' * 64


@pytest.fixture
def sumber(tmp_path):
    data = _buat_bundle(tmp_path)
    (data / 'manifest.json').unlink()
    import research_store
    research_store.siapkan(data / 'riset-konsumen.db', sekarang=1)
    import database
    with database.buka(data / 'latihan.db') as c:
        anak = database.tambah_siswa(c, 'Fixture', 'P3', pemilik='guru')
        sid = database.buat_sesi(c, anak, 1, topik='pola-bilangan', level='P3')
        assert sid == 1
        database.simpan_lampiran(c, sid, 'acak.jpg')
    (data / 'riset-konsumen.db').chmod(0o600)
    (data / 'lampiran').mkdir(mode=0o700)
    (data / 'lampiran' / '1').mkdir(mode=0o700)
    (data / 'lampiran' / '1' / 'acak.jpg').write_bytes(b'foto sintetis')
    (data / 'lampiran' / '1' / 'acak.jpg').chmod(0o600)
    (data / 'sesi.json').write_text('JANGAN SALIN')
    (data / 'deepseek.key').write_text('BUKAN CREDENTIAL NYATA')
    (data / 'transient').mkdir()
    return data


def buat(sumber, tmp_path):
    target = tmp_path / 'backup-uji'
    backup.capture(sumber, target, REV, IMAGE, lambda: None)
    return target


def test_capture_lengkap_privat_dan_transfer_roundtrip(sumber, tmp_path):
    calls = []
    target = tmp_path / 'backup-uji'
    result = backup.capture(sumber, target, REV, IMAGE, lambda: calls.append(1))
    assert calls == [1, 1]
    assert result['ok'] and result['core_files'] == 5 and result['attachments'] == 1
    assert result['research_separate']
    assert (target / 'lampiran/1/acak.jpg').read_bytes() == b'foto sintetis'
    assert not (target / 'sesi.json').exists() and not (target / 'deepseek.key').exists()
    for p in target.rglob('*'):
        assert p.stat().st_mode & 0o077 == 0
    archive = tmp_path / 'privat.tar'
    with archive.open('wb') as f:
        backup.export(target, f)
    (tmp_path / 'restore').mkdir(mode=0o700)
    restored = tmp_path / 'restore' / 'backup-uji'
    assert backup.unpack(archive, restored) == result
    assert backup.inventory(restored) == backup.inventory(target)


def test_foto_durable_img_dari_writer_kanonis_ikut_roundtrip(sumber, tmp_path, monkeypatch):
    import attachments
    monkeypatch.setattr(attachments, 'direktori_lampiran', lambda: sumber / 'lampiran')
    nama = attachments._file_baru_durable(1, b'foto durable sintetis', 'foto_' + 'a' * 32)
    with sqlite3.connect(sumber / 'latihan.db') as c:
        c.execute('INSERT INTO lampiran (sesi_id,nama_berkas,mime) VALUES (1,?,?)', (nama, 'image/jpeg'))
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['attachments'] == 2
    assert (target / 'lampiran/1' / nama).read_bytes() == b'foto durable sintetis'


def test_writer_aktif_tidak_membuat_backup(sumber, tmp_path):
    def aktif():
        raise backup.Ditolak('writer aktif')
    with pytest.raises(backup.Ditolak, match='writer'):
        backup.capture(sumber, tmp_path / 'backup-uji', REV, IMAGE, aktif)
    assert not (tmp_path / 'backup-uji').exists()
    assert not list(tmp_path.glob('.partial-*'))


def test_writer_muncul_ulang_tidak_publikasi(sumber, tmp_path):
    n = []
    def check():
        n.append(1)
        if len(n) == 2:
            raise backup.Ditolak('writer muncul')
    with pytest.raises(backup.Ditolak, match='writer'):
        backup.capture(sumber, tmp_path / 'backup-uji', REV, IMAGE, check)
    assert not (tmp_path / 'backup-uji').exists()
    assert len(list(tmp_path.glob('.partial-*'))) == 1


@pytest.mark.parametrize('name', ('admin-control.db', 'sandi.json', 'riset-konsumen.db', 'lampiran'))
def test_state_wajib_hilang_tidak_sukses(sumber, tmp_path, name):
    p = sumber / name
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()
    with pytest.raises((OSError, backup.Ditolak)):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_lampiran_absent_sah_hanya_jika_tanpa_referensi(sumber, tmp_path):
    with sqlite3.connect(sumber / 'latihan.db') as c:
        c.execute('DELETE FROM lampiran')
    shutil.rmtree(sumber / 'lampiran')
    target = buat(sumber, tmp_path)
    assert backup.validate(target)['attachments'] == 0


@pytest.mark.parametrize('name', ('../escape.jpg', '/escape.jpg', 'sub/escape.jpg'))
def test_referensi_lampiran_tidak_aman_ditolak(sumber, tmp_path, name):
    with sqlite3.connect(sumber / 'latihan.db') as c:
        c.execute('UPDATE lampiran SET nama_berkas=?', (name,))
    with pytest.raises(backup.Ditolak, match='referensi'):
        buat(sumber, tmp_path)


def test_riset_schema_parsial_ditolak(sumber, tmp_path):
    (sumber / 'riset-konsumen.db').unlink()
    with sqlite3.connect(sumber / 'riset-konsumen.db') as c:
        c.execute('CREATE TABLE palsu(id INTEGER)')
    with pytest.raises((RuntimeError, ValueError)):
        buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()


def test_hash_berubah_dan_file_tambahan_ditolak(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    path = target / 'lampiran/1/acak.jpg'
    path.write_bytes(b'rusak')
    with pytest.raises(backup.Ditolak, match='hash'):
        backup.validate(target)
    path.write_bytes(b'foto sintetis')
    (target / 'sesi.json').write_text('{}')
    with pytest.raises(backup.Ditolak, match='inventaris'):
        backup.validate(target)


def test_no_overwrite_dan_symlink(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    before = backup.inventory(target)
    with pytest.raises(backup.Ditolak, match='output sudah'):
        backup.capture(sumber, target, REV, IMAGE, lambda: None)
    assert backup.inventory(target) == before
    p = sumber / 'lampiran/1/escape'
    p.symlink_to(sumber / 'sandi.json')
    with pytest.raises(backup.Ditolak, match='symlink'):
        backup.capture(sumber, tmp_path / 'backup-kedua', REV, IMAGE, lambda: None)
    assert not (tmp_path / 'backup-kedua').exists()


@pytest.mark.parametrize('name,kind', (('../escape','file'), ('/tmp/escape','file'), ('link','sym'), ('link','hard')))
def test_arsip_traversal_dan_link_ditolak(tmp_path, name, kind):
    archive = tmp_path / 'bad.tar'
    with tarfile.open(archive, 'w') as tf:
        item = tarfile.TarInfo(name)
        if kind != 'file':
            item.type = tarfile.SYMTYPE if kind == 'sym' else tarfile.LNKTYPE
            item.linkname = '../escape'
        tf.addfile(item)
    try:
        backup.unpack(archive, tmp_path / 'restored-uji')
    except (backup.Ditolak, OSError):
        pass
    else:
        pytest.fail('arsip tidak aman diterima')
    assert not (tmp_path / 'escape').exists(), 'traversal menulis di luar staging'
    assert not (tmp_path / 'restored-uji').exists()


def test_validator_tolak_referensi_hilang_meski_manifest_diperbarui(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    (target / 'lampiran/1/acak.jpg').unlink()
    m = backup.read_json(target / backup.MANIFEST)
    m['files'], m['directories'] = backup.inventory(target)
    (target / backup.MANIFEST).write_text(json.dumps(m))
    with pytest.raises(OSError):
        backup.validate(target)


def test_private_mode_ditolak(sumber, tmp_path):
    target = buat(sumber, tmp_path)
    (target / 'riset-separate.db').chmod(0o644)
    with pytest.raises(backup.Ditolak, match='privat'):
        backup.validate(target)


def test_ancestor_symlink_source_output_ditolak(sumber, tmp_path):
    alias = tmp_path / 'alias'
    alias.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(backup.Ditolak, match='ancestor symlink'):
        backup.capture(alias / sumber.name, tmp_path / 'backup-uji', REV, IMAGE, lambda: None)
    with pytest.raises(backup.Ditolak, match='ancestor symlink'):
        backup.capture(sumber, alias / 'backup-uji', REV, IMAGE, lambda: None)
    with pytest.raises(backup.Ditolak, match='ancestor symlink'):
        backup.fetch('backup-uji', 'host.invalid', alias / 'operasional')
    assert not (tmp_path / 'backup-uji').exists()


def test_ancestor_writable_asing_ditolak(sumber, tmp_path):
    parent = tmp_path / 'terbuka'
    parent.mkdir(mode=0o777)
    parent.chmod(0o777)
    private = parent / 'privat'
    private.mkdir(mode=0o700)
    with pytest.raises(backup.Ditolak, match='ancestor dapat ditulis'):
        backup.capture(sumber, private / 'backup-uji', REV, IMAGE, lambda: None)


def test_auth_lock_ditolak(sumber, tmp_path):
    import fcntl
    with (sumber / '.sandi.json.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            buat(sumber, tmp_path)
    assert not (tmp_path / 'backup-uji').exists()
