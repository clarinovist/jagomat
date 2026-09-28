"""Guru/murid foto ON memakai request native, kuota orang tua, guard404 identik."""
import base64
import re
import urllib.error
import urllib.request

import pytest

import admin_store
import attachments as foto
import assistant_entitlement_runtime as runtime
import auth
import database
import llm
import subscription as d
import subscription_store as v1
import subscription_package_store as paket
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
from test_murid_kirim_foto import _sesi_untuk_feby
from test_photo_attempts import tubuh, HASIL


@pytest.fixture
def server(tmp_path,monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'enforcement_aktif',lambda:True)
    # Helper ServerUji sudah mengarahkan database.BAWAAN ke DB sintetis.
    database.migrasikan_operasi_foto(database.BAWAAN)
    parent=auth.cari_akun('guru')
    admin=tmp_path/'kuota.db'
    admin_store.siapkan(admin,paket_v2=True)
    on=d.Sakelar(True,True,True,False)
    v1.enroll(admin,parent['id_akun'],sumber_id='enroll_http',asal='transisi',mulai=1,peran='guru',sakelar=on)
    paket.adopsi(admin,parent['id_akun'],operasi_id='adopsi_http',sekarang=2,sakelar=on)
    monkeypatch.setattr(admin_store,'BAWAAN',admin)
    admin_store.migrasikan_kuota_pendamping(admin)
    # Waktu frozen untuk trial; tidak mengubah clock global HTTP/autentikasi.
    asli=foto.proses_foto_terjaga
    monkeypatch.setattr(foto,'proses_foto_terjaga',lambda *a,**kw:asli(*a,**kw,sekarang=3))
    s.sesi_foto=_sesi_untuk_feby(s)
    s.kuota_path=admin
    yield s
    s.berhenti()


def post_foto(s,path,operasi,akun):
    ct,body=tubuh(operasi)
    req=urllib.request.Request(s.alamat+path,data=body,method='POST',headers={
        'Content-Type':ct,'Authorization':'Basic '+base64.b64encode((akun[0]+':'+akun[1]).encode()).decode()})
    try:
        with urllib.request.urlopen(req,timeout=10) as r:return r.status,r.read().decode()
    except urllib.error.HTTPError as e:return e.code,e.read().decode()


@pytest.mark.parametrize('peran',['guru','murid'])
def test_http_foto_parent_quota_replay_dan_neutral(server,monkeypatch,peran):
    calls=[]
    def baca(*a,sebelum_kirim):
        sebelum_kirim();calls.append(1)
        return llm.BacaanFoto('result',HASIL)
    monkeypatch.setattr(llm,'ekstrak_lembar_tercatat',baca)
    sid=server.sesi_foto
    if peran=='guru':
        kode,html,_=server.minta(f'/sesi/{sid}/lampiran',auth=('guru',SANDI_GURU))
        path=f'/lampiran/{sid}';akun=('guru',SANDI_GURU)
    else:
        kode,html,_=server.minta(f'/murid/kerjakan/{sid}',auth=('feby',SANDI_MURID))
        path=f'/murid/foto/{sid}';akun=('feby',SANDI_MURID)
    assert kode==200
    oid=re.search(r'name="operasi_foto" value="([^"]+)"',html).group(1)
    assert post_foto(server,path,oid,akun)[0]==200
    assert post_foto(server,path,oid,akun)[0]==200 and calls==[1]
    with server.buka() as kon:assert len(database.daftar_lampiran(kon,sid))==1
    if peran=='murid':
        for n in ('b','c'):
            kode,isi=post_foto(server,path,'foto_'+n*32,akun)
            assert kode==200
        assert 'Foto belum dapat diproses' in isi
        assert all(s not in isi for s in ('kuota_habis','jago_pro','trial_aktif'))
        assert len(calls)==2


def test_http_foreign_404_zero_provider_and_reread_strict(server,monkeypatch):
    monkeypatch.setattr(llm,'ekstrak_lembar_tercatat',lambda *a,**kw:pytest.fail('provider tidak boleh dipanggil'))
    with server.buka() as kon:
        sid=database.tambah_siswa(kon,'ProfilAsing',pemilik='guru2')
        foreign=database.buat_sesi(kon,sid,seed=17,jumlah_soal=1)
        lid=database.simpan_lampiran(kon,server.sesi_foto,'tidak-ada.jpg')
    for path,akun in ((f'/lampiran/{foreign}',('guru',SANDI_GURU)),(f'/murid/foto/{foreign}',('feby',SANDI_MURID))):
        assert post_foto(server,path,'foto_'+'d'*32,akun)[0]==404
    kode,_,_=server.minta(f'/lampiran/{lid}/baca-ulang',auth=('guru',SANDI_GURU),data={})
    assert kode==400
    with server.buka() as kon:assert kon.execute('SELECT count(*) FROM operasi_foto_baca').fetchone()[0]==0
