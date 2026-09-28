"""Backup/rehearsal/pair foto sintetis; tidak mengklaim image exact sudah ada."""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest
import admin_backup
import ai_store
import database
from test_admin_backup import _buat_bundle
from test_quota_release_pair import siapkan, recovery9
from test_package_release_pair import jalankan

AKAR=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(AKAR/'scripts'))
import deploy
import release_quota_pair as pair
import verify_release_image


def seed(path):
    database.migrasikan_operasi_foto(path)
    with database.buka(path) as kon:
        sid=database.tambah_siswa(kon,'profil-sintetis',pemilik='keluarga')
        sesi=database.buat_sesi(kon,sid,seed=62,jumlah_soal=1)
        lid=database.simpan_lampiran(kon,sesi,'sintetis.img')
        for n,status in enumerate(('reserved','sent','unknown','result','no_output'),1):
            oid='foto_'+format(n,'032x')
            kon.execute('INSERT INTO operasi_foto_baca VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)',
                (oid,'akun_'+'b'*32,'akun_'+'b'*32,sesi,0,'upload',*(['a'*64]*4),'reserved',1,1))
            if status in ('sent','unknown','result'):
                kon.execute("UPDATE operasi_foto_baca SET status='sent' WHERE operasi_id=?",(oid,))
            if status in ('unknown','result','no_output'):
                kon.execute('UPDATE operasi_foto_baca SET status=?,hasil_id=? WHERE operasi_id=?',
                            (status,lid if status in ('result','no_output') else None,oid))
    return sesi,lid


def manifest(bundle):
    (bundle/'manifest.json').unlink()
    admin_backup.buat_manifest(bundle,bundle_id='foto-sintetis',cutoff=100)


def test_backup_pending_foto_dan_rehearsal_preservasi(tmp_path):
    bundle=_buat_bundle(tmp_path);seed(bundle/'latihan.db');manifest(bundle)
    awal={p.name:p.read_bytes() for p in bundle.iterdir()}
    hasil=admin_backup.validasi_bundle(bundle)
    assert hasil.skema_foto and hasil.operasi_foto_pending==2 and hasil.operasi_foto_unknown==1
    assert hasil.perlu_rekonsiliasi
    akhir=admin_backup.rehearsal_bundle(bundle,migrator_ai=ai_store.siapkan)
    assert akhir==hasil
    assert awal=={p.name:p.read_bytes() for p in bundle.iterdir()}


def test_mutasi_backup_pending_foto_merah_pulih(tmp_path):
    bundle=_buat_bundle(tmp_path);seed(bundle/'latihan.db');manifest(bundle)
    source=tmp_path/'source';source.mkdir()
    for p in (AKAR/'mesin').glob('*.py'):shutil.copy2(p,source/p.name)
    target=source/'admin_backup.py';asli=target.read_text()
    guard='or bool(foto_pending or foto_unknown)'
    assert asli.count(guard)==1
    target.write_text(asli.replace(guard,'or False'))
    code='import sys\nsys.path.insert(0,'+repr(str(source))+')\nimport admin_backup\nassert admin_backup.validasi_bundle('+repr(str(bundle))+').perlu_rekonsiliasi, "pending_foto_tidak_ditandai"'
    def run():return subprocess.run([sys.executable,'-E','-B','-c',code],cwd=tmp_path,capture_output=True,text=True,timeout=20)
    merah=run();assert merah.returncode==1 and 'AssertionError: pending_foto_tidak_ditandai' in merah.stderr
    target.write_text(asli)
    hijau=run();assert hijau.returncode==0,hijau.stderr


def test_rehearsal_foto_optin_tidak_menulis_induk(tmp_path):
    bundle=_buat_bundle(tmp_path);awal=(bundle/'latihan.db').read_bytes()
    assert not admin_backup.validasi_bundle(bundle).skema_foto
    assert not admin_backup.rehearsal_bundle(bundle,migrator_ai=ai_store.siapkan).skema_foto
    hasil=admin_backup.rehearsal_bundle(bundle,migrator_ai=ai_store.siapkan,target_foto=True)
    assert hasil.skema_foto and not hasil.perlu_rekonsiliasi
    assert (bundle/'latihan.db').read_bytes()==awal


@pytest.mark.parametrize('rusak',['schema','pointer'])
def test_backup_tolak_schema_pointer_foto_rusak(tmp_path,rusak):
    bundle=_buat_bundle(tmp_path);_,lid=seed(bundle/'latihan.db')
    with database.buka(bundle/'latihan.db') as kon:
        if rusak=='schema':kon.execute('DROP TRIGGER operasi_foto_baca_ikat_update')
        else:
            ddl=kon.execute("SELECT sql FROM sqlite_master WHERE name='operasi_foto_lampiran_hapus'").fetchone()[0]
            kon.execute('DROP TRIGGER operasi_foto_lampiran_hapus')
            kon.execute('DELETE FROM lampiran WHERE id=?',(lid,));kon.execute(ddl)
    manifest(bundle)
    with pytest.raises(admin_backup.BackupTidakSah,match='foto'):admin_backup.validasi_bundle(bundle)


def test_hapus_session_tombstone_tetap_valid(tmp_path):
    path=tmp_path/'db';database.siapkan(path);sesi,_=seed(path)
    with database.buka(path) as kon:
        assert database.hapus_sesi(kon,sesi)
        database.validasi_operasi_foto(kon)
        states=[r[0] for r in kon.execute('SELECT status FROM operasi_foto_baca ORDER BY operasi_id')]
        assert states==['reserved','sent','unknown','deleted_result','deleted_no_output']


def test_rehearsal_menolak_row_foto_berubah_meski_pending_sama(tmp_path,monkeypatch):
    bundle=_buat_bundle(tmp_path);seed(bundle/'latihan.db');manifest(bundle)
    asli=database.migrasikan_operasi_foto
    def rusak(path):
        asli(path)
        with database.buka(path) as kon:
            ddl=kon.execute("SELECT sql FROM sqlite_master WHERE name='operasi_foto_baca_ikat_update'").fetchone()[0]
            kon.execute('DROP TRIGGER operasi_foto_baca_ikat_update')
            kon.execute("UPDATE operasi_foto_baca SET fence=?",('b'*64,))
            kon.execute(ddl)
    monkeypatch.setattr(database,'migrasikan_operasi_foto',rusak)
    with pytest.raises(admin_backup.BackupTidakSah,match='state belajar berubah'):
        admin_backup.rehearsal_bundle(bundle,migrator_ai=ai_store.siapkan)
    monkeypatch.setattr(database,'migrasikan_operasi_foto',asli)
    assert admin_backup.rehearsal_bundle(bundle,migrator_ai=ai_store.siapkan).operasi_foto_pending==2


def test_pair_foto_source_turunan_candidate_recovery_candidate(tmp_path):
    siapkan(tmp_path)
    sumber=tmp_path/'reader';sumber.mkdir()
    for p in (AKAR/'mesin').glob('*.py'):shutil.copy2(p,sumber/p.name)
    for src,kode in ((AKAR/'mesin',pair.SUMBER_TULIS),(sumber,pair.SUMBER_BACA),(AKAR/'mesin',pair.SUMBER_KEMBALI)):
        hasil=jalankan(src,kode,tmp_path)
        assert hasil.returncode==0,hasil.stderr
    meta=json.loads((tmp_path/'package-pair'/'foto-recovery.json').read_text())
    assert len(meta['belajar']['operasi_foto_baca'])==5


def test_pair_foto_recovery_admin9_historical_ditolak(tmp_path,recovery9):
    siapkan(tmp_path,recovery9)
    hasil=jalankan(AKAR/'mesin',pair.SUMBER_TULIS,tmp_path)
    assert hasil.returncode==0,hasil.stderr
    hasil=jalankan(recovery9,pair.SUMBER_BACA,tmp_path)
    assert hasil.returncode!=0 and 'migrasikan_operasi_foto' in hasil.stderr
    assert verify_release_image.ringkasan_untuk_revision('d973bf8dc329374fc24e928a87f56e7a088ac623')['photo_checks']==0
    assert verify_release_image.ringkasan_untuk_revision('b'*40)['photo_checks']==8


def test_probe_readonly_foto_exact_dan_pointer(tmp_path):
    path=tmp_path/'latihan.db';database.siapkan(path)
    code='akar_app=Path('+repr(str(AKAR/'mesin'))+')\n'+deploy.PROBE_FOTO_SKEMA.replace('/data/',str(tmp_path)+'/')
    exec(code,{'sqlite3':sqlite3,'Path':Path})  # Legacy OFF boleh tanpa DDL.
    seed(path);awal=path.read_bytes()
    exec(code,{'sqlite3':sqlite3,'Path':Path})
    assert path.read_bytes()==awal
    with database.buka(path) as kon:kon.execute('DROP TRIGGER operasi_foto_baca_ikat_update')
    with pytest.raises(AssertionError,match='schema_foto_parsial'):exec(code,{'sqlite3':sqlite3,'Path':Path})
    # Mutation guard readiness yang sama: bypass exact menerima DDL rusak.
    guard="assert aktual_foto==struktur_foto(acuan), 'schema_foto_parsial'"
    assert code.count(guard)==1
    exec(code.replace(guard,'pass'),{'sqlite3':sqlite3,'Path':Path})
    with pytest.raises(AssertionError,match='schema_foto_parsial'):exec(code,{'sqlite3':sqlite3,'Path':Path})


def test_mutasi_recovery_foto_pending_ditangkap_pair_pulih(tmp_path):
    siapkan(tmp_path)
    assert jalankan(AKAR/'mesin',pair.SUMBER_TULIS,tmp_path).returncode==0
    source=tmp_path/'reader';source.mkdir()
    for p in (AKAR/'mesin').glob('*.py'):shutil.copy2(p,source/p.name)
    target=source/'database.py';asli=target.read_text()
    old='        validasi_operasi_foto(kon)\n        if kon.execute'
    assert asli.count(old)==1
    target.write_text(asli.replace(old,"        kon.execute(\"UPDATE operasi_foto_baca SET status='no_output' WHERE status='reserved'\")\n"+old))
    mutan=tmp_path/'mutan';mutan.mkdir();shutil.copytree(tmp_path/'package-pair',mutan/'package-pair')
    merah=jalankan(source,pair.SUMBER_BACA,mutan)
    assert merah.returncode!=0 and 'AssertionError' in merah.stderr
    target.write_text(asli)
    hijau=jalankan(source,pair.SUMBER_BACA,tmp_path)
    assert hijau.returncode==0,hijau.stderr
