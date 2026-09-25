"""Presentasi tab profil dan tabel riwayat; tidak menentukan rekomendasi belajar."""
import html
import design_tokens as T
import profile_history as H
from topics import daftar_topik, ambil


def ikon(nama):
    """Ikon profil lokal tetap terbaca ketika font eksternal tidak tersedia."""
    garis = {
        'share': '<circle cx="6" cy="12" r="2"/><circle cx="18" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="m8 11 8-5M8 13l8 5"/>',
        'link_off': '<path d="m3 3 18 18M9 15l6-6M8 17l-1 1a4 4 0 0 1-6-6l4-4M16 7l1-1a4 4 0 0 1 6 6l-4 4"/>',
        'play_arrow': '<path d="m8 5 11 7-11 7Z"/>',
        'add_circle': '<circle cx="12" cy="12" r="9"/><path d="M7 12h10M12 7v10"/>',
        'restart_alt': '<path d="M4 10a8 8 0 1 1 1 8M4 3v7h7"/>',
        'library_add': '<rect x="6" y="3" width="15" height="15" rx="2"/><path d="M3 7v14h14M10 10h7M13.5 6.5v7"/>',
    }
    return '<svg class="profil-ikon-st" aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">' + garis[nama] + '</svg>'


def _e(nilai):
    return html.escape(str(nilai), quote=True)


def bingkai(siswa, section, total, isi, *, peran='guru', pesan='', kelas_sekolah=None):
    sid = int(siswa['id'])
    from learning_profile import label_kelas_sekolah
    nav = ''.join('<a href="/anak/%d?section=%s"%s>%s</a>' %
                  (sid, k, ' aria-current="page"' if k==section else '', label)
                  for k,label in [('latihan','Buat latihan'),('rencana','Rencana belajar'),('riwayat','Riwayat <span>%d</span>' % total)])
    keluarga = '<span class="st-badge selesai">keluarga: %s</span>' % _e(siswa['pemilik'] or 'warisan') if peran=='admin' else ''
    kabar = '<div class="st-banner-sukses" role="status">%s</div>' % _e(pesan) if pesan else ''
    return ('<main aria-labelledby="judul-profil"><div class="jejak"><a href="%s">&larr; Semua anak</a></div>'
            '<header class="kepala-anak-st editorial-kepala-st"><p class="editorial-alis-st">RUANG BELAJAR ANAK</p>'
            '<h1 class="st" id="judul-profil">%s <span class="st-badge selesai">(%s)</span>%s</h1>'
            '<p class="sub"><a href="%s">Kelola kelas sekolah</a></p></header>'
            '<nav class="profil-tabs-st" aria-label="Bagian profil anak">%s</nav>%s%s</main>') % (
                '/admin' if peran=='admin' else '/guru', _e(siswa['nama']),
                _e(label_kelas_sekolah(kelas_sekolah)), keluarga,
                '/admin?section=siswa&amp;id=%d' % sid if peran == 'admin' else '/akun?section=siswa',
                nav, kabar, isi)


def _opsi(opsi, terpilih):
    return ''.join('<option value="%s"%s>%s</option>' % (_e(k),' selected' if k==terpilih else '',_e(v)) for k,v in opsi)


def _pager(sid, filter_data, total):
    """Satu navigasi: nomor desktop, posisi ringkas mobile, tautan tetap sama."""
    jumlah = (total + H.PER_HALAMAN - 1) // H.PER_HALAMAN
    if jumlah <= 1:
        return ''
    kini = filter_data.halaman
    nomor = sorted({1, jumlah} | set(range(max(1, kini-1), min(jumlah, kini+2)+1)))
    bagian = [
        '<a class="profil-prev-st" href="%s">← Sebelumnya</a>' % _e(filter_data.tautan(sid, kini-1))
        if kini > 1 else '<span class="profil-prev-st" aria-disabled="true">← Sebelumnya</span>'
    ]
    lalu = 0
    for n in nomor:
        if lalu and n > lalu + 1:
            bagian.append('<span class="profil-page-number-st">…</span>')
        bagian.append(
            '<span class="profil-page-number-st" aria-current="page">%d</span>' % n if n == kini
            else '<a class="profil-page-number-st" href="%s">%d</a>' % (_e(filter_data.tautan(sid, n)), n))
        lalu = n
    bagian.append('<span class="profil-page-status-st" aria-current="page">Halaman %d/%d</span>' % (kini, jumlah))
    bagian.append(
        '<a class="profil-next-st" href="%s">Berikutnya →</a>' % _e(filter_data.tautan(sid, kini+1))
        if kini < jumlah else '<span class="profil-next-st" aria-disabled="true">Berikutnya →</span>')
    return '<nav class="profil-pager-st" aria-label="Halaman riwayat">%s</nav>' % ''.join(bagian)


def _nama_topik_filter(topik):
    return 'Campuran semua topik' if topik == 'campuran' else ambil(topik).nama


def _ringkasan_filter(f):
    """Ringkasan filter aktif selalu tampak tanpa perlu membuka form."""
    bagian = []
    if f.mulai:
        bagian.append('Dari ' + f.mulai)
    if f.sampai:
        bagian.append('Sampai ' + f.sampai)
    if f.topik:
        bagian.append(_nama_topik_filter(f.topik))
    if f.jenis != 'semua':
        bagian.append('Latihan bebas' if f.jenis == 'bebas' else 'Rencana terpandu')
    if f.tinjauan != 'semua':
        bagian.append(dict(H.TINJAUAN)[f.tinjauan])
    return ' · '.join(bagian)


def riwayat(siswa_id, baris, total, filter_data, *, judul_topik, tanggal, badge_tinjauan, aksi_bagikan):
    f=filter_data
    ringkasan = _ringkasan_filter(f)
    reset = '<a class="profil-reset-st" href="/anak/%d?section=riwayat">Reset filter</a>' % siswa_id if ringkasan else ''
    filter_html = ('<form method="get" action="/anak/%d" class="profil-filter-st">'
                   '<input type="hidden" name="section" value="riwayat">'
                   '<label>Dari tanggal<input type="date" name="mulai" value="%s"></label>'
                   '<label>Sampai tanggal<input type="date" name="sampai" value="%s"></label>'
                   '<label>Topik<select name="topik">%s</select></label>'
                   '<label>Jenis latihan<select name="jenis">%s</select></label>'
                   '<label>Tinjauan<select name="tinjauan">%s</select></label>'
                   '<button type="submit" class="st-tombol-sekunder">Terapkan filter</button></form>') % (
                       siswa_id,_e(f.mulai),_e(f.sampai),_opsi([('','Semua topik')]+[(k,_nama_topik_filter(k)) for k in daftar_topik()],f.topik),
                       _opsi([('semua','Semua jenis'),('bebas','Latihan bebas'),('terpandu','Rencana terpandu')],f.jenis),_opsi(H.TINJAUAN,f.tinjauan))
    filter_html = (
        '<details class="profil-saring-st"><summary class="profil-saring-judul-st">'
        '<span>Saring riwayat</span><small>%s</small></summary>%s</details>'
        % (_e(ringkasan or 'Semua sesi · terbaru dahulu'), filter_html)
    ) + ('<div class="profil-reset-wrap-st">' + reset + '</div>' if total and reset else '')
    isi=[]
    from question_context import label_profil_parameter as label_kelas
    for r in baris:
        judul,rincian=judul_topik(r['topik'])
        batal=r['dibatalkan'] is not None
        proses='Dibatalkan' if batal else ('Sudah dikirim' if r['selesai'] is not None else ('Sedang Dikerjakan' if r['terisi'] else 'Belum Dikerjakan'))
        tinjauan='<span class="badge-direview batal">Tidak berlaku</span>' if batal else ('<span class="badge-direview belum">Menunggu pengiriman</span>' if r['selesai'] is None else badge_tinjauan(r))
        jenis='Latihan bebas' if r['tujuan']=='bebas' else 'Rencana terpandu'
        if r['jenis']=='remedial':
            jenis += ' · Remedial'
            if r['sumber_sesi_id'] is not None:
                jenis += ' · dari sesi #%d' % r['sumber_sesi_id']
        mode = ('Pilihan ganda · latihan manual' if r['format_jawaban']=='pilihan_ganda'
                else 'Latihan Cepat' if r['mode']=='drill' else 'Mode Diagnosa')
        meta='%s · %s · Sesi #%d' % (label_kelas(r['level']),mode,r['id'])
        isi.append('<tr data-sesi-id="%d"><td class="riwayat-tanggal-st">%s</td>'
                   '<td class="riwayat-latihan-st"><strong>%s</strong><small class="riwayat-jenis-st">%s</small><small class="riwayat-meta-st">%s</small>%s</td>'
                   '<td class="riwayat-angka-st">%d</td><td class="riwayat-proses-st"><span>%s</span></td>'
                   '<td class="riwayat-tinjauan-st">%s</td><td class="riwayat-aksi-st"><a href="/sesi/%d" aria-label="Buka sesi %d">Buka →</a>%s</td></tr>' % (
                       r['id'],tanggal(r['tanggal']),_e(judul),_e(jenis),_e(meta),('<small>'+rincian+'</small>') if rincian else '',
                       r['n'],_e(proses),tinjauan,r['id'],r['id'],aksi_bagikan(r)))
    if not isi:
        isi.append('<tr class="profil-kosong-st"><td colspan="6"><p>Tidak ada sesi yang cocok. '
                   'Ubah filter atau buat latihan baru.</p>%s</td></tr>' % reset)
    awal=(f.halaman-1)*H.PER_HALAMAN+1 if total else 0
    akhir=min(f.halaman*H.PER_HALAMAN,total)
    hitung='Menampilkan %d–%d dari %d sesi' % (awal,akhir,total)
    urutan = '<br>Terbaru dahulu · 20 sesi per halaman' if total else ''
    kaki = ('<div class="profil-paging-st profil-riwayat-kaki-st"><span>%s</span>'
            '<a href="#filter-riwayat">Kembali ke filter &amp; halaman ↑</a></div>' % hitung) if total else ''
    return ('<section aria-labelledby="judul-riwayat"><div class="kepala-riwayat-st"><h2 class="st" id="judul-riwayat">Riwayat latihan</h2>'
            '<a class="tautan-laporan-st" href="/laporan/%d"><svg class="ikon-laporan-st" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19V10M10 19V5M16 19v-7M22 19V8"/></svg>Lihat laporan perkembangan →</a></div>'
            '<p class="sub">Status pengerjaan dan tinjauan bukan penilaian penguasaan materi.</p>'
            '<div class="profil-arsip-st" id="filter-riwayat">%s<div class="profil-paging-st"><span>%s%s</span>%s</div>'
            '<div class="profil-table-wrap-st"><table class="tabel-riwayat-st"><caption class="profil-sr-st">Riwayat latihan anak</caption><thead><tr>'
            '<th scope="col">Tanggal</th><th scope="col">Latihan</th><th scope="col">Soal</th><th scope="col">Pengerjaan</th><th scope="col">Tinjauan</th><th scope="col">Aksi</th>'
            '</tr></thead><tbody>%s</tbody></table></div>%s</div></section>') % (
                siswa_id,filter_html,hitung,urutan,_pager(siswa_id,f,total),''.join(isi),kaki)


GAYA_PROFIL = f"""
/* Ruang kerja profil v2: seluruh selector terbatas ke halaman profil. */
.profil-workspace-st .pilot-pemulihan-st {{ display:grid; gap:{T.SP_4}; }}
.profil-workspace-st .pilot-pemulihan-st label {{ display:flex; align-items:flex-start; gap:{T.SP_3}; font-size:1rem; }}
.profil-workspace-st .pilot-pemulihan-st input[type="checkbox"] {{ flex:none; width:1.25rem; height:1.25rem; margin-top:.2rem; }}
.profil-workspace-st .pilot-pemulihan-st button {{ justify-self:start; }}
.profil-workspace-st .pilot-mulai-st summary {{ padding:{T.SP_3}; min-height:{T.TARGET_SENTUH}; }}
.profil-workspace-st .pilot-mulai-st > p {{ padding:0 {T.SP_4}; }}
.profil-workspace-st .pilot-mulai-st label:has(input[type="checkbox"]) {{ display:flex; align-items:flex-start; gap:{T.SP_3}; }}
.profil-workspace-st .pilot-mulai-st input[type="checkbox"] {{ width:1.25rem; height:1.25rem; min-height:0; flex:none; margin-top:.15rem; }}
.pendamping-editorial-st.profil-editorial-st.profil-workspace-st {{ max-width:{T.LEBAR_LANDING}; }}
.profil-workspace-st .profil-tabs-st {{ display:flex; gap:{T.SP_5}; overflow-x:auto; border-bottom:1px solid {T.BORDER_HALUS}; margin-bottom:{T.SP_5}; }}
.profil-workspace-st .profil-tabs-st a {{ display:inline-flex; align-items:center; gap:{T.SP_2}; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2} 0; color:{T.TEKS_VARIAN}; text-decoration:none; white-space:nowrap; border-bottom:3px solid transparent; font-weight:650; }}
.profil-workspace-st .profil-tabs-st a[aria-current] {{ color:{T.AKSEN_TEAL_TUA}; border-color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-tabs-st span {{ font-size:.75rem; padding:.1rem .4rem; border-radius:{T.RADIUS_KECIL}; background:{T.LATAR_SEKUNDER_LEMBUT}; }}
.profil-workspace-st .profil-rappel-st {{ display:flex; align-items:center; justify-content:space-between; gap:{T.SP_4}; padding:{T.SP_3} {T.SP_4}; background:{T.LATAR_CATATAN}; border:1px solid {T.BORDER_CATATAN}; border-radius:{T.RADIUS_KARTU}; margin-bottom:{T.SP_5}; font-size:.875rem; }}
.profil-workspace-st .profil-rappel-st a {{ color:{T.AKSEN_TEAL_TUA}; white-space:nowrap; font-weight:650; }}
.profil-workspace-st .profil-formulaire-st {{ min-width:0; }}
.profil-workspace-st .profil-formulaire-st > .buat-latihan-st {{ padding:{T.SP_5}; background:{T.LATAR_KARTU}; border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU_BESAR}; }}
.profil-workspace-st .profil-formulaire-st .buat-latihan-st > h2 {{ margin-top:0; }}
.profil-workspace-st [data-panel="baru"] > .strip-sesi {{ display:block; }}
.profil-workspace-st .profil-champs-st {{ display:grid; grid-template-columns:minmax(0,1fr); gap:{T.SP_5}; min-width:0; }}
.profil-workspace-st .profil-champs-st > * {{ grid-column:1/-1; min-width:0; }}
.profil-workspace-st .profil-champs-st label {{ white-space:normal; overflow-wrap:anywhere; }}
.profil-workspace-st .profil-champs-st .strip-kolom > label {{ font-size:.875rem; color:{T.TEKS_JUDUL}; line-height:1.4; }}
.profil-workspace-st .profil-champs-st select.st-input {{ font-size:{T.UKURAN_BADAN_LAYAR}; min-height:{T.TARGET_SENTUH}; padding:{T.SP_3}; }}
.profil-workspace-st .profil-champs-st .strip-kolom > small {{ font-size:.8125rem; line-height:1.5; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .profil-assistant-st > .pendamping-buka-inline {{ display:flex; margin-top:{T.SP_2}; }}
.profil-workspace-st .profil-formulaire-st .tab-label-st {{ border-radius:{T.RADIUS_KECIL}; }}
.profil-workspace-st .profil-formulaire-st:has(.tab-radio-st:focus-visible) .tab-bar-st {{ outline:none; }}
.profil-workspace-st .buat-latihan-st:has(#tab-baru:focus-visible) [for="tab-baru"],
.profil-workspace-st .buat-latihan-st:has(#tab-ulang:focus-visible) [for="tab-ulang"],
.profil-workspace-st .buat-latihan-st:has(#tab-gabungan:focus-visible) [for="tab-gabungan"] {{ outline:2px solid {T.FOKUS_AKSEN}; outline-offset:2px; }}
.profil-workspace-st .profil-ikon-st {{ width:1.2rem; height:1.2rem; flex:none; vertical-align:middle; }}
.profil-workspace-st .tab-label-st {{ display:inline-flex; align-items:center; gap:{T.SP_2}; }}
.profil-workspace-st .profil-assistant-st .pendamping-tombol,.profil-workspace-st .profil-assistant-st .st-tombol-sekunder {{ background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; border:1px solid {T.BORDER_VARIAN}; }}
.profil-workspace-st .riwayat-aksi-st .tombol-ikon-st {{ display:inline-flex; width:auto; height:auto; min-width:{T.TARGET_SENTUH}; min-height:{T.TARGET_SENTUH}; position:relative; }}
.profil-workspace-st .profil-champs-st > .strip-kolom:nth-child(-n+2) {{ grid-column:auto; }}
.profil-workspace-st .profil-champs-st .st-tombol-coral {{ width:fit-content; }}
.profil-workspace-st .profil-assistant-st {{ min-width:0; margin-top:{T.SP_4}; }}
.profil-workspace-st .profil-assistant-st .pendamping-inline {{ margin:0; min-width:0; }}
.profil-workspace-st .profil-assistant-st .pendamping-inline > details > summary {{ font-size:1.1rem; }}
.profil-workspace-st .profil-assistant-st textarea {{ max-width:100%; }}
.profil-workspace-st .profil-taches-st {{ margin-top:{T.SP_5}; }}
.profil-workspace-st .profil-arsip-st {{ background:{T.LATAR_KARTU}; border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU_BESAR}; overflow:hidden; }}
.profil-workspace-st .profil-saring-st {{ margin:0; }}
.profil-workspace-st .profil-saring-judul-st {{ padding:{T.SP_4} {T.SP_5}; color:{T.AKSEN_TEAL_TUA}; cursor:pointer; min-height:{T.TARGET_SENTUH}; }}
.profil-workspace-st .profil-saring-judul-st > span {{ font-weight:650; }}
.profil-workspace-st .profil-saring-judul-st small {{ display:block; margin-top:{T.SP_1}; color:{T.TEKS_VARIAN}; font-size:.8125rem; overflow-wrap:anywhere; }}
.profil-workspace-st .profil-reset-wrap-st {{ padding:0 {T.SP_5} {T.SP_3}; }}
.profil-workspace-st .profil-reset-st {{ display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH}; color:{T.AKSEN_TEAL_TUA}; text-decoration:underline; font-size:.875rem; }}
.profil-workspace-st .profil-kosong-st p {{ margin:0; }}
.profil-workspace-st .profil-pager-st .profil-page-status-st {{ display:none; }}
.profil-workspace-st .profil-pager-st [aria-disabled="true"] {{ color:{T.TEKS_VARIAN}; background:{T.LATAR_SEKUNDER_LEMBUT}; }}
.profil-workspace-st .profil-filter-st {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:{T.SP_4}; padding:{T.SP_5}; align-items:end; }}
.profil-workspace-st .profil-filter-st label {{ display:grid; gap:{T.SP_1}; color:{T.TEKS_VARIAN}; font-size:.8125rem; }}
.profil-workspace-st .profil-filter-st input,.profil-workspace-st .profil-filter-st select {{ width:100%; min-width:0; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2}; font:inherit; font-size:{T.UKURAN_BADAN_LAYAR}; border:1px solid {T.BORDER_VARIAN}; background:{T.LATAR_KARTU}; border-radius:{T.RADIUS_KECIL}; }}
.profil-workspace-st .profil-paging-st {{ display:flex; gap:{T.SP_4}; flex-wrap:wrap; justify-content:space-between; align-items:center; padding:{T.SP_4} {T.SP_5}; border-top:1px solid {T.BORDER_HALUS}; font-size:.8125rem; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .profil-paging-st a {{ color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-pager-st {{ display:flex; flex-wrap:wrap; gap:{T.SP_1}; }}
.profil-workspace-st .profil-pager-st > * {{ display:inline-flex; align-items:center; justify-content:center; min-width:2.75rem; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2}; border-radius:{T.RADIUS_KECIL}; border:1px solid {T.BORDER_HALUS}; text-decoration:none; }}
.profil-workspace-st .profil-pager-st [aria-current] {{ background:{T.LATAR_TERSIMPAN}; color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-table-wrap-st {{ overflow-x:auto; }}
.profil-workspace-st .tabel-riwayat-st {{ width:100%; border-collapse:collapse; }}
.profil-workspace-st .tabel-riwayat-st th,.profil-workspace-st .tabel-riwayat-st td {{ padding:{T.SP_3}; border-bottom:1px solid {T.BORDER_HALUS}; text-align:left; vertical-align:middle; font-size:.8125rem; }}
.profil-workspace-st .tabel-riwayat-st th {{ background:{T.LATAR_SEKUNDER_LEMBUT}; color:{T.TEKS_VARIAN}; font-size:.75rem; }}
.profil-workspace-st .riwayat-latihan-st strong,.profil-workspace-st .riwayat-latihan-st small {{ display:block; }}
.profil-workspace-st .riwayat-latihan-st small {{ margin-top:{T.SP_1}; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .riwayat-tanggal-st {{ white-space:nowrap; }}
.profil-workspace-st .tabel-riwayat-st .riwayat-angka-st {{ text-align:right; font-variant-numeric:tabular-nums; }}
.profil-workspace-st .riwayat-aksi-st > a {{ display:inline-flex; min-height:{T.TARGET_SENTUH}; align-items:center; color:{T.AKSEN_TEAL_TUA}; white-space:nowrap; }}
.profil-workspace-st .profil-sr-st {{ position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }}
@media(min-width:49rem) {{
 .profil-workspace-st .profil-champs-st {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
}}
@media(min-width:64rem) {{
 .profil-workspace-st .profil-formulaire-st:has(.pendamping-inline) .strip-sesi.profil-manuel-st {{ display:grid; grid-template-columns:minmax(0,1.4fr) minmax(19rem,1fr); gap:{T.SP_5}; align-items:start; }}
 .profil-workspace-st .profil-formulaire-st:has(.pendamping-inline) .strip-sesi.profil-manuel-st > .profil-champs-st {{ grid-column:1; grid-template-columns:minmax(0,1fr); }}
 .profil-workspace-st .profil-formulaire-st:has(.pendamping-inline) .strip-sesi.profil-manuel-st > .profil-assistant-st {{ grid-column:2; grid-row:1; margin-top:0; }}
}}
@media(max-width:48rem) {{
 .profil-workspace-st .profil-tabs-st {{ gap:{T.SP_4}; font-size:.8rem; }}
 .profil-workspace-st .profil-rappel-st {{ flex-direction:column; align-items:start; }}
 .profil-workspace-st .profil-filter-st {{ grid-template-columns:minmax(0,1fr); padding:{T.SP_4}; }}
 .profil-workspace-st .profil-filter-st button {{ width:100%; }}
 .profil-workspace-st .profil-saring-judul-st {{ padding:{T.SP_3} {T.SP_4}; }}
 .profil-workspace-st .profil-reset-wrap-st {{ padding:0 {T.SP_4} {T.SP_2}; }}
 .profil-workspace-st .profil-pager-st {{ display:flex; flex-wrap:wrap; gap:{T.SP_1}; width:100%; }}
 .profil-workspace-st .profil-pager-st > * {{ flex:1 1 6em; min-width:min(100%,6em); padding:{T.SP_1}; font-size:.75rem; text-align:center; }}
 .profil-workspace-st .profil-pager-st .profil-page-number-st {{ display:none; }}
 .profil-workspace-st .profil-pager-st .profil-page-status-st {{ display:inline-flex; flex-basis:6.5em; border:0; background:transparent; color:{T.TEKS_VARIAN}; }}
 .profil-workspace-st .profil-riwayat-kaki-st a {{ min-height:{T.TARGET_SENTUH}; display:inline-flex; align-items:center; }}
 .profil-workspace-st .profil-formulaire-st > .buat-latihan-st {{ padding:{T.SP_4}; }}
 .profil-workspace-st .profil-formulaire-st .tab-bar-st {{ display:grid; grid-template-columns:minmax(0,1fr); gap:{T.SP_1}; padding:{T.SP_1}; margin-bottom:{T.SP_5}; border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_SEDANG}; background:{T.LATAR_SEKUNDER_LEMBUT}; }}
 .profil-workspace-st .profil-formulaire-st .tab-label-st {{ justify-content:flex-start; margin:0; padding:{T.SP_2} {T.SP_3}; border:1px solid transparent; font-size:.875rem; text-align:left; }}
 .profil-workspace-st .buat-latihan-st:has(#tab-baru:checked) [for="tab-baru"],
 .profil-workspace-st .buat-latihan-st:has(#tab-ulang:checked) [for="tab-ulang"],
 .profil-workspace-st .buat-latihan-st:has(#tab-gabungan:checked) [for="tab-gabungan"] {{ background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; border-color:{T.AKSEN_TEAL_TUA}; }}
 .profil-workspace-st .profil-champs-st .st-tombol-coral {{ width:100%; }}
 .profil-workspace-st .profil-assistant-st > .pendamping-buka-inline > button {{ width:100%; white-space:normal; }}
 .profil-workspace-st .profil-paging-st {{ padding:{T.SP_4}; }}
 .profil-workspace-st .tabel-riwayat-st,.profil-workspace-st .tabel-riwayat-st tbody {{ display:block; }}
 .profil-workspace-st .tabel-riwayat-st thead {{ position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }}
 .profil-workspace-st .tabel-riwayat-st tr {{ display:grid; grid-template-columns:minmax(0,1fr) auto; gap:{T.SP_1} {T.SP_2}; padding:{T.SP_3} {T.SP_4}; border-bottom:1px solid {T.BORDER_HALUS}; }}
 .profil-workspace-st .tabel-riwayat-st td {{ padding:0; border:0; min-width:0; line-height:1.4; }}
 .profil-workspace-st .riwayat-latihan-st strong {{ font-size:.9375rem; line-height:1.4; }}
 .profil-workspace-st .riwayat-latihan-st .riwayat-jenis-st,.profil-workspace-st .riwayat-latihan-st .riwayat-meta-st {{ display:inline; font-size:.75rem; line-height:1.4; }}
 .profil-workspace-st .riwayat-latihan-st .riwayat-meta-st::before {{ content:' · '; }}
 .profil-workspace-st .tabel-riwayat-st .badge-direview {{ max-width:100%; font-size:.8125rem; line-height:1.4; }}
 .profil-workspace-st .tabel-riwayat-st .profil-kosong-st {{ display:block; padding:{T.SP_4}; }}
 .profil-workspace-st .tabel-riwayat-st .profil-kosong-st td {{ display:block; }}
 .profil-workspace-st .riwayat-tanggal-st {{ grid-column:1; grid-row:1; }}
 .profil-workspace-st .riwayat-angka-st {{ grid-column:2; grid-row:1; }}
 .profil-workspace-st .riwayat-angka-st::after {{ content:' soal'; }}
 .profil-workspace-st .riwayat-latihan-st {{ grid-column:1/-1; grid-row:2; }}
 .profil-workspace-st .riwayat-proses-st {{ grid-column:1; grid-row:3; }}
 .profil-workspace-st .riwayat-proses-st::before {{ content:'Pengerjaan: '; color:{T.TEKS_VARIAN}; font-size:.75rem; }}
 .profil-workspace-st .riwayat-tinjauan-st {{ grid-column:1; grid-row:4; }}
 .profil-workspace-st .riwayat-tinjauan-st::before {{ content:'Tinjauan: '; color:{T.TEKS_VARIAN}; font-size:.75rem; }}
 .profil-workspace-st .riwayat-aksi-st {{ grid-column:2; grid-row:3/5; align-self:center; }}
}}
"""
