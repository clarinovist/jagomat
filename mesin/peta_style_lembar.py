"""CSS lembar Peta Kemampuan 1 halaman A4 (`/contoh-peta-kemampuan/lembar`).

Dokumen mandiri (bukan bagian `gaya_stitch`). `@page` A4 tanpa margin; lembar
210 x 297 mm harus muat TEPAT satu halaman saat dicetak. Ukuran huruf mengikuti
mockup cetak (9,5-11,5px): lembar A4 sengaja lebih rapat dari aturan teks layar
14px. Di layar sempit lembar diperkecil dengan `transform: scale()` per rentang
lebar (tanpa JS), jadi tidak ada gulir horizontal. Warna dari `design_tokens`.
"""

import design_tokens as T
from peta_style import GAYA_UBIN

GAYA_LEMBAR = GAYA_UBIN + f"""
*, *::before, *::after {{ box-sizing: border-box; }}
@page {{ size: A4 portrait; margin: 0; }}
html, body {{ margin: 0; background: {T.LAPORAN_MEJA_LEMBAR}; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.peta-l-badan-st {{ font-family: {T.FONT_BODY}; color: {T.TEKS_JUDUL}; font-size: 8.62pt; line-height: 1.42; --peta-skala: 1; }}
.peta-l-badan-st :is(h1, h2, h3, b) {{ font-family: {T.FONT_HEADLINE}; }}
.peta-l-badan-st :is(h1, h2, h3, p) {{ margin: 0; }}
.peta-l-alat-st {{ max-width: 210mm; margin: 16px auto 0; display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; padding: 0 8px; }}
.peta-l-alat-st :is(a, button) {{ min-height: {T.TARGET_SENTUH}; padding: 0 16px; border-radius: {T.RADIUS_SEDANG}; border: {T.TEBAL_GARIS} solid {T.BORDER_KONTROL}; background: {T.LATAR_KARTU}; font: 600 14px {T.FONT_BODY}; color: {T.TEKS_JUDUL}; cursor: pointer; display: inline-flex; align-items: center; text-decoration: none; }}
.peta-l-alat-st .peta-l-utama-st {{ background: {T.AKSEN_KORAL_TUA}; border-color: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; }}
.peta-l-alat-st :is(a, button):focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.peta-l-bungkus-st {{ width: 210mm; margin: 12px auto 24px; }}
.peta-l-hal-st {{ display: flex; flex-direction: column; gap: 2.4mm; position: relative; overflow: hidden; width: 210mm; height: 297mm; padding: 8mm 9mm 7mm; background: {T.LATAR_MURID}; box-shadow: {T.LAPORAN_BAYANGAN_LEMBAR}; }}
.peta-l-hal-st > * {{ flex-shrink: 0; }}
.peta-l-kop-st {{ position: relative; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 4mm; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border-radius: 16px; padding: 3.4mm 5mm; overflow: hidden; }}
.peta-l-doodle-st {{ position: absolute; inset: 0; color: {T.LAPORAN_PUTIH_14}; font-family: {T.FONT_HEADLINE}; font-weight: 800; pointer-events: none; }}
.peta-l-doodle-st span {{ position: absolute; line-height: 1; }}
.peta-l-logo-kotak-st {{ background: {T.LATAR_MURID}; border-radius: {T.RADIUS_SEDANG}; padding: 5px 9px; display: inline-flex; margin-bottom: 6px; position: relative; }}
.peta-l-logo-kotak-st img {{ height: 20px; width: auto; display: block; }}
.peta-l-kop-st h1 {{ font-size: 15.75pt; font-weight: 800; letter-spacing: -.01em; position: relative; }}
.peta-l-kop-st p {{ font-size: 8.62pt; color: {T.LAPORAN_TEKS_HERO}; position: relative; }}
.peta-l-kop-st > img {{ width: 64px; height: 64px; position: relative; object-fit: contain; }}
.peta-l-data-st {{ display: grid; grid-template-columns: 1.3fr .7fr 1fr .8fr 1.4fr; border: 1.5px solid {T.TEKS_JUDUL}; border-radius: {T.RADIUS_SEDANG}; overflow: hidden; background: {T.LATAR_KARTU}; }}
.peta-l-data-st div {{ padding: 2mm 3mm; border-right: {T.TEBAL_GARIS} dashed {T.BORDER_VARIAN}; }}
.peta-l-data-st div:last-child {{ border-right: 0; }}
.peta-l-data-st small {{ display: block; font-size: 7.12pt; text-transform: uppercase; letter-spacing: .06em; color: {T.TEKS_VARIAN}; font-weight: 700; }}
.peta-l-data-st b {{ font-size: 9.38pt; }}
.peta-l-dua-st {{ display: grid; grid-template-columns: 52mm 1fr; gap: 2.4mm; }}
.peta-l-kartu-st {{ background: {T.LATAR_KARTU}; border: 1.5px solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU}; padding: 2.6mm 3.4mm; position: relative; }}
.peta-l-ttl-st {{ display: flex; align-items: center; gap: 6px; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 13px; margin-bottom: 1.6mm; }}
.peta-l-nomor-st {{ width: 20px; height: 20px; border-radius: {T.RADIUS_BULAT}; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; display: inline-flex; align-items: center; justify-content: center; font-size: 8.25pt; }}
.peta-l-skor-st {{ display: flex; flex-direction: column; align-items: center; gap: 1.4mm; text-align: center; }}
.peta-l-skor-st .peta-l-ttl-st {{ align-self: flex-start; }}
.peta-l-cincin-st {{ position: relative; width: 74px; height: 74px; }}
.peta-l-cincin-st svg {{ width: 74px; height: 74px; transform: rotate(-90deg); }}
.peta-cincin-trek-st, .peta-cincin-isi-st {{ fill: none; stroke-width: 14; }}
.peta-cincin-trek-st {{ stroke: {T.LAPORAN_GRID_BAR}; }}
.peta-cincin-isi-st {{ stroke: {T.AKSEN_MURID_UTAMA}; stroke-linecap: round; }}
.peta-l-cincin-angka-st {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
.peta-l-cincin-angka-st b {{ font-size: 19.5pt; line-height: 1; }}
.peta-l-cincin-angka-st small {{ font-size: 7.5pt; color: {T.TEKS_VARIAN}; }}
.peta-l-pita-st {{ background: {T.AKSEN_MURID_AMBER}; font-family: {T.FONT_HEADLINE}; font-weight: 800; padding: 2px 12px; border-radius: {T.RADIUS_PIL}; font-size: 12px; }}
.peta-l-posisi-st {{ background: {T.LAPORAN_TINT_NAVY}; border-radius: {T.RADIUS_KECIL}; padding: 1.2mm 2mm; font-weight: 600; line-height: 1.3; font-size: 7.88pt; }}
.peta-l-posisi-st b {{ color: {T.AKSEN_KORAL_TUA}; font-size: 13px; }}
.peta-l-posisi-st span {{ font-size: 7.12pt; color: {T.TEKS_VARIAN}; font-weight: 400; }}
.peta-l-lencana-st {{ display: flex; gap: 6px; justify-content: center; margin-top: 1mm; }}
.peta-l-lencana-st > span {{ display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 7.12pt; font-weight: 700; width: 68px; text-align: center; line-height: 1.2; }}
.peta-l-lencana-st i {{ width: 32px; height: 32px; border-radius: {T.RADIUS_BULAT}; display: flex; align-items: center; justify-content: center; border: 2px solid {T.TEKS_PUTIH}; box-shadow: 0 0 0 2px var(--peta-lencana); font-style: normal; }}
.peta-l-lencana-teal-st {{ --peta-lencana: {T.AKSEN_MURID_UTAMA}; }}
.peta-l-lencana-teal-st i {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.peta-l-lencana-amber-st {{ --peta-lencana: {T.AKSEN_MURID_AMBER}; }}
.peta-l-lencana-amber-st i {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.peta-l-lencana-st em {{ color: {T.TEKS_JUDUL}; font-style: normal; }}
.peta-l-materi-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 1.6mm; }}
.peta-l-materi-st li {{ display: grid; grid-template-columns: 28px 1fr 28mm 34px 28mm; align-items: center; gap: 2.5mm; }}
.peta-l-nm-st {{ font-weight: 600; }}
.peta-l-materi-st b {{ text-align: right; }}
.peta-bar-st {{ display: block; height: 9px; border-radius: {T.RADIUS_PIL}; background: {T.LAPORAN_GRID_BAR}; overflow: hidden; }}
.peta-bar-st i {{ display: block; height: 100%; border-radius: inherit; background-image: repeating-linear-gradient(-45deg, {T.LAPORAN_PUTIH_25} 0 6px, transparent 6px 12px); }}
.peta-bar-st .peta-bar-kuat-st {{ background-color: {T.AKSEN_MURID_UTAMA}; }}
.peta-bar-st .peta-bar-perkuat-st {{ background-color: {T.AKSEN_MURID_AMBER}; }}
.peta-status-st {{ display: inline-flex; align-items: center; justify-content: center; gap: 3px; font-size: 7.12pt; font-weight: 700; border-radius: {T.RADIUS_PIL}; padding: 1px 7px; text-align: center; white-space: nowrap; }}
.peta-status-kuat-st {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.peta-status-perkuat-st {{ background: {T.LATAR_REVIEW}; color: {T.TEKS_REVIEW}; }}
.peta-status-belum-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_VARIAN}; }}
.peta-l-temuan-st {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; }}
.peta-l-temuan-st li {{ display: flex; flex-direction: column; gap: 1mm; background: {T.LATAR_MURID}; border-radius: {T.RADIUS_SEDANG}; padding: 2.2mm 2.4mm; }}
.peta-l-temuan-st b {{ font-size: 8.62pt; line-height: 1.3; display: block; }}
.peta-l-hit-st {{ display: inline-block; margin-top: 1mm; font-size: 7.5pt; font-weight: 700; background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; border-radius: {T.RADIUS_PIL}; padding: 1px 7px; }}
.peta-l-ct-st {{ display: block; margin-top: 1mm; font-size: 7.88pt; color: {T.TEKS_VARIAN}; }}
.peta-l-resep-st {{ display: grid; grid-template-columns: auto 1fr; gap: 3.5mm; background: {T.LAPORAN_TINT_KORAL}; border: 1.5px dashed {T.AKSEN_KORAL_TUA}; border-radius: {T.RADIUS_KARTU}; padding: 2.6mm 3.6mm; }}
.peta-l-rx-st {{ width: 46px; height: 46px; border-radius: {T.RADIUS_KARTU}; background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; display: flex; align-items: center; justify-content: center; transform: rotate(-5deg); }}
.peta-l-resep-st h3 {{ font-size: 14px; font-weight: 800; }}
.peta-l-resep-st p {{ font-size: 8.25pt; }}
.peta-l-hari-st {{ display: flex; gap: 5px; margin-top: 2mm; }}
.peta-l-hr-st {{ display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 7.12pt; font-weight: 700; width: 34px; }}
.peta-l-hr-st i {{ width: 22px; height: 22px; border-radius: {T.RADIUS_BULAT}; border: 1.6px dashed {T.BORDER_KONTROL}; background: {T.LATAR_KARTU}; }}
.peta-l-misi-st {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; }}
.peta-l-misi-st li {{ background: {T.LATAR_KARTU}; border: 1.5px solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_SEDANG}; padding: 2.4mm 2.8mm; display: grid; grid-template-columns: auto 1fr; gap: 2.5mm; align-items: center; }}
.peta-l-no-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 7.5pt; background: {T.LATAR_REVIEW}; color: {T.TEKS_REVIEW}; border-radius: {T.RADIUS_PIL}; padding: 1px 8px; white-space: nowrap; }}
.peta-l-misi-st li:first-child .peta-l-no-st {{ background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; }}
.peta-l-misi-st b {{ font-size: 8.25pt; display: block; }}
.peta-l-k-st {{ font-size: 7.5pt; color: {T.TEKS_VARIAN}; }}
.peta-l-guru-st {{ display: grid; grid-template-columns: 1fr 62mm; gap: 4mm; align-items: end; }}
.peta-l-guru-st blockquote {{ margin: 0; font-style: italic; color: {T.TEKS_VARIAN}; border-left: 3px solid {T.AKSEN_MURID_UTAMA}; padding-left: 3mm; font-size: 8.62pt; }}
.peta-l-ttd-st {{ text-align: center; font-size: 7.88pt; }}
.peta-l-ttd-st b {{ font-size: 8.62pt; display: block; }}
.peta-l-garis-st {{ position: relative; height: 11mm; border-bottom: 1.5px solid {T.TEKS_JUDUL}; margin-bottom: 1.5mm; display: flex; align-items: flex-end; justify-content: center; }}
.peta-l-paraf-st {{ width: 140px; height: 37px; display: block; }}
.peta-l-paraf-t-st {{ font-family: "Snell Roundhand", "Segoe Script", "Brush Script MT", cursive; font-size: 22.5pt; fill: {T.AKSEN_TEAL_TUA}; }}
.peta-l-paraf-garis-st {{ fill: none; stroke: {T.AKSEN_TEAL_TUA}; stroke-width: 2; stroke-linecap: round; }}
.peta-l-cap-st {{ position: absolute; right: 1mm; bottom: -4mm; width: 62px; height: 62px; transform: rotate(-14deg); opacity: .85; }}
.peta-l-cap-garis-st, .peta-l-cap-garis-tipis-st {{ fill: none; stroke: {T.AKSEN_KORAL_TUA}; stroke-width: 3; }}
.peta-l-cap-garis-tipis-st {{ stroke-width: 1.5; }}
.peta-l-cap-t-st, .peta-l-cap-b-st, .peta-l-cap-k-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; fill: {T.AKSEN_KORAL_TUA}; }}
.peta-l-cap-t-st {{ font-size: 6.6pt; letter-spacing: .5px; }}
.peta-l-cap-b-st {{ font-size: 11.25pt; }}
.peta-l-cap-k-st {{ font-size: 6pt; font-weight: 700; }}
.peta-l-kaki-st {{ margin-top: auto; display: grid; grid-template-columns: 1fr auto; gap: 4mm; align-items: end; font-size: 7.12pt; color: {T.TEKS_VARIAN}; border-top: 1.5px dashed {T.BORDER_VARIAN}; padding-top: 2.4mm; }}
.peta-l-sint-st {{ display: inline-block; background: {T.LATAR_REVIEW}; color: {T.TEKS_REVIEW}; font-weight: 700; border-radius: {T.RADIUS_PIL}; padding: 1px 8px; margin-bottom: 1mm; }}
.peta-l-situs-st {{ text-align: right; }}
.peta-l-situs-st b {{ color: {T.AKSEN_TEAL_TUA}; }}
@media screen and (max-width: 820px) {{
  .peta-l-bungkus-st {{ width: 100%; height: calc(297mm * var(--peta-skala)); margin: 8px 0 16px; overflow: hidden; }}
  .peta-l-hal-st {{ transform-origin: top left; transform: scale(var(--peta-skala)); box-shadow: none; }}
  .peta-l-badan-st {{ --peta-skala: .9; }}
}}
@media screen and (max-width: 719px) {{ .peta-l-badan-st {{ --peta-skala: .75; }} }}
@media screen and (max-width: 599px) {{ .peta-l-badan-st {{ --peta-skala: .6; }} }}
@media screen and (max-width: 479px) {{ .peta-l-badan-st {{ --peta-skala: .5; }} }}
@media screen and (max-width: 399px) {{ .peta-l-badan-st {{ --peta-skala: .45; }} }}
@media screen and (max-width: 359px) {{ .peta-l-badan-st {{ --peta-skala: .4; }} }}
@media print {{
  html, body {{ background: {T.LATAR_MURID}; }}
  .peta-l-alat-st {{ display: none; }}
  .peta-l-bungkus-st {{ margin: 0; width: 210mm; height: 297mm; overflow: hidden; }}
  .peta-l-hal-st {{ margin: 0; box-shadow: none; transform: none; }}
}}
"""
