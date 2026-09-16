"""Kontrol native PG dan cetak; seluruh opsi berasal dari snapshot publik."""
import html
import re

import brand
import visual_renderer
import design_tokens as T


def format_dari_form(data):
    from choice_store import validasi_format
    nilai = data.get('format_jawaban', ['isian'])
    if len(nilai) != 1:
        raise ValueError('Pilih satu format jawaban.')
    return validasi_format(nilai[0])


def kontrol_format(identitas, nilai='isian'):
    return (f'<div class="strip-kolom"><label for="{identitas}-format">Format jawaban</label>'
            f'<select id="{identitas}-format" name="format_jawaban" class="st-input">'
            + ''.join(f'<option value="{v}"{" selected" if v == nilai else ""}>{t}</option>'
                      for v, t in (('isian', 'Isian'), ('pilihan_ganda', 'Pilihan ganda (3–5 opsi)')))
            + '</select><small>Pilihan ganda untuk latihan manual, belum menjadi bukti penguasaan.</small></div>')


def pertanyaan(penyajian, pilihan, template_id, gaya='stitch', namespace='soal'):
    if pilihan is not None and template_id == 'benar_salah_pengandaian':
        teks = re.split(r'^A\.\s', penyajian.teks_soal, maxsplit=1, flags=re.M)[0].strip()
        return '<div class="teks">' + html.escape(teks).replace('\n', '<br>') + '</div>'
    return visual_renderer.render_pertanyaan(penyajian, gaya=gaya, namespace=namespace)


def radio_pilihan(pilihan, jawaban='', template_id=''):
    sid = pilihan.sesi_soal_id
    isi = []
    for o in pilihan.opsi:
        # Jaring sudah berlabel pada diagram, kontrol memakai label asal persis.
        teks = f'Pilihan {o.label}' if template_id == 'jaring_jaring' else f'{o.label}. {o.teks}'
        isi.append(f'<label class="pg-opsi"><input type="radio" name="opsi_{sid}" '
                   f'value="{o.id}"{" checked" if jawaban == o.nilai else ""}>'
                   f'<span>{html.escape(teks)}</span></label>')
    isi.append(f'<label class="pg-kosong"><input type="radio" name="opsi_{sid}" value=""'
               f'{" checked" if not jawaban else ""}> Belum menjawab</label>')
    return f'<fieldset class="pg-pilihan"><legend>Jawabanku — pilih satu</legend>{"".join(isi)}</fieldset>'


def select_guru(pilihan, jawaban='', identitas=None):
    sid = pilihan.sesi_soal_id
    identitas = identitas or f'jwb-{sid}'
    return (f'<select class="koreksi-input-st" id="{identitas}" name="jwb_{sid}">'
            '<option value="">Belum menjawab</option>'
            + ''.join(f'<option value="{html.escape(o.nilai, quote=True)}"'
                      f'{" selected" if o.nilai == jawaban else ""}>'
                      f'{html.escape(o.label + " — " + o.teks)}</option>' for o in pilihan.opsi)
            + '</select>')


def ringkas_opsi(pilihan, template_id=''):
    if pilihan is None:
        return ''
    if template_id == 'jaring_jaring':
        return '<p>Pilih salah satu gambar A–E.</p>'
    return '<div class="pg-daftar">' + ''.join(
        '<p>' + html.escape(o.label + '. ' + o.teks) + '</p>' for o in pilihan.opsi) + '</div>'


def gaya_pilihan():
    return f'''
.pg-pilihan {{ border: 0; padding: 0; margin: {T.SP_4} 0; min-width: 0; }}
.pg-pilihan legend {{ font-weight: 700; margin-bottom: {T.SP_2}; }}
.pg-opsi, .pg-kosong {{ display: flex; align-items: center; gap: {T.SP_3};
 scroll-margin-block: 8rem;
 min-height: {T.TARGET_SENTUH}; padding: {T.SP_3}; margin-bottom: {T.SP_2};
 border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_SEDANG}; cursor: pointer;
 background: {T.LATAR_KARTU}; overflow-wrap: anywhere; }}
.pg-opsi input, .pg-kosong input {{ flex: 0 0 auto; }}
.pg-opsi:has(input:checked) {{ border-color: {T.AKSEN_MURID_UTAMA}; font-weight: 700; }}
.pg-opsi:focus-within, .pg-kosong:focus-within {{ outline: 2px solid {T.TEKS_JUDUL}; outline-offset: 2px; }}
.pg-kosong {{ color: {T.TEKS_SUBTLE}; border-style: dashed; }}
.pg-daftar p {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
'''


def lembar_pilihan(kon, sesi_id, untuk_guru=False):
    import database
    import question_views
    from choice_store import daftar_pilihan
    from screen_style import GAYA_LAYAR
    info = kon.execute('SELECT s.tanggal,w.nama FROM sesi s JOIN siswa w ON w.id=s.siswa_id WHERE s.id=?', (sesi_id,)).fetchone()
    pilihan = daftar_pilihan(kon, sesi_id)
    kartu = []
    for b in database.isi_sesi(kon, sesi_id):
        p = pilihan[b['sesi_soal_id']]
        teks = pertanyaan(question_views.penyajian_dari_baris(b), p, b['template_id'], 'cetak', str(b['nomor']))
        opsi = ringkas_opsi(p, b['template_id'])
        kunci = ''
        if untuk_guru:
            benar = next(o for o in p.opsi if o.nilai == b['kunci'])
            kunci = '<p><b>Kunci: ' + html.escape(benar.label + ' — ' + benar.teks) + '</b></p>'
        kartu.append(f'<section class="soal"><span class="nomor">{b["nomor"]}</span>{teks}{opsi}{kunci}'
                     '<p>Jawabanku: ______</p><div class="label">Caraku (boleh dikosongkan):</div><div class="cara sedang"></div></section>')
    judul = 'Penilaian pilihan ganda — khusus orang tua' if untuk_guru else 'Latihan pilihan ganda'
    pesan = ('Pilihan benar belum membuktikan pemahaman. Tanyakan cara anak; jangan menyimpulkan diagnosis hanya dari opsi.' if untuk_guru else
             'Pilih satu jawaban tiap soal. Boleh menuliskan caramu dan boleh melewati soal yang belum bisa.')
    return (f'<!DOCTYPE html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(brand.judul(judul))}</title>{brand.tag_kepala(cetak=True)}'
            f'<style>{GAYA_LAYAR}{gaya_pilihan()}</style></head><body class="lembar-editorial"><main class="wrap">'
            f'<h1>{judul}</h1><p>{html.escape(info["nama"])} · {html.escape(info["tanggal"])}</p><p>{pesan}</p>'
            + ''.join(kartu) + '</main></body></html>').encode()
