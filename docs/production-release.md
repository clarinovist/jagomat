# Rilis integrasi — persiapan baseline, migrasi, dan deploy rutin

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

Workflow kini diawali **periksa** untuk palang repo, klasifikasi perubahan,
scoped test palang CI dan kompilasi. Hanya push yang seluruh deltanya dokumen
allow-list eksplisit boleh melewati suite/build. Dispatch manual dan perubahan
lain tetap menjalankan jalur lengkap **uji → bangun → pasang** di bawah.
**Status CI** mengagregasi keberhasilan/skip yang sah pada kedua jalur; run
dokumen tidak menghasilkan image/manifest atau bukti kelayakan rilis. Daftar
aman, batas pemeriksaan dan penggunaan manual: [CI selektif](ci-selective.md).

1. **uji:** setelah `periksa` sukses dengan output `lengkap=true`, matrix empat
   `uji_kandidat` dan empat `uji_recovery` berjalan independen pada runner
   Ubuntu/Python 3.12 terpisah. Setiap runner menjalankan
   palang privasi dan pytest dengan warning sebagai error. Recovery tetap
   checkout pinned full SHA, cwd terpisah dan canary lokasi import. Helper
   memetakan setiap nodeid secara stateless dan deterministik; union empat
   shard per suite mencakup seluruh test tepat sekali. Test di setiap runner tetap
   serial agar server HTTP tidak berkompetisi socket; `--durations=20` mencatat
   20 fase test paling lambat per shard. Setelah semua shard kandidat sukses,
   job agregat `uji` (nama check tetap **Test kandidat**) memeriksa manifest:
   revision dan koleksi penuh harus sama, pembagian harus sesuai hash, dan setiap
   test harus lulus tepat sekali termasuk setup/call/teardown. Manifest hilang,
   koleksi berbeda, skip/xfail, test gagal atau eksekusi tidak lengkap ditolak.
   Artifact manifest hanya berisi identitas test sintetis dan status, bukan data
   keluarga, body HTTP, atau credential. Manifest disimpan selama tujuh hari.
2. **bangun:** wajib menunggu **kedua job uji sukses**; salah satu gagal,
   dibatalkan, atau dilewati berarti build tidak berjalan. Build/publish
   candidate serta recovery; tarik berdasarkan digest
   output build yang sama; verifikasi image sebenarnya dengan probe sintetis.
   Salah satu gagal berarti job gagal, tidak lanjut pasang.
3. **pasang saat mode rutin:** hanya pada `refs/heads/main` jika output readiness
   build `siap_pasang` **persis `true`** dan repository variable
   `OSN_DEPLOY_RUTIN_SIAP` **persis `1`**. Pada persiapan/migrasi, job memakai
   literal false. Default variable kosong berarti skip seluruh job, termasuk SSH. Variable lama `PENDAMPING_ROLLOUT_SIAP` tidak
   dipakai lagi. CI memanggil `deploy-rutin-v1 <candidate-digest> <recovery-digest>`.

Paralelisme antar-runner memperpendek jalur tunggu, bukan mengurangi cakupan test
atau otomatis menghemat menit komputasi. Durasi aktual tetap dipengaruhi antrean
runner; keuntungan harus diukur pada run CI sesudah perubahan diterapkan.
Seleksi berdasarkan file berubah hanya memilih jalur dokumen aman atau jalur
lengkap, bukan subset test aplikasi. Tidak ada cache hasil test atau pengaktifan
kembali `xdist` dalam satu runner. Delapan runner suite dan build tidak dimulai
untuk jalur dokumen aman.

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

Fingerprint rutin menghitung byte modul schema/startup/persistensi yang tercantum
pada `PROBE_KONTRAK` di `scripts/deploy.py`, termasuk inventaris modul baru bernama
schema/migrat/database/store. Probe network-none tidak membaca volume produksi
atau import aplikasi. Perubahan modul tersebut (termasuk komentar) sengaja menolak
rutin sampai review kompatibilitas/recovery baru. **Fingerprint bukan analisis
semantik semua Python**: penulis data baru, kontrak JSON/provenance atau perubahan
runtime berisiko tetap memerlukan review kritis. Jangan menghapus modul dari
fingerprint atau mengganti hash policy sekadar agar deploy hijau.

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
transient dikecualikan. Prinsipnya dijelaskan di [runbook admin](admin-control-release.md),
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
source kini memakai recovery kalender `e206563`, sebagaimana status terbaru di atas.
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
