# Verifikasi redesain admin — hasil lokal

## Status fase

| Fase | Hasil lokal |
| --- | --- |
| 0 Discovery | Peta kode, batas data/form, baseline dan keputusan tercatat. |
| 1 Fondasi | Token admin terisolasi, komponen, sidebar datar, disclosure mobile, footer tunggal. |
| 2 Halaman utama | Ringkasan berbasis kategori; aktivitas berurutan per siswa/hari; daftar keluarga/siswa dan chip filter yang didukung. |
| 3 Layanan/sistem | Pendaftaran, langganan, KPI/sensor, operasional, AI, riwayat, riset dan rute perhatian. |
| 4 Pemolesan | Error/empty state, tabel, ID salinan, label login lama, hover bahaya, tes dan review. |

Implementasi lokal selesai dengan penyimpangan konservatif yang tercatat pada
[keputusan](redesign-decisions.md). Ini **bukan** bukti rilis atau deploy.
Tidak push, merge main, deploy, atau mutasi produksi. WIP checkout utama tidak disentuh.

## Bukti yang dijalankan

- Baseline awal: 77 tes scoped lulus. Fase 1: 65; fase 2: 89; fase 3: 86.
- Scoped akhir: **560 passed, 51,35 detik**, Python lokal 3.9.6, warning-error:
  `python -m pytest mesin/__tests__/test_admin*.py mesin/__tests__/test_ai*.py
  mesin/__tests__/test_school_profile_admin.py mesin/__tests__/test_support_settings_http.py
  mesin/__tests__/test_sensor*.py -q -W error -p no:cacheprovider`.
  Mencakup HTTP/otorisasi/CSRF/reauth, mutation existing, query, riset, AI, sensor,
  kontrak form baru serta regresi tiga finding reviewer.
- Tes kontrak 11 halaman membandingkan metode/action/nama/tipe/required/disabled/
  min/max/step dengan baseline sebelum redesain. Fixture hanya struktur, tanpa token
  atau data pengguna. Nilai dinamis bukan bagian golden ini.
- Perbandingan DOM browser terpisah pada baseline exact `39f7530` dan hasil akhir:
  semua form 11 halaman identik, termasuk nilai input, checkbox checked, opsi/select
  selected. Hanya token signed dan ID akun acak sintetis dinormalisasi. Dukungan
  diuji dengan konfigurasi sintetis valid di kedua baseline/kandidat.
- HTTP `ServerUji` seluruh 11 halaman 200; DB/auth/AI/riset hanya temp. Tidak memakai
  `serve.py`, tidak memanggil provider, tidak membaca backup nyata.
- Chrome headless profil sementara: 390, 768, 1100, 1280px; tidak ada overflow
  halaman, satu h1, kontrol utama ≥44px, header tabel nowrap, tanpa pageerror.
  Scroll tabel internal disengaja. Screenshot sebelum/sesudah desktop/mobile tersedia.
- 11 halaman pada 390px, semua disclosure dibuka: tetap tanpa page overflow,
  input memiliki label, th scope tersedia, kontrol utama ≥44px. Tab pertama ke
  skip link dengan outline terlihat, Enter ke `#konten-admin`; menu mobile dapat
  dibuka dengan keyboard. Bukan audit screen reader/Safari penuh.
- Kontras dihitung dari computed color/background: teks normal ≥4,5:1, teks besar
  ≥3:1 pada teks terlihat dari 11 halaman sintetis; tidak ada pasangan gagal.
  Estimasi visual model tidak dipakai sebagai ukuran CSS persis.
- Detail keluarga/siswa, form tindakan dan error juga dirender. Pointer-hover pada
  tautan bahaya awal mereproduksi putih/abu terang; setelah fix putih di atas
  `rgb(127,29,29)`. Tes cascade selector ditambahkan.
- Reviewer independen menemukan ID terpotong, label login warisan, hover bahaya.
  Ketiganya diperbaiki dan re-check **OK with notes**, tidak ada finding baru dalam
  cakupan fix. Reviewer tidak menjalankan tes sendiri.
- Palang index dan `git diff --check` lulus pada checkpoint; compile source tanpa
  import dijalankan. `spec.md`, `context.md`, design system disinkronkan.

## Belum dijalankan / tidak termasuk

- **Full suite CI, build image, deploy** belum dijalankan karena push ditahan.
  Jangan menyatakan branch sudah lolos gate rilis. Full suite exact SHA tetap
  diperlukan sebelum merge/rilis sesuai workflow repo.
- Tidak menambah linter/typechecker/npm gate karena proyek tidak memilikinya.
- Tidak mengubah domain/backend/schema/guard; tidak ada guard keamanan baru yang
  perlu mutation baru. Mutation existing yang masuk tes scoped tetap dijalankan.
- Tidak ada pengujian Safari/perangkat fisik/screen reader atau semua kombinasi
  state data dunia nyata. Form mutasi diuji oleh tes HTTP sintetis, bukan mengklik
  aksi produksi dalam screenshot.
- Fitur opsional mockup dan facet count yang tidak tersedia tidak dibangun;
  lihat keputusan. Kesetiaan struktur/komponen, bukan salinan pixel-exact prototipe.

## Artefak

Bukti privat dan screenshot disimpan di luar Git pada
`../osn-resources/referensi/jagomat-admin-redesign/evidence/`.
Script capture/DOM tersimpan bersama bukti untuk reproduksi. Referensi desain
asli tetap di direktori saudara tersebut. Tidak ada DB/auth nyata pada artefak.
