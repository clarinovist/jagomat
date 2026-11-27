"""CSS blok Peta Kemampuan versi 2 di halaman orang tua (F4): layar, grid per nomor, dan cetak A4 portrait.

Nilai hanya dari `design_tokens` (`T.*`). Cetak: hanya blok laporan yang tampil (kartu lain di halaman disembunyikan
lewat `:has()`), tiap bagian tidak terpotong antarhalaman, dan tombol cetak tidak ikut tercetak.
"""
from __future__ import annotations

import design_tokens as T

GAYA_PETA_V2 = f"""
.ortu-peta-cetak-baris-st {{ margin: 0; display: flex; justify-content: flex-end; }}
.ortu-peta-cetak-st {{ min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; border: 0; border-radius: {T.RADIUS_SEDANG};
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font: 700 {T.UKURAN_TEKS_LABEL}/1.4 {T.FONT_HEADLINE}; cursor: pointer; }}
.ortu-peta-cetak-st:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.ortu-peta-detail-st {{ display: grid; gap: {T.SP_3}; padding: 0; list-style: none; }}
.ortu-peta-detail-st li {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: {T.SP_1} {T.SP_3};
  font-size: {T.UKURAN_BADAN_LAYAR}; color: {T.TEKS_UTAMA}; }}
.ortu-peta-label-st {{ font-weight: 700; color: {T.TEKS_JUDUL}; }}
.ortu-peta-grid-st {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(3rem, 1fr)); gap: {T.SP_2};
  padding: 0; list-style: none; }}
.ortu-peta-soal-st {{ min-height: {T.TARGET_SENTUH}; display: flex; align-items: center; justify-content: center;
  border: 1px solid {T.GARIS_KISI}; border-radius: {T.RADIUS_SEDANG}; font: 700 {T.UKURAN_TEKS_LABEL}/1 {T.FONT_HEADLINE};
  color: {T.TEKS_JUDUL}; }}
.ortu-peta-soal-benar-st {{ background: {T.LAPORAN_TINT_MINT}; }}
.ortu-peta-soal-salah-st {{ background: {T.LAPORAN_TINT_KORAL}; }}
.ortu-peta-soal-dilewati-st {{ background: {T.LATAR_SEKUNDER_NETRAL}; }}
.ortu-peta-legenda-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2} {T.SP_4}; padding: 0; margin: 0; list-style: none;
  font-size: {T.UKURAN_TEKS_CATATAN}; color: {T.TEKS_VARIAN}; }}
.ortu-peta-sr-st {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }}
@page {{ size: A4 portrait; margin: 14mm; }}
@media print {{
  .funnel-alur-st:has(> .ortu-peta-v2-st) {{ max-width: none; }}
  .funnel-alur-st:has(> .ortu-peta-v2-st) > :not(.ortu-peta-v2-st) {{ display: none; }}
  .ortu-peta-v2-st {{ margin: 0; border: 0; box-shadow: none; }}
  .ortu-peta-v2-st .ortu-peta-bagian-st, .ortu-peta-v2-st .ortu-peta-grid-st li {{ break-inside: avoid; page-break-inside: avoid; }}
  .ortu-peta-v2-st .ortu-peta-cetak-baris-st {{ display: none; }}
}}
"""
