"""Proyeksi soal ruang ke fakta visual yang aman untuk anak."""
from __future__ import annotations
from collections.abc import Mapping
from types import MappingProxyType

from solid_geometry_nets import opsi_jaring_v2
from solid_geometry_visual_data import validasi_data
from visual_contract import DescriptorVisual

_FIELD = MappingProxyType({
    'unsur_bangun': frozenset(('bangun', 'tanya', 'n')),
    'kubus_dicat': frozenset(('n', 'tanya', 'n_kubus')),
    'jaring_jaring': frozenset(('pilihan_benar', 'urutan', 'versi')),
    'volume_kubus_balok': frozenset(('varian', 's', 'p', 'l', 't', 'V')),
    'volume_prisma_tabung': frozenset(('varian', 'a', 't_segitiga', 't_prisma', 'r', 't', 'V', 'versi')),
    'luas_permukaan': frozenset(('varian', 's', 'p', 'l', 't', 'r', 'LP', 'versi')),
})


def _hasil(teks, data):
    validasi_data(data)
    return teks, DescriptorVisual('geometri_ruang', 1, data)


def _unsur(p):
    tanya = p['tanya']
    pilihan = tuple(s+k for s in ('rusuk', 'sisi', 'titik') for k in ('', '_kali'))
    if tanya not in pilihan:
        raise ValueError('pertanyaan unsur tidak dikenal')
    jumlah = p['n'] if tanya.endswith('_kali') else 1
    data = {'model': 'unsur', 'bangun': p['bangun'], 'jumlah': jumlah}
    validasi_data(data)
    nama = p['bangun'].replace('_', ' ')
    unsur = 'titik sudut' if tanya.startswith('titik') else tanya.replace('_kali', '')
    konteks = f'Ada {jumlah} bangun {nama} identik. Diagram menunjukkan satu contohnya.'
    return _hasil(f'{konteks} Berapa total {unsur} seluruh bangun?', data)


def _dicat(p):
    tanya = p['tanya']
    nama = {'nol_sisi': 'tidak terkena cat', 'satu_sisi': 'terkena cat pada tepat 1 sisi',
            'dua_sisi': 'terkena cat pada tepat 2 sisi', 'tiga_sisi': 'terkena cat pada tepat 3 sisi'}
    if tanya not in tuple(k+akhir for k in nama for akhir in ('', '_kali')):
        raise ValueError('pertanyaan kubus dicat tidak dikenal')
    jumlah = p['n_kubus'] if tanya.endswith('_kali') else 1
    data = {'model': 'kubus_dicat', 'n': p['n'], 'jumlah': jumlah}
    target = nama[tanya.replace('_kali', '')]
    return _hasil(f'Ada {jumlah} kubus besar identik seperti contoh pada diagram. '
                  'Semua sisi luarnya dicat, lalu dipotong mengikuti kisi menjadi kubus kecil sama besar. '
                  f'Berapa total kubus kecil yang {target}?', data)


def _jaring(p):
    if p.get('versi', 1) == 1:
        return None
    if type(p['versi']) is not int or p['versi'] != 2:
        raise ValueError('versi jaring visual tidak didukung')
    opsi = opsi_jaring_v2(p['pilihan_benar'], p['urutan'])
    return _hasil('Manakah susunan persegi yang dapat dilipat menjadi kubus? '
                  'Jawab A, B, C, D, atau E.', {'model': 'jaring', 'opsi': opsi})


def _dimensi(tid, p):
    v = p['varian']
    if not isinstance(v, str):
        raise ValueError('varian dimensi wajib teks')
    besaran = 'luas_permukaan' if tid == 'luas_permukaan' else 'volume'
    bidang = 'LP' if besaran == 'luas_permukaan' else 'V'
    if v.startswith('tabung'):
        return _tabung(p, v, besaran, bidang)
    if tid == 'volume_prisma_tabung':
        return _prisma(p, v)
    varian = {'kubus_cari_V', 'kubus_cari_s', 'balok_cari_V', 'balok_cari_p'}
    if tid == 'luas_permukaan':
        varian = {'kubus_LP', 'kubus_cari_s', 'balok_LP', 'balok_cari_p'}
    if v not in varian:
        raise ValueError('varian bangun ruang tidak didukung')
    kubus = v.startswith('kubus')
    balik = v.endswith(('_s', '_p'))
    model = 'kubus' if kubus else 'balok'
    data = {'model': model, 's': p['s']} if kubus else {
        'model': model, 'p': p['p'], 'l': p['l'], 't': p['t']}
    if balik:
        data = {'model': model+'_balik', 'besaran': besaran, 'nilai': p[bidang],
                **({} if kubus else {'l': p['l'], 't': p['t']})}
    target = ('panjang rusuknya (cm)' if kubus else 'panjangnya (cm)') if balik else (
        'volumenya (cm³)' if bidang == 'V' else 'luas permukaannya (cm²)')
    return _hasil(f'Perhatikan {model} pada diagram. Berapa {target}?', data)


def _tabung(p, v, besaran, bidang):
    if p.get('versi', 1) == 1:
        return None
    if type(p['versi']) is not int or p['versi'] != 2:
        raise ValueError('versi tabung visual tidak didukung')
    maju, balik = (('tabung_V', 'tabung_balik') if bidang == 'V'
                    else ('tabung_LP', 'tabung_cari_t'))
    if v not in (maju, balik):
        raise ValueError('varian tabung tidak dikenal')
    data = {'model': 'tabung', 'r': p['r'], 't': p['t']} if v == maju else {
        'model': 'tabung_balik', 'r': p['r'], 'besaran': besaran, 'nilai': p[bidang]}
    validasi_data(data)
    pi = '22/7' if p['r'] % 7 == 0 else '3,14'
    target = ('tingginya (cm)' if v == balik else
              'volumenya (cm³)' if bidang == 'V' else 'luas permukaannya (cm²)')
    return _hasil(f'Perhatikan tabung pada diagram (π = {pi}). Berapa {target}?', data)


def _prisma(p, v):
    if v not in ('prisma_V', 'prisma_balik'):
        raise ValueError('varian prisma tidak dikenal')
    data = {'model': 'prisma' if v == 'prisma_V' else 'prisma_balik',
            'a': p['a'], 'tinggi_alas': p['t_segitiga'],
            **({'tinggi': p['t_prisma']} if v == 'prisma_V' else {'nilai': p['V']})}
    target = 'volumenya (cm³)' if v == 'prisma_V' else 'tinggi prismanya (cm)'
    return _hasil(f'Perhatikan prisma beralas segitiga pada diagram. Berapa {target}?', data)


def proyeksi_geometri_ruang(template_id, parameter):
    """Keluarga lain tetap teks; parameter visual yang rusak gagal terlihat."""
    if not isinstance(template_id, str) or not isinstance(parameter, Mapping):
        raise ValueError('template dan parameter visual tidak valid')
    if template_id not in _FIELD:
        return None
    from catalog_versions import parameter_visual
    parameter = parameter_visual(template_id, parameter, {'unsur_bangun', 'jaring_jaring', 'volume_prisma_tabung'})
    if any(not isinstance(k, str) for k in parameter) or set(parameter) - _FIELD[template_id]:
        raise ValueError('field parameter visual tidak dikenal')
    if 'versi' in parameter and (type(parameter['versi']) is not int or parameter['versi'] not in (1, 2)):
        raise ValueError('versi visual tidak didukung')
    fungsi = {'unsur_bangun': _unsur, 'kubus_dicat': _dicat, 'jaring_jaring': _jaring}.get(template_id)
    try:
        return fungsi(parameter) if fungsi else _dimensi(template_id, parameter)
    except KeyError as galat:
        raise ValueError('parameter visual tidak lengkap') from galat
