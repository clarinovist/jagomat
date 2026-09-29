"""Backup/rehearsal registrasi profil, fixture sintetis tanpa layanan jaringan."""
import json
import sqlite3
from pathlib import Path

import pytest
import admin_backup as backup
import admin_registration as reg
import ai_store
import auth
import database
from test_admin_backup import _buat_bundle


def buat(tmp_path, status='selesai', *, profil_parameter='P4'):
    bundle=_buat_bundle(tmp_path)
    pd=bundle/'latihan.db';pa=bundle/'admin-control.db';ph=bundle/'sandi.json'
    reg.migrasikan_profil_registrasi(pd)
    kw=dict(operasi_id='register_lifecycle_01',alias='ortu-lifecycle',sandi='sandi-lifecycle-sintetis',
            token_form='x'*64,nama_anak='Profil Sintetis',kelas_sekolah=4,profil_parameter=profil_parameter,sekarang=10)
    if status=='selesai':reg.daftar_dengan_profil(pa,ph,pd,**kw)
    else:
        with pytest.raises(reg.RegistrasiBelumSelesai):
            reg.daftar_dengan_profil(pa,ph,pd,**kw,failpoint=status)
    manifest(bundle)
    return bundle,kw


def manifest(bundle):
    (bundle/'manifest.json').unlink(missing_ok=True)
    # Hanya lock fixture; bundle backup kanonis tidak membawa state transient.
    for name in ('.admin-registration.lock','.sandi.json.lock'):
        (bundle/name).unlink(missing_ok=True)
    backup.buat_manifest(bundle,bundle_id='registrasi-sintetis',cutoff=100)


@pytest.mark.parametrize('titik',['setelah_intent','setelah_db','selesai'])
def test_backup_registrasi_terkait_dan_pending(tmp_path,titik):
    b,_=buat(tmp_path,titik);awal={p.name:p.read_bytes() for p in b.iterdir()}
    hasil=backup.validasi_bundle(b)
    assert hasil.skema_registrasi_profil
    assert hasil.operasi_registrasi_profil_pending==(0 if titik=='selesai' else 1)
    assert hasil.perlu_rekonsiliasi==(titik!='selesai')
    assert awal=={p.name:p.read_bytes() for p in b.iterdir()}


@pytest.mark.parametrize('titik', ['setelah_intent', 'setelah_db', 'selesai'])
def test_backup_rehearsal_profil_belum_dipilih(tmp_path, titik):
    bundle, kw = buat(tmp_path, titik, profil_parameter=None)
    awal = {p.name: p.read_bytes() for p in bundle.iterdir()}
    hasil = backup.rehearsal_bundle(bundle, migrator_ai=ai_store.siapkan, target_registrasi=True)
    assert hasil.operasi_registrasi_profil_pending == (0 if titik == 'selesai' else 1)
    assert awal == {p.name: p.read_bytes() for p in bundle.iterdir()}
    reg.daftar_dengan_profil(bundle / 'admin-control.db', bundle / 'sandi.json', bundle / 'latihan.db', **kw)
    with database.buka(bundle / 'latihan.db') as kon:
        baris = kon.execute('SELECT tingkat FROM siswa WHERE pemilik=?', (kw['alias'],)).fetchone()
        assert baris[0] == ''
        assert not kon.execute('PRAGMA foreign_key_check').fetchone()


@pytest.mark.parametrize('rusak',['tanpa_schema','tanpa_intent','public_account','public_hash','public_target',
    'account_hilang','account_role','owner','db_binding','pending_account','pending_public','duplikat_intent','profil_hilang'])
def test_backup_tolak_pasangan_registrasi_rusak(tmp_path,rusak):
    b,kw=buat(tmp_path,'setelah_db' if rusak.startswith('pending') else 'selesai')
    ph=b/'sandi.json';data=json.loads(ph.read_text());item=data['registrasi_profil'][kw['operasi_id']]
    if rusak=='tanpa_intent':data['registrasi_profil']={}
    elif rusak=='public_account':data['operasi_registrasi'][kw['operasi_id']]['hasil_id']='akun_'+'e'*32
    elif rusak=='public_hash':data['operasi_registrasi'][kw['operasi_id']]['sidik_perintah']='f'*64
    elif rusak=='public_target':data['operasi_registrasi'][kw['operasi_id']]['target_id']='candidate_'+'e'*32
    elif rusak=='account_hilang':data['akun']=[a for a in data['akun'] if a['id_akun']!=item['akun_id']]
    elif rusak=='account_role':next(a for a in data['akun'] if a['id_akun']==item['akun_id'])['peran']='admin'
    elif rusak=='pending_account':data['akun'].append(dict(pengguna=kw['alias'],peran='guru',id_akun=item['akun_id'],revisi_auth=1,**auth.buat_hash('sandi-sintetis')))
    elif rusak=='pending_public':data['operasi_registrasi']={kw['operasi_id']:dict(versi=1,operasi_id=kw['operasi_id'],target_id=item['target_id'],hasil_id=item['akun_id'],hasil_kode='teacher_created',revisi_hasil=1,dibuat=10,sidik_perintah=item['sidik_perintah'])}
    elif rusak=='duplikat_intent':data['registrasi_profil']['register_lifecycle_02']=dict(item)
    ph.write_text(json.dumps(data))
    with database.buka(b/'latihan.db') as kon:
        if rusak=='tanpa_schema':kon.execute('DROP TABLE registrasi_profil_anak')
        elif rusak=='profil_hilang':kon.execute('DELETE FROM siswa WHERE id=?',(item['siswa_id'],))
        elif rusak=='owner':kon.execute("UPDATE siswa SET pemilik='asing' WHERE id=?",(item['siswa_id'],))
        elif rusak=='db_binding':
            ddl=kon.execute("SELECT sql FROM sqlite_master WHERE name='registrasi_profil_anak_tolak_update'").fetchone()[0]
            kon.execute('DROP TRIGGER registrasi_profil_anak_tolak_update')
            kon.execute("UPDATE registrasi_profil_anak SET sidik_perintah=?",('f'*64,))
            kon.execute(ddl)
    manifest(b)
    with pytest.raises(backup.BackupTidakSah,match='registrasi'):backup.validasi_bundle(b)


def test_rehearsal_target_registrasi_optin_preservasi(tmp_path):
    b,_=buat(tmp_path,'setelah_db');awal={p.name:p.read_bytes() for p in b.iterdir()}
    r=backup.rehearsal_bundle(b,migrator_ai=ai_store.siapkan,target_registrasi=True)
    assert r.skema_registrasi_profil and r.operasi_registrasi_profil_pending==1 and r.perlu_rekonsiliasi
    assert awal=={p.name:p.read_bytes() for p in b.iterdir()}


def test_rehearsal_migrasi_registrasi_hanya_turunan(tmp_path):
    b=_buat_bundle(tmp_path);awal=(b/'latihan.db').read_bytes()
    assert not backup.rehearsal_bundle(b,migrator_ai=ai_store.siapkan).skema_registrasi_profil
    akhir=backup.rehearsal_bundle(b,migrator_ai=ai_store.siapkan,target_registrasi=True)
    assert akhir.skema_registrasi_profil and not akhir.perlu_rekonsiliasi
    assert (b/'latihan.db').read_bytes()==awal


def test_pending_pracommit_id_terpakai_keluarga_lain_tetap_sah(tmp_path):
    b,_=buat(tmp_path,'setelah_intent')
    with database.buka(b/'latihan.db') as c:database.tambah_siswa(c,'Profil Asing',pemilik='keluarga')
    manifest(b)
    assert backup.validasi_bundle(b).operasi_registrasi_profil_pending==1


def test_pending_pracommit_profile_alias_sama_tanpa_receipt_ditolak(tmp_path):
    b,kw=buat(tmp_path,'setelah_intent')
    with database.buka(b/'latihan.db') as c:database.tambah_siswa(c,'Profil Asing',pemilik=kw['alias'])
    manifest(b)
    with pytest.raises(backup.BackupTidakSah,match='registrasi'):backup.validasi_bundle(b)


def test_rehearsal_menolak_pengubahan_intent_auth(tmp_path,monkeypatch):
    b,_=buat(tmp_path,'setelah_db')
    asli=reg.migrasikan_profil_registrasi
    def rusak(path):
        asli(path)
        ph=Path(path).parent/'sandi.json';data=json.loads(ph.read_text())
        next(iter(data['registrasi_profil'].values()))['kredensial']['iterasi']+=1
        ph.write_text(json.dumps(data))
    monkeypatch.setattr(reg,'migrasikan_profil_registrasi',rusak)
    with pytest.raises(backup.BackupTidakSah,match='auth berubah'):
        backup.rehearsal_bundle(b,migrator_ai=ai_store.siapkan,target_registrasi=True)
    monkeypatch.setattr(reg,'migrasikan_profil_registrasi',asli)
    assert backup.rehearsal_bundle(b,migrator_ai=ai_store.siapkan).operasi_registrasi_profil_pending==1


def test_backup_reset_sandi_dan_kelas_bukan_kerusakan_histori(tmp_path):
    b,kw=buat(tmp_path)
    auth.simpan_sandi('sandi-baru-sintetis',kw['alias'],b/'sandi.json')
    with database.buka(b/'latihan.db') as kon:
        kon.execute("UPDATE siswa SET nama='Nama Berubah',tingkat='P5'")
        kon.execute('UPDATE profil_belajar SET kelas_sekolah=5,revisi=revisi+1')
    manifest(b)
    assert backup.validasi_bundle(b).skema_registrasi_profil
