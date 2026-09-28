"""Operasi foto durable/kuota akun bersama dengan provider dan keluarga sintetis."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import re
import sqlite3
import threading
import urllib.error

import pytest

import admin_store
import attachments as foto
import assistant_entitlement_runtime as runtime
import assistant_quota_store as quota
import auth
import database
import llm
import schema
import sessions
import student_pages
import subscription as d
import subscription_package_store as paket
import subscription_store as v1
import teacher_pages

T0 = 1800000000
JPEG = b'\xff\xd8\xff\xe0foto-sintetis'
HASIL = [{'nomor': 1, 'jawaban': '12', 'caraku': 'contoh sintetis'}]
ON = d.Sakelar(True, True, True, False)


@pytest.fixture
def kasus(tmp_path, monkeypatch):
    monkeypatch.setenv('OSN_PBKDF2_ITERASI', '1000')
    monkeypatch.setattr(auth, 'BERKAS_SANDI', tmp_path/'sandi.json')
    auth.tambah_akun('orangtua', 'sandi-sintetis', 'guru')
    parent = sessions.principal_basic('orangtua', 'sandi-sintetis')
    auth.tambah_akun('muridsintetis', 'sandi-sintetis', 'murid')
    child = sessions.principal_basic('muridsintetis', 'sandi-sintetis')
    path = tmp_path/'belajar.db'
    monkeypatch.setattr(database, 'BAWAAN', path)
    monkeypatch.setenv('OSN_DIREKTORI_LAMPIRAN', str(tmp_path/'foto'))
    database.siapkan(path)
    database.migrasikan_operasi_foto(path)
    with database.buka(path) as kon:
        sid = database.tambah_siswa(kon, 'muridsintetis', pemilik='orangtua')
        sesi = database.buat_sesi(kon, sid, seed=31, jumlah_soal=1)
        sid2 = database.tambah_siswa(kon, 'profilsintetis2', pemilik='orangtua')
        sesi2 = database.buat_sesi(kon, sid2, seed=32, jumlah_soal=1)
    admin = tmp_path/'admin.db'
    admin_store.siapkan(admin, paket_v2=True)
    v1.enroll(admin, parent.id_akun, sumber_id='enroll_sintetis', asal='transisi', mulai=T0,
              peran='guru', sakelar=ON)
    paket.adopsi(admin, parent.id_akun, operasi_id='adopsi_sintetis', sekarang=T0, sakelar=ON)
    admin_store.migrasikan_kuota_pendamping(admin)
    monkeypatch.setattr(admin_store, 'BAWAAN', admin)
    monkeypatch.setattr(runtime, 'enforcement_aktif', lambda: True)
    return dict(path=path, parent=parent, child=child, sesi=sesi, sesi2=sesi2, sid=sid,
                admin=admin, root=tmp_path)


def tubuh(operasi, isi=JPEG):
    boundary='----SintetisFoto'
    parts=(f'--{boundary}\r\nContent-Disposition: form-data; name="operasi_foto"\r\n\r\n'
           f'{operasi}\r\n--{boundary}\r\nContent-Disposition: form-data; name="foto"; filename="uji.jpg"\r\n'
           'Content-Type: image/jpeg\r\n\r\n').encode()+isi+f'\r\n--{boundary}--\r\n'.encode()
    return 'multipart/form-data; boundary='+boundary,parts


def kirim(k, operasi='foto_'+'a'*32, *, sesi=None, principal=None, **kw):
    ct,body=tubuh(operasi)
    p=principal or k['parent']
    return foto.proses_foto_terjaga(k['path'], sesi or k['sesi'], principal=p,
        periksa_principal=lambda:p, content_type=ct, tubuh=body, sekarang=T0+2, **kw)


def pasang_provider(monkeypatch, fungsi=None):
    calls=[]
    def panggil(konteks,b64,*,sebelum_kirim):
        sebelum_kirim()
        calls.append(1)
        if fungsi:
            return fungsi()
        return llm.BacaanFoto('result', HASIL)
    monkeypatch.setattr(llm,'ekstrak_lembar_tercatat',panggil)
    return calls


def baris(path, tabel):
    with database.buka(path) as kon:
        return [dict(r) for r in kon.execute('SELECT * FROM '+tabel+' ORDER BY rowid')]


def test_migrasi_menolak_versi_belajar_tidak_dikenal(tmp_path):
    path=tmp_path/'belajar.db';database.siapkan(path)
    with database.buka(path) as kon:kon.execute('PRAGMA user_version=77')
    awal=path.read_bytes()
    with pytest.raises(ValueError,match='tidak dikenal'):database.migrasikan_operasi_foto(path)
    assert path.read_bytes()==awal


def test_migrasi_optin_idempotent_preservasi_dan_parsial(tmp_path):
    path=tmp_path/'belajar.db'
    with pytest.raises(sqlite3.OperationalError):database.migrasikan_operasi_foto(path)
    assert not path.exists()
    database.siapkan(path)
    with database.buka(path) as kon:
        assert not kon.execute("SELECT 1 FROM sqlite_master WHERE name='operasi_foto_baca'").fetchone()
        sid=database.tambah_siswa(kon,'sintetis',pemilik='guru')
        database.buat_sesi(kon,sid,seed=17,jumlah_soal=1)
    awal=baris(path,'sesi')
    database.migrasikan_operasi_foto(path);database.migrasikan_operasi_foto(path)
    assert baris(path,'sesi')==awal and baris(path,'operasi_foto_baca')==[]
    with database.buka(path) as kon:
        kon.execute('DROP TRIGGER operasi_foto_baca_ikat_update')
    with pytest.raises(ValueError,match='belum terverifikasi'):database.migrasikan_operasi_foto(path)


@pytest.mark.parametrize('peran',['parent','child'])
def test_foto_valid_commit_sebelum_finalisasi_parent_account(kasus,monkeypatch,peran):
    k=kasus;calls=[]
    def baca():
        with database.buka(k['path']) as kon:
            kon.execute('BEGIN IMMEDIATE')  # Bebas lock belajar saat provider berjalan.
            assert kon.execute("SELECT status FROM operasi_foto_baca").fetchone()[0]=='sent'
        rows=baris(k['admin'],'kuota_pendamping_operasi')
        assert len(rows)==1 and rows[0]['akun_id']==k['parent'].id_akun
        assert rows[0]['akun_id']!=k['child'].id_akun and rows[0]['status']=='reserved'
        return llm.BacaanFoto('result', HASIL)
    pasang_provider(monkeypatch,baca)
    asli=runtime.finalisasi
    def selesai(ikatan,*,sekarang,**kw):
        rows=baris(k['path'],'operasi_foto_baca')
        assert rows[0]['status']=='result'
        assert len(baris(k['path'],'lampiran'))==1
        calls.append(1)
        asli(ikatan,sekarang=sekarang,**kw)
    monkeypatch.setattr(runtime,'finalisasi',selesai)
    lid,pesan=kirim(k,principal=k[peran])
    assert lid and len(calls)==1
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='completed'
    if peran=='child':
        assert all(x not in pesan.lower() for x in ('kuota','paket','pro','trial','50','5'))


def test_reservasi_commit_lalu_adapter_gagal_release_exact_tanpa_provider(kasus,monkeypatch):
    k=kasus; calls=pasang_provider(monkeypatch)
    asli=runtime.reservasi
    def gagal(*a,**kw):
        asli(*a,**kw)
        raise runtime.GalatKuotaRuntime('adapter gagal setelah commit sintetis')
    monkeypatch.setattr(runtime,'reservasi',gagal)
    assert kirim(k)[0] is None
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='no_output'
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'
    assert kirim(k)[0] is None and calls==[]


def test_reservasi_lookup_gagal_dapat_dipulihkan_retry_exact(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    asli_reserve=runtime.reservasi;asli_lookup=quota.baca_operasi
    def gagal(*a,**kw):
        asli_reserve(*a,**kw)
        raise runtime.GalatKuotaRuntime('setelah commit')
    monkeypatch.setattr(runtime,'reservasi',gagal)
    monkeypatch.setattr(quota,'baca_operasi',lambda *a,**kw:(_ for _ in ()).throw(sqlite3.OperationalError('lookup sintetis')))
    with pytest.raises(sqlite3.OperationalError):kirim(k)
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='no_output'
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='reserved'
    monkeypatch.setattr(quota,'baca_operasi',asli_lookup)
    # Retry dengan sesi/content lain tidak boleh menggunakan receipt no_output.
    with pytest.raises(foto.KonflikFoto):kirim(k,sesi=k['sesi2'])
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='reserved'
    assert kirim(k)[0] is None and calls==[]
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'


@pytest.mark.parametrize('adapter_error',[False,True])
def test_callback_commit_sent_lalu_gagal_sebelum_transport_release(kasus,monkeypatch,adapter_error):
    k=kasus; calls=[]
    monkeypatch.setattr(llm,'konfigurasi_vision',lambda:dict(api_key='sintetis',base_url='https://example.invalid',model='sintetis'))
    monkeypatch.setattr(llm.ai_control,'panggil',lambda f,a,k:k())
    monkeypatch.setattr(llm.urllib.request,'urlopen',lambda *a,**kw:calls.append(1))
    if adapter_error:
        def adapter(f,a,k):
            try:k()
            except Exception:raise sqlite3.OperationalError('ledger biaya gagal sintetis') from None
        monkeypatch.setattr(llm.ai_control,'panggil',adapter)
    asli=llm.ekstrak_lembar_tercatat
    def baca(*a,sebelum_kirim):
        def callback():
            sebelum_kirim()
            raise RuntimeError('callback setelah commit sintetis')
        return asli(*a,sebelum_kirim=callback)
    monkeypatch.setattr(llm,'ekstrak_lembar_tercatat',baca)
    try:kirim(k)
    except RuntimeError:pass
    assert calls==[]
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='no_output'
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'


def test_cleanup_orphan_permission_error_tidak_menggagalkan_replay(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch,lambda:llm.BacaanFoto('unknown'))
    kirim(k)
    foto._file_baru_durable(k['sesi'],JPEG,'foto_'+'a'*32)
    def gagal(*a,**kw):raise PermissionError('cleanup sintetis')
    monkeypatch.setattr(Path,'unlink',gagal)
    assert kirim(k)[0] is None and calls==[1]
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='unknown'


def test_trigger_pointer_receipt_tolak_sesi_lain(kasus):
    k=kasus
    with database.buka(k['path']) as kon:
        lid=database.simpan_lampiran(kon,k['sesi2'],'sintetis.img')
        with pytest.raises(sqlite3.IntegrityError,match='pointer receipt foto'):
            kon.execute('INSERT INTO operasi_foto_baca VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('foto_'+'c'*32,k['parent'].id_akun,k['parent'].id_akun,k['sesi'],0,'upload',*(['a'*64]*4),'result',lid,T0,T0))


def test_cleanup_insert_gagal_tetap_release_saat_unlink_ditolak(kasus,monkeypatch):
    k=kasus;pasang_provider(monkeypatch)
    def insert_gagal(*a,**kw):raise sqlite3.OperationalError('insert sintetis')
    monkeypatch.setattr(database,'simpan_lampiran',insert_gagal)
    def unlink_gagal(*a,**kw):raise PermissionError('cleanup sintetis')
    with monkeypatch.context() as m:
        m.setattr(Path,'unlink',unlink_gagal)
        with pytest.raises(sqlite3.OperationalError,match='insert sintetis'):kirim(k)
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='no_output'
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'
    assert list((k['root']/'foto').rglob('*.img'))
    assert kirim(k)[0] is None
    assert not list((k['root']/'foto').rglob('*.img'))


@pytest.mark.parametrize('status',['result','no_output'])
@pytest.mark.parametrize('target',['hilang','sesi_lain'])
def test_semantik_pointer_receipt_harus_sesi_sama(kasus,status,target):
    k=kasus
    with database.buka(k['path']) as kon:
        lid=999 if target=='hilang' else database.simpan_lampiran(kon,k['sesi2'],'sintetis.img')
        # Matikan hanya trigger write untuk mensimulasikan restore rusak;
        # pembaca semantik tetap harus menolak dengan schema exact dipulihkan.
        triggers=list(kon.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='operasi_foto_baca'"))
        for nama,_ in triggers:kon.execute('DROP TRIGGER '+nama)
        kon.execute('INSERT INTO operasi_foto_baca VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            ('foto_'+'c'*32,k['parent'].id_akun,k['parent'].id_akun,k['sesi'],0,'upload',*(['a'*64]*4),status,lid,T0,T0))
        for _,ddl in triggers:kon.execute(ddl)
        with pytest.raises(ValueError,match='receipt foto'):database.validasi_operasi_foto(kon)


def test_sameop_replay_crash_finalisasi_tidak_provider_kedua(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    asli=runtime.finalisasi
    def gagal(*a,**kw):raise runtime.GalatKuotaRuntime('crash sintetis')
    monkeypatch.setattr(runtime,'finalisasi',gagal)
    with pytest.raises(runtime.GalatKuotaRuntime):kirim(k)
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='result'
    assert len(baris(k['path'],'lampiran'))==1
    monkeypatch.setattr(runtime,'finalisasi',asli)
    lid,_=kirim(k)
    assert lid and calls==[1] and len(baris(k['path'],'lampiran'))==1
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='completed'


def test_admission_habis_tertahan_sebelum_provider(kasus,monkeypatch):
    k=kasus;calls=[]
    def ditolak(*a,**kw):raise runtime.GalatKuotaRuntime('habis sintetis')
    monkeypatch.setattr(runtime,'reservasi',ditolak)
    def baca(*a,**kw):
        calls.append(1)
        return llm.BacaanFoto('unknown')
    monkeypatch.setattr(llm,'ekstrak_lembar_tercatat',baca)
    monkeypatch.setattr(runtime,'lepaskan',lambda *a,**kw:None)
    monkeypatch.setattr(runtime,'tandai_unknown',lambda *a,**kw:None)
    assert kirim(k)[0] is None
    assert calls==[]


def test_replay_tertahan_sebelum_reservasi_kedua(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    lid,_=kirim(k)
    reserves=[]
    def ditolak(*a,**kw):
        reserves.append(1)
        raise runtime.GalatKuotaRuntime('ulang tidak sah')
    monkeypatch.setattr(runtime,'reservasi',ditolak)
    try:
        hasil=kirim(k)
    except runtime.GalatKuotaRuntime:
        hasil=(None,'')
    assert reserves==[] and calls==[1]
    assert hasil[0]==lid


def test_admin_membaca_sesi_keluarga_memakai_kuota_parent(kasus,monkeypatch):
    k=kasus;auth.tambah_akun('adminsintetis','sandi-sintetis','admin')
    admin=sessions.principal_basic('adminsintetis','sandi-sintetis')
    calls=pasang_provider(monkeypatch)
    assert kirim(k,principal=admin)[0]
    assert calls==[1]
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['akun_id']==k['parent'].id_akun


def test_dua_profil_berbagi_kuota_dan_habis_zero_provider(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    assert kirim(k)[0]
    assert kirim(k,'foto_'+'b'*32,sesi=k['sesi2'])[0]
    assert kirim(k,'foto_'+'c'*32)[0] is None
    assert len(calls)==2
    assert len(baris(k['path'],'lampiran'))==2
    assert all(r['akun_id']==k['parent'].id_akun for r in baris(k['admin'],'kuota_pendamping_operasi'))


def test_nonce_multipart_ganda_atau_nonascii_ditolak():
    ct,body=tubuh('foto_'+'a'*32)
    field=b'Content-Disposition: form-data; name="operasi_foto"\r\n\r\n'
    assert foto.operasi_multipart(body,ct)=='foto_'+'a'*32
    extra=b'------SintetisFoto\r\n'+field+b'foto_'+b'b'*32+b'\r\n'
    with pytest.raises(foto.KonflikFoto):foto.operasi_multipart(extra+body,ct)
    with pytest.raises((foto.KonflikFoto,UnicodeError)):
        foto.operasi_multipart(body.replace(b'foto_'+b'a'*32,b'\xff'*37),ct)


def test_invalid_upload_nonce_foreign_tanpa_efek(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    ct,body=tubuh('foto_'+'a'*32,b'bukanfoto')
    assert foto.proses_foto_terjaga(k['path'],k['sesi'],principal=k['parent'],periksa_principal=lambda:k['parent'],content_type=ct,tubuh=body,sekarang=T0+2)[0] is None
    with pytest.raises(foto.KonflikFoto):kirim(k,'nonce_invalid')
    with pytest.raises(LookupError):kirim(k,sesi=k['sesi2'],principal=k['child'])
    assert calls==[] and baris(k['path'],'operasi_foto_baca')==[]
    assert baris(k['admin'],'kuota_pendamping_operasi')==[]


def test_dua_tab_operasi_sama_hanya_satu_provider(kasus,monkeypatch):
    k=kasus;mulai=threading.Event();lanjut=threading.Event()
    def baca():
        mulai.set();assert lanjut.wait(5)
        return llm.BacaanFoto('result',HASIL)
    calls=pasang_provider(monkeypatch,baca)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future=pool.submit(kirim,k)
        assert mulai.wait(5)
        assert kirim(k)[0] is None
        lanjut.set();assert future.result()[0]
    assert calls==[1] and len(baris(k['path'],'lampiran'))==1


def test_timeout_unknown_replay_tidak_provider(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch,lambda:llm.BacaanFoto('unknown'))
    assert kirim(k)[0] is None
    assert kirim(k)[0] is None and calls==[1]
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='unknown'
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='unknown'
    assert baris(k['path'],'lampiran')==[]
    assert not list((k['root']/'foto').rglob('*'))


@pytest.mark.parametrize('terkirim',[False,True])
def test_known_no_output_release_dan_replay_tetap_no_provider(kasus,monkeypatch,terkirim):
    k=kasus;calls=[]
    def baca(*a,sebelum_kirim):
        if terkirim:sebelum_kirim()
        calls.append(1)
        return llm.BacaanFoto('no_output')
    monkeypatch.setattr(llm,'ekstrak_lembar_tercatat',baca)
    lid,_=kirim(k)
    assert lid and calls==[1]
    assert baris(k['path'],'lampiran')[0]['hasil_json']==''
    assert kirim(k)[0]==lid and calls==[1]
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'


@pytest.mark.parametrize('ubah',['owner','generation','context'])
def test_final_fencing_owner_auth_context_tolak_hasil(kasus,monkeypatch,ubah):
    k=kasus
    def baca():
        if ubah=='generation':auth.naikkan_revisi_auth(k['parent'].id_akun)
        else:
            with database.buka(k['path']) as kon:
                if ubah=='owner':kon.execute("UPDATE siswa SET pemilik='lain' WHERE id=?",(k['sid'],))
                else:kon.execute("UPDATE sesi SET dibatalkan='sintetis' WHERE id=?",(k['sesi'],))
        return llm.BacaanFoto('result',HASIL)
    pasang_provider(monkeypatch,baca)
    with pytest.raises((LookupError,foto.KonflikFoto)):kirim(k)
    assert baris(k['path'],'lampiran')==[]
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'


def test_result_dto_invalid_tidak_menjadi_completed(kasus,monkeypatch):
    k=kasus;pasang_provider(monkeypatch,lambda:llm.BacaanFoto('result',[{'nomor':99,'jawaban':'','caraku':''}]))
    with pytest.raises(foto.KonflikFoto):kirim(k)
    assert baris(k['path'],'lampiran')==[]
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'


def test_insert_gagal_rollback_dan_file_created_dibersihkan(kasus,monkeypatch):
    k=kasus;pasang_provider(monkeypatch)
    monkeypatch.setattr(database,'simpan_lampiran',lambda *a,**kw:(_ for _ in ()).throw(sqlite3.OperationalError('sintetis')))
    with pytest.raises(sqlite3.OperationalError):kirim(k)
    assert baris(k['path'],'lampiran')==[]
    assert not [p for p in (k['root']/'foto').rglob('*') if p.is_file()]
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']=='released'


def ulang(k,lid,operasi):
    return foto.proses_foto_terjaga(k['path'],k['sesi'],principal=k['parent'],
        periksa_principal=lambda:k['parent'],target_id=lid,operasi_id=operasi,sekarang=T0+3)


def test_reread_nonce_baru_applied_tetap_replay_tidak_provider(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    lid,_=kirim(k)
    with database.buka(k['path']) as kon:database.tandai_lampiran(kon,lid,'diterapkan')
    assert ulang(k,lid,'foto_'+'b'*32)[0]==lid
    assert ulang(k,lid,'foto_'+'b'*32)[0]==lid
    assert calls==[1,1]
    assert baris(k['path'],'lampiran')[0]['status']=='diterapkan'


def test_reread_isi_berubah_setelah_claim_tidak_keluar_ke_provider(kasus,monkeypatch):
    k=kasus;pasang_provider(monkeypatch);lid,_=kirim(k)
    with database.buka(k['path']) as kon:
        nama=database.ambil_lampiran(kon,lid)['nama_berkas']
    asli=runtime.reservasi
    def berubah(*a,**kw):
        ikatan=asli(*a,**kw)
        (k['root']/'foto'/str(k['sesi'])/nama).write_bytes(JPEG+b'berubah')
        return ikatan
    monkeypatch.setattr(runtime,'reservasi',berubah)
    calls=pasang_provider(monkeypatch)
    with pytest.raises(foto.KonflikFoto):ulang(k,lid,'foto_'+'b'*32)
    assert calls==[]
    assert baris(k['admin'],'kuota_pendamping_operasi')[-1]['status']=='released'


def test_reread_fence_mencegah_late_result_menimpa_applied(kasus,monkeypatch):
    k=kasus;pasang_provider(monkeypatch);lid,_=kirim(k)
    def baca():
        with database.buka(k['path']) as kon:
            kon.execute("UPDATE lampiran SET hasil_json='manual-sintetis',status='diterapkan' WHERE id=?",(lid,))
        return llm.BacaanFoto('result',HASIL)
    pasang_provider(monkeypatch,baca)
    with pytest.raises(foto.KonflikFoto):ulang(k,lid,'foto_'+'b'*32)
    row=baris(k['path'],'lampiran')[0]
    assert row['hasil_json']=='manual-sintetis' and row['status']=='diterapkan'


def test_form_native_token_on_off_tidak_membocorkan_billing(kasus,monkeypatch):
    k=kasus
    with database.buka(k['path']) as kon:
        halaman=student_pages.halaman_kerja_baru(kon,k['sid'],k['sesi']).decode()
        guru=teacher_pages.halaman_sesi_lampiran(kon,k['sesi']).decode()
    for html in (halaman,guru):
        assert len(re.findall(r'name="operasi_foto" value="foto_[0-9a-f]{32}"',html))==1
    assert all(s not in halaman.split('</style>')[-1] for s in ('kuota_habis','jago_pro','trial_aktif'))
    monkeypatch.setattr(runtime,'enforcement_aktif',lambda:False)
    assert foto.field_operasi_foto()==''


def test_upload_nonce_beda_binding_tidak_meminjam_hasil(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    kirim(k)
    with pytest.raises(foto.KonflikFoto):kirim(k,sesi=k['sesi2'])
    ct,body=tubuh('foto_'+'a'*32,JPEG+b'beda')
    with pytest.raises(foto.KonflikFoto):
        foto.proses_foto_terjaga(k['path'],k['sesi'],principal=k['parent'],periksa_principal=lambda:k['parent'],content_type=ct,tubuh=body,sekarang=T0+2)
    assert calls==[1]


def test_dua_reread_aktif_satu_lampiran_ditolak_tanpa_reserve(kasus,monkeypatch):
    k=kasus;pasang_provider(monkeypatch);lid,_=kirim(k)
    ready=threading.Event();lanjut=threading.Event()
    def baca():
        ready.set();assert lanjut.wait(5)
        return llm.BacaanFoto('result',HASIL)
    calls=pasang_provider(monkeypatch,baca)
    with ThreadPoolExecutor(max_workers=2) as pool:
        future=pool.submit(ulang,k,lid,'foto_'+'b'*32)
        assert ready.wait(5)
        with pytest.raises(foto.KonflikFoto):ulang(k,lid,'foto_'+'c'*32)
        lanjut.set();assert future.result()[0]==lid
    assert calls==[1] and len(baris(k['admin'],'kuota_pendamping_operasi'))==2


def test_parent_hilang_failclosed_sebelum_reserve(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch)
    with database.buka(k['path']) as kon:kon.execute("UPDATE siswa SET pemilik='akun-tidak-ada' WHERE id=?",(k['sid'],))
    with pytest.raises(foto.KonflikFoto):kirim(k,principal=k['child'])
    assert calls==[] and baris(k['admin'],'kuota_pendamping_operasi')==[]


def test_result_lampiran_hilang_tidak_diciptakan_ulang(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch);lid,_=kirim(k)
    with database.buka(k['path']) as kon:
        kon.execute('DELETE FROM lampiran WHERE id=?',(lid,))
    assert kirim(k)[0] is None
    assert calls==[1] and len(baris(k['path'],'operasi_foto_baca'))==1
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='deleted_result'
    with database.buka(k['path']) as kon:database.validasi_operasi_foto(kon)


def test_unknown_atau_result_receipt_tidak_dihapus_bersama_session(kasus,monkeypatch):
    k=kasus;pasang_provider(monkeypatch);kirim(k)
    with database.buka(k['path']) as kon:
        for sql in ('DELETE FROM operasi_foto_baca',"UPDATE operasi_foto_baca SET status='reserved'",
                    'INSERT OR REPLACE INTO operasi_foto_baca SELECT * FROM operasi_foto_baca'):
            with pytest.raises(sqlite3.IntegrityError):kon.execute(sql)
    assert baris(k['path'],'operasi_foto_baca')[0]['status']=='result'


def test_retry_membersihkan_orphan_crash_attempt_sendiri_saja(kasus,monkeypatch):
    k=kasus;calls=pasang_provider(monkeypatch,lambda:llm.BacaanFoto('unknown'))
    assert kirim(k)[0] is None
    oid='foto_'+'a'*32
    nama=foto._file_baru_durable(k['sesi'],JPEG,oid)
    lain=k['root']/'foto'/str(k['sesi'])/'foto-lain.img'
    lain.write_bytes(JPEG)
    assert kirim(k)[0] is None and calls==[1]
    assert not (k['root']/'foto'/str(k['sesi'])/nama).exists() and lain.exists()


def test_file_attempt_o_excl_tidak_menghapus_file_existing(kasus):
    k=kasus;oid='foto_'+'a'*32
    nama=foto._file_baru_durable(k['sesi'],JPEG,oid)
    with pytest.raises(FileExistsError):foto._file_baru_durable(k['sesi'],b'lain',oid)
    assert (k['root']/'foto'/str(k['sesi'])/nama).read_bytes()==JPEG


@pytest.mark.parametrize('respons,status',[
    (json.dumps({'soal':HASIL}),'completed'),('bukan-json','released'),(None,'unknown')])
def test_transport_vision_nyata_sintetis_sampai_receipt(kasus,monkeypatch,respons,status):
    k=kasus;calls=[]
    monkeypatch.setattr(llm,'konfigurasi_vision',lambda:{'api_key':'sintetis','base_url':'https://example.invalid','model':'sintetis'})
    monkeypatch.setattr(llm.ai_control,'panggil',lambda fitur,akun,kirim:kirim())
    class Balasan:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'choices':[{'message':{'content':respons}}]}).encode()
    def jaringan(*a,**kw):
        calls.append(1)
        with database.buka(k['path']) as kon:
            kon.execute('BEGIN IMMEDIATE')
            assert kon.execute('SELECT status FROM operasi_foto_baca').fetchone()[0]=='sent'
        if respons is None:raise urllib.error.URLError('timeout sintetis')
        return Balasan()
    monkeypatch.setattr(llm.urllib.request,'urlopen',jaringan)
    lid,_=kirim(k)
    assert calls==[1]
    assert (lid is None)==(status=='unknown')
    assert baris(k['admin'],'kuota_pendamping_operasi')[0]['status']==status


def test_vision_milestone_preflight_timeout_parse_valid(monkeypatch):
    cfg={'api_key':'sintetis','base_url':'https://example.invalid','model':'sintetis'}
    monkeypatch.setattr(llm,'konfigurasi_vision',lambda:cfg)
    calls=[]
    monkeypatch.setattr(llm.ai_control,'panggil',lambda f,a,k:k())
    def timeout(*a,**kw):raise urllib.error.URLError('timeout sintetis')
    monkeypatch.setattr(llm.urllib.request,'urlopen',timeout)
    r=llm.ekstrak_lembar_tercatat(['soal'],'eA==',sebelum_kirim=lambda:calls.append(1))
    assert r.status=='unknown' and calls==[1]
    cfg['api_key']=''
    assert llm.ekstrak_lembar_tercatat(['soal'],'eA==').status=='no_output'
    cfg['api_key']='sintetis'
    monkeypatch.setattr(llm.ai_control,'panggil',lambda *a:'tidak json')
    assert llm.ekstrak_lembar_tercatat(['soal'],'eA==').status=='no_output'
