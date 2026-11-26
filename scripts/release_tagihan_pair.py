"""Probe pasangan tagihan Paket Belajar (`tagihan_catatan`: batal/pulih) lintas image; data sintetis, tanpa provider jaringan.

Kandidat memasang kelas dan `tagihan_catatan`, lalu membatalkan satu tagihan sintetis. Recovery membuka DB yang sama tanpa
menulis dan membaca catatan batal secara mentah. Perilaku rollback "tagihan tampak terbuka lagi" TIDAK diasersi di sini: pin
recovery yang sesuai kontrak membawa `kelas_store`/`kelas_status` versi main (sadar batal), jadi bergantung pada pin yang dipilih.
Kandidat melanjutkan: replay batal ditolak tanpa menulis, lalu pulih memulihkan tagihan yang sama. Semua id, sha, dan waktu buatan dan TETAP (tidak memakai jam nyata); tidak menyentuh
DB/volume keluarga.
"""

BERSAMA = r'''
import contextlib, json, sqlite3
from pathlib import Path
import admin_store
root = Path('/data/tagihan-pair')
pa = root/'admin-control.db'
AKUN = 'akun_' + 'a'*32
KINI = '2026-11-20T09:00:00'
BATAL = '2026-11-20T09:10:00'
PULIH = '2026-11-20T09:20:00'

def rows(path):
    with contextlib.closing(sqlite3.connect(path)) as con:
        assert con.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
        assert not con.execute('PRAGMA foreign_key_check').fetchall()
        return {t:[list(r) for r in con.execute('SELECT * FROM "'+t+'" ORDER BY rowid')]
                for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")}

def simpan(nama, nilai):
    (root/nama).write_text(json.dumps(nilai, sort_keys=True))

def baca(nama):
    return json.loads((root/nama).read_text())
'''

SUMBER_TULIS = BERSAMA + r'''
root.mkdir()
admin_store.siapkan(pa, sekarang=1)
import schema_pesanan, schema_transfer, schema_purna, schema_kelas, schema_tagihan_catatan
import kelas_batal, kelas_dasar, kelas_store
for _ in range(2):
    schema_pesanan.migrasikan(pa)
    schema_transfer.migrasikan(pa)
    schema_purna.migrasikan(pa)
    schema_kelas.migrasikan(pa)
    schema_tagihan_catatan.migrasikan(pa)
with kelas_store.buka(pa, tulis_data=True) as kon:
    tagihan = kelas_store.buat_tagihan(kon, AKUN, 1, 'mini', KINI, acak=lambda bebas: bebas[0])
    assert tagihan.status == 'belum_bayar', tagihan.status
    batal = kelas_batal.batalkan_tagihan(kon, AKUN, 1, 'mini', BATAL)
    assert batal == {'order_id': tagihan.order_id, 'status': kelas_dasar.STATUS_DIBATALKAN}, batal
awal = rows(pa)
simpan('awal.json', dict(admin=awal, order=tagihan.order_id))
print('OSN_TAGIHAN_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
import admin_store
meta = baca('awal.json')
assert rows(pa) == meta['admin'], 'histori_tagihan_berubah'
with admin_store.buka_baca(pa) as kon:
    catatan = [tuple(r) for r in kon.execute('SELECT order_id, aksi FROM tagihan_catatan ORDER BY id')]
    assert catatan == [(meta['order'], 'batal')], catatan
assert rows(pa) == meta['admin'], 'recovery_menulis'
print('OSN_TAGIHAN_RECOVERY_OK')
'''

SUMBER_KEMBALI = BERSAMA + r'''
import pesanan_dasar, kelas_batal, kelas_store
import admin_store
meta = baca('awal.json')
assert rows(pa) == meta['admin'], 'histori_tagihan_berubah_sebelum_lanjut'
with kelas_store.buka(pa, tulis_data=True) as kon:
    try:
        kelas_batal.batalkan_tagihan(kon, AKUN, 1, 'mini', PULIH)
    except pesanan_dasar.PesananTidakDitemukan:
        pass
    else:
        raise AssertionError('batal_ganda_diterima')
    assert rows(pa) == meta['admin'], 'batal_ganda_menulis'
    pulih = kelas_store.buat_tagihan(kon, AKUN, 1, 'mini', PULIH, acak=lambda bebas: bebas[0])
    assert pulih.order_id == meta['order'] and pulih.status == 'belum_bayar', pulih
with admin_store.buka_baca(pa) as kon:
    catatan = [tuple(r) for r in kon.execute('SELECT order_id, aksi FROM tagihan_catatan ORDER BY id')]
    assert catatan == [(meta['order'], 'batal'), (meta['order'], 'pulih')], catatan
rows(pa)
print('OSN_TAGIHAN_RETURN_OK')
'''
