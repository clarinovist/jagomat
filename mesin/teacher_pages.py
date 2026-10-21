"""Façade kompatibel halaman guru: workspace, sesi, review, dan lembar.

Router HTTP tetap di web.py. Bingkai/topbar dimiliki ``teacher_shell.py``
dan di-re-export di sini agar caller lama tetap bekerja. Aturan lama tetap:
modul ini tidak boleh mengimpor students di atas file (impor terlambat di
fungsi yang membutuhkannya).
"""

from __future__ import annotations

import html
import random
import design_tokens as T
import database
import domain_clock
import question_views
import teacher_home_priority
import worksheets
from generator import LEVEL_BAWAAN
from topics import TOPIK_BAWAAN, ambil
from template_labels import nama_tipe_soal as _nama_template
from templates import Soal
from teacher_corrections import KODE_PILIHAN
from teacher_shell import (
    _halaman,
    _halaman_stitch,
    _topbar,
    _topbar_stitch,
)
from teacher_print_pages import (
    _pil_sesi,
    _tombol_cerita,
    halaman_bagikan_sesi,
    halaman_konfirmasi_hapus,
    halaman_sesi_cetak,
    halaman_sesi_lampiran,
    halaman_lembar as _halaman_lembar_impl,
)
from teacher_review_service import simpan_sesi as _simpan_sesi_impl
from teacher_session_pages import (
    _badge_mode,
    _blok_latihan_serupa,
    _label_tahap_sesi,
    _pil_sesi_stitch,
    halaman_sesi_stitch as _halaman_sesi_stitch_impl,
)
from teacher_workspace import (
    INFO_LATIHAN_BEBAS,
    LABEL_KODE_REMEDIAL,
    _ambil,
    _badge_review_status,
    _kelas_sekolah_profil,
    _kontrol_mode_sesi,
    _kontrol_profil_parameter,
    _fmt_durasi,
    _form_remedial,
    _mode_sesi,
    _nama_topik_sesi,
    _ringkasan_angka_sesi,
    _tanggal_ringkas,
    _topik_untuk_level,
    halaman_anak,
)


# Satu sumber teks bubble ikon "ⓘ" beranda guru: dipakai sebagai aria-label
# tombol sekaligus isi bubble supaya pembaca layar dan mata membaca hal sama.
INFO_DAFTAR_ANAK = (
    "Setiap anak punya halaman sendiri: buat latihan, rencana belajar, "
    "dan riwayat."
)



def _soal_dari_baris(baris) -> Soal:
    """Wrapper kompatibilitas menuju adapter pembaca penyajian sesi."""
    return question_views.soal_dari_baris(baris)




def _daftar_anak_berkelompok(baris) -> str:
    """Kartu anak per kelompok kerja guru; urutan dan label dari reducer."""
    kartu = {langkah.siswa_id: isi for langkah, isi in baris}
    urut = teacher_home_priority.urutkan([langkah for langkah, _ in baris])
    bagian = []
    for kelompok in sorted({langkah.kelompok for langkah in urut}):
        anggota = [kartu[a.siswa_id] for a in urut if a.kelompok == kelompok]
        bagian.append(
            f'<section class="guru-kelompok-bagian-st" aria-labelledby="kelompok-{kelompok}">'
            f'<h3 class="guru-kelompok-st" id="kelompok-{kelompok}">'
            f'{teacher_home_priority.JUDUL_KELOMPOK[kelompok]} <span>{len(anggota)}</span></h3>'
            f'<div class="daftar-anak">{"".join(anggota)}</div></section>'
        )
    return "".join(bagian)


GAYA_FILTER_GURU = f'''
.guru-filter-st {{ display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1fr) auto;
  gap:{T.SP_3}; align-items:end; margin:{T.SP_4} 0; padding:{T.SP_4};
  border:{T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius:{T.RADIUS_SEDANG}; }}
.guru-filter-st label {{ display:block; margin-bottom:{T.SP_2}; color:{T.TEKS_UTAMA}; }}
.guru-filter-st > div {{ min-width:0; }}
.guru-filter-st input, .guru-filter-st select {{ width:100%; min-width:0;
  box-sizing:border-box; min-height:{T.TARGET_SENTUH}; font:inherit; padding:{T.SP_2};
  color:{T.TEKS_UTAMA}; background:{T.LATAR_KARTU}; border:{T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; }}
.guru-filter-aksi-st {{ display:flex; gap:{T.SP_3}; align-items:center; flex-wrap:wrap; }}
.guru-filter-aksi-st button, .guru-filter-aksi-st a {{ min-height:{T.TARGET_SENTUH};
  display:inline-flex; align-items:center; justify-content:center; font:inherit; }}
.guru-filter-aksi-st a {{ color:{T.AKSEN_TEAL_TUA}; padding-inline:{T.SP_2}; }}
.guru-filter-aksi-st button {{ padding:{T.SP_2} {T.SP_4}; background:{T.AKSEN_TEAL_TUA};
  color:{T.TEKS_PUTIH}; border:0; border-radius:{T.RADIUS_KECIL}; cursor:pointer; }}
.guru-filter-st :is(input, select, button, a):focus-visible {{
  outline:{T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset:2px; }}
.guru-hasil-filter-st {{ color:{T.TEKS_VARIAN}; margin:{T.SP_3} 0 {T.SP_4}; }}
.guru-beranda-st .guru-langkah-st, .guru-beranda-st .guru-status-st {{ overflow-wrap:anywhere; }}
@media (max-width:36rem) {{
  .guru-filter-st {{ grid-template-columns:minmax(0, 1fr); }}
  .guru-filter-aksi-st button {{ flex:1; }}
  .guru-beranda-st .guru-sapaan-st {{ padding:{T.SP_4} 0 {T.SP_5}; }}
  .guru-beranda-st .guru-kepala-daftar-st {{ align-items:stretch; }}
  .guru-beranda-st .guru-tambah-st {{ width:100%; box-sizing:border-box; }}
  .guru-beranda-st .kartu-anak {{ align-items:start; }}
  .guru-beranda-st .guru-buka-st {{ justify-self:start; }}
}}
'''


def _form_filter_guru(cari, kelompok):
    pilihan = ''.join(
        '<option value="' + nilai + '"' + (' selected' if nilai == kelompok else '')
        + '>' + html.escape(label) + '</option>'
        for nilai, label in teacher_home_priority.PILIHAN_FILTER.items()
    )
    reset = ('<a id="guru-hapus-filter" href="/guru">Hapus filter</a>'
             if cari or kelompok != 'semua' else '')
    return ('<form id="guru-filter" class="guru-filter-st" method="get" action="/guru" role="search">'
            '<div><label for="guru-cari">Cari nama siswa atau akun murid</label>'
            '<input id="guru-cari" name="cari" type="search" maxlength="100" '
            'autocomplete="off" value="' + html.escape(cari, quote=True) + '"></div>'
            '<div><label for="guru-kelompok">Kelompok langkah</label>'
            '<select id="guru-kelompok" name="kelompok">' + pilihan + '</select></div>'
            '<div class="guru-filter-aksi-st"><button type="submit">Terapkan</button>'
            + reset + '</div></form>')


def halaman_utama_stitch(
    kon,
    pesan: str = "",
    pemilik: str | None = None,
    peran: str = "guru",
    sorot: int | None = None,
    cari: str = '',
    kelompok: str = 'semua',
) -> bytes:
    """Beranda pendamping: satu pintu per anak, tanpa keputusan belajar baru.

    Anak dikelompokkan menurut langkah berikutnya dari reducer yang sama dengan
    profil anak (``teacher_home_priority``); status kirim/review hanya ringkasan
    aktivitas, bukan bukti penguasaan.
    """
    baris = []
    cari, kelompok = teacher_home_priority.normalkan_filter(cari, kelompok)
    siswa_sendiri = database.daftar_siswa(kon, pemilik)
    total = len(siswa_sendiri)
    hari_ini = domain_clock.hari_wib()
    for s in siswa_sendiri:
        langkah = teacher_home_priority.langkah_anak(kon, s)
        nama_akun = None
        if cari:
            # Lookup existing hanya untuk siswa yang sudah lolos scope pemilik.
            from students import akun_murid_dari_siswa
            nama_akun = akun_murid_dari_siswa(kon, int(s['id']))
        if not teacher_home_priority.cocok_filter(langkah, cari, kelompok, nama_akun):
            continue
        rekap = kon.execute(
            """SELECT COUNT(*) AS jumlah,
                      SUM(CASE WHEN dibatalkan IS NOT NULL
                          THEN 1 ELSE 0 END) AS dibatalkan,
                      SUM(CASE WHEN dibatalkan IS NULL
                          AND selesai IS NOT NULL AND direview IS NULL
                          THEN 1 ELSE 0 END) AS belum_review,
                      SUM(CASE WHEN dibatalkan IS NULL AND selesai IS NULL
                          THEN 1 ELSE 0 END) AS belum_kirim
               FROM sesi WHERE siswa_id = ?""",
            (s["id"],),
        ).fetchone()
        jumlah_sesi = rekap["jumlah"] or 0
        dibatalkan = rekap["dibatalkan"] or 0
        belum_review = rekap["belum_review"] or 0
        belum_kirim = rekap["belum_kirim"] or 0
        status = []
        if belum_review:
            status.append(f'<span class="guru-status-st periksa">{belum_review} menunggu diperiksa</span>')
        if belum_kirim:
            status.append(f'<span class="guru-status-st">{belum_kirim} belum dikirim</span>')
        if not status:
            if jumlah_sesi == 0:
                ringkasan = "Belum ada sesi"
            elif jumlah_sesi == dibatalkan:
                ringkasan = "Tidak ada latihan yang perlu dikerjakan."
            elif langkah.tindakan == "konfirmasi_hasil":
                # Dibuka bukan dikonfirmasi: jangan tampak selesai; kalimat berupa tindakan.
                ringkasan = "Hasil menunggu Anda tinjau"
            else:
                ringkasan = "semua direview"
            status.append(f'<span class="guru-status-st">{ringkasan}</span>')
        label_batal = (
            f'<span>{dibatalkan} dibatalkan</span>' if dibatalkan else ""
        )
        label_keluarga = ""
        if peran == "admin":
            label_keluarga = f'<span>keluarga: {html.escape(s["pemilik"] or "warisan")}</span>'
        nama = str(s["nama"])
        from learning_profile import label_kelas_sekolah
        kelas_sekolah = _kelas_sekolah_profil(kon, s)
        tujuan_anak = f'/anak/{s["id"]}'
        baris.append((langkah,
            f'<a class="st-kartu kartu-anak" href="{tujuan_anak}">'
            f'<span class="guru-inisial-st" aria-hidden="true">{html.escape(nama[:1].upper())}</span>'
            '<div class="guru-identitas-st">'
            f'<h3 class="guru-nama-st">{html.escape(nama)}</h3>'
            '<div class="guru-meta-st">'
            f'<span>{html.escape(label_kelas_sekolah(kelas_sekolah))}</span>'
            f'<span>{jumlah_sesi} latihan tercatat</span>{label_batal}{label_keluarga}</div>'
            f'<div class="guru-status-daftar-st">{"".join(status)}</div>'
            f'<p class="guru-langkah-st">Langkah: {html.escape(teacher_home_priority.keterangan_langkah(langkah, hari_ini))}</p></div>'
            '<span class="guru-buka-st">Buka profil <span aria-hidden="true">→</span></span>'
            '</a>'
        ))

    tambah = (
        '<a class="guru-tambah-st" href="/akun?section=siswa">'
        '<span aria-hidden="true">＋</span> '
        + ('Tambah anak' if total else 'Tambahkan anak pertama') + '</a>'
    )
    isi_utama = (
        '<div class="guru-kepala-daftar-st"><div>'
        '<p class="guru-alis-st">RUANG BELAJAR MEREKA</p>'
        f'<h2 id="daftar-anak">Anak &amp; siswa <span>{total}</span></h2>'
        f'</div>{tambah}</div>'
        '<p class="guru-petunjuk-st info-baris">Pilih nama untuk mulai. '
        f'<button type="button" class="info" aria-label="{html.escape(INFO_DAFTAR_ANAK, quote=True)}">'
        f'i<span class="info-bubble" role="tooltip">{html.escape(INFO_DAFTAR_ANAK)}</span></button></p>'
        + _form_filter_guru(cari, kelompok)
        + f'<p class="guru-hasil-filter-st" role="status">{len(baris)} dari {total} siswa ditampilkan.</p>'
        + (_daftar_anak_berkelompok(baris) if baris else
           '<p class="guru-hasil-kosong-st">Tidak ada siswa yang cocok. Ubah pencarian atau kelompok.</p>')
    ) if total else (
        '<div class="guru-kosong-st">'
        '<p class="guru-alis-st">MULAI DARI SINI</p>'
        '<h2 id="daftar-anak">Kenali langkah pertama mereka.</h2>'
        '<p>Akunmu sudah siap. Tambahkan anak dengan nama panggilan, '
        'lalu buka profilnya untuk mulai mendampingi belajar.</p>'
        f'{tambah}<p class="guru-petunjuk-st">Belum ada latihan. '
        'Langkah berikutnya akan tersedia di profil anak.</p>'
        + (_form_filter_guru(cari, kelompok) if cari or kelompok != 'semua' else '') + '</div>'
    )
    kabar = (
        '<div class="st-banner-sukses" role="status"><span class="ikon" aria-hidden="true">✓</span>'
        f'<span>{html.escape(pesan)}</span></div>' if pesan else ''
    )
    return _halaman_stitch(
        "Ruang pendamping",
        f'<style>{GAYA_FILTER_GURU}</style><main aria-labelledby="judul-guru">'
        '<header class="guru-sapaan-st"><div>'
        '<p class="guru-alis-st">RUANG PENDAMPING</p>'
        '<h1 id="judul-guru">Langkah kecil,<br><span>tumbuh bersama.</span></h1>'
        '<p>Temani prosesnya, bukan hanya hasilnya.<br>'
        'Mulai dari ruang belajar anak di bawah ini.</p></div>'
        '<div class="guru-catatan-st" aria-hidden="true">'
        '<span class="guru-coret-st">✳</span>'
        '<img src="/aset/maskot-membaca-v3-240.png" width="240" height="240" alt="">'
        '<span>Satu langkah yang berarti.</span></div></header>'
        f'{kabar}<section aria-labelledby="daftar-anak">{isi_utama}</section>'
        '<footer class="guru-kaki-st"><span aria-hidden="true">✳</span> '
        'Beri ruang untuk mencoba, bertanya, dan menjelaskan.</footer></main>',
        ident=(pemilik if pemilik else "guru", peran),
        kelas_bungkus="guru-beranda-st",
    )


















def halaman_lembar(kon, sesi_id: int, untuk_guru: bool = False) -> bytes | None:
    """Façade lembar dengan lookup renderer dan adapter soal tetap runtime."""
    return _halaman_lembar_impl(
        kon, sesi_id, untuk_guru, soal_dari_baris=_soal_dari_baris,
        worksheets_module=worksheets,
    )


def halaman_sesi_stitch(
    kon, sesi_id: int, pesan: str = "", peran: str = "guru",
    pengguna: str = "", bantuan: str = "", bantuan_nomor: int | None = None,
    draf_koreksi=None,
    privat: bool = False,
    masalah_konfirmasi=(),
) -> bytes:
    """Façade renderer sesi dengan lookup adapter soal tetap runtime."""
    return _halaman_sesi_stitch_impl(
        kon, sesi_id, pesan=pesan, peran=peran, pengguna=pengguna,
        bantuan=bantuan, bantuan_nomor=bantuan_nomor,
        draf_koreksi=draf_koreksi, privat=privat,
        masalah_konfirmasi=masalah_konfirmasi,
        soal_dari_baris=_soal_dari_baris,
    )



def simpan_sesi(
    kon, sesi_id: int, data: dict, *, tinjauan_disimpan: bool = False,
    guru: str = 'guru',
) -> str:
    """Façade layanan koreksi dengan lookup adapter soal tetap runtime."""
    return _simpan_sesi_impl(
        kon, sesi_id, data, tinjauan_disimpan=tinjauan_disimpan, guru=guru,
        soal_dari_baris=_soal_dari_baris,
    )


def buat_sesi_seed_baru(
    kon,
    siswa_id: int,
    level: str | None = None,
    topik: str | None = None,
    mode: str = "diagnostik",
    timer_mode: str = "tanpa",
    durasi_menit: int = 15,
    timer_auto: int = 0,
    jumlah_soal: int | None = None,
    format_jawaban: str = 'isian',
) -> int:
    """Sesi baru dengan seed yang belum pernah dipakai siswa ini."""
    if level is None:
        baris = kon.execute(
            "SELECT tingkat FROM siswa WHERE id = ?", (siswa_id,)
        ).fetchone()
        level = baris["tingkat"] if baris else LEVEL_BAWAAN
    if topik is None:
        topik = TOPIK_BAWAAN
    else:
        ambil(topik)  # validasi awal: gagal cepat sebelum menyentuh basis data

    dipakai = {
        r["seed"]
        for r in kon.execute(
            "SELECT seed FROM sesi WHERE siswa_id = ?", (siswa_id,)
        ).fetchall()
    }
    for _ in range(500):
        seed = random.randint(1, 9_999_999)
        if seed not in dipakai:
            return database.buat_sesi(
                kon, siswa_id, seed, level=level, topik=topik, mode=mode,
                timer_mode=timer_mode, durasi_menit=durasi_menit,
                timer_auto=timer_auto, jumlah_soal=jumlah_soal, format_jawaban=format_jawaban,
            )
    raise RuntimeError("gagal menemukan seed baru")
