"""Konteks parameter warisan eksplisit, bukan label atau bukti kemampuan."""
from dataclasses import FrozenInstanceError

import pytest
import topics
from templates import LEVEL


def _konteks():
    import question_context
    return question_context


def test_seluruh_pasangan_komposisi_dipetakan_tanpa_pola_hilang():
    konteks = _konteks()
    harapan = {(tid, lv) for nama in topics.daftar_topik() if nama != 'campuran'
               for lv, pola in topics.ambil(nama).komposisi.items() for tid in pola}
    hasil = konteks.daftar_konteks()
    assert {(x.template_id, x.profil_parameter) for x in hasil} == harapan
    assert len(hasil) == len(harapan)
    assert len({x.id for x in hasil}) == len(hasil)
    assert hasil == konteks.daftar_konteks()
    for item in hasil:
        assert item.versi == 1
        assert item.topik_id == topics.pemilik_template(item.template_id)
        assert item.profil_parameter in LEVEL
        assert konteks.konteks_warisan(item.template_id, item.profil_parameter) == item


@pytest.mark.parametrize('pola,profil', [
    ('pola-asing', 'P3'), ('deret_aritmetika', 'kelas 4'),
    ('deret_aritmetika', ''), ('deret_aritmetika', None),
    ('persen_diskon', 'P6'), ('luas_kotak_satuan', 'P4'),
    ('paritas', 'P6'), ('fpb_dua_bilangan', 'P3'),
    (None, 'P3'), ([], 'P3'), ('deret_aritmetika', []),
])
def test_pasangan_tidak_dikenal_tidak_fallback(pola, profil):
    with pytest.raises(ValueError, match='konteks soal'):
        _konteks().konteks_warisan(pola, profil)


def test_pola_sama_profil_berbeda_tidak_dianggap_setara():
    konteks = _konteks()
    dasar = konteks.konteks_warisan('keliling_luas_datar', 'P3')
    lanjut = konteks.konteks_warisan('keliling_luas_datar', 'P4')
    assert dasar.id != lanjut.id
    assert dasar != lanjut
    with pytest.raises(FrozenInstanceError):
        dasar.profil_parameter = 'P4'


def test_id_konteks_stabil_tidak_memuat_identitas_anak():
    konteks = _konteks().konteks_warisan('persen_diskon', 'P5')
    assert konteks.id == 'warisan-v1:persen_diskon:P5'
    assert set(konteks.__dataclass_fields__) == {'template_id', 'profil_parameter'}
