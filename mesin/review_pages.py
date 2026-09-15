"""Komponen tinjauan guru: sumber asli, catatan anak, dan hasil bantuan terpisah."""
from html import escape

import review_store
from student_submissions import ALASAN

PERTANYAAN = {
    'maksud_soal': 'Menurutmu, soal ini meminta kita mencari apa?',
    'langkah_awal': 'Ada langkah pertama yang terpikir? Ceritakan saja, belum harus selesai.',
    'belum_sempat': 'Tadi belum sempat mengerjakan? Kita boleh mencatatnya untuk ditinjau nanti.',
    'belum_bisa_menjelaskan': 'Tidak apa-apa kalau belum bisa bercerita. Kita bisa lanjut nanti.',
}


def nilai(tinjauan, draf, nama, bawaan=''):
    v = getattr(draf, nama, None) if draf else None
    if v is not None:
        return v
    return tinjauan.get('catatan' if nama == 'catatan_tinjauan' else nama, bawaan)


def sumber_html(awal, b, foto=False):
    kosong = not (awal['jawaban'] if awal else b['jawaban'] or '').strip()
    judul = 'Jawaban saat dikirim' if awal else 'Jawaban tersimpan; rekaman saat pengiriman belum tersedia'
    isi = awal['jawaban'] if awal else b['jawaban'] or ''
    cara = awal['cara'] if awal else b['cara'] or ''
    restatement = awal['restatement'] if awal else b['restatement'] or ''
    alasan = awal['alasan'] if awal else ''
    pengalaman = awal['belum_pernah'] if awal else b['belum_pernah']
    if cara.startswith('[pilihan] bingung'):
        cara = 'Aku bingung' + cara[len('[pilihan] bingung'):]
    tambahan = ''
    label_catatan = 'Catatan dari anak' if awal else 'Catatan tersimpan (sumber awal belum tersedia)'
    if cara:
        tambahan += f'<p><b>{label_catatan}:</b> {escape(cara)}</p>'
    if restatement:
        tambahan += f'<p><b>{"Pemahaman soal saat dikirim" if awal else "Pemahaman soal tersimpan"}:</b> {escape(restatement)}</p>'
    if alasan:
        tambahan += f'<p><b>Dari anak:</b> {escape(ALASAN.get(alasan, alasan))}</p>'
    elif kosong:
        tambahan += ('<p>Anak sudah mencatat bingung; bagian yang membingungkan belum diperjelas.</p>'
                     if cara.startswith('Aku bingung') else
                     '<p>Anak belum mencatat alasannya. Penyebabnya belum diketahui.</p>')
    if pengalaman:
        label_pengalaman = 'Pengalaman yang dicatat anak' if awal else 'Catatan pengalaman tersimpan (sumber awal belum tersedia)'
        tambahan += f'<p><b>{label_pengalaman}:</b> belum pernah melihat soal seperti ini. Guru perlu memastikan kebutuhan pengenalan.</p>'
    if kosong and foto:
        tambahan += '<p>Isian digital kosong; jawaban mungkin ada pada foto yang perlu ditinjau.</p>'
    status = 'Jawaban akhir belum diisi' if cara or restatement or foto else 'Belum ada jawaban — perlu ditinjau bersama'
    return (f'<section class="pembahasan-soal-st"><b>{judul}</b><p>{escape(isi) if isi else status}</p>{tambahan}</section>',
            PERTANYAAN.get(alasan, 'Tadi waktu mengerjakan soal ini, apa yang membuatmu belum menjawab?') if kosong else 'Kamu dapat jawaban ini dari mana?', kosong)


def kontrol(kon, sid, tinjauan, draf):
    catatan = nilai(tinjauan, draf, 'catatan_tinjauan')
    provenance = nilai(tinjauan, draf, 'provenance')
    bantuan = nilai(tinjauan, draf, 'jawaban_bantuan')
    versi = nilai({}, draf, 'versi_tinjauan', review_store.tanda(kon, sid))
    opsi = ''.join(f'<option value="{v}"{" selected" if v == provenance else ""}>{label}</option>' for v, label in (
        ('', 'Belum dicatat'), ('penjelasan_asli', 'Penjelasan pekerjaan asli, tanpa bantuan'),
        ('koreksi_transkripsi', 'Koreksi salinan pekerjaan asli'), ('setelah_bantuan', 'Hasil setelah diberi petunjuk atau contoh'),
    ))
    buka = bool(catatan or provenance or bantuan)
    return f'''<details class="koreksi-opsi-st koreksi-tinjauan-st"{' open' if buka else ''}><summary>Catatan tinjauan guru (opsional)</summary>
<fieldset class="koreksi-pemahaman-st"><legend>Catatan tinjauan guru</legend>
<label class="koreksi-label-st" for="tinjauan-{sid}">Catatan percakapan (boleh dilanjutkan nanti)</label>
<textarea class="koreksi-textarea-st" name="catatan_tinjauan_{sid}" id="tinjauan-{sid}" maxlength="8000">{escape(catatan)}</textarea>
<details class="koreksi-opsi-st"{' open' if provenance or bantuan else ''}><summary>Catat sumber koreksi atau hasil setelah dibantu</summary>
<label class="koreksi-label-st" for="provenance-{sid}">Sumber penjelasan atau koreksi</label>
<select class="koreksi-select-st" name="provenance_{sid}" id="provenance-{sid}">{opsi}</select>
<label class="koreksi-label-st" for="bantuan-{sid}">Jawaban setelah dibantu (jika ada, bukan jawaban mandiri)</label>
<input class="koreksi-input-st" name="jawaban_bantuan_{sid}" id="bantuan-{sid}" value="{escape(bantuan, quote=True)}" maxlength="8000">
</details><input type="hidden" name="versi_tinjauan_{sid}" value="{escape(versi, quote=True)}">
<p class="koreksi-catatan-st">Jangan menimpa jawaban awal dengan hasil bantuan. Bukti mandiri baru memerlukan soal berikutnya.</p>
</fieldset></details>'''
