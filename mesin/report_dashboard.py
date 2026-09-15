"""Dashboard laporan dan resume rencana; tanpa inferensi pedagogis baru."""
from __future__ import annotations

import html
from datetime import timedelta

import design_tokens as T
from cycle_report import JENIS, judul_tindakan, render_perjalanan
from report_summary import _langkah, _perlu_diperiksa, _terlihat
from templates import label_kelas


GAYA_LAPORAN = f"""
.laporan-editorial-st .laporan-metrik {{
  display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:{T.SP_4};
  margin:{T.SP_5} 0;
}}
.laporan-editorial-st .laporan-metrik .stat {{
  padding:{T.SP_4}; background:{T.LATAR_KARTU}; border:1px solid {T.BORDER_HALUS};
  border-radius:{T.RADIUS_KARTU}; min-width:0;
}}
.laporan-editorial-st .laporan-metrik strong {{
  display:block; font-size:2rem; color:{T.TEKS_JUDUL}; line-height:1.2;
}}
.laporan-editorial-st .laporan-metrik span {{display:block; margin-top:{T.SP_2};}}
.laporan-editorial-st .laporan-catatan {{color:{T.TEKS_SUBTLE}; font-size:.9rem;}}
.laporan-editorial-st .laporan-materi {{width:100%; border-collapse:collapse;}}
.laporan-editorial-st .laporan-materi td,.laporan-editorial-st .laporan-materi th {{
  text-align:left; vertical-align:top; padding:{T.SP_3}; border-bottom:1px solid {T.BORDER_HALUS};
}}
.laporan-editorial-st .laporan-materi small {{display:block; color:{T.TEKS_SUBTLE};}}
.laporan-editorial-st .laporan-materi progress {{
  width:100%; max-width:10rem; accent-color:{T.AKSEN_TEAL_TUA}; display:block; margin-top:{T.SP_2};
}}
.laporan-editorial-st .laporan-resume summary,.laporan-editorial-st .laporan-bukti summary {{
  min-height:{T.TARGET_SENTUH}; cursor:pointer; padding:{T.SP_3} 0; font-weight:700;
}}
.laporan-editorial-st .laporan-resume > summary {{
  background:{T.LATAR_KARTU_SEKUNDER}; color:{T.TEKS_JUDUL}; border-radius:{T.RADIUS_KECIL};
  padding:{T.SP_4}; font-size:1.1rem;
}}
.laporan-editorial-st .laporan-resume summary:focus-visible {{outline:2px solid {T.AKSEN_TEAL_TUA};}}
.laporan-editorial-st .aksi-rencana-laporan {{
  display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH};
  background:{T.AKSEN_TEAL_TUA}; color:{T.LATAR_KARTU}; padding:{T.SP_3} {T.SP_4};
  border-radius:{T.RADIUS_KECIL}; font-weight:700; text-decoration:none;
}}
.laporan-editorial-st .laporan-dasar summary {{
  min-height:{T.TARGET_SENTUH}; cursor:pointer; padding:{T.SP_3} 0;
  color:{T.TEKS_JUDUL}; font-weight:600;
}}
.laporan-editorial-st .laporan-seluruh {{border-top:1px solid {T.BORDER_HALUS}; padding-top:{T.SP_3};}}
.laporan-editorial-st .laporan-resume .ringkasan-laporan {{border:0; padding:0; margin:0; box-shadow:none;}}
.laporan-editorial-st .laporan-resume li {{margin-bottom:{T.SP_3};}}
.laporan-editorial-st .laporan-tugas {{padding-left:{T.SP_5};}}
.laporan-editorial-st .laporan-periode {{color:{T.TEKS_SUBTLE};}}
.laporan-editorial-st .editorial-kepala-st h1 {{overflow-wrap:anywhere;}}
@media(max-width:46rem) {{
  .laporan-editorial-st .laporan-metrik {{grid-template-columns:repeat(2,minmax(0,1fr)); gap:{T.SP_3};}}
  .laporan-editorial-st .laporan-materi thead {{position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%);}}
  .laporan-editorial-st .laporan-materi,.laporan-editorial-st .laporan-materi tbody,
  .laporan-editorial-st .laporan-materi tr,.laporan-editorial-st .laporan-materi td {{display:block;}}
  .laporan-editorial-st .laporan-materi tr {{padding:{T.SP_3} 0; border-bottom:1px solid {T.BORDER_HALUS};}}
  .laporan-editorial-st .laporan-materi td {{border:0; padding:{T.SP_2} 0; overflow-wrap:anywhere;}}
  .laporan-editorial-st .laporan-materi td::before {{content:attr(data-label) ' '; font-weight:600;}}
}}
"""


def persen(nilai) -> str:
    """Tampilkan presisi terbatas tanpa memalsukan hasil sempurna/nol."""
    if nilai is None:
        return "—"
    if 99.9 < nilai < 100:
        return "<100%"
    if 0 < nilai < 0.1:
        return "<0,1%"
    return f"{nilai:.1f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


def _hasil(hitungan) -> str:
    return f"{html.escape(persen(hitungan.persen))} · {hitungan.benar}/{hitungan.dinilai} soal dinilai"


def _perubahan(materi) -> str:
    if not materi.sebanding:
        return "Belum cukup data sebanding"
    beda = materi.kini.persen - materi.lalu.persen
    arah = "Naik" if beda > 0 else "Turun" if beda < 0 else "Tetap"
    angka = ("<0,1" if 0 < abs(beda) < 0.1 else
             f"{abs(beda):.1f}".rstrip("0").rstrip(".").replace(".", ","))
    return f"{arah} {angka} poin persentase"


def render_aktivitas(data, tanggal) -> str:
    kini = data.kini
    kartu = "".join(
        f'<div class="stat"><strong>{nilai}</strong><span>{label}</span></div>'
        for nilai, label in (
            (str(kini.dikerjakan), "soal dikerjakan"),
            (str(kini.benar), "butir benar"),
            (str(kini.salah), "butir salah"),
            (html.escape(persen(kini.persen)), "jawaban benar dari yang dinilai"),
        )
    )
    catatan_tanggal = (
        f'<p class="laporan-catatan">{data.tanpa_tanggal} catatan tanpa tanggal valid '
        'hanya masuk total seluruh catatan, bukan periode mingguan.</p>'
        if data.tanpa_tanggal else ""
    )
    return (
        '<section aria-labelledby="judul-aktivitas">'
        '<h2 id="judul-aktivitas">Aktivitas 7 hari terakhir</h2>'
        f'<p class="laporan-periode">{tanggal(data.mulai.isoformat())} – '
        f'{tanggal(data.akhir.isoformat())} · WIB</p>'
        f'<div class="kartu-stat laporan-metrik">{kartu}</div>'
        '<p class="laporan-catatan">'
        f'{kini.perlu_ditinjau} jawaban perlu ditinjau · '
        f'{kini.belum_dikenalkan} perlu cek pengenalan materi · {kini.dilewati} dilewati.</p>'
        f'<p class="laporan-catatan">Dari {kini.dinilai} butir dinilai, '
        f'{kini.terkonfirmasi} sudah dikonfirmasi; '
        f'{kini.dinilai - kini.terkonfirmasi} masih sementara. '
        'Persentase = benar ÷ (benar + salah).</p>'
        '<details class="laporan-dasar"><summary>Dasar hitungan dan total seluruh catatan</summary>'
        '<p class="laporan-catatan">Belum dinilai, menebak, perlu cek pengenalan, dan dilewati '
        'tidak dihitung sebagai salah. Perlu cek pengenalan bisa berarti belum belajar atau '
        'mengaku bingung; bukan kepastian materi belum diajarkan. Semua latihan, termasuk sesi berjalan. '
        'Dikerjakan berarti ada jawaban atau coretan cara; memilih status saja belum dihitung. '
        'Kerja yang perlu cek pengenalan atau dilewati tetap masuk aktivitas, bukan hasil benar/salah. Tanggal mengikuti '
        'pencatatan pertama; hasil kertas mengikuti waktu input, bukan waktu pengerjaan sebenarnya. '
        'Koreksi dapat mengubah hasil statistik, bukan menambah jumlah soal dikerjakan.</p>'
        f'<p class="laporan-catatan laporan-seluruh">Total seluruh catatan: <b>{data.semua.dikerjakan} soal dikerjakan</b> '
        f'· {data.semua.benar} benar · {data.semua.salah} salah '
        f'· {data.semua.perlu_ditinjau} perlu ditinjau.</p>{catatan_tanggal}</details></section>'
    )


def render_materi(data, nama_tipe, tanggal) -> str:
    baris = []
    for materi in data.materi:
        tipe, kelas, mode, tujuan, representasi = materi.kunci
        konteks = ' · '.join((label_kelas(kelas), "Latihan cepat" if mode == "drill" else "Diagnostik",
                              JENIS.get(tujuan, "Latihan"), "Visual" if representasi != "teks-v1" else "Teks"))
        hitungan = materi.kini
        meter = (
            f'<progress max="100" value="{hitungan.persen:.4f}" '
            f'aria-label="Persentase jawaban benar {html.escape(nama_tipe(tipe), quote=True)}">'
            f'{html.escape(persen(hitungan.persen))}</progress>' if hitungan.persen is not None else ""
        )
        baris.append(
            '<tr><td data-label="Materi:">'
            f'<b>{html.escape(nama_tipe(tipe))}</b><small>{html.escape(konteks)}</small></td>'
            f'<td data-label="7 hari terakhir:">{_hasil(hitungan)}{meter}'
            f'<small>{hitungan.dikerjakan} dikerjakan · {hitungan.perlu_ditinjau} perlu ditinjau '
            f'· {hitungan.belum_dikenalkan} perlu cek pengenalan · {hitungan.dilewati} dilewati</small></td>'
            f'<td data-label="7 hari sebelumnya:">{_hasil(materi.lalu)}</td>'
            f'<td data-label="Perubahan:">{html.escape(_perubahan(materi))}</td></tr>'
        )
    isi = (
        '<table class="laporan-materi"><caption class="sr-only">Hasil dan perubahan per materi</caption>'
        '<thead><tr><th scope="col">Materi dan jenis latihan</th><th scope="col">7 hari terakhir</th>'
        '<th scope="col">7 hari sebelumnya</th><th scope="col">Perubahan</th></tr></thead>'
        '<tbody>' + ''.join(baris) + '</tbody></table>' if baris else
        '<p>Belum ada aktivitas tercatat pada dua periode ini. Materi belum dicoba bukan berarti belum dikuasai.</p>'
    )
    awal_lalu = data.mulai - timedelta(days=7)
    akhir_lalu = data.mulai - timedelta(days=1)
    return (
        '<section class="kartu" aria-labelledby="judul-hasil-materi">'
        '<h2 id="judul-hasil-materi">Hasil dan tren per materi</h2>'
        f'<p class="laporan-catatan">Pembanding: {tanggal(awal_lalu.isoformat())} – '
        f'{tanggal(akhir_lalu.isoformat())}. {len(data.sebanding)} kelompok latihan memiliki data sebanding.</p>'
        f'{isi}<p class="laporan-catatan">Persentase adalah hasil jawaban, bukan persentase pemahaman. '
        'Tanda — berarti belum ada jawaban yang bisa dinilai.</p>'
        '<details class="laporan-dasar"><summary>Dasar perbandingan</summary>'
        '<p class="laporan-catatan">Perubahan hanya dibandingkan pada tipe soal, kelas, jenis latihan, tujuan, dan representasi yang sama, '
        'dengan minimal 5 butir dinilai per periode. Ini batas kecukupan tampilan, bukan bukti peningkatan kemampuan. '
        'Jumlah soal dasar selalu ditampilkan; komposisi kelompok tidak digabung menjadi skor penguasaan.</p>'
        '<p class="laporan-catatan">Contoh cara baca: 80% menjadi 85% berarti naik 5 poin persentase. '
        'Status pemahaman dan jadwal pemeriksaan ada di rencana belajar.</p>'
        '</details></section>'
    )


def render_resume(perjalanan, tugas, siswa_id, nama_tipe, nama_topik, tanggal) -> str:
    rencana = perjalanan.rekomendasi
    daftar = []
    for satu in tugas:
        label = f'Sesi #{satu["id"]} · {nama_topik(satu["topik"])} · {label_kelas(satu["level"])}'
        # CTA utama sudah menuju sesi ini; hindari entry point ganda.
        nama = html.escape(label)
        if satu["id"] != rencana.sesi_id:
            nama = f'<a href="/sesi/{int(satu["id"])}">{nama}</a>'
        daftar.append(f'<li>{nama}: {satu["terisi"]}/{satu["tersedia"]} soal terisi.</li>')
    belum = ('<ul class="laporan-tugas">' + ''.join(daftar) + '</ul>' if daftar else
             '<p>Tidak ada sesi latihan yang belum selesai.</p>')
    materi = tuple(dict.fromkeys(kunci[0] for kunci in rencana.kandidat))
    materi_html = (
        '<p>Materi berikutnya: <b>' + ', '.join(html.escape(nama_tipe(t)) for t in materi) + '</b>.</p>'
        if materi else ""
    )
    if rencana.tindakan in {"lanjutkan_sesi", "konfirmasi_hasil"} and rencana.sesi_id:
        tujuan = f'/sesi/{int(rencana.sesi_id)}'
        label = "Lanjutkan latihan" if rencana.tindakan == "lanjutkan_sesi" else "Tinjau hasil latihan"
    else:
        tujuan = f'/anak/{int(siswa_id)}#judul-rencana-belajar'
        label = "Buka langkah belajar ini"
    return (
        '<details class="kartu laporan-resume" id="rencana-belajar-laporan">'
        '<summary>Lihat rencana belajar</summary>'
        '<div class="kartu ringkasan-laporan">'
        '<h2>Rencana belajar berikutnya</h2>'
        '<h3>Belum selesai dikerjakan</h3>' + belum +
        '<p class="laporan-catatan">Terisi juga mencakup pilihan status, bukan berarti selesai dikerjakan. '
        'Latihan manual atau kelas lama tidak menghalangi langkah utama.</p>'
        '<section><h3>Posisi belajar saat ini</h3>' + _terlihat(perjalanan, nama_tipe) + '</section>'
        '<section><h3>Masih perlu diperiksa</h3>' + _perlu_diperiksa(perjalanan, nama_tipe) + '</section>'
        '<section><h3>Berikutnya dipelajari</h3>'
        f'{materi_html}<p>{_langkah(perjalanan, tanggal)}</p></section>'
        f'<a class="tombol aksi-rencana-laporan" href="{tujuan}">{label}</a>'
        '</div></details>'
        '<details class="kartu laporan-bukti"><summary>Perjalanan dan bukti belajar</summary>'
        + render_perjalanan(perjalanan, nama_tipe, tanggal) + '</details>'
    )
