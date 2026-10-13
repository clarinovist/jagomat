"""Laporan publik lanskap persaingan bimbel Indonesia 2026.

Halaman ini statis dan read-only. Ia tidak membuka basis data, membaca sesi,
atau memproyeksikan data keluarga. Observasi publik, inferensi strategi, dan
rekomendasi untuk Jagomat dibedakan agar laporan tidak menyamarkan pendapat
sebagai fakta pasar.
"""
from __future__ import annotations

from pathlib import Path

import brand
import design_tokens as T

JALUR = "/riset/persaingan-bimbel-2026"
JALUR_PDF = f"{JALUR}.pdf"
NAMA_PDF = "jagomat-riset-persaingan-bimbel-2026.pdf"
BERKAS_PDF = Path(__file__).resolve().parent / "publik" / NAMA_PDF

RINGKASAN_META = (
    "Analisis independen lanskap bimbel Indonesia: kelemahan struktural pemain, "
    "unfair advantage Jagomat, pilihan PLG-assisted, dan risiko strategis."
)


def _font_link() -> str:
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700'
        '&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap" rel="stylesheet">'
    )


GAYA_RISET = f"""
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; scroll-padding-top: 5.5rem; }}
body {{
  margin: 0; background: {T.LATAR_MURID}; color: {T.TEKS_UTAMA};
  font-family: {T.FONT_BODY}; font-size: {T.UKURAN_BADAN_LAYAR};
  line-height: {T.LINE_HEIGHT}; -webkit-text-size-adjust: 100%;
}}
a {{ color: {T.AKSEN_TEAL_TUA}; text-underline-offset: .18em; }}
a:hover {{ color: {T.AKSEN_TEAL_HOVER}; }}
a:focus-visible, summary:focus-visible {{
  outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: {T.SP_1};
  border-radius: {T.RADIUS_KECIL};
}}
img {{ display: block; max-width: 100%; }}
h1, h2, h3, h4 {{
  color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; line-height: 1.18;
  text-wrap: balance;
}}
h1 {{ font-size: clamp(2.2rem, 5.7vw, 4.8rem); letter-spacing: -.045em; margin: 0; max-width: 16ch; }}
h2 {{ font-size: clamp(1.7rem, 3vw, 2.7rem); letter-spacing: -.025em; margin: 0; }}
h3 {{ font-size: clamp(1.1rem, 1.6vw, 1.35rem); margin: 0; }}
p {{ margin: 0; }}
.riset-lewati {{
  position: absolute; left: {T.SP_4}; top: -5rem; z-index: 100;
  background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; padding: {T.SP_3} {T.SP_4};
  border-radius: {T.RADIUS_KECIL}; font-weight: 700;
}}
.riset-lewati:focus {{ top: {T.SP_4}; }}
.riset-topbar {{
  position: sticky; top: 0; z-index: 30; border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  background: {T.LATAR_SEKUNDER_LEMBUT};
}}
.riset-topbar-dalam {{
  width: min(calc(100% - 2rem), {T.LEBAR_LANDING}); min-height: 4rem; margin: 0 auto;
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_4};
}}
.riset-brand {{
  display: inline-flex; align-items: center; gap: {T.SP_2}; color: {T.TEKS_JUDUL};
  text-decoration: none; font-family: {T.FONT_HEADLINE}; font-weight: 800;
}}
.riset-nav {{ display: flex; align-items: center; gap: {T.SP_2}; }}
.riset-nav a {{
  display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH};
  padding: 0 {T.SP_3}; border-radius: {T.RADIUS_PIL}; text-decoration: none; font-weight: 700;
}}
.riset-unduh {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; }}
.riset-unduh:hover {{ background: {T.AKSEN_TEAL_HOVER}; color: {T.TEKS_PUTIH}; }}
.riset-bungkus {{ width: min(calc(100% - 2rem), {T.LEBAR_LANDING}); margin: 0 auto; }}
.riset-hero {{
  min-height: min(48rem, calc(100vh - 4rem)); display: grid; align-items: center;
  gap: {T.SP_7}; padding: {T.SP_8} 0;
}}
.riset-alis {{
  color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_TEKS_LABEL};
  font-weight: 800; letter-spacing: .08em; text-transform: uppercase;
}}
.riset-hero-copy {{ display: grid; gap: {T.SP_5}; }}
.riset-dek {{ max-width: 64ch; color: {T.TEKS_VARIAN}; font-size: clamp(1.05rem, 2vw, 1.3rem); }}
.riset-meta {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; }}
.riset-chip {{
  display: inline-flex; align-items: center; min-height: 2rem; padding: {T.SP_1} {T.SP_3};
  background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_PIL}; color: {T.TEKS_VARIAN}; font-size: {T.UKURAN_TEKS_CATATAN}; font-weight: 700;
}}
.riset-keputusan {{
  display: grid; gap: {T.SP_4}; align-content: start; padding: {T.SP_6};
  background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_KARTU_BESAR};
  box-shadow: {T.BAYANGAN_MENU};
}}
.riset-keputusan .riset-alis {{ color: {T.AKSEN_MURID_AMBER}; }}
.riset-keputusan h2 {{ color: {T.TEKS_PUTIH}; font-size: clamp(1.45rem, 2.4vw, 2rem); }}
.riset-keputusan strong {{ color: {T.AKSEN_MURID_AMBER}; }}
.riset-keputusan ul {{ margin: 0; padding-left: {T.SP_5}; display: grid; gap: {T.SP_2}; }}
.riset-indeks {{
  display: flex; gap: {T.SP_2}; overflow-x: auto; padding: {T.SP_4} 0 {T.SP_5};
  border-top: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
}}
.riset-indeks a {{
  flex: 0 0 auto; min-height: {T.TARGET_SENTUH}; display: inline-flex; align-items: center;
  padding: 0 {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_PIL}; background: {T.LATAR_KARTU}; text-decoration: none; font-weight: 700;
}}
.riset-bagian {{ padding: {T.SP_8} 0; border-top: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; }}
.riset-kepala {{ display: grid; gap: {T.SP_3}; margin-bottom: {T.SP_6}; max-width: 62rem; }}
.riset-kepala > p:last-child {{ color: {T.TEKS_VARIAN}; max-width: 70ch; }}
.riset-callout {{
  display: grid; gap: {T.SP_3}; margin: {T.SP_6} 0; padding: {T.SP_5};
  background: {T.LATAR_CATATAN}; border-left: .35rem solid {T.AKSEN_MURID_AMBER};
  border-radius: 0 {T.RADIUS_KARTU} {T.RADIUS_KARTU} 0;
}}
.riset-callout strong {{ color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-size: 1.1rem; }}
.riset-grid {{ display: grid; gap: {T.SP_4}; }}
.riset-kartu {{
  display: grid; gap: {T.SP_4}; padding: {T.SP_5}; background: {T.LATAR_KARTU};
  border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU_BESAR};
  box-shadow: {T.BAYANGAN_KARTU};
}}
.riset-kartu p, .riset-kartu li {{ color: {T.TEKS_VARIAN}; }}
.riset-kartu ul {{ margin: 0; padding-left: {T.SP_5}; display: grid; gap: {T.SP_2}; }}
.riset-label {{
  width: fit-content; padding: {T.SP_1} {T.SP_3}; border-radius: {T.RADIUS_PIL};
  background: {T.LATAR_SEKUNDER_NETRAL}; color: {T.TEKS_VARIAN};
  font-size: {T.UKURAN_TEKS_META}; font-weight: 800; letter-spacing: .045em; text-transform: uppercase;
}}
.riset-label-teal {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.riset-label-koral {{ background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; }}
.riset-label-amber {{ background: {T.LATAR_CATATAN}; color: {T.TEKS_REVIEW}; }}
.riset-detail {{
  background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU_BESAR}; overflow: clip;
}}
.riset-detail + .riset-detail {{ margin-top: {T.SP_3}; }}
.riset-detail summary {{
  min-height: 4.5rem; padding: {T.SP_4} {T.SP_5}; cursor: pointer; list-style: none;
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_4};
  color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-weight: 800;
}}
.riset-detail summary::-webkit-details-marker {{ display: none; }}
.riset-detail summary::after {{ content: "+"; font-size: 1.5rem; color: {T.AKSEN_TEAL_TUA}; }}
.riset-detail[open] summary {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.riset-detail[open] summary::after {{ content: "−"; }}
.riset-detail-isi {{ display: grid; gap: {T.SP_4}; padding: 0 {T.SP_5} {T.SP_5}; }}
.riset-lensa {{
  display: grid; gap: {T.SP_3}; padding: {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_SEKUNDER_LEMBUT};
}}
.riset-lensa b {{ color: {T.TEKS_JUDUL}; }}
.riset-confidence {{ font-size: {T.UKURAN_TEKS_CATATAN}; color: {T.TEKS_VARIAN}; font-weight: 700; }}
.riset-tabel-bungkus {{ overflow-x: auto; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
table {{ width: 100%; min-width: 50rem; border-collapse: collapse; background: {T.LATAR_KARTU}; }}
th, td {{ padding: {T.SP_4}; text-align: left; vertical-align: top; border-bottom: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; }}
th {{ color: {T.TEKS_JUDUL}; background: {T.LATAR_SEKUNDER_LEMBUT}; font-family: {T.FONT_HEADLINE}; }}
tr:last-child td {{ border-bottom: 0; }}
.riset-peta {{
  display: grid; grid-template-columns: 6rem minmax(0, 1fr); gap: {T.SP_3};
  padding: {T.SP_5}; background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU_BESAR};
}}
.riset-sumbu-y {{
  writing-mode: vertical-rl; transform: rotate(180deg); text-align: center;
  color: {T.TEKS_VARIAN}; font-size: {T.UKURAN_TEKS_CATATAN}; font-weight: 700;
}}
.riset-kuadran {{
  min-height: 27rem; display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr;
  background: {T.LATAR_SEKUNDER_LEMBUT}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
}}
.riset-kuadran > div {{ position: relative; padding: {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; }}
.riset-kuadran small {{ color: {T.TEKS_VARIAN}; font-weight: 700; }}
.riset-titik {{
  display: inline-flex; margin: {T.SP_1}; padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_PIL};
  background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; font-weight: 800; box-shadow: {T.BAYANGAN_NOMOR};
}}
.riset-titik-jagomat {{ background: {T.AKSEN_TEAL_TUA}; }}
.riset-sumbu-x {{ grid-column: 2; display: flex; justify-content: space-between; color: {T.TEKS_VARIAN}; font-size: {T.UKURAN_TEKS_CATATAN}; font-weight: 700; }}
.riset-loop {{ display: grid; gap: {T.SP_3}; counter-reset: loop; }}
.riset-loop li {{
  counter-increment: loop; list-style: none; display: grid; grid-template-columns: 2.6rem 1fr;
  gap: {T.SP_3}; align-items: start; padding: {T.SP_4}; background: {T.LATAR_KARTU};
  border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU};
}}
.riset-loop li::before {{
  content: counter(loop, decimal-leading-zero); width: 2.6rem; height: 2.6rem;
  display: grid; place-items: center; border-radius: {T.RADIUS_BULAT};
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font-weight: 800;
}}
.riset-loop b {{ display: block; color: {T.TEKS_JUDUL}; margin-bottom: {T.SP_1}; }}
.riset-duel {{ display: grid; gap: {T.SP_4}; }}
.riset-duel .riset-kartu:first-child {{ border-top: .35rem solid {T.AKSEN_MURID_KORAL}; }}
.riset-duel .riset-kartu:last-child {{ border-top: .35rem solid {T.AKSEN_TEAL_TUA}; }}
.riset-risiko {{ display: grid; gap: {T.SP_4}; }}
.riset-risiko article {{
  display: grid; gap: {T.SP_4}; padding: {T.SP_5}; background: {T.LATAR_KARTU};
  border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU_BESAR};
}}
.riset-risiko-nomor {{ color: {T.AKSEN_KORAL_TUA}; font-family: {T.FONT_HEADLINE}; font-size: 2.5rem; font-weight: 800; }}
.riset-risiko dl {{ display: grid; gap: {T.SP_3}; margin: 0; }}
.riset-risiko dt {{ color: {T.TEKS_JUDUL}; font-weight: 800; }}
.riset-risiko dd {{ margin: 0; color: {T.TEKS_VARIAN}; }}
.riset-roadmap {{ display: grid; gap: {T.SP_3}; }}
.riset-roadmap article {{
  display: grid; grid-template-columns: 6rem 1fr; gap: {T.SP_4}; padding: {T.SP_5};
  background: {T.LATAR_KARTU}; border-left: .35rem solid {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_KARTU};
}}
.riset-roadmap time {{ color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE}; font-weight: 800; }}
.riset-roadmap ul {{ margin: {T.SP_2} 0 0; padding-left: {T.SP_5}; }}
.riset-sumber {{ padding-left: {T.SP_5}; display: grid; gap: {T.SP_3}; }}
.riset-catatan {{ color: {T.TEKS_VARIAN}; font-size: {T.UKURAN_TEKS_CATATAN}; }}
.riset-footer {{
  padding: {T.SP_6} 0; background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH};
}}
.riset-footer-dalam {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: {T.SP_4}; }}
.riset-footer a {{ color: {T.TEKS_PUTIH}; }}
@media (min-width: {T.BATAS_HP}) {{
  .riset-grid-2, .riset-duel {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .riset-grid-3 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
}}
@media (min-width: {T.MULAI_DESKTOP}) {{
  .riset-hero {{ grid-template-columns: minmax(0, 1.2fr) minmax(21rem, .8fr); }}
  .riset-grid-3 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
  .riset-risiko {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
}}
@media (max-width: {T.BATAS_HP}) {{
  .riset-nav .riset-nav-teks {{ display: none; }}
  .riset-topbar-dalam, .riset-bungkus {{ width: min(calc(100% - 1.25rem), {T.LEBAR_LANDING}); }}
  .riset-hero, .riset-bagian {{ padding-top: {T.SP_7}; padding-bottom: {T.SP_7}; }}
  .riset-keputusan, .riset-kartu, .riset-risiko article {{ padding: {T.SP_4}; }}
  .riset-peta {{ grid-template-columns: 1fr; padding: {T.SP_3}; }}
  .riset-sumbu-y {{ writing-mode: horizontal-tb; transform: none; }}
  .riset-sumbu-x {{ grid-column: 1; }}
  .riset-kuadran {{ min-height: 32rem; }}
  .riset-titik {{ font-size: {T.UKURAN_TEKS_META}; }}
  .riset-roadmap article {{ grid-template-columns: 1fr; }}
}}
@media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} * {{ transition-duration: 0.01ms !important; }} }}
@media print {{
  @page {{ size: A4; margin: 14mm 13mm 16mm; }}
  body {{ background: {T.TEKS_PUTIH}; color: {T.CETAK_TINTA}; font-size: 9pt; }}
  .riset-topbar, .riset-indeks, .riset-web-saja, .riset-footer {{ display: none !important; }}
  .riset-bungkus {{ width: 100%; }}
  .riset-hero {{ min-height: auto; display: block; padding: 0 0 10mm; }}
  .riset-hero-copy {{ gap: 4mm; }}
  .riset-keputusan {{ margin-top: 8mm; background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.CETAK_TINTA}; box-shadow: none; }}
  .riset-keputusan h2, .riset-keputusan strong {{ color: {T.TEKS_JUDUL}; }}
  .riset-bagian {{ padding: 9mm 0; }}
  .riset-kartu, .riset-detail, .riset-risiko article, .riset-roadmap article, .riset-peta {{ break-inside: avoid; box-shadow: none; }}
  .riset-detail > summary {{ display: none; }}
  .riset-detail > .riset-detail-isi {{ display: grid; padding: 5mm; }}
  .riset-detail:not([open]) > .riset-detail-isi {{ display: grid; }}
  a {{ color: {T.CETAK_TINTA}; text-decoration: none; }}
  a[href^="http"]::after {{ content: " — " attr(href); font-size: 7pt; overflow-wrap: anywhere; }}
  h1 {{ font-size: 28pt; }} h2 {{ font-size: 20pt; }} h3 {{ font-size: 13pt; }}
}}
"""


def halaman() -> bytes:
    """Render laporan HTML statis tanpa membaca state pengguna."""
    logo = brand.mark("topbar")
    tag_kepala = brand.tag_kepala({
        "judul": "Lanskap persaingan bimbel Indonesia 2026 · Jagomat",
        "deskripsi": RINGKASAN_META,
        "jalur": JALUR,
    })
    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{brand.judul('Lanskap persaingan bimbel Indonesia 2026')}</title>
{tag_kepala}{_font_link()}<style>{GAYA_RISET}</style></head>
<body><a class="riset-lewati" href="#konten-riset">Lewati ke laporan</a>
<header class="riset-topbar"><div class="riset-topbar-dalam">
<a class="riset-brand" href="/">{logo}<span>Jagomat</span></a>
<nav class="riset-nav" aria-label="Aksi laporan">
<a class="riset-nav-teks" href="#metodologi">Metodologi</a>
<a class="riset-unduh" href="{JALUR_PDF}">Unduh PDF</a>
</nav></div></header>
<main id="konten-riset">
<div class="riset-bungkus">
<section class="riset-hero" aria-labelledby="judul-riset">
<div class="riset-hero-copy">
<p class="riset-alis">Jagomat Strategy Brief · Indonesia</p>
<h1 id="judul-riset">Analisis lanskap persaingan bimbel dan les online</h1>
<p class="riset-dek">Di pasar yang dipenuhi konten, kelas, dan promosi, ruang paling defensible bagi Jagomat bukan “lebih banyak soal”—melainkan keputusan belajar yang lebih tepat dan dapat dibuktikan.</p>
<div class="riset-meta" aria-label="Metadata laporan">
<span class="riset-chip">Snapshot riset · 13 Oktober 2026</span>
<span class="riset-chip">Fokus · Matematika kelas 3–6</span>
<span class="riset-chip">Observasi publik + inferensi strategi</span>
</div>
</div>
<aside class="riset-keputusan" aria-labelledby="keputusan-utama">
<p class="riset-alis">Keputusan utama</p>
<h2 id="keputusan-utama">Menangkan momen setelah anak salah.</h2>
<p>Jagomat harus menjawab tiga hal: <strong>mengapa salah, apa langkah berikutnya, dan apakah intervensinya berhasil.</strong></p>
<ul>
<li>Moat: verified learning loop, bukan chatbot.</li>
<li>GTM: PLG-assisted, bukan sales keluarga.</li>
<li>Ekspansi: tutor sebagai kanal, bukan scope baru.</li>
</ul>
</aside>
</section>
<nav class="riset-indeks" aria-label="Bagian laporan">
<a href="#ringkasan">Ringkasan</a><a href="#peta-arena">Peta arena</a>
<a href="#pemain">Pemain</a><a href="#moat">Unfair advantage</a>
<a href="#gtm">PLG vs SLG</a><a href="#risiko">Risiko</a>
<a href="#roadmap">Roadmap</a><a href="#metodologi">Metodologi</a>
</nav>

<section class="riset-bagian" id="ringkasan" aria-labelledby="judul-ringkasan">
<div class="riset-kepala"><p class="riset-alis">01 · Kesimpulan eksekutif</p>
<h2 id="judul-ringkasan">Pasar konten sudah padat. Pasar keputusan belajar belum.</h2>
<p>Ruangguru unggul pada skala dan distribusi; Zenius pada pemahaman konseptual dan harga akses; GO pada merek, pengajar, dan orientasi ujian; Kumon pada metode individual serta kebiasaan belajar. Jagomat tidak seharusnya menyalin mesin keunggulan mereka.</p></div>
<div class="riset-grid riset-grid-3">
<article class="riset-kartu"><span class="riset-label riset-label-koral">Hindari</span><h3>Perang katalog</h3><p>Jumlah video, soal, guru, atau badge mudah dibandingkan dan didiskon. AI generatif makin menekan nilai konten generik.</p></article>
<article class="riset-kartu"><span class="riset-label riset-label-teal">Miliki</span><h3>Loop belajar berbukti</h3><p>Hubungkan pola kesalahan, intervensi, latihan, evaluasi berjeda, dan bukti kemajuan menjadi satu workflow.</p></article>
<article class="riset-kartu"><span class="riset-label riset-label-amber">Distribusikan</span><h3>Melalui produk dan tutor</h3><p>Self-service membuktikan nilai; onboarding selektif mengurangi friksi; tutor memperluas distribusi setelah core loop teruji.</p></article>
</div>
<div class="riset-callout"><strong>Tesis strategi</strong><p>Jagomat tidak perlu memenangkan kategori “bimbel online”. Jagomat perlu menjadi sistem pendamping keputusan belajar matematika keluarga.</p></div>
</section>

<section class="riset-bagian" id="peta-arena" aria-labelledby="judul-peta">
<div class="riset-kepala"><p class="riset-alis">02 · Peta arena</p><h2 id="judul-peta">Lebar versus dalam, konten versus keputusan</h2>
<p>Peta ini bersifat directional—bukan pengukuran market share, kualitas absolut, atau posisi berdasarkan data internal pemain.</p></div>
<div class="riset-peta" role="img" aria-label="Peta posisi directional. Sumbu mendatar dari konten ke keputusan belajar. Sumbu tegak dari fokus sempit ke cakupan luas. Ruangguru berada pada cakupan luas dan konten, Zenius pada konten konseptual, GO pada delivery kelas, Kumon pada metode individual, dan Jagomat ditargetkan pada keputusan belajar dengan fokus sempit.">
<div class="riset-sumbu-y">Cakupan sempit → luas</div>
<div class="riset-kuadran">
<div><small>Cakupan luas · konten/delivery</small><p><span class="riset-titik">Ruangguru</span><span class="riset-titik">GO</span></p></div>
<div><small>Cakupan luas · keputusan</small><p class="riset-catatan">Ruang sulit: kompleks dan mahal dioperasikan pada skala.</p></div>
<div><small>Fokus sempit · konten/metode</small><p><span class="riset-titik">Zenius</span><span class="riset-titik">Kumon</span></p></div>
<div><small>Fokus sempit · keputusan</small><p><span class="riset-titik riset-titik-jagomat">Target Jagomat</span></p></div>
</div><div class="riset-sumbu-x"><span>Konten & kelas</span><span>Keputusan & bukti</span></div>
</div>
<div class="riset-tabel-bungkus" style="margin-top:{T.SP_5}"><table>
<caption class="riset-lewati">Perbandingan mesin keunggulan dan celah relatif pemain</caption>
<thead><tr><th>Arena</th><th>Pemain</th><th>Mesin keunggulan</th><th>Celah relatif yang relevan</th></tr></thead>
<tbody>
<tr><td>Platform horizontal</td><td>Ruangguru</td><td>Brand, konten luas, live class, cabang, privat, AI</td><td>Sulit mengoptimalkan satu problem mikro secara mendalam</td></tr>
<tr><td>Konten konseptual</td><td>Zenius</td><td>Penjelasan konsep, video, latihan, tryout, harga akses</td><td>Content-centric dan menuntut self-direction</td></tr>
<tr><td>Bimbel berjaringan</td><td>GO</td><td>Pengajar, cabang, bahan ajar, TOBK, IRT</td><td>Fixed cost dan variasi delivery manusia</td></tr>
<tr><td>Metode individual</td><td>Kumon</td><td>Worksheet bertahap, pembimbing, kebiasaan, pelaporan</td><td>Personalisasi dalam jalur metode yang terstandardisasi</td></tr>
<tr><td>Pendamping keputusan</td><td>Jagomat</td><td>Pola kesalahan → intervensi → evaluasi berjeda</td><td>Outcome, engagement, dan willingness-to-pay belum terbukti</td></tr>
</tbody></table></div>
</section>

<section class="riset-bagian" id="pemain" aria-labelledby="judul-pemain">
<div class="riset-kepala"><p class="riset-alis">03 · Kelemahan struktural pemain</p>
<h2 id="judul-pemain">Eksploitasi trade-off mereka—bukan menyerang mereknya</h2>
<p>“Kelemahan” berikut adalah bayangan dari skala dan model operasi masing-masing. Tidak terlihat pada halaman publik bukan berarti suatu kapabilitas tidak ada.</p></div>

<details class="riset-detail" open><summary>Ruangguru · breadth menciptakan kompleksitas</summary><div class="riset-detail-isi">
<div class="riset-lensa"><b>Observasi</b><p>Portofolio publik mencakup video adaptif, Dafa & Lulu, Brain Academy online dan lebih dari 270 cabang, privat, Roboguru, tryout, AI, bahasa, coding, serta layanan persiapan studi.</p></div>
<div class="riset-lensa"><b>Inferensi</b><p>Produk horizontal harus membagi perhatian ke banyak jenjang, tujuan, dan mode delivery. Pengalaman sangat mendalam untuk satu pola kesalahan anak berisiko kalah prioritas dari fitur berskala besar.</p><p class="riset-confidence">Confidence: tinggi untuk kompleksitas portofolio; sedang untuk kedalaman diagnosis internal.</p></div>
<div class="riset-lensa"><b>Implikasi untuk Jagomat</b><p>Jangan tandingi jumlah konten atau guru. Menangkan resolusi diagnosis dan kejelasan satu tindakan berikutnya.</p></div>
</div></details>

<details class="riset-detail"><summary>Zenius · kuat pada konsep, masih content-centric</summary><div class="riset-detail-isi">
<div class="riset-lensa"><b>Observasi</b><p>Zenius aktif kembali dengan materi SD–UTBK, video, latihan, PDF, tryout, bank soal, dan ZenCore adaptif. Aplikasi Android diluncurkan kembali pada 7 Juli 2026. Paket premium 12 bulan tampil Rp450.000 saat snapshot.</p></div>
<div class="riset-lensa"><b>Inferensi</b><p>Unit nilai utama tetap akses konten dan latihan; perbandingan harga mudah terjadi. Self-directed learning paling kuat bagi siswa yang sudah tahu apa yang perlu dipelajari.</p><p class="riset-confidence">Confidence: tinggi untuk kondisi produk publik; sedang untuk implikasi kapabilitas organisasi.</p></div>
<div class="riset-lensa"><b>Implikasi untuk Jagomat</b><p>Bergerak dari “membantu memahami” menjadi “menentukan apa yang bermasalah, memilih intervensi, dan membuktikan hasilnya”. Jangan memakai narasi usang bahwa Zenius masih berhenti beroperasi.</p></div>
</div></details>

<details class="riset-detail"><summary>Ganesha Operation · delivery kuat, personalisasi dibatasi kapasitas</summary><div class="riset-detail-isi">
<div class="riset-lensa"><b>Observasi</b><p>Situs resmi menonjolkan pengajar, bahan ajar dan latihan, TOBK, GO Kreasi, serta penilaian IRT. Bukti publik terstruktur yang dapat diakses dalam riset ini terbatas.</p></div>
<div class="riset-lensa"><b>Inferensi</b><p>Cabang dan guru memberi kepercayaan, tetapi menambah fixed cost dan variasi pelaksana. Kelas cenderung mengoptimalkan kelompok; diagnosis mikro menyerap waktu pengajar.</p><p class="riset-confidence">Confidence: sedang–rendah; perlu wawancara pengguna dan observasi cabang.</p></div>
<div class="riset-lensa"><b>Implikasi untuk Jagomat</b><p>Jangan menggantikan guru. Jadilah infrastructure layer yang membantu tutor menghasilkan latihan, tindak lanjut, dan laporan konsisten.</p></div>
</div></details>

<details class="riset-detail"><summary>Kumon · pesaing filosofi yang paling dekat</summary><div class="riset-detail-isi">
<div class="riset-lensa"><b>Observasi</b><p>Kumon menawarkan materi perseorangan menurut kemampuan, worksheet bertahap, pembimbing, belajar mandiri, serta KUMON CONNECT untuk progres digital. Biaya resmi 2026 untuk SD Rp430.000–Rp525.000 per subjek per bulan, ditambah pendaftaran.</p></div>
<div class="riset-lensa"><b>Inferensi</b><p>Personalisasi berlangsung di dalam jalur worksheet yang sangat terstandardisasi. Digitalisasi memperkuat metode yang sama, bukan otomatis memperluas diagnosis pola kesalahan.</p><p class="riset-confidence">Confidence: tinggi berdasarkan metode dan harga resmi publik.</p></div>
<div class="riset-lensa"><b>Implikasi untuk Jagomat</b><p>“Kurikulum personal”, worksheet digital, dan laporan orang tua bukan pembeda. Jagomat harus menjual precision of intervention: jawaban salah yang sama dapat memerlukan bantuan berbeda.</p></div>
</div></details>
</section>

<section class="riset-bagian" id="moat" aria-labelledby="judul-moat">
<div class="riset-kepala"><p class="riset-alis">04 · Unfair advantage</p><h2 id="judul-moat">Bangun verified learning loop</h2>
<p>Fitur individual mudah ditiru. Daya tahan muncul ketika seluruh langkah membentuk sistem yang membaik melalui workflow, kepercayaan, data outcome, dan kebiasaan keluarga.</p></div>
<ol class="riset-loop">
<li><div><b>Taksonomi kesalahan yang actionable</b>B/K/H/E/T/N harus menghasilkan bantuan berbeda, dikonfirmasi manusia, dan membawa tingkat ketidakpastian yang jujur.</div></li>
<li><div><b>Soal parametrik dan deterministik</b>Variasi baru menguji konsep yang sama tanpa sekadar mengulang soal, sehingga transfer pemahaman dapat diperiksa.</div></li>
<li><div><b>Intervensi spesifik</b>Rekomendasi menghubungkan pola yang diamati dengan contoh, latihan terbimbing, dan penguatan yang relevan.</div></li>
<li><div><b>Evaluasi berjeda</b>Kemajuan diuji kembali pada hari berbeda dan soal baru—bukan disimpulkan dari satu jawaban benar.</div></li>
<li><div><b>Action–outcome graph</b>Dengan persetujuan dan privasi ketat, sistem belajar intervensi mana yang bekerja untuk konteks kesalahan tertentu.</div></li>
<li><div><b>Trust + distribution moat</b>Konfirmasi orang tua menjaga akuntabilitas; tutor kemudian menjadi kanal distribusi dan pemakai workflow.</div></li>
</ol>
<div class="riset-callout"><strong>Yang bukan moat</strong><p>Chatbot AI, gamifikasi, dashboard, video, dan bank soal adalah komponen pendukung. Gamifikasi sebaiknya memberi penghargaan pada menjelaskan cara, memperbaiki kesalahan, dan kembali untuk evaluasi—bukan volume atau kecepatan.</p></div>
</section>

<section class="riset-bagian" id="gtm" aria-labelledby="judul-gtm">
<div class="riset-kepala"><p class="riset-alis">05 · Product-led vs sales-led</p><h2 id="judul-gtm">PLG-assisted: produk membuktikan, manusia melancarkan</h2>
<p>Nilai kontrak keluarga tidak cocok dengan penjualan high-touch. Namun workflow awal Jagomat meminta keterlibatan orang tua, sehingga PLG murni berisiko menghasilkan abandono.</p></div>
<div class="riset-duel">
<article class="riset-kartu"><span class="riset-label riset-label-koral">Bukan pilihan utama</span><h3>Sales-led keluarga</h3><ul><li>CAC dan support berisiko terlalu tinggi.</li><li>Nilai perlu dialami sebelum dipercaya.</li><li>Diskon mudah menggantikan diferensiasi.</li></ul></article>
<article class="riset-kartu"><span class="riset-label riset-label-teal">Rekomendasi</span><h3>PLG-assisted</h3><ul><li>Self-service sebagai mesin utama.</li><li>Onboarding clinic selektif untuk friksi awal.</li><li>Referral setelah milestone kemajuan.</li><li>Tutor sebagai kanal B2B2C setelah core loop terbukti.</li></ul></article>
</div>
<div class="riset-grid riset-grid-3" style="margin-top:{T.SP_5}">
<article class="riset-kartu"><span class="riset-label">Acquire</span><h3>Tangkap problem intent</h3><p>Konten menjawab pertanyaan nyata seperti “anak paham konsep tetapi sering salah hitung”, bukan artikel matematika generik.</p></article>
<article class="riset-kartu"><span class="riset-label">Activate</span><h3>First value ≤48 jam</h3><p>Latihan awal selesai, hasil ditinjau dan dikonfirmasi, lalu satu langkah berikutnya tampil. Signup bukan aktivasi.</p></article>
<article class="riset-kartu"><span class="riset-label">Retain</span><h3>Selesaikan siklus berbukti</h3><p>North-star: jumlah anak yang menyelesaikan satu siklus belajar berbukti dalam 28 hari, disertai counter-metric friksi dan koreksi.</p></article>
<article class="riset-kartu"><span class="riset-label">Monetize</span><h3>Bayar untuk kontinuitas</h3><p>Value metric per anak aktif atau keluarga—bukan per soal, menit AI, atau video. Harga final perlu willingness-to-pay setelah nilai dialami.</p></article>
<article class="riset-kartu"><span class="riset-label">Expand</span><h3>Tutor sebagai multiplier</h3><p>Partner layak diperbesar bila mengaktifkan anak lebih murah, memakai produk standar, dan meningkatkan retensi atau outcome.</p></article>
<article class="riset-kartu"><span class="riset-label">Defer</span><h3>Enterprise sekolah</h3><p>Hindari tender besar, kustomisasi kurikulum, dan integrasi khusus sebelum outcome serta unit economics keluarga terbukti.</p></article>
</div>
</section>

<section class="riset-bagian" id="risiko" aria-labelledby="judul-risiko">
<div class="riset-kepala"><p class="riset-alis">06 · Tiga risiko strategis</p><h2 id="judul-risiko">Risiko terbesar bukan kompetitor—melainkan tesis yang tidak terbukti</h2>
<p>Setiap risiko memiliki indikator dini dan mitigasi operasional agar strategi dapat dihentikan atau dikoreksi sebelum modal pertumbuhan dibakar.</p></div>
<div class="riset-risiko">
<article><span class="riset-risiko-nomor">01</span><h3>Outcome tidak terbukti</h3><dl><dt>Mekanisme</dt><dd>Personalisasi terlihat pintar, tetapi anak tidak membaik pada soal baru.</dd><dt>Indikator dini</dt><dd>Diagnosis sering dikoreksi; delayed probe gagal; rekomendasi berulang.</dd><dt>Mitigasi</dt><dd>Human confirmation, ketidakpastian eksplisit, audit ahli, dan evaluasi dengan variasi baru.</dd></dl></article>
<article><span class="riset-risiko-nomor">02</span><h3>Keterlibatan menjadi friksi</h3><dl><dt>Mekanisme</dt><dd>Latihan dan review orang tua terlalu berat untuk diselesaikan rutin.</dd><dt>Indikator dini</dt><dd>Profil tanpa latihan, abandono tinggi, first value lewat 48 jam.</dd><dt>Mitigasi</dt><dd>Pause/resume, progress jelas, minimum sufficient parent involvement, dan bantuan selektif.</dd></dl></article>
<article><span class="riset-risiko-nomor">03</span><h3>CAC tinggi, fitur ditiru</h3><dl><dt>Mekanisme</dt><dd>Paid acquisition mahal sementara dashboard atau chatbot cepat disalin.</dd><dt>Indikator dini</dt><dd>Referral rendah, diskon dominan, support tinggi, retensi lemah.</dd><dt>Mitigasi</dt><dd>Problem-intent SEO, action–outcome graph, laporan referral aman, dan kanal tutor.</dd></dl></article>
</div>
<div class="riset-callout"><strong>Red line: privasi anak</strong><p>Privasi adalah license to operate. Pertumbuhan tidak boleh mendorong pelacak iklan pada ruang belajar, pengiriman data yang tidak perlu, diagnosis otomatis oleh LLM, atau pemakaian outcome tanpa persetujuan dan batas retensi.</p></div>
</section>

<section class="riset-bagian" id="roadmap" aria-labelledby="judul-roadmap">
<div class="riset-kepala"><p class="riset-alis">07 · Prioritas 12 bulan</p><h2 id="judul-roadmap">Scale distribution, bukan scope</h2><p>Pertahankan fokus kelas 3–6 dan matematika sampai outcome, kebiasaan, willingness-to-pay, dan unit economics cukup kuat.</p></div>
<div class="riset-roadmap">
<article><time>0–3 bulan</time><div><h3>Buktikan core loop</h3><ul><li>Ukur funnel latihan → tinjau → langkah berikutnya.</li><li>Validasi agreement sistem–orang tua/tutor.</li><li>Uji hasil pada soal baru dan evaluasi berjeda.</li><li>Bandingkan onboarding assisted versus self-service.</li></ul></div></article>
<article><time>3–6 bulan</time><div><h3>Buktikan habit dan monetisasi</h3><ul><li>Uji paket berbayar pada pengguna baru.</li><li>Aktifkan referral setelah milestone kemajuan.</li><li>Pilot terbatas bersama tutor independen.</li><li>Audit intervensi dengan ahli eksternal.</li></ul></div></article>
<article><time>6–12 bulan</time><div><h3>Perbesar kanal yang efisien</h3><ul><li>Bangun SEO berbasis problem intent.</li><li>Standardisasi paket partner tutor.</li><li>Publikasikan outcome dengan metodologi transparan.</li><li>Jangan menambah mata pelajaran hanya demi TAM.</li></ul></div></article>
</div>
</section>

<section class="riset-bagian" id="metodologi" aria-labelledby="judul-metodologi">
<div class="riset-kepala"><p class="riset-alis">08 · Metodologi dan batasan</p><h2 id="judul-metodologi">Bukti publik dipisahkan dari inferensi</h2><p>Laporan ini adalah analisis independen untuk Jagomat dan tidak berafiliasi dengan Ruangguru, Zenius, Ganesha Operation, atau Kumon.</p></div>
<div class="riset-grid riset-grid-2">
<article class="riset-kartu"><h3>Yang diperiksa</h3><ul><li>Situs dan halaman produk/harga resmi.</li><li>Pengumuman peluncuran kembali aplikasi Zenius.</li><li>Kontrak produk publik Jagomat.</li><li>Snapshot akses 13 Oktober 2026.</li></ul></article>
<article class="riset-kartu"><h3>Yang tidak diklaim</h3><ul><li>Market share, traffic, revenue, dan profitabilitas tidak diestimasi.</li><li>Tidak ada audit produk berbayar atau operasi internal kompetitor.</li><li>“Tidak terlihat” tidak berarti “tidak ada”.</li><li>Peta posisi bersifat directional, bukan skor kualitas.</li></ul></article>
</div>
<details class="riset-detail" style="margin-top:{T.SP_5}"><summary>Cara membaca confidence</summary><div class="riset-detail-isi"><p><b>Tinggi</b>: didukung sumber primer yang eksplisit. <b>Sedang</b>: inferensi model bisnis yang konsisten dengan observasi publik. <b>Rendah</b>: bukti publik terbatas dan perlu wawancara atau trial sebelum dipakai untuk keputusan besar.</p></div></details>
<details class="riset-detail"><summary>Stress-test keputusan</summary><div class="riset-detail-isi"><p>Evaluasi semantik terstruktur tambahan memilih verified learning loop sebagai moat dan PLG-assisted sebagai motion awal. Sinyal ini probabilistik, bukan bukti pasar; outcome dan engagement tetap harus dibuktikan lewat data pengguna.</p></div></details>
</section>

<section class="riset-bagian" id="sumber" aria-labelledby="judul-sumber">
<div class="riset-kepala"><p class="riset-alis">09 · Referensi</p><h2 id="judul-sumber">Sumber utama</h2><p>Tautan berikut merupakan snapshot sumber primer yang tersedia saat riset.</p></div>
<ol class="riset-sumber">
<li><a href="https://jagomat.id/">Jagomat</a> — positioning, alur awal, privasi, dan status akses awal.</li>
<li><a href="https://www.ruangguru.com/">Ruangguru</a> — portofolio produk, Brain Academy, privat, AI, dan cabang.</li>
<li><a href="https://www.ruangguru.com/blog/informasi-produk-ruangguru-yang-jadi-unggulan">Produk dan paket Ruangguru</a> — fitur dan struktur paket; sebagian harga berlabel TA 2025/2026.</li>
<li><a href="https://www.zenius.net/about-us">About Zenius</a> — positioning dan model belajar.</li>
<li><a href="https://www.zenius.net/blog/aplikasi-belajar-online-zenius/">Peluncuran kembali aplikasi Zenius</a> — 7 Juli 2026.</li>
<li><a href="https://www.zenius.net/payment/package">Paket belajar Zenius</a> — cakupan dan harga saat snapshot.</li>
<li><a href="https://zenius.com/about-us/">Zenius Aktibet Group</a> — struktur grup publik.</li>
<li><a href="https://id.kumonglobal.com/metode-kumon/?lang=id">Metode Kumon</a> — personalisasi dan peran pembimbing.</li>
<li><a href="https://id.kumonglobal.com/kumon-connect/?lang=id">KUMON CONNECT</a> — worksheet dan progres digital.</li>
<li><a href="https://id.kumonglobal.com/biaya-kursus/?lang=id">Biaya resmi Kumon 2026</a>.</li>
<li><a href="https://www.ganesha-operation.com/">Ganesha Operation</a> — proposisi publik, TOBK, GO Kreasi, dan IRT.</li>
</ol>
<p class="riset-catatan" style="margin-top:{T.SP_5}">Nama dan merek kompetitor adalah milik masing-masing pemegang hak. Laporan ini menggunakan penyebutan nominatif untuk analisis persaingan dan tidak menyatakan dukungan atau kemitraan.</p>
</section>
</div></main>
<footer class="riset-footer"><div class="riset-bungkus riset-footer-dalam"><p>Jagomat · Jago karena tahu caranya.</p><p><a href="/">Kembali ke Jagomat</a> · <a href="{JALUR_PDF}">Unduh PDF</a></p></div></footer>
</body></html>""".encode("utf-8")


def kirim_pdf(penangan) -> None:
    """Kirim PDF statis publik dengan MIME dan nama unduhan yang ketat."""
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
