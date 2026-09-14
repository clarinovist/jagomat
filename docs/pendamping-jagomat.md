# Pendamping Jagomat — spesifikasi versi awal

**Status: spesifikasi awal/historis; arah halaman chat terpisah sudah digantikan.**
Dicatat 11 September 2026 dari kesepakatan diskusi produk. Bagian historis di
bawah merekam tahap saat dokumen dibuat, bukan arah UI terkini. Pendamping sekarang
menyatu pada profil anak dan pemeriksaan sesi; lihat
[kontrak runtime Pendamping](pendamping-runtime.md). Chat umum lama dipertahankan
sebagai arsip hanya-baca di pengaturan akun; tidak ada composer atau halaman
Pendamping mandiri. Penerimaan redesign dan keadaan produksi tetap harus
dibuktikan terpisah; dokumen
ini bukan persetujuan mengirim data personal ke layanan AI.

Acuan: [palang proyek](../CLAUDE.md), [siklus belajar](siklus-belajar-terpandu.md),
[design system](design-system.md), dan [workflow](workflow-reference.md).
Jika ada konflik, palang akses/privasi dan kontrak siklus tetap berlaku.

## 1. Tujuan dan batas versi awal

Halaman khusus **Pendamping** bagi orang tua: tempat bercerita, memahami Jagomat,
membahas soal, dan menyiapkan langkah yang disetujui. Bukan chatbot anak,
bukan pengganti pendidik/profesional kesehatan, dan bukan AI penentu kurikulum.
Ukuran keberhasilan: orang tua lebih memahami situasi dan satu langkah berikutnya;
bukan panjang percakapan atau banyaknya soal yang dihasilkan.

Kesepakatan produk:

- Halaman awal lega dengan kolom **Apa yang bisa dibantu hari ini?**;
  tanpa judul besar, contoh pertanyaan, atau kartu saran.
- Setelah ada pesan, percakapan menjadi fokus; kolom pesan berada di bawah.
- Tombol **Chat baru**, riwayat di panel yang dapat ditutup, dan menu chat.
- **Chat tanpa memori** tersedia di menu; kontrol lengkap di **Pengaturan → Memori**.
- Mengenal katalog Jagomat dan mengambil soal tertentu saat diperlukan.
- Memori lintas chat tersedia setelah diaktifkan dengan persetujuan.
- Konteks anak/sesi terlihat dan dipilih, bukan otomatis dibaca karena membuka chat.

Tahap pekerjaan sekarang hanya spesifikasi dan mockup sintetis. Belum membuat
endpoint, tabel, autentikasi baru, integrasi AI, atau perubahan aplikasi.

## 2. Empat prinsip karakter

| Prinsip | Perilaku yang diharapkan | Yang dihindari |
| --- | --- | --- |
| Hangat dan mendengarkan | Tanggapi keresahan singkat, pahami situasi sebelum menyarankan tindakan | Menyalahkan, menghakimi, langsung menambah soal |
| Santai dan ringkas | Bahasa Indonesia sehari-hari yang rapi; satu klarifikasi relevan pada satu waktu bila perlu | Sapaan Bunda/Ayah otomatis, pujian pembuka rutin, emoji berlebihan, daftar panjang tanpa diminta |
| Jujur, tidak asal mengiyakan | Bedakan fakta, cerita, dan dugaan; koreksi pendekatan yang merugikan dengan sopan | Janji keberhasilan, label anak, diagnosis psikologis, mengarang dukungan fitur |
| Membantu tanpa mengambil alih | Tawarkan langkah konkret; minta konfirmasi tindakan tersimpan | Membuat sesi, menyimpan memori, atau mengubah status belajar berdasarkan tebakan niat |

Contoh sintetis:

> Orang tua: “Capek, sudah dijelaskan berkali-kali masih lupa.”
>
> Pendamping: “Mengulang hal yang sama memang bisa melelahkan. Biasanya lupa saat
> mengerjakan sendiri, atau saat dibahas bersama juga masih bingung?”

Tidak semua percakapan harus berakhir dengan tindakan. Penolakan tindakan yang
merugikan tetap empatik. Saran pendampingan umum bukan intervensi resmi; materi
intervensi yang digunakan anak harus pra-tulis atau direview manusia sesuai siklus.

## 3. Sumber pengetahuan dan kewenangan

| Sumber | Penggunaan | Batas |
| --- | --- | --- |
| Katalog topik/template, level, parameter yang didukung | Menjawab jenis soal dan menyusun usulan latihan | Jangan mengklaim variasi tersedia tanpa hasil pemeriksaan katalog |
| Soal spesifik beserta visual, kunci, dan pembahasan resmi | Menjelaskan soal yang benar-benar sedang dibahas | Permukaan orang tua; validasi akses sebelum mengambil data |
| Panduan produk | Menjelaskan fitur dan navigasi | Bedakan tersedia, direncanakan, dan tidak didukung |
| Hasil reducer siklus | Menjelaskan langkah belajar resmi dan alasannya | Tidak menghitung ulang status lewat LLM |
| Catatan belajar yang aksesnya disetujui | Menyesuaikan bantuan dengan konteks anak terpilih | Ambil minimum yang relevan; tidak membuka seluruh keluarga |
| Cerita pengguna dan memori | Menjaga kesinambungan percakapan | Bukan bukti pedagogis atau diagnosis |

Generator berparameter mempunyai banyak kemungkinan soal. “Tahu seluruh soal”
berarti katalog mencakup seluruh template yang tersedia dan dapat mengambil
instance yang tepat, bukan memasukkan semua variasi ke setiap prompt.

Peta sumber implementasi untuk investigasi berikutnya: `mesin/topics.py`,
`mesin/templates.py`, `mesin/generator.py`, pembahasan/kartu rumus resmi, dan
`mesin/learning_cycle.py`. Ini bukan API alat agent yang sudah tersedia. Adapter
katalog kelak harus diuji terhadap registry aktual supaya template baru tidak
terlewat. Dukungan perubahan cerita tidak otomatis berarti semua tema bebas bisa
dipilih; kemampuan aktual harus diverifikasi.

Jawaban tentang soal merujuk nomor soal/sumber yang benar. Jangan meregenerasi
soal berbeda lalu mengaku sedang membaca soal sesi. Jika visual atau pembahasan
belum dapat diakses, nyatakan keterbatasan dan jangan menebak.

Alur tindakan:

`percakapan → usulan terstruktur → validasi mesin → tinjau orang tua → konfirmasi → eksekusi → hasil nyata`

LLM tidak menentukan kunci, malrule, diagnosis, bukti, atau status siklus. Latihan
manual tidak diam-diam mengubah putaran. Klik tinjau bukan konfirmasi membuat sesi.
Konfirmasi harus terikat parameter/konteks yang ditinjau; perubahan usulan
membutuhkan tinjauan ulang. Hanya hasil eksekusi berhasil yang boleh disebut selesai.

Perluasan chat bukan sekadar memperlebar fungsi parafrase soal B2 pada `llm.py`.
Jalur chat dan akses alat harus dirancang tersendiri tanpa melemahkan verifikasi
soal atau permukaan anak yang sudah ada.

## 4. Tiga lapisan yang terpisah

1. **Percakapan/riwayat:** pesan dalam sebuah chat; dapat dibuka lagi.
2. **Memori:** catatan ringkas yang disetujui untuk digunakan lintas chat.
3. **Konteks belajar:** resource resmi yang dipilih dan diizinkan, bukan memori.

| Situasi | Pesan chat lama | Memori lintas chat | Konteks belajar |
| --- | --- | --- | --- |
| Chat baru, memori aktif | Tidak otomatis diambil | Hanya yang disetujui, relevan, dan sesuai lingkup | Mulai umum; konteks baru perlu dipilih/disetujui |
| Melanjutkan chat biasa | Pesan di chat yang sama, bukan chat lain | Mengikuti pengaturan saat ini | Validasi ulang akses dan kebaruan |
| Chat tanpa memori | Hanya pesan di chat ini saat dilanjutkan | Tidak dibaca dan tidak ditambahkan | Tetap bisa dipilih/disetujui secara eksplisit |
| Penggunaan memori dimatikan | Tetap dapat membuka riwayat | Catatan tetap tersimpan, tetapi tidak dipakai atau ditambah | Tidak berubah menjadi akses bebas |

“Chat tanpa memori” **bukan** janji chat tidak disimpan. Riwayat dapat tetap
tersimpan dan harus dijelaskan. Kebijakan retensi belum dipilih (bagian 9).
Mengubah mode sebaiknya membuka chat baru: jangan mengklaim percakapan yang sudah
mengandung jawaban berbasis memori tiba-tiba bersih setelah tombol diganti.
Mode tanpa memori melekat pada chat ketika dibuka kembali.

Katalog/panduan Jagomat selalu boleh dipakai, termasuk tanpa memori. Instruksi
saat ini mengalahkan preferensi tersimpan, tetapi tidak dapat membatalkan palang.

## 5. Memori yang bisa dikendalikan

Rancangan konservatif versi awal:

- Penggunaan memori awalnya belum aktif; pengguna mengaktifkan setelah membaca
  penjelasan. Setelah diaktifkan, chat biasa berikutnya boleh menggunakannya.
- Setiap penambahan/perubahan memori harus menampilkan teks yang akan disimpan
  dan lingkupnya untuk dikonfirmasi. Jangan meminta konfirmasi setiap pesan.
- Preferensi cara menjawab dan tujuan pendampingan adalah kandidat yang sesuai.
  Curhatan sesaat, dugaan diagnosis, label karakter anak, sandi, serta email/telepon
  tidak dijadikan memori. Kontak dan credential tidak diminta oleh fitur ini.
- Memori preferensi melekat pada akun orang tua. Memori khusus anak, jika kelak
  disetujui cakupannya, harus terpisah per anak dan hanya dipakai dalam konteks
  anak yang dipilih. Tidak ada berbagi otomatis antarorang tua/pengelola.
- Pengaturan menampilkan isi, lingkup, sumber/waktu konfirmasi, aksi koreksi,
  hapus satu, dan hapus semua. Status aktif/nonaktif tidak disamakan dengan hapus.
- Saat penggunaan memori nonaktif, pengguna tetap boleh melihat, mengoreksi, atau
  menghapus catatan melalui pengaturan. Yang dihentikan adalah pemakaian/penambahan
  oleh asisten, bukan kendali pengguna atas catatannya.
- Informasi yang berubah perlu dikonfirmasi ulang; jangan menimpa diam-diam.
  Jawaban tidak perlu menyebut memori setiap saat, tetapi sumber penggunaannya
  harus dapat diperiksa, misalnya lewat rincian jawaban.
- Hapus memori menghentikan pengambilan catatan itu untuk respons selanjutnya;
  tidak otomatis menghapus chat sumber atau teks jawaban lama. Membuka chat
  sumber masih memperlihatkan pesan di sana, tanpa membuat ulang memori otomatis.
- Hapus chat harus menjelaskan apakah ada memori turunannya; usulan UX menyediakan
  pilihan eksplisit menghapus memori terkait juga. Jangan menyisakan salinan
  tersembunyi melalui ringkasan/cache. Mekanisme retensi/purging masih perlu desain.

Bukan keputusan versi awal: menelusuri seluruh transkrip chat lama, mengekstrak
profil otomatis, atau mengambil data keluarga lain. Ingat yang relevan, bukan
selalu membahas masa lalu.

## 6. Pemilihan konteks

- Dari menu Pendamping: **Obrolan umum · tanpa catatan anak**.
- Dari halaman anak: tawarkan konteks anak itu, jelaskan kategori data yang
  diperlukan, lalu tunggu persetujuan. Nama/ID asal tautan bukan izin akses.
- Dari sesi: tawarkan sesi/soal yang sedang dibuka. Memahami katalog tidak berarti
  boleh membaca lembar terisi tanpa pemeriksaan kepemilikan dan persetujuan.
- Persetujuan memakai konteks bukan persetujuan umum mengirim data ke provider.
  Ringkasan tanpa nama tetap dapat menjadi data anak.
- Gunakan penanda ringkas di chat. Rincian dapat dibuka untuk melihat sumber yang
  dipakai, mengganti, atau menghentikan konteks.
- Usulan aman: berpindah anak atau melepas konteks membuka chat baru. Menyembunyikan
  label tidak menghilangkan informasi dari pesan yang sudah masuk percakapan.
- Konteks yang dicabut, tidak lagi dimiliki, diarsipkan, atau berubah harus
  divalidasi ulang. Jangan memakai ringkasan lama sebagai jalan belakang.

## 7. Tampilan dan aksesibilitas

- Nuansa sederhana seperti halaman chat, identitas tetap Jagomat. Warna memakai
  token aplikasi, tanpa font/CDN, JS, atau dependency baru untuk mockup.
- Kolom awal di tengah area utama. Placeholder sesuai kesepakatan; tetap ada label
  aksesibel yang tidak bergantung pada placeholder. Input mendukung beberapa baris.
- Saat ada percakapan, pesan orang tua dibedakan dari jawaban pendamping dengan
  label teks, bukan warna saja. Panjang jawaban nyaman dibaca pada desktop/HP.
- Panel riwayat tertutup secara bawaan; dapat dibuka dengan keyboard. Fokus
  terlihat; target sentuh minimum 44px; tidak ada gulir horizontal pada 390px.
- Tidak ada pilihan model, mikrofon, unggah berkas, atau kartu pertanyaan awal.
- Usulan latihan hanya muncul bila relevan dan telah tervalidasi. Satu tindakan
  memiliki satu entry point; opsi perbaikan hanya saat diperlukan.
- Pengiriman, galat, dan hasil tindakan harus punya status teks yang aksesibel.
  Zero-JS adalah batas awal. Pengecualian yang disetujui: Kirim/Periksa status
  inline tanpa reload, status menunggu, dan pemulihan pesan gagal; fallback native
  tetap tersedia. Streaming, auto-scroll ke balasan, textarea auto-grow, atau
  interaksi JS lain memerlukan persetujuan tersendiri. Lihat
  [kontrak runtime](pendamping-runtime.md#kirim-tanpa-reload).

Mockup lokal: `../../osn-resources/referensi/desain-ui/pendamping-2026-09-11/`.
Folder tersebut opsional dan tidak diperlukan untuk clone, test, atau build.
Mockup adalah kumpulan keadaan statis, bukan percakapan atau penyimpanan nyata.
Tombol tulis dinonaktifkan; perpindahan halaman hanya memperlihatkan contoh.

## 8. Failure path dan palang implementasi berikutnya

Implementasi nanti **jalur Kritis** karena auth, konteks anak, riwayat, dan memori.
Spesifikasi ini tidak mengubah izin admin yang sudah ada menjadi izin membaca
curhatan keluarga. Batas akses chat/memori harus ditentukan tersendiri.

| Kondisi | Perilaku wajib |
| --- | --- |
| Provider belum dikonfigurasi/tidak tersedia | Pesan jujur; jangan memberi jawaban tiruan atau mengklaim tindakan berhasil |
| Katalog kosong, sumber usang, atau variasi tidak didukung | Tidak mengarang katalog; beri keterbatasan/pilihan valid |
| Akses resource asing | 404 dengan body identik; tidak ada pembacaan data privat atau efek samping |
| Akses dari permukaan murid | Tidak ada chat orang tua, memori, kunci, diagnosis, atau laporan |
| Permintaan/teks soal berisi instruksi mengambil data lain | Diperlakukan sebagai data tidak tepercaya; izin alat tetap ditentukan server |
| Mode tanpa memori atau pengaturan nonaktif | Asisten tidak mengambil/menggunakan/menambahkan memori, termasuk melalui cache; pengelolaan eksplisit oleh pengguna tetap tersedia |
| Memori anak A di chat anak B/umum | Tidak diambil, tidak disebut, tidak dipakai untuk usulan |
| Konteks berubah atau persetujuan dicabut | Hentikan pengambilan; perlakukan pesan lama secara eksplisit, tawarkan chat baru |
| Timeout setelah konfirmasi tindakan | Periksa hasil/idempotensi; retry tidak membuat sesi ganda |
| AI salah menjelaskan soal | Kunci resmi tidak berubah; tampilkan sumber dan jalur koreksi manusia |

Tool dibatasi daftar izin, tidak ada SQL/akses berkas bebas. Otorisasi per resource
berlaku sebelum query/retrieval, bukan sekadar instruksi dalam prompt. Tidak ada
raw credential, chat, lembar terisi, atau konteks anak dalam log pengujian/CI.

## 9. Keputusan sebelum integrasi

Belum diputuskan; blocker untuk integrasi personal/live, bukan blocker mockup:

1. Provider/model, biaya/batas penggunaan, lokasi pemrosesan, kebijakan pelatihan,
   retensi provider, dan persetujuan pengiriman. Kredensial tidak masuk browser.
2. Retensi chat, memori, turunan, dan cadangan; hak hapus serta keterlambatan
   penghapusan pada backup/provider harus dinyatakan secara jujur.
3. Kategori konteks anak yang boleh dikirim dan redaksi persetujuannya. Default
   minimum, bukan seluruh DB atau laporan. Tanpa persetujuan, tidak dikirim.
4. Kategori memori khusus anak di luar preferensi orang tua, dan akses dukungan
   pengelola ke chat/memori. Tidak diasumsikan ikut izin administrasi data murid.
5. Bentuk integrasi UI: pertahankan POST/render server-side dahulu atau minta
   persetujuan JS terbatas. Tidak memakai layanan builder eksternal untuk mockup.
6. Penanganan kontak/credential yang tidak sengaja diketik: harus dicegah masuk
   riwayat, memori, log, dan payload AI sebelum penyimpanan/pengiriman. Peringatan
   UI saja tidak memenuhi larangan menyimpan email/telepon proyek.

Implementasi bertahap yang diusulkan: adapter katalog + panduan tanpa data anak,
kemudian chat/riwayat dan memori berizin, lalu konteks belajar serta usulan tindakan.
Urutan ini tidak menghapus kebutuhan memori lintas chat yang telah disepakati.

## 10. Acceptance criteria dan verifikasi

Untuk **dokumen + mockup sekarang**:

- [x] Halaman awal hanya berfokus pada kolom pesan, tanpa kartu pertanyaan.
- [x] Desktop/HP menunjukkan percakapan, riwayat tertutup/terbuka, tanpa memori,
      persetujuan konteks, serta pengaturan memori.
- [x] Pengaturan nonaktif tidak digambarkan sebagai penghapusan; mode tanpa memori
      tidak digambarkan sebagai penghapusan riwayat.
- [x] Seluruh contoh sintetis; tidak ada DB, provider, penyimpanan, atau kiriman pesan.
- [x] Referensi internal konsisten; diff dokumen dan palang repo direview.

Hasil lokal 11 September 2026: 7 keadaan × viewport 1440/390px; pemeriksaan
markup/tautan, tidak ada resource jaringan pada halaman, lebar dokumen, target
sentuh, keyboard `<details>`, serta kompilasi dua alat preview lulus. Kontras teks
sekunder terhadap krem 7,07:1; teal tua terhadap putih 4,95:1. Screenshot sintetis
utama ditinjau visual; tidak ditemukan clipping/overlap. Ini bukan audit WCAG penuh.
Bukti command, checksum, dan screenshot berada di folder mockup lokal (opsional).
**Residual Gap: 0 untuk scope dokumen + mockup.** Keputusan bagian 9 masih menjadi
blocker implementasi/integrasi personal, bukan dianggap selesai oleh verifikasi ini.

Untuk **implementasi berikutnya** (belum dijalankan oleh pekerjaan ini):

- Scoped test kontrak katalog/soal aktual, negatif kepemilikan dan permukaan murid,
  persetujuan, sumber konteks, invalidasi, dan pemisahan antar-anak/akun.
- Uji memori lintas chat: relevansi, sumber, koreksi/hapus, nonaktif, mode tanpa
  memori, riwayat lama tidak diambil secara implisit, dan cache tidak membypass.
- Uji pemanggilan provider sintetis: hanya field yang disetujui; timeout, parsing
  rusak, prompt injection, dan konfigurasi hilang tidak membuka akses/tindakan.
- Uji usulan → validasi → konfirmasi, konteks usang, retry/idempotensi, tidak ada
  perubahan bukti/siklus dari percakapan.
- Mutation guard baru keamanan/data/pedagogis di salinan terisolasi, lalu preset
  Kritis lengkap, visual sintetis, dan CI build sebelum deploy.

Tidak ada klaim terimplementasi, ter-deploy, atau terverifikasi secara runtime
hanya karena keadaan tersebut tampak pada mockup.

## 11. Investigasi integrasi — 11 September 2026

Tahap lanjutan masih investigasi dan perencanaan, belum implementasi aplikasi.
Plan kerja lengkap lokal: `plan/2026-09-11-pendamping-implementation.md`;
plan tidak diperlukan untuk build dan tidak mengubah kesepakatan bagian 9.

### Hasil inventaris sumber

Probe tanpa DB/network menemukan **10 topik asli, 93 template unik**, serta
satu paket campuran. Seluruh template memiliki kartu konsep; pada 196 pasangan
template × level yang masuk komposisi, sampel seed 0 memiliki teks, kunci,
malrule, dan pembahasan tidak kosong. Ini inventaris source pada tanggal tersebut,
bukan klaim seluruh variasi sudah diaudit atau seluruh materi kompetisi tercakup.

Sumber implementasi terpetakan:

- `mesin/topics.py:322` dan `:350`: daftar topik/registry; katalog tidak perlu
  disalin ke bank pengetahuan manual. Label kemampuan/variasi tetap perlu
  metadata terverifikasi, bukan tebakan nama template atau satu sampel soal.
- `mesin/question_views.py:186` dan `:205`: pembaca penyajian snapshot/soal;
  pembahasan soal tertentu harus mengikuti instance yang dibuka.
- `mesin/database.py:828`: query sesi juga mengambil jawaban dan diagnosis.
  Jangan menjadikannya payload AI utuh; perlu query minimal berizin.
- `mesin/llm.py:106` dan `:356`: klien urllib OpenAI-compatible dengan default
  DeepSeek di source. Konfigurasi aktual/produksi tidak diperiksa. Chat akan
  punya konfigurasi/transport tersendiri; jangan otomatis memakai credential B2.

### Risiko yang harus ditutup sebelum integrasi personal

| Severity | Temuan integrasi | Tindakan yang direncanakan |
| --- | --- | --- |
| High | Akun/sesi berbasis username; akun guru pengganti memang dapat mengambil alih data belajar lama (`auth.py:362`, `sessions.py:73`) | Jangan mewariskan semantik itu ke curhatan. Chat/memori perlu identitas akun yang tidak dipakai ulang serta pengujian hapus/buat ulang dan sesi lama |
| High | Helper akses sesi/siswa memberi admin akses global (`web.py:248`, `:261`) | Gunakan izin chat/memori tersendiri; hak pengelolaan data murid bukan hak membaca curhatan keluarga |
| High | Kebijakan publik menjelaskan dua fitur AI, belum chat/memori (`landing.py:184`) | Pilih provider/retensi, kebijakan pengiriman, dan persetujuan chat sebelum menerima input personal; obrolan umum pun dapat berisi data personal |
| Medium | Bentuk snapshot, level legacy, dan isi query berbeda dari kebutuhan agent | Adapter minimal dan validasi ketat; jangan mengubah fallback legacy atau mengirim seluruh baris sesi |

Ini risiko penerapan fitur baru berdasarkan source, **bukan bukti kebocoran live**.

Urutan engineering: **katalog offline → identitas/storage berizin → chat umum →
memori lintas chat → konteks anak dan usulan tindakan**. Tahap katalog dapat
berjalan tanpa provider dan tanpa menerima curhatan, tetapi belum disebut chat
fungsional. Tahap berikutnya berhenti pada keputusan bagian 9 yang relevan.

Baseline lokal: **162 test existing lulus** (`test_topics`, `test_llm`,
`test_question_views`, `test_auth`, `test_sessions`, `test_learning_cycle_origin`,
`test_learning_cycle_routes`), dengan warning error, DB/sandi/sesi temp, dan
transport AI palsu. Probe katalog, kompilasi alat lokal, tautan/diff, serta palang
repo juga diperiksa. Tidak ada test chat/memori baru karena implementasinya belum
ada. Full suite, mutation, build, dan pemeriksaan produksi belum dijalankan pada
tahap investigasi ini; hasil scoped bukan pengganti gate Kritis implementasi.
