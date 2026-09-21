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


def kontrol_variasi(identitas, terpilih=None):
    """Satu pilihan native; kode historis tetap menjadi nilai kiriman."""
    identitas = html.escape(identitas, quote=True)
    return (
        f'<div class="strip-kolom"><label for="{identitas}-profil">Variasi soal</label>'
        f'<select id="{identitas}-profil" name="profil_parameter" class="st-input" required '
        f'aria-describedby="{identitas}-profil-bantuan">'
        '<option value="">Pilih variasi soal</option>'
        + ''.join(f'<option value="{p}"' + (' selected' if p == terpilih else '')
                  + f'>{label_profil_parameter(p)}</option>' for p in LEVEL)
        + f'</select><small class="profil-petunjuk-st" id="{identitas}-profil-bantuan">'
        'Pilih berdasarkan materi dan contoh, bukan kelas anak. '
        '<a href="#panduan-variasi">Bandingkan isi dan contoh soal</a>.</small></div>'
    )


def detail_kode(profil):
    """Kode untuk penelusuran histori, bukan identitas atau jenjang anak."""
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


@lru_cache(maxsize=1)
def panduan_variasi():
    """Daftar pola dan contoh per materi; tak menjanjikan kesetaraan lintas variasi."""
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
    return (
        '<details class="panduan-variasi" id="panduan-variasi">'
        '<summary>Bandingkan isi dan contoh soal</summary>'
        '<p>Huruf A–D hanya pembeda variasi, <b>bukan urutan kemampuan</b>. '
        'Buka materi yang ingin dilatih, lalu bandingkan pola dan contohnya. '
        'Nama pola yang sama dapat memakai angka atau bentuk tugas berbeda.</p>'
        '<p>Contoh ini bukan soal sesi yang akan dibuat. Angka dan pola pada sesi bisa berbeda; '
        'satu contoh tidak mewakili seluruh pola. Tidak semua variasi tersedia pada setiap materi.</p>'
        + ''.join(bagian)
        + '<p>Campuran mengikuti materi yang tersedia pada variasi pilihan. '
        'Untuk gabungan topik, pilih variasi yang tersedia pada semua topik yang dicentang; '
        'kombinasi yang tidak tersedia tidak akan dibuat.</p></details>'
    )


GAYA_VARIASI = f"""
.panduan-variasi {{ margin:{T.SP_4} 0; border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU}; padding:{T.SP_4}; background:{T.LATAR_KARTU}; min-width:0; }}
.panduan-variasi summary,.variasi-kode summary {{ cursor:pointer; min-height:{T.TARGET_SENTUH}; padding:{T.SP_2} 0; line-height:1.5; overflow-wrap:anywhere; }}
.panduan-variasi p,.variasi-kode p {{ line-height:1.6; overflow-wrap:anywhere; }}
.variasi-materi {{ border-top:1px solid {T.BORDER_HALUS}; padding:{T.SP_2} 0; }}
.variasi-daftar {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,18rem),1fr)); gap:{T.SP_4}; }}
.variasi-contoh {{ min-width:0; border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KECIL}; padding:{T.SP_3}; }}
.variasi-contoh h4 {{ margin:0; color:{T.TEKS_JUDUL}; }}
.variasi-soal {{ overflow-x:auto; padding:{T.SP_3} 0; }}
.variasi-soal svg {{ max-width:100%; height:auto; }}
.pengaturan-awal {{ border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KECIL}; margin:{T.SP_4} 0; padding:{T.SP_4}; min-width:0; }}
"""
