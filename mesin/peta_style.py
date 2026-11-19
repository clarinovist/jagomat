"""CSS laporan Peta Kemampuan playful (`/contoh-peta-kemampuan`).

Namespace `peta-...-st`; semua nilai dari `design_tokens` (tanpa warna literal).
Ikut `style_stitch.gaya_stitch()` hanya saat sakelar funnel hidup, bersama
`GAYA_FUNNEL`. Teks minimal 14px, target sentuh 44px, responsif 360px, dan animasi
hanya didefinisikan saat pengguna tidak meminta gerak berkurang.
"""

import design_tokens as T
from peta_donat import TEBAL_CINCIN

_TEKS_MIN = ".875rem"

# Ubin warna per materi: dipakai laporan dan lembar 1 halaman.
GAYA_UBIN = f"""/* Ubin warna per materi. */
.peta-ubin-st {{ display: inline-flex; align-items: center; justify-content: center; flex: none; border-radius: 14px; transform: rotate(-4deg); box-shadow: {T.LAPORAN_BAYANGAN_UBIN}; }}
.peta-u-s-st {{ width: 28px; height: 28px; border-radius: {T.RADIUS_KECIL}; transform: none; box-shadow: none; }}
.peta-u-m-st {{ width: 40px; height: 40px; }}
.peta-u-l-st {{ width: 52px; height: 52px; }}
.peta-u-xl-st {{ width: 72px; height: 72px; }}
.peta-ubin-teal-st {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.peta-ubin-koral-st {{ background: {T.LAPORAN_TINT_KORAL}; color: {T.AKSEN_KORAL_TUA}; }}
.peta-ubin-amber-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.peta-ubin-navy-st {{ background: {T.LAPORAN_TINT_NAVY}; color: {T.TEKS_JUDUL}; }}
.peta-ubin-mint-st {{ background: {T.LAPORAN_TINT_MINT}; color: {T.AKSEN_TEAL_TUA}; }}"""

GAYA_PETA = f"""
/* Laporan Peta Kemampuan: dasar, hero, tab. */
.peta-halaman-st {{ max-width: 68rem; }}
.peta-halaman-st .funnel-alis-st {{ font-size: {_TEKS_MIN}; }}
.peta-laporan-st {{ display: flex; flex-direction: column; gap: {T.SP_5}; max-width: 68rem; margin: 0 auto; padding-bottom: {T.SP_6}; font-family: {T.FONT_BODY}; font-size: 1rem; line-height: 1.55; color: {T.TEKS_JUDUL}; }}
.peta-laporan-st :is(h2, h3, h4) {{ font-family: {T.FONT_HEADLINE}; line-height: 1.2; letter-spacing: -.01em; margin: 0; }}
.peta-laporan-st p {{ margin: 0; }}
.peta-laporan-st svg {{ flex: none; }}
.peta-laporan-st a {{ color: {T.AKSEN_TEAL_TUA}; }}
.peta-laporan-st :is(a, button, summary):focus-visible, .peta-laporan-st input:focus-visible + label {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.peta-laporan-st [hidden] {{ display: none; }}
.peta-bantuan-st {{ font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; }}
.peta-alis-st {{ font-size: {_TEKS_MIN}; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: {T.AKSEN_TEAL_TUA}; }}
.peta-kartu-st {{ background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_5}; }}
.peta-judul-bagian-st {{ font-size: {T.UKURAN_BAGIAN_DEWASA}; font-weight: 700; }}
.peta-hanya-js-st {{ display: none; }}
.peta-js-st .peta-hanya-js-st {{ display: block; }}
.peta-js-st .peta-sebaris-st.peta-hanya-js-st {{ display: inline; }}
.peta-js-st .peta-tanpa-js-st {{ display: none; }}
.peta-tombol-st {{ display: inline-flex; align-items: center; justify-content: center; min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_4}; border: {T.TEBAL_GARIS} solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; font-size: {_TEKS_MIN}; font-weight: 600; text-decoration: none; }}
.peta-laporan-st a.peta-tombol-st {{ color: {T.TEKS_JUDUL}; }}
.peta-tombol-st:hover {{ border-color: {T.AKSEN_TEAL_TUA}; }}

{GAYA_UBIN}

/* Hero. */
.peta-hero-st {{ position: relative; overflow: hidden; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_5}; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: {T.SP_5}; align-items: center; }}
.peta-doodle-st {{ position: absolute; inset: 0; pointer-events: none; color: {T.LAPORAN_PUTIH_14}; font-family: {T.FONT_HEADLINE}; font-weight: 800; }}
.peta-doodle-st span {{ position: absolute; line-height: 1; }}
.peta-maskot-st {{ position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; }}
.peta-maskot-st img {{ width: 132px; height: 132px; object-fit: contain; }}
.peta-hero-tengah-st {{ position: relative; z-index: 1; display: flex; flex-direction: column; gap: {T.SP_3}; min-width: 0; }}
.peta-gelembung-st {{ position: relative; background: {T.LATAR_MURID}; color: {T.TEKS_JUDUL}; border-radius: 18px; padding: {T.SP_3} {T.SP_4}; font-weight: 600; font-size: {T.UKURAN_TEKS_BANTUAN}; max-width: 22rem; box-shadow: {T.LAPORAN_BAYANGAN_TIMBUL}; }}
.peta-gelembung-st::before {{ content: ""; position: absolute; left: -10px; top: 24px; border: 10px solid transparent; border-right-color: {T.LATAR_MURID}; border-left: 0; }}
.peta-hero-st .peta-alis-st {{ color: {T.LAPORAN_TEKS_HERO}; }}
.peta-hero-st :is(h1, h2) {{ font-family: {T.FONT_HEADLINE}; font-size: clamp(1.5rem, 3vw, 2rem); font-weight: 800; color: {T.TEKS_PUTIH}; margin: 0; line-height: 1.15; }}
.peta-chips-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; }}
.peta-chip-st {{ display: inline-flex; align-items: center; gap: 6px; min-height: 32px; padding: 2px {T.SP_3}; border-radius: {T.RADIUS_PIL}; font-size: {_TEKS_MIN}; font-weight: 600; background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.peta-hero-st .peta-chip-st {{ background: {T.LAPORAN_PUTIH_16}; color: {T.TEKS_PUTIH}; }}
.peta-hero-st .peta-chip-netral-st {{ background: {T.LAPORAN_PUTIH_10}; color: {T.LAPORAN_TEKS_HERO}; }}
.peta-skor-st {{ position: relative; z-index: 1; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; border-radius: 20px; padding: {T.SP_4}; display: flex; flex-direction: column; align-items: center; gap: {T.SP_2}; min-width: 176px; box-shadow: {T.LAPORAN_BAYANGAN_TIMBUL_KUAT}; transform: rotate(2deg); }}
.peta-skor-st .peta-bantuan-st {{ text-align: center; max-width: 11rem; }}
.peta-pita-st {{ background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; font-weight: 800; font-family: {T.FONT_HEADLINE}; font-size: 1rem; padding: 4px 14px; border-radius: {T.RADIUS_PIL}; }}
.peta-cincin-st {{ position: relative; width: 112px; height: 112px; }}
.peta-cincin-st svg {{ width: 112px; height: 112px; transform: rotate(-90deg); }}
.peta-cincin-trek-st, .peta-cincin-isi-st {{ fill: none; stroke-width: 14; }}
.peta-cincin-trek-st {{ stroke: {T.LAPORAN_GRID_BAR}; }}
.peta-cincin-isi-st {{ stroke: {T.AKSEN_MURID_UTAMA}; stroke-linecap: round; }}
.peta-cincin-angka-st {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
.peta-cincin-angka-st b {{ font-family: {T.FONT_HEADLINE}; font-size: 1.75rem; font-weight: 800; line-height: 1; }}
.peta-cincin-angka-st small {{ font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; }}
.peta-batas-st {{ display: flex; gap: {T.SP_3}; align-items: flex-start; border-left: 4px solid {T.AKSEN_MURID_AMBER}; background: {T.LATAR_CATATAN}; border-radius: {T.RADIUS_KECIL}; padding: {T.SP_3} {T.SP_4}; font-size: {T.UKURAN_TEKS_BANTUAN}; }}

/* Tab dan panel. */
.peta-tabs-st {{ display: flex; gap: {T.SP_2}; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }}
.peta-tabs-st a {{ flex: 1 0 auto; display: inline-flex; align-items: center; justify-content: center; gap: {T.SP_2}; min-height: {T.TINGGI_KONTROL}; padding: 0 {T.SP_4}; border-radius: {T.RADIUS_PIL}; border: 2px solid {T.ANAK_BORDER}; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: {T.UKURAN_TEKS_BANTUAN}; text-decoration: none; white-space: nowrap; }}
.peta-tabs-st a[aria-current="true"] {{ background: {T.AKSEN_TEAL_TUA}; border-color: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; box-shadow: 0 3px 0 {T.AKSEN_TEAL_HOVER}; }}
.peta-tabs-st a:hover:not([aria-current="true"]) {{ border-color: {T.AKSEN_TEAL_TUA}; }}
.peta-panel-st {{ display: flex; flex-direction: column; gap: {T.SP_5}; scroll-margin-top: {T.SP_4}; }}
.peta-kepala-panel-st {{ display: flex; align-items: center; gap: {T.SP_3}; }}
.peta-kepala-panel-st h2 {{ font-size: 1.25rem; font-weight: 800; }}
.peta-kepala-kartu-st {{ display: flex; flex-direction: column; gap: {T.SP_1}; }}

/* Ringkasan: posisi, histogram, lencana, daftar. */
.peta-posisi-st {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr); gap: {T.SP_5}; align-items: center; background: linear-gradient(135deg, {T.LAPORAN_TINT_NAVY}, {T.LATAR_KARTU} 60%); }}
.peta-posisi-kosong-st {{ grid-template-columns: minmax(0, 1fr); }}
.peta-posisi-kiri-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-posisi-besar-st {{ font-family: {T.FONT_HEADLINE}; font-size: clamp(1.25rem, 2.4vw, 1.6rem); font-weight: 800; line-height: 1.2; }}
.peta-posisi-besar-st b {{ color: {T.AKSEN_KORAL_TUA}; font-size: 1.5em; }}
.peta-posisi-kata-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_2}; font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.peta-posisi-kata-st li, .peta-daftar-st li {{ display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: {T.SP_2}; align-items: start; }}
.peta-histo-st {{ display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-histo-bar-st {{ display: grid; grid-template-columns: repeat(10, minmax(0, 1fr)); gap: 4px; align-items: end; height: 190px; padding-top: 44px; border-bottom: 2px solid {T.TEKS_JUDUL}; }}
.peta-kol-st {{ display: flex; flex-direction: column; justify-content: flex-end; align-items: center; height: 100%; position: relative; }}
.peta-bt-st {{ display: block; width: 100%; background: {T.BORDER_VARIAN}; border-radius: 6px 6px 0 0; position: relative; }}
.peta-kol-aktif-st .peta-bt-st {{ background: {T.AKSEN_KORAL_TUA}; box-shadow: 0 0 0 3px {T.LAPORAN_TINT_KORAL}; }}
.peta-kol-st small {{ position: absolute; bottom: -24px; font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; white-space: nowrap; }}
.peta-pin-st {{ position: absolute; bottom: calc(100% + 8px); left: 50%; transform: translateX(-50%); background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; font-size: {_TEKS_MIN}; font-weight: 700; white-space: nowrap; padding: 3px 9px; border-radius: {T.RADIUS_PIL}; }}
.peta-pin-st::after {{ content: ""; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-top-color: {T.TEKS_JUDUL}; }}
.peta-histo-st .peta-histo-ket-st {{ margin-top: 34px; font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; text-align: center; }}
.peta-lencana-wrap-st {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: {T.SP_3}; margin-top: {T.SP_4}; }}
.peta-lencana-st {{ display: flex; flex-direction: column; align-items: center; text-align: center; gap: {T.SP_2}; padding: {T.SP_4} {T.SP_2}; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_KARTU}; border: 2px solid {T.ANAK_BORDER}; }}
.peta-medali-st {{ position: relative; width: 76px; height: 84px; }}
.peta-bulat-lencana-st {{ position: absolute; top: 0; left: 4px; width: 68px; height: 68px; border-radius: {T.RADIUS_BULAT}; display: flex; align-items: center; justify-content: center; border: 4px solid {T.TEKS_PUTIH}; box-shadow: 0 0 0 3px var(--peta-lencana); }}
.peta-pita-k-st, .peta-pita-n-st {{ position: absolute; bottom: 0; width: 16px; height: 26px; background: var(--peta-lencana); clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 75%, 0 100%); }}
.peta-pita-k-st {{ left: 20px; transform: rotate(12deg); }}
.peta-pita-n-st {{ right: 20px; transform: rotate(-12deg); }}
.peta-lencana-teal-st {{ --peta-lencana: {T.AKSEN_MURID_UTAMA}; }}
.peta-lencana-teal-st .peta-bulat-lencana-st {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.peta-lencana-amber-st {{ --peta-lencana: {T.AKSEN_MURID_AMBER}; }}
.peta-lencana-amber-st .peta-bulat-lencana-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.peta-lencana-kunci-st {{ --peta-lencana: {T.BORDER_VARIAN}; border-style: dashed; background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.peta-lencana-kunci-st .peta-bulat-lencana-st {{ background: {T.LATAR_KARTU}; color: {T.BORDER_KONTROL}; }}
.peta-lencana-st b {{ font-family: {T.FONT_HEADLINE}; font-size: 1rem; line-height: 1.25; color: {T.TEKS_JUDUL}; }}
.peta-lencana-st small {{ font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; }}
.peta-tag-st {{ font-size: {_TEKS_MIN}; font-weight: 700; border-radius: {T.RADIUS_PIL}; padding: 2px 10px; }}
.peta-lencana-dapat-st .peta-tag-st {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.peta-lencana-kunci-st .peta-tag-st {{ background: {T.LATAR_REVIEW}; color: {T.TEKS_REVIEW}; }}
.peta-dua-st {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: {T.SP_4}; }}
.peta-daftar-st {{ list-style: none; margin: {T.SP_3} 0 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-k-kuat-st {{ background: linear-gradient(180deg, {T.ANAK_AKSEN_LATAR}, {T.LATAR_KARTU} 55%); }}
.peta-k-kuat-st h3 {{ color: {T.AKSEN_TEAL_TUA}; }}
.peta-k-perkuat-st {{ background: linear-gradient(180deg, {T.LATAR_REVIEW}, {T.LATAR_KARTU} 55%); }}
.peta-k-perkuat-st h3 {{ color: {T.AKSEN_AMBER_TUA}; }}
.peta-fokus-st {{ display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: {T.SP_4}; align-items: center; background: {T.LAPORAN_TINT_KORAL}; border-color: {T.LAPORAN_BORDER_KORAL}; }}
.peta-fokus-st h3 {{ font-size: 1.25rem; font-weight: 800; margin: 2px 0 {T.SP_1}; }}
.peta-lembar-ajak-st {{ display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: {T.SP_4}; align-items: center; background: {T.LATAR_REVIEW}; border-color: {T.BORDER_CATATAN}; }}
.peta-catatan-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-catatan-st blockquote {{ margin: 0; font-style: italic; color: {T.TEKS_VARIAN}; border-left: 3px solid {T.AKSEN_MURID_UTAMA}; padding-left: {T.SP_3}; }}
.peta-guru-st {{ display: flex; align-items: center; gap: {T.SP_3}; }}
.peta-guru-st small {{ display: block; color: {T.TEKS_VARIAN}; font-size: {_TEKS_MIN}; }}
.peta-inisial-st {{ width: 44px; height: 44px; border-radius: {T.RADIUS_BULAT}; background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; display: flex; align-items: center; justify-content: center; font-weight: 800; flex: none; }}

/* Per materi. */
.peta-legenda-st {{ display: flex; gap: {T.SP_4}; flex-wrap: wrap; font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; }}
.peta-status-st {{ display: inline-flex; align-items: center; gap: 4px; font-size: {_TEKS_MIN}; font-weight: 700; padding: 2px 10px; border-radius: {T.RADIUS_PIL}; white-space: nowrap; }}
.peta-status-kuat-st {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.peta-status-perkuat-st {{ background: {T.LATAR_REVIEW}; color: {T.TEKS_REVIEW}; }}
.peta-status-belum-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_VARIAN}; }}
.peta-materi-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-materi-st details {{ background: {T.LATAR_KARTU}; border: 2px solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU}; scroll-margin-top: {T.SP_4}; }}
.peta-materi-st details[open] {{ border-color: {T.AKSEN_TEAL_TUA}; }}
.peta-laporan-st summary {{ list-style: none; cursor: pointer; min-height: {T.TARGET_SENTUH}; }}
.peta-laporan-st summary::-webkit-details-marker {{ display: none; }}
.peta-laporan-st summary::after, .peta-laporan-st details[open] > summary::after {{ content: none; }}
.peta-materi-st summary {{ display: grid; grid-template-columns: auto minmax(0, 1fr) auto 24px; gap: {T.SP_2} {T.SP_3}; align-items: center; padding: {T.SP_4}; font: inherit; color: inherit; }}
.peta-nama-st {{ font-weight: 700; }}
.peta-nama-st small {{ display: block; font-weight: 400; font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; }}
.peta-kanan-st {{ display: flex; align-items: center; gap: {T.SP_2}; }}
.peta-persen-st {{ font-weight: 800; font-variant-numeric: tabular-nums; }}
.peta-panah-st {{ display: inline-flex; }}
.peta-materi-st summary .peta-bar-st {{ grid-column: 2 / -1; }}
.peta-bar-st {{ display: block; height: 14px; border-radius: {T.RADIUS_PIL}; background: {T.LAPORAN_GRID_BAR}; overflow: hidden; }}
.peta-bar-st i {{ display: block; height: 100%; border-radius: inherit; background-image: repeating-linear-gradient(-45deg, {T.LAPORAN_PUTIH_22} 0 8px, transparent 8px 16px); }}
.peta-bar-st .peta-bar-kuat-st {{ background-color: {T.AKSEN_MURID_UTAMA}; }}
.peta-bar-st .peta-bar-perkuat-st {{ background-color: {T.AKSEN_MURID_AMBER}; }}
.peta-isi-st {{ padding: 0 {T.SP_4} {T.SP_4}; display: flex; flex-direction: column; gap: {T.SP_4}; }}
.peta-grid-st {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: {T.SP_4}; }}
.peta-soal-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_4}; display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-label-st {{ font-size: {_TEKS_MIN}; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; color: {T.TEKS_VARIAN}; }}
.peta-langkah-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-langkah-st li {{ display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: {T.SP_2}; align-items: start; padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_KECIL}; background: {T.LATAR_KARTU}; font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.peta-n-st {{ width: 24px; height: 24px; border-radius: {T.RADIUS_BULAT}; background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; font-size: {_TEKS_MIN}; font-weight: 800; display: flex; align-items: center; justify-content: center; }}
.peta-langkah-st li.peta-salah-st {{ background: {T.LATAR_GALAT}; outline: 2px solid {T.AKSEN_MURID_KORAL}; }}
.peta-salah-st .peta-n-st {{ background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; }}
.peta-tanda-st {{ display: block; font-size: {_TEKS_MIN}; font-weight: 700; color: {T.TEKS_GALAT}; margin-top: 2px; }}
.peta-mono-st {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.peta-susun-st {{ display: grid; grid-template-columns: repeat(var(--peta-kol, 4), 1.2ch); justify-items: center; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 1.25rem; line-height: 1.35; width: max-content; padding: {T.SP_2} {T.SP_4}; background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_KECIL}; }}
.peta-bawa-st {{ font-size: {_TEKS_MIN}; color: {T.AKSEN_KORAL_TUA}; font-weight: 700; }}
.peta-garis-hasil-st {{ border-top: 2px solid {T.TEKS_JUDUL}; justify-self: stretch; text-align: center; }}
.peta-x-st {{ color: {T.AKSEN_KORAL_TUA}; text-decoration: line-through; }}
.peta-petak-isi-st {{ fill: {T.AKSEN_MURID_UTAMA}; stroke: {T.TEKS_JUDUL}; stroke-width: 2; }}
.peta-petak-kosong-st {{ fill: {T.LATAR_KARTU}; stroke: {T.TEKS_JUDUL}; stroke-width: 2; }}
.peta-latih-st {{ border: {T.TEBAL_GARIS} dashed {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_4}; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-latih-st h4 {{ font-size: 1rem; color: {T.AKSEN_TEAL_TUA}; }}

/* Pola kesalahan: donat dan daftar. */
.peta-pola-st {{ display: flex; flex-direction: column; gap: {T.SP_4}; position: relative; overflow: hidden; background-color: {T.LATAR_KARTU}; background-image: linear-gradient({T.LAPORAN_KERTAS_GARIS} 1px, transparent 1px), linear-gradient(90deg, {T.LAPORAN_KERTAS_GARIS} 1px, transparent 1px); background-size: 24px 24px; }}
.peta-hias-st {{ position: absolute; inset: 0; pointer-events: none; }}
.peta-simbol-hias-st {{ position: absolute; font-family: {T.FONT_HEADLINE}; font-weight: 800; color: {T.LAPORAN_SIMBOL_TEAL}; line-height: 1; }}
.peta-pita-judul-st {{ position: relative; align-self: center; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 1rem; padding: {T.SP_2} {T.SP_5}; border-radius: {T.RADIUS_PIL}; box-shadow: {T.LAPORAN_BAYANGAN_UBIN}; transform: rotate(-1.5deg); text-align: center; }}
.peta-donat-st {{ position: relative; width: 100%; max-width: 760px; margin: 0 auto; }}
.peta-donat-st svg {{ width: 100%; height: auto; display: block; overflow: visible; }}
.peta-seg-st {{ cursor: pointer; }}
.peta-seg-w0-st, .peta-seg-w1-st, .peta-seg-w2-st, .peta-seg-w3-st {{ fill: none; stroke-width: {TEBAL_CINCIN}; }}
.peta-seg-w0-st, .peta-garis-w0-st, .peta-kotak-w0-st, .peta-bulat-w0-st {{ stroke: {T.AKSEN_KORAL_TUA}; }}
.peta-seg-w1-st, .peta-garis-w1-st, .peta-kotak-w1-st, .peta-bulat-w1-st {{ stroke: {T.AKSEN_MURID_AMBER}; }}
.peta-seg-w2-st, .peta-garis-w2-st, .peta-kotak-w2-st, .peta-bulat-w2-st {{ stroke: {T.AKSEN_MURID_UTAMA}; }}
.peta-seg-w3-st, .peta-garis-w3-st, .peta-kotak-w3-st, .peta-bulat-w3-st {{ stroke: {T.TEKS_JUDUL}; }}
.peta-garis-w0-st, .peta-garis-w1-st, .peta-garis-w2-st, .peta-garis-w3-st {{ fill: none; stroke-width: 2.5; stroke-dasharray: 5 4; }}
.peta-kotak-w0-st, .peta-kotak-w1-st, .peta-kotak-w2-st, .peta-kotak-w3-st {{ fill: {T.LATAR_KARTU}; stroke-width: 2.5; }}
.peta-lbl-st circle.peta-bulat-w0-st {{ fill: {T.AKSEN_KORAL_TUA}; }}
.peta-lbl-st circle.peta-bulat-w1-st {{ fill: {T.AKSEN_MURID_AMBER}; }}
.peta-lbl-st circle.peta-bulat-w2-st {{ fill: {T.AKSEN_MURID_UTAMA}; }}
.peta-lbl-st circle.peta-bulat-w3-st {{ fill: {T.TEKS_JUDUL}; }}
.peta-bulat-w0-st, .peta-bulat-w1-st, .peta-bulat-w2-st, .peta-bulat-w3-st {{ stroke-width: 3; fill: {T.LATAR_KARTU}; }}
.peta-panah-w0-st {{ fill: {T.AKSEN_KORAL_TUA}; }}
.peta-panah-w1-st {{ fill: {T.AKSEN_MURID_AMBER}; }}
.peta-panah-w2-st {{ fill: {T.AKSEN_MURID_UTAMA}; }}
.peta-panah-w3-st {{ fill: {T.TEKS_JUDUL}; }}
.peta-cincin-kosong-st {{ fill: none; stroke: {T.LAPORAN_KERTAS_GARIS}; stroke-width: {TEBAL_CINCIN}; }}
.peta-lubang-st {{ fill: {T.LATAR_MURID}; }}
.peta-l-judul-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 14px; fill: {T.TEKS_JUDUL}; }}
.peta-l-sub-st {{ font-weight: 700; font-size: 14px; fill: {T.TEKS_VARIAN}; }}
.peta-l-materi-st {{ font-size: 14px; fill: {T.TEKS_VARIAN}; }}
.peta-simbol-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 16px; fill: {T.TEKS_PUTIH}; }}
.peta-angka-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 16px; fill: {T.TEKS_JUDUL}; stroke: none; }}
.peta-t-angka-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 33pt; fill: {T.TEKS_JUDUL}; }}
.peta-t-teks-st {{ font-size: 14px; font-weight: 600; fill: {T.TEKS_VARIAN}; }}
.peta-t-kecil-st {{ font-size: 14px; fill: {T.TEKS_VARIAN}; }}
.peta-pilih-st .peta-seg-st {{ opacity: .28; }}
.peta-pilih-st .peta-seg-st.peta-aktif-st {{ opacity: 1; }}
.peta-cara-baca-st {{ position: relative; text-align: center; font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; max-width: 40rem; align-self: center; background: {T.LATAR_MURID}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_2} {T.SP_4}; }}
.peta-pola-bawah-st {{ position: relative; display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr); gap: {T.SP_4}; align-items: start; }}
.peta-pola-daftar-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-pola-tombol-st {{ width: 100%; text-align: left; display: grid; grid-template-columns: 40px minmax(0, 1fr) auto; gap: {T.SP_3}; align-items: center; min-height: {T.TARGET_SENTUH}; padding: {T.SP_3}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_KARTU}; font: inherit; color: {T.TEKS_JUDUL}; text-decoration: none; cursor: pointer; }}
.peta-laporan-st a.peta-pola-tombol-st {{ color: {T.TEKS_JUDUL}; }}
.peta-js-st .peta-pola-tombol-st.peta-hanya-js-st {{ display: grid; }}
.peta-pola-tombol-st[aria-pressed="true"] {{ border-color: {T.AKSEN_TEAL_TUA}; box-shadow: inset 0 0 0 1px {T.AKSEN_TEAL_TUA}; }}
.peta-pola-tombol-st b {{ font-variant-numeric: tabular-nums; white-space: nowrap; }}
.peta-pola-tombol-st small {{ display: block; color: {T.TEKS_VARIAN}; font-size: {_TEKS_MIN}; }}
.peta-pola-detail-st {{ display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-detail-st {{ background: {T.LATAR_CATATAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_4}; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-js-st .peta-detail-st[hidden] {{ display: none; }}

/* Misi berikutnya. */
.peta-prioritas-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-prioritas-st details {{ border: 2px solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_KARTU}; }}
.peta-prioritas-st details[open] {{ border-color: {T.AKSEN_TEAL_TUA}; }}
.peta-prioritas-st summary {{ display: grid; grid-template-columns: auto auto minmax(0, 1fr) 24px; gap: {T.SP_3}; align-items: center; padding: {T.SP_4}; font: inherit; color: inherit; }}
.peta-prioritas-st summary small {{ display: block; color: {T.TEKS_VARIAN}; font-size: {_TEKS_MIN}; font-weight: 400; }}
.peta-no-st {{ font-family: {T.FONT_HEADLINE}; font-size: {_TEKS_MIN}; font-weight: 800; padding: 2px 10px; border-radius: {T.RADIUS_PIL}; background: {T.LATAR_REVIEW}; color: {T.TEKS_REVIEW}; white-space: nowrap; }}
.peta-prioritas-st li:first-child .peta-no-st {{ background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; }}
.peta-prioritas-st .peta-isi-st ul {{ margin: 0; padding-left: 20px; display: flex; flex-direction: column; gap: {T.SP_1}; }}
.peta-minggu-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-hari-st {{ display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: {T.SP_2}; }}
.peta-hari-st input {{ position: absolute; opacity: 0; pointer-events: none; }}
.peta-hari-st label {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; min-height: 64px; border: {T.TEBAL_GARIS} solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU}; font-size: {_TEKS_MIN}; font-weight: 600; cursor: pointer; user-select: none; }}
.peta-ck-st {{ width: 30px; height: 30px; border-radius: {T.RADIUS_BULAT}; border: 2px dashed {T.BORDER_KONTROL}; display: flex; align-items: center; justify-content: center; }}
.peta-ck-st svg {{ display: none; fill: {T.AKSEN_MURID_AMBER}; stroke: {T.AKSEN_AMBER_TUA}; }}
.peta-hari-st input:checked + label {{ background: {T.LATAR_REVIEW}; border-color: {T.AKSEN_AMBER_TUA}; color: {T.AKSEN_AMBER_TUA}; }}
.peta-hari-st input:checked + label .peta-ck-st {{ border: 0; }}
.peta-hari-st input:checked + label .peta-ck-st svg {{ display: block; }}
.peta-coba-st {{ position: relative; overflow: hidden; display: flex; flex-direction: column; gap: {T.SP_3}; background: {T.LAPORAN_TINT_NAVY}; border-color: {T.LAPORAN_BORDER_NAVY}; }}
.peta-coba-opsi-st {{ gap: {T.SP_2}; flex-wrap: wrap; }}
.peta-js-st .peta-coba-opsi-st.peta-hanya-js-st {{ display: flex; }}
.peta-coba-opsi-st button {{ min-height: {T.TARGET_SENTUH}; min-width: 96px; padding: 0 {T.SP_4}; border: 2px solid {T.BORDER_KONTROL}; border-radius: {T.RADIUS_PIL}; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-size: 1.125rem; font-weight: 700; cursor: pointer; box-shadow: {T.LAPORAN_BAYANGAN_TOMBOL}; }}
.peta-coba-opsi-st button.peta-benar-st {{ background: {T.LATAR_TERSIMPAN}; border-color: {T.TEKS_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.peta-coba-opsi-st button.peta-keliru-st {{ background: {T.LATAR_GALAT}; border-color: {T.TEKS_GALAT}; color: {T.TEKS_GALAT}; }}
.peta-coba-umpan-st {{ min-height: 1.5em; font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.peta-jawaban-st p {{ padding-bottom: {T.SP_3}; }}
.peta-konfeti-st {{ position: absolute; inset: 0; pointer-events: none; }}
.peta-konfeti-st i {{ position: absolute; top: -12px; width: 9px; height: 14px; border-radius: 2px; opacity: 0; background: {T.AKSEN_MURID_UTAMA}; }}
.peta-konfeti-st i:nth-child(4n + 2) {{ background: {T.AKSEN_MURID_KORAL}; }}
.peta-konfeti-st i:nth-child(4n + 3) {{ background: {T.AKSEN_MURID_AMBER}; }}
.peta-konfeti-st i:nth-child(4n) {{ background: {T.TEKS_JUDUL}; }}
.peta-jalur-st {{ list-style: none; margin: {T.SP_4} 0 0; padding: 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: {T.SP_3}; position: relative; }}
.peta-jalur-st::before {{ content: ""; position: absolute; top: 26px; left: 12%; right: 12%; border-top: 4px dashed {T.BORDER_VARIAN}; }}
.peta-jalur-st li {{ position: relative; display: flex; flex-direction: column; align-items: center; text-align: center; gap: {T.SP_2}; font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.peta-batu-st {{ width: 56px; height: 56px; border-radius: {T.RADIUS_BULAT}; display: flex; align-items: center; justify-content: center; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 1.25rem; background: {T.LATAR_KARTU}; border: 4px solid {T.AKSEN_MURID_UTAMA}; color: {T.AKSEN_TEAL_TUA}; box-shadow: {T.LAPORAN_BAYANGAN_TIMBUL}; }}
.peta-jalur-st li:last-child .peta-batu-st {{ border-color: {T.AKSEN_MURID_AMBER}; background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.peta-jalur-st b {{ font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; font-weight: 700; }}
.peta-program-st {{ display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: {T.SP_4}; align-items: start; }}
.peta-konsul-st {{ background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; border-color: {T.TEKS_JUDUL}; display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-konsul-st .peta-alis-st {{ color: {T.LAPORAN_TEKS_KONSUL}; }}
.peta-konsul-st h3 {{ color: {T.TEKS_PUTIH}; }}
.peta-konsul-st p {{ color: {T.LAPORAN_TEKS_KONSUL}; }}
.peta-konsul-st .landing-cta-baris-st {{ margin: 0; }}
.peta-kelas-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.peta-cek-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.peta-cek-st li {{ display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: {T.SP_2}; }}
.peta-cek-st svg {{ color: {T.AKSEN_TEAL_TUA}; }}
.peta-voucher-st {{ display: flex; gap: {T.SP_3}; align-items: flex-start; background: {T.LATAR_CATATAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_3} {T.SP_4}; font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.AKSEN_AMBER_TUA}; }}
.peta-voucher-st span {{ color: {T.TEKS_JUDUL}; }}
.peta-kaki-st {{ font-size: {_TEKS_MIN}; color: {T.TEKS_VARIAN}; display: flex; flex-direction: column; gap: {T.SP_2}; border-top: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; padding-top: {T.SP_4}; }}

/* Animasi: hanya bila pengguna tidak meminta gerak berkurang. */
@media (prefers-reduced-motion: no-preference) {{
  .peta-lompat-st {{ animation: peta-lompat .6s ease; }}
  .peta-tabs-st a, .peta-materi-st details, .peta-seg-st {{ transition: background-color {T.DURASI_CEPAT}, color {T.DURASI_CEPAT}, border-color {T.DURASI_CEPAT}, opacity {T.DURASI_CEPAT}; }}
  .peta-hari-st input:checked + label .peta-ck-st {{ animation: peta-pop .35s ease; }}
  .peta-konfeti-st.peta-jalan-st i {{ animation: peta-jatuh 1.4s ease-in forwards; }}
}}
@keyframes peta-lompat {{ 30% {{ transform: translateY(-14px) rotate(-6deg); }} 60% {{ transform: translateY(0) rotate(4deg); }} }}
@keyframes peta-pop {{ 0% {{ transform: scale(.3); }} 70% {{ transform: scale(1.25); }} 100% {{ transform: scale(1); }} }}
@keyframes peta-jatuh {{ 0% {{ opacity: 1; transform: translateY(0) rotate(0); }} 100% {{ opacity: 0; transform: translateY(260px) rotate(540deg); }} }}

/* Layar sempit. */
@media (max-width: {T.BATAS_TABLET}) {{
  .peta-hero-st {{ grid-template-columns: auto minmax(0, 1fr); }}
  .peta-hero-st .peta-skor-st {{ grid-column: 1 / -1; flex-direction: row; justify-content: center; flex-wrap: wrap; transform: none; }}
  .peta-maskot-st img {{ width: 96px; height: 96px; }}
  .peta-posisi-st, .peta-grid-st, .peta-pola-bawah-st, .peta-program-st, .peta-dua-st {{ grid-template-columns: minmax(0, 1fr); }}
  .peta-lencana-wrap-st {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .peta-jalur-st {{ grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: {T.SP_5}; }}
  .peta-jalur-st::before {{ display: none; }}
  .peta-fokus-st, .peta-lembar-ajak-st {{ grid-template-columns: auto minmax(0, 1fr); }}
  .peta-fokus-st .peta-tombol-st, .peta-lembar-ajak-st .peta-tombol-st {{ grid-column: 1 / -1; justify-self: start; }}
  .peta-fokus-st .peta-ubin-st {{ width: 56px; height: 56px; }}
  .peta-tabs-st a {{ flex: 0 0 auto; }}
  .peta-donat-st {{ aspect-ratio: 1 / 1; overflow: hidden; max-width: 360px; }}
  .peta-donat-st svg {{ position: absolute; width: var(--peta-w); left: var(--peta-x); top: var(--peta-y); max-width: none; }}
  .peta-lbl-st {{ display: none; }}
  .peta-kol-st small {{ display: none; }}
  .peta-kol-st:nth-child(3n + 1) small, .peta-kol-aktif-st small {{ display: block; }}
}}
@media (max-width: {T.BATAS_HP}) {{
  .peta-kartu-st {{ padding: {T.SP_4}; border-radius: {T.RADIUS_KARTU}; }}
  .peta-hero-st {{ grid-template-columns: minmax(0, 1fr); padding: {T.SP_4}; }}
  .peta-maskot-st {{ align-items: flex-start; }}
  .peta-gelembung-st::before {{ left: 28px; top: -10px; border: 10px solid transparent; border-bottom-color: {T.LATAR_MURID}; border-top: 0; }}
  .peta-materi-st summary {{ grid-template-columns: auto minmax(0, 1fr) 24px; }}
  .peta-materi-st summary .peta-kanan-st {{ grid-column: 2 / 3; grid-row: 2; flex-wrap: wrap; }}
  .peta-materi-st summary .peta-bar-st {{ grid-column: 1 / -1; }}
  .peta-prioritas-st summary {{ grid-template-columns: auto minmax(0, 1fr) 24px; }}
  .peta-prioritas-st summary .peta-ubin-st {{ display: none; }}
  .peta-jalur-st {{ grid-template-columns: minmax(0, 1fr); }}
  .peta-hari-st {{ gap: 4px; }}
  .peta-hari-st label {{ min-height: 56px; }}
  .peta-pola-tombol-st {{ grid-template-columns: 40px minmax(0, 1fr); }}
  .peta-pola-tombol-st b {{ grid-column: 2; }}
  .peta-konsul-st .landing-cta-baris-st a {{ width: 100%; justify-content: center; }}
}}
@media print {{
  .peta-tabs-st, .peta-konfeti-st, .peta-gelembung-st, .peta-coba-st {{ display: none; }}
  .peta-laporan-st .peta-panel-st[hidden] {{ display: flex; }}
}}
"""
