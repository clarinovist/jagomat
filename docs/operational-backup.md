# Backup operasional Jagomat

## Status audit25 Oktober2026

- Backup rilis lengkap tersedia; itu berbeda dari jadwal backup rutin.
- Inventaris lokal tidak menemukan LaunchAgent/cron Jagomat. Di VPS, cron yang
  ditemukan untuk backup adalah milik PolyFlow dan skripnya tidak mencakup Jagomat.
  Belum ada bukti scheduler Jagomat otomatis; audit ini **tidak memasang cron baru**.
- Skrip lama hanya menyalin tiga DB terpisah, tidak menyertakan auth/admin/riset/
  lampiran, memakai nama temp tetap, dan memangkas30hari. Jalur lama diganti
  entrypoint **fetch paket lengkap existing**; tidak lagi mengklaim backup parsial
  sebagai pemulihan aplikasi utuh. Tidak ada backup lama yang dihapus atau retensi
  existing yang diubah. Kebijakan retensi tetap berlaku dan perlu operator;
  tooling ini tidak melakukan prune otomatis.

## Cakupan paket

`operasional/<id>/` privat:

- `bundle/`: empat DB durable dan `sandi.json`, dengan manifest/validator
  `admin_backup` existing;
- `riset-separate.db`: salinan terpisah dengan validasi schema+instrumen kanonis
  `research_store.buka_baca`; retensi riset tetap terpisah;
- `lampiran/`: seluruh berkas foto; setiap referensi metadata harus menunjuk file
  aman yang ada. Direktori sumber belum terbentuk sah hanya bila tanpa referensi;
- `opsional/` (manifest **v2**): DB SQLite di `/data` yang boleh tidak ada,
  yaitu `sakelar.db` (sakelar fitur admin), `kurikulum.db` (override kurikulum),
  `cetakan.db` (cetakan soal berpola, `cetakan_store`), dan `cetakan_ai.db` (kuota + audit permintaan draf AI cetakan,
  `cetakan_ai_store`). Yang ada saat capture dikunci `BEGIN IMMEDIATE` bersama core dan
  disalin dengan SQLite backup API; yang tidak ada dilewati; symlink/non-regular
  ditolak. Manifest mencatat daftar terurut di key `optional`; isi `opsional/` harus
  persis sama, tiap DB lulus integrity+FK, dan `sakelar.db` wajib `user_version`
  sesuai `feature_switch.VERSI_SKEMA` serta tabel `sakelar`+`audit_sakelar`;
  `kurikulum.db`, `cetakan.db`, dan `cetakan_ai.db` wajib `user_version` + `TABEL_SKEMA` modulnya
  (`kurikulum_override`, `cetakan_store`, `cetakan_ai_store`).
  Folder `opsional/` selalu ada, boleh kosong. Bundle **v1 lama tetap valid** (tanpa
  `opsional/`). `admin_backup.BERKAS_WAJIB` dan bundle core tidak berubah. Tool host
  di `/opt/osn/backup-tool` perlu `mesin/feature_switch.py`, `kurikulum_override.py`, dan
  `cetakan_store.py` (+ `cetakan_pola.py`, `kurikulum_kelas.py`), dan `cetakan_ai_store.py` (+ `jurnal_wal.py`) agar validasi skema berjalan
  (tool host lama TIDAK menolak: `OPSIONAL`-nya tak memuat `cetakan_ai.db`, jadi berkas itu diam-diam tak ikut bundle; sebaliknya
  `operational_backup.py` baru tanpa `cetakan_ai_store.py` + `jurnal_wal.py` di host gagal `ImportError` saat cek skema. Perbarui tool host
  `/opt/osn/backup-tool` DAN salinan `/opt/osn/backup-harian/backup_harian.py` (daftar `OPSIONAL` sendiri) sebelum mengandalkan backup kuota;
  cetakan.db tetap aman, `cetakan_ai.db` hanya kuota + audit permintaan, bukan isi cetakan);
- `operational-manifest.json`: revision/digest aplikasi, cutoff, daftar/hash/ukuran
  file dan direktori. Tidak berisi isi jawaban, nama anak, atau credential.
  Path lampiran tetap privat, bukan untuk log/prompt.

Tidak menyertakan sesi/transient, lembar/cache generated, arsip backup lain,
provider credential atau konfigurasi host. **Ini paket data aplikasi, bukan backup
seluruh VPS.** Pemulihan host juga membutuhkan image exact, config/secret existing
melalui inventaris privat, dan rotasi/rekonsiliasi sesuai runbook. Jangan memulihkan
sesi login lama atau consent epoch tanpa prosedur domain.

## Capture terkontrol, bukan backup hot lintas-DB

Tool `scripts/operational_backup.py` tidak menghentikan server atau memasang hold.
Operator memakai maintenance/drain existing dari [runbook rilis](production-release.md),
setelah preflight current/image/schema sehat. Semua writer (HTTP, cron, worker,
proses file lain) harus ditahan. Jangan memakai produksi sebagai test.

Capture memverifikasi app `exited`, maintenance terpasang, tiga cron writer
terkomentar, tidak ada container lain me-mount data/ancestor/subtree dan fuser
(termasuk DB opsional yang ada) hanya melihat collector sendiri. Lock deploy mencegah persaingan deployment;
DB/auth diambil berurutan belajar→auth→admin→AI→Pendamping→riset. Caller wajib
mempertahankan hold selama capture; pemeriksaan sesaat bukan penghalang proses
root nakal. Tidak menjalankan callback DB/provider atau migrasi saat capture.

Sesudah gate CI exact dan pemasangan tooling privat terverifikasi, operator root:

```text
python3 -B /opt/osn/backup-tool/scripts/operational_backup.py capture --id <id-baru> --revision <SHA-current> --image sha256:<digest-current>
```

Target tetap `/opt/osn/data`, output `/opt/osn/cadangan/operasional/<id>`. ID hanya
huruf kecil/angka/tanda-hubung,2–80 karakter; tidak ada path bebas di capture.
Tidak menimpa. Salinan memakai SQLite backup API, auth lock dan copy foto. Mode
journal salinan dinormalkan ke DELETE; header dan WAL kosong diperiksa sebelum
sidecar salinan milik collector dibersihkan. Mode/sidecar DB live tidak diubah. Output
stage privat baru dipublikasikan setelah validator/hash/fsync lulus. Failure
meninggalkan `.partial-*` privat, bukan marker sukses. Jangan menghapusnya sebelum
penyebab diketahui. Setelah capture dan kondisi data sehat, pulihkan akses segera;
transfer dan rehearsal tidak perlu memperpanjang downtime.

## Transfer off-site ke Mac existing

Dari akar repo:

```bash
bash mesin/cadangkan.sh <id-bundle-operasional>
```

Script memakai interpreter proyek, alias `biznet-sekolahdesain` (override
`OSN_HOST_VPS` hanya target yang telah diverifikasi), SSH batch existing. Destination
mengikuti lokasi repo/alias, bukan cwd/home lama:
`mesin/cadangan/operasional/<id>`. File privat tidak masuk log/chat atau Git.

Export memvalidasi paket sebelum stream. Transfer gagal tetap `.transfer-*` privat;
extractor menolak path traversal, symlink/hardlink/perangkat, duplikat, >100.000
entri atau total>2GiB. Tidak memakai `extractall`. Setelah hash/schema/linkage/ID
lulus dan direktori tersinkron, staging di-rename atomik. Output sebelumnya tidak
ditimpa. Backup2GiB+ perlu rencana ukuran terpisah, bukan melemahkan batas diam-diam.

`validate <path>` read-only; tidak memperbaiki backup rusak. Manifest dan hash
mendeteksi perubahan, **bukan autentikasi atau bukti quiesce**; kepercayaan asal
berasal SSH terverifikasi dan prosedur operator. Mac tetap perlu perlindungan disk,
akses dan kebijakan retensi. Lokasi Mac tidak tersedia saat laptop mati; tidak
mengklaim off-site otomatis24/7.

## Pemulihan dan verifikasi

Uji hanya pada turunan privat/sintetis, tidak restore live. Validator memastikan
core/hash/schema/FK/auth/linkage foto/riset. Rehearsal startup memakai artifact exact
teruji dan salinan terisolasi, tanpa network; periksa idempotensi, preservasi dan
kebutuhan rekonsiliasi. Pemulihan manual `opsional/*` ke `/data` (hanya saat semua writer ditahan, mode
600, owner sama dengan DB lain di `/data`; jangan menimpa tanpa backup berkas yang
ada): salin `opsional/<nama>` ke `/data/<nama>`, hapus sidecar `-wal`/`-shm` lama
bila ada, lalu verifikasi `PRAGMA integrity_check` = `ok`. Tanpa berkas ini aplikasi
memakai bawaan kode/env (sakelar) sehingga pemulihan opsional tidak memblokir startup.
Restore live merupakan operasi terpisah: sesi diinvalidasi,
izin/sensor dan billing direkonsiliasi sesuai kontrak, backup sebelum cutover,
operator memverifikasi target dan recovery. Jangan menimpa seluruh data dengan
`cp` atau menghapus histori untuk membuat startup hijau.

Tes: `test_operational_backup*`, `test_backup_location`, validator core/riset existing.
Mutation menghapus guard hash/linkage/schema/writer/traversal untuk membuktikan
kegagalan ditangkap; data sintetis saja. Status live/hasil satu eksekusi dicatat
terpisah di plan/runbook, bukan disimpulkan dari keberadaan skrip.

## Eksekusi terverifikasi25 Oktober2026

Tool host **5c2e07b** dipasang privat pada `/opt/osn/backup-tool`, SHA256 script
`2975238e56058c96d9ca3587a9c268abf926d5bea94cc4c96cb63b9eefe8b5bc`.
CI dispatch [40141156791](https://github.com/clarinovist/jagomat/actions/runs/40141156791)
lulus14.332 tes kandidat exact-once, recovery/build/pair; push40141156237 sukses.
Lokal69 tes terarah termasuk6mutation lulus; reviewer source OK with notes.
Image aplikasi **tetap ab3234d**, tidak diganti oleh pemasangan tool backup.

Capture pertama pada a5bae28 ditolak karena sidecar WAL salinan. Akses langsung
dipulihkan; bukan backup sukses. Akar masalah direproduksi sintetis, diperbaiki pada
salinan saja, kemudian CI baru lulus sebelum retry. Validator inventaris tidak
dilonggarkan. Partial gagal disimpan privat untuk diagnosis, bukan restore target.

Capture `manual-20261025-02` berhasil setelah preflight/maintenance/drain existing;
core5file, riset terpisah, lampiran0file pada state saat itu. Dukungan foto `.img`
dibuktikan fixture writer kanonis, bukan diasumsikan dari direktori produksi kosong.
Akses publik dipulihkan sebelum transfer/rehearsal. Paket ditarik ke Mac dan
hash/schema/linkage/ID tervalidasi di
`mesin/cadangan/operasional/manual-20261025-02/` (privat, ignored).

Rehearsal startup idempoten pada turunan dengan image exact ab3234d/digest69d900d0…,
networknone, preserve core dan riset lulus; bundle asli tidak berubah. Turunan
rehearsal dibersihkan. Tidak ada restore live. Validator menandai
`needs_reconciliation=true`: bila restore kelak, state layanan/billing perlu
rekonsiliasi sesuai runbook, bukan langsung membuka transaksi.

Final read-only: image tetap healthy, hash10tabel histori identik, Caddy/cron/config
kembali identik, smoke publik `/`200 `/akun`401 `/murid/`303. Backup pengaman/partial
privat dipertahankan; tidak ada cron baru, prune, perubahan retensi atau provider.
Bukti lokal ignored: `docs/plan/backup-operation-retry-20261025/`.

## Backup harian otomatis (Tahap 0, mulai 20 Nov 2026)

- **Host `biznet-sekolahdesain`**, cron `/etc/cron.d/osn-backup-harian` pukul 21:45 WIB:
  `/usr/bin/python3 /opt/osn/backup-harian/backup_harian.py` menulis
  `/opt/osn/backup-harian/<YYYYMMDD-HHMMSS>/`, retensi 14 salinan. Log di
  `/opt/osn/log/backup-harian.log`: tiap run mencetak satu baris JSON
  (`id`, `status`, jumlah `db`/`berkas`, `ukuran_total`, `salinan_tersisa`) setelah
  bundle divalidasi ulang (hash + `integrity_check`); validasi gagal membuat skrip keluar
  dengan galat sehingga jejaknya masuk log.
- **Isi**: lima DB wajib (`latihan`, `admin-control`, `ai-control`, `pendamping`,
  `riset-konsumen`) + `sandi.json`, ditambah `sakelar.db`, `kurikulum.db`, `cetakan.db`,
  `cetakan_ai.db` bila ada (dibuat saat fiturnya pertama dipakai), serta `kelas-daftar.db`
  (sumber `/var/lib/kelas-daftar/daftar.db`, pendaftaran `kelas.jagomat.id` milik service
  `kelas-daftar` di port 8731) yang disalin lewat backup API baca-saja. Salinan memakai SQLite backup API, dinormalkan `journal_mode=DELETE`,
  lolos `integrity_check`, dan hash-nya dicatat di `manifest.json` dengan
  `needs_reconciliation=true`. Lampiran tidak disalin (ikut bundle rilis); bukti
  transfer tidak disalin (keputusan Pemilik: bukti sementara 30 hari).
- **Off-site**: Hermes cron `osn-cadangan-harian` pukul 22:00 menjalankan
  `~/.hermes/scripts/jagomat-backup-offsite.sh` (sumber terlacak:
  `scripts/backup_offsite_mac.sh`; salinan Hermes harus identik, sinkron manual): periksa
  umur bundle terbaru (maks 26 jam, `OSN_OFFSITE_UMUR_MAKS_JAM`) supaya bundle kemarin tidak
  diunggah ulang bila backup 21:45 gagal → validasi di VPS → tarik tar →
  enkripsi AES-256-CBC/PBKDF2 (kunci `~/.config/jagomat-backup/offsite.key`, 0600,
  tidak pernah masuk VPS/repo) → unggah ke `r2:jagomat-app-cadangan/harian/<id>.tar.gz.enc`,
  retensi 30 hari. Tidak ada salinan plaintext yang disimpan di Mac.
- **Drill 20 Nov 2026 18:43**: unduh dari R2 → dekripsi → validasi manifest/hash →
  lima DB `integrity_check=ok`, `journal_mode=delete`. Ini drill baca, bukan restore live.
- **Drill restore 21 Nov 2026 (kontainer sementara di VPS)**: bundle cron `20261120-214501`
  divalidasi (`backup_harian.py --validasi`), disalin ke folder sementara `/var/tmp`
  (root, dihapus sesudahnya), `chown 10001:10001`, lalu image produksi yang sama dijalankan
  tanpa jaringan (`--network none`, `--cap-drop ALL`, `no-new-privileges`, memori 256 MB;
  hanya env jalur DB yang diteruskan, kunci API tidak). Hasil: lima DB `integrity_check=ok`,
  status `healthy`, smoke di loopback `/` 200, `/akun` 401, `/murid/` 303, tanpa galat di log,
  `osn-mesin` produksi tidak berubah. Setelah app start, empat DB kembali `wal`; **`pendamping.db`
  tetap `delete`** sampai `assistant_schema.siapkan()` dijalankan (startup `serve.py` belum
  memanggilnya), jadi setelah restore sungguhan periksa mode jurnalnya. Perbaikannya
  (`berkas_data.kencangkan_saat_start()`: WAL dipulihkan dan semua DB durable beserta sidecar
  dikunci 0600 saat start, tanpa DDL) ada di `main` lokal dan belum dirilis. Ini bukan restore ke
  produksi sungguhan.
- **Batas**: off-site bergantung pada Mac menyala; bila Mac mati, backup lokal VPS tetap
  jalan tetapi tidak ada salinan keluar VPS hari itu. Kegagalan off-site mengirim alert
  Telegram lewat `notify-telegram.py` (token dari `~/.hermes/.env`) untuk setiap keluar
  non-nol, termasuk `exit 1` eksplisit (kunci hilang, ID tidak sah, bundle basi). Jalur gagal
  diuji end-to-end 21 Nov 2026 12:30 WIB dengan host palsu (Telegram membalas `ok`). Backup memegang koneksi baca singkat; jangan jadwalkan
  deploy/preflight `host_quiescent` tepat pada 21:45 karena `fuser` bisa menganggapnya writer.

- **Rotasi log**: `/etc/logrotate.d/osn-log` (21 Nov 2026) merotasi `/opt/osn/log/*.log` mingguan
  atau saat melewati 5 MB, 8 salinan, terkompresi, `copytruncate` (cron menulis dengan `>>`).
  Log Docker `osn-mesin` belum dibatasi (`json-file` tanpa `max-size`); menambah
  `--log-opt max-size=10m --log-opt max-file=5` pada `docker run` deployer menunggu rilis berikutnya.

### Restore dari backup harian

1. Hentikan app lewat runbook rilis (maintenance + container berhenti). Jangan restore
   saat masih ada writer.
2. **Pindahkan** (jangan hapus dulu) `*.db-wal` dan `*.db-shm` dari `/opt/osn/data` ke
   folder `sampingan-<id>`. Sidecar basi membuat SQLite membuka WAL lama dan menyajikan
   data yang salah tanpa error — `integrity_check` tetap `ok`.
3. Salin DB dari bundle ke `/opt/osn/data/`; samakan pemilik/mode dengan berkas asli
   (biasanya `osn:osn`, 0600). `sandi.json` hanya bila akun ikut dipulihkan.
4. `PRAGMA integrity_check` + hitung baris tabel kunci; bandingkan dengan `manifest.json`.
5. Start app, smoke publik, cek login admin. `needs_reconciliation=true` berarti state
   lintas DB (langganan/pesanan/refund) harus dicek sebelum menerima transaksi.

## Off-site dari VPS (terpasang dan diuji 21 Nov 2026)

Tujuan: salinan di luar VPS tidak bergantung Mac menyala. Jalur Mac di atas tetap
berjalan sebagai cadangan kedua.

- **Arsitektur**: `scripts/backup_offsite_vps.py` (root, cron terpisah setelah
  backup 21:45) memilih bundle terbaru, menolaknya bila lebih tua dari 26 jam atau
  tak lolos `backup_harian.validasi`, lalu tar.gz (hanya berkas yang tercantum di
  manifest, dibuka `O_NOFOLLOW`), enkripsi AES-256-CBC (PBKDF2 200.000, sandi sesi
  acak 256 bit), membungkus sandi sesi dengan **RSA-OAEP SHA-256 memakai kunci
  publik** (wajib RSA >= 3072 bit; kunci non-RSA, lebih kecil, atau kunci privat
  ditolak), HMAC-SHA256, dan unggah ke R2. Pasang berdampingan di
  `/opt/osn/backup-harian/`: `backup_offsite_vps.py`, `offsite_kripto.py`,
  `offsite_kerja.py`, `offsite_retensi.py`, `offsite_penanda.py`, `r2_s3.py`,
  `backup_harian.py` (klien S3 SigV4 stdlib, tanpa dependency; hanya butuh biner
  `openssl`).
- **Objek** di `vps/<id>/`: `data.enc`, `kunci.enc`, `meta.json` (id, ukuran, sha256,
  mac, sidik jari SHA-256 kunci publik, parameter algoritma; tanpa nama berkas isi
  bundle). Sebelum unggah skrip melakukan List `vps/<id>/`: bila ketiga objek sudah
  ada, unggahan DILEWATI (ringkasan `sudah_ada: true`); bila hanya sebagian (sisa
  unggahan terputus), diunggah ulang dengan urutan data, kunci, **meta terakhir**
  (`meta.json` lama dihapus lebih dulu agar set tak tampak lengkap selama ditimpa).
  Set tanpa `meta.json` dianggap tidak lengkap dan ditolak pemulihan.
- **Penanda ganda** (urutan: unggah + verifikasi List -> tulis `last-ok` -> retensi ->
  tulis `retention-ok` hanya bila retensi sukses). Keduanya ditulis lewat berkas
  sementara acak (`mkstemp`, fsync, 0644, `os.replace`) sehingga symlink yang
  ditanam tidak diikuti. `/opt/osn/log/offsite-vps.last-ok`: `<stempel WIB> <id>
  mac=<hex> sha256=<hex> kunci=<hex>`, ditulis setelah semua objek terunggah dan
  terverifikasi (ukuran sama), TIDAK diubah mundur bila retensi gagal.
  `/opt/osn/log/offsite-vps.retention-ok` (`--penanda-retensi`): `<stempel> <id>
  terhapus=<n>`; penanda lama dibiarkan bila retensi gagal. Untuk set yang
  dilewati (`sudah_ada`), mac/sha256 hanya dipertahankan bila `last-ok` lama
  bernomor id yang sama; selain itu ditulis `-` (tidak pernah disalin dari
  `meta.json` di R2 yang tidak tepercaya).
- **Retensi** (`--retensi-hari`, 30): hanya set `vps/<id>/` yang seluruh objeknya
  lebih tua dari batas menurut LastModified; prefix lain (mis. `harian/` milik jalur
  Mac) tidak disentuh. Pagar terhadap jam VPS yang salah: (1) `--simpan-minimal`
  (7) set lengkap terbaru selalu dijaga apa pun umurnya; (2) `--hapus-maks` (5):
  bila kandidat hapus lebih dari itu, **tidak ada yang dihapus** dan skrip keluar
  kode 3 dengan pesan jelas (periksa jam VPS). Set yang baru diunggah tidak pernah
  dihapus. Keluar 0 sukses; 1 gagal sebelum/selama unggah (penanda tidak diubah);
  3 set baru terunggah dan terverifikasi tetapi retensi gagal atau dibatalkan.
  Retry 429 dan 5xx (3 percobaan, jeda 1 dan 2 detik); galat jaringan/TLS di log
  hanya menyebut nama kelas galat.
- **Keamanan**: VPS hanya memegang kunci PUBLIK (skrip tidak punya kode/argumen
  untuk kunci privat); data anak tidak pernah plaintext di luar VPS. Sandi sesi
  hanya lewat berkas 0600 di direktori 0700 yang dihapus saat keluar (kegagalan
  hapus dicatat ke stderr; di awal run, sisa direktori `offsite-*` milik root, mode
  0700, berumur > 1 hari di direktori sementara disapu), tidak lewat argv/env.
  Kredensial R2 dari `/etc/osn/offsite-r2.env` (milik root, mode maksimal 0600; kunci
  `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`), tidak
  pernah dicetak. Respons XML R2 yang memuat `<!DOCTYPE`/`<!ENTITY` ditolak.
- **Keterbatasan keaslian (penting)**: HMAC memberi integritas, **bukan bukti asal**.
  Kunci publik memang publik; siapa pun yang memegang token R2 dengan akses tulis
  dapat membuat set `vps/<id-baru>/` yang sah secara internal. Token R2 **tidak bisa
  dibatasi per prefix**, jadi token VPS juga bisa menimpa/menghapus `harian/`.
  Mitigasi: (a) pakai **bucket terpisah khusus VPS** dengan token yang hanya dipakai
  VPS (token baca-saja untuk Mac di bucket yang sama), agar kebocoran token jalur
  lain tidak mencapai set ini; (b) saat memulihkan, berikan `--mac-harapan` dan
  `--sha256-harapan` yang dibaca dari sumber tepercaya di VPS: baris JSON terakhir
  di `/opt/osn/log/offsite-vps.log` (bidang `mac`, `sha256`, `id`) atau
  `/opt/osn/log/offsite-vps.last-ok` (untuk set terbaru). Tanpa keduanya pemulihan
  tetap jalan tetapi mencetak peringatan bahwa keaslian TIDAK diverifikasi.
  Sisa celah: pada set yang dilewati karena sudah ada tanpa riwayat penanda,
  mac/sha256 tidak diketahui (`-`), jadi set itu tidak bisa diverifikasi; dan
  penyerang yang bisa menanam set pada id yang BELUM dipakai VPS (id mengikuti
  jam) hanya terdeteksi lewat perbandingan di atas.
- **Pemulihan (Mac)**: `scripts/pulihkan_offsite.py --id <id> --env <env baca-saja>
  --kunci-privat <pem> --tujuan <direktori baru> --mac-harapan <hex> --sha256-harapan
  <hex>` (atau `--dari-direktori` untuk berkas yang sudah diunduh). Urutan: unduh
  `meta.json` dulu dan validasi (tipe ketat), unduh `data.enc` dibatasi sebesar
  `meta.ukuran` -> cocokkan mac/sha256 dengan nilai harapan -> cek ukuran+sha256 ->
  buka sandi sesi dengan kunci privat -> **verifikasi HMAC sebelum dekripsi** ->
  dekripsi -> ekstraksi tar aman (batas byte terdekompresi) -> `validasi` bundle ->
  rename atomik ke tujuan. Hasil JSON memuat `kunci_publik_sha256` (cocokkan dengan
  kunci yang Anda pegang) dan `keaslian_terverifikasi`. Tujuan tak kosong ditolak.
  Pakai openssl Homebrew bila `/usr/bin/openssl` (LibreSSL) bermasalah; keduanya lolos
  tes interop. Setelah itu lanjut ke "Restore dari backup harian".
- **Kunci RSA** (contoh perintah, jalankan di Mac; JANGAN di VPS):
  `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -aes-256-cbc -out jagomat-offsite-privat.pem`
  lalu `openssl pkey -in jagomat-offsite-privat.pem -pubout -out jagomat-offsite-publik.pem`.
  Salin hanya `publik.pem` ke `/etc/osn/offsite-publik.pem` (0644). Skrip menolak
  kunci publik RSA di bawah 3072 bit.
- **Cron terpasang 21 Nov 2026** (`/etc/cron.d/osn-offsite-vps`, 0644 root):
  `0 22 * * * root /usr/bin/python3 -I /opt/osn/backup-harian/backup_offsite_vps.py >> /opt/osn/log/offsite-vps.log 2>&1`
  (`-I` = mode terisolasi: abaikan env `PYTHON*` dan direktori kerja.)
  Drill pulihkan dari objek `vps/` sudah lulus 21 Nov; job Hermes 22:00 baru boleh
  dihentikan setelah pemilik memutuskan, sampai itu jalur Mac tetap cadangan kedua.
- **PERINGATAN**: tanpa kunci privat, semua backup `vps/` tidak bisa dibuka. Simpan
  kunci privat (dan passphrase) dengan **salinan aman terpisah** (mis. pengelola
  sandi + media offline di tempat lain); jangan hanya di satu Mac. Uji pulihkan
  dengan kunci yang sama sebelum mengandalkan jalur ini.
- **Terbukti 21 Nov 2026**: ListObjectsV2 dan PUT di R2 sungguhan dengan token khusus
  bucket, enkripsi OpenSSL 3.0.13 (VPS) → dekripsi LibreSSL 3.3.6 (Mac), penanda
  `last-ok`/`retention-ok`, dan run ulang id yang sama (`sudah_ada: true`, mac/sha256
  dipertahankan). **Belum terbukti**: retry 429/5xx dan galat TLS nyata, retensi yang
  benar-benar menghapus (belum ada set > 30 hari), sapuan sisa `/tmp` sebagai root, dan
  cron 22:00 yang benar-benar terpicu (dipasang 21 Nov, run pertama jatuh 22 Nov).
  Tes memakai server S3 tiruan lokal dan vektor resmi AWS SigV4.
- **Instalasi 21 Nov 2026**: bucket terpisah `jagomat-app-cadangan-vps` dengan token
  Object Read & Write yang dibatasi ke bucket itu (dibuktikan: List ke
  `jagomat-app-cadangan` dan bucket lain ditolak `403 AccessDenied`), jadi kebocoran
  token VPS tidak mencapai jalur Mac. Kunci publik RSA-3072 di
  `/etc/osn/offsite-publik.pem` (sidik jari SHA-256 DER
  `451fa1660651725e9cb3b3a66e788ef44f24bb2cf461e7fbd4bd83d3d5ad00df`), env
  `/etc/osn/offsite-r2.env` milik root 0600, tujuh skrip di `/opt/osn/backup-harian/`.
  Run manual 15:06 WIB atas bundle `20261121-140623`: tiga objek terunggah
  (`data.enc` 990.688 B), penanda `last-ok` + `retention-ok` tertulis, keluar 0.
  Drill pulihkan dari R2 sungguhan di Mac lulus dengan `--mac-harapan/--sha256-harapan`
  dari `last-ok`: MAC + sha256 cocok, `keaslian_terverifikasi=true`, 8 berkas
  (7 + `manifest.json`), `integrity_check` ok.
- **Sisa langkah pemilik**: salin kunci privat + passphrase ke pengelola sandi (dan
  media offline), lalu buat token R2 **baca-saja** untuk bucket yang sama agar Mac
  tidak perlu memegang token tulis saat memulihkan.

## Yang tetap terbuka

1. ~~Frekuensi/jam backup~~ → harian 21:45 WIB di host, off-site 22:00 dari Mac.
2. ~~Off-site otomatis independen laptop~~ → R2 terenkripsi. Jalur VPS→R2 terpasang dan
   diuji 21 Nov 2026 (bucket `jagomat-app-cadangan-vps`, cron 22:00, drill pulihkan dari
   R2 lulus), jadi salinan keluar VPS tidak lagi bergantung Mac menyala. Job Mac tetap
   berjalan sebagai cadangan kedua sampai pemilik memutuskan menghentikannya.
3. Retensi sudah jalan (14 lokal, 30 R2). Alert kegagalan off-site sudah dikirim ke
   Telegram dan jalur gagalnya sudah diuji end-to-end. Drill restore ke kontainer sementara lulus (21 Nov); restore
   ke produksi sungguhan belum pernah dilakukan. Kunci enkripsi `offsite.key` hanya ada di Mac: tanpa salinan aman
   terpisah, kehilangan Mac berarti seluruh backup R2 tidak bisa dibuka. Retensi per domain dan bukti penghapusan tetap perlu dioperasionalkan.
