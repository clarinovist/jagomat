"""Lifecycle admin9 opt-in/backup dengan DB sintetis, bukan startup produksi."""
from contextlib import closing
import sqlite3

import pytest

import admin_store
import admin_backup
import ai_store
import assistant_quota_schema as schema
import assistant_quota_store as q
import subscription as d
import subscription_store as v1
import subscription_package_store as v2
from test_admin_backup import _buat_bundle, OWNER

ON = d.Sakelar(True, True, True, False)
T0 = 1800000000


def baris(path):
    with closing(sqlite3.connect(path)) as con:
        return {t: tuple(con.execute('SELECT * FROM "'+t+'" ORDER BY rowid'))
                for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def siapkan8(path):
    admin_store.siapkan(path, paket_v2=True, sekarang=T0)
    v1.enroll(path, OWNER, sumber_id='enrollment_sintetis', asal='transisi', mulai=T0,
              peran='guru', sakelar=ON)
    v2.adopsi(path, OWNER, operasi_id='adopsi_sintetis', sekarang=T0+1, sakelar=ON)


def reserve(path, operasi='operasi_sintetis', fitur='balasan_pendamping', sekarang=T0+2):
    return q.reservasi(path, OWNER, operasi_id=operasi, fitur=fitur, sekarang=sekarang, penegakan=True)


def test_startup_paket8_tidak_otomatis_mengaktifkan9(tmp_path):
    path = tmp_path/'admin.db'
    admin_store.siapkan(path, paket_v2=True)
    with admin_store.buka_baca(path) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 8
        assert not schema.struktur(con)


def test_optin_strict_missing7_default8_tetap_tanpa_kuota(tmp_path):
    path = tmp_path/'admin.db'
    with pytest.raises(admin_store.StoreBelumSiap):
        admin_store.migrasikan_kuota_pendamping(path)
    assert not path.exists()
    admin_store.siapkan(path)
    with pytest.raises(admin_store.StoreBelumSiap):
        admin_store.migrasikan_kuota_pendamping(path)
    siapkan8(path)
    awal = baris(path)
    admin_store.siapkan(path)
    assert baris(path) == awal and not set(schema.TABEL) & set(awal)
    assert q.baca_status(path, OWNER, fitur='balasan_pendamping', sekarang=T0+2).status == 'storage_tidak_terverifikasi'
    assert baris(path) == awal
    admin_store.migrasikan_kuota_pendamping(path)
    for _ in range(2):
        admin_store.migrasikan_kuota_pendamping(path)
        admin_store.siapkan(path)
    akhir = baris(path)
    assert all(akhir[t] == rs for t, rs in awal.items())
    assert all(not akhir[t] for t in schema.TABEL)
    with admin_store.buka_baca(path) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 9
    assert q.baca_status(path, OWNER, fitur='balasan_pendamping', sekarang=T0+2).tersisa == 10
    assert baris(path) == akhir


@pytest.mark.parametrize('jenis', ['partial8','partial9','unknown','rusak8'])
def test_partial_unknown_tidak_diperbaiki_migrator(tmp_path, jenis):
    path = tmp_path/'admin.db'
    siapkan8(path)
    with closing(sqlite3.connect(path)) as con, con:
        if jenis == 'partial8':
            con.execute('CREATE TABLE kuota_pendamping_jendela(salah TEXT)')
        elif jenis == 'partial9':
            con.execute('PRAGMA user_version=9')
        elif jenis == 'unknown':
            con.execute('PRAGMA user_version=10')
        else:
            con.execute('DROP TRIGGER paket_grant_tolak_update')
    awal = path.read_bytes()
    with pytest.raises((admin_store.StoreBelumSiap, ValueError)):
        admin_store.migrasikan_kuota_pendamping(path)
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(path):
            pass
    assert path.read_bytes() == awal


def test_reader7_lengkap_bukan_izin_migrasi_kuota(tmp_path):
    path = tmp_path/'admin.db'
    siapkan8(path)
    # Admin7 tanpa paket tetap tidak memenuhi sumber migrasi kuota.
    with closing(sqlite3.connect(path)) as con, con:
        con.execute('PRAGMA foreign_keys=OFF')
        for tabel in ('paket_rekonsiliasi','paket_grant','paket_receipt','paket_invoice','paket_akun'):
            con.execute('DROP TABLE '+tabel)
        con.execute('PRAGMA user_version=7')
    with admin_store.buka_baca(path):
        pass
    awal = path.read_bytes()
    with pytest.raises(admin_store.StoreBelumSiap):
        admin_store.migrasikan_kuota_pendamping(path)
    assert path.read_bytes() == awal


def test_reader_partial8_tolak_tanpa_migrasi(tmp_path):
    path = tmp_path/'admin.db'
    siapkan8(path)
    with closing(sqlite3.connect(path)) as con, con:
        con.execute('CREATE TABLE kuota_pendamping_jendela(salah TEXT)')
    awal = path.read_bytes()
    with pytest.raises(admin_store.StoreBelumSiap):
        with admin_store.buka_baca(path):
            pass
    assert path.read_bytes() == awal


def test_migrasi_crash_ddl_rollback_versi_dan_tabel(tmp_path, monkeypatch):
    path = tmp_path/'admin.db'
    siapkan8(path)
    awal = baris(path)
    monkeypatch.setattr(schema, 'DDL', schema.DDL + '\nSQL_SINTETIS_RUSAK;\n')
    with pytest.raises(sqlite3.Error):
        admin_store.migrasikan_kuota_pendamping(path)
    assert baris(path) == awal
    with admin_store.buka_baca(path) as con:
        assert con.execute('PRAGMA user_version').fetchone()[0] == 8


def test_writer_path_trial_unknown_replay_finalisasi_dan_no_get_write(tmp_path):
    path = tmp_path/'admin.db'
    siapkan8(path)
    admin_store.migrasikan_kuota_pendamping(path)
    r = reserve(path)
    assert r.boleh_outbound and not reserve(path).boleh_outbound
    q.tandai_unknown(path, r.ikatan, sekarang=T0+3)
    assert q.baca_status(path, OWNER, fitur='balasan_pendamping', sekarang=T0+4).direservasi == 1
    with pytest.raises(q.KonflikKuota):
        q.lepaskan(path, r.ikatan, sekarang=T0+4, tanpa_output_terbukti=True)
    q.finalisasi(path, r.ikatan, sekarang=T0+4, hasil_valid_tersimpan=True, rekonsiliasi=True)
    awal = baris(path)
    assert q.baca_operasi(path, OWNER, r.ikatan.operasi_id, fitur=r.ikatan.fitur).status == 'completed'
    assert q.baca_status(path, OWNER, fitur=r.ikatan.fitur, sekarang=T0+5).tersisa == 9
    assert baris(path) == awal
    assert q.baca_operasi(path, OWNER, 'operasi_tidak_ada', fitur=r.ikatan.fitur) is None


def test_sumber_pro_tidak_boleh_invoice_asing_pada_metadata_window(tmp_path):
    path = tmp_path/'admin.db'
    siapkan8(path)
    inv=v2.buat_invoice(path,OWNER,(1,),kode='jago_pro',penagihan='tahunan',
                       invoice_id='inv_'+'a'*32,idempotency_key='invoice_sintetis',
                       provider='sintetis',merchant='sintetis',sekarang=T0+2,kedaluwarsa=T0+100,
                       pemilik_profil=lambda _:OWNER,sakelar=ON)
    bukti=d.Pembayaran('sintetis','transaksi_sintetis',inv['invoice_id'],OWNER,inv['rupiah'],
                       'IDR','qris','sintetis','settlement',True)
    v1.terapkan_pembayaran(path,OWNER,bukti,sekarang=T0+3,sakelar=ON)
    admin_store.migrasikan_kuota_pendamping(path)
    reserve(path,sekarang=T0+d.DURASI_TRIAL)
    # Restore sintetis salah sumber tetapi hash/angka window tidak berubah.
    with closing(sqlite3.connect(path)) as con,con:
        ddl=con.execute("SELECT sql FROM sqlite_master WHERE name='kuota_pendamping_jendela_tolak_update'").fetchone()[0]
        con.execute('DROP TRIGGER kuota_pendamping_jendela_tolak_update')
        con.execute("UPDATE kuota_pendamping_jendela SET sumber_id=?",('inv_'+'b'*32,))
        con.execute(ddl)
    assert q.baca_status(path,OWNER,fitur='balasan_pendamping',sekarang=T0+d.DURASI_TRIAL).status=='storage_tidak_terverifikasi'
    with pytest.raises(q.KonflikKuota):
        reserve(path,operasi='operasi_setelah_rusak',sekarang=T0+d.DURASI_TRIAL)


@pytest.mark.parametrize('status', ['reserved', 'unknown', 'completed', 'released'])
def test_backup9_unknown_pending_wajib_rekonsiliasi(tmp_path, status):
    bundle = _buat_bundle(tmp_path)
    path = bundle/'admin-control.db'
    (bundle/'manifest.json').unlink()  # Manifest fixture baru sesudah writer sintetis selesai.
    siapkan8(path)
    admin_store.migrasikan_kuota_pendamping(path)
    r = reserve(path)
    if status == 'unknown':
        q.tandai_unknown(path, r.ikatan, sekarang=T0+3)
    elif status == 'completed':
        q.finalisasi(path, r.ikatan, sekarang=T0+3, hasil_valid_tersimpan=True)
    elif status == 'released':
        q.lepaskan(path, r.ikatan, sekarang=T0+3, tanpa_output_terbukti=True)
    admin_backup.buat_manifest(bundle, bundle_id='kuota-sintetis', cutoff=T0+5)
    sebelum = {p.name:p.read_bytes() for p in bundle.iterdir()}
    hasil = admin_backup.validasi_bundle(bundle)
    assert hasil.versi_admin == 9
    assert hasil.operasi_kuota_pending == int(status == 'reserved')
    assert hasil.operasi_kuota_unknown == int(status == 'unknown')
    assert hasil.perlu_rekonsiliasi == (status in ('reserved','unknown'))
    pulih = admin_backup.rehearsal_bundle(bundle, migrator_ai=ai_store.siapkan, target_admin=9)
    assert pulih == hasil
    assert {p.name:p.read_bytes() for p in bundle.iterdir()} == sebelum
