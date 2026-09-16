"""Jalur negatif PG, migrasi, provenance, serta batas rilis build-only."""
from dataclasses import replace
from datetime import date
import json
import sqlite3

import pytest

import database
import students
import student_submissions as kiriman
import reports
import attachments
from choice_store import daftar_pilihan, validasi_arsip, format_sesi
from http_test_kit import ServerUji, SANDI_GURU, SANDI_MURID


@pytest.fixture
def db(tmp_path):
    p=tmp_path/'uji.db';database.siapkan(p)
    with database.buka(p) as k:
        siswa=database.tambah_siswa(k,'Sintetis',pemilik='guru')
        sid=database.buat_sesi(k,siswa,4,jumlah_soal=2,format_jawaban='pilihan_ganda')
        yield k,siswa,sid,p


def selesai(k,sid):
    for b in database.isi_sesi(k,sid):
        database.simpan_jawaban(k,b['sesi_soal_id'],b['kunci'])
    kiriman.arsipkan(k,sid,'akun');reports.diagnosa_murid(k,sid);database.tandai_selesai(k,sid)


def test_arsip_tidak_boleh_hilang_dan_konfirmasi_tidak_memperbaikinya_diam_diam(db):
    k,_,sid,_=db;selesai(k,sid)
    kid=database.konfirmasi_hasil(k,sid,'guru')
    k.execute('DROP TRIGGER konfirmasi_pilihan_immutable_delete')
    k.execute('DELETE FROM konfirmasi_pilihan')
    with pytest.raises(ValueError,match='Arsip pilihan'):
        database.konfirmasi_hasil(k,sid,'guru')
    with pytest.raises(ValueError,match='Arsip pilihan'):
        database.muat_bukti_siklus(k,k.execute('SELECT siswa_id FROM sesi WHERE id=?',(sid,)).fetchone()[0])
    assert k.execute('SELECT COUNT(*) FROM konfirmasi_pilihan').fetchone()[0]==0
    assert k.execute('SELECT COUNT(*) FROM konfirmasi_hasil').fetchone()[0]==1


def test_arsip_snapshot_asing_ditolak_db(db):
    k,_,sid,_=db;selesai(k,sid)
    ssid=next(iter(daftar_pilihan(k,sid)))
    kid=k.execute("INSERT INTO konfirmasi_hasil(sesi_id,nomor_urut,guru,fingerprint) VALUES (?,1,'guru','uji')",(sid,)).lastrowid
    with pytest.raises(sqlite3.IntegrityError,match='sumber'):
        k.execute('INSERT INTO konfirmasi_pilihan VALUES (?,?,?,?)',(kid,ssid,'{}','a'*64))
    assert k.execute('SELECT COUNT(*) FROM konfirmasi_pilihan').fetchone()[0]==0


def test_nilai_mentah_di_luar_opsi_ditolak_penyimpanan(db):
    k,_,sid,_=db;ssid=next(iter(daftar_pilihan(k,sid)))
    with pytest.raises(sqlite3.IntegrityError,match='jawaban'):
        database.simpan_jawaban(k,ssid,'jawaban asing')
    assert k.execute('SELECT COUNT(*) FROM jawaban').fetchone()[0]==0


def test_bank_berbeda_membatalkan_pembuatan_tanpa_sesi_parsial(db):
    k,siswa,sid,_=db
    b=database.isi_sesi(k,sid)[0]
    k.execute("UPDATE soal SET kunci='kunci-warisan-berbeda' WHERE id=?",(b['soal_id'],))
    jumlah=k.execute('SELECT COUNT(*) FROM sesi').fetchone()[0]
    with pytest.raises(ValueError,match='Kunci bank'):
        database.buat_sesi(k,siswa,4,jumlah_soal=2,format_jawaban='pilihan_ganda')
    assert k.execute('SELECT COUNT(*) FROM sesi').fetchone()[0]==jumlah
    assert k.execute('SELECT COUNT(*) FROM pilihan_butir').fetchone()[0]==2


def test_format_sesi_tidak_dapat_diubah_atau_dijadikan_terpandu(db):
    k,siswa,sid,_=db
    for sql in ("UPDATE sesi SET format_jawaban='isian' WHERE id=?", "UPDATE sesi SET tujuan='evaluasi' WHERE id=?"):
        with pytest.raises(sqlite3.IntegrityError):k.execute(sql,(sid,))
    assert format_sesi(k,sid)=='pilihan_ganda'


def test_foto_pg_ambigu_dan_sudah_dikirim_tidak_menimpa(db):
    k,_,sid,_=db
    lid=database.simpan_lampiran(k,sid,'sintetis.png')
    ids=list(daftar_pilihan(k,sid))
    nilai=daftar_pilihan(k,sid)[ids[0]].opsi[0].nilai
    with pytest.raises(ValueError):attachments.terapkan(k,lid,{f'jwb_{ids[0]}':nilai,f'jwb_{ids[1]}':'A dan B'})
    assert k.execute('SELECT COUNT(*) FROM jawaban').fetchone()[0]==0
    selesai(k,sid)
    awal=[tuple(b) for b in k.execute('SELECT * FROM jawaban')]
    with pytest.raises(ValueError,match='sumber koreksi'):
        attachments.terapkan(k,lid,{f'jwb_{ids[0]}':nilai})
    assert [tuple(b) for b in k.execute('SELECT * FROM jawaban')]==awal


def test_koreksi_transkripsi_dan_setelah_bantuan_tetap_dipisah(db):
    k,_,sid,_=db;selesai(k,sid)
    import review_store
    from learning_cycle_service import konfirmasi_dari_form
    ssid=next(iter(daftar_pilihan(k,sid)))
    salah=next(o.nilai for o in daftar_pilihan(k,sid)[ssid].opsi if o.nilai!=database.isi_sesi(k,sid)[0]['kunci'])
    with pytest.raises(ValueError):
        konfirmasi_dari_form(k,sid,'guru',{f'jwb_{ssid}':salah,f'kode_{ssid}':'H'})
    assert database.isi_sesi(k,sid)[0]['benar']==1
    kid=konfirmasi_dari_form(k,sid,'guru',{f'jwb_{ssid}':salah,f'kode_{ssid}':'H',f'provenance_{ssid}':'koreksi_transkripsi',f'catatan_tinjauan_{ssid}':'Cocokkan dengan kertas sintetis',f'versi_tinjauan_{ssid}':review_store.tanda(k,ssid)})
    assert kid
    validasi_arsip(k,sid,kid)
    with pytest.raises(ValueError):
        konfirmasi_dari_form(k,sid,'guru',{f'provenance_{ssid}':'setelah_bantuan',f'catatan_tinjauan_{ssid}':'Dibantu menghitung',f'versi_tinjauan_{ssid}':review_store.tanda(k,ssid)})


def test_migrasi_db_pra_pg_idempoten_dan_histori_tidak_diubah(tmp_path):
    import schema
    import choice_schema
    p=tmp_path/'warisan.db'
    # Reproduksi schema pra-PG tanpa mengubah source runtime.
    sql=schema.SKEMA.replace(choice_schema.SKEMA_PILIHAN,'')
    sql=sql.replace("    format_jawaban TEXT NOT NULL DEFAULT 'isian' CHECK(format_jawaban IN ('isian','pilihan_ganda')),\n",'')
    with database.buka(p) as k:
        database._jalankan_skema(k,sql)
        siswa=database.tambah_siswa(k,'Warisan',pemilik='guru')
        k.execute('INSERT INTO sesi(siswa_id,seed) VALUES (?,1)',(siswa,))
    database.siapkan(p);database.siapkan(p)
    with database.buka(p) as k:
        assert format_sesi(k,1)=='isian'
        assert k.execute('SELECT COUNT(*) FROM pilihan_butir').fetchone()[0]==0
        assert k.execute('SELECT COUNT(*) FROM konfirmasi_hasil').fetchone()[0]==0
        assert k.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert k.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


@pytest.fixture
def server(tmp_path,monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    with s.buka() as k:
        siswa=database.tambah_siswa(k,'feby',pemilik='guru')
        lain=database.tambah_siswa(k,'Lain',pemilik='orangtua-lain')
        sid=database.buat_sesi(k,siswa,4,format_jawaban='pilihan_ganda',jumlah_soal=2)
        asing=database.buat_sesi(k,lain,5,format_jawaban='pilihan_ganda',jumlah_soal=2)
    yield s,siswa,sid,asing
    s.berhenti()


def test_http_asing_404_identik_tanpa_perubahan(server):
    s,siswa,sid,asing=server
    with s.buka() as k:awal=k.total_changes;before=[tuple(b) for b in k.execute('SELECT * FROM jawaban')]
    for akun in [('guru',SANDI_GURU),('feby',SANDI_MURID)]:
        prefix='/sesi/' if akun[0]=='guru' else '/murid/kerjakan/'
        a=s.minta(prefix+str(asing),auth=akun)
        b=s.minta(prefix+'99999',auth=akun)
        assert a[0]==b[0]==404 and a[1]==b[1]
    with s.buka() as k:assert [tuple(b) for b in k.execute('SELECT * FROM jawaban')]==before


def test_http_kosong_dan_token_dicabut(server):
    s,siswa,sid,_=server
    import share_links
    with s.buka() as k:token=share_links.buat(k,sid)
    kode,_,_=s.minta('/mulai/'+token,data={'aksi':'selesai','revisi_pekerjaan':'0'})
    assert kode==200
    with s.buka() as k:
        assert k.execute('SELECT COUNT(*) FROM pengiriman_butir').fetchone()[0]==2
        assert k.execute('SELECT COUNT(*) FROM pengiriman_pilihan').fetchone()[0]==2
        assert k.execute('SELECT COUNT(*) FROM diagnosis').fetchone()[0]==0
        share_links.cabut(k,sid)
    assert s.minta('/mulai/'+token,data={'aksi':'selesai','revisi_pekerjaan':'0'})[0]==404
