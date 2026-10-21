"""Playbook tambahan khusus guru, tanpa I/O saat impor atau keputusan belajar.

JSON internal bukan aset publik. Validasi teknis/hash tidak membuktikan review
manusia; pengesahan di repo tetap harus dilakukan reviewer manusia atas isi exact.
"""
import hashlib
import json
from datetime import date
from html import escape
from pathlib import Path

import design_tokens as T

BERKAS = Path(__file__).resolve().parent / 'konten' / 'playbook_p3.json'
# Pengecualian pemilik 2026-10-22: draf boleh dibaca semua guru, bukan disahkan.
PERINGATAN_DRAF = 'DRAF — belum direview manusia; jangan dianggap panduan ajar final'
_REVIEW = {'status', 'reviewer', 'tanggal_review', 'versi_review', 'sha256_review'}
_ISI = {'template_id', 'profil', 'kode_intervensi', 'malrule_id', 'versi', 'saksi_seed',
        'miskonsepsi', 'batas', 'urutan', 'pertanyaan', 'pendekatan', 'tanda_paham', 'sumber'}


def sidik_isi(entri):
    """Sidik isi mengikat ulasan ke versi; bukan bukti identitas reviewer."""
    isi = {k: v for k, v in entri.items() if k not in _REVIEW}
    return hashlib.sha256(json.dumps(isi, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def _teks(nilai):
    if type(nilai) is not str or not 0 < len(nilai.strip()) <= 3000:
        return False
    try:
        nilai.encode('utf-8')
    except UnicodeError:
        return False
    return True


def _daftar(nilai, minimum=1, maksimum=8):
    return (type(nilai) is list and minimum <= len(nilai) <= maksimum
            and all(_teks(v) for v in nilai))


def _identitas(e):
    nilai = tuple(e.get(k) for k in ('template_id', 'profil', 'kode_intervensi', 'malrule_id'))
    return nilai if all(type(v) is str or v is None for v in nilai) else None


def _cocok_domain(e):
    """Saksi generator sintetis membuktikan ID/kode, bukan kebenaran pedagogis."""
    import topics
    import interventions
    from generator import buat_soal

    pemilik = topics.pemilik_template(e['template_id'])
    if pemilik is None:
        return False
    paket = topics.ambil(pemilik)
    if e['profil'] not in paket.komposisi or e['template_id'] not in paket.komposisi[e['profil']]:
        return False
    fokus = (e['template_id'], e['kode_intervensi'], e['malrule_id'])
    if e['malrule_id'] is not None:
        soal = buat_soal(e['template_id'], e['saksi_seed'], e['profil'], pemilik)
        if not any((m.id, m.kode) == (e['malrule_id'], e['kode_intervensi']) for m in soal.malrule):
            return False
    tersedia = {m.pendekatan_id for m in interventions.pilihan_untuk_fokus(fokus) if m.tersedia}
    return all(p['pendekatan_id'] in tersedia for p in e['pendekatan'])


def validasi_entri(e):
    """Validasi offline juga menerima draf; kosong berarti struktur/domain cocok."""
    if type(e) is not dict or set(e) != _ISI | _REVIEW:
        return ('Field entri tidak sesuai format.',)
    if (not all(_teks(e[k]) for k in ('template_id', 'profil', 'miskonsepsi', 'batas'))
            or e['kode_intervensi'] not in ('B', 'K', 'H', 'E', 'N', 'T')
            or not (e['malrule_id'] is None or _teks(e['malrule_id']))
            or type(e['versi']) is not int or e['versi'] < 1
            or type(e['saksi_seed']) is not int or not 0 <= e['saksi_seed'] <= 9999):
        return ('Identitas atau versi tidak sah.',)
    if (type(e['urutan']) is not dict or set(e['urutan']) != {'benda', 'gambar', 'simbol'}
            or not all(_teks(v) for v in e['urutan'].values())
            or not _daftar(e['pertanyaan'], 2, 3)
            or not _daftar(e['tanda_paham']) or not _daftar(e['sumber'])):
        return ('Isi ajar belum lengkap.',)
    p = e['pendekatan']
    if (type(p) is not list or not 1 <= len(p) <= 3
            or any(type(v) is not dict or set(v) != {'pendekatan_id', 'contoh'}
                   or not all(_teks(t) for t in v.values()) for v in p)):
        return ('Pendekatan belum lengkap.',)
    if (len({v['pendekatan_id'] for v in p}) != len(p)
            or len({v['contoh'].strip() for v in p}) != len(p)):
        return ('ID dan contoh pendekatan harus berbeda.',)
    if e['status'] not in ('draf', 'disahkan'):
        return ('Status tidak dikenal.',)
    try:
        if not _cocok_domain(e):
            return ('Identitas tidak cocok dengan domain existing.',)
    except (ValueError, KeyError, TypeError, RuntimeError):
        return ('Identitas tidak dapat diverifikasi.',)
    return ()


def _review_sah(e):
    if e['status'] != 'disahkan':
        return False
    if (not _teks(e['reviewer']) or type(e['versi_review']) is not int
            or e['versi_review'] != e['versi'] or e['sha256_review'] != sidik_isi(e)):
        return False
    try:
        return date.fromisoformat(e['tanggal_review']).isoformat() == e['tanggal_review']
    except (ValueError, TypeError):
        return False


def _boleh_tampil(e):
    """Draf harus jujur tanpa pengesahan; isi disahkan tetap perlu ulasan sah."""
    if e['status'] == 'draf':
        return all(e[k] is None for k in _REVIEW - {'status'})
    return _review_sah(e)


def _tanpa_kunci_ganda(pasangan):
    hasil = {}
    for k, v in pasangan:
        if k in hasil:
            raise ValueError('Kunci JSON ganda')
        hasil[k] = v
    return hasil


def _baca():
    """Baca path tetap per permintaan; tidak cache konten yang dicabut/berubah."""
    try:
        with BERKAS.open(encoding='utf-8') as f:
            mentah = f.read(512 * 1024 + 1)
        if len(mentah) > 512 * 1024:
            return ()
        data = json.loads(mentah, object_pairs_hook=_tanpa_kunci_ganda)
        if (type(data) is not dict or set(data) != {'versi_format', 'entri'}
                or type(data['versi_format']) is not int or data['versi_format'] != 1
                or type(data['entri']) is not list or len(data['entri']) > 500):
            return ()
        return data['entri']
    except (OSError, ValueError, UnicodeError, RecursionError):
        return ()


def render(fokus, profil, *, peran, pendekatan_id=None):
    """Guru boleh membaca draf berlabel; invalid/ambigu/review rusak tetap kosong."""
    if peran != 'guru':
        return ''
    if not isinstance(fokus, tuple) or len(fokus) != 3:
        return ''
    identitas = (fokus[0], profil, fokus[1], fokus[2])
    entri = [e for e in _baca() if type(e) is dict]
    cocok = [e for e in entri if _identitas(e) == identitas]
    if len(cocok) != 1:
        return ''
    e = cocok[0]
    if validasi_entri(e) or not _boleh_tampil(e):
        return ''
    pilihan = [p for p in e['pendekatan'] if pendekatan_id is None or p['pendekatan_id'] == pendekatan_id]
    if not pilihan:
        return ''
    def daftar(nilai):
        return '<ul>' + ''.join('<li>' + escape(v) + '</li>' for v in nilai) + '</ul>'
    langkah = ''.join('<li><b>' + judul + ':</b> ' + escape(e['urutan'][k]) + '</li>'
                      for k, judul in (('benda', 'Benda'), ('gambar', 'Gambar'), ('simbol', 'Simbol')))
    contoh = ''.join('<p><b>Contoh ' + str(i) + ':</b> ' + escape(p['contoh']) + '</p>'
                     for i, p in enumerate(pilihan, 1))
    draf = e['status'] == 'draf'
    peringatan = ('<span class="playbook-peringatan">' + PERINGATAN_DRAF + '</span>') if draf else ''
    metadata = ('Draf versi ' + str(e['versi']) + ' · Belum ada pengesahan manusia.' if draf else
                'Versi ' + str(e['versi']) + ' · Ulasan: ' + escape(e['reviewer'])
                + ' · ' + escape(e['tanggal_review']))
    return ('<details class="playbook-guru" data-playbook-guru'
            + (' data-playbook-draf' if draf else '') + '><summary>Panduan mengajar'
            + peringatan + '</summary>'
            '<div class="playbook-isi"><p><b>Miskonsepsi yang perlu diperiksa:</b> ' + escape(e['miskonsepsi'])
            + '</p><p>' + escape(e['batas']) + '</p><ol>' + langkah + '</ol>'
            '<b>Pertanyaan pancingan</b>' + daftar(e['pertanyaan']) + contoh
            + '<b>Tanda pemahaman — bukan kelulusan otomatis</b>' + daftar(e['tanda_paham'])
            + '<p>Hasil setelah dibantu bukan jawaban mandiri. Status belajar tetap dari siklus.</p>'
            '<p class="playbook-meta">' + metadata + '</p></div></details>')


GAYA = f'''
.playbook-guru {{ margin-block: {T.SP_3}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU}; color: {T.TEKS_UTAMA};
  min-width: 0; overflow-wrap: anywhere; }}
.playbook-guru > summary {{ padding: {T.SP_3} {T.SP_4}; cursor: pointer;
  min-height: {T.TARGET_SENTUH}; box-sizing: border-box; font-weight: 600; }}
.playbook-guru > summary:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; }}
.playbook-isi {{ padding: 0 {T.SP_4} {T.SP_3}; line-height: 1.6; }}
.playbook-meta {{ color: {T.TEKS_SUBTLE}; }}
.playbook-peringatan {{ display: block; margin-top: {T.SP_2}; color: {T.TEKS_REVIEW};
  line-height: 1.5; }}
'''
