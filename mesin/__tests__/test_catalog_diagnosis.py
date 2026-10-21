"""Batch C: kategori diagnosis berbasis arti, bukan ordinal, dan reproduksi Medium."""
from collections import defaultdict
from fractions import Fraction as F

import pytest
from generator import buat_soal
from solid_geometry_nets import opsi_jaring_v2


@pytest.fixture(autouse=True)
def versi(monkeypatch):
    monkeypatch.setenv('OSN_KATALOG_VERSI','2')


def test_jaring_kategori_stabil_terhadap_urutan():
    kode=defaultdict(set)
    identitas=defaultdict(set)
    for seed in range(600):
        s=buat_soal('jaring_jaring',seed,'P6','geometri-ruang')
        opsi=opsi_jaring_v2(s.parameter['pilihan_benar'],s.parameter['urutan'])
        assert len(s.malrule)==4
        for m in s.malrule:
            kode[opsi['ABCDE'.index(m.jawaban)]].add(m.kode)
            identitas[opsi['ABCDE'.index(m.jawaban)]].add(m.id)
            assert m.kode=='K', (seed,m)
            assert 'susunan' in m.alasan
    assert len(kode)==5
    assert all(v=={'K'} for v in kode.values())
    assert all(len(ids)==1 for ids in identitas.values()), 'ID fokus tidak boleh berubah ketika huruf berpindah'


@pytest.mark.parametrize('lv',('P3','P5','P6'))
def test_pengandaian_tidak_mengklaim_kesalahan_hitung(lv):
    for seed in range(600):
        s=buat_soal('benar_salah_pengandaian',seed,lv,'logika')
        p=s.parameter
        assert s.kunci=='ABCDE'[p['urutan_tampil'].index(0)]
        for m in s.malrule:
            pernyataan=p['urutan_tampil']['ABCDE'.index(m.jawaban)]
            assert m.kode=='K', (seed,p,m)
            if p['varian']=='warna':
                assert 'hanya satu warna' in s.teks
                assert 'bertentangan' in m.alasan
            elif pernyataan in (2,4):
                assert 'bertentangan' in m.alasan
            else:
                assert 'tidak dijamin' in m.alasan
        assert 'Hari ini' in s.teks if p['varian']=='bekal' else True


def test_jumlah_deret_rata_ujung_eksak():
    for seed in range(600):
        s=buat_soal('jumlah_deret',seed,'P6','pola-bilangan')
        p=s.parameter
        deret=list(range(p['awal'],p['awal']+p['beda']*p['n'],p['beda']))
        assert int(s.kunci)==sum(deret)
        for m in s.malrule:
            if m.id=='jumlah_deret.rata_rata_ujung_tanpa_kali_n':
                assert F(m.jawaban.replace(',','.'))==F(deret[0]+deret[-1],2)


def test_kotak_tepi_dihitung_sekali_per_sel():
    for seed in range(600):
        s=buat_soal('luas_kotak_satuan',seed,'P3','geometri-datar')
        p=s.parameter
        tepi=sum(x in (0,p['p']-1) or y in (0,p['l']-1)
                 for x in range(p['p']) for y in range(p['l']))
        for m in s.malrule:
            if m.id=='datar.hitung_keliling':
                assert int(m.jawaban)==tepi
                assert m.kode=='K'


@pytest.mark.parametrize('lv',('P5','P6'))
def test_konversi_waktu_pembahasan_faktor_60(lv):
    n=0
    for seed in range(100):
        s=buat_soal('satuan_konversi',seed,lv,'aritmatika-lanjut')
        if s.parameter['varian'] in ('jam_ke_menit','menit_ke_jam'):
            n+=1
            assert '1 jam = 60 menit' in s.pembahasan
            assert 'DIKALI 10' not in s.pembahasan
    assert n


def test_korek_teks_dan_visual_tidak_mengklaim_segitiga(monkeypatch):
    from question_views import penyajian_dari_soal
    for visual in ('','pola-bilangan'):
        monkeypatch.setenv('OSN_VISUAL_KELUARGA',visual)
        for seed in range(100):
            s=buat_soal('korek_api',seed,'P6','pola-bilangan')
            assert 'Segitiga' not in penyajian_dari_soal(s).teks_soal
            for m in s.malrule:
                if m.id=='korek.tidak_sadar_batang_bersama':
                    assert int(m.jawaban)==s.parameter['awal']*s.parameter['gambar_ke']
                    assert 'awal' in m.alasan
