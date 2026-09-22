# Soal visual — verifikasi dan rilis bertahap

## Status pekerjaan lanjutan — 18 September 2026

**DIBATALKAN (cancelled)** atas permintaan pengguna: penerimaan soal visual pada
HP/printer fisik serta pengembangan/penerimaan representasi nonvisual K4.
Keduanya bukan backlog aktif; pembukaan kembali memerlukan keputusan baru.
Lihat [keputusan pembatalan](README.md#keputusan-pembatalan-pengembangan--18-september-2026).

Implementasi visual yang sudah ada tidak dibatalkan. Uji perangkat tetap belum
dilakukan dan K4 tetap nonaktif/belum diterima sebagai tugas ekuivalen.
Pembatalan bukan kelulusan, pengecualian gerbang aktivasi luas, atau izin mengubah
konfigurasi/produksi. Kontrak dan batas klaim di bawah tetap berlaku.

## Kontrak implementasi

- SVG deterministik dari proyeksi allow-list, bukan gambar AI atau parameter mentah.
- Snapshot pertanyaan milik butir sesi; mematikan keluarga tidak mengubah snapshot yang sudah dibuat.
- `OSN_VISUAL_KELUARGA` default kosong. Nilai yang didukung: `statistika`, `geometri-datar`, `geometri-ruang`, `pengukuran`, `kombinatorik`, `pola-bilangan`; pisahkan dengan koma. Nilai asing gagal terlihat.
- Bantuan belajar terpisah dari pertanyaan dan tidak masuk evaluasi/checkpoint.
- `penyajian_outcome` adalah provenance append-only yang ditautkan ke `snapshot_outcome`. Ia tidak menambah bukti pedagogis atau mengubah fingerprint konfirmasi lama.
- Konfirmasi baru dan provenance atomik. Backfill hanya mengisi metadata hilang dari hubungan/snapshot tervalidasi; sumber rusak atau hilang menggagalkan migrasi, bukan ditebak sebagai teks.
- Loader membaca provenance tanpa penulisan. Kunci fokus tetap `(template_id, kode_intervensi, malrule_id)`.

## Pemisahan bukti

Reducer memilih representasi dari sesi sah terbaru per template dalam konteks putaran/level. Sesi manual tanpa opt-in, milik siswa lain, dibatalkan, belum selesai, atau belum dikonfirmasi tidak boleh menentukan pilihan tersebut. Dua representasi untuk template sama pada sesi terbaru dianggap ambigu, bukan digabung.

Bukti dengan representasi berbeda tidak menjumlahkan kelemahan, jumlah probe, atau kegagalan. Checkpoint harus sesuai dengan evaluasi sah terbaru dan dibuat setelah evaluasi itu; bagian checkpoint sebelumnya tidak dilanjutkan. Pemetaan yang butirnya dilewati tidak dianggap pergantian representasi. Riwayat asli tetap disimpan, dan profil/laporan menjelaskan ketika ringkasan memakai kelompok representasi terbaru.

## Gate verifikasi Fase 8

Daftar ini mencatat cakupan penerimaan teknis, bukan kewajiban menjalankan suite
berat/Docker lokal. Eksekusi mengikuti [kebijakan resource](../CLAUDE.md#izin-tetap--resource-lokal):
scoped test lokal, full suite/sweep/build di CI atau lingkungan terisolasi.

- Suite Python 3.9 dengan warning-as-error; unit, integrasi, HTTP dan golden generator.
- Sweep seluruh komposisi 100 seed; 500 untuk pasangan visual. XML, finite, namespace/referensi, anchor teks dan batas primitif, serta inventaris varian diperiksa. Invariant matematika per keluarga tetap diuji terpisah.
- Dua proses/PYTHONHASHSEED menghasilkan snapshot/HTML identik.
- Payload label/namespace berbahaya, kontras, ARIA, penanda nonwarna dan larangan jawaban diuji.
- HTTP guru/admin/murid/share/hasil/cetak, remedial seluruh keluarga, serta siklus melalui pergantian teks ke visual. Penolakan akses dan rollback diperiksa efek sampingnya.
- Browser 320/390/768/1280: seluruh varian visual dan ekstrem minimum/maksimum parameter teramati dalam 500 seed; halaman penuh 50 soal. Ukur overflow, bbox teks, sampel titik perpotongan stroke, dan hit-testing kontrol terlihat. Resource gambar eksternal tidak diperlukan; font CDN tetap opsional.
- Benchmark before/after memakai workload identik dan urutan berpasangan; batas awal 300 ms per halaman 50 soal dan toleransi tambahan maksimum dari 50% baseline atau 20 ms. Ini benchmark lokal, bukan SLA produksi.
- Coverage memakai stdlib trace `--count --missing --summary`; cakupan baris, bukan cabang. Artefak rinci/angka eksekusi ada di laporan lokal `docs/plan/2026-09-07-visual-fase8-verifikasi.md`.

## Urutan rilis wajib

Tahap berikut adalah urutan penerimaan/pemasangan awal Fase 8, **bukan perintah
mengulang migrasi atau mengubah flag produksi sekarang**. Periksa snapshot live
dan runbook aktif terlebih dahulu; jangan menganggap histori sebagai status terkini.

1. Verifikasi commit, CI, dan target sesuai izin tetap serta scope tugas. Sebelum startup image bermigrasi, ikuti [runbook rilis](production-release.md): backup konsisten seluruh state durable dan uji salinan, migrasi idempoten, `integrity_check`, `foreign_key_check`, jumlah provenance serta fingerprint lama. Izin tetap tidak menggantikan token approval/preflight teknis.
2. Deploy image Fase 8 sebagai pembaca pendahulu dengan visual tetap OFF. Jangan mengganti versi matematika hanya untuk mematikan visual; keduanya konfigurasi berbeda.
3. Pastikan image rollback juga sudah mempunyai sidecar dan reducer pemisah representasi. Image lama dapat mengabaikan provenance meski masih membaca SVG: kemampuan membaca gambar tidak sama dengan keamanan bukti belajar.
4. Setelah gate pembaca pendahulu lulus, aktifkan satu keluarga pada satu waktu. Snapshot yang sudah tersimpan tetap dibaca saat flag dimatikan. Kill switch menghentikan writer keluarga, bukan menulis ulang soal/hasil lama.
5. Jika ada cacat, matikan keluarga dan pertahankan image pembaca kompatibel. Jangan rollback ke image sebelum Fase 8 setelah ada bukti lintas representasi; jangan hard-delete sesi berbukti.
6. Verifikasi revisi/digest, healthcheck, rute publik/otorisasi, serta probe sintetis. Jangan membuka data anak untuk smoke test atau menyalinnya ke log/repo.

## Batas klaim

- Mode nonvisual K4 untuk pembaca layar masih nonaktif. ARIA benar bukan bukti tugas baca grafik sudah ekuivalen bagi pembaca layar.
- Bbox font dan stroke diuji pada sampel varian/ekstrem teramati, bukan seluruh kemungkinan parameter matematis. Sweep koordinat bukan mesin layout browser.
- Viewport Chromium, PDF A4 dan raster hitam-putih bukan pengujian HP/printer fisik. Uji perangkat nyata tetap gerbang penerimaan sebelum aktivasi luas.
- Pool `titik_segitiga` P3 masih sempit untuk siklus panjang; ini keterbatasan kurikulum pra-ada, bukan diperbaiki dengan melonggarkan anti-pengulangan.
- Penyelesaian implementasi lokal tidak berarti push, migrasi, aktivasi, atau deploy produksi sudah dilakukan.
