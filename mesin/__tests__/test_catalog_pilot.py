"""Reader pilot memahami marker katalog baru tanpa menafsir ulang bukti lama."""
import pytest
from generator import buat_soal
from skill_pilot import KonteksPilot, PRASYARAT, POLA_KISI, sidik_variasi, validasi_fokus
from skill_pilot_selector import pilih_probe


def test_selector_pilot_katalog2_dan_sidik_geometri_tetap(monkeypatch):
    monkeypatch.setenv('OSN_KATALOG_VERSI','2')
    k=KonteksPilot(PRASYARAT,'P3','teks-v1')
    for seed in range(25):
        soal=buat_soal(POLA_KISI,seed,'P3','geometri-datar')
        try:
            sidik=sidik_variasi(k,POLA_KISI,soal.parameter)
        except ValueError:
            pytest.fail('reader pilot menolak marker katalog2 yang sah')
        lama={a:b for a,b in soal.parameter.items() if a!='versi_katalog'}
        assert sidik==sidik_variasi(k,POLA_KISI,lama)
        for m in soal.malrule:
            try: validasi_fokus(k,(POLA_KISI,m.kode,m.id))
            except ValueError: pytest.fail('reader pilot menolak kategori rule katalog2 yang sah')
    assert len(pilih_probe(k,0,4))==4
    assert len(pilih_probe(k,0,4,fokus=(POLA_KISI,'K','datar.hitung_keliling')))==4
    validasi_fokus(k,(POLA_KISI,'H','datar.hitung_keliling'))  # Histori tetap sah.


@pytest.mark.parametrize('nilai',(1,3,True,'2',None))
def test_marker_pilot_asing_tidak_membuka_guard(nilai):
    k=KonteksPilot(PRASYARAT,'P3','teks-v1')
    with pytest.raises(ValueError):
        sidik_variasi(k,POLA_KISI,dict(p=8,l=3,satuan='cm',konteks='ubin',versi_katalog=nilai))


def test_marker_sah_tidak_mengabaikan_field_asing():
    k=KonteksPilot(PRASYARAT,'P3','teks-v1')
    with pytest.raises(ValueError):
        sidik_variasi(k,POLA_KISI,dict(p=8,l=3,satuan='cm',konteks='ubin',versi_katalog=2,asing=1))
