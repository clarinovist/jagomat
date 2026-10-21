# Jagomat — Spesifikasi ringkas

> Ringkasan produk ±1 halaman, bukan spesifikasi baru atau bukti deployment.
> Peta teknis: [context.md](context.md). Palang pengembangan: [CLAUDE.md](../CLAUDE.md).
> Jika berbeda, kontrak domain yang ditautkan di bawah tetap menjadi acuan.
> Wajib disinkronkan saat cakupan/kontrak/batas produk berubah, dalam perubahan
> yang sama; tetap ±1 halaman. Aturan: [sinkronisasi ringkasan](../CLAUDE.md#jaga-ringkasan-proyek-tetap-sinkron).

## Tujuan dan pengguna

Aplikasi web latihan matematika SD untuk persiapan OSN/SASMO yang membantu orang
tua menentukan **satu langkah belajar berikutnya**, bukan sekadar menambah soal.
Peran: **guru** = orang tua yang mengelola keluarganya; **murid** = anak yang
mengerjakan latihan; **admin** = pengelola lintas keluarga dengan batas akun khusus.

## Cakupan produk

- Panel pengelola memakai navigasi datar dengan ikon, badge jumlah item di Ringkasan,
  dan penanda perhatian di Operasional. Pengelola dapat memilih tampilan Sistem,
  Terang, atau Gelap per browser; Sistem mengikuti preferensi perangkat. Ringkasan
  memprioritaskan antrean satu baris per item (invoice/operasi, backup, keluarga,
  siswa, login; maks 50 baris + "dan N
  lainnya"); umur hanya tampil bila waktu awalnya tercatat. Tanpa penanggung jawab
  dan pencarian global (belum ada fiturnya). Aktivitas mengelompokkan sesi berurutan
  siswa/hari WIB tanpa mengubah bukti. Rute Perlu ditangani tetap hidup; pencarian
  identitas dan ekspor riset tetap POST privat. Label login tertaut tidak meniadakan
  kemungkinan akses akun lama melalui kecocokan nama.

- [Persetujuan awal](persetujuan-awal.md) menyatukan Terms, Privacy, dan pilihan
  [sensor internal](sensor-perbaikan.md) pada satu layar sejak daftar/kunjungan awal.
  Klik Setuju & aktifkan semua menyetujui alur, ringkasan konfirmasi pertama dan
  kategori chat; opsi penolakan/pilihan tetap tersedia tanpa mengurangi layanan inti.
  Tanpa teks mentah/provider analitik/backfill; detail30hari/izin90hari, dashboard
  ≥5keluarga per sel. Restart mempertahankan izin; restore mengganti epoch eksternal.
  Receipt berversi tetap ada saat sensor dicabut. KPI/provider AI tetap terpisah.
- Generator soal berparameter dan seed deterministik, lembar cetak, latihan daring,
  tinjauan hasil, diagnosis B/K/H/E/T/N, serta laporan perkembangan per anak.
  Teori-bilangan mencakup menghitung kelipatan/prima dalam rentang, sisa operasi,
  dan jumlah kelipatan; komposisi internal P4/P5 masing-masing 7/10 jenis, P6 tetap 7.
  Keragaman jenis bukan klaim penguasaan atau kesetaraan dengan kelas sekolah.
  [Bank kalimat offline](story-frames.md) tersedia lewat opt-in default nonaktif
  untuk tiga konsep bercerita; snapshot lama/kunci/diagnosis tetap. Paket cetak
  mandiri 6 tantangan KPK/pencacahan kelas5 memiliki solusi terpisah tanpa akun,
  penyimpanan jawaban, atau kaitan ke diagnosis/penguasaan aplikasi.
- Panel privat admin `/admin/riset` menyimpan wawancara eksploratif konsumen
  dalam database terpisah tanpa hubungan ke akun keluarga/siswa. Instrumen hybrid
  berversi memisahkan jawaban/kutipan responden, coding, dan catatan interviewer;
  jawaban boleh berstatus tidak dibahas/tidak tahu tanpa dipaksa lengkap. Hanya admin
  dengan sesi cookie hidup yang dapat membaca atau menulis. Kontak, nama, sekolah,
  foto, rekaman, dan jawaban soal anak tidak disimpan; consent, redaksi, penarikan,
  retensi 90 hari, matriks ber-denominator, serta ekspor anonim CSV/JSON dipagari.
  Hitungan studi bukan klaim populasi, PMF, atau keputusan launch otomatis.
- Pusat publik read-only `/riset` dan PDF unduhannya menyajikan business case
  peluang pasar/unit economics, strategi persaingan, psikologi konsumen, serta
  validasi GTM. Ia membedakan fakta, proxy, asumsi, hasil hitung, dan rekomendasi;
  bukan forecast, valuasi, klaim outcome, atau penawaran berbayar aktif. Laporan
  bootstrap `/riset/mulai` dan PDF-nya menambah action plan, biaya/SDM serta model
  cohort sintetis 12 bulan, bukan aktivasi penawaran atau instrumentasi baru. Laporan
  rinci `/riset/persaingan-bimbel-2026` tetap tersedia sebagai audit empat pemain
  terpilih. Semua permukaan riset memakai sumber publik, tidak membaca data
  keluarga, dan tidak menyatakan afiliasi atau market share.
- Siklus terpandu; latihan manual tetap tersedia tanpa otomatis mengubah putaran.
  Beranda menampilkan satu tugas/CTA, metadata sesi dan estimasi pengerjaan,
  instruksi, peta enam tahap terbuka, maksimal tiga sesi terkirim yang menunggu
  tinjauan (terlama dahulu; sesi dengan hasil 0 benar yang terlalu cepat diberi catatan
  "mungkin belum dikerjakan"), lalu tautan angka progres dari laporan yang sama. Kartu
  tinjau menampilkan lama menunggu sejak tanggal sesinya.
  Contoh, tanggal tunggu dan peringatan penting tetap terlihat; penjelasan panjang
  dilipat. Sesi belum dikirim tetap di Riwayat. Sementara form
  awal Pendampingan orang tua opsional berada di Latihan. Pilot aktif,
  pemulihan dan CTA reducer tetap di Beranda.
- Bantuan orang tua tanpa AI: satu disclosure kunci/pembahasan tiap soal tinjauan
  berada dekat soal dan jawaban anak, tertutup sampai dibuka. Sumber pembahasan
  existing tetap, bukan petunjuk buatan model atau hasil mandiri anak. Tiga kartu
  pra-tulis (bingung mulai, menolak bantuan, pendamping kesal) tersedia di Beranda
  profil dan setelah tinjauan sesi. FAQ kontekstual menjelaskan langkah Beranda,
  latihan dari hasil terbaru, serta arti status Perkembangan. Tanpa izin/kuota AI,
  input personalisasi, event baru atau perubahan penilaian.
- Pendamping AI inline untuk orang tua; konteks profil berizin memuat tahap/jumlah
  target dan maksimal tiga sesi perlu ditinjau menurut urutan aplikasi, bukan pilihan
  AI. Alias sesi dipetakan ke tautan lokal, bukan ID asli pada payload. Izin provider
  dan snapshot sumber tetap terpisah; konteks berubah menjadi hanya-baca. Panel
  overlay/sheet menjaga lebar konten dan tab asal; contoh hanya mengisi draf, tidak
  mengirim otomatis. Usulan latihan tetap memerlukan tinjauan dan konfirmasi, bukan
  perubahan diagnosis atau bukti belajar otomatis. Kelola data Pendamping dari
  Akun tersedia dengan sesi guru meski provider/fitur kirim nonaktif atau kuota
  habis: tinjau lalu hapus satu chat, atau cabut izin AI beserta izin sumber lama.
  Metadata/hapus tetap tersedia pasca-cabut; transkrip tetap mengikuti izin baca.
  Hapus memberi tombstone dan jadwal purge, bukan jaminan hapus fisik seketika;
  memori terkonfirmasi, sesi hasil, backup dan provider memiliki aturan terpisah.
- Akun keluarga dan pengelolaan anak: nama login terlihat, penghapusan profil
  ber-riwayat atau bukti pendaftaran ditahan, dan pilihan data tambahan dibedakan
  dari izin yang masih aktif. Tambah anak mengikuti policy awal tanpa checkbox
  persetujuan berulang atau mengaktifkan kembali analitik. Pemulihan akun melalui
  bantuan tanpa kontak tersimpan.
  Soft launch saat ini adalah akses awal
  nonkomersial; Jago/Jago Pro sedang disiapkan dan pendaftaran tidak mengaktifkan
  paket, masa coba, promo, atau pembayaran. Domain langganan/pembayaran tetap ada
  tetapi tidak dipromosikan sebagai penawaran aktif. Dukungan publik
  memakai satu konfigurasi privat untuk WhatsApp Business, jam Senin–Jumat
  09.00–17.00 WIB, respons awal maksimal 1 hari kerja, serta status/penyelesaian
  awal maksimal 3 hari kerja. Kanal ini tidak menambah kontak pada profil keluarga,
  tidak mengirim pesan otomatis, dan bukan bukti kepemilikan akun. Reset hanya
  setelah verifikasi independen; bila tidak tersedia, reset ditahan. Pendaftaran
  membuat profil anak pertama tanpa meminta variasi soal; kelas sekolah opsional,
  lalu mengarahkan orang tua ke **Beranda** untuk menyiapkan latihan awal.
  Nilai pertama ditargetkan dalam 48 jam: latihan awal pertama selesai, hasilnya diperiksa
  dan dikonfirmasi, lalu satu langkah lanjutan tampil. Ini baru catatan awal, bukan diagnosis,
  bagian bantuan final, atau klaim penguasaan. Tautan satu sesi dibuat dan langsung disalin dari layar aktif pada browser yang
  mendukung, dengan form native sebagai fallback; masa berlaku dan pencabutan tetap
  dipagari. Saat menyiapkan latihan, orang tua cukup memilih topik, jumlah, format,
  dan mode; Jagomat memilih satu konfigurasi internal yang didukung topik, sedangkan
  seed mengganti parameter dan susunan model di dalam konfigurasi itu. P3–P6 tetap
  disimpan sebagai konteks historis, bukan kelas atau ukuran kemampuan. Anak baru
  belum berpartisipasi sampai pemetaan pertama disiapkan; saat itu sistem memakai
  konteks fondasi internal P3 secara atomik, tanpa menebak dari kelas sekolah. Ruang
  anak memiliki empat tujuan berurutan: **Beranda**, **Latihan**, **Riwayat**,
  dan **Perkembangan**. URL profil tanpa query serta `?section=rencana` membuka
  Beranda; latihan manual berada di `?section=latihan`, arsip operasional tunggal
  di `?section=riwayat`, dan proyeksi bukti di `?section=perkembangan` sebagai satu
  tab dengan saklar **Ringkasan / Per materi** server-side. Riwayat putaran
  dilipat di bawah Per materi bersama catatan putaran aktif dan histori variasi;
  tautan Perjalanan lama tetap membuka riwayat itu. Bukti per konteks dan cara menilai
  dilipat dalam satu disclosure tertutup per materi, bukan dihapus.
  Anchor lama memiliki tautan penerus. Header orang tua di ruang anak memakai
  menu akun ringkas, avatar inisial, nama dan kelas sebagai teks terpisah, serta
  tab sticky; topbar dan identitas tetap ikut scroll. Pemicu Pendamping berupa
  pill melayang “Tanya” yang tetap membawa konteks tab aktif. Kelas hanya tampil bila
  metadata opsionalnya terisi; nama akun diformat untuk tampilan tanpa mengubah login. Deep link `/laporan/<id>` lama
  dialihkan setelah guard kepemilikan. Judul progres menampilkan jumlah target
  menunjukkan pemahaman bila ada, atau sedang dipelajari bila belum ada; status
  reducer dan denominator tidak berubah.
  Aksi utama ruang anak memakai teal; label tinjauan Perlu ditinjau, Draf
  tersimpan, atau ✓ Selesai mengikuti konfirmasi aktif, bukan penguasaan.
  Konfirmasi yang tidak lagi aktif tetap meminta konfirmasi ulang.
  Aktivitas memakai Semua (bawaan), 7 hari terakhir, atau tanggal pilihan; empat
  angka netral bukan persentase pemahaman. Preset minggu/bulan lama tetap terbaca.
  Riwayat menampilkan satu status/aksi per sesi dan strip tinjauan terlama; filter
  tambahan/paging tetap tersedia, pengelolaan tautan di halaman sesi. Latihan memakai
  satu form aktif dengan tiga mode, fallback pemilih GET, dan skrip lokal berhash
  CSP untuk mode/disabled Gabungan minimal dua topik. Server tetap memvalidasi;
  Pendamping tidak menerima draf sebagai data AI. Detail paket mengikuti kontraknya.

## Kontrak belajar utama

**Pemetaan → fokus → intervensi/contoh → latihan terbimbing → penguatan mandiri →
evaluasi berjeda → checkpoint → maju atau eskalasi.**

- Bukti sah berupa snapshot outcome **append-only**, setelah tinjauan dan
  konfirmasi eksplisit guru. `direview` dan `kode_final` mutable bukan bukti sendiri.
  Tinjauan sesi diproyeksikan exception-first sebagai **Perlu diperiksa**,
  **Tanyakan cara anak**, atau **Tinjauan tercatat**; kelompok terakhir bukan
  pengesahan dan tetap disahkan bersama saat Konfirmasi hasil sesi. Kartu aktif
  menampilkan pertanyaan/jawaban, empat pilihan pemahaman, dan penilaian langsung;
  dua disclosure datar (catatan tambahan dan kunci) tertutup tanpa menghilangkan
  input saat menyimpan seluruh sesi. Accordion tidak menilai atau mengirim otomatis;
  lewati memerlukan konfirmasi lokal, hitungan pekerjaan tetap proyeksi server.
  Pada kategori Tanyakan cara anak, guru dapat membuka **Minta foto cara** ke
  Lampiran bila upload tersedia; simpan draf sebelum pindah. Tidak mengirim permintaan
  otomatis atau membuka upload lewat tautan anak. Konfirmasi foto melipat kartu tanpa
  penanda masalah dengan preview bacaan awal; kosong/ragu/berbeda dari jawaban lama
  dan PG tetap terbuka. Semua field tetap terkirim; AI belum diverifikasi manusia,
  Terapkan tetap eksplisit dan bukan konfirmasi bukti belajar.
  Koreksi menginvalidasi bukti aktif; snapshot lama dan provenance tetap terjaga.
- Maksimal dua fokus per putaran, dengan kunci
  `(template_id, kode_intervensi, malrule_id)`. Terbimbing/penguatan tidak menambah
  kelemahan. Sesi manual, usang, atau beda level tidak menghalangi CTA utama.
- B: baca; K: konsep; H: hitung; E: tulis akhir; N: menebak; T: belum mengenal.
  T memerlukan pengenalan lalu probe, bukan langsung remedial.
- Jawaban benar belum cukup tanpa bisa menjelaskan. Evaluasi minimal empat probe
  per fokus; checkpoint setiap 28 hari minimal tiga probe per fokus. Gagal kedua
  atau tidak ada pendekatan alternatif → eskalasi. Detail kelulusan ada di kontrak.
- Pilihan ganda manual adalah riwayat latihan, bukan bukti pemetaan/penguasaan.
  Form foto disembunyikan pada PG tanpa lampiran; lampiran lama dan sesi isian
  tetap didukung, tanpa mengubah handler atau batas akses.

## Batas yang tidak boleh dilanggar

- Guru hanya mengakses data sendiri; resource asing → **404 dengan body identik**,
  tanpa efek samping. Murid tidak menerima kunci, malrule, diagnosis, atau laporan.
- Admin boleh mengelola data murid semua keluarga, tetapi tidak boleh mengubah
  akun/sandi sesama pengelola. Sesi berbukti tidak boleh dihapus permanen.
- Data anak, kredensial, sesi, data wawancara konsumen, dan cadangan tidak masuk
  Git/log/fixture. Tes memakai
  data sintetis; pengiriman ke AI hanya melalui alur dan izin produk yang disetujui.
  Tidak menyimpan email/telepon pengguna. Nomor WhatsApp Business adalah konfigurasi
  operasi Jagomat, bukan kontak keluarga; URL publik tidak membawa nama akun/anak.
- Penghapusan seluruh keluarga memakai primitive domain teruji yang memerlukan
  verifikasi independen, preview exact, backup coherent empat DB + auth, dan cutover
  terkontrol; tidak boleh dirangkai dari penghapusan login guru. Data aktif dihapus,
  identitas pada arsip diputus bila kontrak mengizinkan, sementara bukti/ledger
  append-only tetap dipertahankan.
- [Koreksi katalog](catalog-corrections.md) memakai identitas konten baru tanpa
  mengoreksi riwayat; writer perbaikan masih opt-in/nonaktif bawaan dan belum dirilis.
  Soal umur baru memakai dua orang tanpa hubungan keluarga, bukan menaikkan rentang
  angka agar usia ayah masuk akal. Tinjauan manusia konten berubah serta gate
  recovery exact tetap wajib.
- Kunci dan diagnosis tidak ditentukan LLM. Tidak menjanjikan kesiapan juara atau
  menyamakan progres target Jagomat dengan penguasaan seluruh kurikulum sekolah.

## Acuan dan keputusan produk

[Siklus belajar](siklus-belajar-terpandu.md) · [Pilihan ganda](multiple-choice.md) ·
[Pendamping](pendamping-runtime.md) · [Paket](subscription-packages.md) ·
[Pembayaran](pembayaran-produksi.md) · [Operasi dukungan](support-operations.md).
Pekerjaan berstatus **DIBATALKAN** pada [indeks keputusan](README.md) bukan backlog
aktif; hanya dibuka kembali melalui keputusan baru pengguna. Perubahan kurikulum,
jenis soal, atau cakupan produk memerlukan keputusan pengguna.
