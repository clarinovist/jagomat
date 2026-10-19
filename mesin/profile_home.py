"""Beranda orang tua: proyeksi ringkas, tanpa keputusan atau penulisan bukti."""
import html

import learning_cycle_ui as UI
from learning_history import catatan_histori_beda_level


def _e(nilai):
    return html.escape(str(nilai), quote=True)


def _meta(rencana, bukti, jumlah_soal):
    """Metadata CTA, bukan sesi terbaru; durasi ialah estimasi pengerjaan."""
    identitas = UI._identitas_sesi(rencana, bukti)
    if identitas:
        # Helper menghasilkan satu paragraf identitas yang sama dengan kartu sesi.
        tambahan = f' · {jumlah_soal} soal · sekitar {jumlah_soal * 3} menit pengerjaan' if jumlah_soal else ''
        return identitas.removesuffix('</p>') + tambahan + '</p>'
    return '<p class="beranda-meta-st">' + _e(UI._waktu(rencana, bukti)) + '</p>'


def posisi(rencana, bukti, nama):
    """Tahap aktif dari pemetaan presenter existing; bukan indikator kelulusan."""
    nomor = UI._indeks_tahap(rencana, bukti) + 1
    return (
        '<section class="beranda-posisi-st" aria-labelledby="judul-posisi">'
        f'<h2 class="st" id="judul-posisi">Posisi {_e(nama)}: tahap {nomor} dari 6</h2>'
        + UI._strip_tahap(rencana, bukti)
        + '<p>Ini peta perjalanan, bukan nilai.</p>'
        '<details class="alur-rencana-jelas-st"><summary>Apa yang terjadi di setiap tahap?</summary>'
        '<div class="isi-alur-rencana-st"><p>Latihan awal membantu menentukan bagian yang perlu dibantu. '
        'Setelah itu, anak belajar bersama, berlatih dengan bantuan lalu mandiri, menjalani cek setelah jeda, '
        'dan mengecek kembali pemahaman sebelum langkah berikutnya dipilih.</p>'
        '<p>Urutan ini adalah peta perjalanan, bukan tanda bahwa tahap sebelumnya pasti selesai.</p>'
        '</div></details></section>'
    )


def kartu(rencana, bukti, siswa, *, jumlah_soal=None, slot_bantuan=''):
    """Susun kartu Beranda; aksi, materi dan status tetap milik helper siklus."""
    from cycle_carry import bukti_lanjutan
    from cycle_representations import CATATAN_PEMISAHAN, bukti_satu_representasi
    from learning_cycle import _putaran_aktif

    sid = int(siswa['id'])
    if bukti.siswa_id != sid:
        raise ValueError('bukti bukan milik siswa')
    bukti = bukti_lanjutan(bukti)
    terpilih = bukti_satu_representasi(bukti, _putaran_aktif(bukti))
    catatan_mode = '<p>' + _e(CATATAN_PEMISAHAN) + '</p>' if terpilih != bukti else ''
    bukti = terpilih
    fokus = UI._fokus_utama(rencana)
    materi = UI._materi(rencana, fokus)
    tertahan = bool(materi is not None and not materi.tersedia)
    instruksi = ('Tunggu materi pendamping tersedia; jangan membuat latihan pengganti.'
                 if tertahan else UI._tindakan_orang_tua(rencana, materi))
    judul = ('Tinjau hasil latihan ' + siswa['nama'] if rencana.tindakan == 'konfirmasi_hasil'
             else 'Mulai dengan latihan awal' if rencana.tindakan == 'pilih_variasi'
             else UI._judul(rencana, fokus, bukti))
    cta = UI._cta(rencana, bukti, sid, fokus, materi)
    if rencana.tindakan == 'pilih_variasi':
        cta = (f'<form method="post" action="/siklus/{sid}/buat" class="rencana-form-st">'
               '<button type="submit" class="rencana-cta-utama-st">Siapkan latihan awal</button></form>')
    contoh = ''
    if materi is not None:
        if tertahan:
            contoh = '<p class="rencana-peringatan-st">' + _e(materi.instruksi_orang_tua) + '</p>'
        elif materi.contoh_terbimbing:
            contoh = ('<div class="contoh-rencana-st"><b>Contoh terbimbing</b><p>'
                      + _e(materi.contoh_terbimbing) + '</p>'
                      + UI._visual_materi(rencana, materi, sid) + '</div>')
    tanggal = (f'<p class="tanggal-rencana-st">Tersedia pada {_e(UI._tanggal_indonesia(rencana.tersedia_pada))}.</p>'
               if rencana.tersedia_pada else '')
    histori = ''.join('<p class="catatan-histori-level-st">' + _e(teks) + '</p>'
                      for teks in catatan_histori_beda_level(
                          bukti, mulai_dari_awal=(rencana.tindakan == 'pemetaan'
                          and bool(rencana.putaran) and not rencana.putaran.tanggal_pemetaan)))
    progres = '' if rencana.tindakan in {'lanjutkan_sesi', 'konfirmasi_hasil'} else (
        '<p class="beranda-progres-st">' + _e(UI._progres(rencana, bukti)) + '</p>')
    konteks = UI._konteks_pemetaan(rencana)
    if rencana.tindakan == 'pilih_variasi':
        konteks = '<p class="catatan-tiga-latihan-st"><b>Rangkaian awal:</b> tiga latihan pada tanggal berbeda.</p>'
    peringatan = ('<p class="beranda-konfirmasi-st">Konfirmasi hanya setelah hasil diperiksa.</p>'
                  if rencana.tindakan == 'konfirmasi_hasil' else '')
    petunjuk = ('<p class="petunjuk-sesudah-cta-st">Bisa disimpan sebagai draf dan dilanjutkan nanti.</p>'
                if rencana.tindakan == 'konfirmasi_hasil' else '')
    meta = ('<p class="beranda-meta-st">' + _e(UI._waktu(rencana, bukti, tertahan=True)) + '</p>'
            if tertahan else _meta(rencana, bukti, jumlah_soal))
    return (
        '<section class="kartu-rencana-st" aria-labelledby="judul-rencana-belajar">'
        '<p class="label-rencana-st">Yang perlu dilakukan sekarang</p>'
        f'<h2 class="st" id="judul-rencana-belajar">{_e(judul)}</h2>'
        + meta + progres + tanggal + konteks
        + '<div class="beranda-caranya-st"><b>Caranya</b><p>' + _e(instruksi) + '</p>'
        + peringatan + '</div>'
        + contoh + '<div class="beranda-aksi-st">' + cta + petunjuk + '</div>'
        + '<details class="rincian-ui-st batas-rencana-st"><summary>Cara membaca progres ini</summary>'
        '<p>' + _e(UI._alasan(rencana, fokus)) + '</p>' + catatan_mode + '</details>'
        + histori + slot_bantuan + UI._override(rencana, sid) + '</section>'
        + posisi(rencana, bukti, siswa['nama'])
    )


def sesi_lain(baris, *, judul_topik, tanggal, badge_tinjauan):
    """Tiga sesi siap ditinjau dari query terbatasi, satu aksi per kartu."""
    if not baris:
        return ''
    kartu = []
    for r in baris:
        judul, _ = judul_topik(r['topik'])
        badge = badge_tinjauan(r)
        label = 'Lanjutkan' if 'Draf tersimpan' in badge else 'Tinjau'
        kartu.append(
            '<article class="st-kartu-baris kartu-sesi-guru beranda-sesi-st" '
            f'data-sesi-id="{r["id"]}"><div><h3>{_e(judul)}</h3>'
            f'<p>{tanggal(r["tanggal"])} · Sesi #{r["id"]} · {r["n"]} soal</p>'
            + badge + '</div>'
            f'<a class="beranda-tinjau-st" href="/sesi/{r["id"]}" '
            f'aria-label="{label} sesi {r["id"]}">{label}</a></article>')
    return ('<section class="profil-taches-st"><h2 class="st">Sesi lain yang menunggu tinjauan</h2>'
            '<div class="daftar-anak">' + ''.join(kartu) + '</div></section>')


def tautan_perkembangan(kon, siswa_id):
    """Peta yang sama dengan laporan; jangan mengarang angka bila bukti berubah."""
    import database
    from mastery_evidence import lengkapi_bukti_materi
    from mastery_report import peta_penguasaan

    try:
        bukti = database.muat_bukti_siklus(kon, siswa_id)
        peta = peta_penguasaan(lengkapi_bukti_materi(kon, bukti), siswa_id)
    except ValueError:
        peta = None
    teks = 'Lihat perkembangan'
    if peta is not None and peta.target:
        jumlah = peta.jumlah
        teks = f'{jumlah["dipelajari"]} dari {len(peta.target)} target sedang dipelajari.'
        if jumlah['terbukti']:
            teks += f' {jumlah["terbukti"]} menunjukkan pemahaman.'
        if jumlah['perlu_cek']:
            teks += f' {jumlah["perlu_cek"]} perlu dicek kembali.'
        teks += f' {jumlah["belum_dinilai"]} belum dinilai; belum dinilai bukan berarti tidak mampu.'
    return (f'<a class="beranda-perkembangan-st" href="/anak/{siswa_id}?section=perkembangan">'
            '<span><b>Perkembangan:</b> ' + _e(teks) + '</span>'
            '<span aria-hidden="true">→</span></a>')
