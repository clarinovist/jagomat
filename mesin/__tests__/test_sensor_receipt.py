"""Receipt konfirmasi immutable, bukan pointer mutable paling baru."""
import time

import auth
import admin_store
import database
import sensor_http as h
import sensor_store as s
import sensor_schema
from test_subscription_service import keluarga
from test_subscription_store import T0
from test_learning_cycle_http import _buat_sesi_selesai


def test_hook_pertama_tetap_receipt_pertama(keluarga,monkeypatch):
    k=keluarga
    sensor_schema.migrasikan(k.admin)
    monkeypatch.setattr(h,'SIAP',True)
    monkeypatch.setattr(auth,'BERKAS_SANDI',k.auth)
    monkeypatch.setattr(admin_store,'BAWAAN',k.admin)
    monkeypatch.setattr(database,'BAWAAN',k.db)
    monkeypatch.setattr(time,'time',lambda:T0+10)
    s.setuju(k.admin,k.auth,k.principal,hasil=True,chat=False,sekarang=T0)
    with database.buka(k.db) as c:
        siswa=database.tambah_siswa(c,'Anak-receipt','P3',pemilik=k.principal.pengguna)
        sid=_buat_sesi_selesai(c,siswa,seed=8)
        c.execute("UPDATE sesi SET dibuat=datetime(?,'unixepoch','+7 hours') WHERE id=?",(T0+1,sid))
        first=database.konfirmasi_hasil(c,sid,k.principal.pengguna)
    h.sesi(sid,'disiapkan',pengguna=k.principal.pengguna,peran='guru')
    with database.buka(k.db) as c:
        # Koreksi mutable menginvalidasi pointer; snapshot pertama tidak berubah.
        b=database.isi_sesi(c,sid)[0]
        database.simpan_diagnosis(c,b['jawaban_id'],benar=True,kode_usulan=None,kode_final=None,
                                 malrule_id=None,alasan='koreksi sintetis',manual=True)
        second=database.konfirmasi_hasil(c,sid,k.principal.pengguna)
    assert first!=second
    h.sesi(sid,'dikonfirmasi',pengguna=k.principal.pengguna,peran='guru',konfirmasi_id=second)
    with s.buka(k.admin) as c:
        assert not c.execute('SELECT 1 FROM sensor_hasil').fetchone()
    h.sesi(sid,'dikonfirmasi',pengguna=k.principal.pengguna,peran='guru',konfirmasi_id=first)
    with s.buka(k.admin) as c:
        row=c.execute('SELECT benar,kode_k FROM sensor_hasil').fetchone()
        assert row is not None and row['benar']==0 and row['kode_k']==1
