# Audit konsistensi UI — 24 Oktober 2026

Audit G2 menutup inkonsistensi presentasi yang teridentifikasi, **bukan** pengesahan
seluruh aksesibilitas/perangkat atau perubahan produk. Data browser/test seluruhnya
sintetis; tidak ada akun anak, DB produksi, atau provider AI yang dipakai untuk test.
Status rilis terpisah di [runbook](production-release.md).

## Pola yang dipertahankan

| Permukaan | Wadah dan navigasi |
| --- | --- |
| Landing | `LEBAR_LANDING` 75rem/1200px, kanvas marketing |
| Ruang guru | Kolom baca `LEBAR_KONTEN` 46rem; kartu daftar satu kolom |
| Profil anak dan laporan lama | `ANAK_LEBAR` 60rem/960px **isi**, gutter32px desktop/16px HP; empat tab/header bersama |
| Akun | Wadah72rem dua kolom; persetujuan tinjau/Data Pendamping46rem |
| Tinjauan/cetak/lampiran | Wadah editorial60rem termasuk padding; kembali ke konteks sesi/riwayat |
| Admin | Sidebar256px, kanvas fluida, tema Sistem/Terang/Gelap dan font sistem tersendiri |
| Murid/lembar | Kanvas latihan dan cetak A4 sendiri; tidak dipaksa mengikuti lebar guru |

“Konsisten” tidak berarti semua halaman960px. Kembali tetap kontekstual: profil
memakai **Semua anak** pada baris identitas; halaman tugas memakai tautan sebelum
judul; admin memakai navigasi hierarkis. Shell404 generik tetap tanpa aksi otomatis
agar respons resource yang tidak boleh diakses tetap identik.

## Perbaikan yang diterapkan

| Temuan | Penutupan |
| --- | --- |
| Laporan lama berganti lebar/header saat pindah subtab | Memakai shell profil yang sama, parsing query dan isi bukti tetap; CSS rincian legacy dipertahankan khusus laporan dalam stylesheet terpisah |
| Tab Perkembangan terpotong di HP | Padding/gap mobile dipadatkan, label14px dan target48px; empat tab utuh pada320/360/390px |
| Select Latihan kalah cascade shared | Selector tersekop menang; border/radius token anak, chevron dan padding kanan native tetap |
| Grid Gabungan dan pagu AI melampaui ruang kartu320px | Minimum track dijepit terhadap100% ruang tersedia; tidak menyembunyikan page overflow |
| Input mewarisi label14px | Kontrol teks editorial/admin16px; label/body admin tidak dibesarkan global |
| Pil Riwayat berbeda warna/padding | Token inactive/active shared, kompensasi border aktif |
| Metadata Riwayat dan label tahap HP12px | Naik14px secara tersekop, bukan mengganti token meta global |
| Ikon status privat menjadi kata `task_alt`/`cancel`/`history` | SVG lokal dekoratif; tidak membuka CDN/CSP |
| Teks Keluar coral terang | Token coral text-safe; kontras dihitung dan computed color diperiksa |
| Akun mempunyai dua form Keluar | Satu form header, item topbar dihilangkan hanya untuk caller Akun; caller lain tetap mempunyai Keluar |
| Pendaftaran tertutup dua tautan Masuk | Satu pintu Masuk di topbar; keadaan ditutup/tidak tersedia tetap jelas |
| Opsi kode riset semua bernama “Utama/Tambahan” | Nama opsi masuk accessible name setiap kontrol; nilai POST/readonly tetap |
| Tabel AI/daftar admin/persaingan sulit dijangkau keyboard | Region scroll bernama dengan tabindex/fokus, tanpa JS baru |
| Tema/consent riset target kurang44px | Target diperluas44px; tema dan izin tetap form native |
| Waktu refill berupa epoch; empty state salah nama menu | Tanggal WIB terbaca; langganan kosong menuju tab Anak tanpa mengaktifkan checkout |
| Konflik pilihan data berakhir tanpa pemulihan |409 memiliki tautan GET untuk mengambil form baru, tidak mengirim ulang persetujuan basi |

Review independen menangkap regresi sementara hilangnya CSS rincian/cetak dan posisi
`@import` admin saat menyatukan shell; semuanya diperbaiki sebelum penerimaan patch.
Aturan print tersekop menyembunyikan topbar/tab/kembali; override layar tetap utuh.

## Bukti verifikasi

- HTTP browser Chrome headless, profil temp: landing/login/daftar/legal/bantuan,
  guru, empat tab profil, nama panjang/profil kosong, tiga tab Akun, tinjauan
  siap/terkirim/selesai/batal, laporan lama dan rincian catatan/tren/tugas pada kedua
  URL, Kelola Pendamping, murid/pengerjaan, cetak/lampiran, panel admin dan riset publik.
  Viewport320,360,390,768,1280px; tidak ditemukan page overflow/error JS pada jalur
  yang tersedia. Tabel scroll internal bukan page overflow.
- Snapshot renderer untuk gate/tinjau persetujuan, daftar tertutup, langganan kosong,
  formulir riset dan kuota; layanan gated tidak dinyalakan. Endpoint foto murid hanya
  POST: halaman GET terpisah memang tidak tersedia, bukan dihitung halaman lulus.
- Keyboard Enter/Spasi pada menu, accordion tinjauan, ArrowRight pada tabel admin;
  pointer toggle sandi/tiga mode Latihan; fallback form GET tanpa JavaScript;
  tema admin cerah/gelap, CSSOM font admin, emulasi print kedua peran.
- DOM: target header44px/tab48px, grid Gabungan254px di ruang254px, grid AI204px
  di ruang204px pada320px; input16px. Dasar konten profil berada di atas tombol
  Tanya saat scroll paling bawah. Pembesaran relatif teks200% diuji pada form Gabungan.
- Regression baru `test_ui_consistency.py`;14 assertion perilaku merah pada salinan
  HEAD sebelum perbaikan, hijau setelah patch. Tes existing terkait, compile Python3.9,
  palang index dan full suite CI adalah gate terpisah; angka/status CI dicatat saat rilis.
- Dua scout read-only dan reviewer fresh; pemeriksaan ulang reviewer atas temuan
  berakhir **OK**. Screenshot diperiksa visual dan dibandingkan dengan DOM, bukan
  menganggap estimasi vision sebagai ukuran CSS.
- JEV `jev-1.14.0`, rubrik sama sebelum/sesudah: konsistensi bingkai laporan1,83→2,65
  dari3; sinyal tab utuh0,53→0,97. Hanya tiga screenshot sintetis tiap evaluasi,
  satu evaluasi ulang. Ini sinyal probabilistik terbatas, **bukan ukuran mutu seluruh UI**.

Bukti lokal sementara di `docs/plan/ui-audit-20261024/` (ignored); tidak berisi data
pengguna nyata. Audit tidak mengubah auth/ownership, schema, reducer, penilaian,
aktivasi paket atau izin data. [Spec](spec.md) tidak berubah cakupan; [context](context.md)
dan [design system](design-system.md) diperbarui untuk komposisi shell.

## Batas yang tetap terbuka

Safari/iOS, HP/printer fisik, screen reader nyata, semua kombinasi data/state, serta
uji performa transkripsi guru belum dibuktikan. Panel AI diuji tanpa provider;
checkout aktif/QRIS/pembayaran dan pengiriman foto bukan transaksi audit ini.
Tidak menambah JavaScript atau dependency. Perubahan header/desain akun yang masih
menunggu keputusan pada design system tidak diadopsi diam-diam.
