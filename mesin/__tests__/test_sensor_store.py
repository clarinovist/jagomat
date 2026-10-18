"""Sensor menggunakan keluarga dan outcome sintetis; tanpa provider."""
import sqlite3

import pytest
import admin_store
import sensor_domain as d
import sensor_http as h
import sensor_schema as schema
import sensor_store as s
from test_subscription_service import keluarga
from test_subscription_store import T0, dump


@pytest.fixture
def sensor(keluarga, monkeypatch):
    k = keluarga
    schema.migrasikan(k.admin)
    monkeypatch.setattr(s, 'GAGAL', False)
    s.setuju(k.admin, k.auth, k.principal, hasil=True, chat=True, sekarang=T0)
    k.izin = s.izin(k.admin, k.principal.id_akun, sekarang=T0)
    return k


def catat(k, kode, **kw):
    return s.catat_sesi(k.admin, k.izin, 123, kode=kode, dibuat=T0+1,
                        jalur='terpandu', sekarang=T0+2, **kw)


def test_schema_migrasi_idempoten_tanpa_consent(keluarga):
    k = keluarga
    with admin_store.buka_baca(k.admin) as c:
        assert not schema.validasi(c)
    schema.migrasikan(k.admin)
    awal = dump(k.admin)
    schema.migrasikan(k.admin)
    assert dump(k.admin) == awal
    with s.buka(k.admin) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0] == 7
        assert not c.execute('SELECT 1 FROM sensor_peserta').fetchone()
    with sqlite3.connect(k.admin) as c:
        c.execute('DROP INDEX sensor_episode_retensi')
    with pytest.raises((ValueError, RuntimeError)):
        with admin_store.buka_baca(k.admin):
            pass


def test_episode_dedup_dan_tidak_mengarang_prepare(sensor):
    k = sensor
    assert not catat(k, 'dikirim')
    assert catat(k, 'disiapkan')
    assert not catat(k, 'disiapkan')
    assert catat(k, 'dikirim')
    assert not catat(k, 'dikirim')
    with s.buka(k.admin) as c:
        rows = list(c.execute('SELECT * FROM sensor_event'))
        assert len(rows) == 2
        assert all(len(r['token']) == 64 and r['token'] != '123' for r in rows)
        assert not {'sesi_id','siswa_id','jawaban','teks'} & set(rows[0].keys())


def test_consent_race_reconsent_boot_cabut(sensor, monkeypatch):
    k = sensor
    catat(k, 'disiapkan')
    assert s.catat_chat(k.admin,k.izin,'request-sintetis',dibuat=T0+1,sekarang=T0+2,kategori='hasil')
    s.setuju(k.admin,k.auth,k.principal,hasil=False,chat=False,sekarang=T0+3)
    assert not catat(k, 'dikirim')
    assert not s.catat_chat(k.admin,k.izin,'lain',dibuat=T0+4,sekarang=T0+4,kategori='hasil')
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_event').fetchone()
        assert not c.execute('SELECT 1 FROM sensor_chat').fetchone()
    assert s.izin(k.admin,k.principal.id_akun,sekarang=T0+4)
    monkeypatch.setattr(s,'BOOT','boot-baru')
    assert s.izin(k.admin,k.principal.id_akun,sekarang=T0+4) is None
    assert s.kesehatan(k.admin,siap=True,sekarang=T0+4)['status'] == 'menunggu_izin_ulang'
    s.cabut(k.admin,k.auth,k.principal)
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_peserta').fetchone()


def test_snapshot_izin_berubah_ditolak_sebelum_tulis(sensor):
    k=sensor
    catat(k,'disiapkan')
    with s.buka(k.admin,tulis=True) as c:
        c.execute('UPDATE sensor_peserta SET chat=0 WHERE akun_id=?',(k.principal.id_akun,))
    assert not s.catat_chat(k.admin,k.izin,'in-flight',dibuat=T0+1,sekarang=T0+2,kategori='hasil')
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_chat').fetchone()


def test_sumber_lama_dan_payload_asing_ditolak(sensor):
    k = sensor
    assert not s.catat_sesi(k.admin,k.izin,1,kode='disiapkan',dibuat=T0-1,jalur='manual',sekarang=T0+2)
    assert not s.catat_chat(k.admin,k.izin,'lama',dibuat=T0-1,sekarang=T0+2,kategori='hasil')
    with pytest.raises(ValueError):
        catat(k, 'jawaban_bebas')
    with pytest.raises(ValueError):
        s.catat_chat(k.admin,k.izin,'raw',dibuat=T0+1,sekarang=T0+2,kategori='nama pribadi')


def test_hasil_konfirmasi_pertama_saja(sensor):
    k = sensor
    rows = [{'benar':True,'kode_final':None,'dilewati':False},
            {'benar':False,'kode_final':'K','dilewati':False},
            {'benar':None,'kode_final':None,'dilewati':True}]
    hasil = d.ringkas_hasil(rows)
    assert hasil['jumlah'] == 3 and hasil['benar'] == hasil['kode_k'] == hasil['belum_jelas'] == 1
    catat(k,'disiapkan')
    assert catat(k,'dikonfirmasi',hasil=hasil)
    assert not catat(k,'dikonfirmasi',hasil=d.ringkas_hasil(rows[:1]))
    with s.buka(k.admin) as c:
        assert c.execute('SELECT jumlah FROM sensor_hasil').fetchone()[0] == 3


def test_retensi_detail_tidak_menunggu_consent(sensor):
    k = sensor
    catat(k,'disiapkan')
    s.catat_chat(k.admin,k.izin,'request',dibuat=T0+1,sekarang=T0+2,kategori='hasil')
    s.retensi(k.admin,sekarang=T0+2+d.RETENSI_DETAIL)
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_episode').fetchone()
        assert not c.execute('SELECT 1 FROM sensor_chat').fetchone()
        assert c.execute('SELECT 1 FROM sensor_peserta').fetchone()
    s.retensi(k.admin,sekarang=T0+d.RETENSI_CONSENT)
    assert s.izin(k.admin,k.principal.id_akun,sekarang=T0+d.RETENSI_CONSENT) is None


def test_transformasi_lazy_tidak_dipanggil_saat_izin_berubah(sensor):
    k=sensor
    catat(k,'disiapkan')
    s.cabut(k.admin,k.auth,k.principal)
    def tolak():
        raise AssertionError('sumber diproses setelah cabut')
    assert not catat(k,'dikonfirmasi',hasil=tolak)
    assert not s.catat_chat(k.admin,k.izin,'q',dibuat=T0+1,sekarang=T0+2,kategori=tolak)


def test_hapus_sumber_saat_boot_berubah(sensor,monkeypatch):
    k=sensor
    catat(k,'disiapkan')
    monkeypatch.setattr(s,'BOOT','boot-lain')
    s.hapus_sumber_sesi(k.admin,k.principal.id_akun,123)
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_episode').fetchone()


def test_kesehatan_nonaktif_bukan_nol(sensor):
    k = sensor
    assert s.kesehatan(k.admin,siap=False,sekarang=T0)['status']=='nonaktif'
    assert s.kesehatan(k.admin,siap=True,sekarang=T0)['status']=='siap_best_effort'
    s.gangguan()
    assert s.kesehatan(k.admin,siap=True,sekarang=T0)['status']=='terganggu'


def test_klasifikasi_chat_ambigu_bukan_label_anak():
    assert d.kategori_chat('Tolong jelaskan konsep ini') == 'penjelasan'
    assert d.kategori_chat('Jelaskan soal latihan') == 'belum_diketahui'
    assert d.kategori_chat('Halo') == 'belum_diketahui'


def test_izin_opsional_tidak_boleh_menyimpan_hasil(sensor):
    k = sensor
    s.setuju(k.admin,k.auth,k.principal,hasil=False,chat=False,sekarang=T0)
    k.izin=s.izin(k.admin,k.principal.id_akun,sekarang=T0)
    catat(k,'disiapkan')
    catat(k,'dikonfirmasi',hasil=d.ringkas_hasil([{'benar':True,'kode_final':None,'dilewati':False}]))
    assert not s.catat_chat(k.admin,k.izin,'q',dibuat=T0+1,sekarang=T0+2,kategori='hasil')
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_hasil').fetchone()


def test_family_deletion_menghapus_semua_sensor(sensor):
    from family_deletion import _ubah_admin
    k=sensor
    catat(k,'disiapkan')
    _ubah_admin(k.admin,k.principal.id_akun)
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_peserta').fetchone()
        assert not c.execute('SELECT 1 FROM sensor_event').fetchone()
