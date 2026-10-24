# Audit ulang UI/UX admin — 25 Oktober 2026

Acuan: [design system](design-system.md), `design_tokens.py` (`ADMIN_*`) dan
komponen server-side yang aktif. Ini penyelarasan, bukan desain baru. Admin tetap
font sistem, teal/netral, sidebar256px, kartu16px dan tema Sistem/Terang/Gelap.
Tidak ada dependency atau JavaScript baru; perubahan presentasi tidak mengubah
CSRF, payload form, otorisasi, billing, riset, atau data belajar.

## Temuan dan perbaikan

| Severity | Bukti sebelum | Perbaikan |
| --- | --- | --- |
| Medium | Tautan Lewati navigasi menggulir tetapi fokus tetap BODY | Target `main` memakai `tabindex=-1`; fokus browser menjadi MAIN tanpa tab stop tambahan |
| Medium | Batas kontrol terang hanya1,37:1 terhadap putih | `ADMIN_BORDER_KUAT_CERAH` menjadi `#7C8B88`; batas kontrol ≥3:1 terhadap permukaan/latar, tanpa menggelapkan border kartu |
| Medium | Tautan Isi riset sekitar15×23px; item terakhir terbungkus | Komponen `admin-tautan`, tidak menyusut, label aksesibel menyebut topik; tombol konsisten ≥44px |
| Medium | Tautan tabel selain kolom terakhir hanya16–23px tinggi | Seluruh kolom memakai target minimal44×44px; fokus inset agar tidak terpotong wadah scroll |
| Medium | Selesaikan wawancara disabled tetap teal/kursor pointer | State nonaktif netral + not-allowed; read-only/disabled field dibedakan tanpa mengubah atribut/validasi |
| Medium | Tema Gelap manual menang terhadap CSS print | Selektor print menyamai spesifisitas tema manual; halaman cetak kembali terang |
| Medium | Form hapus profil kosong tidak memicu konfirmasi browser existing | `data-konfirmasi` menjelaskan login+profil dihapus dan tidak dapat dibatalkan; checkbox/reauth/server guard tetap |
| Low | Header seluler memotong Admin-C ketika label menu panjang | Topbar membungkus per kontrol; nama panjang tetap utuh, dropdown dibatasi viewport |
| Low | Tombol bulk/pager/tautan operasional memakai gaya native atau target kecil | Komponen primary/secondary/pager bersama, gap antartombol; query dan field tetap |
| Low | Dua aksi riset sama-sama primary, penghentian consent berdekatan | Simpan draf/redaksi sekunder, area destruktif dipisahkan warna/border; konsekuensi dan signed form tetap |
| Low | Semua checkbox tampak sebagai peringatan amber | Pilihan biasa netral; penghentian AI/destruktif mempertahankan warna bahaya |
| Low | Ringkasan menimpa line-height badan menjadi normal | Mengikuti line-height1,6 shell; min-width grid operasional dibatasi wadah |

## Cakupan

Inventaris source mencakup seluruh11 bagian `admin_pages.SECTION` (Perhatian
rute tersendiri, bukan menu ganda), renderer AI/sensor, riwayat dan form bulk.
**51 halaman/state sintetis**, masing-masing dirender pada320/375/768/1024/1440px,
light+dark: **510 render**, seluruh respons200, tanpa overflow dokumen. Tabel
lebar tetap scroll internal; bukan diubah menjadi tabel yang menyembunyikan kolom.

- Ringkasan: kosong/berisi, antrean mendesak, nama/ID panjang, kondisi layanan.
- Keluarga/Siswa: daftar/detail, buat akun, reset, cabut sesi, hapus login,
  kelas sekolah, profil warisan, buat login, hapus profil kosong, credential sekali tampil.
- Pendaftaran: buka/tutup; bulk pilih/impor/perhatian/hasil; audit batch daftar/detail.
- Langganan: kosong/berisi, pager, detail invoice; Perhatian kosong/berisi/pager.
- KPI: kosong/berisi, sensor agregat/supresi; Operasional belum siap/siap.
- AI: status, tabel, pagu, penghentian, tes, riwayat pengaturan.
- Riset: daftar/filter/pager, wawancara draf/final, pertanyaan editable/read-only,
  kode jawaban terbuka, matriks kosong/berisi.
- Riwayat admin/AI/batch; state galat sintetis.

HTTP nyata memakai server fixture terisolasi; state langka memakai renderer
produksi dengan DTO sintetis, **bukan** bukti semua mutasi server diuji melalui browser.
Form/negative-path diperiksa terpisah melalui regression test HTTP.

## Verifikasi

- Browser Chrome headless, profil sementara, koneksi preview loopback. Tidak memakai
  akun, DB, backup, sandi, atau screenshot keluarga nyata.
- Keyboard: skip link, menu seluler, scroll tabel; pointer: pencarian POST (nama
  tidak di URL), tiga pilihan tema (override preferensi sistem), mata sandi,
  batal hapus login/profil, menu dan pencarian tanpa JS.
- Text stress200% pada Ringkasan/Operasional/Riset/AI tanpa overflow dokumen.
  Ini simulasi pembesaran teks, bukan pengujian zoom/perangkat fisik.
- Screenshot awal/akhir ditinjau visual dan dicocokkan DOM: kontrol Dukungan
  semuanya47,59px, font16px; tombol Lihat67,45×44,39px. Dugaan visual ukuran kontrol
  berbeda ditolak karena DOM membuktikan sama.
- Regression baru awal6 gagal pada masalah yang ditargetkan, lalu hijau.
  Kontrak form11 bagian, tema, akses negatif, konfirmasi/CSRF, riset, bulk,
  markup AI, token dan state UI: **638 tes lulus** (47,24s, Python3.9.6,
  `-W error`), compile8 berkas lulus. Print manual Gelap terbukti kembali ke
  latar terang rgb(246,248,248) dengan sidebar tersembunyi.
  Gate rilis [40142093633](https://github.com/clarinovist/jagomat/actions/runs/40142093633)
  sukses pada `7695cf9`: **14.341 tes kandidat exact-once**, empat shard recovery,
  build/probe/pair. CI push dibatalkan oleh push dokumentasi sesi backup lain,
  bukan kegagalan test; gate dispatch exact tetap selesai penuh.

Bukti lokal ignored: `docs/plan/admin-audit-20261025/` (script preview, metrics JSON,
screenshot sintetis, log pengujian). Audit ini tidak menyertifikasi WCAG menyeluruh:
Safari/iOS/Android fisik, screen reader, forced-colors OS, dan seluruh kombinasi data
produksi belum diuji. Escape/click-outside pada menu native tidak ditambahkan karena
memerlukan enhancement JS baru. Batas akses, kesiapan pembayaran dan izin riset
bukan target perubahan.

## Produksi

Controlled deploy memasang `7695cf9a5450029a71d8e88d9a351439155233cf` pada
25Oktober2026 06.30WIB, healthy/restart0. Preflight live read-only dilakukan sebelum
hold; backup4DB+auth dan riset terpisah, rehearsal C2–B2–C2, validator, transfer/hash
privat serta approval exact-pair lulus. Histori dan konfigurasi tetap; tidak ada migrasi.
Probe sintetis dalam memori container membuktikan patch UI tersedia. Smoke publik
`/`200, `/akun`401, `/murid/`303 menuju `/masuk`; marker galat0.
[Identitas artifact/recovery dan rincian rilis](production-release.md#deploy-audit-ui-admin--25-oktober-2026).
Backup induk/receipt disimpan privat; empat turunan rehearsal dan container probe
milik tugas sudah dibersihkan. Ini bukan walkthrough akun keluarga nyata.

`docs/spec.md` dan `docs/context.md` diperiksa: kontrak produk dan arsitektur tetap;
hanya tautan referensi audit admin ditambahkan pada konteks/desain.
