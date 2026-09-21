"""Kontrak pilihan konfigurasi dan pelestarian draf Pendamping."""
import pytest

from assistant_inline import parse_draf_latihan, GalatInline
from question_context import profil_dari_form, validasi_pilihan, label_profil_parameter


def test_draf_pendamping_mempertahankan_pilihan_profil_tanpa_kelas():
    data = {'topik': ['aritmatika-lanjut'], 'jumlah_soal': ['10'], 'mode': ['drill'],
            'hadir_timer_mode': ['1'], 'durasi_menit': ['15'], 'timer_auto': ['0'],
            'profil_parameter': ['P6']}
    draf = parse_draf_latihan(data, ['aritmatika-lanjut'])
    assert draf.profil_parameter == 'P6' and draf.topik == 'aritmatika-lanjut'
    with pytest.raises(GalatInline):
        parse_draf_latihan(dict(data, profil_parameter=['P3', 'P6']), ['aritmatika-lanjut'])
    with pytest.raises(GalatInline):
        parse_draf_latihan(dict(data, profil_parameter=['asing']), ['aritmatika-lanjut'])


def test_draf_lama_tidak_menebak_default_profil():
    data = {'topik': ['pola-bilangan'], 'jumlah_soal': ['10'], 'mode': ['drill'],
            'hadir_timer_mode': ['1'], 'durasi_menit': ['15'], 'timer_auto': ['0']}
    assert parse_draf_latihan(data, ['pola-bilangan']).profil_parameter == ''


@pytest.mark.parametrize('nilai', [None, [], [''], ['P2'], ['P3', 'P6'], 'P3'])
def test_pilihan_profil_eksplisit_tanpa_fallback(nilai):
    with pytest.raises(ValueError):
        profil_dari_form({'profil_parameter': nilai})


def test_pilihan_topik_profil_tidak_membatasi_kelas():
    assert profil_dari_form({'profil_parameter': ['P6']}) == 'P6'
    validasi_pilihan(['aritmatika-lanjut'], 'P6')
    with pytest.raises(ValueError):
        validasi_pilihan(['aritmatika-lanjut', 'pola-bilangan'], 'P3')
    assert label_profil_parameter('P6') == 'Profil P6'
    assert label_profil_parameter('kelas 4') == 'Profil warisan: kelas 4'
