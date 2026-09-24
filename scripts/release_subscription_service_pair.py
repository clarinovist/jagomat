"""Pair service langganan: kandidat menyimpan intent, recovery melanjutkan query."""

BERSAMA = r'''
import json, sqlite3, socket
from pathlib import Path
import auth, admin_registration, admin_store, database
import subscription as d, subscription_store as st, subscription_service as svc
import midtrans_contract as mt
root = Path('/data/subscription-service-pair')
pa, ph, pd = root/'admin.db', root/'sandi.json', root/'belajar.db'
now = 1800000000
on = d.Sakelar(True,True,True,False)
inv_id = 'inv_'+'d'*32
config = mt.Konfigurasi('sandbox','kunci-pair-sintetis','M_PAIR')
def fingerprint_service():
    import hashlib
    return [hashlib.sha256(p.read_bytes()).hexdigest() for p in (ph,pd)]
class ResponsService:
    status=200
    headers={'Content-Type':'application/json'}
    def __init__(self,url): self.url=url
    def __enter__(self): return self
    def __exit__(self,*_): pass
    def read(self,n):
        return json.dumps(dict(order_id=inv_id,transaction_id='trx_pair_service',gross_amount='35000.00',currency='IDR',payment_type='qris',merchant_id='M_PAIR',status_code='200',transaction_status='settlement')).encode()[:n]
def transport_service(req,**kw):
    assert req.metode=='GET', 'recovery_membuat_charge_baru'
    assert kw['allow_redirects'] is False
    return ResponsService(req.url)
'''

SUMBER_TULIS = BERSAMA + r'''
root.mkdir()
admin_store.siapkan(pa,sekarang=now)
database.siapkan(pd)
admin_registration.daftar_publik(pa,ph,pd,operasi_id='daftar_service_pair',alias='keluarga-pair',sandi='sandi-pair-sintetis',token_form='x'*64,sekarang=now)
principal=auth.autentikasi('keluarga-pair','sandi-pair-sintetis',ph)
args=(pa,ph,pd,principal)
svc.sinkron_pendaftaran(*args,sumber_id='daftar_service_pair',cutoff=now,sekarang=now,sakelar=on)
with database.buka(pd) as kon:
    sid=database.tambah_siswa(kon,'Profil Pair Sintetis','P3',pemilik=principal.pengguna)
svc.atur_cakupan(*args,(sid,),operasi_id='cakupan_service_pair',revisi=0,sekarang=now,sakelar=on)
svc.buat_invoice(*args,invoice_id=inv_id,idempotency_key='idem_service_pair',merchant='M_PAIR',sekarang=now,kedaluwarsa=now+100,sakelar=on)
try:
    svc.mulai_pembayaran(*args,inv_id,config=config,transport=transport_service,sekarang=now+1,sakelar=on,failpoint='setelah_intent')
except svc.SinkronBelumSelesai:
    pass
else:
    raise AssertionError('intent_tidak_durable')
(root/'before.json').write_text(json.dumps(fingerprint_service()))
'''

SUMBER_BACA = BERSAMA + r'''
principal=auth.autentikasi('keluarga-pair','sandi-pair-sintetis',ph)
args=(pa,ph,pd,principal)
for _ in range(2):
    hasil=svc.mulai_pembayaran(*args,inv_id,config=config,transport=transport_service,sekarang=now+2,sakelar=on)
    assert hasil.status=='lunas'
assert fingerprint_service()==json.loads((root/'before.json').read_text())
snap=st.baca(pa,principal.id_akun)
assert len(snap.grants)==1
assert snap.enrollment.mulai==now
with admin_store.buka_baca(pa) as kon:
    assert kon.execute('SELECT COUNT(*) FROM langganan_receipt').fetchone()[0]==1
    assert not kon.execute('PRAGMA foreign_key_check').fetchall()
assert d.akses(snap.enrollment,snap.grants,sekarang=snap.grants[0].periode.akhir).status=='expired'
try:
    svc.periksa_pembayaran(*args,inv_id,config=config,transport=transport_service,sekarang=now+3)
except d.FiturNonaktif:
    pass
else:
    raise AssertionError('default_service_aktif')
'''
