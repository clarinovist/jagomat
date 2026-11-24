# Jagomat — Spesifikasi ringkas

Ringkasan produk; detail di [referensi produk](product-reference.md), status dan
pekerjaan tersisa di [status proyek](status-proyek.md), arsitektur di [context.md](context.md).
Bukan keputusan produk baru atau bukti deployment.

## Tujuan dan pengguna

Latihan matematika SD untuk persiapan OSN/SASMO, diprioritaskan sebagai alat guru
les **in-house** untuk menentukan satu langkah belajar berikutnya. Sasaran jenjang
kelas 1 SD–kelas 9 dibuka bertahap (keputusan pemilik 28 Okt 2026); saat ini latihan
berkonten P3–P6 dan profil anak menyimpan kelas sekolah 1–6. Topik `bilangan-dasar`
menambah penjumlahan teks untuk Latihan manual P1 (hasil ≤10) / P2 (11–20). Source juga
memuat pengurangan, bilangan yang hilang, nilai tempat, dan membandingkan (tanda <, >, =)
untuk P1 (bilangan ≤20, tambah-kurang ≤10) / P2 (≤100, tambah-kurang ≤20); jenis itu hanya
dibuat bila `OSN_DASAR_LENGKAP=1` (bawaan kode 0; **produksi 1 sejak 6 Nov 2026** atas
keputusan pemilik setelah self-review, bukan ulasan guru independen), sedangkan pembaca
selalu mengenalnya. Recovery `c58390a` (writer katalog1/teori1) mengenal kelima jenis.
Topik `bilangan-sekolah` (P3–P5, mode sekolah: nilai tempat, mengurutkan, penjumlahan/pengurangan
bersusun, perkalian/pembagian, kalimat matematika; semua teks angka) hanya dibuat bila
`OSN_BILANGAN_SEKOLAH=1` (bawaan kode 0; **produksi 1 sejak 23 Nov 2026** setelah ulasan Mutia atas
rentang dan malrule) dan **hanya untuk Latihan manual guru dan lembar cetak**: tidak masuk Campuran,
siklus terpandu, Pendamping, atau sisi murid.
Topik `matematika-awal` ("Matematika Awal"; level P1 sampai P6) mengisi bab Kurikulum Merdeka SD yang
belum cukup soal dengan 25 jenis soal (teks, dan bergambar lewat keluarga visual `matematika-awal` yang flagnya belum menyala): P1 `kenali_bentuk`, `ukur_satuan_tak_baku`,
`baca_diagram_gambar`, `bilang_benda_awal`, `tambah_kurang_20`, `kenali_bangun_awal`; P2 `kenali_bentuk`, `pola_posisi`,
`pecahan_setengah`, `waktu_berat_awal`, `turus_gambar_awal`, `tambah_kurang_100`, `kenali_bangun_awal`, `baca_jam_awal`; P3 `ukur_konversi_awal`,
`unsur_bangun_datar`; P4 `pecahan_senilai_desimal`, `luas_petak_volume_kubus`, `ciri_komposisi_bangun`;
P5 `bandingkan_ciri_bangun`, `keliling_gabungan`, `ukur_sudut_awal`, `piktogram_lima_awal`; P6 `peluang_dasar`, `pecahan_bilangan_asli_desimal`, `pecahan_campur_awal`, `tampak_kubus_awal`.
Status bab di `/admin/kurikulum` (40 bab): 40 "Sudah ada soal", 0 "Perlu disempurnakan", 0 "Belum ada
soal" di kode lokal (22 Nov 2026; belum push/deploy). Jenis berkecocokan "ada" menaikkan bab dengan sub-materi yang
tertutup soal teks (K1 B1, K1 B6, K2 B2, K3 B4, K4 B2, K4 B4, K4 B5, K5 B4, K6 B1 lewat `pecahan_campur_awal`;
K2 B4, K2 B5, K3 B3, K5 B7, K6 B4 atas keputusan pemilik 21 Nov 2026). K3 B5 dan K4 B6 "ada" lewat pelatih `statistika`
yang `wajib_visual` (flag visual menyala di produksi per `/opt/osn/visual.conf`, dibaca 21 Nov 2026). Sembilan bab
bergambar lewat keluarga `matematika-awal` (K1 B4, K1 B7, K1 B8, K2 B3, K2 B6, K2 B8, K5 B6, K5 B8, K6 B3)
"ada" mengandaikan flag keluarga itu, yang BELUM menyala di produksi dan tak boleh sebelum recovery/reader membaca
skema `adegan_awal` (tanpa flag soalnya teks yang tetap bisa dijawab). Celah isi yang dicatat untuk ulasan Mutia:
K5 B6 belum memuat sudut bertolak belakang/sehadap, K5 B8 tanpa gambar setengah dan tanpa membuat piktogram dari tabel,
K2 B6 "Membandingkan berat" hanya teks, jam hanya jam penuh dan setengah.
Sama seperti `bilangan-sekolah`, topik ini **hanya untuk Latihan manual guru dan lembar cetak** (bukan
Campuran, siklus, Pendamping, sisi murid). Karena memuat P3+ ia bukan "materi dasar": `OSN_MATERI_DASAR`
tidak menyembunyikannya. Pembuatan di balik `OSN_MATEMATIKA_AWAL` (env-only, "0"/"1", **bawaan 1** atas
keputusan pemilik 21 Nov 2026, jadi menyala otomatis di image yang memuat kode ini). Rentang angka,
malrule, dan fakta bangun datar belum diulas Mutia/guru.
Soal dalam lembar tidak kembar hingga seluruh domain level terpakai; setelah itu
pengulangan diizinkan. Latihan satu topik menawarkan kartu Variasi Dasar 1/2 dengan contoh
hanya untuk materi dasar; bawaan tetap otomatis dan tingkat anak tidak berubah.
`OSN_MATERI_DASAR=0` (bawaan kode; **produksi 1 sejak 4 Nov 2026** atas keputusan pemilik) menyembunyikan penawaran dan menolak pembuatan materi
dasar, termasuk draf Pendamping/remedial; sesi yang sudah ada tetap dapat dibaca, ditinjau, dicetak, dan dilaporkan.
Visual, cerita, dan integrasi siklus menyusul. Tingkat internal siswa,
siklus dan pilot tetap P3–P6 (keputusan 30 Okt 2026). Batas klaim publik di
[referensi workflow](workflow-reference.md#konteks-kurikulum--batas-klaim-produk). Pengembangan
pivot memakai data sintetis; pilot dengan data nyata perlu keputusan dan gerbang
privasi tersendiri. Peran teknis `guru` mencakup orang tua dan hanya mengelola data
miliknya; `murid` mengerjakan latihan; `admin` mengelola lintas keluarga dengan
batas khusus. **Akun anak (23 Nov 2026; produksi aktif sejak rilis 7a4d388: sakelar `DAFTAR_AKUN_ANAK` = 1 lewat
`visual.conf`, lembaga antrean id 1 "jagomat" milik `koordinator-jagomat`; lihat Fitur di bawah):** pendaftaran publik
membuat akun anak; orang tua melihat hasil lewat halaman orang tua di akun anak (anak boleh ikut
melihat, kecuali orang tua memasang PIN tirai); `guru` khusus guru les; anak pendaftar dipegang
lembaga Jagomat lalu dipindah ke guru anggota; Latihan Harian per tingkat (Rp39.000/bulan,
Rp349.000/tahun, termasuk untuk murid les; mesin soal Latihan Harian = F4, langganan = F5 di bawah). Pada UI guru, orang dewasa disebut **Guru/Anda**, **Pendamping** nama AI.
**Pemilik les** adalah akun guru yang oleh admin dijadikan pemilik sebuah lembaga
(tersimpan di DB, bukan peran baru di berkas akun). Admin mengatur lembaga, anggota,
dan pembubaran di `/admin/lembaga` (setiap aksi tulis meminta sandi admin; pembubaran juga meminta nama
lembaga diketik persis, divalidasi di server); satu guru maksimal satu lembaga; login guru yang
masih terikat lembaga tidak bisa dihapus. Pemilik les hanya melihat ringkasan per guru
anggota di `/lembaga` (anak, jumlah sesi, sesi terakhir, menunggu konfirmasi) dan bisa
memindahkan anak antar guru lembaganya; ia **tidak** membuka sesi/jawaban anak guru lain.
Pindah ditolak bila anak sedang punya sesi berjalan; nama kembar di guru tujuan tidak menolak,
tetapi nama anak diberi pembeda "(2)", "(3)", dst. (ditolak hanya bila pembeda habis di "(99)").
Pemilik les juga bisa **memindahkan banyak anak sekaligus** ke satu guru tujuan: centang anak di `/lembaga`
(HTML native, satu form per seksi guru asal: daftar centang hanya berisi anak guru itu dan pilihan tujuan tidak memuat guru asal; maksimal 50 per permintaan; `POST /lembaga/pindah-banyak`), satu transaksi semua-atau-tidak-sama-sekali
dengan kewenangan yang sama seperti pindah satu anak (anak dan tujuan penghuni lembaga yang sama, selain itu 404 identik).
Seluruh permintaan ditolak tanpa mengubah apa pun, dengan jumlah anak bermasalah di pesan, bila ada anak yang
sudah di guru tujuan, bersesi berjalan, atau pembeda nama habis; nama kembar (juga antar anak dalam batch) diberi
pembeda, dan tiap anak mendapat satu jejak pindah.
Admin yang melepas anggota mengembalikan **semua** anaknya ke pemilik lembaga (satu jejak per anak,
nama kembar diberi pembeda; ditolak bila ada anaknya dengan sesi berjalan, tanpa mengubah apa pun).
Riwayat belajar ikut anak, jejak pindah append-only. Guru lain mendapat 404 identik.

## Cakupan aktif

- Generator deterministik, lembar cetak, latihan daring/manual, foto atau isi dari
  lembar, tinjauan dan laporan per anak. Kunci/diagnosis bukan keputusan LLM.
  Di halaman isi dari lembar, guru boleh mencentang "jawaban anak benar" alih-alih
  mengetik: jawaban tersimpan sebagai kunci, dinilai benar sebagai keputusan guru
  (manual, berpenanda), dan butir salah tetap diketik persis. Centang dengan teks yang
  berbeda dari kunci ditolak utuh. Bila anak mengubah jawaban tercentang sesudahnya,
  tanda benar dilepas dan Jagomat menilai ulang butir itu seperti jawaban biasa.
- **Tes Diagnostik Baku (live 15 Nov 2026):** guru membuat sesi **isian berpasangan**
  dari `POST /sesi-diagnostik/<siswa>` untuk jenjang P1–P6: 3–4 butir triase prasyarat
  di awal, lalu minimal dua probe per sub-konsep (P1/P2 10, P3 20, P4–P6 24 butir).
  Topik `berhitung-sekolah` (perkalian, pembagian, pecahan sederhana, nilai tempat
  ratusan/ribuan) tersedia untuk Latihan manual P3–P4 dan ikut pemetaan terpandu P3.
  Pilihan cara `hitung di kertas / di kepala` menjadi jejak cara: jawaban tanpa kotak
  "Caraku" tidak otomatis dianggap tebakan, tetapi penanda `tebak` tetap `N` meski
  benar. `evaluasi_pasangan_diagnostik` mengelompokkan hasil per sub-konsep menjadi
  `kuat`, `konsisten_k`, `konsep_awal`, `teliti`, `tebak`, `belum_diajari`, atau
  `belum_dinilai`, dengan penanda sesi `triase_macet`. Salah konsep dan sekadar
  kurang teliti sengaja dipisah karena intervensinya berbeda; `triase_macet` adalah
  keadaan sesi, bukan status per sub-konsep. Ringkasannya tampil di halaman tinjauan
  guru hanya untuk sesi berkomposisi baterai exact, tanpa kode/malrule/skor mentah.
- Jawaban salah tanpa dugaan ("Belum yakin") di halaman tinjauan menampilkan tiga
  pertanyaan pancingan per jenis soal plus satu saran tindak lanjut untuk guru (cadangan:
  pertanyaan umum per topik), berlabel draf sampai ditinjau reviewer; bukan diagnosis,
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
  tanpa skor, kode diagnosis, malrule, ID, level, atau kelas. Sejak 15 Nov 2026 snapshot v2
  menambah peta topik (maks. 6 status ramah), alur berpikir empat tahap, poin kuat/fokus,
  satu langkah rumah 15 menit, dan ringkasan siap salin — dirender sebagai **SVG sebaris
  sisi server (Zero-JS)**, tetap tanpa angka/skor/kode/level; snapshot v1 lama jatuh ke
  tampilan lama. Snapshot dibekukan saat terbit,
  tidak ada edit sesudahnya, admin hanya melihat, dan semua tautan tidak sah satu 404 identik.
  Menulis laporan tidak menyentuh bukti belajar. Laporan tidak memuat kontak.
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
- Menu admin (Fase B redesign): Ringkasan; Penjualan (Pesanan & transfer, Rekening transfer, Topik Cek
  Kemampuan); Pengguna (Keluarga, Siswa, Lembaga les, Guru & pemakaian, Riset konsumen sementara); Sistem
  (Pengaturan layanan, Riwayat admin); Lainnya terlipat (Langganan lama, KPI uji
  coba dan AI yang akan dimatikan; halaman KPI dan AI memuat kartu pemberitahuan). Pendaftaran mandiri
  menjadi bagian `#pendaftaran` di Pengaturan layanan (`/admin?section=pendaftaran` mengalihkan 303).
- Admin melihat **Pemakaian guru** (`/admin/pemakaian`, baca-saja; tab "Pemakaian" | "Profil guru
  peninjau" satu butir menu "Guru & pemakaian"): per akun guru per minggu
  WIB, 8 minggu terakhir: minggu aktif, sesi dibuat/selesai/dikonfirmasi, median lama anak,
  jeda selesai→konfirmasi, perkiraan waktu tinjau, sumber, laporan terbit. Tanpa nama anak;
  waktu persiapan belum terukur.
- Admin melihat **Topik Cek Kemampuan** (`/admin/cek-topik`, baca-saja, tanpa DB): topik cek gratis
  per kelas, soal per topik, contoh jenis soal, dan status materi dasar kelas 1–2. Diturunkan dari kode;
  mengubahnya lewat kode dan rilis, bukan dari admin. Tab "Kurikulum Merdeka" (`/admin/kurikulum`):
  tabel 40 bab buku siswa 2022 per kelas 1–6 dengan jenis soal Jagomat, jenis, variasi, jumlah soal yang pernah
  dipakai (agregat COUNT, tanpa data anak), dan status (dari level kelas); tautan "Buat soal" (`/admin/kurikulum/buat`)
  membangkitkan 5/10/20/30 contoh soal bab itu dari seed, tanpa menyimpan. Jenis yang sakelar rilisnya mati ditandai
  "belum dinyalakan". Tab "Detail CP" (`/admin/kurikulum/cp-detail`):
  butir CP Merdeka per fase, celah cakupan SD (dihitung dari pemetaan efektif), dan grup per topik. Admin bisa **mengubah
  pemetaan CP per grup** (`/admin/kurikulum/cp?grup=<topik>/<kode>`: sampai 12 butir + kecocokan): langsung berlaku tanpa
  draf, tercatat di audit (waktu, akun, lama→baru), tombol "Kembalikan ke bawaan" kode. Aksi memakai tinjauan bertanda
  tangan + sandi ulang + revisi (konflik 409). Admin juga bisa **mengubah label awam topik** (`/admin/kurikulum/label?topik=<id>`, 1-40
  karakter, unik tanpa beda huruf besar-kecil, tidak sama dengan nama resmi topik): langsung berlaku untuk layar anak dan
  hasil cek yang dinilai sesudahnya; hasil cek yang sudah dinilai tetap memakai label lama (ringkasan tersimpan sebagai teks).
  Audit, kembalikan ke bawaan, dan guard sama seperti pemetaan CP. Topik, grup, dan butir CP tetap di kode.
  Admin juga menulis **cetakan soal berpola** per bab (C2, manual, tanpa AI; `/admin/kurikulum/cetakan?kelas=&bab=`, tautan
  "Kelola cetakan" di tiap baris tabel): cetakan = data (teks dengan `{a}`, rentang variabel, syarat, rumus kunci), kunci selalu
  dihitung mesin. Draf diperiksa di `/cetakan/periksa?id=` (10 contoh soal + kunci, uji kelayakan, riwayat), lalu **Setujui**
  (draf -> aktif, wajib lolos uji kelayakan), **Nonaktifkan**, atau **Aktifkan kembali**; semua aksi memakai tinjauan bertanda tangan
  + sandi ulang, semua admin boleh menyetujui. Isi tak sah = halaman dirender ulang 400 tanpa tulis. Hanya cetakan AKTIF
  tampil di tabel (jenis soal bab; bab tanpa soal kode tetapi punya cetakan aktif = "Perlu disempurnakan", variasi "banyak") dan
  Buat soal (bergiliran dengan soal kode, label "Cetakan: judul"); belum masuk sesi anak (C4 ditunda). `cetakan.db` rusak = tabel
  dan Buat soal tetap jalan dengan soal kode saja; aksi POST = 503.
  **Draf dari AI** (C3): di halaman cetakan bab ada tombol "Buatkan draf cetakan dengan AI" (sandi ulang; sisa kuota ditampilkan; di tabel Kurikulum
  Merdeka bab belum/sebagian juga bertaut "Buatkan draf cetakan"). AI (DeepSeek, kunci server) hanya diberi kelas, judul bab, dan sub-materi, lalu menulis
  1-3 draf; mesin memeriksa tiap draf (kelas/bab dari halaman, bukan dari AI) dan menghitung kuncinya sendiri. Yang lolos tersimpan sebagai **draf** (label
  "Draf AI", tak pernah aktif sendiri; Setujui tetap oleh admin), yang gagal ditampilkan dengan alasannya. Maks 20 permintaan per hari WIB untuk semua admin
  (slot terpakai walau AI gagal), balasan > 8 KB atau > 30 detik ditolak. Tanpa kunci atau kuota habis/tak terbaca, tombol hilang dan cetakan manual
  tetap jalan. Fitur ini berdiri sendiri: menghentikan fitur AI lama di /admin/ai tidak mematikannya dan pemakaiannya tidak muncul di ledger /admin/ai.
- **Pengaturan layanan** (`/admin/sakelar`, satu halaman; `/admin?section=operasional` mengalihkan 303 ke
  sini), dirombak 23 Nov 2026 agar terbaca Pemilik: ringkasan "Yang aktif sekarang" (badge Aktif/Mati), lalu kelompok Penjualan dan pembayaran
  (Cek Kemampuan, pembayaran QRIS Midtrans dengan label tahap awam Tutup/Buka, transfer rekening + checklist tiga langkah membukanya, kartu rekening; ubah di `/admin/pesanan/rekening`),
  Fitur belajar, pendaftaran mandiri (form lama, POST tetap ke `/admin/pendaftaran`), dan Kesehatan sistem terlipat (kesiapan, dukungan). Kolom sandi tiap form baru tampil
  setelah `<details>` tindakan dibuka; mematikan fitur aktif memakai konfirmasi yang menyebut akibatnya (`akibat_mati` di registri). Baris status AI sudah dihapus dari halaman ini. Admin mengubah **sakelar fitur**: `FUNNEL_AKTIF`, `PESANAN_TRANSFER_AKTIF`,
  `OSN_CETAK_RINGKAS`, `OSN_BANK_KALIMAT`, `OSN_LOMBA`, `DAFTAR_AKUN_ANAK`, `LATIHAN_HARIAN` (bawaan mati; kontrak `akses_harian.py`: tanpa batas bila langganan aktif atau anak dipegang guru anggota lembaga antrean, selain itu 1 sesi gratis per hari; sakelar ini juga membuka rute MURID langganan di bawah, mati = 404 rute tak dikenal; antrean admin `/admin/langganan` tetap terbuka walau mati supaya bukti yang sudah masuk bisa diputuskan). Nilai disimpan di DB terpisah `/data/sakelar.db` (dibuat saat
  perubahan pertama; env tetap fallback; DB lama dengan empat nama diperlebar saat perubahan pertama tanpa menaikkan versi skema), dengan tinjauan bertanda tangan, sandi ulang, optimistic
  concurrency, dan audit. DB sakelar rusak = kartu galat + status 503, bagian lain halaman tetap tampil; menyalakan transfer ditolak bila funnel
  mati atau rekening kosong.
  **Langganan Latihan Harian (F5):** orang tua di akun anak membuka `/murid/langganan`, memilih paket Bulanan (Rp39.000, 1 bulan kalender) atau Tahunan (Rp349.000, 12 bulan), mendapat tagihan transfer (rekening admin yang sama dengan Paket Coba, nominal = harga + kode unik 1..999 bebas tabrakan, jendela bayar 24 jam, satu tagihan terbuka per anak), mengunggah bukti (JPEG/PNG/PDF maks 5 MB), lalu melihat status menunggu/ditolak (dengan alasan; boleh unggah ulang)/aktif. Admin memeriksa di `/admin/langganan` (tinjauan bertanda tangan + sandi ulang); setuju menulis keputusan dan masa aktif dalam satu transaksi, perpanjangan menyambung dari akhir masa aktif. Halaman orang tua menampilkan kartu status dan banner "berakhir N hari lagi" bila sisa <= 3 hari. Harga hanya konstanta server; tanpa WA. Berkas bukti langganan dihapus 30 hari sesudah keputusan admin (bukti menunggu tidak pernah dihapus) lewat sapuan harian yang sama dengan Paket Coba.
- **Pendaftaran akun anak (F2a, 23 Nov 2026)**: saat sakelar `DAFTAR_AKUN_ANAK` hidup DAN lembaga antrean
  terkonfigurasi (env server `OSN_LEMBAGA_ANTREAN` = id lembaga; pemilik lembaga = akun koordinator), `/daftar`
  dan `/daftar?jalur=cek` memakai satu form orang tua: nama login anak, sandi anak, nama lengkap anak (1–80),
  kelas 1–6, WA orang tua, centang persetujuan, PIN tirai opsional 4 digit. Hasilnya akun **murid** terikat satu
  anak (baris `siswa` BARU milik koordinator, nama kembar diberi pembeda "(2)", tidak pernah digabung), kontak di
  akun anak, persetujuan (`versi_notice` sama dengan cek gratis) dan hash PIN (bila diisi) di transaksi yang sama,
  lalu sesi murid dan redirect ke `/murid`. Sakelar hidup tetapi antrean belum siap = "Pendaftaran sementara belum
  dibuka." tanpa menulis apa pun (tidak jatuh ke alur guru). Sakelar mati = alur akun guru seperti sebelumnya.
  Akun guru lama tidak dimigrasi.
- **Halaman orang tua di akun murid (F3, 23 Nov 2026)**: di balik sakelar yang sama (`DAFTAR_AKUN_ANAK`; mati = 404 identik rute murid
  tak dikenal, tanpa tombol), untuk SEMUA akun murid terhubung siswa. Beranda murid menampilkan tautan sekunder "Untuk Ayah/Bunda" ke
  `/murid/orang-tua`: baca-saja berisi hasil cek (skor, kategori, ringkasan topik), laporan Guru terbit terbaru (tidak tampil bila Guru mencabut tautannya; kedaluwarsa tautan tidak menyembunyikannya; tampil lagi bila tautan diganti/terbit baru), status pembayaran Peta
  Kemampuan (teks sama dengan halaman pesanan, tanpa tombol bayar) dan kartu PIN. Bila anak punya PIN tirai, halaman hanya menampilkan form
  PIN (4 angka) sampai PIN benar; tirai terbuka 30 menit per sesi (hilang saat keluar), salah 5x/15 menit = "Coba lagi beberapa menit lagi."
  Pasang/ganti/hapus PIN hanya saat tirai terbuka atau belum ada PIN (hapus wajib centang konfirmasi). Nomor WhatsApp, kunci, malrule,
  kode diagnosis, dan pembahasan tidak pernah tampil; nomor hanya bisa diubah lewat tim. PIN tirai bukan batas keamanan data.
  Tampilan gaya landing page (24 Nov 2026, presentasi saja): urutan blok = banner "berakhir N hari lagi" (bila ada), hero teal "Halo,
  Ayah/Bunda" + nama anak (tiga angka hari latihan/soal dikerjakan/persen tepat hanya saat Latihan Harian aktif; tanpa chip kelas karena
  kelas anak tidak ada di data halaman), hasil cek (cincin skor yang sudah ada; tanpa batang per bagian karena data hanya memuat skor,
  kategori, dan daftar topik), Latihan Harian (titik hari), kartu langganan, laporan Guru (kosong = kartu sabar), kartu Peta Kemampuan, lalu PIN
  dilipat dalam `<details>` (terbuka otomatis bila ada pesan PIN). Kartu langganan punya enam keadaan berlencana teks: belum berlangganan
  (navy, "Rp39.000/bulan" dihitung dari paket), menunggu pemeriksaan (kuning), aktif (hijau, "Tanpa batas sampai ..."), segera berakhir
  (sisa <= 3 hari, koral lembut, Perpanjang), bukti ditolak (alasan + Unggah ulang bukti), murid les (hijau, tanpa tombol); tombol selalu ke
  `/murid/langganan`. Halaman itu: satu kartu per paket (form native "Pilih Bulanan/Tahunan"; stiker "Paling hemat", "Setara sekitar" dan
  "Hemat" Tahunan dihitung dari konstanta paket), kartu tagihan berpola kertas dengan nominal besar + langkah "1 Transfer, 2 Unggah bukti,
  3 Aktif", status menunggu (maskot berpikir) dan aktif (hero berkonfeti); satu maskot per layar, tanpa skrip baru.
- **Cek kemampuan di sesi anak (F2b, 23 Nov 2026)**: bila sakelar `DAFTAR_AKUN_ANAK` DAN funnel hidup, beranda murid
  menampilkan kartu "Cek kemampuan" (Mulai/Lanjutkan) hanya untuk anak hasil pendaftaran mode anak (ada
  `persetujuan_daftar_anak` bernotice sama) yang cek-nya belum dikumpulkan; setelah dikumpulkan kartu hilang (hasil dilihat
  orang tua di halaman orang tua, F3). `POST /murid/cek/mulai` (tanpa field; siswa dan akun HANYA dari sesi) membuat/
  melanjutkan cek lewat mesin yang ada lalu 303 ke tautan anak `/mulai/<token>?di=akun` (layar akhir tetap "Hore" tanpa skor; varian `akun` menambah tautan "Kembali ke beranda" ke `/murid` dan kalimat minta Ayah/Bunda membuka halaman orang tua; varian lain tak berubah).
  Sesi cek disembunyikan dari daftar latihan biasa. Tanpa persetujuan/anak lain/gerbang mati: tak ada tulisan; gerbang
  mati = jalur murid asing. Skor dihitung `cek_gratis.selesaikan_jika_siap`, dibaca `cek_gratis.hasil_siswa(id_akun_murid, siswa_id)`.
  Akun guru lama tidak dimigrasi; halaman orang tua dan cek di sesi anak menyusul (F2b/F3).
- **Pesanan Peta Kemampuan dari akun anak (F2c, 23 Nov 2026)**: di balik sakelar `DAFTAR_AKUN_ANAK` (mati = jawaban
  sama dengan jalur `/murid` tak dikenal), orang tua yang memakai akun anak memesan dan membayar Rp49.000 untuk anak itu
  sendiri lewat mesin pesanan/transfer yang sama dengan guru. Titik masuk GET `/murid/pesanan` (belum ada pesanan =
  kartu "Pesan Peta Kemampuan"; sudah ada = status, tagihan transfer, unggah bukti maks 5 MB, QRIS bila jalur itu aktif);
  aksi POST di bawah `/murid/pesanan/{pesan,tagihan,bukti,tagihan/ulang,periksa,ulang,buat}`, `/murid/pesanan/qr` untuk
  gambar QRIS. Pembeli = akun murid dari sesi, anak = siswa tertaut akun itu (bukan dari URL/form), kontak = WA yang ditulis
  saat daftar; nomor WA tidak pernah tampil. Prasyarat (cek anak selesai, kontak ada) dan pesan penolakan sama dengan guru
  (tanpa tautan lengkapi kontak: nomor diubah lewat admin). Pesanan milik akun/anak lain = 404 yang sama dengan jalur tak dikenal.
- **Latihan Lomba** (Grand Final Corexis, Matematika Level 1; segmen khusus untuk anak pemilik, di balik sakelar admin `OSN_LOMBA` = saklar induk, bawaan mati;
  mati = semua alamatnya 404). Aktivasi per anak oleh Guru (Mode Lomba, 22 Nov 2026): murid hanya melihat Lomba bila sakelar induk hidup DAN Guru/admin mengaktifkannya untuk anak itu: tombol Aktifkan/Matikan di kartu anak `/akun?section=siswa` (hanya mengubah aktif; target, durasi, tanggal, dan nama lomba tetap), atau rinci di `/anak/<id>/lomba` (kartu "Mode Lomba": aktif/belum, target harian 0-3 atau ikut paket, hitung mundur tampil/tidak, tanggal lomba (kosong = tanpa hitung mundur; tiap anak punya tanggal sendiri) dan nama lomba (hanya terlihat oleh Guru), waktu Latihan dan waktu Simulasi dalam menit bulat 5-180, kosong = bawaan 15/60, di luar itu ditolak dengan pesan ramah tanpa menyimpan, berlaku untuk sesi berikutnya; tanpa penugasan = tidak aktif; anak tanpa penugasan aktif mendapat 404 yang sama dengan jalur murid tak dikenal; riwayat Guru tetap terbuka walau mati). Murid yang terhubung ke data siswa dan sudah ditugaskan membuka `/murid/lomba` (tautan di beranda murid hanya saat itu) dan memilih dua mode (22 Nov 2026): **Latihan** 10 soal
  (8 pilihan ganda + 2 isian; maks satu soal Inggris) atau **Simulasi Lomba** 35 soal (30 PG + 5 isian, format PDF lomba: Bilangan 9, Operasi 9, Pengukuran 8, Bangun 9; isian di ≥3 topik;
  satu jenis soal maks dua kali dengan angka/gambar berbeda; maks dua soal Inggris; kunci 7-8 per huruf), dari 38 template buatan sendiri, waktu (bawaan 15/60 menit atau durasi Guru) yang
  dihitung dan ditegakkan server (jawaban setelah batas ditolak, layar soal tertutup, hasil langsung tampil). Satu sesi berjalan per anak apa pun modenya. Soal baru tiap sesi: tidak mengulang soal lima sesi terakhir
  (bila bank tidak cukup, larangan sesi tertua dilepas lebih dulu, tanpa galat), jenis soal dua sesi Latihan terakhir dihindari. Jawaban tersimpan lewat form biasa (tanpa autosave JS; satu-satunya JS adalah hitung mundur). Setelah selesai atau waktu habis anak
  melihat nilai, nilai per topik, jawabannya, kunci, dan pembahasan; selama sesi berjalan kunci/pembahasan tidak pernah dikirim (keputusan Pemilik 21 Nov 2026, pengecualian
  terbatas dari palang murid). Guru/admin melihat progress dan riwayat per anak di `/anak/<id>/lomba` (grafik nilai, nilai per topik, jenis soal paling sering salah dengan label ramah Guru, detail
  sesi dengan dugaan kesalahan; riwayat berupa kartu di HP). Perilaku sisi anak (keputusan Pemilik 22 Nov 2026): jawaban PG atau isian yang sah langsung pindah ke soal kosong berikutnya (siklis; klik nomor/tombol soal tetap ke tujuannya);
  isian membuang semua spasi ("5 9 4" = 594; titik/koma/huruf ditolak, ketikan galat dipertahankan); konfirmasi kumpul menunjukkan soal kosong; hasil berisi nilai (x/10 atau x/35, label mode), banding dengan sesi sah
  sebelumnya bermode sama, peta nomor, soal salah/kosong terbuka dan yang benar dilipat; halaman awal dan kartu beranda menampilkan hitung mundur ke tanggal lomba anak itu (bukan satu tanggal untuk semua) dan target latihan harian. Satu Simulasi sah = satu sesi target harian; riwayat diberi label Latihan/Simulasi; nilai terbaik dipisah per mode; terbaik/rata-rata/tren Guru dari Latihan, grafik Guru memakai persen benar bila ada Simulasi. Sesi "asal kumpul"
  (Latihan: < 120 detik atau < 3 soal terisi; Simulasi: < 10 menit, kecuali waktunya memang habis, atau < 12 soal terisi) tetap di riwayat tetapi tidak ikut nilai terbaik, banding, target, maupun rata-rata/tren/topik/jenis sering salah di halaman Guru (ditandai "Dikumpulkan cepat", titik grafik abu-abu). Paket lomba (nama, tanggal, durasi, target) adalah konfigurasi kode `contest_paket`.
  Data di tabel `lomba_*` (termasuk `lomba_penugasan`) terpisah dari sesi guru; ikut terhapus saat penghapusan keluarga; tidak menulis ke Peta Kemampuan, diagnosis, laporan, atau bukti.
- **Latihan Harian** (F4; di balik sakelar admin `LATIHAN_HARIAN`, bawaan mati; **produksi aktif sejak 23 Nov 2026 rilis cf43373** lewat `visual.conf`; mati = semua alamat `/murid/latihan-harian...` 404 identik jalur tak dikenal dan tanpa kartu): anak memilih **kelas** sendiri (saran dari kelas di profil anak): Kelas 1-6 (bab Kurikulum Merdeka per kelas) atau Tantangan OSN Pemula (pengayaan P3-P4) / Lanjut (P5-P6). Satu sesi = 10 soal pilihan ganda 4 opsi dicampur dari beberapa bab kelas itu (+ maks 2 ulangan kelas bawah); jenis soal tanpa pembahasan atau yang tak bisa jadi PG 4 opsi sah dikeluarkan (audit `harian_tingkat.laporan_audit`). Setiap soal dinilai langsung: jawaban terkunci, lalu benar/salah + pembahasan; kunci dan pembahasan soal yang belum dijawab tidak pernah dikirim ke klien. Layar pilih kelas: maskot menyebut kelas saran (atau "Pilih kelasmu ya."), enam kartu kelas (grid 3 kolom, stiker "Saran") dan dua kartu Tantangan OSN bergaya navy berstiker "Pengayaan". Layar soal: info "Kelas N · Soal i dari 10", progres 10 kotak, pilihan besar A-D, tombol "Periksa jawabanku". Umpan balik hangat (betul = hijau "Betul!"; belum tepat = amber "Belum tepat, tidak apa-apa.", bukan merah) dengan satu maskot (pose mengikuti hasil beruntun dalam sesi itu: 3 betul berturut-turut = terkejut, 2 belum tepat berturut-turut = menyemangati, selain itu merayakan/memeriksa), status selalu berteks ("Jawabanmu", "Jawaban benar") dan kartu "Cara mengerjakannya". Ringkasan akhir = hero berkonfeti dengan skor besar "N dari 10 benar" dan titik terisi, tanpa peringkat. Batas: `akses_harian` (langganan/murid les tanpa batas; selain itu 1 sesi dikerjakan per hari WIB (dimulai ATAU dijawab hari itu: menyelesaikan sesi menggantung dari hari sebelumnya memakai jatah hari baru), sesi berjalan boleh dilanjutkan; habis = banner hangat "Hebat, latihan hari ini selesai!" plus kartu navy "Untuk Ayah/Bunda · lihat paket", harga "Rp39.000/bulan" dihitung dari konstanta paket; tombol tetap ke halaman orang tua, tanpa mengubah akses. Kartu ajakan yang sama muncul di ringkasan sesi hanya untuk anak yang belum tanpa batas; keduanya disembunyikan bila halaman orang tua tak tersedia (sakelar `DAFTAR_AKUN_ANAK` mati), tampilan saja bukan gerbang). Kartu di beranda murid (judul kelas, titik hari pekan ini, tombol koral; tanpa tautan ke halaman orang tua, beranda tetap punya satu) dan header sapaan beranda murid berupa hero teal tanpa maskot tambahan; ringkasan di halaman orang tua (hari latihan 7 hari, soal dikerjakan, persen tepat). Bukan bukti siklus belajar (tidak menulis/membaca sesi, diagnosis, `learning_cycle`).
- Admin mengelola **profil guru peninjau** (`/admin/profil-guru`): nama, latar, lama mengajar, urutan,
  tampil/tidak. Profil `tampil=1` dipakai kartu guru di halaman funnel dengan cache 30 detik; profil
  kosong = tanpa kartu. Perubahan dan hapus memakai tinjauan bertanda tangan + sandi ulang.
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
  Kontak hanya untuk orang dewasa pembayar demi penagihan (keputusan 6 Nov 2026), bukan
  kontak anak/orang tua murid. Satu-satunya kontak terstruktur: nomor WhatsApp per akun
  (`kontak_akun`, kunci `id_akun`, tanpa kunci ke data anak), wajib hanya pada pendaftaran
  jalur funnel (`/daftar?jalur=cek`, di balik `FUNNEL_AKTIF`, bawaan mati) dan dilengkapi akun lama
  lewat `/akun/kontak` (guru). Tidak tampil ke murid/tautan; retensi 12 bulan sejak aktivitas
  terakhir akun (sapuan belum dijadwalkan). Hapus keluarga memerlukan verifikasi,
  preview/backup/cutover; bukan sekadar menghapus login atau bukti immutable.
- Halaman publik funnel `/cek-kemampuan` dan `/paket-coba` (Fase 1) ada di balik `FUNNEL_AKTIF` (bawaan
  mati: halaman "belum dibuka"). Sejak 20 Nov 2026 beranda `/` untuk pengunjung anonim memakai landing
  `/cek-kemampuan` yang sama saat `FUNNEL_AKTIF` hidup; saat mati `/` kembali ke landing lama (guru/admin login
  tetap ke berandanya). Sejak 19 Nov 2026 (Keputusan 19) `/cek-kemampuan` bergaya playful (bagian cerita statis,
  demo tebak langkah, satu CTA; bagian harga hanya hasil gratis, tawaran Rp49.000 ada di halaman hasil dan FAQ) dan `/contoh-peta-kemampuan` menampilkan laporan Peta Kemampuan playful dengan data
  sintetis konsisten (skor/kategori `cek_gratis_skor`, Kuat ≥80%, <3 soal "Belum cukup soal", pola = jumlah salah)
  plus lembar A4 1 halaman `/contoh-peta-kemampuan/lembar`. Sejak 21 Nov 2026 (Keputusan 20) tab "Misi berikutnya" menampilkan harga kelas (Rp200.000 per bulan, 8 pertemuan; hanya tampilan, belum ada tagihan kelas) dan menaruh cek ulang minggu ke-4 sebagai bagian kelas; halaman publik tetap tanpa harga kelas. Peringkat/persentil DITAMPILKAN (`peta_posisi`: pembanding
  kelas sama, minimal 30 anak, selalu dengan penyebut); laporan nyata pesanan berbayar, isian Guru, dan agregat
  skor per kelas belum dibangun. Fase 2: cek gratis per anak di `/cek-kemampuan/mulai` (centang persetujuan wajib,
  tersimpan), `/hasil`, `/tautan` (peran guru; anak mengerjakan lewat `/mulai/<token>` yang ada); sesi biasa PG 15 soal
  (`tujuan='bebas'`, bukan bukti siklus). Pendaftaran jalur cek mewajibkan kelas. Halaman siap mulai menawarkan
  "Kerjakan di HP ini" (`cara=hp_ini`: sesi login dihapus di server, lalu anak dibawa ke tautan) atau "Di HP/tablet anak"
  (QR); cek berjalan dilanjutkan lewat `/tautan` dengan status X/15. Untuk sesi cek (dan hanya saat `FUNNEL_AKTIF`),
  `/mulai/<token>` memakai tampilan anak khusus: satu soal per layar, jeda regang setelah soal 5 dan 10, peta soal,
  Kumpulkan, layar Hore berbasis usaha (jumlah soal dijawab, tanpa benar/salah/skor); sesi biasa tak berubah. Topik cek
  mengikuti kelas (kelas 3: berhitung sekolah, geometri datar, statistika; 4: berhitung sekolah, pengukuran, geometri datar;
  5–6: aritmetika dasar, aritmetika lanjut, geometri datar; 1–2: bilangan dasar), 5 soal per topik; nama materi boleh tampil
  di layar anak (hanya nama, bukan label kemampuan). Orang tua
  kembali lewat `/masuk?lanjut=/cek-kemampuan/hasil` (allow-list persis dua rute cek, peran guru). Hasil gratis hanya skor (benar/15), kategori, ringkasan nama topik (label awam dari `topik_awam`; hasil lama tersimpan dipetakan saat render), berlabel "belum
  ditinjau guru". **Pengecualian bercakupan sempit** atas larangan skor/persentase di laporan orang tua (Keputusan 17): skor cek
  dihitung di `cek_gratis` dan tidak lewat `parent_report_snapshot`. Bahan mentah dihapus 30 hari setelah selesai (sapuan
  `sapu_cek_gratis` dijadwalkan harian lewat `cek_retensi.py` + cron host); turunan tetap selama akun aktif. Akun funnel tetap akun guru biasa, jadi halaman guru
  yang ada (mis. `/sesi/<id>`) tetap terjangkau; bagian "terkunci" hanya berlaku di halaman hasil cek.
- Fase 3 (Paket Coba sekali bayar Rp49.000, kode selesai, **belum aktif**): guru yang cek anaknya sudah selesai dan punya WhatsApp
  bisa memesan lewat `/paket-coba/pesan` dan memantau di `/pesanan` (QR QRIS via Midtrans, jendela bayar bisa dibuka ulang
  sampai batas). Nominal selalu konstanta server; status lunas hanya dari ledger yang diisi provider (callback atau periksa
  server-ke-server), tidak dari URL/form. Pembayaran hanya hidup bila tiga syarat terpenuhi: `FUNNEL_AKTIF`, sakelar pembayaran
  efektif, dan tahap `checkout`; selain itu halaman status jujur/404 dan POST tanpa efek. Admin memantau di `/admin/pesanan`
  (daftar minimal, periksa status, catat refund manual; tanpa API refund). Belum ada worker rekonsiliasi; kebijakan refund dan
  hapus keluarga vs catatan keuangan menunggu keputusan Pemilik.
  Jalur transfer rekening (verifikasi manual admin, **belum aktif**): bila `PESANAN_TRANSFER_AKTIF=1`, funnel aktif, runtime produksi ada,
  dan admin sudah mengisi rekening, `/pesanan` menawarkan "Bayar lewat transfer" (nominal Rp49.000 + kode unik, harus persis) dan
  unggah bukti (JPEG/PNG/PDF, maks 5 MB, maks 5 bukti); QRIS tampil sebagai pilihan kedua bila Midtrans juga terbuka. Status
  `menunggu_verifikasi`/`ditolak`; lunas hanya setelah admin menyetujui. Admin memverifikasi di `/admin/pesanan` (tab Menunggu
  verifikasi, pratinjau bukti, setujui atau tolak dengan alasan, sandi ulang) dan mengisi rekening di `/admin/pesanan/rekening`; guru dapat
  membuka waktu pembayaran baru (maks 5 jendela) bila waktu habis tanpa bukti dan Midtrans tertutup. Satu akun hanya boleh punya satu
  pesanan menunggu verifikasi; admin melihat penanda "Menunggu > 72 jam", "Dibayar lewat dua jalur" (QRIS + transfer, cek refund), dan
  peringatan bila berkas bukti identik muncul di order lain. Bukti dihapus 30 hari sesudah keputusan lewat CLI operator dan tidak ikut backup.
- [Backup operasional](operational-backup.md) manual mencakup core, riset dan foto;
  scheduler/off-site otomatis belum tersedia, bukan janji pemulihan seluruh VPS.

## Batas dan keputusan

Batch katalog aktif dan bank kalimat tidak mengesahkan seluruh katalog. Revisi
penilaian1/pilot bank dan [draf koreksi lanjutan2](catalog-followup.md) tetap
offline/default0; playbook masih draf; efektivitas
pada guru/anak belum dibuktikan. Pancingan dan tiga playbook `berhitung-sekolah` yang
live 15 Nov 2026 masih **draf belum direview manusia**, dan pemetaan terpandu P3
bergeser karena topik baru (tiga pola keluar, tiga masuk) atas pilihan pemilik —
bukan hasil ulasan guru. Tidak menjanjikan siap juara atau penguasaan seluruh
kurikulum. Pekerjaan [dibatalkan/ditunda](status-proyek.md) tidak dibuka otomatis.

Acuan: [playbook](playbook-guru.md) · [Pendamping](pendamping-runtime.md) ·
[paket](subscription-packages.md) · [privasi/dukungan](support-operations.md) ·
[aturan proyek](../CLAUDE.md). Perubahan cakupan harus memperbarui ringkasan ini
bersama kontrak detail; status operasi dicatat terpisah di runbook rilis.
