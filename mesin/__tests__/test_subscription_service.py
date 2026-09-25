"""Alur nyata auth/DB/ledger dengan fake transport dan waktu sintetis saja."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import socket
from types import SimpleNamespace

import pytest
import admin_registration
import admin_store
import auth
import database
import subscription as d
import subscription_service as s
import subscription_store as store
from test_subscription_store import T0, ON, dump
from test_midtrans_contract import CFG, Respons, Transport


@pytest.fixture(autouse=True)
def tanpa_network(monkeypatch):
    def tolak(*a, **kw):
        pytest.fail('network tidak diizinkan')
    monkeypatch.setattr(socket, 'create_connection', tolak)
    monkeypatch.setattr(socket, 'socket', tolak)
    monkeypatch.setattr(socket, 'getaddrinfo', tolak)


@pytest.fixture
def keluarga(tmp_path):
    k = SimpleNamespace(admin=tmp_path/'admin.db', auth=tmp_path/'sandi.json', db=tmp_path/'belajar.db')
    admin_store.siapkan(k.admin, sekarang=T0)
    database.siapkan(k.db)
    store.buat_kampanye(k.admin, 'kampanye', mulai=T0, sakelar=ON)
    k.op = 'daftar_sintetis_001'
    admin_registration.daftar_publik(k.admin,k.auth,k.db,operasi_id=k.op,alias='keluarga-sintetis',
                                      sandi='sandi-sintetis-123',token_form='x'*64,sekarang=T0)
    k.principal = auth.autentikasi('keluarga-sintetis','sandi-sintetis-123',k.auth)
    with database.buka(k.db) as kon:
        k.sid = database.tambah_siswa(kon,'Profil Sintetis','P3',pemilik=k.principal.pengguna)
        k.asing = database.tambah_siswa(kon,'Profil Lain','P3',pemilik='keluarga-lain')
    k.args = (k.admin,k.auth,k.db,k.principal)
    return k


def sinkron(k, **kw):
    return s.sinkron_pendaftaran(*k.args,sumber_id=k.op,cutoff=T0,sekarang=T0+1,sakelar=ON,**kw)


def quote(k):
    sinkron(k)
    s.atur_cakupan(*k.args,(k.sid,),operasi_id='cakupan_sintetis',revisi=0,sekarang=T0+1,sakelar=ON)
    return s.buat_invoice(*k.args,invoice_id='inv_'+'b'*32,idempotency_key='idem_'+'c'*32,
                          merchant=CFG.merchant,sekarang=T0+2,kedaluwarsa=T0+1000,sakelar=ON)


def transport(inv, status='settlement'):
    class ProviderPalsu:
        def __init__(self): self.panggilan=[]
        def __call__(self, req, *, timeout, allow_redirects):
            assert timeout==10 and allow_redirects is False
            self.panggilan.append(req)
            return Respons(dict(order_id=inv['invoice_id'],transaction_id='trx_sintetis',gross_amount=str(inv['rupiah'])+'.00',
                currency='IDR',payment_type='qris',merchant_id=CFG.merchant,status_code='200',transaction_status=status),url=req.url)
    return ProviderPalsu()


def test_sinkron_receipt_exact_trial_tidak_reset(keluarga):
    k=keluarga
    awal=(k.auth.read_bytes(),k.db.read_bytes())
    e=sinkron(k)
    assert e.mulai==T0 and e.peserta_promo
    assert sinkron(k)==e
    assert (k.auth.read_bytes(),k.db.read_bytes())==awal
    assert auth.setel_sandi_guru(k.principal.pengguna,'sandi-baru-sintetis',k.auth)
    baru=auth.autentikasi(k.principal.pengguna,'sandi-baru-sintetis',k.auth)
    assert s.sinkron_pendaftaran(k.admin,k.auth,k.db,baru,sumber_id=k.op,cutoff=T0,sekarang=T0+100,sakelar=ON)==e


def test_sinkron_gagal_store_lalu_retry_tidak_mengubah_auth(keluarga,monkeypatch):
    k=keluarga
    awal=k.auth.read_bytes()
    asli=store.enroll
    def gagal(*a,**kw): raise admin_store.StoreBelumSiap('sink gagal')
    monkeypatch.setattr(store,'enroll',gagal)
    with pytest.raises(admin_store.StoreBelumSiap): sinkron(k)
    assert k.auth.read_bytes()==awal
    monkeypatch.setattr(store,'enroll',asli)
    assert sinkron(k).mulai==T0


@pytest.mark.parametrize('jenis',['owner','receipt','cutoff','admin','stale'])
def test_identitas_receipt_dan_cutoff_tolak_tanpa_efek(keluarga,jenis):
    k=keluarga
    principal=k.principal; sumber=k.op; cutoff=T0
    if jenis=='owner': principal=replace(principal,id_akun='akun_'+'f'*32)
    if jenis=='receipt': sumber='receipt_tidak_ada'
    if jenis=='cutoff': cutoff=T0+1
    if jenis=='admin': principal=replace(principal,peran='admin')
    if jenis=='stale': principal=replace(principal,revisi_auth=99)
    awal=dump(k.admin)
    with pytest.raises(LookupError):
        s.sinkron_pendaftaran(k.admin,k.auth,k.db,principal,sumber_id=sumber,cutoff=cutoff,sekarang=T0+2,sakelar=ON)
    assert dump(k.admin)==awal


def test_receipt_akun_lain_ditolak(keluarga):
    k=keluarga
    data=json.loads(k.auth.read_text())
    data['operasi_registrasi'][k.op]['hasil_id']='akun_'+'f'*32
    k.auth.write_text(json.dumps(data))
    awal=dump(k.admin)
    with pytest.raises(LookupError): sinkron(k)
    assert dump(k.admin)==awal


def test_profile_owner_dan_tanpa_login(keluarga):
    k=keluarga; sinkron(k)
    awal=dump(k.admin)
    for sid in (k.asing,99999):
        with pytest.raises(LookupError,match='profil tidak ditemukan'):
            s.atur_cakupan(*k.args,(sid,),operasi_id='cakupan_tolak',revisi=0,sekarang=T0+1,sakelar=ON)
        assert dump(k.admin)==awal
    s.atur_cakupan(*k.args,(k.sid,),operasi_id='cakupan_benar',revisi=0,sekarang=T0+1,sakelar=ON)
    assert len(auth.muat_akun(k.auth))==1  # profil tercakup tanpa credential anak


def test_intent_crash_retry_hanya_query(keluarga):
    k=keluarga; inv=quote(k); tr=transport(inv)
    with pytest.raises(s.SinkronBelumSelesai):
        s.mulai_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+3,sakelar=ON,failpoint='setelah_intent')
    assert tr.panggilan==[]
    hasil=s.mulai_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+4,sakelar=ON)
    assert hasil.status=='lunas'
    assert [r.metode for r in tr.panggilan]==['GET']
    assert len(store.baca(k.admin,k.principal.id_akun).grants)==1


def test_create_concurrent_paling_sekali_receipt_grant_idempoten(keluarga):
    k=keluarga; inv=quote(k); tr=transport(inv)
    with ThreadPoolExecutor(max_workers=3) as pool:
        hasil=list(pool.map(lambda _: s.mulai_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+3,sakelar=ON),range(6)))
    assert all(h.status=='lunas' for h in hasil)
    assert sum(r.metode=='POST' for r in tr.panggilan)==1
    snap=store.baca(k.admin,k.principal.id_akun)
    assert len(snap.grants)==1
    pending=transport(inv,'pending')
    assert s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=pending,sekarang=T0+4,sakelar=ON).status=='lunas'
    assert store.baca(k.admin,k.principal.id_akun)==snap


def test_timeout_create_lalu_reconcile_tanpa_charge_baru(keluarga):
    k=keluarga; inv=quote(k); tr=Transport(TimeoutError('sintetis'))
    hasil=s.mulai_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+3,sakelar=ON)
    assert hasil.status=='belum_terverifikasi'
    tr=transport(inv)
    # Mematikan create tidak menutup rekonsiliasi in-flight.
    hasil=s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+4,sakelar=d.Sakelar(rekonsiliasi=True))
    assert hasil.status=='lunas' and [r.metode for r in tr.panggilan]==['GET']


def test_receipt_crash_dipulihkan_tanpa_tulis_auth_belajar(keluarga):
    k=keluarga; inv=quote(k); tr=transport(inv)
    awal=(k.auth.read_bytes(),k.db.read_bytes())
    with pytest.raises(RuntimeError,match='crash sintetis'):
        s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+3,sakelar=ON,failpoint='setelah_receipt')
    assert not store.baca(k.admin,k.principal.id_akun).grants
    assert s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+4,sakelar=ON).status=='lunas'
    assert (k.auth.read_bytes(),k.db.read_bytes())==awal


@pytest.mark.parametrize('ubah',['sandi','owner','hapus_alias'])
def test_perubahan_saat_transport_tidak_grant_dan_tidak_memegang_lock(keluarga,ubah):
    k=keluarga; inv=quote(k); tr=transport(inv)
    def saat_transport(req,**kw):
        def ubah_data():
            if ubah=='sandi': auth.setel_sandi_guru(k.principal.pengguna,'sandi-baru-sintetis',k.auth)
            elif ubah=='owner':
                with database.buka(k.db) as kon: kon.execute('UPDATE siswa SET pemilik=? WHERE id=?',('keluarga-lain',k.sid))
            else:
                assert auth.hapus_akun_guru(k.principal.pengguna,k.auth)
                auth.tambah_akun(k.principal.pengguna,'sandi-lain-sintetis','guru',k.auth)
        with ThreadPoolExecutor(max_workers=1) as pool: pool.submit(ubah_data).result(timeout=3)
        return tr(req,**kw)
    with pytest.raises(LookupError):
        s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=saat_transport,sekarang=T0+3,sakelar=ON)
    assert not store.baca(k.admin,k.principal.id_akun).grants


def test_sesi_stale_setelah_provider_tidak_boleh_grant(keluarga):
    k=keluarga; inv=quote(k); tr=transport(inv)
    def stale():
        raise LookupError('resource tidak ditemukan')
    with pytest.raises(LookupError):
        s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,
                             sekarang=T0+3,sakelar=ON,cek_sesi=stale)
    assert not store.baca(k.admin,k.principal.id_akun).grants


def test_receipt_committed_pengamatan_gagal_replay_tidak_ganda(keluarga,monkeypatch):
    k=keluarga; inv=quote(k); tr=transport(inv)
    asli=store.catat_pengamatan
    def gagal(*a,**kw): raise RuntimeError('pengamatan gagal sintetis')
    monkeypatch.setattr(store,'catat_pengamatan',gagal)
    with pytest.raises(RuntimeError,match='pengamatan gagal'):
        s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+3,sakelar=ON)
    snap=store.baca(k.admin,k.principal.id_akun)
    assert len(snap.grants)==1
    monkeypatch.setattr(store,'catat_pengamatan',asli)
    assert s.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=tr,sekarang=T0+4,sakelar=ON).status=='lunas'
    assert store.baca(k.admin,k.principal.id_akun)==snap


def test_default_off_tidak_membaca_file_atau_transport(tmp_path):
    args=(tmp_path/'admin',tmp_path/'auth',tmp_path/'db',None)
    with pytest.raises(d.FiturNonaktif): s.sinkron_pendaftaran(*args,sumber_id='daftar_sintetis',cutoff=T0,sekarang=T0)
    with pytest.raises(d.FiturNonaktif): s.atur_cakupan(*args,(1,),operasi_id='cakupan_off',revisi=0,sekarang=T0)
    with pytest.raises(d.FiturNonaktif): s.buat_invoice(*args,invoice_id='inv_'+'a'*32,idempotency_key='idem_sintetis',merchant='M',sekarang=T0,kedaluwarsa=T0+1)
    for fn in (s.periksa_pembayaran,s.mulai_pembayaran):
        with pytest.raises(d.FiturNonaktif): fn(*args,'inv_'+'a'*32,config=None,transport=None,sekarang=T0)
    assert not list(tmp_path.iterdir())


def test_receipt_tertunda_promo_mengikuti_urutan_daftar(keluarga):
    k=keluarga
    # Receipt sintetis sesuai bentuk actual; tes ini khusus peringkat, bukan backfill.
    data=json.loads(k.auth.read_text())
    r=data['operasi_registrasi'][k.op]
    for i in range(100):
        key='daftar_%04d'%i
        data['operasi_registrasi'][key]={**r,'operasi_id':key,'hasil_id':'akun_%032x'%i,'dibuat':T0+i}
    data['operasi_registrasi'][k.op]['dibuat']=T0+101
    k.auth.write_text(json.dumps(data))
    e=s.sinkron_pendaftaran(*k.args,sumber_id=k.op,cutoff=T0,sekarang=T0+102,sakelar=ON)
    assert not e.peserta_promo
