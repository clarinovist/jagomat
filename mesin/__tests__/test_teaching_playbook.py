"""Palang playbook dengan ulasan SINTETIS, bukan pengesahan isi ajar nyata."""
import copy
import json
from pathlib import Path

import pytest

import teaching_playbook as pb

FOKUS = ('deret_aritmetika', 'K', 'aritmetika.beda_dikira_satu')
PENDEKATAN = 'konsep:deret_aritmetika:aritmetika.beda_dikira_satu'


def entri_sintetis():
    """Data positif buatan khusus tes, tidak pernah menulis konten runtime."""
    e = {
        'template_id': FOKUS[0], 'profil': 'P3', 'kode_intervensi': 'K',
        'malrule_id': FOKUS[2], 'versi': 1, 'saksi_seed': 0,
        'miskonsepsi': 'PENANDA SINTETIS <b>bukan diagnosis baru</b>',
        'batas': 'Hanya fixture pengujian, bukan pengesahan matematika.',
        'urutan': {'benda': 'Langkah benda sintetis.', 'gambar': 'Langkah gambar sintetis.',
                   'simbol': 'Langkah simbol sintetis.'},
        'pertanyaan': ['Apa yang berubah?', 'Bagaimana memeriksanya?'],
        'pendekatan': [
            {'pendekatan_id': PENDEKATAN, 'contoh': 'Contoh sintetis A.'},
            {'pendekatan_id': 'jelaskan-balik:deret_aritmetika:aritmetika.beda_dikira_satu',
             'contoh': 'Contoh sintetis B.'}],
        'tanda_paham': ['Menjelaskan tanpa menyalin.'],
        'sumber': ['Fixture sintetis, bukan sumber ajar.'],
        'status': 'disahkan', 'reviewer': 'ULASAN SINTETIS BUKAN PENGESAHAN KONTEN',
        'tanggal_review': '2026-10-22', 'versi_review': 1, 'sha256_review': '',
    }
    e['sha256_review'] = pb.sidik_isi(e)
    return e


def simpan(path, entri):
    path.write_text(json.dumps({'versi_format': 1, 'entri': entri}), encoding='utf-8')


@pytest.fixture
def konten(tmp_path, monkeypatch):
    path = tmp_path / 'fixture-sintetis.json'
    monkeypatch.setattr(pb, 'BERKAS', path)
    simpan(path, [entri_sintetis()])
    return path


def render(peran='guru', fokus=FOKUS, profil='P3', pendekatan_id=None):
    return pb.render(fokus, profil, peran=peran, pendekatan_id=pendekatan_id)


def test_fixture_positif_dan_escape(konten):
    isi = render(pendekatan_id=PENDEKATAN)
    assert 'data-playbook-guru' in isi and 'PENANDA SINTETIS' in isi
    assert '&lt;b&gt;' in isi and '<b>bukan diagnosis' not in isi
    assert 'Contoh sintetis A.' in isi and 'Contoh sintetis B.' not in isi
    assert 'bukan kelulusan otomatis' in isi
    assert '<script' not in isi and '<form' not in isi and '<input' not in isi
    assert '<details' in isi and '<details open' not in isi


def test_tinjauan_boleh_membaca_kedua_contoh_tanpa_memilih_rekomendasi(konten):
    isi = render()
    assert 'Contoh sintetis A.' in isi and 'Contoh sintetis B.' in isi


def test_draf_tidak_tampil_walau_metadata_review_lengkap(konten):
    e = entri_sintetis()
    e['status'] = 'draf'
    simpan(konten, [e])
    assert render() == ''


@pytest.mark.parametrize('field,value', [
    ('reviewer', None), ('reviewer', ''), ('tanggal_review', None),
    ('tanggal_review', '2026-02-30'), ('tanggal_review', '2026-2-2'),
    ('versi_review', 2), ('sha256_review', '0'*64), ('status', 'Disahkan'),
])
def test_review_tidak_sah_gagal_tertutup(konten, field, value):
    e = entri_sintetis()
    e[field] = value
    simpan(konten, [e])
    assert render() == ''


def test_edit_isi_membatalkan_review_tanpa_perlu_ganti_versi(konten):
    e = entri_sintetis()
    e['pendekatan'][0]['contoh'] = 'Konten telah berubah.'
    simpan(konten, [e])
    assert render() == ''


@pytest.mark.parametrize('peran', ['murid', 'admin', '', None])
def test_peran_lain_tidak_membaca_berkas(konten, monkeypatch, peran):
    def dilarang(*a, **kw):
        pytest.fail('Permukaan bukan guru membaca JSON playbook')
    monkeypatch.setattr(pb, '_baca', dilarang)
    assert render(peran=peran) == ''


@pytest.mark.parametrize('fokus,profil,pendekatan', [
    (FOKUS, 'P4', None), ((FOKUS[0], 'H', FOKUS[2]), 'P3', None),
    ((FOKUS[0], 'K', None), 'P3', None), ((FOKUS[0], 'K', 'lain'), 'P3', None),
    (('tidak_ada', 'K', FOKUS[2]), 'P3', None), (FOKUS, 'P3', 'tidak_ada'),
])
def test_kecocokan_tepat_tanpa_fallback(konten, fokus, profil, pendekatan):
    assert render(fokus=fokus, profil=profil, pendekatan_id=pendekatan) == ''


@pytest.mark.parametrize('field,value', [
    ('urutan', {}), ('pertanyaan', ['Satu saja']), ('pertanyaan', 'bukan daftar'),
    ('versi', True), ('profil', 'P99'), ('kode_intervensi', 'X'),
    ('miskonsepsi', ''), ('sumber', []), ('tanda_paham', []),
    ('batas', None), ('template_id', '../../privat'), ('pendekatan', []),
    ('saksi_seed', True), ('saksi_seed', -1), ('saksi_seed', 10000),
])
def test_skema_invalid_tidak_tampil(konten, field, value):
    e = entri_sintetis()
    e[field] = value
    e['sha256_review'] = pb.sidik_isi(e)
    simpan(konten, [e])
    assert render() == ''


def test_contoh_alternatif_harus_berbeda_dan_id_existing(konten):
    e = entri_sintetis()
    e['pendekatan'][1]['contoh'] = e['pendekatan'][0]['contoh']
    e['sha256_review'] = pb.sidik_isi(e)
    simpan(konten, [e])
    assert render() == ''
    e = entri_sintetis()
    e['pendekatan'][1]['pendekatan_id'] = 'pendekatan-rekaan'
    e['sha256_review'] = pb.sidik_isi(e)
    simpan(konten, [e])
    assert render() == ''


@pytest.mark.parametrize('isi', ['{', 'null', '[]', '{"versi_format":2,"entri":[]}',
                                  '{"versi_format":1,"entri":"salah"}',
                                  '{"versi_format":1,"versi_format":1,"entri":[]}'])
def test_berkas_rusak_tidak_merusak_halaman(konten, isi):
    konten.write_text(isi, encoding='utf-8')
    assert render() == ''


def test_berkas_hilang_dan_encoding_rusak(konten):
    konten.unlink()
    assert render() == ''
    konten.write_bytes(b'\xff')
    assert render() == ''


def test_kunci_json_ganda_pada_entri_valid_ditolak(konten):
    simpan(konten, [entri_sintetis()])
    isi = konten.read_text()
    konten.write_text(isi.replace('"versi_format": 1', '"versi_format": 1, "versi_format": 1'))
    assert render() == ''


def test_duplikat_identitas_ditolak_bukan_ambil_pertama(konten):
    e = entri_sintetis()
    simpan(konten, [e, copy.deepcopy(e)])
    assert render() == ''


def test_pasangan_malrule_kode_rekaan_ditolak(konten):
    e = entri_sintetis()
    e['malrule_id'] = 'aritmetika.rekaan'
    for p in e['pendekatan']:
        p['pendekatan_id'] = p['pendekatan_id'].replace(FOKUS[2], e['malrule_id'])
    e['sha256_review'] = pb.sidik_isi(e)
    simpan(konten, [e])
    assert render(fokus=(FOKUS[0], 'K', e['malrule_id'])) == ''


@pytest.mark.parametrize('field', ['miskonsepsi', 'reviewer', 'sumber', 'urutan', 'pendekatan'])
def test_surrogate_json_gagal_tertutup(konten, field):
    e = entri_sintetis()
    if field == 'sumber':
        e[field] = ['\ud800']
    elif field == 'urutan':
        e[field]['benda'] = '\ud800'
    elif field == 'pendekatan':
        e[field][0]['contoh'] = '\ud800'
    else:
        e[field] = '\ud800'
    simpan(konten, [e])
    assert render() == ''


def test_profil_template_tidak_didukung_meski_request_cocok(konten):
    e = entri_sintetis()
    e['profil'] = 'P99'
    e['sha256_review'] = pb.sidik_isi(e)
    simpan(konten, [e])
    assert render(profil='P99') == ''


def test_validasi_skema_gagal_sebelum_render(konten):
    e = entri_sintetis()
    e['versi'] = True
    e['versi_review'] = 1
    e['sha256_review'] = pb.sidik_isi(e)
    simpan(konten, [e])
    assert render() == ''


def test_entri_rusak_tidak_menghilangkan_entri_lain(konten):
    simpan(konten, [None, {'template_id': 'rusak'}, entri_sintetis()])
    assert 'PENANDA SINTETIS' in render()


def test_draf_valid_bisa_diulas_offline_tetapi_tidak_dirender(konten):
    e = entri_sintetis()
    e.update(status='draf', reviewer=None, tanggal_review=None, versi_review=None, sha256_review=None)
    assert pb.validasi_entri(e) == ()
    simpan(konten, [e])
    assert render() == ''


def test_json_disertakan_image_di_luar_aset_publik():
    root = Path(__file__).resolve().parents[1]
    assert 'COPY --chown=osn:osn konten/ /app/konten/' in (root / 'Dockerfile').read_text()
    assert pb.BERKAS == root / 'konten' / 'playbook_p3.json'
