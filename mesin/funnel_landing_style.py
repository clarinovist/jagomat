"""CSS landing `/cek-kemampuan` gaya playful (v4, 19 Nov 2026).

Namespace `cek-...-st`, dipasang `style_stitch.gaya_stitch` bersama `GAYA_FUNNEL`
hanya saat `FUNNEL_AKTIF=1`. Semua nilai dari `design_tokens` (tanpa warna
literal). Animasi hanya didefinisikan di dalam
`prefers-reduced-motion: no-preference`, jadi pengguna yang mematikan gerak
tidak mendapat animasi (tanpa `!important`). Teks minimal 14px
(`UKURAN_TEKS_LABEL`), target sentuh minimal `TARGET_SENTUH`.
"""

import design_tokens as T

GAYA_LANDING_CEK = f"""
/* Landing Cek Kemampuan v4: dasar, judul, wadah. */
.cek-halaman-st {{ background: {T.LATAR_MURID}; color: {T.TEKS_JUDUL}; font-family: {T.FONT_BODY}; font-size: {T.UKURAN_BADAN_LAYAR}; line-height: {T.LINE_HEIGHT}; }}
.cek-halaman-st :is(h1, h2, h3) {{ font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; line-height: 1.15; letter-spacing: -.02em; }}
.cek-halaman-st [hidden] {{ display: none; }}
.cek-halaman-st summary::after, .cek-halaman-st details[open] > summary::after {{ content: none; }}
.cek-halaman-st section[id] {{ scroll-margin-top: {T.SP_4}; }}
.cek-w-st {{ max-width: {T.LEBAR_LANDING}; margin: 0 auto; padding: 0 {T.SP_4}; }}
.cek-blok-st {{ padding: {T.SP_8} 0; }}
.cek-rapat-st {{ padding-top: 0; }}
.cek-alis-st {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: {T.AKSEN_TEAL_TUA}; }}
.cek-halaman-st h2.cek-judul-b-st {{ font-size: clamp(1.6rem, 3.4vw, 2.3rem); font-weight: 800; }}
.cek-sub-b-st {{ color: {T.TEKS_VARIAN}; max-width: 40rem; font-size: {T.UKURAN_BADAN_LAYAR}; }}
.cek-kepala-st {{ display: flex; flex-direction: column; gap: {T.SP_2}; margin-bottom: {T.SP_5}; }}
.cek-kepala-st.cek-tengah-st {{ align-items: center; text-align: center; }}
.cek-halaman-st a {{ color: {T.AKSEN_TEAL_TUA}; }}
.cek-halaman-st :is(a, summary, button, [tabindex]):focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.AKSEN_TEAL_TUA}; outline-offset: 2px; }}

/* Ubin ikon. */
.cek-ubin-st {{ display: inline-flex; align-items: center; justify-content: center; flex: none; border-radius: 14px; transform: rotate(-4deg); box-shadow: {T.BAYANGAN_TIMBUL_TIPIS}; }}
.cek-ubin-44-st {{ width: 44px; height: 44px; }}
.cek-ubin-36-st {{ width: 36px; height: 36px; box-shadow: none; transform: none; }}
.cek-ubin-30-st {{ width: 30px; height: 30px; box-shadow: none; transform: none; }}
.cek-ubin-teal-st {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; }}
.cek-ubin-koral-st {{ background: {T.LATAR_UBIN_KORAL}; color: {T.AKSEN_KORAL_TUA}; }}
.cek-ubin-amber-st {{ background: {T.LATAR_REVIEW}; color: {T.AKSEN_AMBER_TUA}; }}
.cek-ubin-navy-st {{ background: {T.LATAR_UBIN_NAVY}; color: {T.TEKS_JUDUL}; }}
.cek-ubin-mint-st {{ background: {T.LATAR_UBIN_MINT}; color: {T.AKSEN_TEAL_TUA}; }}

/* Hero. */
.cek-hero-st {{ position: relative; overflow: hidden; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border-radius: 0 0 36px 36px; padding: {T.SP_7} 0 {T.SP_8}; }}
.cek-doodle-st {{ position: absolute; inset: 0; pointer-events: none; color: {T.DOODLE_PUTIH}; font-family: {T.FONT_HEADLINE}; font-weight: 800; }}
.cek-doodle-st span {{ position: absolute; line-height: 1; font-size: {T.UKURAN_DOODLE}; }}
.cek-doodle-st span:nth-child(1) {{ left: 2%; top: 10%; transform: rotate(-10deg); }}
.cek-doodle-st span:nth-child(2) {{ left: 38%; top: 78%; transform: rotate(12deg) scale(1.25); }}
.cek-doodle-st span:nth-child(3) {{ left: 48%; top: 4%; }}
.cek-doodle-st span:nth-child(4) {{ left: 60%; top: 66%; transform: rotate(-8deg); }}
.cek-doodle-st span:nth-child(5) {{ left: 92%; top: 8%; transform: rotate(10deg); }}
.cek-doodle-st span:nth-child(6) {{ left: 86%; top: 80%; }}
.cek-doodle-st span:nth-child(7) {{ left: 20%; top: 58%; transform: rotate(16deg) scale(.8); }}
.cek-doodle-st span:nth-child(8) {{ left: 72%; top: 30%; transform: scale(.85); }}
.cek-hero-isi-st {{ position: relative; display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr); gap: {T.SP_7}; align-items: center; }}
.cek-hero-kiri-st {{ display: flex; flex-direction: column; gap: 18px; min-width: 0; }}
.cek-tanya-st {{ display: inline-flex; align-self: flex-start; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: {T.UKURAN_TEKS_BANTUAN}; padding: 6px {T.SP_4}; border-radius: {T.RADIUS_PIL}; transform: rotate(-1.5deg); box-shadow: {T.BAYANGAN_TIMBUL_GELAP}; }}
.cek-halaman-st .cek-hero-st h1 {{ font-size: clamp(2.1rem, 5vw, 3.4rem); font-weight: 800; color: {T.TEKS_PUTIH}; margin: 0; }}
.cek-hero-st h1 em {{ font-style: normal; color: {T.AKSEN_MURID_AMBER}; background-image: linear-gradient({T.AKSEN_MURID_KORAL}, {T.AKSEN_MURID_KORAL}); background-repeat: no-repeat; background-size: 100% .12em; background-position: 0 96%; padding-bottom: .06em; }}
.cek-hero-st .cek-sub-st {{ font-size: {T.UKURAN_BAGIAN_DEWASA}; color: {T.TEKS_DI_TEAL}; max-width: 34rem; margin: 0; }}
.cek-hero-st .landing-cta-baris-st {{ margin: 0; }}
.cek-hero-st .landing-cta-baris-st a.tombol-coral {{ min-height: 56px; padding: 0 28px; border-radius: {T.RADIUS_PIL}; background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; font-size: {T.UKURAN_BAGIAN_DEWASA}; font-weight: 800; gap: 10px; box-shadow: 0 5px 0 {T.AKSEN_KORAL_TEPI}; }}
.cek-hero-st .landing-cta-baris-st a.tombol-coral:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.cek-hero-st .landing-cta-baris-st a.tombol-coral:focus-visible {{ outline-color: {T.AKSEN_MURID_AMBER}; }}
.cek-hero-st .landing-cta-baris-st a > span {{ font-size: 1rem; }}
.cek-kecil-st {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_DI_TEAL_REDUP}; margin: 0; }}
.cek-fakta-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; }}
.cek-fakta-st span {{ display: inline-flex; align-items: center; gap: 6px; background: {T.LATAR_BENING_PUTIH}; border-radius: {T.RADIUS_PIL}; padding: 6px {T.SP_3}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; }}

/* Panggung kartu bertumpuk. */
.cek-panggung-st {{ position: relative; min-height: 440px; }}
.cek-maskot-st {{ position: absolute; left: -8px; bottom: -12px; width: 150px; height: 150px; z-index: 3; filter: {T.BAYANGAN_MASKOT}; object-fit: contain; }}
.cek-gelembung-st {{ position: absolute; left: 120px; bottom: 118px; z-index: 4; margin: 0; background: {T.LATAR_MURID}; color: {T.TEKS_JUDUL}; border-radius: 18px; padding: 10px 14px; font-weight: 700; font-size: {T.UKURAN_TEKS_LABEL}; max-width: 15rem; box-shadow: {T.BAYANGAN_TIMBUL_GELAP}; }}
.cek-gelembung-st::before {{ content: ""; position: absolute; left: 18px; bottom: -10px; border: 10px solid transparent; border-top-color: {T.LATAR_MURID}; border-bottom: 0; }}
.cek-kt-st {{ position: absolute; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; border-radius: 20px; box-shadow: {T.BAYANGAN_TIMBUL_KARTU}; padding: 18px; }}
.cek-kt-skor-st {{ right: 8%; top: 0; width: 290px; transform: rotate(3deg); z-index: 2; }}
.cek-kt-materi-st {{ right: 0; top: 206px; width: 300px; transform: rotate(-4deg); z-index: 1; }}
.cek-kt-lencana-st {{ left: 6%; top: 36px; width: 150px; transform: rotate(-8deg); z-index: 1; text-align: center; }}
.cek-panggung-st .cek-kt-st:hover, .cek-panggung-st .cek-kt-st:focus-visible {{ transform: rotate(0) scale(1.04); z-index: 5; }}
.cek-panggung-st .cek-kt-st.cek-kt-depan-st {{ transform: rotate(0) scale(1.04); z-index: 5; }}
.cek-lbl-st {{ display: flex; justify-content: space-between; align-items: center; gap: {T.SP_2}; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 700; color: {T.TEKS_VARIAN}; }}
.cek-lbl-st span {{ background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_PIL}; padding: 2px 10px; }}
.cek-nama-contoh-st {{ font-weight: 700; margin: 6px 0 0; }}
.cek-skor-baris-st {{ display: flex; align-items: center; gap: 14px; margin-top: 10px; }}
.cek-cincin-st {{ position: relative; width: 86px; height: 86px; flex: none; }}
.cek-cincin-st svg {{ width: 86px; height: 86px; transform: rotate(-90deg); }}
.cek-cincin-jalur-st {{ stroke: {T.LATAR_JALUR_BAR}; }}
.cek-cincin-isi-st {{ stroke: {T.AKSEN_MURID_UTAMA}; }}
.cek-cincin-angka-st {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }}
.cek-cincin-angka-st b {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_JUDUL_STITCH}; line-height: 1; }}
.cek-cincin-angka-st small {{ font-size: {T.UKURAN_TEKS_META}; color: {T.TEKS_VARIAN}; }}
.cek-pita-st {{ display: inline-block; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: {T.UKURAN_TEKS_LABEL}; border-radius: {T.RADIUS_PIL}; padding: 2px 12px; }}
.cek-ringkas-st {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_VARIAN}; margin: 6px 0 0; }}
.cek-posisi-st {{ margin: 10px 0 0; background: {T.LATAR_UBIN_NAVY}; border-radius: {T.RADIUS_SEDANG}; padding: 6px 10px; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; }}
.cek-posisi-st b {{ color: {T.AKSEN_KORAL_TUA}; }}
.cek-mini-materi-st {{ list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.cek-mini-materi-st li {{ display: grid; grid-template-columns: 30px minmax(0, 1fr); gap: {T.SP_2}; align-items: center; font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 600; }}
.cek-materi-nama-st {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0 {T.SP_2}; }}
.cek-materi-nama-st b {{ font-weight: 700; color: {T.TEKS_VARIAN}; text-align: right; }}
.cek-bar-st {{ grid-column: 2; height: 8px; border-radius: 9px; background: {T.LATAR_JALUR_BAR}; overflow: hidden; }}
.cek-bar-st i {{ display: block; height: 100%; border-radius: inherit; background-color: {T.AKSEN_MURID_UTAMA}; background-image: repeating-linear-gradient(-45deg, {T.GARIS_BENING_PUTIH} 0 6px, transparent 6px 12px); }}
.cek-bar-lemah-st i {{ background-color: {T.AKSEN_MURID_AMBER}; }}
.cek-bar-83-st i {{ width: 83%; }}
.cek-bar-55-st i {{ width: 55%; }}
.cek-bar-35-st i {{ width: 35%; }}
.cek-medali-st {{ width: 70px; height: 70px; margin: 4px auto 6px; border-radius: {T.RADIUS_BULAT}; background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; display: flex; align-items: center; justify-content: center; border: 4px solid {T.TEKS_PUTIH}; box-shadow: 0 0 0 3px {T.AKSEN_MURID_UTAMA}; }}
.cek-kt-lencana-st b {{ font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_TEKS_LABEL}; display: block; }}
.cek-kt-lencana-st small {{ font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_VARIAN}; }}
.cek-ket-contoh-st {{ position: absolute; right: 0; bottom: -28px; margin: 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_DI_TEAL_REDUP}; }}

/* Cerita: situasi, akar masalah, jembatan, solusi (statis, tanpa JS). */
.cek-situasi-st {{ list-style: none; margin: 0 0 {T.SP_5}; padding: 0; display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }}
.cek-situasi-st li {{ display: grid; grid-template-columns: 44px minmax(0, 1fr); gap: 14px; align-items: start; background: {T.LATAR_KARTU}; border: 2px solid {T.ANAK_BORDER}; border-radius: 20px; padding: {T.SP_4}; box-shadow: {T.BAYANGAN_TIMBUL_HALUS}; }}
.cek-situasi-judul-st {{ display: block; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: {T.UKURAN_BAGIAN_DEWASA}; line-height: 1.25; }}
.cek-situasi-isi-st {{ margin: {T.SP_2} 0 0; color: {T.TEKS_VARIAN}; }}
.cek-akar-st {{ background: {T.LATAR_REVIEW}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_5}; display: flex; flex-direction: column; gap: {T.SP_2}; }}
.cek-akar-st p {{ margin: 0; }}
.cek-akar-judul-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: {T.UKURAN_BAGIAN_STITCH}; line-height: 1.25; }}
.cek-jembatan-st {{ text-align: center; max-width: 44rem; margin: {T.SP_7} auto; display: flex; flex-direction: column; gap: {T.SP_3}; }}
.cek-jembatan-st p {{ margin: 0; color: {T.TEKS_VARIAN}; }}
.cek-halaman-st .cek-jembatan-st p.cek-jembatan-kutip-st {{ font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: clamp(1.4rem, 3vw, 2rem); line-height: 1.25; letter-spacing: -.02em; color: {T.TEKS_JUDUL}; }}
.cek-solusi-st {{ background: {T.TEKS_JUDUL}; color: {T.TEKS_PUTIH}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: 26px; display: flex; flex-direction: column; align-items: flex-start; gap: 14px; }}
.cek-solusi-st .cek-alis-st {{ color: {T.AKSEN_MURID_AMBER}; }}
.cek-halaman-st .cek-solusi-st h3 {{ font-size: {T.UKURAN_JUDUL_STITCH}; color: {T.TEKS_PUTIH}; margin: 0; }}
.cek-solusi-st p {{ margin: 0; color: {T.TEKS_DI_NAVY}; }}
.cek-solusi-daftar-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; color: {T.TEKS_DI_NAVY}; }}
.cek-solusi-daftar-st li {{ display: grid; grid-template-columns: 24px minmax(0, 1fr); gap: 10px; align-items: start; }}
.cek-solusi-st a {{ color: {T.AKSEN_MURID_AMBER}; font-weight: 700; }}
.cek-solusi-st a:focus-visible {{ outline-color: {T.AKSEN_MURID_AMBER}; }}
.cek-solusi-tautan-st {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; font-family: {T.FONT_HEADLINE}; text-underline-offset: 3px; }}

/* Demo tebak langkah. */
.cek-demo-w-st {{ background-color: {T.LATAR_KARTU}; border: 2px solid {T.ANAK_BORDER}; border-radius: 28px; padding: 28px; overflow: hidden; background-image: linear-gradient({T.GARIS_KISI} 1px, transparent 1px), linear-gradient(90deg, {T.GARIS_KISI} 1px, transparent 1px); background-size: 24px 24px; }}
.cek-demo-st {{ display: grid; grid-template-columns: minmax(0, .8fr) minmax(0, 1.2fr); gap: 28px; align-items: center; }}
.cek-soal-k-st {{ background: {T.LATAR_MURID}; border-radius: 20px; padding: 22px; display: flex; flex-direction: column; gap: 10px; align-items: flex-start; box-shadow: {T.BAYANGAN_TIMBUL_SEDANG}; transform: rotate(-2deg); }}
.cek-label-st {{ font-size: {T.UKURAN_TEKS_LABEL}; font-weight: 800; letter-spacing: .06em; text-transform: uppercase; color: {T.TEKS_VARIAN}; }}
.cek-soal-teks-st {{ margin: 0; font-family: ui-monospace, Menlo, monospace; font-size: {T.UKURAN_BAGIAN_STITCH}; }}
.cek-susun-st {{ display: grid; grid-template-columns: repeat(4, 1.3ch); justify-items: center; font-family: ui-monospace, Menlo, monospace; font-size: {T.UKURAN_ANGKA_FUNNEL_HP}; line-height: 1.3; background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_2} 18px; }}
.cek-bawa-st {{ font-size: {T.UKURAN_BAGIAN_DEWASA}; color: {T.AKSEN_KORAL_TUA}; font-weight: 700; }}
.cek-gr-st {{ border-top: 3px solid {T.TEKS_JUDUL}; justify-self: stretch; text-align: center; }}
.cek-digit-salah-st {{ color: {T.AKSEN_KORAL_TUA}; text-decoration: line-through; }}
.cek-jwb-st {{ margin: 0; font-size: {T.UKURAN_TEKS_BANTUAN}; }}
.cek-langkah-d-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }}
.cek-langkah-d-st li {{ border: 2px solid {T.ANAK_BORDER}; border-radius: 14px; background: {T.LATAR_KARTU}; }}
.cek-langkah-isi-st {{ display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: {T.SP_3}; align-items: center; min-height: 60px; padding: 10px 14px; }}
.cek-langkah-d-st button {{ display: block; width: 100%; padding: 0; border: 0; border-radius: 12px; background: transparent; font: inherit; color: inherit; text-align: left; cursor: pointer; }}
.cek-langkah-d-st li:has(button):hover {{ border-color: {T.AKSEN_TEAL_TUA}; }}
.cek-no-st {{ width: 32px; height: 32px; border-radius: {T.RADIUS_BULAT}; background: {T.ANAK_AKSEN_LATAR}; color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE}; font-weight: 800; display: flex; align-items: center; justify-content: center; }}
.cek-langkah-d-st button.cek-keliru-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.cek-langkah-d-st button.cek-tepat-st {{ background: {T.LATAR_GALAT}; outline: 3px solid {T.AKSEN_KORAL_TUA}; outline-offset: -3px; }}
.cek-tepat-st .cek-no-st {{ background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; }}
.cek-kunci-d-st {{ margin-top: {T.SP_3}; background: {T.LATAR_MURID}; border-radius: {T.RADIUS_KARTU}; padding: 0 {T.SP_4}; }}
.cek-kunci-d-st summary {{ min-height: {T.TARGET_SENTUH}; display: flex; align-items: center; justify-content: space-between; font-weight: 700; cursor: pointer; }}
.cek-kunci-d-st p {{ margin: 0 0 {T.SP_3}; font-weight: 600; }}
.cek-umpan-st {{ margin: {T.SP_3} 0 0; min-height: 3.2em; font-weight: 600; }}
.cek-umpan-ok-st {{ color: {T.TEKS_GALAT}; }}
.cek-demo-bawah-st {{ margin: {T.SP_2} 0 0; color: {T.TEKS_VARIAN}; }}
.cek-demo-bawah-st a, .cek-naik-st {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; font-weight: 700; }}

/* Jalur tiga langkah. */
.cek-jalur-st {{ list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; position: relative; }}
.cek-jalur-st::before {{ content: ""; position: absolute; top: 44px; left: 16%; right: 16%; border-top: 4px dashed {T.BORDER_VARIAN}; }}
.cek-jalur-st li {{ position: relative; display: flex; flex-direction: column; align-items: center; text-align: center; gap: 10px; padding: 0 {T.SP_2}; }}
.cek-batu-st {{ width: 88px; height: 88px; border-radius: {T.RADIUS_BULAT}; background: {T.LATAR_KARTU}; border: 5px solid {T.AKSEN_MURID_UTAMA}; display: flex; align-items: center; justify-content: center; box-shadow: {T.BAYANGAN_TIMBUL_SEDANG}; position: relative; color: {T.AKSEN_TEAL_TUA}; }}
.cek-no-batu-st {{ position: absolute; top: -8px; right: -8px; width: 30px; height: 30px; border-radius: {T.RADIUS_BULAT}; background: {T.AKSEN_MURID_AMBER}; color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: {T.UKURAN_TEKS_BANTUAN}; display: flex; align-items: center; justify-content: center; border: 3px solid {T.LATAR_MURID}; }}
.cek-jalur-st li:nth-child(2) .cek-batu-st {{ border-color: {T.AKSEN_MURID_KORAL}; color: {T.AKSEN_KORAL_TUA}; }}
.cek-jalur-st li:nth-child(3) .cek-batu-st {{ border-color: {T.AKSEN_MURID_AMBER}; color: {T.AKSEN_AMBER_TUA}; }}
.cek-halaman-st .cek-jalur-st h3 {{ font-size: {T.UKURAN_BAGIAN_STITCH}; margin: 0; }}
.cek-jalur-st p {{ margin: 0; font-size: {T.UKURAN_TEKS_BANTUAN}; color: {T.TEKS_VARIAN}; max-width: 18rem; }}

/* Hasil gratis. */
.cek-gratis-w-st {{ max-width: 640px; margin: 0 auto; }}
.cek-peta-lanjut-st {{ margin: {T.SP_5} auto 0; max-width: 40rem; text-align: center; color: {T.TEKS_VARIAN}; }}
.cek-kartu-g-st {{ background: {T.LATAR_KARTU}; border: 2px solid {T.ANAK_BORDER}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_5}; display: flex; flex-direction: column; gap: 14px; }}
.cek-harga-st {{ margin: 0; font-family: {T.FONT_HEADLINE}; font-size: 2.5rem; font-weight: 800; line-height: 1; }}
.cek-harga-st small {{ font-family: {T.FONT_BODY}; font-size: 1rem; color: {T.TEKS_VARIAN}; font-weight: 600; margin-left: 6px; }}
.cek-cek-st {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }}
.cek-cek-st li {{ display: grid; grid-template-columns: 32px 1fr; gap: 10px; align-items: start; }}
.cek-kartu-catatan-st {{ margin: auto 0 0; font-size: {T.UKURAN_TEKS_LABEL}; color: {T.TEKS_VARIAN}; }}
.cek-tautan-st {{ margin: 0; display: flex; flex-wrap: wrap; gap: 0 20px; }}
.cek-tautan-st a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; }}
.cek-tautan-st a {{ text-underline-offset: 3px; }}
.cek-tautan-tengah-st {{ justify-content: center; }}
.cek-tautan-st a.cek-tautan-contoh-st {{ text-decoration-thickness: 2px; }}
/* FAQ. */
.cek-faq-st {{ display: flex; flex-direction: column; gap: 10px; max-width: 48rem; margin: 0 auto; }}
.cek-faq-st details {{ background: {T.LATAR_KARTU}; border: 2px solid {T.ANAK_BORDER}; border-radius: 16px; }}
.cek-faq-st details[open] {{ border-color: {T.AKSEN_TEAL_TUA}; }}
.cek-faq-st summary {{ list-style: none; cursor: pointer; display: grid; grid-template-columns: 40px 1fr 24px; gap: {T.SP_3}; align-items: center; padding: 14px {T.SP_4}; min-height: 56px; font-weight: 700; }}
.cek-faq-st summary::-webkit-details-marker {{ display: none; }}
.cek-tanda-st {{ display: inline-flex; }}
.cek-faq-st details[open] .cek-tanda-st {{ transform: rotate(45deg); }}
.cek-isi-f-st {{ padding: 0 {T.SP_4} {T.SP_4} 68px; color: {T.TEKS_VARIAN}; }}
.cek-isi-f-st ul {{ margin: 0; padding-left: 18px; }}

/* Penutup. */
.cek-penutup-st {{ background: {T.ANAK_AKSEN_LATAR}; border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_6}; display: grid; grid-template-columns: auto 1fr; gap: {T.SP_5}; align-items: center; }}
.cek-penutup-st img {{ width: 140px; height: 140px; object-fit: contain; }}
.cek-halaman-st .cek-penutup-st h2 {{ font-size: clamp(1.5rem, 3vw, 2rem); font-weight: 800; margin: 0 0 {T.SP_2}; }}
.cek-naik-st {{ margin-top: {T.SP_2}; font-family: {T.FONT_HEADLINE}; font-size: {T.UKURAN_BADAN_LAYAR}; font-weight: 800; color: {T.AKSEN_TEAL_TUA}; text-decoration: none; border-bottom: 3px solid {T.AKSEN_MURID_UTAMA}; }}
.cek-penutup-bungkus-st {{ padding-bottom: {T.SP_7}; }}

@media (max-width: 60rem) {{
  .cek-hero-isi-st {{ grid-template-columns: minmax(0, 1fr); }}
  .cek-panggung-st {{ min-height: 420px; max-width: 440px; width: 100%; margin: 0 auto; }}
}}
@media (max-width: 48rem) {{
  .cek-demo-st {{ grid-template-columns: minmax(0, 1fr); }}
  .cek-jalur-st {{ grid-template-columns: minmax(0, 1fr); gap: 28px; }}
  .cek-jalur-st::before {{ top: 44px; bottom: 44px; left: 50%; right: auto; border-top: 0; border-left: 4px dashed {T.BORDER_VARIAN}; }}
  .cek-jalur-st li {{ background: {T.LATAR_MURID}; padding: 6px; }}
  .cek-penutup-st {{ grid-template-columns: minmax(0, 1fr); text-align: center; justify-items: center; }}
  .cek-blok-st {{ padding: {T.SP_7} 0; }}
  .cek-rapat-st {{ padding-top: 0; }}
}}
@media (min-width: 48rem) {{
  .cek-situasi-st {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
  .cek-situasi-st li {{ grid-template-columns: minmax(0, 1fr); }}
}}
@media (max-width: 30rem) {{
  .cek-hero-st {{ padding: {T.SP_6} 0 56px; }}
  .cek-hero-st .landing-cta-baris-st a.tombol-coral {{ width: 100%; }}
  .cek-panggung-st {{ min-height: 630px; }}
  .cek-kt-skor-st {{ width: 280px; right: 0; transform: rotate(2deg); }}
  .cek-kt-materi-st {{ width: 300px; top: 262px; transform: rotate(-2deg); }}
  .cek-kt-lencana-st {{ display: none; }}
  .cek-maskot-st {{ width: 110px; height: 110px; left: -6px; bottom: 0; }}
  .cek-gelembung-st {{ left: 100px; bottom: 40px; max-width: 12rem; }}
  .cek-ket-contoh-st {{ left: 0; right: 0; bottom: -34px; text-align: center; }}
  .cek-susun-st {{ font-size: {T.UKURAN_JUDUL_STITCH}; }}
  .cek-isi-f-st {{ padding-left: {T.SP_4}; }}
  .cek-demo-w-st {{ padding: 18px; }}
  .cek-solusi-st {{ padding: {T.SP_5} 20px; }}
}}
@media (prefers-reduced-motion: no-preference) {{
  html:has(.cek-halaman-st) {{ scroll-behavior: smooth; }}
  .cek-kt-st {{ transition: transform .35s; }}
  .cek-hero-st .landing-cta-baris-st a.tombol-coral {{ transition: transform .15s, box-shadow .15s; }}
  .cek-hero-st .landing-cta-baris-st a.tombol-coral:hover {{ transform: translateY(-2px); box-shadow: 0 7px 0 {T.AKSEN_KORAL_TEPI}; }}
  .cek-hero-st .landing-cta-baris-st a.tombol-coral:active {{ transform: translateY(3px); box-shadow: 0 2px 0 {T.AKSEN_KORAL_TEPI}; }}
  .cek-langkah-d-st li {{ transition: border-color .15s, transform .15s; }}
  .cek-langkah-d-st li:has(button):hover {{ transform: translateY(-2px); }}
  .cek-langkah-d-st button.cek-keliru-st {{ animation: cek-geleng-st .35s; }}
  .cek-tanda-st {{ transition: transform .15s; }}
}}
@keyframes cek-geleng-st {{ 25% {{ transform: translateX(-5px); }} 75% {{ transform: translateX(5px); }} }}
"""
