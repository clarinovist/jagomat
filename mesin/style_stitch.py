"""Style Stitch — CSS bersama untuk adopsi desain Stitch (16 halaman).

Semua 16 halaman kini diadopsi ke Stitch (S1-S17 selesai 1 Sep 2026).
CSS guru bersama (teacher_style.GAYA_GURU) tetap dipakai markup dan
bingkai halaman aktif lewat _halaman(stitch=True). Renderer murid lama
beserta stylesheet khususnya sudah dihapus; murid memakai GAYA_STITCH.

Kelas dipisah dengan suffix "-st" agar tidak tabrakan dengan CSS lama yang
masih bertugas.
"""

import design_tokens as T
from presentation_style import GAYA_PENYAJIAN

GAYA_STITCH = f"""
/* ── Font CDN (diizinkan 2026-09-01) — satu baris utuh; @import multi-baris
   memutus URL dan membuat font gagal dimuat tanpa jejak di konsol. ── */
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

{GAYA_PENYAJIAN}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body.st {{
  font-family: {T.FONT_BODY};
  font-size: {T.UKURAN_BADAN_LAYAR};
  line-height: {T.LINE_HEIGHT};
  color: {T.TEKS_UTAMA};
  margin: 0;
  background: {T.LATAR_MURID};
}}

.material-symbols-outlined {{
  font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
  font-family: 'Material Symbols Outlined', sans-serif;
  font-style: normal; font-weight: normal;
  display: inline-block; line-height: 1; letter-spacing: normal;
  text-transform: none; white-space: nowrap; word-wrap: normal;
  direction: ltr; -webkit-font-smoothing: antialiased;
}}
.material-symbols-outlined.fill {{
  font-variation-settings: 'FILL' 1, 'wght' 400, 'GRAD' 0, 'opsz' 24;
}}

h1.st, h2.st, h3.st, .st-headline {{
  font-family: {T.FONT_HEADLINE};
  color: {T.TEKS_JUDUL};
}}
h1.st {{ font-size: 1.75rem; margin: 0.4rem 0; font-weight: 800; letter-spacing: -0.02em; }}
h2.st {{ font-size: 1.25rem; margin: 1rem 0 0.6rem; font-weight: 700; }}
h3.st {{ font-size: 1.05rem; margin: 0.4rem 0; font-weight: 700; }}

/* Topbar */
.st-topbar {{
  background: {T.LATAR_SEKUNDER_LEMBUT};
  border-bottom: 1px solid {T.BORDER_VARIAN};
  height: {T.TARGET_SENTUH};
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 {T.SP_4};
  width: 100%; max-width: {T.LEBAR_KONTEN};
  margin: 0 auto;
  position: sticky; top: 0; z-index: 50;
  font-family: {T.FONT_HEADLINE};
}}
.st-topbar .brand {{ display: flex; align-items: center; gap: {T.SP_2}; font-weight: 800; }}
.st-topbar .brand .owl {{
  color: {T.WARNA_WORDMARK}; font-size: {T.LOGO_TOPBAR};
  display: inline-flex; align-items: center;
}}
/* Lambang brand: satu ukuran dari token, bukan angka lepas per stylesheet. */
.st-topbar .brand img {{ width: {T.LOGO_TOPBAR}; height: {T.LOGO_TOPBAR}; flex: none; }}
.st-topbar .brand .nama {{ color: {T.WARNA_WORDMARK}; font-size: 1.1rem; }}
.st-topbar .cta {{
  font: inherit; color: {T.AKSEN_MURID_KORAL};
  background: none; border: 0;
  padding: {T.SP_2} {T.SP_4}; font-weight: 700;
  min-height: {T.TARGET_SENTUH};
}}
.st-topbar .cta:hover {{ opacity: .9; }}

/* Kartu utama */
.st-kartu {{
  background: {T.LATAR_KARTU};
  border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU_BESAR};
  padding: {T.SP_4};
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}}
.st-kartu:hover {{
  border-color: {T.FOKUS_AKSEN};
  box-shadow: 0 2px 8px rgba(0,106,106,0.12);
}}

/* Banner sukses */
.st-banner-sukses {{
  background: {T.LATAR_TERSIMPAN};
  border: 1px solid {T.BORDER_TERSIMPAN};
  color: {T.TEKS_TERSIMPAN};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_3} {T.SP_4};
  display: flex; gap: {T.SP_3}; align-items: center;
  margin: 0 0 {T.SP_4};
}}
.st-banner-sukses .ikon {{
  background: {T.BORDER_TERSIMPAN};
  color: {T.TEKS_TERSIMPAN};
  border-radius: 50%; width: 24px; height: 24px;
  display: inline-flex; align-items: center; justify-content: center;
  font-weight: bold;
}}
/* Maskot di banner perayaan. Screenshot 430px menemukan DUA cacat: pada 48px
   ayamnya sesak, DAN kalimatnya terpotong ("...sudah masuk" tanpa titik)
   karena maskot memakan lebar yang dibutuhkan teks.

   flex-wrap saja TIDAK cukup — span teks tetap dipaksa muat satu baris.
   Yang menyelesaikan: beri span teks flex-basis 100% supaya ia turun ke
   baris sendiri begitu ruangnya kurang, dengan maskot + centang di atasnya. */
.st-banner-sukses {{
  flex-wrap: wrap;
}}
.st-banner-sukses .maskot-banner {{
  flex: none; width: 36px; height: auto;
}}
.st-banner-sukses > span:last-child {{
  flex: 1 1 12rem; min-width: 0; overflow-wrap: anywhere;
}}
/* Maskot di badge sapaan. Ditemukan lewat screenshot: maskot 96px di dalam
   badge 4,5rem (72px) TERPOTONG lingkaran. Dibatasi 82% diameter badge
   supaya ayamnya utuh dengan sedikit ruang napas — bukan di-crop. */
.maskot-sapaan {{
  width: 82%; height: auto; max-width: none;
}}

/* Badge status mode */
.st-badge {{
  display: inline-flex; align-items: center; gap: {T.SP_1};
  border-radius: {T.RADIUS_PIL};
  padding: {T.SP_1} {T.SP_3};
  font-family: {T.FONT_HEADLINE};
  font-weight: 600; font-size: .78rem; letter-spacing: .01em;
}}
.st-badge.diagnostik {{ background: {T.STATUS_DIAGNOSTIK_BG}; color: {T.STATUS_DIAGNOSTIK_TEKS}; }}
.st-badge.latihan    {{ background: {T.STATUS_LATIHAN_BG};    color: {T.STATUS_LATIHAN_TEKS}; }}
.st-badge.baru       {{ background: {T.AKSEN_MURID_KORAL};    color: #fff; }}
.st-badge.selesai    {{ background: {T.LATAR_ELEVASI};        color: {T.TEKS_VARIAN}; }}
/* Status review (1 Sep, feedback orang tua): "masih direview" dan
   "selesai" tidak boleh sama tampilannya — dulunya dua-duanya kelas
   .selesai, orang tua tidak bisa membedakan. */
.st-badge.review     {{
  background: #fff0d6; color: #815600;
  /* HP sempit: badge boleh pecah dua baris — min-content-nya tidak boleh
     memaksa kartu melebihi layar (temuan screenshot 390px 1 Sep). */
  white-space: normal; text-align: left; line-height: 1.3;
  max-width: 100%; overflow-wrap: anywhere;
}}
/* Ukuran terkendali di HP: inline-flex + min-content menang atas
   "max-width:100%" (pemegangnya sendiri tak terbatas). Klem eksplisit
   dari piksel screenshot 390px. */
@media (max-width: 36rem) {{
  .st-badge.review {{
    max-width: 9.5rem;
    font-size: .72rem; padding: .2rem .5rem;  /* muat di baris meta */
  }}
}}

/* Badge peran di topbar — dipakai _topbar_stitch lewat _badge_peran lama */
.badge-peran {{
  display: inline-flex; align-items: center;
  border-radius: {T.RADIUS_PIL};
  padding: 0.15rem 0.55rem;
  font-family: {T.FONT_HEADLINE};
  font-weight: 700; font-size: .72rem; letter-spacing: .02em;
}}
.badge-peran-admin {{ background: {T.BADGE_ADMIN_BG}; color: {T.BADGE_ADMIN_TEKS}; }}
.badge-peran-guru  {{ background: {T.BADGE_GURU_BG};  color: {T.BADGE_GURU_TEKS}; }}

/* Menu pengguna CSS-only di topbar */
.topbar-navigasi {{ display: flex; align-items: center; gap: {T.SP_3}; }}
.menu-pengguna {{ position: relative; }}
.menu-pengguna summary {{
  list-style: none; cursor: pointer; min-height: {T.TARGET_SENTUH};
  display: flex; align-items: center; padding: 0 {T.SP_2};
  font-family: {T.FONT_HEADLINE}; font-weight: 600; color: {T.TEKS_JUDUL};
  border-radius: {T.RADIUS_SEDANG};
}}
.menu-pengguna summary::-webkit-details-marker {{ display: none; }}
.menu-pengguna summary:hover {{ background: {T.LATAR_SEKUNDER_NETRAL}; }}
.menu-pengguna[open] summary {{ background: {T.LATAR_SEKUNDER_NETRAL}; }}
.menu-isi {{
  position: absolute; right: 0; top: calc(100% + 6px);
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; min-width: 12rem; max-width: min(12rem, calc(100vw - 1.2rem));
  box-shadow: 0 8px 24px rgba(0,0,0,.10); padding: {T.SP_2};
  display: flex; flex-direction: column; gap: {T.SP_1}; z-index: 60;
}}
.menu-isi a, .menu-isi button {{
  display: block; width: 100%; text-align: left;
  padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_KECIL};
  color: {T.TEKS_UTAMA}; text-decoration: none; background: none; border: 0;
  font: inherit; font-size: .92rem; cursor: pointer;
  min-height: {T.TARGET_SENTUH};
}}
.menu-isi a:hover, .menu-isi button:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.menu-pisah {{ border-top: 1px solid {T.BORDER_VARIAN}; margin: {T.SP_1} 0; }}

/* ── Komponen Info "ⓘ" (Figma `Jagomat/Info`, pilot 25 Sep 2026). Aturan
   produk yang wajib tetap satu baris di layar; detail penjelasannya pindah
   ke bubble yang muncul saat hover atau fokus — tanpa JS. Di perangkat
   sentuh bubble mengandalkan emulasi hover + fokus tap (bukan atribut
   title); lebarnya dibatasi supaya tidak melewati viewport. ── */
.info {{
  position: relative;
  display: inline-flex; align-items: center; justify-content: center;
  width: {T.TARGET_INFO}; height: {T.TARGET_INFO};   /* kotak sentuh 26x26 */
  padding: 0; border: 0; background: transparent;
  color: {T.AKSEN_TEAL_TUA};
  font: 700 .75rem/1 {T.FONT_BODY};
  vertical-align: middle; cursor: pointer;
}}
.info::before {{ /* lingkaran ikon 18px */
  content: ''; position: absolute;
  width: {T.UKURAN_INFO}; height: {T.UKURAN_INFO};
  border: {T.TEBAL_GARIS} solid currentColor; border-radius: 50%;
  pointer-events: none;
}}
.info:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; border-radius: {T.RADIUS_KECIL}; }}
.info-bubble {{
  position: absolute; bottom: calc(100% + {T.SP_2}); left: 50%;
  transform: translateX(-50%);
  width: max-content; max-width: min({T.LEBAR_TOOLTIP}, calc(100vw - {T.SP_6}));
  background: {T.LATAR_TOOLTIP}; color: {T.TEKS_TOOLTIP};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_2} {T.SP_3};
  font: 400 .8125rem/1.45 {T.FONT_BODY};
  text-align: left; visibility: hidden; opacity: 0;
  z-index: 40; pointer-events: none;
}}
.info:hover .info-bubble,
.info:focus .info-bubble,
.info:focus-visible .info-bubble {{ visibility: visible; opacity: 1; }}

/* Beranda pendamping editorial — semua override dibatasi ke kanvas ini. */
.guru-beranda-st {{ padding-top: {T.SP_5}; }}
.guru-beranda-st :is(a, button, summary):focus-visible {{
  outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 4px;
}}
.guru-beranda-st .st-topbar {{
  position: relative; height: auto; min-height: {T.TARGET_SENTUH};
  background: transparent; padding: 0 0 {T.SP_4}; gap: {T.SP_3};
}}
.guru-beranda-st .brand {{ text-decoration: none; }}
.guru-beranda-st .brand .nama {{ color: {T.AKSEN_TEAL_TUA}; font-size: 1.5rem; letter-spacing: -.04em; }}
.guru-beranda-st .topbar-navigasi {{ gap: {T.SP_2}; min-width: 0; }}
.guru-beranda-st .menu-pengguna {{ min-width: 0; }}
.guru-beranda-st .menu-pengguna summary {{
  font-size: .82rem; overflow-wrap: anywhere; gap: {T.SP_2};
}}
.guru-beranda-st .menu-pengguna summary::after {{ content: '⌄'; flex: none; }}
.guru-beranda-st .badge-peran-guru {{ background: transparent; color: {T.TEKS_VARIAN}; font-weight: 500; }}
.guru-sapaan-st {{ display: grid; grid-template-columns: minmax(0, 1fr) 13rem; gap: {T.SP_5}; align-items: center; padding: 3rem 0; }}
.guru-alis-st {{ color: {T.AKSEN_TEAL_TUA}; font: 700 .7rem/1.5 {T.FONT_HEADLINE}; letter-spacing: .1em; margin: 0 0 {T.SP_3}; }}
.guru-sapaan-st h1 {{ color: {T.TEKS_JUDUL}; font: 800 2.7rem/1.17 {T.FONT_HEADLINE}; letter-spacing: -.045em; margin: 0 0 {T.SP_4}; }}
.guru-sapaan-st h1 span {{ color: {T.AKSEN_TEAL_TUA}; }}
.guru-sapaan-st p:not(.guru-alis-st) {{ color: {T.TEKS_VARIAN}; font-size: .9rem; line-height: 1.8; margin: 0; }}
.guru-catatan-st {{
  position: relative; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU};
  background-color: {T.LATAR_KARTU}; transform: rotate(4deg); padding: {T.SP_3}; text-align: center;
  background-image: linear-gradient(color-mix(in srgb, {T.AKSEN_TEAL_TUA} 7%, transparent) 1px, transparent 1px);
  background-size: 100% 1.5rem;
}}
.guru-catatan-st img {{ display: block; width: 100%; height: auto; }}
.guru-catatan-st > span:last-child {{ display: block; font-size: .66rem; color: {T.TEKS_VARIAN}; }}
.guru-coret-st {{ position: absolute; right: {T.SP_2}; top: -.7rem; font-size: 2.5rem; color: {T.AKSEN_KORAL_TUA}; }}
.guru-kepala-daftar-st {{ display: flex; gap: {T.SP_4}; align-items: center; justify-content: space-between; flex-wrap: wrap; }}
.guru-kepala-daftar-st .guru-alis-st {{ margin-bottom: {T.SP_1}; }}
.guru-kepala-daftar-st h2 {{ color: {T.TEKS_JUDUL}; font: 800 1.45rem/1.4 {T.FONT_HEADLINE}; margin: 0; }}
.guru-kepala-daftar-st h2 span {{ font-size: .85rem; font-weight: 500; color: {T.TEKS_VARIAN}; margin-left: {T.SP_2}; }}
.guru-tambah-st {{ display: inline-flex; align-items: center; justify-content: center; gap: {T.SP_2}; min-height: {T.TINGGI_KONTROL}; padding: {T.SP_2} {T.SP_4}; color: {T.TEKS_PUTIH}; background: {T.AKSEN_KORAL_TUA}; border-radius: {T.RADIUS_KECIL}; text-decoration: none; font: 700 .8rem/1.5 {T.FONT_HEADLINE}; }}
.guru-tambah-st:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.guru-petunjuk-st {{ color: {T.TEKS_VARIAN}; font-size: .8rem; line-height: 1.7; margin: {T.SP_3} 0 {T.SP_5}; }}
.guru-beranda-st .daftar-anak {{ display: grid; gap: {T.SP_3}; }}
.guru-beranda-st .kartu-anak {{ display: grid; grid-template-columns: 3rem minmax(0, 1fr) auto; align-items: center; gap: {T.SP_4}; padding: {T.SP_5}; text-decoration: none; color: inherit; box-shadow: none; }}
.guru-beranda-st .kartu-anak:hover {{ border-color: {T.AKSEN_TEAL_TUA}; background: color-mix(in srgb, {T.LATAR_KARTU} 95%, {T.AKSEN_TEAL_TUA}); }}
.guru-inisial-st {{ display: grid; place-items: center; width: 3rem; height: 3.5rem; background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.AKSEN_TEAL_TUA}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL}; font: 700 1.5rem/1 {T.FONT_HEADLINE}; }}
.guru-identitas-st {{ min-width: 0; }}
.guru-nama-st {{ font: 800 1.12rem/1.4 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; margin: 0 0 {T.SP_1}; overflow-wrap: anywhere; }}
.guru-meta-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; color: {T.TEKS_VARIAN}; font-size: .75rem; overflow-wrap: anywhere; }}
.guru-meta-st > span + span::before {{ content: '·'; margin-right: {T.SP_2}; }}
.guru-status-daftar-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin-top: {T.SP_3}; }}
.guru-status-st {{ font-size: .72rem; color: {T.TEKS_VARIAN}; }}
.guru-status-st.periksa {{ color: {T.BADGE_ADMIN_TEKS}; background: {T.BADGE_ADMIN_BG}; padding: 0 {T.SP_2}; border-radius: {T.RADIUS_KECIL}; }}
.guru-buka-st {{ font: 700 .75rem/1.5 {T.FONT_HEADLINE}; color: {T.AKSEN_TEAL_TUA}; }}
.guru-buka-st > span {{ margin-left: {T.SP_2}; }}
.guru-kosong-st {{ border: 1px dashed {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU}; padding: {T.SP_6}; background: color-mix(in srgb, {T.LATAR_KARTU} 65%, transparent); }}
.guru-kosong-st h2 {{ font: 800 1.8rem/1.3 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; max-width: 20rem; margin: 0 0 {T.SP_4}; }}
.guru-kosong-st > p:not(.guru-alis-st) {{ color: {T.TEKS_VARIAN}; font-size: .85rem; max-width: 32rem; }}
.guru-kosong-st .guru-tambah-st {{ margin-top: {T.SP_3}; }}
.guru-kosong-st .guru-petunjuk-st {{ margin-bottom: 0; }}
.guru-kaki-st {{ display: flex; gap: {T.SP_2}; align-items: center; color: {T.TEKS_VARIAN}; font-size: .75rem; border-top: 1px solid {T.BORDER_VARIAN}; margin-top: {T.SP_6}; padding-top: {T.SP_5}; }}
.guru-kaki-st > span {{ color: {T.AKSEN_KORAL_TUA}; font-size: 1.5rem; }}
@media (max-width: 36rem) {{
  .guru-beranda-st .st-topbar {{ flex-wrap: wrap; }}
  .guru-beranda-st .topbar-navigasi {{ flex-wrap: wrap; justify-content: flex-end; margin-left: auto; }}
  .guru-beranda-st .badge-peran-guru {{ font-size: .65rem; padding: 0; }}
  .guru-sapaan-st {{ grid-template-columns: minmax(0, 1fr); padding: {T.SP_6} 0; }}
  .guru-sapaan-st h1 {{ font-size: 2.3rem; }}
  .guru-catatan-st {{ display: none; }}
  .guru-beranda-st .kartu-anak {{ grid-template-columns: 2.4rem minmax(0, 1fr); padding: {T.SP_4}; gap: {T.SP_3}; }}
  .guru-inisial-st {{ width: 2.4rem; height: 3rem; font-size: 1.2rem; align-self: start; }}
  .guru-buka-st {{ grid-column: 2; }}
  .guru-kosong-st {{ padding: {T.SP_5}; }}
}}
/* Akhir beranda pendamping */

/* Input + tombol */
.st-input {{
  font: inherit; font-size: 1rem;
  min-height: {T.TINGGI_KONTROL};
  border-radius: {T.RADIUS_SEDANG};
  border: 1px solid {T.BORDER_VARIAN};
  background: {T.LATAR_KARTU};
  padding: 0 {T.SP_3};
  width: 100%;
}}
.st-input:focus {{
  border-color: {T.FOKUS_AKSEN}; outline: 0;
  box-shadow: 0 0 0 3px {T.AKSEN_MURID_UTAMA}55; /* ring teal lembut */
}}
.st-tombol-coral {{
  font: inherit;
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  border: 0; border-radius: {T.RADIUS_SEDANG};
  min-height: {T.TINGGI_KONTROL};
  padding: 0 {T.SP_5};
  font-weight: 700; cursor: pointer;
}}
.st-tombol-coral:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}

/* Baris kartu (dipakai daftar sesi guru & murid di Stitch) */
.st-kartu-baris {{
  display: flex; align-items: center; gap: {T.SP_4};
  background: {T.LATAR_KARTU};
  border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_3} {T.SP_4};
}}
/* Juga badge-keluarga untuk data — admin melihat siapa pemilik keluarga */
.badge-keluarga {{
  font-size: .7rem; font-weight:700;
  background: {T.BADGE_ADMIN_BG};
  color: {T.BADGE_ADMIN_TEKS};
  padding: .15rem .5rem; border-radius: {T.RADIUS_PIL}; margin-left: .25rem;
}}

/* Baris jadwal sesi (pasangan kekeluargaan untuk grid kel) */
.st-kartu-baris {{
  display: flex; align-items: center; gap: {T.SP_4};
  flex-wrap: wrap; /* 1 Sep: badge panjang mesti bisa pindah baris di HP */
  background: {T.LATAR_KARTU};
  border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_3} {T.SP_4};
  /* 1 Sep: tanpa guard ini, kartu melebar mengikuti min-content anak
     (badge panjang) → halaman menyamping di HP. max-width memaksa kartu
     tetap selebar konten; dengan wrap di bawah, badge pindah baris. */
  max-width: 100%;
}}
/* Pitas-vagasi 1 Sep: badge panjang ("Menunggu direview") + jumlah soal
   mengoverflow di HP 360-420px → halaman menyamping. min-width:0 pada
   anak fleksibel + wrap pada baris menjaga badge tetap di dalam layar.
   !important diperlukan: markup kartu memakai inline style="flex:none"
   yang tanpa ini menang atas media query.

   3 Sep: selector diubah dari `> span` ke `> *`. Kartu sesi GURU anaknya
   <div>, jadi aturan lama tidak pernah kena di /anak/<id> — kolom pertama
   menyusut jadi 76px dan judul sesi terlipat 3 baris. Semua anak kartu
   murid adalah <span>, jadi bagi mereka perubahan ini no-op. */
.st-kartu-baris > * {{ min-width: 0; }}
@media (max-width: 46rem) {{
  .st-kartu-baris {{ flex-wrap: wrap; }}
  .st-kartu-baris > *:nth-child(2) {{ flex: 1 1 10rem; }}
  /* pemegang badge jumlah + status boleh menyusut & pindah baris */
  .st-kartu-baris > *:nth-child(n+3) {{
    flex: 0 1 auto !important; margin-left: 0;
  }}
  /* Kartu sesi guru baru punya dua anak: isi dan aksi. Isi mengambil ruang
     utama; aksi tetap di kanan bila muat dan turun utuh bila layar sempit. */
  .kartu-sesi-guru > .isi-kartu-sesi-st {{ flex: 1 1 15rem !important; }}
  .kartu-sesi-guru > .aksi-sesi-st {{ margin-left: auto; }}
  .kepala-riwayat-st {{ align-items: flex-start; flex-direction: column; gap: 0; }}
  .tautan-laporan-st {{ margin-top: {T.SP_1}; }}
  .st-kartu-baris:not(.kartu-sesi-guru) > *:first-child {{ flex: none; }}
}}

/* 3 Sep: .daftar-anak sebelumnya HANYA ada di GAYA_GURU, yang tidak dimuat
   _halaman_stitch → grid+gap hilang dan kartu sesi dempet (terukur 1px).
   Versi di teacher_style.py dibiarkan: halaman non-stitch masih memakainya. */
.daftar-anak {{ display: grid; gap: {T.SP_3}; }}

/* ── Kartu sesi murid (3 Sep, feedback layout) ──
   Tiga masalah terukur di headless Chrome, akarnya satu markup:

   1. Badge "{{n}} soal" dulu ditulis DI DALAM kolom teks. Kolom itu
      flex-direction:column, jadi badge kena stretch: 271px di HP dan 617px
      di 1440px untuk konten yang lebar aslinya +-67px — terbaca orang tua
      sebagai "blok abu memanjang sampai habis" seolah progress bar.
   2. Kolom teks tak punya gap (computed `normal` = 0px) → tanggal, meta,
      dan badge dempet: "kayak agak bertumpuk".
   3. Karena (1), kartu hanya punya 2 anak flex sehingga aturan HP
      `.st-kartu-baris > *:nth-child(n+3)` di atas tidak pernah kena. */
.st-kartu-teks {{
  flex: 1; display: flex; flex-direction: column;
  gap: {T.SP_1};              /* akar keluhan "bertumpuk" */
  min-width: 0;
}}
/* Pill statis: lebar mengikuti isi, TIDAK memanjang. flex:none menahan
   shrink; align-self mencegah stretch kalau kartu jatuh ke mode wrap. */
.st-jumlah-soal {{
  flex: none; align-self: center; margin-left: auto;
  white-space: nowrap; font-size: 0.8rem;
}}
/* Bar progres hanya dipakai sesi yang SEDANG dikerjakan — saat pecahannya
   informatif. Sesi baru (0%) dan selesai (100%) tetap pill statis. */
.st-progres-soal {{
  flex: none; align-self: center; margin-left: auto;
  display: flex; flex-direction: column; gap: 0.2rem;
  width: 6.5rem;
}}
.st-progres-jalur {{
  display: block;
  height: 0.4rem; border-radius: {T.RADIUS_PIL};
  background: {T.LATAR_ELEVASI}; overflow: hidden;
}}
/* display:block WAJIB: penanda ini <span>, dan span inline mengabaikan
   width/height sepenuhnya — terukur 3 Sep, bar tampil kosong (0px) padahal
   style="width:30%" terpasang. Test HTML tidak menangkapnya; hanya render
   yang menangkap (CLAUDE.md §10). */
.st-progres-isi {{
  display: block;
  height: 100%; border-radius: {T.RADIUS_PIL};
  background: {T.AKSEN_MURID_UTAMA};
}}
.st-progres-label {{
  font-size: 0.7rem; color: {T.TEKS_VARIAN}; white-space: nowrap;
}}
@media (max-width: 46rem) {{
  /* Aturan HP `.st-kartu-baris > *:nth-child(n+3)` di atas memberi penanda
     `flex: 0 1 auto` + `margin-left: 0`, sehingga bar jatuh ke baris kedua
     dan menempel KIRI (terukur x=31, kartu memanjang 143→159px). Kembalikan
     dorongan ke kanan supaya bar tetap sebaris dengan kolom teks. */
  .st-jumlah-soal, .st-progres-soal {{ margin-left: auto !important; }}
  .st-progres-soal {{ width: 5.5rem; }}
}}

/* ── Beranda murid — buku belajar pribadi ── */
.murid-beranda-st {{
  --murid-teal-lembut: color-mix(in srgb, {T.AKSEN_MURID_UTAMA} 6%, {T.LATAR_KARTU});
  --murid-amber-lembut: color-mix(in srgb, {T.AKSEN_MURID_AMBER} 24%, {T.LATAR_KARTU});
}}
.murid-beranda-st :is(a, button, summary):focus-visible {{
  outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 5px;
}}
.murid-lewati-st {{ position: absolute; left: {T.SP_4}; top: -8rem; padding: {T.SP_3}; background: {T.LATAR_KARTU}; z-index: 100; }}
.murid-lewati-st:focus {{ top: {T.SP_3}; }}
.murid-kepala-st {{ border-bottom: 1px solid {T.BORDER_CATATAN}; }}
.murid-kepala-st > div {{ max-width: 70rem; margin: auto; padding: 0 2.5rem; min-height: 5.5rem; display: flex; justify-content: space-between; align-items: center; gap: {T.SP_4}; }}
.murid-brand-st {{ display: flex; gap: {T.SP_2}; align-items: center; font: 800 1.7rem/1 {T.FONT_HEADLINE}; color: {T.AKSEN_TEAL_TUA}; letter-spacing: -.04em; }}
.murid-kepala-st form {{ margin: 0; }}
.murid-kepala-st button {{ font: 600 .85rem {T.FONT_HEADLINE}; color: {T.TEKS_VARIAN}; background: none; border: 0; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; cursor: pointer; }}
.murid-kepala-st button:hover {{ color: {T.AKSEN_KORAL_TUA}; }}
.murid-kanvas-st {{ max-width: 70rem; margin: auto; padding: 2.5rem 2.5rem 0; }}
.murid-sapaan-st {{ margin-bottom: 1.9rem; }}
.murid-alis-st {{ font: 700 .75rem/1.5 {T.FONT_HEADLINE}; letter-spacing: .09em; color: {T.AKSEN_TEAL_TUA}; margin: 0 0 {T.SP_2}; }}
.murid-sapaan-st h1 {{ font: 800 2.4rem/1.25 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; letter-spacing: -.04em; margin: 0 0 {T.SP_2}; overflow-wrap: anywhere; }}
.murid-sapaan-st > p:not(.murid-alis-st) {{ font-size: .95rem; margin: 0; }}
.murid-akun-hint-st {{ display: block; margin-top: {T.SP_1}; font-size: .75rem; color: {T.TEKS_SUBTLE}; }}
.murid-grid-st {{ display: grid; grid-template-columns: minmax(0, 1fr) 20rem; gap: 1.75rem; align-items: start; }}
.murid-grid-st.satu-kolom {{ grid-template-columns: minmax(0, 1fr); max-width: 46rem; }}
.murid-kolom-utama-st, .murid-pendamping-st {{ min-width: 0; }}
.murid-pendamping-st {{ display: grid; gap: {T.SP_5}; }}
.murid-ikon-st {{ display: block; width: 1.35rem; height: 1.35rem; flex: none; }}
.murid-beranda-st .st-kartu-baris {{
  display: grid; grid-template-columns: 2.8rem minmax(0, 1fr) auto; gap: {T.SP_3};
  align-items: center; padding: {T.SP_4}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU}; color: {T.TEKS_VARIAN}; background: {T.LATAR_KARTU};
  text-decoration: none; margin: {T.SP_3} 0 0;
}}
.murid-beranda-st a.st-kartu-baris:hover {{ border-color: {T.AKSEN_TEAL_TUA}; }}
.murid-beranda-st .st-kartu-baris > * {{ min-width: 0; }}
.murid-beranda-st .st-kartu-teks {{ gap: {T.SP_1}; }}
.murid-ikon-topik-st {{ width: 2.8rem; height: 2.8rem; border-radius: {T.RADIUS_KARTU}; display: grid; place-items: center; color: {T.AKSEN_TEAL_TUA}; background: var(--murid-teal-lembut); }}
.murid-judul-kartu-st {{ font: 800 1.05rem/1.4 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; overflow-wrap: anywhere; }}
.murid-tahap-st {{ font: 600 .8rem/1.5 {T.FONT_HEADLINE}; color: {T.TEKS_VARIAN}; overflow-wrap: anywhere; }}
.murid-meta-st {{ font-size: .75rem; color: {T.TEKS_SUBTLE}; overflow-wrap: anywhere; }}
.murid-beranda-st .st-badge {{ align-self: flex-start; padding: 0; font-size: .75rem; border-radius: 0; font-weight: 500; background: transparent; line-height: 1.5; }}
.murid-beranda-st .st-badge.baru {{ color: {T.AKSEN_KORAL_TUA}; }}
.murid-beranda-st .st-badge.selesai {{ color: {T.TEKS_SUBTLE}; }}
.murid-beranda-st .st-badge.review {{ color: {T.BADGE_ADMIN_TEKS}; max-width: none; }}
.murid-beranda-st .st-badge.diagnostik {{ color: {T.AKSEN_TEAL_TUA}; }}
.murid-ujung-st {{ display: flex; flex-direction: column; align-items: flex-end; gap: {T.SP_2}; width: auto; max-width: 8rem; }}
.murid-beranda-st .st-progres-soal, .murid-beranda-st .st-jumlah-soal {{ white-space: normal; margin-left: 0 !important; }}
.murid-jumlah-st {{ font-size: .75rem; color: {T.TEKS_SUBTLE}; }}
.murid-beranda-st .st-progres-label {{ font-size: .75rem; white-space: normal; }}
.murid-beranda-st .st-progres-jalur {{ width: 100%; min-width: 4rem; height: .45rem; }}
.murid-beranda-st .st-progres-isi {{ background: {T.AKSEN_TEAL_TUA}; }}
.murid-aksi-st {{ display: inline-flex; gap: {T.SP_1}; align-items: center; color: {T.AKSEN_TEAL_TUA}; font: 700 .8rem/1.4 {T.FONT_HEADLINE}; }}
.murid-aksi-st .murid-ikon-st {{ width: 1rem; height: 1rem; }}

/* Satu tautan: tombol hanya penanda visual dari kartu yang menaut. */
.murid-beranda-st .st-kartu-baris[data-utama] {{
  position: relative; isolation: isolate; grid-template-columns: minmax(0, 1fr);
  gap: 0; padding: 0; margin: 0; border: 1px solid {T.AKSEN_TEAL_TUA}; border-radius: 1.4rem;
  background: var(--murid-teal-lembut); overflow: hidden;
  box-shadow: 0 5px 0 color-mix(in srgb, {T.AKSEN_TEAL_TUA} 7%, transparent);
}}
.murid-beranda-st [data-utama] > .st-kartu-teks {{
  grid-column: 1; grid-row: 1; display: block; min-height: 18rem; padding: {T.SP_5} 2rem;
  padding-right: 43%; background-image: linear-gradient(color-mix(in srgb, {T.AKSEN_TEAL_TUA} 4%, transparent) 1px, transparent 1px), linear-gradient(90deg, color-mix(in srgb, {T.AKSEN_TEAL_TUA} 4%, transparent) 1px, transparent 1px); background-size: 1.5rem 1.5rem;
}}
.murid-label-utama-st {{ display: block; color: {T.AKSEN_TEAL_TUA}; font: 700 .8rem/1.5 {T.FONT_HEADLINE}; }}
.murid-beranda-st [data-utama] .murid-tahap-st {{ display: block; margin: 1.5rem 0 {T.SP_2}; color: {T.AKSEN_TEAL_TUA}; }}
.murid-judul-sampul-st {{ display: block; font: 800 2.65rem/1.12 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; letter-spacing: -.04em; overflow-wrap: anywhere; }}
.murid-sub-sampul-st {{ display: block; font-size: .8rem; margin-top: {T.SP_3}; }}
.murid-beranda-st [data-utama] .murid-meta-st {{ display: block; margin-top: {T.SP_2}; }}
.murid-ilustrasi-st {{ position: absolute; z-index: -1; right: 1rem; top: 3.5rem; width: 12rem; height: 14rem; }}
.murid-ilustrasi-st img {{ position: absolute; width: 100%; bottom: 1rem; right: 0; display: block; }}
.murid-lingkaran-st {{ position: absolute; right: .3rem; bottom: 1.7rem; width: 10rem; height: 10rem; border-radius: 50%; background: var(--murid-amber-lembut); }}
.murid-beranda-st [data-utama] > .murid-lanjut-bawah-st {{
  grid-column: 1; grid-row: 2; display: flex; flex-direction: column; align-items: stretch;
  width: 100%; max-width: none; gap: {T.SP_3}; padding: {T.SP_5} 2rem;
  background: {T.LATAR_KARTU}; border-top: 1px solid {T.BORDER_VARIAN};
}}
.murid-beranda-st [data-utama] .st-progres-label {{ font-size: .9rem; }}
.murid-tombol-utama-st {{ display: flex; align-items: center; justify-content: space-between; gap: {T.SP_4}; min-height: {T.TINGGI_CTA}; padding: {T.SP_3} {T.SP_5}; border-radius: {T.RADIUS_KARTU}; background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; font: 700 1rem/1.4 {T.FONT_HEADLINE}; margin-top: {T.SP_2}; }}
.murid-beranda-st [data-utama]:hover .murid-tombol-utama-st {{ background: {T.AKSEN_KORAL_HOVER}; }}
.murid-aman-st {{ text-align: center; font-size: .75rem; color: {T.TEKS_SUBTLE}; }}
.murid-latihan-lain-st {{ margin-top: {T.SP_6}; }}
.murid-kepala-bagian-st {{ display: flex; justify-content: space-between; gap: {T.SP_3}; align-items: center; }}
.murid-kepala-bagian-st h2 {{ font: 800 1.15rem/1.4 {T.FONT_HEADLINE}; margin: 0; color: {T.TEKS_JUDUL}; }}
.murid-kepala-bagian-st > span {{ font-size: .8rem; color: {T.TEKS_SUBTLE}; }}
.murid-menunggu-st {{ border: 1px solid {T.BORDER_CATATAN}; border-radius: 1.2rem; background: {T.LATAR_CATATAN}; padding: {T.SP_5}; }}
.murid-menunggu-st > h2 {{ display: flex; gap: {T.SP_2}; align-items: center; font: 700 .9rem/1.5 {T.FONT_HEADLINE}; color: {T.BADGE_ADMIN_TEKS}; margin: 0; }}
.murid-menunggu-st h3 {{ font: 800 1.5rem/1.25 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; margin: {T.SP_5} 0 {T.SP_3}; }}
.murid-menunggu-st > p {{ font-size: .9rem; margin: 0; }}
.murid-menunggu-st .st-kartu-baris {{ background: transparent; padding: {T.SP_4} 0 0; border: 0; border-top: 1px solid {T.BORDER_CATATAN}; border-radius: 0; grid-template-columns: 1.4rem minmax(0, 1fr); gap: {T.SP_3}; align-items: start; }}
.murid-menunggu-st .murid-ikon-topik-st {{ width: auto; height: auto; background: none; margin-top: {T.SP_1}; }}
.murid-menunggu-st .murid-ujung-st {{ grid-column: 2; align-items: flex-start; }}
.murid-riwayat-st {{ background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.murid-riwayat-st summary {{ display: flex; gap: {T.SP_3}; align-items: center; list-style: none; padding: {T.SP_4}; min-height: {T.TARGET_SENTUH}; cursor: pointer; border-radius: {T.RADIUS_KARTU_BESAR}; }}
.murid-riwayat-st summary::-webkit-details-marker {{ display: none; }}
.murid-riwayat-st summary > span {{ flex: 1; display: flex; flex-direction: column; gap: {T.SP_1}; min-width: 0; }}
.murid-riwayat-st summary b {{ font: 700 .9rem/1.4 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.murid-riwayat-st summary span span {{ font-size: .75rem; color: {T.TEKS_SUBTLE}; }}
.murid-riwayat-st summary .murid-ikon-st {{ width: 1.2rem; height: 1.2rem; color: {T.AKSEN_TEAL_TUA}; }}
.murid-riwayat-st[open] summary > svg:last-child {{ transform: rotate(90deg); }}
.murid-riwayat-isi-st {{ padding: 0 {T.SP_4} {T.SP_4}; }}
.murid-riwayat-isi-st .st-kartu-baris {{ display: flex; flex-wrap: wrap; gap: {T.SP_3}; padding: {T.SP_3} 0 0; border: 0; border-top: 1px solid {T.BORDER_HALUS}; border-radius: 0; }}
.murid-riwayat-isi-st .murid-ikon-topik-st {{ display: none; }}
.murid-riwayat-isi-st .st-kartu-teks {{ flex: 1 1 8rem; }}
.murid-riwayat-isi-st .murid-ujung-st {{ align-items: flex-start; }}
.murid-keadaan-st {{ border: 1px solid {T.BORDER_CATATAN}; border-radius: 1.4rem; padding: {T.SP_6}; background: {T.LATAR_KARTU}; }}
.murid-keadaan-st img {{ width: 9rem; height: auto; display: block; margin: 0 auto {T.SP_5}; }}
.murid-keadaan-st h2 {{ font: 800 2rem/1.25 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; margin: 0 0 {T.SP_4}; }}
.murid-keadaan-st p {{ font-size: .95rem; margin: 0; }}
.murid-kaki-st {{ display: flex; justify-content: center; align-items: center; flex-wrap: wrap; gap: {T.SP_3}; margin: {T.SP_6} {T.SP_4}; font-size: .75rem; color: {T.TEKS_SUBTLE}; }}
.murid-kaki-st > span {{ color: {T.AKSEN_KORAL_TUA}; }}
@media (max-width: 60rem) {{
  .murid-grid-st {{ grid-template-columns: minmax(0, 1fr) 17rem; gap: {T.SP_5}; }}
  .murid-ilustrasi-st {{ width: 9rem; right: .6rem; }}
  .murid-lingkaran-st {{ width: 8rem; height: 8rem; }}
  .murid-judul-sampul-st {{ font-size: 2.2rem; }}
}}
@media (max-width: 48rem) {{
  .murid-kepala-st > div {{ min-height: 4.5rem; padding: 0 1.35rem; }}
  .murid-brand-st {{ font-size: 1.5rem; }}
  .murid-kanvas-st {{ padding: 1.7rem 1.35rem 0; max-width: 36rem; }}
  .murid-sapaan-st {{ margin-bottom: {T.SP_5}; }}
  .murid-sapaan-st h1 {{ font-size: 1.95rem; }}
  .murid-sapaan-st > p:not(.murid-alis-st) {{ font-size: .9rem; }}
  .murid-grid-st {{ display: flex; flex-direction: column; gap: 1.75rem; }}
  .murid-kolom-utama-st, .murid-pendamping-st {{ width: 100%; }}
  .murid-beranda-st [data-utama] > .st-kartu-teks {{ min-height: 17rem; padding: 1.3rem; padding-right: 40%; }}
  .murid-ilustrasi-st {{ width: 8.5rem; top: 3.5rem; height: 12rem; right: .3rem; }}
  .murid-lingkaran-st {{ width: 7.5rem; height: 7.5rem; right: 0; }}
  .murid-judul-sampul-st {{ font-size: 2.15rem; }}
  .murid-beranda-st [data-utama] > .murid-lanjut-bawah-st {{ padding: 1.3rem; }}
  .murid-tombol-utama-st {{ font-size: .95rem; padding: {T.SP_3} {T.SP_4}; }}
  .murid-beranda-st .st-kartu-baris:not([data-utama]) {{ grid-template-columns: 2.2rem minmax(0, 1fr); }}
  .murid-beranda-st .st-kartu-baris:not([data-utama]) .murid-ujung-st {{ grid-column: 2; flex-direction: row; flex-wrap: wrap; align-items: center; justify-content: space-between; max-width: none; width: 100%; }}
  .murid-beranda-st .st-kartu-baris:not([data-utama]) .st-progres-label {{ width: 100%; }}
  .murid-beranda-st .st-kartu-baris:not([data-utama]) .st-progres-jalur {{ width: 55%; }}
  .murid-ikon-topik-st {{ width: 2.2rem; height: 2.5rem; }}
  .murid-menunggu-st .st-kartu-baris:not([data-utama]) {{ grid-template-columns: 1.4rem minmax(0, 1fr); }}
  .murid-menunggu-st {{ padding: 1.3rem; }}
  .murid-riwayat-isi-st .st-kartu-baris:not([data-utama]) {{ display: block; }}
  .murid-riwayat-isi-st .murid-ujung-st {{ margin-top: {T.SP_2}; }}
}}
@media (max-width: 23.5rem) {{
  .murid-kanvas-st {{ padding-left: {T.SP_4}; padding-right: {T.SP_4}; }}
  .murid-sapaan-st h1 {{ font-size: 1.75rem; }}
  .murid-beranda-st [data-utama] > .st-kartu-teks {{ padding: {T.SP_4}; padding-right: 39%; }}
  .murid-judul-sampul-st {{ font-size: 1.85rem; }}
  .murid-ilustrasi-st {{ width: 6.3rem; top: 4.2rem; right: .25rem; }}
  .murid-lingkaran-st {{ width: 6rem; height: 6rem; }}
}}

/* Sorot-baru — sisip baris yang baru dibuat */
tr.sorot-baru, div.sorot-baru {{
  background: {T.AKSEN_MURID_UTAMA}20;
  border-left: 4px solid {T.AKSEN_MURID_UTAMA};
}}

/* Meta info: tanggal, waktu */
.st-meta {{ color: {T.TEKS_SUBTLE}; font-size: .9rem; }}

/* Kanvas konten Stitch — _halaman_stitch dan seterusnya tidak lagi bergantung
   pada .bungkus milik teacher_style lama */
.bungkus-st {{ max-width: {T.LEBAR_KONTEN}; margin: 0 auto; padding: {T.SP_4} 0.9rem 3rem; }}

/* 3 Sep: blok lama ".strip-sesi / .mode-pilih / .mode-opsi" (versi strip satu
   baris) DIHAPUS dari sini — sisa refactor S6 yang tidak ikut dibersihkan.
   Bahayanya bukan sekadar duplikasi: ia membawa `align-items: flex-end`, dan
   blok S6 di bawah yang mengubah arah jadi kolom tidak me-reset properti itu,
   sehingga tiap anak yang tidak selebar penuh menempel ke tepi KANAN.
   Versi yang menang ada di bagian "Form buat sesi (S6)". */

/* ── Halaman /anak/<id> (5 Sep): struktur & hierarki riwayat ── */
.kepala-anak-st {{ margin-bottom: {T.SP_4}; }}
.kepala-anak-st h1.st {{ margin-bottom: 0; }}
.kepala-riwayat-st {{
  display: flex; align-items: center; justify-content: space-between;
  gap: {T.SP_3}; margin-bottom: {T.SP_3};
}}
.kepala-riwayat-st h2.st {{ margin: 0; font-size: 1.2rem; }}
.tautan-laporan-st {{
  display: inline-flex; align-items: center; gap: {T.SP_1};
  color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE};
  font-size: .86rem; font-weight: 700; text-decoration: none;
  min-height: {T.TARGET_SENTUH};
}}
.tautan-laporan-st:hover {{ text-decoration: underline; }}
.tautan-laporan-st .ikon-laporan-st {{
  width: 1.1rem; height: 1.1rem; flex: none;
}}

.kartu-sesi-guru {{
  align-items: flex-start; padding: {T.SP_4};
}}
.isi-kartu-sesi-st {{
  flex: 1; min-width: 0; display: flex; flex-direction: column;
  gap: {T.SP_1};
}}
.judul-sesi-st {{
  color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE};
  font-size: 1rem; font-weight: 800; line-height: 1.3;
  text-decoration: none;
}}
.judul-sesi-st:hover {{ color: {T.AKSEN_TEAL_TUA}; text-decoration: underline; }}
.rincian-topik-st {{
  color: {T.TEKS_UTAMA}; font-size: .9rem; line-height: 1.45;
  overflow-wrap: anywhere;
}}
.meta-sesi-st {{
  display: flex; flex-wrap: wrap; align-items: center; gap: 0 {T.SP_2};
  color: {T.TEKS_SUBTLE}; font-size: .8rem; line-height: 1.5;
}}
.meta-sesi-st time {{ white-space: nowrap; }}
.nomor-sesi-st {{ color: {T.TEKS_VARIAN}; }}
.ringkasan-sesi-st {{
  margin-top: {T.SP_1}; color: {T.TEKS_JUDUL}; font-size: .9rem;
  font-weight: 700; font-variant-numeric: tabular-nums;
}}
.aksi-sesi-st {{
  flex: none; display: flex; flex-direction: column;
  gap: {T.SP_2}; align-items: flex-end;
}}
.blok-bagikan-st {{
  display: flex; flex-direction: column; align-items: flex-end; gap: {T.SP_1};
}}
.kabar-bagikan-st {{
  color: {T.TEKS_SUBTLE}; font-size: .75rem; line-height: 1.35;
  max-width: 15rem; text-align: right;
}}
.kabar-bagikan-st:empty {{ display: none; }}
.kabar-bagikan-st:not(:empty) {{
  padding: {T.SP_1} {T.SP_2}; background: {T.LATAR_SEKUNDER_LEMBUT};
  border-radius: {T.RADIUS_KECIL};
}}

/* Mobile-first: bawaannya SATU kolom, jadi di HP tampilannya sama persis
   seperti sebelum blok ini ada. Grid dan pelebar kanvas baru hidup di
   >= 64rem, tempat halaman lama menyisakan ~350px kosong di kiri-kanan
   sambil memanjang 1698px ke bawah. */
.anak-grid {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}
.anak-kolom-kanan {{ display: flex; flex-direction: column; gap: {T.SP_4}; }}

@media (min-width: 64rem) {{
  .bungkus-st.lebar {{ max-width: 72rem; }}
  .bungkus-st.lebar > .st-topbar {{ max-width: none; }}
  .anak-grid {{
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
    gap: {T.SP_5};
    align-items: start;
  }}
  /* Strip pertama di kolom kanan sudah punya jarak dari grid gap. */
  .anak-kolom-kanan > .strip-sesi:first-child {{ margin-top: 0; }}
}}
/* Fase 4: marker kolom lama tetap di DOM untuk kompatibilitas, tetapi satu
   alur vertikal mencegah kolom kosong dan menempatkan manual sebelum riwayat. */
.anak-grid[data-rencana="vertikal"] {{
  display: flex; flex-direction: column; gap: {T.SP_4};
  align-items: stretch; width: 100%;
}}
.anak-grid[data-rencana="vertikal"] > .anak-kolom-kanan {{ order: 1; }}
.anak-grid[data-rencana="vertikal"] > .anak-kolom-kiri {{ order: 2; }}


/* ── Kartu rencana belajar guru (Fase 4) ── */
.kartu-rencana-st {{
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN};
  border-left: 4px solid {T.AKSEN_MURID_UTAMA};
  border-radius: {T.RADIUS_KARTU_BESAR}; padding: {T.SP_5};
  margin: 0 0 {T.SP_5}; display: flex; flex-direction: column; gap: {T.SP_3};
}}
.kartu-rencana-st h2.st {{ margin: 0; }}
.label-rencana-st {{
  margin: 0; color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE};
  font-size: .8rem; font-weight: 800; letter-spacing: .04em; text-transform: uppercase;
}}
.alasan-rencana-st, .progres-rencana-st, .tanggal-rencana-st {{ margin: 0; }}
.alasan-rencana-st {{ color: {T.TEKS_VARIAN}; }}
.progres-rencana-st {{
  color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; font-weight: 700;
}}
.strip-rencana-st {{
  list-style: none; display: grid; grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: {T.SP_1}; padding: 0; margin: {T.SP_1} 0;
}}
.tahap-rencana-st {{
  min-width: 0; padding: {T.SP_2} {T.SP_1}; text-align: center;
  border-radius: {T.RADIUS_KECIL}; background: {T.LATAR_SEKUNDER_NETRAL};
  color: {T.TEKS_VARIAN}; font-family: {T.FONT_HEADLINE}; font-size: .72rem;
  font-weight: 600; overflow-wrap: anywhere;
}}
.tahap-rencana-st.selesai {{ background: {T.LATAR_TERSIMPAN}; color: {T.TEKS_TERSIMPAN}; }}
.tahap-rencana-st.aktif {{ background: {T.AKSEN_MURID_UTAMA}; color: {T.TEKS_PUTIH}; }}
.tindakan-rencana-st {{
  background: {T.LATAR_SEKUNDER_LEMBUT}; border-radius: {T.RADIUS_SEDANG};
  padding: {T.SP_3} {T.SP_4};
}}
.tindakan-rencana-st b {{ font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.tindakan-rencana-st p {{ margin: {T.SP_1} 0 0; }}
.contoh-rencana-st {{
  border-left: 3px solid {T.AKSEN_MURID_AMBER}; padding: {T.SP_2} {T.SP_3};
  color: {T.TEKS_UTAMA};
}}
.contoh-rencana-st b {{ font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.contoh-rencana-st p {{ margin: {T.SP_1} 0 0; }}
.rencana-peringatan-st {{
  margin: 0; padding: {T.SP_3}; background: {T.LATAR_CATATAN};
  border: 1px solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_SEDANG};
}}
.rencana-form-st {{ margin: 0; }}
.rencana-cta-utama-st {{
  width: 100%; min-height: {T.TINGGI_CTA}; display: inline-flex;
  align-items: center; justify-content: center; padding: {T.SP_3} {T.SP_5};
  border: 0; border-radius: {T.RADIUS_SEDANG};
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  font: inherit; font-family: {T.FONT_HEADLINE}; font-weight: 700;
  text-decoration: none; cursor: pointer;
}}
.rencana-cta-utama-st:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.ubah-fokus-st, .atur-latihan-st {{
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU}; padding: 0 {T.SP_4};
}}
.ubah-fokus-st summary, .atur-latihan-st summary {{
  min-height: {T.TARGET_SENTUH}; display: flex; align-items: center;
  color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE}; font-weight: 700;
  cursor: pointer;
}}
.ubah-fokus-st p, .atur-latihan-st > p {{ color: {T.TEKS_VARIAN}; }}
.ubah-fokus-st form {{ display: grid; gap: {T.SP_3}; padding-bottom: {T.SP_4}; }}
.ubah-fokus-st label {{ display: grid; gap: {T.SP_1}; font-weight: 600; }}
.ubah-fokus-st input, .ubah-fokus-st select {{
  min-height: {T.TINGGI_KONTROL}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; padding: 0 {T.SP_3}; font: inherit;
}}
.ubah-fokus-st button {{
  min-height: {T.TINGGI_KONTROL}; border: 1px solid {T.AKSEN_TEAL_TUA};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU};
  color: {T.AKSEN_TEAL_TUA}; font: inherit; font-weight: 700; cursor: pointer;
}}
.atur-latihan-st > .buat-latihan-st {{ margin: 0 0 {T.SP_4}; border: 0; padding: 0; }}
@media (max-width: 34rem) {{
  .strip-rencana-st {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
  .kartu-rencana-st {{ padding: {T.SP_4}; }}
}}

/* ── Kartu "Buat latihan" (3 Sep, Fase C): tab CSS-only ──
   Tiga form sebelumnya berdiri sebagai tiga kartu abu-abu berurutan; di
   kolom kanan itu berarti menggulir jauh untuk sampai ke form ketiga.
   Kini satu kartu dengan tab. TANPA JS: radio + :has(), sama seperti
   .mode-opsi:has(input:checked) yang sudah dipakai. */
.buat-latihan-st {{
  background: {T.LATAR_KARTU};
  border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_4};
}}
.buat-latihan-st > h2.st {{ margin: 0 0 {T.SP_3}; }}
/* Radio penggerak tab: disembunyikan dari mata, TETAP dapat difokus papan
   ketik (bukan display:none yang mencabutnya dari urutan tab). */
.tab-radio-st {{
  position: absolute; opacity: 0; width: 1px; height: 1px;
  margin: 0; pointer-events: none;
}}
.tab-bar-st {{
  display: flex; flex-wrap: wrap; gap: {T.SP_2};
  border-bottom: 1px solid {T.BORDER_VARIAN};
  margin-bottom: {T.SP_4};
}}
.tab-label-st {{
  display: inline-flex; align-items: center; gap: {T.SP_2};
  padding: {T.SP_2} {T.SP_3}; min-height: {T.TARGET_SENTUH};
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .88rem;
  color: {T.TEKS_VARIAN}; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -1px;
}}
.tab-label-st .material-symbols-outlined {{ font-size: 1.1rem; }}
.tab-label-st:hover {{ color: {T.TEKS_JUDUL}; }}
/* Strip di dalam panel sudah dibingkai kartu induk — buang bingkai gandanya. */
.panel-latihan-st > .strip-sesi {{
  margin-top: 0; padding: 0; background: none; border: 0;
}}

/* Penyembunyian panel HANYA kalau :has() didukung. Tanpa penjagaan ini,
   browser lama menyembunyikan panel dan tidak punya cara menampilkannya
   lagi — guru kehilangan tombol buat sesi sama sekali. Di sana semua panel
   tampil berurutan seperti sebelum Fase C: lebih panjang, tetap berfungsi. */
@supports selector(:has(*)) {{
  .panel-latihan-st {{ display: none; }}
  .buat-latihan-st:has(#tab-baru:checked) [data-panel="baru"],
  .buat-latihan-st:has(#tab-ulang:checked) [data-panel="ulang"],
  .buat-latihan-st:has(#tab-gabungan:checked) [data-panel="gabungan"] {{
    display: block;
  }}
  .buat-latihan-st:has(#tab-baru:checked) .tab-label-st[for="tab-baru"],
  .buat-latihan-st:has(#tab-ulang:checked) .tab-label-st[for="tab-ulang"],
  .buat-latihan-st:has(#tab-gabungan:checked) .tab-label-st[for="tab-gabungan"] {{
    color: {T.AKSEN_MURID_UTAMA}; border-bottom-color: {T.AKSEN_MURID_UTAMA};
  }}
}}
/* Fokus papan ketik harus terlihat: radio-nya kasat mata nol, jadi cincin
   fokus dipinjamkan ke labelnya. */
.tab-radio-st:focus-visible + .tab-bar-st .tab-label-st,
.buat-latihan-st:has(.tab-radio-st:focus-visible) .tab-bar-st {{
  outline: {T.TEBAL_FOKUS} solid {T.AKSEN_MURID_UTAMA}; outline-offset: 2px;
}}

/* ── Halaman kerja murid (/murid/kerjakan/<id>) — S4 adopsi Stitch ── */

/* Badan kerja: sticky topbar + timer, lalu konten utama, lalu save strip.  */
.kerja-badan-st {{ max-width: {T.LEBAR_KONTEN}; margin: 0 auto; padding: {T.SP_4} 0.9rem 5rem; min-height: 60vh; }}
.kerja-topbar-st {{
  background: {T.LATAR_SEKUNDER_LEMBUT};
  border-bottom: 1px solid {T.BORDER_VARIAN};
  height: {T.TARGET_SENTUH};
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 {T.SP_4};
  width: 100%; max-width: {T.LEBAR_KONTEN};
  margin: 0 auto; position: sticky; top: 0; z-index: 50;
  font-family: {T.FONT_HEADLINE};
}}
.kerja-topbar-st .brand {{ display: flex; align-items: center; gap: {T.SP_2}; }}
.kerja-topbar-st .brand .ik-owl {{
  width: {T.LOGO_TOPBAR}; height: {T.LOGO_TOPBAR}; flex: none;
  display: inline-flex; align-items: center;
}}
.kerja-topbar-st .brand .nama-osn {{ color: {T.WARNA_WORDMARK}; font-size: 1.1rem; font-weight: 800; }}
.kerja-topbar-st .cta-keluar {{
  font: inherit; color: {T.AKSEN_KORAL_TUA};
  background: none; border: 0; padding: {T.SP_2} {T.SP_4};
  font-weight: 700; min-height: {T.TARGET_SENTUH};
}}

.kerja-meta-st {{ font-size: .9rem; color: {T.TEKS_VARIAN}; margin: 0 0 {T.SP_4}; }}
.kerja-meta-st b {{ color: {T.TEKS_JUDUL}; font-family: {T.FONT_HEADLINE}; }}

.kerja-petunjuk-st {{
  background: {T.LATAR_SEKUNDER_LEMBUT};
  border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_3} {T.SP_4}; margin-bottom: {T.SP_5};
  font-size: .95rem; line-height: 1.55;
}}
.kerja-petunjuk-st .baris-petunjuk {{ display: flex; gap: {T.SP_3}; align-items: flex-start; }}
.kerja-petunjuk-st p {{ margin: 0 0 0.55rem; }}
.kerja-petunjuk-st p:last-child {{ margin-bottom: 0; }}

/* Timer strip per-sesi (Latihan Cepat). Sticky di bawah topbar, teal penuh.  */
.kerja-timer-st {{
  position: sticky; top: {T.TARGET_SENTUH}; z-index: 40;
  background: {T.AKSEN_MURID_UTAMA}; color: #fff;
  padding: {T.SP_2} {T.SP_4}; border-radius: {T.RADIUS_SEDANG};
  margin-bottom: {T.SP_5}; font-size: .98rem; font-weight: 600;
  text-align: center; display: flex; justify-content: center; align-items: center; gap: {T.SP_2};
}}
.kerja-timer-st b {{ font-size: 1.15rem; font-family: {T.FONT_HEADLINE}; }}
.kerja-timer-st.habis {{
  background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT};
  border: 2px solid {T.BORDER_GALAT};
}}

/* Banner konfirmasi tersimpan. */
.kerja-tersimpan-st {{
  background: {T.LATAR_TERSIMPAN};
  border: 1px solid {T.BORDER_TERSIMPAN};
  color: {T.TEKS_TERSIMPAN};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_3} {T.SP_4}; margin: 0 0 {T.SP_4};
  display: flex; gap: {T.SP_3}; align-items: center;
  font-size: .98rem;
}}
.kerja-tersimpan-st .ikon {{
  background: {T.BORDER_TERSIMPAN}; color: #fff;
  border-radius: 50%; width: 24px; height: 24px;
  display: inline-flex; align-items: center; justify-content: center; font-weight: bold;
}}

/* Section heading bagian soal. */
.kerja-bagian-st {{
  font-family: {T.FONT_HEADLINE}; font-size: 1.05rem; font-weight: 700;
  color: {T.TEKS_JUDUL}; margin: {T.SP_5} 0 {T.SP_2};
  padding-bottom: .35rem; border-bottom: 2px solid {T.AKSEN_MURID_UTAMA};
}}
.kerja-catatan-bagian-st {{
  background: {T.LATAR_CATATAN}; border: 1px solid {T.BORDER_CATATAN};
  border-radius: {T.RADIUS_KECIL};
  padding: .55rem .8rem; margin: -.2rem 0 {T.SP_4}; font-size: .92rem;
}}

/* Kartu soal Stitch — primer. Nomor badge lingkaran teal menggantung di pojok. */
.kerja-soal-st {{
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_5} {T.SP_4} {T.SP_4}; margin-bottom: {T.SP_5};
  position: relative; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}}
/* Nomor badge — di Stitch: lingkaran teal absolute -top-4 left-4. */
.kerja-nomor-st {{
  position: absolute; top: -0.85rem; left: {T.SP_3};
  width: 2.2rem; height: 2.2rem;
  background: {T.AKSEN_MURID_UTAMA}; color: {T.TEKS_PUTIH};
  border-radius: {T.RADIUS_BULAT}; border: 2px solid {T.LATAR_KARTU};
  display: inline-flex; align-items: center; justify-content: center;
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: .95rem;
  box-shadow: 0 2px 6px rgba(0,0,0,.18);
}}
.kerja-bintang-st {{ font-weight: 700; color: {T.AKSEN_MURID_AMBER}; margin-left: {T.SP_2}; }}

.kerja-teks-st {{ display: block; margin-top: {T.SP_2}; color: {T.TEKS_UTAMA}; }}
.kerja-tanya-st {{
  display: block; font-family: {T.FONT_HEADLINE}; font-size: 1.12rem; font-weight: 700;
  margin-top: {T.SP_3}; color: {T.TEKS_JUDUL}; line-height: 1.45;
}}

/* Label kecil (Caraku / restate). */
.kerja-label-st {{
  display: block; font-size: .85rem; color: {T.TEKS_VARIAN};
  margin: {T.SP_4} 0 {T.SP_2};
  display: flex; align-items: center; gap: {T.SP_1};
  font-family: {T.FONT_HEADLINE}; font-weight: 600;
}}

/* Restatement textarea. */
.kerja-restate-st {{
  width: 100%; min-height: 84px;
  border: 1.5px dashed #99a; border-radius: {T.RADIUS_KECIL};
  padding: .6rem; font-size: 1rem; font-family: inherit;
  background: {T.LATAR_SEKUNDER_LEMBUT};
}}
.kerja-restate-st:focus {{
  outline: none; border-color: {T.AKSEN_MURID_UTAMA}; border-style: solid;
  box-shadow: 0 0 0 3px rgba(15,163,163,0.18);
}}

/* Pilihan Caraku — pil 2-kolom; radio tersembunyi di dalam label yang tampil. */
.kerja-pill-grup-st {{
  display: grid; grid-template-columns: 1fr 1fr;
  gap: {T.SP_2}; margin-bottom: {T.SP_4};
}}
@media (max-width: 24rem) {{ .kerja-pill-grup-st {{ grid-template-columns: 1fr; }} }}
.kerja-pill-st {{
  display: flex; align-items: center; justify-content: center;
  border: 1.5px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_PIL};
  padding: {T.SP_2} {T.SP_3}; min-height: {T.TARGET_SENTUH};
  background: {T.LATAR_KARTU}; cursor: pointer; font-size: .92rem;
  font-family: {T.FONT_HEADLINE}; font-weight: 500;
  text-align: center;
}}
.kerja-pill-st input {{ position: absolute; opacity: 0; pointer-events: none; }}
/* :has() — terpilih = teal solid penuh. */
.kerja-pill-st:has(input:checked) {{
  background: {T.AKSEN_MURID_UTAMA}; color: {T.TEKS_PUTIH};
  border-color: {T.AKSEN_MURID_UTAMA}; font-weight: 700;
}}
.kerja-pill-st:has(input:focus-visible) {{
  border-color: {T.AKSEN_MURID_UTAMA};
  box-shadow: 0 0 0 3px rgba(15,163,163,0.28);
}}
.kerja-pill-st:hover:not(:has(input:checked)) {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}

/* Textarea "tulis lebih jelas" opsional di Caraku. */
.kerja-cara-st {{
  width: 100%; min-height: 70px;
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG};
  padding: .6rem; font-size: 1rem; font-family: inherit;
  background: {T.LATAR_SEKUNDER_LEMBUT};
}}
.kerja-cara-st:focus {{
  outline: none; border-color: {T.AKSEN_MURID_UTAMA};
  box-shadow: 0 0 0 3px rgba(15,163,163,0.18);
}}

/* Baris Jawabanku: label + input besar, tekan tombol keyboard. */
.kerja-jawab-st {{
  display: flex; flex-direction: column; gap: {T.SP_2}; margin-top: {T.SP_4};
}}
.kerja-jawab-st .head-jawab {{
  display: flex; align-items: center; gap: {T.SP_2};
  font-family: {T.FONT_HEADLINE}; font-weight: 700; color: {T.TEKS_JUDUL};
  font-size: 1rem;
}}
.kerja-jawab-st .head-jawab .material-symbols-outlined {{ color: {T.AKSEN_MURID_UTAMA}; font-size: 1.15rem; }}
.kerja-jawab-st input[type=text] {{
  width: 100%; min-height: {T.TINGGI_KONTROL};
  font-size: 1.15rem; font-family: inherit;
  text-align: center;
  border: 1.5px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; padding: .55rem .7rem;
  background: {T.LATAR_KARTU};
}}
.kerja-jawab-st input[type=text]:focus {{
  outline: none; border-color: {T.AKSEN_MURID_UTAMA};
  box-shadow: 0 0 0 3px rgba(15,163,163,0.20);
}}

/* Centang "belum pernah lihat". */
.kerja-centang-st {{
  display: flex; align-items: center; gap: .5rem; margin-top: {T.SP_3};
  font-size: .92rem; color: {T.TEKS_VARIAN}; font-family: {T.FONT_HEADLINE};
}}
.kerja-centang-st input {{ width: 1.3rem; height: 1.3rem; flex: none; accent-color: {T.AKSEN_MURID_UTAMA}; }}

.catatan-soal-timer-st {{
  margin-top: .5rem; font-size: .85rem; color: {T.AKSEN_KORAL_TUA};
}}

/* Save strip sticky bawah: simpan sementara + kirim final. */
.kerja-simpan-strip-st {{
  position: sticky; bottom: 0; padding: {T.SP_3} 0 {T.SP_2};
  background: linear-gradient(to top, {T.LATAR_MURID} 70%, transparent);
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.35fr);
  gap: {T.SP_2};
}}
.kerja-simpan-strip-st button {{
  width: 100%; font-size: 1rem; padding: .85rem {T.SP_2};
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  border: 0; border-radius: {T.RADIUS_PIL};
  font-family: {T.FONT_HEADLINE}; font-weight: 700; cursor: pointer;
  min-height: {T.TINGGI_KONTROL};
  display: flex; align-items: center; justify-content: center; gap: {T.SP_2};
  box-shadow: 0 4px 12px rgba(255,107,91,.30);
}}
.kerja-simpan-strip-st button:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.kerja-simpan-strip-st button.sekunder {{
  background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA};
  border: 1px solid {T.AKSEN_TEAL_TUA}; box-shadow: none;
}}

/* Varian putih: hover memakai permukaan naik, bukan koral. */
.kerja-simpan-strip-st button.sekunder:hover {{ background: {T.LATAR_ELEVASI}; }}
.kerja-simpan-strip-st button:disabled {{ opacity: .55; cursor: not-allowed; }}
@media (max-width: 24rem) {{
  .kerja-simpan-strip-st {{ grid-template-columns: 1fr; }}
}}

/* Tombol sekunder Cetak/PDF + Sesi lain. */
.kerja-btn-sekunder-st {{
  font-family: {T.FONT_HEADLINE};
  background: {T.LATAR_SEKUNDER_NETRAL};
  color: {T.TEKS_JUDUL}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG};
  padding: .55rem {T.SP_4}; font-weight: 600; font-size: .95rem;
  text-decoration: none; cursor: pointer;
  min-height: {T.TARGET_SENTUH};
  display: inline-flex; align-items: center; gap: {T.SP_1};
}}
.kerja-btn-sekunder-st:hover {{ background: {T.LATAR_ELEVASI}; }}

/* Kirim foto cara pengerjaan (anak yang mengerjakan di kertas).
   Sengaja terlihat sebagai jalur ALTERNATIF, bukan tombol utama: anak
   yang mengerjakan online tidak boleh merasa wajib memfoto. */
.kerja-foto-st {{
  background: {T.LATAR_KARTU_MURID};
  border: 1px dashed {T.AKSEN_MURID_UTAMA};
  border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_4}; margin-top: {T.SP_4};
}}
.kerja-foto-kepala-st {{
  display: flex; align-items: center; gap: {T.SP_2};
  font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL};
}}
.kerja-foto-kepala-st .material-symbols-outlined {{
  color: {T.AKSEN_MURID_UTAMA};
}}
.kerja-foto-sub-st {{
  color: {T.TEKS_SUBTLE}; font-size: .9rem; margin: {T.SP_2} 0 {T.SP_3};
}}
.kerja-foto-kabar-st {{
  background: {T.LATAR_TERSIMPAN}; border: 1px solid {T.BORDER_TERSIMPAN};
  color: {T.TEKS_TERSIMPAN}; border-radius: {T.RADIUS_SEDANG};
  padding: {T.SP_2} {T.SP_3}; margin: 0 0 {T.SP_3}; font-size: .92rem;
}}
.kerja-foto-jumlah-st {{
  color: {T.TEKS_SUBTLE}; font-size: .88rem; margin: 0 0 {T.SP_3};
}}
.kerja-foto-form-st {{
  display: flex; flex-wrap: wrap; gap: {T.SP_3}; align-items: center;
}}
/* Input file bawaan browser punya lebar intrinsik besar (nama berkas +
   tombol Choose File) dan TIDAK mengecil hanya dengan flex:1 — di HP 420px
   ia mendorong tombol kirim keluar layar (terbukti lewat screenshot
   headless). Paksa tiap anak jadi satu baris penuh: input dan tombol
   bertumpuk, tidak ada yang terpotong. */
.kerja-foto-form-st > * {{ flex: 1 0 100%; min-width: 0; max-width: 100%; }}
.kerja-foto-form-st input[type=file] {{
  font-size: .92rem; width: 100%;
}}
.kerja-foto-form-st button {{ width: 100%; justify-content: center; }}
@media (min-width: 34rem) {{
  /* Layar lebar: cukup ruang untuk sebaris. */
  .kerja-foto-form-st > * {{ flex: 0 1 auto; }}
  .kerja-foto-form-st input[type=file] {{ flex: 1 1 auto; }}
  .kerja-foto-form-st button {{ width: auto; }}
}}

/* Drill: kartu "ringan" — tetap punya kartu utuh, hilangkan pill Caraku.
   Pakai kelas modifier .kerja-soal-st.drill untuk menandakan. */
.kerja-soal-st.drill {{ padding-top: {T.SP_5}; }}

/* Cetak: halaman kerja harus cetak baik di A4. */
@media print {{
  body.st {{ background: #fff; font-size: {T.UKURAN_BADAN_CETAK}; }}
  .kerja-badan-st {{ max-width: none; padding: 0; }}
  .kerja-topbar-st, .kerja-simpan-strip-st, .hanya-layar {{ display: none; }}
  .kerja-soal-st {{ break-inside: avoid; box-shadow: none; border-color: #000; }}
  .kerja-bagian-st {{ break-after: avoid; }}
}}

/* Hormati preferensi gerak. */
@media (prefers-reduced-motion: reduce) {{
  * {{ transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; }}
}}

/* ── Form buat sesi (S6) — card radio mode + timer toggle ── */

/* Wrapper form di kartu siswa dashboard. */
.strip-sesi {{
  margin-top: {T.SP_4};
  padding: {T.SP_4};
  background: {T.LATAR_SEKUNDER_LEMBUT};
  border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU};
  display: flex; flex-direction: column; gap: {T.SP_4};
  /* 3 Sep: ditulis EKSPLISIT meski stretch itu nilai default. Sebelumnya ada
     blok .strip-sesi lain di atas dengan align-items:flex-end, dan blok kolom
     ini mewarisinya → label & select menempel ke tepi kanan (terukur x=866
     dan x=744, seharusnya 383). Baris ini yang menahannya kalau terulang. */
  align-items: stretch;
  flex-wrap: nowrap;
}}
.strip-sesi .strip-kolom {{ display: flex; flex-direction: column; gap: {T.SP_2}; min-width: 0; }}
/* Di desktop select melar selebar kartu (673px) dan lelah dipindai mata;
   22rem masih jauh di atas target sentuh saat di HP. */
.strip-sesi select.st-input {{ max-width: 22rem; }}
/* Tombol aksi di dalam strip: di HP ia melebihi lebar kartu karena
   padding tetap 1.5rem + label panjang ("Buat latihan ulang") dan
   terpotong di kanan (terbukti lewat screenshot headless 390px).
   Satu baris penuh di layar sempit, kembali auto di layar lebar. */
.strip-sesi .st-tombol-coral {{
  width: 100%; justify-content: center; padding: 0 {T.SP_4};
  display: inline-flex; align-items: center; gap: {T.SP_2};
}}
@media (min-width: 34rem) {{
  .strip-sesi .st-tombol-coral {{ width: auto; align-self: flex-start; }}
}}
.strip-sesi .strip-kolom > label {{
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .82rem;
  color: {T.TEKS_VARIAN};
}}
.remedial-st {{
  margin-top: {T.SP_5}; padding: {T.SP_4}; background: {T.LATAR_KARTU};
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU};
}}
.remedial-st > h2 {{ margin: 0 0 {T.SP_2}; font-family: {T.FONT_HEADLINE}; }}
.remedial-st > .strip-sesi {{ margin-top: {T.SP_3}; }}
.daftar-remedial-st {{ display: grid; gap: {T.SP_2}; }}
.pilihan-remedial-st {{
  display: flex; gap: {T.SP_3}; align-items: flex-start; padding: {T.SP_3};
  min-height: {T.TARGET_SENTUH}; cursor: pointer; background: {T.LATAR_KARTU};
  border: 1.5px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG};
}}
.pilihan-remedial-st:has(input:checked) {{
  border-color: {T.AKSEN_MURID_UTAMA}; background: {T.LATAR_KARTU_SEKUNDER};
}}
.pilihan-remedial-st input {{
  flex: none; width: 1.25rem; height: 1.25rem; margin-top: .15rem;
  accent-color: {T.AKSEN_MURID_UTAMA};
}}
.isi-pilihan-remedial-st {{ display: flex; flex-direction: column; gap: {T.SP_1}; min-width: 0; }}
.meta-remedial-st, .batas-remedial-st {{
  color: {T.TEKS_VARIAN}; font-size: .82rem; line-height: 1.45;
}}
.batas-remedial-st {{ margin: 0; }}

/* Card radio mode (Diagnosa / Latihan Cepat) — bukan radio kecil. */
.mode-pilih {{ display: flex; flex-direction: column; gap: {T.SP_2}; }}
.mode-opsi {{
  display: flex; align-items: flex-start; gap: {T.SP_3};
  border: 1.5px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG};
  padding: {T.SP_3}; min-height: {T.TARGET_SENTUH};
  background: {T.LATAR_KARTU}; cursor: pointer;
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .92rem;
  color: {T.TEKS_JUDUL};
}}
.mode-opsi input {{
  flex: none; width: 1.3rem; height: 1.3rem; margin-top: 0.15rem;
  accent-color: {T.AKSEN_MURID_UTAMA};
}}
.mode-opsi .mode-teks {{ display: flex; flex-direction: column; gap: 0.15rem; }}
.mode-opsi .mode-teks .mode-desk {{
  font-family: {T.FONT_BODY}; font-weight: 400; font-size: .82rem;
  color: {T.TEKS_VARIAN};
}}
.mode-opsi:has(input:checked) {{
  border-color: {T.AKSEN_MURID_UTAMA}; background: {T.LATAR_KARTU_SEKUNDER};
  box-shadow: 0 0 0 3px rgba(15,163,163,0.12);
}}

/* Batas waktu adalah opsi Latihan Cepat, bukan mode latihan ketiga.
   Fallback browser tanpa :has(): tampilkan panel agar kontrol tidak hilang. */
.pengaturan-timer {{
  display: flex;
  margin: 0; min-width: 0;
  background: {T.LATAR_SEKUNDER_NETRAL};
  border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG};
  padding: {T.SP_3};
  flex-direction: column; gap: {T.SP_2};
}}
.rincian-timer {{
  display: flex; flex-direction: column; gap: {T.SP_3};
  padding-top: {T.SP_1};
}}
@supports selector(:has(*)) {{
  .pengaturan-timer {{ display: none; }}
  .strip-sesi:has(input[name=mode][value=drill]:checked) .pengaturan-timer {{
    display: flex;
  }}
  .rincian-timer {{ display: none; }}
  .pengaturan-timer:has(.timer-toggle input:checked) .rincian-timer {{
    display: flex;
  }}
}}
.pengaturan-timer > legend, .akibat-timer > legend {{
  padding: 0 {T.SP_1};
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .82rem;
  color: {T.TEKS_VARIAN};
}}
.pengaturan-timer .mode-opsi {{
  min-height: 0; padding: {T.SP_2} {T.SP_3};
  font-weight: 500; font-size: .88rem;
}}
.durasi-timer {{
  display: flex; flex-wrap: wrap; align-items: center; gap: {T.SP_2};
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .88rem;
  color: {T.TEKS_JUDUL};
}}
.durasi-timer small {{
  flex-basis: 100%; font-family: {T.FONT_BODY}; font-weight: 400;
  color: {T.TEKS_VARIAN}; font-size: .78rem;
}}
.akibat-timer {{
  display: flex; flex-direction: column; gap: {T.SP_2};
  margin: 0; min-width: 0; padding: {T.SP_2};
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG};
}}
.pengaturan-timer input[name=durasi_menit] {{
  width: 4.5rem; display: inline-block;
  font: inherit; font-size: 1rem; min-height: {T.TINGGI_KONTROL};
  border-radius: {T.RADIUS_SEDANG}; border: 1px solid {T.BORDER_VARIAN};
  background: {T.LATAR_KARTU}; padding: 0 {T.SP_3};
}}

/* ── Pendaftaran editorial — scoped, form/skrip shared tidak diubah ── */
.daftar-editorial-st {{ max-width: 68rem; margin: 0 auto; padding: {T.SP_3} {T.SP_4} 0; }}
.daftar-editorial-st .publik-topbar-st {{
  position: static; height: auto; min-height: 3.5rem; max-width: none;
  background: transparent; border: 0; padding: 0; margin-bottom: {T.SP_5}; gap: {T.SP_4};
}}
.daftar-editorial-st .brand {{ min-height: {T.TARGET_SENTUH}; color: {T.AKSEN_TEAL_TUA}; font-size: 1.5rem; letter-spacing: -.04em; border-radius: {T.RADIUS_KECIL}; }}
.daftar-editorial-st .tombol-putih {{ border: 1px solid {T.AKSEN_TEAL_TUA}; background: transparent; color: {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_PIL}; padding: {T.SP_2} {T.SP_5}; min-height: {T.TARGET_SENTUH}; }}
.daftar-editorial-st .tombol-putih:hover {{ background: {T.LATAR_KARTU}; text-decoration: underline; }}
.daftar-editorial-st .daftar-panel-st {{
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_CATATAN};
  border-radius: {T.RADIUS_KARTU}; box-shadow: 8px 10px 0 {T.BORDER_CATATAN};
}}
.daftar-editorial-st .daftar-catatan-st {{
  min-width: 0; border-radius: {T.RADIUS_KARTU} 0 0 {T.RADIUS_KARTU};
  background: {T.KODE_BELUM_LIAT_BG}; border-right: 1px solid {T.BORDER_VARIAN}; padding: 2.5rem;
}}
.daftar-editorial-st .daftar-alis-st {{ color: {T.AKSEN_TEAL_TUA}; font: 800 .7rem/1.5 {T.FONT_HEADLINE}; letter-spacing: .1em; margin: 0 0 {T.SP_3}; }}
.daftar-editorial-st .daftar-catatan-st h2 {{ font: 800 clamp(1.8rem, 3vw, 2.5rem)/1.15 {T.FONT_HEADLINE}; letter-spacing: -.055em; color: {T.TEKS_JUDUL}; margin: 0; }}
.daftar-editorial-st .daftar-catatan-st h2 span {{ color: {T.AKSEN_TEAL_TUA}; }}
.daftar-editorial-st .daftar-pengantar-st {{ font-size: .85rem; line-height: 1.75; color: {T.TEKS_VARIAN}; margin: {T.SP_4} 0 0; }}
.daftar-editorial-st .daftar-buku-st {{
  position: relative; display: flex; align-items: center; justify-content: center; flex-direction: column;
  margin: {T.SP_5} 0; padding: {T.SP_4}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL};
  background-color: {T.LATAR_KARTU};
  background-image: repeating-linear-gradient(to bottom, transparent 0, transparent 31px, {T.LATAR_SEKUNDER_NETRAL} 31px, {T.LATAR_SEKUNDER_NETRAL} 32px);
}}
.daftar-editorial-st .daftar-buku-st::before {{ content: ""; position: absolute; width: 4rem; height: 1.2rem; background: {T.AKSEN_MURID_AMBER}; opacity: .65; top: -.6rem; left: calc(50% - 2rem); transform: rotate(-5deg); }}
.daftar-editorial-st .daftar-maskot-st {{ width: 8.5rem; height: 8.5rem; object-fit: contain; }}
.daftar-editorial-st .daftar-buku-st > span {{ color: {T.TEKS_VARIAN}; font: 600 .8rem/1.5 {T.FONT_HEADLINE}; transform: rotate(-3deg); }}
.daftar-editorial-st .daftar-langkah-st {{ list-style: none; padding: 0; margin: {T.SP_5} 0 0; display: grid; gap: {T.SP_4}; }}
.daftar-editorial-st .daftar-langkah-st li {{ display: flex; align-items: flex-start; gap: {T.SP_3}; }}
.daftar-editorial-st .daftar-langkah-st li > span {{ font: 800 .75rem/1.8 {T.FONT_HEADLINE}; color: {T.AKSEN_TEAL_TUA}; }}
.daftar-editorial-st .daftar-langkah-st b {{ font: 700 .85rem/1.5 {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.daftar-editorial-st .daftar-langkah-st p {{ font-size: .75rem; color: {T.TEKS_VARIAN}; margin: {T.SP_1} 0 0; line-height: 1.6; }}
.daftar-editorial-st .daftar-kartu-st {{
  width: 100%; min-width: 0; max-width: none; margin: 0; padding: 2.5rem;
  display: flex; flex-direction: column; justify-content: center; gap: {T.SP_5};
  background: transparent; box-shadow: none; border: 0; border-radius: 0 {T.RADIUS_KARTU} {T.RADIUS_KARTU} 0;
}}
.daftar-editorial-st .publik-judul-st {{ font: 800 clamp(1.7rem, 3vw, 2.1rem)/1.2 {T.FONT_HEADLINE}; letter-spacing: -.045em; margin: 0 0 {T.SP_3}; color: {T.TEKS_JUDUL}; }}
.daftar-editorial-st .publik-sub-st {{ font-size: .9rem; line-height: 1.7; color: {T.TEKS_VARIAN}; margin: 0; }}
.daftar-editorial-st .masuk-form-st {{ gap: {T.SP_5}; }}
.daftar-editorial-st .masuk-field-st {{ gap: {T.SP_2}; }}
.daftar-editorial-st .masuk-field-st label {{ font-size: .85rem; color: {T.TEKS_JUDUL}; }}
.daftar-editorial-st .masuk-field-st input {{ min-height: {T.TINGGI_KONTROL}; border-color: {T.BORDER_VARIAN}; }}
.daftar-editorial-st .daftar-petunjuk-st {{ font-size: .75rem; color: {T.TEKS_VARIAN}; line-height: 1.65; margin: 0; }}
.daftar-editorial-st .daftar-persetujuan-st {{ background: {T.LATAR_CATATAN}; border: 1px solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_3}; }}
.daftar-editorial-st .koreksi-centang-st {{ gap: {T.SP_3}; margin: 0; align-items: flex-start; font: 400 .8rem/1.7 {T.FONT_BODY}; color: {T.TEKS_VARIAN}; cursor: pointer; }}
.daftar-editorial-st .koreksi-centang-st input {{ margin: .2rem 0 0; width: 1.2rem; height: 1.2rem; accent-color: {T.AKSEN_TEAL_TUA}; flex: none; }}
.daftar-editorial-st .koreksi-centang-st a {{ color: {T.AKSEN_TEAL_TUA}; text-underline-offset: .2em; }}
.daftar-editorial-st .masuk-tombol-st {{
  min-height: {T.TINGGI_CTA}; justify-content: space-between; padding: {T.SP_3} {T.SP_5};
  font-size: 1rem; background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  border-radius: {T.RADIUS_PIL}; box-shadow: none;
}}
/* Editorial: hover tetap tenang (underline); warna dasar tidak berubah. */
.daftar-editorial-st .masuk-tombol-st:hover {{ filter: none; text-decoration: underline; background: {T.AKSEN_KORAL_TUA}; }}
.daftar-editorial-st .masuk-tombol-st:disabled {{ opacity: .65; cursor: not-allowed; }}
.daftar-editorial-st .daftar-bawah-st {{ margin: -{T.SP_2} 0 0; font-size: .75rem; line-height: 1.6; color: {T.TEKS_VARIAN}; }}
.daftar-editorial-st .masuk-galat-st {{ text-align: left; padding: {T.SP_3} {T.SP_4}; border-left: 3px solid {T.TEKS_GALAT}; font-size: .85rem; overflow-wrap: anywhere; }}
.daftar-editorial-st .masuk-galat-st p {{ margin: {T.SP_1} 0 0; }}
.daftar-editorial-st .pesan-st {{ padding: {T.SP_3} {T.SP_4}; border: 1px solid {T.BORDER_VARIAN}; background: {T.LATAR_SEKUNDER_LEMBUT}; border-radius: {T.RADIUS_SEDANG}; font-size: .85rem; color: {T.TEKS_VARIAN}; overflow-wrap: anywhere; }}
.daftar-editorial-st .pesan-st p {{ margin: {T.SP_1} 0 0; }}
.daftar-editorial-st :is(a, button, input):focus-visible,
.daftar-editorial-st .masuk-field-st input:focus-visible {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; box-shadow: none; }}
.daftar-editorial-st .daftar-kaki-st {{ font-size: .75rem; text-align: center; color: {T.TEKS_VARIAN}; margin: {T.SP_5} 0 0; }}
@media (max-width: 59.99rem), (max-height: 36rem) {{
  .daftar-editorial-st {{ max-width: 32rem; padding: 0; }}
  .daftar-editorial-st .daftar-panel-st {{ grid-template-columns: minmax(0, 1fr); box-shadow: 4px 6px 0 {T.BORDER_CATATAN}; }}
  .daftar-editorial-st .daftar-catatan-st {{ display: none; }}
  .daftar-editorial-st .daftar-kartu-st {{ padding: {T.SP_6} {T.SP_5}; }}
  .daftar-editorial-st .publik-topbar-st {{ margin-bottom: {T.SP_4}; }}
}}
@media (max-width: 24rem) {{
  .daftar-editorial-st .daftar-kartu-st {{ padding: {T.SP_5} {T.SP_4}; gap: {T.SP_4}; }}
  .daftar-editorial-st .publik-judul-st {{ font-size: 1.65rem; }}
  .daftar-editorial-st .masuk-form-st {{ gap: {T.SP_4}; }}
  .daftar-editorial-st .tombol-putih {{ padding: {T.SP_2} {T.SP_4}; }}
  .daftar-editorial-st .brand {{ font-size: 1.35rem; }}
}}

/* ── Halaman masuk editorial — kanvas khusus, bukan form daftar ── */
.masuk-badan-st {{
  min-height: 100vh; max-width: 62rem; margin: 0 auto;
  display: flex; flex-direction: column; justify-content: center;
  padding: {T.SP_6} {T.SP_5} 3rem;
}}
.masuk-kepala-st {{ margin: 0 0 {T.SP_5}; }}
.masuk-brand-st {{
  display: inline-flex; align-items: center; gap: {T.SP_2};
  min-height: {T.TARGET_SENTUH}; text-decoration: none;
  border-radius: {T.RADIUS_KECIL}; font-family: {T.FONT_HEADLINE};
}}
.masuk-brand-st .nama-brand {{
  font-weight: 800; font-size: 1.5rem; color: {T.AKSEN_TEAL_TUA}; letter-spacing: -.04em;
}}
.masuk-beranda-st {{ color: {T.TEKS_VARIAN}; font-size: .75rem; margin-left: {T.SP_2}; }}
.masuk-brand-st:hover .masuk-beranda-st {{ text-decoration: underline; }}
.masuk-panel-st {{
  display: grid; grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr);
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_CATATAN};
  border-radius: {T.RADIUS_KARTU}; box-shadow: 8px 10px 0 {T.BORDER_CATATAN};
}}
.masuk-catatan-st {{
  display: flex; flex-direction: column; justify-content: center;
  background: {T.KODE_BELUM_LIAT_BG}; border-right: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU} 0 0 {T.RADIUS_KARTU};
  padding: 3rem {T.SP_6}; min-width: 0;
}}
.masuk-alis-st {{
  font-family: {T.FONT_HEADLINE}; font-size: .7rem; font-weight: 800;
  letter-spacing: .1em; color: {T.AKSEN_TEAL_TUA}; margin: 0 0 {T.SP_4};
}}
.masuk-pesan-st {{
  font-family: {T.FONT_HEADLINE}; font-size: clamp(2rem, 3vw, 2.7rem);
  font-weight: 800; line-height: 1.2; letter-spacing: -.055em;
  color: {T.TEKS_JUDUL}; margin: 0;
}}
.masuk-pesan-st span {{ color: {T.AKSEN_TEAL_TUA}; }}
.masuk-buku-st {{
  position: relative; display: flex; flex-direction: column; align-items: center;
  width: 100%; margin: {T.SP_6} 0 0; padding: {T.SP_5} {T.SP_3} {T.SP_4};
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL};
  background-color: {T.LATAR_KARTU};
  background-image: repeating-linear-gradient(to bottom, transparent 0, transparent 31px,
    {T.LATAR_SEKUNDER_NETRAL} 31px, {T.LATAR_SEKUNDER_NETRAL} 32px);
}}
.masuk-buku-st::before {{
  content: ""; position: absolute; width: 4rem; height: 1.25rem;
  top: -.65rem; left: calc(50% - 2rem); transform: rotate(-5deg);
  background: {T.AKSEN_MURID_AMBER}; opacity: .65;
}}
.masuk-maskot-st {{ width: 11rem; height: 11rem; object-fit: contain; }}
.masuk-coret-st {{
  position: absolute; right: {T.SP_4}; top: {T.SP_3}; color: {T.AKSEN_KORAL_TUA};
  font-size: 2.5rem; line-height: 1;
}}
.masuk-catatan-kecil-st {{
  font-family: {T.FONT_HEADLINE}; font-size: .8rem; font-weight: 600;
  color: {T.TEKS_VARIAN}; transform: rotate(-3deg);
}}
.masuk-kartu-st {{
  min-width: 0; padding: 3rem; display: flex; flex-direction: column;
  justify-content: center; gap: {T.SP_5};
}}
.masuk-judul-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 800;
  font-size: clamp(1.8rem, 3vw, 2.2rem); line-height: 1.2;
  letter-spacing: -.045em; color: {T.TEKS_JUDUL}; margin: 0 0 {T.SP_3};
}}
.masuk-sub-st {{ font-size: .9rem; color: {T.TEKS_VARIAN}; margin: 0; }}
@media (max-width: 59.99rem), (max-height: 36rem) {{
  .masuk-badan-st {{ max-width: 31rem; padding: {T.SP_5} {T.SP_4} {T.SP_6}; }}
  .masuk-panel-st {{ grid-template-columns: minmax(0, 1fr); box-shadow: 4px 6px 0 {T.BORDER_CATATAN}; }}
  .masuk-catatan-st {{ display: none; }}
  .masuk-kartu-st {{ padding: {T.SP_6} {T.SP_5} {T.SP_5}; }}
  .masuk-kepala-st {{ margin-bottom: {T.SP_4}; }}
}}
@media (max-width: 24rem) {{
  .masuk-badan-st {{ padding: {T.SP_4} {T.SP_3} {T.SP_5}; }}
  .masuk-kartu-st {{ padding: {T.SP_5} {T.SP_4} {T.SP_4}; gap: {T.SP_4}; }}
  .masuk-judul-st {{ font-size: 1.5rem; }}
  .masuk-sapaan-st .masuk-alis-st {{ margin-bottom: {T.SP_2}; }}
  .masuk-kepala-st {{ margin-bottom: {T.SP_3}; }}
}}

/* Galat / error flash. */
.masuk-galat-st {{
  background: {T.LATAR_GALAT}; border: 1px solid {T.BORDER_GALAT};
  color: {T.TEKS_GALAT}; border-radius: {T.RADIUS_SEDANG};
  padding: {T.SP_2} {T.SP_3}; font-size: .9rem; text-align: center;
}}

/* Form fields. */
.masuk-form-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.masuk-field-st {{ display: flex; flex-direction: column; gap: {T.SP_1}; }}
.masuk-field-st label {{
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .82rem;
  color: {T.TEKS_VARIAN};
}}
.masuk-field-st input {{
  font: inherit; font-size: 1rem; min-height: {T.TINGGI_KONTROL};
  border-radius: {T.RADIUS_SEDANG}; border: 1px solid {T.BORDER_VARIAN};
  background: {T.LATAR_KARTU}; padding: 0 {T.SP_3}; width: 100%;
}}
.masuk-field-st input:focus {{
  border-color: {T.FOKUS_AKSEN}; outline: 0;
  box-shadow: 0 0 0 3px {T.AKSEN_MURID_UTAMA}55;
}}

/* ── Tombol mata sandi pada permukaan Stitch ───────────────────────────
   SKRIP_MATA_SANDI (teacher_style.py) membungkus tiap input[type=password]
   dengan .kolom-sandi lalu menyisipkan tombol .tombol-mata. CSS-nya wajib
   ada di SINI, bukan cuma di GAYA_GURU: halaman publik (/masuk, /daftar)
   hanya memuat gaya_stitch(), jadi tanpa blok ini tombolnya lahir tanpa
   posisi absolut dan nongol di BAWAH kolom, bukan di dalamnya. */
.kolom-sandi {{ position: relative; display: block; }}
.kolom-sandi > input {{ padding-right: 3rem !important; }}
.tombol-mata {{
  position: absolute; top: 50%; right: {T.SP_1}; transform: translateY(-50%);
  width: {T.TARGET_SENTUH}; height: {T.TARGET_SENTUH};
  display: inline-flex; align-items: center; justify-content: center;
  padding: 0; border: none; background: none; box-shadow: none;
  color: {T.TEKS_VARIAN}; cursor: pointer; border-radius: {T.RADIUS_KECIL};
}}
.tombol-mata:hover {{ color: {T.TEKS_UTAMA}; }}
.tombol-mata svg {{ display: block; }}

.masuk-tombol-st {{
  width: 100%; font-size: 1.05rem; padding: .9rem;
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  border: 0; border-radius: {T.RADIUS_SEDANG};
  font-family: {T.FONT_HEADLINE}; font-weight: 700; cursor: pointer;
  min-height: {T.TINGGI_KONTROL};
  display: flex; align-items: center; justify-content: center; gap: {T.SP_2};
  box-shadow: 0 4px 12px rgba(255,107,91,.25);
}}
.masuk-tombol-st:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}

.masuk-link-st {{
  text-align: center; font-size: .9rem; margin-top: {T.SP_2};
  font-family: {T.FONT_HEADLINE};
}}
.masuk-link-st a {{
  color: {T.AKSEN_MURID_UTAMA}; text-decoration: none; font-weight: 600;
}}
.masuk-link-st a:hover {{ text-decoration: underline; }}

/* ══ Form login editorial — override hanya di /masuk, bukan /daftar ══ */
.masuk-badan-st .masuk-form-st {{ gap: {T.SP_5}; }}
.masuk-badan-st .masuk-field-st {{ gap: {T.SP_2}; }}
.masuk-badan-st .masuk-field-st label {{ font-size: .85rem; color: {T.TEKS_JUDUL}; }}
.masuk-badan-st .masuk-field-st input {{ min-height: {T.TINGGI_KONTROL}; border-color: {T.BORDER_VARIAN}; }}
.masuk-badan-st .masuk-petunjuk-st {{
  margin: 0; font-size: .75rem; line-height: 1.65; color: {T.TEKS_VARIAN};
}}
.masuk-badan-st .masuk-tombol-st {{
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  border-radius: {T.RADIUS_PIL}; box-shadow: none; font-size: 1rem;
  justify-content: space-between; padding: {T.SP_3} {T.SP_5}; min-height: {T.TINGGI_KONTROL};
}}
.masuk-badan-st .masuk-tombol-st:hover {{ filter: none; text-decoration: underline; }}
.masuk-badan-st .masuk-link-st {{ margin: -{T.SP_3} 0 0; }}
.masuk-badan-st .masuk-link-st a {{
  display: inline-flex; align-items: center; justify-content: center;
  min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3};
  color: {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_KECIL}; font-size: .85rem;
  text-decoration: underline; text-underline-offset: .2em;
}}
.masuk-badan-st .masuk-galat-st {{
  padding: {T.SP_3} {T.SP_4}; text-align: left; font-size: .85rem;
  border-left: 3px solid {T.TEKS_GALAT};
}}
.masuk-badan-st .masuk-galat-st p {{ margin: {T.SP_1} 0 0; line-height: 1.65; }}
.masuk-badan-st :is(a, button, input):focus-visible {{
  outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; box-shadow: none;
}}
@media (max-width: 24rem) {{
  .masuk-badan-st .masuk-form-st {{ gap: {T.SP_4}; }}
}}

/* ── Halaman publik (S8 daftar, S9 lupa-sandi, S10 kebijakan) ── */

.publik-badan-st {{
  min-height: 100vh; padding: {T.SP_5} {T.SP_4} 3rem;
}}
.publik-topbar-st {{
  background: {T.LATAR_SEKUNDER_LEMBUT}; border-bottom: 1px solid {T.BORDER_VARIAN};
  height: {T.TARGET_SENTUH}; display: flex; align-items: center;
  justify-content: space-between; padding: 0 {T.SP_4};
  width: 100%; max-width: {T.LEBAR_KONTEN}; margin: 0 auto;
  position: sticky; top: 0; z-index: 50; font-family: {T.FONT_HEADLINE};
}}
.publik-topbar-st .brand {{
  display: flex; align-items: center; gap: {T.SP_2}; text-decoration: none;
  font-weight: 800; font-size: 1.1rem; color: {T.WARNA_WORDMARK};
}}
.publik-topbar-st .brand img {{
  width: {T.LOGO_TOPBAR}; height: {T.LOGO_TOPBAR}; flex: none;
}}
.publik-topbar-st .tombol-putih {{
  font: inherit; color: {T.AKSEN_TEAL_TUA}; background: none;
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG};
  padding: {T.SP_2} {T.SP_4}; font-weight: 600; font-size: .9rem;
  text-decoration: none; min-height: {T.TARGET_SENTUH};
  display: inline-flex; align-items: center; gap: {T.SP_1};
}}
.publik-topbar-st .tombol-putih:hover {{
  border-color: {T.AKSEN_MURID_UTAMA}; color: {T.AKSEN_MURID_UTAMA};
}}

.publik-bungkus-st {{
  max-width: {T.LEBAR_KONTEN}; margin: 0 auto; padding: {T.SP_5} 0;
}}
.publik-kartu-st {{
  max-width: 28rem; margin: 0 auto;
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_6} {T.SP_5} {T.SP_5};
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
  display: flex; flex-direction: column; gap: {T.SP_4};
}}
.publik-kartu-st.lebar {{
  max-width: {T.LEBAR_KONTEN};
}}
.publik-judul-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 1.4rem;
  color: {T.TEKS_JUDUL}; margin: 0; letter-spacing: -0.01em;
}}
.publik-sub-st {{
  font-family: {T.FONT_BODY}; font-size: .9rem; color: {T.TEKS_VARIAN};
  margin: 0;
}}
.publik-isi-st {{
  font-family: {T.FONT_BODY}; font-size: .95rem; color: {T.TEKS_UTAMA};
  line-height: 1.6;
}}
.publik-isi-st h2 {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: 1.05rem;
  color: {T.TEKS_JUDUL}; margin: {T.SP_5} 0 {T.SP_2};
}}
.publik-isi-st ul, .publik-isi-st ol {{
  padding-left: 1.2rem; margin: {T.SP_2} 0;
}}
.publik-isi-st li {{ margin-bottom: 0.4rem; }}
.publik-isi-st a {{ color: {T.AKSEN_MURID_UTAMA}; }}

/* Tombol coral reusable di halaman publik. */
a.tombol-coral {{
  display: inline-block; padding: .7rem 1.4rem;
  border-radius: {T.RADIUS_SEDANG}; text-decoration: none; font-weight: 700;
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  font-family: {T.FONT_HEADLINE}; min-height: {T.TINGGI_KONTROL};
  display: inline-flex; align-items: center; gap: {T.SP_2};
}}
a.tombol-coral:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
/* ══ Landing editorial — buku latihan ══
   Semua selector dibatasi landing. Kanvas 75rem tidak mewarisi padding
   form publik; warna, font, dan ukuran dasar memakai token existing. */
.landing-halaman-st {{ min-height: 100vh; }}
.landing-halaman-st :is(a, summary):focus-visible {{
  outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 5px;
}}
.landing-lewati-st {{
  position: absolute; left: {T.SP_4}; top: -6rem; z-index: 100;
  padding: {T.SP_3} {T.SP_4}; background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA};
}}
.landing-lewati-st:focus {{ top: {T.SP_3}; }}
.landing-topbar-st {{ border-bottom: 1px solid {T.BORDER_CATATAN}; }}
.landing-topbar-isi-st {{
  max-width: {T.LEBAR_LANDING}; margin: 0 auto;
  min-height: 5.5rem; display: flex; align-items: center;
  justify-content: space-between; gap: {T.SP_4}; padding: {T.SP_3} {T.SP_5};
  font-family: {T.FONT_HEADLINE};
}}
.landing-topbar-st .brand {{
  display: inline-flex; align-items: center; gap: {T.SP_2}; text-decoration: none;
  min-height: {T.TARGET_SENTUH}; font-weight: 800; font-size: 1.5rem;
  color: {T.AKSEN_TEAL_TUA}; letter-spacing: -.04em;
}}
.landing-topbar-st .topbar-navigasi {{
  display: flex; align-items: center; gap: {T.SP_6};
}}
.landing-nav-st {{
  display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH};
  color: {T.TEKS_VARIAN}; text-decoration: none; font-size: .85rem; font-weight: 600;
}}
.landing-topbar-st .tombol-putih {{
  font: inherit; color: {T.TEKS_JUDUL}; background: transparent;
  border: 1px solid {T.TEKS_JUDUL}; border-radius: {T.RADIUS_PIL};
  padding: {T.SP_2} {T.SP_5}; font-weight: 700; font-size: .85rem;
  text-decoration: none; min-height: {T.TARGET_SENTUH};
  display: inline-flex; align-items: center;
}}
.landing-topbar-st a:hover {{ color: {T.AKSEN_KORAL_TUA}; }}
.landing-bungkus-st {{
  max-width: {T.LEBAR_LANDING}; margin: 0 auto;
  padding: 0 {T.SP_5} 4rem;
}}
.landing-bungkus-st section[id] {{ scroll-margin-top: {T.SP_6}; }}
.landing-hero-st {{
  display: grid; grid-template-columns: minmax(0, 1fr); gap: {T.SP_6};
  align-items: center; padding: 3rem 0 4rem;
}}
@media (min-width: 60rem) {{
  .landing-hero-st {{
    grid-template-columns: minmax(0, 1.08fr) minmax(0, 1fr); gap: 3rem;
    padding: 4rem 0 4.5rem;
  }}
}}
.landing-hero-teks-st {{ min-width: 0; }}
.landing-alis-st {{
  display: flex; align-items: center; gap: {T.SP_2};
  font-family: {T.FONT_HEADLINE}; font-size: .72rem; font-weight: 800;
  letter-spacing: .1em; color: {T.AKSEN_TEAL_TUA}; margin: 0 0 {T.SP_5};
}}
.landing-alis-st > span {{ color: {T.AKSEN_KORAL_TUA}; font-size: 1.6rem; line-height: 1; }}
.landing-judul-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 800;
  font-size: clamp(2.6rem, 4.7vw, 4.25rem); line-height: 1.08;
  letter-spacing: -.065em; color: {T.TEKS_JUDUL}; margin: 0 0 {T.SP_5};
}}
.landing-judul-st > span {{
  display: block; color: {T.AKSEN_TEAL_TUA};
  text-decoration: underline; text-decoration-color: {T.AKSEN_MURID_AMBER};
  text-decoration-thickness: .07em; text-underline-offset: .12em;
}}
.landing-sub-st {{
  font-size: .98rem; line-height: 1.8;
  color: {T.TEKS_VARIAN}; margin: {T.SP_3} 0 0; max-width: 30rem;
}}
.landing-tagline-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: 1rem;
  color: {T.TEKS_JUDUL}; margin: 0;
}}
.landing-cta-baris-st {{ margin: {T.SP_6} 0 {T.SP_3}; }}
.landing-cta-baris-st a.tombol-coral {{
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  padding: {T.SP_4} {T.SP_5}; font-size: .95rem; gap: {T.SP_5};
  border-radius: {T.RADIUS_PIL};
}}
.landing-cta-baris-st a.tombol-coral:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.landing-cta-baris-st a > span {{ font-size: 1.3rem; line-height: 1; }}
.landing-catatan-cta-st {{ color: {T.TEKS_VARIAN}; font-size: .72rem; margin: 0; }}

/* Kertas bergaris + maskot lokal, tanpa kontrol palsu atau animasi. */
.landing-panggung-st {{
  position: relative; isolation: isolate; min-width: 0;
  padding: 3.5rem {T.SP_5} 3rem; max-width: 34rem; width: 100%; margin: auto;
}}
.landing-panggung-st::before {{
  content: ""; position: absolute; inset: {T.SP_5} 0 {T.SP_6}; z-index: -1;
  background-color: {T.LATAR_SEKUNDER_NETRAL};
  background-image: radial-gradient({T.BORDER_VARIAN} 1px, transparent 1px);
  background-size: 18px 18px; border-radius: 48% 48% {T.RADIUS_KARTU} {T.RADIUS_KARTU};
}}
.landing-coret-st {{
  position: absolute; right: 0; top: -1rem; color: {T.AKSEN_KORAL_TUA};
  font-size: 5rem; line-height: 1; transform: rotate(12deg);
}}
.landing-catatan-kertas-st {{
  position: absolute; top: -.8rem; left: {T.SP_6}; margin: 0;
  font-family: {T.FONT_HEADLINE}; font-size: .8rem; line-height: 1.5;
  color: {T.TEKS_JUDUL}; transform: rotate(-5deg);
}}
.landing-demo-st {{
  position: relative; background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_5};
  box-shadow: 7px 9px 0 {T.BORDER_CATATAN};
  display: flex; flex-direction: column; gap: {T.SP_4};
  max-width: 28rem; width: 100%; margin: 0 auto;
}}
.landing-demo-st::before {{
  content: ""; position: absolute; width: 5rem; height: 1.5rem;
  background: {T.AKSEN_MURID_AMBER}; opacity: .55;
  top: -.8rem; left: calc(50% - 2.5rem); transform: rotate(-4deg);
}}
.landing-demo-kepala-st {{
  display: flex; justify-content: space-between; align-items: center;
  border-bottom: 1px solid {T.BORDER_HALUS}; padding-bottom: {T.SP_3};
  font-family: {T.FONT_HEADLINE}; font-size: .72rem; color: {T.TEKS_VARIAN}; font-weight: 700;
}}
.landing-demo-kepala-st span:last-child {{
  color: {T.AKSEN_TEAL_TUA}; background: {T.KODE_BELUM_LIAT_BG};
  padding: {T.SP_1} {T.SP_2}; border-radius: {T.RADIUS_KECIL};
}}
.landing-demo-soal-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: 1.05rem;
  color: {T.TEKS_JUDUL}; margin: 0;
}}
.landing-demo-cara-st {{
  border-left: 2px solid {T.BORDER_GALAT};
  background: repeating-linear-gradient(to bottom, transparent 0, transparent 31px,
    {T.LATAR_SEKUNDER_NETRAL} 31px, {T.LATAR_SEKUNDER_NETRAL} 32px);
  padding: {T.SP_2} {T.SP_4}; font-family: {T.FONT_CETAK};
  font-variant-numeric: tabular-nums; font-size: 1.5rem; line-height: 32px;
  text-align: center; color: {T.TEKS_JUDUL}; white-space: pre-line;
}}
.landing-demo-hasil-st {{
  background: {T.KODE_BELUM_LIAT_BG}; border-radius: {T.RADIUS_KECIL};
  padding: {T.SP_4}; display: flex; flex-direction: column; gap: {T.SP_2};
}}
.landing-demo-label-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: .75rem;
  color: {T.TEKS_VARIAN}; margin: 0;
}}
.landing-kode-grup-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; }}
.landing-kode-st {{
  display: inline-flex; align-items: center; padding: .2rem 0;
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .66rem;
  color: {T.TEKS_VARIAN};
}}
.landing-kode-st.aktif {{
  padding: .2rem .5rem; background: {T.KODE_SALAH_HITUNG_BG};
  color: {T.KODE_SALAH_HITUNG_TEKS}; border-radius: {T.RADIUS_KECIL};
}}
.landing-demo-catatan-st {{ font-size: .78rem; line-height: 1.65; color: {T.TEKS_UTAMA}; margin: 0; }}
.landing-maskot-st {{
  position: absolute; width: 7rem; height: 7rem; object-fit: contain;
  right: -{T.SP_3}; bottom: -{T.SP_4}; pointer-events: none;
}}
.landing-demo-keterangan-st {{
  font-size: .66rem; color: {T.TEKS_VARIAN}; margin: {T.SP_5} 5rem 0 0; text-align: center;
}}

/* Baris manfaat: penanda editorial, bukan tombol. */
.landing-manfaat-st {{
  display: grid; gap: {T.SP_5}; align-items: center;
  border-top: 1px solid {T.BORDER_CATATAN}; border-bottom: 1px solid {T.BORDER_CATATAN};
  padding: {T.SP_6} 0;
}}
.landing-manfaat-st h2 {{
  font-family: {T.FONT_HEADLINE}; font-size: 1rem; font-weight: 700;
  line-height: 1.6; max-width: 17rem; color: {T.TEKS_JUDUL}; margin: 0;
}}
.landing-pill-baris-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_5}; justify-content: space-between; }}
.landing-pill-st {{
  display: inline-flex; align-items: center; gap: {T.SP_3};
  font-family: {T.FONT_HEADLINE}; font-size: .9rem; font-weight: 700; color: {T.TEKS_JUDUL};
}}
.landing-pill-st > span {{ color: {T.AKSEN_TEAL_TUA}; font-size: .72rem; }}
.landing-kenali-st, .landing-contoh-st {{ padding-top: 5rem; }}
.landing-bagian-kepala-st {{ margin-bottom: {T.SP_6}; }}
.landing-bagian-kepala-st .landing-alis-st {{ margin-bottom: {T.SP_3}; }}
.landing-bagian-kepala-st h2, .landing-contoh-judul-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 800;
  font-size: clamp(1.7rem, 3vw, 2.5rem); line-height: 1.2;
  letter-spacing: -.045em; color: {T.TEKS_JUDUL}; margin: 0 0 {T.SP_4};
}}
.landing-bagian-kepala-st > p:last-child, .landing-contoh-sub-st {{
  color: {T.TEKS_VARIAN}; font-size: .92rem; line-height: 1.8; margin: 0;
}}
.landing-grid-st {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: {T.SP_5}; }}
.landing-kartu-st {{
  min-width: 0; background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_CATATAN};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_5};
  display: flex; flex-direction: column; gap: {T.SP_4};
}}
.landing-kartu-judul-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: 1.05rem;
  color: {T.TEKS_JUDUL}; margin: 0; display: flex; align-items: center; gap: {T.SP_3};
}}
.landing-nomor-st {{ font-size: .75rem; color: {T.AKSEN_TEAL_TUA}; }}
.landing-kartu-isi-st {{ font-size: .9rem; line-height: 1.8; color: {T.TEKS_VARIAN}; }}
.landing-kartu-isi-st p {{ margin: 0 0 {T.SP_3}; }}
.landing-kartu-isi-st p:last-child {{ margin-bottom: 0; }}
.landing-kartu-isi-st b {{ color: {T.TEKS_JUDUL}; }}
.landing-cara-st {{ background: {T.TEKS_JUDUL}; border-color: {T.TEKS_JUDUL}; }}
.landing-cara-st :is(.landing-kartu-judul-st, .landing-kartu-isi-st) {{ color: {T.TEKS_PUTIH}; }}
.landing-cara-st .landing-nomor-st {{ color: {T.AKSEN_MURID_AMBER}; font-size: 1.5rem; }}
.landing-cara-st ol {{ list-style: none; counter-reset: langkah; margin: 0; padding: 0; }}
.landing-cara-st li {{
  counter-increment: langkah; display: flex; gap: {T.SP_4};
  align-items: flex-start; padding: {T.SP_4} 0; border-top: 1px solid {T.CHART_AXIS};
}}
.landing-cara-st li::before {{
  content: "0" counter(langkah); color: {T.AKSEN_MURID_AMBER}; font-weight: 700;
}}
.landing-topik-st {{ background: {T.KODE_BELUM_LIAT_BG}; border-color: {T.BORDER_VARIAN}; }}
.landing-kompetisi-st {{ background: transparent; }}
.landing-contoh-st .landing-kartu-st {{ border: 0; border-top: 3px solid {T.BORDER_GALAT}; border-radius: 0; }}
.landing-contoh-st .landing-kartu-st:nth-child(2) {{ border-color: {T.AKSEN_MURID_AMBER}; }}
.landing-contoh-st .landing-kartu-st:nth-child(3) {{ border-color: {T.AKSEN_MURID_UTAMA}; }}
.landing-contoh-dot-st {{ flex: none; width: .6rem; height: .6rem; border-radius: {T.RADIUS_BULAT}; }}
.landing-contoh-kode-st {{
  display: inline-flex; align-items: center; gap: {T.SP_2}; color: {T.TEKS_JUDUL};
  font-family: {T.FONT_HEADLINE}; font-weight: 800; font-size: .85rem;
}}
.landing-resep-st {{
  border-top: 1px solid {T.BORDER_CATATAN};
  padding-top: {T.SP_3}; margin-top: {T.SP_4}; font-size: .85rem;
}}
.landing-pilot-st {{
  display: grid; gap: {T.SP_5}; margin: 5rem 0; padding: {T.SP_6};
  background: {T.TEKS_JUDUL}; border-radius: {T.RADIUS_KARTU};
}}
.landing-pilot-st .landing-alis-st {{ color: {T.AKSEN_MURID_AMBER}; margin-bottom: {T.SP_3}; }}
.landing-pilot-st .landing-contoh-judul-st {{ color: {T.TEKS_PUTIH}; font-size: 3rem; margin: 0; }}
.landing-pilot-st .landing-contoh-sub-st {{ color: {T.TEKS_PUTIH}; align-self: center; }}

/* FAQ bawaan browser: panah buka/tutup hanya dekorasi. */
.landing-faq-st {{ display: grid; gap: {T.SP_5}; }}
.landing-faq-st details {{ border-bottom: 1px solid {T.BORDER_CATATAN}; }}
.landing-faq-st details:first-child {{ border-top: 1px solid {T.BORDER_CATATAN}; }}
.landing-faq-st summary {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: .92rem;
  color: {T.TEKS_JUDUL}; cursor: pointer; min-height: {T.TARGET_SENTUH};
  display: flex; align-items: center; justify-content: space-between; gap: {T.SP_4};
  padding: {T.SP_5} 0; list-style: none;
}}
.landing-faq-st summary::-webkit-details-marker {{ display: none; }}
.landing-faq-st summary::after {{
  content: ""; width: .65rem; height: .65rem; flex: none;
  border-right: 2px solid currentColor; border-bottom: 2px solid currentColor;
  transform: rotate(45deg); margin-right: {T.SP_2};
}}
.landing-faq-st details[open] summary::after {{ transform: rotate(225deg); }}
.landing-faq-st details p {{
  font-size: .9rem; line-height: 1.8; color: {T.TEKS_VARIAN}; margin: 0 0 {T.SP_5};
}}
.landing-faq-st a, .landing-footer-st a {{ color: {T.AKSEN_TEAL_TUA}; }}
.landing-footer-st {{ border-top: 1px solid {T.BORDER_CATATAN}; padding: {T.SP_6} {T.SP_5}; }}
.landing-footer-isi-st {{
  max-width: {T.LEBAR_LANDING}; margin: auto; color: {T.TEKS_VARIAN}; font-size: .75rem;
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: {T.SP_4};
}}
.landing-footer-isi-st a {{ display: inline-flex; min-height: {T.TARGET_SENTUH}; align-items: center; }}
@media (min-width: 48rem) {{
  .landing-manfaat-st {{ grid-template-columns: 1fr 2fr; gap: {T.SP_6}; }}
  .landing-grid-st {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
  .landing-info-st {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .landing-cara-st {{ grid-column: 2; grid-row: 1 / 3; padding: {T.SP_6}; }}
  .landing-kompetisi-st {{ grid-column: 1 / -1; }}
  .landing-pilot-st, .landing-faq-st {{ grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: 3rem; }}
  .landing-pilot-st {{ padding: 3rem; }}
}}
@media (max-width: 40rem) {{
  .landing-bungkus-st {{ padding: 0 {T.SP_4} 3rem; }}
  .landing-topbar-isi-st {{ min-height: 4.5rem; padding: {T.SP_2} {T.SP_4}; }}
  .landing-nav-st {{ display: none; }}
  .landing-hero-st {{ padding-top: {T.SP_6}; }}
  .landing-judul-st {{ font-size: clamp(2.6rem, 9vw, 3.6rem); }}
  .landing-panggung-st {{ padding: 3.5rem {T.SP_2} 3rem; margin-top: {T.SP_5}; }}
  .landing-demo-st {{ padding: {T.SP_4}; }}
  .landing-demo-soal-st {{ font-size: .95rem; }}
  .landing-maskot-st {{ width: 6rem; height: 6rem; right: 0; }}
  .landing-demo-keterangan-st {{ text-align: left; font-size: .6rem; }}
  .landing-pill-baris-st {{ flex-direction: column; gap: {T.SP_4}; }}
  .landing-kenali-st, .landing-contoh-st {{ padding-top: 3.5rem; }}
  .landing-pilot-st {{ margin: 3.5rem 0; padding: {T.SP_5}; }}
}}
/* Halaman hasil murid (/murid/hasil/<id>) — anak melihat letak salahnya.
   Warna status memakai palet murid yang sudah ada; tidak ada token baru. */
.hasil-ringkas-st {{
  display: flex; align-items: center; gap: {T.SP_4};
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_4}; margin-bottom: {T.SP_4};
}}
.hasil-skor-st {{
  font-family: {T.FONT_HEADLINE}; font-size: 2rem; font-weight: 800;
  color: {T.AKSEN_TEAL_TUA}; line-height: 1; flex: none;
}}
.hasil-skor-st span {{ font-size: 1.1rem; color: {T.TEKS_VARIAN}; }}
.hasil-pesan-st {{ font-size: .95rem; color: {T.TEKS_UTAMA}; }}
.hasil-soal-st {{
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-left: 4px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_4}; margin-bottom: {T.SP_3};
}}
.hasil-soal-st.benar {{ border-left-color: {T.AKSEN_MURID_UTAMA}; }}
.hasil-soal-st.salah {{ border-left-color: {T.AKSEN_MURID_KORAL}; }}
.hasil-kepala-st {{
  display: flex; align-items: center; gap: {T.SP_2}; margin-bottom: {T.SP_2};
  flex-wrap: wrap;
}}
.hasil-nomor-st {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.9rem; height: 1.9rem; border-radius: 50%; flex: none;
  background: {T.AKSEN_TEAL_TUA}; color: #fff; font-weight: 700;
}}
.hasil-teks-st {{ margin: 0 0 {T.SP_2}; font-size: .98rem; }}
.hasil-jawabku-st {{
  margin: 0 0 {T.SP_2}; font-size: .93rem; color: {T.TEKS_VARIAN};
}}
.hasil-langkah-st {{
  display: flex; gap: {T.SP_2}; align-items: flex-start;
  background: {T.LATAR_CATATAN}; border: 1px solid {T.BORDER_CATATAN};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_3}; font-size: .93rem;
}}
.hasil-langkah-st .material-symbols-outlined {{
  color: {T.AKSEN_MURID_AMBER}; flex: none; font-size: 1.15rem;
}}

/* Kartu rumus (poin c) — muncul di halaman hasil untuk konsep yang salah. */
.rumus-blok-st {{
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.AKSEN_MURID_AMBER};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_4}; margin-bottom: {T.SP_4};
}}
.rumus-kepala-st {{
  display: flex; align-items: center; gap: {T.SP_2}; margin-bottom: {T.SP_3};
  font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL};
}}
.rumus-kepala-st .material-symbols-outlined {{
  color: {T.AKSEN_MURID_AMBER}; flex: none;
}}
.rumus-kartu-st {{
  border-left: 3px solid {T.AKSEN_MURID_AMBER};
  padding: {T.SP_2} 0 {T.SP_2} {T.SP_3}; margin-bottom: {T.SP_3};
}}
.rumus-kartu-st:last-child {{ margin-bottom: 0; }}
.rumus-judul-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: .95rem;
  color: {T.TEKS_JUDUL}; margin-bottom: .15rem;
}}
.rumus-inti-st {{ font-size: .93rem; }}
.rumus-contoh-st {{
  font-size: .88rem; color: {T.TEKS_VARIAN}; margin-top: .2rem;
}}

/* Ikon aksi pada kartu sesi guru. Berada di GAYA_STITCH karena halaman
   /anak memakai _halaman_stitch tanpa CSS_SESI. */
.aksi-bagikan-st {{ display: flex; gap: {T.SP_1}; justify-content: flex-end; }}
.tombol-ikon-st {{
  width: {T.TINGGI_KONTROL}; height: {T.TINGGI_KONTROL}; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_BULAT};
  background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA}; cursor: pointer;
  -webkit-appearance: none; appearance: none; touch-action: manipulation;
}}
.tombol-ikon-st * {{ pointer-events: none; }}
.tombol-ikon-st:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.tombol-ikon-st:focus-visible {{
  outline: 3px solid {T.FOKUS_AKSEN}; outline-offset: 2px;
}}
.tombol-ikon-st:disabled {{ opacity: .55; cursor: wait; }}

/* WORKER B editorial scoped — murid, dukungan publik, dan pesan khusus. */
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-topbar-st {{
  background: {T.LATAR_MURID}; border-bottom: 1px solid {T.BORDER_VARIAN};
  height: auto; min-height: 3.5rem; padding: {T.SP_1} {T.SP_4};
}}
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-topbar-st .nama-osn {{ color: {T.AKSEN_TEAL_TUA}; }}
:is(.kerja-editorial-st, .hasil-editorial-st) .cta-keluar {{
  display: inline-flex; align-items: center; gap: {T.SP_2};
  color: {T.AKSEN_TEAL_TUA}; text-decoration: none; padding: {T.SP_2};
}}
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-badan-st {{ padding-top: {T.SP_5}; overflow-wrap: anywhere; }}
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-pembuka-st {{ margin-bottom: {T.SP_4}; }}
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-alis-st {{
  color: {T.AKSEN_TEAL_TUA}; font-size: .72rem; font-weight: 700;
  letter-spacing: .13em; margin: 0 0 {T.SP_2};
}}
:is(.kerja-editorial-st, .hasil-editorial-st) h1 {{
  font-family: {T.FONT_HEADLINE}; font-size: clamp(1.65rem, 5.5vw, 2.35rem);
  line-height: 1.2; letter-spacing: -.045em; color: {T.TEKS_JUDUL}; margin: 0 0 {T.SP_3};
}}
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-meta-st {{ font-size: .82rem; margin-bottom: 0; }}
.kerja-editorial-st .kerja-petunjuk-st {{
  border: 0; border-left: 3px solid {T.BORDER_CATATAN}; background: {T.LATAR_CATATAN};
  border-radius: 0 {T.RADIUS_KECIL} {T.RADIUS_KECIL} 0; font-size: .85rem;
  padding: {T.SP_3}; margin-bottom: {T.SP_4};
}}
.kerja-editorial-st .kerja-petunjuk-st .baris-petunjuk > .material-symbols-outlined {{ display: none; }}
.kerja-editorial-st .kerja-bagian-st {{
  color: {T.AKSEN_TEAL_TUA}; border-bottom: 1px solid {T.BORDER_VARIAN};
  margin: {T.SP_5} 0 {T.SP_4}; font-size: .94rem;
}}
.kerja-editorial-st .kerja-soal-st {{
  padding: {T.SP_4}; border-radius: {T.RADIUS_SEDANG};
  border-color: {T.BORDER_VARIAN}; box-shadow: none;
}}
.kerja-editorial-st .kerja-nomor-st {{
  position: static; width: 2rem; height: 2rem; box-shadow: none;
  background: {T.AKSEN_TEAL_TUA}; border: 0; margin-bottom: {T.SP_1};
}}
.kerja-editorial-st .kerja-cara-pilih-st {{ min-width: 0; border: 0; padding: 0; margin: {T.SP_4} 0 0; }}
.kerja-editorial-st .kerja-cara-pilih-st legend {{ padding: 0; }}
.kerja-editorial-st .refleksi-pilihan-st {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: {T.SP_2}; margin-top: {T.SP_3}; }}
.kerja-editorial-st .refleksi-pilihan-st .kerja-pill-st {{ white-space: normal; overflow-wrap: anywhere; justify-content: flex-start; }}
.kerja-editorial-st .kerja-pill-grup-st {{ grid-template-columns: repeat(2, minmax(0, 1fr)); margin-bottom: 0; }}
.kerja-editorial-st .kerja-pill-st {{ border-radius: {T.RADIUS_KECIL}; font-size: .85rem; }}
.kerja-editorial-st .kerja-pill-st:has(input:checked) {{
  background: {T.AKSEN_TEAL_TUA}; border-color: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH};
}}
.kerja-editorial-st :is(.kerja-cara-st, .kerja-restate-st) {{ background: {T.LATAR_KARTU}; }}
.kerja-editorial-st .kerja-centang-st {{ min-height: {T.TARGET_SENTUH}; font-size: .85rem; }}
.kerja-editorial-st .kerja-centang-st input {{ accent-color: {T.AKSEN_TEAL_TUA}; }}
.kerja-editorial-st .kerja-simpan-strip-st {{ z-index: 30; background: {T.LATAR_MURID}; border-top: 1px solid {T.BORDER_VARIAN}; }}
.kerja-editorial-st .kerja-simpan-strip-st button {{
  background: {T.AKSEN_KORAL_TUA}; box-shadow: none; border-radius: {T.RADIUS_SEDANG};
  font-size: .9rem; min-height: {T.TINGGI_KONTROL};
}}
.kerja-editorial-st .kerja-simpan-strip-st button.sekunder {{
  background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA};
}}
.kerja-editorial-st .kerja-simpan-strip-st button:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.kerja-editorial-st .kerja-simpan-strip-st button.sekunder:hover {{ background: {T.LATAR_ELEVASI}; }}
.kerja-editorial-st .kerja-timer-st {{
  top: 3.5rem; background: {T.AKSEN_TEAL_TUA}; flex-wrap: wrap;
  border-radius: {T.RADIUS_KECIL}; margin-bottom: {T.SP_4};
}}
.kerja-editorial-st .kerja-timer-st.habis {{ background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; }}
.kerja-editorial-st .kerja-tersimpan-st .ikon {{ color: {T.TEKS_TERSIMPAN}; flex: none; }}
.kerja-editorial-st .kerja-foto-st {{
  background: transparent; border: 0; border-top: 1px solid {T.BORDER_VARIAN}; border-radius: 0;
  padding: {T.SP_5} 0 0; margin-top: {T.SP_5};
}}
.kerja-editorial-st .kerja-foto-form-st {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: {T.SP_2}; }}
.kerja-editorial-st .kerja-foto-form-st input[type=file] {{ min-height: {T.TINGGI_KONTROL}; font: inherit; font-size: .85rem; }}
.kerja-editorial-st input[type=file]::file-selector-button {{
  font: inherit; min-height: {T.TINGGI_KONTROL}; padding: {T.SP_2}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KECIL}; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; margin-right: {T.SP_2};
}}
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-btn-sekunder-st {{
  background: transparent; color: {T.AKSEN_TEAL_TUA}; border-color: {T.BORDER_VARIAN};
  font-size: .85rem; justify-content: center;
}}
:is(.kerja-editorial-st, .hasil-editorial-st) .kerja-navigasi-st {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin-top: {T.SP_4}; }}
:is(.kerja-editorial-st, .hasil-editorial-st) :is(a, button, input, textarea):focus-visible {{
  outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; box-shadow: none;
}}
.kerja-editorial-st .kerja-pill-st:has(input:focus-visible) {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; box-shadow: none; }}
.kerja-editorial-st .kerja-selesai-st {{ padding-top: clamp(3rem, 10vh, 6rem); }}
.hasil-editorial-st .hasil-ringkas-st {{
  border: 0; border-block: 1px solid {T.BORDER_VARIAN}; border-radius: 0; background: transparent;
  padding: {T.SP_4} 0; gap: {T.SP_5}; margin-bottom: {T.SP_5};
}}
.hasil-editorial-st .hasil-skor-st small {{
  display: block; font-size: .7rem; color: {T.TEKS_VARIAN}; line-height: 1.5; margin-top: {T.SP_2}; font-weight: 500;
}}
.hasil-editorial-st .hasil-soal-st {{ border-radius: {T.RADIUS_SEDANG}; margin-bottom: {T.SP_4}; }}
.hasil-editorial-st .hasil-langkah-st {{ border: 0; border-left: 2px solid {T.BORDER_CATATAN}; border-radius: 0; }}
.hasil-editorial-st .hasil-langkah-st > div {{ min-width: 0; }}
.hasil-editorial-st .hasil-langkah-st .material-symbols-outlined {{ color: {T.TEKS_VARIAN}; }}
.hasil-editorial-st .st-badge.diagnostik {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; }}
.hasil-editorial-st .st-badge.baru {{ background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; }}
.hasil-editorial-st .rumus-blok-st {{ background: {T.LATAR_CATATAN}; border: 0; border-top: 2px solid {T.BORDER_CATATAN}; border-radius: 0; }}
.hasil-editorial-st .rumus-kepala-st .material-symbols-outlined {{ color: {T.TEKS_VARIAN}; }}
.dukungan-editorial-st {{ max-width: 64rem; margin: 0 auto; overflow-wrap: anywhere; }}
.dukungan-editorial-st :is(.publik-topbar-st, .dukungan-topbar-st) {{
  display: flex; justify-content: space-between; align-items: center; gap: {T.SP_3};
  max-width: none; border-bottom: 1px solid {T.BORDER_VARIAN}; padding: {T.SP_3} 0;
}}
.dukungan-editorial-st .brand {{
  display: inline-flex; align-items: center; gap: {T.SP_2}; min-height: {T.TARGET_SENTUH};
  color: {T.AKSEN_TEAL_TUA}; text-decoration: none; font-family: {T.FONT_HEADLINE}; font-weight: 800;
}}
.dukungan-editorial-st .brand img {{ width: {T.LOGO_TOPBAR}; height: {T.LOGO_TOPBAR}; }}
.dukungan-editorial-st .dukungan-topbar-catatan-st {{ color: {T.TEKS_VARIAN}; font-size: .8rem; }}
.dukungan-editorial-st .publik-bungkus-st {{ max-width: 48rem; padding: clamp(1.5rem, 5vw, 3.5rem) 0; margin: 0 auto; }}
.dukungan-editorial-st .publik-kartu-st {{ max-width: none; background: transparent; border: 0; border-radius: 0; padding: 0; box-shadow: none; }}
.dukungan-editorial-st h1 {{
  font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL};
  font-size: clamp(2rem, 5vw, 3rem); letter-spacing: -.045em; line-height: 1.15; margin: 0 0 {T.SP_4};
}}
.dukungan-editorial-st .dukungan-alis-st {{
  color: {T.AKSEN_TEAL_TUA}; font-size: .72rem; font-weight: 700; letter-spacing: .13em; margin: 0 0 {T.SP_3};
}}
.dukungan-editorial-st .publik-sub-st {{ color: {T.TEKS_VARIAN}; margin-bottom: {T.SP_6}; max-width: 38rem; }}
.dukungan-editorial-st .publik-isi-st {{ font-size: .95rem; line-height: 1.8; color: {T.TEKS_VARIAN}; }}
.dukungan-editorial-st .publik-isi-st h2 {{
  font-family: {T.FONT_HEADLINE}; font-size: 1.15rem; color: {T.TEKS_JUDUL};
  margin: {T.SP_6} 0 {T.SP_3}; padding-top: {T.SP_5}; border-top: 1px solid {T.BORDER_VARIAN};
}}
.dukungan-editorial-st .publik-isi-st li {{ margin-bottom: {T.SP_3}; }}
.lupa-editorial-st .publik-isi-st ul {{ list-style: none; padding: 0; counter-reset: bantuan; }}
.lupa-editorial-st .publik-isi-st li {{
  counter-increment: bantuan; position: relative; padding: {T.SP_4} 0 {T.SP_4} 2.7rem;
  border-top: 1px solid {T.BORDER_VARIAN}; margin: 0;
}}
.lupa-editorial-st .publik-isi-st li::before {{
  content: '0' counter(bantuan); position: absolute; left: 0; top: {T.SP_4};
  color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE}; font-weight: 700;
}}
.lupa-editorial-st .publik-isi-st li b {{ display: block; color: {T.TEKS_JUDUL}; margin-bottom: {T.SP_1}; }}
.dukungan-editorial-st .dukungan-kembali-st a {{
  display: inline-flex; align-items: center; gap: {T.SP_3}; min-height: {T.TARGET_SENTUH};
  color: {T.AKSEN_TEAL_TUA}; font-weight: 700; text-underline-offset: .2em;
}}
.dukungan-editorial-st .tombol-putih:hover {{ color: {T.AKSEN_TEAL_TUA}; border-color: {T.AKSEN_TEAL_TUA}; }}
.dukungan-editorial-st a:focus-visible {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; }}
.pesan-editorial-st {{ max-width: 46rem; margin: 0 auto; padding: {T.SP_4}; overflow-wrap: anywhere; }}
.pesan-editorial-st .pesan-brand-st {{
  display: flex; align-items: center; gap: {T.SP_2}; min-height: 3.5rem;
  color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE}; font-weight: 800; border-bottom: 1px solid {T.BORDER_VARIAN};
}}
.pesan-editorial-st .pesan-brand-st img {{ width: {T.LOGO_TOPBAR}; height: {T.LOGO_TOPBAR}; }}
.pesan-editorial-st .pesan-catatan-st {{ margin: clamp(2rem, 8vh, 5rem) 0; border-left: 3px solid {T.BORDER_CATATAN}; padding-left: {T.SP_5}; }}
.pesan-editorial-st .pesan-alis-st {{ font-size: .72rem; font-weight: 700; color: {T.AKSEN_TEAL_TUA}; letter-spacing: .12em; }}
.pesan-editorial-st h1 {{ font: 800 clamp(1.8rem, 5vw, 2.6rem)/1.2 {T.FONT_HEADLINE}; letter-spacing: -.04em; color: {T.TEKS_JUDUL}; }}
.pesan-editorial-st p {{ color: {T.TEKS_VARIAN}; }}
.pesan-editorial-st a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; color: {T.AKSEN_TEAL_TUA}; font-weight: 700; text-underline-offset: .2em; }}
.pesan-editorial-st a:focus-visible {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; }}
@media (max-width: 24rem) {{
  .kerja-editorial-st .kerja-pill-grup-st {{ grid-template-columns: minmax(0, 1fr); }}
  .hasil-editorial-st .hasil-ringkas-st {{ align-items: flex-start; gap: {T.SP_3}; }}
}}
@media print {{
  @page murid-editorial {{ size: A4; margin: 13mm 12mm 11mm; }}
  :is(.kerja-editorial-st, .hasil-editorial-st) {{ page: murid-editorial; }}
  :is(.kerja-editorial-st, .hasil-editorial-st) :is(.kerja-topbar-st, .hanya-layar) {{ display: none; }}
  :is(.kerja-editorial-st, .hasil-editorial-st) .kerja-badan-st {{ padding: 0; }}
  :is(.kerja-editorial-st, .hasil-editorial-st) h1 {{ font-size: 16pt; }}
  :is(.kerja-editorial-st, .hasil-editorial-st) :is(.kerja-soal-st, .hasil-soal-st, .rumus-kartu-st) {{ break-inside: avoid; }}
  .kerja-editorial-st .kerja-nomor-st {{ background: transparent; color: {T.TEKS_UTAMA}; border: 1px solid {T.TEKS_UTAMA}; }}
  .kerja-editorial-st .kerja-pill-st:has(input:checked) {{ background: transparent; color: {T.TEKS_UTAMA}; border: 2px solid {T.TEKS_UTAMA}; }}
}}
/* Akhir WORKER B editorial scoped. */
/* Rencana belajar jelas — kartu */
.kartu-rencana-st .penanda-judul-rencana-lama-st,
.kartu-rencana-st .penanda-rencana-lama-st {{ display: none; }}
.kartu-rencana-st .judul-tugas-rencana-st {{ margin: 0; }}
.kartu-rencana-st .konteks-pemetaan-jelas-st {{
  display: grid; gap: {T.SP_2}; padding: {T.SP_3} {T.SP_4};
  background: {T.LATAR_SEKUNDER_LEMBUT}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG};
}}
.kartu-rencana-st .konteks-pemetaan-jelas-st p,
.kartu-rencana-st .petunjuk-sesudah-cta-st {{ margin: 0; }}
.kartu-rencana-st .petunjuk-sesudah-cta-st {{
  color: {T.TEKS_VARIAN}; font-size: .9rem; text-align: center;
}}
.kartu-rencana-st .alur-rencana-jelas-st {{
  border-top: 1px solid {T.BORDER_VARIAN}; padding-top: {T.SP_2};
}}
.kartu-rencana-st .alur-rencana-jelas-st > summary {{
  min-height: {T.TARGET_SENTUH}; display: list-item; padding: {T.SP_2} 0;
  color: {T.AKSEN_TEAL_TUA}; font-family: {T.FONT_HEADLINE};
  font-weight: 700; cursor: pointer;
}}
.kartu-rencana-st .alur-rencana-jelas-st > summary::marker {{
  color: {T.AKSEN_TEAL_TUA};
}}
.kartu-rencana-st .alur-rencana-jelas-st > summary:focus-visible {{
  outline: 3px solid {T.FOKUS_AKSEN}; outline-offset: 3px;
  border-radius: {T.RADIUS_KECIL};
}}
.kartu-rencana-st .tahap-aktif-ringkas-st {{
  display: block; margin-top: {T.SP_1}; color: {T.TEKS_VARIAN};
  font-size: .78rem; font-weight: 600;
}}
.kartu-rencana-st .isi-alur-rencana-st {{
  display: grid; gap: {T.SP_2}; padding-top: {T.SP_2};
}}
.kartu-rencana-st .isi-alur-rencana-st p {{ margin: 0; color: {T.TEKS_VARIAN}; }}
/* Akhir rencana belajar jelas — kartu */

/* WORKER A editorial scoped — permukaan pendamping, bukan beranda/murid. */
.pendamping-editorial-st {{
  max-width: 68rem; padding: {T.SP_5} {T.SP_5} 4rem;
  color: {T.TEKS_UTAMA}; overflow-wrap: anywhere;
}}
.pendamping-editorial-st *, .pendamping-editorial-st *::before {{ box-sizing: border-box; }}
.pendamping-editorial-st .sesi-badan-st {{ max-width: none; padding: 0; margin: 0; background: transparent; }}
.pendamping-editorial-st .st-topbar {{
  border-bottom: 1px solid {T.BORDER_CATATAN}; padding: 0 0 {T.SP_4};
  margin-bottom: {T.SP_5}; gap: {T.SP_3}; background: transparent;
  height: auto; min-height: {T.TARGET_SENTUH}; position: relative; max-width: none;
}}
.pendamping-editorial-st .brand {{ text-decoration: none; }}
.pendamping-editorial-st .brand .nama {{ color: {T.AKSEN_TEAL_TUA}; font-size: 1.5rem; letter-spacing: -.04em; }}
.pendamping-editorial-st .topbar-navigasi {{ gap: {T.SP_2}; min-width: 0; }}
.pendamping-editorial-st .menu-pengguna {{ min-width: 0; }}
.pendamping-editorial-st .menu-pengguna summary {{
  min-height: {T.TARGET_SENTUH}; display: flex; align-items: center; gap: {T.SP_2};
  max-width: 18rem; overflow-wrap: anywhere; padding: {T.SP_2};
}}
.pendamping-editorial-st .menu-pengguna summary::after {{ content: '⌄'; flex: none; }}
.pendamping-editorial-st .badge-peran-guru {{ background: transparent; color: {T.TEKS_VARIAN}; }}
.pendamping-editorial-st :is(h1, h2, h3) {{ color: {T.TEKS_JUDUL}; }}
.pendamping-editorial-st h1 {{
  font: 800 clamp(1.6rem, 3vw, 2.25rem)/1.2 {T.FONT_HEADLINE};
  letter-spacing: -.045em; margin: 0; max-width: 40ch;
}}
.pendamping-editorial-st h2 {{ font: 700 1.22rem/1.4 {T.FONT_HEADLINE}; letter-spacing: -.025em; }}
.pendamping-editorial-st .editorial-kepala-st {{ display: block; margin: 0 0 {T.SP_5}; }}
.pendamping-editorial-st .editorial-alis-st {{
  color: {T.AKSEN_TEAL_TUA}; font: 700 .72rem/1.5 {T.FONT_LAYAR};
  letter-spacing: .14em; margin: 0 0 {T.SP_2};
}}
.pendamping-editorial-st :is(.sub, .sesi-sub-st) {{ color: {T.TEKS_VARIAN}; line-height: 1.65; }}
.pendamping-editorial-st :is(.jejak, .sesi-jejak-st) {{ margin: 0 0 {T.SP_3}; }}
.pendamping-editorial-st :is(.jejak, .sesi-jejak-st) a {{
  display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH};
  color: {T.AKSEN_TEAL_TUA}; font-size: .87rem; text-decoration: none;
}}
.pendamping-editorial-st a {{ color: {T.AKSEN_TEAL_TUA}; text-underline-offset: .2em; }}
.pendamping-editorial-st :is(a, button, input, select, textarea, summary, .tab-label-st):focus-visible {{
  outline: 3px solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; box-shadow: none;
}}
.pendamping-editorial-st :is(input:not([type=checkbox]):not([type=radio]):not([type=hidden]), select, textarea) {{
  min-height: {T.TINGGI_KONTROL}; max-width: 100%; min-width: 0;
  background: {T.LATAR_KARTU}; color: {T.TEKS_UTAMA};
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL};
  font: inherit; padding: {T.SP_2} {T.SP_3};
}}
.pendamping-editorial-st label {{ color: {T.TEKS_VARIAN}; font-size: .88rem; }}
.pendamping-editorial-st :is(.baris, .baris-aksi) {{ gap: {T.SP_3}; }}
.pendamping-editorial-st .baris > div {{ min-width: 0; }}
.pendamping-editorial-st :is(button, .btn, .st-tombol-coral, .rencana-cta-utama-st) {{
  min-height: {T.TINGGI_KONTROL}; border-radius: {T.RADIUS_KECIL};
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; box-shadow: none;
  font: 600 .92rem/1.4 {T.FONT_LAYAR}; white-space: normal;
}}
.pendamping-editorial-st :is(.st-tombol-coral, .tombol-coral, .rencana-cta-utama-st) {{ background: {T.AKSEN_KORAL_TUA}; }}
.pendamping-editorial-st :is(.st-tombol-coral, .tombol-coral, .rencana-cta-utama-st):hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.pendamping-editorial-st :is(.tombol-hapus, .tombol-kecil-st) {{ background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT}; border: 1px solid {T.BORDER_GALAT}; }}
.pendamping-editorial-st :is(.tombol-ikon-st, .tombol-mata) {{ background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA}; }}
.pendamping-editorial-st :is(.pil-sesi, .pil-sesi-st) {{
  display: flex; flex-wrap: wrap; gap: {T.SP_2}; padding: 0 0 {T.SP_3};
  border-bottom: 1px solid {T.BORDER_CATATAN}; margin: 0 0 {T.SP_5};
}}
.pendamping-editorial-st :is(.pil-sesi, .pil-sesi-st) a {{
  display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH};
  padding: {T.SP_2} {T.SP_3}; border: 1px solid transparent;
  border-radius: {T.RADIUS_KECIL}; color: {T.TEKS_VARIAN}; text-decoration: none;
}}
.pendamping-editorial-st :is(.pil-sesi, .pil-sesi-st) a.aktif {{
  background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; border-color: {T.AKSEN_TEAL_TUA};
}}
.pendamping-editorial-st :is(.kartu, .koreksi-kartu-st) {{
  border: 1px solid {T.BORDER_CATATAN}; border-radius: {T.RADIUS_KARTU};
  box-shadow: none; background: {T.LATAR_KARTU}; padding: {T.SP_5}; margin-bottom: {T.SP_5};
}}
.pendamping-editorial-st .kartu-judul {{ gap: {T.SP_2}; }}
.pendamping-editorial-st .ikon-kartu {{ display: none; }}
.pendamping-editorial-st :is(.kartu-stat, .ringkasan-dashboard-laporan) {{ box-shadow: none; }}
.pendamping-editorial-st .kartu-stat {{ background: transparent; border: 0; border-block: 1px solid {T.BORDER_CATATAN}; border-radius: 0; }}
.pendamping-editorial-st :is(.angka-besar, .stat-nilai-utama) {{ color: {T.AKSEN_TEAL_TUA}; }}
.pendamping-editorial-st :is(.stat-label, .kosong) {{ color: {T.TEKS_VARIAN}; }}
.pendamping-editorial-st .tabel-wrap {{ max-width: 100%; min-width: 0; }}
.pendamping-editorial-st table {{ width: 100%; }}
.pendamping-editorial-st th {{ background: {T.LATAR_CATATAN}; color: {T.TEKS_VARIAN}; }}
.pendamping-editorial-st td {{ border-color: {T.BORDER_CATATAN}; }}
.pendamping-editorial-st td a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; }}
.pendamping-editorial-st .status-ok {{ color: {T.AKSEN_TEAL_TUA}; }}
.pendamping-editorial-st .status-buruk {{ color: {T.AKSEN_KORAL_TUA}; }}
.pendamping-editorial-st details > summary {{ min-height: {T.TARGET_SENTUH}; cursor: pointer; }}
.pendamping-editorial-st :is(.kode.B, .kode.T, .kunci) {{ color: {T.TEKS_JUDUL}; }}
.pendamping-editorial-st :is(.st-badge.diagnostik, .mode-badge.diagnostik) {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; }}

.pendamping-editorial-st.profil-editorial-st {{ max-width: 62rem; }}
.profil-editorial-st .kepala-anak-st h1 .st-badge {{ display: inline-flex; vertical-align: middle; margin-left: {T.SP_2}; letter-spacing: 0; }}
.profil-editorial-st .kartu-rencana-st {{
  box-shadow: none;
  border: 1px solid {T.BORDER_CATATAN}; border-top: 3px solid {T.AKSEN_TEAL_TUA};
  background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_5}; gap: {T.SP_3};
}}
.profil-editorial-st .studio-layout-st {{
  display: grid; grid-template-columns: minmax(0, 1fr);
  grid-template-areas: "utama" "pendamping" "aksi" "alur";
  gap: {T.SP_3};
}}
.profil-editorial-st .studio-utama-st {{ grid-area: utama; display: grid; gap: {T.SP_3}; align-content: start; min-width: 0; }}
.profil-editorial-st .studio-pendamping-st {{
  grid-area: pendamping; display: flex; flex-direction: column; gap: {T.SP_3};
  min-width: 0;
}}
.profil-editorial-st .studio-aksi-st {{
  grid-area: aksi; display: grid; grid-template-columns: auto minmax(0, 1fr);
  align-items: center; align-self: start; gap: {T.SP_2} {T.SP_4};
  justify-items: start; min-width: 0;
}}
.profil-editorial-st .label-rencana-st {{ color: {T.AKSEN_TEAL_TUA}; }}
.profil-editorial-st #judul-rencana-belajar {{ font-size: clamp(1.25rem, 2.2vw, 1.6rem); letter-spacing: -.025em; max-width: 38ch; }}
.profil-editorial-st .alasan-rencana-st {{ font-size: 1.04rem; }}
.profil-editorial-st .identitas-sesi-rencana-st {{
  margin: 0; color: {T.TEKS_JUDUL}; font-weight: 600;
}}
.profil-editorial-st .konteks-pemetaan-jelas-st {{
  background: transparent; border: 0; border-block: 1px solid {T.BORDER_CATATAN};
  border-radius: 0; padding: {T.SP_3} 0;
}}
.profil-editorial-st .progres-rencana-st {{ margin: 0; padding: 0 0 {T.SP_4}; background: transparent; }}
.profil-editorial-st .progres-rencana-st::before {{
  content: "Posisi sekarang"; display: block; color: {T.TEKS_VARIAN};
  font: 500 .78rem/1.5 {T.FONT_LAYAR}; margin-bottom: {T.SP_1};
}}
.profil-editorial-st .tindakan-rencana-st {{
  margin: 0; padding: {T.SP_2} 0; border: 0;
  border-radius: 0; background: transparent;
}}
.profil-editorial-st .contoh-rencana-st {{ background: {T.LATAR_CATATAN}; border-color: {T.AKSEN_MURID_AMBER}; padding: {T.SP_4}; }}
.profil-editorial-st .tanggal-rencana-st {{ border-left: 3px solid {T.AKSEN_TEAL_TUA}; padding-left: {T.SP_4}; }}
.profil-editorial-st .alur-rencana-jelas-st {{
  grid-area: alur; margin: 0; padding: {T.SP_3} 0 0;
  border: 0; border-top: 1px solid {T.BORDER_CATATAN};
}}
.profil-editorial-st .isi-alur-rencana-st {{
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 {T.SP_5};
}}
.profil-editorial-st .isi-alur-rencana-st .strip-rencana-st {{
  grid-column: 1 / -1; display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr)); margin: {T.SP_3} 0;
}}
.profil-editorial-st .isi-alur-rencana-st > p {{ margin: 0; color: {T.TEKS_VARIAN}; }}
.profil-editorial-st .isi-alur-rencana-st > .progres-rencana-st {{ grid-column: 1 / -1; }}
.cetak-editorial-st .cerita-tambahan-st {{ margin-block: {T.SP_4}; padding-block: {T.SP_3}; border-block: 1px solid {T.BORDER_CATATAN}; }}
.cetak-editorial-st .cerita-tambahan-st > summary {{ min-height: {T.TARGET_SENTUH}; cursor: pointer; font-weight: 600; color: {T.AKSEN_TEAL_TUA}; }}
.cetak-editorial-st .cerita-tambahan-st > summary:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.AKSEN_TEAL_TUA}; outline-offset: 3px; }}
.profil-editorial-st .strip-rencana-st .tahap-rencana-st {{
  position: relative; text-align: center; padding: 1.7rem {T.SP_1} {T.SP_2};
  background: transparent; color: {T.TEKS_VARIAN}; border-radius: 0;
}}
.profil-editorial-st .strip-rencana-st .tahap-rencana-st::before {{
  content: ""; position: absolute; left: calc(50% - .31rem); top: .35rem;
  width: .62rem; height: .62rem; border: 2px solid {T.BORDER_VARIAN};
  background: {T.LATAR_KARTU}; border-radius: {T.RADIUS_BULAT}; z-index: 1;
}}
.profil-editorial-st .strip-rencana-st .tahap-rencana-st.aktif {{ font-weight: 700; color: {T.TEKS_JUDUL}; }}
.profil-editorial-st .strip-rencana-st .tahap-rencana-st.aktif::before {{ background: {T.AKSEN_TEAL_TUA}; border-color: {T.AKSEN_TEAL_TUA}; }}
.profil-editorial-st .strip-rencana-st .tahap-rencana-st:not(:last-child)::after {{
  content: ""; position: absolute; left: 50%; right: -50%; top: .73rem;
  height: 1px; background: {T.BORDER_VARIAN};
}}
.profil-editorial-st .rencana-form-st {{ display: inline-flex; align-self: start; }}
.profil-editorial-st .rencana-cta-utama-st {{
  width: auto; min-width: 16rem; align-self: start; padding-block: {T.SP_3};
}}
.profil-editorial-st .petunjuk-sesudah-cta-st {{ text-align: left; }}
.profil-editorial-st .ubah-fokus-st {{ margin-top: {T.SP_4}; }}
.profil-editorial-st .atur-latihan-st {{ background: transparent; border: 0; border-block: 1px solid {T.BORDER_CATATAN}; border-radius: 0; padding: {T.SP_3} 0; }}
.profil-editorial-st .atur-latihan-st summary {{ display: flex; align-items: center; gap: {T.SP_2}; color: {T.AKSEN_TEAL_TUA}; }}
.profil-editorial-st .atur-latihan-st summary::before {{ content: '+'; font-size: 1.2rem; }}
.profil-editorial-st .atur-latihan-st[open] summary::before {{ content: '−'; }}
.profil-editorial-st .atur-latihan-st > .buat-latihan-st > h2 {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }}
.profil-editorial-st .buat-latihan-st {{ box-shadow: none; padding-top: {T.SP_4}; }}
.profil-editorial-st .tab-label-st {{ white-space: normal; flex: 1 1 10rem; }}
.profil-editorial-st [data-panel="baru"] > .strip-sesi {{
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: {T.SP_4};
}}
.profil-editorial-st [data-panel="baru"] > .strip-sesi > * {{ grid-column: 1 / -1; min-width: 0; }}
.profil-editorial-st [data-panel="baru"] > .strip-sesi > .strip-kolom:nth-of-type(-n+2) {{ grid-column: auto; }}
.profil-editorial-st .strip-sesi select.st-input {{ width: 100%; max-width: 100%; }}
.profil-editorial-st .kepala-riwayat-st {{ align-items: center; gap: {T.SP_3}; flex-wrap: wrap; }}
.profil-editorial-st .tautan-laporan-st {{ min-height: {T.TARGET_SENTUH}; color: {T.AKSEN_TEAL_TUA}; }}
.profil-editorial-st .kartu-sesi-guru {{ border: 0; border-bottom: 1px solid {T.BORDER_CATATAN}; background: transparent; box-shadow: none; border-radius: 0; padding: {T.SP_4} 0; }}
.profil-editorial-st .judul-sesi-st {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; }}
.profil-editorial-st .badge-direview {{
  display: inline-block; max-width: 19rem; white-space: normal; overflow-wrap: anywhere;
  padding: {T.SP_1} {T.SP_2}; border-radius: {T.RADIUS_KECIL};
  font-size: .8rem; line-height: 1.5; color: {T.TEKS_VARIAN}; background: {T.LATAR_INTI};
}}
.profil-editorial-st .badge-direview.perlu {{ background: {T.LATAR_CATATAN}; color: {T.TEKS_JUDUL}; }}
.profil-editorial-st .badge-direview.sudah {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; }}
.profil-editorial-st .buat-latihan-st:has(#tab-baru:checked) [for=tab-baru],
.profil-editorial-st .buat-latihan-st:has(#tab-ulang:checked) [for=tab-ulang],
.profil-editorial-st .buat-latihan-st:has(#tab-gabungan:checked) [for=tab-gabungan] {{ color: {T.AKSEN_TEAL_TUA}; }}
.profil-editorial-st :is(.mode-opsi, .tab-label-st) {{ min-height: {T.TARGET_SENTUH}; }}
.profil-editorial-st .tab-radio-st:focus-visible + .tab-bar-st {{ outline: 3px solid {T.AKSEN_TEAL_TUA}; }}

.koreksi-editorial-st, .foto-editorial-st {{ max-width: 60rem; }}
.koreksi-editorial-st .koreksi-isi-st.sudah {{ opacity: 1; }}
.koreksi-editorial-st .status-sesi-st {{ background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN}; }}
.koreksi-editorial-st .koreksi-nomor-st {{ background: {T.AKSEN_TEAL_TUA}; box-shadow: none; }}
.koreksi-editorial-st .koreksi-tipe-st {{ background: transparent; padding-left: 0; }}
.koreksi-editorial-st .kunci-baris-st {{ background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN}; }}
.koreksi-editorial-st .pembahasan-soal-st {{ background: {T.LATAR_CATATAN}; }}
.koreksi-editorial-st .koreksi-centang-st {{ min-height: {T.TARGET_SENTUH}; }}
.koreksi-editorial-st .koreksi-centang-st label {{ padding-block: {T.SP_2}; }}
.pendamping-editorial-st .koreksi-simpan-st {{ background: {T.LATAR_MURID}; border-top: 1px solid {T.BORDER_CATATAN}; }}
.pendamping-editorial-st .koreksi-simpan-st button {{ background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH}; box-shadow: none; }}
.pendamping-editorial-st .koreksi-simpan-st button.sekunder {{ background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA}; border: 1px solid {T.BORDER_VARIAN}; }}
.koreksi-editorial-st .koreksi-simpan-st:has(button[formaction]) button:not([formaction]) {{ background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA}; border: 1px solid {T.BORDER_VARIAN}; }}
.koreksi-editorial-st .danger-zone-st {{ margin-top: {T.SP_6}; }}
.koreksi-editorial-st .danger-zone-st form {{ max-width: 34rem; }}
.koreksi-editorial-st .form-pembatalan-st {{
  display: grid; grid-template-columns: minmax(0, 1fr); justify-items: start;
  gap: {T.SP_2}; margin: {T.SP_3} 0 0;
}}
.koreksi-editorial-st .form-pembatalan-st label {{
  color: {T.TEKS_JUDUL}; font-weight: 700;
}}
.koreksi-editorial-st .form-pembatalan-st label span {{
  color: {T.TEKS_VARIAN}; font-weight: 500;
}}
.koreksi-editorial-st .form-pembatalan-st input {{
  box-sizing: border-box; width: 100%; min-height: {T.TINGGI_KONTROL};
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL};
  padding: {T.SP_2} {T.SP_3}; background: {T.LATAR_KARTU}; color: {T.TEKS_UTAMA};
  font: inherit;
}}
.koreksi-editorial-st .form-pembatalan-st .tombol-kecil-st {{
  width: auto; margin-top: {T.SP_1};
}}

.akun-editorial-st .layout-samping {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: {T.SP_5}; }}
.akun-editorial-st .nav-samping {{ position: static; display: flex; flex-direction: row; flex-wrap: wrap; gap: {T.SP_2}; padding-bottom: {T.SP_3}; border-bottom: 1px solid {T.BORDER_CATATAN}; }}
.akun-editorial-st .nav-samping a {{ display: inline-flex; min-height: {T.TARGET_SENTUH}; align-items: center; border-radius: {T.RADIUS_KECIL}; padding: {T.SP_2} {T.SP_4}; }}
.akun-editorial-st .nav-samping a.aktif {{ background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; }}
.akun-editorial-st .kartu:has(input[name=lama]) {{ max-width: 42rem; }}
.akun-editorial-st .baris-aksi {{ flex-wrap: wrap; }}
.akun-editorial-st .baris-aksi form {{ flex-wrap: wrap; max-width: 100%; margin-left: 0 !important; }}
.akun-editorial-st .input-sandi-kecil {{ width: 100%; }}
.akun-editorial-st td[data-label=Nama] {{ font-weight: 700; color: {T.TEKS_JUDUL}; }}
.akun-editorial-st .kartu:has(input[name=persetujuan_ortu]) form {{ max-width: 48rem; }}
.akun-editorial-st :is(th, td) {{ border: 0; border-bottom: 1px solid {T.BORDER_CATATAN}; vertical-align: top; }}
.akun-editorial-st .pengaturan-awal {{ border: 0; border-top: 1px solid {T.BORDER_CATATAN}; border-radius: 0; padding: {T.SP_4} 0 0; margin: {T.SP_5} 0; }}
.akun-editorial-st .pengaturan-awal legend {{ font-weight: 700; color: {T.TEKS_JUDUL}; padding-right: {T.SP_3}; }}
.akun-editorial-st .pengaturan-awal > p {{ margin-top: 0; }}
.akun-editorial-st .profil-petunjuk-st {{ display: block; margin-top: {T.SP_2}; color: {T.TEKS_VARIAN}; line-height: 1.6; }}
.akun-editorial-st .panduan-variasi {{ border: 0; border-radius: 0; padding: 0; margin: {T.SP_3} 0 0; }}
.akun-editorial-st .panduan-variasi > summary {{ color: {T.AKSEN_TEAL_TUA}; font-weight: 600; }}
.admin-editorial-st .kartu-stat-admin {{ margin-bottom: {T.SP_5}; }}
.admin-editorial-st .kartu:has(input[value=guru_hapus]) {{ border-color: {T.BORDER_GALAT}; }}
.laporan-editorial-st #perjalanan-belajar {{ border-top: 3px solid {T.AKSEN_TEAL_TUA}; }}
.laporan-editorial-st .ringkasan-dashboard-laporan {{ gap: {T.SP_5}; }}
.laporan-editorial-st .ringkasan-laporan {{ background: {T.LATAR_CATATAN}; }}
.laporan-editorial-st .chart-wrap {{ max-width: 44rem; margin-inline: auto; }}
.cetak-editorial-st .cetak-pilihan-st .btn {{ display: inline-flex; align-items: center; margin: 0 {T.SP_2} {T.SP_2} 0; }}
.cetak-editorial-st .cetak-pilihan-st .btn + .btn {{ background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA}; border: 1px solid {T.BORDER_VARIAN}; }}
.cetak-editorial-st .kartu-variasi {{ background: {T.LATAR_CATATAN}; }}
.lampiran-editorial-st .daftar-lampiran {{ padding: 0; list-style: none; }}
.lampiran-editorial-st .daftar-lampiran li {{ display: flex; align-items: center; gap: {T.SP_3}; flex-wrap: wrap; border-bottom: 1px solid {T.BORDER_CATATAN}; padding: {T.SP_3} 0; }}
.lampiran-editorial-st .daftar-lampiran a {{ min-height: {T.TARGET_SENTUH}; display: inline-flex; align-items: center; }}
.lampiran-editorial-st .blok-lampiran form {{ max-width: 42rem; padding-top: {T.SP_4}; }}
.lampiran-editorial-st input[type=file] {{ width: 100%; margin-bottom: {T.SP_3}; }}
.foto-editorial-st .pratinjau-foto-st {{ background: {T.LATAR_CATATAN}; }}
.foto-editorial-st .foto-lembar {{ max-height: 70vh; }}
.foto-editorial-st .baca-ulang-form button {{ width: auto; background: {T.LATAR_KARTU}; color: {T.AKSEN_TEAL_TUA}; }}
.foto-editorial-st .nomor {{ background: {T.AKSEN_TEAL_TUA}; }}
.foto-editorial-st .centang {{ min-height: {T.TARGET_SENTUH}; }}
.hapus-editorial-st {{ max-width: 48rem; }}
.hapus-editorial-st form {{ flex-wrap: wrap; }}
.hapus-editorial-st form a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; padding-inline: {T.SP_3}; }}

/* Studio kembali satu kolom sebelum ruang materi menjadi terlalu sempit. */
@media (max-width: 48rem) {{
  .profil-editorial-st .studio-layout-st {{ display: flex; flex-direction: column; }}
  .profil-editorial-st .studio-utama-st {{ order: 1; }}
  .profil-editorial-st .studio-pendamping-st {{ display: contents; }}
  .profil-editorial-st .tindakan-rencana-st {{ order: 2; padding: {T.SP_3} 0 {T.SP_3} {T.SP_4}; border: 0; border-left: 3px solid {T.BORDER_CATATAN}; }}
  .profil-editorial-st .studio-aksi-st {{ order: 3; grid-template-columns: minmax(0, 1fr); }}
  .profil-editorial-st .progres-rencana-st {{ order: 4; margin-top: {T.SP_1}; padding: {T.SP_4} 0 0; border-top: 1px solid {T.BORDER_CATATAN}; }}
  .profil-editorial-st .alur-rencana-jelas-st {{ order: 5; }}
  .profil-editorial-st .isi-alur-rencana-st {{ grid-template-columns: minmax(0, 1fr); }}
  .profil-editorial-st .isi-alur-rencana-st .strip-rencana-st {{ grid-template-columns: minmax(0, 1fr); }}
  .profil-editorial-st .isi-alur-rencana-st > p {{ margin-top: {T.SP_3}; }}
  .profil-editorial-st .strip-rencana-st .tahap-rencana-st {{ text-align: left; padding: {T.SP_1} 0 {T.SP_3} 1.7rem; }}
  .profil-editorial-st .strip-rencana-st .tahap-rencana-st::before {{ left: .18rem; top: .55rem; }}
  .profil-editorial-st .strip-rencana-st .tahap-rencana-st:not(:last-child)::after {{ left: .52rem; right: auto; top: 1.25rem; bottom: -.15rem; width: 1px; height: auto; }}
  .profil-editorial-st .rencana-cta-utama-st {{ width: 100%; min-width: 0; }}
  .profil-editorial-st [data-panel="baru"] > .strip-sesi {{ grid-template-columns: minmax(0, 1fr); }}
  .profil-editorial-st .tab-label-st {{ flex: 1 1 8rem; justify-content: center; text-align: center; }}
}}
@media (max-width: 40rem) {{
  .pendamping-editorial-st {{ width: 100%; max-width: 100%; padding: {T.SP_4} {T.SP_4} 3rem; overflow-x: clip; }}
  .pendamping-editorial-st.profil-editorial-st {{ width: 100%; max-width: 100%; margin-inline: 0; }}
  .pendamping-editorial-st .st-topbar {{ flex-wrap: wrap; }}
  .pendamping-editorial-st .topbar-navigasi {{ flex-wrap: wrap; margin-left: auto; justify-content: flex-end; }}
  .pendamping-editorial-st .badge-peran-guru {{ padding: 0; font-size: .7rem; }}
  .pendamping-editorial-st .menu-pengguna summary {{ max-width: 12rem; }}
  .pendamping-editorial-st :is(.kartu, .koreksi-kartu-st, .kartu-rencana-st) {{ padding: {T.SP_4}; }}
  .pendamping-editorial-st .baris {{ flex-direction: column; }}
  .pendamping-editorial-st .baris > div {{ width: 100%; }}
  .pendamping-editorial-st .kartu-stat {{ gap: {T.SP_2}; }}
  .pendamping-editorial-st .angka-besar {{ font-size: 1.7rem; }}
  .pendamping-editorial-st .stat-label {{ font-size: .78rem; }}
  .profil-editorial-st .kartu-sesi-guru {{ flex-wrap: wrap; }}
  .profil-editorial-st .aksi-sesi-st {{ width: 100%; flex-direction: row; align-items: center; justify-content: space-between; }}
  .pendamping-editorial-st:is(.akun-editorial-st, .admin-editorial-st) table {{ min-width: 0; }}
  .pendamping-editorial-st:is(.akun-editorial-st, .admin-editorial-st) tr {{ display: block; border-bottom: 1px solid {T.BORDER_CATATAN}; padding: {T.SP_3} 0; }}
  .pendamping-editorial-st:is(.akun-editorial-st, .admin-editorial-st) tr:has(th) {{ position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); padding: 0; }}
  .pendamping-editorial-st:is(.akun-editorial-st, .admin-editorial-st) td {{ display: block; border: 0; padding: {T.SP_2} 0; text-align: left; white-space: normal; }}
  .pendamping-editorial-st:is(.akun-editorial-st, .admin-editorial-st) td[data-label]::before {{ content: attr(data-label); display: block; font-size: .72rem; font-weight: 700; color: {T.TEKS_VARIAN}; margin-bottom: {T.SP_1}; }}
}}
.pendamping-editorial-st.bagikan-editorial-st {{ max-width: 48rem; }}
.bagikan-editorial-st .bagikan-kartu-st label {{ display: block; font-weight: 700; margin-bottom: {T.SP_2}; }}
.bagikan-editorial-st #tautan-sesi {{ width: 100%; font-size: .9rem; }}
.bagikan-editorial-st .bagikan-perhatian-st {{
  color: {T.TEKS_VARIAN}; background: {T.LATAR_CATATAN}; border-left: 3px solid {T.BORDER_CATATAN};
  padding: {T.SP_3}; margin-bottom: 0; font-size: .85rem;
}}
/* FIN WORKER A editorial scoped */

/* Pendamping inline dipakai lintas host yang hanya memuat GAYA_STITCH. */
.pendamping-inline {{ margin-top: {T.SP_5}; padding-top: {T.SP_4}; border-top: 1px solid {T.BORDER_VARIAN}; min-width: 0; }}
.akun-editorial-st .form-kelas-sekolah {{ display:flex; flex-direction:column; align-items:flex-start; gap:{T.SP_2}; }}
.akun-editorial-st .form-kelas-sekolah select {{ max-width:100%; margin:0; }}
.akun-editorial-st .form-kelas-sekolah button {{ min-height:{T.TINGGI_KONTROL}; margin:0; }}

.pendamping-inline > details > summary {{ min-height: {T.TARGET_SENTUH}; color: {T.AKSEN_TEAL_TUA}; font-weight: 700; cursor: pointer; }}
.pendamping-inline-isi {{ padding: {T.SP_3} 0 0; min-width: 0; }}
.pendamping-inline-isi h3 {{ margin: 0 0 {T.SP_2}; color: {T.TEKS_JUDUL}; }}
.pendamping-inline .pendamping-sumber, .pendamping-inline .pendamping-catatan {{ color: {T.TEKS_VARIAN}; font-size: .875rem; }}
.pendamping-inline textarea {{ display: block; width: 100%; min-height: 5.5rem; margin: {T.SP_2} 0; padding: {T.SP_3}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG}; font: inherit; resize: vertical; }}
.pendamping-inline button, .pendamping-inline a {{ min-height: {T.TARGET_SENTUH}; }}
.pendamping-inline .pendamping-tombol {{ display: inline-flex; align-items: center; justify-content: center; padding: {T.SP_2} {T.SP_4}; border: 1px solid {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_SEDANG}; background: {T.AKSEN_TEAL_TUA}; color: {T.TEKS_PUTIH}; font: inherit; font-weight: 700; cursor: pointer; }}
.pendamping-inline .pendamping-tombol:hover {{ background: {T.AKSEN_TEAL_HOVER}; border-color: {T.AKSEN_TEAL_HOVER}; }}
.pendamping-inline .pendamping-sekunder {{ background: transparent; color: {T.AKSEN_TEAL_TUA}; }}
.pendamping-inline button[hidden] {{ display: none; }}
.pendamping-inline button:disabled {{ opacity: .6; cursor: wait; }}
.pendamping-inline .pendamping-tautan {{ display: inline-flex; align-items: center; padding: {T.SP_2}; border: 0; background: transparent; color: {T.AKSEN_TEAL_TUA}; font: inherit; text-decoration: underline; cursor: pointer; }}
.pendamping-inline .pendamping-cek {{ display: flex; align-items: flex-start; gap: {T.SP_2}; width: 100%; min-height: {T.TARGET_SENTUH}; margin: {T.SP_3} 0; padding-block: {T.SP_2}; }}
.pendamping-inline .pendamping-cek input {{ width: 1.25rem; height: 1.25rem; flex: none; margin-top: .15rem; }}
.pendamping-inline-isi > form > .pendamping-tombol {{ display: flex; width: fit-content; margin-top: {T.SP_4}; clear: both; }}
.pendamping-inline-isi > form + form {{ margin-top: {T.SP_3}; }}
.pendamping-inline .pendamping-aksi {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; margin-top: {T.SP_3}; clear: both; }}
.pendamping-inline .pendamping-info, .pendamping-inline .pendamping-galat {{ padding: {T.SP_3}; border-inline-start: 3px solid {T.AKSEN_TEAL_TUA}; background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.pendamping-inline .pendamping-galat {{ border-color: {T.TEKS_GALAT}; color: {T.TEKS_GALAT}; }}
.pendamping-inline .pendamping-pesan {{ margin: {T.SP_4} 0; }}
.pendamping-inline .pendamping-pesan.pengguna {{ margin-inline-start: auto; max-width: 88%; padding: {T.SP_3}; border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.pendamping-inline .pendamping-peran {{ margin: 0 0 {T.SP_1}; font-size: .8125rem; color: {T.TEKS_VARIAN}; }}
.pendamping-inline .pendamping-teks {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.pendamping-inline .pendamping-transkrip, .pendamping-inline .pendamping-composer {{ width: 100%; max-width: {T.LEBAR_KONTEN}; }}
.pendamping-inline .pendamping-riwayat nav {{ display: grid; gap: {T.SP_1}; }}
.pendamping-inline .pendamping-riwayat button, .pendamping-inline .pendamping-riwayat a {{ padding: {T.SP_2}; border: 0; border-bottom: 1px solid {T.BORDER_VARIAN}; background: transparent; color: {T.AKSEN_TEAL_TUA}; text-align: left; font: inherit; }}
.pendamping-inline .pendamping-composer {{ display: grid; grid-template-columns: minmax(0, 1fr); gap: {T.SP_4}; min-width: 0; }}
.pendamping-inline .pendamping-composer textarea {{ min-height: 7.5rem; margin: 0; }}
.pendamping-inline .pendamping-composer .pendamping-tombol {{ width: fit-content; margin: 0 0 0 {T.SP_1}; }}
.pendamping-inline .pendamping-memori {{ margin-top: {T.SP_4}; }}
.pendamping-inline .pendamping-memori > summary {{ display: list-item; width: fit-content; min-height: {T.TARGET_SENTUH}; padding: {T.SP_1} 0; color: {T.AKSEN_TEAL_TUA}; background: transparent; border: 0; font-size: .875rem; font-weight: 600; cursor: pointer; }}
.pendamping-inline .pendamping-memori > summary::marker {{ color: {T.AKSEN_TEAL_TUA}; }}
.pendamping-inline .pendamping-memori > summary:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 3px; }}
.profil-editorial-st .atur-latihan-st .pendamping-inline .pendamping-memori > summary {{ display: list-item; min-height: {T.TARGET_SENTUH}; }}
.profil-editorial-st .atur-latihan-st .pendamping-inline .pendamping-memori > summary::before {{ content: none; }}
@media (max-width: 24rem) {{ .pendamping-inline .pendamping-pesan.pengguna {{ max-width: 96%; }} }}
"""
# diimpor utuh; dipanggil oleh halaman_sesi_stitch lewat gaya_stitch() + blok
# tambahan ini.
CSS_SESI = f"""
/* ── Halaman koreksi sesi guru /sesi/<id> — S5 adopsi Stitch ── */

.sesi-badan-st {{ max-width: {T.LEBAR_KONTEN}; margin: 0 auto; padding: {T.SP_4} 0.9rem 3rem; }}
.sesi-jejak-st {{ margin-bottom: {T.SP_3}; font-size:.9rem; }}
.sesi-jejak-st a {{ color: {T.AKSEN_MURID_UTAMA}; text-decoration: none; }}
.sesi-jejak-st a:hover {{ text-decoration: underline; }}

.sesi-judul-st {{
  font-family: {T.FONT_HEADLINE}; font-size: 1.5rem; font-weight: 800;
  color: {T.TEKS_JUDUL}; margin: 0 0 0.3rem; letter-spacing: -0.01em;
}}
.sesi-sub-st {{ font-size: .92rem; color: {T.TEKS_VARIAN}; margin: 0 0 {T.SP_1}; }}

/* Pill mode Latihan Cepat — class badge-mode dipertahankan supaya test drill
   tetap mengenalinya (marker kelas, bukan teks global). */
.badge-mode {{
  display: inline-block;
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: .72rem;
  background: {T.STATUS_LATIHAN_BG}; color: {T.STATUS_LATIHAN_TEKS};
  padding: 0.15rem 0.5rem; border-radius: {T.RADIUS_PIL};
  margin-left: 0.3rem; vertical-align: middle;
}}

/* Pesan flash (sukses setelah simpan). */
.pesan-st {{
  background: {T.LATAR_TERSIMPAN}; border: 1px solid {T.BORDER_TERSIMPAN};
  color: {T.TEKS_TERSIMPAN}; border-radius: {T.RADIUS_KARTU};
  padding: {T.SP_3} {T.SP_4}; margin: 0 0 {T.SP_4}; font-size: .95rem;
}}

/* Pil navigasi antar-alat sesi (Koreksi · Cetak · Lampiran). */
.pil-sesi-st {{
  display: flex; gap: {T.SP_2}; flex-wrap: wrap;
  margin: 0 0 {T.SP_4};
  border-bottom: 1px solid {T.BORDER_VARIAN}; padding-bottom: {T.SP_2};
}}
.pil-sesi-st a {{
  font-family: {T.FONT_HEADLINE}; font-weight: 600; font-size: .88rem;
  color: {T.TEKS_VARIAN}; text-decoration: none;
  padding: {T.SP_2} {T.SP_3}; border-radius: {T.RADIUS_SEDANG};
  border: 1px solid transparent; min-height: {T.TARGET_SENTUH};
  display: inline-flex; align-items: center; gap: {T.SP_1};
}}
.pil-sesi-st a:hover {{ background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_JUDUL}; }}
.pil-sesi-st a.aktif {{
  background: {T.LATAR_SEKUNDER_NETRAL}; color: {T.TEKS_JUDUL};
  border-color: {T.BORDER_VARIAN};
}}

/* Status alur sesi sebelum/ sesudah pengumpulan. */
.status-sesi-st {{
  display: flex; align-items: flex-start; gap: {T.SP_3};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_3} {T.SP_4};
  margin: 0 0 {T.SP_4}; border: 1px solid {T.BORDER_VARIAN};
  background: {T.LATAR_SEKUNDER_LEMBUT}; color: {T.TEKS_UTAMA};
}}
.status-sesi-st .material-symbols-outlined {{ color: {T.AKSEN_MURID_UTAMA}; flex: none; }}
.status-sesi-st b {{ font-family: {T.FONT_HEADLINE}; color: {T.TEKS_JUDUL}; }}
.status-sesi-st p {{ margin: {T.SP_1} 0 0; font-size: .9rem; color: {T.TEKS_VARIAN}; }}
.status-sesi-st.selesai {{
  background: {T.LATAR_TERSIMPAN}; border-color: {T.BORDER_TERSIMPAN};
}}

/* Pemulihan konfirmasi: ringkasan bertaut dan penanda nonwarna per soal. */
.koreksi-galat-st, .koreksi-masalah-st {{
  padding: {T.SP_4}; border: 1px solid {T.BORDER_CATATAN};
  border-left: 4px solid {T.AKSEN_KORAL_TUA}; border-radius: {T.RADIUS_SEDANG};
  background: {T.LATAR_CATATAN}; color: {T.TEKS_UTAMA}; overflow-wrap: anywhere;
}}
.koreksi-galat-st {{ margin-bottom: {T.SP_4}; }}
.koreksi-galat-st h2 {{ margin: 0; font: 700 1.15rem/1.4 {T.FONT_HEADLINE}; }}
.koreksi-galat-st p {{ margin: {T.SP_2} 0; line-height: 1.55; }}
.koreksi-galat-st ul {{ display: flex; flex-wrap: wrap; gap: {T.SP_2}; padding: 0; margin: {T.SP_3} 0 0; list-style: none; }}
.koreksi-galat-st a {{ display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3}; color: {T.AKSEN_TEAL_TUA}; background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL}; }}
.koreksi-galat-st a:focus-visible, .koreksi-kartu-st[tabindex]:focus {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 3px; }}
.koreksi-kartu-st[tabindex] {{ scroll-margin-top: {T.SP_6}; }}
.koreksi-masalah-st {{ margin: 0; font-size: .9rem; line-height: 1.55; }}

/* Kartu soal koreksi — satu kolom. Status menyatu dengan nomor dan jenis
   soal di kepala kartu agar hasil dapat dipindai tanpa menoleh ke sisi kanan. */
.koreksi-kartu-st {{
  background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU}; padding: {T.SP_4};
  margin-bottom: {T.SP_4}; position: relative;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
  display: flex; flex-direction: column; gap: {T.SP_4};
}}
.koreksi-isi-st {{ display: flex; flex-direction: column; gap: {T.SP_3}; }}
.koreksi-isi-st.sudah {{ opacity: .85; }}

/* Nomor, jenis soal, dan hasil koreksi dalam satu baris pemindaian. */
.koreksi-kepala-st {{ display: flex; align-items: center; gap: {T.SP_3}; flex-wrap: wrap; }}
.koreksi-nomor-st {{
  flex: none; width: 2rem; height: 2rem;
  background: {T.AKSEN_MURID_UTAMA}; color: {T.TEKS_PUTIH};
  border-radius: {T.RADIUS_BULAT}; border: 2px solid {T.LATAR_KARTU};
  display: inline-flex; align-items: center; justify-content: center;
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: .9rem;
  box-shadow: 0 2px 6px rgba(0,0,0,.18);
}}
.koreksi-tipe-st {{
  font-family: {T.FONT_HEADLINE}; font-size: .78rem; font-weight: 600;
  color: {T.TEKS_VARIAN}; background: {T.LATAR_SEKUNDER_NETRAL};
  padding: 0.15rem 0.5rem; border-radius: {T.RADIUS_PIL};
}}

.teks-soal-st {{ color: {T.TEKS_UTAMA}; line-height: 1.5; }}

.pembahasan-soal-st {{
  background: {T.LATAR_SEKUNDER_LEMBUT};
  border-left: 3px solid {T.AKSEN_MURID_UTAMA};
  border-radius: 0 {T.RADIUS_KECIL} {T.RADIUS_KECIL} 0;
  color: {T.TEKS_VARIAN}; font-size: .88rem; line-height: 1.45;
  padding: {T.SP_2} {T.SP_3};
}}
.pembahasan-soal-st b {{ color: {T.TEKS_JUDUL}; }}

.kunci-baris-st {{
  background: {T.LATAR_SEKUNDER_LEMBUT}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_2} {T.SP_3};
  font-size: .92rem;
}}
.kunci-baris-st .kunci-val {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; color: {T.TEKS_JUDUL};
  background: {T.LATAR_KARTU}; padding: 0.1rem 0.5rem;
  border-radius: {T.RADIUS_KECIL};
}}

/* Hierarki koreksi: jawaban, pendampingan, lalu penilaian. */
.koreksi-bukti-st {{ display: grid; gap: {T.SP_4}; grid-template-columns: minmax(0, 1fr); }}
.koreksi-bukti-st > div {{ min-width: 0; }}
@media (min-width: 40rem) {{
  .koreksi-bukti-st {{ grid-template-columns: minmax(8rem, 10rem) minmax(0, 1fr); }}
}}
.koreksi-bukti-st.koreksi-bukti-tunggal-st {{ grid-template-columns: minmax(0, 1fr); }}
.koreksi-bukti-tunggal-st .koreksi-input-st {{ max-width: 20rem; }}
.koreksi-ringkasan-catatan-st {{ display: block; margin-top: {T.SP_1}; font-size: .85rem; line-height: 1.55; color: {T.TEKS_VARIAN}; overflow-wrap: anywhere; }}
.koreksi-pendampingan-isi-st {{ min-width: 0; }}
.koreksi-pendampingan-isi-st .koreksi-pemahaman-st {{ margin-top: {T.SP_4}; }}
.koreksi-catatan-st {{ margin: {T.SP_2} 0 0; font-size: .85rem; line-height: 1.55; color: {T.TEKS_VARIAN}; }}
.koreksi-pemahaman-st {{ min-width: 0; margin: 0; padding: {T.SP_3} {T.SP_4}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG}; }}
.koreksi-pemahaman-st legend {{ font: 600 .85rem/1.5 {T.FONT_HEADLINE}; padding-inline: {T.SP_2}; color: {T.TEKS_JUDUL}; }}
.koreksi-pemahaman-st .koreksi-centang-st {{ margin-top: {T.SP_2}; }}
.koreksi-tanya-st {{ margin: 0 0 {T.SP_3}; color: {T.TEKS_JUDUL}; font-weight: 600; }}
.koreksi-radio-paham-st {{ min-width: 0; padding: 0; margin: 0; border: 0; }}
.koreksi-radio-paham-st legend {{ padding: 0; margin-bottom: {T.SP_2}; }}
.koreksi-pilihan-paham-grid-st {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: {T.SP_2}; }}
.koreksi-pilihan-paham-st {{ position: relative; min-width: 0; }}
.koreksi-pilihan-paham-st input {{ position: absolute; left: {T.SP_3}; top: 50%; transform: translateY(-50%); margin: 0; accent-color: {T.AKSEN_TEAL_TUA}; }}
.koreksi-pilihan-paham-st label {{ display: flex; align-items: center; min-height: {T.TARGET_SENTUH}; height: 100%; padding: {T.SP_2} {T.SP_3} {T.SP_2} {T.SP_6}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL}; background: {T.LATAR_KARTU}; color: {T.TEKS_JUDUL}; font-size: .85rem; line-height: 1.5; cursor: pointer; overflow-wrap: anywhere; }}
.koreksi-pilihan-paham-st input:checked + label {{ border-color: {T.AKSEN_TEAL_TUA}; background: {T.LATAR_SEKUNDER_LEMBUT}; font-weight: 600; }}
.koreksi-pilihan-paham-st input:focus-visible + label {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.koreksi-pemahaman-st .koreksi-centang-st label {{ min-height: {T.TARGET_SENTUH}; }}
.koreksi-perbaikan-st .koreksi-centang-st label {{ min-height: {T.TARGET_SENTUH}; }}
.koreksi-opsi-st {{ min-width: 0; }}
.koreksi-opsi-st summary {{ cursor: pointer; min-height: {T.TARGET_SENTUH}; padding-block: {T.SP_3}; font-size: .9rem; color: {T.AKSEN_TEAL_TUA}; }}
.koreksi-opsi-st summary:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.koreksi-opsi-st .pembahasan-soal-st {{ margin-top: {T.SP_2}; }}
.koreksi-simpan-st .koreksi-catatan-st {{ margin: 0; }}

/* Navigasi kandidat C tetap opsional: kartu dan form tidak bergantung padanya. */
.koreksi-editorial-st .antrean-tinjauan-st {{
  margin-bottom: {T.SP_5}; padding: {T.SP_4}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; background: {T.LATAR_KARTU};
}}
.koreksi-editorial-st .antrean-tinjauan-st h2 {{ font-size: 1.05rem; margin: 0 0 {T.SP_2}; }}
.koreksi-editorial-st .antrean-tinjauan-st p {{ margin: {T.SP_2} 0; }}
.koreksi-editorial-st .antrean-tinjauan-st ul {{
  display: flex; flex-wrap: wrap; gap: {T.SP_2}; padding: 0; margin: {T.SP_3} 0; list-style: none;
}}
.koreksi-editorial-st .antrean-tinjauan-st a {{
  display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH}; padding: {T.SP_2} {T.SP_3};
  color: {T.AKSEN_TEAL_TUA}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KECIL};
}}
.koreksi-editorial-st .antrean-tinjauan-st a:focus-visible,
.koreksi-editorial-st .koreksi-kartu-st[tabindex]:focus {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 3px; }}
.koreksi-editorial-st .koreksi-kartu-st[tabindex] {{ scroll-margin-top: {T.SP_6}; }}

/* Tinjauan progresif: kontrol di details tetap dikirim oleh form native. */
.koreksi-editorial-st .koreksi-pengantar-st {{ background: none; border: 0; padding: {T.SP_2} 0; margin-bottom: {T.SP_3}; }}
.koreksi-editorial-st .koreksi-lipat-st {{ display: block; padding: 0; box-shadow: none; }}
.koreksi-editorial-st .koreksi-lipat-st > summary {{
  cursor: pointer; min-height: {T.TARGET_SENTUH}; padding: {T.SP_4};
  color: {T.TEKS_JUDUL}; overflow-wrap: anywhere;
}}
.koreksi-lipat-st > summary:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
.koreksi-ringkas-kepala-st {{ display: inline-flex; align-items: center; gap: {T.SP_2}; flex-wrap: wrap; width: calc(100% - 2rem); vertical-align: middle; }}
.koreksi-ringkas-kepala-st .koreksi-tipe-st {{ background: none; padding: 0; font-size: 1rem; color: {T.TEKS_JUDUL}; }}
.koreksi-tindakan-st {{ margin-left: auto; font-size: .8rem; color: {T.TEKS_JUDUL}; background: {T.LATAR_CATATAN}; padding: {T.SP_1} {T.SP_2}; border-radius: {T.RADIUS_PIL}; }}
.koreksi-ringkas-hasil-st {{ display: block; margin: {T.SP_2} 0 0 {T.SP_6}; font-size: .85rem; color: {T.TEKS_VARIAN}; }}
.koreksi-lipat-st[open] > summary {{ border-bottom: 1px solid {T.BORDER_VARIAN}; }}
.koreksi-lipat-st[open] > summary .koreksi-ringkas-hasil-st {{ display: none; }}
.koreksi-editorial-st .koreksi-lipat-st > .koreksi-isi-st {{ padding: {T.SP_4}; opacity: 1; }}
.koreksi-lipat-st .koreksi-kepala-st {{ justify-content: flex-end; }}
.koreksi-lipat-st .koreksi-pendampingan-st {{ border-top: 1px solid {T.BORDER_VARIAN}; }}
.koreksi-lipat-st .koreksi-pemahaman-st {{ border: 0; padding: 0; }}
.koreksi-lipat-st .koreksi-pendampingan-st[open] > summary {{ padding-bottom: {T.SP_2}; }}
.koreksi-lipat-st .koreksi-lanjutan-st {{ border-top: 1px solid {T.BORDER_VARIAN}; }}
.koreksi-jawaban-utama-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_4}; overflow-wrap: anywhere; }}
.koreksi-jawaban-utama-st p {{ margin: 0; font-size: 1.35rem; font-weight: 700; color: {T.TEKS_JUDUL}; white-space: pre-wrap; }}
.koreksi-progres-st {{ padding: {T.SP_4}; margin-bottom: {T.SP_3}; background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_KARTU}; }}
.koreksi-progres-st h2 {{ font-size: 1.3rem; margin: {T.SP_2} 0; }}
.koreksi-progres-st progress {{ width: 100%; height: .6rem; accent-color: {T.AKSEN_TEAL_TUA}; }}
.koreksi-progres-st .editorial-alis-st {{ margin: 0; }}
.koreksi-ringkasan-sesi-st {{ margin-bottom: {T.SP_4}; }}
.koreksi-editorial-st .antrean-tinjauan-st {{ border: 0; background: none; padding: {T.SP_3} 0; margin-bottom: {T.SP_3}; }}
.koreksi-editorial-st .koreksi-tercatat-st {{ padding: {T.SP_3} {T.SP_4}; background: {T.LATAR_KARTU}; border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG}; margin-bottom: {T.SP_4}; }}
.koreksi-tercatat-st .koreksi-tindakan-st {{ background: {T.LATAR_SEKUNDER_LEMBUT}; }}
.koreksi-tercatat-st > p {{ margin-bottom: {T.SP_3}; }}
@media (max-width: 30rem) {{
  .koreksi-ringkas-kepala-st {{ align-items: flex-start; }}
  .koreksi-ringkas-kepala-st .koreksi-tindakan-st {{ margin-left: {T.SP_6}; }}
}}

/* Label kecil di kartu koreksi. */
.koreksi-label-st {{
  display: block; font-family: {T.FONT_HEADLINE}; font-weight: 600;
  font-size: .82rem; color: {T.TEKS_VARIAN}; margin: 0 0 {T.SP_2};
  display: flex; align-items: center; gap: {T.SP_1};
}}

.koreksi-input-st {{
  font: inherit; font-size: 1rem; min-height: {T.TINGGI_KONTROL};
  border-radius: {T.RADIUS_SEDANG}; border: 1px solid {T.BORDER_VARIAN};
  background: {T.LATAR_KARTU}; padding: 0 {T.SP_3}; width: 100%;
}}
.koreksi-input-st:focus {{
  border-color: {T.FOKUS_AKSEN}; outline: 0;
  box-shadow: 0 0 0 3px {T.AKSEN_MURID_UTAMA}55;
}}
.koreksi-select-st {{
  font: inherit; font-size: .95rem; min-height: {T.TINGGI_KONTROL};
  border-radius: {T.RADIUS_SEDANG}; border: 1px solid {T.BORDER_VARIAN};
  background: {T.LATAR_SEKUNDER_LEMBUT}; padding: 0 {T.SP_3}; width: 100%;
  cursor: pointer;
}}
.koreksi-select-st:focus {{
  border-color: {T.FOKUS_AKSEN}; outline: 0;
  box-shadow: 0 0 0 3px {T.AKSEN_MURID_UTAMA}55;
}}

.koreksi-textarea-st {{
  width: 100%; min-height: 56px;
  border: 1px solid {T.BORDER_VARIAN}; border-radius: {T.RADIUS_SEDANG};
  padding: .6rem; font-size: 1rem; font-family: inherit;
  background: {T.LATAR_SEKUNDER_LEMBUT};
}}
.koreksi-textarea-st:focus {{
  outline: none; border-color: {T.AKSEN_MURID_UTAMA};
  box-shadow: 0 0 0 3px rgba(15,163,163,0.18);
}}

.koreksi-centang-st {{
  display: flex; align-items: center; gap: .5rem;
  font-size: .9rem; color: {T.TEKS_VARIAN}; font-family: {T.FONT_HEADLINE};
}}
.koreksi-centang-st input {{ width: 1.3rem; height: 1.3rem; flex: none; accent-color: {T.AKSEN_MURID_UTAMA}; }}
.koreksi-centang-st label {{ margin: 0; cursor: pointer; }}

.info-anak-st {{
  background: {T.LATAR_SEKUNDER_LEMBUT}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_SEDANG}; padding: {T.SP_2} {T.SP_3};
  color: {T.TEKS_VARIAN}; font-size: .9rem; line-height: 1.45;
}}
.info-anak-label-st {{
  font-family: {T.FONT_HEADLINE}; font-weight: 700; color: {T.TEKS_JUDUL};
}}

.usulan-st {{
  background: {T.LATAR_SEKUNDER_NETRAL}; border-left: 3px solid {T.AKSEN_MURID_UTAMA};
  border-radius: 0 {T.RADIUS_KECIL} {T.RADIUS_KECIL} 0;
  padding: {T.SP_2} {T.SP_3}; font-size: .9rem; color: {T.TEKS_VARIAN};
  margin-top: {T.SP_2};
}}
.usulan-st.ragu {{ border-left-color: {T.AKSEN_KORAL_TUA}; }}
.usulan-st b {{ color: {T.TEKS_JUDUL}; }}

/* Status hasil koreksi menyatu dengan kepala kartu. */
.koreksi-status-st {{
  display: inline-flex; align-items: center; gap: {T.SP_1};
  margin-left: auto; padding: .25rem .65rem;
  border-radius: {T.RADIUS_PIL};
  font-family: {T.FONT_HEADLINE}; font-weight: 700; font-size: .78rem;
  white-space: nowrap;
}}
.koreksi-status-st .kode {{
  display: none;
  color: inherit; background: none; padding: 0; border: 0; font: inherit;
}}
/* Teks kode tetap ada sebagai marker kompatibilitas test lama, tetapi label
   ramah seperti "Tepat" dan "Salah hitung" menjadi satu-satunya teks visual. */
.koreksi-status-st.benar {{ background: {T.KODE_BENAR_BG}; color: {T.KODE_BENAR_TEKS}; }}
.koreksi-status-st.N {{ background: {T.KODE_MENEBAK_BG}; color: {T.KODE_MENEBAK_TEKS}; }}
.koreksi-status-st.K {{ background: {T.KODE_SALAH_KONSEP_BG}; color: {T.KODE_SALAH_KONSEP_TEKS}; }}
.koreksi-status-st.B {{ background: {T.KODE_SALAH_BACA_BG}; color: {T.TEKS_JUDUL}; }}
.koreksi-status-st.H {{ background: {T.KODE_SALAH_HITUNG_BG}; color: {T.KODE_SALAH_HITUNG_TEKS}; }}
.koreksi-status-st.E {{ background: {T.KODE_SALAH_TULIS_BG}; color: {T.KODE_SALAH_TULIS_TEKS}; }}
.koreksi-status-st.T {{ background: {T.KODE_BELUM_LIAT_BG}; color: {T.TEKS_JUDUL}; }}
.koreksi-status-label-st {{ font-weight: 600; }}
@media (max-width: 30rem) {{
  .koreksi-status-st {{ margin-left: 0; }}
}}

/* Simpan & diagnosis — tombol coral penuh. */
.koreksi-simpan-st {{
  display: grid; gap: {T.SP_2};
  position: sticky; bottom: 0; padding: {T.SP_3} 0 {T.SP_2};
  background: linear-gradient(to top, {T.LATAR_SEKUNDER_LEMBUT} 70%, transparent);
}}
.koreksi-simpan-st button {{
  width: 100%; font-size: 1.05rem; padding: .9rem;
  background: {T.AKSEN_KORAL_TUA}; color: {T.TEKS_PUTIH};
  border: 0; border-radius: {T.RADIUS_SEDANG};
  font-family: {T.FONT_HEADLINE}; font-weight: 700; cursor: pointer;
  min-height: {T.TINGGI_KONTROL};
  display: flex; align-items: center; justify-content: center; gap: {T.SP_2};
  box-shadow: 0 4px 12px rgba(255,107,91,.25);
}}
.koreksi-simpan-st button:hover {{ background: {T.AKSEN_KORAL_HOVER}; }}
.koreksi-simpan-st:has(button[formaction]) button:not([formaction]) {{
  background: {T.LATAR_KARTU}; color: {T.TEKS_UTAMA};
  border: 1px solid {T.BORDER_HALUS}; box-shadow: none;
}}

/* Varian putih (sekunder / tombol non-formaction saat ada formaction):
   hover memakai permukaan naik supaya tidak ikut koral. */
.koreksi-simpan-st button.sekunder:hover,
.koreksi-simpan-st:has(button[formaction]) button:not([formaction]):hover {{ background: {T.LATAR_ELEVASI}; }}

/* Satu area aksi sesi, tidak mengambang di atas kartu yang sedang dibaca. */
.koreksi-editorial-st .koreksi-simpan-st {{ position: static; padding: {T.SP_4} 0; gap: {T.SP_3}; }}
.koreksi-aksi-sesi-st {{ display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); gap: {T.SP_3}; }}
.koreksi-aksi-sesi-st button:focus-visible {{ outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 2px; }}
@media (max-width: 30rem) {{
  .koreksi-aksi-sesi-st {{ grid-template-columns: minmax(0, 1fr); }}
}}

/* Rencana belajar jelas — panduan sesi */
.panduan-sesi-st > div {{ flex: 1; min-width: 0; }}
.marker-status-lama-st {{ display: none; }}
.panduan-sesi-st form {{ margin: {T.SP_3} 0 0; }}
.panduan-sesi-st button,
.panduan-rencana-st {{
  display: inline-flex; align-items: center; justify-content: center;
  min-height: {T.TINGGI_KONTROL}; padding: {T.SP_2} {T.SP_4};
  border-radius: {T.RADIUS_SEDANG}; font: 700 .9rem/1.4 {T.FONT_HEADLINE};
  cursor: pointer; text-decoration: none;
}}
.pendamping-editorial-st .panduan-sesi-st .panduan-aksi-utama-st button,
.panduan-rencana-st {{
  color: {T.TEKS_PUTIH}; background: {T.AKSEN_KORAL_TUA};
  border: 1px solid {T.AKSEN_KORAL_TUA};
}}
.pendamping-editorial-st .panduan-sesi-st .panduan-aksi-sekunder-st button {{
  color: {T.TEKS_JUDUL}; background: {T.LATAR_KARTU};
  border: 1px solid {T.BORDER_VARIAN};
}}
.panduan-rencana-st {{ margin: 0 0 {T.SP_4}; }}
.panduan-pratinjau-st,
.panduan-edit-hasil-st {{
  margin: 0 0 {T.SP_4}; border: 1px solid {T.BORDER_VARIAN};
  border-radius: {T.RADIUS_KARTU}; background: {T.LATAR_SEKUNDER_LEMBUT};
  padding: {T.SP_3} {T.SP_4};
}}
.panduan-pratinjau-st summary,
.panduan-edit-hasil-st summary {{
  min-height: {T.TARGET_SENTUH}; padding-block: {T.SP_2};
  color: {T.TEKS_JUDUL}; font: 700 .9rem/1.4 {T.FONT_HEADLINE}; cursor: pointer;
}}
.panduan-pratinjau-st summary::marker,
.panduan-edit-hasil-st summary::marker {{ color: {T.AKSEN_TEAL_TUA}; }}
.panduan-pratinjau-st summary:focus-visible,
.panduan-edit-hasil-st summary:focus-visible {{
  outline: {T.TEBAL_FOKUS} solid {T.FOKUS_AKSEN}; outline-offset: 3px;
}}
.panduan-pratinjau-st > .sub,
.panduan-edit-hasil-st > .sub {{ color: {T.TEKS_VARIAN}; font-size: .85rem; }}
.panduan-pratinjau-st .koreksi-kartu-st:first-of-type,
.panduan-edit-hasil-st .koreksi-kartu-st:first-of-type {{ margin-top: {T.SP_3}; }}

/* Danger zone hapus sesi. */
.danger-zone-st {{
  margin-top: 1.2rem; border-top: 1px solid {T.BORDER_GALAT}; padding-top: .7rem;
}}
.danger-zone-st p.sub {{ margin: 0 0 .4rem; font-size: .85rem; color: {T.TEKS_VARIAN}; }}
.tombol-kecil-st {{
  font: inherit; font-family: {T.FONT_HEADLINE}; font-size: .85rem;
  background: {T.LATAR_GALAT}; color: {T.TEKS_GALAT};
  border: 1px solid {T.BORDER_GALAT}; border-radius: {T.RADIUS_SEDANG};
  padding: .5rem {T.SP_4}; cursor: pointer;
  min-height: {T.TARGET_SENTUH};
}}
/* Varian kecil berlatar galat lembut: tidak ada token hover yang aman
   (menggelapkan latar menurunkan kontras TEKS_GALAT); kecerahan tipis
   sengaja dipertahankan. */
.tombol-kecil-st:hover {{ filter: brightness(1.04); }}

/* Cetak. */
@media print {{
  .sesi-badan-st {{ max-width: none; padding: 0; }}
  .st-topbar, .koreksi-simpan-st, .pil-sesi-st, .danger-zone-st, .hanya-layar {{ display: none; }}
  .koreksi-kartu-st {{ break-inside: avoid; box-shadow: none; border-color: #000; flex-direction: column; }}
  .koreksi-status-st {{ border: 0; }}
}}

"""


from choice_pages import gaya_pilihan
GAYA_STITCH += gaya_pilihan()


def gaya_stitch() -> str:
    """
    Kembalikan string CSS lengkap untuk halaman yang difase-in ke Stitch.
    Dipakai oleh fungsi render halaman versi '_baru' di file-file yang ada.
    """
    return GAYA_STITCH


if __name__ == "__main__":
    # quick lint: unmatched braces?
    css = GAYA_STITCH
    open_count = css.count("{") + css.count("{{") / 2
    close_count = css.count("}") + css.count("}}") / 2
    print("fstring-open:", css.count("{"), "output-open:", GAYA_STITCH.count("{"), "len:", len(GAYA_STITCH))
