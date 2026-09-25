"""Recovery admin7: replay biaya, consent lama tertahan, dan retensi tanpa data asli."""

SUMBER_TULIS = r'''
import auth, admin_store, admin_launch_service as layanan, product_analytics_store as kpi
import json, sqlite3
from pathlib import Path
root_launch = Path('/data/admin-launch-pair')
root_launch.mkdir(exist_ok=True)
p_launch = root_launch/'admin.db'
a_launch = root_launch/'auth.json'
admin_store.siapkan(p_launch,sekarang=1)
auth.tambah_akun('admin-layanan','sandi-pair-sintetis','admin',a_launch)
p_launch_actor=auth.autentikasi('admin-layanan','sandi-pair-sintetis',a_launch)
nilai_launch=dict(anggaran=475000,server=200000,domain=25000,ai=0,pendukung=0,lengkap=False)
kpi.simpan_biaya(p_launch,a_launch,p_launch_actor,operasi='pair_biaya_001',bulan='2026-09',revisi=0,nilai=nilai_launch,sekarang=1)
kpi.atur_eksperimen(p_launch,a_launch,p_launch_actor,operasi='pair_config_001',mulai=1,aktif=True,revisi=0,sekarang=1)
siap_launch=dict(provider_produksi=True,callback=True,recovery=True,kebijakan=True)
layanan.atur_pembayaran(p_launch,a_launch,p_launch_actor,operasi='pair_sakelar_001',tahap='rekonsiliasi',revisi=1,kesiapan=siap_launch,sekarang=1)
layanan.atur_pembayaran(p_launch,a_launch,p_launch_actor,operasi='pair_sakelar_002',tahap='checkout',revisi=2,kesiapan=siap_launch,sekarang=1)
layanan.atur_pembayaran(p_launch,a_launch,p_launch_actor,operasi='pair_sakelar_003',tahap='rekonsiliasi',revisi=3,kesiapan={k:False for k in siap_launch},sekarang=1)
with admin_store._transaksi(p_launch) as c:
    c.execute("INSERT INTO kpi_peserta VALUES('peserta','uji-coba-v1',?,1,1,'analitik-keluarga-v1',?,'tidak_diketahui',0)",('akun_'+'f'*32,kpi.BOOT_ID))
    c.execute("INSERT INTO kpi_aktivitas VALUES('peserta','1970-01-01','latihan_dikirim',1)")
(root_launch/'meta.json').write_text(json.dumps({'nilai':nilai_launch,'akun':p_launch_actor.id_akun}))
'''

SUMBER_BACA = r'''
import auth, admin_store, admin_launch_service as layanan, product_analytics_store as kpi
import json, sqlite3
from pathlib import Path
root_launch = Path('/data/admin-launch-pair')
p_launch,a_launch=root_launch/'admin.db',root_launch/'auth.json'
meta_launch=json.loads((root_launch/'meta.json').read_text())
p_launch_actor=auth.autentikasi('admin-layanan','sandi-pair-sintetis',a_launch)
for _ in range(2):
    admin_store.siapkan(p_launch,sekarang=2)
    kpi.simpan_biaya(p_launch,a_launch,p_launch_actor,operasi='pair_biaya_001',bulan='2026-09',revisi=0,nilai=meta_launch['nilai'],sekarang=2)
with admin_store.buka_baca(p_launch) as c:
    assert c.execute('SELECT COUNT(*) FROM kpi_audit_biaya').fetchone()[0]==1
    assert c.execute('SELECT COUNT(*) FROM pembayaran_audit').fetchone()[0]==3
    assert layanan.konfigurasi_pembayaran(c)['tahap']=='rekonsiliasi'
    assert layanan.sakelar_pembayaran(c).rekonsiliasi is True
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
# Proses recovery baru tidak mewarisi consent/lengkap dari proses kandidat.
assert not kpi.laporan(p_launch,sekarang=2,bulan='2026-09')[1].kualitas
kpi.catat(p_launch,'akun_'+'f'*32,kode='lembar_soal_disajikan',sekarang=2)
with admin_store.buka_baca(p_launch) as c:
    assert c.execute('SELECT COUNT(*) FROM kpi_aktivitas').fetchone()[0]==1
kpi.retensi(p_launch,sekarang=1+90*86400)
with admin_store.buka_baca(p_launch) as c:
    assert not c.execute('SELECT 1 FROM kpi_peserta').fetchone()
    assert not c.execute('SELECT 1 FROM kpi_aktivitas').fetchone()
    assert not c.execute('SELECT 1 FROM kpi_agregat').fetchone()
'''
