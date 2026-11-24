"""CSS halaman langganan Latihan Harian (`GAYA_LANGGANAN_HARIAN`): kartu paket, kartu tagihan berpola kertas, langkah mini.

Namespace `lg-`. Dipakai bersama `playful_style.GAYA_CERIA` lewat `pesanan_murid_pages.halaman_murid(css_tambahan=...)`.
Semua nilai dari `design_tokens` (tanpa warna literal). Tulisan tangan memakai `FONT_HEADLINE` miring (tanpa berkas font baru).
Status langkah tidak hanya warna: langkah sekarang bertanda `aria-current` dan teks tersembunyi.
"""
from __future__ import annotations

import design_tokens as T

_UKURAN_KISI = "16px"
_MIRING_TULISAN = "-1.5deg"

GAYA_LANGGANAN_HARIAN = f"""
.lg-isi {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}
.lg-isi > h1 {{ margin: 0; font: 800 {T.UKURAN_JUDUL_STITCH}/1.2 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.lg-isi > section {{ margin: 0; }}
.lg-isi :focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 3px; }}
.lg-kartu {{ display: flex; flex-direction: column; gap: {T.SP_3}; padding: {T.SP_4}; background: {T.LATAR_KARTU};
  border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.lg-kartu > * {{ margin: 0; }}
.lg-kartu h2 {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.25 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.lg-kartu p {{ line-height: 1.5; }}
.lg-kecil {{ font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; }}
.lg-pilih-judul {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.lg-pilih-judul > * {{ margin: 0; }}
.lg-pilih-judul h2 {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.25 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.lg-paket {{ position: relative; display: flex; flex-direction: column; gap: {T.SP_3}; padding: {T.SP_4}; background: {T.LATAR_KARTU};
  border: 2px solid {T.ANAK_BORDER_PIL}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.lg-paket > * {{ margin: 0; }}
.lg-paket-hemat {{ margin-top: {T.SP_2}; background: {T.ANAK_AKSEN_LATAR}; border-color: {T.ANAK_AKSEN}; }}
.lg-paket .ceria-stiker {{ margin-bottom: -{T.SP_1}; }}
.lg-paket-kepala {{ display: flex; justify-content: space-between; align-items: flex-start; gap: {T.SP_3}; }}
.lg-paket-nama {{ display: flex; flex-direction: column; gap: {T.SP_1}; min-width: 0; }}
.lg-paket-nama > * {{ margin: 0; }}
.lg-paket-nama h3 {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.2 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.lg-ket {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_VARIAN}; }}
.lg-hemat {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; color: {T.TEKS_TERSIMPAN}; }}
.lg-harga {{ margin: 0; white-space: nowrap; font: 800 {T.UKURAN_BAGIAN_STITCH}/1.2 {T.FONT_HEADLINE}; font-variant-numeric: tabular-nums;
  color: {T.TEKS_JUDUL}; }}
.lg-paket form, .lg-kartu form {{ display: flex; flex-direction: column; gap: {T.SP_3}; margin: 0; }}
.lg-isi button.ceria-tombol {{ width: 100%; border: 0; cursor: pointer; font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 800; line-height: 1.3;
  padding: {T.SP_3} {T.SP_4}; background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_PIL}; box-shadow: 0 4px 0 {T.AKSEN_KORAL_TEPI}; }}
.lg-isi button.ceria-tombol:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.lg-langkah {{ display: flex; gap: {T.SP_2}; margin: 0; padding: 0; list-style: none; }}
.lg-langkah li {{ flex: 1; min-width: 0; padding: {T.SP_1} {T.SP_2}; text-align: center; border-radius: {T.RADIUS_PIL};
  background: {T.LATAR_JALUR_BAR}; color: {T.TEKS_VARIAN}; font: 700 {T.UKURAN_TEKS_META}/1.3 {T.FONT_HEADLINE}; }}
.lg-langkah li.lg-selesai {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.lg-langkah li[aria-current="step"] {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; }}
.lg-kertas {{ background-color: {T.LATAR_KARTU};
  background-image: linear-gradient({T.GARIS_KISI} 1px, transparent 1px), linear-gradient(90deg, {T.GARIS_KISI} 1px, transparent 1px);
  background-size: {_UKURAN_KISI} {_UKURAN_KISI}; }}
.lg-nominal {{ font: 800 {T.UKURAN_ANGKA_FUNNEL}/1.1 {T.FONT_HEADLINE}; letter-spacing: -.01em; font-variant-numeric: tabular-nums;
  color: {T.TEKS_JUDUL}; }}
.lg-tulis {{ font-family: {T.FONT_HEADLINE}; font-style: italic; font-weight: 700; color: {T.AKSEN_KORAL_TUA};
  transform: rotate({_MIRING_TULISAN}); transform-origin: left center; }}
.lg-pemisah {{ width: 100%; border: 0; border-top: 1px dashed {T.BORDER_VARIAN}; }}
.lg-rincian {{ display: flex; flex-direction: column; gap: {T.SP_1}; }}
.lg-rincian > p {{ margin: 0; }}
.lg-berkas {{ display: flex; flex-direction: column; gap: {T.SP_2}; margin: 0; font-weight: 600; }}
.lg-berkas input {{ max-width: 100%; font: inherit; font-weight: 400; }}
.lg-berkas input::file-selector-button {{ margin-right: {T.SP_3}; padding: {T.SP_2} {T.SP_3}; border: 0; border-radius: {T.RADIUS_SEDANG};
  background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; font: inherit; font-weight: 700; cursor: pointer; }}
.lg-kembali {{ margin: 0; text-align: center; }}
.lg-kembali a {{ color: {T.AKSEN_TEAL_TUA}; font-weight: 700; }}
.lg-isi .ceria-hero > .ceria-maskot-baris {{ margin: 0; }}
.lg-isi .ceria-hero p {{ line-height: 1.5; }}
"""
