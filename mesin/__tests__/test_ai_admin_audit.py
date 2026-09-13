"""Audit tes AI memakai SQLite dan provider sintetis saja."""
import sqlite3
from dataclasses import fields

import pytest
import ai_store
import ai_admin

ACTOR = 'akun_' + 'a'*32


def test_migrasi_ai_satu_ke_dua_idempoten_tanpa_backfill_actor(tmp_path):
    path=tmp_path/'ai.db'
    ai_store.siapkan(path,sekarang=100)
    with sqlite3.connect(path) as kon:
        kon.execute('DROP TABLE audit_uji_admin')
        kon.execute('PRAGMA user_version=1')
    ai_store.siapkan(path,sekarang=101)
    ai_store.siapkan(path,sekarang=102)
    with sqlite3.connect(path) as kon:
        assert kon.execute('PRAGMA user_version').fetchone()[0]==2
        assert kon.execute('SELECT COUNT(*) FROM audit_uji_admin').fetchone()[0]==0
        assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert kon.execute('PRAGMA foreign_key_check').fetchall()==[]


def test_reservasi_audit_actor_dan_ledger_satu_transaksi(tmp_path):
    path=tmp_path/'ai.db'; ai_store.siapkan(path,sekarang=100)
    ai_store.reservasi(path,'uji_1','uji_sintetis',None,'model',1,sekarang=100,actor_id=ACTOR)
    with pytest.raises(ai_store.Ditolak):
        ai_store.reservasi(path,'uji_1','uji_sintetis',None,'model',1,sekarang=200,actor_id=ACTOR)
    ai_store.selesaikan(path,'uji_1',status='tak_pasti',sekarang=101)
    page=ai_admin.daftar_riwayat(path,actor_id=ACTOR)
    assert page.total==1 and page.item[0].status=='tak_pasti'
    assert {f.name for f in fields(page.item[0])}=={'sumber','id','actor_id','aksi','status','dibuat','field'}
    with sqlite3.connect(path) as kon:
        kon.execute("CREATE TRIGGER gagal_audit BEFORE INSERT ON audit_uji_admin BEGIN SELECT RAISE(ABORT,'uji'); END")
    with pytest.raises(sqlite3.IntegrityError):
        ai_store.reservasi(path,'uji_2','uji_sintetis',None,'model',1,sekarang=10000,actor_id=ACTOR)
    with sqlite3.connect(path) as kon:
        assert kon.execute("SELECT COUNT(*) FROM ledger WHERE operasi_id='uji_2'").fetchone()[0]==0


@pytest.mark.parametrize('actor,fitur', [('rahasia','uji_sintetis'),(ACTOR,'cerita'),(True,'uji_sintetis')])
def test_actor_invalid_ditolak_sebelum_tulis(tmp_path,actor,fitur):
    path=tmp_path/'ai.db'; ai_store.siapkan(path,sekarang=100)
    with pytest.raises(ValueError):
        ai_store.reservasi(path,'uji_1',fitur,None,'model',1,sekarang=100,actor_id=actor)
    with sqlite3.connect(path) as kon:
        assert kon.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]==0


def test_audit180_tetap_ada_setelah_ledger90_purge(tmp_path):
    path=tmp_path/'ai.db'; ai_store.siapkan(path,sekarang=100)
    ai_store.reservasi(path,'uji_1','uji_sintetis',None,'model',1,sekarang=100,actor_id=ACTOR)
    ai_store.selesaikan(path,'uji_1',status='selesai',sekarang=101)
    ai_store.purge(path,sekarang=100+100*86400)
    with sqlite3.connect(path) as kon:
        assert kon.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]==0
    assert ai_admin.daftar_riwayat(path).total==1
    ai_store.purge(path,sekarang=100+181*86400)
    assert ai_admin.daftar_riwayat(path).total==0


def test_reader_tidak_membuat_db_hilang_dan_filter_invalid(tmp_path):
    path=tmp_path/'missing.db'
    with pytest.raises(sqlite3.OperationalError):
        ai_admin.daftar_riwayat(path)
    assert not path.exists()
    for kwargs in ({'halaman':0},{'per_halaman':101},{'aksi':'payload'},{'actor_id':'kontak'}, {'mulai':10,'selesai':1}):
        with pytest.raises(ValueError):
            ai_admin.daftar_riwayat(path,**kwargs)
