"""Probe konfigurasi dukungan C→B→C pada admin9 sintetis."""

BERSAMA = r'''
import hashlib,json,sqlite3
from pathlib import Path
import admin_store,auth,support_settings as dukungan
pa=Path('/data/admin-control.db'); ph=Path('/data/sandi.json'); now=1700000000
def rows():
 with sqlite3.connect(pa) as c:
  return {t:[list(r) for r in c.execute('SELECT * FROM "'+t+'" ORDER BY rowid')]
          for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'dukungan_*' ORDER BY name")}
def baca(n): return json.loads(Path('/data/'+n).read_text())
def simpan(n,x): Path('/data/'+n).write_text(json.dumps(x,sort_keys=True))
def migrasi():
 for _ in range(2): dukungan.migrasikan(pa,sekarang=now)
def principal(): return auth.autentikasi('support-admin','sandi-support-sintetis-123',ph)
'''

SUMBER_TULIS = BERSAMA + r'''
admin_store.siapkan(pa,sekarang=now,paket_v2=True);admin_store.migrasikan_kuota_pendamping(pa)
auth.tambah_akun('support-admin','sandi-support-sintetis-123','admin',ph)
with admin_store.buka_baca(pa) as c: assert not dukungan.validasi_schema(c), 'startup_migrasi_dukungan'
migrasi();cfg=dukungan.baca(pa);assert cfg and cfg.revisi==1
hasil=dukungan.ubah(pa,ph,principal(),operasi='support_pair_001',revisi=cfg.revisi,
 sidik_awal=dukungan.sidik_konfigurasi(cfg),whatsapp='0821 3711 1988',
 jam_layanan='weekday_0900_1700_wib',sla_respons=2,sla_status=4,sekarang=now+1)
assert hasil.revisi==2
simpan('support.json',dict(rows=rows(),auth=hashlib.sha256(ph.read_bytes()).hexdigest(),
 label=dukungan.proyeksi_publik(hasil).whatsapp_label))
print('OSN_SUPPORT_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
meta=baca('support.json');migrasi();assert rows()==meta['rows'];assert hashlib.sha256(ph.read_bytes()).hexdigest()==meta['auth']
cfg=dukungan.baca(pa);assert cfg and dukungan.proyeksi_publik(cfg).whatsapp_label==meta['label']
assert dukungan.ubah(pa,ph,principal(),operasi='support_pair_001',revisi=1,
 sidik_awal=meta['rows']['dukungan_audit'][0][5],whatsapp='082137111988',
 jam_layanan='weekday_0900_1700_wib',sla_respons=2,sla_status=4,sekarang=now+2).revisi==2
assert rows()==meta['rows'];simpan('support-recovery.json',dict(rows=rows()))
print('OSN_SUPPORT_RECOVERY_OK')
'''

SUMBER_KEMBALI = BERSAMA + r'''
meta=baca('support-recovery.json');migrasi();assert rows()==meta['rows']
cfg=dukungan.baca(pa);assert cfg and cfg.revisi==2 and cfg.sla_respons_hari==2 and cfg.sla_status_hari==4
print('OSN_SUPPORT_RETURN_OK')
'''
