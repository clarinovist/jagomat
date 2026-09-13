"""Regresi review query admin; identitas dan waktu seluruhnya sintetis."""
from datetime import datetime

import admin_queries as q
from test_admin_queries import db, _akun, _isi_anomali  # noqa: F401


def test_jendela_aktivitas_tidak_menghitung_sesi_masa_depan(db):
    _isi_anomali(db)
    db.execute("INSERT INTO sesi(id,siswa_id,level,tanggal,dibuat) VALUES(99,1,'P3','2099-01-01','2099-01-01 00:00:00')")
    hasil = q.ringkasan_admin(db, q.buat_konteks(db, _akun()), sekarang_wib=datetime(2026, 9, 13, 12))
    assert hasil.jumlah_sesi == 4
    assert hasil.sesi_7_hari == 2
    assert hasil.sesi_30_hari == 3


def test_cari_login_eksplisit_literal_bukan_login_warisan(db):
    _isi_anomali(db)
    akun = _akun()
    akun[3]['pengguna'] = 'login_%satu'
    konteks = q.buat_konteks(db, akun)
    assert [s.id for s in q.daftar_siswa(db, konteks, cari='login_%').item] == [1]
    assert q.daftar_siswa(db, konteks, cari='login-Z').item == ()
    assert q.daftar_siswa(db, konteks, cari='TakAda').item == ()


def test_daftar_masalah_ringkasan_dibatasi_tanpa_mengurangi_count(db):
    akun = [{'id_akun': 'akun_uji_%d' % i, 'pengguna': 'yatim-%d' % i,
             'peran': 'murid', 'siswa_id': i + 100} for i in range(130)]
    hasil = q.ringkasan_admin(db, q.buat_konteks(db, akun))
    assert len(hasil.login_bermasalah) <= 25
    assert dict((x.kode, x.jumlah) for x in hasil.perhatian)['orphan_login'] == 130


def test_owner_berperan_murid_tidak_hilang_dari_daftar_anomali(db):
    _isi_anomali(db)
    db.execute("UPDATE siswa SET pemilik='login-satu' WHERE id=2")
    hasil = q.daftar_keluarga(db, q.buat_konteks(db, _akun()))
    salah = [k for k in hasil.item if k.pengguna == 'login-satu']
    assert len(salah) == 1
    assert salah[0].id_akun is None
    assert salah[0].kategori == 'pemilik_tanpa_akun'
