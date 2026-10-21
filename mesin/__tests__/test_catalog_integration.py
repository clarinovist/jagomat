"""Kontrak lintas registry, visual, PG, bank dan reader untuk koreksi katalog."""
from dataclasses import replace
import random

import pytest
from catalog_versions import TEMPLATE_DIPERBAIKI
from generator import buat_soal
from topics import ambil, daftar_topik
from question_views import penyajian_dari_soal, soal_dari_baris
from render import _badan_soal
from choice_generation import buat_lembar_pilihan, kandidat

PASANGAN = [(topik,tid,lv) for topik in daftar_topik() if topik!='campuran'
            for lv, tids in ambil(topik).komposisi.items() for tid in sorted(set(tids))
            if tid in TEMPLATE_DIPERBAIKI]
VISUAL='statistika,geometri-datar,geometri-ruang,kombinatorik,pengukuran,pola-bilangan'


@pytest.fixture(autouse=True)
def writer(monkeypatch):
    monkeypatch.setenv('OSN_KATALOG_VERSI','2')


@pytest.mark.parametrize('topik,tid,lv',PASANGAN)
def test_registry_visual_identitas_dan_jalur_k(topik,tid,lv,monkeypatch):
    paket=ambil(topik)
    monkeypatch.setenv('OSN_VISUAL_KELUARGA',VISUAL)
    tanpa_k=[]
    unik=set()
    for seed in range(500):
        soal=buat_soal(tid,seed,lv,topik)
        assert soal.parameter['versi_katalog']==2
        unik.add(soal.tanda_tangan)
        if not any(m.kode=='K' for m in soal.malrule): tanpa_k.append(seed)
        assert len({m.jawaban for m in soal.malrule})==len(soal.malrule)
        assert soal.kunci not in {m.jawaban for m in soal.malrule}
        if seed<25:
            from diagnosis import setara, diagnosa
            aturan=[dict(malrule_id=m.id,jawaban=m.jawaban,kode=m.kode,alasan=m.alasan) for m in soal.malrule]
            for m in soal.malrule:
                usulan=diagnosa(soal.kunci,m.jawaban,'perhitungan sintetis','',False,aturan,soal=soal)
                assert not usulan.benar and usulan.malrule_id==m.id and usulan.kode==m.kode
                if '/' in m.jawaban:
                    from fractions import Fraction
                    angka = Fraction(m.jawaban)
                    ekuivalen = str(angka.numerator*2)+'/'+str(angka.denominator*2)
                    assert setara(ekuivalen,m.jawaban,soal=soal)
                    hasil=diagnosa(soal.kunci,ekuivalen,'perhitungan sintetis','',False,aturan,soal=soal)
                    assert not hasil.benar and hasil.malrule_id==m.id
            assert soal==buat_soal(tid,seed,lv,topik)
            p=paket.parameter_untuk(tid,random.Random(seed),lv)
            assert soal==replace(paket.templates[tid](**p),level=lv)
            penyajian=penyajian_dari_soal(soal)
            assert _badan_soal(replace(soal,penyajian=penyajian),paket)
    assert len(tanpa_k)<=10, (tid,lv,'tanpa K',tanpa_k)
    if tid not in {'fpb_dua_bilangan','jumlah_deret','korek_api'}:
        assert len(unik)>=200, (tid,lv,len(unik))


@pytest.mark.parametrize('topik,lv', sorted({(a,c) for a,b,c in PASANGAN}))
def test_lembar_pg_tetap_dapat_dibuat_tanpa_angka_rekaan(topik,lv,monkeypatch):
    monkeypatch.setenv('OSN_VISUAL_KELUARGA',VISUAL)
    for seed in range(25):
        lembar=buat_lembar_pilihan(seed,level=lv,topik=topik)
        for soal in lembar.soal:
            assert kandidat(soal)
            assert penyajian_dari_soal(soal)


@pytest.fixture()
def db(tmp_path):
    import database
    path=tmp_path/'bank-katalog-sintetis.db'
    database.siapkan(path)
    with database.buka(path) as kon:
        yield kon


@pytest.mark.parametrize('topik,lv', sorted({(a,c) for a,b,c in PASANGAN}))
def test_bank_snapshot_diagnosis_konteks_dan_outcome_tidak_ditulis_ulang(db,monkeypatch,topik,lv):
    import database
    import teacher_print_pages
    import teacher_review_service
    from templates import REGISTRI
    monkeypatch.setenv('OSN_VISUAL_KELUARGA',VISUAL)
    siswa=database.tambah_siswa(db,'Fixture Katalog Lengkap',lv,pemilik='guru')
    soal=[]
    for _,tid,level in PASANGAN:
        if level!=lv or tid not in ambil(topik).templates:
            continue
        cabang=set()
        for seed in range(25):
            baru=buat_soal(tid,seed,lv,topik)
            p=baru.parameter
            varian=(p.get('varian'),p.get('tanya'),p.get('bangun'))
            if varian in cabang: continue
            cabang.add(varian)
            lama=replace(REGISTRI[tid](**{k:v for k,v in p.items() if k not in ('versi_katalog','konteks_umur')}),level=lv)
            old_id=database.simpan_soal(db,lama)
            new_id=database.simpan_soal(db,baru)
            assert old_id!=new_id
            assert database.simpan_soal(db,baru)==new_id
            soal.extend((lama,baru))
    assert soal
    sesi=database.buat_sesi_dari_urutan(db,siswa,seed=42,
        urutan=tuple(s.template_id for s in soal),topik=topik,level=lv,soal_terpilih=tuple(soal))
    form={}
    for b in database.isi_sesi(db,sesi):
        form['jwb_'+str(b['sesi_soal_id'])]=b['kunci']
        form['cara_'+str(b['sesi_soal_id'])]='perhitungan sintetis'
    teacher_review_service.simpan_sesi(db,sesi,form)
    assert all(b['benar']==1 for b in database.isi_sesi(db,sesi))
    database.tandai_selesai(db,sesi)
    database.konfirmasi_hasil(db,sesi,'guru')
    tabel=('soal','malrule','sesi_soal','jawaban','diagnosis','konfirmasi_hasil',
           'snapshot_outcome','penyajian_outcome','konteks_butir','konteks_konfirmasi')
    def rekaman():
        return tuple(tuple(tuple(r) for r in db.execute('SELECT * FROM '+t+' ORDER BY 1')) for t in tabel)
    sebelum=rekaman()
    hashes=tuple(teacher_print_pages.halaman_lembar(db,sesi,untuk_guru=g) for g in (False,True))
    bukti=database.muat_bukti_siklus(db,siswa)
    for flag in ('1','salah','2'):
        monkeypatch.setenv('OSN_KATALOG_VERSI',flag)
        hasil=tuple(soal_dari_baris(b) for b in database.isi_sesi(db,sesi))
        assert tuple((s.tanda_tangan,s.kunci,s.malrule,s.pembahasan) for s in hasil)==tuple(
            (s.tanda_tangan,s.kunci,s.malrule,s.pembahasan) for s in soal)
        assert tuple(teacher_print_pages.halaman_lembar(db,sesi,untuk_guru=g) for g in (False,True))==hashes
        assert database.muat_bukti_siklus(db,siswa)==bukti
        assert rekaman()==sebelum


@pytest.mark.parametrize('tid,parameter', (
    ('median_modus',{'varian':'median','data':[3,12,27]}),
    ('rata_rata_gabungan',{'n1':8,'n2':8,'x1':10,'x2':38}),
    ('unsur_bangun',{'bangun':'tabung','tanya':'titik_kali','n':3}),
))
def test_rule_sama_dengan_kunci_dibuang_bukan_digeser(tid,parameter):
    from templates import REGISTRI
    s=REGISTRI[tid](**parameter,versi_katalog=2)
    dibuang={'median_modus':'median.tanpa_urut','rata_rata_gabungan':'gabung.rata_rata_rata',
             'unsur_bangun':'unsur.kali_lupa_tabung'}[tid]
    assert dibuang not in {m.id for m in s.malrule}


@pytest.mark.parametrize('topik,tid', (('geometri-ruang','jaring_jaring'),
    ('geometri-ruang','perbandingan_volume'),('pengukuran','skala_peta'),('pengukuran','jam_menit_detik')))
def test_kombinasi_writer_tidak_didukung_ditolak(monkeypatch,topik,tid):
    monkeypatch.setenv('OSN_MATEMATIKA_VERSI','1')
    with pytest.raises(ValueError,match='matematika versi 2'):
        buat_soal(tid,0,'P6',topik)
