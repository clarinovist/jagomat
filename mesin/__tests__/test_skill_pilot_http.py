"""Pilot melalui HTTP nyata, tanpa akses data keluarga."""
import html
import re
import pytest
import auth
import database
from http_test_kit import ServerUji, SANDI_GURU
from skill_pilot import LANGSUNG, BALIK
from skill_pilot_service import revisi


@pytest.fixture
def server(tmp_path,monkeypatch):
    s=ServerUji(tmp_path,monkeypatch)
    auth.tambah_akun('lain','sandi-sintetis-lain-456','guru',path=auth.BERKAS_SANDI)
    with s.buka() as kon:
        siswa=database.tambah_siswa(kon,'Anak Uji','P3',pemilik='guru')
    yield s,siswa
    s.berhenti()


def test_http_pilih_buat_cetak_tinjau_konfirmasi(server):
    s,siswa=server
    kode,body,_=s.minta('/anak/%d?section=rencana'%siswa,auth=('guru',SANDI_GURU))
    assert kode==200
    teks=body.decode() if isinstance(body,bytes) else body
    assert 'Pilot keliling dan luas' in teks
    with s.buka() as kon:
        data={'aksi':'mulai','revisi':revisi(kon,siswa),'tuntutan':LANGSUNG,'profil':'P3','representasi':'teks-v1'}
    kode,body,_=s.minta('/siklus/%d/pilot'%siswa,auth=('guru',SANDI_GURU),data=data)
    assert kode==200
    with s.buka() as kon:
        sid=kon.execute('SELECT max(id) FROM sesi').fetchone()[0]
        assert kon.execute('SELECT count(*) FROM pilot_sesi').fetchone()[0]==1
        butir=database.isi_sesi(kon,sid)
        for b in butir:
            jid=database.simpan_jawaban(kon,b['sesi_soal_id'],b['kunci'])
            database.simpan_diagnosis(kon,jid,True,None,None)
        database.tandai_selesai(kon,sid)
        data={f'cek_pemahaman_{b["sesi_soal_id"]}':'bisa_menjelaskan' for b in butir}
    kode,_,_=s.minta('/sesi/%d/konfirmasi'%sid,auth=('guru',SANDI_GURU),data=data)
    assert kode==200
    with s.buka() as kon:
        assert kon.execute('SELECT count(*) FROM pilot_konfirmasi').fetchone()[0]==1
    kode,body,_=s.minta('/anak/%d?section=rencana'%siswa,auth=('guru',SANDI_GURU))
    assert kode==200
    teks=body.decode() if isinstance(body,bytes) else body
    assert 'Bukti per tuntutan pilot' in teks and 'Masih dipelajari' in teks
    assert teks.count('class="rencana-cta-utama-st"')<=1
    kode,body,_=s.minta('/anak/%d?section=latihan'%siswa,auth=('guru',SANDI_GURU))
    assert kode==200
    assert 'profil_parameter' in (body.decode() if isinstance(body,bytes) else body)


def test_pilot_tautan_anak_kirim_dan_cetak(server):
    from skill_pilot_service import jalankan
    import share_links
    s,siswa=server
    with s.buka() as kon:
        url=jalankan(kon,siswa,{'aksi':'mulai','revisi':revisi(kon,siswa),'tuntutan':LANGSUNG,'profil':'P3','representasi':'geometri_datar-v1'})
        sid=int(url.split('/')[-1]); token=share_links.buat(kon,sid)
    status,body,_=s.minta('/mulai/'+token)
    assert status==200 and 'geometri_datar' not in body
    for rahasia in (LANGSUNG,'datar.lupa_kali_dua','Bukti per tuntutan','Konfirmasi hasil'):
        assert rahasia not in body
    status,body,_=s.minta('/mulai/'+token,data={'aksi':'kirim_latihan','revisi_pekerjaan':'0'})
    assert status==200
    with s.buka() as kon:
        assert kon.execute('SELECT count(*) FROM pengiriman_butir WHERE sesi_id=?',(sid,)).fetchone()[0]==4
        assert kon.execute('SELECT count(*) FROM pilot_konfirmasi').fetchone()[0]==0
        from teacher_pages import halaman_lembar
        cetak=halaman_lembar(kon,sid)
        assert cetak and LANGSUNG not in cetak.decode()


@pytest.mark.parametrize('pengguna', ('guru','pengelola'))
def test_pemulihan_http_owner_checkbox_dan_status_terpisah(server,pengguna):
    from test_skill_pilot_recovery import siapkan_masalah
    s,siswa=server
    auth.tambah_akun('pengelola',SANDI_GURU,'admin',path=auth.BERKAS_SANDI)
    with s.buka() as kon:
        pid,sesi,sehat=siapkan_masalah(kon,siswa)
        data={'aksi':'pulihkan_sumber','revisi':revisi(kon,siswa),'konfirmasi_pemulihan':'1'}
        sebelum=tuple(kon.iterdump())
    hasil=[]
    for identitas in (siswa,999999):
        kode,body,_=s.minta('/siklus/%d/pilot'%identitas,
            auth=('lain','sandi-sintetis-lain-456'),data=data)
        assert kode==404
        hasil.append(body)
    assert hasil[0]==hasil[1]
    for konfirmasi in ('','0'):
        kode,_,_=s.minta('/siklus/%d/pilot'%siswa,auth=(pengguna,SANDI_GURU),
                         data={**data,'konfirmasi_pemulihan':konfirmasi})
        assert kode==400
    with s.buka() as kon: assert tuple(kon.iterdump())==sebelum
    kode,body,_=s.minta('/anak/%d?section=rencana'%siswa,auth=('guru',SANDI_GURU))
    assert kode==200 and 'Tinjau ulang sumber fokus pilot' in body
    assert 'Menunjukkan pemahaman' in body and 'Perlu cek kembali' in body
    assert body.count('class="rencana-cta-utama-st"')==1
    assert 'name="konfirmasi_pemulihan"' in body and 'return confirm(' in body
    for sid in sesi[:1]: assert 'href="/sesi/%d"'%sid in body
    # GET tidak mengubah revisi pemulihan.
    with s.buka() as kon: assert tuple(kon.iterdump())==sebelum
    kode,body,_=s.minta('/siklus/%d/pilot'%siswa,auth=(pengguna,SANDI_GURU),data=data)
    assert kode==200 and 'Pilot keliling dan luas' in body
    assert 'name="aksi" value="pulihkan_sumber"' not in body
    with s.buka() as kon:
        assert all(kon.execute('SELECT dibatalkan FROM sesi WHERE id=?',(sid,)).fetchone()[0] for sid in sesi)
        assert all(kon.execute('SELECT dibatalkan FROM sesi WHERE id=?',(sid,)).fetchone()[0] is None for sid in sehat)


def test_pemulihan_http_murid_dan_pilot_sehat_ditolak(server):
    from http_test_kit import SANDI_MURID
    from skill_pilot_service import jalankan
    s,siswa=server
    with s.buka() as kon:
        jalankan(kon,siswa,{'aksi':'mulai','revisi':revisi(kon,siswa),'tuntutan':LANGSUNG,'profil':'P3','representasi':'teks-v1'})
        data={'aksi':'pulihkan_sumber','revisi':revisi(kon,siswa),'konfirmasi_pemulihan':'1'}
        sebelum=tuple(kon.iterdump())
    kode,_,_=s.minta('/siklus/%d/pilot'%siswa,auth=('feby',SANDI_MURID),data=data)
    assert kode==401  # Permukaan guru tidak menerima Basic akun murid.
    kode,_,_=s.minta('/siklus/%d/pilot'%siswa,auth=('guru',SANDI_GURU),data=data)
    assert kode==400
    with s.buka() as kon: assert tuple(kon.iterdump())==sebelum


def test_owner_404_identik_dan_tanpa_efek(server):
    s,siswa=server
    with s.buka() as kon:
        sebelum=tuple(kon.iterdump())
    hasil=[]
    for identitas in (siswa,999999):
        kode,body,_=s.minta('/siklus/%d/pilot'%identitas,auth=('lain','sandi-sintetis-lain-456'),data={'aksi':'mulai'})
        assert kode==404
        hasil.append(body)
    assert hasil[0]==hasil[1]
    with s.buka() as kon: assert tuple(kon.iterdump())==sebelum


def test_tujuan_p3_balik_ditolak_tanpa_sesi(server):
    s,siswa=server
    with s.buka() as kon:
        data={'aksi':'mulai','revisi':revisi(kon,siswa),'tuntutan':BALIK,'profil':'P3','representasi':'teks-v1'}
        sebelum=tuple(kon.iterdump())
    kode,_,_=s.minta('/siklus/%d/pilot'%siswa,auth=('guru',SANDI_GURU),data=data)
    assert kode==400
    with s.buka() as kon: assert tuple(kon.iterdump())==sebelum
