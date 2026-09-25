# Fondasi langganan (belum aktif)

Implementasi ini **bukan pembayaran/paywall live**. Tidak ada perubahan landing,
checkout, callback publik, countdown, enrollment/backfill akun nyata, atau gate
latihan/Pendamping. Semua `subscription.SAKELAR` default OFF, tidak membaca env.
Tidak ada SDK, dependency atau JavaScript baru.

## Adapter sandbox opt-in

`mesin/midtrans_sandbox.py` menyediakan `TransportSandbox(config)` untuk injeksi
ke kontrak Midtrans, **bukan caller aplikasi**. Konfigurasi harus sandbox; host
HTTPS dikunci ke `api.sandbox.midtrans.com`, TLS diverifikasi, request harus persis
payload minimal kontrak. Tidak ada env/key default, proxy, redirect atau retry.
Timeout socket dan tenggat pembacaan diterapkan, body dibatasi 128 KB; error tidak
menampilkan kredensial. Resolver DNS/platform dan pembacaan header HTTP masih
mengikuti perilaku stdlib: bukan jaminan deadline wall-clock absolut setiap fase.
Caller tetap wajib menyimpan intent dan query order sama jika create tidak pasti.

Uji manual 25 September 2026, terpisah dari pytest dan DB aplikasi: satu QRIS
sintetis Rp15.000 berhasil dibuat tanpa customer_details/kontak. GET status awal
pending; setelah simulator resmi Midtrans, GET terautentikasi memberi settlement
dan binding order/transaction ID/merchant/nominal/IDR/QRIS lolos. Tidak memakai
saldo nyata, mengirim key ke simulator, atau membuat receipt/grant aplikasi.
Key merchant tidak dilacak; berkas lokal `/midtrans.rtf` di-ignore.

Ini membuktikan create/status sandbox dan simulator, **bukan** pembayaran produksi,
UX satu HP, callback publik, enrollment, atau checkout aplikasi live. Adapter HTTP
opt-in berikutnya tersedia melalui `mesin/subscription_preview.py`: launcher hanya
loopback, membuat auth/sesi/DB/profil baru sintetis, meminta key via input tersembunyi,
dan memasang `subscription_http.RuntimeSandbox` yang tidak ada pada `serve.py` biasa.
Tanpa runtime exact/path state preview, `/langganan` selalu404 dan tautan akun tidak
muncul. QR diproksi same-origin; alamat transaksi sandbox untuk simulator boleh tampil,
tetapi Server Key/Authorization/ID akun tidak dikirim ke browser. GET status hanya
menampilkan hasil provider; settlement baru dicatat oleh POST bertoken dan tetap
melalui revalidasi sesi/principal/pemilik sebelum grant. Sakelar aplikasi global
tetap OFF; D8/D9, kontrak merchant dan gate aktivasi tetap berlaku. QR sandbox hanya
boleh dibayar melalui [simulator resmi](https://docs.midtrans.com/docs/testing-payment-on-sandbox),
jangan memakai aplikasi bank/e-wallet bersaldo nyata.

## Lanjutan service terisolasi

`mesin/subscription_service.py` membaca receipt registrasi actual dan memvalidasi
principal hidup/revisi/alias, cutoff eksplisit serta pemilik profil. Enrollment
tertunda mengikuti urutan receipt publik, bukan urutan retry. Data auth/belajar tidak
ditulis oleh service; kegagalan sinkron dipulihkan dari receipt sukses yang sama.
Belum ada caller HTTP/startup/scheduler dan tidak ada backfill yang dijalankan.

Intent create disimpan atomik pada metadata rekonsiliasi sebelum fake transport.
Crash/timeout/restart memeriksa order lama, bukan create kedua. Transport di luar
lock; sesudahnya principal/pemilik diperiksa ulang sebelum receipt/grant. Urutan
fencing DB→auth→ledger mengikuti lifecycle existing. Bukan transaksi atomik lintas
DB/auth atau pembayaran jaringan nyata. Reset/alias baru tidak mewarisi grant.

Pair ditambah: writer menyimpan intent serta registrasi committed belum enrolled;
reader menyinkronkan receipt, query settlement dan replay sambil melestarikan auth/
belajar. Kandidat memiliki wrapper `subscription_registration.py` yang tidak ada
pada recovery; wrapper belum dihubungkan web. Akun committed tetapi sink gagal
memberi `belum_terverifikasi`, bukan menghapus akun atau mengulang t0.

Baseline service `4c88dc956b33ae6246b6f7b15f54e87e6c8f172a` telah lolos
[CI35995276357](https://github.com/clarinovist/jagomat/actions/runs/35995276357),
11.708 test, build/probe. Kandidat mematok baseline tersebut pada mode `migrasi`
agar pair exact digest wajib; pasang tetap literal false. Mode ini bukan izin
migrasi/deploy produksi atau aktivasi switch.

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

Metadata kini memakai mode existing **migrasi**, recovery service admin6 pinned.
Verifier historis hanya menerima kontrak admin5 untuk SHA explicit; kandidat dan
recovery baru wajib admin6 + `subscription_checks=4`. Proof pair wajib
`subscription_pair_checks=4` selain seluruh proof sebelumnya, mencakup service
registrasi/intent/query/replay. Reader admin5 historis tetap ditolak, bukan dilonggarkan.
Uji source memakai arsip Git baseline pinned; kelulusan image tetap menunggu pair
exact digest CI. Job `pasang` literal false dan `siap_pasang=false` meski pair lulus.

Sebelum rilis/aktivasi: putuskan D8/D9/batas AI/tanggal, adapter otorisasi dan lifecycle
registrasi, kontrak transaksi lintas store, sandbox/UX/merchant no-contact, baseline
recovery kompatibel + pair exact digest, bundle coherent/rehearsal dan rekonsiliasi
cutoff. Jangan downgrade schema, hapus ledger, atau memakai binary admin5 sebagai
fallback setelah admin6 dipakai. Tugas fondasi tidak melakukan deploy/SSH/migrasi data
pengguna maupun transaksi Midtrans sandbox/produksi.

## Verifikasi yang dapat diulang

Scoped: `test_subscription*.py`, `test_midtrans_contract.py`,
`test_midtrans_sandbox.py`, `test_subscription_http.py`,
`test_subscription_preview.py`, serta test admin store, backup, deployer/readiness,
image/probe/pair/metadata dan CI yang terdampak. Mutation
memodifikasi salinan source temp, memanggil regression yang sama, memeriksa sebab
merah invariant dan memulihkan hijau. Socket/DNS pada test Midtrans selalu dilarang;
kontrak memakai fake transport, adapter memakai koneksi HTTP palsu. Uji jaringan
manual tidak dimasukkan dalam pytest/CI dan tidak membaca data pengguna. Full suite
warning-error dan kompilasi lewat CI Python3.12; lokal kompatibel Python3.9. Tidak memerlukan Docker lokal.
