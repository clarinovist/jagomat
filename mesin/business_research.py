"""Pusat riset bisnis publik Jagomat 2026.

Halaman statis dan read-only ini menyatukan peluang pasar, unit economics,
strategi persaingan, psikologi konsumen, serta rencana validasi GTM. Fakta,
proxy, asumsi, hasil hitung, dan rekomendasi dibedakan. Modul tidak membuka
basis data, membaca sesi, atau memproyeksikan data keluarga.
"""
from __future__ import annotations

from pathlib import Path

import brand
import design_tokens as T
from competitive_research import GAYA_RISET, _font_link

JALUR = "/riset"
JALUR_PDF = "/riset/laporan-bisnis-2026.pdf"
NAMA_PDF = "jagomat-riset-bisnis-2026.pdf"
VERSI_ISI = "2026-10-13-r2"
BERKAS_PDF = Path(__file__).resolve().parent / "publik" / NAMA_PDF

RINGKASAN_META = (
    "Business case Jagomat 2026: peluang pasar, unit economics, strategi, "
    "psikologi orang tua-anak, dan rencana validasi go-to-market 90 hari."
)

GAYA_BISNIS = f"""
.riset-hero-bisnis {{ min-height: auto; grid-template-columns: 1fr; }}
.riset-hero-bisnis h1 {{ max-width: 19ch; }}
.riset-primer {{
  display: grid; gap: {T.SP_4}; padding: {T.SP_5}; border-radius: {T.RADIUS_KARTU_BESAR};
  background: {T.LATAR_TERSIMPAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_TERSIMPAN};
}}
.riset-primer h2 {{ font-size: clamp(1.35rem, 2.2vw, 1.8rem); }}
.riset-primer p {{ color: {T.TEKS_VARIAN}; max-width: 72ch; }}
.riset-angka-besar {{
  display: block; color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE};
  font-size: clamp(1.8rem, 4vw, 3rem); font-weight: 800; line-height: 1.05;
}}
.riset-stat {{
  display: grid; align-content: start; gap: {T.SP_3}; padding: {T.SP_5};
  border-radius: {T.RADIUS_KARTU_BESAR}; background: {T.LATAR_KARTU};
  border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
}}
.riset-stat p {{ color: {T.TEKS_VARIAN}; }}
.riset-definisi {{
  display: grid; gap: {T.SP_3}; padding: {T.SP_5}; margin: {T.SP_5} 0;
  border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU_BESAR};
  background: {T.LATAR_SEKUNDER_LEMBUT};
}}
.riset-legenda {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; }}
.riset-lencana {{
  display: inline-flex; align-items: center; min-height: 2rem; padding: {T.SP_1} {T.SP_3};
  border-radius: {T.RADIUS_PIL}; font-size: {T.UKURAN_TEKS_META}; font-weight: 800;
  letter-spacing: .035em; text-transform: uppercase; border: {T.TEBAL_GARIS} solid currentColor;
}}
.riset-lencana-fakta {{ color: {T.TEKS_TERSIMPAN}; background: {T.LATAR_TERSIMPAN}; }}
.riset-lencana-proxy {{ color: {T.KODE_SALAH_HITUNG_TEKS}; background: {T.KODE_SALAH_HITUNG_BG}; }}
.riset-lencana-asumsi {{ color: {T.TEKS_REVIEW}; background: {T.LATAR_REVIEW}; }}
.riset-lencana-hitung {{ color: {T.KODE_SALAH_TULIS_TEKS}; background: {T.KODE_SALAH_TULIS_BG}; }}
.riset-lencana-rekomendasi {{ color: {T.TEKS_GALAT}; background: {T.LATAR_GALAT}; }}
.riset-modul {{ position: relative; }}
.riset-modul-nomor {{
  color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE}; font-weight: 800;
  font-size: clamp(3.5rem, 8vw, 7rem); line-height: .85; opacity: .16;
}}
.riset-rumus {{
  overflow-x: auto; padding: {T.SP_4}; border-radius: {T.RADIUS_KARTU};
  background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH};
  font: 600 .9rem/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  white-space: nowrap;
}}
.riset-tabel-bungkus:focus-visible {{
  outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: {T.SP_1};
}}
.riset-tabel-bungkus caption {{
  padding: {T.SP_3} {T.SP_4}; text-align: left; caption-side: top;
  color: {T.TEKS_JUDUL}; background: {T.LATAR_SEKUNDER_LEMBUT}; font-weight: 800;
}}
.riset-tabel-bungkus td:first-child, .riset-tabel-bungkus th:first-child {{ font-weight: 700; }}
.riset-tabel-bungkus td[data-label="Asumsi"] {{ background: {T.LATAR_CATATAN}; }}
.riset-bar {{ display: grid; gap: {T.SP_2}; }}
.riset-bar-item {{ display: grid; grid-template-columns: minmax(7rem, 11rem) 1fr; gap: {T.SP_3}; align-items: center; }}
.riset-bar-track {{ height: 1.2rem; overflow: hidden; border-radius: {T.RADIUS_PIL}; background: {T.LATAR_SEKUNDER_NETRAL}; }}
.riset-bar-fill {{ display: block; height: 100%; border-radius: inherit; background: {T.AKSEN_TEAL_TUA}; }}
.riset-bar-fill-koral {{ background: {T.AKSEN_KORAL_TUA}; }}
.riset-bar-item b {{ color: {T.TEKS_JUDUL}; }}
.riset-putusan {{
  display: grid; gap: {T.SP_4}; padding: {T.SP_5}; margin-top: {T.SP_5};
  border-left: .4rem solid {T.AKSEN_TEAL_TUA}; border-radius: 0 {T.RADIUS_KARTU} {T.RADIUS_KARTU} 0;
  background: {T.LATAR_SEKUNDER_LEMBUT};
}}
.riset-putusan h3 {{ font-size: 1.2rem; }}
.riset-urutan {{ display: grid; gap: {T.SP_3}; counter-reset: tahap; padding: 0; }}
.riset-urutan > li {{
  counter-increment: tahap; list-style: none; display: grid; grid-template-columns: 3rem 1fr;
  gap: {T.SP_3}; padding: {T.SP_4}; border-radius: {T.RADIUS_KARTU};
  background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
}}
.riset-urutan > li::before {{
  content: counter(tahap); display: grid; place-items: center; width: 3rem; height: 3rem;
  border-radius: {T.RADIUS_BULAT}; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH};
  font-family: {T.FONT_HEADLINE}; font-weight: 800;
}}
.riset-urutan h3 {{ margin-bottom: {T.SP_1}; }}
.riset-urutan p, .riset-urutan li {{ color: {T.TEKS_VARIAN}; }}
.riset-sumber li {{ overflow-wrap: anywhere; }}
.riset-kecil {{ color: {T.TEKS_VARIAN}; font-size: {T.UKURAN_TEKS_CATATAN}; }}
.riset-jeda {{ margin-top: {T.SP_5}; }}
.riset-anti-tam {{ border-top: .35rem solid {T.AKSEN_MURID_AMBER}; }}
.riset-kartu-utama {{ border-top: .35rem solid {T.AKSEN_TEAL_TUA}; }}
.riset-kartu-risiko {{ border-top: .35rem solid {T.AKSEN_KORAL_TUA}; }}
.riset-daftar-cek {{ margin: 0; padding-left: {T.SP_5}; display: grid; gap: {T.SP_2}; }}
.riset-batas {{
  padding: {T.SP_4}; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_GALAT};
  border: {T.TEBAL_GARIS} solid {T.BORDER_GALAT}; color: {T.TEKS_GALAT}; font-weight: 700;
}}
@media (min-width: {T.BATAS_TABLET}) {{
  .riset-hero-bisnis {{ grid-template-columns: minmax(0, 1.25fr) minmax(20rem, .75fr); }}
  .riset-stat-grid {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
}}
@media (max-width: {T.BATAS_HP}) {{
  .riset-bar-item {{ grid-template-columns: 1fr; }}
  .riset-modul-nomor {{ font-size: 4rem; }}
  .riset-rumus {{ white-space: normal; overflow-wrap: anywhere; }}
}}
@media print {{
  .riset-modul-nomor {{ font-size: 34pt; }}
  .riset-rumus {{ white-space: normal; color: {T.CETAK_TINTA}; background: {T.CETAK_LATAR_PETUNJUK}; }}
  .riset-primer, .riset-stat, .riset-definisi, .riset-putusan {{ break-inside: avoid; box-shadow: none; }}
  .riset-lencana {{ border: 1px solid {T.CETAK_GARIS_HALUS}; color: {T.CETAK_TINTA}; background: transparent; }}
}}
"""


def halaman() -> bytes:
    """Render pusat riset lengkap tanpa membaca state pengguna."""
    logo = brand.mark("topbar")
    tag_kepala = brand.tag_kepala({
        "judul": "Riset bisnis Jagomat 2026",
        "deskripsi": RINGKASAN_META,
        "jalur": JALUR,
    })
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul(f'Riset bisnis Jagomat 2026 · {VERSI_ISI}')}</title>
{tag_kepala}{_font_link()}<style>{GAYA_RISET}{GAYA_BISNIS}</style></head>
<body><a class="riset-lewati" href="#konten-riset">Lewati ke laporan</a>
<header class="riset-topbar"><div class="riset-topbar-dalam">
<a class="riset-brand" href="/">{logo}<span>Jagomat</span></a>
<nav class="riset-nav" aria-label="Aksi laporan">
<a class="riset-nav-teks" href="#cara-baca">Cara baca</a>
<a class="riset-unduh" href="{JALUR_PDF}">Unduh PDF</a>
</nav></div></header>
<main id="konten-riset"><div class="riset-bungkus">
<section class="riset-hero riset-hero-bisnis" aria-labelledby="judul-riset">
<div class="riset-hero-copy">
<p class="riset-alis">Jagomat Business Case · Indonesia · 2026</p>
<h1 id="judul-riset">Seberapa besar peluang Jagomat—dan apa yang harus dibuktikan lebih dulu?</h1>
<p class="riset-dek">Jawaban singkatnya: ruang ekonominya mungkin besar, tetapi bisnisnya belum terbukti. Laporan ini menunjukkan angka yang dapat dihitung, asumsi yang masih rapuh, serta eksperimen paling hemat untuk mengubah dugaan menjadi bukti.</p>
<div class="riset-meta" aria-label="Metadata laporan">
<span class="riset-chip">Snapshot · 13 Oktober 2026</span>
<span class="riset-chip">Revisi isi · {VERSI_ISI}</span>
<span class="riset-chip">Core case · Matematika SD/OSN–SASMO</span>
<span class="riset-chip">Bukan forecast atau valuasi</span>
</div></div>
<aside class="riset-keputusan" aria-labelledby="keputusan-utama">
<p class="riset-alis">Kesimpulan untuk pemilik</p>
<h2 id="keputusan-utama">Jangan membeli pertumbuhan sebelum retensi terbukti.</h2>
<ul>
<li>Fokuskan produk pada matematika SD; jenjang lain adalah bisnis berbeda.</li>
<li>Gunakan cohort dan kapasitas, bukan TAM, untuk membuat target pendapatan.</li>
<li>Tahan paid scale sampai first value, support, WTP, dan M3/M6 terukur.</li>
</ul>
</aside></section>

<section class="riset-primer" aria-labelledby="kesimpulan-awam">
<p class="riset-alis">Kalau hanya membaca satu bagian</p>
<h2 id="kesimpulan-awam">Jagomat bisa menjadi bisnis miliaran rupiah, tetapi baru sebagai skenario—bukan fakta.</h2>
<p>Pada ARPA asumsi Rp32.000 per bulan, sekitar <strong>2.605 akun aktif</strong> menghasilkan ARR run-rate Rp1 miliar. Sekitar <strong>13.021 akun aktif</strong> menghasilkan Rp5 miliar. Namun angka itu hanya berguna bila keluarga bertahan, biaya dukungan rendah, dan akuisisi tidak lebih mahal daripada nilai yang mereka hasilkan.</p>
</section>

<nav class="riset-indeks" aria-label="Bagian laporan">
<a href="#ringkasan">Ringkasan</a><a href="#pasar">1 · Pasar & ekonomi</a>
<a href="#strategi">2 · Strategi</a><a href="#psikologi">3 · Psikologi</a>
<a href="#gtm">4 · GTM 90 hari</a><a href="#metodologi">Metodologi</a>
<a href="#sumber">Sumber</a>
</nav>

<section class="riset-bagian" id="ringkasan" aria-labelledby="judul-ringkasan">
<div class="riset-kepala"><p class="riset-alis">Ringkasan eksekutif</p>
<h2 id="judul-ringkasan">Empat keputusan, bukan empat tumpukan slide</h2>
<p>Setiap modul di bawah diarahkan pada keputusan yang dapat diuji. Istilah bisnis diterjemahkan ke bahasa sehari-hari dan ketidakpastian ditampilkan di tempat angkanya muncul.</p></div>
<div class="riset-grid riset-grid-2">
<article class="riset-kartu riset-kartu-utama"><span class="riset-label riset-label-teal">Keputusan 1</span><h3>Core tetap matematika SD</h3><p>Jumlah murid SD adalah batas atas demografis, bukan jumlah pembeli. SMP, PTN, dan kedinasan memiliki pengguna, materi, harga, serta kompetisi berbeda; jangan dijumlahkan sebagai satu TAM.</p></article>
<article class="riset-kartu riset-kartu-utama"><span class="riset-label riset-label-teal">Keputusan 2</span><h3>Posisi: setelah salah, tahu langkah berikutnya</h3><p>Ini paling jelas dari tiga konsep dalam stress-test semantik, tetapi belum menjadi bukti pasar. Concept test langsung dengan orang tua tetap wajib sebelum dipakai untuk scale.</p></article>
<article class="riset-kartu riset-kartu-utama"><span class="riset-label riset-label-teal">Keputusan 3</span><h3>PLG-assisted, dibatasi kapasitas</h3><p>Produk harus membuktikan nilai sendiri, sementara bantuan manusia dipakai selektif untuk friksi awal. Jika bantuan menjadi layanan tanpa batas, paket murah tidak ekonomis.</p></article>
<article class="riset-kartu riset-kartu-risiko"><span class="riset-label riset-label-koral">Keputusan 4</span><h3>90 hari adalah validasi, bukan scale-up</h3><p>Periode ini cukup untuk menguji pemahaman, usability, first value, dan beban support. Belum cukup untuk menyatakan LTV, retensi tahunan, outcome kausal, atau valuasi.</p></article>
</div>
<div class="riset-callout"><strong>Tiga klaim yang sengaja tidak dibuat</strong><p>Kami tidak menyatakan Jagomat meningkatkan nilai, memiliki market share tertentu, atau sudah memiliki moat. Desain siklus belajar, data populasi, dan skenario ekonomi adalah tiga jenis bukti yang berbeda.</p></div>
<details class="riset-detail"><summary>Kamus singkat untuk pembaca awam</summary><div class="riset-detail-isi"><p><b>ARPA</b>: pendapatan rata-rata per akun per bulan. <b>MRR</b>: pendapatan bulanan berulang pada titik waktu tertentu. <b>ARR run-rate</b>: MRR akhir dikali 12—bukan otomatis omzet tahun pertama. <b>CAC</b>: seluruh biaya mendapatkan satu pelanggan. <b>Churn</b>: persentase akun yang berhenti per bulan. <b>LTV contribution</b>: perkiraan uang kontribusi selama pelanggan bertahan, setelah biaya variabel.</p></div></details>
</section>

<section class="riset-bagian" id="cara-baca" aria-labelledby="judul-cara-baca">
<div class="riset-kepala"><p class="riset-alis">Cara membaca angka</p><h2 id="judul-cara-baca">Tidak semua angka mempunyai kekuatan bukti yang sama</h2><p>Lencana ini mencegah asumsi terlihat seperti data pasar. Confidence tinggi pada sumber tidak otomatis membuat proxy cocok untuk keputusan.</p></div>
<div class="riset-legenda" aria-label="Legenda kekuatan bukti">
<span class="riset-lencana riset-lencana-fakta">Fakta sumber</span>
<span class="riset-lencana riset-lencana-proxy">Proxy</span>
<span class="riset-lencana riset-lencana-asumsi">Asumsi manajemen</span>
<span class="riset-lencana riset-lencana-hitung">Hasil hitung</span>
<span class="riset-lencana riset-lencana-rekomendasi">Rekomendasi</span>
</div>
<div class="riset-definisi"><p><b>TAM</b> adalah seluruh universe yang mungkin relevan. <b>SAM</b> adalah bagian yang benar-benar dapat dilayani produk dan kanal sekarang. <b>SOM</b> adalah bagian yang realistis dicapai berdasarkan funnel serta kapasitas—bukan persentase pasar yang dipilih sesuka hati.</p></div>
</section>

<section class="riset-bagian riset-modul" id="pasar" aria-labelledby="judul-pasar">
<div class="riset-modul-nomor" aria-hidden="true">01</div>
<div class="riset-kepala"><p class="riset-alis">Market opportunity &amp; unit economics</p>
<h2 id="judul-pasar">Peluang besar di atas kertas; bisnis ditentukan di cohort</h2>
<p>Market sizing menjawab “seberapa lebar ruangnya”, bukan “berapa pelanggan yang pasti datang”. Karena unit paket adalah akun keluarga plus profil tambahan, jumlah anak tidak boleh langsung dikalikan harga paket dasar sebagai market revenue.</p></div>

<div class="riset-grid riset-stat-grid">
<article class="riset-stat"><span class="riset-lencana riset-lencana-proxy">Proxy</span><span class="riset-angka-besar">Belum dikunci</span><p>Denominator murid SD perlu tabel primer Kemendikbud/BPS per tingkat. Laporan sengaja tidak memakai angka sekunder yang tautannya sudah tidak dapat diaudit.</p></article>
<article class="riset-stat"><span class="riset-lencana riset-lencana-fakta">Fakta sumber</span><span class="riset-angka-besar">72,78%</span><p>Individu Indonesia yang menggunakan internet pada 2024 menurut World Bank. Ini bukan kesiapan household untuk membayar.</p></article>
<article class="riset-stat"><span class="riset-lencana riset-lencana-hitung">Hasil hitung</span><span class="riset-angka-besar">2.605</span><p>Akun aktif untuk ARR run-rate Rp1 miliar pada ARPA asumsi Rp32 ribu/bulan.</p></article>
<article class="riset-stat"><span class="riset-lencana riset-lencana-asumsi">Belum terbukti</span><span class="riset-angka-besar">5 variabel</span><p>WTP, activation, churn, CAC, dan menit support masih menentukan apakah ruang pasar dapat menjadi bisnis.</p></article>
</div>

<div class="riset-grid riset-grid-2 riset-jeda">
<article class="riset-kartu riset-anti-tam"><span class="riset-label riset-label-amber">TAM volume</span><h3>Denominator resmi masih perlu diverifikasi</h3><p>Ceiling demografis harus memakai tabel primer murid SD per tingkat yang dapat diaudit. Setelah tersedia pun, tidak semua anak membutuhkan OSN/SASMO, dapat dilayani secara digital, atau berada dalam household pembayar yang berbeda.</p><p class="riset-kecil">Keputusan: jangan publikasikan satu angka TAM volume sampai tabel primer berhasil dikunci.</p></article>
<article class="riset-kartu riset-anti-tam"><span class="riset-label riset-label-amber">TAM rupiah</span><h3>Sengaja tidak dinyatakan sebagai market revenue</h3><p>Rumus yang benar membutuhkan jumlah household pembayar, mix Jago/Pro, periode bayar, promo, dan harga profil tambahan. Mengalikan semua anak dengan harga dasar akan menghitung sebagian keluarga dua kali.</p><div class="riset-rumus" tabindex="0" role="region" aria-label="Rumus revenue berdasarkan household dan profil">Revenue = household × ARPA dasar + profil tambahan × harga incremental</div></article>
<article class="riset-kartu"><span class="riset-label">SAM</span><h3>Belum dapat disebut satu angka yang sah</h3><p>Internet 72,78% hanya proxy akses. Problem-fit, kemampuan bayar, kemauan menjalankan review orang tua, dan kecocokan OSN/SASMO belum diukur. Rentang 5–20% boleh dipakai untuk sensitivity, bukan sebagai data pasar.</p></article>
<article class="riset-kartu riset-kartu-utama"><span class="riset-label riset-label-teal">SOM</span><h3>Bangun dari kapasitas dan funnel</h3><p>Target yang dapat diaudit berasal dari lead berkualitas, conversion, survival cohort, dan kapasitas support. Unit harus konsisten: akun keluarga dibanding household, profil aktif dibanding anak.</p><div class="riset-rumus" tabindex="0" role="region" aria-label="Rumus jumlah akun aktif">Akun_t = Akun_(t−1) × (1 − churn_t) + pelanggan_baru_t</div></article>
</div>

<h3 class="riset-jeda">Skenario target pendapatan—bukan forecast</h3>
<div class="riset-tabel-bungkus riset-jeda" tabindex="0" role="region" aria-label="Tabel skenario target pendapatan" aria-describedby="catatan-revenue">
<table><caption>Skenario ending run-rate berdasarkan akun aktif akhir periode</caption><thead><tr><th scope="col">Skenario</th><th scope="col">Akun aktif akhir</th><th scope="col">ARPA/bln</th><th scope="col">Ending MRR</th><th scope="col">ARR run-rate</th><th scope="col">Makna</th></tr></thead><tbody>
<tr><td>Konservatif</td><td data-label="Asumsi">300</td><td data-label="Asumsi">Rp27.000</td><td>Rp8,1 juta</td><td>Rp97,2 juta</td><td>Pilot niche; belum bisnis miliaran</td></tr>
<tr><td>Moderat</td><td data-label="Asumsi">1.500</td><td data-label="Asumsi">Rp32.000</td><td>Rp48 juta</td><td>Rp576 juta</td><td>Butuh funnel dan support yang berulang</td></tr>
<tr><td>Agresif</td><td data-label="Asumsi">5.000</td><td data-label="Asumsi">Rp38.000</td><td>Rp190 juta</td><td>Rp2,28 miliar</td><td>Bukan omzet tahun pertama; butuh cohort matang</td></tr>
</tbody></table></div>
<p class="riset-kecil" id="catatan-revenue">ARR run-rate = 12 × MRR pada akhir periode. Omzet tahun pertama harus menjumlahkan akun aktif rata-rata setiap bulan, bukan mengalikan pelanggan akhir dengan 12.</p>

<div class="riset-putusan"><h3>Apa arti “bisnis miliaran” secara konkret?</h3><p>Pada ARPA Rp32.000, ARR run-rate Rp1 miliar memerlukan 2.605 akun aktif; Rp5 miliar memerlukan 13.021; Rp10 miliar memerlukan 26.042. Ini omzet run-rate, bukan valuasi. Valuasi memerlukan bukti pertumbuhan, retensi, margin, risiko, dan transaksi pembanding; laporan ini tidak menerapkan multiple.</p></div>

<h3 class="riset-jeda">Unit economics: apakah satu pelanggan menambah atau membakar uang?</h3>
<div class="riset-tabel-bungkus riset-jeda" tabindex="0" role="region" aria-label="Tabel unit economics skenario">
<table><caption>Baris bertanda “Asumsi” harus diganti data cohort; warna hanya penguat visual</caption><thead><tr><th scope="col">Metrik</th><th scope="col">Konservatif</th><th scope="col">Moderat</th><th scope="col">Agresif</th></tr></thead><tbody>
<tr><td>ARPA/bulan <small>(Asumsi)</small></td><td data-label="Asumsi">Rp27.000</td><td data-label="Asumsi">Rp32.000</td><td data-label="Asumsi">Rp38.000</td></tr>
<tr><td>Biaya variabel/akun <small>(Asumsi)</small></td><td data-label="Asumsi">Rp14.000</td><td data-label="Asumsi">Rp10.000</td><td data-label="Asumsi">Rp8.000</td></tr>
<tr><td>Contribution/akun</td><td>Rp13.000</td><td>Rp22.000</td><td>Rp30.000</td></tr>
<tr><td>Contribution margin</td><td>48,1%</td><td>68,8%</td><td>78,9%</td></tr>
<tr><td>CAC <small>(Asumsi)</small></td><td data-label="Asumsi">Rp180.000</td><td data-label="Asumsi">Rp120.000</td><td data-label="Asumsi">Rp90.000</td></tr>
<tr><td>Churn logo/bulan <small>(Asumsi)</small></td><td data-label="Asumsi">12%</td><td data-label="Asumsi">7%</td><td data-label="Asumsi">4%</td></tr>
<tr><td>LTV contribution sederhana</td><td>Rp108.333</td><td>Rp314.286</td><td>Rp750.000</td></tr>
<tr><td>Payback</td><td>13,85 bulan</td><td>5,45 bulan</td><td>3,00 bulan</td></tr>
<tr><td>LTV:CAC</td><td>0,60×</td><td>2,62×</td><td>8,33×</td></tr>
</tbody></table></div>
<div class="riset-rumus riset-jeda" tabindex="0" role="region" aria-label="Rumus contribution dan LTV sederhana">Contribution = ARPA − payment − provider − refund/fraud − support − variable ops · LTV sederhana = contribution ÷ churn</div>
<p class="riset-kecil riset-jeda">Skenario agresif terlihat terbaik karena diberi CAC dan churn terbaik; skala belum membuktikannya. LTV sederhana hanya sensitivity shorthand. Setelah cohort matang, gunakan jumlah contribution yang dibobot survival tiap bulan.</p>

<div class="riset-grid riset-grid-2 riset-jeda">
<article class="riset-kartu"><span class="riset-label">Guard CAC</span><h3>Berapa CAC maksimum?</h3><p>Pada skenario moderat, payback 6 bulan mengizinkan CAC sampai Rp132 ribu. Rasio LTV:CAC 3× mengizinkan sekitar Rp105 ribu. Gunakan batas yang lebih ketat: <strong>sekitar Rp105 ribu</strong>, sampai data cohort menggantikan asumsi.</p></article>
<article class="riset-kartu"><span class="riset-label">Guard support</span><h3>Waktu manusia bukan gratis</h3><p>Biaya support per akun = menit support ÷ 60 × fully loaded hourly cost. Lima menit pada Rp60 ribu/jam sudah Rp5 ribu. Jika bantuan 20 menit per akun, paket murah cepat kehilangan margin.</p></article>
</div>

<h3 class="riset-jeda">Ekspansi bukan tambahan baris di TAM</h3>
<div class="riset-tabel-bungkus riset-jeda" tabindex="0" role="region" aria-label="Tabel pilihan segmen pasar">
<table><caption>Pisahkan core case dan opsi ekspansi</caption><thead><tr><th scope="col">Segmen</th><th scope="col">Pembeli/pengguna</th><th scope="col">Produk yang dibutuhkan</th><th scope="col">Keputusan</th></tr></thead><tbody>
<tr><td>SD OSN/SASMO</td><td>Orang tua / anak</td><td>Latihan, review manusia, siklus tindak lanjut</td><td><b>Core sekarang</b></td></tr>
<tr><td>SMP</td><td>Orang tua / remaja</td><td>Kurikulum, motivasi, dan diagnosis baru</td><td>Riset terpisah; jangan digabung</td></tr>
<tr><td>PTN</td><td>Remaja / keluarga</td><td>Tryout, ranking, time pressure, high-stakes prep</td><td>Bisnis berbeda; tunda</td></tr>
<tr><td>Kedinasan</td><td>Pelamar dewasa</td><td>Seleksi, jadwal, materi dan compliance berbeda</td><td>Di luar scope Jagomat saat ini</td></tr>
<tr><td>Tutor/les mikro</td><td>Tutor / banyak keluarga</td><td>Role, consent, ownership, seat, billing, support</td><td>Opsi B2B2C; bukan “kanal saja”</td></tr>
</tbody></table></div>
</section>

<section class="riset-bagian riset-modul" id="strategi" aria-labelledby="judul-strategi">
<div class="riset-modul-nomor" aria-hidden="true">02</div>
<div class="riset-kepala"><p class="riset-alis">Competitive advantage &amp; growth strategy</p>
<h2 id="judul-strategi">Jangan menjadi Ruangguru yang lebih kecil</h2>
<p>Audit ini memeriksa permukaan publik empat pemain terpilih. Ia tidak mengukur market share, kualitas absolut, produk berbayar secara penuh, atau operasi internal. “Tidak terlihat” bukan berarti “tidak ada”.</p></div>

<div class="riset-tabel-bungkus" tabindex="0" role="region" aria-label="Perbandingan empat pemain dan Jagomat">
<table><caption>Apa yang ditampilkan pemain—dan hipotesis ruang posisi Jagomat</caption><thead><tr><th scope="col">Pemain/model</th><th scope="col">Observasi publik</th><th scope="col">Yang belum dapat disimpulkan</th><th scope="col">Implikasi hipotesis</th></tr></thead><tbody>
<tr><td>Ruangguru</td><td>Portofolio luas: konten, latihan, live class, cabang, AI, hingga program matematika/olimpiade. Harga dan paket dinamis.</td><td>Breadth tidak membuktikan diagnosis mikro mereka lemah.</td><td>Jagomat jangan perang katalog; uji kejelasan tindak lanjut.</td></tr>
<tr><td>Zenius</td><td>Permukaan publik menonjolkan materi dan latihan; beberapa halaman dinamis menolak otomasi saat audit.</td><td>Tingkat pendampingan aktual dan status paket tidak dapat diaudit penuh.</td><td>Jangan memakai narasi lama tanpa verifikasi manual.</td></tr>
<tr><td>Ganesha Operation</td><td>Situs resmi menonjolkan pengajar, materi, TOBK, dan penilaian; ekstraksi audit terbatas.</td><td>Biaya, variasi delivery, dan kedalaman diagnosis internal.</td><td>Butuh wawancara/trial sebelum memakai klaim trade-off.</td></tr>
<tr><td>Kumon</td><td>Worksheet bertahap, level perseorangan, pembimbing, dan progres; SD Rp430–525 ribu/subjek/bulan menurut wilayah, efektif 1 Jan 2026.</td><td>Halaman metode tidak cukup menilai seluruh praktik diagnosis pembimbing.</td><td>“Personalisasi” dan laporan saja bukan pembeda.</td></tr>
<tr><td>Jagomat</td><td>Desain menghubungkan latihan, tinjauan manusia, intervensi, dan pengecekan ulang.</td><td>Outcome, engagement, WTP, dan defensibility belum terbukti.</td><td>Posisi target: membantu keputusan setelah anak salah.</td></tr>
</tbody></table></div>

<div class="riset-callout"><strong>Candidate advantage, bukan moat hari ini</strong><p>Fitur dapat disalin. Daya tahan baru mungkin muncul bila workflow dipakai berulang, diagnosis cukup dipercaya, intervensi menghasilkan tindak lanjut yang berguna, bukti dijaga dengan privasi, dan distribusi menjadi efisien. Belum ada bukti bahwa kelima hal itu sudah terjadi.</p></div>

<div class="riset-grid riset-grid-3">
<article class="riset-kartu"><span class="riset-label">Lapisan 1</span><h3>Taksonomi yang actionable</h3><p>B/K/H/E/N/T harus menghasilkan bantuan berbeda, ditinjau manusia, dan mengakui ketidakpastian.</p></article>
<article class="riset-kartu"><span class="riset-label">Lapisan 2</span><h3>Soal parametrik</h3><p>Variasi baru mengecek konsep yang sama tanpa mengulang angka persis. Ini desain pengukuran, bukan bukti outcome.</p></article>
<article class="riset-kartu"><span class="riset-label">Lapisan 3</span><h3>Siklus terkonfirmasi</h3><p>Bukti append-only menjaga provenance keputusan. Ia tidak otomatis membuktikan efektivitas kausal.</p></article>
<article class="riset-kartu"><span class="riset-label">Lapisan 4</span><h3>Kebiasaan keluarga</h3><p>Jika keluarga kembali pada milestone belajar nyata, switching cost workflow dapat muncul. Masih hipotesis.</p></article>
<article class="riset-kartu"><span class="riset-label">Lapisan 5</span><h3>Outcome learning</h3><p>Hanya data berizin, volume memadai, metode transparan, dan audit ahli yang boleh mengubahnya menjadi aset pembelajaran.</p></article>
<article class="riset-kartu riset-kartu-risiko"><span class="riset-label riset-label-koral">Bukan moat</span><h3>Chatbot, badge, dashboard</h3><p>Komponen ini berguna, tetapi tidak cukup sendiri untuk menghasilkan defensibility.</p></article>
</div>

<h3 class="riset-jeda">PLG atau sales-led?</h3>
<div class="riset-duel riset-jeda">
<article class="riset-kartu"><span class="riset-label riset-label-koral">Tahan</span><h3>Sales-led keluarga</h3><ul><li>Nilai kontrak rendah tidak cocok dengan sales high-touch.</li><li>Diskon mudah menggantikan diferensiasi.</li><li>Support dapat menghabiskan margin sebelum retensi terbukti.</li></ul></article>
<article class="riset-kartu riset-kartu-utama"><span class="riset-label riset-label-teal">Uji</span><h3>PLG-assisted</h3><ul><li>Produk membuktikan nilai sebagai mesin utama.</li><li>Clinic onboarding hanya untuk friksi terpilih.</li><li>Throttling akuisisi mengikuti kapasitas support.</li><li>Tutor hanya referral sampai role/data B2B2C diputuskan.</li></ul></article>
</div>

<h3 class="riset-jeda">Tiga risiko strategis terbesar</h3>
<div class="riset-risiko riset-jeda">
<article><span class="riset-risiko-nomor">01</span><h3>Desain tidak menjadi outcome</h3><dl><dt>Mekanisme</dt><dd>Siklus terlihat rapi, tetapi anak tidak membaik pada soal baru.</dd><dt>Indikator</dt><dd>Override diagnosis tinggi, probe baru gagal, rekomendasi berulang.</dd><dt>Mitigasi</dt><dd>Konfirmasi manusia, delayed probe, audit ahli, dan klaim terbatas.</dd></dl></article>
<article><span class="riset-risiko-nomor">02</span><h3>Orang tua terlalu terbebani</h3><dl><dt>Mekanisme</dt><dd>Review yang menjaga kualitas terasa seperti pekerjaan tambahan.</dd><dt>Indikator</dt><dd>Abandonment sebelum first value; support tinggi.</dd><dt>Mitigasi</dt><dd>Minimum sufficient involvement, pause/resume, dan bantuan selektif.</dd></dl></article>
<article><span class="riset-risiko-nomor">03</span><h3>CAC lebih besar dari nilai</h3><dl><dt>Mekanisme</dt><dd>Paid acquisition mahal untuk ARPA rendah, sementara fitur permukaan disalin.</dd><dt>Indikator</dt><dd>Payback panjang, referral lemah, churn tinggi.</dd><dt>Mitigasi</dt><dd>Problem-intent organic, referral sesudah milestone, dan kill rules.</dd></dl></article>
</div>
</section>

<section class="riset-bagian riset-modul" id="psikologi" aria-labelledby="judul-psikologi">
<div class="riset-modul-nomor" aria-hidden="true">03</div>
<div class="riset-kepala"><p class="riset-alis">Consumer psychology &amp; behavioral barriers</p>
<h2 id="judul-psikologi">Orang tua membeli kejelasan; anak membutuhkan rasa aman untuk mencoba</h2>
<p>Riset mendukung hubungan antara kecemasan matematika dan prestasi, tetapi tidak mengizinkan kita mendiagnosis motif bawah sadar setiap keluarga. Growth mindset juga bukan kalimat ajaib: efek rata-rata kecil dan bergantung konteks.</p></div>

<div class="riset-tabel-bungkus" tabindex="0" role="region" aria-label="Peta dua audiens Jagomat">
<table><caption>Dual-audience map: pembayar dan pengguna langsung</caption><thead><tr><th scope="col">Dimensi</th><th scope="col">Orang tua</th><th scope="col">Anak SD</th><th scope="col">Konsekuensi produk/pesan</th></tr></thead><tbody>
<tr><td>Pekerjaan</td><td>Memahami apa yang terjadi dan memilih bantuan tanpa menjadi tutor penuh.</td><td>Mengerjakan tantangan yang terasa aman dan tahu apa yang dilakukan.</td><td>Orang tua mendapat satu langkah; anak mendapat instruksi netral.</td></tr>
<tr><td>Pertanyaan</td><td>“Salahnya di mana? Mulai dari apa? Apakah membaik?”</td><td>“Aku harus apa? Kalau salah bagaimana? Boleh coba lagi?”</td><td>Copy menjawab pertanyaan nyata, bukan menebak ketakutan tersembunyi.</td></tr>
<tr><td>Risiko emosi</td><td>Kewalahan, frustrasi, takut salah membantu.</td><td>Cemas, malu, menghindar, terburu-buru, menebak.</td><td>Sebut sebagai kemungkinan/sinyal, bukan diagnosis psikologis.</td></tr>
<tr><td>Bukti nilai</td><td>Outcome ditinjau, probe baru, langkah berikutnya jelas.</td><td>“Aku bisa menjelaskan dan mencoba soal baru”, bukan skor semata.</td><td>Rayakan proses spesifik; jangan melabeli bakat.</td></tr>
<tr><td>Otonomi</td><td>Bisa override dan memilih latihan manual.</td><td>Bisa jeda/lanjut dalam batas sesi.</td><td>Hindari countdown, streak guilt, dan kelangkaan palsu.</td></tr>
</tbody></table></div>

<div class="riset-grid riset-grid-3 riset-jeda">
<article class="riset-kartu riset-kartu-utama"><span class="riset-label riset-label-teal">Konsep A · utama</span><h3>Setelah salah, tahu langkah berikutnya</h3><p>Paling langsung menghubungkan masalah orang tua dengan fungsi produk. Batas: Jagomat membantu menata keputusan, bukan otomatis menemukan akar masalah.</p></article>
<article class="riset-kartu"><span class="riset-label">Konsep B · trust</span><h3>Bukan cuma benar sekali</h3><p>Kemajuan dicek lagi dengan soal baru dan jeda waktu. Kuat untuk metodologi, tetapi lebih teknis bagi cold traffic.</p></article>
<article class="riset-kartu"><span class="riset-label">Konsep C · reassurance</span><h3>Pendamping, bukan pengganti</h3><p>Menjelaskan human-in-the-loop dan mengurangi resistensi pada otomatisasi, tetapi dapat terdengar menambah pekerjaan.</p></article>
</div>
<div class="riset-callout"><strong>Stress-test semantik, bukan survei pasar</strong><p>Evaluasi terstruktur memprioritaskan konsep A, tetapi hasilnya hanya membantu menyusun urutan eksperimen. Ia tidak memakai sampel calon pelanggan dan tidak menggantikan wawancara, concept test, atau conversion behavior.</p></div>

<h3 class="riset-jeda">Hambatan perilaku dan respons yang etis</h3>
<div class="riset-tabel-bungkus riset-jeda" tabindex="0" role="region" aria-label="Hambatan perilaku belajar matematika">
<table><caption>Jangan menjual ketakutan; kurangi ancaman dan buat tindakan kecil</caption><thead><tr><th scope="col">Hambatan</th><th scope="col">Bagaimana terlihat</th><th scope="col">Respons produk</th><th scope="col">Yang dihindari</th></tr></thead><tbody>
<tr><td>Takut salah</td><td>Menghindar, buru-buru, menebak.</td><td>Feedback spesifik, kesempatan memperbaiki, bahasa netral.</td><td>“Kamu bukan anak matematika”, ranking, rasa malu.</td></tr>
<tr><td>Beban kognitif</td><td>Tidak tahu mulai dari mana.</td><td>Satu tugas berikutnya, contoh bertahap, visual konkret.</td><td>Dashboard penuh pilihan dan istilah diagnosis untuk anak.</td></tr>
<tr><td>Konflik pendampingan</td><td>Orang tua mengulang perintah; anak defensif.</td><td>Skrip bantuan singkat dan minimum involvement.</td><td>Mengubah orang tua menjadi pemeriksa tanpa akhir.</td></tr>
<tr><td>Pujian yang salah sasaran</td><td>Fokus pada “pintar” atau volume usaha.</td><td>Feedback pada strategi yang benar-benar diamati.</td><td>“Coba lebih keras” ketika pendekatan tidak bekerja.</td></tr>
<tr><td>Kebiasaan rapuh</td><td>Berhenti setelah terlewat satu hari.</td><td>Cue stabil, sesi kecil, jeda sah, resume tanpa reset streak.</td><td>Janji “21 hari” atau rasa bersalah.</td></tr>
</tbody></table></div>

<div class="riset-batas riset-jeda">Jagomat bukan layanan psikologi atau terapi. Jangan menjanjikan penurunan kecemasan. Bila distress berat atau konsisten, keluarga perlu bantuan profesional/sekolah yang sesuai.</div>

<h3 class="riset-jeda">Pemicu konversi yang boleh diuji</h3>
<div class="riset-grid riset-grid-3 riset-jeda">
<article class="riset-kartu"><h3>Problem recognition</h3><p>“Anak paham konsep tapi sering salah hitung?” Pertanyaan spesifik lebih berguna daripada ancaman tertinggal.</p></article>
<article class="riset-kartu"><h3>Value preview</h3><p>Tunjukkan contoh anonim bagaimana satu jawaban salah dapat menghasilkan dua tindak lanjut berbeda.</p></article>
<article class="riset-kartu"><h3>Truthful friction</h3><p>Jelaskan bahwa orang tua tetap meninjau hasil. Transparansi menyaring pengguna yang tidak cocok dan mencegah ekspektasi palsu.</p></article>
<article class="riset-kartu"><h3>Milestone proof</h3><p>Gunakan first value: latihan selesai, hasil dikonfirmasi, satu langkah tampil—bukan pendaftaran saja.</p></article>
<article class="riset-kartu"><h3>Privacy assurance</h3><p>Bahasa konkret tentang data, human review, dan apa yang tidak dikirim lebih kuat daripada badge “aman” generik.</p></article>
<article class="riset-kartu"><h3>Low-risk invitation</h3><p>Akses awal terbatas dengan status jujur; jangan menyebut trial/promo/paket aktif sebelum benar-benar tersedia.</p></article>
</div>
</section>

<section class="riset-bagian riset-modul" id="gtm" aria-labelledby="judul-gtm">
<div class="riset-modul-nomor" aria-hidden="true">04</div>
<div class="riset-kepala"><p class="riset-alis">Go-to-market funnel &amp; retention engine</p>
<h2 id="judul-gtm">90 hari untuk mengurangi ketidakpastian—bukan mengejar vanity metrics</h2>
<p>Funnel berakhir pada nilai nyata, bukan lead. Analitik Jagomat saat ini belum mengukur rangkaian first value ≤48 jam; pilot harus memakai agregat manual/minimal yang disetujui sampai purpose, schema, retensi, purge, backup, dan recovery siap.</p></div>

<div class="riset-rumus" tabindex="0" role="region" aria-label="Urutan funnel go-to-market">Visit → intent → signup → latihan disiapkan → selesai → ditinjau → dikonfirmasi → langkah berikutnya → siklus berbukti → referral</div>

<div class="riset-tabel-bungkus riset-jeda" tabindex="0" role="region" aria-label="Definisi funnel GTM Jagomat">
<table><caption>Definisi operasional funnel</caption><thead><tr><th scope="col">Tahap</th><th scope="col">Definisi</th><th scope="col">KPI</th><th scope="col">Counter-metric</th></tr></thead><tbody>
<tr><td>Reach</td><td>Pengunjung relevan pada konten problem-intent.</td><td>Qualified visits/channel</td><td>Traffic tidak relevan, biaya</td></tr>
<tr><td>Intent</td><td>Memulai daftar setelah memahami status akses awal.</td><td>Start rate</td><td>Salah paham soal trial/paket aktif</td></tr>
<tr><td>First value</td><td>Target ≤48 jam: latihan awal selesai, ditinjau, dikonfirmasi, lalu satu langkah tampil.</td><td>% cohort; median time</td><td>Correction, abandonment, support</td></tr>
<tr><td>Verified cycle</td><td>Satu siklus bukti sesuai kontrak, bukan sekadar login.</td><td>% cohort 28/35 hari</td><td>Beban review, eskalasi</td></tr>
<tr><td>Retention</td><td>Kembali saat milestone belajar jatuh tempo.</td><td>M1/M3/M6 milestone retention</td><td>Complaint, notification opt-out</td></tr>
<tr><td>Referral</td><td>Undangan consented setelah nilai dialami.</td><td>Referred family mencapai first value</td><td>Spam atau data anak terbawa</td></tr>
</tbody></table></div>

<h3 class="riset-jeda">Rencana stage-gated 90 hari</h3>
<ol class="riset-urutan riset-jeda">
<li><div><h3>Hari 1–15 · Truth dan comprehension</h3><p>Audit copy akses awal, consent, data map, kapasitas support, lalu uji tiga konsep pada 12–18 orang tua. Gate: mayoritas dapat menjelaskan untuk siapa, masalah apa, dan apa yang tidak dijanjikan.</p></div></li>
<li><div><h3>Hari 16–30 · Usability sintetis</h3><p>Uji daftar → profil → latihan awal dengan data sintetis. Ukur titik friksi dan menit bantuan. Gate: alur dapat selesai tanpa intervensi founder berulang.</p></div></li>
<li><div><h3>Hari 31–55 · Alpha terbatas kapasitas</h3><p>Undang cohort kecil sesuai kapasitas aktual; bandingkan self-service dan onboarding clinic. Ukur first value secara manual/minimal, abandonment, correction, dan support minutes.</p></div></li>
<li><div><h3>Hari 56–75 · Channel microtests</h3><p>Uji problem-intent organic dan belanja kecil Google/Meta hanya jika first value dapat diukur sah. TikTok dipakai untuk discovery kreatif, bukan mengasumsikan conversion. Tidak menarget anak.</p></div></li>
<li><div><h3>Hari 76–90 · Retention awal dan keputusan</h3><p>Uji reminder opt-in hanya bila kanal/consent siap; referral prototype setelah milestone tanpa data anak. Keputusan akhir: tambah sampel terbatas, revisi, atau berhenti—bukan otomatis scale.</p></div></li>
</ol>

<h3 class="riset-jeda">Peran kanal berbayar</h3>
<div class="riset-grid riset-grid-3 riset-jeda">
<article class="riset-kartu riset-kartu-utama"><span class="riset-label riset-label-teal">Prioritas 1</span><h3>Google Search</h3><p>Tangkap problem intent: salah hitung berulang, anak sulit menjelaskan cara, latihan OSN SD. Ukur cost per first-value family, bukan CPC.</p></article>
<article class="riset-kartu"><span class="riset-label">Prioritas 2</span><h3>Meta</h3><p>Concept-test kreatif untuk orang dewasa berdasarkan konteks. Hindari customer-list upload, child targeting, dan retargeting ruang belajar.</p></article>
<article class="riset-kartu"><span class="riset-label">Eksplorasi</span><h3>TikTok</h3><p>Uji format edukatif pendek dan creator fit. Jangan menganggap view murah sebagai CAC murah; validasi sampai first value.</p></article>
</div>
<div class="riset-callout"><strong>Budget envelope adalah asumsi</strong><p>Lean validation Rp10–20 juta/90 hari; pilot standar Rp30–60 juta hanya setelah instrumentation dan kapasitas lolos gate. Pembagian indikatif: riset/kreatif 20–30%, distribusi 35–45%, onboarding/ops 20–30%, contingency 10–15%. Ini bukan benchmark industri atau perintah belanja.</p></div>

<h3 class="riset-jeda">Kill dan scale rules</h3>
<div class="riset-tabel-bungkus riset-jeda" tabindex="0" role="region" aria-label="Aturan penghentian dan peningkatan eksperimen">
<table><caption>Decision rules pilot—harus dikalibrasi setelah baseline</caption><thead><tr><th scope="col">Situasi</th><th scope="col">Tindakan</th><th scope="col">Alasan</th></tr></thead><tbody>
<tr><td>&gt;10% peserta salah memahami paket/trial aktif</td><td>Pause acquisition dan perbaiki copy</td><td>Conversion dari ekspektasi palsu bukan bukti demand</td></tr>
<tr><td>First value tidak dapat diukur sesuai definisi</td><td>Tahan paid scale</td><td>Signup/CPC bukan proxy nilai</td></tr>
<tr><td>Support melewati 80% kapasitas atau SLA</td><td>Throttle cohort</td><td>Pertumbuhan tidak boleh merusak layanan</td></tr>
<tr><td>Cost/first value &gt;2× channel pembanding setelah sampel minimum</td><td>Pause channel</td><td>Uji kualitas cohort sebelum menyalahkan iklan</td></tr>
<tr><td>Satu insiden privasi material</td><td>Hentikan acquisition</td><td>Akar masalah dan koreksi harus selesai lebih dulu</td></tr>
<tr><td>Cohort ≥50 qualified starts, mutu stabil, support aman</td><td>Naikkan spend maksimal 2×/minggu</td><td>Scale terbatas, bukan pengesahan LTV</td></tr>
</tbody></table></div>

<div class="riset-putusan"><h3>Rumus kapasitas sebelum menyalakan iklan</h3><div class="riset-rumus" tabindex="0" role="region" aria-label="Rumus kapasitas keluarga baru per minggu">Keluarga baru/minggu = floor((menit support tersedia × 0,8) ÷ median menit support per keluarga)</div><p>Contoh ilustratif: 600 menit tersedia dan median 20 menit berarti batas 24 keluarga baru, bukan 30. Buffer 20% menjaga kasus sulit dan SLA. Ganti contoh dengan kapasitas aktual sebelum kampanye.</p></div>

<h3 class="riset-jeda">Retention engine berbasis milestone</h3>
<div class="riset-tabel-bungkus riset-jeda" tabindex="0" role="region" aria-label="Milestone retensi Jagomat">
<table><caption>Kembali karena ada nilai, bukan karena streak</caption><thead><tr><th scope="col">Milestone</th><th scope="col">Nilai</th><th scope="col">Trigger etis</th><th scope="col">Jangan</th></tr></thead><tbody>
<tr><td>Latihan awal</td><td>Tahu langkah pertama</td><td>Satu reminder opt-in dengan resume aman</td><td>Countdown tertinggal</td></tr>
<tr><td>First value</td><td>Satu tindak lanjut tampil</td><td>Ringkasan tindakan dan estimasi waktu</td><td>Diagnosis sebagai kebenaran final</td></tr>
<tr><td>Penguatan</td><td>Siap menunggu cek ulang</td><td>Tanggal evaluasi jelas</td><td>Mendorong drill demi DAU</td></tr>
<tr><td>Evaluasi berjeda</td><td>Tahu apakah pendekatan mulai membantu</td><td>Hasil + pilihan pendekatan berikut</td><td>“Sudah menguasai” dari satu skor</td></tr>
<tr><td>Checkpoint</td><td>Melihat apakah hasil bertahan</td><td>Perjalanan ringkas dan langkah selanjutnya</td><td>Streak guilt</td></tr>
<tr><td>Eskalasi</td><td>Mengetahui batas pendekatan</td><td>Penjelasan jujur dan opsi bantuan manusia</td><td>Menahan anak dalam loop tak efektif</td></tr>
</tbody></table></div>

<div class="riset-callout"><strong>Referral moment</strong><p>Jangan meminta referral saat signup. Minta setelah keluarga mengalami first value atau, lebih kuat, evaluasi/checkpoint. Materi bagikan tidak boleh membawa nama, kelas, skor, diagnosis, screenshot laporan, atau klaim kemajuan anak.</p></div>
</section>

<section class="riset-bagian" id="metodologi" aria-labelledby="judul-metodologi">
<div class="riset-kepala"><p class="riset-alis">Metodologi dan keterbatasan</p><h2 id="judul-metodologi">Analisis yang dapat dibantah lebih berguna daripada kepastian palsu</h2><p>Riset dilakukan dari kontrak produk Jagomat, sumber publik, formula transparan, dua lane riset independen, kritik terpisah, dan stress-test semantik terstruktur. Alat bantu tersebut dipakai untuk menemukan blind spot, bukan sebagai responden pasar; keputusan akhir tetap diverifikasi terhadap sumber dan hitungan.</p></div>
<div class="riset-grid riset-grid-2">
<article class="riset-kartu"><h3>Yang dilakukan</h3><ul><li>Memisahkan fakta, proxy, asumsi, hasil hitung, dan rekomendasi.</li><li>Mengaudit source date serta keterbatasan akses.</li><li>Menguji ulang rumus unit economics dan konsistensi unit.</li><li>Menyerang tesis dengan kritik independen sebelum publikasi.</li><li>Mengutamakan core SD dan memisahkan opsi ekspansi.</li></ul></article>
<article class="riset-kartu"><h3>Yang belum dilakukan</h3><ul><li>Wawancara atau survei orang tua/tutor baru untuk laporan ini.</li><li>Trial produk berbayar kompetitor atau audit operasi internal.</li><li>Pengukuran CAC, churn, support, WTP, atau outcome Jagomat.</li><li>Market sizing household dari microdata primer.</li><li>Valuasi perusahaan atau forecast kas.</li></ul></article>
</div>
<details class="riset-detail riset-jeda"><summary>Catatan tentang denominator jumlah murid</summary><div class="riset-detail-isi"><p>Publikasi Statistik Pendidikan 2024 BPS tersedia, tetapi tabel jumlah murid per tingkat tidak berhasil diekstrak pada sesi ini. Sumber sekunder lama juga tidak lagi menyediakan tautan yang dapat diaudit. Karena itu laporan menahan angka TAM volume dan revenue sampai tabel primer berhasil diverifikasi.</p></div></details>
<details class="riset-detail"><summary>Catatan tentang harga Jagomat</summary><div class="riset-detail-isi"><p>Rencana Jago/Jago Pro mencantumkan Rp29 ribu/Rp59 ribu bulanan dan Rp290 ribu/Rp590 ribu tahunan, tetapi paket, masa coba, promo, dan pembayaran belum aktif. Skenario ARPA bukan penawaran publik atau bukti willingness-to-pay.</p></div></details>
<details class="riset-detail"><summary>Catatan tentang kompetitor</summary><div class="riset-detail-isi"><p>Harga dan paket dinamis. Data Ruangguru/Kumon diikat ke halaman/tanggal; halaman Zenius/GO tidak seluruhnya dapat diaudit otomatis secara andal. Official marketing membuktikan apa yang ditampilkan, bukan efektivitas atau operasi internal.</p></div></details>
<details class="riset-detail"><summary>Catatan tentang psikologi</summary><div class="riset-detail-isi"><p>Mayoritas studi bukan konteks anak SD Indonesia atau Jagomat. Hubungan math anxiety–achievement tidak sama dengan diagnosis individu atau bukti bahwa Jagomat dapat mengurangi kecemasan.</p></div></details>
</section>

<section class="riset-bagian" id="sumber" aria-labelledby="judul-sumber">
<div class="riset-kepala"><p class="riset-alis">Sumber dan provenance</p><h2 id="judul-sumber">Rujukan utama</h2><p>Diakses 13 Oktober 2026 kecuali tanggal publikasi dinyatakan. Tautan primer diutamakan; keterbatasan dicatat pada laporan.</p></div>
<ol class="riset-sumber">
<li><a href="https://www.bps.go.id/id/publication/2024/11/22/c20eb87371b77ee79ea1fa86/statistik-pendidikan-2024.html">BPS · Statistik Pendidikan 2024</a> — keberadaan publikasi primer; tabel tidak berhasil diekstrak.</li>
<li><a href="https://api.worldbank.org/v2/country/IDN/indicator/IT.NET.USER.ZS?format=json">World Bank · Individuals using the Internet, Indonesia</a> — 72,78075544% pada 2024.</li>
<li><a href="https://www.ruangguru.com/blog/informasi-produk-ruangguru-yang-jadi-unggulan">Ruangguru · Info produk dan harga TA 2025/2026</a> — dipublikasikan 9 Januari, dimodifikasi 9 Juni 2026; harga dapat berubah.</li>
<li><a href="https://id.kumonglobal.com/metode-kumon/?lang=id">Kumon Indonesia · Metode Kumon</a> — materi perseorangan, worksheet bertahap, dan peran pembimbing.</li>
<li><a href="https://id.kumonglobal.com/biaya-kursus/?lang=id">Kumon Indonesia · Biaya kursus</a> — efektif 1 Januari 2026; SD Rp430–525 ribu/subjek/bulan menurut wilayah.</li>
<li><a href="https://midtrans.com/id/pricing">Midtrans · Biaya transaksi</a> — QRIS 0,7% saat snapshot; tarif dapat berubah.</li>
<li><a href="https://doi.org/10.1037/bul0000307">Barroso et al. (2021)</a> — meta-analisis hubungan math anxiety dan achievement.</li>
<li><a href="https://doi.org/10.1177/0956797615592630">Maloney et al. (2015)</a> — kecemasan matematika orang tua dan outcome anak dalam kondisi tertentu.</li>
<li><a href="https://doi.org/10.1177/0956797617739704">Sisk et al. (2018)</a> — dua meta-analisis growth mindset; efek akademik kecil/heterogen.</li>
<li><a href="https://doi.org/10.1038/s41586-019-1466-y">Yeager et al. (2019)</a> — eksperimen nasional growth mindset dan pentingnya konteks.</li>
<li><a href="https://doi.org/10.1037/0022-3514.75.1.33">Mueller &amp; Dweck (1998)</a> — risiko pujian kecerdasan pada motivasi/performa.</li>
<li><a href="https://doi.org/10.3102/003465430298487">Hattie &amp; Timperley (2007)</a> — feedback, tujuan, progres, dan next step.</li>
<li><a href="https://doi.org/10.1002/ejsp.674">Lally et al. (2010)</a> — pembentukan kebiasaan bervariasi; bukan aturan universal 21 hari.</li>
<li><a href="https://doi.org/10.1037/0033-2909.132.3.354">Cepeda et al. (2006)</a> — distributed practice/spacing; transfer ke Jagomat tetap perlu diuji.</li>
<li><a href="https://www.oecd.org/en/publications/pisa-2022-results-volume-v_2ee5d1e8-en.html">OECD · PISA 2022 Volume V</a> — konteks sikap dan strategi belajar; peserta usia 15 tahun, bukan bukti produk SD.</li>
<li><a href="/riset/persaingan-bimbel-2026">Jagomat · Audit lanskap persaingan bimbel 2026</a> — laporan rinci terdahulu dengan sumber dan keterbatasan.</li>
</ol>
<p class="riset-catatan riset-jeda">Analisis independen, tidak berafiliasi dengan pemain yang disebut. Nama dan merek merupakan milik pemegang hak masing-masing. Laporan ini bukan nasihat investasi, hukum, psikologi, atau jaminan hasil belajar.</p>
</section>
</div></main>
<footer class="riset-footer"><div class="riset-bungkus riset-footer-dalam"><p>Jagomat · Jago karena tahu caranya.</p><p><a href="/">Kembali ke Jagomat</a> · <a href="{JALUR_PDF}">Unduh PDF</a></p></div></footer>
</body></html>""".encode("utf-8")


def kirim_pdf(penangan) -> None:
    """Kirim PDF business case statis dengan nama dan MIME ketat."""
    try:
        isi = BERKAS_PDF.read_bytes()
    except OSError:
        from support_pages import halaman_pesan

        penangan._kirim(
            halaman_pesan(
                "Laporan belum tersedia",
                "<h1>Laporan belum tersedia</h1><p>Coba lagi beberapa saat.</p>",
            ),
            503,
        )
        return
    penangan.send_response(200)
    penangan.send_header("Content-Type", "application/pdf")
    penangan.send_header("Content-Length", str(len(isi)))
    penangan.send_header("Content-Disposition", f'attachment; filename="{NAMA_PDF}"')
    penangan.send_header("Cache-Control", "public, max-age=3600")
    penangan.send_header("X-Content-Type-Options", "nosniff")
    penangan.end_headers()
    penangan.wfile.write(isi)
