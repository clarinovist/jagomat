# Design system — Jagomat

Rujukan desain tunggal untuk UI Jagomat. Isinya **kontrak yang berlaku sekarang**.
Catatan bertanggal dan alasan keputusan lama ada di
[riwayat design system](design-system-history.md).

## Sumber kebenaran

| Pertanyaan | Sumber |
| --- | --- |
| Nilai warna, ukuran, jarak, bayangan | `mesin/design_tokens.py` (`T.*`) |
| Token mana untuk peran apa di permukaan tertentu | `mesin/design_roles.py` (`peta_peran()`), dijaga `test_design_roles.py` |
| Melihat token, kontras, dan komponen ter-render | Katalog hidup `scripts/design_catalog.py` (lihat [Katalog](#katalog-hidup)) |
| Aturan pakai, komponen, keputusan | Dokumen ini |
| Bukti audit dan batas perangkat | [Audit UI lintas halaman](ui-consistency-audit.md), [audit admin](admin-ui-audit.md) |
| Alasan lama | [Riwayat](design-system-history.md), [keputusan redesain admin](redesign-decisions.md) |
| Mockup | `docs/mockup/` (canvas profil/ruang guru 19 Okt 2026), arsip lokal `../osn-resources/referensi/desain-ui/` (PNG Agustus, pilot Figma 25 Sep) |

Urutan otoritas: **kode/DOM ter-render → dokumen ini → mockup**. Mockup adalah
acuan desain, bukan runtime dan bukan bukti aksesibilitas. Perubahan UI tetap
dirender dengan data sintetis sebelum diterima.

## Prinsip

1. **Zero-JS default.** Interaksi memakai HTML native (`<details>`, form, tautan
   GET). Enhancement hanya yang disetujui di `CLAUDE.md`, berhash CSP, dengan
   fallback native utuh.
2. **Satu aksi, satu entry point.** CTA atau form ganda untuk aksi yang sama adalah bug.
3. **Makna selalu berteks.** Ikon dan warna mendukung, tidak menggantikan label aksi
   atau status (status/badge selalu punya teks).
4. **Terbaca dewasa.** Teks informatif minimal 14px; input teks 16px; target sentuh
   minimal 44px.
5. **Hanya token.** Tidak ada hex/RGB literal di CSS modul lain (dijaga
   `test_ui_tokens.py`). Nilai baru masuk `design_tokens.py` dulu.
6. **Satu fondasi Jagomat.** Admin, keluarga, dan murid berbagi token warna terang,
   skala tipe/jarak/radius serta ukuran kontrol. Varian layout boleh berbeda sesuai
   tugas; adapter tema gelap bukan design system kedua.
7. **Sisi murid netral.** Anak hanya melihat tahap netral: tanpa kode diagnosis,
   label kelemahan, kunci, malrule, atau alasan internal.

## Permukaan

| Permukaan | Rute contoh | Stylesheet utama | Token warna | Wadah isi |
| --- | --- | --- | --- | --- |
| Publik | `/`, `/masuk`, `/daftar`, legal, riset publik | `style_stitch.GAYA_STITCH`, `landing.py`, `competitive_research.py` | Dasar hangat | `LEBAR_LANDING` 75rem (landing), `LEBAR_KONTEN` 46rem |
| Ruang guru | `/guru` | `GAYA_STITCH` (`.guru-beranda-st`) | `ANAK_*` + dasar | 46rem, kartu satu kolom |
| Profil anak | `/anak/<id>` empat tab, laporan lama | `GAYA_STITCH` + `GAYA_PROFIL` + `child_style.GAYA_ANAK` | `ANAK_*` | `ANAK_LEBAR` 60rem isi, gutter 32/16px |
| Akun | `/akun`, `/persetujuan` (tinjau), Data Pendamping | `account_style.GAYA_AKUN` (`.akun-editorial-st`) | Dasar hangat | 72rem dua kolom; 46rem (`.akun-sempit-st`) |
| Tinjauan, cetak, lampiran | sesi guru, lampiran foto | `CSS_SESI`, `teacher_style.GAYA_GURU` | Dasar + `KODE_*` | Editorial 60rem termasuk padding |
| Pendamping | panel inline, kelola | `assistant_style.GAYA_PENDAMPING` | Dasar hangat | Panel penuh di HP |
| Murid | `/murid`, pengerjaan | `GAYA_STITCH` | Dasar hangat | Mobile-first, kolom 46rem di desktop |
| Lembar | `/lembar/<id>`, penilaian | `screen_style.GAYA_LAYAR`, `print_style.GAYA_CETAK` | Dasar + `LEMBAR_AKSEN` beku (layar), `CETAK_*` (kertas) | A4 |
| Admin | `/admin/...` | `admin_style.GAYA_ADMIN` | Dasar hangat + alias profil lewat `ADMIN_*` (adapter tema) | Sidebar 256px, kanvas fluida; form pendek maks. 46rem |

Font: `FONT_HEADLINE` (Plus Jakarta Sans) dan `FONT_BODY` (Be Vietnam Pro) hanya
tampil di halaman yang memasang webfont: publik, murid, lampiran, dan halaman guru
yang tidak privat. Halaman privat (`privat=True` pada `teacher_shell._halaman` atau
`_halaman_stitch`: Akun, profil anak dan laporan untuk guru yang masuk, kelola
Pendamping, persetujuan, langganan, sebagian sesi) membuang `@import` webfont, dan
Admin tidak memuatnya; semuanya jatuh ke font sistem lewat stack fallback.
`FONT_CETAK` khusus A4. Jangan menambah atau menghapus sumber font tanpa memeriksa CSP
halaman yang bersangkutan.

## Warna

### Keluarga palet

**Dasar hangat** (publik, akun, tinjauan, Pendamping, murid, lembar layar):

| Token | Nilai | Peran |
| --- | --- | --- |
| `LATAR_MURID` | #FFF8EE | Latar halaman (cream) |
| `LATAR_KARTU` | #fff | Permukaan kartu |
| `TEKS_UTAMA` / `TEKS_JUDUL` | #111 / #16213e | Badan / judul |
| `TEKS_SUBTLE` / `TEKS_VARIAN` | #555 / #3d4949 | Teks sekunder |
| `BORDER_VARIAN` / `BORDER_HALUS` | #bcc9c8 / #d5d8de | Garis kartu dan pemisah (dekoratif, bukan batas kontrol) |
| `BORDER_KONTROL` | #7b8786 | Batas input, select, textarea (≥3:1 di putih dan cream) |
| `AKSEN_MURID_UTAMA` / `_KORAL` / `_AMBER` | #0FA3A3 / #FF6B5B / #FFB020 | Aksen **grafis**: border, ilustrasi, latar dengan teks gelap |
| `AKSEN_TEAL_TUA` / `AKSEN_KORAL_TUA` | #0F6B64 / #cc3f2b | Aksen **berteks**: tautan, teks status, tombol solid berteks putih |
| `AKSEN_TEAL_HOVER` / `AKSEN_KORAL_HOVER` | #0A4F4A / #ba3c2d | Hover tombol solid (lebih gelap) |
| `FOKUS_AKSEN` | = `AKSEN_TEAL_TUA` | Cincin fokus, border fokus input, hover kartu (≥3:1 di cream) |
| `LATAR_GALAT` / `TEKS_GALAT` | #fdecea / #93352b | Galat |
| `LATAR_TERSIMPAN` / `TEKS_TERSIMPAN` | #e8f6ec / #14532d | Sukses/tersimpan |

**Profil anak dan ruang guru** memakai `ANAK_*`: teks `ANAK_TEKS` (= `TEKS_JUDUL`),
aksen `ANAK_AKSEN` (= `AKSEN_TEAL_TUA`), garis kartu `ANAK_BORDER`, serta chip nada
`ANAK_PERHATIAN_*`, `ANAK_BAIK_*`, `ANAK_NETRAL_*`, `ANAK_INFO_*`. Batas kontrol
memakai `BORDER_KONTROL` yang sama dengan permukaan lain. Aksi utama profil memakai
teal, bukan coral.

**Satu teal berteks.** Sejak 25 Okt 2026 seluruh permukaan keluarga memakai satu teal
teks-aman, #0F6B64 dari mockup profil 19 Okt (6,0:1 di cream). Sebelumnya #0a7d7d
(tombol profil, tautan) dan #0F6B64 (pil, disclosure) tampil berdampingan di halaman
yang sama. Teal yang tersisa punya peran berbeda dan memang dibedakan:
`AKSEN_MURID_UTAMA` #0FA3A3 untuk grafis/border terang, `AKSEN_TEAL_HOVER` #0A4F4A
untuk hover, tema gelap admin yang memerlukan pasangan kontras berbeda, dan
`LEMBAR_AKSEN` #0a7d7d yang dibekukan pada lembar (lihat di bawah). Duplikat satu
peran ditulis sebagai alias eksplisit (`STATUS_*`, `ANAK_TEKS`, `ANAK_AKSEN*`,
`ANAK_BAIK_TEKS`, `ANAK_HEADER_AVATAR_TEKS`, `BORDER_KUAT`, `TEKS_REVIEW`, dan
lain-lain), bukan hex kembar.

**Lembar dibekukan.** HTML lembar latihan (`teacher_print_pages.halaman_lembar`, CSS
`screen_style.GAYA_LAYAR`) wajib identik byte-per-byte antara writer dan image
recovery yang dipin (`test_question_release.py`, gate rilis question pair). Karena itu
lembar memakai `LEMBAR_AKSEN`/`BORDER_CORET` sendiri dan tidak ikut restyle layar.
Mengubah gaya lembar hanya bersama pembaruan pasangan recovery menurut
[runbook rilis](production-release.md).

**Admin adalah varian layout dari fondasi yang sama**, bukan palet atau skala
komponen terpisah. Seluruh `ADMIN_*_CERAH` adalah alias token dasar/profil: cream
`LATAR_MURID`, kartu `LATAR_KARTU`, teal `AKSEN_TEAL_TUA`, batas `BORDER_KONTROL`,
dan status bersama. `ADMIN_*`/`--admin-*` hanya adapter tema agar gelap tetap terbaca.
Tema Sistem mengikuti `prefers-color-scheme`; Terang/Gelap tetap cookie `HttpOnly`
server-side (`data-tema`). Tidak ada skala `ADMIN_UKURAN_*` atau `ADMIN_RADIUS*`.
Logo sidebar dan header HP memakai `brand.mark()` lokal yang sama; hanya satu
logo terlihat pada tiap viewport. CSS shell admin tetap tersekop; tidak memuat webfont.

**Cetak** memakai `CETAK_*` (tinta hitam, garis abu, tanpa latar berwarna) agar
tema layar tidak mengubah kertas.

**Status dan diagnosis:** `STATUS_KUAT/LEMAH/SALAH` untuk grafik tren;
`KODE_*_BG/_TEKS` untuk pill kode B/K/H/E/T/N di tinjauan guru (pill tinjauan B dan T
memakai teks `TEKS_JUDUL` di atas latar kodenya; pill lama `.kode.*` memakai
`KODE_*_TEKS`). Pill kode tidak pernah tampil di sisi murid.

### Aturan kontras

| Pemakaian | Minimum |
| --- | --- |
| Teks normal | 4,5:1 |
| Teks besar (≥24px, atau ≥18,66px tebal) | 3:1 |
| Batas kontrol (input, select, checkbox) terhadap latar sekitarnya | 3:1 |
| Indikator fokus | 3:1 |
| Grafis yang membawa informasi | 3:1 |

Aksen terang (`AKSEN_MURID_*`, `STATUS_*`) tidak dipakai sebagai warna teks atau
latar teks putih; versi berteksnya `AKSEN_TEAL_TUA`, `AKSEN_KORAL_TUA`,
`AKSEN_AMBER_TUA` #815600. `test_design_roles.py` memindai semua CSS dan hanya
mengizinkan daftar beralasan `design_roles.AKSEN_TERANG_DIIZINKAN` (amber di atas latar
navy, ikon dekoratif, glyph ikon, lembar beku). Rasio dihitung dengan luminansi relatif
sRGB (WCAG), bukan selisih hex.

### Peta peran

`design_roles.py` memetakan **peran semantik** ke nama token untuk tiap permukaan:
`dasar`, `profil` (profil anak dan ruang guru), `murid` (pengerjaan), `tinjauan`
(pill kode, nomor, jejak), `admin_cerah`, `admin_gelap`, `cetak`. Setiap entri menunjuk
aturan CSS nyata (modul, konstanta, selektor, properti). `test_design_roles.py` menukar
token di namespace terisolasi untuk membuktikan token itu mencapai aturan tersebut
(untuk admin juga bahwa nilai tema dipasang di blok `data-tema` yang benar), menjaga
satu peran = satu token per permukaan, lalu menghitung kontras pasangan yang tampil
bersama. Pemeriksaan hanya mencakup assignment pertama tiap konstanta CSS; blok `+=`
sesudahnya (mis. `GAYA_TEKS_MIN`) tidak dipetakan. Modul ini rujukan dan guard, bukan
dependensi runtime.

| Peran | dasar | profil | admin (cerah) |
| --- | --- | --- | --- |
| `latar_halaman` | `LATAR_MURID` | `LATAR_MURID` | `ADMIN_LATAR_CERAH` |
| `latar_kartu` | `LATAR_KARTU` | `LATAR_KARTU` | `ADMIN_PERMUKAAN_CERAH` |
| `teks_utama` | `TEKS_UTAMA` | `ANAK_TEKS` | `ADMIN_TEKS_CERAH` |
| `tautan` | `AKSEN_TEAL_TUA` | `ANAK_AKSEN` | — |
| `aksi_utama` / `teks_aksi` | `AKSEN_KORAL_TUA` / `TEKS_PUTIH` | `AKSEN_TEAL_TUA` / `TEKS_PUTIH` | `ADMIN_AKSEN_CERAH` / `ADMIN_PERMUKAAN_CERAH` |
| `batas_kontrol` | `BORDER_KONTROL` | `BORDER_KONTROL` | `ADMIN_BORDER_KUAT_CERAH` |
| `fokus` | `FOKUS_AKSEN` (= `AKSEN_TEAL_TUA`) | `AKSEN_TEAL_TUA` | `ADMIN_AKSEN_CERAH` (= `AKSEN_TEAL_TUA`) |

Peta lengkap (badge, chip, pill kode, galat/sukses) dibaca lewat
`design_roles.peta_peran("<permukaan>")`. Komponen baru yang memperkenalkan pasangan
warna teks/latar atau batas kontrol menambahkan pasangannya ke `design_roles.py`.

`PENGECUALIAN` mencatat pasangan yang sengaja ditunda beserta alasannya; test menuntut
daftar itu sama persis dengan kegagalan nyata. **Saat ini kosong**: sepuluh kegagalan
yang ditemukan saat peta dibuat (garis input 1,7:1, cincin fokus 2,9:1 di cream, badge
teks putih di teal/coral terang, tautan publik teal terang, select profil 2,1:1, pill
kode lama B/T dan teks kunci) diperbaiki 25 Okt 2026, dan test regresi memastikan nilai
lama itu merah lagi bila dikembalikan.

## Tipografi

| Peran | Token | Nilai | Pakai untuk |
| --- | --- | --- | --- |
| Judul halaman dewasa | `UKURAN_JUDUL_DEWASA` | clamp 22–26px | h1 ruang guru, akun, laporan, Pendamping |
| Judul bagian dewasa | `UKURAN_BAGIAN_DEWASA` | 18px | h2 dan judul kartu |
| Angka statistik | `UKURAN_ANGKA_DEWASA` | 24px | Statistik, peta laporan, nominal |
| Badan | `UKURAN_BADAN_LAYAR` | 16px | Body dan semua input teks |
| Bantuan | `UKURAN_TEKS_BANTUAN` | 14,4px | Petunjuk dan teks bantuan |
| Label | `UKURAN_TEKS_LABEL` | 14px | Label, chip, metadata informatif; **batas bawah teks informatif** |
| Catatan | `UKURAN_TEKS_CATATAN` | 13px | Eyebrow kapital dekoratif saja |
| Meta | `UKURAN_TEKS_META` | 12px | Warisan; jangan dipakai untuk informasi baru |
| Judul Stitch | `UKURAN_JUDUL_STITCH` / `UKURAN_BAGIAN_STITCH` | 28 / 20px | `h1.st`/`h2.st` publik, murid, judul halaman anak |
| Admin | Skala dewasa yang sama | Judul 22–26 / isi 16 / statistik 24px | Tidak punya skala tersendiri |
| Cetak | `UKURAN_BADAN_CETAK` | 10,5pt | Lembar A4 |

`LINE_HEIGHT` 1,55 untuk badan. Judul anak/murid dan landing memakai skala Stitch
sendiri karena audiensnya berbeda. `GAYA_TEKS_MIN` di `style_stitch.py` menaikkan teks
informatif yang diketahui ke 14px secara tersekop. Ukuran relatif (`em`, `%`) dan
`clamp()` boleh untuk konteks komponen; nilai rem/px baru harus salah satu ukuran skala.

**Ratchet skala tipe.** Per 25 Okt 2026, 293 dari 444 deklarasi ukuran huruf literal
rem/px (`font-size` dan shorthand `font:`) di dalam string Python berada di luar skala
(terbanyak `style_stitch.py` 198, `teacher_style.py` 29, `screen_style.py` 14).
`test_type_scale.py` mengunci jumlah per berkas: literal di luar skala tidak boleh
bertambah, dan setiap pengurangan wajib menurunkan `BATAS`.
Menyamakan sisa literal itu ke skala adalah perubahan visual dan dikerjakan bertahap
per permukaan dengan render, bukan sapuan massal. Admin kini tanpa literal ukuran
font dan radius; tujuh penyimpangan tipenya sudah dihapus. Dua judul promosi40px
non-admin tetap dalam cakupan ratchet lama agar restyle admin tidak mengubahnya.

## Jarak, radius, wadah, breakpoint

| Jarak | `SP_1` | `SP_2` | `SP_3` | `SP_4` | `SP_5` | `SP_6` | `SP_7` | `SP_8` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nilai | 4px | 8px | 12px | 16px | 24px | 32px | 48px | 64px |

Pakai `SP_*` hanya bila nilainya persis sama; jangan membulatkan nilai lain atau
mengikat tinggi/font ke skala jarak.

| Radius | Nilai | Pakai untuk |
| --- | --- | --- |
| `RADIUS_KARTU_BESAR` | 22px | Kartu konten utama |
| `RADIUS_KARTU` | 12px | Menu dropdown, banner peringatan, kartu kecil |
| `RADIUS_SEDANG` | 10px | Tombol dan input Stitch |
| `RADIUS_KECIL` | 8px | Catatan, input kecil |
| `RADIUS_PIL` / `RADIUS_BULAT` | 999px / 50% | Chip, pill / nomor bulat |

Admin memakai radius bersama: kartu utama22px, kartu layanan/menu12px, kontrol10px,
dan pil999px; tidak ada token radius khusus admin.

Breakpoint: `BATAS_HP` 30rem, `BATAS_KOLOM_BACA` 46rem, `BATAS_TABLET` 48rem,
`MULAI_DESKTOP` 64rem, `ANAK_BATAS_HP` 43,75rem; admin memakai ≤820px lokal. Kondisi
`@media` memakai interpolasi Python, bukan `var()`. Breakpoint khusus komponen boleh
tetap lokal.

Bayangan memakai deklarasi utuh `BAYANGAN_*`; varian yang ada sengaja tidak
disamakan. Gerak memakai `DURASI_CEPAT` dan `DURASI_STANDAR`, hanya di layar, dan
harus mati saat cetak serta `prefers-reduced-motion`.

## Ukuran kontrol dan target sentuh

| Token | Nilai | Pakai untuk |
| --- | --- | --- |
| `TINGGI_CTA` | 52px | CTA utama halaman |
| `TINGGI_KONTROL` | 48px | Tombol form, input teks, select, textarea, input berkas di keluarga/murid/admin |
| `TARGET_SENTUH` | 44px | Tautan, `summary`, chip/pill, nav, baris daftar, label centang, tombol ikon inset (mata sandi), tombol kecil, topbar |

`TINGGI_KONTROL` dipakai tombol dan input form di Stitch, akun, profil (filter, pilihan
isi, select Latihan), rentang tanggal laporan, langganan, lampiran (input dan baca
ulang), tombol halaman kelola Pendamping (`GAYA_PENDAMPING`), serta input/select/
textarea dasar `GAYA_GURU` yang tidak ditimpa aturan lebih spesifik. Tab profil juga
48px. Pengecualian yang disengaja tetap 44px:

- topbar/header dan tombol di dalamnya (harus muat `height: 44px`), termasuk tombol
  Keluar di kepala Akun;
- tombol bar Simpan draf/Konfirmasi di tinjauan editorial (versi dasar
  `.koreksi-simpan-st button` 48px) dan tombol ringkas/lewati di kartu tinjauan;
- tombol panel Pendamping inline (`.pendamping-inline button`), tombol kirim bulat
  Pendamping, `.tombol-kecil-st`, dan `.tombol-mata` (inset);
- tombol sekunder ringkas yang juga dipakai sebagai tautan: `.kerja-btn-sekunder-st`
  (halaman murid) dan tombol kelola tautan `.aksi-bagikan-st button` (profil);
- nav, tautan tabel, disclosure, tombol mata sandi dan kontrol topbar admin.

Form/input/tombol aksi/tab admin mengikuti `TINGGI_KONTROL`48px. Toolbar memakai
aksi Cari/Terapkan sekunder, aksi pembuatan utama. Form akun/siswa pendek memakai
`.admin-form-pendek` dengan `LEBAR_KONTEN`46rem; daftar/tabel tetap kanvas fluida.
Pencarian privat tetap POST, form dan guard server tidak diubah oleh presentasi.

Ikon Info ⓘ berdiameter 18px dengan area sentuh 44px.

## Fokus dan state

- Fokus keyboard: `:focus-visible` dengan `outline: {T.TEBAL_FOKUS} solid <aksen>`,
  offset 2px. Jangan `outline: 0` tanpa pengganti yang sama jelasnya.
- Hover tombol solid memakai token `*_HOVER`; tombol berlatar terang memakai
  `LATAR_ELEVASI` atau `filter: brightness` (alasan di riwayat, Penerapan keempat).
- Disabled/read-only tetap terbaca; panel tersembunyi tidak men-disable field
  kecuali fieldset nonaktif `disabled hidden`.
- Galat berbeda dari sukses (warna **dan** teks). Konflik/basi menyediakan jalan
  pulih (tautan GET), bukan kiriman ulang diam-diam.
- Aksi destruktif memakai `confirm()` yang menyebut konsekuensi persis; handler POST
  tetap menegakkan invariant.

## Komponen

| Komponen | Kelas / helper | CSS | Aturan inti |
| --- | --- | --- | --- |
| Kartu | `.st-kartu` | `style_stitch.py` | Putih, `BORDER_VARIAN`, radius 22px, hover border aksen |
| Tombol utama | `.st-tombol-coral`, `a.tombol-coral` | `style_stitch.py` | `AKSEN_KORAL_TUA` berteks putih, hover `AKSEN_KORAL_HOVER`, tinggi 48px |
| CTA rencana | `.rencana-cta-utama-st` | `style_stitch.py`, `child_beranda_style.py`, `profile_workspace.py` | Satu per halaman; 52px (`TINGGI_CTA`), 48px di beranda profil (`profile_workspace.py`); di profil teal |
| Input teks | `.st-input` | `style_stitch.py` | 16px, 48px, fokus border + ring aksen |
| Dropdown | `<select>` native | `form_style.GAYA_SELECT` | Chevron CSS 16px dari kanan, padding kanan 48px; `multiple`/forced-colors tetap native |
| Toggle sandi | `.kolom-sandi`, `.tombol-mata` | `style_stitch.py`, `teacher_style.py`, `admin_style.py` | Wajib di setiap input sandi |
| Info ⓘ | `button.info` + `.info-bubble[role=tooltip]` | `style_stitch.py` | Tanpa JS, `aria-label` = isi bubble; hanya penjelasan produk |
| Disclosure | `.rincian-ui-st`, `.anak-disclosure-st`, `child_components.disclosure()` | `style_stitch.py`, `child_style.py` | Untuk penjelasan sekunder, bukan menyembunyikan status/konsekuensi |
| Chip status | `.anak-chip-st` + nada, `child_components.chip_status()` | `child_style.py` | Nada perhatian/baik/netral/info/galat; selalu berteks |
| Pil filter | `.anak-pil-st[aria-current]`, `child_components.pil_filter()` | `child_style.py` | Tautan GET, aktif = border 2px + latar aksen |
| Badge | `.st-badge` (`diagnostik`, `latihan`, `baru`, `selesai`, `review`) | `style_stitch.py` | Status berteks; "Selesai" = konfirmasi aktif, bukan penguasaan |
| Badge peran | `.badge-peran` | `style_stitch.py`, `child_header.py`, `teacher_style.py` | Pengelola amber, Guru teal |
| Pill kode diagnosis | `.koreksi-status-st.<kode>`, pill lama `.kode.<kode>` | `style_stitch.py` (`CSS_SESI`), `teacher_style.py` | `KODE_*`; hanya permukaan guru |
| Banner tautan | `.anak-banner-st`, `child_components.banner_tautan()` | `child_style.py` | Satu tautan aksi di kanan |
| Kartu sesi | `.anak-kartu-sesi-st`, `child_components.kartu_sesi()` | `child_style.py` | Satu status dan satu aksi per baris |
| Tab profil | `.profil-tabs-st`, `profile_workspace.navigasi_profil()` | `child_header.py` | Beranda, Latihan, Riwayat, Perkembangan; 48px; satu baris di 320px |
| Header | `.st-topbar`, `.menu-pengguna` | `style_stitch.py`, `child_header.py` | Peran + nama dalam satu menu native; satu form Keluar |
| Bar simpan | `.kerja-simpan-strip-st`, `.koreksi-simpan-st` | `style_stitch.py` | Mengikuti aliran form, tidak menutupi kontrol, tidak menggandakan CTA |
| Banner peringatan cetak | `.mesin-banner` | `screen_style.py`, `print_style.py` | Radius 12px |
| Admin | `.admin-kartu`, `.admin-tombol`, `.admin-bahaya`, `.admin-chip`, `.admin-tab`, `.admin-form-pendek`; `admin_komponen.py` | `admin_style.py` | Fondasi bersama, kontrol48px/target44px, adapter tema terang/gelap |
| Pendamping | `.pendamping-tombol`, `.pendamping-tautan` | `assistant_style.py` | Kontrak izin/memori di [runtime Pendamping](pendamping-runtime.md) |

Lembar anak (`/lembar/<id>`) tidak boleh memuat kunci; lembar penilaian memuatnya.
Dijaga `test_web_worksheet.py`.

### Katalog hidup

```bash
cd /Users/nugroho/Documents/jagomat && mesin/.venv/bin/python scripts/design_catalog.py --output <folder-baru>
```

Skrip menulis satu `index.html` statis ke folder baru (tidak menimpa): tabel peran
dan kontras tiap permukaan, skala tipe/jarak/radius, lalu contoh komponen di dalam
`iframe sandbox srcdoc` yang memuat **CSS aplikasi asli** per permukaan (dasar,
profil/ruang guru, tinjauan, akun, admin terang/gelap). Tanpa DB, jaringan, atau
JavaScript; webfont dibuang sehingga teks memakai font sistem. Contoh memakai helper
nyata bila ada (`child_components`, `profile_workspace.navigasi_profil`,
`admin_komponen.badge_status`). `test_design_catalog.py` menolak kelas contoh yang
tidak punya aturan di CSS permukaannya, jadi katalog ikut merah bila komponen
berganti nama. Hover dan fokus tetap harus dicoba langsung di browser. Simpan keluaran
di folder sementara, bukan di repo dan bukan di `mesin/publik/` (folder itu masuk image
dan disajikan publik; katalog memuat contoh gaya kunci/kode diagnosis).

## Bahasa dan konten UI

- Orang dewasa di UI guru disebut **Guru/Anda**; **Pendamping** adalah nama fitur AI.
- Aksi utama berlabel teks. Kartu akun tanpa ikon emoji.
- Tahap belajar memakai enam segmen terbuka dengan satu penanda aktif, bukan
  centang kelulusan.
- Bubble Info tidak memuat kunci jawaban, aturan kritis yang wajib terbaca, atau data
  anak. Jangan memakai atribut `title=` sebagai pengganti (tidak muncul di layar sentuh).

## Pemakaian di kode

```python
import design_tokens as T

# CSS sebagai f-string; kurung kurawal CSS digandakan.
CSS = f"""
.soal {{
  background: {T.LATAR_KARTU};
  border-radius: {T.RADIUS_KARTU_BESAR};
}}
@media (max-width: {T.BATAS_HP}) {{ .soal {{ padding: {T.SP_3}; }} }}
"""
```

- Ubah nilai di `design_tokens.py`, bukan di CSS modul.
- Token baru: tambahkan ke `design_tokens.py`, catat di dokumen ini, dan pastikan
  ada pemakainya (token tanpa pemakai dihapus).
- Gaya tersekop memakai kelas pembungkus permukaan (`.akun-editorial-st`,
  `.profil-workspace-st`, `.guru-beranda-st`), bukan override global.
- Ukuran/progres dinamis boleh inline; gaya statis tidak.

## Workflow halaman atau komponen baru

1. Tentukan jalur risiko menurut `CLAUDE.md`; halaman/alur baru minimal Normal,
   perubahan akses/data tetap Kritis. Mockup baru hanya bila butuh keputusan visual.
2. Pilih permukaan dan keluarga tokennya dari tabel di atas.
3. Pakai komponen yang ada sebelum membuat yang baru; komponen baru dicatat di
   tabel Komponen.
4. Ekstrak nilai visual baru ke `design_tokens.py` bila memang perlu.
5. Render dan lihat dengan data/profil sintetis sesuai
   [workflow](workflow-reference.md#visual-sintetis--desain); jalankan scoped test
   markup/style dan gate jalur.

## Keputusan desain

Usulan mockup/riwayat yang sebelumnya menunggu keputusan diputuskan 25 Okt 2026 atas
rekomendasi agent yang diterima umum oleh pengguna (bukan keputusan per butir).
Membuka kembali salah satunya memerlukan keputusan produk baru.

| Usulan | Keputusan | Alasan |
| --- | --- | --- |
| Header Akun abu rata khusus (canvas "Jagomat Akun Redesign") | Tidak diadopsi | Akun memakai `teacher_shell._topbar_stitch` yang sama dengan ruang guru dan profil; varian header per halaman memecah shell bersama |
| Isi kartu anak terbuka dengan satu tombol Simpan | Tidak diadopsi | Kelola berisi tiga aksi independen (kelas sekolah, sandi anak, hapus anak) dengan form/handler sendiri; satu Simpan mencampur aksi destruktif dengan edit dan mengubah kontrak handler data anak (jalur Kritis) demi kosmetik |
| Tombol Keluar kedua di dasar halaman HP | Ditolak | Melanggar satu aksi satu entry point; audit 24 Okt sengaja menyisakan satu form Keluar di header |
| Ikon, jumlah pesan, dan rentang tanggal di daftar chat Pendamping | Tidak diadopsi | Daftar sengaja hanya metadata minimal; jumlah/rentang butuh query turunan isi percakapan, ikon tidak menambah makna. Pengelompokan per tanggal tetap |
| Meter "0/12 karakter" dan chip paket di header | Tetap tidak diadopsi | Butuh JavaScript baru dan data langganan di header (keputusan 22 Okt) |
| Satu konfigurasi pemuatan font | Tetap per halaman | Halaman privat tanpa aset jaringan; sumber font mengikuti CSP masing-masing |
| Admin satu design system | Disetujui pengguna setelah audit lanjutan | Menggantikan pengecualian palet/skala admin25 Okt: token terang, logo, tipe, radius, spacing dan kontrol48px bersama; sidebar/tabel serta adapter gelap tetap |
| Lembar latihan ikut teal tunggal | Ditunda | Lembar dibekukan gate rilis question pair; perlu pembaruan pasangan recovery tersendiri |
| Sisa literal `font-size` di luar skala | Bertahap | Dikunci ratchet `test_type_scale.py`; tiap penyamaan dirender per permukaan |

Tindak lanjut terbuka: PDF statis riset publik di `mesin/publik/` dibuat sebelum teal
disatukan; isinya sama, tetapi aksen tealnya sedikit berbeda dari HTML sampai PDF
dibuat ulang dari renderer.

## Batas verifikasi

Safari/iOS, screen reader nyata, HP/printer fisik, dan semua kombinasi data/state
belum dibuktikan. Kontras dan ukuran di dokumen ini adalah target desain yang
diuji pada data sintetis, bukan sertifikasi aksesibilitas.
