"""Konteks umur baru tidak mengarang hubungan keluarga; reader lama tetap utuh."""
from dataclasses import replace

import pytest
from generator import buat_soal
from templates import REGISTRI


@pytest.mark.parametrize('level',('P3','P6'))
def test_umur_baru_dua_orang_tanpa_relasi_keluarga(monkeypatch,level):
    monkeypatch.setenv('OSN_KATALOG_VERSI','2')
    for seed in range(600):
        s=buat_soal('soal_umur',seed,level,'logika')
        assert 'ayah' not in s.teks.lower() and 'anak' not in s.teks.lower(), (seed,s.teks)
        assert 'Ari' in s.teks and 'Bima' in s.teks
        assert s.parameter.get('konteks_umur')=='dua_orang_v1'
        assert 'Ari' in s.pembahasan and 'Bima' in s.pembahasan
        assert all('ayah' not in m.alasan and 'anak' not in m.alasan for m in s.malrule)


def test_identitas_konteks_baru_tidak_meminjam_soal_v2_lama(monkeypatch):
    monkeypatch.setenv('OSN_KATALOG_VERSI','2')
    p=dict(a=44,b=8,k=5,n=1,tanya='kali_umur',versi_katalog=2)
    lama=replace(REGISTRI['soal_umur'](**p),level='P6')
    baru=buat_soal('soal_umur',0,'P6','logika')
    assert baru.tanda_tangan!=lama.tanda_tangan, 'konteks baru harus beridentitas sendiri'
    assert lama.kunci==baru.kunci=='5'
    assert 'ayah' in lama.teks and 'anak' in lama.teks
    monkeypatch.setenv('OSN_KATALOG_VERSI','rusak')
    assert replace(REGISTRI['soal_umur'](**p),level='P6')==lama
    assert replace(REGISTRI['soal_umur'](**baru.parameter),level='P6')==baru


def test_domain_angka_dan_rng_umur_tidak_diperlebar(monkeypatch):
    from random import Random
    import topic_logic
    for level in ('P3','P6'):
        for seed in range(100):
            a,b=Random(seed),Random(seed)
            monkeypatch.setenv('OSN_KATALOG_VERSI','1')
            lama=topic_logic._parameter('soal_umur',a,level)
            monkeypatch.setenv('OSN_KATALOG_VERSI','2')
            baru=topic_logic._parameter('soal_umur',b,level)
            assert {k:v for k,v in baru.items() if k not in ('versi_katalog','konteks_umur')}==lama
            assert a.getstate()==b.getstate()


@pytest.mark.parametrize('konteks',('ayah_baru','',None,False))
def test_konteks_asing_ditolak(konteks):
    with pytest.raises(ValueError,match='konteks umur'):
        REGISTRI['soal_umur'](12,3,2,6,'kali_umur',versi_katalog=2,konteks_umur=konteks)
