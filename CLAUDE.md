# CLAUDE.md — Jagomat

## Commit lokal, izin rilis & resource lokal

- Commit lokal dulu; push/deploy perlu izin eksplisit untuk scope yang disetujui.
  Izin push bukan izin deploy: periksa pemicu auto-deploy dan dapatkan izin deploy
  sebelum push bila pipeline akan merilis. Jangan mengirim WIP sesi lain.
- SSH read-only untuk diagnosis dalam scope tetap diizinkan setelah target terverifikasi;
  akses SSH/root/sudo bukan izin deploy, mengubah akses, atau memodifikasi data.
- Dalam Hermes, kerjakan langsung di sesi yang sama. CommandCode tidak aktif;
  jangan otomatis login, smoke-test, atau menjalankan CLI/API-nya. Worker tambahan
  memerlukan persetujuan runner/model/scope dan verifikasi akses. Review sendiri
  adalah self-review, bukan review independen; jangan mengendurkan gate.
- Lokal untuk review, palang, kompilasi, dan scoped test yang terjangkau. Full suite,
  mutation berat, integration/E2E, dan build image diutamakan di CI/remote test terisolasi;
  bukan prasyarat lokal sebelum commit/push. Gate rilis tetap wajib pada SHA yang sama.
- Jangan otomatis menyalakan Docker, membuat container/Compose stack, atau menarik/build
  image lokal. Utamakan runner CI; Docker lokal hanya bila reproduksi khusus benar-benar
  memerlukan lokal dan resource memadai. Batasi resource dan bersihkan milik tugas sendiri.
- Batas ini menggantikan izin push/deploy otomatis di referensi lama. Gate berat
  tetap boleh melalui CI setelah izin yang diperlukan ada. Bukan izin force-push,
  menghapus data, atau operasi di luar scope.

Panduan utama agent untuk repo ini. **Verifikasi mengikuti risiko, bukan jumlah
file/baris. Kurangi administrasi, bukan perlindungan data.** Baca detail domain
hanya saat relevan di [`docs/workflow-reference.md`](docs/workflow-reference.md).

Bahasa: jawaban, commit message, docstring, dan string UI dalam **Bahasa Indonesia**,
santai tapi akurat. Nama berkas modul bahasa Inggris; fungsi/variabel tetap Indonesia.

## 1. Konteks & batas arsitektur

Aplikasi orang tua (peran guru) untuk latihan OSN/SASMO anak SD: generator soal
berparameter, diagnosis B/K/H/E/T/N, lembar cetak, dan laporan per anak. Sasaran
diperluas bertahap hingga kelas 9 (keputusan pemilik 28 Okt 2026); klaim publik
mengikuti batas jenjang di referensi workflow.

- **Pure Python stdlib**, tanpa framework/dependensi pihak ketiga. Dev dependency hanya
  `pytest` + `pytest-xdist`. Paket tambahan harus diajukan ke user dulu.
- **Zero-JS default**: menu `<details>`, navigasi `?section=` server-side. Pengecualian
  disetujui: toggle mata sandi, `confirm()` aksi destruktif, refresh pilihan isi ketika
  topik manual berubah, serta Kirim/Periksa status Pendamping inline tanpa reload
  (skrip berhash CSP, koneksi same-origin bila ada, fallback form native; bukan
  streaming). Tinjauan sesi memakai enhancement berhash CSP untuk accordion satu
  kartu aktif, penanda isian dan konfirmasi lewati; tidak menilai/mengirim otomatis,
  fallback form native tetap utuh. Akun memakai penanda kelas belum tersimpan dan
  validasi field Bahasa Indonesia secara lokal (tanpa network/autosave), disetujui
  pada penuntasan audit akun; server tetap otoritatif. Form Latihan memakai
  enhancement lokal berhash CSP untuk pilihan mode dan disabled Gabungan minimal
  dua topik, tanpa network/autosave; fallback pemilih GET serta validasi server tetap
  berlaku (disetujui pada penuntasan UI langkah 3–6). Beranda guru (`/guru`) memakai filter
  instan chip langkah berhash CSP (`guru_browser.py`; disetujui 22 Okt 2026): hanya
  menyembunyikan/menampilkan kartu yang sudah dirender server, tanpa network/storage;
  fallback chip tautan GET tetap utuh. Perlu approval untuk tambahan.
- `mesin/`: aplikasi, `__tests__/`, aset, Dockerfile, cadangan. `scripts/`: otomasi/palang.
  `docs/`: spesifikasi teknis; `docs/plan/` lokal/gitignored. `.github/`: CI/deploy.
- Riset/materi/kurikulum/mockup/bisnis/eksperimen berada di `../osn-resources/referensi/` lokal,
  bukan dependensi aplikasi/test/build. Jangan masukkan kembali ke Git.
- Alur: `topics` → `generator` → `templates` → `render`/`worksheets` → `database` →
  `diagnosis` → `reports`. Router/palang di `web.py`; data anak di `students.py`;
  auth/sesi di `auth.py`/`sessions.py`; SQLite di `database.py`/`schema.py`.
- `llm.py` hanya memparafrase kalimat soal (B2), bukan menentukan kunci/diagnosis.
  Detail modul, soal, pengujian, visual, dan batas klaim produk ada di referensi workflow.

## 2. Jalur kerja — Ringan / Normal / Kritis

Sebelum edit, sebut **jalur + alasan + acceptance criteria + verifikasi** secara singkat.
Risiko belum jelas → investigasi dulu. Jika scope/risiko bertambah, naikkan jalur dan
perbarui plan sebelum melanjutkan; jangan menurunkan jalur demi cepat/hijau.

| Jalur | Kriteria | Plan | Gate lokal ringan / CI sebelum rilis |
| --- | --- | --- | --- |
| **Ringan** | Dokumen, typo non-substantif, styling lokal tanpa mengubah perilaku/akses/makna soal | Cukup di chat | Review diff + palang repo; dokumen: link/konsistensi; UI: render sintetis + test markup/style yang terdampak, kompilasi bila Python berubah. Tidak wajib full suite/mutation/build. |
| **Normal** | Bug logika terbatas atau UI/alur nonkritis dengan dampak yang dipahami | Kecil cukup di chat; file plan untuk pekerjaan panjang/multitahap atau handoff | Palang repo + scoped regression test + kompilasi Python terkait; visual bila UI berubah. Full suite bila trigger di bawah, utamakan CI. |
| **Kritis** | Perubahan privasi/integritas data anak, auth/sesi/kepemilikan, palang murid, schema/migration, penghapusan data, kunci/malrule/diagnosis, bukti/reducer siklus belajar, runtime/dependency/build/deploy; operasi data/produksi berisiko | Satu plan lokal ringkas: sebab/target, scope, kriteria, invariant, failure path, verifikasi, recovery | Perubahan kode/config: palang + scoped test lokal; preset lengkap (full pytest, warning error, kompilasi) dan test domain/negatif/mutation relevan sebelum rilis, utamakan CI. Operasi tanpa perubahan artifact mengikuti ketentuan di bawah. |

Satu baris palang kepemilikan tetap Kritis. Typo yang mengubah angka, satuan, jawaban,
atau arti soal bukan Ringan. Refactor shared/cross-module minimal Normal; Kritis jika
menyentuh invariant kritis. Perubahan interaksi UI minimal Normal.

### Pahami → Perbaiki → Review & verifikasi → Laporkan

- Permintaan eksplisit “perbaiki/implementasikan” sudah mengizinkan edit sesuai scope:
  tidak perlu berhenti meminta pilihan lagi untuk fix yang jelas. Pertanyaan/“cek dulu”
  berarti investigasi dan laporkan temuan dengan `file:line`, bukan otomatis izin edit.
- Minta keputusan bila opsi mengubah scope/produk/kurikulum, menambah dependency/JS,
  atau memerlukan operasi berisiko di luar izin. Tawarkan A/B hanya bila trade-off nyata.
- Rencana ada sebelum fix; file `docs/plan/YYYY-MM-DD-slug.md` wajib untuk Kritis,
  pekerjaan panjang/multitahap, atau handoff. Cukup bagian yang relevan; dugaan sebab
  ditandai, bukan dianggap fakta. Plan lokal jangan di-stage; contoh di referensi workflow.
- Bug logika perlu regression test yang membuktikan bug tertangkap (merah pada kondisi
  rusak, hijau setelah fix). Tidak wajib TDD/mutation untuk typo atau styling murni.
- **Mutation wajib untuk guard baru keamanan, privasi/integritas data, atau kebenaran
  pedagogis**: test harus merah ketika guard/invariant yang sama dinonaktifkan lewat jalur
  yang dipanggil test, lalu hijau setelah dipulihkan. Bukti regression merah→hijau boleh
  sekaligus memenuhi ini jika membuktikan kondisi tersebut; jangan ulang pembuktian identik.
  Merah karena import/fixture rusak tidak sah. Mutasi terisolasi, bukan workspace sesi lain/DB nyata.
- Review diff aktual terhadap acceptance criteria, regresi, dan invariant; selesaikan
  blocker patch sebelum commit. Tidak wajib hitungan/checklist “Residual Gap” terpisah.
  Temuan di luar scope menjadi follow-up kecuali memengaruhi keamanan/kebenaran patch.
- Jalankan gate jalur. Gagal → fix → review → ulangi gate terdampak. Hasil boleh dipakai
  ulang jika input source/config/runtime/data sintetis relevan identik dan command/output/
  exit status tersedia; jangan ulang suite yang sudah tercakup atau hanya karena pindah agent.
- Normal wajib full suite bila mengubah utilitas bersama/kontrak lintas modul, caller belum
  terpetakan, atau memperbaiki kegagalan CI yang scope-nya belum jelas. Test domain khusus
  tidak boleh dilewati hanya karena jalur lebih ringan.
- Ringkasan akhir menyebut yang lolos/gagal/tidak dijalankan beserta alasan. Gate wajib
  terblokir berarti belum terverifikasi; jangan silent skip atau menganggap baseline gagal aman.

### Jaga ringkasan proyek tetap sinkron

- Sebelum implementasi, baca [`docs/spec.md`](docs/spec.md) dan
  [`docs/context.md`](docs/context.md) sebagai orientasi, lalu acuan domain yang relevan.
- Setiap perubahan wajib diperiksa dampaknya pada kedua ringkasan sebelum pekerjaan
  dinyatakan selesai. Jika terdampak, perbarui dalam perubahan/commit yang sama:
  - `docs/spec.md`: tujuan, cakupan fitur, perilaku/kontrak produk, dan batas akses/data.
  - `docs/context.md`: arsitektur, tanggung jawab modul, struktur folder, konvensi,
    serta keputusan teknis penting dan alasannya.
- Bila kontrak detail ikut berubah, perbarui dokumen sumbernya juga; jangan hanya
  mengubah ringkasan atau menyamarkan penyimpangan kode sebagai keputusan baru.
  Persetujuan yang diwajibkan untuk perubahan produk/arsitektur tetap berlaku.
- Pertahankan sekitar satu halaman per file: ganti informasi usang, tautkan detail,
  jangan menumpuk changelog, rencana sementara, atau klaim deployment tanpa bukti.
- Typo, styling lokal, atau refactor internal yang tidak mengubah isi ringkasan tidak
  perlu edit dokumentasi. Laporan akhir cukup menyebut ringkasan diperbarui atau
  tidak terdampak beserta alasan singkat.

### Eksekusi proporsional — jalur terpendek yang aman

- Cek/investigasi read-only tidak otomatis menjadi pekerjaan implementasi atau rilis:
  cukup bukti dan kesimpulan. Jangan membuat plan file atau menjalankan suite tanpa
  pertanyaan konkret yang perlu dibuktikan; privasi dan batas akses tetap berlaku.
- Investigasi cukup ketika penyebab/kondisi awal, target, jalur tindakan, dan invariant
  penting sudah terbukti. Baca referensi/caller relevan; perluas hanya untuk pertanyaan
  belum terjawab yang mengubah keputusan. Jangan mengulang penelusuran tanpa bukti baru.
- Utamakan fitur, runbook, tooling, dan environment terisolasi yang sudah tersedia.
  Jangan membuat skrip koreksi atau infrastruktur baru sebelum membuktikan jalur existing
  tidak cukup. Label Kritis sendiri bukan alasan menambah prosedur atau Docker.
- **Operasi data melalui aplikasi/tooling teruji yang tidak berubah tetap Kritis, tetapi
  bukan rilis kode baru.** Jika source/tooling, dependency, schema, runtime/config tetap,
  gunakan bukti gate artifact exact yang sama dan uji domain yang masih berlaku; tidak
  perlu full suite/build ulang. Bukti kurang/input berubah → jalankan gate terdampak.
  Skrip baru wajib review dan test terisolasi, bukan meminjam bukti aplikasi lama.
- Koreksi data tetap memerlukan target/otorisasi terverifikasi, backup yang dapat dipulihkan,
  preview/dry-run, atomicity, audit/provenance, pencegahan duplikasi, pemeriksaan hasil dan
  recovery sesuai operasi. Jangan melewati service/guard, mengubah bukti append-only, atau
  memakai produksi untuk test. Ringkas langkah ini dalam satu plan, bukan laporan berlapis.
- Memasang artifact teruji bukan mengubah mekanisme deploy. Bukti suite/build exact boleh
  dipakai ulang; preflight, pasangan digest, backup/rehearsal migrasi, health dan recovery
  sesuai runbook tetap wajib. Jangan mengulang cutover historis atau mengaktifkan `pasang`
  hanya karena sedang mengerjakan operasi rutin.
- Jika pekerjaan melebar, jelaskan blocker spesifik dan langkah berikutnya; temuan tidak
  terkait tidak otomatis menjadi proyek tambahan.

### Codemode — khusus Pi

Resep berikut hanya berlaku di Pi dengan `codemode` tersedia. Di Hermes gunakan
tool yang tersedia pada sesi aktif, bukan memasang Pi atau menebak nama tool.
Prinsip file-backed, urutan mutasi, exit status, dan privasi tetap berlaku di semua runner.

- Gunakan `codemode` untuk minimal dua call independen, loop/filter/agregasi, output besar
  yang perlu diringkas, atau chaining sederhana. Satu `read`/`bash`/`edit`/`write`
  trivial memakai tool langsung.
- Heredoc, SQL multi-statement, Markdown/code fence, SSH→SQLite/DB, dan nested quoting
  wajib file-backed: tulis file → inspect → jalankan file. Setelah satu parse failure,
  jangan retry inline kompleks; beralih ke direct/file-backed dan cek partial side effect.
- Untuk `bash`, periksa `exit_code`, `truncated`, `full_output_path`; expected-nonzero
  dinyatakan eksplisit. Jalur data/produksi tetap berurutan: target+backup → dry-run →
  apply → verifikasi. Resep lengkap ada di `~/.pi/agent/docs/codemode-playbook.md`.
- Personal codemode quality guard memberi syntax preflight, memblokir payload inline
  kompleks, dan mengklasifikasikan parse/tool/shell/timeout/stalled/output-limit error.
  Jangan melemahkan guard. Aturan privasi anak tetap berlaku pada seluruh tool/model.

## 3. Runtime & perintah verifikasi

- Pakai **`mesin/.venv/bin/python` (Python 3.9.6 lokal)**; `python3` polos bukan pengganti.
  CI/container memakai **3.12**, tetapi kode tetap kompatibel 3.9. Jangan pakai sintaks
  khusus 3.12 (contoh: kutip bersarang f-string); cek interpreter aktual bila environment berubah.
- Cwd shell tidak boleh diasumsikan bertahan; awali `cd /Users/nugroho/Documents/jagomat && ...`.
- Palang repo: `mesin/.venv/bin/python scripts/check_repo.py` — membaca **index Git**,
  bukan data anak. Jalankan setelah stage scope yang sudah direview.
- Scoped test: `mesin/.venv/bin/python -m pytest mesin/__tests__/test_<area>.py -q -W error -p no:cacheprovider`.
  Test aplikasi berada di `mesin/__tests__/`, bukan plan/spike/salinan repo lama. Mulai dari
  test regression dan caller yang terdampak; jangan menjalankan seluruh `mesin/__tests__/`
  secara lokal sebagai default, termasuk dari salinan kerja `/tmp`.
- Full suite tetap wajib sebelum rilis, tetapi jalur defaultnya **CI empat shard** dengan
  interpreter workflow. Setelah izin push/deploy yang diperlukan ada dan gate lokal
  scoped lulus, push boleh dilakukan agar CI menjadi
  gate lengkap pada SHA yang sama; jangan menunggu full suite serial lokal sebelum push.
  Full suite lokal hanya untuk reproduksi kegagalan CI yang belum dapat diisolasi, instruksi
  eksplisit pengguna/harness, atau ketika CI benar-benar tidak tersedia. Sebelum memulainya,
  beri tahu alasan dan perkiraan durasi; `timeout` adalah batas, bukan perkiraan selesai.
  Jika pengecualian berlaku, gunakan `mesin/.venv/bin/python -m pytest mesin/__tests__/ -q -W error -p no:cacheprovider`.
- Jangan otomatis memakai `-n auto` untuk full suite lokal: test HTTP berbagi socket. Untuk
  guard mutation, jalankan lokal hanya berkas mutation dan regression yang terkait; cakupan
  suite penuh tetap dibuktikan oleh CI. Jangan menjalankan suite berat ganda jika source,
  konfigurasi, runtime, dan bukti gate yang relevan identik.
- Kompilasi file terkait dengan `compile()` tanpa import/menjalankan aplikasi, lihat referensi.
  Repo ini **tidak** punya gate npm/lint/coverage; jangan menambah dependency
  atau mengklaim coverage global diperiksa CI. Trace/mutation domain mengikuti scope.
- `.project-gate.json` adalah preset lengkap serial untuk Kritis/audit penuh, bukan ritual
  lokal setiap edit. CI boleh memenuhi gate lengkap; jangan mengulang lokal jika input dan
  bukti identik. Suite satu runner tetap serial karena test HTTP berbagi socket; paralelisme
  CI memakai runner terisolasi. Jika harness mewajibkan preset, **jangan bypass**; laporkan
  konflik. Perubahan preset/harness perlu scope dan approval tersendiri.
- Build Docker lokal bukan default atau prasyarat commit/push. Perubahan packaging harus diverifikasi
  via test image/aset dan build CI sebelum deploy. **Jangan build di VPS** atau memakai
  Docker/DB lokal nyata untuk eksperimen. Terminal aktif bukan otomatis blocker: cek resource,
  port, DB, dan file yang bentrok; jangan hentikan proses sesi lain tanpa izin.

## 4. Git & shared workspace — selalu repo luar

Repo benar `/Users/nugroho/Documents/jagomat` (`main`); `/Users/nugroho/Documents/osn`
adalah alias kompatibilitas sementara ke folder yang sama, bukan repo kedua.
Origin kanonis `git@github.com:clarinovist/jagomat.git` (repo `clarinovist/jagomat`).
Nama GitHub lama `clarinovist/osn-mesin-latihan` mengalihkan ke repo yang sama;
namespace image GHCR tetap lama. Detail kompatibilitas dan pemulihan ada di
[`docs/repository-naming.md`](docs/repository-naming.md).
`mesin/.git` adalah repo lama/basi; git di sana bisa menelan commit atau menampilkan diff palsu.

- **Setiap git pakai `git -C /Users/nugroho/Documents/jagomat ...`**, tidak dari dalam `mesin/`.
  Path alias lama tetap sah untuk sesi yang sudah berjalan; jangan hapus alias sebelum
  venv, scheduler, editor, dan sesi agent dipindahkan.
- Cek status sebelum mulai. Jangan menimpa/revert/stash perubahan sesi lain. Satu writer
  per file; overlap perlu workspace terisolasi/koordinasi, bukan overwrite.
- Setelah edit massal 5+ file atau rewrite komponen, cek status + diff stat; review diff
  aktual. Stage hanya file/hunk sendiri sebagai checkpoint, bukan seluruh workspace.
- Jangan otomatis `reset`, `checkout --`, atau memulihkan versi lama untuk “repo hantu”.
  Investigasi repo/HEAD dan simpan WIP dulu. Mutasi/eksperimen di salinan temp terisolasi;
  jika backup file dipakai, pemulihan tidak boleh menimpa edit baru sesi lain.
- Commit setelah blocker patch selesai, review dan pemeriksaan lokal yang terjangkau;
  gate berat lewat CI sebelum rilis. Kode + test yang saling bergantung harus atomik; tidak wajib satu
  commit setiap langkah TDD. Jangan campur WIP sesi lain.
- Format conventional commit Bahasa Indonesia (`fix(murid):`, `feat(soal):`, `docs(mesin):`).
  Pesan multi-baris lewat berkas temp unik dan `git ... commit -F <berkas>`.
  Bila index berisi sesi lain, gunakan pathspec scope sendiri; file campuran harus dipisahkan
  dahulu karena commit pathspec mengambil isi working tree, bukan hanya hunk staged.
- **Commit lokal dulu; push dan deploy masing-masing perlu izin eksplisit.** Periksa
  pemicu pipeline sebelum push ke branch rilis: jika akan memicu deploy produksi,
  dapatkan izin deploy juga. Setelah diizinkan, pantau CI untuk SHA yang benar.
  Jangan mengirim WIP sesi lain atau memakai izin untuk rilis lain.

### Rapikan setelah pekerjaan selesai

Preferensi pengguna: **selalu rapikan setelah selesai, tanpa menunggu permintaan khusus**.

- Cek status Git dan artefak yang dibuat selama tugas sebelum laporan akhir. Catat perubahan
  yang sengaja dipertahankan; jangan membuang WIP atau perubahan sesi lain demi status bersih.
- Hapus cache sementara dan salinan kerja duplikat milik tugas yang sudah tidak diperlukan.
  Hentikan hanya proses preview/pengujian yang dimulai untuk tugas sendiri dan sudah selesai;
  jangan mengganggu proses atau berkas sesi lain.
- Pertahankan bukti pengujian/rilis yang berguna. Jika artefak selesai perlu diarsipkan,
  simpan secara privat di luar Git, verifikasi isi/hash sebelum menghapus sumber, lalu catat
  lokasi arsip tanpa memaparkan data anak atau kredensial.
- Source, tes, dokumentasi, `.env`, `.venv`, data anak/bisnis, image aktif, skrip recovery,
  dan backup yang diperlukan tetap aman. Jangan memakai penghapusan massal, Docker prune,
  atau commit/push otomatis hanya untuk merapikan.
- Cleanup bukan alasan menghapus artefak produksi atau mengubah retensi/backup di luar scope.
  Restart untuk deploy/recovery hanya dalam operasi yang sudah diizinkan.
- Laporkan singkat yang dirapikan serta yang sengaja disimpan atau ditunda. Jangan membuat
  artefak tambahan yang tidak diperlukan hanya untuk mencatat pembersihan sederhana.

## 5. Palang domain yang tidak boleh dilemahkan

- **Privasi anak:** DB, sandi/sesi, lembar terisi, cache, turunan, kejadian, cadangan tetap
  ignored/lokal. Jangan `git add -f` atau mengirim data/credential ke repo, prompt, log,
  screenshot, layanan AI, atau fixture. Uji menggunakan data sintetis; jangan memperluas
  akses/pengiriman data di luar alur produk yang telah disetujui.
- Tidak menyimpan email/telepon siapa pun; jangan usulkan fitur yang membutuhkan kontak.
- **Palang murid:** sisi anak tidak boleh membaca kunci/malrule/diagnosis/laporan. Fixture
  `db` guru dan `db_terjaga` harus terpisah; stamp `pemilik="guru"` bila perlu, bukan kendurkan
  guard. Rute MURID sebelum `_lolos_sandi`; fungsi berkunci di permukaan terpisah (misalnya
  `diagnosa_murid` di `web.py`, bukan `students.py`). CSS murid di `GAYA_STITCH`, bukan `CSS_SESI`.
- **Kepemilikan:** guru hanya datanya sendiri; resource bukan miliknya → **404** dengan body
  identik, bukan 403. Test juga membuktikan tidak ada efek samping, bukan status saja.
- Admin boleh membaca/menulis data murid semua keluarga melalui permukaan pengelola
  (sesi, jawaban, koreksi, lampiran, akun murid), serta membuat/reset/hapus akun orang tua.
  Admin **tidak boleh** mengubah akun/sandi sesama pengelola.
- **Soal/diagnosis:** perubahan modul topik wajib uji lintas seed × level, jalur malrule,
  determinisme, kartu rumus, dan pembahasan. Baca bagian Soal di referensi **sebelum edit**.
  Jangan `hash()` untuk randomisasi. Jenis soal/kurikulum baru harus dipilih user.
- Refactor “dipindah, bukan diubah” harus menjaga golden signature byte-per-byte;
  jika merah cari perubahan perilaku, jangan update golden agar hijau.

**Siklus belajar:** sumber produk `docs/siklus-belajar-terpandu.md`; baca ketika menyentuh
alur/bukti/rekomendasi. Jangan ringkas menjadi diagnosis → lebih banyak soal. Kontrak inti:

- pemetaan → fokus → intervensi/contoh → penguatan → evaluasi berjeda → checkpoint → maju/eskalasi;
- bukti hanya snapshot outcome append-only dikonfirmasi eksplisit; `direview`/`kode_final`
  mutable bukan bukti sendiri. Sesi berbukti tidak di-hard-delete; jaga provenance;
- `learning_cycle.py` sumber tunggal status/rekomendasi, reducer murni tanpa tulis DB;
- fokus kanonis `(template_id, kode_intervensi, malrule_id)`, maksimal dua per putaran;
  terbimbing/penguatan tidak menambah kelemahan;
- B/K/H/E/N/T punya tindakan masing-masing; T lewat pengenalan lalu probe; jawaban benar
  belum lulus tanpa bisa menjelaskan. Evaluasi ≥4 probe/fokus; checkpoint tiap 28 hari
  ≥3 probe/fokus; gagal kedua/tidak ada pendekatan lain → eskalasi;
- sesi manual/stale/beda level tidak memblokir CTA utama; anak hanya tahap netral, bukan
  kode diagnosis, label kelemahan, kunci, malrule, atau alasan internal.

## 6. UI & uji visual

- Nilai visual melalui `design_tokens.py` (`T.*`), tidak ada hex hardcoded di modul lain.
  Satu aksi satu entry point; CTA/form ganda bug. Input sandi punya toggle mata;
  tombol destruktif `confirm()` menyebut konsekuensi persis. Handler POST tetap menegakkan invariant.
- Alat perbaikan jalur-langka hanya tampil saat relevan, bukan memenuhi halaman normal.
- Keluhan visual **wajib render dan lihat**, bukan menebak CSS. Jangan `serve.py` untuk
  preview berdata: itu memakai DB/sandi asli. Server preview memakai DB/sandi temp + data
  sintetis; profil browser terisolasi. Matikan setelah selesai. Detail ada di referensi.

## 7. Produksi & deploy

- Image tetap **`ghcr.io/clarinovist/osn-mesin-latihan`**, independen dari nama repo.
  Jangan menggantinya ke `github.repository` atau namespace baru tanpa migrasi artefak/
  verifier/deployer/recovery tersendiri. Pin ini tidak mengaktifkan job `pasang`.
- Perubahan aplikasi tetap mengikuti **`uji` → `bangun` → `pasang`** di workflow:
  palang privasi + seluruh test sebelum build GHCR, deploy **digest output build yang sama**,
  forced-command SSH, swap container, auto-rollback jika healthcheck gagal. Push dokumen
  allow-list memakai [CI ringan](docs/ci-selective.md), bukan bukti kelayakan rilis.
- Izin tetap tidak menggantikan gate teknis: mode/pin mengikuti
  `scripts/release-metadata.json` dan `.github/workflows/deploy.yml`. Selama job
  `pasang` literal false, CI sukses bukan deployment. Status dan prosedur ada di
  [`docs/production-release.md`](docs/production-release.md).
- SSH read-only untuk diagnosis tetap diizinkan dalam scope; deploy/restart produksi
  dan mutasi data memerlukan izin operasi yang spesifik.
  Server lewat SSH alias `biznet-sekolahdesain`; perintah Docker produksi diawali `ssh biznet-sekolahdesain '...'`,
  jangan sampai mengenai Docker lokal. Tidak build di VPS atau menghapus container sebelum image siap.
- Setelah push, pantau run untuk commit yang benar sampai selesai:
  `gh run list --repo clarinovist/jagomat --branch main`, lalu
  `gh run watch <id> --repo clarinovist/jagomat --exit-status`.
- **Preflight sebelum maintenance:** tarik kedua digest exact dan jalankan `PROBE_SKEMA`
  dari image kandidat terhadap metadata DB live melalui koneksi `mode=ro`/`query_only`,
  tanpa network, migrasi, atau import startup. Probe ini wajib lulus **sebelum** Caddy/
  cron ditahan atau container dihentikan. Setelah refactor ownership modul, periksa semua
  probe/source-inspection yang mencari konstanta atau simbol di berkas lama (misalnya
  `VERSI_SKEMA` yang pindah dari façade ke modul core), lalu kunci jalur exact-image ini
  dengan regression test; probe fixture sintetis saja tidak cukup membuktikan readiness live.
- **Gagal cepat dan pulihkan akses:** bila kandidat gagal tetapi recovery exact sudah
  healthy, schema/integrity tetap bersih, dan tidak ada migrasi/write data, segera pulihkan
  Caddy serta cron sebelum diagnosis atau menunggu CI perbaikan. Pertahankan maintenance
  hanya bila state data/schema belum pasti. Jangan mengulang backup/rehearsal sebelum akar
  masalah diketahui; bukti boleh dipakai ulang hanya bila artifact, config, runtime, dan
  snapshot input benar-benar identik serta write hold belum pernah dilepas.
  Verifikasi publik di domain produksi kanonis **`https://jagomat.id`**
  (sesuai `URL_SITUS` di `mesin/brand.py`): `/` 200, `/akun` anonim 401,
  `/murid/` 303 ke `/masuk`. **Jangan menyentuh data anak** untuk smoke test.
  `https://osn.lesprivate.id` hanya domain lama yang mengalihkan ke `jagomat.id`,
  bukan target utama smoke test.
- “Ada di source”, “ter-deploy”, dan “berfungsi” tiga klaim berbeda. Untuk keadaan live,
  cek container berjalan secara read-only lewat SSH yang sudah diizinkan; jangan menganggap checkout sama
  dengan produksi. `llm.py` fail-dry: konfigurasi hilang bisa mematikan fitur tanpa error.
- Migrasi produksi hanya dalam rilis yang sudah diizinkan, setelah target, backup konsisten seluruh
  state durable, uji idempotensi/FK, serta recovery terverifikasi. Ikuti runbook aktif:
  bundle admin5 mencakup empat DB + auth `sandi.json`, bukan hanya DB belajar. Database riset konsumen punya retensi/backup terpisah dan tidak ikut bundle kampanye.
  `cadangkan.sh` lama bukan bukti bundle lengkap/no-prune. Token approval exact-pair
  dan preflight deployer tetap wajib; izin tetap tidak membuat artefak itu otomatis sah.
  Laporkan agregat saja, tidak nama anak.
- Investigasi data kosong yang diizinkan: backup terbaru di `mesin/cadangan/` read-only
  (`sqlite3 "file:...?mode=ro"`), bukan DB lokal kosong. Jangan tampilkan rekaman pribadi.
- `Dockerfile` memakai `COPY *.py` (guard `test_image.py`); aset non-Python punya COPY/guard
  tersendiri. Jangan kembali ke daftar modul manual.
- `/usr/local/bin/osn-deploy` tidak tracked; bila perubahannya disetujui, periksa kedua
  jalur `docker run` (utama **dan rollback**) agar konfigurasi tidak hilang saat recovery.

## 8. Pelaporan

Ringkas dan jujur: bukti tool aktual untuk klaim “terverifikasi”. Review/audit memakai
tabel severity High/Medium/Low bila relevan. Temuan di luar scope dilaporkan sebagai
follow-up, bukan otomatis memperluas pekerjaan. Klaim produk/kurikulum harus memakai
batas dan sumber di referensi, bukan janji “siap juara nasional”.
