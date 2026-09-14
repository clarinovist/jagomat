"""Gaya layar guru — CSS untuk 5 halaman guru (dashboard, sesi, laporan, akun, masuk).

Dipecah dari web.py (restyle 29 Aug 2026). Mengikuti mockup guru (guru-*.png):
cream hangat #FFF8EE + teal #0FA3A3 + coral #FF6B5B + amber #FFB020 — palet
yang SAMA dengan permukaan murid. Keputusan desain (29 Aug): guru dan murid
berbagi palet hangat; yang membedakan hanyalah kepadatan data. Guru butuh
konsentrasi, jadi kartu tetap netral putih di atas cream, dengan biru tua
#16213e untuk judul — persis murid.

Nilai visual dipusatkan di design_tokens.py — ubah di sana, efek ke semua
permukaan. Jangan hardcode hex literal di sini; selalu rujuk T.NAMA_TOKEN.

Kelas yang didefinisikan di sini harus mencakup SEMUA kelas yang dipakai
halaman guru di web.py (.kartu, .soal-kartu, .kode, .usulan, table, ...)
supaya tidak ada gaya patah. Daftar dipetakan dari fungsi halaman_* di
Bingkai aktif: halaman_utama_stitch, halaman_sesi_stitch, halaman_laporan, halaman_akun,
_halaman_masuk, _kartu_akun_murid, _tombol_cerita, _halaman.
"""

import design_tokens as T
from presentation_style import GAYA_PENYAJIAN

GAYA_GURU = f"""
{GAYA_PENYAJIAN}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  font-family: {T.FONT_LAYAR};
  font-size: {T.UKURAN_BADAN_LAYAR}; line-height: {T.LINE_HEIGHT};
  color: {T.TEKS_UTAMA}; margin: 0; background: {T.LATAR_MURID};
}}
.bungkus {{ max-width: 960px; margin: 0 auto; padding: {T.SP_4} 0.9rem 3rem; }}
a {{ color: {T.AKSEN_TEAL_TUA}; }}
h1 {{ font-size: 1.5rem; margin: 0.3rem 0 0.3rem; color: {T.TEKS_JUDUL}; }}
h2 {{ font-size: 1.15rem; margin: 1.4rem 0 0.6rem; color: {T.TEKS_JUDUL}; }}
.sub {{ color: {T.TEKS_SUBTLE}; font-size: .9rem; margin: 0 0 1.3rem; }}
.jejak {{ font-size: .88rem; margin: 0 0 0.8rem; color: {T.TEKS_SUBTLE}; }}
.jejak a {{ color: {T.TEKS_SUBTLE}; text-decoration: none; }}
.jejak a:hover {{ color: {T.AKSEN_TEAL_TUA}; }}

/* ── Kartu ─────────────────────────────────────────────────────────── */
.kartu {{
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU}; padding: 1rem 1.1rem; margin-bottom: 1rem;
  box-shadow: 0 1px 3px rgba(22,33,62,0.04);
}}
.kartu h2 {{ margin-top: 0; }}

/* ── Tombol ────────────────────────────────────────────────────────── */
/* Latar tombol solid memakai aksen versi teks-aman: teks putih di atas
   teal/coral terang hanya 3.1:1 / 2.8:1 — di bawah ambang 4.5:1 teks
   berukuran normal. Warna tetap satu rasa, hanya lebih dalam. */
button {{
  background: {T.AKSEN_TEAL_TUA}; color: #fff; border: 0;
  border-radius: 9px; padding: .7rem 1.2rem; font-size: 1rem; cursor: pointer;
}}
button:hover {{ filter: brightness(0.94); }}
button.tombol-sekunder {{
  background: {T.LATAR_KARTU_SEKUNDER}; color: {T.TEKS_JUDUL};
  border: 1px solid {T.BORDER_INTERAKTIF};
}}
button.tombol-coral {{ background: {T.AKSEN_KORAL_TUA}; }}
/* Tombol cerita (amber): teks amber di atas putih 1.9:1 tidak terbaca —
   pakai pasangan badge amber yang sudah lolos kontras (Pengelola). */
button.tombol-amber {{
  background: {T.BADGE_ADMIN_BG}; color: {T.BADGE_ADMIN_TEKS};
}}
button.tombol-kecil {{ padding: .35rem .7rem; font-size: .82rem; border-radius: 6px; }}
button.tombol-putih {{
  background: #fff; color: {T.TEKS_JUDUL}; border: 1px solid {T.BORDER_KUAT};
}}
.btn {{
  display: inline-block; padding: .55rem 1rem; border-radius: 8px;
  font-size: .9rem; text-decoration: none; background: {T.LATAR_KARTU_SEKUNDER};
  color: {T.TEKS_JUDUL}; border: 1px solid {T.BORDER_INTERAKTIF};
}}
.btn.utama {{ background: {T.AKSEN_TEAL_TUA}; color: #fff; border: 0; }}
.btn.coral {{ background: {T.AKSEN_KORAL_TUA}; color: #fff; border: 0; }}

/* Keadaan mati: tombol/isi yang dinonaktifkan (fieldset admin, auto-lock
   timer drill, tombol tanpa siswa) harus TERLIHAT mati, bukan sekadar
   tak bereaksi. */
button:disabled {{
  opacity: .55; cursor: not-allowed; filter: none;
}}
input:disabled, textarea:disabled, select:disabled {{
  background: #f3f4f6; color: {T.TEKS_SUBTLE};
  border-color: {T.BORDER_HALUS}; cursor: not-allowed;
}}

/* ── Header halaman guru (mockup guru-dashboard) ───────────────────── */
.topbar {{
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 1rem; padding: 0.6rem 0 0.2rem; margin-bottom: 0.4rem;
  border-bottom: 1px solid {T.BORDER_HALUS};
}}
.brand {{
  font-weight: 800; font-size: 1.15rem; color: {T.WARNA_WORDMARK};
  display: flex; align-items: center; gap: .55rem;
}}
/* Lambang brand memakai token, bukan angka lepas: sebelum ini ikon yang
   sama dirender 34px di sini dan ~21px di style_stitch. */
.brand img {{ width: {T.LOGO_TOPBAR}; height: {T.LOGO_TOPBAR}; flex: none; }}
.topbar-navigasi {{ display: flex; align-items: center; gap: .7rem; }}
.topbar-navigasi a {{ color: {T.TEKS_SUBTLE}; text-decoration: none; font-size: .9rem; }}
.topbar-navigasi a:hover {{ color: {T.AKSEN_TEAL_TUA}; }}
.topbar-navigasi form {{ margin: 0; }}
.badge-peran {{
  display: inline-block; padding: .12rem .55rem; border-radius: {T.RADIUS_PIL};
  font-size: .7rem; font-weight: 700; letter-spacing: .02em;
  vertical-align: middle;
}}
.badge-peran-admin {{ background: {T.BADGE_ADMIN_BG}; color: {T.BADGE_ADMIN_TEKS}; }}
.badge-peran-guru {{ background: {T.BADGE_GURU_BG}; color: {T.BADGE_GURU_TEKS}; }}
.badge-keluarga {{
  display: inline-block; margin-left: .45rem; padding: .1rem .5rem;
  border-radius: {T.RADIUS_PIL}; font-size: .72rem; font-weight: 600;
  background: {T.LATAR_KARTU_SEKUNDER}; color: {T.TEKS_JUDUL};
  border: 1px solid {T.BORDER_INTERAKTIF};
}}

/* ── Menu pengguna dropdown (CSS-only) ────────────────────────────── */
.menu-pengguna {{ position: relative; }}
.menu-pengguna summary {{
  display: flex; align-items: center; gap: .4rem;
  padding: .35rem .7rem; border: 1px solid {T.BORDER_INTERAKTIF};
  border-radius: 8px; cursor: pointer; font-size: .9rem;
  color: {T.TEKS_JUDUL}; background: none; list-style: none;
}}
.menu-pengguna summary::-webkit-details-marker {{ display: none; }}
.menu-pengguna[open] summary {{ border-color: {T.AKSEN_MURID_UTAMA}; }}
.menu-isi {{
  position: absolute; right: 0; top: calc(100% + .4rem);
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU};
  box-shadow: 0 8px 24px rgba(0,0,0,.08);
  min-width: 12rem; max-width: min(12rem, calc(100vw - 1.2rem)); padding: .4rem; z-index: 20;
  display: flex; flex-direction: column;
}}
.menu-isi a, .menu-isi button {{
  display: block; width: 100%; text-align: left;
  padding: .45rem .6rem; border-radius: 6px; background: none; border: none;
  color: {T.TEKS_JUDUL}; text-decoration: none; font-size: .9rem;
  cursor: pointer; font-family: inherit;
}}
.menu-isi a:hover, .menu-isi button:hover {{ background: {T.LATAR_KARTU_SEKUNDER}; }}
.menu-pisah {{ border-top: 1px solid {T.BORDER_HALUS}; margin: .3rem 0; }}

/* ── Sidebar halaman /akun ────────────────────────────────────────── */
.layout-samping {{
  display: grid; grid-template-columns: 13rem 1fr;
  gap: 1.2rem; align-items: start;
}}
.nav-samping {{
  display: flex; flex-direction: column; gap: .25rem;
  position: sticky; top: 1rem;
}}
.nav-samping a {{
  padding: .5rem .7rem; border-radius: 8px; text-decoration: none;
  color: {T.TEKS_SUBTLE}; font-size: .92rem; border: 1px solid transparent;
}}
.nav-samping a.aktif {{
  color: {T.AKSEN_TEAL_TUA}; border-color: {T.BORDER_HALUS};
  font-weight: 600; background: {T.LATAR_KARTU_SEKUNDER};
}}
@media (max-width: 46rem) {{
  .layout-samping {{ grid-template-columns: 1fr; }}
  .nav-samping {{ flex-direction: row; flex-wrap: wrap; position: static; }}
}}

/* Band per anak (dashboard keluarga): satu anak satu baris penuh. Dulu
   1fr 1fr memaksa dua kartu berdampingan — tabel 7 kolom terjepit di
   ±460px (tanggal dan nomor sesi wrap dua baris) sementara form
   buat-sesi yang jarang datanya justru memakan tinggi kartu. Band penuh
   memberi tabel ruang; form cukup jadi strip ringkas (.strip-sesi). */
.daftar-anak {{ display: grid; gap: 1.2rem; }}
.kolom-sesi, .kolom-tanggal {{ white-space: nowrap; }}

/* Strip buat-sesi: satu baris di bawah tabel, tombol tidak lagi
   memakan lebar penuh kartu. Pengaturan timer mengambil satu baris
   sendiri saat muncul (mode Latihan Cepat). */
.strip-sesi {{
  display: flex; flex-wrap: wrap; gap: .7rem 1.2rem; align-items: flex-end;
  margin-top: .8rem; padding-top: .8rem;
  border-top: 1px dashed {T.BORDER_HALUS};
}}
.strip-sesi .strip-kolom {{ display: flex; flex-direction: column; gap: .2rem; }}
.strip-sesi label {{ margin: 0; }}
.strip-sesi select {{
  flex: 1; min-width: 10rem; max-width: 100%;
}}
@media (max-width: 30rem) {{
  .strip-sesi select {{ min-width: 0; }}
}}
.strip-sesi .pengaturan-timer {{ flex-basis: 100%; }}
.strip-sesi button {{ padding: .55rem 1.2rem; }}
.badge-tingkat {{
  font-size: .78rem; font-weight: 700; color: {T.AKSEN_TEAL_TUA};
  background: {T.LATAR_KARTU_SEKUNDER}; padding: .15rem .5rem;
  border-radius: {T.RADIUS_PIL}; margin-left: .3rem;
}}
/* Penanda "Latihan Cepat" memakai pasangan badge amber (sama dengan badge
   Pengelola): coral terang di atas hijau muda hanya ~2.6:1. */
.badge-mode {{
  font-size: .78rem; font-weight: 700; color: {T.BADGE_ADMIN_TEKS};
  background: {T.BADGE_ADMIN_BG};
  padding: .12rem .5rem; border-radius: {T.RADIUS_PIL}; white-space: nowrap;
}}
.kosong-hint-guru {{
  border: 1.5px dashed {T.BORDER_HALUS}; text-align: center;
  color: {T.TEKS_SUBTLE}; font-size: 1rem; padding: 2.5rem;
}}

/* ── Tabel ─────────────────────────────────────────────────────────── */
table {{ width: 100%; border-collapse: collapse; background: #fff; }}
th, td {{
  border: 1px solid {T.BORDER_HALUS}; padding: .5rem .6rem; text-align: left;
  font-size: .88rem;
}}
th {{ background: {T.LATAR_KARTU_SEKUNDER}; color: {T.TEKS_JUDUL}; font-weight: 600; }}
.angka {{ text-align: right; font-variant-numeric: tabular-nums; }}
.kosong {{ color: {T.TEKS_SUBTLE}; font-style: italic; }}
.tipe {{ color: {T.TEKS_SUBTLE}; font-size: .82rem; }}
.tabel-wrap {{
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-x: contain;
  scrollbar-width: thin;
}}
/* Hint scroll halus — bayangan kanan tipis agar user tahu tabel bisa digeser */
.tabel-wrap table {{ min-width: 480px; }}
/* Sesi baru: baris disorot 1x di dashboard (opsi 1 — tanpa lompat ke /sesi/). */
tr.sorot-baru td {{
  background: {T.BADGE_GURU_BG}; color: {T.BADGE_GURU_TEKS};
}}
tr.sorot-baru a {{ color: #fff; text-decoration: underline; }}
@media (prefers-reduced-motion: no-preference) {{
  tr.sorot-baru {{ animation: sorot-masuk 1.4s ease-out; }}
  @keyframes sorot-masuk {{
    0% {{ filter: brightness(1.4); }}
    100% {{ filter: none; }}
  }}
}}
/* Pil navigasi sesi (opsi 3): Koreksi · Cetak & Cerita · Lampiran */
.pil-sesi {{ display: flex; gap: .6rem; flex-wrap: wrap; margin: .6rem 0 1rem; }}
.pil-sesi .pil {{
  display: inline-block; padding: .35rem .75rem; border-radius: {T.RADIUS_PIL};
  border: 1px solid {T.BORDER_HALUS}; background: #fff; color: {T.TEKS_SUBTLE};
  text-decoration: none; font-size: .88rem;
}}
.pil-sesi .pil.aktif {{
  background: {T.AKSEN_TEAL_TUA}; color: #fff; border-color: {T.AKSEN_TEAL_TUA};
}}
.pil-sesi .pil:hover {{ border-color: {T.AKSEN_TEAL_TUA}; }}

/* ── Form ──────────────────────────────────────────────────────────── */
label {{ display: block; font-size: .84rem; color: {T.TEKS_SUBTLE}; margin: .55rem 0 .2rem; }}
/* font-size 1rem, bukan .95rem: di iOS fokus pada input < 16px memicu
   zoom viewport otomatis dan merusak layout. type=number & type=file
   ikut diatur — dulu keduanya tak tersentuh sehingga memakai ukuran
   bawaan peramban (dan ikut memicu zoom). */
input[type=text], input[type=password], input[type=number], input[type=file],
textarea, select {{
  width: 100%; padding: .5rem .6rem; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KECIL}; font-size: 1rem; font-family: inherit;
  background: #fff; color: {T.TEKS_UTAMA};
}}
input[type=text]:focus, input[type=password]:focus, input[type=number]:focus,
textarea:focus, select:focus {{
  outline: none; border-color: {T.AKSEN_MURID_UTAMA};
  box-shadow: 0 0 0 2px rgba(15,163,163,0.12);
}}
textarea {{ min-height: 3.2rem; resize: vertical; }}
.baris {{ display: flex; gap: .8rem; flex-wrap: wrap; }}
.baris > * {{ flex: 1; min-width: 180px; }}
@media (max-width: 30rem) {{ .baris > * {{ min-width: 0; }} }}

/* ── Tombol mata pada kolom sandi (lihat/sembunyikan) ──────────────── */
/* Input dibungkus .kolom-sandi oleh SKRIP_MATA_SANDI. padding-right
   penting: input "sandi baru" di tabel akun memakai style inline. */
.kolom-sandi {{ position: relative; }}
.kolom-sandi > input {{ padding-right: 3rem !important; }}
.tombol-mata {{
  position: absolute; top: 50%; right: .3rem; transform: translateY(-50%);
  width: 2.75rem; height: 2.75rem; display: inline-flex; align-items: center;
  justify-content: center; padding: 0; border: none; background: none;
  color: {T.TEKS_SUBTLE}; cursor: pointer; border-radius: {T.RADIUS_KECIL};
}}
.tombol-mata:hover {{ color: {T.TEKS_UTAMA}; }}
.tombol-mata svg {{ display: block; }}

/* ── Pilihan mode & batas waktu saat buat sesi ──────────────────────── */
.mode-pilih {{ display: flex; flex-wrap: wrap; gap: .4rem 1rem; margin-top: .2rem; }}
.mode-opsi {{ display: flex; align-items: center; gap: .4rem; font-size: .88rem;
  color: {T.TEKS_UTAMA}; margin: 0; }}
.mode-opsi input {{ width: auto; margin: 0; }}
.mode-teks {{ display: flex; flex-direction: column; gap: .15rem; }}
.mode-desk {{ color: {T.TEKS_SUBTLE}; font-size: .82rem; font-weight: 400; }}
.pengaturan-timer {{
  display: flex; flex-basis: 100%; margin: 0;
  border: 1.5px dashed {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL};
  padding: .55rem .7rem; background: {T.LATAR_KARTU_MURID};
  flex-direction: column; gap: .5rem;
}}
.rincian-timer {{ display: flex; flex-direction: column; gap: .55rem; }}
@supports selector(:has(*)) {{
  .pengaturan-timer {{ display: none; }}
  .strip-sesi:has(input[name=mode][value=drill]:checked) .pengaturan-timer {{
    display: flex;
  }}
  .rincian-timer {{ display: none; }}
  .pengaturan-timer:has(.timer-toggle input:checked) .rincian-timer {{ display: flex; }}
}}
.pengaturan-timer > legend, .akibat-timer > legend {{
  padding: 0 .25rem; color: {T.TEKS_SUBTLE}; font-size: .82rem;
  font-weight: 600;
}}
.durasi-timer {{ display: flex; flex-wrap: wrap; align-items: center; gap: .4rem; }}
.durasi-timer small {{ flex-basis: 100%; color: {T.TEKS_SUBTLE}; font-size: .78rem; }}
.akibat-timer {{ display: flex; flex-direction: column; gap: .4rem; margin: 0;
  padding: .45rem; border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL}; }}
.pengaturan-timer input[name=durasi_menit] {{ padding: .3rem .45rem; width: 4.5rem; }}

/* ── Halaman sesi: kartu soal (mockup guru-sesi) ───────────────────── */
.peta {{ margin-bottom: 1rem; }}
.soal-kartu {{ border-left: 4px solid {T.BORDER_HALUS}; }}
.soal-kartu.sudah {{ border-left-color: {T.STATUS_KUAT}; }}
.soal-kartu.perlu {{ border-left-color: {T.STATUS_LEMAH}; }}
.kartu-kepala {{
  display: flex; align-items: center; gap: .55rem; margin-bottom: .5rem;
}}
.nomor {{
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 2.1rem; height: 2.1rem; font-weight: 700; font-size: .95rem;
  background: {T.AKSEN_TEAL_TUA}; color: #fff;
  border-radius: {T.RADIUS_BULAT};
}}
.teks-soal {{
  background: {T.LATAR_KARTU_SEKUNDER}; border: 1px solid {T.BORDER_INTERAKTIF};
  border-radius: {T.RADIUS_KECIL}; padding: .55rem .7rem; margin: .4rem 0;
  white-space: pre-wrap; font-size: .93rem;
}}
/* Kunci jawaban adalah data yang dibaca terus: amber terang #FFB020 di
   atas putih 1.9:1 tidak layak — pakai versi amber teks-aman. */
.kunci {{ font-weight: 700; color: {T.KODE_SALAH_BACA_TEKS}; }}
.centang {{
  display: flex; align-items: center; gap: .45rem; margin-top: .55rem;
  font-size: .88rem; color: {T.TEKS_SUBTLE};
}}
.centang input {{ width: auto; }}
.usulan {{
  background: {T.LATAR_KARTU_SEKUNDER}; border: 1px solid {T.BORDER_INTERAKTIF};
  border-radius: 8px; padding: .5rem .6rem; margin-top: .55rem; font-size: .87rem;
}}
.usulan.ragu {{ background: {T.LATAR_CATATAN}; border-color: {T.BORDER_CATATAN}; }}

/* Kode pill (diagnosis) — warna per kode, lihat design_tokens */
.kode {{
  display: inline-block; min-width: 1.9rem; text-align: center;
  font-weight: 700; border-radius: {T.RADIUS_PIL}; padding: .18rem .5rem;
  font-size: .82rem;
}}
.kode.K {{ background: {T.KODE_SALAH_KONSEP_BG}; color: {T.KODE_SALAH_KONSEP_TEKS}; }}
.kode.B {{ background: {T.KODE_SALAH_BACA_BG}; color: {T.KODE_SALAH_BACA_TEKS}; }}
.kode.H {{ background: {T.KODE_SALAH_HITUNG_BG}; color: {T.KODE_SALAH_HITUNG_TEKS}; }}
.kode.E {{ background: {T.KODE_SALAH_TULIS_BG}; color: {T.KODE_SALAH_TULIS_TEKS}; }}
.kode.T {{ background: {T.KODE_BELUM_LIAT_BG}; color: {T.KODE_BELUM_LIAT_TEKS}; }}
.kode.N {{ background: {T.KODE_MENEBAK_BG}; color: {T.KODE_MENEBAK_TEKS}; }}
.kode.benar {{ background: {T.KODE_BENAR_BG}; color: {T.KODE_BENAR_TEKS}; }}

/* Tombol variasi cerita (LLM) — amber outline, sesuai mockup */
.kartu-variasi h2 {{ display: flex; align-items: center; gap: .5rem; }}

/* Sticky simpan bar */
.simpan-strip {{
  position: sticky; bottom: 0; padding: .8rem 0 .4rem;
  background: linear-gradient(to top, {T.LATAR_MURID} 70%, transparent);
}}
.simpan-strip button {{ width: 100%; font-size: 1.05rem; padding: .85rem; }}

/* ── Halaman laporan (dashboard responsif) ─────────────────────────── */
.ringkasan-dashboard-laporan {{
  display: flex; flex-direction: column; gap: 1rem;
  margin-bottom: 1rem;
}}
.kartu-stat {{
  display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1rem;
  margin-bottom: 1.2rem;
}}
.kartu-stat-admin {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
.ringkasan-dashboard-laporan .kartu-stat {{
  grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .7rem;
  margin-bottom: 0;
}}
.ringkasan-dashboard-laporan .kartu-stat .stat:last-child {{ grid-column: 1 / -1; }}
.stat {{
  background: {T.LATAR_KARTU_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU}; padding: 1rem; text-align: center;
  box-shadow: 0 1px 3px rgba(22,33,62,0.04);
}}
.stat .angka-besar {{
  font-size: 2rem; font-weight: 800; color: {T.AKSEN_MURID_UTAMA};
  line-height: 1.1;
}}
.stat .stat-label {{ color: {T.TEKS_SUBTLE}; font-size: .88rem; margin-top: .3rem; }}
.stat .stat-nilai-utama {{ font-size: 1.15rem; font-weight: 700; color: {T.TEKS_JUDUL}; }}

.layout-laporan {{ display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; }}
@media (max-width: 46rem) {{ .layout-laporan {{ grid-template-columns: 1fr; }} }}
.chart-wrap {{ overflow-x: auto; }}
.chart-wrap svg {{ display: block; margin: 0 auto; max-width: 100%; }}

.diagnosis-lis {{ list-style: none; margin: 0; padding: 0; }}
.diagnosis-lis li {{
  display: flex; align-items: flex-start; gap: .65rem; padding: .6rem 0;
  border-bottom: 1px solid {T.BORDER_HALUS}; font-size: .92rem;
}}
.diagnosis-lis li:last-child {{ border-bottom: none; }}
#perjalanan-belajar .diagnosis-lis li {{ display: block; }}
.dot {{
  flex: none; width: .85rem; height: .85rem; border-radius: {T.RADIUS_BULAT};
  margin-top: .3rem;
}}
.dot.kuat {{ background: {T.STATUS_KUAT}; }}
.dot.lemah {{ background: {T.STATUS_LEMAH}; }}
.dot.salah {{ background: {T.STATUS_SALAH}; }}

/* Laporan orang tua: tindakan didahulukan, istilah teknis dilipat. */
.sr-only {{
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}}
.ringkasan-laporan p:last-child {{ margin-bottom: 0; }}
.ringkasan-laporan {{
  background: {T.LATAR_CATATAN}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU}; padding: 1.15rem;
}}
.ringkasan-laporan > h2 {{ margin-top: 0; }}
.bagian-ringkasan-laporan {{
  border-top: 1px solid {T.BORDER_HALUS}; padding-top: .75rem; margin-top: .75rem;
}}
.bagian-ringkasan-laporan h3 {{ margin: 0 0 .45rem; font-size: 1rem; }}
.bagian-ringkasan-laporan p {{ margin: 0; }}
.daftar-fokus-ringkasan {{ margin: 0; padding-left: 1.15rem; }}
.item-fokus-ringkasan + .item-fokus-ringkasan {{ margin-top: .4rem; }}
.sumber-ringkasan-laporan {{
  color: {T.TEKS_SUBTLE}; font-size: .85rem; margin-top: 1rem;
}}
.sumber-ringkasan-laporan a {{ text-decoration: underline; text-underline-offset: .15em; }}
.aksi-ringkasan-laporan {{
  display: inline-flex; align-items: center; min-height: {T.TARGET_SENTUH};
  margin-top: .75rem; padding: .55rem .85rem;
  border: 1px solid {T.AKSEN_TEAL_TUA}; border-radius: {T.RADIUS_KECIL};
  color: {T.AKSEN_TEAL_TUA}; font-weight: 700; text-decoration: none;
}}
.aksi-ringkasan-laporan:hover {{ text-decoration: underline; }}
.grid-tindakan-laporan {{
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem; align-items: stretch;
}}
.grid-tindakan-laporan > .kartu {{ height: 100%; }}
.daftar-aksi-laporan {{ list-style: none; margin: 0; padding: 0; }}
.aksi-laporan {{
  border: 1px solid {T.BORDER_HALUS}; border-left-width: .3rem;
  border-radius: {T.RADIUS_KECIL}; padding: .8rem .9rem;
  margin-bottom: .7rem; background: {T.LATAR_KARTU_MURID};
}}
.aksi-laporan:last-child {{ margin-bottom: 0; }}
.aksi-laporan.salah {{ border-left-color: {T.STATUS_SALAH}; }}
.aksi-laporan.baru {{ border-left-color: {T.STATUS_LEMAH}; }}
.aksi-laporan.kuat {{ border-left-color: {T.STATUS_KUAT}; }}
.aksi-laporan p {{ margin: .45rem 0 0; font-size: .9rem; }}
.meta-laporan {{
  display: block; color: {T.TEKS_SUBTLE}; font-size: .8rem; margin-top: .15rem;
}}
.skor-sekunder {{ margin-bottom: .4rem; }}
.tanggal-ringkas {{ white-space: nowrap; font-variant-numeric: tabular-nums; }}
.cara-baca-laporan summary,
.detail-teknis-laporan summary {{ cursor: pointer; }}
.cara-baca-laporan summary h2,
.detail-teknis-laporan summary h2 {{ display: inline; margin-right: .5rem; }}
.cara-baca-laporan summary .sub,
.detail-teknis-laporan summary .sub {{ display: inline; margin: 0; }}
.cara-baca-laporan[open] summary,
.detail-teknis-laporan[open] summary {{ margin-bottom: 1rem; }}
.legenda-teknis {{
  color: {T.TEKS_SUBTLE}; font-size: .82rem; line-height: 1.7;
  padding: .65rem .75rem; background: {T.LATAR_KARTU_SEKUNDER};
  border-radius: {T.RADIUS_KECIL};
}}
.detail-teknis-laporan .tabel-wrap {{ margin-top: 1.2rem; }}
.detail-teknis-laporan h3 {{
  color: {T.TEKS_JUDUL}; font-size: 1rem; margin: 0 0 .55rem;
}}
@media (min-width: 64rem) {{
  .bungkus-st.laporan-lebar {{ max-width: 72rem; }}
  .bungkus-st.laporan-lebar > .st-topbar {{ max-width: none; }}
  .bungkus-st.laporan-lebar .sesi-badan-st {{ max-width: none; }}
  .ringkasan-dashboard-laporan {{
    display: grid;
    grid-template-columns: minmax(0, 1.45fr) minmax(18rem, .8fr);
    grid-template-areas: "ringkasan metrik";
    gap: 1rem; align-items: stretch;
  }}
  .ringkasan-dashboard-laporan > .ringkasan-laporan {{
    grid-area: ringkasan; margin-bottom: 0; min-height: 100%;
  }}
  .ringkasan-dashboard-laporan > .kartu-stat {{
    grid-area: metrik; align-self: start;
  }}
  .ringkasan-dashboard-laporan .kartu-stat {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
  .ringkasan-dashboard-laporan .kartu-stat .stat:last-child {{ grid-column: 1 / -1; }}
}}
@media (max-width: 42rem) {{
  .kartu-stat {{ grid-template-columns: 1fr; }}
  .ringkasan-dashboard-laporan .kartu-stat {{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }}
  .ringkasan-dashboard-laporan .kartu-stat .stat:last-child {{ grid-column: 1 / -1; }}
}}
@media (max-width: 46rem) {{
  .grid-tindakan-laporan {{ grid-template-columns: 1fr; }}
  .cara-baca-laporan summary .sub,
  .detail-teknis-laporan summary .sub {{ display: block; margin-top: .25rem; }}
}}
@media (max-width: 23rem) {{
  .kartu-stat,
  .ringkasan-dashboard-laporan .kartu-stat {{ grid-template-columns: 1fr; }}
  .kartu-stat .stat:last-child,
  .ringkasan-dashboard-laporan .kartu-stat .stat:last-child {{ grid-column: auto; }}
}}

/* ── Halaman akun (mockup guru-akun) ───────────────────────────────── */
.kartu-judul {{
  display: flex; align-items: center; gap: .6rem; margin: 0 0 .7rem;
}}
.ikon-kartu {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 2rem; height: 2rem; border-radius: {T.RADIUS_BULAT};
  background: {T.AKSEN_MURID_UTAMA}; color: #fff; font-size: 1rem;
}}
.ikon-kartu.amber {{ background: {T.AKSEN_MURID_AMBER}; }}
.baris-aksi {{ display: flex; align-items: center; gap: .3rem; }}
.tombol-hapus {{
  background: {T.KODE_SALAH_KONSEP_BG}; color: {T.KODE_SALAH_KONSEP_TEKS};
  border: 1px solid {T.KODE_SALAH_KONSEP_TEKS};
}}
.baris-form {{ display: flex; gap: .7rem; align-items: flex-end; flex-wrap: wrap; }}
.baris-form > div {{ flex: 1; min-width: 150px; }}
.status-ok {{ color: {T.AKSEN_TEAL_TUA}; }}
.status-buruk {{ color: {T.AKSEN_KORAL_TUA}; }}

/* ── Halaman masuk (mockup guru-masuk) ─────────────────────────────── */
.masuk-kiri {{ text-align: center; }}
.masuk-kiri img {{ width: 200px; height: 200px; max-width: 70vw; }}
.masuk-kiri h1 {{
  font-size: 1.8rem; margin: .4rem 0 0; color: {T.AKSEN_MURID_UTAMA};
}}
.masuk-kiri p {{ color: {T.TEKS_SUBTLE}; margin: .2rem 0 0; }}
.masuk-kanan {{ display: flex; justify-content: center; }}
.kartu-masuk {{
  width: 100%; max-width: 380px; padding: 1.6rem;
}}
.kartu-masuk .ikon-gembok {{
  display: block; margin: 0 auto .8rem; width: 44px; height: 44px;
}}
/* Hanya type=submit: tombol mata disuntik SKRIP_MATA_SANDI di dalam kartu
   yang sama. Tanpa pembatasan ini, .kartu-masuk button (spesifisitas 0,1,1)
   mengalahkan .tombol-mata (0,1,0) — tombol mata melebar 100% dan ikonnya
   jatuh di tengah kolom sandi. */
.kartu-masuk button[type=submit] {{ width: 100%; margin-top: .7rem; padding: .8rem; }}

/* ── Pesan (sukses/galat) ──────────────────────────────────────────── */
.pesan {{
  background: {T.LATAR_TERSIMPAN}; border: 1px solid {T.BORDER_TERSIMPAN};
  color: {T.TEKS_TERSIMPAN}; border-radius: {T.RADIUS_SEDANG};
  padding: .7rem .9rem; margin-bottom: 1rem; font-size: .93rem;
}}
.pesan.galat {{ background: {T.LATAR_GALAT}; border-color: {T.BORDER_GALAT}; color: {T.TEKS_GALAT}; }}
.pesan-terlarang {{ background: {T.LATAR_GALAT}; border-color: {T.BORDER_GALAT}; }}

/* Masuk yg gagal / 401 */
.masuk-luar {{
  background: {T.LATAR_MURID}; border: 1px solid {T.BORDER_HALUS};
  border-radius: {T.RADIUS_KARTU}; padding: 1.4rem; max-width: 440px;
  margin: 2rem auto; text-align: center;
}}

/* ── Mobile polish: tabel card-stacked & form compact ─────────────── */

/* Tabel laporan tren 11 kol di HP — simpan wrapper scroll, tapi jadikan
   kartu stacked agar tidak perlu menggeser ke kanan terus. Label diambil
   dari data-label tiap td; header disembunyikan. Aktif di bawah 46rem. */
/* Diterapkan via kelas wrapper .tabel-tren di reports.py */
@media (max-width: 46rem) {{
  .tabel-tren table,
  .tabel-tren thead,
  .tabel-tren tbody,
  .tabel-tren tr,
  .tabel-tren th,
  .tabel-tren td {{ display: block; }}
  .tabel-tren thead {{ display: none; }}
  .tabel-tren table {{ min-width: 0; border: 0; }}
  .tabel-tren tr {{
    border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL};
    margin-bottom: .7rem; overflow: hidden; background: #fff;
  }}
  .tabel-tren td {{
    border: none; border-bottom: 1px solid {T.BORDER_HALUS};
    display: flex; justify-content: space-between; gap: .6rem;
    padding: .45rem .6rem; font-size: .9rem;
  }}
  .tabel-tren td:last-child {{ border-bottom: none; }}
  .tabel-tren td::before {{
    content: attr(data-label); font-weight: 600; color: {T.TEKS_SUBTLE};
    flex: none; max-width: 46%; text-align: left;
  }}
  .tabel-tren td.angka {{ text-align: right; }}
}}

/* Form tabel akun murid: tumpuk vertical di HP, input fleksibel */
.baris-aksi {{ display: flex; align-items: center; gap: .3rem; flex-wrap: wrap; }}
.input-sandi-kecil {{
  width: 8.5rem; max-width: 42vw; padding: .3rem .5rem; font-size: .9rem;
  border: 1px solid {T.BORDER_HALUS}; border-radius: {T.RADIUS_KECIL};
  font-family: inherit;
}}
@media (max-width: 30rem) {{
  .baris-aksi {{ flex-direction: column; align-items: stretch; }}
  .baris-aksi form {{ width: 100%; }}
  .input-sandi-kecil {{ width: 100%; max-width: none; flex: 1; }}
  .baris-aksi form[style] {{ margin-left: 0 !important; }}
}}

/* Miskonsepsi & materi: kecilkan padding di HP supaya tidak makan lebar */
@media (max-width: 30rem) {{
  .bungkus {{ padding-left: .6rem; padding-right: .6rem; }}
}}

/* Hormati preferensi gerak: transisi hover/dropdown dimatikan bagi yang
   memintanya. Satu blok untuk seluruh permukaan guru. */
@media (prefers-reduced-motion: reduce) {{
  * {{
    transition-duration: .01ms !important;
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
  }}
}}

@media print {{
  body {{ background: #fff; }}
  .simpan-strip, .tombol-coral, .tombol-kecil {{ display: none; }}
}}
"""

# Skrip cegah kirim ganda — dipasang shell halaman (web.py _halaman,
# landing.py _halaman_publik) setelah SKRIP_MATA_SANDI. Setiap submit:
# tombolnya dimatikan dan diberi teks "Menyimpan…" supaya guru yang
# menekan dua kali (atau menekan lagi saat jaringan lambat) tidak
# mengirim form yang sama dua kali. pageshow memulihkan tombol bila
# peramban kembali lewat cache (tombol jangan mati selamanya).
SKRIP_CEGAH_KIRIM_GANDA = """\
(function(){
  document.addEventListener('submit', function(e){
    var b = e.target.querySelector('button[type=submit]');
    if (!b || b.disabled) return;
    b.disabled = true;
    b.dataset.labelAsli = b.textContent;
    b.textContent = 'Menyimpan…';
    b.classList.add('sedang-kirim');
  }, true);
  window.addEventListener('pageshow', function(e){
    if (!e.persisted) return;
    var b = document.querySelectorAll('button.sedang-kirim');
    for (var i = 0; i < b.length; i++) {
      b[i].disabled = false;
      if (b[i].dataset.labelAsli) b[i].textContent = b[i].dataset.labelAsli;
      b[i].classList.remove('sedang-kirim');
    }
  });
})();
"""

# Skrip tombol mata — dipasang shell halaman (web.py _halaman,
# landing.py _halaman_publik) di akhir <body>. Membungkus setiap
# input sandi dengan .kolom-sandi lalu menambah tombol tampilkan/
# sembunyikan. Murni penampilan: name, value, dan validasi tak berubah.
SKRIP_MATA_SANDI = """\
(function(){
  var ikonLihat = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 12s4-7.5 11-7.5S23 12 23 12s-4 7.5-11 7.5S1 12 1 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var ikonSembunyi = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M17.94 17.94A10.4 10.4 0 0 1 12 19.5C5 19.5 1 12 1 12a18.6 18.6 0 0 1 5.06-5.94"/><path d="M9.9 4.74A9.9 9.9 0 0 1 12 4.5c7 0 11 7.5 11 7.5a18.6 18.6 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';
  var kolom = document.querySelectorAll('input[type=password]');
  for (var i = 0; i < kolom.length; i++) { (function(el){
    if (el.closest('.kolom-sandi')) return;
    var bungkus = document.createElement('div');
    bungkus.className = 'kolom-sandi';
    el.parentNode.insertBefore(bungkus, el);
    bungkus.appendChild(el);
    var mata = document.createElement('button');
    mata.type = 'button';
    mata.className = 'tombol-mata';
    mata.title = 'Tampilkan sandi';
    mata.setAttribute('aria-label', 'Tampilkan sandi');
    mata.setAttribute('aria-pressed', 'false');
    mata.innerHTML = ikonLihat;
    mata.addEventListener('click', function(){
      var tampil = el.type === 'password';
      el.type = tampil ? 'text' : 'password';
      mata.innerHTML = tampil ? ikonSembunyi : ikonLihat;
      mata.title = tampil ? 'Sembunyikan sandi' : 'Tampilkan sandi';
      mata.setAttribute('aria-label', mata.title);
      mata.setAttribute('aria-pressed', String(tampil));
      el.focus({ preventScroll: true });
    });
    bungkus.appendChild(mata);
  })(kolom[i]); }
})();
"""
