"""Kontrak revisi penilaian: fakta, prosedur, ekuivalensi dan histori terpisah."""
from dataclasses import replace
from fractions import Fraction as F

import pytest
from generator import buat_soal
from diagnosis import diagnosa, setara
from templates import REGISTRI, Malrule


def usulan(s,jawaban,mal=None):
    aturan=[dict(malrule_id=m.id,jawaban=m.jawaban,kode=m.kode,alasan=m.alasan)
            for m in (s.malrule if mal is None else mal)]
    return diagnosa(s.kunci,jawaban,'cara sintetis','',False,aturan,soal=s)


@pytest.mark.parametrize('tid,topik,seed,jawaban',(
    ('pecahan_operasi_campuran','aritmetika-dasar',0,'4/6'),
    ('pecahan_kali_bagi','aritmetika-dasar',0,'16/98'),
    ('luas_permukaan','geometri-ruang',5,'715,920'),
))
def test_jawaban_ekuivalen_baru_diterima(monkeypatch,tid,topik,seed,jawaban):
    monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
    s=buat_soal(tid,seed,'P5',topik)
    assert usulan(s,jawaban).benar
    assert s.parameter['revisi_penilaian']==1
    for buruk in ('1/0','1+2','1, 2','nan','1e3','2 kg','9'*129):
        assert not usulan(s,buruk).benar


def test_menyusul_tidak_menuduh_angka_nudge(monkeypatch):
    monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
    s=buat_soal('menyusul',1,'P6','aritmatika-lanjut')
    assert usulan(s,'3').kode is None
    u=usulan(s,'0,52')
    assert not u.benar and u.kode=='K'
    assert 'berpapasan' in u.alasan


def test_windu_menyalin_input_tetap_input(monkeypatch):
    monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
    s=buat_soal('satuan_waktu_lama',17,'P6','pengukuran')
    assert usulan(s,'218').kode is None
    assert 'menyalin' in usulan(s,'135').alasan
    assert 'membalik' in usulan(s,'84,375').alasan


def test_hasil_collision_tidak_dipilih_dari_urutan(monkeypatch):
    monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
    s=buat_soal('pecahan_operasi_campuran',0,'P6','aritmetika-dasar')
    mal=(Malrule('satu','4/6','K','prosedur1'),Malrule('dua','2/3','H','prosedur2'))
    s=replace(s,kunci='9')
    for aturan in (mal,tuple(reversed(mal))):
        hasil=usulan(s,'2/3',aturan)
        assert hasil.kode is None and hasil.malrule_id is None and not hasil.yakin


@pytest.mark.parametrize('tid,topik',(
    ('pecahan_operasi_campuran','aritmetika-dasar'),('pecahan_kali_bagi','aritmetika-dasar'),
    ('menyusul','aritmatika-lanjut'),('kecepatan_jarak_waktu','aritmatika-lanjut'),
    ('satuan_waktu_lama','pengukuran'),('luas_permukaan','geometri-ruang'),
))
def test_reader_lama_tetap_identik(monkeypatch,tid,topik):
    for seed in range(25):
        monkeypatch.setenv('OSN_PENILAIAN_REVISI','0')
        lama=buat_soal(tid,seed,'P6',topik)
        monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
        baru=buat_soal(tid,seed,'P6',topik)
        assert replace(REGISTRI[tid](**lama.parameter),level='P6')==lama
        if tid!='luas_permukaan' or lama.parameter['varian'].startswith('tabung'):
            assert lama.tanda_tangan!=baru.tanda_tangan
        monkeypatch.setenv('OSN_PENILAIAN_REVISI','rusak')
        assert replace(REGISTRI[tid](**baru.parameter),level='P6')==baru


def test_collision_mentah_pecahan_tidak_hilang_sebelum_filter():
    s=REGISTRI['pecahan_operasi_campuran'](2,3,2,3,3,4,revisi_penilaian=1)
    assert s.kunci=='7/12'
    assert all(F(m.jawaban.replace(',','.'))!=F(1,2) for m in s.malrule)
    assert usulan(s,'1/2').kode is None


def test_filter_semantik_membuang_semua_collision():
    from assessment_revision import saring_eksak
    kandidat=(Malrule('kunci','4/6','K','sama kunci'),Malrule('a','1/2','K','satu'),
              Malrule('b','0,50','H','dua'),Malrule('c','3/4','K','lain'))
    assert saring_eksak('2/3',kandidat)==(kandidat[-1],)
    assert saring_eksak('2/3',tuple(reversed(kandidat)))==(kandidat[-1],)


@pytest.mark.parametrize('nilai',(None,0,2,True,'1'))
def test_revisi_asing_ditolak(nilai):
    with pytest.raises(ValueError,match='revisi penilaian'):
        REGISTRI['pecahan_operasi_campuran'](3,6,2,3,2,4,revisi_penilaian=nilai)


def test_caller_bank_historis_dan_baru_tetap_terpisah(tmp_path,monkeypatch):
    import database, reports, teacher_review_service
    from question_views import soal_dari_baris
    path=tmp_path/'sintetis.db';database.siapkan(path)
    with database.buka(path) as c:
        anak=database.tambah_siswa(c,'Fixture','P5',pemilik='guru')
        monkeypatch.setenv('OSN_PENILAIAN_REVISI','0')
        lama=buat_soal('pecahan_operasi_campuran',0,'P5','aritmetika-dasar')
        monkeypatch.setenv('OSN_PENILAIAN_REVISI','1')
        baru=buat_soal('pecahan_operasi_campuran',0,'P5','aritmetika-dasar')
        sid=database.buat_sesi_dari_urutan(c,anak,0,urutan=(lama.template_id,baru.template_id),
            topik='aritmetika-dasar',level='P5',soal_terpilih=(lama,baru))
        rows=database.isi_sesi(c,sid)
        assert rows[0]['soal_id']!=rows[1]['soal_id']
        for row in rows:database.simpan_jawaban(c,row['sesi_soal_id'],'4/6','sintetis')
        reports.diagnosa_murid(c,sid)
        assert [r['benar'] for r in database.isi_sesi(c,sid)]==[0,1]
        for row in rows:
            teacher_review_service.simpan_sesi(c,sid,{f"jwb_{row['sesi_soal_id']}":'4/6',f"cara_{row['sesi_soal_id']}":'sintetis ulang'})
        assert [r['benar'] for r in database.isi_sesi(c,sid)]==[0,1]
        # Guru mengesahkan jawaban lama secara eksplisit, bukan backfill parser.
        old=rows[0]['sesi_soal_id']
        teacher_review_service.simpan_sesi(c,sid,{f'kode_{old}':'benar'})
        assert database.isi_sesi(c,sid)[0]['manual']==1
        database.tandai_selesai(c,sid);database.konfirmasi_hasil(c,sid,'guru')
        before=tuple(tuple(r) for r in c.execute('SELECT * FROM snapshot_outcome'))
        for flag in ('0','rusak'):
            monkeypatch.setenv('OSN_PENILAIAN_REVISI',flag)
            assert [soal_dari_baris(r).kunci for r in database.isi_sesi(c,sid)]==[lama.kunci,baru.kunci]
            assert tuple(tuple(r) for r in c.execute('SELECT * FROM snapshot_outcome'))==before


def test_default_tidak_mengubah_penilaian_histori(monkeypatch):
    monkeypatch.delenv('OSN_PENILAIAN_REVISI',raising=False)
    s=buat_soal('pecahan_operasi_campuran',0,'P5','aritmetika-dasar')
    assert 'revisi_penilaian' not in s.parameter
    assert not usulan(s,'4/6').benar
