# Rencana redesain panel pengelola

## Mandat dan batas

Brief: `/Users/nugroho/Downloads/jagomat-admin-redesign.zip`, 19 Oktober 2026.
Referensi privat diekstrak di luar Git: `../osn-resources/referensi/jagomat-admin-redesign/`.
Pengguna menyetujui seluruh fase pada percakapan ini, termasuk delegasi bila perlu.
Branch `feat/admin-redesign`, baseline `39f7530`. Tidak merge/push main atau deploy.
Worktree terisolasi `../jagomat-admin-redesign` melindungi WIP latihan/laporan sesi lain.
Satu penulis; scout/reviewer hanya membaca source relevan, tanpa data/backup.

Jalur **Normal**, lintas renderer. Backend, skema, endpoint, CSRF/reauth,
field/metode/nilai form, guard, query privat via POST, dan urutan data kanonis tetap.
Jika perubahan invariant diperlukan, pisahkan dan naikkan jalur; bukan diam-diam
mengubah backend untuk menyesuaikan mockup.

## Fase 0 — discovery

- Stack: Python stdlib, HTML lewat string renderer server-side, SQLite. CSS berupa
  string Python `GAYA_ADMIN`, token di `design_tokens.py`, tanpa bundler/framework.
  Font sistem lokal. Tidak ada gate npm/linter/typechecker aplikasi.
- Kerangka, sidebar desktop/mobile, judul/footer, Ringkasan/Keluarga/Siswa,
  Pendaftaran/Riwayat: `mesin/admin_pages.py`; CSS `mesin/admin_style.py`.
- Layanan Langganan/Perhatian/Operasional/KPI: `admin_launch_pages.py`, adapter
  `admin_launch_http.py`. KPI juga menyertakan sensor existing; tidak boleh hilang.
- AI: `ai_pages.py`, `ai_http.py`; riset: `admin_research_pages.py`,
  `admin_research_http.py`. Semua memakai `halaman_admin`.
- Navigasi: `SECTION`, `GRUP_SECTION`, `_nav`; desktop dan disclosure mobile memakai
  builder sama. `aria-current` dari section. Rute perhatian dipisah dari daftar menu,
  tidak dihapus dari validasi section.
- Komponen reusable: `admin-kartu`, `admin-tombol`, `admin-tautan`, `admin-chip`,
  `admin-badge`, `admin-tabel-wrap`, `admin-form-cari`, `admin-info`, toggle sandi.
- Ringkasan: `admin_queries.ringkasan_admin` menghitung akun/siswa/login/sesi dan
  proyeksi kondisi akun; `admin_operations.antrean` memberi antrean lintas sumber;
  `admin_store.daftar_riwayat` memberi uncertain/reserved; registrasi dan konfigurasi
  pembayaran dibaca di GET `admin_http`. Urutan aktivitas sudah WIB dan dibatasi 10.
  Status backup ringkasan saat ini hanya tautan pemeriksaan, bukan bukti kegagalan.
- Filter keluarga: `memiliki_anak=semua|ya|tidak`, `status=semua|perlu_perhatian`.
  Siswa: tingkat P3–P6, keluarga ID, kondisi spesifik. `normal` dan agregat
  `perlu_perhatian` siswa tidak boleh diasumsikan didukung. Search privat POST;
  jangan mengubahnya menjadi GET atau membocorkan alias/nama lewat chip.
- AI stop switch adalah field `dihentikan` pada form pengaturan, bukan endpoint
  darurat mandiri. Riset ekspor adalah POST signed, bukan tautan GET.
- Tes: `test_admin_pages`, `test_admin_navigation_style`, `test_admin_http_*`,
  `test_admin_launch_*`, `test_admin_research_*`, `test_ai_admin_*`, dan security.
  Tes markup/style tersedia; tidak ada snapshot visual browser kanonis.
- Baseline scoped: **77 lulus** (pages/navigation/security/launch final/research HTTP/
  AI audit). Bukti `/tmp/jagomat-admin-baseline.log`. Semua 11 rute utama 200 pada
  `ServerUji` dengan SQLite/auth temp; HTML, screenshot desktop/mobile dan kontrak
  form baseline di `/tmp/jagomat-admin-before`. Preview tidak memakai `serve.py`.

## Fase implementasi

1. **Fondasi** — token khusus admin (tanpa mengubah tema publik), CSS, sidebar
   datar/mobile disclosure, footer tunggal, komponen dan fokus. Tes struktur dan
   perbandingan form; commit terpisah.
2. **Halaman utama** — kamus label/tanggal, antrean kategori tanpa angka palsu,
   layanan, aktivitas, chip filter didukung, keluarga/siswa. Query baru opsional
   tidak otomatis masuk scope. Tes proyeksi, XSS, POST privat, paginasi, HTTP.
3. **Layanan/sistem** — pendaftaran, langganan, KPI/sensor, operasional/stepper,
   AI, riwayat, riset dan perhatian. Kontrak form sebelum–sesudah harus sama.
4. **Pemolesan** — error/empty states, 390/768/1100/1280 px, keyboard, target
   sentuh 44 px, kontras, cleanup selector terbukti mati, reviewer dan CI.

## Acceptance dan verifikasi

Semua halaman memakai tema baru; tidak ada perubahan data/security/field/action;
route/filter lama hidup; guardrail tetap; status berteks, tidak hanya warna;
header tabel nowrap dengan scroll internal, tidak ada page overflow; satu h1,
focus/skip link/meta privat utuh; tidak memuat font/JS eksternal.

Lokal: pytest scoped warning-error, compile file Python, review diff dan palang
index setelah stage scope sendiri. Bukti HTTP/DOM dan screenshot memakai data
sintetis baru. Full suite lintas modul lewat CI pada SHA branch exact; tidak deploy.
Jika CI branch tidak menjalankan full gate, gunakan dispatch yang sudah tersedia.
Catat gate terblokir secara jujur. Tiap fase commit sendiri, penyimpangan dalam
`redesign-decisions.md`. Pemulihan: kembalikan commit branch yang bersangkutan;
tidak ada migrasi, mutasi produksi atau recovery DB.
