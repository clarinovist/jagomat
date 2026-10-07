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


def navigasi_profil(siswa_id, total, aktif):
    """Empat tujuan utama ruang anak dengan penanda aktif yang konsisten."""
    del total  # jumlah arsip tersedia di kepala Riwayat, bukan badge navigasi.
    item = (
        ('rencana', f'/anak/{siswa_id}?section=rencana', 'Berikutnya'),
        ('latihan', f'/anak/{siswa_id}?section=latihan', 'Buat latihan'),
        ('riwayat', f'/anak/{siswa_id}?section=riwayat', 'Riwayat'),
        ('perkembangan', f'/anak/{siswa_id}?section=perkembangan', 'Perkembangan'),
    )
    return ''.join(
        f'<a href="{url}"' + (' aria-current="page"' if kode == aktif else '')
        + f'>{label}</a>' for kode, url, label in item
    )


def bagian_identitas(siswa, *, peran='guru', kelas_sekolah=None, id_judul='judul-profil', kembali=None):
    """Header identitas tunggal untuk seluruh ruang anak, termasuk laporan.

    Tautan kembali digabung ke baris identitas supaya kepala halaman tidak
    menumpuk menjadi empat baris terpisah (topbar, kembali, identitas, tab).
    Kelas sekolah diubah dari menu akun, jadi kepala profil tidak lagi
    menyediakan tautan "Ubah kelas" yang menduplikasi entry point itu.
    """
    from learning_profile import label_kelas_sekolah
    keluarga = '<span class="st-badge selesai">keluarga: %s</span>' % _e(siswa['pemilik'] or 'warisan') if peran=='admin' else ''
    aksi = (
        '<div class="profil-aksi-kepala-st">'
        '<a class="profil-kembali-st" href="%s">&larr; Semua anak</a></div>' % _e(kembali)
        if kembali else ''
    )
    return (
        '<header class="kepala-anak-st editorial-kepala-st">'
        '<p class="editorial-alis-st">RUANG BELAJAR ANAK</p>'
        '<div class="profil-identitas-st"><h1 class="st" id="%s">%s '
        '<span class="st-badge selesai">(%s)</span>%s</h1>%s</div></header>'
    ) % (
        _e(id_judul), _e(siswa['nama']), _e(label_kelas_sekolah(kelas_sekolah)),
        keluarga, aksi,
    )


def bingkai(siswa, section, total, isi, *, peran='guru', pesan='', kelas_sekolah=None):
    sid = int(siswa['id'])
    nav = navigasi_profil(sid, total, section)
    kabar = '<div class="st-banner-sukses" role="status">%s</div>' % _e(pesan) if pesan else ''
    kembali = '/admin' if peran == 'admin' else '/guru'
    return ('<main aria-labelledby="judul-profil">%s'
            '<nav class="profil-tabs-st" aria-label="Bagian profil anak">%s</nav>%s%s</main>') % (
                bagian_identitas(siswa, peran=peran, kelas_sekolah=kelas_sekolah,
                                 kembali=kembali),
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
    if f.q:
        bagian.append('Cari "%s"' % f.q)
    return ' · '.join(bagian)


BULAN_RIWAYAT = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember")


def _grup_riwayat(tanggal_mentah):
    """Kelompok kartu per bulan kalender; rel timeline berhenti di tiap grup."""
    from datetime import date
    try:
        hari = date.fromisoformat(str(tanggal_mentah)[:10])
    except ValueError:
        return "Arsip"
    return "%s %d" % (BULAN_RIWAYAT[hari.month - 1], hari.year)


def _tanggal_timeline(tanggal_mentah, fallback):
    """Tanggal dua tingkat untuk rel; data warisan tetap memakai formatter aman."""
    from datetime import date
    try:
        hari = date.fromisoformat(str(tanggal_mentah)[:10])
    except ValueError:
        return '<span class="riwayat-tanggal-warisan-st">%s</span>' % fallback(tanggal_mentah)
    bulan = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")
    return ('<time datetime="%s"><strong>%d</strong><span>%s</span></time>'
            % (hari.isoformat(), hari.day, bulan[hari.month - 1]))


def _cta_riwayat(r):
    """Label aksi kontekstual; href tetap /sesi/id supaya tanpa tebakan rute."""
    if r['dibatalkan'] is not None:
        return None
    if r['selesai'] is None:
        return 'Lanjutkan mengerjakan' if r['terisi'] else 'Mulai mengerjakan'
    return 'Buka sesi'


def riwayat(
    siswa_id, baris, total, filter_data, *, judul_topik, tanggal,
    badge_tinjauan, ringkasan_hasil, aksi_bagikan, statistik=None,
):
    f = filter_data
    ringkasan = _ringkasan_filter(f)
    reset = ('<a class="profil-reset-st" href="/anak/%d?section=riwayat">Reset filter</a>' % siswa_id
             if ringkasan else '')
    ada_rentang = bool(f.mulai or f.sampai)
    form_filter = ('<form method="get" action="/anak/%d" class="profil-filter-st">'
                   '<input type="hidden" name="section" value="riwayat">'
                   '<input type="hidden" name="tinjauan" value="%s">'
                   '<label class="profil-cari-st">Cari sesi / topik<input type="search" name="q" value="%s" placeholder="cth: KPK, sesi #128…" maxlength="64"></label>'
                   '<label>Topik<select name="topik">%s</select></label>'
                   '<label>Jenis<select name="jenis">%s</select></label>'
                   '<button type="submit" class="st-tombol-sekunder">Terapkan filter</button>'
                   '<details class="riwayat-tanggal-st"%s><summary>Rentang tanggal khusus</summary>'
                   '<label>Dari tanggal<input type="date" name="mulai" value="%s"></label>'
                   '<label>Sampai tanggal<input type="date" name="sampai" value="%s"></label></details></form>') % (
                       siswa_id, _e(f.tinjauan), _e(f.q),
                       _opsi([('', 'Semua topik')] + [(k, _nama_topik_filter(k)) for k in daftar_topik()], f.topik),
                       _opsi([('semua', 'Semua jenis'), ('bebas', 'Latihan bebas'), ('terpandu', 'Rencana terpandu')], f.jenis),
                       ' open' if ada_rentang else '', _e(f.mulai), _e(f.sampai))
    from dataclasses import replace
    from datetime import date, timedelta
    hari_ini = date.today()
    rentang = (("7 hari", hari_ini - timedelta(days=6), hari_ini),
               ("30 hari", hari_ini - timedelta(days=29), hari_ini),
               ("Bulan ini", hari_ini.replace(day=1), hari_ini))
    cepat = []
    preset_aktif = False
    for label, awal, akhir in rentang:
        cocok = (not preset_aktif and (f.mulai, f.sampai)
                 == (awal.isoformat(), akhir.isoformat()))
        preset_aktif = preset_aktif or cocok
        chip = replace(f, mulai=awal.isoformat(), sampai=akhir.isoformat(), halaman=1)
        cepat.append('<a href="%s"%s>%s</a>' % (
            _e(chip.tautan(siswa_id)), ' aria-current="true"' if cocok else '', label))
    polos = replace(f, mulai="", sampai="", halaman=1)
    cepat.append('<a href="%s"%s>Semua</a>' % (
        _e(polos.tautan(siswa_id)),
        ' aria-current="true"' if not f.mulai and not f.sampai else ''))
    cepat_html = '<div class="profil-cepat-st"><span>Rentang cepat:</span>%s</div>' % ''.join(cepat)
    hitung_status = (statistik or {}).get('hitung_status') or {}
    pil = []
    for kode, label in H.TINJAUAN:
        jumlah = int(hitung_status.get(kode) or 0)
        if kode != 'semua' and not jumlah and f.tinjauan != kode:
            continue
        tandai = (' aria-current="true"'
                   if f.tinjauan == kode or (kode == 'semua' and f.tinjauan == 'semua') else '')
        tautan_filter = replace(f, tinjauan=kode, halaman=1).tautan(siswa_id)
        angka = '' if kode == 'semua' else ' (%d)' % jumlah
        pil.append('<a class="riwayat-pil-st" href="%s"%s>%s%s</a>' % (
            _e(tautan_filter), tandai, _e(label), angka))
    cepat_html += '<div class="riwayat-pilbar-st"><span>Status:</span>%s</div>' % ''.join(pil)
    judul_saring = _e(ringkasan or 'Semua sesi · terbaru dahulu')
    kelas_saring = 'profil-saring-st aktif' if ringkasan else 'profil-saring-st'
    filter_html = ('<details class="%s"><summary class="riwayat-saring-judul-st">'
                   '<span>Saring riwayat</span><small>%s</small></summary>'
                   '<div class="riwayat-filterbar-st">%s%s%s</div></details>') % (
                       kelas_saring, judul_saring, form_filter, cepat_html,
                       ('<div class="profil-reset-wrap-st">' + reset + '</div>') if total and reset else '')
    isi = []
    grup_terakhir = None
    from question_context import label_profil_parameter as label_kelas
    for r in baris:
        judul, rincian = judul_topik(r['topik'])
        batal = r['dibatalkan'] is not None
        proses = ('Dibatalkan' if batal else 'Sudah dikirim' if r['selesai'] is not None
                  else 'Sedang Dikerjakan' if r['terisi'] else 'Belum Dikerjakan')
        tinjauan = ('<span class="badge-direview batal">Tidak berlaku</span>' if batal
                    else '<span class="badge-direview belum">Menunggu pengiriman</span>'
                    if r['selesai'] is None else badge_tinjauan(r))
        jenis = 'Latihan bebas' if r['tujuan'] == 'bebas' else 'Rencana terpandu'
        if r['jenis'] == 'remedial':
            jenis += ' · Remedial'
            if r['sumber_sesi_id'] is not None:
                jenis += ' · dari sesi #%d' % r['sumber_sesi_id']
        mode = ('Pilihan ganda · latihan manual' if r['format_jawaban'] == 'pilihan_ganda'
                else 'Latihan Cepat' if r['mode'] == 'drill' else 'Mode Diagnosa')
        meta = '%s · %s · Sesi #%d' % (label_kelas(r['level']), mode, r['id'])
        grup = _grup_riwayat(r['tanggal'])
        if grup != grup_terakhir:
            if grup_terakhir is not None:
                isi.append('</ol></section>')
            isi.append('<section class="riwayat-grup-st"><h3 class="riwayat-grup-judul-st">%s</h3>'
                       '<ol class="riwayat-daftar-st">' % _e(grup))
            grup_terakhir = grup
        hasil = ringkasan_hasil(r) if r['selesai'] is not None else ''
        hasil_html = '<small class="riwayat-hasil-st">Hasil latihan: %s</small>' % hasil if hasil else ''
        tag = ('<div class="riwayat-tagbar-st"><span class="riwayat-tag-st">%s</span>'
               '<span class="riwayat-tag-st">%s</span></div>') % (
                   _e(label_kelas(r['level'])), _e(mode))
        cta = _cta_riwayat(r)
        if r['selesai'] is not None and not batal and any(
                label in tinjauan for label in ('Belum ditinjau', 'Sudah dibuka', 'Draf tinjauan', 'konfirmasi ulang')):
            cta = 'Periksa sekarang'
        label_cta = cta if cta else 'Buka sesi'
        isi.append('<li class="riwayat-kartu-st" data-sesi-id="%d">'
                   '<div class="riwayat-tanggal-blok-st">%s</div><span class="riwayat-rel-st" aria-hidden="true"></span>'
                   '<article class="riwayat-kartu-isi-st"><div class="riwayat-kartu-utama-st">'
                   '<div class="riwayat-kartu-kepala-st"><strong>%s</strong>'
                   '<small>%d soal · %s</small></div>'
                   '<div class="riwayat-status-st"><span><small>Pengerjaan</small>'
                   '<span class="riwayat-proses-nilai-st">%s</span></span>'
                   '<span><small>Tinjauan</small>%s</span></div></div>'
                   '<div class="riwayat-aksi-st"><a class="riwayat-buka-st" href="/sesi/%d" '
                   'aria-label="%s sesi %d">%s <span aria-hidden="true">→</span></a></div>'
                   '<details class="rincian-ui-st riwayat-detail-st"><summary>Detail sesi</summary>'
                   '<div class="riwayat-detail-isi-st">%s<small class="riwayat-meta-st">%s</small>%s%s'
                   '<details class="riwayat-kelola-st"><summary>Kelola tautan</summary>%s</details>'
                   '</div></details></article></li>' % (
                       r['id'], _tanggal_timeline(r['tanggal'], tanggal), _e(judul), r['n'], _e(jenis),
                       _e(proses), tinjauan, r['id'], _e(label_cta), r['id'], _e(label_cta),
                       tag, _e(meta), hasil_html, ('<small>' + rincian + '</small>') if rincian else '',
                       aksi_bagikan(r)))
    if grup_terakhir is not None:
        isi.append('</ol></section>')
    if not baris:
        isi.append('<div class="profil-kosong-st"><p>Tidak ada sesi yang cocok. '
                   'Ubah filter atau buat latihan baru.</p>%s</div>' % reset)
    awal = (f.halaman - 1) * H.PER_HALAMAN + 1 if total else 0
    akhir = min(f.halaman * H.PER_HALAMAN, total)
    hitung = 'Menampilkan %d–%d dari %d sesi' % (awal, akhir, total)
    pager = _pager(siswa_id, f, total)
    paging = ('<div class="profil-paging-st"><span>%s</span>%s</div>' % (hitung, pager)
              if pager or not total else '')
    kaki = ('<div class="profil-paging-st profil-riwayat-kaki-st"><span>%s</span>'
            '<a href="#filter-riwayat">Kembali ke filter &amp; halaman ↑</a></div>' % hitung) if total else ''
    toolbar = ('<div class="riwayat-toolbar-st"><p><strong>%d sesi</strong>'
               '<span> · Terbaru dahulu</span></p>%s</div>') % (total, filter_html)
    arsip = ('<div class="profil-arsip-st" id="filter-riwayat">%s%s'
             '<div class="riwayat-grup-daftar-st">%s</div>%s</div>') % (
                 toolbar, paging, ''.join(isi), kaki)
    return ('<section aria-labelledby="judul-riwayat"><div class="kepala-riwayat-st">'
            '<h2 class="st" id="judul-riwayat">Riwayat latihan</h2></div>'
            '<p class="sub">Status pengerjaan dan tinjauan bukan penilaian penguasaan materi.</p>'
            + arsip + '</section>')


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
.pendamping-editorial-st.profil-editorial-st.profil-workspace-st,
.pendamping-editorial-st.laporan-editorial-st.profil-workspace-st {{ max-width:{T.LEBAR_LANDING}; }}
.profil-workspace-st .profil-tabs-st {{ display:flex; gap:{T.SP_5}; overflow-x:auto; border-bottom:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; margin-bottom:{T.SP_5}; scrollbar-width:thin; }}
.profil-workspace-st .profil-tabs-st a {{ display:inline-flex; align-items:center; gap:{T.SP_2}; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2} 0; color:{T.TEKS_VARIAN}; text-decoration:none; white-space:nowrap; border-bottom:3px solid transparent; font-weight:650; }}
.profil-workspace-st .profil-tabs-st a[aria-current] {{ color:{T.AKSEN_TEAL_TUA}; border-color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-tabs-st span {{ font-size:{T.UKURAN_TEKS_META}; padding:.1rem .4rem; border-radius:{T.RADIUS_KECIL}; background:{T.LATAR_SEKUNDER_LEMBUT}; }}
.profil-workspace-st .profil-rappel-st {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:{T.SP_1} {T.SP_4}; padding:{T.SP_1} {T.SP_3}; background:{T.LATAR_CATATAN}; border:{T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius:{T.RADIUS_KECIL}; margin-bottom:{T.SP_4}; font-size:{T.UKURAN_TEKS_LABEL}; }}
.profil-workspace-st .profil-rappel-st a {{ display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH}; color:{T.AKSEN_TEAL_TUA}; white-space:nowrap; font-weight:650; }}
.profil-workspace-st .profil-formulaire-st {{ min-width:0; }}
.profil-workspace-st .profil-formulaire-st > .buat-latihan-st {{ padding:{T.SP_5}; background:{T.LATAR_KARTU}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU_BESAR}; }}
.profil-workspace-st .profil-formulaire-st .buat-latihan-st > h2 {{ margin-top:0; }}
.profil-workspace-st [data-panel="baru"] > .strip-sesi {{ display:block; }}
.profil-workspace-st .profil-champs-st {{ display:grid; grid-template-columns:minmax(0,1fr); gap:{T.SP_4}; min-width:0; }}
.profil-workspace-st .profil-champs-st > * {{ grid-column:1/-1; min-width:0; }}
.profil-workspace-st .profil-champs-st label {{ white-space:normal; overflow-wrap:anywhere; }}
.profil-workspace-st .profil-champs-st .strip-kolom > label {{ font-size:{T.UKURAN_TEKS_LABEL}; color:{T.TEKS_JUDUL}; line-height:1.4; }}
.profil-workspace-st .profil-champs-st select.st-input {{ font-size:{T.UKURAN_BADAN_LAYAR}; min-height:{T.TARGET_SENTUH}; padding:{T.SP_3}; }}
.profil-workspace-st .profil-champs-st .strip-kolom > small {{ font-size:{T.UKURAN_TEKS_CATATAN}; line-height:1.5; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .profil-assistant-st > .pendamping-buka-inline {{ display:contents; }}
.profil-workspace-st .profil-formulaire-st .tab-label-st {{ border-radius:{T.RADIUS_KECIL}; }}
.profil-workspace-st .profil-formulaire-st:has(.tab-radio-st:focus-visible) .tab-bar-st {{ outline:none; }}
.profil-workspace-st .buat-latihan-st:has(#tab-baru:focus-visible) [for="tab-baru"],
.profil-workspace-st .buat-latihan-st:has(#tab-ulang:focus-visible) [for="tab-ulang"],
.profil-workspace-st .buat-latihan-st:has(#tab-gabungan:focus-visible) [for="tab-gabungan"] {{ outline:2px solid {T.FOKUS_AKSEN}; outline-offset:2px; }}
.profil-workspace-st .profil-ikon-st {{ width:1.2rem; height:1.2rem; flex:none; vertical-align:middle; }}
.profil-workspace-st .tab-label-st {{ display:inline-flex; align-items:center; gap:{T.SP_2}; }}
.profil-workspace-st .profil-assistant-st .pendamping-tombol,.profil-workspace-st .profil-assistant-st .st-tombol-sekunder {{ background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; border:{T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; }}
.profil-workspace-st .riwayat-aksi-st .tombol-ikon-st {{ display:inline-flex; width:auto; height:auto; min-width:{T.TARGET_SENTUH}; min-height:{T.TARGET_SENTUH}; position:relative; }}
.profil-workspace-st .profil-champs-st > .strip-kolom:nth-child(-n+4) {{ grid-column:auto; }}
.profil-workspace-st .profil-aide-st {{ position:relative; display:grid; grid-template-columns:minmax(0,1fr) auto; align-items:start; gap:{T.SP_2}; margin:0 0 {T.SP_3}; }}
.profil-workspace-st .profil-formulaire-st .panduan-variasi {{ padding:0; border:0; margin:0; border-radius:0; min-width:0; }}
.profil-workspace-st .profil-formulaire-st .panduan-variasi > summary {{ font-size:{T.UKURAN_TEKS_LABEL}; width:fit-content; color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-aide-st .info:is(button) {{ position:static; margin-top:{T.SP_2}; }}
.profil-workspace-st .profil-aide-st .info-bubble {{ max-width:min({T.LEBAR_TOOLTIP},100%); }}
.profil-workspace-st .riwayat-detail-st {{ margin:0; }}
.profil-workspace-st .riwayat-detail-st > summary {{ font-size:{T.UKURAN_TEKS_META}; padding:{T.SP_1} 0; }}
.profil-workspace-st .kepala-anak-st {{ margin-bottom:{T.SP_3}; }}
.profil-workspace-st .kepala-anak-st .editorial-alis-st {{ display:none; }}
.profil-workspace-st .profil-identitas-st {{ display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:{T.SP_2} {T.SP_3}; }}
.profil-workspace-st .kepala-anak-st h1 {{ margin:0; }}
.profil-workspace-st .profil-aksi-kepala-st {{ display:flex; flex-wrap:wrap; align-items:center; gap:{T.SP_2} {T.SP_4}; }}
.profil-workspace-st .profil-kembali-st {{ display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH}; color:{T.TEKS_SUBTLE}; font-size:{T.UKURAN_TEKS_CATATAN}; text-decoration:none; }}
.profil-workspace-st .profil-kembali-st:hover {{ color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-champs-st .st-tombol-coral {{ width:fit-content; }}
.profil-workspace-st .profil-assistant-st {{ min-width:0; }}
.profil-workspace-st .profil-assistant-st .pendamping-inline {{ margin:0; min-width:0; }}
.profil-workspace-st .profil-assistant-st .pendamping-inline > details > summary {{ font-size:{T.UKURAN_BAGIAN_DEWASA}; }}
.profil-workspace-st .profil-assistant-st textarea {{ max-width:100%; }}
.profil-workspace-st .profil-taches-st {{ margin-top:{T.SP_5}; }}
.profil-workspace-st .profil-arsip-st {{ background:transparent; border:0; border-radius:0; overflow:visible; }}
.profil-workspace-st .profil-saring-st {{ margin:0; }}
.profil-workspace-st .profil-saring-judul-st {{ padding:{T.SP_4} {T.SP_5}; color:{T.AKSEN_TEAL_TUA}; cursor:pointer; min-height:{T.TARGET_SENTUH}; }}
.profil-workspace-st .profil-saring-judul-st > span {{ font-weight:650; }}
.profil-workspace-st .profil-saring-judul-st small {{ display:block; margin-top:{T.SP_1}; color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_CATATAN}; overflow-wrap:anywhere; }}
.profil-workspace-st .profil-reset-wrap-st {{ padding:0 {T.SP_5} {T.SP_3}; }}
.profil-workspace-st .profil-reset-st {{ display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH}; color:{T.AKSEN_TEAL_TUA}; text-decoration:underline; font-size:{T.UKURAN_TEKS_LABEL}; }}
.profil-workspace-st .profil-kosong-st p {{ margin:0; }}
.profil-workspace-st .profil-pager-st .profil-page-status-st {{ display:none; }}
.profil-workspace-st .profil-pager-st [aria-disabled="true"] {{ color:{T.TEKS_VARIAN}; background:{T.LATAR_SEKUNDER_LEMBUT}; }}
.profil-workspace-st .profil-filter-st {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:{T.SP_4}; padding:{T.SP_5}; align-items:end; }}
.profil-workspace-st .profil-filter-st label {{ display:grid; gap:{T.SP_1}; color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_CATATAN}; }}
.profil-workspace-st .profil-cepat-st {{ display:flex; flex-wrap:wrap; align-items:center; gap:{T.SP_2}; margin-bottom:{T.SP_3}; }}
.profil-workspace-st .profil-cepat-st > span {{ font-size:{T.UKURAN_TEKS_META}; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .profil-cepat-st a {{ display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH}; padding:{T.SP_1} {T.SP_3}; border-radius:{T.RADIUS_PIL}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; background:{T.LATAR_KARTU}; color:{T.TEKS_JUDUL}; text-decoration:none; font-size:{T.UKURAN_TEKS_LABEL}; }}
.profil-workspace-st .profil-cepat-st a[aria-current] {{ background:{T.AKSEN_TEAL_TUA}; border-color:{T.AKSEN_TEAL_TUA}; color:{T.TEKS_INVERS}; font-weight:700; }}
.profil-workspace-st .profil-filter-st input[type="date"] {{ color-scheme:light; }}
.profil-workspace-st .profil-filter-st input[type="date"]::-webkit-calendar-picker-indicator {{ cursor:pointer; opacity:.65; }}
.profil-workspace-st .profil-filter-st input,.profil-workspace-st .profil-filter-st select {{ width:100%; min-width:0; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2}; font:inherit; font-size:{T.UKURAN_BADAN_LAYAR}; border:{T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; background:{T.LATAR_KARTU}; border-radius:{T.RADIUS_KECIL}; }}
.profil-workspace-st .profil-paging-st {{ display:flex; gap:{T.SP_4}; flex-wrap:wrap; justify-content:space-between; align-items:center; padding:{T.SP_3} 0; font-size:{T.UKURAN_TEKS_CATATAN}; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .profil-paging-st a {{ color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-pager-st {{ display:flex; flex-wrap:wrap; gap:{T.SP_1}; }}
.profil-workspace-st .profil-pager-st > * {{ display:inline-flex; align-items:center; justify-content:center; min-width:2.75rem; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2}; border-radius:{T.RADIUS_KECIL}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; text-decoration:none; }}
.profil-workspace-st .profil-pager-st [aria-current] {{ background:{T.LATAR_TERSIMPAN}; color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .profil-lanjutan-st {{ grid-column:1/-1; }}
.profil-workspace-st .profil-lanjutan-isi-st {{ display:grid; gap:{T.SP_4}; padding-bottom:{T.SP_4}; }}
.profil-workspace-st .profil-batas-manual-st {{ grid-column:1/-1; margin:{T.SP_5} 0 0; padding:{T.SP_3}; background:{T.LATAR_CATATAN}; border:{T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius:{T.RADIUS_KECIL}; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .profil-sr-st {{ position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }}
/* Riwayat timeline bulanan refined: tanggal, rel, kartu, status, dan satu CTA utama. */
.profil-workspace-st .riwayat-toolbar-st {{ display:flex; align-items:center; justify-content:space-between; gap:{T.SP_4}; margin:{T.SP_4} 0 {T.SP_3}; }}
.profil-workspace-st .riwayat-toolbar-st > p {{ margin:0; color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_LABEL}; }}
.profil-workspace-st .profil-saring-st {{ position:relative; }}
.profil-workspace-st .riwayat-saring-judul-st {{ display:flex; align-items:center; justify-content:center; gap:{T.SP_2}; min-height:{T.TARGET_SENTUH}; margin:0; padding:{T.SP_2} {T.SP_4}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KECIL}; background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; cursor:pointer; list-style:none; }}
.profil-workspace-st .riwayat-saring-judul-st::-webkit-details-marker {{ display:none; }}
.profil-workspace-st .riwayat-saring-judul-st > span {{ font-weight:650; }}
.profil-workspace-st .riwayat-saring-judul-st small {{ display:none; color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_CATATAN}; overflow-wrap:anywhere; }}
.profil-workspace-st .profil-saring-st.aktif .riwayat-saring-judul-st small {{ display:block; }}
.profil-workspace-st .profil-saring-st[open] > .riwayat-saring-judul-st {{ border-color:{T.AKSEN_TEAL_TUA}; }}
.profil-workspace-st .riwayat-filterbar-st {{ position:absolute; z-index:4; top:calc(100% + {T.SP_2}); right:0; width:min(42rem,calc(100vw - {T.SP_6})); display:grid; gap:{T.SP_2}; padding:{T.SP_4}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU_BESAR}; background:{T.LATAR_KARTU}; box-shadow:{T.BAYANGAN_MENU_GURU}; }}
.profil-workspace-st .riwayat-filterbar-st .profil-filter-st {{ padding:0; gap:{T.SP_3}; }}
.profil-workspace-st .riwayat-filterbar-st .profil-filter-st button {{ background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; border:{T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; }}
.profil-workspace-st .riwayat-filterbar-st .profil-cepat-st {{ margin-bottom:{T.SP_2}; }}
.profil-workspace-st .riwayat-filterbar-st .riwayat-pilbar-st {{ margin-top:{T.SP_2}; }}
.profil-workspace-st .profil-reset-wrap-st {{ padding:0; }}
.profil-workspace-st .profil-filter-st .profil-cari-st {{ grid-column:1/-1; }}
.profil-workspace-st .riwayat-pilbar-st {{ display:flex; flex-wrap:wrap; align-items:center; gap:{T.SP_2}; margin-top:{T.SP_3}; }}
.profil-workspace-st .riwayat-pilbar-st > span {{ font-size:{T.UKURAN_TEKS_META}; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .riwayat-pil-st {{ display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH}; padding:{T.SP_1} {T.SP_3}; border-radius:{T.RADIUS_PIL}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; background:{T.LATAR_SEKUNDER_LEMBUT}; color:{T.TEKS_VARIAN}; text-decoration:none; font-size:{T.UKURAN_TEKS_LABEL}; }}
.profil-workspace-st .riwayat-pil-st[aria-current] {{ background:{T.TEKS_JUDUL}; border-color:{T.TEKS_JUDUL}; color:{T.TEKS_PUTIH}; font-weight:700; }}
.profil-workspace-st .riwayat-grup-daftar-st {{ display:grid; gap:{T.SP_5}; margin-top:{T.SP_2}; }}
.profil-workspace-st .riwayat-grup-st {{ display:grid; gap:{T.SP_3}; }}
.profil-workspace-st .riwayat-grup-judul-st {{ display:flex; align-items:center; gap:{T.SP_4}; margin:0; color:{T.TEKS_JUDUL}; font-size:{T.UKURAN_TEKS_META}; text-transform:uppercase; letter-spacing:.04em; }}
.profil-workspace-st .riwayat-grup-judul-st::after {{ content:""; flex:1; height:{T.TEBAL_GARIS}; background:{T.BORDER_HALUS}; }}
.profil-workspace-st .riwayat-daftar-st {{ list-style:none; margin:0; padding:0; display:grid; gap:{T.SP_3}; }}
.profil-workspace-st .riwayat-kartu-st {{ position:relative; display:grid; grid-template-columns:3.5rem 1.5rem minmax(0,1fr); gap:{T.SP_2}; align-items:stretch; min-width:0; font-size:{T.UKURAN_TEKS_LABEL}; }}
.profil-workspace-st .riwayat-tanggal-blok-st {{ display:flex; align-items:center; min-width:0; }}
.profil-workspace-st .riwayat-tanggal-blok-st time {{ display:grid; align-content:center; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .riwayat-tanggal-blok-st strong {{ color:{T.TEKS_JUDUL}; font-size:1.5rem; line-height:1.15; }}
.profil-workspace-st .riwayat-tanggal-blok-st span {{ font-size:{T.UKURAN_TEKS_META}; }}
.profil-workspace-st .riwayat-rel-st {{ position:relative; min-height:7rem; }}
.profil-workspace-st .riwayat-rel-st::after {{ content:""; position:absolute; left:50%; top:50%; width:.55rem; height:.55rem; transform:translate(-50%,-50%); border:2px solid {T.BORDER_HALUS}; border-radius:50%; background:{T.LATAR_MURID}; z-index:1; }}
.profil-workspace-st .riwayat-kartu-st:not(:last-child) .riwayat-rel-st::before {{ content:""; position:absolute; left:50%; top:50%; bottom:calc(-50% - {T.SP_3}); width:2px; transform:translateX(-50%); background:{T.BORDER_HALUS}; }}
.profil-workspace-st .riwayat-kartu-isi-st {{ display:grid; grid-template-columns:minmax(0,1fr) auto; grid-template-areas:"utama aksi" "detail detail"; align-items:center; gap:0 {T.SP_4}; min-width:0; padding:{T.SP_4} {T.SP_5}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU_BESAR}; background:{T.LATAR_KARTU_MURID}; box-shadow:{T.BAYANGAN_KARTU_GURU}; }}
.profil-workspace-st .riwayat-kartu-utama-st {{ grid-area:utama; display:grid; gap:{T.SP_2}; min-width:0; }}
.profil-workspace-st .riwayat-kartu-kepala-st {{ display:grid; gap:0; min-width:0; }}
.profil-workspace-st .riwayat-kartu-kepala-st strong {{ color:{T.TEKS_JUDUL}; font-size:1.05rem; line-height:1.4; }}
.profil-workspace-st .riwayat-kartu-kepala-st small {{ color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_META}; line-height:1.5; }}
.profil-workspace-st .riwayat-status-st {{ display:grid; grid-template-columns:repeat(2,minmax(10rem,15rem)); gap:{T.SP_6}; align-items:start; line-height:1.4; }}
.profil-workspace-st .riwayat-status-st > span {{ display:grid; align-content:start; gap:{T.SP_1}; min-width:0; }}
.profil-workspace-st .riwayat-status-st small {{ color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_META}; font-weight:650; }}
.profil-workspace-st .riwayat-proses-nilai-st {{ color:{T.TEKS_JUDUL}; font-weight:500; }}
.profil-workspace-st .riwayat-status-st .badge-direview {{ width:fit-content; max-width:100%; margin:0; }}
.profil-workspace-st .riwayat-status-st .badge-direview.belum,
.profil-workspace-st .riwayat-status-st .badge-direview.batal {{ background:{T.LATAR_SEKUNDER_LEMBUT}; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .riwayat-status-st .badge-direview.perlu {{ background:{T.LATAR_CATATAN}; color:{T.TEKS_JUDUL}; }}
.profil-workspace-st .riwayat-status-st .badge-direview.sudah {{ background:{T.LATAR_TERSIMPAN}; color:{T.TEKS_TERSIMPAN}; }}
.profil-workspace-st .riwayat-aksi-st {{ grid-area:aksi; display:flex; align-items:center; justify-content:flex-end; }}
.profil-workspace-st .riwayat-aksi-st > .riwayat-buka-st {{ display:inline-flex; min-height:{T.TARGET_SENTUH}; align-items:center; justify-content:center; color:{T.AKSEN_TEAL_TUA}; text-decoration:none; white-space:nowrap; font-weight:700; font-size:{T.UKURAN_TEKS_LABEL}; }}
.profil-workspace-st .riwayat-detail-st {{ grid-area:detail; margin:{T.SP_1} 0 0; }}
.profil-workspace-st .riwayat-detail-st > summary {{ width:fit-content; min-height:{T.TARGET_SENTUH}; display:flex; align-items:center; color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_META}; }}
.profil-workspace-st .riwayat-detail-isi-st {{ display:grid; gap:{T.SP_2}; padding:{T.SP_2} 0; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .riwayat-tagbar-st {{ display:flex; flex-wrap:wrap; gap:{T.SP_1}; }}
.profil-workspace-st .riwayat-tag-st {{ width:fit-content; font-size:{T.UKURAN_TEKS_CATATAN}; font-weight:700; border-radius:{T.RADIUS_PIL}; padding:.15rem .6rem; background:{T.LATAR_SEKUNDER_LEMBUT}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; color:{T.TEKS_VARIAN}; }}
.profil-workspace-st .riwayat-hasil-st {{ color:{T.TEKS_JUDUL}; font-weight:650; }}
.profil-workspace-st .riwayat-kelola-st {{ width:fit-content; }}
.profil-workspace-st .riwayat-kelola-st > summary {{ display:flex; align-items:center; min-height:{T.TARGET_SENTUH}; width:fit-content; color:{T.TEKS_VARIAN}; cursor:pointer; font-size:{T.UKURAN_TEKS_CATATAN}; }}
@media(min-width:49rem) {{
 .profil-workspace-st .profil-champs-st {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
 .profil-workspace-st .profil-champs-st > .strip-kolom > .mode-pilih {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }}
 .profil-workspace-st .profil-champs-st .mode-opsi {{ margin:0; }}
}}
@media(max-width:{T.BATAS_TABLET}) {{
 .profil-workspace-st .profil-tabs-st {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:0; overflow-x:hidden; padding-bottom:{T.SP_1}; font-size:{T.UKURAN_TEKS_META}; }}
 .profil-workspace-st .profil-tabs-st a {{ justify-content:center; padding:{T.SP_2} {T.SP_1}; white-space:nowrap; text-align:center; letter-spacing:-.02em; }}
 .profil-workspace-st .profil-filter-st {{ grid-template-columns:minmax(0,1fr); padding:{T.SP_4}; }}
 .profil-workspace-st .profil-filter-st button {{ width:100%; }}
 .profil-workspace-st .profil-saring-judul-st {{ padding:{T.SP_3} {T.SP_4}; }}
 .profil-workspace-st .profil-reset-wrap-st {{ padding:0 {T.SP_4} {T.SP_2}; }}
 .profil-workspace-st .profil-pager-st {{ display:flex; flex-wrap:wrap; gap:{T.SP_1}; width:100%; }}
 .profil-workspace-st .profil-pager-st > * {{ flex:1 1 6em; min-width:min(100%,6em); padding:{T.SP_1}; font-size:{T.UKURAN_TEKS_META}; text-align:center; }}
 .profil-workspace-st .profil-pager-st .profil-page-number-st {{ display:none; }}
 .profil-workspace-st .profil-pager-st .profil-page-status-st {{ display:inline-flex; flex-basis:6.5em; border:0; background:transparent; color:{T.TEKS_VARIAN}; }}
 .profil-workspace-st .profil-riwayat-kaki-st a {{ min-height:{T.TARGET_SENTUH}; display:inline-flex; align-items:center; }}
 .profil-workspace-st .profil-formulaire-st > .buat-latihan-st {{ padding:{T.SP_4}; }}
 .profil-workspace-st .buat-latihan-st > .profil-aide-st {{ display:none; }}
 .profil-workspace-st .profil-champs-st {{ gap:{T.SP_3}; }}
 .profil-workspace-st .profil-champs-st .strip-kolom > small {{ display:none; }}
 .profil-workspace-st .profil-formulaire-st .tab-bar-st {{ display:grid; grid-template-columns:minmax(0,1fr); gap:{T.SP_1}; padding:{T.SP_1}; margin-bottom:{T.SP_3}; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_SEDANG}; background:{T.LATAR_SEKUNDER_LEMBUT}; }}
 .profil-workspace-st .profil-formulaire-st .tab-label-st {{ justify-content:flex-start; margin:0; padding:{T.SP_2} {T.SP_3}; border:{T.TEBAL_GARIS} solid transparent; font-size:{T.UKURAN_TEKS_LABEL}; text-align:left; }}
 .profil-workspace-st .buat-latihan-st:has(#tab-baru:checked) [for="tab-baru"],
 .profil-workspace-st .buat-latihan-st:has(#tab-ulang:checked) [for="tab-ulang"],
 .profil-workspace-st .buat-latihan-st:has(#tab-gabungan:checked) [for="tab-gabungan"] {{ background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; border-color:{T.AKSEN_TEAL_TUA}; }}
 .profil-workspace-st .profil-champs-st .st-tombol-coral {{ width:100%; }}
 .profil-workspace-st .profil-paging-st {{ padding:{T.SP_3} 0; }}
 .profil-workspace-st .riwayat-toolbar-st {{ align-items:stretch; flex-wrap:wrap; }}
 .profil-workspace-st .riwayat-toolbar-st > p {{ display:flex; align-items:center; }}
 .profil-workspace-st .riwayat-saring-judul-st small {{ display:none; }}
 .profil-workspace-st .profil-saring-st[open] {{ flex-basis:100%; }}
 .profil-workspace-st .profil-saring-st[open] > .riwayat-saring-judul-st {{ width:fit-content; margin-left:auto; }}
 .profil-workspace-st .riwayat-filterbar-st {{ position:static; width:100%; max-height:none; margin-top:{T.SP_2}; overflow:visible; }}
 .profil-workspace-st .riwayat-kartu-st {{ grid-template-columns:2.5rem 1rem minmax(0,1fr); gap:{T.SP_1}; }}
 .profil-workspace-st .riwayat-tanggal-blok-st strong {{ font-size:1.15rem; }}
 .profil-workspace-st .riwayat-kartu-isi-st {{ grid-template-columns:minmax(0,1fr); grid-template-areas:"utama" "aksi" "detail"; padding:{T.SP_4}; }}
 .profil-workspace-st .riwayat-status-st {{ grid-template-columns:minmax(0,1fr); gap:{T.SP_2}; }}
 .profil-workspace-st .riwayat-daftar-st .badge-direview {{ max-width:100%; font-size:{T.UKURAN_TEKS_CATATAN}; line-height:1.4; }}
 .profil-workspace-st .riwayat-daftar-st .profil-kosong-st {{ grid-column:1/-1; padding:{T.SP_4}; }}
 .profil-workspace-st .riwayat-aksi-st {{ align-self:stretch; justify-content:stretch; padding-top:{T.SP_3}; }}
 .profil-workspace-st .riwayat-aksi-st > .riwayat-buka-st {{ width:100%; justify-content:center; min-height:{T.TINGGI_CTA}; background:{T.AKSEN_TEAL_TUA}; color:{T.TEKS_PUTIH}; border-radius:{T.RADIUS_KECIL}; text-decoration:none; }}
}}
"""
