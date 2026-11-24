# Status proyek dan pekerjaan tersisa

**Diperbarui 25 November 2026.** Ini indeks status, bukan perubahan keputusan produk
atau izin aktivasi. Kontrak detail tetap pada dokumen domain; aturan kerja di
[CLAUDE.md](../CLAUDE.md). Catatan lama harus dibaca menurut tanggal dan scope-nya.

## Arah dan rilis terakhir

- Fokus: alat guru les **in-house**, dengan pengembangan/pilot pivot memakai data
  sintetis. Peran `guru` tetap mencakup orang tua dan hanya mengakses data miliknya.
- Akses awal **nonkomersial**. Keputusan paket Jago/Jago Pro tidak sama dengan
  pembukaan penjualan, trial otomatis, promo, atau paywall. **Pembaruan 16 November 2026:**
  Pemilik memutuskan **funnel berbayar Cek Kemampuan / Paket Coba Rp49.000 dibuka**
  (Keputusan 16 di `../tim/founder/keputusan-pemilik.md`). Plan dan mockup UI sudah ada;
  kandidat Fase 1–3 ter-deploy dan **funnel diaktifkan 19 November 2026 termasuk
  pembayaran Paket Coba** (`FUNNEL_AKTIF=1`, ledger `pesanan_*` dimigrasikan);
  deliverable Fase 4 masih menyusul/manual. Status baris F1 di tabel bawah.
- Artifact aplikasi produksi terakhir yang diverifikasi: **`5c7849f`** (25 November 2026; jadwal Paket Belajar
  `jadwal_*` terpasang untuk admin, sakelar `PAKET_BELAJAR` mati, recovery 6142611 kontrak 9443dac; rincian di
  production-release.md). Sebelumnya **`c2d89fe`** (25 November 2026; Paket Belajar 1 Bulan `kelas_*`, recovery
  85bbd52). Sebelumnya **`1e61c8f`** (24 November 2026; Peta Kemampuan ditulis Guru + deposit
  purna_*, recovery 6613e5d). Sebelumnya **`deb96ef`** (22 November 2026 sore; tombol Mode Lomba per anak di
  `/akun?section=siswa`, tanpa skema, recovery 1206bc9). Sebelumnya **`7982f2c`** (22 November 2026 sore;
  Mode Lomba per anak diaktifkan Guru, tabel `lomba_penugasan`, recovery baru 1206bc9 kontrak 47a7cd9;
  rincian di production-release.md). Sebelumnya **`4a6b93e`** (22 November 2026 siang;
  UI Latihan Lomba + paket konfigurasi, tanpa migrasi; sakelar `OSN_LOMBA` hidup sejak pagi oleh Pemilik;
  rincian di production-release.md). Sebelumnya **`179733f`** (22 November 2026;
  topik Matematika Awal 25 jenis (40/40 bab "ada", `OSN_MATEMATIKA_AWAL` bawaan 1, dibuka sebelum ulasan Mutia),
  Latihan Lomba dan flag visual `matematika-awal` tetap mati, recovery pin `a8c587e`, kontrak `4b20d8ce`;
  rincian di production-release.md). Sebelumnya **`63f8756`** (21 November 2026;
  draf cetakan AI C3 mematikan thinking DeepSeek, recovery pin `4cef3ab`, kontrak `660fe23`;
  deploy terkontrol mulai 10.25 WIB). Uji kunci asli: `finish_reason=stop`, 3 kandidat, 1.745 byte.
  Uji UI end-to-end oleh Pemilik belum. Sebelumnya **`b512df0`** (21 November 2026; halaman admin
  cetakan soal berpola C2 + draf AI C3, kuota 20/hari; draf AI kosong karena reasoning) dan
  **`55aaa49`** (20 November 2026; WAL SQLite lima DB, recovery pin `bf5de20`) dan
  **`fa037344`** (20 November 2026 pagi;
  beranda funnel) dan **`efe9514`** (19 November 2026;
  funnel Peta Kemampuan playful v4 + `/contoh-peta-kemampuan`, topik cek gratis per kelas,
  admin `/admin/cek-topik` baca-saja, serta kode transfer rekening yang nonaktif — tabel
  `transfer_*`/`rekening_*` belum dimigrasikan dan `PESANAN_TRANSFER_AKTIF` kosong; recovery
  pin `7bab118`). Sebelumnya `a1443b3` (19 November 2026;
  Fase 3 pesanan Paket Coba — ledger aditif, rute pelanggan, callback Midtrans `ord_`,
  panel admin pesanan, copy refund Keputusan 17 — dengan **`FUNNEL_AKTIF=1` dan ledger
  `pesanan_*` dimigrasikan sejak 19 November 2026**; pembayaran terbuka, deliverable
  Fase 4 menyusul; recovery pin `5b8e1d3`). Sebelumnya `2f546ef` (15 November 2026;
  ringkasan pasangan diagnostik read-only di halaman tinjauan guru, penyelarasan
  spec/context, dan perbaikan dokumen status/kit; tanpa schema/migrasi/flag). Sebelumnya
  `7b57cc7` (15 November 2026; tes diagnostik tajam berpasangan P1–P6, topik
  `berhitung-sekolah` P3–P4, laporan orang tua snapshot v2 + SVG sebaris, landing kelas
  1–6 SD, pancingan/playbook draf). Sebelumnya `d1d2f76` (6 November 2026;
  aktivasi `OSN_DASAR_LENGKAP=1`, lembar P1/P2 berisi lima jenis dua soal per jenis;
  lihat catatan rilis). Sebelumnya `58a52a4` (6 November) membawa empat jenis baru dengan
  sakelar mati; `b412b42` (6 November)
  membawa pancingan per template, `/admin/pemakaian`, dan lembaga les; `efb9a03`
  (5 November) laporan guru→orang tua G3. Rilis `5245656` (4 November) membawa tata letak cetak PG ringkas, `OSN_CETAK_RINGKAS=1`. Rilis `7dee2ed` menulis ulang pembahasan
  Bilangan Dasar P2 dan **mengaktifkan `OSN_MATERI_DASAR=1` di produksi atas keputusan
  pemilik**, sebelum pembahasan baru diulas ulang. Rilis `ac87170` (3 November
  15.45 WIB) membawa
  pecahan bertumpuk di layar (bukan bank cetak) dan lima commit pengerasan
  keamanan sesudah `3d5c215` (pembatas laju mandiri, batas body POST, CSP
  kredensial, resolusi IP klien, CSP halaman tautan). Sebelumnya `3d5c215`
  membawa banner offline dan petunjuk beranda. Dispatch gate
  [41595651322](https://github.com/clarinovist/jagomat/actions/runs/41595651322)
  (delapan shard hijau, pair terverifikasi), container healthy, smoke publik lulus.
  Digest/recovery/backup ada di
  [catatan rilis](production-release.md#deploy-pecahan-bertumpuk-dan-pengerasan-keamanan--3-november-2026).
- Commit dokumentasi sesudahnya tidak otomatis menjadi revision image. Status
  di sini adalah snapshot bertanggal, bukan monitor live atau klaim `main` selalu deployed.
- Auto-deploy tetap nonaktif: push hanya feedback CI; dispatch manual menjalankan
  gate rilis lengkap, lalu pemasangan terkontrol sesuai [runbook](production-release.md).
- **Lingkungan uji** `https://uji.jagomat.id` — **DINONAKTIFKAN 20 November 2026** atas
  keputusan Pemilik: vhost 443 membalas `410 Gone` dengan halaman berdesain dari
  token merek (halaman dan aset di `/var/www/uji-nonaktif`), container `jagomat-uji` dihentikan
  (dihapus 21 November 2026; image dan vhost dipertahankan, aktivasi ulang lewat `docker run` dari
  `container-inspect.json`), data sintetis `/opt/jagomat-uji/data` tidak disentuh, DNS dan
  sertifikat dipertahankan. Image terakhir `b412b42` (digest `0757224c…`), jadi tidak
  pernah disamakan ke rilis 19–20 November. Container dicatat di
  `/root/monitoring/container-dikecualikan.txt` agar tidak memicu alert CONTAINER DOWN;
  langkah aktivasi ulang ada di `/opt/jagomat-uji/deaktivasi-20261120/README.md`.
  Sebelumnya (1 November 2026; disamakan ke `a9977f8` pada 2 November): image yang sama
  dengan produksi (digest `756e23d6…`), data sintetis, di VPS non-produksi yang dipakai
  bersama proyek lain. Dilindungi gerbang sandi tim di depan login app, `noindex`;
  Pendamping/LLM dan pembayaran nonaktif; tautan berbagi diarahkan ke host uji. Bukan
  deployment produksi, tidak ikut backup, hanya untuk data sintetis. Walkthrough
  admin → guru → anak → sesi → tautan berbagi lulus dari luar (diverifikasi ulang 2 November).
- **Ruang berkas tim** `https://tim.jagomat.id` (1 November 2026): Nextcloud 34.0.5 di VPS
  non-produksi yang sama, terpisah dari app. Akun per peran, folder tim milik organisasi,
  tautan publik mati; backup harian lokal + Cloudflare R2. **Bukan tempat data
  anak.** Konfigurasi dan runbook di luar repo: `~/Documents/jagomat/berkas`.

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
| K1 | Review 15 playbook P3 | **Ulasan terkumpul di cek.jagomat.id (4 Nov): 3 isian, 1 selesai; hasil “perlu perbaikan/tinjau ulang”.** Ini catatan ulasan, bukan pengesahan: `disahkan` tetap ditulis manusia di JSON setelah perbaikan dan review exact. Bahasa pembahasan dinilai rumit. [Antrean](playbook-ulasan-p3.md) |
| K2 | Pilot bank terkurasi 90 item A/B/C | **Eksperimen offline selesai; evaluasi manusia terkumpul 4 Nov (satu isian lengkap, ada butir ditolak).** Hasil belum diterjemahkan ke perubahan konten. Catat kualitas dan waktu nyata; B belum punya malrule, belum setara kapabilitas diagnosis A/C. [Pilot](catalog-pilot.md) |
| K3 | Revisi penilaian1 | **Source tersedia, aktivasi ditahan; ulasan manusia 4 Nov: perlu perbaikan.** Default0 dan produksi nonaktif; perlu review isi, reader recovery baru serta pair exact sebelum aktivasi. [Kontrak](catalog-pilot.md#fondasi-bersama) |
| K4 | Audit katalog di luar batch/pilot | **Audit batch terbatas dan draf2 tersedia; belum diaktifkan/disahkan; ulasan manusia revisi2 4 Nov: perlu perbaikan.** Kuantitas, rata-rata dan arsiran diperbaiki di jalur opt-in default0. LP/pecahan memakai fondasi revisi1 existing; berkurung/label volume masih follow-up. Review manusia dan recovery/pair baru wajib sebelum aktivasi. [Hasil/batas](catalog-followup.md) |
| G1 | Kecepatan transkripsi dan tinjauan guru | **Belum terukur.** Target 15 soal ≤5 menit masih usulan; UI yang lebih ringkas bukan bukti penghematan waktu. Pengukuran dapat memakai data sintetis; observasi guru sebelumnya sengaja dilewati. |
| G2 | Penutupan brief UI lintas halaman | **Ditutup24Oktober; rilis223eb35 healthy.** Shell laporan/profil, kontrol, target sentuh, ikon, navigasi, aksesibilitas markup dan state pendukung diperbaiki; CI14.267 tes kandidat lulus. [Cakupan/batas](ui-consistency-audit.md), [bukti rilis](production-release.md); bukan klaim semua perangkat lulus. |
| G3 | Laporan khusus guru→orang tua, sesi per topik/kelompok, mutu per guru | **Laporan guru→orang tua: live di produksi sejak 5 Nov 2026 (`efb9a03`)** — dua tabel aditif, tautan baca-saja, guard M1–M4 lulus; `postcheck` hanya mencatat 1 `BrokenPipeError` jinak. Sesi per topik/kelompok dan mutu per guru tetap usulan. Plan: `docs/plan/2026-11-04-laporan-ortu-g3.md`. |
| G4 | Pilot in-house dengan anak sungguhan / fondasi lembaga | **Menunggu keputusan.** Rencana pivot mensyaratkan persetujuan wali/serah-terima serta tinjauan jalur foto→AI sebelum data nyata. Ini tidak mengubah izin alur keluarga existing. |
| L1 | Kontrak sesi campuran v2 dan katalog tuntutan luas | **Codec saja; integrasi nonaktif.** Pilot homogen dua tuntutan sudah ada, bukan implementasi writer campuran. [Matriks integrasi](skill-demand-proposal.md#integrasi-wajib-sebelum-writer-v2-boleh-aktif) |
| A1 | Penyederhanaan Pendamping kandidat baru | **Ditahan gate mutu.** Dua batch selesai tetapi tidak memenuhi seluruh rubrik; tidak ada retry/pilot otomatis. Kendali data existing sudah selesai, tidak ikut ditahan. [Evaluasi](pendamping-runtime.md#retest-perbaikan-prompt-01--20-oktober-2026) |
| B1 | Launch komersial paket v2 | **Ditunda.** Katalog/ledger/service dan fondasi kuota ada; checkout/panel v2 lengkap, transisi, refund, eligibility/promo dan aktivasi perlu dituntaskan bila dipilih. [Paket](subscription-packages.md) |
| J1 | Perluasan jenjang hingga kelas 9 | **Diputuskan pemilik 28 Okt 2026; kelas 1–2 live di produksi sejak 2 Nov (`a9977f8`), penawaran dibuka sejak 4 Nov (`7dee2ed`, `OSN_MATERI_DASAR=1` atas keputusan pemilik; ulasan ulang pembahasan belum).** Landing menyebut sasaran bersama ketersediaan saat ini. Level P1/P2 hanya untuk Latihan manual (tingkat anak, siklus, pilot tetap P3–P6), migrasi CHECK konteks sudah diterapkan di produksi, topik `bilangan-dasar` dengan `tambah_dasar` (P1 hasil ≤10, P2 11–20) dan kartu Variasi Dasar 1/2. `OSN_MATERI_DASAR` default0 mengunci penawaran/pembuatan, bukan pembaca histori; aktivasi perlu review guru, recovery yang mengenali topik dasar, dan izin rilis. Gate selector CI lokal 406 berkas lulus; full suite 3.12 lulus pada dispatch [41355603056](https://github.com/clarinovist/jagomat/actions/runs/41355603056). Ulasan Materi Dasar kelas 1–2 (4 Nov, cek.jagomat.id): rekomendasi **ubah dulu** (pembahasan berbelit, kode K=0 pada soal berhasil 10), jadi aktivasi tetap ditahan. Pembahasan P2 ditulis ulang dengan kalimat penuh pada 4 Nov (soal, kunci, malrule, PG identik; belum rilis, perlu ulasan ulang); recovery `39fcfa7` terbukti memuat topik `bilangan-dasar` P1/P2 dan template `tambah_dasar` (probe image), dan pasangan CI kandidat→recovery lulus. Batch 2 (6 Nov, source `77faa58`+`67b9518`, live `58a52a4`, **aktif 6 Nov `d1d2f76`**): `kurang_dasar`, `bilangan_hilang`, `nilai_tempat`, `bandingkan_bilangan` (tanda <, >, =; PG `simbol_perbandingan`) di balik sakelar writer `OSN_DASAR_LENGKAP`, keputusan materi mengikuti Jev atas instruksi pemilik; **`OSN_DASAR_LENGKAP=1` di produksi sejak 6 Nov**, lembar P1/P2 berisi lima jenis dua soal per jenis. Ulasan guru diganti self-review agent atas keputusan pemilik 6 Nov (bukan ulasan independen): seluruh 2.275 butir domain lima jenis diperiksa (kunci vs solver terpisah, hitungan setiap persamaan pembahasan, malrule≠kunci dan tidak kembar, PG tepat tiga opsi), lalu contoh per malrule×bentuk×level dibaca. K=0 **dipertahankan**: 0 sah sebagai salah tipikal (menulis satuan saja untuk 10, atau mengerjakan 5−5), jadi tanpa versi katalog. Pin recovery `58a52a4` ditolak gate karena writer katalog bawaan 2; recovery `c58390a` (57817a5 + writer katalog1/teori1) mengenal kelima jenis. Dua perbaikan teks jenis baru (alasan `nilai_bukan_banyak` memakai angka soal; pembahasan membandingkan satu digit lewat urutan membilang) masuk kandidat `57817a5`/`d1d2f76`. Pemilih topik Latihan memberi label rentang kelas (live `4ce333a` 6 Nov, masukan guru: Aritmetika Dasar = kelas 5–6, Bilangan Dasar tidak bisa masuk Gabungan). Belum ada: cerita/visual, integrasi siklus, kelas 7–9 dan SMP. [Batas klaim](workflow-reference.md#konteks-kurikulum--batas-klaim-produk) |
| O1 | Backup operasional terjadwal end-to-end | **Harian otomatis berjalan sejak 20 Nov 2026; drill restore lulus 21 Nov (kontainer sementara), restore ke produksi sungguhan belum pernah.** Cron host 21:45 WIB (`/etc/cron.d/osn-backup-harian`) menulis bundle `/opt/osn/backup-harian/<id>` (lima DB wajib + `sandi.json` + DB tambahan, retensi 14). Off-site: job Hermes 22:00 WIB di Mac menarik bundle lewat SSH, mengenkripsi, lalu mengunggah ke R2 (retensi 30 hari). Skrip dan kunci enkripsi hanya ada di Mac (di luar Git dan VPS); aplikasi sendiri tidak terhubung ke R2. Run terjadwal pertama 20 Nov terbukti: bundle `20261120-214501` ada di VPS dan objek terenkripsinya di R2. Jalur VPS→R2 terpasang 21 Nov 2026 (bucket terpisah `jagomat-app-cadangan-vps`, token khusus bucket, cron 22:00, drill pulihkan dari R2 sungguhan lulus); job Mac tetap cadangan kedua; monitor `scripts/pantau_offsite_vps.py` (job Hermes 08:30 WIB) mengalert Telegram bila `last-ok`/`retention-ok`/umur bundle/kunci tak sehat atau VPS tak terjangkau. Drill baca R2 lulus (20 Nov). Drill restore 21 Nov: bundle cron `20261120-214501` → 5 DB `integrity_check=ok`, app start `healthy`, smoke `/` 200, `/akun` 401, `/murid/` 303. Alert Telegram untuk kegagalan lulus uji end-to-end 21 Nov. Terpasang 21 Nov (`0fef96a`, VPS dan job Hermes): log harian berisi ringkasan JSON + validasi ulang, dan skrip off-site `scripts/backup_offsite_mac.sh` yang menolak bundle basi dan selalu mengalert saat gagal. Terbuka: off-site bergantung Mac menyala, salinan aman kunci enkripsi, `pendamping.db` tetap `delete` setelah restore (perbaikan `berkas_data` ada di `main` lokal, belum dirilis), retensi per domain. [Runbook backup](operational-backup.md) |
| F1 | Funnel berbayar Cek Kemampuan / Paket Coba Rp49.000 | **Diputuskan Pemilik 16 Nov 2026; funnel penuh aktif 19 Nov (`a1443b3`), termasuk pembayaran Paket Coba.** `FUNNEL_AKTIF=1`, ledger `pesanan_*` dimigrasikan (6 tabel, 0 order), gerbang tiga syarat terbuka; tidak ada order sampai ada pembeli. **Deliverable Fase 4 belum ada di aplikasi**: laporan lengkap, latihan 30 hari, konsultasi, dan voucher masih menyusul/manual, dan halaman pembeli berkata "Akses laporan lengkap menyusul". Belum ada worker rekonsiliasi order (pembeli/admin harus menekan Periksa) dan sapuan retensi 30 hari belum dijadwalkan; risiko ini diterima Pemilik 19 Nov. Copy refund Keputusan 17 masih DRAF. Jangan menyalakan `penegakan` atau mengubah tahap tanpa keputusan terpisah. Plan: `docs/plan/2026-11-16-funnel-cek-kemampuan.md` (gitignored); mockup: `docs/mockup/funnel-20261116/`. |

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
