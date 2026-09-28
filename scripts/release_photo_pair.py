"""Receipt foto lintas binary C→B→C; probe sintetis tanpa transport provider.

Dijalankan sesudah fase kuota9 masing-masing. Recovery lama yang hanya mengenal
admin9 sengaja gagal: bukan bukti preservasi reader/migrator foto.
"""
BERSAMA = r'''
import sqlite3, json, hashlib
import database

def foto_rows():
    with database.buka(pd) as kon:
        database.validasi_operasi_foto(kon)
        return [list(r) for r in kon.execute('SELECT * FROM operasi_foto_baca ORDER BY operasi_id')]
def foto_migrasi():
    for _ in range(2):
        database.migrasikan_operasi_foto(pd)
        database.siapkan(pd)
    foto_rows()
def foto_snapshot():
    return dict(admin=rows(pa),belajar=rows(pd),ai=rows(pai),chat=rows(pc),auth=hashlib.sha256(ph.read_bytes()).hexdigest())
'''
SUMBER_TULIS = BERSAMA + r'''
awal_foto=rows(pd)
with database.buka(pd) as kon:
    assert not kon.execute("SELECT 1 FROM sqlite_master WHERE name='operasi_foto_baca'").fetchone(), 'foto_startup_migrasi'
foto_migrasi()
tetap(awal_foto,rows(pd)); assert foto_rows()==[], 'foto_migrasi_membuat_attempt'
with database.buka(pd) as kon:
    sesi=kon.execute('SELECT id FROM sesi ORDER BY id LIMIT 1').fetchone()[0]
    lid=database.simpan_lampiran(kon,sesi,'foto-pair-sintetis.img',hasil_json='{"soal":[]}')
    for n,st in enumerate(('reserved','sent','unknown','result','no_output'),1):
        oid='foto_'+format(n,'032x')
        kon.execute('INSERT INTO operasi_foto_baca VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL,?,?)',
            (oid,akun,akun,sesi,0,'upload',*(['a'*64]*4),'reserved',now,now))
        if st in ('sent','unknown','result'):
            kon.execute("UPDATE operasi_foto_baca SET status='sent' WHERE operasi_id=?",(oid,))
        if st in ('unknown','result','no_output'):
            kon.execute('UPDATE operasi_foto_baca SET status=?,hasil_id=? WHERE operasi_id=?',
                        (st,lid if st in ('result','no_output') else None,oid))
simpan('foto-awal.json',foto_snapshot())
# Snapshot kuota memang dibuat sebelum attempt foto. Perbarui hanya fixture
# belajar agar fase kuota berikutnya membuktikan preservasi tambahan ini juga.
q=baca('kuota-awal.json');q['belajar']=rows(pd);simpan('kuota-awal.json',q)
'''
SUMBER_BACA = BERSAMA + r'''
awal_foto=baca('foto-awal.json')
foto_migrasi()
assert rows(pd)==awal_foto['belajar'], 'receipt_foto_recovery_berubah'
assert [r[10] for r in foto_rows()]==['reserved','sent','unknown','result','no_output'], 'pending_foto_hilang'
with database.buka(pd) as kon:
    for sql in ('DELETE FROM operasi_foto_baca',
                "UPDATE operasi_foto_baca SET status='reserved' WHERE status='unknown'",
                'INSERT OR REPLACE INTO operasi_foto_baca SELECT * FROM operasi_foto_baca'):
        try:kon.execute(sql)
        except sqlite3.IntegrityError:pass
        else:raise AssertionError('receipt_foto_mutable')
simpan('foto-recovery.json',foto_snapshot())
'''
SUMBER_KEMBALI = BERSAMA + r'''
akhir_foto=baca('foto-recovery.json')
foto_migrasi()
assert rows(pd)==akhir_foto['belajar'], 'receipt_foto_return_berubah'
assert [r[10] for r in foto_rows()]==['reserved','sent','unknown','result','no_output'], 'pending_foto_return_hilang'
assert rows(pai)==akhir_foto['ai'] and rows(pc)==akhir_foto['chat']
assert hashlib.sha256(ph.read_bytes()).hexdigest()==akhir_foto['auth']
'''
