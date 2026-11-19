"""CSS sisi orang tua alur Cek Kemampuan (daftar jalur cek, siap mulai, QR, hasil, serah-ke-orang-tua).

Ikut `GAYA_FUNNEL` (hanya aktif saat sakelar funnel hidup), jadi halaman lain
tidak berubah byte-per-byte selama funnel mati. Semua nilai dari `design_tokens`
(tanpa warna literal); ukuran huruf hanya token `UKURAN_*` (minimal 14px);
target sentuh minimal `TARGET_SENTUH`. Tanpa JS: pilihan kelas adalah radio
native, progres adalah elemen `<progress>`.
"""

import design_tokens as T

GAYA_ALUR = f"""
/* Alur Cek Kemampuan sisi orang tua: kerangka, sapaan, tab, form. */
.funnel-alur-st {{ max-width: 30rem; margin: 0 auto; display: flex; flex-direction: column; gap: {T.SP_4}; font-family: {T.FONT_BODY}; color: {T.TEKS_JUDUL}; }}
.funnel-daftar-st {{ padding: {T.SP_3} {T.SP_4} {T.SP_6}; }}
.funnel-daftar-st :is(p, li, a, h1, h2, label, legend) {{ overflow-wrap: anywhere; }}
.funnel-alur-st :is(h1, h2, h3, p, ul) {{ margin: 0; }}
.funnel-sr-st {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }}
.funnel-appbar-st {{ display: flex; align-items: center; gap: {T.SP_3}; }}
.funnel-appbar-st .brand {{ display: inline-flex; align-items: center; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH}; color: {T.AKSEN_TEAL_TUA}; font: 800 {T.UKURAN_BAGIAN_DEWASA}/1 {T.FONT_HEADLINE}; text-decoration: none; }}
.funnel-appbar-label-st {{ margin-left: auto; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; color: {T.TEKS_VARIAN}; }}
.funnel-sapa-st {{ display: flex; align-items: flex-end; gap: {T.SP_2}; }}
.funnel-sapa-maskot-st {{ width: 6rem; height: 6rem; flex: none; object-fit: contain; }}
.funnel-gelembung-st {{ position: relative; margin-bottom: {T.SP_4}; padding: {T.SP_3} {T.SP_4}; background: {T.LATAR_KARTU}; border: {T.TEBAL_FOKUS} solid {T.TEKS_JUDUL}; border-radius: 18px; font-weight: 600; font-size: {T.UKURAN_BADAN_LAYAR}; line-height: 1.4; box-shadow: 0 4px 0 {T.ANAK_BORDER}; }}
.funnel-gelembung-st::before {{ content: ""; position: absolute; left: -12px; bottom: 14px; border: 10px solid transparent; border-right-color: {T.TEKS_JUDUL}; border-left: 0; }}
.funnel-gelembung-st::after {{ content: ""; position: absolute; left: -8px; bottom: 16px; border: 8px solid transparent; border-right-color: {T.LATAR_KARTU}; border-left: 0; }}
.funnel-alur-judul-st {{ font: 800 {T.UKURAN_JUDUL_STITCH}/1.15 {T.FONT_HEADLINE}; letter-spacing: -.02em; color: {T.TEKS_JUDUL}; }}
.funnel-tab-st {{ display: grid; grid-template-columns: 1fr 1fr; gap: {T.SP_1}; padding: {T.SP_1}; background: {T.LATAR_SEKUNDER_LEMBUT}; border-radius: 14px; }}
.funnel-tab-st > * {{ display: flex; align-items: center; justify-content: center; min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_2}; border-radius: 11px; font-weight: 700; font-size: {T.UKURAN_BADAN_LAYAR}; text-align: center; text-decoration: none; color: {T.TEKS_VARIAN}; }}
.funnel-tab-st > [aria-current] {{ background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; box-shadow: 0 2px 0 {T.ANAK_BORDER}; }}
.funnel-tab-st > a:hover {{ color: {T.AKSEN_TEAL_TUA}; text-decoration: underline; }}
.funnel-form-st {{ display: flex; flex-direction: column; gap: {T.SP_5}; }}
.funnel-seksi-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; min-width: 0; }}
.funnel-seksi-kepala-st {{ display: flex; align-items: center; gap: {T.SP_3}; }}
.funnel-nomor-st {{ width: 1.75rem; height: 1.75rem; flex: none; display: inline-flex; align-items: center; justify-content: center; border: {T.TEBAL_FOKUS} solid {T.TEKS_JUDUL}; border-radius: {T.RADIUS_BULAT}; background: {T.LATAR_MURID}; font: 800 {T.UKURAN_TEKS_LABEL}/1 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.funnel-seksi-judul-st {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.2 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.funnel-anak-sapa-st {{ font-weight: 600; font-size: {T.UKURAN_BADAN_LAYAR}; color: {T.TEKS_JUDUL}; }}
.funnel-alur-st .masuk-field-st {{ gap: {T.SP_2}; }}
.funnel-alur-st .masuk-field-st label {{ font: 700 {T.UKURAN_BADAN_LAYAR}/1.3 {T.FONT_BODY}; color: {T.TEKS_JUDUL}; }}
.funnel-alur-st .masuk-field-st input {{ min-height: {T.TINGGI_KONTROL}; padding: 0 {T.SP_3}; border: {T.TEBAL_FOKUS} solid {T.BORDER_KONTROL}; border-radius: 12px; font-size: {T.UKURAN_BADAN_LAYAR}; color: {T.TEKS_JUDUL}; }}
.funnel-alur-st .masuk-field-st input:focus {{ border-color: {T.AKSEN_TEAL_TUA}; box-shadow: {T.BAYANGAN_FOKUS}; }}
.funnel-alur-st .daftar-petunjuk-st {{ font-size: {T.UKURAN_TEKS_BANTUAN}; line-height: 1.5; color: {T.TEKS_VARIAN}; }}
.funnel-alur-st .masuk-galat-st {{ text-align: left; padding: {T.SP_3} {T.SP_4}; border-left: 3px solid {T.TEKS_GALAT}; font-size: {T.UKURAN_TEKS_BANTUAN}; overflow-wrap: anywhere; }}
.funnel-alur-st .masuk-galat-st p {{ margin: {T.SP_1} 0 0; }}
.funnel-kelas-st {{ display: flex; flex-direction: column; gap: {T.SP_2}; min-width: 0; margin: 0; padding: 0; border: 0; }}
.funnel-kelas-st legend {{ padding: 0; margin-bottom: {T.SP_2}; font: 700 {T.UKURAN_BADAN_LAYAR}/1.3 {T.FONT_BODY}; color: {T.TEKS_JUDUL}; }}
.funnel-kelas-grid-st {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: {T.SP_2}; }}
.funnel-kelas-pil-st {{ position: relative; display: block; cursor: pointer; }}
.funnel-kelas-pil-st input {{ position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; }}
.funnel-kelas-pil-st span {{ display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 4rem; border: {T.TEBAL_FOKUS} solid {T.ANAK_BORDER}; border-radius: 16px; background: {T.ANAK_AKSEN_LATAR}; font: 800 {T.UKURAN_BAGIAN_STITCH}/1 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.funnel-kelas-pil-st small {{ margin-top: {T.SP_1}; font: 600 {T.UKURAN_TEKS_LABEL}/1.2 {T.FONT_BODY}; color: {T.TEKS_VARIAN}; }}
.funnel-kelas-pil-st:nth-child(2) span, .funnel-kelas-pil-st:nth-child(6) span {{ background: {T.LATAR_GALAT}; }}
.funnel-kelas-pil-st:nth-child(3) span {{ background: {T.LATAR_REVIEW}; }}
.funnel-kelas-pil-st:nth-child(4) span {{ background: {T.ANAK_INFO_LATAR}; }}
.funnel-kelas-pil-st:nth-child(5) span {{ background: {T.ANAK_BAIK_LATAR}; }}
.funnel-kelas-pil-st input:checked + span {{ border-color: {T.TEKS_JUDUL}; box-shadow: 0 4px 0 {T.TEKS_JUDUL}; transform: rotate(-3deg); }}
.funnel-kelas-pil-st input:focus-visible + span {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; }}
.funnel-alur-st .daftar-persetujuan-st {{ padding: {T.SP_3}; background: {T.LATAR_CATATAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: 14px; }}
.funnel-alur-st .koreksi-centang-st {{ align-items: flex-start; gap: {T.SP_3}; margin: 0; font: 400 {T.UKURAN_TEKS_BANTUAN}/1.5 {T.FONT_BODY}; color: {T.TEKS_VARIAN}; cursor: pointer; }}
.funnel-alur-st .koreksi-centang-st input {{ width: 1.5rem; height: 1.5rem; margin: 2px 0 0; flex: none; accent-color: {T.AKSEN_TEAL_TUA}; }}
.funnel-alur-st .koreksi-centang-st a {{ color: {T.AKSEN_TEAL_TUA}; text-underline-offset: .2em; }}
.funnel-alur-st .masuk-tombol-st, .funnel-cta-st {{ min-height: {T.TINGGI_CTA}; justify-content: center; padding: 0 {T.SP_4}; border-radius: 14px; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font-size: {T.UKURAN_BADAN_LAYAR}; box-shadow: 0 4px 0 {T.AKSEN_TEAL_HOVER}; }}
.funnel-alur-st .masuk-tombol-st:hover, .funnel-cta-st:hover {{ background: {T.AKSEN_TEAL_HOVER}; text-decoration: underline; }}
.funnel-kaki-st {{ text-align: center; font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; }}
.funnel-alur-st :is(a, button, input, summary):focus-visible {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; }}

/* Siap mulai: kartu anak, info, tips, lipatan, persetujuan, pilihan perangkat. */
.funnel-sub-judul-st {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.2 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.funnel-alur-st h3.funnel-sub-judul-st {{ font-size: {T.UKURAN_BAGIAN_DEWASA}; }}
.funnel-bantuan-st {{ font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; line-height: 1.5; }}
.funnel-kartu-anak-st {{ display: flex; align-items: center; gap: {T.SP_3}; padding: {T.SP_3}; background: {T.LATAR_KARTU}; border: {T.TEBAL_FOKUS} solid {T.ANAK_BORDER}; border-radius: 18px; }}
.funnel-avatar-st {{ width: 3rem; height: 3rem; flex: none; display: flex; align-items: center; justify-content: center; border-radius: {T.RADIUS_BULAT}; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; font: 800 {T.UKURAN_BAGIAN_STITCH}/1 {T.FONT_HEADLINE}; transform: rotate(-6deg); }}
.funnel-kartu-anak-meta-st {{ flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: flex-start; gap: {T.SP_1}; }}
.funnel-kartu-anak-meta-st b {{ font-size: {T.UKURAN_BADAN_LAYAR}; color: {T.TEKS_JUDUL}; }}
.funnel-pita-st {{ display: inline-flex; align-items: center; min-height: 1.75rem; padding: 0 {T.SP_3}; border-radius: {T.RADIUS_PIL}; font: 700 {T.UKURAN_TEKS_LABEL}/1.2 {T.FONT_BODY}; }}
.funnel-pita-belum-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_VARIAN}; }}
.funnel-pita-jalan-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.funnel-progres-st {{ width: 100%; height: .5rem; margin-top: {T.SP_1}; border: 0; border-radius: {T.RADIUS_PIL}; overflow: hidden; appearance: none; background: {T.LATAR_ELEVASI}; }}
.funnel-progres-st::-webkit-progress-bar {{ background: {T.LATAR_ELEVASI}; }}
.funnel-progres-st::-webkit-progress-value {{ background: {T.AKSEN_MURID_UTAMA}; border-radius: {T.RADIUS_PIL}; }}
.funnel-progres-st::-moz-progress-bar {{ background: {T.AKSEN_MURID_UTAMA}; border-radius: {T.RADIUS_PIL}; }}
.funnel-info-st {{ display: grid; grid-template-columns: 1fr 1fr; gap: {T.SP_2}; }}
.funnel-info-st > div {{ display: flex; flex-direction: column; gap: 2px; padding: {T.SP_3}; border-radius: 16px; background: {T.ANAK_AKSEN_LATAR}; }}
.funnel-info-st > div:nth-child(2) {{ background: {T.LATAR_GALAT}; transform: rotate(1deg); }}
.funnel-info-st > div:nth-child(3) {{ background: {T.LATAR_REVIEW}; transform: rotate(1deg); }}
.funnel-info-st > div:nth-child(4) {{ background: {T.ANAK_INFO_LATAR}; transform: rotate(-1deg); }}
.funnel-info-st > div:nth-child(1) {{ transform: rotate(-1.5deg); }}
.funnel-info-st b {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.1 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.funnel-info-st span {{ font: 600 {T.UKURAN_TEKS_LABEL}/1.3 {T.FONT_BODY}; color: {T.TEKS_VARIAN}; }}
.funnel-tips-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; margin: 0; padding: 0; list-style: none; }}
.funnel-tips-st li {{ display: flex; align-items: flex-start; gap: {T.SP_3}; font-size: {T.UKURAN_TEKS_BANTUAN}; line-height: 1.5; color: {T.TEKS_JUDUL}; }}
.funnel-ubin-st {{ width: 2.25rem; height: 2.25rem; flex: none; display: inline-flex; align-items: center; justify-content: center; border-radius: 12px; transform: rotate(-4deg); box-shadow: 0 3px 0 {T.ANAK_BORDER}; }}
.funnel-ubin-besar-st {{ width: 3rem; height: 3rem; }}
.funnel-ubin-teal-st {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.funnel-ubin-koral-st {{ background: {T.LATAR_GALAT}; color: {T.AKSEN_KORAL_TUA}; }}
.funnel-ubin-amber-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.funnel-lipat-st {{ margin-top: {T.SP_3}; background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: 14px; }}
.funnel-lipat-st summary {{ display: flex; align-items: center; justify-content: space-between; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH}; padding: 0 {T.SP_3}; font: 700 {T.UKURAN_TEKS_BANTUAN}/1.3 {T.FONT_BODY}; color: {T.AKSEN_TEAL_TUA}; cursor: pointer; list-style: none; }}
.funnel-lipat-st summary::-webkit-details-marker {{ display: none; }}
.funnel-lipat-st summary::after {{ content: "+"; font-size: {T.UKURAN_BAGIAN_STITCH}; line-height: 1; }}
.funnel-lipat-st[open] > summary::after {{ content: "\\2013"; }}
.funnel-lipat-st > :not(summary) {{ margin: 0; padding: 0 {T.SP_3} {T.SP_3}; font-size: {T.UKURAN_TEKS_BANTUAN}; line-height: 1.5; color: {T.TEKS_VARIAN}; }}
.funnel-lipat-st ul {{ padding-left: {T.SP_5}; display: grid; gap: {T.SP_1}; }}
.funnel-alur-st .funnel-setuju-st {{ display: flex; align-items: flex-start; gap: {T.SP_3}; padding: {T.SP_3}; background: {T.LATAR_CATATAN}; border: {T.TEBAL_GARIS} solid {T.BORDER_CATATAN}; border-radius: 14px; font: 400 {T.UKURAN_TEKS_BANTUAN}/1.5 {T.FONT_BODY}; color: {T.TEKS_VARIAN}; cursor: pointer; }}
.funnel-alur-st label.funnel-setuju-st, .funnel-alur-st label.funnel-setuju-st span {{ font-weight: 400; color: {T.TEKS_VARIAN}; }}
.funnel-alur-st .funnel-setuju-st input {{ width: 1.5rem; height: 1.5rem; flex: none; margin: 2px 0 0; accent-color: {T.AKSEN_TEAL_TUA}; }}
.funnel-pilih-alat-st {{ display: grid; gap: {T.SP_3}; }}
.funnel-alur-st .funnel-pilih-alat-st .funnel-alat-st {{ display: flex; align-items: center; gap: {T.SP_3}; width: 100%; min-height: 4.75rem; padding: {T.SP_3} {T.SP_4}; text-align: left; cursor: pointer; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; border: {T.TEBAL_FOKUS} solid {T.ANAK_BORDER}; border-radius: 18px; box-shadow: 0 4px 0 {T.ANAK_BORDER}; font: 400 {T.UKURAN_BADAN_LAYAR}/1.3 {T.FONT_BODY}; }}
.funnel-alur-st .funnel-pilih-alat-st .funnel-alat-st:hover {{ border-color: {T.AKSEN_TEAL_TUA}; box-shadow: 0 4px 0 {T.AKSEN_TEAL_TUA}; }}
.funnel-alur-st .funnel-pilih-alat-st .funnel-alat-st:active {{ transform: translateY(3px); box-shadow: 0 1px 0 {T.ANAK_BORDER}; }}
.funnel-alur-st .funnel-pilih-alat-st .funnel-alat-st b {{ display: block; font-size: {T.UKURAN_BADAN_LAYAR}; color: {T.TEKS_JUDUL}; }}
.funnel-alur-st .funnel-pilih-alat-st .funnel-alat-st small {{ display: block; margin-top: 2px; font-size: {T.UKURAN_TEKS_LABEL}; line-height: 1.4; color: {T.TEKS_VARIAN}; }}

/* Lembar QR (gaya bottom-sheet tanpa JS). */
.funnel-lembar-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; padding: {T.SP_5} {T.SP_4} {T.SP_6}; background: {T.LATAR_KARTU}; border: {T.TEBAL_GARIS} solid {T.ANAK_BORDER}; border-radius: 28px 28px 0 0; box-shadow: {T.BAYANGAN_MENU}; }}
.funnel-pegangan-st {{ width: 2.75rem; height: .3rem; margin: -{T.SP_2} auto {T.SP_2}; border-radius: {T.RADIUS_PIL}; background: {T.BORDER_VARIAN}; }}
.funnel-lembar-aksi-st {{ display: flex; flex-direction: column; align-items: stretch; gap: {T.SP_2}; margin: 0; }}
.funnel-lembar-aksi-st .funnel-tautan-st {{ justify-content: center; }}
.funnel-alur-st .funnel-cta-tautan-st {{ display: flex; align-items: center; justify-content: center; min-height: {T.TINGGI_CTA}; padding: 0 {T.SP_4}; border-radius: 14px; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font: 700 {T.UKURAN_BADAN_LAYAR}/1.2 {T.FONT_HEADLINE}; text-decoration: none; box-shadow: 0 4px 0 {T.AKSEN_TEAL_HOVER}; }}
.funnel-alur-st .funnel-cta-tautan-st:hover {{ background: {T.AKSEN_TEAL_HOVER}; text-decoration: underline; }}

/* Hasil: kepala skor, cincin, ringkasan, daftar terkunci, kotak batas. */
.funnel-hasil-kepala-st {{ position: relative; display: flex; align-items: center; gap: {T.SP_4}; padding: {T.SP_4}; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.funnel-cincin-wadah-st {{ position: relative; width: 6.5rem; height: 6.5rem; flex: none; background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_BULAT}; transform: rotate(-4deg); box-shadow: 0 5px 0 {T.AKSEN_TEAL_HOVER}; }}
.funnel-cincin-svg-st {{ display: block; width: 100%; height: 100%; transform: rotate(-90deg); }}
.funnel-cincin-latar-st, .funnel-cincin-busur-st {{ fill: none; stroke-width: 12; }}
.funnel-cincin-latar-st {{ stroke: {T.LATAR_ELEVASI}; }}
.funnel-cincin-busur-st {{ stroke: {T.AKSEN_MURID_UTAMA}; }}
.funnel-cincin-angka-st {{ position: absolute; inset: 0; margin: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; color: {T.TEKS_JUDUL}; }}
.funnel-cincin-angka-st b {{ font: 800 {T.UKURAN_JUDUL_STITCH}/1 {T.FONT_HEADLINE}; }}
.funnel-cincin-angka-st small {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_VARIAN}; }}
.funnel-hasil-teks-st {{ display: flex; flex-direction: column; align-items: flex-start; gap: {T.SP_2}; min-width: 0; }}
.funnel-hasil-untuk-st {{ font: 700 {T.UKURAN_TEKS_LABEL}/1.3 {T.FONT_BODY}; color: {T.TEKS_PUTIH}; }}
.funnel-kategori-judul-st {{ font: 800 {T.UKURAN_BAGIAN_STITCH}/1.15 {T.FONT_HEADLINE}; color: {T.TEKS_PUTIH}; }}
.funnel-pil-hasil-st {{ display: inline-flex; align-items: center; min-height: 1.75rem; padding: {T.SP_1} {T.SP_3}; border-radius: {T.RADIUS_PIL}; background: {T.AKSEN_TEAL_HOVER}; color: {T.TEKS_PUTIH}; font: 700 {T.UKURAN_TEKS_LABEL}/1.2 {T.FONT_BODY}; }}
.funnel-benar-st {{ font: 700 {T.UKURAN_BADAN_LAYAR}/1.4 {T.FONT_BODY}; color: {T.TEKS_JUDUL}; text-align: center; }}
.funnel-ringkasan-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.funnel-ringkasan-st .funnel-chip-baris-st {{ margin: 0; padding: 0; list-style: none; }}
.funnel-terkunci-st {{ display: flex; flex-direction: column; gap: {T.SP_2}; margin: {T.SP_3} 0 0; padding: 0; list-style: none; }}
.funnel-terkunci-butir-st {{ display: flex; align-items: center; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; border-radius: 12px; background: {T.LATAR_KARTU}; font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; }}
.funnel-terkunci-butir-st svg {{ flex: none; }}
.funnel-batas-hasil-st {{ display: flex; flex-direction: column; gap: {T.SP_2}; padding: {T.SP_3} {T.SP_4}; border-left: 4px solid {T.AKSEN_MURID_AMBER}; background: {T.LATAR_CATATAN}; border-radius: {T.RADIUS_KECIL}; }}
.funnel-batas-hasil-st ul {{ display: grid; gap: {T.SP_1}; margin: 0; padding-left: {T.SP_4}; font-size: {T.UKURAN_TEKS_BANTUAN}; line-height: 1.5; color: {T.TEKS_JUDUL}; }}

/* Serah ke orang tua (login dengan lanjut ke hasil). */
.funnel-gembok-st {{ width: 3.5rem; height: 3.5rem; margin-bottom: {T.SP_3}; display: flex; align-items: center; justify-content: center; border-radius: 18px; background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; transform: rotate(-6deg); }}

@media (max-width: 560px) {{
  .funnel-hasil-kepala-st {{ gap: {T.SP_3}; padding: {T.SP_3}; }}
  .funnel-cincin-wadah-st {{ width: 5.5rem; height: 5.5rem; }}
  .funnel-cincin-angka-st b {{ font-size: {T.UKURAN_BAGIAN_STITCH}; }}
}}
@media (prefers-reduced-motion: reduce) {{
  .funnel-alat-st:active {{ transform: none; }}
}}
"""
