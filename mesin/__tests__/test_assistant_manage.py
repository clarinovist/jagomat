"""Kendali chat/izin lokal tanpa provider; fixture sintetis saja."""
import re

import pytest

import assistant_manage as manage
import assistant_policy as policy
import assistant_schema as schema
import assistant_service as service
import assistant_store as store
import auth
import database
import sessions
from http_test_kit import ServerUji, SANDI_GURU
from test_assistant_runtime import _token_guru, ProviderPalsu


@pytest.fixture()
def server(tmp_path, monkeypatch, request):
    monkeypatch.setenv('PENDAMPING_AKTIF', '0')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.setattr(schema, 'BAWAAN', tmp_path/'pendamping.db')
    s = ServerUji(tmp_path, monkeypatch)
    request.addfinalizer(s.berhenti)
    s.token = _token_guru(s)
    s.akun = auth.cari_akun('guru')['id_akun']
    schema.siapkan()
    with s.buka() as data:
        anak = database.tambah_siswa(data, 'Anak Sintetis', pemilik='guru')
        asing = database.tambah_siswa(data, 'Sumber Asing', pemilik='lain')
    with schema.buka() as kon:
        for _ in range(2):
            store.beri_persetujuan(kon,s.akun,policy_version=policy.VERSI_KEBIJAKAN,provider_id='deepseek',kategori='chat_umum',sekarang=100)
        konteks = store.beri_persetujuan_konteks(kon,s.akun,jenis='anak',resource_id=str(anak),resource_version='snapshot',kategori='ringkasan_netral',sekarang=100)
        s.chat = store.buat_chat(kon,s.akun,'aktif',sekarang=101,context_kind='anak',context_id=str(anak),context_version=konteks.versi,context_resource_version='snapshot',context_category='ringkasan_netral')
        store.tambah_pesan(kon,s.akun,s.chat.id,'pengguna','Isi privat sintetis jangan tampilkan.',request_id='req_awal',sekarang=102)
        s.umum=store.buat_chat(kon,s.akun,'aktif',sekarang=100)
        s.foreign=store.buat_chat(kon,'akun_'+'b'*32,'aktif',sekarang=100)
        izin_asing=store.beri_persetujuan_konteks(kon,s.akun,jenis='anak',resource_id=str(asing),resource_version='snapshot',kategori='ringkasan_netral',sekarang=100)
        s.sumber_asing=store.buat_chat(kon,s.akun,'aktif',sekarang=100,context_kind='anak',context_id=str(asing),context_version=izin_asing.versi,context_resource_version='snapshot',context_category='ringkasan_netral')
    def tidak_boleh(*a,**kw):pytest.fail('Kontrol lokal tidak boleh mengakses provider/entitlement')
    monkeypatch.setattr(service,'panggil_provider_default',tidak_boleh)
    monkeypatch.setattr(service,'tersedia',tidak_boleh)
    s.origin={'Origin':s.alamat,'Sec-Fetch-Site':'same-origin'}
    yield s


def form(server,path):
    code,body,head=server.minta(path,cookie=server.token)
    assert code==200
    return re.search(r'name="versi" value="([0-9]+)"',body).group(1)


def test_get_metadata_saat_off_tanpa_transkrip_write(server):
    with schema.buka() as kon:sebelum=tuple(kon.iterdump())
    code,body,head=server.minta(manage.DASAR,cookie=server.token)
    assert code==200 and 'Kelola data Pendamping' in body
    assert server.chat.id in body and server.umum.id in body
    assert server.foreign.id not in body and server.sumber_asing.id not in body
    assert 'Isi privat sintetis' not in body
    assert head['Cache-Control']=='no-store' and "default-src 'none'" in head['Content-Security-Policy']
    with schema.buka() as kon:assert tuple(kon.iterdump())==sebelum


def test_hapus_chat_versi_tepat_hilang_aktif_bukan_purge(server):
    path=manage.DASAR+'/chat/'+server.chat.id+'/hapus'
    versi=form(server,path)
    code,body,_=server.minta(path,cookie=server.token,data={'versi':versi,'konfirmasi':'1'},headers=server.origin)
    assert code==200 and server.chat.id not in body
    with schema.buka() as kon:
        assert store.ambil_chat(kon,server.akun,server.chat.id) is None
        row=kon.execute('SELECT dihapus,purge_setelah FROM chat WHERE id=?',(server.chat.id,)).fetchone()
        assert row['dihapus']==row['purge_setelah']
        assert kon.execute('SELECT 1 FROM pesan WHERE chat_id=?',(server.chat.id,)).fetchone()
        assert store.ambil_chat(kon,server.akun,server.umum.id)
    assert server.minta(path,cookie=server.token)[0]==404
    assert server.minta(path,cookie=server.token,data={'versi':versi,'konfirmasi':'1'},headers=server.origin)[0]==404


def test_owner_asing_dan_tidak_ada_404_identik(server):
    bodies=[]
    for id in (server.foreign.id,server.sumber_asing.id,'chat_'+'f'*32):
        path=manage.DASAR+'/chat/'+id+'/hapus'
        for post in (False,True):
            kw={'data':{'versi':'1','konfirmasi':'1'},'headers':server.origin} if post else {}
            code,body,_=server.minta(path,cookie=server.token,**kw)
            assert code==404
            bodies.append(body)
    assert len(set(bodies))==1


def test_csrf_konfirmasi_dan_stale_tidak_menghapus(server):
    path=manage.DASAR+'/chat/'+server.chat.id+'/hapus'
    versi=form(server,path)
    for data,headers,status in [({'versi':versi,'konfirmasi':'1'},{},403),
                               ({'versi':versi,'konfirmasi':'0'},server.origin,400),
                               ({'versi':'999','konfirmasi':'1'},server.origin,409)]:
        assert server.minta(path,cookie=server.token,data=data,headers=headers)[0]==status
    with schema.buka() as kon:assert store.ambil_chat(kon,server.akun,server.chat.id)


def test_cabut_semua_dan_reconsent_tidak_menghidupkan_sumber(server):
    versi=form(server,manage.DASAR+'/cabut')
    assert server.minta(manage.DASAR+'/cabut',cookie=server.token,data={'versi':versi,'konfirmasi':'1'},headers=server.origin)[0]==200
    with schema.buka() as kon:
        assert not store.persetujuan_aktif(kon,server.akun,kategori='chat_umum',provider_id='deepseek')
        assert not kon.execute('SELECT 1 FROM persetujuan_konteks WHERE account_id=? AND dicabut IS NULL',(server.akun,)).fetchone()
        store.beri_persetujuan(kon,server.akun,policy_version=policy.VERSI_KEBIJAKAN,provider_id='deepseek',kategori='chat_umum',sekarang=200)
        assert not store.persetujuan_konteks_aktif(kon,server.akun,jenis='anak',resource_id=server.chat.context_id,versi=server.chat.context_version)
    assert form(server,manage.DASAR+'/chat/'+server.chat.id+'/hapus')


def test_role_cookie_wajib(server):
    for role in ('murid','admin'):
        akun=auth.cari_akun('feby' if role=='murid' else 'guru')
        token=sessions.buat(akun['pengguna'],role,id_akun=akun['id_akun'],revisi_auth=akun['revisi_auth'])
        assert server.minta(manage.DASAR,cookie=token)[0]==401
    assert server.minta(manage.DASAR,auth=('guru',SANDI_GURU))[0]==401


def test_revoke_rollback_dan_versi(server,monkeypatch):
    with schema.buka() as kon:
        before=tuple(kon.iterdump());v=store.versi_persetujuan(kon,server.akun)
        with pytest.raises(manage.GalatForm):
            with kon:manage.cabut_semua(kon,server.akun,v+1,sekarang=300)
        assert tuple(kon.iterdump())==before
        monkeypatch.setattr(store,'cabut_persetujuan_konteks',lambda *a,**kw:False)
        with pytest.raises(manage.GalatForm):
            with kon:manage.cabut_semua(kon,server.akun,v,sekarang=300)
        assert tuple(kon.iterdump())==before


def test_get_tanpa_db_tidak_membuat(server,monkeypatch,tmp_path):
    path=tmp_path/'belum-ada.db';monkeypatch.setattr(schema,'BAWAAN',path)
    assert server.minta(manage.DASAR,cookie=server.token)[0]==200
    assert not path.exists()


@pytest.mark.parametrize('aksi',['hapus','cabut'])
@pytest.mark.parametrize('waktu',['admission','provider'])
def test_race_tidak_kirim_setelah_admission_dan_tidak_commit_late(tmp_path,monkeypatch,aksi,waktu):
    import assistant_client
    import ai_service
    akun='akun_'+'a'*32;path=tmp_path/'privat.db';schema.siapkan(path)
    monkeypatch.setenv('DEEPSEEK_API_KEY','key-sintetis')
    with schema.buka(path) as kon:
        store.beri_persetujuan(kon,akun,policy_version=policy.VERSI_KEBIJAKAN,provider_id='deepseek',kategori='chat_umum',sekarang=1)
        chat=store.buat_chat(kon,akun,'aktif',sekarang=1)
    def ubah():
        with schema.buka(path) as kon:
            if aksi=='hapus':store.hapus_chat(kon,akun,chat.id,versi_diharapkan=1,sekarang=3,retensi_detik=0)
            else:manage.cabut_semua(kon,akun,store.versi_persetujuan(kon,akun),sekarang=3)
    def admission(fitur,account,pemanggil,**kw):
        if waktu=='admission':ubah()
        return pemanggil()
    calls=[]
    def client(*a,**kw):
        calls.append(1)
        if waktu=='provider':ubah()
        return ProviderPalsu().respons
    monkeypatch.setattr(ai_service,'panggil',admission)
    monkeypatch.setattr(assistant_client,'kirim',client)
    with schema.buka(path) as kon:
        with pytest.raises(service.GalatPendamping):
            service.kirim_pesan(kon,akun,chat.id,'Pertanyaan sintetis.',request_id='req_race_manage',sekarang=2)
        assert kon.execute('SELECT count(*) FROM pesan').fetchone()[0]==0
        with pytest.raises(service.GalatPendamping):
            service.kirim_pesan(kon,akun,chat.id,'Pertanyaan sintetis.',request_id='req_race_manage',sekarang=4)
    assert len(calls)==(0 if waktu=='admission' else 1)


def test_purge_chat_tidak_menghapus_memori_terkonfirmasi(server):
    with schema.buka() as kon:
        memori=store.tambah_memori(kon,server.akun,'Jawab singkat.',sumber_chat_id=server.chat.id,dikonfirmasi=True,sekarang=100,lingkup='preferensi_orang_tua')
    path=manage.DASAR+'/chat/'+server.chat.id+'/hapus'
    versi=form(server,path)
    server.minta(path,cookie=server.token,data={'versi':versi,'konfirmasi':'1'},headers=server.origin)
    with schema.buka() as kon:
        due=kon.execute('SELECT purge_setelah FROM chat WHERE id=?',(server.chat.id,)).fetchone()[0]
        assert store.purge(kon,sekarang=due)==1
        assert kon.execute('SELECT 1 FROM pesan WHERE chat_id=?',(server.chat.id,)).fetchone() is None
        row=kon.execute('SELECT sumber_chat_id FROM memori WHERE id=?',(memori.id,)).fetchone()
        assert row is not None and row[0] is None


def test_schema_rusak_tidak_membocorkan_error(server,monkeypatch,tmp_path):
    path=tmp_path/'rusak.db';path.write_bytes(b'bukan database')
    monkeypatch.setattr(schema,'BAWAAN',path)
    kode,isi,_=server.minta(manage.DASAR,cookie=server.token)
    assert kode==503 and 'Traceback' not in isi and 'bukan database' not in isi


def test_sensor_rekonsiliasi_setelah_cabut(server):
    import admin_store
    import sensor_schema
    import sensor_store
    import sensor_cleanup
    sensor_schema.migrasikan(admin_store.BAWAAN)
    with schema.buka() as kon:
        operasi=store.mulai_operasi(kon,server.akun,server.umum.id,'req_sensor_manage',consent_version=store.versi_persetujuan(kon,server.akun),memory_version=0,context_version=0,sekarang=101)
        kon.execute("UPDATE operasi SET status='selesai',selesai=102 WHERE request_id=?",(operasi.request_id,))
    with sensor_store.buka(admin_store.BAWAAN,tulis=True) as con:
        con.execute('INSERT INTO sensor_peserta VALUES(?,?,?,?,?,?,?,?,?)',(server.akun,'a'*32,'f'*64,sensor_store.BOOT,100,7776100,'sensor-keluarga-v1',0,1))
        izin=sensor_store.Izin(server.akun,'a'*32,'f'*64,100,7776100,False,True)
        con.execute('INSERT INTO sensor_chat VALUES(?,?,?,?)',('a'*32,sensor_store.token(izin,'chat','req_sensor_manage'),'hasil',1))
    sensor_cleanup.bersihkan(admin_store.BAWAAN,server.db,schema.BAWAAN,auth.BERKAS_SANDI,sekarang=200)
    with sensor_store.buka(admin_store.BAWAAN) as con:
        assert con.execute('SELECT 1 FROM sensor_chat').fetchone()
    versi=form(server,manage.DASAR+'/cabut')
    server.minta(manage.DASAR+'/cabut',cookie=server.token,data={'versi':versi,'konfirmasi':'1'},headers=server.origin)
    for _ in range(2):
        sensor_cleanup.bersihkan(admin_store.BAWAAN,server.db,schema.BAWAAN,auth.BERKAS_SANDI,sekarang=201)
    with sensor_store.buka(admin_store.BAWAAN) as con:
        assert not con.execute('SELECT 1 FROM sensor_chat').fetchone()
        assert con.execute('SELECT 1 FROM sensor_peserta').fetchone()
