"""Kualitas, retensi, dan pemulihan consent tidak bergantung akun nyata."""

import sqlite3
from datetime import datetime

import pytest
import admin_store
import product_analytics as d
import product_analytics_store as s
from test_admin_launch_domain import layanan, aktif
from test_subscription_service import keluarga
from test_subscription_store import T0


def test_restore_boot_tidak_mewarisi_consent(layanan,monkeypatch):
    k=layanan;aktif(k)
    s.setuju(k.admin,k.auth,k.principal,sumber='rekomendasi',sekarang=T0,saat_daftar=True)
    s.catat(k.admin,k.principal.id_akun,kode='latihan_dikirim',sekarang=T0+1)
    monkeypatch.setattr(s,'BOOT_ID','boot-baru-sintetis')
    assert not s.laporan(k.admin,sekarang=T0+14*d.HARI,bulan='2026-09')[1].kualitas
    assert s.laporan(k.admin,sekarang=T0+14*d.HARI,bulan='2026-09')[1].peserta==0
    s.atur_eksperimen(k.admin,k.auth,k.admin_principal,operasi='aktif_ulang_001',mulai=T0,aktif=True,revisi=1,sekarang=T0+2)
    s.catat(k.admin,k.principal.id_akun,kode='lembar_soal_disajikan',sekarang=T0+3)
    with admin_store.buka_baca(k.admin) as c:
        assert c.execute('SELECT COUNT(*) FROM kpi_aktivitas').fetchone()[0]==1
    # Persetujuan ulang tidak menghidupkan aktivitas dari backup.
    s.setuju(k.admin,k.auth,k.principal,sumber='tidak_diketahui',sekarang=T0+4)
    s.catat(k.admin,k.principal.id_akun,kode='lembar_soal_disajikan',sekarang=T0+5)
    with admin_store.buka_baca(k.admin) as c:
        assert [r[0] for r in c.execute('SELECT kode FROM kpi_aktivitas')]==['lembar_soal_disajikan']
        assert c.execute('SELECT terlambat FROM kpi_peserta').fetchone()[0]==1


def test_retensi_agregat_no_mapping_minimal5(layanan):
    k=layanan;aktif(k)
    with admin_store._transaksi(k.admin) as c:
        for i in range(5):
            c.execute("INSERT INTO kpi_peserta VALUES(?, 'uji-coba-v1',?, ?,?,'analitik-keluarga-v1',?,'rekomendasi',0)",
                      ('peserta_'+str(i),'akun_'+format(i,'032x'),T0,T0,s.BOOT_ID))
            c.execute("INSERT INTO kpi_aktivitas VALUES(?,?,'latihan_dikirim',1)",('peserta_'+str(i),d.hari_wib(T0)))
    s.retensi(k.admin,sekarang=T0+90*d.HARI)
    with admin_store.buka_baca(k.admin) as c:
        assert not c.execute('SELECT 1 FROM kpi_peserta').fetchone()
        agregat=dict(c.execute('SELECT * FROM kpi_agregat').fetchone())
        assert agregat['peserta']==agregat['aktivasi']==5
        assert not {'akun_id','peserta_id','nama'} & set(agregat)
    assert not s.laporan(k.admin,sekarang=T0+90*d.HARI,bulan='2026-09')[1].kualitas
    s.retensi(k.admin,sekarang=agregat['hapus_setelah'])
    with admin_store.buka_baca(k.admin) as c:
        assert not c.execute('SELECT 1 FROM kpi_agregat').fetchone()


def test_gagal_sink_dan_konfigurasi_tidak_bisa_hijau_lagi(layanan,monkeypatch):
    k=layanan;aktif(k)
    asli=s._transaksi
    def gagal(*args): raise sqlite3.OperationalError('sink gagal sintetis')
    monkeypatch.setattr(s,'_transaksi',gagal)
    with pytest.raises(sqlite3.Error):s.gangguan(k.admin)
    monkeypatch.setattr(s,'_transaksi',asli)
    assert not s.laporan(k.admin,sekarang=T0,bulan='2026-09')[1].kualitas


def test_ttl_agregat_duabelas_bulan_kabisat():
    awal=int(datetime(2024,2,29,12,tzinfo=d.WIB).timestamp())
    akhir=int(datetime(2025,2,28,12,tzinfo=d.WIB).timestamp())
    assert d.akhir_retensi_agregat(awal)==akhir
