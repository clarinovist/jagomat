"""CSS halaman publik funnel Cek Kemampuan (`/cek-kemampuan`, `/paket-coba`).

Hanya kelas yang dipakai `funnel_pages`; namespace `funnel-...-st`. Semua nilai
dari `design_tokens` (tanpa warna literal). Kerangka, kartu, topbar, dan tombol
coral memakai kelas landing yang sudah ada di `style_stitch`.
"""

import design_tokens as T

GAYA_FUNNEL = f"""
/* Funnel Cek Kemampuan: harga, pil, kartu batas, tautan. */
.funnel-harga-st {{ display: flex; align-items: baseline; gap: {T.SP_2}; flex-wrap: wrap; margin: {T.SP_1} 0 {T.SP_2}; }}
.funnel-harga-angka-st {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_ANGKA_FUNNEL}; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; color: {T.TEKS_JUDUL}; }}
.funnel-harga-satuan-st {{ font-size: 1rem; color: {T.TEKS_VARIAN}; }}
.funnel-pil-baris-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin: 0 0 {T.SP_3}; }}
.funnel-pil-st {{ display: inline-block; padding: {T.SP_1} {T.SP_3}; border-radius: {T.RADIUS_PIL}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; background: {T.LATAR_CATATAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; color: {T.TEKS_JUDUL}; }}
.funnel-pil-jujur-st {{ background: {T.LATAR_KARTU_SEKUNDER}; border-color: {T.BORDER_INTERAKTIF}; }}
.funnel-dua-kolom-st {{ display: grid; gap: {T.SP_5}; grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr); align-items: start; }}
.funnel-dua-kolom-st > .landing-kartu-st {{ height: 100%; }}
.funnel-kartu-batas-st {{ background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN}; }}
.funnel-catatan-st {{ font-size: .9rem; color: {T.TEKS_VARIAN}; margin: {T.SP_3} 0 0; }}
.funnel-tautan-st {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; color: {T.TEKS_JUDUL}; font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }}
.funnel-tautan-baris-st {{ display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_2} {T.SP_5}; margin: {T.SP_3} 0 0; }}
.funnel-aksi-st {{ margin: {T.SP_6} 0 0; color: {T.TEKS_VARIAN}; }}
.funnel-skor-st {{ display: flex; align-items: baseline; gap: {T.SP_2}; flex-wrap: wrap; margin: {T.SP_1} 0 {T.SP_2}; }}
.funnel-skor-angka-st {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_ANGKA_FUNNEL}; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; color: {T.TEKS_JUDUL}; }}
.funnel-skor-satuan-st {{ font-size: 1rem; color: {T.TEKS_VARIAN}; }}
.funnel-kunci-st {{ margin: {T.SP_4} 0; padding: {T.SP_4}; border: {T.TEBAL_GARIS} dashed {T.BORDER_KONTROL}; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_VARIAN}; }}
.funnel-halaman-st :is(p, li, a, h1, h2, h3) {{ overflow-wrap: anywhere; }}
@media (max-width: 820px) {{
  .funnel-dua-kolom-st {{ grid-template-columns: minmax(0, 1fr); }}
}}
@media (max-width: 560px) {{
  .funnel-harga-angka-st, .funnel-skor-angka-st {{ font-size: {T.UKURAN_ANGKA_FUNNEL_HP}; }}
  .funnel-halaman-st .landing-cta-baris-st a.tombol-coral {{ width: 100%; justify-content: center; }}
}}
/* Desain baru funnel (hero, kartu contoh, langkah, blok Peta Kemampuan, akordeon, FAQ). */
.funnel-halaman-st {{ font-family: {T.FONT_BODY}; color: {T.TEKS_VARIAN}; }}
.funnel-halaman-st :is(h1, h2, h3) {{ font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; margin: 0; text-wrap: balance; }}
:where(.funnel-halaman-st) p {{ margin: 0; }}
.funnel-bagian-st {{ padding: {T.SP_6} 0; }}
.funnel-hero-st {{ display: grid; grid-template-columns: 1.05fr .95fr; gap: {T.SP_6}; align-items: center; padding: {T.SP_7} 0 {T.SP_6}; }}
.funnel-tanya-st {{ font: 700 1.06rem/1.3 {T.FONT_HEADLINE}; color: {T.AKSEN_KORAL_TUA}; }}
.funnel-halaman-st h1.funnel-judul-hero-st {{ font-size: 3.25rem; line-height: 1.04; letter-spacing: -.025em; font-weight: 800; margin-top: {T.SP_3}; }}
.funnel-judul-hero-st em {{ font-style: normal; color: {T.AKSEN_TEAL_TUA}; text-decoration: underline; text-decoration-color: {T.AKSEN_MURID_AMBER}; text-decoration-thickness: .07em; text-underline-offset: .12em; }}
.funnel-sub-st {{ font-size: 1.19rem; color: {T.TEKS_JUDUL}; font-weight: 500; margin: {T.SP_4} 0 {T.SP_5}; max-width: 30ch; }}
.funnel-kecil-st {{ margin-top: {T.SP_3}; font-size: .88rem; }}
.funnel-fakta-st {{ margin-top: {T.SP_4}; font-size: .88rem; font-weight: 600; color: {T.TEKS_JUDUL}; }}
.funnel-halaman-st .landing-cta-baris-st {{ margin: 0; }}
.funnel-panggung-st {{ position: relative; display: flex; justify-content: center; }}
.funnel-lengkung-st {{ position: absolute; inset: 10% 4% 0 8%; background: {T.ANAK_AKSEN_LATAR}; border-radius: 220px 220px {T.RADIUS_KARTU_BESAR} {T.RADIUS_KARTU_BESAR}; }}
.funnel-contoh-st {{ position: relative; width: min(100%, 380px); }}
.funnel-kartu-contoh-st {{ position: relative; background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_5}; box-shadow: {T.BAYANGAN_MENU}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; }}
.funnel-kepala-st {{ display: flex; justify-content: space-between; align-items: center; font-size: .81rem; font-weight: 600; }}
.funnel-lencana-st {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_PIL}; padding: {T.SP_1} {T.SP_3}; font-size: .75rem; font-weight: 700; }}
.funnel-anak-st {{ font: 700 .94rem/1.2 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; margin: {T.SP_3} 0 {T.SP_3}; }}
.funnel-skor-baris-st {{ display: flex; align-items: center; gap: {T.SP_4}; }}
.funnel-cincin-st {{ --p: 72; width: 6rem; height: 6rem; border-radius: {T.RADIUS_BULAT}; flex: none; display: grid; place-items: center; background: conic-gradient({T.AKSEN_MURID_UTAMA} calc(var(--p) * 1%), {T.LATAR_ELEVASI} 0); }}
.funnel-cincin-dalam-st {{ width: 4.6rem; height: 4.6rem; border-radius: {T.RADIUS_BULAT}; background: {T.LATAR_KARTU}; display: grid; place-items: center; text-align: center; font: 800 1.75rem/1 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.funnel-cincin-dalam-st small {{ display: block; font: 500 .69rem/1 {T.FONT_BODY}; margin-top: 3px; }}
.funnel-kategori-st {{ font: 800 1.25rem/1.1 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.funnel-kategori-st small {{ display: block; font: 500 .81rem/1.3 {T.FONT_BODY}; color: {T.TEKS_VARIAN}; margin-top: {T.SP_1}; }}
.funnel-chip-baris-st {{ display: grid; gap: {T.SP_2}; margin-top: {T.SP_4}; }}
.funnel-chip-st {{ display: flex; align-items: center; gap: {T.SP_3}; padding: {T.SP_3}; border-radius: {T.RADIUS_KARTU}; font-weight: 600; font-size: .88rem; line-height: 1.3; }}
.funnel-chip-st svg {{ flex: none; }}
.funnel-chip-kuat-st {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.funnel-chip-lemah-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.funnel-chip-kunci-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_VARIAN}; border: {T.TEBAL_GARIS} dashed {T.BORDER_VARIAN}; font-weight: 500; }}
.funnel-otomatis-st {{ margin-top: {T.SP_3}; font-size: .78rem; }}
.funnel-ket-contoh-st {{ position: relative; font-size: .78rem; margin-top: {T.SP_3}; padding: 0 5.5rem 0 {T.SP_1}; min-height: 2.5rem; }}
.funnel-maskot-st {{ position: absolute; width: 5.25rem; height: 5.25rem; object-fit: contain; right: -{T.SP_1}; bottom: -{T.SP_2}; z-index: 2; pointer-events: none; }}
.funnel-alis-st {{ font: 700 .81rem/1 {T.FONT_HEADLINE}; letter-spacing: .08em; text-transform: uppercase; color: {T.AKSEN_TEAL_TUA}; }}
.funnel-halaman-st h2.funnel-judul-bagian-st {{ font-size: 2rem; line-height: 1.12; letter-spacing: -.02em; font-weight: 800; margin-top: {T.SP_3}; }}
.funnel-langkah-st {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: {T.SP_4}; margin-top: {T.SP_5}; }}
.funnel-langkah-st article {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: 18px; padding: {T.SP_5}; }}
.funnel-ikon-st {{ width: 3.25rem; height: 3.25rem; border-radius: 14px; display: grid; place-items: center; background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.funnel-langkah-st article:nth-child(2) .funnel-ikon-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.funnel-langkah-st article:nth-child(3) .funnel-ikon-st {{ background: {T.LATAR_GALAT}; color: {T.AKSEN_KORAL_TUA}; }}
.funnel-halaman-st .funnel-langkah-st h3 {{ font-size: 1.19rem; margin: {T.SP_4} 0 {T.SP_2}; font-weight: 800; }}
.funnel-langkah-st p {{ font-size: .94rem; }}
.funnel-paket-st {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.75rem; align-items: center; background: {T.TEKS_JUDUL}; color: {T.LATAR_KARTU_SEKUNDER}; border-radius: 24px; padding: 2.25rem; }}
.funnel-paket-st .funnel-alis-st {{ color: {T.AKSEN_MURID_AMBER}; }}
.funnel-halaman-st .funnel-paket-st h2 {{ color: {T.TEKS_PUTIH}; font-size: 1.9rem; font-weight: 800; letter-spacing: -.02em; margin-top: {T.SP_3}; }}
.funnel-paket-sub-st {{ margin-top: {T.SP_2}; max-width: 34ch; font-size: 1.06rem; }}
.funnel-harga-baris-st {{ display: flex; align-items: baseline; gap: {T.SP_3}; flex-wrap: wrap; margin: {T.SP_3} 0 {T.SP_1}; }}
.funnel-harga-baris-st strong {{ font: 800 2.75rem/1 {T.FONT_HEADLINE}; color: {T.TEKS_PUTIH}; letter-spacing: -.02em; }}
.funnel-harga-baris-st span {{ font-size: .94rem; }}
.funnel-paket-st .funnel-bukan-st {{ color: {T.BORDER_INTERAKTIF}; font-size: .9rem; margin: 2px 0 {T.SP_2}; }}
.funnel-pil-terang-st {{ display: inline-block; font-size: .78rem; font-weight: 700; padding: 5px {T.SP_3}; border-radius: {T.RADIUS_PIL}; border: {T.TEBAL_GARIS} solid {T.BORDER_INTERAKTIF}; color: {T.TEKS_PUTIH}; margin: {T.SP_1} {T.SP_2} 0 0; }}
.funnel-pil-kuota-st {{ background: {T.AKSEN_MURID_AMBER}; border-color: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; }}
.funnel-centang-st {{ list-style: none; padding: 0; margin: 0; display: grid; gap: {T.SP_3}; }}
.funnel-centang-st li {{ display: flex; gap: {T.SP_3}; align-items: flex-start; font-size: .97rem; line-height: 1.4; }}
.funnel-centang-st svg {{ flex: none; margin-top: 2px; }}
.funnel-paket-st .funnel-centang-st svg {{ color: {T.AKSEN_MURID_AMBER}; }}
.funnel-harga-kartu-st .funnel-centang-st svg {{ color: {T.AKSEN_TEAL_TUA}; }}
.funnel-tautan-terang-st {{ color: {T.TEKS_PUTIH}; font-weight: 600; text-underline-offset: 4px; display: inline-flex; min-height: {T.TARGET_SENTUH}; align-items: center; margin-top: {T.SP_3}; }}
.funnel-akordeon-st {{ margin-top: {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; background: {T.LATAR_CATATAN}; border-radius: 14px; padding: {T.SP_1} {T.SP_4}; }}
.funnel-halaman-st summary {{ cursor: pointer; font: 700 .94rem/1.3 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; padding: {T.SP_3} 0; min-height: {T.TARGET_SENTUH}; list-style: none; display: flex; justify-content: space-between; align-items: center; gap: {T.SP_3}; }}
.funnel-halaman-st summary::-webkit-details-marker {{ display: none; }}
.funnel-halaman-st summary::after {{ content: "+"; font-size: 1.4rem; font-weight: 600; color: {T.AKSEN_TEAL_TUA}; line-height: 1; }}
.funnel-halaman-st details[open] > summary::after {{ content: "\\2013"; }}
.funnel-akordeon-st ul {{ margin: 0 0 {T.SP_3}; padding-left: {T.SP_5}; font-size: .91rem; display: grid; gap: {T.SP_2}; }}
.funnel-judul-halaman-st {{ font-size: 2.75rem; line-height: 1.06; letter-spacing: -.025em; font-weight: 800; margin-top: {T.SP_3}; }}
.funnel-pengantar-st {{ margin-top: {T.SP_3}; font-size: 1.13rem; color: {T.TEKS_JUDUL}; max-width: 46ch; }}
.funnel-harga-kartu-st {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: 1.75rem; }}
.funnel-harga-kartu-st .funnel-harga-baris-st strong {{ color: {T.TEKS_JUDUL}; font-size: 3.5rem; }}
.funnel-harga-kartu-st .funnel-centang-st {{ margin: {T.SP_5} 0; }}
.funnel-pil-hijau-st {{ display: inline-block; font-size: .78rem; font-weight: 700; padding: 5px {T.SP_3}; border-radius: {T.RADIUS_PIL}; background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; margin: {T.SP_1} {T.SP_1} 0 0; }}
.funnel-pil-kuning-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.funnel-tegas-st {{ margin: {T.SP_3} 0; padding: {T.SP_3} {T.SP_4}; border-left: 4px solid {T.AKSEN_KORAL_TUA}; background: {T.LATAR_CATATAN}; border-radius: {T.RADIUS_SEDANG}; font-weight: 600; color: {T.TEKS_JUDUL}; }}
.funnel-dua-st {{ display: grid; grid-template-columns: 1.1fr .9fr; gap: {T.SP_5}; align-items: stretch; margin-top: 1.75rem; }}
.funnel-batas-kartu-st {{ background: {T.LATAR_CATATAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: 1.75rem; display: flex; flex-direction: column; gap: {T.SP_3}; }}
.funnel-halaman-st .funnel-batas-kartu-st h2 {{ font-size: 1.25rem; font-weight: 800; }}
.funnel-batas-kartu-st ul {{ list-style: none; padding: 0; margin: 0; display: grid; gap: {T.SP_3}; }}
.funnel-batas-kartu-st li {{ display: flex; gap: {T.SP_3}; font-size: .94rem; line-height: 1.4; }}
.funnel-batas-kartu-st li svg {{ flex: none; margin-top: 2px; color: {T.AKSEN_AMBER_TUA}; }}
.funnel-catatan-kelas-st {{ font-size: .88rem; }}
.funnel-aksi-st {{ display: grid; gap: {T.SP_2}; justify-items: start; }}
.funnel-aksi-st p {{ font-size: .91rem; }}
.funnel-faq-st {{ margin-top: {T.SP_5}; display: grid; gap: {T.SP_3}; }}
.funnel-faq-st details {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_1} {T.SP_5}; }}
.funnel-jawab-st {{ padding: 0 0 {T.SP_4}; font-size: .94rem; }}
.funnel-jawab-st ul {{ padding-left: {T.SP_5}; margin: 0; display: grid; gap: {T.SP_2}; }}
@media (max-width: 820px) {{
  .funnel-hero-st {{ grid-template-columns: minmax(0, 1fr); padding: {T.SP_6} 0 {T.SP_5}; }}
  .funnel-halaman-st h1.funnel-judul-hero-st {{ font-size: 2.6rem; }}
  .funnel-langkah-st, .funnel-dua-st {{ grid-template-columns: minmax(0, 1fr); }}
  .funnel-paket-st {{ grid-template-columns: minmax(0, 1fr); padding: 1.75rem; }}
  .funnel-judul-halaman-st {{ font-size: 2.25rem; }}
}}
@media (max-width: 560px) {{
  .funnel-halaman-st h1.funnel-judul-hero-st {{ font-size: 2.1rem; }}
  .funnel-sub-st {{ font-size: 1.06rem; }}
  .funnel-halaman-st .funnel-hero-st .landing-cta-baris-st a.tombol-coral, .funnel-aksi-st .landing-cta-baris-st a.tombol-coral {{ width: 100%; justify-content: center; }}
  .funnel-halaman-st h2.funnel-judul-bagian-st {{ font-size: 1.62rem; }}
  .funnel-paket-st {{ padding: 1.4rem; border-radius: 20px; }}
  .funnel-halaman-st .funnel-paket-st h2 {{ font-size: 1.5rem; }}
  .funnel-harga-baris-st strong {{ font-size: 2.4rem; }}
  .funnel-harga-kartu-st, .funnel-batas-kartu-st {{ padding: 1.4rem; }}
  .funnel-harga-kartu-st .funnel-harga-baris-st strong {{ font-size: 2.75rem; }}
  .funnel-judul-halaman-st {{ font-size: 1.88rem; }}
  .funnel-maskot-st {{ width: 4.25rem; height: 4.25rem; right: 0; }}
  .funnel-ket-contoh-st {{ padding-right: 4.75rem; }}
  .funnel-kartu-contoh-st {{ padding: {T.SP_4}; }}
  .funnel-bagian-st {{ padding: 2rem 0; }}
}}
"""
