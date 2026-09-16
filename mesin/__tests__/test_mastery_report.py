"""Peta penguasaan end-to-end snapshot, grafik, dan batas permukaan guru."""
from datetime import date, timedelta
from dataclasses import replace
from pathlib import Path
import sys
import html

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

import database
import reports
import mastery_report as mr
import mastery_catalog as katalog
import learning_cycle as lc
from mastery_evidence import lengkapi_bukti_materi
from test_mastery_targets import HARI, _baik, _bukti, TARGET


@pytest.fixture
def db(tmp_path,monkeypatch):
    import auth
    monkeypatch.setattr(auth,"BERKAS_SANDI",tmp_path/"sandi.json")
    path=tmp_path/"uji.db"
    database.siapkan(path)
    return path


def _buat_bukti(kon,sid,pid,seed,hari,tipe="rata_rata",jumlah=4):
    sesi=database.buat_sesi_dari_urutan(kon,sid,seed,(tipe,)*jumlah,level="P5",topik="statistika")
    database.tautkan_sesi_putaran(kon,pid,[sesi])
    kon.execute("UPDATE sesi SET tujuan='pemetaan',tanggal=? WHERE id=?",(hari.isoformat(),sesi))
    cek={}
    for b in database.isi_sesi(kon,sesi):
        j=database.simpan_jawaban(kon,b["sesi_soal_id"],b["kunci"],"cara sintetis")
        database.simpan_diagnosis(kon,j,True,None,None)
        cek[b["sesi_soal_id"]]="bisa_menjelaskan"
    database.tandai_selesai(kon,sesi)
    database.konfirmasi_hasil(kon,sesi,"guru",cek_pemahaman=cek)
    return sesi


def test_peta_memuat_semua_materi_dan_progres_bukan_rasio():
    peta=mr.peta_penguasaan(_bukti(_baik()),1,HARI)
    assert len(peta.target)==len(katalog.katalog_target("P5"))
    assert peta.jumlah["terbukti"]==1
    assert peta.persen==pytest.approx(100/len(peta.target))
    h=mr.render_peta(peta,reports._tanggal_pendek)
    kedua=mr.render_peta(peta,reports._tanggal_pendek,halaman='2')
    for nama in {t.topik for t in peta.target}:assert html.escape(nama) in h + kedua
    ringkas=mr.render_peta(peta,reports._tanggal_pendek,ringkas=True)
    assert 'role="img"' in ringkas and 'class="peta-grafik"' in ringkas
    assert f'1 dari {len(peta.target)} target' in h
    assert "1/10 materi" in ringkas
    assert "Belum dinilai" in h


def test_grafik_semua_kategori_jumlah_target_dan_presisi():
    peta=mr.peta_penguasaan(_bukti(_baik()),1,HARI)
    status=list(peta.status)
    for i,kode in enumerate(["terbukti","dipelajari","perlu_cek"]):
        status[i]=replace(status[i],status=kode)
    peta=replace(peta,status=tuple(status))
    h=mr._grafik(peta.jumlah,len(peta.target))
    import re
    lebar=[float(n) for n in re.findall(' width="([0-9.]+)"',h)]
    assert sum(lebar)==pytest.approx(600,abs=.01)
    for kode,nama,_ in mr.STATUS:assert f'{nama}: {peta.jumlah[kode]}' in h


def test_peta_snapshot_sah_dan_koreksi_mengubah_status_tanpa_write(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Snapshot","P5",pemilik="guru")
        pid=database.buat_putaran_fokus(kon,sid,"P5")
        a=_buat_bukti(kon,sid,pid,11,HARI-timedelta(days=7))
        b=_buat_bukti(kon,sid,pid,12,HARI-timedelta(days=3))
        sebelum=tuple(kon.iterdump())
        data=mr.peta_penguasaan(lengkapi_bukti_materi(kon,database.muat_bukti_siklus(kon,sid)),sid,HARI)
        assert tuple(kon.iterdump())==sebelum
        assert data.jumlah["terbukti"]==1
        butir=database.isi_sesi(kon,b)[0]
        database.simpan_diagnosis(kon,butir["jawaban_id"],False,"K","K")
        data=mr.peta_penguasaan(lengkapi_bukti_materi(kon,database.muat_bukti_siklus(kon,sid)),sid,HARI)
        assert data.jumlah["terbukti"]==0 and data.jumlah["perlu_cek"]==1
        assert kon.execute("SELECT COUNT(*) FROM konfirmasi_hasil").fetchone()[0]==2


def test_skor_topik_tidak_memakai_jenis_soal_yang_sudah_dikerjakan_saja():
    peta=mr.peta_penguasaan(_bukti(_baik()),1,HARI)
    h=mr.render_peta(peta,reports._tanggal_pendek,materi='statistika')
    bagian=h.split('<b>Statistika</b>',1)[1].split('</a>',1)[0]
    assert "1/5 target" in bagian and "20%" in bagian
    assert "100%" not in bagian


def test_peta_kosong_dan_kelas_asing_tidak_pura_pura_nol_kemampuan():
    peta=mr.peta_penguasaan(_bukti(()),1,HARI)
    assert peta.persen is None
    h=mr.render_peta(peta,reports._tanggal_pendek)
    ringkas=mr.render_peta(peta,reports._tanggal_pendek,ringkas=True)
    assert 'peta-persentase">— · Belum dinilai' in ringkas
    assert 'peta-persentase">0%' not in ringkas
    assert "Belum dinilai bukan berarti tidak mampu" in h
    asing=mr.peta_penguasaan(replace(_bukti(()),level_aktif="asing"),1,HARI)
    assert "belum tersedia" in mr.render_peta(asing,reports._tanggal_pendek)


def test_mutable_bernilai_bagus_tidak_naikkan_penguasaan(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Sementara","P5",pemilik="guru")
        pid=database.buat_putaran_fokus(kon,sid,"P5")
        for i in (1,2):
            s=_buat_bukti(kon,sid,pid,33+i,HARI-timedelta(days=9-i*3))
            j=database.isi_sesi(kon,s)[0]["jawaban_id"]
            database.simpan_diagnosis(kon,j,True,None,None)
        peta=mr.peta_penguasaan(lengkapi_bukti_materi(kon,database.muat_bukti_siklus(kon,sid)),sid,HARI)
    assert peta.jumlah["terbukti"]==0


def test_adapter_menolak_bukti_siswa_asing(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Satu","P5")
        asing=database.tambah_siswa(kon,"Dua","P5")
        pid=database.buat_putaran_fokus(kon,sid,"P5")
        _buat_bukti(kon,sid,pid,321,HARI)
        bukti=database.muat_bukti_siklus(kon,sid)
        campur=replace(bukti,siswa_id=asing)
        awal=tuple(kon.iterdump())
        with pytest.raises(ValueError):lengkapi_bukti_materi(kon,campur)
        assert tuple(kon.iterdump())==awal


def test_adapter_versi_bukti_usang_tidak_dipasangkan_snapshot_baru(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Versi","P5")
        pid=database.buat_putaran_fokus(kon,sid,"P5")
        sesi=_buat_bukti(kon,sid,pid,322,HARI)
        bukti=database.muat_bukti_siklus(kon,sid)
        j=database.isi_sesi(kon,sesi)[0]["jawaban_id"]
        database.simpan_diagnosis(kon,j,False,"H","H")
        database.konfirmasi_hasil(kon,sesi,"guru")
        with pytest.raises(ValueError):lengkapi_bukti_materi(kon,bukti)


def test_adapter_mempertahankan_mode_drill_agar_bukan_bukti_penguasaan(db):
    with database.buka(db) as kon:
        sid=database.tambah_siswa(kon,"Drill","P5")
        pid=database.buat_putaran_fokus(kon,sid,"P5")
        for seed,hari in [(323,HARI-timedelta(days=7)),(324,HARI-timedelta(days=3))]:
            sesi=_buat_bukti(kon,sid,pid,seed,hari)
            kon.execute("UPDATE sesi SET mode='drill' WHERE id=?",(sesi,))
        asli=database.muat_bukti_siklus(kon,sid)
        bukti=lengkapi_bukti_materi(kon,asli)
    assert all(s.mode=="drill" for s in bukti.sesi)
    assert mr.peta_penguasaan(bukti,sid,HARI).jumlah["terbukti"]==0
    assert all(o.fingerprint_matematis is None for s in asli.sesi for o in s.outcomes)


def test_get_laporan_peta_menjaga_ownership_murid_dan_tidak_menulis(tmp_path,monkeypatch):
    from http_test_kit import ServerUji,SANDI_GURU,SANDI_MURID
    server=ServerUji(tmp_path,monkeypatch)
    try:
        with server.buka() as kon:
            sid=database.tambah_siswa(kon,"Anak Uji","P5",pemilik="guru")
            asing=database.tambah_siswa(kon,"Rahasia Keluarga Lain","P5",pemilik="lain")
            sebelum=tuple(kon.iterdump())
        kode,h,_=server.minta(f"/laporan/{sid}",auth=("guru",SANDI_GURU))
        assert kode==200 and 'id="peta-penguasaan"' in h
        assert "Rahasia Keluarga Lain" not in h
        ka,ha,_=server.minta(f"/laporan/{asing}",auth=("guru",SANDI_GURU))
        kh,hh,_=server.minta("/laporan/999999",auth=("guru",SANDI_GURU))
        assert ka==kh==404 and ha==hh
        km,hm,_=server.minta(f"/laporan/{sid}",auth=("feby",SANDI_MURID))
        assert km in (401,403) and 'id="peta-penguasaan"' not in hm
        with server.buka() as kon:assert tuple(kon.iterdump())==sebelum
    finally:server.berhenti()
