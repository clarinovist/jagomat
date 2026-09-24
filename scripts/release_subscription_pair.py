"""Kontrak pair admin6; reader lama tidak boleh mengaku memulihkan ledger baru."""

SUMBER_TULIS = r'''
import json
from pathlib import Path
import subscription as sub, subscription_store as subs
exec(PROBE_LANGGANAN)
assert uji_langganan('/data/subscription-pair') == 4
p_sub = Path('/data/subscription-pair/admin-control.db')
sub_akun = 'akun_' + 'a'*32
sub_awal = subs.baca(p_sub, sub_akun)
with __import__('sqlite3').connect(p_sub) as kon:
    sub_dump = tuple(kon.iterdump())
Path('/data/subscription-pair.json').write_text(json.dumps(sub_dump))
'''

SUMBER_BACA = r'''
import json, sqlite3
from pathlib import Path
import admin_store, subscription as sub, subscription_store as subs
p_sub = Path('/data/subscription-pair/admin-control.db')
sub_akun = 'akun_' + 'a'*32
sub_dump = json.loads(Path('/data/subscription-pair.json').read_text())
for _ in range(2):
    admin_store.siapkan(p_sub)
    b = sub.Pembayaran('fake','trx_probe','inv_'+'b'*32,sub_akun,35000,'IDR','qris','M','settlement',True)
    assert subs.terapkan_pembayaran(p_sub,sub_akun,b,sekarang=3,sakelar=sub.Sakelar(True,True,True,False)) == 'grant'
with sqlite3.connect(p_sub) as kon:
    assert list(kon.iterdump()) == sub_dump
    assert kon.execute('SELECT COUNT(*) FROM langganan_receipt').fetchone()[0] == 1
snap = subs.baca(p_sub,sub_akun)
assert len(snap.grants) == 1
assert sub.akses(snap.enrollment,snap.grants,sekarang=snap.grants[0].periode.akhir).status == 'expired'
try:
    subs.baca_invoice(p_sub,'akun_'+'f'*32,'inv_'+'b'*32)
except LookupError:
    pass
else:
    raise AssertionError('owner_ledger_dilewati')
'''
