# Paket Jago dan Jago Pro — kontrak versi 2

Keputusan produk: **27 September 2026**, disetujui pengguna. Dokumen ini menggantikan
rancangan penawaran v1 untuk penjualan baru setelah aktivasi v2; **bukan bukti bahwa
checkout, masa coba otomatis, kuota paket, atau refund sudah aktif**. Tidak memberi
izin mengubah invoice/grant lama atau mengaktifkan kampanye tanpa tanggal.

## 1. Status dan sumber kebenaran

| Lapisan | Status saat keputusan |
| --- | --- |
| Keputusan harga/fitur di dokumen ini | Disetujui |
| Ledger, checkout, rekonsiliasi produksi | Masih kontrak v1, bulanan per profil |
| Masa coba otomatis dari pendaftaran | Belum aktif (`CUTOFF_AKTIVASI=None`) |
| Paket v2, tahunan, kuota AI per paket | Belum terintegrasi |
| Refund tahunan 7 hari | Kebijakan baru, belum alur aplikasi |
| Pembukaan kampanye promo v2 | Tanggal dan mekanisme eligibility belum ditetapkan |

Katalog kode v2 harus menjadi sumber angka bagi penawaran baru dan rendering.
Ledger v1 tetap memakai [kontrak historis](subscription-foundation.md). Aturan yang
dibekukan pada invoice/grant tidak mengikuti perubahan katalog di kemudian hari.
Status rilis exact ada di [runbook produksi](production-release.md).

## 2. Coba Gratis untuk semua member

- Bukan paket Free permanen: **Rp0 selama 30 × 24 jam, satu kali per akun**.
- Semua member pelanggan memperoleh masa coba, bukan hanya peserta kampanye promo.
  Admin/internal bukan akun pelanggan dan tidak ikut otomatis.
- Mencakup **1 profil anak**, seluruh fitur belajar inti, **10 balasan Pendamping AI
  dan 2 pembacaan foto** untuk seluruh masa coba (tidak diisi ulang harian/bulanan).
- Aktif sejak aktivasi enrollment yang berhasil dan durable; replay receipt tidak
  memundurkan/mengulang waktu awal. Pendaftaran sebelum pembukaan tidak boleh
  diam-diam menghabiskan masa coba tanpa pemberitahuan/aktivasi transisi.
- Berakhir pada deadline eksklusif. Pengguna memilih paket dan membayar sendiri;
  tidak ada debit otomatis. Pembayaran di muka tidak memangkas sisa masa coba.
- Ganti paket, berhenti, refund, dan berlangganan kembali tidak mengulang masa coba.
- Akun lama ditransisikan eksplisit. Hak berbayar yang masih berjalan tidak dipotong,
  profil/data tidak dihapus, dan trial yang sudah dipakai tidak diulang. Urutan transisi
  untuk akun lama harus dipreview sebelum perubahan data, bukan backfill dari GET.
- Akses setelah trial habis harus dijelaskan sebelum aktivasi penegakan. Login,
  pembayaran, bantuan, pengelolaan privasi/data tidak boleh diblokir oleh paywall.

## 3. Harga yang disetujui

Harga rupiah total untuk **1 profil anak**, termasuk pajak bila berlaku; bukan faktur
pajak. Dua periode pembayaran untuk fitur yang sama, tanpa tier fitur khusus tahunan.

| Paket | Bulanan normal | Bulanan promo | Tahunan normal | Tahunan promo |
| --- | ---: | ---: | ---: | ---: |
| **Jago** | Rp29.000 | **Rp25.000** | Rp290.000 | **Rp250.000** |
| **Jago Pro** | Rp59.000 | **Rp49.000** | Rp590.000 | **Rp490.000** |

- Tahunan dibayar **sekaligus di muka untuk 12 bulan kalender**, bukan cicilan atau
  365 hari tetap. Bulanan memakai 1 bulan kalender. Tanggal/jam jangkar memakai WIB;
  akhir bulan dan 29 Februari dijepit ke hari valid tanpa kehilangan jangkar asli.
- Tahunan normal maupun promo setara harga 10 bulan pada tarif bulanan yang sama:
  hemat **16,7% dibanding 12 pembayaran bulanan dengan tarif yang sama**. Ini bukan
  perbandingan terhadap skenario bulanan campuran promo3bulan + normal9bulan.
- Promo tahunan setara sekitar **Rp20.833/bulan (Jago)** atau **Rp40.833/bulan (Pro)**;
  tampilkan total tahunan lebih utama dan beri tanda perkiraan. Jangan menagih angka
  ekuivalen yang sudah dibulatkan sebagai 12 transaksi terpisah.
- Profil pertama termasuk. Tambahan **Rp10.000/profil/bulan** atau
  **Rp100.000/profil/tahun**, sama untuk kedua paket, normal maupun promo.
  Diskon promo tidak diterapkan lagi pada tambahan profil.
- Contoh 3 profil: Jago promo Rp45.000/bulan atau Rp450.000/tahun; Pro promo
  Rp69.000/bulan atau Rp690.000/tahun. Jangan menyebut harga dasar sebagai total
  tagihan bila profil lebih dari satu.
- Model ini bukan tarif grosir tutor/sekolah. Batas jumlah profil yang dijual dan
  perubahan cakupan di tengah masa bayar perlu kontrak checkout eksplisit.

## 4. Pembeda fitur dan kuota

| Fitur | Coba Gratis | Jago | Jago Pro |
| --- | --- | --- | --- |
| Latihan, pembahasan, lembar cetak | Ya | Ya | Ya |
| Tinjauan hasil, rencana terpandu, peta penguasaan, laporan | Ya | Ya | Ya |
| Profil termasuk | 1 | 1 | 1 |
| Balasan Pendamping AI | 10 selama trial | Tidak termasuk | 50 per bulan layanan |
| Pembacaan foto dengan AI | 2 selama trial | Tidak termasuk | 5 per bulan layanan |

Kuota akun **dipakai bersama seluruh profil**, bukan dikalikan jumlah anak.
Kuota Pro diperbarui setiap bulan layanan pada jangkar grant, termasuk pembayaran
tahunan; tidak diberikan sekaligus setahun dan tidak diakumulasikan ke bulan berikut.
Setiap foto berarti satu operasi pembacaan satu lampiran gambar yang diterima, bukan
janji jumlah soal yang pasti berhasil dikenali. Satu balasan berarti satu keluaran
Pendamping yang berhasil diterima aplikasi, bukan satu token atau satu percakapan.

Invariant implementasi kuota: reserve sebelum jaringan, serial/atomic antar tab,
operation ID durable, replay sukses tidak menghabiskan jatah lagi. Kegagalan validasi
sebelum provider tidak mengonsumsi kuota; unknown setelah pengiriman tidak boleh
membebaskan reservasi untuk pemanggilan kedua sampai direkonsiliasi. Biaya provider
untuk hasil gagal tetap terpisah dari kuota layanan yang diperoleh pelanggan.

Izin penggunaan AI, kepemilikan, kebijakan data, batas biaya global/provider dan
peninjauan hasil tetap berlaku. Habis kuota AI tidak mencabut fitur belajar inti.
Teks soal standar/generator tidak boleh menjadi berbayar per panggilan AI. Fitur
parafrase cerita AI yang sudah ada belum ditetapkan sebagai bonus paket baru; jangan
mengiklankan AI tanpa batas atau membuka bypass kuota lewat jalur tersebut.

## 5. Promo peluncuran

- Semua member mendapat trial; **tidak berarti semua member mendapat harga promo**.
- Peserta promo bulanan: **3 periode berbayar pertama**, lalu tarif normal.
- Peserta promo tahunan: **tahun berbayar pertama**, lalu tarif tahunan normal.
- Ini dua alternatif, bukan diskon ditumpuk. Tidak ada diskon tahunan tambahan lagi
  terhadap harga tahunan promo di tabel.
- Keikutsertaan, versi kampanye dan penggunaan promo melekat pada akun, bukan nama
  paket, sehingga mengganti Jago/Pro tidak mereset promo.
- Tanggal pembukaan, penutupan, dan eligibility kampanye v2 belum ditetapkan.
  Batas100akun/8minggu v1 adalah histori, **bukan otomatis keputusan kampanye v2**.
- Kebijakan promo ketika pindah bulanan↔tahunan sesudah sebagian promo terpakai belum
  diputuskan. Sampai diputuskan, operasi tersebut harus ditahan dengan pesan jelas;
  jangan memberi jatah promo baru atau mengurangi hak periode berjalan diam-diam.
- Refund tidak mengembalikan jatah promo secara otomatis. Keputusan penghitungan
  entitlement setelah refund harus tercatat, bukan menghapus invoice/grant historis.

## 6. Tahunan: pengembalian dana 7 hari

Kebijakan ini adalah **garansi pengembalian dana**, bukan batas waktu boleh berhenti
memperpanjang. Berlaku juga untuk pembayaran perpanjangan tahunan.

- Pengajuan dalam **7 × 24 jam sejak pembayaran berhasil**, deadline eksklusif.
  Timestamp settlement tepercaya yang dibekukan menjadi acuan, bukan waktu callback
  diterima atau tombol Periksa diklik. Bila waktu bukti belum dapat diverifikasi,
  kasus ditinjau; jangan menolak pelanggan berdasarkan timestamp buatan.
- Refund penuh maksimum **nominal yang benar-benar dibayar**, termasuk tambahan profil
  dalam invoice tahunan tersebut, bukan harga normal sebelum diskon.
- Batas7hari adalah batas pengajuan, bukan janji durasi dana kembali. Pemrosesan
  manual mengikuti jurnal admin dan bukti provider/bank; tidak ada pengiriman dana
  otomatis hanya karena eligibility terpenuhi.
- Setelah refund terbukti selesai, cabut hanya hak yang berasal dari pembayaran
  terkait. Grant lain/trial yang sah tidak dicabut; data belajar tidak otomatis dihapus.
- Setelah7hari, pembatalan biasa tidak mendapat refund prorata dan akses tetap sampai
  akhir masa bayar. Pengecualian untuk kegagalan layanan, sengketa, atau kewajiban hukum
  tetap ditinjau; ketentuan ini tidak mengurangi hak konsumen yang wajib dipenuhi.
- QRIS saat ini membutuhkan pembayaran baru untuk memperpanjang, bukan debit otomatis.
- Duplikasi pembayaran, nominal salah, settlement terlambat, chargeback/refund khusus
  tetap memakai [penanganan insiden finansial](pembayaran-produksi.md), bukan dipaksa
  masuk kebijakan pembatalan biasa. Horizon rekonsiliasi7hari bukan jendela refund.

## 7. Transisi, penyimpanan, dan fail-closed

**Jangan mengganti `subscription.harga()` atau CHECK tarif v1 dengan angka v2.**
Snapshot v1 harus tetap terbaca, dapat direkonsiliasi/refund, dan cocok dengan backup.
Paket/periode/versi tarif/promo/cakupan/nominal/tanggal grant baru harus dibekukan
bersama invoice, bukan diambil dari pilihan browser saat settlement atau dari katalog
terbaru ketika membaca histori.

Mekanisme v2 terhubung baru setelah migrasi aditif melalui lifecycle admin existing,
reader/validator/backup/recovery mengenali kedua versi, serta uji pair exact lulus.
Tidak ada DB baru atau migrasi saat GET. Unknown version/rusak → belum terverifikasi,
bukan Jago gratis, Pro, atau trial baru. Entitlement harus ditegakkan server-side di
jalur sebenarnya, bukan dengan menyembunyikan tombol.

Aktivasi kampanye, penegakan, pemberian masa coba akun lama, dan migrasi state tidak
terjadi melalui perubahan landing. UI sebelum integrasi tetap berlabel **penawaran
belum dibuka**, dengan harga sebagai rencana dan tanpa CTA yang menjanjikan trial aktif.

## 8. Urutan eksekusi dan acceptance

1. Dokumen ini dan rujukan terkait diperbarui sebelum kode.
2. Katalog/domain v2 murni + tes harga, kalender, jendela kuota/refund dan batas negatif;
   v1 tetap identik. Landing rencana memakai sumber angka katalog yang sama.
3. Snapshot/ledger aditif + service/checkout/admin + callback/worker/backup/recovery.
4. Enrollment/transisi, guard akses dan kuota AI lintas restart/tab, serta request dan
   pemenuhan refund append-only. Pilihan browser bukan sumber harga/otorisasi.
5. UI publik/akun/admin diuji sintetis desktop/mobile, tanpa dependency atau JS baru.
6. Full pytest warning-error/kompilasi/probe/pair/mutation guard keuangan dan kepemilikan
   relevan pada exact artifact di CI. Backup4DB+auth, rehearsal idempoten/FK, verifikasi
   target dan rollback/recovery sebelum aktivasi produksi. Jangan build di VPS.

Batas implementasi harus dilaporkan per tahap: katalog tersedia bukan checkout siap;
checkout siap bukan kampanye aktif; kampanye aktif bukan bukti pembayaran berhasil.
