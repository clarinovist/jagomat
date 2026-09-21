# Rilis integrasi — persiapan baseline, migrasi, dan deploy rutin

## Mode source saat ini: persiapan fondasi profil belajar (20 September 2026)

`scripts/release-metadata.json` memakai **persiapan/build-only** untuk penambahan
schema `profil_belajar`. Kandidat lanjutan menghubungkan kelas sekolah nullable
ke form guru/admin, memisahkan pilihan profil parameter latihan, serta membekukan
konteks per butir/konfirmasi. Registry admin menjadi schema5 dengan receipt kelas
tersendiri. Tidak ada backfill kelas dari P3–P6; rubrik kemampuan otomatis dan sesi
campuran tuntutan belum aktif. Ini status source kandidat, bukan bukti image atau
migrasi produksi.

Pin recovery PG `e38e2e150c514c54db5470820561e69654c699bf` dan kontraknya
`a65060bc3ae65e4c78011499137508f6a873a6d19b0f77395efa0a7936424acf` tetap.
Fingerprint kandidat berbeda karena schema baru; jangan memperbarui anchor atau
mengeluarkan modul dari probe agar dianggap cocok. Manifest persiapan mengukur
perbedaan tersebut: `compatible=false`, `pair_verified=false`, `siap_pasang=false`.
Flag `requires_controlled_migration` pada manifest menunjukkan mode **migrasi**;
nilainya false pada persiapan bukan izin memasang schema baru secara rutin.

Job `pasang` tetap literal `if: ${{ false }}`. Full test kandidat/recovery serta
build dan probe masing-masing image tetap wajib di CI. Langkah **lintas image**
hanya berjalan saat mode migrasi/rutin; persiapan tidak mengklaim recovery PG
sudah diuji terhadap data profil baru. Tidak ada push, build image, atau operasi
produksi yang otomatis diizinkan oleh perubahan mode source ini.

Sebelum kembali ke mode migrasi, siapkan baseline recovery schema baru yang
fungsional, verifikasi image dan pin terukurnya, lalu uji pasangan termasuk
pelestarian metadata profil, revisi, arsip konteks, receipt/journal admin schema5,
histori/bukti, pengiriman isian, dan PG.
Fingerprint sama tidak menggantikan uji baca/tulis/recovery data baru. Jangan
aktifkan penulis kemampuan penuh atau cutover tanpa kontrak dan pengujian yang
lengkap. Ikuti urutan bootstrap di bawah dengan izin rilis/produksi terpisah.

### Probe kandidat admin5 dan recovery historis

Deployer source kini mensyaratkan **admin5, Pendamping4, AI2, transient2** beserta
metadata `profil_belajar`, receipt `operasi_admin_profil`, dan tabel/trigger konteks.
Marker probe menjadi `OSN_IMAGE_ADMIN5_AI2_OK` / `OSN_SCHEMA_ADMIN5_AI2_OK`.
`schema_target=4` pada approval/policy tetap menunjuk kontrak Pendamping existing,
bukan versi admin; menaikkan angka itu tidak mengaktifkan dukungan admin5.
Readiness hanya membaca metadata schema/registry dengan SQLite `mode=ro` dan
`query_only`; tidak mengimpor aplikasi atau memigrasikan data keluarga.

Verifier CI mengirim probe tambahan dari `scripts/release_profile_probe.py` lewat
stdin (tanpa mount source host): migrasi admin4→5 berulang/preservasi, commit/replay
receipt kelas, konflik revisi, histori/konteks tetap, arsip immutable/hilang dan
receipt rusak. Kandidat wajib melaporkan `profil_checks=6`, `admin_schema=5` setelah
pemeriksaan selesai. Recovery historis yang dipatok eksplisit diuji sesuai kontrak
lamanya: `profil_checks=0`, `admin_schema=null`; itu **tidak** membuktikan recovery
tersebut dapat membaca data admin5. Image lain tidak otomatis mendapat pengecualian.

Artefak deployer VPS tetap satu berkas mandiri. Perubahan source ini belum memasang
`/usr/local/bin/osn-deploy` atau memperbarui hash policy/approval di host. Kedua jalur
run utama/rollback tetap utuh; semua preflight kontrak, izin dan digest tetap wajib.

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
Tidak ada klaim recovery historis cocok dengan schema baru. Kini
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
1. Freeze baseline B yang fungsional penuh dan aman untuk schema baru; full gate
   lokal dalam mode persiapan. Commit/push B hanya oleh koordinator, CI build-only.
2. Setelah CI dan image B terverifikasi, kandidat C mematok SHA B dan fingerprint
   terukurnya. B dan C punya persistensi sama, dengan delta aplikasi nyata yang
   menyediakan recovery bermakna; bukan beda label/cosmetic untuk dua digest.
3. Mode migrasi tetap literal false untuk auto-routine. Kedua image, schema upgrade,
   dan uji pair harus lulus. Jalankan cutover `deploy-v2` dengan approval exact pair,
   backup/drain/rehearsal dan recovery sesuai runbook di bawah.
4. Setelah current sehat dan policy terverifikasi, pengaktifan mode/gate rutin
   adalah perubahan tersendiri yang direview. Jangan mengaktifkan variable saja.

Suite recovery B kelak membaca mode/pin historis dari source B sendiri; itu bukan
izin menggunakan recovery historis33e241 untuk schema baru. Seluruh pengujian
aplikasi tetap berjalan; mode persiapan bukan skip test atau pelemahan probe.

Bagian berikut merekam kontrak dan prosedur rutin/migrasi existing. Deskripsi
eligibility rutin berlaku **setelah** aktivasi mode rutin, bukan pada mode
persiapan saat ini.

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

Workflow tetap **uji → bangun → pasang**:

1. **uji:** matrix empat `uji_kandidat` dan empat `uji_recovery` berjalan
   independen pada runner Ubuntu/Python 3.12 terpisah. Setiap runner menjalankan
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
Tidak ada seleksi berdasarkan file berubah, cache hasil test, atau pengaktifan
kembali `xdist` dalam satu runner pada perubahan penjadwalan ini.

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

### Bootstrap rutin — sekali, dengan izin produksi tersendiri

1. Review/gate source, commit/push hanya setelah izin. CI membangun/verifikasi
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

Recovery pinned untuk rollout pengendali AI adalah
`33e241c18024190f41ebca1986e35af26c0397fd`, baseline pertama yang memahami
`ai-control.db`. Setiap pembaruan recovery harus diuji dan direview; label revision
sendiri bukan bukti kompatibilitas. Preflight kontrak/live readiness tetap wajib.
Deploy rutin tidak menyediakan restore data atau zero-downtime.

Rollout satu kali ini wajib memakai `deploy-v2`: backup konsisten DB belajar dan
Pendamping lebih dulu, lalu migrasi/startup membuat DB pengendali AI. Sesudah
candidate sehat, backup berikutnya mencakup ketiga DB dan policy rutin diperbarui
ke fingerprint kandidat/recovery yang identik.

## Recovery berbeda dari candidate

Recovery historis rollout Pendamping v4 dibangun dari commit backend
`bc9c973b50eb1fb04edd37df62f71ba0123f29c6`: UI sebelum redesign, guard
tinjauan server, catatan eksekusi dan idempotensi tahan crash, ditambah perbaikan
penutupan transport HTTP yang sama dengan kandidat.
Recovery historis itu bukan image produksi lama, bukan perubahan konstanta
schema saja, dan bukan memilih kembali candidate yang sama ketika gagal.
**Baseline B pengiriman pada tahap itu adalah
`0ee93109f7950fb6fd86ae93fb63ffbd69bcb10c`**, yang juga memahami arsip pengiriman dan
provenance tinjauan. Pin source saat ini tetap recovery PG e38e2e1, sebagaimana
bagian mode source di atas; belum menjadi recovery schema profil belajar baru.
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

## B2 — membutuhkan izin produksi tersendiri

Rollout v4 telah dilakukan sesuai snapshot di atas. Urutan ini tetap menjadi
panduan migrasi berikutnya, **bukan perintah mengulang migrasi v4**. Sebelum
meminta persetujuan baru, lengkapi runbook dengan
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
