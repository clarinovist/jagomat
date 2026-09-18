# Spesifikasi Siklus Belajar Terpandu

**Status dokumen:** sumber kebenaran produk untuk siklus belajar Jagomat.

Dokumen ini memuat kontrak yang harus bertahan lintas implementasi. Rincian
urutan kerja TDD ada di
`plan/2026-09-06-siklus-belajar-terpandu.md` (lokal/gitignored),
sedangkan perilaku yang sudah tersedia tetap dibuktikan oleh kode dan test
`../mesin/`.

Jika dokumen produk lama berbeda dengan spesifikasi ini, spesifikasi ini yang
berlaku untuk siklus belajar. `../CLAUDE.md` tetap menjadi sumber palang
arsitektur, privasi, pengujian, dan proses pengembangan.

## 1. Tujuan

Jagomat harus memberi satu langkah belajar berikutnya yang jelas, bukan hanya
menyediakan kumpulan alat atau menghasilkan lebih banyak soal setelah anak
salah.

Siklus utama:

`pemetaan → fokus → intervensi → latihan terbimbing → penguatan mandiri → evaluasi berjeda → checkpoint → maju atau eskalasi`

Guru boleh mengabaikan rekomendasi dan memakai latihan manual. Aktivitas manual
tidak boleh diam-diam mengubah putaran belajar.

## 2. Bukti yang sah

Bukti pedagogis hanya berasal dari sesi yang:

1. selesai;
2. setiap butir memiliki outcome—jawaban dan diagnosis, atau penanda dilewati;
3. ditinjau dan dikoreksi bila perlu;
4. dikonfirmasi eksplisit oleh guru.

Membuka halaman hanya mengisi `direview`; itu bukan konfirmasi. `kode_final`
yang masih mutable juga bukan bukti permanen.

Anak boleh mengirim latihan dengan jawaban kosong dan tanpa alasan. Refleksi kosong
opsional tersimpan terpisah dari jawaban/cara. Bingung atau catatan belum pernah
melihat soal bukan diagnosis otomatis: guru memastikan kebutuhan pengenalan sebelum
memilih T. Pekerjaan sebagian tetap diakui, bukan dilabeli tidak dikerjakan.

Pengiriman baru mengarsipkan seluruh butir secara immutable, termasuk yang kosong;
arsip ini bukan bukti pedagogis. Sesi warisan tanpa arsip diberi keterangan jujur
bahwa rekaman saat pengiriman belum tersedia. Koreksi transkripsi pekerjaan asli
memerlukan sumber; jawaban setelah diberi bantuan dicatat terpisah dan tidak boleh
disahkan sebagai bukti mandiri, baik benar maupun salah. Hasil setelah bantuan
tidak boleh menambah bukti kelemahan K/H atau kategori lain. Gunakan probe berikutnya
untuk bukti mandiri; penanda dilewati tetap harus eksplisit.

**Simpan tinjauan** menjaga catatan/keputusan sementara agar dapat dilanjutkan,
tanpa snapshot bukti atau pemetaan. **Konfirmasi hasil** tetap mengharuskan outcome
lengkap atau penanda dilewati eksplisit. Tinjauan dan provenance yang dipakai diikat
pada fingerprint/snapshot konfirmasi; perubahan relevan mencabut bukti aktif tanpa
mengubah snapshot lama. Tab lama yang berbeda tidak boleh menimpa tinjauan terbaru.

Setiap konfirmasi membuat snapshot kanonis append-only berisi outcome tiap
butir, kode final, malrule, penanda dilewati, level efektif, dan cek pemahaman.
Bukti putaran merujuk `konfirmasi_id`. Koreksi berikutnya menginvalidasi bukti
aktif dan membutuhkan konfirmasi baru, tetapi snapshot lama tetap dapat
direproduksi.

Sesi diagnostik bebas hanya masuk pemetaan bila guru memilih **Sertakan dalam
pemetaan** saat konfirmasi. Latihan terbimbing dan penguatan tidak pernah
memperbesar skor kelemahan.

**Pilihan ganda manual** adalah format latihan tambahan (3–5 opsi sesuai pola),
bukan bukti pemetaan atau penguasaan. Hasil boleh ditinjau dan dikonfirmasi sebagai
riwayat, tetapi tidak dapat opt-in pemetaan, memicu remedial otomatis, atau mengubah
fokus/evaluasi/checkpoint. Pilihan tepat hanya menunjukkan kecocokan jawaban;
penyebab salah dan pemahaman tetap memerlukan tinjauan orang tua. Format isian
pada alur terpandu tidak berubah. Opsi serta urutannya disimpan per butir dan
ikut arsip pengiriman/konfirmasi agar cetak ulang dan koreksi dapat ditelusuri.

## 3. Pemetaan dan fokus

Pemetaan awal memakai tiga sesi 15 soal pada tiga tanggal berbeda:

- sesi pertama memperluas cakupan;
- sesi kedua dan ketiga menyertakan maksimal lima *anchor probe* kandidat dari
  sesi sebelumnya dengan parameter baru;
- kandidat yang baru muncul pada sesi ketiga atau tidak masuk kuota lima
  dilanjutkan lewat probe diagnostik tambahan, bukan dibuang.

Kunci fokus kanonis:

`(template_id, kode_intervensi, malrule_id)`

`malrule_id` boleh kosong untuk kebiasaan atau bukti tanpa malrule spesifik.
Dua miskonsepsi berbeda pada template yang sama memakai dua slot. Maksimal dua
kunci fokus aktif per putaran.

Fokus otomatis membutuhkan kunci K atau H yang sama pada minimal dua sesi
berbeda. Satu kejadian hanya berstatus **pantau**. Campuran satu K dan satu H
tidak dihitung sebagai dua bukti yang sama.

Guru dapat melakukan override fokus sebelum intervensi dimulai. Setelah tahap
pertama berjalan, perubahan fokus harus menutup konfigurasi lama dan
membatalkan sesi turunannya secara non-destruktif sebelum membuka putaran baru.

## 4. Tindakan per diagnosis

| Kode | Tindakan |
|---|---|
| B | Tandai informasi dan ucapkan ulang yang ditanya; strategi ditempel pada sesi berikutnya |
| K | Konsep konkret/visual → contoh terbimbing → penguatan mandiri |
| H | Tulis langkah dan periksa ulang; bukan lubang konsep |
| E | Cocokkan hasil kerja dengan jawaban akhir sebelum mengirim |
| N | Tanyakan “dapat dari mana?”; kegagalan berulang menjadi kandidat K terselubung tanpa mengubah diagnosis lama |
| T | Pengenalan materi → contoh awal → probe diagnostik; bukan remedial |

Intervensi yang dipakai anak harus pra-tulis atau sudah direview manusia. K
tanpa konten spesifik harus gagal secara terlihat kepada orang tua, bukan jatuh
diam-diam ke drill generik.

Setiap pendekatan mempunyai `pendekatan_id`. Setelah evaluasi gagal pertama,
pendekatan berikutnya harus berbeda. Jika tidak ada alternatif, langsung
eskalasi.

## 5. Evaluasi dan pemahaman

Evaluasi tersedia tiga hari setelah penguatan selesai dan dikonfirmasi.
Komposisi minimum:

- satu fokus: 4 probe fokus + 6 soal pembanding;
- dua fokus: 4 + 4 probe fokus + 2 soal pembanding.

Soal pembanding tidak masuk denominator fokus. Seluruh soal memakai parameter
baru dan tidak menyalin soal penguatan.

Status **mulai membaik** membutuhkan semuanya:

- minimal 75% probe fokus benar;
- tidak ada K final;
- guru mencatat **bisa menjelaskan**.

Pilihan **ragu** atau **menghafal** mencegah kelulusan walaupun jawaban benar.
Kegagalan pertama kembali ke intervensi berbeda. Kegagalan kedua berturut-turut
memicu cek prasyarat statis atau Uji Ulang Lisan.

## 6. Checkpoint dan kekambuhan

Checkpoint dijadwalkan per fokus:

- pertama: 28 hari setelah evaluasi sukses;
- berikutnya: 28 hari setelah checkpoint sukses terakhir;
- setiap occurrence terdiri dari dua sesi 10 soal;
- pasangan sesi memuat minimal tiga probe baru per fokus yang jatuh tempo;
- status tidak berubah sebelum kedua bagian selesai dan dikonfirmasi.

Checkpoint pertama yang seluruh probe fokusnya benar, tanpa K, dan tetap
**bisa menjelaskan** menghasilkan status **bertahan**. Fokus bertahan tetap
diuji berkala.

K baru yang dikonfirmasi pada fokus bertahan, atau pola gagal pada dua sesi
baru, membuka putaran baru tanpa menghapus histori keberhasilan sebelumnya.

## 7. Progresi materi baru

Kode T bukan kelemahan. Ia masuk antrean pengenalan:

`T → pengenalan_selesai → probe diagnostik → hasil terkonfirmasi`

Materi baru tidak boleh keluar dari antrean atau jatuh ke mixed maintenance
sebelum probe tersebut dikonfirmasi. Jika tidak ada fokus aktif atau materi T,
sistem boleh merekomendasikan mixed maintenance.

## 8. Prioritas rekomendasi

1. Sesi orkestrator belum selesai pada putaran aktif.
2. Sesi orkestrator selesai tetapi belum dikonfirmasi.
3. Eskalasi setelah dua kegagalan.
4. Pemetaan atau probe diagnostik lanjutan.
5. Evaluasi yang jatuh tempo.
6. Intervensi yang belum dilakukan.
7. Latihan terbimbing atau penguatan yang belum dilakukan.
8. Checkpoint fokus yang jatuh tempo.
9. Probe setelah pengenalan materi.
10. Pengenalan materi T/kandidat kemajuan.
11. Mixed maintenance.

Hanya sesi dengan putaran dan level aktif, tujuan bukan `bebas`, serta belum
dibatalkan yang boleh memblokir kartu utama. Jika lebih dari satu, pilih yang
tertua secara deterministik. Sesi manual/lama tampil sebagai tugas sekunder.

## 9. Penyimpanan dan batas modul

`learning_cycle.py` adalah reducer domain murni: menerima bukti immutable dan
menghasilkan status/rekomendasi tanpa menulis database. Query, transaksi,
validasi ulang, dan pembuatan sesi tinggal di lapisan database/layanan.

Identitas dan provenance disimpan melalui putaran, kejadian, konfirmasi, dan
snapshot outcome append-only. Status tampilan selalu diturunkan, bukan ditimpa.
Sesi berbukti tidak boleh di-hard-delete; gunakan pembatalan/arsip dan FK
`RESTRICT`.

Idempotensi pembuatan sesi membedakan double-submit dari retry sah. Kunci
memuat siswa, tujuan, putaran, fokus terurut, sumber, bagian checkpoint, dan
occurrence; pembatalan melepaskan kunci aktif.

Perubahan level menutup putaran lama dengan kejadian `diganti_level`, membuat
sesi level lama tidak memblokir, dan memulai pemetaan level baru tanpa
menghapus histori.

### Data warisan

Sesi lama tetap latihan bebas; tidak ada konfirmasi, fokus, atau putaran yang
dibuat otomatis dari `direview` maupun diagnosis lama. Sesi yang sudah dilihat
tetapi belum selesai tetap dianggap belum lengkap, bukan diperbaiki otomatis.

Level sesi lama tidak mengikuti perubahan level profil. Profil dan laporan
menjelaskan histori beda level sebagai catatan yang tetap tersimpan, bukan
bukti pemetaan level aktif. Pemetaan level aktif dimulai dari bukti yang sah.

Sebelum migrasi, buat cadangan konsisten dan uji pada salinan terlebih dahulu.
Pastikan isi histori dan jumlah baris tetap utuh, migrasi idempoten, serta
`integrity_check` dan `foreign_key_check` bersih. Jangan melakukan backfill
keputusan pedagogis atau koreksi data anak saat verifikasi deploy.

## 10. Permukaan pengguna

Profil anak memakai tiga tab server-side: **Buat latihan** (halaman awal),
**Rencana belajar**, dan **Riwayat**. Buat latihan menyediakan form manual secara
langsung, pintu Pendamping kontekstual, pengingat untuk membuka rencana, serta
maksimal tiga sesi terbaru yang perlu tindakan. Sesi manual tidak mengambil alih
rekomendasi reducer.

Tab Rencana belajar menampilkan satu kartu **Rencana belajar hari ini**, berisi
alasan, progres, tindakan orang tua, dan satu CTA utama. Tab Riwayat menampilkan
20 sesi per halaman, filter tanggal/topik/jenis/tinjauan, serta status pengerjaan
dan tinjauan yang terpisah. Pindah tab atau memfilter tidak menulis bukti maupun
mengubah progres. Pendamping tetap pada konteks rencana, latihan, atau sesi/soal;
riwayat lengkap tidak otomatis dikirim ke layanan AI.

Profil dan laporan wajib memakai reducer yang sama. Statistik seluruh latihan
boleh tetap ada tetapi dilabeli terpisah agar tidak bertentangan dengan status
siklus.

Permukaan anak hanya menampilkan istilah netral seperti **Pelajari bersama**,
**Coba mandiri**, dan **Latihan campuran**. Jangan tampilkan kode diagnosis,
label kelemahan, alasan internal, kunci, atau malrule.

### Peta penguasaan target Jagomat (15 September 2026)

Angka utama laporan adalah **progres target keterampilan Jagomat di kelas aktif**,
bukan rasio jawaban benar atau klaim seluruh kurikulum sekolah. Katalog eksplisit
`mastery_catalog.py` mengelompokkan pola terkait; semua pola yang tersedia pada
kelas tersebut wajib terbukti sebelum target dihitung menunjukkan pemahaman.
Target berbobot sama, terlepas jumlah soal yang dikerjakan. Penyebut tidak menyusut
menjadi hanya materi yang pernah dicoba. Topik menampilkan progres targetnya sendiri.

API murni `learning_cycle.penguasaan_target` memutuskan status, tanpa mengubah
rekomendasi/fokus siklus existing. Kontrak bukti:

- Hanya snapshot aktif dari sesi selesai, terkonfirmasi, kelas/siswa benar, bukan
  dibatalkan, mode diagnostik. Latihan manual perlu opt-in pemetaan pada konfirmasi
  yang sama. Drill/terbimbing/penguatan/pengenalan bukan sertifikasi penguasaan.
- Satu pola dapat menunjukkan pemahaman dari dua pemetaan terbaru berjarak minimal
  tiga hari, minimal empat probe total dengan fingerprint matematis berbeda, tiap
  pemeriksaan minimal75% benar, tanpa K/N/T/hasil belum jelas, dan seluruh probe
  memiliki catatan bisa menjelaskan. Sidik hilang/duplikat tidak dianggap variasi.
- Alternatifnya evaluasi terpandu: minimal empat probe per fokus kanonis, ambang
  reducer75%, tanpa K/N/T/hasil belum jelas, bisa menjelaskan, dan soal bervariasi.
  Soal pembanding bukan bukti penguasaan pola lain. Dua fokus pada pola yang sama
  tidak disatukan; fokus belum pulih menghalangi klaim pola tersebut.
- Checkpoint mengikuti pasangan occurrence dan kelulusan reducer existing,
  minimal tiga probe bervariasi. Bagian belum lengkap tidak memperbarui bukti.
- Representasi tidak dicampur. Koreksi yang belum dikonfirmasi ulang membutuhkan
  cek kembali, bukan diam-diam memilih keberhasilan lama. Bukti baru yang tidak
  mendukung pemahaman menahan klaim; drill/latihan terbimbing tidak membuat kelemahan.
- Bukti penguasaan berumur28hari ditandai **perlu cek kembali**; tidak permanen.
  Pergantian kelas memulai cakupan bukti kelas aktif yang baru, bukan menghidupkan
  sertifikasi kelas lama saat profil kembali ke kelas tersebut.

Status target: **menunjukkan pemahaman**, **masih dipelajari** (termasuk sebagian pola
belum diperiksa), **perlu cek kembali**, atau **belum dinilai**. Tanpa catatan bukti,
persentase tampil—dan label belum dinilai; itu bukan ketidakmampuan anak. Bila ada
bukti sebagian, persentase menunjukkan bagian dari seluruh target yang telah
terbukti. Grafik komposisi menampilkan semua status; bukan rekonstruksi tren waktu
atau tes psikometrik. Penambahan target katalog memperluas bagian belum dinilai,
bukan bukti anak mengalami penurunan kemampuan.

Cakupan ini tidak menjadwalkan target baru otomatis. Resume tetap mengikuti prioritas
siklus existing. Katalog menyajikan sasaran yang belum memiliki bukti, bukan membuat
kurikulum/soal baru atau mengubah sesi manual menjadi bukti tanpa persetujuan.

## 11. Batas MVP

MVP tidak mencakup graf prasyarat adaptif penuh, AI pemilih kurikulum,
intervensi AI tanpa review manusia, notifikasi otomatis, gamifikasi, atau
klaim penguasaan permanen. Status tertinggi tetap **bertahan**, bukan
“dikuasai selamanya”.
