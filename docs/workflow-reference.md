# Referensi workflow Jagomat

Sumber kebijakan jalur/approval/gate adalah [`CLAUDE.md`](../CLAUDE.md). Baca bagian
relevan saat menyentuh soal, test, visual, atau klaim produk; tidak perlu membaca
seluruh riwayat untuk typo. Dokumen ini tidak menambah gate universal.

## Plan & verifikasi sesuai risiko

Ringan dan Normal kecil cukup rencana di chat. File plan di `docs/plan/` untuk Kritis,
pekerjaan panjang/multitahap, atau handoff. Gunakan hanya bagian yang relevan:

```text
Masalah / dugaan sebab:
Scope file + di luar scope:
Acceptance criteria:
Rencana fix + regression test:
Review: acceptance criteria, invariant, regresi, dan blocker patch
Verifikasi: command, hasil, alasan tidak dijalankan
Follow-up:
```

Kritis tambahkan invariant, failure path, risiko data/runtime, dan rollback/recovery.
Kritis kecil cukup satu catatan ringkas; tidak perlu checklist Residual Gap atau laporan
pendamping. Plan rutin tetap lokal/gitignored, bukan dokumen permanen yang di-commit.
Cek read-only tidak otomatis memerlukan plan implementasi. Untuk operasi data/tooling
existing tanpa perubahan artifact, gunakan bukti gate identik sesuai ketentuan root;
verifikasi target, backup/recovery, provenance dan hasil operasi tetap wajib.

Semua contoh berikut dijalankan dari root Jagomat, bukan repo lama `mesin/.git`.
Path `Documents/osn` masih menjadi alias sementara; lihat
[panduan penamaan](repository-naming.md).

```bash
cd /Users/nugroho/Documents/jagomat && mesin/.venv/bin/python scripts/check_repo.py
cd /Users/nugroho/Documents/jagomat && mesin/.venv/bin/python -m pytest mesin/__tests__/test_students.py -q -W error -p no:cacheprovider
```

Pilih file test sesuai perubahan; contoh murid di atas bukan scope wajib untuk semua task.
Untuk compile-only file Python terkait (ganti daftar sesuai patch):

```bash
cd /Users/nugroho/Documents/jagomat && mesin/.venv/bin/python -W error -B -c 'from pathlib import Path; berkas = [Path("mesin/student_pages.py")]; [compile(p.read_text(), str(p), "exec") for p in berkas]; print("Kompilasi lulus:", len(berkas), "berkas")'
```

Ini tidak mengimpor aplikasi, membuka DB, atau menulis bytecode. Kompilasi bukan pengganti
test runtime/branch. `.project-gate.json` menyediakan gate lengkap dengan pytest serial,
bukan kewajiban mengulang full suite lokal yang sudah dipenuhi CI pada input identik.
Jangan melewati gate yang diwajibkan harness. CI memakai runner terisolasi untuk paralelisme,
bukan xdist pada socket bersama. Perubahan aplikasi tetap full pytest + palang privasi
sebelum build/deploy; push dokumen allow-list mengikuti [CI selektif](ci-selective.md).
Tidak ada gate coverage global atau dependency lint baru.

Jika test sudah gagal sebelum patch, laporkan bukti baseline terpisah dari regresi dan
selidiki scope-nya; jangan langsung menyebut aman karena “bukan perubahan saya”. Hasil
verifikasi hanya boleh dipakai ulang untuk input relevan identik, dengan command/output/
exit status nyata. Gagal/terblokir bukan lolos.

## Peta modul tambahan

| Modul di `mesin/` | Peran |
| --- | --- |
| `templates.py` | `Soal`, `Malrule`, `saring_malrule`, `LEVEL` P3–P6 |
| `topics.py`, `topic_*.py` | `Topik`, registry `PAKET`, `gabungan()`, paket per topik |
| `generator.py` | `buat_lembar`, `PROFIL_LEVEL`, parameter/pola |
| `render.py`, `worksheets.py` | Struktur HTML lembar tanpa CSS |
| `screen_style.py`, `print_style.py`, `teacher_style.py`, `style_stitch.py` | Gaya layar/cetak |
| `design_tokens.py` | Sumber tunggal nilai visual |
| `teacher_pages.py`, `student_pages.py`, `account_pages.py`, `reports.py`, `landing.py` | Halaman per permukaan |
| `rumus.py` | Kartu rumus per konsep |
| `attachments.py` | Foto lembar → AI vision → konfirmasi guru; bukan izin menggunakan data asli untuk pengujian |
| `learning_cycle.py`, `interventions.py` | Siklus/rekomendasi dan intervensi; kontrak di spesifikasi siklus |

Ketersediaan fitur dibuktikan dari kode/test atau container untuk klaim live, bukan dari
label “direncanakan”/angka baseline yang bisa basi dalam dokumentasi.

## Soal — baca sebelum mengubah topik/generator/template

**Malrule bisa runtuh diam-diam.** `saring_malrule` membuang nilai sama dengan kunci
atau malrule lain. Jalur diagnosis K bisa hilang walau test biasa hijau.

1. Urutan menentukan yang selamat: yang pertama disimpan. Jika K bisa sama dengan H,
   taruh **H dulu**.
2. Bentrok identitas aritmetika (`N//d == N%d`, `d == 2*sisa`, siklus satuan 1 pada `a^b`)
   diperbaiki di `_parameter` dengan while-loop reject, bukan urutan saja.
3. Nudge memakai **while**, bukan `if` sekali: `while str(h) in (kunci, k1, k2): h += 1`.
4. Kunci desimal (π=3,14): kunci/malrule memakai format koma desimal yang sama;
   H desimal = kunci−0,1, bukan kunci−1.
5. Nama variabel malrule konsisten di semua branch (`k1`/`k2`/`h`); nama berbeda per
   varian bisa menghasilkan `UnboundLocalError` di cabang jarang.
6. Key dict `_parameter` harus sama dengan argumen fungsi template. Untuk `unexpected
   keyword argument`, periksa key dict dulu.
7. Kalau `_parameter` sudah menghitung jawaban, template membaca saja, bukan hitung ulang.
8. **Jangan `hash()` untuk randomisasi.** `PYTHONHASHSEED` berbeda per proses; seed sama
   bisa menghasilkan soal berbeda. Hitung via `rng` di `_parameter`, kirim parameter
   eksplisit; determinisme satu-proses saja tidak cukup.

**Scope verifikasi wajib bila modul topik berubah:**

- Jalankan generator/template lintas topik terkait × level × seed, bukan membaca kode
  saja. Untuk tiap template di komposisi tiap level, exercise minimal seed `0..24` lewat
  `parameter_untuk` dan `REGISTRI`, lalu render output. Cabang jarang bisa `NameError`,
  `KeyError`, atau gagal format meski seed default hijau. Perubahan registry/shared
  generator harus menyapu seluruh topik, bukan hanya paket baru.
- `mesin/__tests__/test_level.py`: ≤2% soal tanpa jalur K per template.
- `mesin/__tests__/test_parameter_variants.py`: 500 seed; template di luar 19 template
  asli wajib ≥200 kombinasi parameter unik.
- `test_rumus.py::test_semua_template_punya_kartu` dan
  `test_pembahasan_semua.py::test_pembahasan_tidak_generik` menyapu semua template.
  Template baru harus dilengkapi kartu rumus/pembahasan, bukan melonggarkan guard.
- Kontrak registry **superset**, bukan daftar tertutup: `in` / `<=` / `>=`, bukan
  `== [...]` atau `== 19`.
- Baca hasil render/cetak soal + kunci + pembahasan. Fakta salah, latar mustahil, dan
  bahasa janggal pernah lolos test. **Pembahasan dibaca anak**, bukan tempat istilah
  guru, malrule, atau kode diagnosis.
- **Jenis soal/kurikulum harus diputuskan user**, bukan otomatis dipilih agent.

## Test, mutation & fixture

- Bug logika membutuhkan bukti regression test merah pada kondisi rusak lalu hijau
  setelah fix. Untuk guard baru keamanan, privasi/integritas data, atau kebenaran
  pedagogis, mutation tetap wajib; jangan memperluasnya menjadi ritual semua edit CSS.
  Satu bukti regression merah→hijau dapat sekaligus memenuhi mutation hanya jika kondisi
  merah menonaktifkan guard/invariant yang sama melalui jalur test yang sama, lalu pulih
  dan hijau. Jangan membuat pembuktian kedua yang identik; jika belum tercakup, uji mutasi
  terarah untuk guard tersebut tetap diperlukan.
- Mutasi harus lewat jalur yang benar-benar dipanggil test. Gunakan salinan kerja
  terisolasi dengan data sintetis dan backup temp unik; jangan memutasi repo sesi lain,
  backup produksi, atau DB nyata. Jika memakai file asli, pastikan ownership eksklusif,
  simpan snapshot tepat sebelum mutasi, dan pulihkan hanya jika tidak ada edit baru.
  Jangan `git checkout --` atau reset repo untuk memulihkan karena menghapus WIP.
- Catat test/bug yang dinonaktifkan, kegagalan yang diharapkan, hasil merah, pemulihan,
  dan hasil hijau. Test merah karena import/fixture rusak bukan bukti guard menggigit.
- Fixture `db` (guru) dan `db_terjaga` (palang murid) lokal per file, bukan di conftest;
  berkas test baru perlu definisi masing-masing. Jangan menggabungkannya.
  `conftest.py` menurunkan PBKDF2 melalui `OSN_PBKDF2_ITERASI`.
- `test_students.py` memasang `sqlite3.Row` terjaga: akses `kunci`, `malrule_id`,
  `kode_usulan`, `kode_final`, atau `alasan` harus gagal di sisi anak.
- 404 tidak cukup: assert body identik dan tidak ada efek samping untuk resource orang lain.
- Sebelum mengubah tag/class, cari assertion markup terkait. Pola refresh yang disetujui:
  pertahankan marker HTML lama sebagai elemen anak, matikan tampilan lewat CSS override.
  Jangan menghapus marker kontrak hanya agar desain/test mudah.
- CSS dapat membuat assertion `"X not in html"` false-positive. Assert marker/kode yang
  benar, bukan nilai kunci; jawaban anak sendiri bisa muncul di `<input value=...>`.
- Refactor murni: kunci perilaku dengan `test_golden_identity.py`; golden harus identik
  byte-per-byte. Merah → cari perubahan perilaku, bukan update angka golden.

## Visual sintetis & desain

Ikuti token di `design_tokens.py` dan [design system](design-system.md). Tidak ada hex
hardcoded di modul lain. Halaman murid memakai `GAYA_STITCH`, bukan `CSS_SESI`.

- Jangan diagnosis keluhan tampilan hanya dari CSS. Render halaman yang benar dan lihat.
- `serve.py` bisa menempel DB/sandi asli. Untuk preview berdata, server sekali-pakai
  mengarahkan `database.BAWAAN` dan berkas sandi ke temp serta seed sintetis minimal.
  Jangan salin profil/sesi akun asli. Matikan server sesudah selesai.
- Headless Chrome wajib `--user-data-dir` terisolasi; profil default bisa membawa sesi
  user sehingga `/` menampilkan dashboard, bukan landing publik.
- Halaman auth dengan **akun sintetis saja**: simpan HTML via `curl -u <akun-sintetis>`
  ke temp lalu screenshot `file://`; Chrome membuang kredensial URL. Jangan masukkan
  credential nyata dalam command/log. Gunakan browser terisolasi bila perlu memverifikasi
  perilaku HTTP, form, atau font—snapshot file bukan bukti perilaku server.
- `file://` tidak memuat font CDN: ikon Material Symbols bisa tampil teks (`login`,
  `school`), bukan otomatis bug. Cek elemen dan verifikasi served page bila perlu.
- Breakpoint pill dua kolom Stitch `24rem`, bukan `36rem`.
- `@import` font harus satu baris utuh, atau gunakan `<link>` di `<head>`.
- Tombol destruktif menyebut konsekuensi persis: misalnya akun login dihapus, bukan data
  anak. Handler POST tetap menegakkan invariant, jangan percaya modal konfirmasi.

## Konteks kurikulum & batas klaim produk

Sumber: audit 1.237 soal OSN asli 2016–2026, arsip lokal
`../../osn-resources/referensi/docs/riset-soal-osn-10-tahun.md`. Ini angka audit historis, bukan
ukuran otomatis cakupan kode terbaru. Jika arsip tidak tersedia, jangan mengarang data baru.

- 85 template menutup **74,7%** konsep soal nyata; NAS-eksplorasi **24,4%**.
- Bobot nyata: Aritmatika 24,2% ≈ Geometri 23,2% > Bilangan 21,5% >
  Statistika-Pengukuran 16,2% > Kombinatorik 14,9%. “Geometri paling besar” salah;
  pie silabus 25/25/12/38% dekoratif, bukan bobot untuk dikutip.
- Non-rutin per tahap: kecamatan 10,6% → OSN-K 26,4% → OSN-P 33,3% → nasional ~47%
  → eksplorasi 100%.
- Klaim aman: **fondasi + pola soal OSN-S/K/P**, bukan “siap juara nasional”. Soal
  eksplorasi meminta konstruksi tanpa kunci tunggal; bukan gap yang otomatis selesai
  dengan menambah template diagnosis/malrule.
- `dua_besaran_selisih` dan `piktogram` jangan dihapus hanya karena belum muncul di audit;
  piktogram ada di silabus resmi. P3 tidak dibatasi pola-bilangan saja (SASMO band P1–4).

## Pelajaran insiden, bukan ritual universal

| Insiden / risiko | Pengaman yang dipertahankan |
| --- | --- |
| Git dalam `mesin/` memakai repo basi | Semua git `-C /Users/nugroho/Documents/jagomat`; tidak reset otomatis |
| Test hijau tetapi malrule K hilang | Uji seed/level, collision, baca output soal |
| Modul/aset baru tidak masuk image | COPY wildcard Python + COPY aset, guard image/aset, build CI |
| Mutasi tidak melalui jalur test | Buktikan kegagalan tepat, data sintetis, pulihkan lalu hijau |
| Preview membawa sesi/DB asli | Server temp + profil browser terisolasi |
| Build VPS gagal setelah container lama dihapus | Build CI, deploy digest, healthcheck + rollback |
| Konfigurasi hilang di jalur rollback | Periksa kedua jalur deploy utama/rollback saat script diubah |

Detail akses produksi tetap mengikuti root dan izin user; referensi ini bukan izin
mengeksekusi migrasi, membuka data anak, atau mengubah layanan live.
