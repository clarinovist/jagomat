# Ringkasan perkembangan berbasis bukti — baseline dan palang manfaat

**Keputusan produk 13 September 2026:** Opsi 2 dipilih: ringkasan personal berbasis
bukti, tanpa chat, dengan kewenangan AI dibatasi. User menyetujui implementasi
bersyarat: spike lebih dahulu, lalu berhenti sebelum kompleksitas penuh jika
manfaat AI dibanding deterministik belum berarti.

**Hasil palang manfaat: TAHAN implementasi AI v1.** Spike sintetis tidak memberikan
bukti peningkatan berarti. Ringkasan **deterministik** tiga bagian pernah diterapkan
berdasarkan perjalanan/reducer yang sudah ada. Revisi dashboard 15 September 2026
memindahkan informasi tersebut ke resume rencana belajar (lihat bagian berikut);
ini bukan fitur AI dan bukan klaim sudah ter-deploy. DB, schema, consent, cache, payload,
dan konfigurasi provider tidak diubah. Mengaktifkan ringkasan AI produksi belum
boleh dilakukan; izin Pendamping existing bukan izin baru untuk data laporan.

Acuan: [siklus belajar](siklus-belajar-terpandu.md),
[runtime Pendamping](pendamping-runtime.md), dan [palang proyek](../CLAUDE.md).

## 1. Tujuan dan sumber kebenaran

Ringkasan menjawab **yang terlihat → yang masih perlu diperiksa → langkah
berikutnya**, maksimum sekitar 180 kata. Ia menggantikan ringkasan generik, bukan
menambah chat atau kartu panjang baru. Maksimal dua fokus dijelaskan terpisah.

`learning_cycle.py` tetap satu-satunya penentu status/rekomendasi.
`learning_journey.py` menyajikan perjalanan bukti; statistik `reports.py` tentang
seluruh latihan bukan ukuran kelulusan fokus. `direview`, jawaban benar, atau
kode final mutable tidak otomatis menjadi bukti. Bukti yang telah dikoreksi,
belum dikonfirmasi, atau berbeda level tidak boleh menghasilkan klaim palsu.

Status, fakta, tanggal, tautan, dan tindakan resmi dirender server. AI v1 hanya
memilih potongan penjelasan yang ditinjau manusia dari pilihan yang sah untuk
fakta tersebut: tidak ada narasi bebas, diagnosis baru, label karakter anak,
prediksi prestasi, pemilihan kurikulum, atau intervensi AI untuk anak. Ringkasan
bukan snapshot outcome dan tidak mengubah bukti maupun rencana.

Contoh **sintetis**, bukan keluaran model:

> **Yang terlihat**
>
> Pola bilangan mulai membaik; kemampuan menjelaskan sudah dikonfirmasi.
>
> **Yang masih perlu diperiksa**
>
> Ketahanan pemahaman belum diperiksa dengan checkpoint.
>
> **Langkah berikutnya**
>
> Ikuti jadwal checkpoint pada rencana belajar.

Tanggal aktual dan tautan **Lihat rencana belajar** ditambahkan server. Jika
bukti belum cukup, tampilkan penjelasan deterministik serta tindakan resmi,
bukan memanggil AI untuk membuat paragraf umum.

### Dashboard perkembangan — revisi 15 September 2026

Revisi lanjutan mengutamakan **progres penguasaan target materi Jagomat** sesuai
kelas anak, bukan persentase jawaban pada sebagian soal. Katalog target eksplisit
menjaga seluruh materi tetap terlihat, termasuk belum dinilai. Grafik status
bertumpuk dan rincian seluruh topik berada paling atas, lalu resume rencana dan
aktivitas mingguan. Blok tersendiri “Ringkasan untuk orang tua” tidak ditampilkan.

Progres = target yang menunjukkan pemahaman / seluruh target kelas dalam katalog
Jagomat. Setiap pola dalam target wajib memiliki bukti yang cukup, bervariasi dan
bisa menjelaskan; keputusan milik reducer. Peta bukan klaim seluruh kurikulum sekolah
atau penguasaan permanen. Kriteria pemetaan/evaluasi/checkpoint, invalidasi, pergantian
kelas dan pemeriksaan ulang ada di [kontrak siklus](siklus-belajar-terpandu.md).

- Default 7 hari terakhir WIB dibanding 7 hari sebelumnya. Tanggal mengikuti
  pencatatan jawaban pertama, bukan pembuatan sesi. Hasil kertas mengikuti waktu
  input, bukan klaim waktu pengerjaan sebenarnya. Koreksi tidak dihitung ulang
  sebagai aktivitas baru; hasil statistik periode lama dapat ikut berubah.
- Dikerjakan berarti ada jawaban atau coretan cara, termasuk sesi berjalan.
  Memilih status saja belum dihitung. Kerja berstatus perlu cek pengenalan atau
  dilewati tetap aktivitas, tetapi bukan hasil benar/salah.
- Persentase = benar / (benar + salah). N/menebak, penilaian belum jelas,
  materi perlu cek pengenalan, dan dilewati tidak masuk penyebut. Kode T bisa
  berasal dari pengakuan bingung, bukan kepastian belum pernah diajarkan.
  Tanpa penilaian tampil **—**, bukan 0%. Hasil yang belum seluruhnya dikonfirmasi
  memakai label singkat **Hasil sementara**, tanpa paragraf jumlah konfirmasi atau
  rumus. Ketepatan jawaban hanya catatan aktivitas sekunder, bukan penguasaan.
- Tren memakai kelompok tipe soal, kelas, mode, tujuan, dan representasi sama.
  Minimal lima butir dinilai pada masing-masing periode adalah batas kecukupan
  tampilan, bukan signifikansi statistik. Selisih memakai **poin persentase**,
  dengan jumlah dasar terlihat. Kelompok tidak digabung menjadi skor penguasaan.
- **Lihat rencana belajar** membuka resume native di laporan, bukan redirect:
  tugas belum selesai, posisi belajar, hal yang perlu diperiksa, materi/langkah
  berikutnya dan jadwal. Tugas manual/kelas lama tetap sekunder. Satu aksi utama
  menuju sesi yang direkomendasikan atau langkah belajar pada profil.
- Posisi dua fokus, status dan rekomendasi tetap berasal dari
  `learning_journey.PerjalananBelajar`/reducer. Clock rekomendasi sama dengan
  profil/POST existing; WIB khusus batas statistik, bukan mengubah jadwal domain.
  Perjalanan/bukti lengkap tetap dapat dibuka. Penjelasan hitungan berada di bawah
  data terkait; paragraf panjang “Dasar hitungan dan total seluruh catatan” dihapus,
  total seluruh catatan tetap angka ringkas. Kamus kode di rincian teknis.

Implementasi: `mastery_catalog.py` (target kelas), `learning_cycle.py` (keputusan
penguasaan), `mastery_report.py` (peta/grafik), `report_metrics.py` (statistik aktivitas
read-only), `report_dashboard.py` (presentasi aktivitas/resume), dan `reports.py`
(komposisi halaman). Adapter baca khusus `mastery_evidence.py` membawa
mode/pola/fingerprint matematis dari penyajian immutable, bukan menurunkan
penguasaan dari diagnosis mutable. Kontrak adapter database umum tidak berubah.
Renderer lama `report_summary.py` masih menjadi helper bahasa kompatibel, bukan
sumber keputusan pedagogis. GET tidak menyimpan, membuat cache, atau memanggil
network/AI. Keputusan spike dan batas AI di bawah tetap berlaku sebagai histori
serta batas untuk pengembangan AI mendatang, bukan bentuk dashboard terkini.

## 2. Baseline AI v1 yang disepakati, belum dibangun

### UX dan pemicu

- Satu aksi **Buat ringkasan** melalui POST setelah consent, tanpa chat/pilihan
  model/streaming/JS tambahan. GET dan refresh tidak memanggil provider.
- Bagian **Dasar ringkasan** memuat sumber dan waktu. Tanggal/nama/tautan lokal.
- Cache hasil untuk versi sumber yang sama. Setelah invalidasi, tampilkan
  ringkasan biasa dan tawarkan pembaruan manual, tidak regenerasi otomatis.
- Label **Disusun dengan bantuan AI** hanya untuk hasil valid dari AI nyata,
  bukan fake provider, fallback, atau hasil templat biasa.

### Payload minimum dan persetujuan

Boleh diproses: tahap netral, maksimal dua label fokus terkontrol, status per
fokus, ringkasan bukti terkonfirmasi relevan, kemampuan menjelaskan yang benar-benar
tercatat, perubahan yang dinyatakan sebanding oleh aplikasi, tindakan resmi dan
status menunggu/tersedia, serta potongan penjelasan yang memenuhi prasyarat.

Tidak mengirim nama, ID tetap akun/anak/sesi, tanggal kalender, URL sumber, seed,
kode diagnosis/malrule/alasan internal, jawaban atau catatan bebas, foto, transkrip,
memori, kontak, maupun credential. Provenance dan fingerprint tetap lokal.
Referensi sementara seperti `fakta_1` bukan identitas anak lintas request.
Ringkasan tanpa nama **tetap data anak**, tidak disebut anonim.

Consent terpisah terikat akun-generasi, anak, tujuan, penyedia, dan versi cakupan;
consent chat tidak diwariskan. Berlaku untuk permintaan manual berikutnya, bukan
pekerjaan otomatis. Akses administratif ke laporan tidak otomatis menjadi hak
mengirim data AI keluarga. Consent diperiksa sebelum dan sesudah network.

Contoh inti consent:

> Jagomat akan mengirim ringkasan terbatas tentang fokus, tahap belajar, bukti
> yang sudah dikonfirmasi, kemampuan menjelaskan, dan langkah berikutnya ke
> **penyedia pemroses yang telah diverifikasi**. Nama, jawaban tertulis, foto,
> catatan bebas, dan percakapan tidak dikirim. Meski tanpa nama, ringkasan ini
> tetap berkaitan dengan perkembangan anak. Status dan rencana belajar tetap
> ditentukan oleh aturan Jagomat.
>
> ☐ Saya setuju menggunakan data tersebut untuk membuat ringkasan AI anak ini.

UI final wajib menyebut penerima nyata, termasuk perantara relevan, bukan
"model internal". Aksi nonaktifkan/hapus hasil menjelaskan bahwa sesi/bukti tidak
terhapus dan request yang sudah terkirim tidak dapat ditarik kembali.

### Validasi, fallback, dan batas pemakaian

- JSON tertutup berisi referensi fakta/pilihan konten sah; tolak field tambahan,
  teks bebas, HTML, URL, referensi asing/duplikat, dan pilihan tanpa prasyarat.
- Fakta, batas tafsir, kedua fokus, dan tindakan wajib tidak dapat dihilangkan.
  Pemeriksaan JSON/kata terlarang saja tidak menjamin kebenaran narasi bebas;
  karena itu narasi bebas memang tidak diterima pada baseline ini.
- Provider gagal/timeout/respons invalid/kuota habis: fallback deterministik
  tanpa label keberhasilan AI. Laporan inti tetap dapat digunakan.
- Satu panggilan per versi sumber; dua percobaan berbayar per anak per hari,
  lima per akun per hari. Double-submit dideduplikasi; tidak retry otomatis;
  retry manual minimal satu menit. Timeout 25 detik; tidak menahan transaksi DB.
- Status/versi sumber, izin, dan pemilik diperiksa ulang setelah respons datang.
  Respons yang menjadi usang dibuang, bukan disimpan sebagai hasil terkini.

### Retensi dan invalidasi

- Satu hasil terkini per akun–anak, maksimum 30 hari sejak dibuat; membaca tidak
  memperpanjang TTL. Provenance/versi disimpan bersama hasil.
- Payload lengkap, prompt, dan respons ditolak tidak diarsipkan. Metadata operasi
  tanpa isi maksimal tujuh hari. Bukti consent tidak menyimpan salinan laporan.
- Hasil kedaluwarsa/diganti/dicabut langsung tidak dapat diakses; penghapusan fisik
  maksimal 24 jam sesudahnya. Cadangan dapat bertahan maksimal 30 hari sesudah
  penghapusan aktif. Restore tidak boleh menghidupkan kembali izin/hasil tak sah.
- Invalidasi pada koreksi/rekonfirmasi/pembatalan bukti, perubahan fokus/level/
  status/tindakan, pergantian jatuh tempo, pemilik/generasi akun/consent, serta
  versi aturan/proyeksi/konten. Latihan manual kosong yang tidak mengubah fakta
  atau rekomendasi tidak harus membuang cache.
- Retensi dan penggunaan data oleh provider harus diaudit sendiri; tidak dapat
  disimpulkan dari retensi lokal Jagomat.

## 3. Spike sebelum kompleksitas — kriteria ditetapkan sebelum kode

Eksperimen berada di arsip lokal
`../../osn-resources/referensi/spike/report-summary-2026-09-13-r2nlFI/`.
Berkas eksperimen, tests, HTML, dan evidence **bukan dependensi aplikasi/build/CI**,
tidak dikirim ke Git, dan tidak wajib ada di clone lain.

Pembanding:

1. **Deterministik baru:** fakta sintetis tiga bagian dan pilihan copy yang sama.
2. **Jalur AI terbatas:** callable fake memilih ID varian dari katalog yang sama;
   diuji pilihan ringkas, lebih panjang, campuran, invalid, dan timeout.

Bukan membandingkan AI dengan ringkasan statistik lama yang lebih lemah. Kedua
jalur memperoleh informasi yang sama. Copy eksperimen ditulis untuk spike;
belum merupakan pustaka produksi yang lolos review manusia independen.
Fixtures adalah proyeksi sintetis yang sudah berstatus, bukan hasil menjalankan
adapter/reducer aplikasi. Tidak ada provider nyata, DB, secret, maupun model
yang diberi data anak.

Kriteria lanjut yang dipatok: keselamatan kontrak seluruh kasus; manfaat
nonkosmetik pada minimal tiga kasus layak berupa informasi/tindakan sah tambahan
atau pemadatan minimal 20% tanpa kehilangan fakta/batas/tindakan. Klaim
keterpahaman nyata memerlukan reviewer manusia independen; fake provider tidak
membuktikan kualitas LLM. Variasi urutan/sinonim saja bukan alasan lanjut.

Tiga belas skenario: bukti kosong, belum konfirmasi, pantau tunggal, menunggu
evaluasi, mulai membaik, ragu, menghafal, bertahan, dua fokus berbeda, invalidasi,
beda level, eskalasi, dan materi baru T. Delapan layak memakai selector dalam
simulasi, lima langsung deterministik. Setiap fakta mempunyai dua alternatif
copy; seluruh 72 kombinasi pada kasus layak diperiksa. Tambahan 40 kombinasi
pada kasus tidak layak memastikan bypass/fallback; total 112 jalur.

### Hasil terukur dan batasnya

| Ukuran | Hasil |
|---|---|
| Fakta/batas/tindakan tetap ada | Seluruh 112 jalur terjaga secara struktural |
| Selector memilih seluruh copy ringkas | Identik dengan deterministik pada 13 kasus; lima tanpa panggilan fake |
| Pemadatan terbaik dibanding deterministik ringkas | 0% pada seluruh delapan kasus layak |
| Kasus yang memenuhi ambang manfaat | 0 dari minimal 3 yang diperlukan |
| Panjang deterministik | 15–20 kata isi, tidak menghitung judul/metadata lokal |
| Panggilan fake untuk satu ringkasan layak | 1, dibanding 0 pada deterministic |
| Kualitas model nyata / preferensi orang tua | Tidak diuji; tidak ada skor kualitas/latensi API yang diklaim |

**Keterbatasan penting:** pemadatan 0% mengikuti katalog copy buatan yang versi
ringkasnya memang pendek. Tidak membuktikan semua katalog atau semua model
selalu setara. Tidak ada informasi baru merupakan sifat kontrak input/output,
bukan detektor semantik yang membuktikan kebenaran semua teks. Keterpahaman
"ringkas versus lebih jelas" belum diuji pada orang tua. Hasil fake yang tampak
baik tidak dapat menjadi bukti positif untuk membangun kompleksitas AI penuh.

**Keputusan:** bukti manfaat belum memenuhi palang, sehingga implementasi AI
v1 dihentikan sebelum consent baru, cache/kuota, retensi, endpoint, atau migration
aplikasi dibangun. Fitur/provider ringkasan baru belum ada sehingga tetap tidak
aktif; konfigurasi AI Pendamping existing tidak disentuh. Rekomendasi pragmatis
ialah ringkasan deterministik tiga bagian berdasarkan proyeksi bukti existing.
Rekomendasi tersebut kemudian diterapkan pada source aplikasi sebagai pekerjaan
terpisah dari spike; hasil spike historis tetap tidak diubah atau diklaim sebagai
implementasi AI.

## 4. TDD dan verifikasi eksperimen

- RED pertama: 14 assertion gagal karena skeleton tidak mengembalikan fakta;
  bukan import error. Implementasi minimal deterministic → 14 lulus.
- RED kedua: 39 gagal/14 lulus karena payload/selector/fallback masih skeleton;
  implementasi → 53 lulus. Refactor validator → 53 lulus.
- Empat mutation terisolasi: izinkan narasi tambahan, izinkan field teks tambahan,
  bocorkan sentinel lokal ke payload, dan panggil provider untuk kasus tidak layak.
  Masing-masing membuat regression merah pada jalur aktual; source asal tetap
  utuh dan 53 lulus sesudah mutation. Ini guard spike, bukan guard v1 produksi.
- RED preview: 13 gagal karena HTML kosong; renderer sintetis → total 66 lulus
  (unit/kontrak dan alur input–selector–HTML eksperimen).
- Browser offline: 13 kasus × 320/390/1440 = 39 pemeriksaan lebar/landmark/resource,
  tanpa overflow. Screenshot desktop mulai membaik dan HP dua fokus ditinjau
  visual: struktur tiga bagian jelas, dua fokus tidak diratakan. Bukan studi UX
  orang tua atau E2E aplikasi yang belum dibangun.
- Alat browser sempat membaca berkas port sebelum berisi; diperbaiki dengan
  menunggu isi, kemudian 39 pemeriksaan lulus. Bukan kegagalan aplikasi.

Evidence lokal mencakup `red-*.log`, `green-*.log`, `mutation-*.log`,
`comparison.json`, `visual/geometri.json`, dan screenshot sintetis. Bukti red
mendahului implementasi masing-masing, termasuk source skeleton tersimpan untuk
jalur inti. Tidak ada production code ringkasan AI yang ditulis.

## 5. Jika pengembangan dilanjutkan

Implementasi v1 tetap jalur Kritis dan memerlukan manfaat yang dapat dibuktikan
serta audit penyedia. Acceptance berikut belum dianggap selesai oleh spike:

- Payload minimum/consent/otorisasi sebelum-sesudah request; 404 asing/hilang
  identik dan tidak ada efek samping; akses murid tertutup, admin tidak mewarisi izin.
- Proyeksi bukti sah, dua fokus berbeda, beda level, waktu/jadwal, hasil ragu/
  menghafal, invalidasi, T bukan kelemahan; status sama dengan reducer/profil.
- Cache/TTL/kuota/double-submit/retry/race dan pencabutan izin; purge/restore tidak
  menghidupkan kembali hasil; tidak ada tulisan ke diagnosis/snapshot/siklus.
- Unit, integrasi HTTP, E2E UI dengan fake provider, mutation guard baru,
  full suite warning-error, kompilasi, palang, dan visual HP/desktop.
- Audit penerima/perantara, penggunaan untuk pelatihan, lokasi/retensi/penghapusan,
  biaya/batas layanan. Provider produksi ringkasan harus tetap tidak aktif sampai
  audit diterima. Akses/credential provider chat bukan izin pengiriman laporan.

Tidak memperluas data atau membuka narasi bebas semata-mata agar AI terlihat
berguna. Evaluasi model sungguhan dengan data sintetis atau studi orang tua
memerlukan scope/izin tersendiri di luar eksperimen fake-provider ini.
