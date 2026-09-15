# Kontrak runtime Pendamping

Dokumen ini menjelaskan kontrak **source**, bukan bukti deployment atau penerimaan
redesign. Arah produk tetap [spesifikasi Pendamping](pendamping-jagomat.md);
[palang proyek](../CLAUDE.md) dan [siklus belajar](siklus-belajar-terpandu.md)
tetap berlaku. Seluruh verifikasi lokal menggunakan DB, akun, dan provider sintetis.

## Tinjauan dan pembuatan latihan

- GET tinjauan yang sah menerbitkan token acak, menyimpan **hash token** dan
  ikatan snapshot usulan di DB Pendamping. Ini bukti server menerbitkan tinjauan,
  bukan bukti manusia sudah membaca atau memahami layar.
- Ikatan mencakup generasi akun, pemilik, usulan/payload/hash/versi, pesan sumber,
  chat/versinya, serta consent dan konteks yang ditinjau. POST tidak boleh
  menerbitkan tinjauan sendiri. Token palsu atau milik tinjauan lain ditolak.
- Tinjauan berlaku 30 menit untuk membuat latihan. Membuka tinjauan baru mengganti
  token lama; tab lama mendapat konflik. Refresh tidak mengesahkan usulan usang.
- Konfirmasi menggunakan transaksi privat, lalu transaksi data belajar. Tidak
  ada panggilan provider saat transaksi ditahan. Generator, penguncian sesi,
  dan catatan eksekusi berada dalam transaksi data belajar yang sama.
- Catatan eksekusi `eksekusi_pendamping` mengikat identitas usulan, bukan isi
  payload saja. Hasil commit data belajar dapat ditemukan kembali apabila proses
  terhenti sebelum hasil tersimpan di DB Pendamping. Retry tidak meregenerasi.
- Lookup hasil tetap memeriksa chat, izin, serta kepemilikan sumber dan sesi
  hasil. Sumber/hasil asing atau hilang yang tidak boleh diakses mendapat 404
  generik; hasil dibatalkan/dihapus tidak dibuat ulang. Hasil yang membuat
  ringkasan anak usang dapat ditemukan tanpa menuntut ringkasan lama tetap segar.
- Latihan tetap `bebas`, tanpa putaran atau konfirmasi bukti belajar. Tidak ada
  penulisan diagnosis, fokus, atau kejadian siklus oleh konfirmasi Pendamping.

## Request chat dan consent konteks

- Reservasi chat awal dan operasi dilakukan atomik. Submit ulang request yang
  sama menuju chat asal; bukan membuat chat kosong tambahan.
- Request terikat akun, chat, dan teks pesan asal. Hasil tidak boleh dipinjam oleh
  chat lain. Request pending/gagal tidak otomatis memanggil provider ulang.
- Versi consent konteks adalah versi yang melekat pada **resource chat itu**,
  bukan versi izin terakhir seluruh akun. Memilih resource lain tidak membuat
  chat lama yang masih sah gagal. Resource/izin chat sendiri tetap divalidasi
  sebelum dan sesudah pemanggilan provider.
- Pemulihan request bukan izin menghidupkan chat yang dihapus atau konteks yang
  dicabut. Mode tanpa memori tetap immutable.

## Kegagalan balasan dan metadata teknis

- Callback Pendamping memvalidasi kontrak balasan sebelum ledger AI berstatus
  `selesai`. Status ini bukan bukti chat tersimpan: revalidasi izin, konteks, dan
  transaksi penyimpanan Pendamping tetap sesudahnya.
- Transport Pendamping mengirim `thinking: {type: disabled}` secara eksplisit.
  Model DeepSeek mengaktifkan penalaran secara bawaan, sementara budget keluaran
  Pendamping tetap 1.200 token dan timeout 25 detik. Mode ini hanya untuk chat
  Pendamping; cerita/lampiran, reservasi biaya, dan batas penggunaan tidak berubah.
- JSON sah saja belum cukup. Jawaban, draft memori, usulan latihan, dan boolean
  klarifikasi tetap divalidasi ketat sebagai satu paket; field invalid tidak
  dibuang atau dinormalisasi diam-diam. Balasan terpotong (`finish_reason=length`)
  ditolak, meskipun potongannya kebetulan bisa dibaca sebagai JSON.
- Kategori teknis membedakan timeout/koneksi/status provider, JSON/terpotong,
  serta bagian kontrak balasan. Ledger memakai kolom kategori existing; tidak ada
  migrasi atau salinan isi chat. Kegagalan setelah outbound tetap `tak_pasti`
  untuk debit konservatif, bukan refund atau klaim biaya provider terukur.
- Log Pendamping hanya satu kategori dari allow-list, tanpa isi exception,
  traceback, prompt/balasan, credential, atau identitas keluarga/request.
  Kegagalan admission sebelum reservasi tidak membuat ledger baru; kategori
  aman tetap tersedia di log. Fitur AI lain mempertahankan kategori existing.
- Pesan UI membedakan kuota/pengaturan, timeout, pembatasan provider, format rusak,
  dan balasan terpotong. Galat ada setelah transkrip, dekat area menulis, tanpa
  pesan gagal ganda. Browser menyebut **balasan belum tersedia**, bukan mengklaim
  pesan pasti belum sampai server. Tidak ada retry otomatis, kenaikan timeout,
  pelemahan guard, atau pengiriman ulang balasan gagal ke layanan AI.
- Saat membuka ulang, alasan teknis dibaca dari kategori ledger existing dengan
  koneksi read-only setelah pemeriksaan chat/resource/consent. Hanya operasi yang
  tepat, akun sama, fitur Pendamping, status gagal/tak pasti, dan kategori tertutup
  yang diterima. Storage hilang/rusak atau kategori tak tersedia menghasilkan
  pesan generik; GET tidak membuat storage atau memanggil provider. Status memakai
  operasi terbaru (termasuk sukses), dengan urutan deterministik pada detik sama,
  sehingga kegagalan lama tidak tertinggal setelah balasan baru sukses.
- Tidak ada kolom baru, salinan prompt/balasan gagal, atau klaim draft pesan
  bertahan setelah reload. Kategori yang dulu tidak dicatat tetap tidak diketahui.
  Perilaku ini merupakan
  kontrak source; kehadirannya di produksi harus diverifikasi sesudah deploy.

### Verifikasi transport sintetis — 15 September 2026

Enam panggilan berizin memakai katalog source dan pertanyaan buatan, tanpa data
anak/riwayat pengguna. Pengaturan lama default-thinking/1.200 token menghasilkan
`length`: 848 dari 1.200 token keluaran dipakai reasoning, JSON tidak lengkap.
Dengan thinking nonaktif, empat uji 1.200 token serta satu pembanding 2.000 token
selesai dan lolos validator penuh. Tiga uji terakhir menjalankan byte client patch
sebenarnya (dimuat sementara dalam proses uji, bukan dipasang ke aplikasi).

Skenario: bantuan pemetaan pola, contoh penjelasan pecahan dengan kertas, dan
usulan latihan manual dari template katalog. Respons patch menggunakan 127–200
output token dan 1,53–2,06 detik pada tiga sampel tersebut. Ini bukan benchmark
latensi umum atau jaminan mutu pedagogis: contoh pola masih mencampur istilah
posisi suku dan siklus, sehingga evaluasi kualitas penjelasan tetap follow-up.
Tidak ada alasan menaikkan budget, timeout, atau menerima JSON parsial.

Total enam request: 100.547 input dan 2.033 output token; estimasi biaya memakai
usage cache dan tarif peak saat pemeriksaan sekitar USD 0,0084, bukan audit
invoice. Credential tetap dalam proses server; eksperimen tidak membuka DB atau
mengubah konfigurasi layanan. Artefak sintetis lokal tidak menjadi dependensi test.
Acuan provider: [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode)
dan [tarif](https://api-docs.deepseek.com/quick_start/pricing), diakses 15 September
2026. Sampel kecil ini tidak membuktikan seluruh percakapan bebas truncation.

## Isi memori

Koreksi manual dan draft model menggunakan validator isi yang sama. Memori
hanya menerima bentuk preferensi cara menjawab yang dikenali, misalnya:

- “Jawab ringkas dengan contoh konkret.”
- “Gunakan kalimat pendek.”
- “Dengarkan dulu sebelum memberi saran.”

Ini **bukan penyimpanan bahasa alami bebas**. Frasa di luar bentuk yang didukung
(termasuk preferensi yang mungkin aman tetapi belum dikenali) ditolak, bukan
teksnya dibersihkan atau diparafrase diam-diam. Label/profil/curhatan/kontak/
credential, termasuk awalan preferensi diikuti cerita personal, tidak diterima.
Penggunaan nonaktif tetap mengizinkan koreksi manual; draft tidak otomatis
terkonfirmasi. Invalidasi versi dan kepemilikan tetap berlaku.

Batas patch: validator baru tidak melakukan audit/backfill memori warisan dan
bukan klaim filter chat umum mendeteksi seluruh kemungkinan data personal.
Penolakan koreksi masih mengikuti respons generik endpoint existing; penjelasan
editor yang lebih membantu termasuk pekerjaan UX yang belum diterima.

## Skema, retensi, dan recovery

- Skema privat versi 4 menambah `tinjauan_usulan` secara additive. Tabel ini
  menyimpan hash dan waktu, tidak menyimpan salinan teks chat; purge usulan
  menghapus tinjauannya melalui FK cascade.
- DB belajar menambah `eksekusi_pendamping`: hash identitas/tinjauan dan ID sesi,
  tanpa nama, teks pesan, jawaban, atau payload usulan. ID sesi sengaja bukan FK:
  menghapus sesi tidak boleh menghapus penanda bahwa usulan pernah dieksekusi.
- Penanda eksekusi tersebut bertahan setelah penghapusan sesi/chat untuk mencegah
  eksekusi kedua. Ini bukan bukti pedagogis dan tidak menjanjikan seluruh metadata
  turunan hilang bersama chat. Retensi teks chat tetap 180 hari sejak aktivitas
  terakhir, operasi pending/gagal 7 hari, dan cadangan maksimal 30 hari sesuai
  pengelola retensi existing.
- Jaminan deduplikasi tahan crash berlaku untuk eksekusi melalui runtime baru.
  Hasil lama yang masih memiliki pointer/kunci tetap diperiksa kepemilikannya.
  Crash pada runtime lama yang disusul penghapusan sesi sebelum catatan eksekusi
  tersedia tidak dapat direkonstruksi pasti; patch tidak mengarang riwayat atau
  melakukan backfill dari data keluarga.
- Jangan menurunkan `user_version` atau menghapus catatan eksekusi untuk
  memulihkan request. Usulan usang perlu usulan baru, bukan reaktivasi data lama.
- Rollback binary sebelum skema privat v4 **tidak otomatis kompatibel** karena
  aplikasi lama menolak versi lebih baru. Recovery harus memakai binary yang
  memahami v4 atau perbaikan maju; jangan memulihkan DB lama sebagai rollback UI.
- Sebelum rollout/migrasi produksi: izin baru, cadangan konsisten kedua DB,
  rehearsal idempoten, `integrity_check`/`foreign_key_check`, dan recovery siap.
  Commit lokal bukan izin push/deploy.

## Batas penerimaan

Guard/recovery diuji pada `test_assistant_review_guards.py`,
`test_assistant_retry_guards.py`, `test_assistant_memory_scope.py`, serta suite
existing Pendamping. Pengujian guard tidak menggantikan walkthrough orang tua.

## UI runtime server-side

Arah UI aktif kini menyatukan Pendamping pada profil anak dan pemeriksaan sesi.
Cutover tidak lagi menyediakan dokumen chat mandiri. `/pendamping` dan varian
`tanpa-memori` kembali ke ruang orang tua; POST pembuatan chat umum baru ditolak
tanpa efek samping. Bookmark chat/usulan/operasi berkonteks dipetakan ke host
inline setelah principal, sumber, dan izin divalidasi.

Source inline menyediakan:

- Slot bantuan di dalam kartu rencana, area latihan manual, pengantar sesi, atau
  satu kartu soal yang dipilih. Membuka bantuan dari form aktif memakai POST
  native supaya draf tetap request-local dan tidak disimpan otomatis.
- Consent provider dan konteks tetap terpisah. Draf koreksi/manual tidak masuk
  payload provider, storage Pendamping, cookie, atau URL.
- History dibatasi exact-resource dan seluruh aksi dalam form koreksi memakai
  submit POST yang membawa kembali draf. Mode tanpa memori tetap menyimpan history.
- Host assisted memakai header no-store/no-referrer/noindex/frame/CSP dan tidak
  meminta resource pihak ketiga. Hanya panel chat mendapat skrip berhash CSP
  dengan `connect-src 'self'` untuk Kirim/Periksa status tanpa reload. Halaman
  consent, arsip, dan respons Tutup tetap tanpa skrip chat. Respons Tutup tetap privat;
  tindakan destruktif memakai fallback native dengan konsekuensi dan konfirmasi
  eksplisit, bukan handler JavaScript yang diblokir. Draf dipulihkan dalam request
  yang sama.
- Chat umum lama tampil bersyarat sebagai **Arsip percakapan lama** di pengaturan
  akun: metadata maksimal 20 per halaman dan hanya transkrip yang dipilih yang
  dimuat. Arsip owner-only, readonly, tanpa composer, dan tidak dihubungkan ke
  anak berdasarkan tebakan. Bila kosong, disclosure/menu arsip tidak tampil.
- Hapus/abaikan memori inline selalu melewati tinjauan isi+versi, penjelasan bahwa
  chat sumber tetap ada dan backup maksimal 30 hari, checkbox eksplisit, serta
  pilihan batal. Tombol awal tidak membawa persetujuan tersembunyi.

Adapter warisan yang masih dipertahankan:

- Nama sumber tampil hanya pada proyeksi UI berizin, tidak digabung ke payload
  provider. Sumber soal kembali ke halaman sesi karena anchor input tidak
  tersedia pada seluruh state sesi. Batal/ganti sumber tidak memindahkan chat.
- Continuation login hanya allow-list rute Pendamping kanonik, hanya guru;
  setelah masuk resource tetap diperiksa kepemilikannya. Consent provider
  kembali ke penawaran sumber, tidak otomatis memberi consent konteks.
- Histori konteks usang hanya bisa dibaca bila sumber masih dimiliki dan izin
  baca masih sah; composer/draft/kandidat baru tidak tampil. Hasil yang pernah
  dibuat tetap bisa ditemukan melalui GET usulan yang memvalidasi pemilik.
  Consent dicabut atau resource asing bukan izin membuka histori.
- Pengaturan memori membedakan aktif kosong/berisi, nonaktif dan tanpa memori.
  Pengelolaan aktif dilakukan inline pada host sumber. Koreksi ditolak tidak
  memantulkan input. Hapus memerlukan persetujuan eksplisit dan tidak mengandalkan
  JavaScript.
- Label usulan dari topik/kartu resmi, parameter readonly, pesan sumber beranchor.
  GET hasil memakai hasil mesin sebenarnya; POST konfirmasi tetap terikat guard
  tinjauan dan catatan eksekusi yang sudah dijelaskan di atas.
- GET status operasi owner-scoped membedakan pending/gagal; pending tidak
  menawarkan pengiriman ulang otomatis. Status selesai menuju chat yang sama.
  Tidak ada streaming atau penyimpanan draf di storage browser.

### Kirim tanpa reload

- Progressive enhancement terbatas pada Kirim/Periksa status. POST form native
  tetap fallback jika JavaScript tidak tersedia; endpoint dan guard server sama.
- Browser menampilkan status menunggu dan mengunci pengiriman ganda. Respons HTML
  server hanya mengganti panel dengan ID host dan ID chat yang sama. Form host
  tidak diganti: perubahan latihan/koreksi selama menunggu tetap ada, tanpa autosave.
- Pesan gagal dipertahankan di DOM selama halaman terbuka. Gangguan jaringan tidak
  memicu pengiriman ulang otomatis. Coba lagi memakai payload/request ID yang sama;
  bila server masih pending, lanjutkan dengan Periksa status tanpa provider kedua.
- Sesi berakhir/akses ditolak menampilkan penjelasan generik tanpa menempelkan
  respons ke panel. Pengguna diminta menyalin pesan sebelum masuk/membuka ulang.
- Balasan utuh tampil setelah validasi server, bukan token mentah model. Tidak
  memakai library, aset eksternal, localStorage, sessionStorage, atau cookie draf.
- Skrip berada di modul Python agar termasuk COPY wildcard image; izin CSP hanya
  hash tepat skrip tersebut, bukan `unsafe-inline` atau seluruh script same-origin.

**Belum termasuk:** hapus chat/cabut izin melalui UI baru, pengelolaan saat
provider tidak dikonfigurasi, picker keluarga langsung, editor parameter,
streaming atau interaksi JS di luar Kirim/Periksa status. Semua tetap paket
terpisah, bukan tombol palsu.

Wireframe/prototype lokal opsional, bukan dependensi aplikasi/build/test.
Walkthrough user, Safari/keyboard HP fisik dan aksesibilitas menyeluruh tetap
perlu verifikasi terpisah. Source tersedia, ter-deploy, dan berfungsi pada
produksi bukan tiga klaim yang dapat disamakan. Migrasi v3→v4 dari commit
prasyarat harus memenuhi backup/recovery kompatibel sebelum push otomatis deploy.
