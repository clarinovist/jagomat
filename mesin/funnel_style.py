"""CSS halaman publik funnel Cek Kemampuan (`/cek-kemampuan`, `/paket-coba`).

Hanya kelas yang dipakai `funnel_pages`; namespace `funnel-...-st`. Semua nilai
dari `design_tokens` (tanpa warna literal). Kerangka, kartu, topbar, dan tombol
coral memakai kelas landing yang sudah ada di `style_stitch`.
"""

import design_tokens as T

GAYA_FUNNEL = f"""
/* Funnel Cek Kemampuan: harga, pil, kartu batas, tautan. */
.funnel-harga-st {{ display: flex; align-items: baseline; gap: {T.SP_2}; flex-wrap: wrap; margin: {T.SP_1} 0 {T.SP_2}; }}
.funnel-harga-angka-st {{ font-family: {T.FONT_HEADLINE}; font-size: 2.6rem; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; color: {T.TEKS_JUDUL}; }}
.funnel-harga-satuan-st {{ font-size: 1rem; color: {T.TEKS_VARIAN}; }}
.funnel-pil-baris-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin: 0 0 {T.SP_3}; }}
.funnel-pil-st {{ display: inline-block; padding: {T.SP_1} {T.SP_3}; border-radius: {T.RADIUS_PIL}; font-size: .85rem; font-weight: 600; background: {T.LATAR_CATATAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; color: {T.TEKS_JUDUL}; }}
.funnel-pil-jujur-st {{ background: {T.LATAR_KARTU_SEKUNDER}; border-color: {T.BORDER_INTERAKTIF}; }}
.funnel-dua-kolom-st {{ display: grid; gap: {T.SP_5}; grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr); align-items: start; }}
.funnel-dua-kolom-st > .landing-kartu-st {{ height: 100%; }}
.funnel-kartu-batas-st {{ background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN}; }}
.funnel-catatan-st {{ font-size: .9rem; color: {T.TEKS_VARIAN}; margin: {T.SP_3} 0 0; }}
.funnel-tautan-st {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; color: {T.TEKS_JUDUL}; font-weight: 600; text-decoration: underline; text-underline-offset: 3px; }}
.funnel-tautan-baris-st {{ display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_2} {T.SP_5}; margin: {T.SP_3} 0 0; }}
.funnel-aksi-st {{ margin: {T.SP_6} 0 0; color: {T.TEKS_VARIAN}; }}
.funnel-skor-st {{ display: flex; align-items: baseline; gap: {T.SP_2}; flex-wrap: wrap; margin: {T.SP_1} 0 {T.SP_2}; }}
.funnel-skor-angka-st {{ font-family: {T.FONT_HEADLINE}; font-size: 2.6rem; font-weight: 800; letter-spacing: -.02em; line-height: 1.1; color: {T.TEKS_JUDUL}; }}
.funnel-skor-satuan-st {{ font-size: 1rem; color: {T.TEKS_VARIAN}; }}
.funnel-kunci-st {{ margin: {T.SP_4} 0; padding: {T.SP_4}; border: {T.TEBAL_GARIS} dashed {T.BORDER_KONTROL}; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_VARIAN}; }}
.funnel-halaman-st :is(p, li, a, h1, h2, h3) {{ overflow-wrap: anywhere; }}
@media (max-width: 820px) {{
  .funnel-dua-kolom-st {{ grid-template-columns: minmax(0, 1fr); }}
}}
@media (max-width: 560px) {{
  .funnel-harga-angka-st, .funnel-skor-angka-st {{ font-size: 2.25rem; }}
  .funnel-halaman-st .landing-cta-baris-st a.tombol-coral {{ width: 100%; justify-content: center; }}
}}
"""
