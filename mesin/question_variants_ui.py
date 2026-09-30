"""Panduan variasi dan contoh latihan dari registry yang nyata."""
import html
from functools import lru_cache

import design_tokens as T
import topics
from generator import buat_lembar
from question_context import label_profil_parameter, validasi_pilihan
from render import _badan_soal
from template_labels import nama_tipe_soal
from templates import LEVEL


def kontrol_variasi(identitas, terpilih=None, *, ringkas=False):
    """Pilihan native; onboarding memakai summary di dekatnya, bukan tautan ganda."""
    identitas = html.escape(identitas, quote=True)
    bantuan = (
        'A–D membedakan isi soal, bukan urutan kemampuan atau kelas anak.'
        if ringkas else
        'Variasi isi soal, bukan tingkat kemampuan atau kelas anak.'
    )
    return (
        f'<div class="strip-kolom"><label for="{identitas}-profil">Variasi soal</label>'
        f'<select id="{identitas}-profil" name="profil_parameter" class="st-input" required '
        f'aria-describedby="{identitas}-profil-bantuan">'
        '<option value="">Pilih variasi soal</option>'
        + ''.join(f'<option value="{p}"' + (' selected' if p == terpilih else '')
                  + f'>{label_profil_parameter(p)}</option>' for p in LEVEL)
        + f'</select><small class="profil-petunjuk-st" id="{identitas}-profil-bantuan">'
        + bantuan + '</small></div>'
    )


def detail_kode(profil):
    """Kode untuk penelusuran histori, bukan identitas atau jenjang anak."""
    if profil == '':
        return ''
    return ('<details class="variasi-kode"><summary>Detail pengaturan latihan</summary>'
            '<p>' + html.escape(label_profil_parameter(profil))
            + ' · Kode konfigurasi: ' + html.escape(str(profil))
            + '. Kode disimpan agar riwayat tetap dapat ditelusuri; bukan kelas atau ukuran kemampuan.</p></details>')


@lru_cache(maxsize=64)
def contoh_variasi(topik, profil):
    """Contoh deterministik dari pasangan aktual; tanpa DB, kunci atau sesi baru."""
    validasi_pilihan([topik], profil)
    paket = topics.ambil(topik)
    tid = paket.komposisi[profil][0]
    soal = buat_lembar(42, urutan=(tid,), level=profil, topik=topik).soal[0]
    return (nama_tipe_soal(tid),
            _badan_soal(soal, paket, namespace='contoh-' + topik + '-' + profil))


def _pola_soal(topik, profil):
    paket = topics.ambil(topik)
    return tuple(dict.fromkeys(
        nama_tipe_soal(tid) for tid in paket.komposisi.get(profil, ())
    ))


def _nama_isi(topik, profil):
    """Nama ringkas dari komposisi nyata; tidak mengarang tingkat kesulitan."""
    pola = _pola_soal(topik, profil)
    profil_lain = [
        set(_pola_soal(topik, kandidat))
        for kandidat in LEVEL
        if kandidat != profil and kandidat in topics.ambil(topik).komposisi
    ]
    urutan = {nama: indeks for indeks, nama in enumerate(pola)}
    utama = sorted(
        pola,
        key=lambda nama: (sum(nama in lain for lain in profil_lain), urutan[nama]),
    )[:1]
    return utama[0] if utama else 'Isi latihan belum tersedia'


def _template_contoh(topik, profil):
    """Utamakan pola pembeda; jika komposisi sama, angka contoh tetap mengikuti profil."""
    paket = topics.ambil(topik)
    kandidat = paket.komposisi[profil]
    komposisi_lain = [
        set(komposisi)
        for profil_lain, komposisi in paket.komposisi.items()
        if profil_lain != profil
    ]
    urutan = {tid: indeks for indeks, tid in enumerate(kandidat)}
    return min(
        kandidat,
        key=lambda tid: (sum(tid in komposisi for komposisi in komposisi_lain), urutan[tid]),
    )


@lru_cache(maxsize=64)
def _contoh_isi(topik, profil):
    validasi_pilihan([topik], profil)
    paket = topics.ambil(topik)
    tid = _template_contoh(topik, profil)
    soal = buat_lembar(42, urutan=(tid,), level=profil, topik=topik).soal[0]
    return (nama_tipe_soal(tid),
            _badan_soal(soal, paket, namespace='pilih-isi-' + topik + '-' + profil))


def _topik_tersedia(topik_ids, profil):
    return tuple(
        topik for topik in topik_ids
        if topik != 'campuran' and profil in topics.ambil(topik).komposisi
    )


def _kartu_isi(profil, topik_ids, identitas, terpilih, *, nomor, pemetaan=False):
    topik_ids = tuple(topik_ids)
    pola_per_topik = [(topik, _pola_soal(topik, profil)) for topik in topik_ids]
    jumlah_pola = len({pola for _topik, daftar in pola_per_topik for pola in daftar})
    nama_isi = _nama_isi(topik_ids[0], profil)
    if len(topik_ids) == 1:
        ringkasan = f'Mencakup {jumlah_pola} pola soal.'
    else:
        ringkasan = f'Mencakup {len(topik_ids)} materi dan {jumlah_pola} pola soal.'
    contoh_topik = topik_ids[0]
    nama_contoh, contoh = _contoh_isi(contoh_topik, profil)
    kode = html.escape(profil, quote=True)
    id_radio = f'{identitas}-profil-{kode}'
    checked = ' checked' if profil == terpilih else ''
    konteks = 'pemetaan' if pemetaan else ','.join(topik_ids)
    penanda = str(nomor)
    return (
        f'<article class="variasi-pilihan" data-contoh="{html.escape(konteks, quote=True)}:{kode}">'
        f'<label class="variasi-label" for="{id_radio}">'
        f'<input type="radio" name="profil_parameter" value="{kode}"{checked} '
        f'id="{id_radio}" required>'
        '<span class="variasi-identitas"><span class="variasi-judul">'
        '<span class="variasi-penanda"><span class="variasi-sr">Pilihan </span>'
        + penanda
        + '</span><strong class="variasi-nama-isi">' + html.escape(nama_isi)
        + '</strong></span><span class="variasi-meta">' + ringkasan + '</span></span></label>'
        '<details class="variasi-contoh-dekat"><summary>Lihat contoh'
        + (' materi' if pemetaan or len(topik_ids) > 1 else '') + ': '
        + html.escape(nama_contoh) + '</summary><div class="variasi-soal">' + contoh
        + '</div><p class="profil-petunjuk-st">Contoh dari '
        + html.escape(topics.ambil(contoh_topik).nama)
        + '; angka dan bentuk soal sesi dapat berbeda.</p></details></article>'
    )


def pemilih_isi(topik_ids, identitas, terpilih=None):
    """Radio isi kontekstual untuk satu atau beberapa topik, tanpa pilihan otomatis."""
    topik_ids = tuple(dict.fromkeys(topik_ids))
    if not topik_ids:
        identitas = html.escape(identitas, quote=True)
        return (
            f'<fieldset class="pilih-isi-latihan" aria-describedby="{identitas}-profil-bantuan">'
            '<legend>Pilih isi latihan</legend><p class="variasi-kosong" '
            f'id="{identitas}-profil-bantuan">Pilih minimal dua materi, lalu tekan '
            '<b>Bandingkan isi</b> untuk melihat pilihan yang tersedia.</p></fieldset>'
        )
    if any(topik not in topics.daftar_topik() for topik in topik_ids):
        raise ValueError('Pilih materi latihan sebelum membandingkan isi.')
    if 'campuran' in topik_ids:
        if topik_ids != ('campuran',):
            raise ValueError('Campuran tidak dapat digabungkan sebagai materi biasa.')
        tersedia = tuple(LEVEL)
        topik_ids = ('campuran',)
    else:
        tersedia = tuple(
            profil for profil in LEVEL
            if all(profil in topics.ambil(topik).komposisi for topik in topik_ids)
        )
    if not tersedia:
        identitas = html.escape(identitas, quote=True)
        return (
            f'<fieldset class="pilih-isi-latihan" aria-describedby="{identitas}-profil-bantuan">'
            '<legend>Pilih isi latihan</legend><p class="variasi-kosong" '
            f'id="{identitas}-profil-bantuan">Belum ada variasi yang tersedia untuk seluruh materi pilihan. '
            'Ubah materi, lalu bandingkan lagi.</p></fieldset>'
        )
    identitas = html.escape(identitas, quote=True)
    kartu = ''.join(
        _kartu_isi(profil, topik_ids, identitas, terpilih, nomor=nomor)
        for nomor, profil in enumerate(tersedia, 1)
    )
    konteks = (
        '<input type="hidden" name="versi_pilihan_isi" value="1">'
        + ''.join(
            '<input type="hidden" name="topik_dibandingkan" value="%s">'
            % html.escape(topik, quote=True)
            for topik in topik_ids
        )
    )
    return (
        f'<fieldset class="pilih-isi-latihan" aria-describedby="{identitas}-profil-bantuan">'
        + konteks
        + '<legend>Pilih isi latihan</legend><p class="profil-petunjuk-st" '
        f'id="{identitas}-profil-bantuan">Bandingkan isi dan contohnya, lalu pilih yang ingin dilatih. '
        'Nomor pilihan hanya penanda, bukan urutan kemampuan atau kelas anak.</p>'
        f'<div class="variasi-pilihan-daftar">{kartu}</div></fieldset>'
    )


def pemilih_pemetaan(identitas, terpilih=None):
    """Pilihan eksplisit untuk cakupan pemetaan lintas materi per profil warisan."""
    semua_topik = tuple(t for t in topics.daftar_topik() if t != 'campuran')
    identitas = html.escape(identitas, quote=True)
    kartu = ''.join(
        _kartu_isi(
            profil, _topik_tersedia(semua_topik, profil), identitas, terpilih,
            nomor=nomor, pemetaan=True,
        )
        for nomor, profil in enumerate(LEVEL, 1)
    )
    return (
        f'<fieldset class="pilih-isi-latihan pilih-isi-pemetaan" '
        f'aria-describedby="{identitas}-profil-bantuan"><legend>Pilih isi untuk pemetaan pertama</legend>'
        f'<p class="profil-petunjuk-st" id="{identitas}-profil-bantuan">'
        'Setiap pilihan memetakan materi dan pola soal yang tersedia pada konfigurasi itu. '
        'Nomor pilihan hanya penanda, bukan urutan kemampuan atau kelas anak.</p>'
        f'<div class="variasi-pilihan-daftar">{kartu}</div></fieldset>'
    )


@lru_cache(maxsize=4)
def panduan_variasi(*, ringkas=False, judul="Bandingkan isi dan contoh soal"):
    """Daftar pola nyata; onboarding menyimpan penjelasan lanjut dalam details."""
    bagian = []
    for topik in topics.daftar_topik():
        if topik == 'campuran':
            continue
        paket = topics.ambil(topik)
        pilihan = []
        for profil in LEVEL:
            if profil not in paket.komposisi:
                continue
            pola = ', '.join(dict.fromkeys(nama_tipe_soal(tid) for tid in paket.komposisi[profil]))
            nama, contoh = contoh_variasi(topik, profil)
            pilihan.append(
                '<article class="variasi-contoh" data-contoh="%s:%s"><h4>%s</h4>'
                '<p>Variasi isi, bukan tingkatan.</p><p><b>Pola soal:</b> %s.</p><details><summary>Lihat contoh: %s</summary>'
                '<div class="variasi-soal">%s</div></details>'
                '<details class="variasi-kode"><summary>Detail teknis</summary>'
                '<p>Kode konfigurasi: %s</p></details></article>'
                % (topik, profil, label_profil_parameter(profil), html.escape(pola),
                   html.escape(nama), contoh, profil)
            )
        bagian.append('<details class="variasi-materi"><summary>%s</summary><div class="variasi-daftar">%s</div></details>'
                      % (html.escape(paket.nama), ''.join(pilihan)))
    penjelasan = (
        '<p>Huruf A–D hanya pembeda variasi, <b>bukan urutan kemampuan</b>. '
        'Buka materi yang ingin dilatih, lalu bandingkan pola dan contohnya. '
        'Nama pola yang sama dapat memakai angka atau bentuk tugas berbeda.</p>'
        '<p>Contoh ini bukan soal sesi yang akan dibuat. Angka dan pola pada sesi bisa berbeda; '
        'satu contoh tidak mewakili seluruh pola. Tidak semua variasi tersedia pada setiap materi.</p>'
    )
    campuran = (
        '<p>Campuran mengikuti materi yang tersedia pada variasi pilihan. '
        'Untuk gabungan topik, pilih variasi yang tersedia pada semua topik yang dicentang; '
        'kombinasi yang tidak tersedia tidak akan dibuat.</p>'
    )
    isi = penjelasan + ''.join(bagian) + campuran
    if ringkas:
        isi = (
            '<p>Pilih materi, lalu bandingkan isi dan contoh soalnya.</p>'
            + ''.join(bagian)
            + '<details class="variasi-kode"><summary>Tentang variasi dan contoh</summary>'
            + penjelasan + campuran + '</details>'
        )
    return (
        '<details class="panduan-variasi" id="panduan-variasi">'
        '<summary>' + html.escape(judul) + '</summary>'
        + isi + '</details>'
    )


GAYA_VARIASI = f"""
.panduan-variasi {{ margin:{T.SP_4} 0; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU_BESAR}; padding:{T.SP_4}; background:{T.LATAR_KARTU}; min-width:0; }}
.panduan-variasi summary,.variasi-kode summary {{ cursor:pointer; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2} 0; line-height:1.5; overflow-wrap:anywhere; }}
.panduan-variasi p,.variasi-kode p {{ line-height:1.6; overflow-wrap:anywhere; }}
.variasi-materi {{ border-top:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; padding:{T.SP_2} 0; }}
.variasi-daftar {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr)); gap:{T.SP_4}; }}
.variasi-contoh {{ min-width:0; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KECIL}; padding:{T.SP_3}; }}
.variasi-contoh h4 {{ margin:0; color:{T.TEKS_JUDUL}; }}
.variasi-soal {{ overflow-x:auto; padding:{T.SP_3} 0; }}
.variasi-soal svg {{ max-width:100%; height:auto; }}
.pilih-isi-latihan {{ min-width:0; margin:0; padding:0; border:0; }}
.pilih-isi-latihan > legend {{ padding:0; color:{T.TEKS_JUDUL}; font-weight:700; }}
.pilih-isi-latihan > .profil-petunjuk-st {{ margin:{T.SP_1} 0 {T.SP_3}; color:{T.TEKS_VARIAN}; line-height:1.55; }}
.variasi-pilihan-daftar {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr)); gap:{T.SP_3}; }}
.variasi-pilihan {{ min-width:0; display:flex; flex-direction:column; border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_SEDANG}; background:{T.LATAR_KARTU}; padding:{T.SP_3}; }}
.variasi-pilihan:has(input:checked) {{ border:2px solid {T.AKSEN_TEAL_TUA}; background:{T.LATAR_TERSIMPAN}; }}
.variasi-label {{ display:flex; align-items:flex-start; gap:{T.SP_3}; min-height:{T.TARGET_SENTUH}; cursor:pointer; }}
.variasi-label input {{ flex:none; margin-top:.35rem; }}
.variasi-identitas {{ display:grid; gap:{T.SP_2}; min-width:0; }}
.variasi-judul {{ display:flex; align-items:flex-start; gap:{T.SP_2}; min-width:0; }}
.variasi-sr {{ position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); }}
.variasi-penanda {{ flex:none; min-width:1.45rem; padding:.1rem .38rem; border-radius:{T.RADIUS_PIL}; background:{T.LATAR_SEKUNDER_LEMBUT}; color:{T.AKSEN_TEAL_TUA}; font-size:{T.UKURAN_TEKS_META}; line-height:1.45; font-weight:700; text-align:center; }}
.variasi-nama-isi {{ color:{T.TEKS_JUDUL}; font-size:1rem; line-height:1.35; font-weight:700; overflow-wrap:anywhere; }}
.variasi-meta {{ color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_CATATAN}; line-height:1.55; font-weight:400; overflow-wrap:anywhere; }}
.variasi-meta > span {{ display:block; margin-top:{T.SP_1}; }}
.variasi-meta > span:first-child {{ margin-top:0; }}
.variasi-pilihan:focus-within {{ outline:{T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset:2px; }}
.variasi-contoh-dekat {{ margin-top:auto; border-top:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; }}
.variasi-contoh-dekat > summary {{ min-height:{T.TARGET_SENTUH}; padding:{T.SP_2} 0; color:{T.AKSEN_TEAL_TUA}; cursor:pointer; line-height:1.4; }}
.variasi-contoh-dekat > .profil-petunjuk-st {{ color:{T.TEKS_VARIAN}; font-size:{T.UKURAN_TEKS_CATATAN}; line-height:1.5; }}
.variasi-kosong {{ margin:{T.SP_2} 0; padding:{T.SP_3}; border:{T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius:{T.RADIUS_KECIL}; background:{T.LATAR_CATATAN}; }}
.profil-workspace-st .variasi-bandingkan {{ width:fit-content; min-height:{T.TARGET_SENTUH}; margin-top:{T.SP_2}; padding:{T.SP_2} {T.SP_3}; border:{T.TEBAL_GARIS} solid {T.AKSEN_TEAL_TUA}; border-radius:{T.RADIUS_KECIL}; background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; font:inherit; font-weight:650; cursor:pointer; }}
.profil-workspace-st .variasi-bandingkan:hover {{ background:{T.LATAR_SEKUNDER_LEMBUT}; }}
.pengaturan-awal {{ border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KECIL}; margin:{T.SP_4} 0; padding:{T.SP_4}; min-width:0; }}
"""
