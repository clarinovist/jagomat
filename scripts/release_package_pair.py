"""Probe admin8 lintas binary; seluruh fixture sintetis, tanpa provider jaringan."""

BERSAMA = r'''
import contextlib, hashlib, json, os, sqlite3
from pathlib import Path
import admin_store, auth, database, ai_store, assistant_schema
import assistant_store as chat_store, assistant_policy, assistant_context
import subscription as sub, subscription_store as v1, subscription_package_store as v2
import subscription_package_schema as paket_schema, subscription_worker as worker
import midtrans_contract as midtrans
root = Path('/data/package-pair')
pa, ph, pd = root/'admin.db', root/'sandi.json', root/'belajar.db'
pai, pc = root/'ai.db', root/'pendamping.db'
on = sub.Sakelar(True, True, True, False)
now = 1800000000
config = midtrans.Konfigurasi('sandbox', 'kunci-pair-sintetis', 'M_PAIR')
def rows(path):
    with contextlib.closing(sqlite3.connect(path)) as con:
        assert con.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        return {t:[list(r) for r in con.execute('SELECT * FROM "'+t+'" ORDER BY rowid')]
                for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}
def bayar(inv, trx):
    return sub.Pembayaran('midtrans', trx, inv['invoice_id'], inv['akun_id'], inv['rupiah'],
                          'IDR', 'qris', 'M_PAIR', 'settlement', True)
def invoice(akun, sid, nomor):
    return v2.buat_invoice(pa, akun, (sid,), kode='jago_pro', penagihan='tahunan',
        invoice_id='inv_'+format(nomor,'032x'), idempotency_key='pair_paket_'+str(nomor),
        provider='midtrans', merchant='M_PAIR', sekarang=now+nomor,
        kedaluwarsa=now+86400, pemilik_profil=lambda _:akun, sakelar=on)
def simpan(nama, nilai):
    (root/nama).write_text(json.dumps(nilai, sort_keys=True))
def baca(nama):
    return json.loads((root/nama).read_text())
def tetap(awal, baru):
    assert all(baru.get(t)==rs for t,rs in awal.items()), 'histori_admin8_berubah'
def migrasi():
    for _ in range(2):
        admin_store.siapkan(pa, paket_v2=True, sekarang=now)
        admin_store.siapkan(pa, sekarang=now)
        with admin_store.buka_baca(pa) as con:
            assert con.execute('PRAGMA user_version').fetchone()[0]==8, 'admin8_downgrade'
            paket_schema.validasi(con)
def immutable():
    with sqlite3.connect(pa) as con:
        for t in ('langganan_invoice','langganan_receipt','langganan_grant',*paket_schema.TABEL):
            assert con.execute('SELECT count(*) FROM '+t).fetchone()[0]>0
            kolom=con.execute('PRAGMA table_info('+t+')').fetchone()[1]
            for sql in ('UPDATE '+t+' SET '+kolom+'='+kolom, 'DELETE FROM '+t,
                        'INSERT OR REPLACE INTO '+t+' SELECT * FROM '+t):
                try: con.execute(sql)
                except sqlite3.IntegrityError: pass
                else: raise AssertionError('ledger_pair_mutable')
def privat_tetap(meta):
    assert rows(pd)==meta['belajar'] and rows(pai)==meta['ai']
    assert hashlib.sha256(ph.read_bytes()).hexdigest()==meta['auth']
    assert rows(pc)==meta['chat'], 'histori_pendamping_berubah'
'''

SUMBER_TULIS = BERSAMA + r'''
root.mkdir()
database.siapkan(pd); ai_store.siapkan(pai,sekarang=now); assistant_schema.siapkan(pc)
admin_store.siapkan(pa,sekarang=now)
auth.tambah_akun('keluarga-pair','sandi-pair-sintetis','guru',ph)
principal=auth.autentikasi('keluarga-pair','sandi-pair-sintetis',ph)
akun=principal.id_akun
with database.buka(pd) as con:
    sid=database.tambah_siswa(con,'Profil Pair Sintetis','P3',pemilik=principal.pengguna)
    sesi=database.buat_sesi(con,sid,seed=62,jumlah_soal=1)
    konteks=assistant_context.ambil(con,'sesi',str(sesi),pemilik=principal.pengguna)
v1.enroll(pa,akun,sumber_id='pair_enrollment',asal='transisi',mulai=now,peran='guru',sakelar=on)
v1.atur_cakupan(pa,akun,(sid,),operasi_id='pair_cakupan',revisi=0,sekarang=now,pemilik_profil=lambda _:akun,sakelar=on)
lama=v1.buat_invoice(pa,akun,invoice_id='inv_'+'a'*32,idempotency_key='pair_invoice_lama',provider='midtrans',channel='qris',merchant='M_PAIR',sekarang=now,kedaluwarsa=now+86400,sakelar=on)
v1.terapkan_pembayaran(pa,akun,bayar(lama,'trx_v1'),sekarang=now+1,sakelar=on)
awal=rows(pa)
with admin_store.buka_baca(pa) as con: assert con.execute('PRAGMA user_version').fetchone()[0]==7
migrasi();tetap(awal,rows(pa))
v2.adopsi(pa,akun,operasi_id='pair_adopsi',sekarang=now+2,sakelar=on)
inv=invoice(akun,sid,3)
v1.terapkan_pembayaran(pa,akun,bayar(inv,'trx_v2'),sekarang=now+4,sakelar=on)
v1.catat_pengamatan(pa,akun,inv['invoice_id'],operasi_id='pair_amati',status='settlement',sekarang=now+4,sakelar=on)
pending=invoice(akun,sid,5)
v1.reservasi_create(pa,akun,pending['invoice_id'],sekarang=now+6,sakelar=on)
with contextlib.closing(assistant_schema.buka(pc)) as con, con:
    chat_store.beri_persetujuan(con,akun,policy_version=assistant_policy.VERSI_KEBIJAKAN,provider_id=assistant_policy.PROVIDER_ID,kategori='chat_umum',sekarang=now)
    grant=chat_store.beri_persetujuan_konteks(con,akun,jenis='sesi',resource_id=str(sesi),resource_version=konteks.versi,kategori=konteks.kategori,sekarang=now)
    chat=chat_store.buat_chat(con,akun,'aktif',sekarang=now,context_kind='sesi',context_id=str(sesi),context_version=grant.versi,context_resource_version=konteks.versi,context_category=konteks.kategori)
    chat_store.tambah_pesan(con,akun,chat.id,'pengguna','Pesan sintetis',request_id='pair_pesan',sekarang=now)
    chat_store.mulai_operasi(con,akun,chat.id,'pair_pending',consent_version=1,memory_version=0,context_version=grant.versi,sekarang=now)
immutable()
simpan('awal.json',dict(akun=akun,sid=sid,invoice=inv,pending=pending,lama=awal,
    admin=rows(pa),belajar=rows(pd),ai=rows(pai),chat=rows(pc),chat_id=chat.id,
    auth=hashlib.sha256(ph.read_bytes()).hexdigest()))
print('OSN_PACKAGE_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
meta=baca('awal.json');akun=meta['akun'];sid=meta['sid']
migrasi();tetap(meta['admin'],rows(pa));privat_tetap(meta)
for _ in range(2):
    assert v1.terapkan_pembayaran(pa,akun,bayar(meta['invoice'],'trx_v2'),sekarang=now+10,sakelar=on)=='grant'
assert rows(pa)==meta['admin'], 'replay_menulis_ulang'
# Mutasi kondisi di sela snapshot kedua dan fencing final; auth dipulihkan hanya fixture.
asli=worker._snapshot;putaran=[0];auth_awal=ph.read_bytes()
def snapshot_berubah(*a):
    hasil=asli(*a);putaran[0]+=1
    if putaran[0]==2: auth.naikkan_revisi_auth(akun,ph)
    return hasil
class Respons:
    status=200
    headers={'Content-Type':'application/json'}
    def __init__(self,url): self.url=url
    def __enter__(self): return self
    def __exit__(self,*a): pass
    def read(self,n):
        inv=meta['pending']
        return json.dumps(dict(order_id=inv['invoice_id'],transaction_id='trx_pending',gross_amount=str(inv['rupiah'])+'.00',currency='IDR',payment_type='qris',merchant_id='M_PAIR',status_code='200',transaction_status='settlement')).encode()[:n]
def transport(req,**kw):
    assert req.metode=='GET' and kw['allow_redirects'] is False
    return Respons(req.url)
worker._snapshot=snapshot_berubah
try:
    hasil=worker.jalankan(pa,ph,pd,config=config,transport=transport,sekarang=now+20,sakelar=on)
    assert hasil['dilewati']==1 and len(v2.baca(pa,akun).grants)==1, 'fencing_pair_dilewati'
finally:
    worker._snapshot=asli;ph.write_bytes(auth_awal)
# Pulih: lanjutkan intent sekali, bukan charge baru; restart/retry idempoten.
hasil=worker.jalankan(pa,ph,pd,config=config,transport=transport,sekarang=now+400,sakelar=on)
assert hasil['lunas']==1 and len(v2.baca(pa,akun).grants)==2
assert worker.jalankan(pa,ph,pd,config=config,transport=transport,sekarang=now+800,sakelar=on)['kandidat']==0
baru=invoice(akun,sid,900)
v1.terapkan_pembayaran(pa,akun,bayar(baru,'trx_recovery'),sekarang=now+901,sakelar=on)
with contextlib.closing(assistant_schema.buka(pc)) as con,con:
    assert chat_store.ambil_chat(con,akun,meta['chat_id']) is not None
    assert chat_store.gagalkan_operasi(con,akun,'pair_pending',sekarang=now+10)
    chat_store.tambah_pesan(con,akun,meta['chat_id'],'asisten','Balasan sintetis recovery',request_id='pair_balas',sekarang=now+10)
immutable();tetap(meta['lama'],rows(pa));assert rows(pd)==meta['belajar'] and rows(pai)==meta['ai']
simpan('recovery.json',dict(admin=rows(pa),chat=rows(pc),invoice=baru))
print('OSN_PACKAGE_RECOVERY_OK')
'''

SUMBER_KEMBALI = BERSAMA + r'''
meta=baca('awal.json');akhir=baca('recovery.json');akun=meta['akun']
migrasi();assert rows(pa)==akhir['admin'] and rows(pc)==akhir['chat']
assert len(v2.baca(pa,akun).grants)==3 and len(v1.baca(pa,akun).grants)==1
for _ in range(2):
    assert v1.terapkan_pembayaran(pa,akun,bayar(akhir['invoice'],'trx_recovery'),sekarang=now+902,sakelar=on)=='grant'
assert rows(pa)==akhir['admin']
with contextlib.closing(assistant_schema.buka(pc)) as con:
    assert len(chat_store.daftar_pesan(con,akun,meta['chat_id']))==2
    assert con.execute('PRAGMA user_version').fetchone()[0]==4
meta['chat']=akhir['chat'];privat_tetap(meta);immutable()
print('OSN_PACKAGE_RETURN_OK')
'''
