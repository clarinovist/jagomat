# Fondasi langganan (belum aktif)

Implementasi ini **bukan pembayaran/paywall live**. Tidak ada perubahan landing,
checkout, callback publik, countdown, enrollment/backfill akun nyata, atau gate
latihan/Pendamping. Semua `subscription.SAKELAR` default OFF, tidak membaca env.
Tidak ada SDK, dependency atau JavaScript baru.

## Batas modul

- `mesin/subscription.py`: domain provider-neutral, clock epoch UTC wajib diinjeksi,
  tanggal jangkar bulanan WIB, trial tepat 30×24 jam/deadline eksklusif, harga per
  profil tercakup dan status akses terpisah dari invoice.
- `mesin/subscription_store.py`: ledger privat di `admin-control.db`. API belum
  terhubung ke HTTP/auth/registrasi. ID akun stabil harus berasal principal/service;
  resolver pemilik profil wajib diinjeksi, bukan percaya hidden input. Integrasi
  atomik lintas DB belajar/auth belum diklaim tersedia.
- `mesin/subscription_schema.py`: migrasi additive admin5→6 melalui satu lifecycle
  `admin_store.siapkan`; hanya schema dan versi tarif, tanpa tanggal kampanye,
  enrollment, invoice, receipt atau grant otomatis. Pekerjaan KPI berikutnya harus
  melanjutkan schema6, bukan membuat migrasi independen dari baseline5.
- `mesin/midtrans_contract.py`: payload QRIS minimal tanpa customer_details/kontak/
  data anak, Basic auth tanpa logging/repr key, binding status dan signature callback
  constant-time. Transport wajib diinjeksi; **tidak ada transport jaringan default**.
  Transport kontrak menerima `allow_redirects=False`, timeout dan bounded read;
  respons HTTP non200, URL berubah, JSON duplikat/besar/rusak tidak memberikan bukti.

## Ledger dan keputusan tetap

Tabel terpisah: aturan/tarif, kampanye, enrollment, cakupan, invoice, receipt,
grant dan pengamatan rekonsiliasi. Tidak memakai audit_admin, kejadian_belajar atau
JSON auth sebagai ledger. Reader `ro` tidak membuat DB/tabel; missing/stale/rusak
menghasilkan kegagalan jujur, bukan expired atau grant gratis.

- Harga n=1/2/3: promo Rp15.000/20.000/25.000; lanjutan Rp35.000/45.000/55.000.
  Tiga periode **dibayar**, bukan tiga bulan sejak daftar; jeda tidak reset promo.
- Kampanye delapan minggu, kuota100 publik baru, akun lama eksplisit terpisah.
  Tanggal aktivasi tidak memiliki nilai default. Admin/internal tidak ikut otomatis.
- Invoice membekukan profil/tarif/provider/merchant/key. Unique akun+urutan mencegah
  dua invoice periode sama. Key maksimum46 dan durable lokal tanpa TTL lima menit.
- Perubahan cakupan efektif periode berikutnya. Jika quote belum diselesaikan sudah
  membekukan periode, perubahan ditolak untuk rekonsiliasi—tidak menebak kebijakan
  quote stale/pembayaran di muka. Nol profil tidak membuat charge.
- Receipt+grant satu transaksi `BEGIN IMMEDIATE`; restart/replay mengembalikan hasil
  asli. Unique sumber provider+transaksi lintas invoice/akun. Invoice lunas historis
  bukan hak akses abadi; pending tidak mencabut grant yang sudah ada.
- Catatan append-only, termasuk pengamatan dengan referensi baru; update/delete/
  replace ditolak trigger, unique dan linkage diperiksa saat pembacaan/recovery.
- Kasus settlement terlambat/pembayaran kedua menyimpan receipt `perlu_diperiksa`,
  tanpa grant kedua atau memilih kebijakan refund/revoke/promo. Refund helper hanya
  menormalisasi identitas unik, snapshot kumulatif dan delta bank-confirmed, bukan
  operasi refund. Tidak ada expiry invoice bawaan yang dianggap keputusan produk.
- Pajak snapshot `belum_ditetapkan`: bukan “bebas PPN”, bukan pemungutan PPN atau
  checkout total final. Tidak ada purge/retensi billing otomatis.

Sakelar `fondasi`, `buat_pembayaran`, `rekonsiliasi`, `penegakan` terpisah. Tes boleh
menginjeksikan ON pada storage/transport sintetis; aplikasi tidak melakukannya.
Analytics/consent, login, sandi dan perangkat bukan input entitlement.

## Backup, CI dan batas recovery

Bundle tetap empat DB + auth. Validator/rehearsal admin6 mencakup struktur, linkage
invoice/receipt/grant, preservasi row dan FK/integrity. Bundle berisi invoice memberi
`perlu_rekonsiliasi=true`: restore bukan izin langsung create charge; transaksi
setelah cutoff tetap harus direkonsiliasi pada fase operasional berikutnya.

Metadata memakai mode existing **persiapan/build-only**, pin recovery admin5 tetap.
Verifier historis hanya menerima kontrak admin5 untuk SHA explicit; kandidat wajib
admin6 + `subscription_checks=4`. Proof pair baru wajib
`subscription_pair_checks=4` selain seluruh proof sebelumnya. Reader admin5 ditolak
untuk ledger admin6, tidak dilonggarkan. Tes reader admin6 pada salinan source bukan
bukti pair image kompatibel. Manifest build-only melaporkan mismatch dan
`pair_verified=false`, `siap_pasang=false`. Job `pasang` tetap literal false.

Sebelum rilis/aktivasi: putuskan D8/D9/batas AI/tanggal, adapter otorisasi dan lifecycle
registrasi, kontrak transaksi lintas store, sandbox/UX/merchant no-contact, baseline
recovery kompatibel + pair exact digest, bundle coherent/rehearsal dan rekonsiliasi
cutoff. Jangan downgrade schema, hapus ledger, atau memakai binary admin5 sebagai
fallback setelah admin6 dipakai. Tugas fondasi tidak melakukan deploy/SSH/migrasi data
pengguna maupun transaksi Midtrans sandbox/produksi.

## Verifikasi yang dapat diulang

Scoped: `test_subscription*.py`, `test_midtrans_contract.py`, serta test admin store,
backup, deployer/readiness, image/probe/pair/metadata dan CI yang terdampak. Mutation
memodifikasi salinan source temp, memanggil regression yang sama, memeriksa sebab
merah invariant dan memulihkan hijau. Socket/DNS pada test Midtrans selalu dilarang;
semua request memakai fake transport. Full suite warning-error dan kompilasi lewat
CI Python3.12; lokal kompatibel Python3.9. Tidak memerlukan Docker lokal.
