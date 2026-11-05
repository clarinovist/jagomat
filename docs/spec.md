# Jagomat — Spesifikasi ringkas

Ringkasan produk; detail di [referensi produk](product-reference.md), status dan
pekerjaan tersisa di [status proyek](status-proyek.md), arsitektur di [context.md](context.md).
Bukan keputusan produk baru atau bukti deployment.

## Tujuan dan pengguna

Latihan matematika SD untuk persiapan OSN/SASMO, diprioritaskan sebagai alat guru
les **in-house** untuk menentukan satu langkah belajar berikutnya. Sasaran jenjang
kelas 1 SD–kelas 9 dibuka bertahap (keputusan pemilik 28 Okt 2026); saat ini latihan
berkonten P3–P6 dan profil anak menyimpan kelas sekolah 1–6. Topik `bilangan-dasar`
menambah penjumlahan teks untuk Latihan manual P1 (hasil ≤10) / P2 (11–20).
Soal dalam lembar tidak kembar hingga seluruh domain level terpakai; setelah itu
pengulangan diizinkan. Latihan satu topik menawarkan kartu Variasi Dasar 1/2 dengan contoh
hanya untuk materi dasar; bawaan tetap otomatis dan tingkat anak tidak berubah.
`OSN_MATERI_DASAR=0` (bawaan kode; **produksi 1 sejak 4 Nov 2026** atas keputusan pemilik) menyembunyikan penawaran dan menolak pembuatan materi
dasar, termasuk draf Pendamping/remedial; sesi yang sudah ada tetap dapat dibaca, ditinjau, dicetak, dan dilaporkan.
Jenis lain, visual, dan cerita menyusul. Tingkat internal siswa,
siklus dan pilot tetap P3–P6 (keputusan 30 Okt 2026). Batas klaim publik di
[referensi workflow](workflow-reference.md#konteks-kurikulum--batas-klaim-produk). Pengembangan
pivot memakai data sintetis; pilot dengan data nyata perlu keputusan dan gerbang
privasi tersendiri. Peran teknis `guru` mencakup orang tua dan hanya mengelola data
miliknya; `murid` mengerjakan latihan; `admin` mengelola lintas keluarga dengan
batas khusus. Pada UI guru, orang dewasa disebut **Guru/Anda**, **Pendamping** nama AI.

## Cakupan aktif

- Generator deterministik, lembar cetak, latihan daring/manual, foto atau isi dari
  lembar, tinjauan dan laporan per anak. Kunci/diagnosis bukan keputusan LLM.
  Di halaman isi dari lembar, guru boleh mencentang "jawaban anak benar" alih-alih
  mengetik: jawaban tersimpan sebagai kunci, dinilai benar sebagai keputusan guru
  (manual, berpenanda), dan butir salah tetap diketik persis. Centang dengan teks yang
  berbeda dari kunci ditolak utuh. Bila anak mengubah jawaban tercentang sesudahnya,
  tanda benar dilepas dan Jagomat menilai ulang butir itu seperti jawaban biasa.
- Jawaban salah tanpa dugaan ("Belum yakin") di halaman tinjauan menampilkan tiga
  pertanyaan pancingan umum per topik untuk guru, berlabel draf; bukan diagnosis,
  bukan bukti, dan tidak pernah tampil di permukaan murid atau tautan.
- Beranda guru memprioritaskan yang terlama menunggu konfirmasi: kartu anak dengan satu
  tombol aksi, chip kelompok berhitungan, dan pencarian nama/login (untuk daftar panjang),
  semuanya owner-scoped. Query GET tidak di-cache atau dikirim sebagai referrer, tetapi
  tetap berada di URL/riwayat browser.
- Ruang anak: **Beranda → Latihan → Riwayat → Perkembangan**. Satu CTA dari reducer;
  laporan Ringkasan/Per materi memakai bukti yang sama, bukan skor global anak.
  P3–P6 adalah konfigurasi internal/historis, bukan kelas atau ukuran kemampuan.
- Bantuan statis dan **15 draf playbook P3 berperingatan**, bukan materi yang telah
  disahkan manusia. Hanya guru pada fokus/profil yang cocok; tidak dikirim ke murid.
- **Lembar persiapan sesi** `/anak/{id}/persiapan`: halaman cetak satu anak untuk guru
  pemilik (asing → 404 identik), isi rencana sama dengan kartu Beranda, playbook draf
  terbuka berperingatan, tanpa form/kunci, `no-store`. Satu tautan "Cetak catatan persiapan
  guru" dari Beranda profil (hanya peran guru), juga saat Pendampingan aktif. Bukan bukti
  belajar dan tidak menulis DB; lembar soal murid tetap lewat pil Cetak di sesi.
- **Laporan guru → orang tua (G3; live di produksi sejak 5 Nov 2026):** guru memilih
  periode di tab Perkembangan, meninjau pratinjau identik, menulis catatan (≤2000 karakter; draf menawarkan
  satu kalimat pembuka netral berpenanda `[isi]` yang wajib dilengkapi sebelum disimpan, tidak pernah terbit sendiri),
  lalu menerbitkan tautan baca-saja `/laporan-ortu/<token>` (30 hari, bisa dicabut, satu tautan
  aktif per anak, tanpa login/JS/tautan keluar). Isi hanya nama anak, periode, topik dari sesi
  selesai+terkonfirmasi, tahap netral "n dari 6", satu kalimat langkah, catatan, nama guru;
  tanpa skor, kode diagnosis, malrule, ID, level, atau kelas. Snapshot dibekukan saat terbit,
  tidak ada edit sesudahnya, admin hanya melihat, dan semua tautan tidak sah satu 404 identik.
  Menulis laporan tidak menyentuh bukti belajar. Tidak menyimpan email/telepon.
  Satu alur sesi kertas: Terapkan di halaman isi dari lembar yang membuat semua soal terisi
  membawa guru langsung ke tinjauan; ringkasan tinjauan memisahkan soal yang **wajib** diputuskan
  sebelum konfirmasi dari dugaan Jagomat dan tanya cara yang opsional (proyeksi UI, server tetap
  otoritatif). Setelah konfirmasi, satu tautan menuju halaman laporan orang tua (laporan per
  periode, tidak wajib tiap sesi). Lembar persiapan menyebut langkah sesudah sesi.
  Soal yang kosong di lembar dicentang “Anak tidak mengerjakan soal ini” (tidak menulis jawaban), sehingga
  sesi tetap selesai; di tinjauan soal tanpa jawaban (kertas maupun tautan) bawaan dilewati dari penilaian:
  bukan benar, bukan salah, bukan bukti (keputusan pemilik 6 Nov 2026). Guru bisa menyertakannya kembali;
  sesi tanpa satu jawaban pun tidak diberi bawaan dan tidak bisa diterapkan dari lembar.
- **HP anak sebagai jalur utama sesi les** (keputusan pemilik 6 Nov 2026): tombol utama sesi “Mulai di HP anak”
  (POST, tanpa JS) menampilkan kode QR server-side + tautan teks; anak memindai dengan HP-nya sendiri dan guru
  hanya meninjau. Tautan sesi berlaku 12 jam (sebelumnya 7 hari), satu per sesi, mati setelah dikirim/dicabut.
  Kertas tetap cadangan lewat Cetak; lembar persiapan menyebut keduanya. Kunjungan/uji coba lapangan dengan
  akun buatan tim tidak menunggu gerbang izin wali (G4) (keputusan pemilik 6 Nov 2026).
- **Fitur khusus orang tua dibekukan (keputusan pemilik 1 Nov 2026):** Pendamping AI,
  kartu pra-tulis dan bantuan orang tua tetap berjalan tanpa investasi baru; kendali
  data tetap tersedia. Penghapusannya perlu keputusan terpisah.
- Pendamping inline memakai konteks berizin dan usulan yang harus ditinjau.
  Hapus chat/cabut izin tersedia walau provider mati; tombstone/purge, memori,
  hasil latihan, backup dan provider mempunyai batas retensi berbeda.
- Akun, persetujuan awal, sensor internal opt-in, panel admin/tema, dukungan akun,
  riset publik dan wawancara privat tersedia. Sensor bukan bukti efektivitas belajar.
- Akses awal **nonkomersial**. Fondasi paket/pembayaran tidak berarti trial,
  kampanye, checkout v2, refund atau penegakan paket telah dibuka.

## Kontrak belajar dan perlindungan

**Pemetaan → fokus → intervensi/contoh → terbimbing → penguatan → evaluasi
berjeda → checkpoint → maju/eskalasi.** [Kontrak lengkap](siklus-belajar-terpandu.md).

- Bukti hanya snapshot outcome append-only yang dikonfirmasi eksplisit; status
  review mutable bukan bukti. Koreksi menginvalidasi bukti aktif tanpa menulis ulang histori.
- Maksimal dua fokus `(template_id, kode_intervensi, malrule_id)`. B/K/H/E/N/T
  mempunyai tindakan masing-masing; T lewat pengenalan, bukan langsung remedial.
- Benar belum cukup tanpa penjelasan. Evaluasi ≥4 probe/fokus; checkpoint 28 hari
  ≥3 probe/fokus; gagal kedua/tidak ada alternatif → eskalasi. Syarat kelulusan
  lengkap tetap mengikuti kontrak, bukan jumlah soal saja. Checkpoint yang lebih dini
  dari 28 hari tidak dihitung sebagai retensi, meski sesinya ada.
- Jawaban angka ditulis bebas: pemisah ribuan titik atau spasi (`8.000`, `8 000`)
  dibaca sebagai bilangan bulat; koma tetap desimal. Format salah bukan alasan
  mencatat jawaban benar sebagai salah.
- Manual/PG/terbimbing/penguatan tidak otomatis menjadi bukti penguasaan;
  konteks profil/representasi dan provenance tidak dicampur diam-diam.
- Guru asing mendapat **404 identik**, tanpa efek samping; murid tidak menerima
  kunci, malrule, diagnosis atau laporan. Admin tidak mengubah akun sesama admin.
- Data anak, credential, sesi, wawancara dan backup tidak masuk Git/log/fixture.
  Tidak menyimpan email/telepon pengguna. Hapus keluarga memerlukan verifikasi,
  preview/backup/cutover; bukan sekadar menghapus login atau bukti immutable.
- [Backup operasional](operational-backup.md) manual mencakup core, riset dan foto;
  scheduler/off-site otomatis belum tersedia, bukan janji pemulihan seluruh VPS.

## Batas dan keputusan

Batch katalog aktif dan bank kalimat tidak mengesahkan seluruh katalog. Revisi
penilaian1/pilot bank dan [draf koreksi lanjutan2](catalog-followup.md) tetap
offline/default0; playbook masih draf; efektivitas
pada guru/anak belum dibuktikan. Tidak menjanjikan siap juara atau penguasaan seluruh
kurikulum. Pekerjaan [dibatalkan/ditunda](status-proyek.md) tidak dibuka otomatis.

Acuan: [playbook](playbook-guru.md) · [Pendamping](pendamping-runtime.md) ·
[paket](subscription-packages.md) · [privasi/dukungan](support-operations.md) ·
[aturan proyek](../CLAUDE.md). Perubahan cakupan harus memperbarui ringkasan ini
bersama kontrak detail; status operasi dicatat terpisah di runbook rilis.
