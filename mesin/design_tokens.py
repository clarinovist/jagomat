"""Design tokens — sumber tunggal untuk semua nilai visual aplikasi.

Dipakai oleh screen_style.py, print_style.py, teacher_style.py, dan students.py
(GAYA_STITCH). Tujuan: konsistensi antar-viewport (layar sentuh, cetak A4,
dashboard guru) tanpa duplikasi nilai. Ubah di sini, efek ke semua permukaan.

== Palet ==

Sejak restyle 29 Agu 2026 seluruh permukaan (guru, murid, lembar) memakai
SATU palet hangat dari mockup — cream #FFF8EE + teal #0FA3A3 + coral
#FF6B5B + amber #FFB020. Yang dulu disebut "palet INTI" (biru tua #16213e +
abu) kini hanya tersisa sebagai warna judul/teks (TEKS_JUDUL, BORDER_KUAT)
dan garis cetak; latar semua halaman adalah LATAR_MURID.

== Mockup ==

9 mockup UI/UX ada di ~/Documents/osn-resources/referensi/desain-ui/:
  - murid-sesiku.png, murid-kerjakan.png (mobile portrait)
  - guru-masuk.png, guru-dashboard.png, guru-sesi.png, guru-laporan.png,
    guru-akun.png (desktop landscape)
  - guru-lembar-soal.png, guru-lembar-kunci.png (A4 portrait)

Script generator (arsip lokal): ~/Documents/osn-resources/referensi/desain-ui/gen_guru.py (gpt-image-2 via chenzk.top).

Permukaan guru diimplementasi di teacher_style.py (5 halaman layar); lembar di
screen_style.py (browser) + print_style.py (kertas A4); murid di students.py.
"""

# ─────────────────────────────────────────────────────────────────────
# Palet INTI (permukaan guru: dashboard, sesi, laporan, akun, cetak)
# ─────────────────────────────────────────────────────────────────────

# Ukuran diagram pertanyaan yang dibagikan seluruh permukaan.
LEBAR_VISUAL_SOAL = "24rem"
# Pola v2 dan contoh belajar; koordinat tetap dua kolom.
POLA_LEBAR = 360
POLA_TINGGI = 320
POLA_SEL_LEBAR = 180
POLA_SEL_TINGGI = 160
POLA_BENTUK_Y = 64
POLA_RUAS = 22
POLA_GARIS = 2
POLA_TEBAL = 5
POLA_SAMBUNGAN = 3
POLA_FONT = 16
POLA_LABEL_Y = 122
POLA_TITIK_ATAS = 30
POLA_TITIK_JARAK = 22
POLA_TITIK_RADIUS = 5
# Geometri SVG statistika; satuan koordinat viewBox.
STAT_LEBAR = 360
STAT_MARGIN = 24
STAT_FONT = 16
STAT_GARIS = 2
STAT_GARIS_TIPIS = 1
STAT_LABEL_DX = 8
STAT_LABEL_DY = 5
STAT_ARSIR_JARAK = 8
STAT_NAMA_PER_BARIS = 18
STAT_BARIS = 96
STAT_ATAS = 28
STAT_PLOT_TINGGI = 280
STAT_PLOT_KIRI = 48
STAT_PLOT_KANAN = 336
STAT_RADIUS = 96
STAT_PUSAT_X = 180
STAT_PUSAT_Y = 124
STAT_IKON_RADIUS = 7
STAT_IKON_JARAK = 24
STAT_TURUS_JARAK = 8
STAT_TURUS_BUNDEL = 48
STAT_TURUS_TINGGI = 24

# Geometri SVG geometri datar; satuan koordinat viewBox.
GEO_LEBAR = 360
GEO_TINGGI = 250
GEO_MARGIN = 24
GEO_FONT = 15
GEO_FONT_CATATAN = 12
GEO_CATATAN_BAWAH = 4
GEO_GARIS = 2
GEO_GARIS_TIPIS = 1
GEO_PUTUS = "5 4"
GEO_ARSIR_JARAK = 8
GEO_BENTUK_ATAS = 30
GEO_BENTUK_LEBAR = 240
GEO_BENTUK_TINGGI = 150
GEO_RADIUS = 80
GEO_KISI_SEL = 24
GEO_TANDA_SIKU = 10
GEO_SUDUT_X = 180
GEO_SUDUT_Y = 155
GEO_RADIUS_LABEL_SUDUT = 100
GEO_BASELINE_LABEL_SUDUT = 5
GEO_JARAK_LABEL_SISI = 5
GEO_LABEL_DIAGONAL = ((100, 218), (280, 196))
GEO_LABEL_TINGGI_TRAPESIUM = (280, 218)
GEO_LABEL_SEGITIGA = ((112, 165), (245, 165), (190, 90))
GEO_LABEL_SEGITIGA_LUAR = ((112, 164), (175, 95), (277, 164))
GEO_LABEL_UKURAN = ((80, 218), (180, 218), (280, 198))
GEO_SINAR = 105
GEO_SEGITIGA_KIRI = 70
GEO_SEGITIGA_KANAN = 285
GEO_SEGITIGA_ALAS_Y = 180
GEO_SEGITIGA_PUNCAK_X = 190
GEO_SEGITIGA_PUNCAK_Y = 45
GEO_PERSEGI_X = 100
GEO_PERSEGI_Y = 35
GEO_PERSEGI_SISI = 160
GEO_JALAN_X = 80
GEO_JALAN_Y = 20
GEO_JALAN_SISI = 185
GEO_LABEL_UTAMA_Y = 218
GEO_LABEL_JALAN_Y = 222
JARAK_VISUAL_SOAL = "0.75rem"

# Sketsa ruang dan proyeksi isometrik kisi kubus.
RUANG_ASAL = (165, 200)
RUANG_SUMBU = ((90, -25), (-60, -40), (0, -90))
RUANG_PRISMA = ((80, 180), (235, 180), (130, 80))
RUANG_PRISMA_GESER = (45, -30)
RUANG_LIMAS = ((110, 180), (235, 190), (275, 150), (150, 140), (185, 45))
RUANG_TABUNG_PUSAT = (175, 75)
RUANG_TABUNG_RADIUS = (65, 23)
RUANG_TABUNG_TINGGI = 110
RUANG_KERUCUT_PUNCAK = (175, 45)
RUANG_GRID_RUSUK = 90
RUANG_GRID_ASAL = (180, 210)
RUANG_LABEL_S = (210, 224)
RUANG_LABEL_L = (58, 188)
RUANG_LABEL_T = (308, 148)
RUANG_LABEL_R = (205, 46)
RUANG_LABEL_A = (158, 208)
RUANG_LABEL_H = (46, 123)
RUANG_TITIK_PUSAT = 2
RUANG_LABEL_PRISMA_T = (285, 92)
RUANG_LABEL_TOTAL = (180, 22)
RUANG_LABEL_JUMLAH = (180, 224)
RUANG_LABEL_SKALA = (180, 258)
RUANG_TINGGI = 275
RUANG_JARING_SEL = 22
RUANG_JARING_BARIS = 130
RUANG_JARING_TINGGI = 430
RUANG_JARING_PUSAT = (90, 270, 180)
RUANG_JARING_ATAS = 42
RUANG_JARING_LABEL = 26
# Diagram petak dan linimasa: koordinat tetap, data tidak mengikuti viewport.
FASE6_LEBAR = 360
FASE6_TINGGI = 290
PETAK_AREA_LEBAR = 280
PETAK_AREA_TINGGI = 190
PETAK_ATAS = 38
PETAK_SEL = 40
PETAK_TITIK = 1.8
PETAK_LABEL_JARAK = 16
PETAK_CATATAN_Y = 275
JAM_PUSAT_X = (90, 270)
JAM_PUSAT_Y = 110
JAM_RADIUS = 56
JAM_TANDA_DALAM = 0.9
JAM_ANGKA_RADIUS = 0.73
JAM_JARUM_PENDEK = 0.40
JAM_JARUM_PANJANG = 0.55
JAM_ANGKA_FONT = 12
JAM_JUDUL_Y = 30
JAM_DIGITAL_Y = 190
JAM_HARI_Y = 212
JAM_DURASI_Y = 247
JAM_CATATAN_Y = 277
JAM_PENGHUBUNG_X = (158, 202)
JAM_PANAH = 6
PETA_UJUNG_X = (60, 300)
PETA_GARIS_Y = 105
PETA_KOTA_Y = 78
PETA_TANDA = 6
PETA_JARAK_Y = 145
PETA_SKALA_Y = 195
PETA_NYATA_Y = 232
PETA_CATATAN_Y = 278
VENN_PUSAT_X = (125, 235)
VENN_PUSAT_Y = 138
VENN_RADIUS = 75
VENN_TOTAL_Y = 32
VENN_NAMA_Y = 125
VENN_IRISAN_Y = 143
VENN_IRISAN_LABEL_Y = 252
OBJEK_LEBAR = 28
OBJEK_TINGGI = 32
OBJEK_JARAK = 10
OBJEK_PER_BARIS = 6
OBJEK_ATAS = 55
OBJEK_BARIS = 46
OBJEK_JUDUL_Y = 27
SLOT_ATAS = 203
SLOT_JUDUL_Y = 185
SLOT_LABEL_JARAK = 19
TIM_UJUNG_X = (65, 295)
SUSUNAN_CATATAN_Y = 282

# Latar
LATAR_INTI = "#f0f1f4"          # abu muda, badan halaman
LATAR_KARTU = "#fff"            # putih, kartu/soal
LATAR_KARTU_SEKUNDER = "#eef3fb"  # biru muda, petunjuk/kartu interaktif

# Teks & border
TEKS_UTAMA = "#111"             # hampir hitam, body
TEKS_JUDUL = "#16213e"          # biru tua, heading/judul/border
TEKS_SUBTLE = "#555"            # abu, label/meta
BORDER_HALUS = "#d5d8de"
BORDER_INTERAKTIF = "#c4d3ea"
BORDER_KUAT = "#16213e"

# Aksen sekunder (catatan, penanda)
LATAR_CATATAN = "#fff7e6"
BORDER_CATATAN = "#ecd9a8"
BINTANG = "#b8860b"             # challenge star (legacy gold)

# Konfirmasi positif
LATAR_TERSIMPAN = "#e8f6ec"
BORDER_TERSIMPAN = "#9ed4b0"
TEKS_TERSIMPAN = "#14532d"

# Teks kontras di atas aksen (butuh teks putih di atas teal/coral/amber)
TEKS_PUTIH = "#ffffff"

# Galat (pesan error) — netral merah lembut
LATAR_GALAT = "#fdecea"
BORDER_GALAT = "#f5b5ae"
TEKS_GALAT = "#93352b"

# Status Dashboard (mockup guru-laporan)
STATUS_KUAT = "#0FA3A3"          # teal
STATUS_LEMAH = "#FFB020"        # amber
STATUS_SALAH = "#FF6B5B"        # coral

# Aksen versi teks-aman: kontras >= 4.5:1 di atas putih/krem. Dipakai saat
# aksen menjadi WARNA TEKS (tautan, status, badge) atau latar tombol solid
# ber-teks putih. AKSEN_MURID_* tetap untuk border, badge besar, dan elemen
# grafis besar (di sana 3:1 cukup). Teal/coral terang di atas teks kecil
# gagal kontras (3.1:1 / 2.8:1) — dua token ini penggantinya.
AKSEN_TEAL_TUA = "#0a7d7d"
AKSEN_KORAL_TUA = "#cc3f2b"

# Badge peran topbar (multi-keluarga): Pengelola amber, Orang Tua teal —
# warna status yang sama supaya tetap satu rasa visual.
BADGE_ADMIN_BG = "#FFB020"
BADGE_ADMIN_TEKS = "#5b430a"
BADGE_GURU_BG = "#0FA3A3"
BADGE_GURU_TEKS = TEKS_PUTIH

# Kode diagnosis — warna pill di halaman sesi guru (mockup guru-sesi).
# Mengikuti STATUS_* supaya satu rasa: kuat=teal, lemah=amber, salah=coral.
KODE_BENAR_BG = "#e6f6ec"
KODE_BENAR_TEKS = "#157347"
KODE_SALAH_KONSEP_BG = "#fdecea"   # K
KODE_SALAH_KONSEP_TEKS = "#c2352b"
KODE_SALAH_BACA_BG = "#fdf3e0"     # B
KODE_SALAH_BACA_TEKS = "#a4700f"
KODE_SALAH_HITUNG_BG = "#e8f0fc"   # H
KODE_SALAH_HITUNG_TEKS = "#2c60ad"
KODE_SALAH_TULIS_BG = "#f0ecfb"    # E
KODE_SALAH_TULIS_TEKS = "#6a4bb0"
KODE_BELUM_LIAT_BG = "#eaf4ef"     # T
KODE_BELUM_LIAT_TEKS = "#3f7d57"
KODE_MENEBAK_BG = "#efeff1"        # N
KODE_MENEBAK_TEKS = "#5b5b63"

# Chart tren (mockup guru-laporan) — SVG. Axis digelapkan dari #8a91a3:
# label 11px-nya teks kecil, butuh ~4.5:1 di atas putih.
CHART_GRID = "#e2e6ef"
CHART_AXIS = "#6f7690"

# ─────────────────────────────────────────────────────────────────────
# Palet MURID (permukaan murid: /murid, /murid/kerjakan)
# ─────────────────────────────────────────────────────────────────────

LATAR_MURID = "#FFF8EE"         # cream hangat
AKSEN_MURID_UTAMA = "#0FA3A3"   # teal — primary action, nomor badge
AKSEN_MURID_KORAL = "#FF6B5B"   # coral — tombol simpan, highlight baru
AKSEN_MURID_AMBER = "#FFB020"   # amber — star/challenge
LATAR_KARTU_MURID = "#fff"

# ─────────────────────────────────────────────────────────────────────
# Identitas produk — SUMBER TUNGGAL nama & tagline (launch publik).
# Ganti nama di sini, efek ke semua permukaan (landing, login, dashboard).
# ─────────────────────────────────────────────────────────────────────

NAMA_PRODUK = "Jagomat"
TAGLINE = "Jago karena tahu caranya."

# Kontak dukungan manusia untuk pilot. Aplikasi ini SENGAJA tidak menyimpan
# email/telepon siapa pun (lihat landing.halaman_lupa_sandi), jadi ortu yang
# lupa sandi atau butuh bantuan hanya bisa lewat jalur luar ini. Placeholder:
# GANTI dengan nomor WA asli sebelum pilot dibuka ke keluarga pertama.
WA_SUPPORT = "08xx-xxxx-xxxx"

# Ukuran lambang (mark) per konteks. Audit 3 Sep menemukan ikon brand yang
# sama dirender 20,8px di satu CSS dan 21,6px di CSS lain — akibat ukuran
# ditulis sebagai angka lepas per stylesheet, bukan token.
LOGO_TOPBAR = "26px"   # topbar & ikon kecil (<=32px): pakai mark-sederhana
LOGO_BADGE = "40px"    # badge bulat di kartu masuk / sapaan anak
LOGO_HERO = "80px"     # hero landing (>=48px): pakai mark-penuh

# Warna wordmark — satu nilai. Sebelumnya #0FA3A3 di satu tempat dan
# #0a7d7d (teal tua) di tempat lain, jadi nama produk berganti rona antar
# halaman.
WARNA_WORDMARK = AKSEN_MURID_UTAMA

# ─────────────────────────────────────────────────────────────────────
# Tipografi
# ─────────────────────────────────────────────────────────────────────

FONT_LAYAR = (
    '-apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
)
FONT_CETAK = '"Helvetica Neue", Arial, sans-serif'

# Ukuran teks — skala modular 1.2x (lihat docs/design-system.md)
UKURAN_BADAN_LAYAR = "16px"
UKURAN_BADAN_CETAK = "10.5pt"
LINE_HEIGHT = "1.55"

# ─────────────────────────────────────────────────────────────────────
# Spacing — skala 4px base (lihat docs/design-system.md)
# ─────────────────────────────────────────────────────────────────────

SP_1 = "0.25rem"   # 4px
SP_2 = "0.5rem"    # 8px
SP_3 = "0.75rem"   # 12px
SP_4 = "1rem"      # 16px
SP_5 = "1.5rem"    # 24px
SP_6 = "2rem"      # 32px

# ─────────────────────────────────────────────────────────────────────
# Radius
# ─────────────────────────────────────────────────────────────────────

RADIUS_KARTU = "12px"
RADIUS_SEDANG = "10px"
RADIUS_KECIL = "8px"
RADIUS_PIL = "999px"       # pilihan cara, badge
RADIUS_BULAT = "50%"       # nomor badge

# ─────────────────────────────────────────────────────────────────────
# Touch target
# ─────────────────────────────────────────────────────────────────────

TARGET_SENTUH = "44px"     # pedoman aksesibilitas WCAG 2.5.5
LEBAR_KONTEN = "46rem"     # maksimum lebar konten layar (kolom baca & form)

# Landing publik = permukaan marketing, bukan kolom baca. 46rem di sana
# menyisakan ~776px kosong di laptop 1512px (terukur 4 Sep: konten 736px,
# 48,7% viewport — keluhan "tampilannya cuma separo"). 75rem = 1200px,
# sama dengan container mockup Stitch landing_page_desktop.
LEBAR_LANDING = "75rem"


# ─────────────────────────────────────────────────────────────────────
# Token Stitch (adopsi ui 2026-09-01 — lebih dekat Material 3 "surface")
# ─────────────────────────────────────────────────────────────────────

FONT_HEADLINE = (
    '"Plus Jakarta Sans", -apple-system, "Segoe UI", Roboto, sans-serif'
)
FONT_BODY = (
    '"Be Vietnam Pro", -apple-system, "Segoe UI", Roboto, sans-serif'
)

LATAR_SEKUNDER_LEMBUT = "#f6f3f2"   # surface-container-low (bg blok murid, grid halus)
LATAR_SEKUNDER_NETRAL = "#f0edec"   # surface-container (elemen di dalam kartu)
LATAR_ELEVASI         = "#ebe7e7"   # surface-container-high (hover ringan, level 2)
TEKS_VARIAN           = "#3d4949"   # on-surface-variant — pengganti TEKS_SUBTLE untuk kartu
BORDER_VARIAN         = "#bcc9c8"   # outline-variant (border kartu lembut)

# Status
STATUS_DIAGNOSTIK_BG  = AKSEN_MURID_UTAMA   # bg pill diagnostik (teal teks putih)
STATUS_DIAGNOSTIK_TEKS = "#ffffff"
STATUS_LATIHAN_BG     = "#ffba4b"           # broader "latihan" (amber gelap)
STATUS_LATIHAN_TEKS   = "#291800"           # amber text on light pill

# Glow/fokus aksen (border fokus 2px)
FOKUS_AKSEN = "#0fa3a3"

# ─────────────────────────────────────────────────────────────────────
# Token Figma v2 — sinkron dari file "Jagomat · Sistem Desain & Pilot UI"
# (pilot 2026-09-25). Hanya nilai yang BELUM ada di atas yang ditulis di sini;
# padanan yang sudah ada tidak diduplikasi (mis. cream = LATAR_MURID,
# teal-strong = AKSEN_TEAL_TUA, radius/lg 12 = RADIUS_KARTU,
# radius/pill = RADIUS_PIL, size/touch-min 44 = TARGET_SENTUH).
#
# Catatan: token di blok ini belum dipakai CSS mana pun. Disinkronkan lebih
# dulu supaya desain dan kode memakai satu nama; penerapannya ke tampilan
# menyusul lewat jalur Normal/Kritis, bukan diselundupkan lewat sinkron ini.
# ─────────────────────────────────────────────────────────────────────

# Warna hover tombol solid (Figma action/*-hover) — lebih gelap dari dasarnya.
AKSEN_KORAL_HOVER = "#ba3c2d"    # hover tombol coral (aksi utama)
AKSEN_TEAL_HOVER = "#0b7477"     # hover tombol teal (aksi sekunder)

# Balon penjelasan pola "ⓘ" (komponen Info di Figma: bg/tooltip & text/tooltip).
# Nilainya sama dengan token judul/putih supaya balon tetap tinggi kontras.
LATAR_TOOLTIP = BORDER_KUAT      # #16213e
TEKS_TOOLTIP = TEKS_PUTIH

# Radius kartu utama versi Figma (22px). Kode masih memakai RADIUS_KARTU 12px
# di kartu; token ini belum diterapkan agar sinkron ini tidak mengubah tampilan.
RADIUS_KARTU_BESAR = "22px"

# Tinggi kontrol & CTA (ukuran Figma: kontrol 48, CTA utama 52) + ikon standar.
TINGGI_KONTROL = "48px"
TINGGI_CTA = "52px"
UKURAN_IKON = "24px"

# Ketebalan garis seperti di Figma (border/width & border/focus-width).
TEBAL_GARIS = "1px"
TEBAL_FOKUS = "2px"

# Lanjutan skala spacing 4px (SP_1..SP_6 sudah di atas: 4/8/12/16/24/32).
SP_7 = "3rem"                    # 48px
SP_8 = "4rem"                    # 64px
