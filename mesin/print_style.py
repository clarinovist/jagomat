"""Gaya cetak — CSS kertas A4 untuk lembar soal.

Dipecah dari worksheets.py (Fase 3): CSS cetak dan CSS layar punya alasan
berubah yang berbeda. Yang di sini hanya boleh berubah kalau hasil
cetakannya yang salah.

Riwayat yang mengikat (JANGAN diulang, sudah dua kali gagal):

  Garis panduan kotak Caraku digambar sebagai SVG data-URI yang di-tile,
  BUKAN repeating-linear-gradient.
    1. Gradient tanpa print-color-adjust hilang total di PDF karena Chrome
       mematikan background graphics saat mencetak;
    2. dengan print-color-adjust ia tampil tapi hanya SATU garis — Chrome
       tidak mengulang gradient sepanjang tinggi elemen seperti di layar.
  SVG dengan background-repeat: repeat selalu di-tile apa adanya, dan
  ukurannya dipatok dalam mm lewat background-size supaya jarak garisnya
  persis 7.5mm — setinggi tulisan tangan anak SD.

Nilai visual dipusatkan di design_tokens.py. Satuan di sini tetap mm/pt
(konteks cetak), bukan rem/px.
"""

import design_tokens as T
from presentation_style import GAYA_PENYAJIAN

GAYA_CETAK = f"""
{GAYA_PENYAJIAN}
@page {{ size: A4; margin: 13mm 12mm 11mm 12mm; }}
* {{ box-sizing: border-box; }}
body {{
  font-family: {T.FONT_CETAK};
  font-size: {T.UKURAN_BADAN_CETAK}; line-height: 1.45; color: {T.CETAK_TINTA}; margin: 0;
}}
h1 {{ font-size: 14pt; margin: 0 0 1mm; }}
.identitas {{ font-size: 9.5pt; margin-bottom: 3mm; }}
.identitas span {{ display: inline-block; margin-right: 6mm; }}
.garis {{ display: inline-block; width: 34mm; border-bottom: 1pt solid {T.CETAK_TINTA}; }}
.garis.pendek {{ width: 20mm; }}

.petunjuk {{
  border: 1pt solid {T.CETAK_TINTA}; padding: 2.5mm 3mm; margin-bottom: 4mm;
  font-size: 9.5pt; background: {T.CETAK_LATAR_PETUNJUK};
}}
.petunjuk p {{ margin: 0 0 1.5mm; }}
.petunjuk p:last-child {{ margin-bottom: 0; }}

/* Header banner (mockup lembar) — versi cetak hemat tinta: garis saja,
   tanpa blok teal/koral solid. */
.mesin-banner {{
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1.5pt solid {T.TEKS_JUDUL}; padding-bottom: 1.5mm; margin-bottom: 2.5mm;
  font-size: 10pt;
}}
.mesin-banner .nama-app {{ font-weight: bold; }}
.mesin-banner .meta-sesi {{ color: {T.CETAK_TEKS_SEKUNDER}; }}
.banner-kunci {{ border-bottom-style: double; }}
.kunci-headline {{
  font-size: 13pt; font-weight: bold; text-align: center;
  border: 1.2pt solid {T.CETAK_TINTA}; padding: 1.5mm; margin-bottom: 3mm;
}}

.bagian {{
  font-size: 11pt; font-weight: bold; margin: 4mm 0 2mm;
  border-bottom: 1.5pt solid {T.CETAK_TINTA}; padding-bottom: 1mm;
  /* Judul bagian yang tertinggal sendiri di dasar halaman membuat anak
     mengira bagian itu kosong. Paksa ia menempel ke soal sesudahnya. */
  break-after: avoid; page-break-after: avoid;
}}
.catatan-bagian {{
  border: 0.8pt dashed {T.CETAK_GARIS_HALUS}; padding: 1.5mm 2mm; margin: -1mm 0 2mm;
  font-size: 9pt;
}}

.soal {{
  border: 1.2pt solid {T.CETAK_TINTA}; padding: 2mm 2.5mm; margin-bottom: 2.2mm;
  page-break-inside: avoid; break-inside: avoid;
}}
.nomor {{
  display: inline-block; min-width: 6mm; height: 6mm; line-height: 6mm;
  text-align: center; font-weight: bold; border: 1.2pt solid {T.CETAK_TINTA};
  border-radius: {T.RADIUS_BULAT}; margin-right: 2mm; font-size: 10pt;
}}
.teks {{ display: inline; }}
/* Dulu ".teks .deret" (keturunan) — tidak pernah cocok karena render.py
   menaruh kedua kelas di elemen yang SAMA, jadi deret tidak pernah
   diperbesar. */
.teks.deret {{ font-size: 12pt; letter-spacing: 0.3pt; }}
/* Pertanyaan utama ditebalkan supaya tidak tenggelam di antara badan soal. */
.tanya {{ margin-top: 1.5mm; font-weight: bold; }}

.label {{ font-size: 9pt; color: {T.CETAK_TEKS_SEKUNDER}; margin: 1.4mm 0 0.8mm; }}
.cara {{
  border: {T.TEBAL_GARIS} dashed {T.CETAK_GARIS_HALUS};
  background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='30'%3E%3Cline x1='0' y1='29.5' x2='10' y2='29.5' stroke='{T.CETAK_GARIS_TULIS.replace('#', '%23')}' stroke-width='1'/%3E%3C/svg%3E");
  background-repeat: repeat;
  background-size: 4mm 7.5mm;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}}
/* Tinggi kotak Caraku: JANGAN dikecilkan lagi untuk menghemat halaman.

   Sudah dicoba: 22mm -> 19mm untuk memuat kartu ke-4 di halaman pertama.
   Hasilnya tetap 3 kartu (yang memakan ruang blok petunjuk, bukan tinggi
   kotak) dan jumlah halaman tetap 5 — jadi ruang tulis anak berkurang
   tanpa imbalan apa pun.

   Batas yang disepakati: lembar 12 soal = 5 halaman, dan itu diterima.
   Kotak Caraku yang terlalu kecil membuat anak berhenti menulis, dan kotak
   kosong TIDAK BISA dibedakan dari tidak bisa mengerjakan — itu merusak
   data diagnosis, yang justru satu-satunya alasan lembar ini ada. */
.cara.kecil  {{ height: 22mm; }}
.cara.sedang {{ height: 26mm; }}
.cara.besar {{ height: 30mm; }}

.restate {{
  border-bottom: 1pt solid {T.CETAK_TINTA}; height: 6mm; margin-bottom: 1mm;
}}
.jawab {{ margin-top: 2mm; font-size: 10.5pt; }}
.isian {{
  display: inline-block; width: 20mm; border-bottom: 1.4pt solid {T.CETAK_TINTA};
  vertical-align: -0.6mm;
}}
.isian.lebar {{ width: 30mm; }}
.centang {{ margin-top: 1.5mm; font-size: 9pt; color: {T.CETAK_TEKS_SEKUNDER}; }}
.kotak {{
  display: inline-block; width: 3.4mm; height: 3.4mm;
  border: 1pt solid {T.CETAK_TINTA}; vertical-align: -0.4mm; margin-right: 1.5mm;
}}
.bintang {{ font-weight: bold; }}
.akhir {{
  margin-top: 4mm; border-top: 1.5pt solid {T.CETAK_TINTA}; padding-top: 2mm;
  font-size: 9.5pt;
}}
svg {{ display: block; margin: 1.5mm 0; }}

/* ── lembar penilaian (guru) ── */
.kunci-tabel {{ width: 100%; border-collapse: collapse; margin-top: 1.5mm; }}
.kunci-tabel th, .kunci-tabel td {{
  border: 0.8pt solid {T.CETAK_GARIS_HALUS}; padding: 1mm 2mm; font-size: 9pt; text-align: left;
}}
.kunci-tabel th {{ background: {T.CETAK_LATAR_TABEL}; }}
.kode {{
  display: inline-block; min-width: 5mm; text-align: center;
  font-weight: bold; border: 1pt solid {T.CETAK_TINTA}; padding: 0 1mm;
}}
.kunci-nilai {{ font-size: 11pt; font-weight: bold; }}
.rekap {{ width: 100%; border-collapse: collapse; margin-top: 3mm; }}
.rekap th, .rekap td {{
  border: 0.8pt solid {T.CETAK_TINTA}; padding: 1.6mm 2mm; font-size: 9.5pt;
}}
.rekap th {{ background: {T.CETAK_LATAR_TABEL}; }}

/* Editorial cetak: garis ringan, A4 dan ruang Caraku tidak dikurangi. */
.lembar-editorial {{ color: {T.TEKS_UTAMA}; background: {T.LATAR_KARTU}; }}
.lembar-editorial .mesin-banner {{ border-bottom-width: 1pt; gap: 3mm; }}
.lembar-editorial :is(.petunjuk, .kunci-headline) {{
  background: transparent; border-width: .7pt;
}}
.lembar-editorial .soal {{ border-width: .7pt; }}
.lembar-editorial :is(.kunci-tabel, .rekap) {{ table-layout: fixed; overflow-wrap: anywhere; }}
.lembar-editorial :is(.kunci-tabel, .rekap) th {{ background: transparent; }}
.lembar-editorial :is(.kunci-tabel, .rekap) tr {{ break-inside: avoid; page-break-inside: avoid; }}
.lembar-editorial .kunci-tabel :is(th, td):first-child {{ width: 13mm; }}
.lembar-editorial .rekap :is(th, td):first-child {{ width: 10mm; }}
.lembar-editorial .meta-template {{ overflow-wrap: anywhere; }}
.lembar-editorial :is(h1, .catatan-bagian) {{ break-after: avoid; page-break-after: avoid; }}
.lembar-editorial :is(p, li) {{ orphans: 3; widows: 3; }}
"""
