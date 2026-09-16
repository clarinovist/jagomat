"""Regresi PG menyeluruh dengan akun, sesi, dan arsip sintetis."""
from dataclasses import replace
from datetime import date
import json
import sqlite3

import pytest

import database
import students
import student_pages
import student_submissions as kiriman
import reports
import teacher_pages
from choice_store import daftar_pilihan
from choice_generation import buat_lembar_pilihan, kandidat, kebijakan_soal, pilihan_soal
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID
import topics


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'pg.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa = database.tambah_siswa(kon, 'Sintetis', pemilik='guru')
        sesi = database.buat_sesi(kon, siswa, 7, jumlah_soal=3, format_jawaban='pilihan_ganda')
        yield kon, siswa, sesi, path


@pytest.fixture
def db_terjaga(db):
    kon, siswa, sesi, path = db
    def jaga(aksi, tabel, kolom, _db, _pemicu):
        if aksi == sqlite3.SQLITE_READ and kolom in {'kunci','kode_final','kode_usulan','malrule_id','alasan'}:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    kon.set_authorizer(jaga)
    yield db
    kon.set_authorizer(lambda *args: sqlite3.SQLITE_OK)


def data_pilihan(kon, sesi):
    return {'revisi_pekerjaan': str(kiriman.revisi(kon, sesi)),
            **{f'opsi_{sid}': p.opsi[0].id for sid, p in daftar_pilihan(kon,sesi).items()}}


def test_pg_baca_simpan_tanpa_kunci(db_terjaga):
    kon,siswa,sesi,_ = db_terjaga
    html = student_pages.halaman_kerja_baru(kon,siswa,sesi).decode()
    assert 'name="opsi_' in html and 'name="jwb_' not in html
    assert 'Belum menjawab' in html
    assert students.simpan_jawaban_murid(kon,siswa,sesi,data_pilihan(kon,sesi)) == 3


def test_ganti_kosong_parsial_dan_stale(db):
    kon,siswa,sesi,_ = db
    data = data_pilihan(kon,sesi)
    students.simpan_jawaban_murid(kon,siswa,sesi,data)
    awal = list(kon.execute('SELECT * FROM jawaban'))
    with pytest.raises(kiriman.VersiBerubah):
        students.simpan_jawaban_murid(kon,siswa,sesi,data)
    assert list(kon.execute('SELECT * FROM jawaban')) == awal
    sid = next(iter(daftar_pilihan(kon,sesi)))
    students.simpan_jawaban_murid(kon,siswa,sesi,{'revisi_pekerjaan':str(kiriman.revisi(kon,sesi)),f'opsi_{sid}':'',f'cara_{sid}':'Aku mencoba'})
    assert kon.execute('SELECT jawaban,cara FROM jawaban WHERE sesi_soal_id=?',(sid,)).fetchone()[:] == ('','Aku mencoba')
    assert kon.execute("SELECT COUNT(*) FROM jawaban WHERE jawaban!=''").fetchone()[0] == 2


@pytest.mark.parametrize('rusak', ['asing','teks','tanpa_revisi'])
def test_pg_payload_tidak_sah_tanpa_efek_samping(db,rusak):
    kon,siswa,sesi,_=db
    data=data_pilihan(kon,sesi)
    sid=next(iter(daftar_pilihan(kon,sesi)))
    if rusak=='asing':data[f'opsi_{sid}']='opsi_999'
    elif rusak=='teks':data[f'jwb_{sid}']='24'
    else:data.pop('revisi_pekerjaan')
    with pytest.raises(ValueError):students.simpan_jawaban_murid(kon,siswa,sesi,data)
    assert kon.execute('SELECT COUNT(*) FROM jawaban').fetchone()[0]==0


def test_arsip_diagnosis_konfirmasi_dan_pemetaan_terpisah(db):
    kon,siswa,sesi,_=db
    data={'revisi_pekerjaan':'0'}
    for b in database.isi_sesi(kon,sesi):
        p=daftar_pilihan(kon,sesi)[b['sesi_soal_id']]
        data[f'opsi_{p.sesi_soal_id}']=next(o.id for o in p.opsi if o.nilai==b['kunci'])
    students.simpan_jawaban_murid(kon,siswa,sesi,data)
    kiriman.arsipkan(kon,sesi,'akun');reports.diagnosa_murid(kon,sesi);database.tandai_selesai(kon,sesi)
    assert all(b['benar']==1 and b['kode_final'] is None for b in database.isi_sesi(kon,sesi))
    assert kon.execute('SELECT COUNT(*) FROM pengiriman_pilihan').fetchone()[0]==3
    from learning_cycle_service import konfirmasi_dari_form
    sebelum=kon.total_changes
    with pytest.raises(ValueError,match='pemetaan'):
        konfirmasi_dari_form(kon,sesi,'guru',{'sertakan_pemetaan':'1'})
    assert kon.total_changes==sebelum
    kid=database.konfirmasi_hasil(kon,sesi,'guru')
    assert kon.execute('SELECT COUNT(*) FROM konfirmasi_pilihan WHERE konfirmasi_id=?',(kid,)).fetchone()[0]==3
    from learning_cycle import _sesi_bukti_pemetaan, KejadianSiklus
    bukti=database.muat_bukti_siklus(kon,siswa)
    palsu=replace(bukti,kejadian=(*bukti.kejadian,KejadianSiklus(999,'sertakan_pemetaan',date.today(),None,sesi,kid)))
    assert _sesi_bukti_pemetaan(palsu,None)==()
    with pytest.raises(sqlite3.IntegrityError):
        kon.execute("INSERT INTO kejadian_belajar(siswa_id,sesi_id,konfirmasi_id,jenis) VALUES (?,?,?,'sertakan_pemetaan')",(siswa,sesi,kid))
    cetak=teacher_pages.halaman_lembar(kon,sesi).decode()
    assert 'Kunci:' not in cetak and 'Latihan pilihan ganda' in cetak
    assert 'Kunci:' in teacher_pages.halaman_lembar(kon,sesi,True).decode()
    with pytest.raises(sqlite3.IntegrityError):database.hapus_sesi(kon,sesi)


def test_salah_tidak_otomatis_diagnosis_dan_manual_tetap(db):
    kon,siswa,sesi,_=db
    pilihan=daftar_pilihan(kon,sesi)
    for b in database.isi_sesi(kon,sesi):
        nilai=next(o.nilai for o in pilihan[b['sesi_soal_id']].opsi if o.nilai!=b['kunci'])
        database.simpan_jawaban(kon,b['sesi_soal_id'],nilai)
    reports.diagnosa_murid(kon,sesi)
    assert all(b['benar']==0 and b['kode_final'] is None and b['malrule_id'] is None for b in database.isi_sesi(kon,sesi))
    b=database.isi_sesi(kon,sesi)[0]
    database.simpan_diagnosis(kon,b['jawaban_id'],False,None,'H',None,'ditinjau',True)
    reports.diagnosa_murid(kon,sesi)
    assert database.isi_sesi(kon,sesi)[0]['kode_final']=='H'
    assert database.miskonsepsi_berulang(kon,siswa)==[]


@pytest.mark.parametrize('topik', [n for n in topics.daftar_topik() if n!='campuran'])
def test_sweep_pg_seluruh_level_seed_dan_kunci(topik):
    for level in topics.ambil(topik).komposisi:
        for seed in range(200):
            lembar=buat_lembar_pilihan(seed,level=level,topik=topik)
            for nomor,soal in enumerate(lembar.soal,1):
                p=pilihan_soal(soal,nomor,'a'*64,seed,nomor)
                assert len(p.opsi) in (3,4,5)
                assert sum(o.nilai==soal.kunci for o in p.opsi)==1


@pytest.fixture
def server(tmp_path,monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    with s.buka() as kon:
        siswa=database.tambah_siswa(kon,'feby',pemilik='guru')
        sesi=database.buat_sesi(kon,siswa,7,jumlah_soal=3,format_jawaban='pilihan_ganda')
    yield s,siswa,sesi
    s.berhenti()


@pytest.mark.parametrize('tautan',[False,True])
def test_http_pg_kirim_dan_arsip(server,tautan):
    s,siswa,sesi=server
    with s.buka() as kon:
        if tautan:
            import share_links
            jalur='/mulai/'+share_links.buat(kon,sesi)
        else:jalur=f'/murid/kerjakan/{sesi}'
        data=data_pilihan(kon,sesi)
    auth=None if tautan else ('feby',SANDI_MURID)
    kode,html,_=s.minta(jalur,auth=auth)
    assert kode==200 and 'name="opsi_' in html
    data['aksi']='selesai'
    kode,_,_=s.minta(jalur,auth=auth,data=data)
    assert kode==200
    with s.buka() as kon:
        assert kon.execute('SELECT selesai FROM sesi WHERE id=?',(sesi,)).fetchone()[0]
        assert kon.execute('SELECT COUNT(*) FROM pengiriman_pilihan').fetchone()[0]==3


def test_http_buat_manual_dan_gabungan(server):
    s,siswa,_=server
    for jalur,data in [(f'/sesi-baru/{siswa}',{'topik':'pola-bilangan','mode':'diagnostik','jumlah_soal':'10'}),
                       (f'/sesi-gabungan/{siswa}',{'topik':['pola-bilangan','geometri-datar'],'mode':'drill','jumlah_soal':'10'})]:
        # urllib helper tidak doseq; uji gabungan melalui service, route tunggal melalui HTTP.
        if 'gabungan' in jalur:
            with s.buka() as kon:
                sid=database.buat_sesi_gabungan(kon,siswa,34,data['topik'],format_jawaban='pilihan_ganda',jumlah_soal=10)
                assert len(daftar_pilihan(kon,sid))==10
        else:
            kode,html,_=s.minta(jalur,auth=('guru',SANDI_GURU),data=dict(data,format_jawaban='pilihan_ganda'))
            assert kode==200 and 'berhasil dibuat' in html
    with s.buka() as kon:
        assert kon.execute("SELECT COUNT(*) FROM sesi WHERE format_jawaban='pilihan_ganda'").fetchone()[0]==3
