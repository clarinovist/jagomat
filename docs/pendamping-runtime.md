# Kontrak runtime Pendamping

Dokumen ini menjelaskan kontrak **source**, bukan bukti deployment atau penerimaan
redesign. [Spesifikasi Pendamping](pendamping-jagomat.md) menyimpan rancangan
awal; bagian UI inline di dokumen ini menjelaskan kontrak implementasi sekarang;
[palang proyek](../CLAUDE.md) dan [siklus belajar](siklus-belajar-terpandu.md)
tetap berlaku. Seluruh verifikasi lokal menggunakan DB, akun, dan provider sintetis.

## Status saat ini — 22 Oktober 2026

Panel inline/konteks dan kendali data existing tersedia serta tercakup
[rilis ccb8906](production-release.md#deploy-seluruh-commit-terbaru--22-oktober-2026).
Hapus/cabut dan pengelolaan saat provider mati **sudah dibuka kembali dan selesai**.
Eksperimen prompt baru tetap ditahan setelah dua batch; editor memori lebih luas
dan penerimaan perangkat yang dibatalkan tidak ikut dibuka. Status per scope di
[status proyek](status-proyek.md); bagian bertanggal di bawah mempertahankan histori.

## Status pengembangan lanjutan — 18 September 2026

**DIBATALKAN (cancelled)** atas permintaan pengguna: UI hapus chat/cabut izin,
pengelolaan saat provider tidak dikonfigurasi, perbaikan pesan editor memori,
evaluasi lanjutan mutu penjelasan matematika, serta walkthrough pengguna,
Safari/keyboard HP fisik dan pengujian aksesibilitas menyeluruh. Bukan backlog
aktif; pembukaan kembali memerlukan keputusan baru pengguna. Lihat
[keputusan pembatalan](README.md#keputusan-pembatalan-pengembangan--18-september-2026).

Kontrak runtime dan fitur yang sudah ada tetap berlaku. Pembatalan pekerjaan
verifikasi tidak berarti sudah diuji/lulus, tidak menghapus keterbatasan mutu,
dan bukan izin memperluas akses atau mengubah produksi.

### Evaluasi kandidat sempit — 20 Oktober 2026

Pengguna membuka kembali evaluasi sintetis Pendamping, maksimal 20 request,
plafon USD 0,10, tanpa retry otomatis. Untuk batch sintetis saja, pemeriksaan
matematika lokal dan review AI diterima; review manusia tetap diperlukan sebelum
pilot. Ketidakpastian retensi/pelatihan provider diterima hanya untuk materi
sintetis yang mungkin disimpan/digunakan provider, bukan izin ekspor data keluarga.

Dua kegunaan diuji: petunjuk satu soal resmi dan percakapan pendampingan. Harness
terisolasi memakai prompt kandidat dua field, tanpa katalog/memori, bukan runtime
aktif empat field. Source/kunci generator, skenario, histori dan akun konteks
semuanya sintetis. Parameter: `deepseek-flash`, temperature 0,4, thinking disabled,
output maksimum 1.200 token. Tidak mengubah prompt/rubrik di tengah batch.

Hasil **20/20 request selesai, 20/20 parser sah, 0 retry, 0 hard fail**, tetapi
**kandidat belum lulus rubrik mutu**. Kejelasan dan langkah berikutnya sama-sama
memenuhi pada 18/20; kelompok soal 7/9 (syarat 8/9), percakapan 5/5, batas 6/6.
Akurasi/sumber penuh 16/20 (syarat 20/20), konteks penuh 20/20. Kekurangan: petunjuk
pecahan terlalu umum (S02), keliling mengasumsikan rumus sudah diketahui (S05),
penamaan area luas tanpa diagram ambigu (S06), definisi status produk kurang
presisi (S17). Skor 1 adalah kurang lengkap/ambigu, bukan seluruhnya salah hitung.
Penilaian oleh koordinator AI sesuai gate yang disetujui, bukan penerimaan manusia.

Usage provider 18.046 input/1.844 output token; estimasi konservatif tarif peak
cache-miss **USD 0,007635**, bukan invoice. Median respons 1.357 ms, rentang
1.012–1.796 ms, tidak termasuk pengambilan credential/review. Bukan benchmark umum.
Artefak sintetis, ledger eksperimen dan manifest disimpan privat di referensi
lokal; tidak ada data keluarga, credential, atau raw output dimasukkan Git.

Keputusan: **tahan implementasi luas dan pilot pada kandidat ini**. Izin
penyederhanaan/kendali hapus-cabut berlaku bila uji awal lulus; gerbang gagal tidak
mengizinkan implementasi otomatis. Arah perbaikan terbatas: petunjuk konkret dan
terminologi tepat tanpa data tambahan. Retest memerlukan penetapan scope/budget
baru, tidak memakai ulang ledger untuk melewati batas 20 request. P3–P7 belum
selesai, tidak ada rilis atau klaim manfaat orang tua/PMF. Runtime yang sudah ada
tetap berlaku. [Indeks keputusan](README.md#pembukaan-kembali-pendamping--20-oktober-2026).

### Retest perbaikan prompt 01 — 20 Oktober 2026

Satu retest berizin menambah maksimal 20 request/plafon USD 0,10 tanpa retry.
Hanya system prompt diubah: petunjuk konkret, konsep keliling, batas diagram,
dan istilah status. Dataset, rubrik, model/parameter serta batas output tetap;
batch pertama dan ledger-nya dipertahankan. Preflight 20 body exact, 20 tes
transport/9 mutasi mock serta 3 tes loader credential tiruan lulus sebelum run.

Hasil **20/20 request selesai, parser 20/20, 0 retry/hard fail**, tetapi
**retest tetap belum lulus**. Akurasi/sumber penuh naik 16→19/20; konteks penuh
turun 20→17/20. Kejelasan+langkah penuh naik 18→20/20 (soal 9/9,
percakapan 5/5, batas 6/6). Syarat akurasi/konteks 2 pada semua kasus belum terpenuhi.

S02/S05/S06/S17 membaik. Regresi: S03 belum menjelaskan lima posisi putaran
secara eksplisit; S13/S15/S19 melebar ke status, latihan atau skrip yang tidak
diminta. Kekurangan konteks ini bukan insiden privasi atau aksi terlarang. S06
masih menambah penjelasan umum tetapi memenuhi rubrik semula; tidak ditambah
syarat gagal baru sesudah melihat hasil. Skor berasal dari koordinator AI dengan
rubrik yang sama, bukan penerimaan manusia atau bukti generalisasi.

Usage retest 26.806 input/2.236 output token; estimasi peak cache-miss
**USD 0,010735**, bukan invoice. Median respons 1.250 ms, rentang 812–1.479 ms,
tanpa waktu SSH/review. Total dua batch 40 request, estimasi peak USD 0,018370.
Jumlah request kedua batch sudah habis; sisa estimasi biaya bukan izin putaran
ketiga. Tidak ada perubahan source aplikasi, konfigurasi atau DB keluarga.

Keputusan: **hentikan iterasi otomatis; jangan lanjutkan P3–P6 atau pilot P7
pada kandidat ini**. Prioritaskan pembanding non-AI atau ajukan keputusan scope
AI lebih sempit, bukan menurunkan rubrik/menambah data anak. Ini keputusan pada
gerbang evaluasi, bukan klaim seluruh fase selesai atau bahwa AI tak mungkin
berguna. Penerimaan manusia, perangkat dan walkthrough belum dilakukan; tidak
ada rilis dari eksperimen ini.

### Kendali data existing — 21 Oktober 2026

Paket kendali data dibuka kembali secara eksplisit dan **dipisahkan dari syarat
kelulusan eksperimen P2**. Bukan penghentian fitur memori/usulan atau rilis prompt
kandidat. Source menyediakan `/pendamping/kelola` dari Akun dan tautan tab baru
pada panel AI; tidak menavigasikan form host yang masih berisi draf.

- Principal cookie guru terbaru wajib; admin/murid/Basic tidak mendapat akses.
  Halaman tersedia walau `PENDAMPING_AKTIF=0`, provider belum dikonfigurasi atau
  kuota habis. GET hanya metadata dan owner sumber, tidak transkrip/payload AI,
  tidak membuat/migrasikan DB yang belum ada. DB rusak gagal dengan pesan generik.
- Hapus satu chat melalui GET tinjauan lalu POST versi+konfirmasi dan pemeriksaan
  asal request. Tombstone menghilangkan akses aktif; `purge_setelah=sekarang`
  dijadwalkan untuk janitor existing, bukan purge massal dalam endpoint. Memori
  terkonfirmasi, sesi hasil usulan serta marker deduplikasi tidak ikut dihapus;
  purge memutus provenance memori, menghapus draft/chat/pesan sesuai kontrak lama.
- Cabut izin melalui tinjauan/POST versi mencabut seluruh grant `chat_umum` akun
  dan semua snapshot konteks secara atomik. Izin ulang provider tidak menghidupkan
  snapshot lama. Ini tindakan eksplisit pemilik satu akun, bukan reset lintas akun.
- Setelah cabut, metadata dan hapus tetap tersedia; akses transkrip tidak diperluas
  melewati coupling consent existing. Tidak ada janji chat lama otomatis dapat
  dilanjutkan. Izin sensor tetap terpisah; kategori chat dibersihkan oleh rekonsiliasi
  existing/retensi, bukan atomik lintas DB. Backup maksimal30hari dan provider terpisah.
- Pagar sebelum client memeriksa ulang versi izin/chat/konteks setelah admission AI
  dapat menunggu; response terlambat tetap melewati guard simpan existing. Tidak
  menahan lock DB sepanjang jaringan. Request yang sudah melewati pemeriksaan dan
  terkirim tidak dapat ditarik kembali; jangan menjanjikan pembatalan retroaktif.

Tidak ada schema/migration/backfill, penghapusan massal, perubahan kuota atau
akses admin tambahan. Source/test bukan bukti deployment; paket ini belum
memasang perubahan ke produksi atau mengesahkan walkthrough/perangkat manusia.

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

### Ringkasan profil v2 — 20 Oktober 2026

- Konteks otomatis profil memakai allow-list: jenis, level/konteks variasi, tahap
  netral, waktu tersedia, posisi enam tahap, jumlah target (dipelajari/terbukti/
  perlu cek/belum dinilai), dan maksimal tiga sesi perlu ditinjau dengan alias serta
  jumlah soal. Tidak membawa nama, ID DB, jawaban/catatan/diagnosis atau URL lokal.
  Teks chat yang diketik tetap dikirim sesuai izin provider; ini bukan klaim seluruh
  request bebas data pribadi. Konteks satu soal/sesi tidak diperluas.
- Urutan memakai predicate konfirmasi aktif yang sama dengan Riwayat/Beranda:
  sesi sudah dikirim, tidak dibatalkan, belum memiliki konfirmasi aktif, lalu
  tanggal dibuat dan ID menaik. Bukan urutan waktu pengiriman atau pilihan model.
- Satu snapshot baca konsisten menghasilkan payload dan fingerprint kontrak v2;
  seluruh fakta outbound serta pemetaan alias→ID lokal ikut fingerprint. Perubahan
  status, progres atau binding membuat chat lama hanya-baca. Izin lama tidak dapat
  mengesahkan payload baru; kategori `ringkasan_netral` tetap tanpa migrasi schema.
- UI menampilkan tautan dari binding yang masih sah, tidak dari keluaran model.
  Histori usang tidak memakai pemetaan alias terbaru dan menawarkan tinjauan izin
  baru. AI diarahkan menjelaskan fakta, bukan mengarang nomor/tautan/urutan.

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
posisi suku dan siklus. Evaluasi lanjutan kualitas penjelasan **dibatalkan**
pada 18 September 2026; keterbatasan mutu tersebut tetap tercatat.
Tidak ada alasan menaikkan budget, timeout, atau menerima JSON parsial.

Total enam request: 100.547 input dan 2.033 output token; estimasi biaya memakai
usage cache dan tarif peak saat pemeriksaan sekitar USD 0,0084, bukan audit
invoice. Credential tetap dalam proses server; eksperimen tidak membuka DB atau
mengubah konfigurasi layanan. Artefak sintetis lokal tidak menjadi dependensi test.
Acuan provider: [thinking mode](https://api-docs.deepseek.com/guides/thinking_mode)
dan [tarif](https://api-docs.deepseek.com/quick_start/pricing), diakses 15 September
2026. Sampel kecil ini tidak membuktikan seluruh percakapan bebas truncation.

## Target kuota paket — keputusan 27 September 2026

[Paket Jago/Jago Pro v2](subscription-packages.md#4-pembeda-fitur-dan-kuota)
menetapkan trial10balasan+2foto total, Jago tanpa Pendamping/fotoAI, dan
Pro50balasan+5foto per bulan layanan bersama seluruh profil. Tahunan tetap diisi
ulang per bulan, bukan12kali sekaligus. Ini **belum enforcement paket** pada runtime
existing: pagu biaya/limit request AI bukan pengganti kuota pelanggan.

Integrasi harus mempertahankan persetujuan, kepemilikan, operasi durable dan
penanganan unknown/replay. Kuota dicadangkan atomik sebelum jaringan, hasil sukses
hanya sekali mengonsumsi jatah; unknown tidak membolehkan panggilan baru sampai
rekonsiliasi. Habis kuota AI tidak mematikan fitur belajar inti. AI tambahan tidak
boleh melewati pagu provider/global atau membuka kembali pengembangan yang dibatalkan.

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
editor yang lebih membantu merupakan pekerjaan UX yang **dibatalkan** pada
18 September 2026, bukan fitur yang tersedia.

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
- Sebelum rollout/migrasi produksi: cadangan konsisten seluruh state durable,
  rehearsal idempoten, `integrity_check`/`foreign_key_check`, dan recovery siap.
  Dua DB pada rollout Pendamping awal bukan inventaris produksi admin5 sekarang;
  ikuti [runbook rilis](production-release.md) untuk bundle empat DB + auth.
  Push/deploy/SSH dalam scope mengikuti [izin tetap](../CLAUDE.md#izin-tetap--resource-lokal),
  tetapi commit atau izin tersebut bukan bukti gate teknis sudah lulus.

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

- Satu pemicu aktif (pill melayang Tanya pada profil) membuka overlay nonmodal
  360px desktop atau sheet maksimal 85dvh dengan Kembali pada HP, tanpa menyempitkan
  konten utama. Sumber tetap salah satu dari empat tab profil anak atau
  sesi/soal yang tepat. Pemicu sesi enhanced menawarkan ringkasan/nomor soal;
  bookmark konteks sesi/soal tetap langsung ke sumber kanoniknya.
- Consent provider dan konteks tetap terpisah. Form izin memakai judul sesuai
  tujuan host, penjelasan data/penerima DeepSeek, checkbox tidak dicentang, serta
  satu CTA Mulai percakapan. Mode aktif/tanpa memori dipilih sebelum mulai pada
  Pengaturan percakapan native, bukan dua tombol mulai. Tanpa memori bukan tanpa
  konteks atau riwayat; default dan mode chat immutable tetap. Draf koreksi/manual
  tidak masuk payload provider, storage Pendamping, cookie, atau URL.
- Kepala panel menampilkan sumber dan tab aktif; status hanya-baca tetap terlihat.
  Chat menggulir percakapan terpisah dari composer; respons baru diberi penanda AI
  dan log aksesibel, error tetap menjelaskan ketidakpastian tanpa retry otomatis.
  Contoh pertanyaan per tab hanya mengisi draf setelah klik, bukan mengirim.
  Label riwayat memakai jenis sumber dan waktu, bukan ID mentah atau cuplikan pesan.
  Persetujuan provider dipadatkan dengan rincian retensi tetap tersedia; checkbox
  provider/konteks dan mode tanpa memori tetap eksplisit. Tentang bantuan AI di footer.
- History dibatasi exact-resource dan seluruh aksi dalam form koreksi memakai
  submit POST yang membawa kembali draf. Mode tanpa memori tetap menyimpan history.
- Host yang mempunyai pemicu/panel memakai no-store/no-referrer/noindex/frame/CSP
  sejak respons awal, tanpa font/CDN/resource pihak ketiga. Skrip hanya diizinkan
  dengan hash tepat dan `connect-src 'self'`; consent serta host setelah Tutup
  tetap mendapat enhancement bila memiliki pemicu. Arsip tanpa panel tidak diberi
  skrip panel. Tindakan destruktif memakai fallback native dengan konsekuensi dan
  konfirmasi eksplisit, bukan handler JavaScript yang diblokir.
- POST native tetap penuh: draf manual/gabungan/remedial/koreksi dipulihkan request-local,
  termasuk pilihan kosong/checkbox tidak dicentang, tab, variasi, format dan jumlah.
  Validasi draf bukan izin membuat latihan; aturan submit pembuatan tidak berubah.
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

### Panel tanpa reload — persetujuan teknis 27 September 2026

- Enhancement terbatas pada buka/tutup, persetujuan provider/konteks, picker sumber,
  riwayat exact-resource, pemulihan fokus/scroll serta Kirim/Periksa status. Tambahan
  20 Oktober: contoh isi-draf tanpa kirim, Esc, dan pembaruan tautan empat tab
  profil agar membawa panel/chat pada resource anak sama. Navigasi tetap GET native,
  draf tidak masuk URL/storage; pesan yang belum terkirim diperingatkan sebelum
  pindah tab. Aksi
  memori/usulan tetap POST native. Semua fetch memakai allow-list path exact same-origin;
  tidak ada fetch navigasi global atau retry otomatis. Bila panel dibuka
  enhanced, submit native memori/usulan dilengkapi salinan field draf allow-list
  pada form panel untuk request lokal; form pekerjaan tidak diubah. Salinan bukan
  storage/autosave dan tidak disertakan dalam fetch/provider.
- Buka enhanced hanya mengambil hidden identitas di wrapper pemicu; pemicu sesi
  dengan action kanonik boleh body kosong. Aksi berikutnya hanya mengambil field
  panel + submitter yang diizinkan, bukan FormData seluruh pekerjaan. Server menolak
  draf pada request fragmen. Buka gagal tidak pernah memanggil submit form pekerjaan.
- Respons hanya mengganti panel, tidak form host. Binding host jenis/ID dan resource
  divalidasi per aksi: picker sesi boleh ke nomor yang dipilih dalam sesi sama;
  riwayat boleh mengganti chat hanya exact-resource; Kirim/Status wajib chat dan
  request asal yang sama. ID DOM/anchor bukan identitas keamanan.
- Close lokal hanya untuk panel yang dibuka enhanced pada dokumen yang sama:
  pemicu, fokus, dan scroll dipulihkan; late response diabaikan dan provider tidak
  dibatalkan. Bookmark/native tanpa state pembuka tetap POST untuk memulihkan host.
  Browser mengunci pengiriman ganda tetapi Tutup tetap dapat dijangkau.
- Pesan gagal dipertahankan di DOM selama halaman terbuka. Gangguan jaringan tidak
  memicu pengiriman ulang otomatis. Coba lagi memakai payload/request ID yang sama;
  bila server masih pending, lanjutkan dengan Periksa status tanpa provider kedua.
- Sesi berakhir/akses ditolak menampilkan penjelasan generik tanpa menempelkan
  respons ke panel. Pengguna diminta menyalin pesan sebelum masuk/membuka ulang.
- Balasan utuh tampil setelah validasi server, bukan token mentah model. Tidak
  memakai library, aset eksternal, localStorage, sessionStorage, atau cookie draf.
- Skrip berada di modul Python agar termasuk COPY wildcard image; izin CSP hanya
  hash tepat skrip tersebut, bukan `unsafe-inline` atau seluruh script same-origin.

**Pembaruan 21 Oktober:** hapus chat/cabut izin dan pengelolaan ketika provider mati
tersedia melalui [halaman kelola](#kendali-data-existing--21-oktober-2026), bukan
kontrol ganda di composer. Pembatalan 18 September tidak lagi berlaku untuk scope ini.
Picker keluarga langsung, editor parameter dan streaming tetap di luar cakupan,
bukan janji implementasi atau tombol palsu. Persetujuan JS panel bukan persetujuan provider/konteks, entitlement paket,
perubahan diagnosis/reducer, atau izin mengirim draf pekerjaan.

Wireframe/prototype lokal opsional, bukan dependensi aplikasi/build/test.
Pekerjaan walkthrough pengguna, Safari/keyboard HP fisik dan aksesibilitas
menyeluruh **dibatalkan**; penerimaannya tetap belum terverifikasi, bukan lulus.
Source tersedia, ter-deploy, dan berfungsi pada produksi bukan tiga klaim yang
dapat disamakan. Migrasi v3→v4 merupakan histori rollout, bukan langkah yang
harus diulang. Pemasangan berikutnya tetap perlu backup/recovery kompatibel dan
gate rilis yang sah; push tidak otomatis deploy selama job `pasang` tertutup.
