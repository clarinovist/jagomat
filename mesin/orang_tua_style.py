"""CSS halaman orang tua di akun murid dan tautan sekundernya di beranda murid. Nilai hanya dari token desain."""
from __future__ import annotations

import design_tokens as T

RUTE = "/murid/orang-tua"
TEKS_TAUTAN_BERANDA = "Untuk Ayah/Bunda"
TAUTAN_BERANDA = (
    f'<p class="ortu-tautan-baris-st"><a class="ortu-tautan-st" href="{RUTE}">{TEKS_TAUTAN_BERANDA}</a></p>'
)

GAYA_TAUTAN_BERANDA = f"""
.ortu-tautan-baris-st {{ margin: {T.SP_4} 0 0; text-align: center; }}
.ortu-tautan-st {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3};
  border-radius: {T.RADIUS_SEDANG}; color: {T.AKSEN_TEAL_TUA}; font: 700 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE};
  text-decoration: underline; }}
.ortu-tautan-st:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
"""

GAYA_ORTU = f"""
.ortu-kepala-st {{ display: grid; gap: {T.SP_2}; }}
.ortu-kepala-st h1 {{ margin: 0; font: 800 {T.UKURAN_BAGIAN_STITCH}/1.2 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.ortu-kepala-st p {{ margin: 0; font-size: {T.UKURAN_TEKS_BANTUAN}; line-height: 1.5; color: {T.TEKS_VARIAN}; }}
.ortu-kartu-st {{ display: grid; gap: {T.SP_3}; padding: {T.SP_4}; background: {T.LATAR_KARTU};
  border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU}; }}
.ortu-kartu-st > :is(h2, h3, p, form) {{ margin: 0; }}
.ortu-kartu-st h2 {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.2 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.ortu-kartu-st h3 {{ font: 700 {T.UKURAN_BADAN_LAYAR}/1.3 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.ortu-kartu-st form {{ display: grid; gap: {T.SP_3}; }}
.ortu-kabar-st, .ortu-galat-st {{ margin: 0; padding: {T.SP_3} {T.SP_4}; border-radius: {T.RADIUS_KARTU};
  font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.ortu-kabar-st {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_TERSIMPAN}; }}
.ortu-galat-st {{ background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; border: {T.TEBAL_GARIS} solid {T.BORDER_GALAT}; }}
.ortu-tombol-st {{ min-height: {T.TINGGI_CTA}; padding: 0 {T.SP_4}; border: 0; border-radius: {T.RADIUS_SEDANG};
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font: 700 {T.UKURAN_BADAN_LAYAR}/1.2 {T.FONT_HEADLINE}; cursor: pointer; }}
a.ortu-tombol-st {{ display: inline-flex; align-items: center; justify-content: center; text-decoration: none; }}
.ortu-tombol-st:hover {{ background: {T.AKSEN_TEAL_HOVER}; }}
.ortu-tombol-st:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.ortu-konfirmasi-st {{ display: flex; align-items: flex-start; gap: {T.SP_3}; font-size: {T.UKURAN_TEKS_BANTUAN};
  line-height: 1.5; color: {T.TEKS_VARIAN}; }}
.ortu-konfirmasi-st input {{ width: 1.5rem; height: 1.5rem; flex: none; accent-color: {T.AKSEN_TEAL_TUA}; }}
"""
