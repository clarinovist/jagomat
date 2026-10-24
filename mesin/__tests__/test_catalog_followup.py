"""Revisi2 offline: prosedur eksak, identitas baru, reader histori tetap."""
from dataclasses import replace
from fractions import Fraction as F

import pytest

from diagnosis import diagnosa
from generator import buat_soal
from templates import REGISTRI

TARGET = {'satuan_kuantitas': 'pengukuran', 'rata_rata': 'statistika',
          'luas_arsiran': 'geometri-datar'}


def angka(teks):
    return F(str(teks).replace(',', '.'))


def usulan(soal, jawaban):
    aturan = [dict(malrule_id=m.id, jawaban=m.jawaban, kode=m.kode, alasan=m.alasan)
              for m in soal.malrule]
    return diagnosa(soal.kunci, jawaban, 'cara sintetis', '', False, aturan, soal=soal)


@pytest.mark.parametrize('tid,level,seed,ident,harapan', (
    ('satuan_kuantitas', 'P4', 1, 'rev2.kuantitas.faktor_tertukar_kodi', F(25, 3)),
    ('satuan_kuantitas', 'P5', 6, 'rev2.kuantitas.faktor_tertukar_lusin', F(12, 5)),
    ('rata_rata', 'P4', 1, 'rev2.rata.bagi_n_tambah_satu', F(301, 8)),
    ('luas_arsiran', 'P5', 1, 'rev2.arsiran.pakai_pi_314', F(2107, 50)),
))
def test_prosedur_tidak_dipotong(monkeypatch, tid, level, seed, ident, harapan):
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
    soal = buat_soal(tid, seed, level, TARGET[tid])
    assert soal.parameter.get('revisi_penilaian') == 2
    rule = next(m for m in soal.malrule if m.id == ident)
    assert angka(rule.jawaban) == harapan
    assert usulan(soal, str(harapan)).malrule_id == ident
    assert usulan(soal, str(harapan.numerator * 2) + '/' + str(harapan.denominator * 2)).malrule_id == ident


def test_data_terakhir_bukan_kunci_tambah_satu(monkeypatch):
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
    soal = buat_soal('rata_rata', 0, 'P4', 'statistika')
    p = soal.parameter
    assert p['varian'] == 'cari_data_ke_n'
    harapan = p['rata'] * len(p['data']) - sum(p['data'][:-2])
    rule = next(m for m in soal.malrule if m.id == 'rev2.rata.abaikan_data_diketahui_terakhir')
    assert angka(rule.jawaban) == harapan
    assert all(m.id != 'rata.kurang_satu_data' for m in soal.malrule)


@pytest.mark.parametrize('tid', TARGET)
def test_default_dan_reader_histori_identik(monkeypatch, tid):
    monkeypatch.delenv('OSN_KATALOG_LANJUTAN', raising=False)
    monkeypatch.setenv('OSN_PENILAIAN_REVISI', '0')
    lama = buat_soal(tid, 1, 'P5', TARGET[tid])
    assert 'revisi_penilaian' not in lama.parameter
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
    baru = buat_soal(tid, 1, 'P5', TARGET[tid])
    assert baru.tanda_tangan != lama.tanda_tangan
    assert baru.kunci == lama.kunci
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', 'rusak')
    assert replace(REGISTRI[tid](**lama.parameter), level='P5') == lama
    assert replace(REGISTRI[tid](**baru.parameter), level='P5') == baru
    with pytest.raises(ValueError, match='OSN_KATALOG_LANJUTAN'):
        buat_soal(tid, 1, 'P5', TARGET[tid])


@pytest.mark.parametrize('revisi', (None, 0, 1, True, '2', 3))
def test_revisi_asing_ditolak(revisi):
    with pytest.raises(ValueError, match='revisi penilaian'):
        REGISTRI['rata_rata']('cari_rata', [1, 2, 3], revisi_penilaian=revisi)


@pytest.mark.parametrize('tid,parameter', (
    ('satuan_kuantitas', dict(satuan='lusin', benda='buku', nilai=120, arah='typo')),
    ('rata_rata', dict(varian='typo', data=[1, 2, 3], rata=2)),
    ('luas_arsiran', dict(varian='typo', luar=10, dalam=6)),
))
def test_cabang_typo_ditolak_registry_kontrak_dan_visual(tid, parameter):
    from assessment_revision import kontrak
    from catalog_followup import parameter_visual
    # Legacy boleh fallback; marker2 tidak mewarisi penerimaan cabang typo itu.
    legacy = REGISTRI[tid](**parameter)
    with pytest.raises(ValueError, match='revisi penilaian'):
        REGISTRI[tid](**parameter, revisi_penilaian=2)
    with pytest.raises(ValueError, match='revisi penilaian'):
        kontrak(replace(legacy, parameter=dict(parameter, revisi_penilaian=2)))
    with pytest.raises(ValueError, match='revisi penilaian'):
        parameter_visual(tid, dict(parameter, revisi_penilaian=2))


def test_revisi1_tidak_diperluas_diam_diam(monkeypatch):
    monkeypatch.delenv('OSN_KATALOG_LANJUTAN', raising=False)
    monkeypatch.setenv('OSN_PENILAIAN_REVISI', '1')
    for tid, topik in TARGET.items():
        assert 'revisi_penilaian' not in buat_soal(tid, 1, 'P5', topik).parameter


def test_collision_dibuang_bukan_digeser():
    soal = REGISTRI['rata_rata']('cari_rata', [2, 2, 2], revisi_penilaian=2)
    # K 6/4 berbeda dari H1; keduanya tetap literal dan tidak dinudge.
    assert {angka(m.jawaban) for m in soal.malrule} == {F(6), F(3, 2), F(1)}
    soal = REGISTRI['rata_rata']('cari_rata', [4, 4, 4], revisi_penilaian=2)
    # 12/4 = 3 dan 4-1 = 3: seluruh collision harus hilang.
    assert {angka(m.jawaban) for m in soal.malrule} == {F(12)}
    assert usulan(soal, '3').kode is None


def test_arsiran_teks_tanpa_diagram_menentukan_daerah(monkeypatch):
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
    soal = buat_soal('luas_arsiran', 1, 'P5', 'geometri-datar')
    assert 'berpusat di satu pojok persegi' in soal.teks
    assert 'di dalam persegi tetapi di luar keempat' in soal.teks
    assert 'seperempat lingkaran diarsir' in soal.teks
    assert '(cm²)' in soal.teks


def test_visual_arsiran_menerima_marker_sah_saja(monkeypatch):
    from topic_plane_geometry_visual import proyeksi_geometri_datar
    monkeypatch.setenv('OSN_KATALOG_LANJUTAN', '1')
    soal = buat_soal('luas_arsiran', 1, 'P5', 'geometri-datar')
    assert soal.parameter.get('revisi_penilaian') == 2
    lama = {k: v for k, v in soal.parameter.items() if k != 'revisi_penilaian'}
    assert proyeksi_geometri_datar(soal.template_id, soal.parameter) == proyeksi_geometri_datar(soal.template_id, lama)
    for marker in (1, True, '2', None, 3):
        with pytest.raises(ValueError, match='revisi penilaian'):
            proyeksi_geometri_datar(soal.template_id, dict(lama, revisi_penilaian=marker))
