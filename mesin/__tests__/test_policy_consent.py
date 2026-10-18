"""Persetujuan awal synthetic: durable restart, pilihan, race dan restore."""
import pytest
import auth
import admin_store
import policy_store as s
import policy_schema
import policy_http as h
import sensor_store
from test_subscription_service import keluarga
from test_subscription_store import T0,dump


def simpan(k,**kw):
    args=dict(revisi=0,operasi='operasi_sintetis_0001',pilihan=(True,True,True),sekarang=T0,versi=s.VERSI)
    args.update(kw)
    return s.simpan(k.admin,k.auth,k.principal,**args)


def test_receipt_migrasi_idempoten_durable_dan_cabut(keluarga,monkeypatch):
    k=keluarga;policy_schema.migrasikan(k.admin);awal=dump(k.admin)
    policy_schema.migrasikan(k.admin);assert dump(k.admin)==awal
    simpan(k)
    row=s.baca(k.admin,k.principal.id_akun)
    assert s.berlaku(row)
    izin=sensor_store.izin(k.admin,k.principal.id_akun,sekarang=T0+1)
    assert izin and izin.hasil and izin.chat
    simpan(k)  # replay identik tidak menghapus event/menaikkan revisi
    assert s.baca(k.admin,k.principal.id_akun)['revisi']==1
    sensor_store.cabut(k.admin,k.auth,k.principal)
    assert s.berlaku(s.baca(k.admin,k.principal.id_akun))
    with pytest.raises(admin_store.KonflikOperasi):simpan(k)
    assert sensor_store.izin(k.admin,k.principal.id_akun,sekarang=T0+1) is None
    assert s.baca(k.admin,k.principal.id_akun)['alur']==0


def test_epoch_missing_restore_tidak_mewarisi(keluarga,monkeypatch):
    k=keluarga;policy_schema.migrasikan(k.admin);simpan(k)
    row=s.baca(k.admin,k.principal.id_akun)
    epoch=s.EPOCH
    monkeypatch.setattr(s,'EPOCH','f'*32);monkeypatch.setattr(sensor_store,'BOOT','f'*32)
    assert not s.berlaku(row)
    assert sensor_store.izin(k.admin,k.principal.id_akun,sekarang=T0+1) is None
    monkeypatch.setattr(s,'EPOCH','')
    with pytest.raises(ValueError):simpan(k,revisi=1,operasi='operasi_sintetis_0002')
    monkeypatch.setattr(s,'EPOCH',epoch);monkeypatch.setattr(sensor_store,'BOOT',epoch)
    assert s.berlaku(row)
    assert sensor_store.izin(k.admin,k.principal.id_akun,sekarang=T0+1)


def test_decline_dan_expiry_tidak_mengulang_terms(keluarga):
    k=keluarga;policy_schema.migrasikan(k.admin)
    simpan(k,pilihan=(False,False,False))
    assert s.berlaku(s.baca(k.admin,k.principal.id_akun))
    assert sensor_store.izin(k.admin,k.principal.id_akun,sekarang=T0+1) is None
    simpan(k,revisi=1,operasi='operasi_sintetis_0002')
    sensor_store.retensi(k.admin,sekarang=T0+90*86400)
    assert s.berlaku(s.baca(k.admin,k.principal.id_akun))


def test_replay_registrasi_tidak_mencoba_menulis(keluarga,monkeypatch):
    from types import SimpleNamespace
    import policy_http
    k=keluarga
    monkeypatch.setattr(policy_http,'tersedia',lambda:True)
    def tolak(*a,**kw):raise AssertionError('replay mencoba menulis consent')
    monkeypatch.setattr(s,'simpan',tolak)
    akun=SimpleNamespace(baru=False,pengguna=k.principal.pengguna,peran='guru',id_akun=k.principal.id_akun,revisi_auth=1)
    policy_http.setelah_daftar(akun,{'policy_versi':s.VERSI,'policy_epoch':s.EPOCH,'policy_aksi':'semua'})


def test_pilihan_versi_dan_nonretroactive(keluarga):
    k=keluarga;policy_schema.migrasikan(k.admin)
    assert h.pilihan({'policy_versi':s.VERSI,'policy_epoch':s.EPOCH,'policy_aksi':'semua'})==(True,True,True)
    assert h.pilihan({'policy_versi':s.VERSI,'policy_epoch':s.EPOCH,'policy_aksi':'pilihan'})==(False,False,False)
    with pytest.raises(ValueError):h.pilihan({'policy_versi':'lama','policy_aksi':'semua'})
    with pytest.raises(ValueError):simpan(k,pilihan=(False,True,True))
    simpan(k)
    izin=sensor_store.izin(k.admin,k.principal.id_akun,sekarang=T0+1)
    assert not sensor_store.catat_sesi(k.admin,izin,1,kode='disiapkan',dibuat=T0-1,jalur='manual',sekarang=T0+1)
