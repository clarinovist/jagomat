"""Probe kuota admin9 C→B→C; sumber/DB sintetis, tanpa jaringan provider.

Dimulai sesudah probe paket8 pada volume yang sama. Recovery wajib mempunyai
reader/writer/migrator9 nyata; tidak pernah menurunkan versi atau menghapus ledger.
"""
import importlib.util
from pathlib import Path

_spek = importlib.util.spec_from_file_location('kuota_package_probe', Path(__file__).with_name('release_package_pair.py'))
_paket = importlib.util.module_from_spec(_spek)
_spek.loader.exec_module(_paket)
PAKET_BERSAMA = _paket.BERSAMA

BERSAMA = PAKET_BERSAMA + r'''
import assistant_quota_store as kuota
import assistant_quota_schema as kuota_schema
fitur = 'balasan_pendamping'
def migrasi9():
    for _ in range(2):
        admin_store.migrasikan_kuota_pendamping(pa)
        admin_store.siapkan(pa,sekarang=now)
        with admin_store.buka_baca(pa) as con:
            assert con.execute('PRAGMA user_version').fetchone()[0]==9, 'kuota_schema_bukan9'
            kuota.validasi_sumber(con)
def status(akun,clock,jenis=fitur):
    return kuota.baca_status(pa,akun,fitur=jenis,sekarang=clock,penegakan=True)
def reserve(akun,operasi,clock,jenis=fitur):
    return kuota.reservasi(pa,akun,operasi_id=operasi,fitur=jenis,sekarang=clock,penegakan=True)
def lookup(akun,operasi,jenis=fitur):
    return kuota.baca_operasi(pa,akun,operasi,fitur=jenis)
'''

SUMBER_TULIS = BERSAMA + r'''
meta=baca('awal.json');akun=meta['akun']
awal=rows(pa)
with admin_store.buka_baca(pa) as con: assert con.execute('PRAGMA user_version').fetchone()[0]==8
migrasi9();tetap(awal,rows(pa))
assert all(not rows(pa)[t] for t in kuota_schema.TABEL), 'migrasi_membuat_kuota'
assert status(akun,now+10).tersisa==10, 'trial_bukan10'
r=reserve(akun,'kuota_unknown',now+10)
assert r.boleh_outbound
kuota.tandai_unknown(pa,r.ikatan,sekarang=now+11)
assert not reserve(akun,'kuota_unknown',now+12).boleh_outbound, 'replay_mengirim_ulang'
reserve(akun,'kuota_release',now+12)
assert status(akun,now+12).direservasi==2
pro=v2.baca(pa,akun).grants[0]['mulai']
assert status(akun,pro).tersisa==50
assert status(akun,pro,'pembacaan_foto').tersisa==5
r=reserve(akun,'kuota_pro_selesai',pro)
kuota.finalisasi(pa,r.ikatan,sekarang=pro+1,hasil_valid_tersimpan=True)
reserve(akun,'kuota_foto_reserved',pro,'pembacaan_foto')
simpan('kuota-awal.json',dict(akun=akun,pro=pro,admin=rows(pa),belajar=rows(pd),ai=rows(pai),chat=rows(pc),auth=hashlib.sha256(ph.read_bytes()).hexdigest()))
print('OSN_QUOTA_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
meta=baca('kuota-awal.json');akun=meta['akun'];pro=meta['pro']
migrasi9();assert rows(pa)==meta['admin'];privat_tetap(meta)
r=lookup(akun,'kuota_unknown')
assert r.status=='unknown' and not r.boleh_outbound, 'unknown_hilang'
try: kuota.lepaskan(pa,r.ikatan,sekarang=now+20,tanpa_output_terbukti=True)
except kuota.KonflikKuota: pass
else: raise AssertionError('unknown_dilepas_tanpa_rekonsiliasi')
kuota.finalisasi(pa,r.ikatan,sekarang=now+20,hasil_valid_tersimpan=True,rekonsiliasi=True)
r=lookup(akun,'kuota_release')
kuota.lepaskan(pa,r.ikatan,sekarang=now+20,tanpa_output_terbukti=True)
assert status(akun,now+21).tersisa==9
assert not reserve(akun,'kuota_release',now+21).boleh_outbound
# Dua profil sintetis memakai satu akun; tidak ada key profil pada ledger.
for n in range(9): reserve(akun,'kuota_profil_'+str(n),now+21)
try: reserve(akun,'kuota_profil_lebih',now+21)
except kuota.KuotaDitolak as e: assert e.status=='kuota_habis'
else: raise AssertionError('kuota_akun_tidak_bersama')
assert status(akun,now+21).tersisa==0
assert status(akun,pro).tersisa==49, 'kuota_trial_masuk_pro'
h=status(akun,pro);bulan=h.jendela_akhir
assert status(akun,bulan).tersisa==50 and status(akun,bulan).isi_ulang is not None
reserve(akun,'kuota_bulan_kedua',bulan)
r=lookup(akun,'kuota_foto_reserved','pembacaan_foto')
kuota.lepaskan(pa,r.ikatan,sekarang=pro+2,tanpa_output_terbukti=True)
assert status(akun,pro,'pembacaan_foto').tersisa==5
privat_tetap(meta)
simpan('kuota-recovery.json',dict(admin=rows(pa),bulan=bulan))
print('OSN_QUOTA_RECOVERY_OK')
'''

SUMBER_KEMBALI = BERSAMA + r'''
meta=baca('kuota-awal.json');akhir=baca('kuota-recovery.json');akun=meta['akun']
migrasi9();assert rows(pa)==akhir['admin'];privat_tetap(meta)
assert lookup(akun,'kuota_unknown').status=='completed'
assert lookup(akun,'kuota_release').status=='released'
assert status(akun,akhir['bulan']).tersisa==49
assert not reserve(akun,'kuota_bulan_kedua',akhir['bulan']).boleh_outbound
assert rows(pa)==akhir['admin'], 'readback_kuota_berubah'
print('OSN_QUOTA_RETURN_OK')
'''
