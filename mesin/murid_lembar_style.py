"""CSS tambahan lembar kerja, hasil, dan beranda anak (audit area anak, Fase 2, 22 Nov 2026).

Dimuat lewat `GAYA_STITCH` (CSS murid ada di GAYA_STITCH, bukan CSS_SESI) dan hanya menyasar body murid
(`kerja-editorial-st`, `hasil-editorial-st`, `murid-beranda-st`), jadi halaman guru tidak berubah. Nilai visual
dari `design_tokens`; tanpa JS.
"""
from __future__ import annotations

import design_tokens as T

_KERJA = "body.st.kerja-editorial-st"
_HASIL = "body.st.hasil-editorial-st"
_MURID = "body.st:is(.kerja-editorial-st, .hasil-editorial-st)"
_TINGGI_PILIHAN = "3.25rem"
_LEBAR_HURUF = "2.25rem"
_TEBAL_TERPILIH = "1px"

GAYA_MURID_LEMBAR = f"""
/* #7 Teks soal seragam dengan soal Lomba: kalimat tanya tidak lagi tebal sendiri (kelas kerja-tanya-st). */
{_MURID} :is(.kerja-teks-st, .kerja-tanya-st, .kerja-soal-st > .teks) {{
  display: block; margin-top: {T.SP_2}; font-family: {T.FONT_BODY}; font-size: {T.UKURAN_SOAL};
  font-weight: {T.BOBOT_SOAL}; line-height: {T.LINE_HEIGHT_SOAL}; color: {T.TEKS_JUDUL};
}}

/* #5 Pilihan ganda lembar kerja = kartu huruf A-D seperti soal Lomba; input asli tetap ada (tersembunyi). */
{_KERJA} .pg-pilihan {{ display: flex; flex-direction: column; gap: {T.SP_2}; }}
{_KERJA} .pg-opsi, {_KERJA} .pg-kosong {{
  position: relative; margin: 0; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3};
  border: 2px solid {T.ANAK_BORDER_PIL}; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_KARTU};
}}
{_KERJA} .pg-opsi {{ min-height: {_TINGGI_PILIHAN}; font-weight: {T.BOBOT_SOAL}; }}
{_KERJA} .pg-opsi input {{ position: absolute; opacity: 0; pointer-events: none; }}
{_KERJA} .pg-opsi .pg-huruf {{
  flex: none; display: inline-flex; align-items: center; justify-content: center; width: {_LEBAR_HURUF};
  height: {_LEBAR_HURUF}; font-family: {T.FONT_HEADLINE}; font-weight: 800;
  background: {T.ANAK_ABU_HANGAT}; border-radius: {T.RADIUS_BULAT};
}}
{_KERJA} .pg-opsi .pg-teks {{ flex: 1; min-width: 0; }}
{_KERJA} .pg-opsi .pg-teks-sr {{
  position: absolute; width: 1px; height: 1px; margin: -1px; padding: 0; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}}
{_KERJA} .pg-opsi:hover {{ border-color: {T.ANAK_AKSEN}; }}
{_KERJA} .pg-opsi:has(input:checked) {{
  background: {T.ANAK_AKSEN_LATAR}; border-color: {T.ANAK_AKSEN}; box-shadow: inset 0 0 0 {_TEBAL_TERPILIH} {T.ANAK_AKSEN};
}}
{_KERJA} .pg-opsi:has(input:checked) .pg-huruf {{ background: {T.ANAK_AKSEN}; color: {T.TEKS_PUTIH}; }}
{_KERJA} :is(.pg-opsi, .pg-kosong):focus-within {{ outline: none; }}
{_KERJA} :is(.pg-opsi, .pg-kosong):has(input:focus-visible) {{
  outline: {T.TEBAL_FOKUS} solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px;
}}
/* "Belum menjawab" netral: bukan jawaban, jadi tanpa huruf, tanpa warna aksen. */
{_KERJA} .pg-kosong {{
  gap: {T.SP_3}; color: {T.TEKS_VARIAN}; font-size: {T.UKURAN_TEKS_LABEL};
  background: {T.LATAR_SEKUNDER_LEMBUT}; border-color: transparent;
}}
{_KERJA} .pg-kosong input {{ flex: none; width: 1.25rem; height: 1.25rem; margin: 0; accent-color: {T.TEKS_VARIAN}; }}
{_KERJA} .pg-kosong:has(input:checked) {{ border-color: {T.BORDER_KONTROL}; }}

/* #8 Tombol "Pilih berkas": hover senada tombol sekunder murid (bentuk dasar di aturan file-selector-button). */
{_KERJA} input[type=file]::file-selector-button:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; cursor: pointer; }}

/* #8b Tautan lompat hasil = chip, bukan tautan biru bergaris bawah. */
{_HASIL} .hasil-lompat-st a {{
  justify-content: center; padding: {T.SP_1} {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_PIL}; background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA};
  font: 700 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE}; text-decoration: none;
}}
{_HASIL} .hasil-lompat-st a:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
/* "Ingat rumusnya dulu": satu baris ikon + judul + panah lipat; jarak bawah hanya saat terbuka. */
{_HASIL} .rumus-blok-st {{ padding: 0 {T.SP_3}; }}
{_HASIL} .rumus-blok-st[open] {{ padding-bottom: {T.SP_3}; }}
{_HASIL} .rumus-kepala-st {{
  margin-bottom: 0; min-height: {T.TARGET_SENTUH}; font-size: {T.UKURAN_TEKS_LABEL}; list-style: none;
}}
{_HASIL} .rumus-blok-st[open] > .rumus-kepala-st {{ margin-bottom: {T.SP_2}; }}
{_HASIL} .rumus-kepala-st::-webkit-details-marker {{ display: none; }}
{_HASIL} .rumus-kepala-st .murid-ikon-st:last-child {{ margin-left: auto; width: 1rem; height: 1rem; }}
{_HASIL} .rumus-blok-st[open] > .rumus-kepala-st .murid-ikon-st:last-child {{ transform: rotate(90deg); }}

/* #11 Status netral di beranda ("Belum dimulai"): abu-abu, bukan koral yang terbaca sebagai galat. */
.st-badge.netral {{ background: {T.LATAR_ELEVASI}; color: {T.TEKS_VARIAN}; }}
.murid-beranda-st .st-badge.netral {{ background: transparent; color: {T.TEKS_SUBTLE}; }}

@media print {{
  {_KERJA} .pg-opsi:has(input:checked) {{ background: transparent; border: 3px solid {T.TEKS_UTAMA}; box-shadow: none; }}
}}
"""
