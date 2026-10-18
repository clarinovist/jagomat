"""Kategori sensor tetap: proksi interaksi, bukan keputusan pedagogis."""
import re
import unicodedata

CONSENT = 'sensor-keluarga-v1'
HARI = 86400
RETENSI_DETAIL = 30 * HARI
RETENSI_CONSENT = 90 * HARI
EVENT = frozenset(('disiapkan', 'pekerjaan_disimpan', 'dikirim',
                   'tinjauan_disimpan', 'dikonfirmasi', 'dibatalkan',
                   'lanjutan_disiapkan', 'lembar_disajikan'))
KATEGORI_CHAT = frozenset(('penjelasan', 'latihan', 'hasil', 'penggunaan', 'belum_diketahui'))


def kategori_chat(teks):
    """Aturan kata terbatas pada pesan baru; ambiguitas tidak dipaksa kategorinya."""
    if type(teks) is not str or len(teks) > 20000:
        return 'belum_diketahui'
    kata = set(re.findall(r'[a-z]+', unicodedata.normalize('NFKC', teks).lower()))
    aturan = {
        'penjelasan': {'jelaskan', 'penjelasan', 'konsep', 'mengapa'},
        'latihan': {'latihan', 'soal'},
        'hasil': {'hasil', 'perkembangan', 'nilai'},
        'penggunaan': {'login', 'tombol', 'menu', 'aplikasi', 'error'},
    }
    cocok = [kategori for kategori, pemicu in aturan.items() if kata & pemicu]
    return cocok[0] if len(cocok) == 1 else 'belum_diketahui'


def ringkas_hasil(outcomes):
    """Hitungan dari snapshot konfirmasi pertama; bukan penguasaan terkini."""
    rows = tuple(outcomes)
    if not 1 <= len(rows) <= 100:
        raise ValueError('jumlah outcome sensor tidak sah')
    hasil = {'jumlah': len(rows), 'benar': 0, 'belum_jelas': 0,
             **{'kode_' + k.lower(): 0 for k in 'BKHENT'}}
    for row in rows:
        if row['dilewati']:
            hasil['belum_jelas'] += 1
        elif row['benar']:
            hasil['benar'] += 1
        elif row['kode_final'] in ('B', 'K', 'H', 'E', 'N', 'T'):
            hasil['kode_' + row['kode_final'].lower()] += 1
        else:
            hasil['belum_jelas'] += 1
    return hasil
