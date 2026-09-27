"""Ledger paket admin8 memakai DB sintetis; v1, owner, replay dan kalender dijaga."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import sqlite3

import pytest
import admin_store
import subscription as d
import subscription_packages as p
import subscription_package_schema as schema
import subscription_package_store as paket
import subscription_store as lama
import subscription_service as layanan
import subscription_checkout as checkout
import subscription_worker as worker
import subscription_callback as callback
from test_subscription_service import keluarga, sinkron, transport, tanpa_network
from test_subscription_store import ON, T0
from test_midtrans_contract import CFG


def isi(path):
    with sqlite3.connect(path) as kon:
        tabel = [r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: tuple(kon.execute('SELECT * FROM "'+t+'" ORDER BY rowid')) for t in tabel}


def siapkan(k, *, promo=True):
    sinkron(k)
    admin_store.siapkan(k.admin, paket_v2=True)
    return paket.adopsi(k.admin, k.principal.id_akun, operasi_id='adopsi_sintetis', sekarang=T0+1,
                        peserta_promo=promo, kampanye='uji_paket_v2' if promo else None, sakelar=ON)


def invoice(k, *, urutan=1, kode='jago_pro', penagihan='tahunan', kini=T0+2):
    return layanan.siapkan_paket(*k.args, (k.sid,), kode=kode, penagihan=penagihan,
                                invoice_id='inv_'+format(urutan,'032x'), operasi_id='paket_op_'+format(urutan,'032x'),
                                merchant=CFG.merchant, sekarang=kini, kedaluwarsa=kini+86400, sakelar=ON)


def bukti(inv, transaksi='trx_paket_sintetis'):
    return d.Pembayaran('midtrans', transaksi, inv['invoice_id'], inv['akun_id'], inv['rupiah'],
                        'IDR', 'qris', CFG.merchant, 'settlement', True)


def test_migrasi_opt_in_idempoten_preservasi_v1(keluarga):
    k=keluarga; sinkron(k)
    sebelum=isi(k.admin)
    with pytest.raises(admin_store.StoreBelumSiap):
        paket.adopsi(k.admin,k.principal.id_akun,operasi_id='adopsi_sintetis',sekarang=T0+1,sakelar=ON)
    assert isi(k.admin)==sebelum
    admin_store.siapkan(k.admin,paket_v2=True)
    for t, rows in sebelum.items(): assert isi(k.admin)[t]==rows
    for _ in range(2):
        admin_store.siapkan(k.admin,paket_v2=True)
        admin_store.siapkan(k.admin)  # Tidak downgrade atau menghapus ledger v2.
    with admin_store.buka_baca(k.admin) as kon:
        assert kon.execute('PRAGMA user_version').fetchone()[0]==8
        assert not kon.execute('PRAGMA foreign_key_check').fetchall()
        assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert all(not kon.execute('SELECT * FROM '+t).fetchall() for t in schema.TABEL)


def test_migrasi_tidak_memperbaiki_schema_rusak_diamdiam(keluarga):
    k=keluarga;siapkan(k)
    with sqlite3.connect(k.admin) as kon:kon.execute('DROP TRIGGER paket_invoice_tolak_update')
    with pytest.raises(admin_store.StoreBelumSiap):admin_store.siapkan(k.admin,paket_v2=True)
    with pytest.raises(admin_store.StoreBelumSiap):paket.baca(k.admin,k.principal.id_akun)


@pytest.mark.parametrize('kode,penagihan,harga', [('jago','bulanan',25000),('jago_pro','bulanan',49000),
                                               ('jago','tahunan',250000),('jago_pro','tahunan',490000)])
def test_snapshot_durable_kalender_replay_crash(keluarga,kode,penagihan,harga):
    k=keluarga;siapkan(k)
    inv=invoice(k,kode=kode,penagihan=penagihan)
    assert inv['rupiah']==harga and inv['normal']>harga and inv['versi']==p.VERSI
    awal=isi(k.admin)
    with pytest.raises(RuntimeError,match='crash sintetis'):
        lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=T0+3,sakelar=ON,failpoint='setelah_receipt')
    assert isi(k.admin)==awal
    def bayar(_):return lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=T0+3,sakelar=ON)
    with ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(bayar,range(2)))==['grant','grant']
    admin_store.siapkan(k.admin)
    assert invoice(k,kode=kode,penagihan=penagihan)==inv
    g=paket.baca(k.admin,k.principal.id_akun).grants
    assert len(g)==1 and g[0]['mulai']==T0+d.DURASI_TRIAL
    assert g[0]['akhir']==p.akhir_periode(g[0]['mulai'],penagihan)
    assert (g[0]['paket'],g[0]['penagihan'])==(kode,penagihan)
    assert lama.baca_invoice(k.admin,k.principal.id_akun,inv['invoice_id'])['status']=='lunas'
    # Pembayaran kedua tersimpan untuk tinjauan, tidak menambah grant/promo.
    assert lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv,'trx_kedua'),sekarang=T0+4,sakelar=ON)=='perlu_diperiksa'
    assert len(paket.baca(k.admin,k.principal.id_akun).grants)==1


def test_promo_milik_akun_tidak_reset_ganti_paket(keluarga):
    k=keluarga;siapkan(k)
    harga=[]
    for i,kode in enumerate(('jago','jago_pro','jago','jago_pro'),1):
        inv=invoice(k,urutan=i,kode=kode,penagihan='bulanan',kini=T0+10*i)
        harga.append(inv['rupiah'])
        lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv,'trx_'+str(i)),sekarang=T0+10*i+1,sakelar=ON)
    assert harga==[25000,49000,25000,59000]
    g=paket.baca(k.admin,k.principal.id_akun).grants
    assert all(g[i]['mulai']==g[i-1]['akhir'] for i in range(1,4))
    assert g[-1]['akhir']==p.akhir_periode(g[0]['mulai'],'bulanan',urutan=4)
    with pytest.raises(lama.KonflikLangganan,match='perubahan periode'):
        invoice(k,urutan=5,penagihan='tahunan',kini=T0+100)


def test_tarif_normal_tidak_mewarisi_promo_v1(keluarga):
    k=keluarga;siapkan(k,promo=False)
    assert lama.baca(k.admin,k.principal.id_akun).enrollment.peserta_promo
    inv=invoice(k)
    assert inv['rupiah']==590000 and inv['promo']==0


@pytest.mark.parametrize('ubah', ['nominal','owner','pending','verified','currency','channel','merchant'])
def test_bukti_salah_tanpa_efek(keluarga,ubah):
    k=keluarga;siapkan(k);inv=invoice(k);b=bukti(inv)
    perubahan={'nominal':{'rupiah':1},'owner':{'akun_id':'akun_'+'f'*32},'pending':{'status':'pending'},
               'verified':{'terverifikasi':False},'currency':{'currency':'USD'},'channel':{'channel':'x'},'merchant':{'merchant':'asing'}}
    awal=isi(k.admin)
    with pytest.raises(lama.KonflikLangganan):lama.terapkan_pembayaran(k.admin,k.principal.id_akun,replace(b,**perubahan[ubah]),sekarang=T0+3,sakelar=ON)
    assert isi(k.admin)==awal


@pytest.mark.parametrize('jenis',['profil','principal','pilihan','periode','snapshot','off'])
def test_quote_guard_tanpa_efek(keluarga,jenis):
    k=keluarga;siapkan(k)
    if jenis=='snapshot':invoice(k)
    args=list(k.args);profil=(k.sid,);kode='jago_pro';periode='tahunan';on=ON
    if jenis=='profil':profil=(k.asing,)
    if jenis=='principal':args[-1]=replace(k.principal,revisi_auth=99)
    if jenis=='pilihan':kode='gratis'
    if jenis=='periode':periode='yearly'
    if jenis=='snapshot':kode='jago'
    if jenis=='off':on=d.SAKELAR
    awal=isi(k.admin)
    with pytest.raises((LookupError,ValueError,d.FiturNonaktif)):
        layanan.siapkan_paket(*args,profil,kode=kode,penagihan=periode,invoice_id='inv_'+format(1,'032x'),
                              operasi_id='paket_op_'+format(1,'032x'),merchant=CFG.merchant,sekarang=T0+2,kedaluwarsa=T0+86402,sakelar=on)
    assert isi(k.admin)==awal


def test_service_provider_worker_callback_dan_recheck(keluarga):
    k=keluarga;siapkan(k);inv=invoice(k)
    assert callback._simpan(k.admin,inv['invoice_id'],'belum_terverifikasi','a'*32,T0+3,ON)
    assert not worker.kandidat(k.admin,sekarang=T0+4)
    assert lama.reservasi_create(k.admin,k.principal.id_akun,inv['invoice_id'],sekarang=T0+4,sakelar=ON)
    assert worker.kandidat(k.admin,sekarang=T0+5)==[(inv['invoice_id'],k.principal.id_akun)]
    with pytest.raises(d.FiturNonaktif):
        checkout.baca_tagihan(*k.args,inv['invoice_id'],sakelar=ON)
    with pytest.raises(d.FiturNonaktif):
        checkout.ringkasan(*k.args,sakelar=ON)
    assert checkout.baca_tagihan(*k.args,inv['invoice_id'],sakelar=ON,paket_v2=True)['create_dicoba']
    awal=isi(k.admin)
    def stale():raise LookupError('sesi stale sintetis')
    with pytest.raises(LookupError):
        layanan.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=transport(inv),sekarang=T0+5,sakelar=ON,cek_sesi=stale)
    assert isi(k.admin)==awal
    hasil=layanan.periksa_pembayaran(*k.args,inv['invoice_id'],config=CFG,transport=transport(inv),sekarang=T0+5,sakelar=ON)
    assert hasil.hasil_ledger=='grant'
    assert not worker.kandidat(k.admin,sekarang=T0+6)
    assert len(paket.baca(k.admin,k.principal.id_akun).grants)==1


def test_backup_admin8_dengan_hanya_invoice_v2_perlu_rekonsiliasi(tmp_path):
    import admin_backup
    from test_admin_backup import _buat_bundle, _buat_ai_v2, OWNER
    b = _buat_bundle(tmp_path)
    path = b/'admin-control.db'
    admin_store.siapkan(path,paket_v2=True)
    lama.enroll(path,OWNER,sumber_id='enroll_sintetis',asal='transisi',mulai=1,peran='guru',sakelar=ON)
    paket.adopsi(path,OWNER,operasi_id='adopsi_sintetis',sekarang=2,sakelar=ON)
    inv=paket.buat_invoice(path,OWNER,(1,),kode='jago',penagihan='tahunan',invoice_id='inv_'+'1'*32,
                           idempotency_key='idem_sintetis',provider='midtrans',merchant=CFG.merchant,
                           sekarang=3,kedaluwarsa=999,pemilik_profil=lambda _:OWNER,sakelar=ON)
    (b/'manifest.json').unlink()  # Fixture baru setelah isi bundle sintetis berubah.
    admin_backup.buat_manifest(b,bundle_id='paket_sintetis',cutoff=100)
    assert admin_backup.validasi_bundle(b).perlu_rekonsiliasi
    awal=isi(path)
    hasil=admin_backup.rehearsal_bundle(b,migrator_ai=_buat_ai_v2)
    assert hasil.versi_admin==8 and hasil.perlu_rekonsiliasi
    assert isi(path)==awal


def test_reader_menolak_nominal_dan_grant_rusak(keluarga):
    k=keluarga;siapkan(k);inv=invoice(k)
    # Korupsi sintetis tanpa mengganti trigger permanen; reader harus menolak data.
    with sqlite3.connect(k.admin) as kon:
        ddl=kon.execute("SELECT sql FROM sqlite_master WHERE name='paket_invoice_tolak_update'").fetchone()[0]
        kon.execute('DROP TRIGGER paket_invoice_tolak_update')
        kon.execute('UPDATE paket_invoice SET rupiah=1')
        kon.execute(ddl)
    with pytest.raises(lama.KonflikLangganan,match='snapshot invoice'):
        paket.baca(k.admin,k.principal.id_akun)


def test_jeda_memulai_jangkar_baru_dan_tahunan_promo_hanya_sekali(keluarga):
    k=keluarga;siapkan(k);inv=invoice(k)
    lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=T0+3,sakelar=ON)
    akhir=paket.baca(k.admin,k.principal.id_akun).grants[0]['akhir']
    inv2=invoice(k,urutan=2,kini=akhir+100)
    assert inv2['rupiah']==590000 and inv2['promo']==0
    lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv2,'trx_tahun2'),sekarang=akhir+101,sakelar=ON)
    g=paket.baca(k.admin,k.principal.id_akun).grants[1]
    assert g['mulai']==g['jangkar_mulai']==akhir+101 and g['indeks_bulan']==0
    assert g['akhir']==p.akhir_periode(akhir+101,'tahunan')


def test_quote_deadline_receipt_tidak_mendapat_grant(keluarga):
    k=keluarga;siapkan(k);inv=invoice(k)
    assert lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=inv['kedaluwarsa'],sakelar=ON)=='perlu_diperiksa'
    assert paket.baca(k.admin,k.principal.id_akun).grants==()


def test_duplikat_sumber_v2_menahan_pembayaran_v1(keluarga):
    k=keluarga;siapkan(k);inv=invoice(k)
    lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=T0+3,sakelar=ON)
    asing='akun_'+'e'*32
    lama.enroll(k.admin,asing,sumber_id='enroll_asing_sintetis',asal='transisi',mulai=T0,peran='guru',sakelar=ON)
    lama.atur_cakupan(k.admin,asing,(999,),operasi_id='cakupan_asing_sintetis',revisi=0,sekarang=T0+3,pemilik_profil=lambda _:asing,sakelar=ON)
    v1=lama.buat_invoice(k.admin,asing,invoice_id='inv_'+'d'*32,idempotency_key='idem_asing_sintetis',provider='midtrans',
                         channel='qris',merchant=CFG.merchant,sekarang=T0+3,kedaluwarsa=T0+999,sakelar=ON)
    awal=isi(k.admin)
    with pytest.raises(lama.KonflikLangganan,match='lintas versi'):
        lama.terapkan_pembayaran(k.admin,asing,bukti(v1),sekarang=T0+4,sakelar=ON)
    assert isi(k.admin)==awal


def test_snapshot_grant_rusak_tidak_dibaca_sebagai_hak(keluarga):
    k=keluarga;siapkan(k);inv=invoice(k)
    lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=T0+3,sakelar=ON)
    with sqlite3.connect(k.admin) as kon:
        ddl=kon.execute("SELECT sql FROM sqlite_master WHERE name='paket_grant_tolak_update'").fetchone()[0]
        kon.execute('DROP TRIGGER paket_grant_tolak_update')
        kon.execute('UPDATE paket_grant SET akhir=akhir+1')
        kon.execute(ddl)
    with pytest.raises(lama.KonflikLangganan,match='periode grant'):
        paket.baca(k.admin,k.principal.id_akun)


def test_worker_fencing_setelah_snapshot_menolak_owner_baru(keluarga,monkeypatch):
    import database
    k=keluarga;siapkan(k);inv=invoice(k)
    lama.reservasi_create(k.admin,k.principal.id_akun,inv['invoice_id'],sekarang=T0+3,sakelar=ON)
    asli=worker._snapshot;jumlah=[0]
    def ganti(*args):
        hasil=asli(*args);jumlah[0]+=1
        if jumlah[0]==2:
            with database.buka(k.db) as kon:kon.execute("UPDATE siswa SET pemilik='keluarga-baru' WHERE id=?",(k.sid,))
        return hasil
    monkeypatch.setattr(worker,'_snapshot',ganti)
    hasil=worker.jalankan(k.admin,k.auth,k.db,config=CFG,transport=transport(inv),sekarang=T0+4,sakelar=ON)
    assert hasil['dilewati']==1
    with admin_store.buka_baca(k.admin) as kon:
        assert kon.execute('SELECT count(*) FROM paket_grant').fetchone()[0]==0
        assert kon.execute('SELECT count(*) FROM paket_receipt').fetchone()[0]==0


def test_v1_tertunda_menahan_adopsi_v2(keluarga):
    from test_subscription_service import quote
    k=keluarga;inv=quote(k);admin_store.siapkan(k.admin,paket_v2=True)
    awal=isi(k.admin)
    with pytest.raises(lama.KonflikLangganan,match='tagihan lama'):
        paket.adopsi(k.admin,k.principal.id_akun,operasi_id='adopsi_sintetis',sekarang=T0+3,sakelar=ON)
    assert isi(k.admin)==awal
    lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=T0+3,sakelar=ON)
    paket.adopsi(k.admin,k.principal.id_akun,operasi_id='adopsi_sintetis',sekarang=T0+4,sakelar=ON)
    baru=invoice(k,kini=T0+5)
    with pytest.raises(lama.KonflikLangganan,match='lintas versi'):
        lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(baru),sekarang=T0+6,sakelar=ON)
    lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(baru,'trx_baru'),sekarang=T0+6,sakelar=ON)
    assert paket.baca(k.admin,k.principal.id_akun).grants[0]['mulai']==lama.baca(k.admin,k.principal.id_akun).grants[-1].periode.akhir
    with pytest.raises(lama.KonflikLangganan,match='v2'):
        lama.buat_invoice(k.admin,k.principal.id_akun,invoice_id='inv_'+'f'*32,idempotency_key='idem_v1_baru',
                          provider='midtrans',channel='qris',merchant=CFG.merchant,sekarang=T0+7,kedaluwarsa=T0+999,sakelar=ON)


@pytest.mark.parametrize('tabel',schema.TABEL)
@pytest.mark.parametrize('aksi',['update','delete','replace'])
def test_immutable_snapshot_sql(keluarga,tabel,aksi):
    k=keluarga;siapkan(k);inv=invoice(k)
    lama.terapkan_pembayaran(k.admin,k.principal.id_akun,bukti(inv),sekarang=T0+3,sakelar=ON)
    lama.catat_pengamatan(k.admin,k.principal.id_akun,inv['invoice_id'],operasi_id='amati_sintetis',
                          status='settlement',sekarang=T0+4,sakelar=ON)
    with sqlite3.connect(k.admin) as kon:
        assert kon.execute('SELECT count(*) FROM '+tabel).fetchone()[0]==1
        kolom=kon.execute('PRAGMA table_info('+tabel+')').fetchone()[1]
        sql={'update':'UPDATE '+tabel+' SET '+kolom+'='+kolom,
             'delete':'DELETE FROM '+tabel,
             'replace':'INSERT OR REPLACE INTO '+tabel+' SELECT * FROM '+tabel}[aksi]
        with pytest.raises(sqlite3.IntegrityError):kon.execute(sql)
