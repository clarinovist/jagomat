"""Draf koreksi katalog lanjutan; writer default nonaktif, reader beridentitas2."""
from dataclasses import replace
from fractions import Fraction as F
import os

from catalog_exact import baca_angka, format_angka
from templates import Malrule

TEMPLATE = frozenset({
    'satuan_kuantitas', 'rata_rata', 'luas_arsiran',
    'operasi_berkurung', 'volume_prisma_tabung',
})


def didukung(template_id, parameter):
    """Whitelist cabang; fallback else legacy bukan cabang sah revisi baru."""
    if template_id == 'satuan_kuantitas':
        return (parameter.get('arah') in ('ke_satuan', 'ke_kuantitas')
                and parameter.get('satuan') in ('lusin', 'kodi', 'gros', 'rim'))
    if template_id == 'rata_rata':
        return parameter.get('varian') in ('cari_rata', 'cari_data_ke_n')
    if template_id == 'luas_arsiran':
        return parameter.get('varian') in ('persegi_titik_tengah', 'jalan_pinggir')
    if template_id == 'operasi_berkurung':
        kunci_wajib = ('a', 'b', 'c', 'd', 'e')
        return (all(k in parameter and type(parameter[k]) is int for k in kunci_wajib)
                and parameter['e'] > 0)
    if template_id == 'volume_prisma_tabung':
        varian = parameter.get('varian')
        if varian in ('prisma_V', 'prisma_balik'):
            return all(type(parameter.get(k)) is int and parameter[k] > 0
                       for k in ('a', 't_segitiga'))
        if varian in ('tabung_V', 'tabung_balik'):
            return type(parameter.get('r')) is int and parameter['r'] > 0
    return False


def aktif():
    """Aktivasi bukan pengesahan isi; default tetap0 sampai review/pair exact."""
    nilai = os.environ.get('OSN_KATALOG_LANJUTAN', '0').strip()
    if nilai not in ('0', '1'):
        raise ValueError('OSN_KATALOG_LANJUTAN hanya menerima 0 atau 1')
    return nilai == '1'


def parameter_visual(template_id, parameter):
    """Marker internal dibuang hanya setelah identitas dan tipe tervalidasi."""
    if 'revisi_penilaian' not in parameter:
        return parameter
    if (type(parameter['revisi_penilaian']) is not int
            or parameter['revisi_penilaian'] != 2
            or not didukung(template_id, parameter)):
        raise ValueError('revisi penilaian visual tidak didukung')
    return {k: v for k, v in parameter.items() if k != 'revisi_penilaian'}


def _rule(ident, nilai, kode, alasan):
    return Malrule('rev2.' + ident, format_angka(nilai), kode, alasan)


def _kuantitas(p, kunci):
    faktor = {'lusin': 20, 'kodi': 12, 'gros': 12, 'rim': 100}[p['satuan']]
    salah = (p['nilai'] * faktor if p['arah'] == 'ke_satuan'
             else F(p['nilai'], faktor))
    operasi = 'mengalikan' if p['arah'] == 'ke_satuan' else 'membagi'
    return (
        _rule('kuantitas.faktor_tertukar_' + p['satuan'], salah, 'K',
              f'{operasi} angka masukan dengan {faktor}, memakai faktor konversi yang salah'),
        _rule('kuantitas.belum_dikonversi_' + p['satuan'], p['nilai'], 'K',
              'menyalin angka masukan tanpa mengubah satuan'),
        _rule('kuantitas.kurang_satu', kunci - 1, 'H', 'hasil hitung meleset satu'),
    )


def _rata(p, kunci):
    data = p['data']
    if p['varian'] == 'cari_rata':
        kandidat = (
            _rule('rata.jumlah_saja', sum(data), 'K', 'menjumlahkan seluruh data tanpa membagi'),
            _rule('rata.bagi_n_tambah_satu', F(sum(data), len(data) + 1), 'K',
                  'membagi jumlah dengan banyak data ditambah satu'),
        )
    else:
        kandidat = (
            _rule('rata.total_saja', p['rata'] * len(data), 'K',
                  'menjawab total seluruh data, bukan data terakhir'),
            _rule('rata.abaikan_data_diketahui_terakhir',
                  p['rata'] * len(data) - sum(data[:-2]), 'K',
                  'mengurangi total tanpa menyertakan data diketahui yang terakhir'),
        )
    return kandidat + (_rule('rata.kurang_satu', kunci - 1, 'H', 'hasil hitung meleset satu'),)


def _arsiran(p, kunci):
    if p['varian'] == 'persegi_titik_tengah':
        r = p['r']
        kandidat = (
            _rule('arsiran.pakai_diameter', (2*r)**2 - F(22, 7)*(2*r)**2, 'K',
                  'memakai diameter sebagai jari-jari pada bagian lingkaran yang dikurangi'),
            _rule('arsiran.pakai_pi_314', (2*r)**2 - F(314, 100)*r*r, 'H',
                  'memakai π=3,14 padahal soal menetapkan π=22/7; tanpa pembulatan tambahan'),
        )
    else:
        luar, dalam = p['luar'], p['dalam']
        lebar = F(luar - dalam, 2)
        kandidat = (
            _rule('arsiran.lebar_hanya_sekali', luar*luar - (dalam + lebar)**2, 'K',
                  'lebar jalan hanya dikurangi sekali dari sisi luar, bukan dua kali'),
            _rule('arsiran.jawab_selisih_sisi', luar - dalam, 'B',
                  'menjawab selisih sisi luar dan dalam, bukan luas jalan'),
        )
    return kandidat + (_rule('arsiran.kurang_satu', kunci - 1, 'H', 'hasil hitung meleset satu'),)


def _operasi_berkurung(p, kunci):
    a, b, c, d, e = p['a'], p['b'], p['c'], p['d'], p['e']
    abaikan_kurung = F(a + b * c) - F(d, e)
    bagi_seluruh = F((a + b) * c - d, e)
    return (
        _rule('berkurung.abaikan_kurung', abaikan_kurung, 'K',
              'mengerjakan perkalian lebih dulu sebelum tanda kurung'),
        _rule('berkurung.bagi_seluruh', bagi_seluruh, 'K',
              f'membagi seluruh hasil sebelumnya dengan {e}, padahal {e} hanya membagi {d}'),
        _rule('berkurung.kurang_satu', kunci - 1, 'H', 'urutannya benar, hasil akhirnya meleset satu'),
    )


def _baca_nilai(nilai):
    if type(nilai) is int:
        return F(nilai)
    if isinstance(nilai, str):
        return baca_angka(nilai)
    return None


def _volume_prisma_tabung(p, kunci):
    varian = p['varian']
    if varian == 'prisma_V':
        a, ts, tp = p['a'], p['t_segitiga'], p['t_prisma']
        kandidat = (
            _rule('volprisma.lupa_setengah_segitiga', a * ts * tp, 'K',
                  'lupa membagi dua untuk luas alas segitiga pada prisma'),
            _rule('volprisma.rumus_lain_segitiga', a * tp, 'K',
                  'hanya mengalikan alas segitiga dengan tinggi prisma'),
        )
    elif varian == 'prisma_balik':
        V_val = _baca_nilai(p['V'])
        if V_val is None:
            raise ValueError('volume prisma balik wajib rasional sah')
        a, ts = p['a'], p['t_segitiga']
        kandidat = (
            _rule('volprisma.lupa_setengah_segitiga', V_val / (a * ts), 'K',
                  'lupa faktor setengah luas alas segitiga saat mencari tinggi prisma'),
            _rule('volprisma.rumus_lain_segitiga', V_val / (a + ts), 'K',
                  'menjumlahkan alas dan tinggi segitiga sebagai luas alas prisma'),
        )
    elif varian == 'tabung_V':
        r, t = p['r'], p['t']
        pi = F(22, 7) if r % 7 == 0 else F(314, 100)
        kandidat = (
            _rule('volprisma.keliling_bukan_luas_tabung', 2 * pi * r * t, 'K',
                  'keliru memakai keliling lingkaran (2πr), bukan luas alas lingkaran (πr²)'),
            _rule('volprisma.lupa_tinggi_tabung', pi * r * r, 'K',
                  'menghitung luas alas lingkaran tanpa mengalikan tinggi tabung'),
        )
    else:  # tabung_balik
        r = p['r']
        pi = F(22, 7) if r % 7 == 0 else F(314, 100)
        V_val = _baca_nilai(p['V'])
        if V_val is None:
            raise ValueError('volume tabung balik wajib rasional sah')
        kandidat = (
            _rule('volprisma.keliling_bukan_luas_tabung', V_val / (2 * pi * r), 'K',
                  'keliru membagi volume tabung dengan 2πr, bukan luas alas πr²'),
            _rule('volprisma.rumus_lain_tabung', V_val / r, 'K',
                  'hanya membagi volume tabung dengan jari-jari, bukan luas alas πr²'),
        )
    return kandidat + (_rule('volprisma.kurang_satu', kunci - 1, 'H', 'hasil hitung meleset satu'),)


def perbaiki(soal):
    """Kunci tetap; teks arsiran diperjelas, malrule literal tanpa nudge."""
    from assessment_revision import saring_eksak
    if not didukung(soal.template_id, soal.parameter):
        raise ValueError('cabang tidak mendukung revisi penilaian2')
    kunci = baca_angka(soal.kunci)
    if kunci is None:
        raise ValueError('kunci revisi penilaian2 wajib rasional sah')
    fungsi = {
        'satuan_kuantitas': _kuantitas,
        'rata_rata': _rata,
        'luas_arsiran': _arsiran,
        'operasi_berkurung': _operasi_berkurung,
        'volume_prisma_tabung': _volume_prisma_tabung,
    }
    kandidat = fungsi[soal.template_id](soal.parameter, kunci)
    teks = soal.teks
    if soal.template_id == 'luas_arsiran' and soal.parameter['varian'] == 'persegi_titik_tengah':
        r = soal.parameter['r']
        teks = (f'Persegi bersisi {2*r} cm memuat empat seperempat lingkaran '
                f'berjari-jari {r} cm, masing-masing berpusat di satu pojok persegi '
                f'(π = 22/7). Daerah di dalam persegi tetapi di luar keempat '
                f'seperempat lingkaran diarsir. Berapa luas daerah yang diarsir (cm²)?')
    return replace(soal, parameter={**soal.parameter, 'revisi_penilaian': 2}, teks=teks,
                   malrule=saring_eksak(soal.kunci, kandidat))
