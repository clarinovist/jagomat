"""Satu form latihan orang tua; mode native tetap bekerja tanpa JavaScript."""
import html

from topics import TOPIK_BAWAAN, ambil, daftar_topik
from template_labels import nama_tipe_soal
from question_context import profil_otomatis, topik_dasar
from question_variants_ui import pemilih_dasar

MODES = (('manual','Pilih satu topik','Cocok untuk melatih topik tertentu.'),
         ('remedial','Dari hasil terbaru','Bagian yang masih perlu dibantu.'),
         ('gabungan','Gabungan topik','Campur beberapa topik sekaligus.'))


def _e(nilai):
    return html.escape(str(nilai), quote=True)


def render(kon, siswa, *, mode='manual', draf_latihan=None, draf_gabungan=None,
           draf_remedial=None, bantuan='', kontrol_mode=None):
    import database
    from choice_pages import kontrol_format
    sid = int(siswa['id'])
    aktif = 'gabungan' if draf_gabungan else 'remedial' if draf_remedial else 'manual' if draf_latihan else mode
    if aktif not in {m[0] for m in MODES}:
        aktif = 'manual'
    urls = {'manual':f'/sesi-baru/{sid}', 'gabungan':f'/sesi-gabungan/{sid}', 'remedial':f'/sesi-remedial/{sid}'}
    selector = (f'<form class="latihan-pemilih-st" method="get" action="/anak/{sid}">'
                '<input type="hidden" name="section" value="latihan">'
                '<fieldset><legend>Latihan tentang apa?</legend><div class="latihan-mode-st">'
                + ''.join(f'<label><input type="radio" name="mode_latihan" id="mode-{kode}" value="{kode}"'
                          + (' checked' if kode == aktif else '') + f'><span><b>{nama}</b><small>{desk}</small></span></label>'
                          for kode,nama,desk in MODES)
                + '</div></fieldset><noscript><button class="st-tombol-sekunder" type="submit">Tampilkan mode</button></noscript></form>')
    terakhir = kon.execute('SELECT topik,level FROM sesi WHERE siswa_id=? ORDER BY tanggal DESC,id DESC LIMIT 1', (sid,)).fetchone()
    topik = draf_latihan.topik if draf_latihan else terakhir['topik'] if terakhir and terakhir['topik'] in daftar_topik() else TOPIK_BAWAAN
    dasar_ids = [k for k in daftar_topik() if topik_dasar(k)]
    options = ''.join(f'<option value="{_e(k)}"' + (' selected' if k == topik else '')
                      + (' data-topik-dasar' if k in dasar_ids else '')
                      + f'>{_e("Campuran semua topik" if k == "campuran" else ambil(k).nama)}</option>' for k in daftar_topik())
    variasi = ''
    if dasar_ids:
        dasar = topik if topik in dasar_ids else dasar_ids[0]
        pilihan = profil_otomatis([dasar], siswa['tingkat'])
        if terakhir and terakhir['topik'] == dasar and terakhir['level'] in ambil(dasar).komposisi:
            pilihan = terakhir['level']
        if draf_latihan and draf_latihan.topik == dasar:
            pilihan_draf = (getattr(draf_latihan, 'variasi_dasar', '')
                            or getattr(draf_latihan, 'profil_parameter', ''))
            if pilihan_draf in ambil(dasar).komposisi:
                pilihan = pilihan_draf
        variasi = pemilih_dasar(dasar, pilihan)

    def jumlah(jenis, draf, bawaan, batas):
        nilai = draf.jumlah_soal if draf else bawaan
        opsi = ([('', 'Sesuai topik (disarankan)')] if jenis == 'manual' else []) + [(str(n), f'{n} soal') for n in batas]
        return (f'<label for="{jenis}-jumlah">Jumlah soal</label><select class="st-input" id="{jenis}-jumlah" name="jumlah_soal" aria-describedby="{jenis}-jumlah-petunjuk">'
                + ''.join(f'<option value="{k}"' + (' selected' if k == nilai else '') + f'>{v}</option>' for k,v in opsi)
                + f'</select><small id="{jenis}-jumlah-petunjuk">Sekitar 3 menit per soal.</small>')
    manual = ('<div class="latihan-field-grid"><div><label for="manual-topik">Topik</label>'
              f'<select class="st-input" id="manual-topik" name="topik">{options}</select></div><div>'
              + jumlah('manual',draf_latihan,'',(10,15,20,25,30)) + '</div></div>'
              + variasi + '<details class="atur-latihan-st profil-lanjutan-st"><summary>Pengaturan lanjutan</summary>'
              '<small>Jagomat memilih cakupan yang sesuai untuk topik ini.</small>'
              + kontrol_format('manual', getattr(draf_latihan,'format_jawaban','isian')) + kontrol_mode(draf_latihan) + '</details>')
    dipilih = set(draf_gabungan.topik) if draf_gabungan else set()
    gabungan = ('<p>Pilih dua topik atau lebih. Soal akan dicampur bergantian.</p><div class="latihan-topik-grid">'
                + ''.join(f'<label><input type="checkbox" data-pilih name="topik" value="{_e(k)}"'
                          + (' checked' if k in dipilih else '') + f'> {_e(ambil(k).nama)}</label>'
                          for k in daftar_topik() if k != 'campuran' and not topik_dasar(k)) + '</div>'
                + jumlah('gabungan',draf_gabungan,'10',(10,15,20))
                + '<details class="atur-latihan-st profil-lanjutan-st"><summary>Pengaturan lanjutan</summary>'
                + '<small>Jagomat memilih satu cakupan yang tersedia pada semua topik pilihan.</small>'
                + kontrol_format('gabungan',getattr(draf_gabungan,'format_jawaban','isian'))
                + '<label>Mode sesi<select class="st-input" name="mode">'
                + ''.join(f'<option value="{k}"' + (' selected' if k == getattr(draf_gabungan,'mode','drill') else '') + f'>{v}</option>'
                          for k,v in (('drill','Latihan Cepat'),('diagnostik','Mode Diagnosa')))
                + '</select></label></details>')
    sasaran = (database.sasaran_remedial_sesi(kon, sid, int(draf_remedial.sumber_sesi_id))
               if draf_remedial and draf_remedial.sumber_sesi_id else database.sasaran_remedial_anak(kon, sid))
    saran = [str(s['template_id']) for s in sasaran if s['direkomendasikan']]
    dicentang = set(draf_remedial.template_id) if draf_remedial else set(saran[:3])
    remedial = ('<p>Yang sudah dicentang adalah saran dari hasil terbaru. Anda bisa mengubahnya. Pilih maksimal 3 tipe soal.</p>'
                '<div class="daftar-remedial-st">'
                + ''.join('<label class="pilihan-remedial-st"><input type="checkbox" data-pilih name="template_id" '
                          f'value="{_e(s["template_id"])}"' + (' checked' if s['template_id'] in dicentang else '')
                          + f'><span><b>{_e(nama_tipe_soal(s["template_id"]))}</b><small>Perlu diperhatikan · {int(s["kali_salah"])} kali</small></span></label>'
                          for s in sasaran) + '</div>'
                + ('<p>Belum ada bagian yang disarankan dari hasil terbaru. Pilih satu topik untuk latihan tambahan.</p>' if not sasaran else '')
                + jumlah('remedial',draf_remedial,'10',(10,15,20)))
    if draf_remedial and draf_remedial.sumber_sesi_id:
        remedial += f'<input type="hidden" name="sumber_sesi_id" value="{int(draf_remedial.sumber_sesi_id)}">'
    panels = {'manual':manual,'gabungan':gabungan,'remedial':remedial}
    isi = ''.join(f'<fieldset data-mode-latihan="{k}" data-url="{urls[k]}" data-form-id="form-latihan-{k}-{sid}"'
                  + (' disabled hidden' if k != aktif else '') + f'><legend>{nama}</legend>{panels[k]}</fieldset>'
                  for k,nama,_ in MODES)
    form = (f'<form id="form-latihan-{aktif}-{sid}" data-latihan-terpadu method="post" action="{urls[aktif]}">'
            f'<input type="hidden" name="inline_form" value="{aktif}">' + isi
            + '<div class="latihan-aksi-st"><button type="submit" data-buat-latihan class="st-tombol-coral">Buat latihan</button>'
            '<p>Latihan tambahan tercatat di Riwayat, tapi tidak mengubah tugas di Beranda.</p></div>'
            '<div class="profil-assistant-st">' + bantuan + '</div></form>')
    import skill_pilot_ui
    starter = skill_pilot_ui.starter(kon,sid)
    if starter:
        starter = '<section class="eksplorasi-opsional-st"><h2 class="st">Eksplorasi opsional</h2>' + starter + '</section>'
    return '<section class="latihan-terpadu-st"><h2 class="st">Buat latihan baru</h2>' + selector + form + starter + '</section>', aktif
