"""Probe pasangan harga admin (`harga_*`) lintas image; data sintetis, tanpa provider jaringan.

Kandidat memasang skema harga (dua kali, idempoten) lalu mengubah harga Private dan Mini ke volume sintetis, recovery
(image lama yang BELUM mengenal modul harga) membuka DB yang sama tanpa menulis dan mendapati tabel `harga_*` utuh
(dibaca mentah), lalu kandidat melanjutkan (konflik harga basi ditolak tanpa menulis, ubah sah, riwayat append-only).
Semua id, nilai, dan waktu buatan dan TETAP (tidak memakai jam nyata); tidak menyentuh DB/volume keluarga.
"""

BERSAMA = r'''
import contextlib, json, sqlite3
from pathlib import Path
import admin_store
root = Path('/data/harga-pair')
pa = root/'admin-control.db'
ADMIN = 'admin_sintetis_pair'
KINI = '2026-11-20T09:00:00'
LANJUT = '2026-11-21T09:00:00'

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
import schema_harga, harga
for _ in range(2):
    schema_harga.migrasikan(pa)
with admin_store.buka_baca(pa) as kon:
    assert schema_harga.validasi(kon)
    assert dict(harga.harga_semua(kon)) == dict(harga.HARGA_AWAL)
    assert harga.riwayat(kon) == ()
hasil = harga.ubah_harga(pa, 'private', 700000, 640000, ADMIN, KINI)
assert (hasil.kode, hasil.lama, hasil.baru) == ('private', 640000, 700000), hasil
hasil = harga.ubah_harga(pa, 'mini', 350000, 300000, ADMIN, KINI)
assert (hasil.kode, hasil.lama, hasil.baru) == ('mini', 300000, 350000), hasil
with admin_store.buka_baca(pa) as kon:
    assert dict(harga.harga_semua(kon)) == {'private': 700000, 'mini': 350000, 'peta': harga.HARGA_AWAL['peta']}
    assert [(r.kode, r.lama, r.baru) for r in harga.riwayat(kon)] == [('mini', 300000, 350000), ('private', 640000, 700000)]
awal = rows(pa)
simpan('awal.json', dict(admin=awal, peta=harga.HARGA_AWAL['peta']))
print('OSN_HARGA_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
meta = baca('awal.json')
assert rows(pa) == meta['admin'], 'histori_harga_berubah'
with admin_store.buka_baca(pa) as kon:                    # store admin recovery tidak menolak tabel harga_* yang tidak dikenalnya
    tabel = {r[0] for r in kon.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB 'harga_*'")}
    assert tabel == {'harga_produk', 'harga_riwayat'}, tabel
    assert {r[0]: r[1] for r in kon.execute('SELECT kode, rupiah FROM harga_produk')} == {'private': 700000, 'mini': 350000}
    assert [tuple(r) for r in kon.execute('SELECT kode, lama, baru, oleh FROM harga_riwayat ORDER BY id')] == [
        ('private', 640000, 700000, ADMIN), ('mini', 300000, 350000, ADMIN)]
assert rows(pa) == meta['admin'], 'recovery_menulis'
print('OSN_HARGA_RECOVERY_OK')
'''

SUMBER_KEMBALI = BERSAMA + r'''
import schema_harga, harga
meta = baca('awal.json')
assert rows(pa) == meta['admin'], 'histori_harga_berubah_sebelum_lanjut'
try:
    harga.ubah_harga(pa, 'private', 720000, 640000, ADMIN, LANJUT)      # admin melihat harga basi
except harga.KonflikHarga:
    pass
else:
    raise AssertionError('konflik_harga_diterima')
assert rows(pa) == meta['admin'], 'konflik_menulis'
try:
    harga.ubah_harga(pa, 'peta', 59000, 49000, ADMIN, LANJUT)           # Peta tidak boleh diubah lewat jalur ini
except ValueError:
    pass
else:
    raise AssertionError('peta_bisa_diubah')
assert rows(pa) == meta['admin'], 'penolakan_menulis'
hasil = harga.ubah_harga(pa, 'private', 720000, 700000, ADMIN, LANJUT)
assert (hasil.lama, hasil.baru) == (700000, 720000), hasil
with admin_store.buka_baca(pa) as kon:
    assert harga.harga_aktif(kon, 'private') == 720000 and harga.harga_aktif(kon, 'mini') == 350000
    assert [(r.kode, r.lama, r.baru) for r in harga.riwayat(kon)][0] == ('private', 700000, 720000)
    assert len(harga.riwayat(kon)) == 3
with contextlib.closing(sqlite3.connect(pa)) as con:
    try:
        con.execute('UPDATE harga_riwayat SET baru=baru+1000')
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError('riwayat_bisa_diubah')
rows(pa)
print('OSN_HARGA_RETURN_OK')
'''
