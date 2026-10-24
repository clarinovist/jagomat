# Rilis integrasi — status, kontrak dan riwayat

Mulai dari snapshot terbaru di bawah. Bagian bertanggal berikutnya adalah histori;
SHA/pin/status lama bukan target deploy saat ini. Pin/mode otoritatif source ada di
`scripts/release-metadata.json` dan workflow; status pekerjaan di [status proyek](status-proyek.md).
Kontrak [mode](#kontrak-mode-dan-bootstrap) dan [operasi](#deploy-rutin-vs-migrasi)
tetap berlaku. Izin operasi mengikuti workspace/CLAUDE, bukan larangan push/SSH lama.

## Deploy fondasi katalog lanjutan nonaktif — 24 Oktober 2026

Controlled `deploy-v2` memasang **c335ce5c4ffc2297321badf0218ec5e3a8a2cd70**;
container started `2026-10-24T14:17:11Z` (21.17 WIB), healthy. Isi: audit lanjutan,
reader/draf revisi2 untuk kuantitas/rata-rata/arsiran, tes dan exporter review.
**`OSN_KATALOG_LANJUTAN` dan `OSN_PENILAIAN_REVISI` tetap nonaktif.** Tidak ada
pengesahan manusia baru, aktivasi penilaian, migrasi/backfill atau perubahan config.
Temuan pada konten live yang memerlukan review tetap terbuka; lihat
[hasil audit dan batas](catalog-followup.md).

- Kandidat digest `sha256:05d67c6de9d35ec940190a06d8b60174ca15bc303c59d9dd2aa7d4b030b77340`.
- Recovery `edd323c4822347f6d584bb0f311e76cac4962e40`, digest
  `sha256:ea15b60b72110c81e70b2848172dee01b9d8fb5c63d81dc4adecd8037dec7fa9`.
- Dispatch [40100808120](https://github.com/clarinovist/jagomat/actions/runs/40100808120)
  sukses:14.237 tes kandidat exact-once, empat shard recovery, build/probe/pair.
  Push40100808060 juga sukses. Auto-pasang tetap skipped/literal false.
- Kontrak kedua image `7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`;
  hash deployer host `2479470f927627ab00d7af26876d6525bef897e52cff77c413ac5656b168c810`.
  Katalog aktif hash6522bc48 tetap identik dengan persetujuan sebelumnya; bukan
  persetujuan draf2 hash589780b3.

Lokal final:1.403 tes terkait lolos (32,53s), compile12 berkas, palang947 berkas,
mutation terisolasi. 5.100 keluaran bawaan identik dengan HEAD awal; 5.100 keluaran
opt-in deterministik antarproses. Reviewer read-only: OK with notes **fondasi
nonaktif saja**; guard enum cabang diperbaiki dan dimutasi sebelum commit.

Produksi awal fb7f64b healthy. Pull dua digest → preflight exact-image schema
read-only dan writer0 sebelum maintenance → backup coherent empat DB+auth,
riset terpisah → rehearsal C2–B2–C2 dan validator → hash backup lokal/remote →
approval sekali pakai → deploy exit0 → reopen. Hash10 tabel histori tetap, config,
Caddy dan dua cron kembali identik. Smoke publik jagomat.id `/`200, `/akun`401,
`/murid/`303 ke `/masuk`; marker galat0. Probe in-memory pada container membuktikan
kedua revisi penilaian nonaktif; tidak menggunakan akun/hasil anak untuk test.

Empat turunan rehearsal dibersihkan; backup/receipt privat dipertahankan dengan
ID `deploy-catalog-followup-20261024`. Bukti lokal di folder ignored
`docs/plan/deploy-catalog-followup-20261024/`; paket34 contoh review exact di
`docs/plan/catalog-followup-review-exact-c335ce5/`. WIP UI sesi lain tidak masuk
commit/image ini. Recovery belum mendukung marker2: aktivasi berikutnya tetap
wajib review manusia, reader recovery dan pair konten baru.

## Deploy filter instan Ruang guru — 22 Oktober 2026

Controlled `deploy-v2` berhasil memasang **fb7f64bbb83a199190e88dda640793ea72f7bb93**
pada 22.18 WIB (container started `2026-10-22T15:18:01Z`). Perubahan: filter instan chip
langkah di `/guru` (JS berhash CSP `guru_browser.py`, disetujui pemilik 22 Oktober; hanya
menyembunyikan/menampilkan kartu yang sudah dirender server, tanpa network/storage/eval,
fallback tautan GET utuh). CSP beranda guru kini memuat tiga hash skrip dan tetap tanpa
`connect-src`. Tidak ada perubahan schema, data, atau config.

- Candidate digest `sha256:d6440a99420b02d36098ff766fa2067a0538f74bd4ac7daeb37fbe209b403f6f`.
- Recovery **edd323c4822347f6d584bb0f311e76cac4962e40**, digest
  `sha256:a7aea9b2c8acd4c613879b64052819d7193add32c387404d7775ec4ce61b206b`.
- Dispatch gate [39800524048](https://github.com/clarinovist/jagomat/actions/runs/39800524048):
  seluruh job sukses (empat shard kandidat, empat shard recovery, build, Status CI), manifest
  pair terverifikasi, 14.189 tes kandidat exact-once tanpa kegagalan, katalog identik dengan
  yang disetujui. Snapshot API sempat telat memperbarui status job recovery; hasil akhir
  dibaca ulang eksplisit sebelum cutover.
- Kontrak kedua image tetap `7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`;
  deployer host tetap `2479470f927627ab00d7af26876d6525bef897e52cff77c413ac5656b168c810`.

Produksi awal `2a86eba` healthy. Prosedur sama dengan rilis sebelumnya: kedua digest ditarik,
preflight read-only, backup coherent empat DB+auth dan riset terpisah (hash remote/lokal
cocok), rehearsal C2–B2–C2, approval exact-pair sekali pakai, cutover exit 0, histori 10 tabel
terjaga, Caddy/dua cron/config dipulihkan hash-identik. Smoke eksternal `https://jagomat.id`:
`/`200, `/akun`401, `/guru` anonim 401, `/murid/`303. Marker galat nol. Perilaku filter
diverifikasi di Chrome headless dengan data sintetis lokal (klik chip, hitungan, `aria-current`,
form pencarian, klik modifier); **belum** diuji pada halaman live berdata keluarga. Bila skrip
diblokir, chip tetap tautan biasa. Esc menutup menu akun belum disetujui/dikerjakan.

Backup induk/receipt tetap privat dengan ID `deploy-guru-fb7f64b-20261022`; bukti ignored di
`docs/plan/deploy-guru-fb7f64b/`. Mode migrasi/job pasang otomatis tetap false.

## Deploy Ruang guru selaras mockup — 22 Oktober 2026

Controlled `deploy-v2` berhasil memasang **2a86ebad563359b40d6c6e83b1b6b0b414c4cc9c**
pada 21.48 WIB (container started `2026-10-22T14:48:05Z`). Perubahan hanya tampilan `/guru`:
kartu anak dengan satu tombol aksi, chip kelompok berhitungan (tautan GET tanpa JS), pencarian
bersyarat, penjelasan daftar sebagai teks terlihat, dan modul render `guru_beranda_pages.py`.

- Candidate digest `sha256:f67ebac4a2b55b0812c5511a15d54fc99f4d6def438e0bcf60e728425e54ed73`.
- Recovery **edd323c4822347f6d584bb0f311e76cac4962e40**, digest
  `sha256:b8efde239265105a7fdb48ea519041b42d10b10e02163963d7e5bcae236b4479`.
- Dispatch gate [39795907908](https://github.com/clarinovist/jagomat/actions/runs/39795907908):
  manifest pair terverifikasi, empat shard kandidat exit 0, 14.179 tes terpilih tepat sekali
  tanpa kegagalan, katalog identik dengan yang disetujui. CI push 39794999922 sukses.
  **Catatan:** API GitHub sempat menampilkan beberapa job (kandidat 1/4, agregat, build) tanpa
  hasil padahal run berstatus sukses dan artifact manifest/shard sudah terbit; keputusan memakai
  artifact exact di atas, bukan status job itu.
- Kontrak kedua image tetap `7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`;
  deployer host tetap `2479470f927627ab00d7af26876d6525bef897e52cff77c413ac5656b168c810`.

Produksi awal `250b875` healthy. Kedua digest ditarik; revision, kontrak, config dan
`PROBE_SKEMA` live read-only lulus sebelum maintenance. Backup coherent empat DB+auth dan riset
terpisah diverifikasi hash remote/lokal. Rehearsal preservasi C2–B2–C2, validator bundle,
integrity/FK lulus. Tidak ada migrasi, koreksi data, atau perubahan izin/retensi/config.
Cutover exit 0, kandidat healthy, restart 0; jumlah baris dan hash 10 tabel histori terjaga,
Caddy/dua cron/config dipulihkan hash-identik. Smoke eksternal `https://jagomat.id`: `/`200,
`/akun`401, `/guru` anonim 401, `/murid/`303 ke `/masuk`; domain lama mengalihkan 308. Marker
Traceback/OperationalError/IntegrityError nol. Probe sintetis dalam container memastikan modul
dan CSS Ruang guru terbaru. Tidak ada walkthrough akun keluarga atau klaim penerimaan visual live.

Lokal: 278 tes yang menyentuh markup guru lama, 134 tes ulang akhir, 9 tes mutasi pencarian/akses,
dan helper/probe sintetis lulus. Empat turunan rehearsal dibersihkan; backup induk/receipt tetap
privat dengan ID `deploy-guru-2a86eba-20261022`. Bukti ignored di `docs/plan/deploy-guru-2a86eba/`.
Mode migrasi/job pasang otomatis tetap false.

## Deploy selaras mockup akun — 22 Oktober 2026

Controlled `deploy-v2` berhasil memasang **250b875e018e8f6f9ed0596dbca9553a3bafe9db**
pada 15.10 WIB (container started `2026-10-22T08:10:34Z`). Perubahan hanya tampilan:
label/placeholder form sandi, status Kesepakatan satu baris, catatan Langganan berikon,
kolom 46rem untuk Persetujuan (tinjau) dan Data Pendamping, serta CSS HP.

- Candidate digest `sha256:78c300dc25fd688ca34ee2a75f297cd97d03bf144b42e2adcbd50834e3048bda`.
- Recovery **edd323c4822347f6d584bb0f311e76cac4962e40**, digest
  `sha256:b6960349378ef8e6aeab50be03ebf9c82e8d58dc8306a2345261da241515b47f`.
- [CI lengkap 39738942147](https://github.com/clarinovist/jagomat/actions/runs/39738942147)
  sukses: 14.156 tes kandidat exact-once, seluruh shard recovery, palang/kompilasi,
  build/probe/pair exact. CI push 39737174869 hanya jalur ringan, bukan gate rilis.
- Kontrak kedua image tetap `7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`;
  deployer host tetap `2479470f927627ab00d7af26876d6525bef897e52cff77c413ac5656b168c810`.

Produksi awal `f610d09` healthy. Kedua digest ditarik; revision, kontrak, config dan
`PROBE_SKEMA` live read-only lulus sebelum maintenance. Backup coherent empat DB+auth
dan riset terpisah diverifikasi hash remote/lokal. Rehearsal preservasi C2–B2–C2,
validator bundle, integrity/FK lulus. Tidak ada migrasi, koreksi data, atau perubahan
izin/retensi/config. Cutover exit 0, kandidat healthy; histori 10 tabel terjaga,
Caddy/dua cron/config dipulihkan hash-identik. Smoke eksternal `https://jagomat.id`:
`/`200, `/akun`401, `/murid/`303 ke `/masuk`; loopback sama; marker galat nol. Probe
sintetis dalam container memastikan modul akun terbaru. Tidak ada walkthrough akun
keluarga atau klaim penerimaan visual live.

Lokal: 594 tes deployer/release, 161 tes akun/sensor/pendamping, helper dan probe
sintetis lulus. Empat turunan rehearsal dibersihkan; backup induk/receipt tetap privat
dengan ID `deploy-akun-250b875-20261022`. Bukti ignored di `docs/plan/deploy-akun-250b875/`.
Mode migrasi/job pasang otomatis tetap false.

## Deploy redesain akun — 22 Oktober 2026

Controlled `deploy-v2` berhasil memasang **f610d09b35dade259339b9b349a6c6e2ddca9d1a**
pada 13.08 WIB (container started `2026-10-22T06:08:48Z`), mencakup seluruh
commit aplikasi `origin/main` saat fetch akhir operasi:

- Candidate digest `sha256:f2b8644ca847f125c0f36f2adcc41d5cab83bb769f794af037b5cd199699e37e`.
- Recovery **edd323c4822347f6d584bb0f311e76cac4962e40**, digest
  `sha256:72b531841665a76467eb936e7360f9effafa3661d4d88cabb8eca5d1763ecf43`.
- [CI lengkap 39730859671](https://github.com/clarinovist/jagomat/actions/runs/39730859671)
  sukses: 14.148 tes kandidat exact-once, seluruh shard recovery, palang/kompilasi,
  build/probe/pair exact. CI push 39729799769 sukses, bukan pengganti gate rilis.
- Kontrak kedua image tetap `7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`;
  deployer host tetap `2479470f927627ab00d7af26876d6525bef897e52cff77c413ac5656b168c810`.

Produksi awal `ccb8906` healthy. Kedua digest ditarik; revision, kontrak, config
dan `PROBE_SKEMA` live read-only lulus sebelum maintenance. Backup coherent empat
DB+auth serta riset terpisah diverifikasi hash remote/lokal. Rehearsal preservasi
startup C2–B2–C2 pada turunan, validator bundle, integrity/FK lulus. Tidak ada
migrasi, koreksi data historis, perubahan izin/retensi, atau request provider uji.

Cutover exit0; kandidat healthy. Sebelum membuka akses, jumlah baris dan hash
10 tabel histori terjaga. Caddy/dua cron/config dipulihkan hash-identik. Smoke
eksternal `https://jagomat.id`: `/`200, `/akun`401, `/murid/`303 ke `/masuk`; loopback
sama. Marker Traceback/OperationalError/IntegrityError nol. Probe sintetis dalam
container memastikan modul redesain akun, langganan, persetujuan dan Data Pendamping.
Bank kalimat tetap aktif; revisi penilaian baru tetap nonaktif. Tidak melakukan
walkthrough memakai akun/data keluarga atau mengklaim penerimaan visual live.

Lokal: 345 tes helper/deployer, 33 tes redesain akun, kompilasi helper dan probe
sintetis lulus. Empat direktori turunan rehearsal/validation dibersihkan; backup
induk/receipt tetap privat dengan ID `deploy-akun-f610d09-20261022`. Bukti ignored
di `docs/plan/deploy-akun-f610d09/`. Mode migrasi/job pasang otomatis tetap false.
Commit catatan sesudah operasi tidak mengubah revision image.

## Deploy seluruh commit terbaru — 22 Oktober 2026

Controlled `deploy-v2` berhasil memasang **ccb8906e7475b804a1eac1c267ce4352e8bebf94**
pada 09.44 WIB (container started `2026-10-22T02:44:24Z`):

- Candidate digest `sha256:7519b1372474a509930dd1cabe3d0143e95c81c019ee094156fc61bc1126e1e7`.
- Recovery **edd323c4822347f6d584bb0f311e76cac4962e40**, digest
  `sha256:45c9afae3fd9391bfdae3e48e0e30d89659f57e8fcc1a2bc31fb99457606a54c`.
- [CI lengkap 39711789044](https://github.com/clarinovist/jagomat/actions/runs/39711789044)
  sukses: 14.115 tes kandidat exact-once, seluruh shard recovery, palang/kompilasi,
  build/probe/pair exact. CI push 39710075550 sukses, bukan pengganti gate rilis.
- Kontrak kedua image `7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`;
  deployer host tetap `2479470f927627ab00d7af26876d6525bef897e52cff77c413ac5656b168c810`.

Produksi awal `1472f8c` tertinggal 34 commit. Kedua image ditarik, revision/kontrak/config
dan `PROBE_SKEMA` live read-only lulus **sebelum maintenance**. Bundle coherent
empat DB+auth dan riset terpisah diverifikasi hash remote/lokal. Rehearsal startup
idempoten/preservasi C2–B2–C2, validator bundle, integrity/FK lulus. Tidak ada migrasi
atau koreksi data historis. Approval exact-pair diterbitkan setelah seluruh syarat.

Cutover exit 0, candidate healthy. Sebelum akses dibuka: jumlah baris dan hash 10
tabel histori terjaga; Caddy/dua cron/config dipulihkan hash-identik. Smoke eksternal
`https://jagomat.id`: `/`200, `/akun`401, `/murid/`303 ke `/masuk`; loopback sama.
Marker Traceback/OperationalError/IntegrityError nol pada pemeriksaan pascarilis.
Probe sintetis memastikan katalog writer2/pilot, 15 draf playbook dan modul UI terbaru;
`OSN_BANK_KALIMAT=1` tetap, **revisi penilaian baru nonaktif**. Hash contoh katalog
aktif identik dengan persetujuan sebelumnya, bukan pengesahan pilot/draf baru.

Fetch akhir saat operasi: `origin/main=ccb8906`, tidak ada commit aplikasi tertinggal.
Commit dokumentasi sesudahnya tidak mengubah revision image dan tidak memerlukan
restart/build aplikasi. Mode tetap migrasi; job pasang otomatis tetap false. Tidak ada
walkthrough akun keluarga, request provider uji, atau klaim efektivitas pedagogis.

Empat turunan rehearsal/validation dibersihkan; backup induk/receipt dipertahankan
privat dengan ID `deploy-terbaru-ccb8906-20261022`. Bukti lokal di
`docs/plan/deploy-terbaru-ccb8906/` (ignored); isi data/backup tidak masuk dokumentasi.

## Aktivasi katalog A–C — 21 Oktober 2026

Controlled deploy-v2 berhasil memasang **1472f8c2255f4f9d2c5b552fc71f61a30d194808**,
digest `sha256:c5e70b0fd4c7546c95d0f40f0c277b7c1e115a1460ae0951335952326a488f05`;
recovery **edd323c4822347f6d584bb0f311e76cac4962e40**, digest
`sha256:dea0dcb8a106e57fd6c0aa7104f6b3fc7daa2d8fac68517125b4c5616ee9abdd`.
CI lengkap39610870417 dan push39610870119 sukses. Full kandidat/recovery empat
shard, build/probe dan C→B→C katalog2/pilot lulus. Persetujuan manusia eksplisit
terikat hash konten6522bc48bc9cce2c8edcf354fa1a50adf7b317ea8c6a9a2c83c1097d039e32bc.

Aktivasi awal49a372c ditahan CI karena validator pilot kisi belum memahami marker
katalog2. Reader diperbaiki, regression/mutation ditambahkan, baselineedd323c
(writer katalog1/komposisi1) dibekukan dan diuji CI39609036312 sebelum dipatok.
Koleksi13.896 tes recovery identik arsip exact dan manifest CI. Kandidat final
writer katalog2; tidak memasang env bersama yang mengaktifkan writer recovery.

Preflight dua digest dan metadata skema live read-only lulus sebelum maintenance.
Bundle `deploy-katalog-1472f8c-20261021` empat DB+auth dan riset terpisah diverifikasi
hash remote/lokal. Rehearsal startup/preservasi C–B–C serta validator bundle lulus.
Tanpa migrasi atau koreksi historis: hash sepuluh tabel soal, malrule, jawaban,
diagnosis, snapshot/konfirmasi/konteks tetap sebelum membuka akses.

Cutover exit0, kandidat healthy. Caddy/dua cron/config dipulihkan hash-identik;
probe sintetis dalam memori membuktikan writer2, umur Ari/Bima dan selector pilot.
Smoke publik dari luar VPS `/`200, `/akun`401, `/murid/`303 ke `/masuk`; loopback
sama. Request domain publik dari VPS sempat403 (bukan hasil smoke eksternal);
marker Traceback/OperationalError/IntegrityError nol. Tidak memakai akun/data anak
untuk walkthrough. Empat turunan rehearsal dibersihkan, backup induk/receipt tetap.
Deployer2479470f… tidak diubah; job pasang otomatis tetap false.

## Penyiapan recovery katalog A–C — 21 Oktober 2026

Batch A–C `251d50e` lulus CI39567283483 tetapi writer katalog masih1;
itu bukan bukti aktivasi perbaikan. Baseline berikutnya mempertahankan reader
katalog2 dan marker konteks umur Ari/Bima, dengan writer katalog1 serta komposisi
teori-bilangan1. Mode **persiapan** untuk pembekuan reader, bukan pelemahan gate
rilis: manifest persiapan tidak mengklaim pair teruji atau siap pasang.
Baseline baru **542dcd94132c4b91bca78004643c8eb2c82686d7** lulus full CI39596225447
beserta build/probe digest `sha256:a0be7b3f52679ce8f2ab72997755d1530be37c011a18a2be079457a0952bfac9`.
Fingerprint persistensi tetap7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8;
manifest persiapan tidak mengklaim pair teruji. Kandidat sekarang mematok baseline
ini dan kembali mode migrasi/komposisi2. Probe wajib exercise writer katalog2
meski default aplikasi1, untuk membuktikan C→B→C exact sebelum aktivasi.
Koleksi recovery exact **13.859 nodeid** identik dengan empat manifest CI baseline
(lintas Python3.9/3.12, hash himpunan83c2010d…). Gate kandidat b92ec91 sempat menolak
anchor yang belum terdaftar; jumlah diukur dari arsip immutable sebelum dicatat,
bukan menurunkan guard. Job pasang tetap false, tidak ada deploy.
Contoh tinjauan26 template kini menjadi artefak `catalog-review` terikat SHA/hash;
review manusia belum dinyatakan selesai. Detail [koreksi katalog](catalog-corrections.md).

## Deploy foto opsional dan konfirmasi ringkas — 21 Oktober 2026

Controlled `deploy-v2` berhasil memasang kandidat
`de7c971d9f5c1280f96fc3ad90bcd34be9be644c`, digest
`sha256:91d828ea9e8c6db798a3489032afade7ee0bcfa9c1e5e19a2e2f8f58456789d1`;
recovery `c228749faef8acf29b7d6895173ead6aa5bc9e66`, digest
`sha256:b31048a3149fcc3ef899734b195a01d42ab0b2c9eb9ee90bca65fce4c0d7cde7`.
CI lengkap `39551837740` lulus 13.628 tes kandidat exact-once, seluruh shard
recovery, kompilasi, build/probe/pair; CI push `39551836769` sukses.

P3 menyembunyikan upload PG tanpa lampiran; P2 memakai lipatan native dengan
preview bacaan awal dan Terapkan eksplisit; P1 Tahap 1 memberi tautan foto pada
kategori tinjauan yang sesuai dan tujuan upload tersedia, bukan sesi dibatalkan.
Upload lewat tautan anak tetap tertutup; handler, kuota dan skema tidak berubah.
Lokal 172 tes terkait termasuk mutation lulus; browser sintetis 390/1024px
membuktikan field terlipat tetap masuk FormData, keyboard bekerja dan tidak ada
overflow. Ini bukan bukti empiris pengurangan beban orang tua.

Produksi awal `1406079` healthy; kedua image exact ditarik dan probe metadata live
read-only lulus sebelum hold. Bundle `deploy-foto-de7c971-20261021` empat DB+auth
serta riset terpisah terverifikasi hash remote/lokal. Rehearsal preservasi startup
C2–B2–C2, validator bundle, integrity/FK lulus; tanpa migrasi atau request provider.

Cutover exit0, kandidat healthy; schema dan jumlah baris terjaga sebelum membuka
akses. Caddy/cron/config dipulihkan hash-identik, bank kalimat tetap aktif. Marker
source foto ditemukan pada container live; smoke `/`200, `/akun`401,
`/murid/`303 ke `/masuk` lulus. Marker Traceback/OperationalError/IntegrityError nol.
Backup induk dan receipt dipertahankan, turunan rehearsal/helper remote dibersihkan.
Deployer tetap `2479470f…`; job pasang otomatis tetap nonaktif. Tidak melakukan
walkthrough memakai akun/data keluarga atau memperluas kapabilitas tautan anak.

## Rilis bantuan non-AI dan kendali data Pendamping — 21 Oktober 2026

Controlled `deploy-v2` berhasil memasang kandidat
`1406079e9b805450c42604d7ac2864804a9de034`, digest
`sha256:57b84789b98a102adb2d6b29124e20d5b64d7067ee5bc65be54eb336b689bb7a`;
recovery `c228749faef8acf29b7d6895173ead6aa5bc9e66`, digest
`sha256:a139936994ad67dff880d3feb77516dd5c27f9bab4c93c36d5910b9f1c884a02`.
CI lengkap `39545456250` lulus 13.593 tes kandidat exact-once, seluruh shard
recovery, build/probe/pair. Kontrak kedua image
`7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`.

Pemeriksaan live sebelum rilis menunjukkan `34f596e` sehat: bantuan non-AI sudah
tercakup pada deployment Fase 4 tersebut; rilis ini menambahkan kendali data
Pendamping tanpa menurunkan versi atau memasukkan WIP foto dari sesi lain.

Kedua image ditarik dan probe schema metadata read-only lulus sebelum maintenance.
Bundle `deploy-pendamping-1406079-20261021` empat DB + auth, serta backup riset
terpisah, diverifikasi hash remote/lokal. Rehearsal preservasi C2–B2–C2 dan
validator bundle lulus. Tidak ada migrasi, perubahan retensi, pencabutan izin,
penghapusan data pengguna, atau request provider dalam operasi rilis.

Cutover exit 0; kandidat healthy, jumlah baris/schema terjaga sebelum membuka
akses. Caddy/cron/config dipulihkan hash-identik; `OSN_BANK_KALIMAT=1` tetap aktif.
Marker source kedua paket ditemukan dalam container yang berjalan. Smoke publik
`/` 200, `/akun` 401, `/murid/` 303 ke `/masuk`, serta `/pendamping/kelola` 401
anonim lulus. Marker Traceback/OperationalError/IntegrityError nol. Alur pengguna
hapus/cabut tidak diuji memakai data keluarga; bukti fungsional berasal dari
fixture dan preview sintetis yang lulus sebelum rilis, bukan walkthrough manusia.

Backup induk dan receipt dipertahankan; turunan rehearsal/helper remote tugas
sudah dibersihkan. Deployer tetap hash `2479470f…`, tanpa build di VPS atau
aktivasi auto-deploy. Prompt AI kandidat hasil eksperimen tidak dipasang.

## Deploy Fase 4 dan aktivasi bank kalimat — 21 Oktober 2026

Controlled `deploy-v2` memasang kandidat
`34f596ea38f791d48d51e70b9139c47c8b77c230`, digest
`sha256:c43c8a5fac02c0a63588da1d3fd4ffe148b96f58d6bb512e17c205c9d15f0f33`;
recovery `c228749faef8acf29b7d6895173ead6aa5bc9e66`, digest
`sha256:d4c5a9dd129c20a7ae0379659147aad466109036fd10bcc2db8414ffa5cb169b`.
CI lengkap `39541440130` sukses (13.572 kandidat exact-once, seluruh recovery,
build/probe/pair), push `39541438305` sukses; isi disetujui manusia sebelum aktivasi.

Preflight metadata live read-only dan probe bank1→off pada kedua image tanpa
volume/provider lulus sebelum maintenance. Bundle
`deploy-fase4-34f596e-20261021T043000Z` empat DB+auth, riset terpisah dan config
asal disimpan; hash backup remote/lokal terverifikasi. Rehearsal pada salinan dengan
bank1 serta validator kanonis lulus. CAS menambah tepat `OSN_BANK_KALIMAT=1` di
`/opt/osn/visual.conf`; byte config lain dipertahankan. Tidak ada migrasi/ubah riwayat.

Cutover exit0, kandidat healthy dan bank aktif terverifikasi memakai contoh
sintetis tanpa menyimpan sesi. Helper reopen sempat berhenti karena membandingkan
Caddy/cron yang sedang held dengan hash sebelum hold; diperbaiki terbatas agar
membandingkan hash held untuk maintenance, hash aktivasi untuk env. Setelahnya
semua pemeriksaan lulus dan akses dibuka; tidak ada rollback image/data.
Smoke `/`200, `/akun`401, `/murid/`303 lulus, marker galat teknis0.
Caddy/cron dipulihkan hash-identik; perubahan env hanya flag bank yang disetujui.
Backup induk dipertahankan, turunan rehearsal/helper tugas dibersihkan.
Deployer tetap `2479470f…`; auto-deploy tetap nonaktif. Paket tantangan tetap
file cetak terpisah, bukan menu/sesi/diagnosis baru.

### Kontrak bank kalimat dan recovery

Bank kalimat statis opt-in default0 memerlukan fingerprint penyajian baru
`7a924b190298c326efcedc6f8a1eb0c7bd57579c346b691440984dee069bdae8`.
Schema snapshot tetapv1; teks lama dan kunci/malrule tidak ditulis ulang.
Cache B2 bersnapshot kini diikat fingerprint sumber agar tidak memakai cerita
sumber lain. Baseline recovery Fase4 memuat hook/cache/bank sama tetapi writer
teori-bilangan default1; kandidat default2. Tidak memetakan hash baru ke hash lama.
Baseline **`c228749faef8acf29b7d6895173ead6aa5bc9e66`** dibekukan dalam mode
persiapan untuk mencatat mismatch anchor historis. Kandidat kembali migrasi dengan
pin/fingerprint B exact; koleksi B 13.572 tes diverifikasi dari git archive.
Seluruh gate pasangan image exact tersebut telah lulus pada CI di atas.

Probe soal C→B→C mencakup snapshot bank, cache dua sumber tanpa provider, konteks,
konfirmasi, PG dan cetak; artifact rilis memuat manifest bank18 bingkai dan paket
cetak6 tantangan kelas5. Paket cetak tidak punya sesi/DB/diagnosis/penguasaan.
`OSN_BANK_KALIMAT=1` aktif pada deployment di atas setelah tinjauan manusia Fase4.
Default source tetap0; perubahan bank berikutnya memerlukan review/gate baru.

## Deploy kualitas soal Fase 1–3 — 21 Oktober 2026

Controlled `deploy-v2` berhasil memasang kandidat
`690a9801652be4151d1ca3e85ec41d46eb06246c`, digest
`sha256:2bcf11e05ba2ec0fa4069835aee68bca479557e0d6b5eed116263665e70a2616`;
recovery `ff6acb158985f78ef0287ec18fb045d273921bdc`, digest
`sha256:a5e4f45d6d7b763b581638e58142d65f7eb885540d60cdbdaad4c4c3fae4bf1b`.
CI manual `39517155836` lulus 13.507 tes kandidat exact-once dan seluruh shard
recovery, build/probe serta pair exact dengan `question_pair_checks=8`.
CI push `39517155432` juga sukses. Tinjauan manusia dinyatakan lulus pemilik.

Preflight metadata live read-only, kontrak dan hash deployer lulus sebelum hold.
Bundle `deploy-soal-690a980-20261020T234700Z` empat DB + auth dan backup riset
terpisah terverifikasi remote/lokal. Rehearsal startup/preservasi C–B–C pada salinan
backup dan validator kanonis lulus. Tidak ada migrasi atau koreksi data historis.

Cutover exit0; kandidat healthy. P4 tujuh jenis/P5 sepuluh jenis, writer2 dan
reader baru terverifikasi live tanpa membuka data anak. Smoke `/`200, `/akun`401,
`/murid/`303 ke `/masuk` lulus; marker traceback/OperationalError/IntegrityError nol.
Caddy/cron/config dipulihkan hash-identik, helper/turunan rehearsal tugas dibersihkan,
backup induk tetap disimpan. Deployer tetap hash `2479470f…`; mode migrasi dan
job pasang otomatis tetap false. Catatan penyiapan di bawah menjelaskan batas recovery lama.

### Penyiapan dan kontrak recovery soal

Patch keterbagian/modus 20 Oktober 2026 membutuhkan reader cetak yang memakai
kunci/malrule bank tersimpan. Recovery pinned `c71038bb3b8ceedf10e469eb94766aed7c4c8472`
masih merekonstruksi malrule dari template: pada bank baru ia dapat mencetak aturan
yang berbeda dari diagnosis. **Jangan deploy kandidat ini dengan recovery tersebut**,
meskipun gate struktur/persistensi umum lulus. Tidak ada migrasi atau koreksi riwayat.

Recovery yang didukung harus mempertahankan reader cetak bank ketika mengembalikan
generator/template. Tes `test_question_history.py` membuktikan kontrak source ini,
bukan kompatibilitas image pinned. Penyiapan baseline recovery, pembaruan pin/kontrak,
serta gate dan rehearsal pasangan exact telah dituntaskan untuk pasangan di atas.
Batch Fase 3 menambah ID `banyak_kelipatan`, `sisa_operasi`, `banyak_prima` dan
`jumlah_kelipatan`: reader recovery harus mengenal fungsi-fungsi ini untuk
memuat/cetak riwayat soal baru, walaupun writer komposisinya dikembalikan.
Tinjauan manusia sudah dinyatakan lulus oleh pemilik. Baseline recovery baru
memuat reader seluruh jenis dan fix Fase1, tetapi `number_theory_versions.py`
memilih komposisi lama secara default (1); kandidat memilih batch baru (2).
Override `OSN_TEORI_BILANGAN_VERSI` tervalidasi hanya mengatur komposisi writer,
bukan registry reader: `Topik.komposisi` tetap inventaris historis, override
`komposisi_writer` hanya digunakan generator termasuk gabungan. Konteks butir,
katalog laporan dan konfirmasi hasil tetap mengenali ID baru pada B.
Tes domain secara eksplisit memakai2, tes default/image
membuktikan perilaku recovery1 dan kandidat2 secara terpisah.

Gate `release_question_pair.py` menguji C→B→C atas bank/PG sintetis, cetak,
diagnosis, konteks dan arsip tanpa write ulang; termasuk konfirmasi yang dibuat C,
draft C yang dikonfirmasi B, serta pembacaan bukti B→C. Manifest wajib
`question_pair_checks=8`.
Pin baru **`ff6acb158985f78ef0287ec18fb045d273921bdc`** dibekukan setelah scoped test
(269 lulus); kandidat default2 memakai pin tersebut. Koleksi recovery 13.507 tes
terverifikasi dari git archive, fingerprint tetap `8e10d0fc…` tanpa perubahan
skema/deployer. Kedua image exact lulus gate di atas. Mode tetap migrasi/job pasang false;
deployer host tidak diubah.

## Deploy Pendamping konteks dan panel — 20 Oktober 2026

Controlled `deploy-v2` memasang revision
`c7c18fb858c0f2b57f2732a5f1a7a501ecf12b7e`, digest
`sha256:deb6fc258f019b228ac16e904b2e50a9dd786173ad47783a3d19fab1a6844f5c`;
recovery `c71038bb3b8ceedf10e469eb94766aed7c4c8472`, digest
`sha256:ce439ef45768f02051c9484f1a83dcd1bdf4b7dcfc080989d6950022db7276d8`.
Kontrak sama `8e10d0fc114df780918916f923868b567dd4ef1af34797b7b755837301c6aa89`.
Gate manual CI `39410734621` lulus 13.396 tes kandidat exact-once, 13.126 tes
recovery, build/probe, dan pair exact; push `39410726564` juga hijau.

Preflight image/config dan `PROBE_SKEMA` metadata live read-only lulus sebelum hold.
Bundle `deploy-pendamping-c7c18fb-20261020T120000Z` empat DB + auth dan backup riset
terpisah diverifikasi, termasuk hash salinan privat lokal; rehearsal C2–B2–C2,
validator kanonis, preservasi, integrity/FK lulus. Deployer tetap hash `2479470f…`.
Tidak ada migrasi skema, perubahan konfigurasi fitur, atau pemanggilan provider uji.

Cutover exit 0; kandidat healthy, metadata/baris terjaga, Caddy dan kedua cron
pulih byte-identik. Marker konteks profil v2, alias lokal, log aksesibel dan sheet
HP terkonfirmasi dalam source image live tanpa membuka profil keluarga. Smoke
publik `/` 200, `/akun` 401, `/murid/` 303 ke `/masuk` lulus; marker traceback,
OperationalError dan IntegrityError nol. Turunan rehearsal dibersihkan; backup
induk tetap disimpan tanpa prune. Mode migrasi/job pasang otomatis tetap false.
Uji percakapan provider nyata dan keyboard HP fisik tidak termasuk smoke ini.

## Deploy header halaman anak — 20 Oktober 2026

Controlled `deploy-v2` memasang revision
`004858f81992a6a465b00ea644fa35f3192acfdd`, digest
`sha256:c920ee9e64c2d223c5f37f38d1fc2536d21b174f142c0e7deb8022ea821c3af3`;
recovery `c71038bb3b8ceedf10e469eb94766aed7c4c8472`, digest
`sha256:b11d453f0172615c07c81a2402ac184143492b800e61a1ce06c0c3b98427b13b`.
Kontrak sama `8e10d0fc114df780918916f923868b567dd4ef1af34797b7b755837301c6aa89`.
Gate manual CI `39375457567` lulus kandidat/recovery, build, probe, dan pair exact.
Uji lokal terkait header 388 lulus; render sintetis 974/390/320px memverifikasi
konten pertama y185/y181/y181, tab sticky, target sentuh, menu, dan binding form.

Preflight image/config serta `PROBE_SKEMA` read-only lulus sebelum hold. Bundle
`deploy-header-004858f-20261020T060000Z` empat DB + auth, backup riset terpisah,
validator kanonis, rehearsal exact C2–B2–C2, integrity/FK dan preservasi lulus;
salinan backup privat lokal diverifikasi hash. Tidak ada migrasi skema atau
perubahan konfigurasi fitur. Deployer tetap hash `2479470f…`.

Cutover exit 0, kandidat healthy; metadata/baris terjaga dan Caddy/dua cron pulih
byte-identik. Marker header scoped dan sticky terkonfirmasi dalam image live,
tanpa membuka profil keluarga. Smoke publik `/` 200, `/akun` 401, `/murid/` 303 ke
`/masuk` lulus; marker traceback/OperationalError/IntegrityError nol. Turunan
rehearsal dibersihkan, backup induk dipertahankan tanpa prune. Mode tetap migrasi
dan job pasang otomatis tetap false.

## Deploy pemilih tema admin — 20 Oktober 2026

Controlled `deploy-v2` memasang revision
`babcdb5d6386a1cf1db32a81b3bcd7cc97ebaac8`, digest
`sha256:23cf2cdbde860b061fbc4ec13b62c78771dd935b1147e8908adf9d5bf7a163b7`;
recovery `c71038bb3b8ceedf10e469eb94766aed7c4c8472`, digest
`sha256:c7658cb027605f325bd5c3811ea3fab99585ba7b865104fd4ba5d15f057ecca9`.
Kontrak sama `8e10d0fc114df780918916f923868b567dd4ef1af34797b7b755837301c6aa89`.
Gate manual final CI `39359933527` lulus seluruh shard kandidat/recovery, build,
probe, dan pair exact. Dispatch awal `39358936623` gagal karena baseline test form
belum mengecualikan kontrak form tema yang memang baru; kontrak test diperbaiki
secara terarah pada commit final, bukan dilewati.

Preflight image dan snapshot metadata read-only lulus sebelum hold. Bundle
`deploy-admin-theme-babcdb5-20261020T024723Z` berisi empat DB + auth; riset
dicadangkan terpisah pada cutoff yang sama. Rehearsal validator dan C2–B2–C2 exact
image menjaga integrity/FK serta metadata/baris. Approval exact-pair sekali pakai
diterbitkan sesudah hold, backup, dan rehearsal; deployer terpasang tetap hash
`2479470f…`. Cutover exit 0, candidate healthy, Caddy dan dua cron pulih
byte-identik. Image live memuat kontrol Sistem/Terang/Gelap serta penerapan
server-side; smoke publik `/` 200, `/akun` 401, `/murid/` 303 ke `/masuk` lulus,
marker galat teknis nol. Bundle induk dipertahankan tanpa prune dan helper sementara
dibersihkan. Mode tetap migrasi, job pasang CI tetap false.

## Deploy dark mode admin — 20 Oktober 2026

Controlled `deploy-v2` memasang revision
`f94619afa6a5a336d441251f1e5f35da26e7c24a`, digest
`sha256:0439b1bed24871e83223bd0b7b721eb9451d216322c6718777ce842b40e93a32`;
recovery `c71038bb3b8ceedf10e469eb94766aed7c4c8472`, digest
`sha256:1645c72658cc9ae733f7cb522692932394fb0811a732932edbd5c89b10dc1557`.
Kontrak sama `8e10d0fc114df780918916f923868b567dd4ef1af34797b7b755837301c6aa89`.
Gate manual CI `39342489319` lulus seluruh shard kandidat/recovery, build, probe,
dan pair exact tanpa provider call. Mode tetap migrasi dan job pasang CI tetap false.

Preflight image/metadata read-only lulus sebelum hold. Bundle
`deploy-admin-dark-f94619a-20261019T234729Z` berisi empat DB + auth; backup riset
terpisah pada cutoff yang sama. Rehearsal validator dan C2–B2–C2 exact image menjaga
integrity/FK serta metadata/baris. Attempt awal setelah hold berhenti sebelum approval,
migrasi, atau swap karena modul operator rehearsal tidak tersedia di host; current
sudah ditahan dan bundle tetap utuh. Modul source exact dipakai privat untuk melanjutkan
rehearsal, lalu dibersihkan sebelum approval sekali pakai diterbitkan.

Deployer terpasang cocok source (`2479470f…`); cutover exit 0 dan candidate healthy.
Caddy serta dua cron dipulihkan byte-identik. Container live memuat media query dark
mode dan chevron bertema; smoke publik `/` 200, `/akun` 401, `/murid/` 303 ke `/masuk`
lulus. Marker galat teknis pascarilis nol. Bundle induk dan bukti operasi dipertahankan
tanpa prune; helper/probe sementara dibersihkan.

## Deploy persetujuan awal terpadu — 18 Oktober 2026

Kandidat `5ee3b844001074a601a564f945a0c833dfe6fd78`, digest
`sha256:0a37f88915619476e487d17758185cdf11c12240a936a79ad61cc6efa32c15f9`;
recovery `c71038bb3b8ceedf10e469eb94766aed7c4c8472`, digest
`sha256:6fd46ec45fbe50e8e22b48fe67a4d4c597694b65396f439a82f535decf5bfa03`.
Kontrak sama `8e10d0fc114df780918916f923868b567dd4ef1af34797b7b755837301c6aa89`.
CI `39127519019` lulus seluruh kandidat/recovery, build, probe dan pair policy6/sensor8.
Kegagalan CSS scope pada run awal diperbaiki, bukan dilewati.

Preflight read-only lulus sebelum hold. Bundle `deploy-policy-20261018T140000Z`
empat DB+auth serta backup riset terpisah diverifikasi; rehearsal C2–B2–C2,
migrasi policy opt-in, integrity/FK dan preservasi tabel lama lulus. Deployer teruji
dipasang atomik. Epoch consent eksternal dikonfigurasi sekali di host, tidak di dalam
bundle DB: restart normal mempertahankan izin, **restore wajib rotasi epoch dan
recreate proses**, bukan docker restart. Lihat [kontrak persetujuan](persetujuan-awal.md).

Controlled deploy-v2 exit0, image sehat; Caddy/cron dipulihkan hash-identik. Tidak
ada receipt/peserta policy dibuat otomatis. Smoke `/`, `/syarat-penggunaan`,
`/kebijakan-privasi`200, `/akun`401, `/murid/`303 lulus. Marker galat teknis pascarilis
nol. Turunan rehearsal dibersihkan; kedua backup dipertahankan. Mode tetap migrasi,
job pasang otomatis tetap false. Persetujuan provider AI dan KPI lama tidak disatukan.

## Deploy sensor perbaikan internal — 18 Oktober 2026

Controlled `deploy-v2` kandidat `bd2c6c6783687c2f1661d128f2f2900b1148c761`,
digest `sha256:ddede3b3ccbeb9feb39a583f905d9d9b9f3855e387c789b69f119ac72a2bdf3a`;
recovery `b76c15a5c2b464c17d6343324bfdfa978818bfc2`, digest
`sha256:df90b4650dee9cac2d93d53366217d6ab8e12cfe7fd55ba0478c82bb26a0623b`.
Kontrak keduanya `af2ff2122f78bf6d80a041ef9436dc01075e10354a8ac918ca8def0018189395`.
CI dispatch `39122534114` lulus seluruh shard kandidat/recovery, build, probe image,
dan pair termasuk sensor (provider calls 0). Mode tetap migrasi; job pasang false.

Preflight metadata live sebelum hold lulus. Attempt awal dibatalkan sebelum migrasi
karena helper pemeriksaan belum menutup handle SQLite; layanan segera dipulihkan,
helper diperbaiki dengan regression, dan backup final diambil ulang. Bundle final
`deploy-sensor-20261018T100000Z` coherent empat DB+auth, rehearsal C2–B2–C2,
preservasi/integrity/FK serta hash backup lulus. Namespace sensor dipasang opt-in,
admin versi9 tidak berubah; tidak ada backfill atau enrollment otomatis.

Deployer teruji dipasang atomik (hash `b4d9ab64fd8423a7fbcb4cb1658c3ce21141a2333f9ea6e4f45bb54b83e3e45c`).
`SENSOR_KOLEKSI_SIAP=1` menawarkan consent di Akun, bukan izin koleksi seluruh keluarga;
KPI lama tetap OFF. Cutover exit0, kandidat healthy, Caddy/cron dipulihkan hash-identik,
tabel lama terjaga. Smoke publik `/`200, `/akun`401, `/murid/`303 ke `/masuk` lulus;
marker galat teknis pada log pascarilis nol. Turunan rehearsal dibersihkan, induk
backup dipertahankan. Feature riset existing yang belum live ikut terpasang dan
startup membuat DB riset kosong terpisah. Kontrak [sensor](sensor-perbaikan.md).

## Deploy riwayat mockup-v2 — 4 Oktober 2026

Cutover terkontrol `deploy-40c55ba-20261004T133000Z` untuk revision
`40c55bab32f4f20f0a590465079178b7ec512606` (section riwayat: filter terbuka +
search, pil status berhitungan, 4 kartu stat + rentetan, rel timeline, CTA
kontekstual, primer semua viewport; tanpa schema/migrasi, kontrak persistensi
identik `fc68c8bc…`). Kandidat digest `sha256:2ce151bd…`, recovery `1f056352…`
digest `sha256:0aebb63b…` (pair proof CI, provider_calls 0). Gate dispatch
`37204841596` (delapan shard kandidat+recovery + build + uji pair) lulus; push
`37204693271` hijau; mode tetap `migrasi`, job `pasang` CI tetap literal false.

`PROBE_SKEMA` implisit via prepare (label revisi + kontrak kedua image, env
identik, integrity/FK, tanpa pending) lulus sebelum hold. Bundle backup
`deploy-40c55ba-20261004T133000Z` (empat DB + auth `sandi.json`, SQLite backup
API, tanpa prune) + rehearsal preservasi C2–B2–C2 (siapkan idempoten, baris
identik) + validasi bundle kanonis lulus. Temuan: bundle live perlu
rekonsiliasi jurnal (normal, tanpa assert seperti template Oct-01); biner
deployer terukur `b9403116…` (berubah sejak pin Oct-01 `94ab137b…`, tidak diubah
sesi ini, dicatat). Approval exact-pair sekali pakai (TTL 600 detik) dan
deployer exit 0. Jendela hold: blok Caddy Jagomat → 503, dua cron `osn-*`
dipause; tumpukan polyflow tidak tersentuh.

Pasca-swap: container sehat rev `40c55ba`, integritas/FK bersih, baris
identik baseline, Caddy + kedua cron dipulihkan byte-identik. Smoke publik
`/` 200, `/akun` 401, `/murid/` 303 ke `/masuk` lulus. Bundle induk
dipertahankan tanpa prune.

## Deploy riwayat kartu timeline — 4 Oktober 2026

Cutover terkontrol `deploy-v2` untuk revision `b08a00935ab44d65c060989daae8b8f099d466c4`
(riwayat tabel menjadi kartu timeline grup tanggal + preset rentang cepat + sidebar
lipat admin; dua assert kontrak test diselaraskan tanpa mengubah runtime).
Kandidat digest `sha256:9e050502…`, recovery `1f056352…` digest `sha256:627104ba…`,
kontrak persistensi identik `fc68c8bc…` (pair proof CI). Gate dispatch `37199029709`
(delapan shard kandidat+recovery + build + uji pair) lulus; push `37198922110` hijau
setelah selaras kontrak; mode tetap `migrasi`, job `pasang` CI tetap literal false.

`PROBE_SKEMA` ringan kandidat terhadap metadata DB live (`mode=ro`/`query_only`,
tanpa network, migrasi, atau import startup) lulus sebelum hold: label revisi image
`b08a009` cocok digest exact, agregat live sesi 37/siswa 8. Bundle backup
`deploy-b08a009-20261004T114300Z` (empat DB + auth `sandi.json`, SQLite backup API,
tanpa prune, manifest integritas/FK/preservasi) lolos: latihan 7227, pendamping 44,
admin-control 2288, ai-control 22. Rehearsal kandidat pada turunan identik: healthy,
smoke loopback `/` 200 dan `/akun` 401 lulus, sesi 37 identik; turunan dibersihkan.
Approval exact-pair sekali pakai (TTL 600 detik) dan deployer exit 0.
Jendela hold: blok Caddy Jagomat → 503 (polyflow tidak tersentuh; tidak ada cron
`osn-*` aktif); Caddy dipulihkan byte-identik (`7a1485b6…`).

Pasca-swap: container sehat rev `b08a009`, smoke publik `/` 200, `/akun` 401,
`/murid/` 303 ke `/masuk` lulus. Bundle induk dipertahankan tanpa prune.

## Deploy sembunyi-cetak + gerak modern — 4 Oktober 2026

Cutover terkontrol `deploy-v2` untuk revision `f542b704c665b760c8da24cea11eecc3859221ed`
(CTA cetak disembunyikan dari pil sesi guru dan halaman murid; token `DURASI_*` +
blok animasi CSS-only Zero-JS; kontrak navigasi `aria-current` halaman cetak diselaraskan).
Kandidat digest `sha256:612301d0…`, recovery `1f056352…` digest `sha256:c40d547d…`,
kontrak persistensi identik (pair proof CI). Gate dispatch `37189431272` (delapan shard
kandidat+recovery + build + uji pair) lulus; mode tetap `migrasi`, job `pasang` CI
tetap literal false. Push `4f19962` sempat merah satu test navigasi lalu hijau kembali
pada `f542b70` setelah kontrak test diselaraskan dengan keputusan sembunyi.

`PROBE_SKEMA` ringan kandidat terhadap metadata DB live (`mode=ro`, tanpa network,
migrasi, atau import startup) lulus sebelum hold: label revisi image `f542b70` cocok
digest exact, agregat live 7215/44/2252/22 baris. Bundle backup
`deploy-opsi1-f542b70-20261004T084727Z` (empat DB + auth `sandi.json`,
SQLite backup API, tanpa prune) lolos integritas/FK/preservasi baris. Rehearsal kandidat
pada turunan identik: healthy, smoke loopback `/` 200 dan `/akun` 401 lulus; turunan
dibersihkan. Approval exact-pair sekali pakai (TTL 600 detik) dan deployer exit 0.
Jendela hold: blok Caddy Jagomat → 503, dua cron `osn-*` dipause; site polyflow
pada Caddyfile yang sama tidak tersentuh.

Pasca-swap: container sehat rev `f542b70`, Caddy dipulihkan byte-identik
(`7a1485b6…`) serta cron 2/2 tanpa sisa pause, smoke publik `/` 200, `/akun` 401,
`/murid/` 303 ke `/masuk` lulus. Workdir rehearsal dan log sementara dibersihkan;
bundle induk dipertahankan tanpa prune.

## Deploy scope laporan + tipografi dewasa — 4 Oktober 2026

Cutover terkontrol `deploy-v2` untuk revision `ce5216f619b6f10ab0f0256bc01855704a8442f8`
(scope CSS `laporan-editorial-st` di tab Perkembangan yang memperbaiki kata menempel,
penyeragaman font body/heading dewasa ke token, tokenisasi ukuran teks kecil,
breakpoint admin ke `LEBAR_LANDING`, plus regression test scope laporan).
Kandidat digest `sha256:4a3e98b7…`, recovery `1f056352…` digest `sha256:ea0d290a…`,
kontrak persistensi identik `fc68c8bc…`. Gate dispatch `37185889774` (delapan shard
kandidat+recovery + build + uji pair) lulus; mode tetap `migrasi`, job `pasang` CI
tetap literal false.

`PROBE_SKEMA` kandidat terhadap metadata DB live (koneksi `mode=ro`/`query_only`,
tanpa network, migrasi, atau import startup) lulus sebelum Caddy/cron ditahan.
Bundle backup `deploy-ce5216f-20261004T074233Z` (empat DB + auth `sandi.json`,
SQLite backup API, tanpa prune) lolos integritas/FK/preservasi baris (agregat
2240/22/7215/44 baris). Rehearsal C–B–C pada turunan identik. Approval exact-pair
sekali pakai (TTL 600 detik) dan deployer exit 0. Jendela hold: blok Caddy Jagomat
→ 503, dua cron `osn-*`, dan writer; tumpukan polyflow tidak tersentuh.

Pasca-swap: container sehat rev `ce5216f`, Caddy dipulihkan byte-identik
(`7a1485b6…`) serta cron 2/2, smoke anonim `/` 200, `/akun` 401, `/murid/` 303
ke `/masuk` lulus. Workdir rehearsal, container probe, dan log sementara
dibersihkan; bundle induk dan salinan lokal dipertahankan.

## Deploy produksi satu halaman Perkembangan — 4 Oktober 2026

Cutover terkontrol `deploy-v2` untuk revision `26c3912b2375c1b40ab651a65f3773a5cbd6f655`
(tiga bagian Perkembangan disatukan menjadi satu halaman anchor `#progres`, `#materi`,
`#perjalanan`; hero kartu dan sub-nav dihapus, sub-view lama menjadi disclosure, dan
`?section=` lama tetap diterima sebagai alias anchor). Kandidat digest
`sha256:6a7e0901…`, recovery `1f056352…` digest `sha256:a98ff9ac…`, kontrak persistensi
identik `fc68c8bc…`. Gate dispatch `37161920076` (empat shard kandidat + empat shard
recovery + build + uji pair) lulus; mode tetap `migrasi` dan `siap_pasang=false`, job
`pasang` CI tetap literal false.

`PROBE_SKEMA` kandidat terhadap metadata DB live (koneksi `mode=ro`/`query_only`, tanpa
network, migrasi, atau import startup) lulus sebelum Caddy/cron ditahan. Bundle backup
`deploy-perkembangan-26c3912-20261004T001647Z` (empat DB + auth `sandi.json`, SQLite
backup API, jurnal `delete`, tanpa prune) lolos integritas/FK/preservasi baris. Rehearsal
C–B–C pada turunan berjalan healthy dengan baris identik baseline, lalu approval
exact-pair sekali pakai `.approval-consumed-246ac599…` (TTL 600 s) dan deployer exit 0.
Jendela penahan cron `osn-*` + Caddy sekitar 5 menit; Caddy melayani juga site
polyflow.uk pada Caddyfile yang sama, sehingga site itu ikut tidak terjangkau pada
jendela tersebut.

Pasca-swap: container sehat rev `26c3912` (kode live memuat `ANGKOR_LAPORAN` dan tidak
memuat CSS hero), Caddy serta cron `osn-*` dipulihkan, artefak pasangan tertulis dengan
mode `migrasi`, smoke anonim `/` 200, `/akun` 401, `/murid/` 303 ke `/masuk` lulus.
Backup induk tetap tersimpan di `/opt/osn/cadangan/` tanpa prune dan hash-nya cocok
manifest; turunan rehearsal dihapus. Policy rutin host dan job `pasang` CI tidak diubah.

## Deploy produksi UI profil & Perjalanan — 3 Oktober 2026

Cutover terkontrol `deploy-v2` untuk revision `2c40ffaff6f017acdd02527b44c26c273eb98215`:
kandidat digest `sha256:6f66e515…`, recovery `1f056352…` digest `sha256:974b0bf9…`,
kontrak persistensi identik `fc68c8bc…`. Gate dispatch `37126100523` (empat shard
kandidat + empat shard recovery + build + uji pair) lulus; mode tetap `migrasi`
dan `siap_pasang=false`, job `pasang` CI tetap literal false.

Bundle backup `deploy-profil-ui-2c40ffa-20261003` (empat DB + auth `sandi.json`),
rehearsal C2–B2–C2, readiness schema tanpa migrasi, approval exact-pair, deployer
exit 0, lalu reopen. Pasca-swap: container sehat rev `2c40ffa`, Caddy dan cron
dipulihkan ke hash semula, artefak pasangan tertulis, smoke anonim `/` 200,
`/akun` 401, `/murid/` 303 ke `/masuk` lulus. Marker kode baru terbukti ada di
image live (`profil-kembali-st`, `perjalanan-titik-st`) dan `_ringkasan_setelah`
sudah tidak ada. Policy rutin host tetap `enabled=false`; tidak diubah.

## Kandidat soft launch nonkomersial — 1 Oktober 2026

Recovery source dipatok pada `1f056352075578d01caad4d80de382b04aef028f`,
baseline soft launch yang memuat copy akses awal, review privasi, guard verifikasi
reset, primitive penghapusan keluarga, bukti onboarding sintetis, serta gate CI
portable. Baseline ini membekukan tanggal fixture pemulihan pilot agar suite exact
tidak kedaluwarsa setelah hari berganti, tanpa mengubah source runtime. Fingerprint
kontrak persistensinya `fc68c8bc9280663443718bc1c73764cb0c1034e5d0b733deeb36f5994940aba3`.
Pin ini berada di branch recovery immutable `recovery/soft-launch-clock-20261002`.

Mode tetap **migrasi** dan job `pasang` literal false. Kandidat berikutnya wajib
membangun image recovery dan candidate pada run yang sama, menjalankan seluruh shard,
probe, serta pair exact. Pembaruan anchor ini bukan deploy dan tidak menjalankan
primitive terhadap data produksi. Cutover tetap membutuhkan backup coherent empat DB
+ auth, rehearsal, approval exact pair, health, dan smoke anonim.

## Kandidat konfigurasi dukungan — 30 September 2026

Konfigurasi WhatsApp Business, jam layanan, dan SLA memakai schema dukungan
aditif **tanpa bump `user_version` admin9**. Pemasangan hanya melalui migrator
operator `mesin/.venv/bin/python mesin/support_settings.py --database <salinan-terverifikasi>`
atau API `support_settings.migrasikan`; startup/GET tidak memigrasi dan reader publik
fail-closed bila schema/nilai hilang atau rusak. Baseline recovery
`6621f46c2d1d155c9e607441608407a244d185e0` adalah source pertama yang memahami
schema dukungan, dipatok dengan fingerprint
`b972ca3d2aa7b47c8ec85b09ca183d06ab791d1668014f91d50d147e996cbdc7`.
Kandidat rilis wajib membangun ulang B dan C dalam run yang sama serta membuktikan
probe image dan C→B→C `support_pair_checks=8` pada digest exact.

Sebelum cutover: bundle coherent empat DB + `sandi.json`, rehearsal opt-in
`target_dukungan=True` dua kali dengan preservasi state lama, integrity/FK,
backup induk tetap byte-identik, approval exact-pair, dan health. Mode rilis
`migrasi` dengan job `pasang` tetap literal false; cutover hanya melalui
`deploy-v2`, bukan membuka gate CI. Setelah migrasi,
smoke anonim tetap `/` 200, `/akun` 401, `/murid/` 303 ke `/masuk`, lalu verifikasi
halaman publik dan panel memakai fixture sintetis. Runbook operator:
[support-operations.md](support-operations.md).

## Rilis registrasi tanpa variasi dan UX orang tua — 29 September 2026

Recovery source dipatok ke **`634e077830938dbd3ae20d17e5ac019004e97fc2`**:
registrasi menerima variasi belum dipilih dan dapat melanjutkan intent/receipt
kosong, dengan UI sebelum penyederhanaan Pendamping/kartu/header. Fingerprint
candidate/recovery source sama: `05196a2ff3072afa50ec8015235e11dec30b25aaa177ce787ee0121f50a15680`.
Baseline dibekukan pada branch recovery; seluruh suite serta image B dan C diuji
bersama pada run final, bukan klaim baseline pernah lolos CI terpisah.

Mode tetap **migrasi**, job `pasang` literal false. Pair registrasi kini mencakup
enam registrasi sintetis: variasi eksplisit dan kosong, selesai/pending setelah
intent/pending setelah DB, dilanjutkan recovery lalu replay kandidat tanpa
duplikasi. Delapan kelompok gate registrasi existing tetap; tidak melewati gate
untuk memperbarui pin. Recovery lama dc79c82 tetap tes negatif historis.

Tidak ada perubahan schema/migrasi data pengguna dalam rilis ini. Cutover tetap
memerlukan pasangan image exact teruji, backup CURRENT4DB+auth, rehearsal
preservasi C→B→C, approval exact dan health. Jangan mengulang migrasi penutupan
atau mengasumsikan tabel penutupan kosong: data produksi yang ada harus utuh.
Status CI/deployment dicatat berdasarkan pemeriksaan aktual, bukan keberadaan pin.

## Kandidat controlled release panel/admin8 — 27 September 2026

Baseline recovery **`6a18cc745b79d31aa6112270732fbbb5a63cbc27`** mempunyai UI
sebelum panel samping, dispatcher pembayaran v1/v2 dan fencing final worker.
Image baseline tersedia dari [CI36288247714](https://github.com/clarinovist/jagomat/actions/runs/36288247714),
fingerprint `9db53ff1ce3980558e4eb6247996316bdbdd582717efbfc97ab83dc19df66a7e`.
Source kini mematok baseline ini dalam mode **migrasi**, pasang tetap literal false.
Digest baseline terdahulu bukan digest recovery rilis: kedua image harus dibangun
serta diverifikasi bersama pada run final yang sama.

Gate baru `package_pair_checks=8` mencakup kelompok bukti: migrasi admin7→8
idempoten/preservasi; histori invoice/receipt/grant v1; snapshot paket/kalender v2;
replay tanpa duplikasi; fencing final worker; intent dilanjutkan recovery tanpa
charge baru; empat DB/auth/Pendamping4 context-consent-operation; dan pembacaan ulang
candidate atas write recovery. Probe image wajib `package_checks=8` dan
`admin_package_schema=8`, selain gate existing. Probe HTTP juga memeriksa fallback
draf manual/binding panel bila ada dan penolakan murid pada permukaan guru.
Seluruh state probe sintetis, jaringan provider tidak dipanggil.

Deployer source wajib dapat memigrasikan fixture ke admin8, tetapi readiness
read-only menerima admin7 utuh atau admin8 dengan metadata paket lengkap; admin7
parsial bertabel paket ditolak. Marker kini `OSN_IMAGE_ADMIN8_AI2_OK` dan
`OSN_SCHEMA_ADMIN8_AI2_OK`. Ini bukan instalasi deployer VPS atau aktivasi v2:
startup biasa tetap7, paket_v2 eksplisit, entitlement/kuota/trial/refund tetap belum aktif.

**Belum deployment.** Manifest mode migrasi tetap `siap_pasang=false` karena flag
itu eligibility CI rutin. Permintaan operasi yang melarang cutover ketika flag
false harus diklarifikasi sebelum hold/migrasi/deploy-v2; jangan mengubah makna flag
atau membuka auto-routine demi melewati syarat. Backup coherent4DB+auth, rehearsal
exact C→B→C pada turunan, approval teknis/policy/deployer dan health tetap wajib.
Status CI/live akhir dicatat setelah verifikasi, bukan disimpulkan dari pin source.

## Target paket v2 — 27 September 2026

**Checkpoint D1:** ledger admin8 opt-in dan dispatcher v1/v2 sudah di source.
CI `36284376723` pada `8f6fba7` menolak kontrak kandidat `9db53ff1ce3980558e4eb6247996316bdbdd582717efbfc97ab83dc19df66a7e`
yang berbeda dari recovery admin7 `36b6ac95c83d177e8385167dc983ae5bf34ec051289cb61dd02742e199521891`.
Mode source dipindahkan ke **persiapan (build-only)** untuk menyiapkan baseline
recovery berikutnya. Pin recovery admin7 tetap anchor historis; mismatch harus
terlihat, `pair_verified=false` dan `siap_pasang=false`. Semua suite kandidat/recovery
serta build/probe tetap wajib; bukan izin memasang admin8 dengan recovery7.
Job `pasang` tetap literal false. Tidak ada migrasi/deploy produksi pada checkpoint.

[Kontrak Jago/Jago Pro](subscription-packages.md) disetujui untuk penawaran baru.
Katalog/domain dan landing rencana tidak mengaktifkan checkout, trial, promo atau
kuota v2. Ledger v1 dan invoice/grant lama harus tetap identik; pengubahan tarif v1
in-place bukan migrasi yang sah. Penawaran baru memerlukan snapshot paket/periode,
kuota, refund7hari dan transisi eksplisit sebelum aktivasi.

Jika persistensi berubah: bekukan baseline recovery yang dapat membaca/menulis
kedua versi, verifikasi validator/backup/probe/pair pada exact image, baru ubah pin
melalui perubahan rilis terpisah yang direview. Jangan memasang schema baru dengan
recovery781fbcd yang hanya memahami v1. Persiapan tidak memenuhi gate rilis migrasi;
backup coherent4DB+auth, rehearsal idempoten/FK, preflight dan
approvalexact tetap wajib. Tanggal kampanye dan operasi transisi akun lama bukan
side effect dari landing atau migrasi schema.

## Integrasi terisolasi langganan — 24 September 2026

Baseline service `4c88dc956b33ae6246b6f7b15f54e87e6c8f172a` lulus
[CI35995276357](https://github.com/clarinovist/jagomat/actions/runs/35995276357),
11.708 test kandidat, build/probe admin6. Fingerprint persistensi terukur
`608cd64b1b4a4600eceb2c10b87c37e73c7c6a2300201d54fafe7ab7c65802cd`.
Kandidat mematok B ini dan mode `migrasi` untuk mewajibkan pair exact image,
bukan aktivasi rilis. Pasang tetap literal false, semua switch OFF.

Delta C: wrapper registrasi terisolasi (belum caller web); B tetap bisa sinkron
receipt registrasi committed dan melanjutkan query intent pembayaran dari C.
Pair mencakup alur tersebut selain pengiriman/PG/pilot. Tidak ada perubahan schema
baru sesudah admin6, tidak ada migrasi/backfill data pengguna, transaksi provider,
paywall atau deploy. Source/pair teruji tetap bukan klaim produksi telah berubah.

## Riwayat fondasi langganan — source build-only, 24 September 2026

[Kontrak fondasi](subscription-foundation.md) menambah ledger additive admin6,
verifier/probe dan backup/rehearsal. Seluruh switch OFF, tanpa pembayaran/paywall
atau enrollment akun nyata. Metadata kini `persiapan`, pin recovery admin5 tetap;
mismatch persistensi harus dilaporkan, bukan dianggap compatible. Kandidat wajib
`subscription_checks=4`; pair berikutnya wajib `subscription_pair_checks=4` selain
kontrak pengiriman/PG/pilot. Reader admin5 tidak sah untuk ledger admin6.

Tidak ada deploy pada fase ini. Job `pasang` tetap literal false. Keberhasilan CI
build-only bukan bukti pasangan recovery siap rilis atau keadaan live. Snapshot
produksi dan prosedur di bawah tetap historis; tidak dilakukan ulang oleh fondasi.

## Riwayat runtime produksi (source saja) — 25 September 2026

Runtime produksi Midtrans, callback durable, dan pekerja rekonsiliasi ditambahkan sebagai
source + tes ([kontrak](pembayaran-produksi.md)) tanpa tabel/schema baru, jadi kontrak
persistensi dan pair recovery admin7 tidak berubah. Readiness `kebijakan` sengaja false
selama D8/D9 belum diputuskan, tier Admin tetap `nonaktif`, tidak ada secret terpasang,
tanpa pemanggilan Midtrans, dan job `pasang` tetap literal false.

## Aktivasi infrastruktur pembayaran — 26 September 2026

Keputusan D8/D9 pengguna diambil 26 Sep 2026 (ringkasan keputusan:
`docs/plan/2026-09-26-aktivasi-pembayaran.md`, lokal — bukan artefak rilis). Source
aktivasi pada commit ini: entry worker kanonis `mesin/rekonsiliasi_langganan.py` (ikut
wildcard image; `scripts/rekonsiliasi_langganan.py` tetap pembungkus dev/test), installer
runtime produksi sekali per proses di dispatch `web.py` (fail-closed; tanpa secret sah
seluruh sakelar tetap OFF dan situs lain tidak terpengaruh), `KEBIJAKAN_D8_D9 = True`
dengan keputusan tercatat, dan `scripts/deploy.py` membawa mount read-only
`/opt/osn/midtrans` → `/run/secrets/midtrans` di kedua jalur `docker run` (utama dan
recovery) serta menulis artefak `recovery-pair.json` SEBELUM swap (uid 10001, mode 0400) —
gagal tulis = preflight ditolak, container lama tidak disentuh. Validasi host baru:
`/opt/osn/midtrans` wajib ada, root-controlled, tanpa bit tulis group/other, dengan
other-exec agar uid 10001 dapat traversal membaca berkasnya.

Status **setelah cutover terkontrol 26 Sep 2026 (~06:35–06:37 WIB)**: produksi kini
menjalankan revision `1ba7669` (digest kandidat `sha256:39adf0cf…`), container sehat,
mount read-only `/opt/osn/midtrans` → `/run/secrets/midtrans` aktif di container berjalan,
artefak pair `recovery-pair.json` tertulis (uid 10001, 0400), schema admin-control naik
5→7 lewat rehearsal copy backup (migrasi ×2, integrity/FK, preservasi, uji baca image
recovery), dan smoke kanonis lulus (200/401/303). Semua sakelar pembayaran TETAP OFF:
belum ada secret; readiness panel all-false; callback publik menjawab fail-closed (GET 404,
form 415, JSON 503). Cron worker terpasang (`/etc/cron.d/osn-rekonsiliasi-langganan`,
tiap 10 menit; sebelum secret ada, exit 2 "konfigurasi produksi tidak sah" — fail-closed,
terbukti pada tick pertama). Policy rutin ditulis ulang dengan hash terukur dan
`enabled:false` (izin host rutin tetap dicabut eksplisit); mode tetap `migrasi`, recovery
pin `781fbcd`, job `pasang` tetap literal false.

**Pembaruan 26 Sep 2026 (~07:05 WIB) — deploy surface checkout produksi guru:**
cutover terkontrol kedua (revision `6c8e3d6`, digest `sha256:23208048…`): backup bundle
`aktivasi-20260926T000440Z` (4 DB + sandi, root0700), rehearsal idempoten pada salinan
(versi 7/2/4/2, integrity+FK, preservasi 9 tabel) + uji baca image recovery, approval
exact-pair (receipt `.approval-consumed-44981933…`), deployer exit 0. Pasca-swap:
container sehat (rev `6c8e3d6`), mount secret tetap, artefak pasangan diperbarui, modul
`subscription_produksi_http`/`_pages` ada di image, smoke 200/401/303 lulus,
`/langganan` anon 404 (rute butuh sesi guru), callback tetap fail-closed 404/503.
Tier Admin masih `nonaktif`; kenaikan mengikuti keputusan (rekonsiliasi saat secret
aktif, checkout setelah surface + uji pembayaran nyata, tanpa penegakan tanpa keputusan
terpisah). Gap yang dicatat: alur checkout butuh akun ter-enroll — sinkronisasi
enrollment registrasi publik/cutoff dan jalur `transisi` akun lama = keputusan user
terpisah (tidak dikerjakan).

**Pembaruan 26 Sep 2026 (~12:45–12:49 WIB) — cutover ketiga (jalur transisi + buat ulang QR):**
keputusan user: jalur transisi akun lama dulu, sinkron registrasi publik (default OFF)
menyusul, tombol "buat ulang QR" setelah kedaluwarsa terkonfirmasi, guard kunci
ditunda. Source `32c9ef4`/`1922a31`/`ae8f0ce` (CI run `36221351289` SUCCESS); kontrak
pair tetap `36b6ac95…`. Cutover terkontrol (revision `ae8f0ce`, digest
`sha256:988a21b5…`, recovery `781fbcd` digest `sha256:44529507…`): backup bundle
`aktivasi-20260926T054553Z` (4 DB + sandi, integritas ok), rehearsal idempoten pada
salinan untuk KEDUA image (integritas+FK bersih, preservasi seluruh tabel, tanpa tabel
baru), approval exact-pair (receipt `.approval-consumed-dd5b7536…`, TTL 600 s),
deployer exit 0. Pasca-swap: container sehat rev `ae8f0ce`, mount secret tetap (ro),
artefak pasangan diperbarui, modul `aktifkan_transisi`/`daftar_web`/`buat_ulang_qr` ada
di image, RAHASIA-OK, smoke 200/401/303, `/langganan` anon 404, callback fail-closed
404/403. Tier Admin masih `nonaktif`.

**Pembaruan 26 Sep 2026 (~14:08 & 16:55 WIB) — kenaikan tahap rekonsiliasi + perbaikan worker (cutover keempat):**
pemilik menaikkan tahap Admin `nonaktif → rekonsiliasi` (14:08 WIB; sakelar efektif
fondasi/rekonsiliasi true, buat_pembayaran/penegakan false). Tick worker pertama
(14:10) gagal `putaran rekonsiliasi gagal (ValueError)`: CLI meneruskan jam
`time.time()` (float) ke validasi waktu langganan yang hanya menerima int — seluruh
test CLI lama menyuntik `--sekarang` int sehingga jalur cron tak pernah teruji; tabel
langganan produksi kosong (0 invoice) sehingga tanpa efek data. Perbaikan `a51fc0a`
(koersi int + regression merah→hijau + mutation pengunci) lolos CI `36226140631`.
Cutover keempat (candidate `a51fc0a` digest `sha256:c80f2cb9…`, recovery `781fbcd`
digest `sha256:50bc3e6d…`, kontrak tetap `36b6ac95…`): backup bundle
`aktivasi-20260926T095232Z` (4 DB + sandi, integritas ok), rehearsal idempoten pada
salinan untuk kedua image (integritas/FK/preservasi bersih), approval exact-pair
(receipt `.approval-consumed-ec6fd663…`, TTL 600 s), deployer exit 0. Pasca-swap:
container sehat rev `a51fc0a`, RAHASIA-OK, artefak pasangan diperbarui, smoke
200/401/303; worker manual sekali exit 0 dan tick cron natural 17:00 keluar satu baris
JSON agregat `{"kandidat":0,"lunas":0,"menunggu":0,"perlu_diperiksa":0,"dilewati":0,`
`"kesiapan":{...true}}`. Catatan: sesi desain juga men-deploy `f930085` (~14:25 WIB)
sebelum cutover ini.

**Pembaruan 26 Sep 2026 (~17:04–17:31 WIB) — fix jalur transisi akun legacy (cutover kelima):**
percobaan aktivasi oleh pemilik gagal 400 "Isian layanan tidak sah." — direproduksi
terisolasi dari salinan bundle: validator jalur transisi mensyaratkan revisi target >= 1
padahal akun legacy produksi berevisi 0 (`auth.revisi_auth`: "akun legacy tanpa field
bernilai nol"). Fix `0a5c18a` (batas >= 0 di service + handler; regression domain + HTTP
merah→hijau dengan pesan 400 identik produksi; mutation pengunci) lolos CI
`36234991342`. Fix diverifikasi pada salinan data produksi dengan image baru: keenam
akun guru legacy "diaktifkan" (SEMUA OK). Cutover kelima (candidate
`sha256:cd3b730d…`, recovery `781fbcd` digest `sha256:a1327d14…`): bundle
`aktivasi-20260926T102251Z`, rehearsal kedua image bersih, approval exact-pair
`.approval-consumed-265ca7f0…`, deployer exit 0; pasca-swap rev `0a5c18a` healthy,
smoke 200/401/303, worker tick 17:30 exit 0 dengan JSON agregat. **Aktivasi akun uji
oleh pemilik lewat panel BERHASIL**: enrollment tepat 1 baris `asal='transisi'`, tanpa
efek invoice/receipt/grant; tier tetap `rekonsiliasi`.

**Pembaruan 26 Sep 2026 (~19:43–20:10 WIB) — tahap checkout + uji pembayaran pertama menemukan kanal QRIS belum aktif:**
pemilik menaikkan tahap Admin `rekonsiliasi → checkout` (revisi 3, 19:43:45 WIB; sakelar
efektif `buat_pembayaran=true`, kesiapan all-true, tick cron 19:50 exit 0). Uji 1
pembayaran oleh pemilik: tagihan 1 profil Rp35.000 (enrollment `transisi`, tarif
lanjutan), "Buat QRIS" mencatat intent tetapi create ditolak provider **402 "Payment
channel is not activated."** — kanal QRIS belum aktif pada merchant M822252555 (kunci
valid: query status dijawab normal; tidak ada transaksi, tanpa dana tertahan). Tiga
cacat permukaan ditemukan dan diperbaiki di `23728db` (CI `36246316081` SUCCESS; full
suite 12138 lulus `-W error`; palang bersih): (1) judul tagihan menghitung panjang
string `profil_json` — tampil "3 profil" untuk 1 profil; (2) sentinel 404 "Transaction
doesn't exist." dianggap tak dikenal sehingga retry create tidak pernah terjadi — kini
`tanpa_transaksi` fail-closed + retry create ber-kunci idempoten KANONIS invoice (replay
aman menurut kontrak Midtrans, tanpa charge kedua); (3) copy "Kode pembayaran
sebelumnya tidak lagi berlaku" menyesatkan saat tidak ada kode yang pernah diterbitkan
— pesan netral baru. Deployment fix menunggu cutover keenam setelah pemilik mengaktifkan
QRIS di dashboard Midtrans.

Terbuka dan menunggu aksi pengguna: (1) aktivasi kanal QRIS di dashboard Midtrans
merchant M822252555 (tanpa itu create selalu ditolak 402); (2) cutover keenam membawa
fix `23728db`; (3) ulangi uji pembayaran lalu verifikasi receipt+grant agregat oleh
agent. Sinkron enrollment registrasi publik sudah ter-wire dengan `CUTOFF_AKTIVASI =
None` (default OFF) — pengaktifan sinkron menunggu keputusan pembukaan publik.
`penegakan` tanpa keputusan terpisah.

## Snapshot sebelumnya — 22 September 2026

Pisahkan source, artefak CI, dan produksi; bagian bertanggal lebih lama di bawah
adalah histori, bukan perintah menjalankan ulang cutover.

- Kandidat kode `7ac63da51046b6523ac57e520ed83109c4202ce4` dan recovery
  `e206563468afb805af9612711f3c4d0f9ec81539` lolos
  [run CI 35668660016](https://github.com/clarinovist/jagomat/actions/runs/35668660016):
  **11.429 tes kandidat, 11.425 tes recovery**, build/probe kedua image dan uji pair.
  Perbaikan kalender dijelaskan di [kontrak WIB](domain-clock-release.md).
- Manifest run tersebut: `compatible=true`, `pair_verified=true`, `mode=migrasi`,
  `requires_controlled_migration=true`, **`siap_pasang=false`**. Job `pasang` dilewati.
  Pin/mode aktual tetap bersumber dari `scripts/release-metadata.json` dan workflow,
  bukan menyalin digest atau status dari dokumen historis.
- Snapshot SSH read-only setelah CI tersebut: container `osn-mesin` masih
  **`18bb974684cc0c4cc843b0c6810ef90b4af5d50d` running/healthy**; smoke anonim
  `/` 200, `/akun` 401, `/murid/` 303 ke `/masuk` lulus. Perbaikan kalender,
  penilaian, dan variasi soal belum dinyatakan live.
- Tidak ada backup CURRENT/rehearsal baru atau perubahan policy host dalam tugas
  koreksi CI/dokumentasi ini. Kekurangan penutupan recovery pada snapshot operasi
  berikut tetap belum ditutup oleh keberhasilan build. Verifikasi ulang sebelum
  pemasangan; jangan mengulang migrasi pilot untuk memperbaiki catatan historis.

### Izin operasi dan palang teknis

Push, deploy, SSH, dan migrasi rutin dalam scope mengikuti
[izin tetap workspace](../CLAUDE.md#izin-tetap--resource-lokal), tanpa meminta izin
ulang per koneksi. Kata **approval** pada protokol deploy di dokumen ini berarti
artefak teknis root-controlled yang terikat digest/TTL/preflight; izin tetap tidak
membuat artefak itu sah tanpa bukti prasyarat. Gate yang gagal tetap menahan rilis.
Restore data, penghapusan/destruksi, pelemahan keamanan, atau perubahan di luar
scope tetap memerlukan keputusan spesifik. Perubahan gate/policy tidak dilakukan
hanya untuk membuat pemasangan lolos.

## Koreksi operasi pilot — snapshot 21 September 2026, 08.26 UTC

**Pembaruan terbatas 21 September 2026, 09.05 UTC:** setelah approval baru,
image B exact di bawah berhasil di-pull ulang dan digest/revision/image ID cocok.
Container C/start time/health serta hash Caddy, cron, deployer dan policy tetap.
Ini memulihkan ketersediaan image, **bukan** menjalankan fallback atau menutup gap
backup CURRENT/rehearsal. Penyebab penghapusan historis belum teridentifikasi;
policy/cleanup host tidak diubah. Detail historis berikut tetap dipertahankan.

Bagian prosedur di bawah adalah persyaratan, bukan bukti bahwa operasi terdahulu
memenuhinya. Pilot **sudah live**; jangan mengulang rollout/cutover untuk menutup
catatan. Pemeriksaan read-only menemukan container revision
`18bb974684cc0c4cc843b0c6810ef90b4af5d50d` healthy, image exact C
`sha256:079adc5a9823d3fa70732a5b82d1a8c56a9fc7bb563270b35a5796b19408c500`,
admin5/Pendamping4/AI2/transient2 serta metadata pilot lengkap, integrity/FK lulus,
dan smoke publik 200/401/303. Ini snapshot waktu pemeriksaan, bukan jaminan live
selamanya atau bukti alur pilot/receipt berdata; tabel pilot dan receipt admin
masih kosong pada inspeksi.

[CI exact pair run 35569317083](https://github.com/clarinovist/jagomat/actions/runs/35569317083)
lulus: kandidat 11.368/recovery 11.344 tes, kedua image/probe/pair; deploy skipped.
Ada warning deprecation artifact/Node20 dan notice ubuntu-latest. Manifest tetap
`mode=migrasi`, `pair_verified=true`, `requires_controlled_migration=true`,
`siap_pasang=false`; tidak diubah menjadi izin rutin.

**Penutupan recovery belum lengkap:**

- Backup awal hanya empat DB, dibuat melalui `shutil.copy2` ketika container
  berhenti; **auth `sandi.json` tidak tercakup**, bukan SQLite backup API/bundle
  kanonis. Salinan privat luar Git baru hash-terverifikasi pada sesi post-live.
  Jangan menggabungkan auth current ke backup itu sebagai snapshot pramigrasi.
- Migrasi produksi mendahului verifikasi salinan lokal dan rehearsal lengkap.
  Rehearsal historis hanya `database.siapkan(latihan.db)` C2×/B2×, bukan pembuktian
  admin4→5/revisi/receipt lintas DB+auth. Preservasi tabel/baris lama empat DB kini
  terverifikasi read-only, tetapi tidak menghapus penyimpangan urutan tersebut.
- Backup **CURRENT lengkap** belum dibuat pada sesi penutupan. Bundle kanonis
  adalah empat DB+sandi.json; sesi login dan transient memang dikecualikan.
- Image B exact dari run yang sama
  `sha256:d280f80c7434998e69eb715d3ee3cc57f96460d272c15ae51066a903b9110faf`
  tersedia pukul 08.17 UTC, lalu event Docker mencatat untag/delete 08.20.41 UTC. Penyebab
  belum teridentifikasi; rehearsal ditahan, tidak pull/deploy/restart otomatis.
  Bukti CI B tetap sah, tetapi B tidak tersedia lokal pada pemeriksaan berikutnya.
- Maintenance historis mengganti seluruh Caddyfile dengan komentar, bukan blok
  Jagomat 503 terarah; ada potensi dampak lintas layanan, besarnya tidak diukur.
  Caddy/cron kembali ke hash awal. Container lama telah dihapus saat swap, bukan
  retained. Fallback hanya B compatible, bukan binary lama atau restore DB otomatis.
- **Policy host masih `enabled=true` dengan tuple lama** (deployer `2afe564e`,
  kontrak `a65060`, recovery `e38e2e`). Deployer kini `b7eb3ff1` dan kontrak pilot
  `0cf42d`; mismatch menahan preflight rutin, berbeda dari `enabled=false` eksplisit.
  Job pasang literal false juga berbeda dari pencabutan izin host.

Bukti historis tidak dihapus; artefak koreksi lokal terpisah di
`docs/plan/pilot-postlive-evidence-20260921-0817Z/`. Backup privat tidak masuk Git.
Operasi lanjutan dalam scope mengikuti izin tetap dan preflight teknis di atas.
Restore/destruksi atau perubahan policy/cleanup di luar scope tetap memerlukan
keputusan spesifik. Tidak ada klaim “blocker0” hanya karena halaman publik sehat.

## Riwayat migrasi pilot awal (21 September 2026)

Pada tahap ini kandidat C memakai **migrasi**, bukan izin deploy rutin. Recovery B
`175d8fb2d340c0c56d2f0ace5b6a1145792b8097` memahami admin5/profil/konteks/pilot;
build-only B sukses run35558003458. Fingerprint persistensi B:
`0cf42df6d86263c56f03547e8179eca750e23d3dd26c45cde11201bb2043ce53`.
Ini baseline, bukan bukti C sudah live. Delta C: materi terbimbing mengikuti
intervensi fokus sebelum event sesi dibuat, bukan pendekatan terbaru. Persistensi
B/C tetap sama; sesi campuran v2 nonaktif.

Job `pasang` tetap literal `if: ${{ false }}`. Full test, build/probe dan uji pair
wajib; hasil migrasi yang lolos: `compatible=true`, `pair_verified=true`,
`requires_controlled_migration=true`, **`siap_pasang=false`**. Jangan memaksa true.
Digest B/C wajib dari run CI pasangan yang sama, bukan digest B terdahulu.

Probe isian/PG tetap. `learning_pair_checks=8` berarti delapan kelompok assertion
wajib sebelum marker sukses, bukan jumlah test atau attestasi operator:
1. Migrasi ulang/preservasi ID, isi tabel, tanggal sesi, soal dan arsip konteks.
2. Kelas sekolah/revisi terpisah dari profil parameter.
3. Empat sumber konfirmasi tawaran balik, kontrak dan variasi tervalidasi.
4. Status langsung/kisi terbukti, balik belum dinilai; tuntutan tidak disatukan.
5. Recovery menyelesaikan draft dan replay konfirmasi identik tanpa duplikasi.
6. Pemilik asing ditolak tanpa efek; arsip immutable serta FK/integrity utuh.
7. Receipt admin5 sah setelah crash: replay dua kali, revisi/jurnal/receipt tetap;
   receipt rusak pada fixture terpisah ditolak.
8. Fokus snapshot dilanjutkan recovery; pencabutan sumber menahan alur; pemulihan
   wajib persetujuan, retry idempoten dan histori tidak dihapus.

Proof terikat revision DAN digest kedua image. Field hilang, tipe/nilai salah
menolak rilis. Tes probe nyata memakai C dan arsip B, plus mutation. Image pair CI
dan rehearsal backup privat tetap wajib, bukan digantikan fingerprint/test lokal.

Cutover hanya satu kali: backup quiescent no-prune, salinan lokal terverifikasi,
rehearsal C2×/B2×, migrasi aditif, approval exact pair TTL≤900detik. Sesudah migrasi
hanya B kompatibel; tidak downgrade/restore DB otomatis atau start binary lama.
Job auto-deploy CI tertahan literal false. Policy host bukan disabled: snapshot
post-live di atas masih enabled=true dengan tuple lama yang tidak cocok.
Status live dan kelengkapan recovery dilaporkan terpisah.

### Probe kandidat admin5 dan recovery historis

Deployer source kini mensyaratkan **admin5, Pendamping4, AI2, transient2** beserta
metadata `profil_belajar`, receipt `operasi_admin_profil`, tabel/trigger konteks,
serta seluruh tabel, kolom inti dan trigger immutable/sumber pilot.
Marker probe menjadi `OSN_IMAGE_ADMIN5_AI2_OK` / `OSN_SCHEMA_ADMIN5_AI2_OK`.
`schema_target=4` pada approval/policy tetap menunjuk kontrak Pendamping existing,
bukan versi admin; menaikkan angka itu tidak mengaktifkan dukungan admin5.
Readiness hanya membaca metadata schema/registry dengan SQLite `mode=ro` dan
`query_only`; tidak mengimpor aplikasi atau memigrasikan data keluarga.

Verifier CI mengirim probe tambahan dari `scripts/release_profile_probe.py` lewat
stdin (tanpa mount source host): migrasi admin4→5 berulang/preservasi, commit/replay
receipt kelas, konflik revisi, histori/konteks tetap, arsip immutable/hilang dan
receipt rusak. Kandidat wajib melaporkan `profil_checks=6`, `admin_schema=5` setelah
pemeriksaan selesai. Recovery lama dalam allow-list `RECOVERY_TANPA_PROFIL`
diuji sesuai kontrak historisnya: `profil_checks=0`, `admin_schema=null`; itu
**tidak** membuktikan dukungan admin5. Pin aktif `e206563` tidak termasuk pengecualian
tersebut: ia wajib `profil_checks=6`, `admin_schema=5`, sama seperti kandidat.

Artefak deployer VPS tetap satu berkas mandiri. Source saja tidak memasang
`/usr/local/bin/osn-deploy` atau memperbarui policy/approval. Operasi pilot kemudian
memasang hash `b7eb3ff1`; policy lama tetap, sebagaimana snapshot koreksi di atas.
Kedua jalur run utama/rollback tetap utuh; semua preflight kontrak, izin dan digest tetap wajib.

## Riwayat kandidat migrasi PG (16 September 2026)

Metadata pada tahap tersebut mematok baseline recovery PG
`e38e2e150c514c54db5470820561e69654c699bf`, kontrak persistensi
`a65060bc3ae65e4c78011499137508f6a873a6d19b0f77395efa0a7936424acf`, mode
**migrasi**, dan `pasang: if false`. Baseline tersebut telah lolos build-only
[run 35106204469](https://github.com/clarinovist/osn-mesin-latihan/actions/runs/35106204469).
Kandidat meniadakan overlay toolbar pada PG agar opsi bawah tidak tertutup;
recovery mempertahankan tampilan sebelumnya dengan persistensi yang sama.

Uji pasangan migrasi/rutin wajib mencakup isian **dan PG**: opsi 3/4/5, draft yang
dilanjutkan recovery, arsip/konfirmasi immutable, revisi tab, dan penolakan opt-in
pemetaan. Bukti tanpa `pilihan_pair_checks=8` ditolak. Pin sendiri bukan bukti live;
cutover tetap backup/rehearsal/migrasi `deploy-v2` exact digest yang lolos CI.
Auto-deploy permanen tidak diaktifkan oleh perubahan ini.

## Riwayat baseline pengiriman (15 September 2026)

Pada rilis pengiriman sebelumnya, metadata menetapkan baseline
recovery B `0ee93109f7950fb6fd86ae93fb63ffbd69bcb10c` dan kontrak
`18bbd4f57675cf28900a39c96f8af13cee785ce74d5f6198529b7760bd266b4d`.
Anchor ini cocok antara probe source B dan manifest image CI B
[run 34988722784](https://github.com/clarinovist/osn-mesin-latihan/actions/runs/34988722784).
Run B selesai sukses: seluruh test kandidat/recovery dan build/probe image lulus,
job pasang dilewati sesuai mode persiapan. Image B yang diperiksa mempunyai digest
`sha256:6e5d101ed69012c48dcf27f94f2a98b8d2c0b732b9cf6ebe7a582e389187162f`.
Build recovery berikutnya boleh menghasilkan digest berbeda; wajib diverifikasi
lagi dan memakai digest output build pasangan C/B yang sama, bukan meminjam bukti B.

Job `pasang` tetap **`if: ${{ false }}` secara literal**. Push/main maupun dispatch
dan `OSN_DEPLOY_RUTIN_SIAP=1` tidak dapat mengaktifkannya. Semua test kandidat dan
recovery serta build/probe kedua image tetap dijalankan. Pada mode migrasi,
**kontrak kandidat wajib identik dengan B dan uji lintas image wajib lulus**.
Pin source ini belum membuktikan image pasangan C/B atau deployment produksi.
Cutover tetap menunggu pasangan exact, backup/rehearsal, dan persetujuan spesifik.

Pada tahap persiapan B sebelumnya, mismatch terhadap recovery historis33e241
tercatat jujur (`compatible=false`, `pair_verified=false`, `siap_pasang=false`).
Tidak ada klaim recovery historis cocok dengan schema baru.

## Kontrak mode dan bootstrap

`scripts/release_metadata.py` memvalidasi konfigurasi JSON tertutup, pin workflow,
gate pasang, identitas image, dan fingerprint dari **PROBE_KONTRAK yang sama dengan
deployer** terhadap anchor B yang sudah terukur.

| Mode | Kontrak pasangan | Job pasang rutin | Manifest |
|---|---|---|---|
| `persiapan` | Diukur; mismatch tidak disamarkan | Literal false | `siap_pasang=false`, `pair_verified=false`, kompatibilitas sebenarnya |
| `migrasi` | Wajib identik dan uji lintas image lulus | Literal false | Pasangan teruji, `requires_controlled_migration=true`, belum izin rutin |
| `rutin` | Wajib identik dan uji lintas image lulus | Memerlukan readiness output **dan** variable exact1 **dan** main | Tetap menjalani preflight policy/current VPS |

Mode hilang/tidak dikenal/duplikat ditolak, bukan default ke rutin. Manifest hanya
terbit setelah identitas revision/digest dan fingerprint kedua image diverifikasi.
Pada migrasi/rutin, `verify_submission_pair.py` terlebih dahulu menguji kandidat
menulis pengiriman/tinjauan sintetis lalu recovery membaca/menulis dengan arsip dan
palang bukti tetap. Bukti pair terikat **revision dan digest exact kedua image**;
rebuild revision yang sama tidak boleh meminjam bukti image lain. Bukti hilang,
invalid, atau pair gagal menahan penerbitan manifest/upload/deploy.

Manifest mencatat candidate/recovery revision, digest, contract, mode, kompatibilitas,
`pair_verified`, `siap_pasang`, dan kebutuhan migrasi terkontrol. Boolean diturunkan
oleh helper, bukan input dispatch. Manifest lama tidak ditimpa/dipakai ulang.
`siap_pasang` hanya eligibility CI rutin; **bukan approval migrasi atau izin mengubah
policy VPS**. Equality preflight deployer tetap berlaku pada rutin dan `deploy-v2`.

Urutan bootstrap:
1. Freeze baseline B yang fungsional penuh dan aman untuk schema baru. Review,
   scoped test, kompilasi, dan palang lokal; full suite/build lewat CI sesuai
   kebijakan resource. Commit/push B hanya oleh koordinator.
2. Setelah CI dan image B terverifikasi, kandidat C mematok SHA B dan fingerprint
   terukurnya. B dan C punya persistensi sama, dengan delta aplikasi nyata yang
   menyediakan recovery bermakna; bukan beda label/cosmetic untuk dua digest.
3. Mode migrasi tetap literal false untuk auto-routine. Kedua image, schema upgrade,
   dan uji pair harus lulus. Jalankan cutover `deploy-v2` dengan approval exact pair,
   backup/drain/rehearsal dan recovery sesuai runbook di bawah.
4. Setelah current sehat dan policy terverifikasi, pengaktifan mode/gate rutin
   adalah perubahan tersendiri yang direview. Jangan mengaktifkan variable saja.

Pada koreksi kalender 22 September, bug pada recovery lama menahan build B jika
pipeline lama dijalankan apa adanya. B dibekukan sebagai commit immutable setelah
regresi lokal, lalu **seluruh suite serta image B dan C diuji bersama pada run final
yang sama**. Tidak ada klaim image B pernah lolos run terpisah. Semua gate kandidat,
recovery, probe dan pair tetap wajib; rincian/buktinya ada di [kontrak WIB](domain-clock-release.md).

Suite recovery B membaca mode/pin historis dari source B sendiri; itu bukan
izin menggunakan recovery historis33e241 untuk schema baru. Seluruh pengujian
aplikasi tetap berjalan; mode persiapan bukan skip test atau pelemahan probe.

Bagian berikut merekam kontrak dan prosedur rutin/migrasi existing. Deskripsi
eligibility rutin berlaku **setelah** aktivasi mode rutin; mode source sekarang
masih migrasi dengan job pasang tertutup.

Status inspeksi **13 September 2026 sekitar 09.50 WIB**: produksi masih sehat
di revision `4d5618d5fbb162f72c9a88397976c353ee62b88e`. Deploy kandidat
`90c1aa128c2d124e4056c5f99a1407729fcd55fa` ditolak pada preflight karena
menambah kontrak persistensi `ai-control.db`; container lama tidak disentuh.
Repository variable deploy rutin sudah dinonaktifkan selama rollout terkontrol.
Snapshot ini bukan jaminan keadaan live setelah tanggal tersebut.
Panduan [CLAUDE.md](../CLAUDE.md), [kontrak runtime](pendamping-runtime.md), dan
izin operasi produksi tetap berlaku. Data keluarga/credential tidak masuk repo.

## Mengapa rilis ini perlu pengaman

Inspeksi read-only 12 September 2026 menemukan image produksi revision
`7830b6d3eff11b7a5df41d84260b9b65cd7823ef`, manifest digest
`sha256:0129ea4779dd455c900c16435a4e772a342df53d6be836d3813ebe46db302569`.
Pendamping memakai schema v3. Commit `be4ab003f926382238ea9e7153f063b9c50e9e75`
menambah schema v4 dan catatan eksekusi di DB belajar; binary v3 menolak v4.
Ini snapshot inspeksi, bukan jaminan keadaan live setelah tanggal tersebut.

Deployer lama kembali ke image sebelumnya dan hanya memeriksa halaman publik.
Kegagalan `docker run` langsung dapat keluar sebelum bagian rollback. Karena
itu, keberhasilan uji UI tidak mengizinkan mengganti container tanpa recovery
kompatibel. Menurunkan user_version atau menghapus catatan eksekusi bukan solusi.

## Jalur CI yang dijaga

Workflow **CI Hybrid** selalu diawali `periksa`: palang repo, klasifikasi dokumen,
test kontrak CI, dan kompilasi. Setelah itu event menentukan scope:

1. **Push `main`:** dokumen allow-list berhenti setelah pemeriksaan awal. Push kode
   menjalankan satu job `uji_cepat` yang berisi smoke tetap (auth, database,
   diagnosis, generator, reducer siklus, palang murid, dispatch web), berkas test
   yang berubah, `test_<modul>*`, serta test reverse-import transitif yang sesuai
   delta. Push tidak
   membangun image, tidak mengetes recovery, dan bukan bukti kelayakan rilis.
2. **Schedule Senin 03.00 WIB:** empat shard `uji_kandidat` menjalankan seluruh
   test kandidat pada runner Ubuntu/Python 3.12 terisolasi. Job agregat `uji`
   membuktikan revision/koleksi sama, pembagian hash tepat, dan setiap nodeid lulus
   tepat sekali termasuk setup/call/teardown. Artifact manifest berisi identitas
   test sintetis dan status, bukan data keluarga, dan disimpan tujuh hari. Audit
   mingguan tidak menjalankan recovery atau build image.
3. **Dispatch manual:** menjalankan full kandidat di atas plus empat shard
   `uji_recovery` dari full SHA pinned dalam cwd terpisah, canary lokasi import,
   lalu `bangun`. Build/publish candidate serta recovery berdasarkan digest output
   run yang sama, probe kedua image, uji pasangan exact, dan terbitkan manifest.
   Dispatch pada SHA target ini adalah gate rilis; hasil schedule lama tidak dapat
   menggantikannya.
4. **Pasang saat mode rutin:** hanya setelah build/readiness pada gate rilis jika
   output `siap_pasang` persis `true`, variable `OSN_DEPLOY_RUTIN_SIAP` persis `1`,
   dan ref `main`. Pada mode migrasi sekarang job tetap literal false, termasuk
   dispatch. CI memanggil `deploy-rutin-v1 <candidate-digest> <recovery-digest>`
   hanya bila seluruh syarat mode rutin kelak diaktifkan melalui review terpisah.

Test dalam tiap shard tetap serial agar server HTTP tidak berkompetisi socket;
`--durations=20` mencatat fase lambat. Push baru membatalkan push lama pada ref yang
sama, sementara schedule dan dispatch berbagi antrean release dan tidak dibatalkan.
**Status CI** menolak kombinasi event/job, pembatalan, atau skip yang tidak sah.
Detail seleksi dan cara menjalankan dispatch: [CI hybrid](ci-selective.md).

Paralelisme antar-runner memperpendek waktu tunggu, bukan menit komputasi. Penghematan
utama berasal dari memindahkan delapan runner suite dan build pasangan image keluar
dari setiap push. Tidak ada cache hasil test atau `xdist` dalam satu runner.

Publikasi tidak mengganti `latest`. Identitas kedua image selalu digest output
build yang sama dengan verifikasi dan artifact manifest, bukan tag berubah.
Recovery revision tetap pinned; rebuild revision itu boleh menghasilkan digest
baru, tetapi harus lolos seluruh verifikasi image dan kontrak policy VPS.
Variable diaktifkan sesudah job skip tidak otomatis melanjutkan job tersebut.

Smoke memakai `scripts/smoke_public.py`: request anonim tanpa proxy/redirect/
cookie/body, User-Agent eksplisit `curl/8.7.1` yang lolos inspeksi edge. Python UA
bawaan mendapat 403 saat inspeksi walau curl 200/401/303; tidak menganggap 403 sukses.
Redirect murid boleh `/masuk?galat=...`, tetapi host lain/fragment/header ganda
ditolak. Smoke edge gagal membuat CI gagal, bukan otomatis restore DB.

## Deploy rutin vs migrasi

- **Rutin:** policy tetap root0600, kontrak persistensi current/candidate/recovery
  identik, current sehat dengan schema 4 sebelum swap. Tanpa migrasi baru, tidak
  membuat backup/writehold palsu, tidak menyentuh cron/Caddy. Ada downtime singkat
  saat restart. Kedua image siap dahulu; candidate gagal → recovery exact digest
  terverifikasi, tetap exit 1. Cleanup/recovery gagal → exit 2/intervensi operator.
- **Migrasi:** protokol `deploy-v2` tetap memerlukan approval sekali pakai dengan
  TTL ≤15 menit, pasangan digest exact, hash deployer, backup pasangan, writehold,
  pause maintenance dan rehearsal. Persetujuan lama consumed tidak boleh dipakai
  ulang. Tidak dilakukan otomatis hanya karena push.

Fingerprint rutin memproyeksikan AST operasi/guard persistensi dari modul
schema/startup/persistensi yang tercantum pada `PROBE_KONTRAK` di
`scripts/deploy.py`, termasuk inventaris modul baru bernama
schema/migrat/database/store. Probe network-none tidak membaca volume produksi
atau mengimpor aplikasi. Komentar, format, nama variabel lokal, pemindahan murni,
dan wrapper delegasi murni tidak mengubah fingerprint; perubahan struktur SQL,
guard, transaksi, atau state tetap mengubahnya. Proyeksi semantik yang sudah
dibuktikan identik boleh memakai ID kontrak recovery immutable yang dipetakan
secara eksplisit; ID/pin tidak diganti hanya agar gate hijau. **Fingerprint bukan
analisis semantik semua Python**: penulis data baru, kontrak JSON/provenance atau
perubahan runtime berisiko tetap memerlukan review kritis dan pair exact. Jangan
menghapus operasi dari proyeksi atau mengganti hash policy sekadar agar deploy hijau.

### Bootstrap rutin — sekali, dalam scope aktivasi yang disetujui

1. Review/gate source; commit/push mengikuti izin tetap. CI membangun/verifikasi
   pasangan image; variable tetap off. Tidak build di VPS.
2. Inspeksi ulang live/operasi saingan. Pasang `scripts/deploy.py` secara atomik
   root0755 di `/usr/local/bin/osn-deploy`, simpan versi lama secara terproteksi.
   Verifikasi hash source serta forced-command/wrapper sudo yang melewatkan tepat
   satu argumen. Binary lama tidak mengerti protokol rutin.
3. Dari image yang teruji, operator menghitung fingerprint `PROBE_KONTRAK` pada
   current/candidate/recovery tanpa mount/secret. Ketiganya harus identik.
   Buat `/opt/osn/routine-policy.json` regular root0600 satu hardlink dengan tepat
   field berikut (nilai ilustrasi **bukan policy siap pakai**):

   ```json
   {
     "enabled": true,
     "schema_target": 4,
     "deployer_sha256": "<sha256-byte-script-yang-dipasang>",
     "contract_sha256": "<fingerprint-identik-ketiga-image>",
     "recovery_revision": "bc9c973b50eb1fb04edd37df62f71ba0123f29c6"
   }
   ```

   Policy tidak ditulis oleh SSH caller/CI dan tidak memuat data keluarga.
   Policy hash mengikat deployer yang dipasang; perubahan deployer berikutnya
   memerlukan review/instalasi dan pembaruan policy, bukan auto-update root dari CI.
4. Aktifkan `OSN_DEPLOY_RUTIN_SIAP=1` **setelah izin auto-deploy**. Push main atau
   dispatch berikutnya dapat mengganti aplikasi produksi. Uji pertama dengan
   digest terverifikasi, pantau CI sampai selesai dan smoke publik. Jangan
   mengklaim tahap ini sudah selesai hanya karena source tersedia.
5. Matikan variable untuk menahan CI; set `enabled:false` pada policy untuk
   mencabut izin host di bawah lock deploy (menghentikan kelayakan baru, bukan
   membatalkan swap yang sudah berjalan). Tidak menghapus receipt/backup lama.

Recovery historis yang dipatok untuk rollout pengendali AI adalah
`33e241c18024190f41ebca1986e35af26c0397fd`, baseline pertama yang memahami
`ai-control.db`. Setiap pembaruan recovery harus diuji dan direview; label revision
sendiri bukan bukti kompatibilitas. Preflight kontrak/live readiness tetap wajib.
Deploy rutin tidak menyediakan restore data atau zero-downtime.

Pada rollout pengendali AI tersebut, jalur `deploy-v2` mensyaratkan backup DB
belajar dan Pendamping sebelum startup membuat DB AI. Backup tiga DB sesudahnya
juga merupakan inventaris historis, **bukan bundle lengkap admin5 sekarang**.
Bundle durable saat ini mencakup empat DB + auth `sandi.json`; sesi login dan
transient dikecualikan. Database riset konsumen (`riset-konsumen.db`) memiliki
retensi dan jalur backup terpisah sehingga tidak ikut bundle kampanye; readiness
memperlakukannya optional-absent sebelum rollout pertama dan exact setelah file ada,
sehingga preflight tidak menuntut file yang baru dibuat startup candidate.
Backup/restore riset memakai `research_backup.py` pada salinan di bawah write-hold. Prinsipnya dijelaskan di [runbook admin](admin-control-release.md),
tetapi langkah migrasi admin4 di sana tidak boleh dijalankan mentah pada admin5.

## Recovery berbeda dari candidate

Recovery historis rollout Pendamping v4 dibangun dari commit backend
`bc9c973b50eb1fb04edd37df62f71ba0123f29c6`: UI sebelum redesign, guard
tinjauan server, catatan eksekusi dan idempotensi tahan crash, ditambah perbaikan
penutupan transport HTTP yang sama dengan kandidat.
Recovery historis itu bukan image produksi lama, bukan perubahan konstanta
schema saja, dan bukan memilih kembali candidate yang sama ketika gagal.
**Baseline B pengiriman pada tahap itu adalah
`0ee93109f7950fb6fd86ae93fb63ffbd69bcb10c`**, yang juga memahami arsip pengiriman dan
provenance tinjauan. Pin PG `e38e2e1` dan pilot awal `175d8fb` tersebut historis;
source pada tahap kalender memakai `e206563`; pin aktif sekarang mengikuti
metadata dan snapshot terbaru di atas, bukan baseline historis pada paragraf ini.
Recovery pengendali AI33e241 dan Pendampingbc9c973 di atas merupakan histori,
bukan fallback schema pengiriman baru. Baseline B pengiriman menyediakan
seluruh kartu koreksi; kandidat C menambah navigasi antrean tinjauan server-side.
Delta navigasi tidak boleh mengubah persistensi atau guard B. Kompatibilitas
source tetap harus dibuktikan kembali pada image pasangan C/B dan recovery data
hasil kandidat sebelum meminta approval cutover.

`verify_release_image.py` menjalankan probe stdlib lewat stdin ke image digest
tertentu, non-root, filesystem read-only, tmpfs sintetis dan `--network none`.
Tidak bind-mount source host, Docker socket, atau volume produksi. Uji meliputi
migrasi sintetis v3→v4 berulang/parsial, preservation/FK/integrity, tinjauan,
crash setelah commit belajar, retry satu sesi, hasil batal/hapus, perubahan
pemilik/izin, invariansi bukti dan HTTP/aset. Output hanya ringkasan teknis.
Lolos probe sintetis bukan pengganti rehearsal backup keluarga saat B2.

## Artefak deployer dan kontrak jalur migrasi

Deployer berada di `scripts/deploy.py` dan diuji oleh
`mesin/__tests__/test_deployer.py` serta `test_routine_deployment.py`.
Keberadaan source tidak otomatis mengizinkan instalasi atau eksekusi: artefak
terpasang harus cocok hash source yang lolos gate. Untuk **jalur migrasi B2**,
approval dibuat untuk tepat satu pasangan digest setelah backup dan write hold
benar-benar aktif. Jalur rutin memakai policy berbeda seperti dijelaskan di atas.
Kontrak yang wajib dipenuhi: forced-command/registry/path terbatas, approval
root-controlled sekali pakai dan lock sebelum perubahan container, kedua image
siap sebelum swap, konfigurasi sama pada run utama/recovery, serta health
`/akun` anonim 401 dan kesiapan schema read-only—bukan sekadar `/` 200.

- Preflight ditolak: container lama tidak disentuh.
- Rilis gagal, recovery sehat: tetap lapor kegagalan rilis, bukan sukses.
- Stop/remove/cleanup/recovery gagal: tahan pemeliharaan dan eskalasi; jangan
  membuat dua writer pada volume yang sama atau terus menghapus container.
- Tidak auto-restore DB, downgrade schema, menghapus backup, membuka write hold
  atau mengaktifkan kembali cron melalui cleanup tanpa pemeriksaan operator.

Kontrak approval dan instalasi detail harus dicocokkan dengan source final,
hash artefak, user forced-command dan permission host yang nyata. Path/boolean
approval bukan bukti backup/drain; operator hanya menerbitkannya setelah kondisi
tersebut benar-benar diverifikasi. File yang tidak memenuhi precondition wajib
menolak, bukan di-chmod/chown otomatis oleh deployer.

## B2 — urutan historis rollout Pendamping v4

Rollout v4 telah dilakukan sesuai snapshot di atas. Urutan dua DB ini disimpan
sebagai histori, **bukan prosedur siap-eksekusi untuk admin5 atau perintah mengulang
migrasi v4**. Migrasi berikutnya harus mencakup seluruh state durable saat itu
(empat DB + auth untuk admin5), bukan menyalin inventaris lama. Dalam scope operasi
yang disetujui, lengkapi runbook dan bukti preflight dengan
**digest candidate/recovery nyata, hash deployer, jendela waktu/timezone,
batas durasi/dampak, mekanisme drain, backup dan recovery**.

Urutan minimum:

1. Periksa lagi revision/config/schema dan operasi lain. Pastikan image siap
   sebelum menghentikan layanan. Tidak build di VPS.
2. Pasang deployer yang disetujui secara atomik, simpan script sebelumnya secara
   terproteksi; rollback script bukan izin menjalankan binary v3 pada DB v4.
3. Tahan ingress dan seluruh writer kedua DB, drain request in-flight serta
   pause maintenance. GET/cron juga dapat menulis. Socket count nol sesaat bukan
   bukti semua writer telah berhenti. Cron terkait yang ditemukan `17 20 * * *`;
   timezone/CRON_TZ harus dikonfirmasi sebelum menjadwalkan.
4. Buat backup **pasangan** DB pada keadaan quiescent memakai SQLite backup API,
   temp unik, `umask 077`, transfer terenkripsi ke penyimpanan lokal ignored.
   Catat cutoff/manifest pasangan; hapus hanya temp milik operasi ini.
   **Tidak prune backup lama.** `mesin/cadangkan.sh` existing memakai temp tetap
   dan prune >30 hari, jadi jangan menjalankannya apa adanya sambil mengklaim
   prosedur no-prune. Helper final perlu review dan izin sesuai efek sebenarnya.
5. Rehearsal pada turunan backup, bukan backup induk. Migrasi aktual dua kali,
   integrity/FK serta invariant lintas DB. Tanpa provider/AI atau log isi keluarga.
   Jika write hold sempat dilepas, ambil backup pasangan final baru.
6. Migrasi terkontrol saat write hold sebelum readiness v4; jangan memanggil
   migrator dari pemeriksaan yang diklaim read-only. Pasang digest candidate
   yang sama dengan approval/verifikasi; fallback hanya recovery v4 yang diuji.
7. Periksa schema/integritas/revision/digest aktual. Smoke publik kanonis:
   `https://jagomat.id/` 200, `/akun` 401 anonim, `/murid/` 303 ke `/masuk`.
   Smoke fitur memakai lingkungan sintetis terisolasi, bukan akun keluarga.
8. Buka writer dan resume cron hanya setelah keadaan aman. Recovery gagal
   berarti tetap pemeliharaan dan lapor; jangan restore backup otomatis.

Restore DB memerlukan izin pemulihan data khusus dengan pasangan/cutoff/RPO
serta potensi kehilangan data dan rekonsiliasi. Izin push tidak mencakupnya.

## Pelaporan jujur

Source teruji, image terverifikasi, pemasangan live, dan auto-deploy aktif adalah
empat klaim berbeda. Job skip karena variable belum aktif harus dilaporkan
tertahan bootstrap. Policy ditolak sebelum swap tidak berarti aplikasi baru
terpasang. Recovery sehat tetap kegagalan rilis. Tidak ada klaim deployment hanya
karena push/build berhasil; inspeksi digest aktual dan smoke tetap diperlukan.
