# Runtime produksi pembayaran (source siap, belum aktif)

Lanjutan [fondasi langganan](subscription-foundation.md) untuk tiga hal yang tertunda:
runtime produksi eksplisit, callback durable, dan rekonsiliasi terjadwal. Source dan tes
ada; **pembayaran tetap belum aktif**: tier Admin belum pernah dinaikkan, tidak ada secret
terpasang, dan job `pasang` tetap literal false. Dokumen ini menjelaskan kontraknya, bukan
klaim bahwa collection berjalan.

## Batas yang dipatok

Modul baru: `midtrans_secret.py`, `midtrans_produksi.py`, `subscription_produksi.py`,
`subscription_callback.py`, `subscription_worker.py`, dan `scripts/rekonsiliasi_langganan.py`.
Tidak ada tabel/schema baru, tidak ada migrasi, dan `serve.py` tidak disentuh — kontrak
persistensi yang dipakai pair recovery (baseline admin7) tetap utuh. Dispatch callback
ditambahkan di `web.py` pada path persis, sebelum router langganan existing.

## Berkas rahasia server (mounted secret)

Server Key hanya dibaca dari berkas privat di host/container: default
`/run/secrets/midtrans/produksi-rahasia`. Kontraknya diperiksa tiap pemakaian:

- regular file, bukan symlink (`O_NOFOLLOW`), pemilik = proses, izin tanpa bit group/other;
- ukuran 1 byte sampai 4 KB, ASCII printable, tanpa kontrol karakter;
- grammar dua baris eksplisit `merchant=...` dan `server_key=...` (tanpa duplikat/kunci lain);
- kunci berprefix sandbox (`SB-`) ditolak untuk produksi; tidak ada default dan tidak ada
  fallback sandbox↔produksi;
- nilai tidak pernah muncul di pesan galat, `repr`, log, respons, audit, atau argumen proses.

Merchant ID dan environment terikat konfigurasi server itu (`Konfigurasi("production", ...)`),
bukan input HTTP, bukan DB, bukan panel Admin. Panel Admin hanya boleh menampilkan status
readiness; ia tidak membaca atau mengubah berkas ini.

## Runtime dan readiness

`subscription_produksi.runtime()`/`pasang()` fail-closed: berkas hilang, izin longgar, symlink,
isi rusak, atau kunci sandbox → `None`/`False` dan runtime tidak dipasang, sehingga sakelar
efektif tetap OFF dan permukaan pembayaran melaporkan belum siap (bukan akses gratis).
Readiness dihitung dari runtime/artefak, bukan checkbox:

| Kunci | Sumber | Arti |
| --- | --- | --- |
| `provider_produksi` | secret tervalidasi + transport produksi | kunci server tepercaya terbaca |
| `callback` | permukaan callback ada di image | notifikasi provider dapat diterima |
| `recovery` | artefak pair deployer `/run/secrets/midtrans/recovery-pair.json` | pasangan recovery terverifikasi |
| `kebijakan` | konstanta `KEBIJAKAN_D8_D9 = True` (keputusan 26 Sep 2026) | D8/D9 sudah diputuskan pengguna (lihat bagian keputusan) |

`sakelar_efektif()` memakai tangga yang sama dengan permukaan Admin (parity diuji):
`rekonsiliasi` butuh provider siap; `buat_pembayaran` butuh callback + recovery; `penegakan`
butuh `kebijakan`. Selama `kebijakan` false, tahap produksi tidak bisa benar-benar dibuka —
dan penurunan tahap saat insiden tetap boleh meski provider/callback sedang rusak.

Transport `midtrans_produksi.TransportProduksi` hanya menerima host `api.midtrans.com`,
konfigurasi `production`, request kanonik, TLS terverifikasi, tanpa redirect/retry, dan hanya
membaca respons bounded `application/json`. Merender QR produksi belum dipakai fase ini.

## Callback `POST /midtrans/callback`

Endpoint publik tanpa login, dan sengaja sempit:

- hanya `POST` ke path persis (tanpa query); `GET` → 404 identik, metode lain tidak dilayani;
- `Content-Type: application/json`, body 1..8192 byte, `Content-Length` wajib angka; JSON
  duplikat/rusak/UTF-16/terlalu besar ditolak; payload mentah tidak disimpan;
- request yang membawa `Origin`, `Referer`, `Sec-Fetch-*`, `Cookie`, atau `Authorization`
  ditolak 403: itu bukan kontrak server-to-server provider;
- signature SHA512 dihitung constant-time terhadap Server Key server, lalu field wajib
  (`order_id`, `status_code` 3 digit, `transaction_status`, `transaction_id`) dan binding
  `merchant_id`/`IDR`/`payment_type=qris` diperiksa; pelanggaran apa pun → 403 seragam;
- order yang tidak dikenal → 200 tanpa menulis apa pun (tidak ada invoice, enrollment,
  receipt, grant, atau transaksi baru);
- yang tersimpan hanya petunjuk deterministik `cbk_<32 hex>` di `langganan_rekonsiliasi`
  (status `belum_terverifikasi` untuk klaim bayar, `perlu_diperiksa` untuk refund/koreksi);
- ACK 2xx hanya sesudah petunjuk tersimpan durable; penyimpanan gagal → 503 retryable, dan
  tanpa konfigurasi/sakelar siap → 503 (fail-closed, bukan ACK palsu);
- duplikat/replay idempoten (identitas deterministik), urutan bebas, append-only.

Callback **bukan bukti settlement**: efek finansial hanya lewat query status server-to-server
(pekerja rekonsiliasi atau tombol Periksa milik guru) yang mem-binding order, transaction id,
merchant, nominal, IDR, QRIS, dan status penuh.

## Surface checkout produksi guru (`/langganan`)

Dibangun 26 Sep 2026 (keputusan pengguna): `mesin/subscription_produksi_http.py` +
`mesin/subscription_produksi_pages.py`, didispatch `web.py` sebelum permukaan sandbox.
Tanpa runtime produksi terpasang rute tidak melayani apa pun; tanpa sakelar `fondasi`
hanya halaman status "belum aktif" yang dirender (tanpa membaca ledger).

- Rute: `GET /langganan`, `GET /langganan/<inv>`, `GET /langganan/<inv>/qr`,
  `POST /langganan/siapkan`, `POST /langganan/<inv>/buat|periksa`. Token form bertanda
  tangan terikat sesi+principal (`exp` 900 s) memakai kunci proses; `buat` hanya saat
  intent belum ada + sakelar `buat_pembayaran`; `periksa` = satu-satunya jalur efek
  finansial sisi guru (query server-to-server; grant tepat sekali lewat ledger).
- QR diambil server-side via `TransportProduksi.gambar` (allow-list host/path kontrak,
  PNG bounded) lalu disajikan same-origin; URL tidak pernah dari input browser.
- Teks keputusan: harga total termasuk pajak bila berlaku (bukan faktur pajak),
  disclosure Midtrans (QRIS) + merchant, gagal/kedaluwarsa tidak menahan dana, dukungan
  statis tanpa menyimpan kontak. Tanpa JS/aset pihak ketiga.
- 404 identik untuk anon/bukan guru/invoice asing; batas laju 30 permintaan/menit/akun.
- Uji: `mesin/__tests__/test_subscription_produksi_http.py` + 3 mutation guard baru
  (token, allow-list QR, gate sakelar checkout).
- Aktivasi: **ter-deploy 26 Sep 2026** (revision `6c8e3d6`) lewat cutover terkontrol;
  tier `checkout` menunggu secret terpasang + kenaikan tahap dan akun ter-enroll (gap
  keputusan terpisah). Penegakan tetap butuh keputusan terpisah.

## Jalur transisi akun lama (panel, 26 Sep 2026)

Checkout `/langganan` memerlukan enrollment; akun yang dibuat sebelum sinkron
registrasi publik tidak punya baris itu. Untuk uji terkendali dan akun lama, panel
Langganan menyediakan jalur transisi eksplisit:

- Pencarian alias (`POST /admin/layanan/cari`) menampilkan blok "Belum terdaftar di
  langganan" untuk akun guru tanpa enrollment, dengan form per akun.
- Aksi `POST /admin/layanan/transisi` (tinjauan+csrf+reauth admin; konfirmasi wajib)
  menjalankan `admin_launch_service.aktifkan_transisi`: hanya akun guru dengan revisi
  target masih segar; idempoten lewat `sumber_id=operasi` pada baris enrollment
  (`asal='transisi'`, `mulai=sekarang`, tanpa promo); replay/dua tab tidak menggandakan;
  tanpa efek invoice/receipt/grant. Sakelar fondasi (tahap ≥ rekonsiliasi) wajib;
  readiness provider tidak relevan (tanpa panggilan jaringan).
- Provenance sengaja TIDAK memakai `layanan_operasi`: CHECK `aksi` tabel itu terikat
  kontrak pair rilis (perubahan = re-pin recovery, di luar scope). Bukti operasi =
  baris `langganan_enrollment` (kolom Sumber `transisi`) yang tampil di panel.
- Sinkron registrasi publik (`asal='publik'`) + cutoff pembukaan publik adalah fase
  terpisah dan belum aktif.

## Pekerja rekonsiliasi terjadwal

`scripts/rekonsiliasi_langganan.py` menjalankan satu putaran bounded:

```
mesin/.venv/bin/python scripts/rekonsiliasi_langganan.py \
  --admin-db /data/admin-control.db --auth /data/sandi.json --belajar /data/belajar.db \
  --rahasia /run/secrets/midtrans/produksi-rahasia --lease /data/langganan-rekonsiliasi.lock
```

CLI kanonis kini `mesin/rekonsiliasi_langganan.py` (ikut wildcard image); di container:

```
docker exec osn-mesin python rekonsiliasi_langganan.py \
  --admin-db /data/admin-control.db --auth /data/sandi.json --belajar /data/latihan.db \
  --rahasia /run/secrets/midtrans/produksi-rahasia --lease /data/langganan-rekonsiliasi.lock
```

- hanya invoice yang sudah punya intent (`create_…`) dan belum ber-receipt yang diperiksa;
  pekerja tidak pernah membuat invoice/pembayaran baru, juga tidak mengejar hint callback
  tanpa intent;
- batch 1..20 (default 5), cooldown `--jeda` (default 300 s) per invoice dari penanda
  percobaan durable, cutoff `--horizon-hari` (default 7) untuk invoice kedaluwarsa;
- lease file eksklusif antar proses (`flock`): pemegang kedua keluar dengan kode 3;
- panggilan provider di luar lock DB/auth; sebelum receipt/grant, snapshot invoice +
  owner profil + revisi akun diperiksa ulang — perubahan apa pun selama jaringan → tanpa
  grant;
- hasil ledger yang menentukan: `grant` dari store → pengamatan `settlement`; receipt
  `perlu_diperiksa` (terlambat/receipt sudah ada) → pengamatan `perlu_diperiksa` tanpa
  grant kedua; timeout/404/5xx → `belum_terverifikasi` dan dijadwalkan ulang bounded,
  bukan dianggap gagal;
- crash/restart melanjutkan order yang sama (intent + receipt unik provider+transaksi);
- output satu baris JSON agregat (tanpa id invoice/nama anak/kredensial). Exit: 0 sukses,
  2 konfigurasi produksi tidak sah, 3 lease dipegang proses lain, 4 sakelar/state belum siap,
  1 galat lain.

Jadwal cron terpasang 26 Sep 2026: `/etc/cron.d/osn-rekonsiliasi-langganan` menjalankan
`docker exec osn-mesin python rekonsiliasi_langganan.py …` tiap 10 menit (satu worker;
lease file menolak proses kedua), log agregat di `/opt/osn/log/rekonsiliasi-langganan.log`.
Sebelum secret/tahap siap, worker keluar `2`/`4` (fail-closed) dan tidak menulis apa pun.

## Yang belum dilakukan fase ini

Tidak ada aktivasi pembayaran, tidak ada deploy, tidak ada secret yang dibuat/dipasang,
tidak ada perubahan `.env`/entrypoint, tidak ada pemanggilan Midtrans (sandbox maupun
produksi), tidak ada perubahan schema, dan job `pasang` tetap literal false. Tier Admin
disarankan tetap `nonaktif` sampai keputusan di bawah diambil.

## Keputusan pengguna — SUDAH DIAMBIL 26 September 2026

Diputuskan lewat sesi aktivasi (ringkasan lengkap: `docs/plan/2026-09-26-aktivasi-pembayaran.md`,
lokal). Diaktifkan di kode pada commit aktivasi; kenaikan tahap Admin tetap gerbang terpisah.

1. **D8 — refund/partial/chargeback**: manual & proporsional — admin menyesuaikan/mencabut
   akses lewat panel (bukan otomatis); promo tidak direfund otomatis; refund maksimum sebesar
   nilai bayar aktual; penutupan kasus dicatat di jurnal admin.
2. **D8 — pembayaran terlambat/lebih dan pembayaran kedua**: ketat, sesuai perilaku sekarang —
   grant hanya dari settlement tervalidasi dalam horizon 7 hari dengan nominal persis sama;
   terlambat di luar horizon/nominal beda/pembayaran kedua → `perlu_diperiksa` tanpa grant,
   koreksi manual admin (grant manual atau refund).
3. **D8 — runbook rekonsiliasi manual**: pemilik memeriksa panel Admin tiap hari kerja; SLA
   tindak lanjut ≤3 hari kerja; bukti = status ringkas + jurnal ledger append-only (tanpa
   payload mentah/kontak).
4. **D9 — pajak**: harga final all-in (label "harga termasuk pajak bila berlaku"); invoice/receipt
   sederhana non-faktur-pajak (identitas merchant, tanggal, deskripsi, nominal); dibuka kembali
   bila status PKP terkonfirmasi profesional.
5. **D9 — retensi & penghapusan**: bipartit — ledger finansial minimum (tanpa identitas anak)
   mengikuti kandidat kewajiban pembukuan 10 tahun, ditinjau setelah konfirmasi profesional;
   permintaan hapus menghapus data belajar/identitas anak; ledger & bukti append-only tetap utuh.
6. **Aktivasi teknis**: entry worker kanonis ikut image (`mesin/rekonsiliasi_langganan.py`) +
   cron host `docker exec` tiap 10 menit, 1 worker (lease menolak proses kedua); mount
   `/opt/osn/midtrans` (root-controlled; berkas uid 10001 mode 0400) read-only ke
   `/run/secrets/midtrans` di kedua jalur `docker run` deployer; `scripts/deploy.py` menulis
   artefak `recovery-pair.json` sebelum swap; urutan tahap rekonsiliasi ≥48 jam → checkout
   (uji 1 pembayaran nyata) → penegakan ≥7 hari setelah checkout stabil; penurunan tahap kapan
   saja saat insiden.
7. **Kontrak merchant/disclosure QRIS**: teks halaman pembayaran "Pembayaran diproses Midtrans
   (QRIS) — merchant <akun> — nominal + masa berlaku"; status gagal/kedaluwarsa "invoice bisa
   dibuat ulang; tidak ada dana tertahan"; dukungan = teks statis halaman bantuan tanpa
   menyimpan kontak pengguna. (Diterapkan saat surface checkout produksi guru dibangun.)

Terbuka (bukan keputusan kode): status akun merchant Midtrans + provisioning secret oleh
pemilik (Server Key tidak pernah lewat chat), dan surface checkout produksi guru yang belum
ada — uji "checkout nyata" menunggu fase surface terpisah.

Riset yang mempersempit dua keputusan pertama: `docs/plan/2026-09-24-payment-provider-research.md`
dan `docs/plan/2026-09-24-tax-retention-research.md` (lokal, gitignored).

## Verifikasi yang dapat diulang

```
mesin/.venv/bin/python -m pytest mesin/__tests__/test_midtrans_secret.py \
  mesin/__tests__/test_midtrans_produksi.py mesin/__tests__/test_subscription_produksi.py \
  mesin/__tests__/test_subscription_callback.py mesin/__tests__/test_subscription_worker.py \
  -q -W error -p no:cacheprovider
mesin/.venv/bin/python -m pytest mesin/__tests__/test_subscription_produksi_mutation.py \
  -q -W error -p no:cacheprovider
```

Seluruh tes memakai akun, ledger, secret, dan transport sintetis (tanpa socket keluar, tanpa
kredensial nyata). Mutation guard membuktikan test benar-benar menangkap: bypass signature,
pelanggaran binding merchant/nominal, ACK sebelum hint durable, replay non-idempoten, order
asing yang membuat dokumen baru, runtime/recovery fail-closed, guard lease/cooldown/cutoff,
dan refresh owner/revisi sebelum grant. Kelulusan lokal ini tetap bukan klaim deployed atau
aktif.
