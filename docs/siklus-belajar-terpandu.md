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

### Kelas sekolah dan profil parameter (20 September 2026)

`kelas_sekolah` adalah metadata nullable 1–6, bukan `siswa.tingkat`. Form kelas
memakai revisi profil tersendiri; perubahan kelas tidak memanggil `ganti_level`,
menutup putaran, mengubah sesi, atau menghapus bukti. Admin menggunakan aksi,
token tinjauan, journal dan receipt kelas sekolah yang terpisah. Aksi/event level
lama tetap historis dengan arti profil parameter warisan.

Anak baru memilih konfigurasi latihan awal secara eksplisit; kelas sekolah
opsional dan tidak menentukan pilihan tersebut. Di UI, P3/P4/P5/P6 bernama
**Variasi A/B/C/D**: pembeda konfigurasi, bukan urutan kemampuan. Pengaturan latihan
awal dipisahkan dari identitas anak; header profil hanya menampilkan nama dan kelas.
Panduan native menampilkan pola dari komposisi registry dan contoh deterministik
per materi/variasi, bukan deskripsi kesulitan yang belum dikalibrasi. Contoh bukan
soal sesi yang akan dibuat. Kode historis tetap di nilai kiriman/penyimpanan dan
rincian teknis. Inisialisasi tanpa pilihan belum diaktifkan; tidak ada default
tersembunyi dari kelas sekolah. Anak lama mempertahankan konfigurasi warisannya.
Form manual/gabungan menampilkan pilihan variasi serta seluruh materi;
server menolak kombinasi yang tidak tersedia, tidak mengganti profil diam-diam.
Pemetaan bukan prasyarat latihan manual. Rencana terpandu masih memakai profil
warisan yang dipilih, bukan rekomendasi tuntutan otomatis yang sudah dikalibrasi.

Penulis baru membekukan konfigurasi per butir melalui `konteks_sesi` versi1 dan
`konteks_butir`; event orkestrator memuat konteks per butir/fokus. Konfirmasi
mengarsipkan konteks pada `konteks_konfirmasi`, append-only dan terikat konfirmasi
sumber. Konteks homogen v1 diproyeksikan oleh pola/nomor/level efektif/target fokus
yang sudah berada dalam fingerprint existing; tidak mengganti identitas retry.
Reader inti dan adapter memvalidasi sumber/arsip/outcome, menolak konteks hilang
atau tidak cocok. Histori tanpa marker tetap format lama, tanpa backfill otomatis.
Komposisi eksplisit di luar inventaris tetap latihan; konteks inventarisnya kosong,
bukan klaim tuntutan kemampuan. Sesi campuran profil belum diaktifkan dan tidak
boleh disimpan dengan satu level palsu.

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
langsung, pintu Pendamping kontekstual, pengingat bersyarat untuk membuka rencana,
serta maksimal tiga sesi terbaru yang perlu tindakan. Pengingat berasal dari
`learning_cycle.pengingat_berikutnya`, bukan perhitungan kelas/partisipasi di UI:
anak baru atau hanya latihan manual tanpa opt-in tidak mendapat ajakan pemetaan;
status menunggu dan maintenance tidak membuat banner. Sesi terpandu aktif, hasil
belum dikonfirmasi, dan tindakan tersedia (termasuk eskalasi) tetap diingatkan.
Tab rencana selalu tersedia; GET tidak menulis bukti. Sesi manual tidak mengambil
alih rekomendasi reducer.

Tab Rencana belajar menampilkan satu kartu ringkas **Langkah belajar berikutnya**,
berisi alasan, tindakan orang tua, dan satu CTA utama bila sah. Progres lengkap dan
alur umum berada dalam `<details>` tertutup **Detail progres dan alur belajar**.
Instruksi, contoh terbimbing/visual, beban pemetaan, tanggal menunggu, serta
peringatan konfirmasi/eskalasi/histori tetap terlihat tanpa membuka detail.
Label alat sesi **Cetak** mengutamakan lembar soal/kunci; perubahan cerita tetap
manual dalam `<details>` tambahan. Hasil sukses/gagal tampil di luar disclosure;
GET tidak memanggil AI dan penguncian penyajian tidak berubah. Tab Riwayat menampilkan
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

Angka utama laporan warisan adalah **progres target keterampilan Jagomat pada profil parameter aktif**,
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

### Fondasi pembacaan per konteks (20 September 2026)

`learning_cycle.penguasaan_konteks` menyediakan API murni untuk menilai pasangan
pola/profil parameter warisan secara terpisah. Ini **belum menggantikan laporan
katalog warisan di atas**, bukan tangga kesulitan atau penyebut persentase kesiapan OSN.
Kelas sekolah tidak menjadi input API; bukti profil berbeda tidak disatukan.

`mastery_evidence.lengkapi_bukti_materi` mencocokkan konfirmasi aktif, metadata
sesi, outcome, profil snapshot, hubungan butir dan penyajian soal sebelum memberikan
metadata bukti. Ketidakcocokan ditolak tanpa menulis data. Sidik warisan yang hilang
tidak direka. API konteks mempertahankan seluruh syarat penguasaan existing:
opt-in, representasi, kuota/jeda probe, fokus tertahan, invalidasi dan umur bukti.
Kejadian `diganti_level` historis tetap batas validitas; API bukan jalan menghidupkan
bukti lama yang telah dicabut. Perubahan kelas sekolah pada metadata terpisah tidak
menciptakan kejadian tersebut. Rincian **Bukti per konteks** kini tersedia pada
laporan penguasaan. Keterampilan, status dan nama variasi terlihat langsung; kode
konfigurasi dan tautan sumber berada dalam rincian tertutup. Rincian menampilkan
konteks dengan catatan penilaian relevan, tanpa mengubah 196 pasangan inventaris
menjadi penyebut persentase atau target wajib. Status
berasal dari reducer yang sama; keberhasilan satu profil tidak meluluskan profil
lain. Katalog/persentase lama tetap diberi label cakupan profil warisan, bukan
kemampuan global atau kelas sekolah. Penulis sesi campuran tuntutan dan rubrik
kemampuan baru belum diaktifkan oleh tahap ini.

### Batas aktivasi dan recovery tahap konteks

Mode source tetap persiapan/build-only; job pasang tertutup dan pin recovery tidak
berubah. Lulus probe pengiriman/PG historis tidak membuktikan recovery pin lama
memahami metadata konteks baru atau admin schema5. Sesudah penulis baru dipakai,
recovery harus pembaca kompatibel yang diuji melestarikan arsip konteks, revisi kelas,
receipt admin dan histori; tidak boleh downgrade schema atau menghapus metadata.
Rubrik tuntutan otomatis, kesetaraan lintas profil, serta campuran per fokus masih
menunggu keputusan produk dan implementasi terpisah.

### Pilot tuntutan keliling/luas (persetujuan 21 September 2026)

Pilot opsional pada tab Rencana belajar memisahkan dua tugas: keliling dari dua
sisi, dan mencari sisi dari keliling lalu luas. Rubrik `pilot-keliling-luas-v1`
tidak memberi jenjang kemampuan P3–P6. Tuntutan, profil parameter dan representasi
menjadi unit bukti terpisah; kelas sekolah tidak menjadi input.

Rujukan `luas_kotak_satuan/P3` hanya memeriksa makna luas melalui baris × kolom,
bukan sertifikasi luas semua profil. Bukti langsung + rujukan luas yang sah hanya
membuka pilihan probe balik melalui keputusan orang tua. P3 tidak menyediakan
varian balik; orang tua memilih P4/P5/P6 secara eksplisit. Pilot tidak memakai
codec campuran v2 dan tidak membuat persentase kemampuan baru.

Metadata sesi pilot membekukan seed, tujuan, putaran, butir, penyajian, tuntutan,
profil, versi dan sumber konfirmasi. Konfirmasi baru mengikat kontrak dalam
fingerprint dan arsip immutable. Tidak ada retag atau konfirmasi otomatis untuk
histori lama. API pilot memvalidasi variasi matematika tambahan tanpa mengubah
hash historis: nama benda, cerita, orientasi sisi yang sama, atau label cm/m saja
pada kisi tidak menambah jumlah probe.

Pengenalan/terbimbing/penguatan tetap bukan bukti mandiri. T memerlukan pengenalan
sebelum probe; contoh orang tua menyediakan dua pendekatan tugas balik. Fokus
berulang memakai kunci kanonis dan sumber snapshot aktif; koreksi sumber menahan
kelanjutan hanya pada putaran terkait, bukan menghidupkan bukti lama atau menahan
status tuntutan lain. Orang tua dapat mengonfirmasi penutupan putaran tersebut dan
pembatalan seluruh sesinya tanpa menghapus histori/snapshot. Setelah itu pemeriksaan
baru dipilih eksplisit; fokus/konfirmasi lama tidak diikat ulang otomatis. Metadata
rusak struktural tetap ditolak, bukan dianggap sebagai pencabutan yang sah. Evaluasi, checkpoint,
penjelasan dan eskalasi tetap memakai reducer yang sama. Untuk tuntutan yang
berhasil tanpa fokus diagnosis, retensi memakai checkpoint dua bagian dengan
≥3 probe baru dan seluruhnya benar; tidak membuat fokus K/H palsu. Bila checkpoint
tersebut gagal tanpa pendekatan remedial terikat, arahkan ke pemeriksaan prasyarat
atau uji ulang lisan, bukan menambah latihan tanpa batas.

Rencana v1 yang wajib tetap didahulukan. Satu CTA pilot berlaku untuk langkah
berikutnya; manual selalu dapat diakses tanpa pemetaan wajib. Laporan Tuntutan
pilot memakai status dari reducer, bukan persen baru. Sesi pilot tidak disatukan
ke penguasaan/pemetaan v1. Cetak/pengiriman/tinjauan menggunakan snapshot yang sama;
perubahan cerita tertutup setelah penyajian pilot dibekukan. CLI dan Pendamping
masih manual; serupa/remedial lama tidak boleh membuang konteks pilot.

Migrasi aditif tidak membuat sesi atau keputusan belajar. Kandidat rilis memakai
mode migrasi dan pasang literal false, dengan baseline recovery pilot175d8fb.
Uji pasangan exact image dan rehearsal tetap wajib; status source bukan bukti live.
Materi terbimbing membaca intervensi sebelum sesi dibuat, bukan pendekatan terbaru.

## 11. Batas MVP

MVP tidak mencakup graf prasyarat adaptif penuh, AI pemilih kurikulum,
intervensi AI tanpa review manusia, notifikasi otomatis, gamifikasi, atau
klaim penguasaan permanen. Status tertinggi tetap **bertahan**, bukan
“dikuasai selamanya”.
