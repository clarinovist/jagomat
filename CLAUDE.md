# CLAUDE.md — OSN Mesin Latihan

Panduan utama agent untuk repo ini. **Verifikasi mengikuti risiko, bukan jumlah
file/baris.** Aturan inti di sini; baca detail domain hanya saat relevan di
[`docs/workflow-reference.md`](docs/workflow-reference.md).

Bahasa: jawaban, commit message, docstring, dan string UI dalam **Bahasa Indonesia**,
santai tapi akurat. Nama berkas modul bahasa Inggris; fungsi/variabel tetap Indonesia.

## 1. Konteks & batas arsitektur

Aplikasi orang tua (peran guru) untuk latihan OSN/SASMO anak SD: generator soal
berparameter, diagnosis B/K/H/E/T/N, lembar cetak, dan laporan per anak.

- **Pure Python stdlib**, tanpa framework/dependensi pihak ketiga. Dev dependency hanya
  `pytest` + `pytest-xdist`. Paket tambahan harus diajukan ke user dulu.
- **Zero-JS default**: menu `<details>`, navigasi `?section=` server-side. Pengecualian
  disetujui: toggle mata sandi, `confirm()` aksi destruktif, serta Kirim/Periksa status
  Pendamping inline tanpa reload (skrip berhash CSP, koneksi same-origin, fallback
  form native; bukan streaming). Perlu approval untuk tambahan.
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

| Jalur | Kriteria | Plan | Gate lokal sebelum commit |
| --- | --- | --- | --- |
| **Ringan** | Dokumen, typo non-substantif, styling lokal tanpa mengubah perilaku/akses/makna soal | Cukup di chat | Review diff + palang repo; dokumen: link/konsistensi; UI: render sintetis + test markup/style yang terdampak, kompilasi bila Python berubah. Tidak wajib full suite/mutation/build. |
| **Normal** | Bug logika terbatas atau UI/alur nonkritis dengan dampak yang dipahami | Ringkas di `docs/plan/YYYY-MM-DD-slug.md`: masalah/dugaan sebab, scope, acceptance criteria, test | Palang repo + scoped regression test + kompilasi Python terkait; visual bila UI berubah. Full suite bila trigger di bawah. |
| **Kritis** | Privasi/data anak, auth/sesi/kepemilikan, palang murid, schema/migration, penghapusan data, kunci/malrule/diagnosis, bukti/reducer siklus belajar, runtime/dependency/build/deploy | Plan lengkap: sebab, scope, kriteria, failure path, verifikasi, rollback/recovery | Preset lengkap `.project-gate.json` (palang, full pytest dengan warning error, kompilasi) + test domain/negatif/mutation yang relevan. Build produksi tetap gate CI. |

Satu baris palang kepemilikan tetap Kritis. Typo yang mengubah angka, satuan, jawaban,
atau arti soal bukan Ringan. Refactor shared/cross-module minimal Normal; Kritis jika
menyentuh invariant kritis. Perubahan interaksi UI minimal Normal.

### Plan → Fix → Review Gap → Verify

- Permintaan eksplisit “perbaiki/implementasikan” sudah mengizinkan edit sesuai scope:
  tidak perlu berhenti meminta pilihan lagi untuk fix yang jelas. Pertanyaan/“cek dulu”
  berarti investigasi dan laporkan temuan dengan `file:line`, bukan otomatis izin edit.
- Minta keputusan bila opsi mengubah scope/produk/kurikulum, menambah dependency/JS,
  atau memerlukan operasi berisiko di luar izin. Tawarkan A/B hanya bila trade-off nyata.
- Plan Normal/Kritis harus ada sebelum fix; dugaan root cause ditandai, bukan dianggap fakta.
  Plan lokal jangan di-stage; contoh isi ringkas ada di referensi workflow.
- Bug logika perlu regression test yang membuktikan bug tertangkap (merah pada kondisi
  rusak, hijau setelah fix). Tidak wajib TDD/mutation untuk typo atau styling murni.
- **Mutation wajib untuk guard baru keamanan, privasi/integritas data, atau kebenaran
  pedagogis**: buktikan test merah saat bug diaktifkan lewat jalur yang sama, lalu pulihkan
  dan hijau. Jangan mutasi workspace sesi lain/DB nyata; prosedur aman di referensi.
- Review diff aktual dan acceptance criteria. **Residual Gap: 0** hanya terhadap scope
  patch ini. Temuan lain dicatat follow-up; menjadi blocker bila memengaruhi keamanan/
  kebenaran patch. Ringan cukup catatan chat, lainnya checklist plan.
- Setelah gap implementasi 0, jalankan gate jalur. Gagal → fix → review → ulangi gate
  terdampak. Hasil boleh dipakai ulang jika input source/config/runtime/data sintetis
  relevan identik dan command/output/exit status tersedia; jangan ulang hanya karena pindah agent.
- Normal wajib full suite bila mengubah utilitas bersama/kontrak lintas modul, caller belum
  terpetakan, atau memperbaiki kegagalan CI yang scope-nya belum jelas. Test domain khusus
  tidak boleh dilewati hanya karena jalur lebih ringan.
- Ringkasan akhir menyebut yang lolos/gagal/tidak dijalankan beserta alasan. Gate wajib
  terblokir berarti belum terverifikasi; jangan silent skip atau menganggap baseline gagal aman.

## 3. Runtime & perintah verifikasi

- Pakai **`mesin/.venv/bin/python` (Python 3.9.6 lokal)**; `python3` polos bukan pengganti.
  CI/container memakai **3.12**, tetapi kode tetap kompatibel 3.9. Jangan pakai sintaks
  khusus 3.12 (contoh: kutip bersarang f-string); cek interpreter aktual bila environment berubah.
- Cwd shell tidak boleh diasumsikan bertahan; awali `cd /Users/nugroho/Documents/osn && ...`.
- Palang repo: `mesin/.venv/bin/python scripts/check_repo.py` — membaca **index Git**,
  bukan data anak. Jalankan setelah stage scope yang sudah direview.
- Scoped test: `mesin/.venv/bin/python -m pytest mesin/__tests__/test_<area>.py -q -W error -p no:cacheprovider`.
  Test aplikasi berada di `mesin/__tests__/`, bukan plan/spike/salinan repo lama.
- Full test: `mesin/.venv/bin/python -m pytest mesin/__tests__/ -q -n auto -W error -p no:cacheprovider`.
  `-n auto` hanya bila resource cukup; jangan menjalankan suite berat ganda.
- Kompilasi file terkait dengan `compile()` tanpa import/menjalankan aplikasi, lihat referensi.
  Repo ini **tidak** punya gate npm/lint/coverage; jangan menambah dependency
  atau mengklaim coverage global diperiksa CI. Trace/mutation domain mengikuti scope.
- `.project-gate.json` adalah preset lengkap untuk Kritis/audit penuh, bukan ritual manual
  setiap edit Ringan/Normal. Jika harness mewajibkan preset, **jangan bypass**; laporkan jika
  ada konflik. Perubahan preset/harness perlu scope dan approval tersendiri.
- Build Docker lokal tidak wajib untuk setiap commit. Perubahan packaging harus diverifikasi
  via test image/aset dan build CI sebelum deploy. **Jangan build di VPS** atau memakai
  Docker/DB lokal nyata untuk eksperimen. Terminal aktif bukan otomatis blocker: cek resource,
  port, DB, dan file yang bentrok; jangan hentikan proses sesi lain tanpa izin.

## 4. Git & shared workspace — selalu repo luar

Repo benar `/Users/nugroho/Documents/osn` (origin `clarinovist/osn-mesin-latihan`, `main`).
`mesin/.git` adalah repo lama/basi; git di sana bisa menelan commit atau menampilkan diff palsu.

- **Setiap git pakai `git -C /Users/nugroho/Documents/osn ...`**, tidak dari dalam `mesin/`.
- Cek status sebelum mulai. Jangan menimpa/revert/stash perubahan sesi lain. Satu writer
  per file; overlap perlu workspace terisolasi/koordinasi, bukan overwrite.
- Setelah edit massal 5+ file atau rewrite komponen, cek status + diff stat; review diff
  aktual. Stage hanya file/hunk sendiri sebagai checkpoint, bukan seluruh workspace.
- Jangan otomatis `reset`, `checkout --`, atau memulihkan versi lama untuk “repo hantu”.
  Investigasi repo/HEAD dan simpan WIP dulu. Mutasi/eksperimen di salinan temp terisolasi;
  jika backup file dipakai, pemulihan tidak boleh menimpa edit baru sesi lain.
- Commit setelah gap 0 + gate lokal sesuai jalur lolos. Kode + test yang saling bergantung
  harus atomik; tidak wajib satu commit setiap langkah TDD. Jangan campur WIP sesi lain.
- Format conventional commit Bahasa Indonesia (`fix(murid):`, `feat(soal):`, `docs(mesin):`).
  Pesan multi-baris lewat berkas temp unik dan `git ... commit -F <berkas>`.
  Bila index berisi sesi lain, gunakan pathspec scope sendiri; file campuran harus dipisahkan
  dahulu karena commit pathspec mengambil isi working tree, bukan hanya hunk staged.
- **Jangan push tanpa perintah eksplisit** (“push”, “commit dan push”). “Commit dulu” bukan
  izin push. Push `main` memicu deploy produksi otomatis; jelaskan dampaknya saat minta approval.

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

- Pipeline `.github/workflows/deploy.yml` tetap **`uji` → `bangun` → `pasang`**: palang
  privasi + seluruh test sebelum build GHCR, deploy **digest output build yang sama**,
  forced-command SSH, swap container, auto-rollback jika healthcheck gagal.
- Operasi produksi hanya setelah approval eksplisit. Server lewat SSH alias
  `biznet-sekolahdesain`; perintah Docker produksi diawali `ssh biznet-sekolahdesain '...'`,
  jangan sampai mengenai Docker lokal. Tidak build di VPS atau menghapus container sebelum image siap.
- Setelah push diminta, pantau run untuk commit yang benar sampai selesai:
  `gh run list --repo clarinovist/osn-mesin-latihan --branch main`, lalu
  `gh run watch <id> --repo clarinovist/osn-mesin-latihan --exit-status`.
  Verifikasi publik di domain produksi kanonis **`https://jagomat.id`**
  (sesuai `URL_SITUS` di `mesin/brand.py`): `/` 200, `/akun` anonim 401,
  `/murid/` 303 ke `/masuk`. **Jangan menyentuh data anak** untuk smoke test.
  `https://osn.lesprivate.id` hanya domain lama yang mengalihkan ke `jagomat.id`,
  bukan target utama smoke test.
- “Ada di source”, “ter-deploy”, dan “berfungsi” tiga klaim berbeda. Untuk keadaan live,
  cek container berjalan secara read-only dengan izin; jangan menganggap checkout sama
  dengan produksi. `llm.py` fail-dry: konfigurasi hilang bisa mematikan fitur tanpa error.
- Migrasi produksi: approval + backup `cadangkan.sh`, uji idempotensi dan
  `PRAGMA foreign_key_check`, recovery siap. Laporkan agregat saja, tidak nama anak.
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
