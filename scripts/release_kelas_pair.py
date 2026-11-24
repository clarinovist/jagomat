"""Probe pasangan Paket Belajar (`kelas_*`) lintas image; data sintetis, tanpa provider jaringan.

Kandidat menulis tagihan + bukti ke volume sintetis, recovery (image lama yang sudah mengenal
tabel `kelas_*`) membuka DB yang sama tanpa menulis, lalu kandidat melanjutkan dengan bukti baru
sampai akses tertulis. Semua id, sha, dan waktu buatan; tidak menyentuh DB/volume keluarga.
"""

BERSAMA = r'''
import contextlib, json, sqlite3
from pathlib import Path
import admin_store
root = Path('/data/kelas-pair')
pa = root/'admin-control.db'
AKUN = 'akun_' + 'a'*32
KINI = '2026-11-20T09:00:00'
UNGGAH = '2026-11-20T09:30:00'
MIME = 'image/jpeg'
UKURAN = 120000
SHA1 = '%064x' % 0xB1
BERKAS1 = '%032x' % 0xA1
SHA2 = '%064x' % 0xB2
BERKAS2 = '%032x' % 0xA2
ADMIN = 'admin_sintetis_pair'

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
import schema_pesanan, schema_transfer, schema_purna, schema_kelas, kelas_store
for _ in range(2):
    schema_pesanan.migrasikan(pa)
    schema_transfer.migrasikan(pa)
    schema_purna.migrasikan(pa)
    schema_kelas.migrasikan(pa)
with kelas_store.buka(pa, tulis_data=True) as kon:
    tagihan = kelas_store.buat_tagihan(kon, AKUN, 1, 'mini', KINI, acak=lambda bebas: bebas[0])
    assert tagihan.status == 'belum_bayar', tagihan.status
    bukti = kelas_store.catat_bukti(kon, AKUN, 1, 'mini', MIME, UKURAN, SHA1, BERKAS1, UNGGAH)
    assert bukti['baru'] is True and bukti['status'] == 'menunggu', bukti
awal = rows(pa)
simpan('awal.json', dict(admin=awal, order=tagihan.order_id, bukti=bukti['bukti_id']))
print('OSN_KELAS_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
import schema_pesanan, schema_transfer, kelas_store
meta = baca('awal.json')
assert rows(pa) == meta['admin'], 'histori_kelas_berubah'
with kelas_store.buka(pa) as kon:
    tagihan = kelas_store.tagihan_dari(kon, AKUN, meta['order'], UNGGAH)
    assert tagihan.status == 'menunggu', tagihan.status
    assert tagihan.jumlah_bukti == 1, tagihan.jumlah_bukti
with admin_store.buka_baca(pa) as kon:
    assert schema_pesanan.validasi(kon) and schema_transfer.validasi(kon)
assert rows(pa) == meta['admin'], 'recovery_menulis'
print('OSN_KELAS_RECOVERY_OK')
'''

SUMBER_KEMBALI = BERSAMA + r'''
import kelas_store, kelas_putusan
meta = baca('awal.json')
with kelas_store.buka(pa, tulis_data=True) as kon:
    ulang = kelas_store.catat_bukti(kon, AKUN, 1, 'mini', MIME, UKURAN, SHA1, BERKAS1, UNGGAH)
    assert ulang['baru'] is False, ulang
    assert rows(pa) == meta['admin'], 'replay_menulis_ulang'
    baru = kelas_store.catat_bukti(kon, AKUN, 1, 'mini', MIME, UKURAN, SHA2, BERKAS2, UNGGAH)
    assert baru['baru'] is True, baru
    putusan = kelas_putusan.setujui(kon, meta['order'], ADMIN, UNGGAH, bukti_dilihat=baru['bukti_id'])
    assert putusan['status'] == 'aktif' and putusan['baru'] is True, putusan
    tagihan = kelas_store.tagihan_dari(kon, AKUN, meta['order'], UNGGAH)
    assert tagihan.status == 'aktif' and tagihan.berakhir is not None, tagihan
print('OSN_KELAS_RETURN_OK')
'''
