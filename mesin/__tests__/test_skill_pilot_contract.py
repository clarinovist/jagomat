"""Kontrak dan pembaca pilot aditif; belum aktivasi penulis aplikasi."""
from dataclasses import replace
import json
import sqlite3
import pytest
import database
import question_views
import skill_pilot as p
import skill_pilot_schema as schema
from skill_pilot_contract import (ButirKontrakPilot, KontrakPilot, serialisasi,
                                  deserialisasi, fingerprint)
from skill_pilot_selector import pilih_probe
from skill_pilot_store import baca_kontrak, validasi_konfirmasi


@pytest.fixture
def db(tmp_path):
    path=tmp_path/'pilot-sintetis.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa=database.tambah_siswa(kon,'Sintetis',tingkat='P3',pemilik='guru')
        yield kon,siswa


def _sumber(db):
    kon,siswa=db
    konteks=p.KonteksPilot(p.LANGSUNG,'P3','teks-v1')
    probe=pilih_probe(konteks,71,4)
    sesi=database.buat_sesi_dari_urutan(kon,siswa,71,(p.POLA,)*4,topik='geometri-datar',
        level='P3',soal_terpilih=tuple(x.soal for x in probe))
    sumber=kon.execute('''SELECT ss.*,so.template_id,so.parameter,so.level,so.cerita
        FROM sesi_soal ss JOIN soal so ON so.id=ss.soal_id WHERE ss.sesi_id=? ORDER BY nomor''',(sesi,)).fetchall()
    butir=tuple(ButirKontrakPilot(b['nomor'],b['id'],konteks,probe[i].sidik_variasi,
                 question_views.penyajian_dari_baris(b).fingerprint_penyajian) for i,b in enumerate(sumber))
    return KontrakPilot(siswa,sesi,'P3',probe[0].versi_generator,butir,seed=71)


def _marker(kon,k):
    kon.execute('INSERT INTO pilot_sesi VALUES(?,?,?,?)',(k.sesi_id,1,serialisasi(k),fingerprint(k)))


def _konfirmasi(kon,k):
    database.tandai_selesai(kon,k.sesi_id)
    return database.konfirmasi_hasil(kon,k.sesi_id,'guru',dilewati={b.sesi_soal_id for b in k.butir})


def test_roundtrip_bukan_campuran_dan_strict(db):
    k=_sumber(db)
    assert deserialisasi(serialisasi(k))==k
    assert serialisasi(deserialisasi(serialisasi(k)))==serialisasi(k)
    isi=json.loads(serialisasi(k))
    for perubahan in ({'versi':2},{'siswa_id':True},{'asing':1}):
        with pytest.raises(ValueError): deserialisasi(json.dumps({**isi,**perubahan}))
    with pytest.raises(ValueError): deserialisasi('{"versi":1,'+serialisasi(k)[1:])
    with pytest.raises(ValueError): replace(k,butir=(k.butir[0],k.butir[0]))
    with pytest.raises(ValueError): replace(k,butir=tuple(replace(b,konteks=replace(b.konteks,profil_parameter='P4')) for b in k.butir))
    with pytest.raises(ValueError): replace(k,butir=tuple(replace(b,konteks=None) for b in k.butir))


def test_reader_v1_tanpa_backfill_dan_migrasi_idempoten(db):
    kon,siswa=db
    k=_sumber(db)
    assert baca_kontrak(kon,k.sesi_id,siswa) is None
    with pytest.raises(ValueError,match='bukan milik'):
        baca_kontrak(kon,k.sesi_id,siswa+1)
    lama=tuple(kon.execute('SELECT * FROM sesi').fetchall())
    schema.siapkan_pilot(kon)
    dump=tuple(kon.iterdump())
    schema.siapkan_pilot(kon)
    assert tuple(kon.iterdump())==dump
    assert tuple(kon.execute('SELECT * FROM sesi').fetchall())==lama
    assert baca_kontrak(kon,k.sesi_id,siswa) is None
    assert kon.execute('PRAGMA foreign_key_check').fetchone() is None
    assert kon.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_migrasi_gagal_atomik(db,monkeypatch):
    kon,_=db
    sebelum=tuple(kon.iterdump())
    monkeypatch.setattr(schema,'SKEMA_PILOT',schema.SKEMA_PILOT+'\nINSERT INTO tabel_tidak_ada VALUES (1);\n')
    with pytest.raises(sqlite3.OperationalError): schema.siapkan_pilot(kon)
    assert tuple(kon.iterdump())==sebelum


def test_reader_mencocokkan_sumber_dan_arsip_tanpa_tulis(db):
    kon,siswa=db
    k=_sumber(db)
    schema.siapkan_pilot(kon)
    _marker(kon,k)
    sebelum=tuple(kon.iterdump())
    assert baca_kontrak(kon,k.sesi_id,siswa)==k
    assert tuple(kon.iterdump())==sebelum
    with pytest.raises(ValueError): baca_kontrak(kon,k.sesi_id,siswa+1)
    assert tuple(kon.iterdump())==sebelum
    kh=_konfirmasi(kon,k)
    # Writer terintegrasi mengarsipkan pada transaksi konfirmasi yang sama.
    assert validasi_konfirmasi(kon,k.sesi_id,siswa,kh)==k
    sebelum=tuple(kon.iterdump())
    assert validasi_konfirmasi(kon,k.sesi_id,siswa,kh)==k
    from skill_pilot_store import muat_bukti
    bukti=muat_bukti(kon,siswa)
    assert len(bukti.butir)==4
    assert {b.konfirmasi_id for b in bukti.butir}=={kh}
    assert tuple(kon.iterdump())==sebelum


@pytest.mark.parametrize('rusak',('sidik','pemilik','nomor','variasi','representasi'))
def test_marker_rusak_tidak_fallback(db,rusak):
    kon,siswa=db
    k=_sumber(db)
    schema.siapkan_pilot(kon)
    if rusak=='pemilik': k=replace(k,siswa_id=siswa+1)
    if rusak=='nomor': k=replace(k,butir=tuple(replace(b,sesi_soal_id=b.sesi_soal_id+99) for b in k.butir))
    if rusak=='variasi': k=replace(k,butir=tuple(replace(b,sidik_variasi='f'*64) for b in k.butir))
    if rusak=='representasi': k=replace(k,butir=tuple(replace(b,konteks=replace(b.konteks,mode_representasi='geometri_datar-v1')) for b in k.butir))
    _marker(kon,k)
    if rusak=='sidik':
        kon.execute('DROP TRIGGER pilot_sesi_tolak_update')
        kon.execute("UPDATE pilot_sesi SET fingerprint=?",('a'*64,))
    sebelum=tuple(kon.iterdump())
    with pytest.raises(ValueError): baca_kontrak(kon,k.sesi_id,siswa)
    assert tuple(kon.iterdump())==sebelum


@pytest.mark.parametrize('hiasan',(True,False))
def test_rujukan_luas_dari_db_tidak_mengarang_variasi(db,hiasan):
    from datetime import date
    from dataclasses import replace
    from topic_plane_geometry import luas_kotak_satuan
    from skill_pilot_store import muat_bukti
    import learning_cycle as lc
    kon,siswa=db
    ids=[]
    for bagian,tanggal in enumerate(('2026-09-10','2026-09-13')):
        soal=tuple(replace(luas_kotak_satuan(8 if hiasan else 3+n+bagian*2,8,
                    konteks=('ubin','keramik','stiker','kancing')[bagian*2+n-1]),level='P3') for n in (1,2))
        sesi=database.buat_sesi_dari_urutan(kon,siswa,100+bagian,(p.POLA_KISI,)*2,
                 topik='geometri-datar',level='P3',soal_terpilih=soal)
        kon.execute('UPDATE sesi SET tanggal=? WHERE id=?',(tanggal,sesi))
        for b in database.isi_sesi(kon,sesi):
            jid=database.simpan_jawaban(kon,b['sesi_soal_id'],b['kunci'])
            database.simpan_diagnosis(kon,jid,True,None,None)
        database.tandai_selesai(kon,sesi)
        kh=database.konfirmasi_hasil(kon,sesi,'guru',cek_pemahaman={
            b['sesi_soal_id']:'bisa_menjelaskan' for b in database.isi_sesi(kon,sesi)})
        kon.execute("INSERT INTO kejadian_belajar(siswa_id,sesi_id,konfirmasi_id,jenis,data) VALUES(?,?,?,'sertakan_pemetaan','{}')",(siswa,sesi,kh))
        ids.append(sesi)
    sebelum=tuple(kon.iterdump())
    b=muat_bukti(kon,siswa)
    k=p.KonteksPilot(p.PRASYARAT,'P3','teks-v1')
    status=lc.penguasaan_pilot(b,siswa,(k,),date(2026,9,21))[0].hasil.status
    assert (status=='terbukti') is (not hiasan)
    assert tuple(kon.iterdump())==sebelum
    if not hiasan:
        butir=database.isi_sesi(kon,ids[-1])[0]
        database.simpan_jawaban(kon,butir['sesi_soal_id'],'0')
        b=muat_bukti(kon,siswa)
        assert lc.penguasaan_pilot(b,siswa,(k,),date(2026,9,21))[0].hasil.status=='perlu_cek'


def test_arsip_immutable_dan_fk(db):
    kon,_=db
    k=_sumber(db)
    schema.siapkan_pilot(kon)
    _marker(kon,k)
    kh=_konfirmasi(kon,k)
    for tabel in ('pilot_sesi','pilot_konfirmasi'):
        for sql in ('DELETE FROM '+tabel,"UPDATE "+tabel+" SET kontrak_json='{}'",
                    'INSERT OR REPLACE INTO '+tabel+' SELECT * FROM '+tabel):
            with pytest.raises(sqlite3.IntegrityError): kon.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute('INSERT INTO pilot_konfirmasi VALUES(?,?,?,?)',(kh+1,k.sesi_id,serialisasi(k),fingerprint(k)))
