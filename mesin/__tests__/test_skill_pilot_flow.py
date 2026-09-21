"""Alur pilot melalui transaksi asli, data sintetis dan konfirmasi eksplisit."""
from datetime import date
import json
import pytest
import database
import learning_cycle as lc
from skill_pilot import LANGSUNG, PRASYARAT, BALIK
from skill_pilot_service import jalankan, revisi, keadaan
from skill_pilot_store import muat_bukti, baca_kontrak


@pytest.fixture
def db(tmp_path):
    path=tmp_path/'pilot.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        siswa=database.tambah_siswa(kon,'Sintetis','P3',pemilik='guru')
        yield kon,siswa


def mulai(kon,siswa,tuntutan=LANGSUNG,profil='P3',hari=date(2026,9,1),**opsi):
    data={'aksi':'mulai','revisi':revisi(kon,siswa),'tuntutan':tuntutan,'profil':profil,'representasi':'teks-v1',**opsi}
    url=jalankan(kon,siswa,data,hari=hari)
    return int(url.split('/')[-1]),data


def sahkan(kon,sesi,tanggal='2026-09-01',salah=False):
    kon.execute('UPDATE sesi SET tanggal=? WHERE id=?',(tanggal,sesi))
    for b in database.isi_sesi(kon,sesi):
        jid=database.simpan_jawaban(kon,b['sesi_soal_id'],'0' if salah else b['kunci'])
        database.simpan_diagnosis(kon,jid,not salah,'K' if salah else None,'K' if salah else None,
                                  'datar.lupa_kali_dua' if salah else None)
    database.tandai_selesai(kon,sesi)
    kh=database.konfirmasi_hasil(kon,sesi,'guru',cek_pemahaman={b['sesi_soal_id']:'bisa_menjelaskan' for b in database.isi_sesi(kon,sesi)})
    kon.execute('UPDATE sesi SET selesai=?,dikonfirmasi_guru=? WHERE id=?',(tanggal,tanggal,sesi))
    return kh


def test_dua_pemeriksaan_dan_konfirmasi_terikat_tanpa_bukti_v1(db):
    kon,siswa=db
    sid,data=mulai(kon,siswa)
    assert jalankan(kon,siswa,data,hari=date(2026,9,1))=='/sesi/%d'%sid
    kontrak=baca_kontrak(kon,sid,siswa)
    assert kontrak.seed is not None and kontrak.tujuan=='pemetaan'
    kh=sahkan(kon,sid)
    assert database.konfirmasi_hasil(kon,sid,'guru',cek_pemahaman={b['sesi_soal_id']:'bisa_menjelaskan' for b in database.isi_sesi(kon,sid)})==kh
    b,r,aktif,w=keadaan(kon,siswa,date(2026,9,1))
    assert aktif[2].tindakan=='tunggu_pemetaan'
    assert lc.rencana_berikutnya(b.bukti,siswa,date(2026,9,1)).tindakan=='pemetaan'
    url=jalankan(kon,siswa,{'aksi':'lanjut','revisi':revisi(kon,siswa)},hari=date(2026,9,4))
    sid2=int(url.split('/')[-1]); sahkan(kon,sid2,'2026-09-04')
    paket,_,aktif,_=keadaan(kon,siswa,date(2026,9,4))
    assert aktif[2].tindakan=='tunggu_checkpoint'
    assert lc.penguasaan_pilot(paket,siswa,(kontrak.butir[0].konteks,),date(2026,9,4))[0].hasil.status=='terbukti'
    with pytest.raises(ValueError): jalankan(kon,siswa,{**data,'revisi':revisi(kon,siswa),'tuntutan':BALIK,'profil':'P4'},hari=date(2026,9,4))


def lanjut(kon,siswa,hari):
    return int(jalankan(kon,siswa,{'aksi':'lanjut','revisi':revisi(kon,siswa)},hari=date.fromisoformat(hari)).split('/')[-1])


def test_balik_setelah_prasyarat_hingga_checkpoint(db):
    kon,siswa=db
    awal,_=mulai(kon,siswa); sahkan(kon,awal)
    sahkan(kon,lanjut(kon,siswa,'2026-09-04'),'2026-09-04')
    kisi,_=mulai(kon,siswa,PRASYARAT,hari=date(2026,9,4)); sahkan(kon,kisi)
    sahkan(kon,lanjut(kon,siswa,'2026-09-04'),'2026-09-04')
    data={'aksi':'mulai','revisi':revisi(kon,siswa),'tuntutan':BALIK,'profil':'P4','representasi':'teks-v1'}
    sid=int(jalankan(kon,siswa,data,hari=date(2026,9,5)).split('/')[-1])
    k=baca_kontrak(kon,sid,siswa)
    assert len(k.sumber_konfirmasi)==4
    sahkan(kon,sid,'2026-09-05')
    sahkan(kon,lanjut(kon,siswa,'2026-09-08'),'2026-09-08')
    b,rs,_,_=keadaan(kon,siswa,date(2026,9,8))
    assert {h.hasil.status for h in lc.penguasaan_pilot(b,siswa,tuple(r[1] for r in rs),date(2026,9,8))}=={'terbukti'}
    _,_,aktif,_=keadaan(kon,siswa,date(2026,10,2))
    assert aktif[2].tindakan=='checkpoint'
    satu=lanjut(kon,siswa,'2026-10-02'); sahkan(kon,satu,'2026-10-02')
    dua=lanjut(kon,siswa,'2026-10-02'); sahkan(kon,dua,'2026-10-02')
    assert kon.execute('SELECT bagian_checkpoint FROM sesi WHERE id=?',(dua,)).fetchone()[0]==2


def test_evaluasi_gagal_alternatif_dan_eskalasi(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa); sahkan(kon,sid,salah=True)
    sahkan(kon,lanjut(kon,siswa,'2026-09-04'),'2026-09-04',True)
    for hari in ('2026-09-04','2026-09-08'):
        jalankan(kon,siswa,{'aksi':'pelajari','revisi':revisi(kon,siswa)},hari=date.fromisoformat(hari))
        sahkan(kon,lanjut(kon,siswa,hari),hari)
        sahkan(kon,lanjut(kon,siswa,hari),hari)
        from datetime import timedelta
        evaluasi=(date.fromisoformat(hari)+timedelta(days=3)).isoformat()
        sid=lanjut(kon,siswa,evaluasi)
        assert baca_kontrak(kon,sid,siswa).tujuan=='evaluasi'
        sahkan(kon,sid,evaluasi,True)
    _,_,aktif,_=keadaan(kon,siswa,date(2026,9,12))
    assert aktif[2].tindakan=='eskalasi'
    pendekatan=[json.loads(r[0])['pendekatan_id'] for r in kon.execute("SELECT data FROM kejadian_belajar WHERE jenis='intervensi_selesai'")]
    assert len(set(pendekatan))==2


@pytest.mark.parametrize('mode',('teks-v1','geometri_datar-v1'))
def test_mode_pilot_tidak_mengikuti_env(db,monkeypatch,mode):
    kon,siswa=db
    monkeypatch.setenv('OSN_VISUAL_KELUARGA','geometri-datar')
    data={'aksi':'mulai','revisi':revisi(kon,siswa),'tuntutan':LANGSUNG,'profil':'P3','representasi':mode}
    sid=int(jalankan(kon,siswa,data).split('/')[-1])
    assert {b['mode_representasi'] for b in database.isi_sesi(kon,sid)}=={mode}


@pytest.mark.parametrize('kolom,nilai',(('seed',999),('tujuan','penguatan'),('level','P4')))
def test_envelope_rusak_menolak_tanpa_konfirmasi(db,kolom,nilai):
    kon,siswa=db
    sid,_=mulai(kon,siswa)
    kon.execute('UPDATE sesi SET '+kolom+'=? WHERE id=?',(nilai,sid))
    sebelum=tuple(kon.iterdump())
    with pytest.raises(ValueError): baca_kontrak(kon,sid,siswa)
    assert tuple(kon.iterdump())==sebelum


def test_gagal_arsip_menggulung_konfirmasi(db,monkeypatch):
    kon,siswa=db
    sid,_=mulai(kon,siswa)
    for b in database.isi_sesi(kon,sid):
        jid=database.simpan_jawaban(kon,b['sesi_soal_id'],b['kunci'])
        database.simpan_diagnosis(kon,jid,True,None,None)
    database.tandai_selesai(kon,sid)
    sebelum=tuple(kon.iterdump())
    import skill_pilot_store
    def gagal(*args): raise ValueError('gagal sintetis setelah snapshot')
    monkeypatch.setattr(skill_pilot_store,'arsipkan_konfirmasi',gagal)
    with pytest.raises(ValueError,match='gagal sintetis'):
        database.konfirmasi_hasil(kon,sid,'guru')
    assert tuple(kon.iterdump())==sebelum


def test_fokus_sumber_dicabut_tidak_diam_diam_diteruskan(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa); sahkan(kon,sid,salah=True)
    sid2=lanjut(kon,siswa,'2026-09-04'); sahkan(kon,sid2,'2026-09-04',True)
    jalankan(kon,siswa,{'aksi':'pelajari','revisi':revisi(kon,siswa)},hari=date(2026,9,4))
    # Cabut tanda aktif tanpa mengubah snapshot; guard harus memeriksa sumber
    # aktif sebelum outcome yang kini kosong ditafsir ulang.
    kon.execute('UPDATE sesi SET dikonfirmasi_guru=NULL,fingerprint_konfirmasi=NULL WHERE id=?',(sid,))
    paket,_,aktif,_=keadaan(kon,siswa,date(2026,9,5))
    assert aktif[2].tindakan=='pulihkan_sumber'
    assert lc.penguasaan_pilot(paket,siswa,(aktif[1],),date(2026,9,5))[0].hasil.status=='perlu_cek'


def test_fokus_sesi_sumber_dibatalkan_tidak_menjadi_bukti(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa); sahkan(kon,sid,salah=True)
    sahkan(kon,lanjut(kon,siswa,'2026-09-04'),'2026-09-04',True)
    jalankan(kon,siswa,{'aksi':'pelajari','revisi':revisi(kon,siswa)},hari=date(2026,9,4))
    database.batalkan_sesi(kon,sid,'dibatalkan sintetis')
    sebelum=tuple(kon.iterdump())
    paket,_,aktif,_=keadaan(kon,siswa,date(2026,9,5))
    assert aktif[2].tindakan=='pulihkan_sumber'
    assert lc.penguasaan_pilot(paket,siswa,(aktif[1],),date(2026,9,5))[0].hasil.status=='perlu_cek'
    assert tuple(kon.iterdump())==sebelum


def test_konfirmasi_mengikat_kontrak_bukan_hanya_row_arsip(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa); kh=sahkan(kon,sid)
    kon.execute('DROP TRIGGER konfirmasi_hasil_tolak_update')
    kon.execute("UPDATE konfirmasi_hasil SET fingerprint=? WHERE id=?",('f'*64,kh))
    from skill_pilot_store import validasi_konfirmasi
    with pytest.raises(ValueError,match='fingerprint konfirmasi'):
        validasi_konfirmasi(kon,sid,siswa,kh)


def test_batal_lalu_retry_baru_tidak_memakai_receipt_lama(db):
    kon,siswa=db
    sid,data=mulai(kon,siswa)
    database.batalkan_sesi(kon,sid,'uji sintetis')
    with pytest.raises(ValueError,match='dibatalkan'):
        jalankan(kon,siswa,data)
    sid2=lanjut(kon,siswa,'2026-09-02')
    assert sid2!=sid


def test_tidak_membuka_fokus_baru_saat_putaran_lama_belum_pulih(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa); sahkan(kon,sid)
    sebelum=tuple(kon.iterdump())
    with pytest.raises(ValueError,match='berjalan'):
        mulai(kon,siswa,PRASYARAT,hari=date(2026,9,2))
    assert tuple(kon.iterdump())==sebelum


def test_pilot_sesi_hilang_tidak_jadi_v1(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa)
    kon.execute('DROP TRIGGER pilot_sesi_tolak_delete')
    kon.execute('DELETE FROM pilot_sesi WHERE sesi_id=?',(sid,))
    with pytest.raises(ValueError,match='hilang'):
        baca_kontrak(kon,sid,siswa)


def test_fokus_berhasil_checkpoint_dan_kambuh(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa); sahkan(kon,sid,salah=True)
    sahkan(kon,lanjut(kon,siswa,'2026-09-04'),'2026-09-04',True)
    jalankan(kon,siswa,{'aksi':'pelajari','revisi':revisi(kon,siswa)},hari=date(2026,9,4))
    for tahap in range(2): sahkan(kon,lanjut(kon,siswa,'2026-09-04'),'2026-09-04')
    sahkan(kon,lanjut(kon,siswa,'2026-09-07'),'2026-09-07')
    _,_,a,_=keadaan(kon,siswa,date(2026,9,7))
    assert a[2].tindakan=='tunggu_checkpoint'
    for bagian in range(2): sahkan(kon,lanjut(kon,siswa,'2026-10-05'),'2026-10-05')
    _,_,a,_=keadaan(kon,siswa,date(2026,10,5))
    assert a[2].putaran.fokus[0].status=='bertahan'
    # Pemeriksaan berikutnya yang salah adalah bukti baru, bukan penghapusan histori.
    sid=lanjut(kon,siswa,'2026-11-02'); sahkan(kon,sid,'2026-11-02',True)
    _,_,a,_=keadaan(kon,siswa,date(2026,11,2))
    assert a[2].tindakan=='putaran_baru'
    jalankan(kon,siswa,{'aksi':'putaran_baru','revisi':revisi(kon,siswa)},hari=date(2026,11,2))
    _,_,a,_=keadaan(kon,siswa,date(2026,11,2))
    assert a[2].tindakan=='intervensi'


def test_checkpoint_tidak_menghidupkan_bukti_lama_setelah_gagal(db):
    kon,siswa=db
    awal,_=mulai(kon,siswa); sahkan(kon,awal)
    sahkan(kon,lanjut(kon,siswa,'2026-09-04'),'2026-09-04')
    satu=lanjut(kon,siswa,'2026-10-02'); sahkan(kon,satu,'2026-10-02',True)
    dua=lanjut(kon,siswa,'2026-10-02'); sahkan(kon,dua,'2026-10-02',True)
    _,_,a,_=keadaan(kon,siswa,date(2026,10,2))
    assert a[2].tindakan=='eskalasi'


def test_backup_pilot_baca_saja_dan_menolak_arsip_rusak(db,tmp_path):
    import sqlite3
    from admin_backup import _validasi_pilot, BackupTidakSah
    kon,siswa=db
    sid,_=mulai(kon,siswa); sahkan(kon,sid)
    kon.commit()
    path=tmp_path/'backup.db'
    with sqlite3.connect(path) as target: kon.backup(target)
    sebelum=path.read_bytes()
    _validasi_pilot(path)
    assert path.read_bytes()==sebelum
    with sqlite3.connect(path) as salinan:
        salinan.execute('DROP TRIGGER pilot_konfirmasi_tolak_update')
        salinan.execute("UPDATE pilot_konfirmasi SET fingerprint=?",('f'*64,))
    with pytest.raises(BackupTidakSah): _validasi_pilot(path)


def test_stale_dan_payload_tidak_membuat_sesi(db):
    kon,siswa=db
    sid,data=mulai(kon,siswa)
    sebelum=tuple(kon.iterdump())
    with pytest.raises(ValueError,match='Rencana berubah'):
        jalankan(kon,siswa,{'aksi':'lanjut','revisi':data['revisi']})
    with pytest.raises(ValueError): jalankan(kon,siswa,{**data,'kuota':'1'})
    assert tuple(kon.iterdump())==sebelum


def test_pengenalan_tidak_sertifikasi(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa,belum_dikenal='1')
    assert baca_kontrak(kon,sid,siswa).tujuan=='pengenalan'
    sahkan(kon,sid)
    b,_,a,_=keadaan(kon,siswa,date(2026,9,1))
    assert a[2].tindakan=='tunggu_pemetaan'
    assert lc.penguasaan_pilot(b,siswa,(a[1],),date(2026,9,1))[0].hasil.status=='belum_dinilai'
    url=jalankan(kon,siswa,{'aksi':'lanjut','revisi':revisi(kon,siswa)},hari=date(2026,9,2))
    assert baca_kontrak(kon,int(url.split('/')[-1]),siswa).tujuan=='pemetaan'


def test_kegagalan_berulang_ke_intervensi_konteks_sumber(db):
    kon,siswa=db
    sid,_=mulai(kon,siswa); sahkan(kon,sid,salah=True)
    sid2=int(jalankan(kon,siswa,{'aksi':'lanjut','revisi':revisi(kon,siswa)},hari=date(2026,9,4)).split('/')[-1])
    sahkan(kon,sid2,'2026-09-04',True)
    _,_,a,_=keadaan(kon,siswa,date(2026,9,4))
    assert a[2].tindakan=='intervensi'
    jalankan(kon,siswa,{'aksi':'pelajari','revisi':revisi(kon,siswa)},hari=date(2026,9,4))
    _,_,a,_=keadaan(kon,siswa,date(2026,9,4))
    assert a[2].tindakan=='latihan_terbimbing'
