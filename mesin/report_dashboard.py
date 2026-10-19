"""Dashboard laporan dan resume rencana; tanpa inferensi pedagogis baru."""
from __future__ import annotations

import html
from datetime import timedelta

import design_tokens as T
from cycle_report import JENIS, judul_tindakan
from report_summary import _langkah, _perlu_diperiksa, _terlihat
from templates import label_kelas
from report_navigation import halaman_daftar, navigasi_halaman, url_laporan


GAYA_LAPORAN = f"""
.pendamping-editorial-st.laporan-editorial-st.profil-workspace-st {{max-width:60rem;}}
.laporan-editorial-st .laporan-ke-beranda {{display:block;margin-top:{T.SP_5};padding:{T.SP_4};border-radius:{T.RADIUS_KARTU};background:{T.LATAR_TERSIMPAN};text-decoration:none;}}
.laporan-editorial-st .riwayat-putaran-detail > summary {{min-height:{T.TARGET_SENTUH};cursor:pointer;padding:{T.SP_3} 0;}}
.laporan-editorial-st .laporan-alias {{display:none;}}
.laporan-editorial-st .laporan-alias:target {{display:block;}}

.laporan-editorial-st .laporan-bagian-st {{margin-top:{T.SP_5};}}
.laporan-editorial-st .laporan-bagian-st:first-of-type {{margin-top:0;}}
.laporan-editorial-st .laporan-lipatan-st {{min-width:0;}}
.laporan-editorial-st .aktivitas-kartu-st {{
  margin-top:{T.SP_5}; padding:{T.SP_5}; background:{T.LATAR_KARTU};
  border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU_BESAR};
}}
.laporan-editorial-st .aktivitas-kepala-st {{display:flex;align-items:start;justify-content:space-between;gap:{T.SP_4};}}
.laporan-editorial-st .aktivitas-kepala-st h2 {{margin:0;}}
.laporan-editorial-st .aktivitas-periode-st {{margin:0;color:{T.TEKS_SUBTLE};font-size:{T.UKURAN_TEKS_BANTUAN};}}
.laporan-editorial-st .laporan-metrik {{
  display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:{T.SP_3};
  margin:{T.SP_4} 0;
}}
.laporan-editorial-st .laporan-metrik .stat {{
  padding:{T.SP_4}; background:{T.LATAR_SEKUNDER_LEMBUT};
  border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS};
  border-radius:{T.RADIUS_SEDANG}; min-width:0;
}}
.laporan-editorial-st .laporan-periode-kontrol {{ display:flex; flex-wrap:wrap; align-items:start; gap:{T.SP_3}; }}
.laporan-editorial-st .laporan-pilih-tanggal > summary {{ min-height:{T.TARGET_SENTUH}; padding:{T.SP_2} {T.SP_3}; cursor:pointer; color:{T.AKSEN_TEAL_TUA}; }}
.laporan-editorial-st .laporan-pilih-tanggal[open] {{ flex-basis:100%; }}
.laporan-editorial-st .laporan-metrik strong {{
  display:block; font-size:{T.UKURAN_ANGKA_DEWASA}; color:{T.TEKS_JUDUL}; line-height:1.2;
}}
.laporan-editorial-st .laporan-metrik span {{display:block; margin-top:{T.SP_2};}}
.laporan-editorial-st .aktivitas-komposisi-st {{display:flex;height:.65rem;overflow:hidden;border-radius:{T.RADIUS_PIL};background:{T.LATAR_NONAKTIF};}}
.laporan-editorial-st .aktivitas-benar-st {{background:{T.AKSEN_TEAL_TUA};}}
.laporan-editorial-st .aktivitas-salah-st {{background:{T.AKSEN_KORAL_TUA};}}
.laporan-editorial-st .laporan-insight-st {{display:grid;grid-template-columns:auto minmax(0,1fr);gap:{T.SP_3};align-items:start;margin-top:{T.SP_4};padding:{T.SP_4};background:{T.LATAR_CATATAN};border:{T.TEBAL_GARIS} solid {T.BORDER_CATATAN};border-radius:{T.RADIUS_SEDANG};}}
.laporan-editorial-st .perjalanan-pilot-st {{margin-top:{T.SP_5};}}
.laporan-editorial-st .laporan-insight-ikon-st {{display:grid;place-items:center;width:2rem;height:2rem;border-radius:{T.RADIUS_PIL};background:{T.AKSEN_MURID_AMBER};color:{T.TEKS_JUDUL};font-weight:800;}}
.laporan-editorial-st .laporan-insight-st p {{margin:0;}}
.laporan-editorial-st .laporan-catatan {{color:{T.TEKS_SUBTLE}; font-size:{T.UKURAN_TEKS_BANTUAN};}}
.laporan-editorial-st .laporan-materi {{width:100%; border-collapse:collapse;}}
.laporan-editorial-st .laporan-materi td,.laporan-editorial-st .laporan-materi th {{
  text-align:left; vertical-align:top; padding:{T.SP_3}; border-bottom:{T.TEBAL_GARIS} solid {T.BORDER_HALUS};
}}
.laporan-editorial-st .laporan-materi small {{display:block; color:{T.TEKS_SUBTLE};}}
.laporan-editorial-st .laporan-materi progress {{
  width:100%; max-width:10rem; accent-color:{T.AKSEN_TEAL_TUA}; display:block; margin-top:{T.SP_2};
}}
.laporan-editorial-st .laporan-navigasi {{
  display:flex; flex-wrap:wrap; gap:{T.SP_1}; width:fit-content; margin:0 0 {T.SP_5};
  padding:{T.SP_1}; border:1px solid {T.BORDER_HALUS}; border-radius:{T.RADIUS_KARTU}; background:{T.LATAR_SEKUNDER_LEMBUT};
}}
.laporan-editorial-st .laporan-navigasi a {{
  display:inline-flex; align-items:center; justify-content:center; min-height:{T.TARGET_SENTUH};
  padding:{T.SP_2} {T.SP_4}; border:0; border-radius:{T.RADIUS_KECIL}; text-decoration:none;
  color:{T.TEKS_VARIAN}; font-weight:600;
}}
.laporan-editorial-st .laporan-navigasi a[aria-current="page"] {{
  background:{T.LATAR_KARTU}; color:{T.AKSEN_TEAL_TUA}; box-shadow:{T.BAYANGAN_KARTU_GURU};
}}
.laporan-editorial-st .laporan-resume {{border-top:3px solid {T.AKSEN_TEAL_TUA};}}
.laporan-editorial-st .resume-langkah {{font-size:1.12rem; font-weight:600;}}
.laporan-editorial-st .resume-konteks {{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:{T.SP_5};
  border-top:{T.TEBAL_GARIS} solid {T.BORDER_CATATAN};margin-top:{T.SP_5};padding-top:{T.SP_3};
}}
.laporan-editorial-st .laporan-mingguan > section {{border:0;padding:0;margin:{T.SP_4} 0 0;}}
.laporan-editorial-st .laporan-dasar {{border-top:{T.TEBAL_GARIS} solid {T.BORDER_CATATAN};margin-top:{T.SP_4};padding-top:{T.SP_3};}}
.laporan-editorial-st .laporan-materi {{overflow-wrap:normal;}}
.laporan-editorial-st .tabel-tren table {{min-width:0;table-layout:auto;overflow-wrap:normal;}}
.laporan-editorial-st .tabel-tren th {{white-space:nowrap;}}
.laporan-editorial-st .tabel-tren td {{vertical-align:top;}}
.laporan-editorial-st .tabel-tren th:nth-child(3) {{text-align:right;}}
.laporan-editorial-st .tabel-tren small {{display:block;color:{T.TEKS_SUBTLE};margin-top:{T.SP_1};}}
.laporan-editorial-st .rasio-laporan {{white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:700;}}
.laporan-editorial-st .tabel-tren td:last-child a {{white-space:nowrap;gap:{T.SP_2};}}
.laporan-editorial-st .laporan-metrik .metrik-dasar {{font-size:.8rem;color:{T.TEKS_SUBTLE};}}
.laporan-editorial-st .riwayat-putaran-laporan {{border-top:{T.TEBAL_GARIS} solid {T.BORDER_CATATAN};margin-top:{T.SP_5};}}
.laporan-editorial-st .aksi-rencana-laporan {{
  display:inline-flex; align-items:center; min-height:{T.TARGET_SENTUH};
  background:{T.AKSEN_TEAL_TUA}; color:{T.LATAR_KARTU}; padding:{T.SP_3} {T.SP_4};
  border-radius:{T.RADIUS_KECIL}; font-weight:700; text-decoration:none;
}}
.laporan-editorial-st .laporan-ringkasan-grid {{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:{T.SP_5};align-items:start;}}
.laporan-editorial-st .laporan-ringkasan-grid > section {{margin:0;min-width:0;}}
.laporan-editorial-st .laporan-ringkasan-grid .peta-kepala {{grid-template-columns:minmax(0,1fr);gap:{T.SP_2};}}
.laporan-editorial-st .laporan-ringkasan-grid p {{margin:{T.SP_2} 0;}}
.laporan-editorial-st .laporan-ringkasan-grid .peta-grafik {{height:1.5rem;margin:{T.SP_3} 0;}}
.laporan-editorial-st .laporan-ringkasan-grid .peta-legenda {{font-size:{T.UKURAN_TEKS_BANTUAN};gap:{T.SP_2} {T.SP_3};margin:{T.SP_3} 0;}}
.laporan-editorial-st .laporan-ringkasan-grid .resume-konteks {{margin-top:{T.SP_4};padding-top:{T.SP_2};}}
.laporan-editorial-st .laporan-ringkasan-grid h3 {{margin:{T.SP_2} 0;}}
.laporan-editorial-st .laporan-ringkasan-grid .resume-langkah {{margin:{T.SP_3} 0;}}
.laporan-editorial-st .laporan-ringkasan-grid .resume-konteks {{grid-template-columns:minmax(0,1fr);gap:{T.SP_2};}}
.laporan-editorial-st .laporan-pilihan,.laporan-editorial-st .laporan-paginasi {{display:flex;flex-wrap:wrap;align-items:center;gap:{T.SP_2};margin:{T.SP_3} 0 {T.SP_5};}}
.laporan-editorial-st .laporan-pilihan a,.laporan-editorial-st .laporan-paginasi a,.laporan-editorial-st .laporan-tautan {{display:inline-flex;align-items:center;min-height:{T.TARGET_SENTUH};padding:{T.SP_2} {T.SP_3};}}
.laporan-editorial-st .laporan-pilihan a {{border:{T.TEBAL_GARIS} solid {T.BORDER_HALUS};border-radius:{T.RADIUS_KECIL};background:{T.LATAR_KARTU};text-decoration:none;color:{T.TEKS_SUBTLE};}}
.laporan-editorial-st .laporan-pilihan a[aria-current="true"] {{border:2px solid {T.AKSEN_TEAL_TUA};padding:calc({T.SP_2} - 1px) calc({T.SP_3} - 1px);color:{T.AKSEN_TEAL_TUA};background:{T.LATAR_TERSIMPAN};font-weight:700;}}
.laporan-editorial-st #konten-laporan a:focus-visible {{outline:3px solid {T.AKSEN_TEAL_TUA};outline-offset:3px;}}
.laporan-editorial-st .peta-bukti a,.laporan-editorial-st #perjalanan-belajar li a,.laporan-editorial-st .tabel-tren a {{display:inline-flex;align-items:center;min-height:{T.TARGET_SENTUH};}}
.laporan-editorial-st .perjalanan-kepala-st {{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:{T.SP_2} {T.SP_4};}}
.laporan-editorial-st .perjalanan-kepala-st h2 {{margin:0;}}
.laporan-editorial-st .perjalanan-babak-st {{margin:0;color:{T.TEKS_VARIAN};font-size:{T.UKURAN_TEKS_CATATAN};}}
.laporan-editorial-st .perjalanan-langkah-st {{display:flex;flex-wrap:wrap;align-items:center;gap:{T.SP_3};margin:{T.SP_4} 0;}}
.laporan-editorial-st .perjalanan-titik-baris-st {{display:flex;align-items:center;gap:{T.SP_2};list-style:none;margin:0;padding:0;}}
.laporan-editorial-st .perjalanan-titik-st {{display:flex;align-items:center;justify-content:center;width:2rem;height:2rem;border-radius:{T.RADIUS_BULAT};border:{T.TEBAL_GARIS} solid {T.BORDER_VARIAN};background:{T.LATAR_KARTU};color:{T.TEKS_VARIAN};font-weight:700;font-size:{T.UKURAN_TEKS_LABEL};}}
.laporan-editorial-st .perjalanan-titik-st.selesai {{background:{T.AKSEN_TEAL_TUA};border-color:{T.AKSEN_TEAL_TUA};color:{T.TEKS_PUTIH};}}
.laporan-editorial-st .perjalanan-titik-st.aktif {{border-color:{T.AKSEN_TEAL_TUA};color:{T.AKSEN_TEAL_TUA};box-shadow:0 0 0 3px {T.LATAR_TERSIMPAN};}}
.laporan-editorial-st .perjalanan-langkah-teks-st {{margin:0;font-weight:600;color:{T.TEKS_JUDUL};}}
.laporan-editorial-st .perjalanan-berikut-st {{display:grid;gap:{T.SP_1};margin:{T.SP_3} 0;padding:{T.SP_3} {T.SP_4};border-left:4px solid {T.AKSEN_TEAL_TUA};background:{T.LATAR_SEKUNDER_LEMBUT};border-radius:0 {T.RADIUS_KECIL} {T.RADIUS_KECIL} 0;}}
.laporan-editorial-st .perjalanan-label-st {{color:{T.TEKS_VARIAN};font-size:{T.UKURAN_TEKS_META};text-transform:uppercase;letter-spacing:.06em;}}
.laporan-editorial-st .perjalanan-berikut-st p {{margin:0;font-weight:700;color:{T.TEKS_JUDUL};}}
.laporan-editorial-st .perjalanan-status-st b {{display:inline-block;padding:{T.SP_1} {T.SP_3};border-radius:{T.RADIUS_PIL};background:{T.LATAR_TERSIMPAN};color:{T.AKSEN_TEAL_TUA};font-size:{T.UKURAN_TEKS_LABEL};}}
.laporan-editorial-st .perjalanan-lencana-st {{display:inline-block;padding:{T.SP_1} {T.SP_2};border-radius:{T.RADIUS_KECIL};background:{T.LATAR_CATATAN};color:{T.TEKS_VARIAN};font-size:{T.UKURAN_TEKS_CATATAN};}}
.laporan-editorial-st .perjalanan-jadwal-st {{margin:{T.SP_2} 0;}}
.laporan-editorial-st .perjalanan-catatan-st {{margin:{T.SP_4} 0 0;color:{T.TEKS_SUBTLE};font-size:{T.UKURAN_TEKS_CATATAN};}}
.laporan-editorial-st .perjalanan-garis-waktu-st {{position:relative;margin:0;padding-left:{T.SP_5};}}
.laporan-editorial-st .perjalanan-garis-waktu-st::before {{content:"";position:absolute;left:.35rem;top:.4rem;bottom:{T.SP_4};width:2px;background:{T.BORDER_HALUS};}}
.laporan-editorial-st .perjalanan-riwayat-item-st {{position:relative;padding:0 0 {T.SP_4};border:0;}}
.laporan-editorial-st .perjalanan-riwayat-titik-st {{position:absolute;left:calc(-1 * {T.SP_5} + .35rem);top:.4rem;width:.7rem;height:.7rem;border-radius:{T.RADIUS_BULAT};background:{T.AKSEN_TEAL_TUA};}}
.laporan-editorial-st .perjalanan-riwayat-isi-st {{min-width:0;}}
.laporan-editorial-st .perjalanan-riwayat-meta-st {{margin:{T.SP_1} 0 0;color:{T.TEKS_VARIAN};font-size:{T.UKURAN_TEKS_CATATAN};}}
.laporan-editorial-st #konten-laporan {{min-width:0;}}
.laporan-editorial-st .laporan-paginasi span {{white-space:nowrap;}}
.laporan-editorial-st .laporan-ringkasan-grid .laporan-resume {{background:{T.LATAR_KARTU};}}
.laporan-editorial-st .laporan-resume .ringkasan-laporan {{background:transparent;}}
@media(min-width:46.01rem) and (max-width:63.99rem) {{
 .laporan-editorial-st .laporan-ringkasan-grid {{grid-template-columns:minmax(0,1fr);}}
}}
.laporan-editorial-st .laporan-seluruh {{border-top:{T.TEBAL_GARIS} solid {T.BORDER_HALUS}; padding-top:{T.SP_3};}}
.laporan-editorial-st .laporan-resume .ringkasan-laporan {{border:0; padding:0; margin:0; box-shadow:none;}}
.laporan-editorial-st .laporan-resume li {{margin-bottom:{T.SP_3};}}
.laporan-editorial-st .laporan-tugas {{padding-left:{T.SP_5};}}
.laporan-editorial-st .laporan-periode {{color:{T.TEKS_SUBTLE};}}
.laporan-editorial-st .laporan-periode-kontrol {{margin-bottom:{T.SP_4};}}
.laporan-editorial-st .laporan-periode-kontrol .laporan-pilihan {{margin-bottom:{T.SP_3};}}
.laporan-editorial-st .laporan-rentang-form {{display:flex;flex-wrap:wrap;align-items:end;gap:{T.SP_3};}}
.laporan-editorial-st .laporan-rentang-label {{flex-basis:100%;font-size:{T.UKURAN_TEKS_LABEL};color:{T.TEKS_JUDUL};}}
.laporan-editorial-st .laporan-rentang-form label {{display:grid;gap:{T.SP_1};color:{T.TEKS_SUBTLE};font-size:{T.UKURAN_TEKS_CATATAN};}}
.laporan-editorial-st .laporan-rentang-form input {{min-height:{T.TARGET_SENTUH};padding:{T.SP_2};font:inherit;border:{T.TEBAL_GARIS} solid {T.BORDER_VARIAN};border-radius:{T.RADIUS_KECIL};background:{T.LATAR_KARTU};}}
.laporan-editorial-st .laporan-rentang-form button {{min-height:{T.TARGET_SENTUH};}}
.laporan-editorial-st .editorial-kepala-st h1 {{overflow-wrap:anywhere;}}
@media(max-width:{T.BATAS_KOLOM_BACA}) {{
  .laporan-editorial-st .laporan-ringkasan-grid {{grid-template-columns:minmax(0,1fr);}}
  .laporan-editorial-st .aktivitas-kartu-st {{padding:{T.SP_4};}}
  .laporan-editorial-st .aktivitas-kepala-st {{display:block;}}
  .laporan-editorial-st .laporan-metrik {{grid-template-columns:repeat(2,minmax(0,1fr)); gap:{T.SP_3};}}
  .laporan-editorial-st .laporan-rentang-form {{display:grid;grid-template-columns:minmax(0,1fr);}}
  .laporan-editorial-st .laporan-rentang-form button {{width:100%;}}
  .laporan-editorial-st .resume-konteks {{grid-template-columns:minmax(0,1fr);gap:{T.SP_2};}}
  .laporan-editorial-st .laporan-navigasi {{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:{T.SP_2};}}
  .laporan-editorial-st .laporan-navigasi a {{font-size:.85rem;padding:{T.SP_2};text-align:center;}}
  .laporan-editorial-st .tabel-tren td > span {{min-width:0;overflow-wrap:anywhere;}}
  .laporan-editorial-st .tabel-tren td[colspan]::before {{display:none;}}
  .laporan-editorial-st .tabel-tren thead {{display:table-header-group;position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);}}
  .laporan-editorial-st .laporan-materi thead {{position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%);}}
  .laporan-editorial-st .laporan-materi,.laporan-editorial-st .laporan-materi tbody,
  .laporan-editorial-st .laporan-materi tr,.laporan-editorial-st .laporan-materi td {{display:block;}}
  .laporan-editorial-st .laporan-materi tr {{padding:{T.SP_3} 0; border-bottom:{T.TEBAL_GARIS} solid {T.BORDER_HALUS};}}
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


def render_aktivitas(data, tanggal, *, judul='Aktivitas latihan', kontrol='', semua=False) -> str:
    """Hitungan deskriptif tetap sama; satu kalimat, tanpa grafik penguasaan kedua."""
    kini = data.semua if semua else data.kini
    kartu = ''.join(
        f'<div class="stat"><strong>{nilai}</strong><span>{label}</span></div>'
        for nilai, label in (
            (kini.dikerjakan, 'soal dikerjakan'), (kini.benar, 'benar'),
            (kini.salah, 'salah'), (kini.perlu_ditinjau, 'menunggu tinjauan'),
        )
    )
    rentang = ('Semua waktu' if semua else
               f'{tanggal(data.mulai.isoformat())} – {tanggal(data.akhir.isoformat())} · WIB')
    if kini.dikerjakan or kini.dinilai:
        kalimat = (f'Dari {kini.dinilai} soal yang sudah dinilai, {kini.benar} benar. '
                   f'Ini bukan persentase pemahaman: {kini.perlu_ditinjau} soal masih menunggu tinjauan.')
    else:
        kalimat = 'Belum ada latihan pada rentang ini. Ini bukan tanda anak tidak mampu.'
    tambahan = []
    if kini.belum_dikenalkan:
        tambahan.append(f'{kini.belum_dikenalkan} perlu cek pengenalan materi')
    if kini.dilewati:
        tambahan.append(f'{kini.dilewati} dilewati')
    rincian = '<p class="laporan-catatan">' + ' · '.join(tambahan) + '.</p>' if tambahan else ''
    sementara = ('<span class="laporan-catatan">Hasil sementara</span>'
                 if kini.dinilai > kini.terkonfirmasi else '')
    return (
        '<section class="aktivitas-kartu-st" aria-labelledby="judul-aktivitas">'
        f'<h2 id="judul-aktivitas">{html.escape(judul)}</h2>'
        + kontrol + f'<p class="aktivitas-periode-st">{rentang}</p>'
        f'<div class="kartu-stat laporan-metrik">{kartu}</div>'
        + sementara + '<p class="laporan-catatan">' + kalimat + '</p>' + rincian
        + '<details class="rincian-ui-st"><summary>Tentang catatan aktivitas</summary>'
        '<p>Aktivitas mengikuti pencatatan jawaban pertama atau konfirmasi untuk butir tanpa jawaban, '
        'bukan tanggal sesi. Angka benar/salah adalah catatan latihan, bukan penguasaan materi.</p>'
        '</details></section>'
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
        '<section class="kartu-st" aria-labelledby="judul-hasil-materi">'
        '<h2 id="judul-hasil-materi">Hasil dan tren per materi</h2>'
        f'<p class="laporan-catatan">Periode kini: {tanggal(data.mulai.isoformat())} – '
        f'{tanggal(data.akhir.isoformat())} · WIB.</p>'
        '<p class="laporan-catatan">Berdasarkan tanggal pencatatan jawaban pertama, '
        'atau tanggal konfirmasi jika tidak ada jawaban. Bukan tanggal sesi. '
        'Tampilan ini selalu membandingkan 7 hari terakhir dengan 7 hari sebelumnya, '
        'untuk semua topik; filter pada tampilan Sesi tidak berlaku di sini.</p>'
        f'<p class="laporan-catatan">Pembanding: {tanggal(awal_lalu.isoformat())} – '
        f'{tanggal(akhir_lalu.isoformat())}. {len(data.sebanding)} kelompok latihan memiliki data sebanding.</p>'
        f'{isi}<p class="laporan-catatan">Persentase adalah hasil jawaban, bukan persentase pemahaman. '
        'Tanda — berarti belum ada jawaban yang bisa dinilai.</p>'
        '<div class="laporan-dasar"><h3>Dasar perbandingan</h3>'
        '<p class="laporan-catatan">Perubahan hanya dibandingkan pada tipe soal, kelas, jenis latihan, tujuan, dan representasi yang sama, '
        'dengan minimal 5 butir dinilai per periode. Ini batas kecukupan tampilan, bukan bukti peningkatan kemampuan. '
        'Jumlah soal dasar selalu ditampilkan; komposisi kelompok tidak digabung menjadi skor penguasaan.</p>'
        '<p class="laporan-catatan">Contoh cara baca: 80% menjadi 85% berarti naik 5 poin persentase. '
        'Status pemahaman dan jadwal pemeriksaan ada di rencana belajar.</p>'
        '</div></section>'
    )


def render_tugas(tugas, siswa_id, nama_topik, halaman='1') -> str:
    """Tugas sekunder dipilih lewat URL; tidak menentukan CTA utama."""
    bagian, nomor, jumlah = halaman_daftar(tugas, halaman, 20)
    daftar = ''.join(
        f'<li><a class="laporan-tautan" href="/sesi/{int(satu["id"])}">'
        f'Sesi #{satu["id"]} · {html.escape(nama_topik(satu["topik"]))} · '
        f'{html.escape(label_kelas(satu["level"]))}</a>: '
        f'<span class="rasio-laporan">{satu["terisi"]}/{satu["tersedia"]}</span> soal terisi.</li>'
        for satu in bagian
    )
    return (
        f'<a class="laporan-tautan" href="{url_laporan(siswa_id)}">← Kembali ke ringkasan</a>'
        '<section class="kartu-st" id="rincian-tugas"><h2>Belum selesai dikerjakan '
        f'({len(tugas)} sesi)</h2>'
        + ('<ul class="laporan-tugas">' + daftar + '</ul>' if daftar else '<p>Tidak ada tugas yang belum selesai.</p>')
        + '<p class="laporan-catatan">Terisi juga mencakup pilihan status, bukan berarti selesai dikerjakan. '
        'Latihan manual atau kelas lama tidak menghalangi langkah utama.</p>'
        + navigasi_halaman(nomor, jumlah, lambda n: url_laporan(siswa_id, tampilan='tugas', halaman=n))
        + '</section>'
    )


def render_resume(perjalanan, tugas, siswa_id, nama_tipe, nama_topik, tanggal) -> str:
    rencana = perjalanan.rekomendasi
    belum = (
        f'<a class="laporan-tautan" href="{url_laporan(siswa_id, tampilan="tugas")}">'
        f'Rincian tugas · {len(tugas)} sesi belum selesai →</a>' if tugas else ''
    )
    materi = tuple(dict.fromkeys(kunci[0] for kunci in rencana.kandidat))
    materi_html = (
        '<p>Materi berikutnya: <b>' + ', '.join(html.escape(nama_tipe(t)) for t in materi) + '</b>.</p>'
        if materi else ""
    )
    if rencana.tindakan in {"lanjutkan_sesi", "konfirmasi_hasil"} and rencana.sesi_id:
        tujuan = f'/sesi/{int(rencana.sesi_id)}'
        label = "Lanjutkan latihan" if rencana.tindakan == "lanjutkan_sesi" else "Tinjau"
    else:
        tujuan = f'/anak/{int(siswa_id)}?section=rencana#judul-rencana-belajar'
        label = "Buka Beranda"
    return (
        '<section class="kartu-st laporan-resume" id="rencana-belajar-laporan" aria-labelledby="judul-resume">'
        '<div class="kartu-st ringkasan-laporan">'
        '<h2 id="judul-resume">Yang perlu dilakukan sekarang</h2>'
        f'{materi_html}<p class="resume-langkah">{_langkah(perjalanan, tanggal)}</p>'
        f'<a class="tombol aksi-rencana-laporan" href="{tujuan}">{label}</a>'
        '<div class="resume-konteks"><section><h3>Posisi belajar saat ini</h3>'
        f'<p class="laporan-catatan">Latihan awal {min(len(perjalanan.tanggal_pemetaan), 3)} dari 3 tanggal.</p>'
        + _terlihat(perjalanan, nama_tipe) + '</section>'
        '<section><h3>Masih perlu diperiksa</h3>' + _perlu_diperiksa(perjalanan, nama_tipe)
        + '</section></div>' + belum + '</div></section>'
    )
