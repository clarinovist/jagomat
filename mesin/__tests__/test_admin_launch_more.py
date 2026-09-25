"""Batas negatif billing, mutu metrik, backup, dan retensi sintetis."""
from dataclasses import replace
import sqlite3

import pytest
import auth
import admin_store
import admin_subscription as b
import admin_operations as o
import product_analytics as d
import product_analytics_store as s
import subscription_store as ss
from test_subscription_service import keluarga, quote, transport
from test_admin_launch_domain import layanan, aktif
from test_subscription_store import ON,T0,dump
from test_midtrans_contract import CFG


def test_bayar_terlambat_bukan_akses_aktif(layanan):
    k=layanan;inv=quote(k)
    ss.reservasi_create(k.admin,k.principal.id_akun,inv['invoice_id'],sekarang=T0+3,sakelar=ON)
    hasil=b.periksa(k.admin,k.auth,k.db,k.admin_principal,akun_id=k.principal.id_akun,invoice_id=inv['invoice_id'],
                   target_revisi=k.principal.revisi_auth,operasi='late_admin_001',sekarang=T0+2000,
                   runtime=b.RuntimePembayaran(CFG,transport(inv),ON))
    assert hasil=='perlu_diperiksa'
    r=b.detail(k.admin,k.auth,k.admin_principal,k.principal.id_akun,sekarang=T0+2000)
    assert r['invoices'][0]['status']=='perlu_diperiksa' and not r['grants']
    assert o.antrean(k.admin)[1]>=1


@pytest.mark.parametrize('ubah',['target_reset','owner','sesi'])
def test_recheck_sesudah_network_tahan_grant(layanan,ubah):
    k=layanan;inv=quote(k)
    ss.reservasi_create(k.admin,k.principal.id_akun,inv['invoice_id'],sekarang=T0+3,sakelar=ON)
    tr=transport(inv)
    def network(req,**kw):
        if ubah=='target_reset':auth.naikkan_revisi_auth(k.principal.id_akun,k.auth)
        if ubah=='owner':
            with sqlite3.connect(k.db) as c:c.execute("UPDATE siswa SET pemilik='asing' WHERE id=?",(k.sid,))
        return tr(req,**kw)
    with pytest.raises(LookupError):
        b.periksa(k.admin,k.auth,k.db,k.admin_principal,akun_id=k.principal.id_akun,invoice_id=inv['invoice_id'],
                  target_revisi=k.principal.revisi_auth,operasi='recheck_admin_001',sekarang=T0+4,
                  runtime=b.RuntimePembayaran(CFG,network,ON),periksa_sesi=lambda:ubah!='sesi')
    assert not ss.baca(k.admin,k.principal.id_akun).grants


def test_tanpa_intent_tidak_network(layanan):
    k=layanan;inv=quote(k);tr=transport(inv)
    awal=dump(k.admin)
    with pytest.raises(ValueError,match='intent'):
        b.periksa(k.admin,k.auth,k.db,k.admin_principal,akun_id=k.principal.id_akun,invoice_id=inv['invoice_id'],
                  target_revisi=k.principal.revisi_auth,operasi='nointent_admin_001',sekarang=T0+4,
                  runtime=b.RuntimePembayaran(CFG,tr,ON))
    assert not tr.panggilan and dump(k.admin)==awal


def test_backup_missing_tidak_dinyatakan_sehat(layanan,monkeypatch):
    monkeypatch.setattr(o,'BUNDLE_BACKUP',None)
    monkeypatch.setattr(o.ai_service,'status_fitur',lambda _: (False,['key belum tersedia']))
    r=o.ringkasan(layanan.admin,sekarang=T0)
    assert r['backup']=='Belum terverifikasi' and r['backup_cutoff'] is None


def test_organik_denominator_unknown_dan_respons_minimum():
    acts=(('2026-01-01','latihan_dikirim',1),)
    p=[d.Peserta(T0+28*d.HARI,False,acts,True,'ya' if i<6 else '', 'rekomendasi' if i<6 else 'tidak_diketahui') for i in range(40)]
    r=d.hitung(p,mulai=T0,sekarang=T0+56*d.HARI,lengkap=True)
    assert (r.metrik[3].pembilang,r.metrik[3].penyebut)==(6,40)
    assert r.metrik[2].status=='Respons belum cukup'


def test_migrasi_admin6_preservasi_dan_missing_trigger(layanan):
    k=layanan
    import admin_launch_schema
    with sqlite3.connect(k.admin) as c:
        # Turunkan hanya fixture yang seluruh tabel layanan kosong; bentuk sumber6.
        for t in ('pembayaran_audit','pembayaran_konfigurasi','kpi_audit_biaya','kpi_biaya','kpi_survei','kpi_aktivitas','kpi_peserta','kpi_agregat','kpi_cakupan','kpi_eksperimen','layanan_operasi'):
            c.execute('DROP TABLE '+t)
        c.execute('PRAGMA user_version=6')
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(k.admin):pass
    admin_store.siapkan(k.admin)
    with admin_store.buka_baca(k.admin) as c:
        admin_launch_schema.validasi(c)
        assert tuple(c.execute("SELECT tahap,revisi FROM pembayaran_konfigurasi").fetchone())==('nonaktif',1)
        assert not c.execute('SELECT 1 FROM pembayaran_audit').fetchone()
    with sqlite3.connect(k.admin) as c:c.execute('DROP TRIGGER kpi_audit_tolak_delete')
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(k.admin):pass
