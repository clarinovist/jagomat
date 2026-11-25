"""Probe pasangan jadwal Paket Belajar (`jadwal_*`) lintas image; data sintetis, tanpa provider jaringan.

Kandidat menulis kelompok Mini + penempatan (Mini dan Private) + pertemuan ke volume sintetis, recovery
(image lama yang sudah mengenal tabel `jadwal_*`) membuka DB yang sama tanpa menulis dan membacanya bersih,
lalu kandidat melanjutkan (replay ditolak, geser/batal sesi, lepas dan tempatkan ulang). Semua id, sha, dan
waktu buatan dan TETAP (tidak memakai jam nyata: akses `kelas_*` sintetis berakhir 20 Des 2026 dan tidak boleh
membuat probe kedaluwarsa); tidak menyentuh DB/volume keluarga.
"""

BERSAMA = r'''
import contextlib, json, sqlite3
from pathlib import Path
import admin_store
root = Path('/data/jadwal-pair')
pa = root/'admin-control.db'
AKUN = 'akun_' + 'a'*32
GURU = 'akun_' + '9'*32
GURU2 = 'akun_' + '8'*32
KINI = '2026-11-20T09:00:00'
UNGGAH = '2026-11-20T09:30:00'
MIME = 'image/jpeg'
UKURAN = 120000
ADMIN = 'admin_sintetis_pair'
TANGGAL = '2026-11-21'
JAM = '09:00'
TANGGAL_PRIVATE = '2026-11-23'
JAM_PRIVATE = '16:30'

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
import schema_pesanan, schema_transfer, schema_purna, schema_kelas, schema_jadwal
import kelas_store, kelas_putusan, jadwal_store
for _ in range(2):
    schema_pesanan.migrasikan(pa)
    schema_transfer.migrasikan(pa)
    schema_purna.migrasikan(pa)
    schema_kelas.migrasikan(pa)
    schema_jadwal.migrasikan(pa)

def aktifkan(kon, siswa, paket, n):
    tagihan = kelas_store.buat_tagihan(kon, AKUN, siswa, paket, KINI, acak=lambda bebas: bebas[0])
    bukti = kelas_store.catat_bukti(kon, AKUN, siswa, paket, MIME, UKURAN,
                                    '%064x' % (0xB0 + n), '%032x' % (0xA0 + n), UNGGAH)
    putusan = kelas_putusan.setujui(kon, tagihan.order_id, ADMIN, UNGGAH, bukti_dilihat=bukti['bukti_id'])
    assert putusan['status'] == 'aktif', putusan
    return tagihan.order_id

with jadwal_store.buka(pa, tulis_data=True) as kon:
    mini = aktifkan(kon, 1, 'mini', 1)
    privat = aktifkan(kon, 2, 'private', 2)
    kid = jadwal_store.buat_kelompok(kon, ADMIN, nama='Mini Sintetis', lokasi='Ruang Sintetis', guru_id=GURU,
                                     kuota=3, tanggal=TANGGAL, jam=JAM, sekarang=UNGGAH)
    jadwal_store.tempatkan(kon, ADMIN, mini, kelompok_id=kid, sekarang=UNGGAH)
    jadwal_store.tempatkan(kon, ADMIN, privat, guru_id=GURU, tanggal=TANGGAL_PRIVATE, jam=JAM_PRIVATE,
                           sekarang=UNGGAH)
    detail = jadwal_store.detail_kelompok(kon, kid)
    assert detail['terisi'] == 1 and len(detail['sesi']) == 8, detail
    assert detail['sesi'][0]['mulai'] == '2026-11-21T02:00:00', detail['sesi'][0]
    ringkas = jadwal_store.ringkas_order(kon, privat)
    assert ringkas['guru_id'] == GURU and len(ringkas['sesi']) == 8, ringkas
awal = rows(pa)
simpan('awal.json', dict(admin=awal, mini=mini, privat=privat, kelompok=kid))
print('OSN_JADWAL_WRITER_OK')
'''

SUMBER_BACA = BERSAMA + r'''
import schema_pesanan, schema_transfer, schema_jadwal, jadwal_store
meta = baca('awal.json')
assert rows(pa) == meta['admin'], 'histori_jadwal_berubah'
with jadwal_store.buka(pa) as kon:
    detail = jadwal_store.detail_kelompok(kon, meta['kelompok'])
    assert detail['terisi'] == 1, detail['terisi']
    assert [s['ke'] for s in detail['sesi']] == list(range(1, 9)), detail['sesi']
    assert [a['order_id'] for a in detail['anggota']] == [meta['mini']], detail['anggota']
    ringkas = jadwal_store.ringkas_order(kon, meta['privat'])
    assert ringkas['guru_id'] == GURU and len(ringkas['sesi']) == 8, ringkas
    daftar = jadwal_store.daftar_kelompok(kon, UNGGAH)     # jalur baca antrean admin; store baru + dasar lama harus mandiri
    assert [k['terisi'] for k in daftar] == [1], daftar
with admin_store.buka_baca(pa) as kon:
    assert schema_pesanan.validasi(kon) and schema_transfer.validasi(kon)
    assert schema_jadwal.validasi(kon)
assert rows(pa) == meta['admin'], 'recovery_menulis'
print('OSN_JADWAL_RECOVERY_OK')
'''

SUMBER_KEMBALI = BERSAMA + r'''
import jadwal_dasar, jadwal_store
meta = baca('awal.json')
assert rows(pa) == meta['admin'], 'histori_jadwal_berubah_sebelum_lanjut'
with jadwal_store.buka(pa, tulis_data=True) as kon:
    try:
        jadwal_store.tempatkan(kon, ADMIN, meta['mini'], kelompok_id=meta['kelompok'], sekarang=UNGGAH)
    except jadwal_dasar.JadwalKonflik:
        pass
    else:
        raise AssertionError('replay_penempatan_diterima')
    assert rows(pa) == meta['admin'], 'replay_menulis_ulang'
    detail = jadwal_store.detail_kelompok(kon, meta['kelompok'])
    kedua = detail['sesi'][1]['id']
    jadwal_store.ubah_pertemuan(kon, ADMIN, kedua, tanggal='2026-11-25', jam='10:00', sekarang=UNGGAH)
    jadwal_store.batalkan_pertemuan(kon, ADMIN, kedua, batal=True, sekarang=UNGGAH)
    sesi = jadwal_store.pertemuan_dari(kon, kedua)
    assert sesi['dibatalkan'] == 1 and sesi['mulai'] == '2026-11-25T03:00:00', sesi
    jadwal_store.lepas_penempatan(kon, ADMIN, meta['privat'],
                                  versi=jadwal_store.ringkas_order(kon, meta['privat'])['dibuat'], sekarang=UNGGAH)
    assert jadwal_store.ringkas_order(kon, meta['privat']) is None
    jadwal_store.tempatkan(kon, ADMIN, meta['privat'], guru_id=GURU2, tanggal=TANGGAL_PRIVATE,
                           jam=JAM_PRIVATE, sekarang=UNGGAH)
    ringkas = jadwal_store.ringkas_order(kon, meta['privat'])
    assert ringkas['guru_id'] == GURU2 and len(ringkas['sesi']) == 8, ringkas
rows(pa)
print('OSN_JADWAL_RETURN_OK')
'''
