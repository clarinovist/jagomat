"""Kontrak layanan admin memakai auth/database/provider sintetis."""

from dataclasses import replace
import json
import sqlite3

import pytest
import auth
import admin_store
import admin_launch_schema
import admin_launch_service as guard
import admin_subscription as billing
import product_analytics as metrik
import product_analytics_store as kpi
import subscription_store
from test_subscription_service import keluarga, quote, transport
from test_subscription_store import T0, ON, dump
from test_midtrans_contract import CFG


@pytest.fixture
def layanan(keluarga,monkeypatch):
    monkeypatch.setattr(kpi,'PENCATATAN_GAGAL',False)
    k=keluarga
    auth.tambah_akun('Pengelola-sintetis','sandi-pengelola-123','admin',k.auth)
    k.admin_principal=auth.autentikasi('Pengelola-sintetis','sandi-pengelola-123',k.auth)
    return k


def aktif(k):
    kpi.atur_eksperimen(k.admin,k.auth,k.admin_principal,operasi='eksperimen_uji_001',
                        mulai=T0,aktif=True,revisi=0,sekarang=T0)


def test_schema_additive_tanpa_enrollment(keluarga):
    k=keluarga
    with admin_store.buka_baca(k.admin) as c:
        admin_launch_schema.validasi(c)
        assert c.execute('PRAGMA user_version').fetchone()[0]==7
        assert not c.execute('SELECT 1 FROM kpi_peserta').fetchone()
    awal=dump(k.admin)
    admin_store.siapkan(k.admin)
    assert dump(k.admin)==awal


def test_reader_sakelar_missing_fail_closed(tmp_path):
    assert billing.sakelar_runtime(tmp_path/'missing.db')==__import__('subscription').SAKELAR
    assert not (tmp_path/'missing.db').exists()


def test_sakelar_pembayaran_bertahap_audit_dan_fail_closed(layanan):
    k=layanan
    siap=dict(provider_produksi=True,callback=True,recovery=True,kebijakan=True)
    with admin_store.buka_baca(k.admin) as c:
        assert guard.konfigurasi_pembayaran(c)['tahap']=='nonaktif'
        assert guard.sakelar_pembayaran(c)==__import__('subscription').Sakelar()
    tahap=('rekonsiliasi','checkout','penegakan')
    revisi=1
    for nomor,nama in enumerate(tahap,1):
        hasil=guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
            operasi='sakelar_admin_%03d'%nomor,tahap=nama,revisi=revisi,
            kesiapan=siap,sekarang=T0+nomor)
        revisi=hasil['revisi']
    with admin_store.buka_baca(k.admin) as c:
        assert guard.sakelar_pembayaran(c)==__import__('subscription').Sakelar(True,True,True,True)
        assert c.execute('SELECT COUNT(*) FROM pembayaran_audit').fetchone()[0]==3
    hasil=guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
        operasi='sakelar_admin_turun',tahap='rekonsiliasi',revisi=revisi,
        kesiapan=siap,sekarang=T0+4)
    assert hasil['tahap']=='rekonsiliasi'
    with admin_store.buka_baca(k.admin) as c:
        assert guard.sakelar_pembayaran(c)==__import__('subscription').Sakelar(True,False,True,False)
        sebelum=c.execute('SELECT COUNT(*) FROM pembayaran_audit').fetchone()[0]
    # Replay operasi selesai mengembalikan hasil yang sama tanpa audit kedua.
    assert guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
        operasi='sakelar_admin_turun',tahap='rekonsiliasi',revisi=revisi,
        kesiapan=siap,sekarang=T0+5)['tahap']=='rekonsiliasi'
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute('SELECT COUNT(*) FROM pembayaran_audit').fetchone()[0]==sebelum
    # Saat provider/callback jatuh, admin tetap boleh menurunkan checkout ke
    # rekonsiliasi agar transaksi in-flight dapat diperiksa tanpa create baru.
    guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
        operasi='sakelar_admin_naik_ulang',tahap='checkout',revisi=hasil['revisi'],
        kesiapan=siap,sekarang=T0+6)
    turun=guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
        operasi='sakelar_admin_insiden',tahap='rekonsiliasi',revisi=hasil['revisi']+1,
        kesiapan={k:False for k in siap},sekarang=T0+7)
    assert turun['tahap']=='rekonsiliasi'
    with sqlite3.connect(k.admin) as c:
        with pytest.raises(sqlite3.IntegrityError):
            c.execute('DELETE FROM pembayaran_audit')


def test_sakelar_pembayaran_gate_urutan_revisi_dan_auth(layanan):
    k=layanan
    siap=dict(provider_produksi=True,callback=True,recovery=True,kebijakan=True)
    with pytest.raises(ValueError,match='berurutan'):
        guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,operasi='skip_admin_001',
            tahap='checkout',revisi=1,kesiapan=siap,sekarang=T0)
    for field in siap:
        kondisi=dict(siap); kondisi[field]=False
        target={'provider_produksi':'rekonsiliasi','callback':'checkout','recovery':'checkout','kebijakan':'penegakan'}[field]
        if target!='rekonsiliasi':
            guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
                operasi='prep_'+field,tahap='rekonsiliasi',revisi=1,kesiapan=siap,sekarang=T0)
            revisi=2
            if target=='penegakan':
                guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
                    operasi='prep2_'+field,tahap='checkout',revisi=revisi,kesiapan=siap,sekarang=T0+1)
                revisi=3
        else: revisi=1
        with pytest.raises(ValueError):
            guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,
                operasi='gate_'+field,tahap=target,revisi=revisi,kesiapan=kondisi,sekarang=T0+2)
        # Kembalikan fixture khusus iterasi dengan penurunan legal.
        with admin_store._transaksi(k.admin) as c:
            c.execute("UPDATE pembayaran_konfigurasi SET tahap='nonaktif',revisi=1")
            c.execute("DELETE FROM layanan_operasi")
    with admin_store.buka_baca(k.admin) as c:
        assert guard.konfigurasi_pembayaran(c)['tahap']=='nonaktif'
        # Empat persiapan sukses diaudit meski fixture config diturunkan lagi.
        assert c.execute('SELECT COUNT(*) FROM pembayaran_audit').fetchone()[0]==4
    with pytest.raises(admin_store.KonflikOperasi):
        guard.atur_pembayaran(k.admin,k.auth,k.admin_principal,operasi='stale_admin_001',
            tahap='nonaktif',revisi=99,kesiapan=siap,sekarang=T0)
    with pytest.raises(LookupError):
        guard.atur_pembayaran(k.admin,k.auth,k.principal,operasi='guru_admin_001',
            tahap='rekonsiliasi',revisi=1,kesiapan=siap,sekarang=T0)


def test_metrik_100_cohort_survei_dan_retensi():
    peserta=[]
    for i in range(100):
        acts=[]
        if i<65: acts.append(('2026-01-01','latihan_dikirim',1))
        if i<28: acts.append(('2026-01-08','panduan_hasil_disajikan',2))
        peserta.append(metrik.Peserta(T0,False,tuple(acts),i<65,'ya' if i<23 else 'belum' if i<30 else ''))
    r=metrik.hitung(peserta,mulai=T0,sekarang=T0+14*86400,lengkap=True)
    a,b,c,_=r.metrik
    assert (a.pembilang,a.penyebut)==(65,100)
    assert (b.pembilang,b.penyebut)==(28,100)
    assert (c.pembilang,c.penyebut,c.respons,c.penawaran)==(23,30,30,65)
    assert c.status=='Target tercapai'
    r=metrik.hitung(peserta,mulai=T0,sekarang=T0+14*86400,lengkap=False)
    assert all(m.status=='Data belum lengkap' for m in r.metrik)


def test_maturity_jendela_dan_kelompok_kecil():
    assert [metrik.jendela(T0,T0+x*86400) for x in [0,7,14,30]]==[1,2,3,None]
    p=metrik.Peserta(T0,False,(('2026-01-01','latihan_dikirim',1),))
    assert metrik.hitung([p],mulai=T0,sekarang=T0+14*86400-1,lengkap=True).matang==0
    r=metrik.hitung([p],mulai=T0,sekarang=T0+14*86400,lengkap=True)
    assert r.matang==1 and r.metrik[0].kecil and r.minggu==()


def test_consent_dedup_cabut_tidak_menyentuh_belajar(layanan):
    k=layanan;aktif(k)
    awal=(k.auth.read_bytes(),k.db.read_bytes())
    kpi.catat(k.admin,k.principal.id_akun,kode='latihan_dikirim',sekarang=T0+1)
    assert kpi.laporan(k.admin,sekarang=T0+14*86400,bulan='2026-01')[1].peserta==0
    kpi.setuju(k.admin,k.auth,k.principal,sumber='rekomendasi',sekarang=T0,saat_daftar=True)
    for _ in range(2):
        kpi.catat(k.admin,k.principal.id_akun,kode='latihan_dikirim',sekarang=T0+1)
    assert kpi.survei(k.admin,k.auth,k.principal,sekarang=T0+2)
    assert kpi.survei(k.admin,k.auth,k.principal,sekarang=T0+3,jawaban='ya')
    with pytest.raises(admin_store.KonflikOperasi):
        kpi.survei(k.admin,k.auth,k.principal,sekarang=T0+4,jawaban='belum')
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute('SELECT COUNT(*) FROM kpi_aktivitas').fetchone()[0]==1
    kpi.cabut(k.admin,k.auth,k.principal)
    kpi.catat(k.admin,k.principal.id_akun,kode='latihan_dikirim',sekarang=T0+5)
    with admin_store.buka_baca(k.admin) as c:
        for t in ('kpi_peserta','kpi_aktivitas','kpi_survei'):
            assert not c.execute('SELECT 1 FROM '+t).fetchone()
    assert (k.auth.read_bytes(),k.db.read_bytes())==awal


@pytest.mark.parametrize('jenis',['guru','stale','murid'])
def test_otorisasi_admin_tolak_tanpa_tulis(layanan,jenis):
    k=layanan;p=k.admin_principal
    if jenis=='guru': p=k.principal
    elif jenis=='stale': p=replace(p,revisi_auth=99)
    else: p=replace(p,peran='murid')
    awal=dump(k.admin)
    with pytest.raises(LookupError):
        kpi.atur_eksperimen(k.admin,k.auth,p,operasi='eksperimen_ditolak',mulai=T0,aktif=True,revisi=0,sekarang=T0)
    with pytest.raises(LookupError):
        billing.daftar(k.admin,k.auth,p)
    assert dump(k.admin)==awal


def test_biaya_replay_revisi_dan_negatif(layanan):
    k=layanan;n=dict(anggaran=475000,server=200000,domain=25000,ai=120000,pendukung=0,lengkap=True)
    arg=dict(operasi='biaya_uji_001',bulan='2026-01',revisi=0,nilai=n,sekarang=T0)
    for _ in range(2): kpi.simpan_biaya(k.admin,k.auth,k.admin_principal,**arg)
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute('SELECT COUNT(*) FROM kpi_audit_biaya').fetchone()[0]==1
    with pytest.raises(admin_store.KonflikOperasi):
        kpi.simpan_biaya(k.admin,k.auth,k.admin_principal,**{**arg,'operasi':'biaya_stale_002'})
    with pytest.raises(ValueError):
        kpi.simpan_biaya(k.admin,k.auth,k.admin_principal,**{**arg,'nilai':{**n,'ai':-1}})


def test_restart_dan_gagal_pencatatan_tidak_hijau(layanan,monkeypatch):
    k=layanan;aktif(k)
    assert kpi.laporan(k.admin,sekarang=T0,bulan='2026-01')[1].kualitas
    monkeypatch.setattr(kpi,'BOOT_ID','restart-sintetis')
    assert not kpi.laporan(k.admin,sekarang=T0,bulan='2026-01')[1].kualitas
    kpi.gangguan(k.admin)
    assert not kpi.laporan(k.admin,sekarang=T0,bulan='2026-01')[1].kualitas


def test_reader_billing_no_write_dan_settlement_admin_idempoten(layanan):
    k=layanan;inv=quote(k)
    subscription_store.reservasi_create(k.admin,k.principal.id_akun,inv['invoice_id'],sekarang=T0+3,sakelar=ON)
    before=dump(k.admin)
    r=billing.detail(k.admin,k.auth,k.admin_principal,k.principal.id_akun,sekarang=T0+3)
    assert r['invoices'][0]['dapat_periksa'] and r['akses'].status=='trial'
    assert dump(k.admin)==before
    tr=transport(inv)
    arg=dict(akun_id=k.principal.id_akun,invoice_id=inv['invoice_id'],target_revisi=k.principal.revisi_auth,
             operasi='periksa_admin_001',sekarang=T0+4,runtime=billing.RuntimePembayaran(CFG,tr,ON))
    for _ in range(2):
        assert billing.periksa(k.admin,k.auth,k.db,k.admin_principal,**arg)=='grant'
    assert [r.metode for r in tr.panggilan]==['GET']
    assert len(subscription_store.baca(k.admin,k.principal.id_akun).grants)==1


def test_reset_admin_saat_network_tidak_grant(layanan):
    k=layanan;inv=quote(k)
    subscription_store.reservasi_create(k.admin,k.principal.id_akun,inv['invoice_id'],sekarang=T0+3,sakelar=ON)
    tr=transport(inv)
    def outbound(req,**kw):
        # Mutasi fixture sendiri; proses network tidak menahan lock auth/DB.
        raw=json.loads(k.auth.read_text())
        for a in raw['akun']:
            if a['id_akun']==k.admin_principal.id_akun: a['revisi_auth']+=1
        k.auth.write_text(json.dumps(raw))
        return tr(req,**kw)
    with pytest.raises(LookupError):
        billing.periksa(k.admin,k.auth,k.db,k.admin_principal,akun_id=k.principal.id_akun,
                        invoice_id=inv['invoice_id'],target_revisi=k.principal.revisi_auth,
                        operasi='periksa_race_001',sekarang=T0+4,runtime=billing.RuntimePembayaran(CFG,outbound,ON))
    assert not subscription_store.baca(k.admin,k.principal.id_akun).grants


def _rekonsiliasi(k):
    # Jalur transisi produksi berjalan pada admin9; fixture lama dinaikkan
    # eksplisit agar pengujian adopsi paket tidak menyamarkan schema absen.
    admin_store.siapkan(k.admin, paket_v2=True, sekarang=T0)
    admin_store.migrasikan_kuota_pendamping(k.admin)
    with admin_store._transaksi(k.admin) as c:
        c.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")


def test_transisi_aktifkan_audit_idempoten_dan_kandidat(layanan):
    k=layanan;_rekonsiliasi(k)
    auth.tambah_akun('kandidat-sintetis','sandi-kandidat-123','guru',k.auth)
    akun=auth.cari_akun('kandidat-sintetis',k.auth)
    revisi=auth.revisi_auth(akun)
    assert billing.kandidat_transisi(k.admin,k.auth,k.admin_principal,cari='kandidat')==(
        {'akun_id':akun['id_akun'],'alias':'kandidat-sintetis','revisi':revisi},)
    assert billing.kandidat_transisi(k.admin,k.auth,k.admin_principal,cari='tidak-ada')==()
    p=dict(operasi='op_'+'a'*32,akun_id=akun['id_akun'],target_revisi=revisi,sekarang=T0+7)
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,**p)=='diaktifkan'
    e=subscription_store.baca(k.admin,akun['id_akun']).enrollment
    assert e.mulai==T0+7 and not e.peserta_promo
    with admin_store.buka_baca(k.admin) as c:
        baris=c.execute("SELECT asal,sumber_id FROM langganan_enrollment WHERE akun_id=?",(akun['id_akun'],)).fetchone()
        paket=c.execute("SELECT operasi_id,versi,mulai FROM paket_akun WHERE akun_id=?",(akun['id_akun'],)).fetchone()
        assert (baris['asal'],baris['sumber_id'])==('transisi',p['operasi'])
        assert tuple(paket)==(p['operasi'],'paket-jago-v2',T0+7)
        # Provenance tanpa jurnal layanan_operasi (CHECK aksi ter-pin kontrak).
        assert c.execute("SELECT COUNT(*) FROM layanan_operasi").fetchone()[0]==0
    # Replay operasi sama: hasil sama, tanpa baris kedua.
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,**p)=='diaktifkan'
    # Operasi baru untuk akun yang sama: idempoten 'sudah_terdaftar'.
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,
        **{**p,'operasi':'op_'+'b'*32})=='sudah_terdaftar','idempotensi transisi'
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute("SELECT COUNT(*) FROM langganan_enrollment").fetchone()[0]==1
        assert c.execute("SELECT COUNT(*) FROM paket_akun").fetchone()[0]==1
    assert billing.kandidat_transisi(k.admin,k.auth,k.admin_principal,cari='kandidat')==()


def test_transisi_akun_legacy_revisi_nol_diterima(layanan):
    k=layanan;_rekonsiliasi(k)
    auth.tambah_akun('kandidat-legacy','sandi-kandidat-123','guru',k.auth)
    raw=json.loads(k.auth.read_text())
    for a in raw['akun']:
        if a.get('pengguna')=='kandidat-legacy':
            a.pop('revisi_auth',None)
    k.auth.write_text(json.dumps(raw))
    akun=auth.cari_akun('kandidat-legacy',k.auth)
    assert auth.revisi_auth(akun)==0
    kand=billing.kandidat_transisi(k.admin,k.auth,k.admin_principal,cari='kandidat-legacy')
    assert kand and kand[0]['revisi']==0
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,
        operasi='op_'+'9'*32,akun_id=akun['id_akun'],target_revisi=0,
        sekarang=T0+7)=='diaktifkan','akun legacy revisi nol'
    assert subscription_store.baca(k.admin,akun['id_akun']).enrollment.mulai==T0+7


def test_transisi_guard_tanpa_mutasi(layanan):
    k=layanan
    auth.tambah_akun('kandidat-2','sandi-kandidat-123','guru',k.auth)
    auth.tambah_akun('kandidat-3','sandi-kandidat-123','guru',k.auth)
    akun=auth.cari_akun('kandidat-2',k.auth)
    akun3=auth.cari_akun('kandidat-3',k.auth)
    revisi=auth.revisi_auth(akun)
    p=k.admin_principal
    # Sakelar fondasi OFF: tanpa enrollment.
    awal=dump(k.admin)
    with pytest.raises(__import__('subscription').FiturNonaktif):
        guard.aktifkan_transisi(k.admin,k.auth,p,operasi='op_'+'c'*32,
            akun_id=akun['id_akun'],target_revisi=revisi,sekarang=T0+7)
    assert dump(k.admin)==awal
    _rekonsiliasi(k)
    dasar=dump(k.admin)
    with pytest.raises(LookupError):
        guard.aktifkan_transisi(k.admin,k.auth,p,operasi='op_'+'d'*32,
            akun_id=p.id_akun,target_revisi=p.revisi_auth,sekarang=T0+8)
    with pytest.raises(LookupError):
        guard.aktifkan_transisi(k.admin,k.auth,p,operasi='op_'+'e'*32,
            akun_id=akun['id_akun'],target_revisi=revisi+1,sekarang=T0+8)
    with pytest.raises(LookupError):
        guard.aktifkan_transisi(k.admin,k.auth,replace(p,revisi_auth=99),
            operasi='op_'+'f'*32,akun_id=akun['id_akun'],target_revisi=revisi,sekarang=T0+8)
    assert dump(k.admin)==dasar
    ok=dict(operasi='op_'+'1'*32,akun_id=akun['id_akun'],target_revisi=revisi,sekarang=T0+9)
    assert guard.aktifkan_transisi(k.admin,k.auth,p,**ok)=='diaktifkan'
    # Operasi lain setelah enrollment ada: tanpa penulisan kedua.
    assert guard.aktifkan_transisi(k.admin,k.auth,p,
        **{**ok,'operasi':'op_'+'3'*32})=='sudah_terdaftar'
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute("SELECT COUNT(*) FROM langganan_enrollment").fetchone()[0]==1
    # Otorisasi: principal non-admin tidak boleh membaca kandidat atau mengaktifkan.
    with pytest.raises(LookupError):
        billing.kandidat_transisi(k.admin,k.auth,k.principal,cari='kandidat')
    with pytest.raises(LookupError):
        guard.aktifkan_transisi(k.admin,k.auth,k.principal,operasi='op_'+'2'*32,
            akun_id=akun3['id_akun'],target_revisi=auth.revisi_auth(akun3),sekarang=T0+10)


def test_transisi_admin7_legacy_tanpa_ledger_paket(layanan):
    """Kompatibilitas legacy: schema7 enroll saja; bukan jalur adopsi produksi."""
    k=layanan
    auth.tambah_akun('kandidat-legacy7','sandi-kandidat-123','guru',k.auth)
    akun=auth.cari_akun('kandidat-legacy7',k.auth)
    assert akun is not None
    with admin_store._transaksi(k.admin) as c:
        c.execute("UPDATE pembayaran_konfigurasi SET tahap='rekonsiliasi'")
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==7
        assert not subscription_store.paket_schema.tersedia(c)
    revisi=auth.revisi_auth(akun)
    p=dict(operasi='op_'+'7'*32,akun_id=akun['id_akun'],target_revisi=revisi,sekarang=T0+7)
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,**p)=='diaktifkan'
    e=subscription_store.baca(k.admin,akun['id_akun']).enrollment
    assert e.mulai==T0+7 and not e.peserta_promo
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,**p)=='diaktifkan'
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,
        **{**p,'operasi':'op_'+'8'*32})=='sudah_terdaftar'
    # Tidak ada tabel/adopsi paket di legacy dan tidak ada tagihan/kuota baru.
    assert billing.kandidat_transisi(k.admin,k.auth,k.admin_principal,cari='legacy7')==()
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute("SELECT COUNT(*) FROM langganan_enrollment WHERE akun_id=?",
                         (akun['id_akun'],)).fetchone()[0]==1
        assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='paket_akun'").fetchone()
        assert c.execute("SELECT COUNT(*) FROM langganan_invoice").fetchone()[0]==0
        assert c.execute("SELECT COUNT(*) FROM langganan_grant").fetchone()[0]==0


def test_transisi_admin9_crash_enrollment_ke_paket_replay_tanpa_ganda(layanan,monkeypatch):
    """Jalur produksi admin9 wajib paket; replay melengkapi tanpa trial/invoice ganda."""
    import subscription_package_store as paket_store
    k=layanan;_rekonsiliasi(k)
    auth.tambah_akun('kandidat-crash','sandi-kandidat-123','guru',k.auth)
    akun=auth.cari_akun('kandidat-crash',k.auth)
    assert akun is not None
    revisi=auth.revisi_auth(akun)
    p=dict(operasi='op_'+'4'*32,akun_id=akun['id_akun'],target_revisi=revisi,sekarang=T0+7)
    asli=paket_store.adopsi
    def crash(*a,**kw): raise RuntimeError('crash sintetis sebelum adopsi commit')
    monkeypatch.setattr(paket_store,'adopsi',crash)
    with pytest.raises(RuntimeError):
        guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,**p)
    monkeypatch.setattr(paket_store,'adopsi',asli)
    # Enrollment sudah commit, paket belum: kandidat masih ditawarkan, tanpa tagihan.
    assert subscription_store.baca(k.admin,akun['id_akun']).enrollment.mulai==T0+7
    assert billing.kandidat_transisi(k.admin,k.auth,k.admin_principal,cari='crash')==(
        {'akun_id':akun['id_akun'],'alias':'kandidat-crash','revisi':revisi},)
    with admin_store.buka_baca(k.admin) as c:
        assert not c.execute("SELECT 1 FROM paket_akun WHERE akun_id=?",(akun['id_akun'],)).fetchone()
        assert c.execute("SELECT COUNT(*) FROM langganan_invoice").fetchone()[0]==0
        assert c.execute("SELECT COUNT(*) FROM langganan_grant").fetchone()[0]==0
    # Replay operasi sama: paket dilengkapi tepat sekali, trial tidak diulang.
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,**p)=='diaktifkan'
    assert subscription_store.baca(k.admin,akun['id_akun']).enrollment.mulai==T0+7
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute("SELECT COUNT(*) FROM langganan_enrollment WHERE akun_id=?",
                         (akun['id_akun'],)).fetchone()[0]==1
        paket=c.execute("SELECT operasi_id,versi,mulai FROM paket_akun WHERE akun_id=?",
                        (akun['id_akun'],)).fetchone()
        assert tuple(paket)==(p['operasi'],'paket-jago-v2',T0+7)
        assert c.execute("SELECT COUNT(*) FROM langganan_invoice").fetchone()[0]==0
        assert c.execute("SELECT COUNT(*) FROM langganan_grant").fetchone()[0]==0
    # Idempoten setelah lengkap: tanpa baris kedua; kandidat bersih.
    assert guard.aktifkan_transisi(k.admin,k.auth,k.admin_principal,**p)=='diaktifkan'
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute("SELECT COUNT(*) FROM paket_akun").fetchone()[0]==1
        assert c.execute("SELECT COUNT(*) FROM langganan_enrollment").fetchone()[0]==1
    assert billing.kandidat_transisi(k.admin,k.auth,k.admin_principal,cari='crash')==()


def test_tutup_tagihan_otorisasi_sakelar_dan_replay(layanan):
    """Service: hanya admin hidup; snapshot exact; fondasi wajib; replay aman."""
    k=layanan; inv=quote(k)
    admin_store.siapkan(k.admin,paket_v2=True)
    admin_store.migrasikan_penutupan_tagihan(k.admin)
    args=dict(operasi='op_'+'8'*32,akun_id=k.principal.id_akun,invoice_id=inv['invoice_id'],
              target_revisi=k.principal.revisi_auth)
    auth_awal=k.auth.read_bytes()
    with pytest.raises(LookupError):
        guard.tutup_tagihan(k.admin,k.auth,k.principal,sekarang=T0+1000,sakelar=ON,**args)
    with pytest.raises(LookupError):
        guard.tutup_tagihan(k.admin,k.auth,k.admin_principal,sekarang=T0+1000,sakelar=ON,
                            **{**args,'target_revisi':k.principal.revisi_auth+1})
    with pytest.raises(LookupError):
        guard.tutup_tagihan(k.admin,k.auth,k.admin_principal,sekarang=T0+1000,sakelar=ON,
                            **{**args,'invoice_id':'inv_'+'f'*32})
    with pytest.raises(__import__('subscription').FiturNonaktif):
        guard.tutup_tagihan(k.admin,k.auth,k.admin_principal,sekarang=T0+1000,**args)
    assert k.auth.read_bytes()==auth_awal
    with admin_store.buka_baca(k.admin) as c:
        assert not c.execute('SELECT 1 FROM penutupan_tagihan').fetchone()
    assert guard.tutup_tagihan(k.admin,k.auth,k.admin_principal,sekarang=T0+1000,sakelar=ON,**args)=='ditutup'
    assert guard.tutup_tagihan(k.admin,k.auth,k.admin_principal,sekarang=T0+1001,sakelar=ON,**args)=='ditutup'
    assert k.auth.read_bytes()==auth_awal
    import subscription_package_store as paket
    with admin_store.buka_baca(k.admin) as c:
        baris=c.execute('SELECT operasi_id,invoice_id,akun_id,actor_id,actor_revisi,alasan FROM penutupan_tagihan').fetchall()
        assert len(baris)==1
        assert tuple(baris[0])[:5]==('op_'+'8'*32,inv['invoice_id'],k.principal.id_akun,
                                     k.admin_principal.id_akun,k.admin_principal.revisi_auth)
    paket.adopsi(k.admin,k.principal.id_akun,operasi_id='adopsi_sintetis',sekarang=T0+1002,sakelar=ON)
