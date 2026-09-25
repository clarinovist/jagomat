"""Probe sintetis admin7; output agregat dan network-none."""

SUMBER_UJI_LAYANAN = r'''
def uji_layanan(akar):
    from pathlib import Path
    import sqlite3
    import admin_store, admin_launch_schema, admin_launch_service, auth
    import product_analytics_store as kpi
    import product_analytics as domain
    akar=Path(akar)
    akar.mkdir(parents=True,exist_ok=True)
    pa,ph=akar/'admin.db',akar/'auth.json'
    admin_store.siapkan(pa,sekarang=1)
    auth.tambah_akun('admin-probe','sandi-probe-sintetis','admin',ph)
    principal=auth.autentikasi('admin-probe','sandi-probe-sintetis',ph)
    with admin_store.buka_baca(pa) as kon:
        assert kon.execute('PRAGMA user_version').fetchone()[0]==7
        admin_launch_schema.validasi(kon)
        assert admin_launch_service.konfigurasi_pembayaran(kon)['tahap']=='nonaktif'
        assert admin_launch_service.sakelar_pembayaran(kon).rekonsiliasi is False
        assert not kon.execute('SELECT 1 FROM pembayaran_audit').fetchone()
        assert not kon.execute('SELECT 1 FROM kpi_peserta').fetchone()
    nilai=dict(anggaran=475000,server=200000,domain=25000,ai=0,pendukung=0,lengkap=False)
    for _ in range(2):
        kpi.simpan_biaya(pa,ph,principal,operasi='biaya_probe_001',bulan='2026-09',revisi=0,nilai=nilai,sekarang=1)
    with admin_store.buka_baca(pa) as kon:
        assert kon.execute('SELECT COUNT(*) FROM kpi_audit_biaya').fetchone()[0]==1
        assert not kon.execute('PRAGMA foreign_key_check').fetchall()
    r=domain.hitung([domain.Peserta(1,False,(('2026-09-01','latihan_dikirim',1),))],mulai=1,sekarang=1+14*86400,lengkap=False)
    assert r.metrik[0].status=='Data belum lengkap'
    return 4
'''
