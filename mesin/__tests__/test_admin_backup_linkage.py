"""Pasangan backup sintetis tidak menganggap journal sukses tanpa receipt aman."""
import json
import pytest
import admin_backup
import admin_service
import admin_contracts as c
from test_admin_backup import _buat_bundle, ACTOR, OWNER


def _manifest_ulang(bundle):
    (bundle/'manifest.json').unlink()
    for p in bundle.glob('.*.lock'):p.unlink()
    admin_backup.buat_manifest(bundle,bundle_id='uji-linkage',cutoff=100)


def test_sukses_auth_receipt_pasangan_hilang_ditolak(tmp_path):
    bundle=_buat_bundle(tmp_path)
    cmd=c.PerintahAkun('op_'+'a'*32,ACTOR,3,c.AKSI_CABUT_SESI,OWNER,1,'guru','t'*48)
    admin_service.jalankan(bundle/'admin-control.db',bundle/'sandi.json',cmd)
    _manifest_ulang(bundle)
    assert not admin_backup.validasi_bundle(bundle).perlu_rekonsiliasi
    raw=json.loads((bundle/'sandi.json').read_text());raw['operasi_admin']={}
    (bundle/'sandi.json').write_text(json.dumps(raw))
    _manifest_ulang(bundle)
    with pytest.raises(admin_backup.BackupTidakSah,match='pasangan'):
        admin_backup.validasi_bundle(bundle)


def test_pending_sesudah_auth_commit_wajib_rekonsiliasi(tmp_path):
    bundle=_buat_bundle(tmp_path)
    cmd=c.PerintahAkun('op_'+'b'*32,ACTOR,3,c.AKSI_CABUT_SESI,OWNER,1,'guru','t'*48)
    with pytest.raises(admin_service.CrashSebelumFinalisasi):
        admin_service.jalankan(bundle/'admin-control.db',bundle/'sandi.json',cmd,failpoint='sebelum_finalize')
    _manifest_ulang(bundle)
    hasil=admin_backup.validasi_bundle(bundle)
    assert hasil.perlu_rekonsiliasi and hasil.operasi_admin_pending==1


def test_saga_siswa_sukses_tetapi_auth_sebelum_delete_ditolak(tmp_path):
    import auth
    import database
    bundle=_buat_bundle(tmp_path)
    with database.buka(bundle/'latihan.db') as kon:
        sid=database.tambah_siswa(kon,'Sintetis Saga','P3',pemilik='keluarga')
    auth.tambah_akun('saga-login','sandi-saga-sintetis','murid',bundle/'sandi.json',siswa_id=sid)
    login=auth.cari_akun('saga-login',bundle/'sandi.json')
    old=(bundle/'sandi.json').read_bytes()
    cmd=c.PerintahHapusSiswa('op_'+'c'*32,ACTOR,3,c.AKSI_HAPUS_SISWA,sid,'P3',login['id_akun'],1,'t'*48)
    assert admin_service.hapus_siswa(bundle/'admin-control.db',bundle/'sandi.json',bundle/'latihan.db',cmd).hasil.status=='succeeded'
    _manifest_ulang(bundle)
    assert not admin_backup.validasi_bundle(bundle).perlu_rekonsiliasi
    (bundle/'sandi.json').write_bytes(old);_manifest_ulang(bundle)
    with pytest.raises(admin_backup.BackupTidakSah,match='pasangan'):
        admin_backup.validasi_bundle(bundle)


def test_schema4_tanpa_tabel_batch_ditolak(tmp_path):
    import sqlite3
    bundle=_buat_bundle(tmp_path)
    with sqlite3.connect(bundle/'admin-control.db') as kon:
        for nama in ('penyerahan_admin_item','penyerahan_admin','kelompok_admin_item','kelompok_admin','batch_admin_item','batch_admin'):
            kon.execute('DROP TABLE '+nama)
    _manifest_ulang(bundle)
    with pytest.raises(admin_backup.BackupTidakSah,match='schema'):
        admin_backup.validasi_bundle(bundle)


def test_role_auth_cacat_ditolak_walau_hash_manifest_cocok(tmp_path):
    bundle=_buat_bundle(tmp_path);p=bundle/'sandi.json';data=json.loads(p.read_text());data['akun'][0]['peran']='asing';p.write_text(json.dumps(data));_manifest_ulang(bundle)
    with pytest.raises(admin_backup.BackupTidakSah):admin_backup.validasi_bundle(bundle)
