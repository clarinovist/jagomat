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

- Generator soal berparameter dan seed deterministik, lembar cetak, latihan daring,
  tinjauan hasil, diagnosis B/K/H/E/T/N, serta laporan perkembangan per anak.
- Siklus terpandu; latihan manual tetap tersedia tanpa otomatis mengubah putaran.
- Pendamping AI inline untuk orang tua; usulan latihan memerlukan tinjauan dan
  konfirmasi, bukan perubahan diagnosis atau bukti belajar otomatis.
- Akun keluarga dan pengelolaan murid. Soft launch saat ini adalah akses awal
  nonkomersial; Jago/Jago Pro sedang disiapkan dan pendaftaran tidak mengaktifkan
  paket, masa coba, promo, atau pembayaran. Domain langganan/pembayaran tetap ada
  tetapi tidak dipromosikan sebagai penawaran aktif. Dukungan publik
  memakai satu konfigurasi privat untuk WhatsApp Business, jam Senin–Jumat
  09.00–17.00 WIB, respons awal maksimal 1 hari kerja, serta status/penyelesaian
  awal maksimal 3 hari kerja. Kanal ini tidak menambah kontak pada profil keluarga,
  tidak mengirim pesan otomatis, dan bukan bukti kepemilikan akun. Reset hanya
  setelah verifikasi independen; bila tidak tersedia, reset ditahan. Pendaftaran
  membuat profil anak pertama tanpa meminta variasi soal; kelas sekolah opsional,
  lalu mengarahkan orang tua ke **Berikutnya** untuk menyiapkan latihan awal.
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
  anak memiliki empat tujuan berurutan: **Berikutnya**, **Buat latihan**, **Riwayat**,
  dan **Perkembangan**. URL profil tanpa query serta `?section=rencana` membuka
  Berikutnya; latihan manual berada di `?section=latihan`, arsip operasional tunggal
  di `?section=riwayat`, dan proyeksi bukti di `?section=perkembangan` sebagai satu
  tab dengan tiga bagian (Progres, Materi, Perjalanan) yang dinavigasi lewat
  anchor `#progres`, `#materi`, `#perjalanan`; deep link `/laporan/<id>` lama
  dialihkan ke tab setelah guard kepemilikan; `?section=`/`bagian=` lama tetap
  didukung sebagai alias anchor.
  Ringkasan aktivitas dapat dilihat lewat preset 7 hari,
  minggu ini, bulan ini, atau rentang tanggal sendiri. Detail paket/aktivasi mengikuti
  kontraknya, bukan keberadaan kode.

## Kontrak belajar utama

**Pemetaan → fokus → intervensi/contoh → latihan terbimbing → penguatan mandiri →
evaluasi berjeda → checkpoint → maju atau eskalasi.**

- Bukti sah berupa snapshot outcome **append-only**, setelah tinjauan dan
  konfirmasi eksplisit guru. `direview` dan `kode_final` mutable bukan bukti sendiri.
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

## Batas yang tidak boleh dilanggar

- Guru hanya mengakses data sendiri; resource asing → **404 dengan body identik**,
  tanpa efek samping. Murid tidak menerima kunci, malrule, diagnosis, atau laporan.
- Admin boleh mengelola data murid semua keluarga, tetapi tidak boleh mengubah
  akun/sandi sesama pengelola. Sesi berbukti tidak boleh dihapus permanen.
- Data anak, kredensial, sesi dan cadangan tidak masuk Git/log/fixture. Tes memakai
  data sintetis; pengiriman ke AI hanya melalui alur dan izin produk yang disetujui.
  Tidak menyimpan email/telepon pengguna. Nomor WhatsApp Business adalah konfigurasi
  operasi Jagomat, bukan kontak keluarga; URL publik tidak membawa nama akun/anak.
- Penghapusan seluruh keluarga memakai primitive domain teruji yang memerlukan
  verifikasi independen, preview exact, backup coherent empat DB + auth, dan cutover
  terkontrol; tidak boleh dirangkai dari penghapusan login guru. Data aktif dihapus,
  identitas pada arsip diputus bila kontrak mengizinkan, sementara bukti/ledger
  append-only tetap dipertahankan.
- Kunci dan diagnosis tidak ditentukan LLM. Tidak menjanjikan kesiapan juara atau
  menyamakan progres target Jagomat dengan penguasaan seluruh kurikulum sekolah.

## Acuan dan keputusan produk

[Siklus belajar](siklus-belajar-terpandu.md) · [Pilihan ganda](multiple-choice.md) ·
[Pendamping](pendamping-runtime.md) · [Paket](subscription-packages.md) ·
[Pembayaran](pembayaran-produksi.md) · [Operasi dukungan](support-operations.md).
Pekerjaan berstatus **DIBATALKAN** pada [indeks keputusan](README.md) bukan backlog
aktif; hanya dibuka kembali melalui keputusan baru pengguna. Perubahan kurikulum,
jenis soal, atau cakupan produk memerlukan keputusan pengguna.
