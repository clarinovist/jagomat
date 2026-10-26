# Audit ulang UI/UX admin — 25 Oktober 2026

**Pembaruan setelah audit lanjutan:** pengguna meminta satu design system Jagomat.
Pengecualian palet/skala/44px seluruh admin di catatan historis berikut telah
digantikan oleh [fondasi bersama](design-system.md#warna); rincian verifikasi
implementasi lokal ada di [bagian akhir](#penyatuan-fondasi-admin-dengan-jagomat).
Catatan deployment di bawah tetap milik artifact audit sebelumnya, bukan restyle baru.

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

## Penyatuan fondasi admin dengan Jagomat

Implementasi lokal mengikuti permintaan pengguna: admin adalah varian layout,
bukan sistem desain terpisah. Seluruh31 warna terang `ADMIN_*_CERAH` kini alias
token dasar/profil; tidak menambah hex. Skala tipe/radius admin dihapus: body16,
judul22–26, bagian18, angka24, kartu22/kecil12, kontrol10 dan48px. Tujuh literal
tipe di luar skala hilang; spacing mengikuti skala bersama. Adapter gelap existing,
sidebar256px, tabel scroll internal dan kontrol topbar/nav44px tetap.

- Logo memakai mark lokal bersama, terlihat satu kali per viewport. HP memakai
  logo + akun satu baris dan menu di bawah; nama panjang tetap membungkus.
- Form akun/siswa pendek dibatasi46rem; tabel tetap fluida. Cari/Terapkan sekunder,
  pembuatan akun utama; routes/field/CSRF/reauth/konfirmasi dan POST tidak berubah.
- Guard alias/tipografi/radius/logo ditambahkan, test brand HTTP mencakup `/admin`.
  Peta peran/kontras juga mencakup brand, fokus dan badge admin terang/gelap.
- **451 tes scoped lulus** (19,27s, Python3.9.6, warning-as-error), kompilasi12 berkas
  lulus. Semua token non-admin identik baseline`10a48a7`; lembar tidak direstyle.
- **510 render final**:51 halaman/state x320/375/768/1024/1440 xterang/gelap, seluruh
  respons200; tanpa overflow dokumen, kontrol kecil pada pemindai, field tanpa label
  atau input di bawah16px. DOM form: input48px, radius10px, kartu22px, maks736px.
- Keyboard skip/nav/tabel, tiga pilihan tema, mata sandi, pembatalan hapus,
  pencarian POST dan fallback tanpa JS lulus. Stress teks200% pada4 halaman tidak
  overflow. Print menimpa tema gelap ke cream dan menyembunyikan shell; reduced
  motion tanpa animasi/transisi. Screenshot sintetis ditinjau, estimasi visual
  diperiksa kembali dengan DOM (bukan klaim ukuran berdasarkan gambar saja).

Bukti lokal di `/tmp/jagomat-admin-shared-PJ7oj7/`: log, metrics, screenshot,
interactions/probe dan katalog hidup. Review mandiri, bukan reviewer independen.
`docs/context.md` dan kontrak desain diperbarui; `docs/spec.md` tidak terdampak
karena fitur/akses tetap. Full suite/CI dan deploy belum dilakukan untuk restyle
ini; perlu gate exact sebelum rilis. Safari/iOS/perangkat fisik, screen reader,
forced-colors OS dan seluruh state produksi belum diverifikasi.

## Penuntasan audit lanjutan — 26 Oktober 2026

Audit render sintetis membandingkan produksi `5ae9b00` (masih palet/skala admin
terisolasi, logo "J", tanpa logo di HP) dengan HEAD `b8aea69` (fondasi sudah alias).
Sisa gap HEAD ada di tingkat komponen; acuannya kini tercatat di
[design system](design-system.md#komponen). Font halaman privat/admin diputuskan 26 Okt 2026:
mengikuti design system (font sistem, tanpa webfont/aset jaringan).

| Severity | Temuan | Perbaikan |
| --- | --- | --- |
| Medium | Cari/Terapkan/Saring dan pager pencarian Langganan masih primer di 6 tempat; guard hanya Keluarga | Semua sekunder; `_form_filter` tanpa pilihan kelas; guard render 8 halaman + pindai sumber |
| Medium | Tombol sekunder navy/abu, keluarga teal | Garis + teks aksen, hover latar aksen; pasangan peran terang/gelap |
| Medium | Chip bukan Pil filter (garis gelap, aktif 1px, 48px) | Nilai `.anak-pil-st`: garis `ADMIN_BORDER_PIL`, aktif 2px teal, 44px |
| Medium | Menu akun bersegitiga bawaan + badge | Peran di atas nama + chevron, marker disembunyikan |
| Low | Tab, jangkar Operasional dan chip sama-sama pil; tab terpotong di HP | Tab bergaris bawah (pola tab profil) dan membungkus; jangkar jadi tautan teks |
| Low | "Normal" hijau di daftar, netral di detail | Satu helper `badge_status(())`, netral |
| Low | "← Kembali" berbentuk tombol; detail Langganan tanpa kembali | `.admin-jejak` teks teal 44px; tautan kembali Langganan |
| Low | Lebar sandi konfirmasi 20rem/46rem/kanvas penuh | Selebar kolom, maks. 46rem; form bulk pilih pendek |
| Low | "—" umur tanpa label; dua "Buka operasional" | Teks layar-baca saja; CTA antrean "Periksa backup" → `#kesiapan` |
| Low | Badge status tabel AI terlipat per kata di 375px; kartu batch bisa punya 3 tombol primer | Badge min. 12rem; aksi pertama solid, sisanya sekunder |

Verifikasi lokal: regression 14 test baru merah pada salinan HEAD lalu hijau;
scoped **1.078 tes lulus** (52s, Python3.9.6, `-W error`), kompilasi 15 berkas.
Render 51 halaman/state × 375/1440 × terang/gelap (**204**, semua 200): tanpa overflow,
kontrol <44px, field tanpa label atau input <16px. Interaksi native 22/22: keyboard
menu akun, hover sekunder/pil, tab, jangkar, tautan kembali, menu HP dalam viewport,
tema Gelap→Sistem. Chrome headless profil sementara, DB/sandi temp; bukan data keluarga.
Rilis: gate dispatch 14.663 tes kandidat dan controlled deploy `54f1903` (26 Okt, healthy;
[rincian](production-release.md#deploy-komponen-admin--26-oktober-2026)). Belum: Safari/iOS/Android
fisik, screen reader, forced-colors OS.
