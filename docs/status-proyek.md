# Status proyek dan pekerjaan tersisa

**Diperbarui 30 Oktober 2026.** Ini indeks status, bukan perubahan keputusan produk
atau izin aktivasi. Kontrak detail tetap pada dokumen domain; aturan kerja di
[CLAUDE.md](../CLAUDE.md). Catatan lama harus dibaca menurut tanggal dan scope-nya.

## Arah dan rilis terakhir

- Fokus: alat guru les **in-house**, dengan pengembangan/pilot pivot memakai data
  sintetis. Peran `guru` tetap mencakup orang tua dan hanya mengakses data miliknya.
- Akses awal **nonkomersial**. Keputusan paket Jago/Jago Pro tidak sama dengan
  pembukaan penjualan, trial otomatis, promo, atau paywall.
- Artifact aplikasi produksi terakhir yang diverifikasi: **`7695cf9`**, mulai
  berjalan25Oktober2026 06.30WIB. Audit UI admin mencakup kontrol, state, keyboard,
  tema/cetak; **writer revisi penilaian1/2 tetap nonaktif**, histori tidak diubah.
  Dispatch gate [40142093633](https://github.com/clarinovist/jagomat/actions/runs/40142093633)
  (14.341 tes kandidat exact-once, pair terverifikasi), container healthy, smoke publik
  lulus. Digest/recovery/backup dan batas perangkat ada di
  [catatan rilis](production-release.md#deploy-audit-ui-admin--25-oktober-2026).
- Commit dokumentasi sesudahnya tidak otomatis menjadi revision image. Status
  di sini adalah snapshot bertanggal, bukan monitor live atau klaim `main` selalu deployed.
- Auto-deploy tetap nonaktif: push hanya feedback CI; dispatch manual menjalankan
  gate rilis lengkap, lalu pemasangan terkontrol sesuai [runbook](production-release.md).

## Sudah tersedia dan tercakup artifact tersebut

| Area | Keadaan | Acuan |
| --- | --- | --- |
| Alur belajar | Pemetaan, intervensi, penguatan, evaluasi/checkpoint; konfirmasi eksplisit dan bukti append-only | [Kontrak belajar](siklus-belajar-terpandu.md) |
| Ruang guru | Prioritas terlama menunggu, pencarian/filter GET privat, kartu akun, empat tab profil, tinjauan responsif | [Produk](product-reference.md), [arsitektur](architecture-reference.md) |
| Isi dari lembar | Foto tetap bukti; tanpa kunci vision tersedia transkripsi manual, bukan bacaan AI | [Produk](product-reference.md#kontrak-belajar-utama) |
| Bantuan mengajar | Bantuan statis dan **15 draf playbook** berperingatan; **0 disahkan manusia** | [Playbook](playbook-guru.md) |
| Pendamping | Panel inline/konteks berizin; hapus chat dan cabut izin tersedia meski provider mati | [Runtime](pendamping-runtime.md#kendali-data-existing--21-oktober-2026) |
| Katalog/variasi | Batch A–C writer2 dan bank kalimat aktif; reader histori/recovery tetap terjaga | [Katalog](catalog-corrections.md), [bank kalimat](story-frames.md) |
| Admin | Audit51state, kontrol/fokus/tema/cetak selaras; guard akun/kepemilikan tetap | [Audit admin](admin-ui-audit.md), [arsitektur](architecture-reference.md) |
| Persetujuan/sensor | Receipt persetujuan awal dan sensor terpisah dari KPI lama; koleksi tetap memerlukan izin keluarga | [Persetujuan](persetujuan-awal.md), [sensor](sensor-perbaikan.md) |
| Riset | Halaman riset publik dan panel wawancara privat tersedia; bukan bukti outcome atau launch komersial | [Produk](product-reference.md) |

“Tersedia” tidak menyatakan efektivitas belajar, penerimaan perangkat fisik, atau
seluruh kombinasi penggunaan nyata telah terbukti.

## Pekerjaan terbuka — bukan otomatis izin implementasi

| ID | Pekerjaan | Status / syarat berikutnya |
| --- | --- | --- |
| K1 | Review 15 playbook P3 | **Menunggu manusia.** Tetapkan reviewer; nilai isi exact, putuskan setuju/ubah/tolak. Agent tidak mengisi pengesahan. [Antrean](playbook-ulasan-p3.md) |
| K2 | Pilot bank terkurasi 90 item A/B/C | **Eksperimen offline selesai, evaluasi manusia belum.** Catat kualitas dan waktu nyata; B belum punya malrule, belum setara kapabilitas diagnosis A/C. [Pilot](catalog-pilot.md) |
| K3 | Revisi penilaian1 | **Source tersedia, aktivasi ditahan.** Default0 dan produksi nonaktif; perlu review isi, reader recovery baru serta pair exact sebelum aktivasi. [Kontrak](catalog-pilot.md#fondasi-bersama) |
| K4 | Audit katalog di luar batch/pilot | **Audit batch terbatas dan draf2 tersedia; belum diaktifkan/disahkan.** Kuantitas, rata-rata dan arsiran diperbaiki di jalur opt-in default0. LP/pecahan memakai fondasi revisi1 existing; berkurung/label volume masih follow-up. Review manusia dan recovery/pair baru wajib sebelum aktivasi. [Hasil/batas](catalog-followup.md) |
| G1 | Kecepatan transkripsi dan tinjauan guru | **Belum terukur.** Target 15 soal ≤5 menit masih usulan; UI yang lebih ringkas bukan bukti penghematan waktu. Pengukuran dapat memakai data sintetis; observasi guru sebelumnya sengaja dilewati. |
| G2 | Penutupan brief UI lintas halaman | **Ditutup24Oktober; rilis223eb35 healthy.** Shell laporan/profil, kontrol, target sentuh, ikon, navigasi, aksesibilitas markup dan state pendukung diperbaiki; CI14.267 tes kandidat lulus. [Cakupan/batas](ui-consistency-audit.md), [bukti rilis](production-release.md); bukan klaim semua perangkat lulus. |
| G3 | Laporan khusus guru→orang tua, sesi per topik/kelompok, mutu per guru | **Usulan, bukan kontrak aktif.** Dashboard/latihan manual existing tidak sama dengan fitur ini. Prioritas/scope dan kebutuhan pilot perlu diputuskan. |
| G4 | Pilot in-house dengan anak sungguhan / fondasi lembaga | **Menunggu keputusan.** Rencana pivot mensyaratkan persetujuan wali/serah-terima serta tinjauan jalur foto→AI sebelum data nyata. Ini tidak mengubah izin alur keluarga existing. |
| L1 | Kontrak sesi campuran v2 dan katalog tuntutan luas | **Codec saja; integrasi nonaktif.** Pilot homogen dua tuntutan sudah ada, bukan implementasi writer campuran. [Matriks integrasi](skill-demand-proposal.md#integrasi-wajib-sebelum-writer-v2-boleh-aktif) |
| A1 | Penyederhanaan Pendamping kandidat baru | **Ditahan gate mutu.** Dua batch selesai tetapi tidak memenuhi seluruh rubrik; tidak ada retry/pilot otomatis. Kendali data existing sudah selesai, tidak ikut ditahan. [Evaluasi](pendamping-runtime.md#retest-perbaikan-prompt-01--20-oktober-2026) |
| B1 | Launch komersial paket v2 | **Ditunda.** Katalog/ledger/service dan fondasi kuota ada; checkout/panel v2 lengkap, transisi, refund, eligibility/promo dan aktivasi perlu dituntaskan bila dipilih. [Paket](subscription-packages.md) |
| J1 | Perluasan jenjang hingga kelas 9 | **Diputuskan pemilik 28 Okt 2026; kelas 1–2 dimulai 30 Okt (source, belum rilis).** Landing menyebut sasaran bersama ketersediaan saat ini. Level P1/P2 hanya untuk Latihan manual (tingkat anak, siklus, pilot tetap P3–P6), migrasi CHECK konteks, topik `bilangan-dasar` dengan `tambah_dasar` (P1 hasil ≤10, P2 11–20) dan kartu Variasi Dasar 1/2. Gate selector CI lokal 406 berkas lulus; full suite 3.12, review guru atas malrule/pembahasan, dan pasangan recovery yang mengenali topik baru belum. Belum ada: kurang/bilangan hilang/nilai tempat/membandingkan, cerita/visual, integrasi siklus, kelas 7–9 dan SMP. [Batas klaim](workflow-reference.md#konteks-kurikulum--batas-klaim-produk) |
| O1 | Backup operasional terjadwal end-to-end | **Jalur manual lengkap dipasang dan diuji25Oktober; otomatis belum.** Tool5c2e07b, capture manual, transfer Mac dan rehearsal terisolasi lulus; core4DB+auth, riset/lampiran mengganti jalur tiga DB parsial. Jadwal/downtime berulang, off-site independen laptop, alert dan retensi operasional masih perlu keputusan. [Runbook backup](operational-backup.md) |

G1–G4 berasal dari rencana lokal pivot/brief 21–22 Oktober; keputusan dan batasnya
ringkas di sini agar tidak hanya tersimpan dalam `docs/plan/`. Angka target tetap
usulan, bukan acceptance baru yang telah disetujui. Perluasan template, kurikulum,
JavaScript, data, billing dan arsitektur tetap mengikuti persetujuan proyek.

## Dibatalkan atau sengaja dilewati

Keputusan 18 September tetap berlaku kecuali scope yang dibuka kembali secara
spesifik pada 20–21 Oktober. Lihat [riwayat keputusan](README.md#keputusan-pembatalan-pengembangan--18-september-2026).

- Demo video landing, ringkasan perkembangan AI v1, editor memori lebih luas,
  representasi nonvisual K4/pembaca layar: **bukan backlog aktif**.
- Penerimaan HP/printer fisik, Safari/keyboard HP dan audit aksesibilitas menyeluruh
  yang dibatalkan: **belum terverifikasi**, bukan dianggap lulus.
- Sisa alur kertas→HP lama tidak dibuka seluruhnya; mode isi-manual foto yang
  disetujui belakangan sudah diimplementasikan.
- Observasi guru Fase1b sengaja dilewati pemilik. Jangan mencatatnya selesai atau
  menjalankannya otomatis sebagai prasyarat baru.
- Cleanup API kompatibilitas, rename namespace image, aktivasi auto-deploy dan
  penghapusan alias lokal bukan kebutuhan rilis rutin. Jangan membukanya hanya
  untuk merapikan repo.

## Aturan memperbarui status

1. Tulis tanggal, scope, sumber bukti dan batas klaim; bedakan source, CI, image,
   deployment dan efektivitas produk.
2. Perbarui baris status serta dokumen domain yang terdampak. Pertahankan bukti
   historis, beri penanda supersesi—jangan menulis ulang masa lalu sebagai hasil baru.
3. Tidak ada status “selesai” berdasarkan checkbox lama, keberadaan berkas, atau
   skor AI saja. Kegagalan/belum diuji dan keputusan pembatalan harus tetap terlihat.
4. Data keluarga, credential, DB/backup, screenshot privat dan catatan reviewer
   sensitif tidak masuk indeks ini atau Git.
