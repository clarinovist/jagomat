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
| `kebijakan` | konstanta `KEBIJAKAN_D8_D9 = False` | D8/D9 belum diputuskan pengguna |

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

## Pekerja rekonsiliasi terjadwal

`scripts/rekonsiliasi_langganan.py` menjalankan satu putaran bounded:

```
mesin/.venv/bin/python scripts/rekonsiliasi_langganan.py \
  --admin-db /data/admin-control.db --auth /data/sandi.json --belajar /data/belajar.db \
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

Jadwal cron/systemd belum dipasang; memasangnya baru masuk tahap aktivasi.

## Yang belum dilakukan fase ini

Tidak ada aktivasi pembayaran, tidak ada deploy, tidak ada secret yang dibuat/dipasang,
tidak ada perubahan `.env`/entrypoint, tidak ada pemanggilan Midtrans (sandbox maupun
produksi), tidak ada perubahan schema, dan job `pasang` tetap literal false. Tier Admin
disarankan tetap `nonaktif` sampai keputusan di bawah diambil.

## Keputusan yang perlu dipilih pengguna (D8/D9 dan lanjutannya)

Daftar ini belum diputuskan di kode; jangan memilihnya diam-diam di perubahan berikutnya.

1. **D8 — refund/partial/cancel/chargeback**: kebijakan akses setelah uang dikembalikan
   (revoke? lanjut sampai periode habis?), perlakuan promo, dan siapa yang menutup kasus
   `perlu_diperiksa`.
2. **D8 — pembayaran terlambat/lebih dan pembayaran kedua**: apakah tetap tanpa grant
   (status sekarang), dan bagaimana runbook koreksi manualnya.
3. **D8 — runbook rekonsiliasi manual**: siapa yang menindaklanjuti receipt
   `perlu_diperiksa`, SLA, dan bukti yang harus disimpan.
4. **D9 — pajak**: status PPN produk ini, apakah harga Rp15.000/… sudah final atau
   ditambah pajak, serta teks/invoice yang ditampilkan ke pembeli.
5. **D9 — retensi & penghapusan**: berapa lama data billing disimpan, apa yang dihapus saat
   permintaan penghapusan, dan bagaimana bukti audit tetap utuh.
6. **Aktivasi teknis**: lokasi final mount secret + artefak recovery, pemilik izin berkas,
   cara menjalankan pekerja (host checkout vs di dalam image — image sekarang hanya memuat
   `mesin/*.py`, jadi `scripts/` belum ada di sana), jumlah shard/worker, jadwal cron, dan
   urutan naik tahap Admin (`nonaktif → rekonsiliasi → checkout → penegakan`).
7. **Kontrak merchant/disclosure**: teks QRIS, identitas merchant yang tampil, kebijakan
   bila pembayaran gagal, dan dukungan pelanggan tanpa mengirim kontak ke provider.

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
