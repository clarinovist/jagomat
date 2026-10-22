# Jagomat — Referensi arsitektur

Peta modul dan keputusan teknis rinci, dipindahkan dari ringkasan pada 22 Oktober
2026 tanpa perubahan arsitektur. Orientasi singkat: [context.md](context.md);
cakupan: [spec.md](spec.md); status: [status proyek](status-proyek.md).
[CLAUDE.md](../CLAUDE.md) tetap mengatur workflow, privasi dan gate.

## Arsitektur

**Monolit Python stdlib, HTML dirender server, penyimpanan SQLite.**
`serve.py` menjalankan server HTTP; `web.py` mengatur transport, dispatch, dan
palang akses. `student_http.py` memiliki alur GET/POST akun murid,
`session_http.py` memiliki pembuatan, tampilan/cetak, review, dan latihan tindak
lanjut sesi guru; `share_http.py` memiliki capability satu sesi dan aksi bagikan guru;
`public_http.py` memiliki halaman publik tanpa data keluarga, termasuk pusat
`business_research.py`, audit `competitive_research.py`, rencana/model sintetis
`bootstrap_research.py` + materi `bootstrap_content.py`, dan PDF statis di
`publik/`; `auth_http.py` memiliki
login/logout; `registration_http.py` memiliki pendaftaran keluarga;
`account_http.py` memiliki halaman dan mutasi akun guru; `teacher_http.py` memiliki
beranda, workspace anak, dan laporan; `admin_research_http.py` memiliki permukaan
interviewer privat `/admin/riset`; sementara `attachment_http.py` memagari baca,
upload, dan penerapan foto guru.
Nama modul di bawah relatif terhadap `mesin/`, bukan direktori baru.

| Lapisan | Modul dan tanggung jawab |
| --- | --- |
| Identitas | `auth.py`, `sessions.py`: akun dan sesi login; `students.py`: data anak |
| Soal | `topics.py` + `topic_*.py`: topik; `generator.py`: pembangkitan; `templates.py`: kontrak soal |
| Penyajian | `render.py`, `worksheets.py`, `*_pages.py`, `*_ui.py`: HTML/layar; `teacher_shell.py`: bingkai/topbar; `teacher_workspace.py`: profil/form; `teacher_session_pages.py`: tinjauan; `review_navigation.py`: proyeksi kategori exception-first fail-closed; `teacher_print_pages.py`: cetak/lampiran; `teacher_review_service.py`: koreksi |
| Data | `database.py`, `schema.py`, `*_store.py`, `*_schema.py`: penyimpanan dan migrasi; `research_store.py` + `research_schema.py`: wawancara konsumen anonim di `riset-konsumen.db`; `attachment_store.py`: metadata lampiran; `report_store.py`: proyeksi laporan; `student_profile_store.py`: profil/kepemilikan siswa; `question_bank_store.py`: bank soal; `session_read_store.py`: query/status dasar sesi; `session_store.py`: pembuatan sesi; `answer_store.py`: jawaban/diagnosis; `learning_evidence_store.py`: snapshot konfirmasi dan loader bukti siklus |
| Belajar | `diagnosis.py`, `learning_cycle.py`, `learning_cycle_service.py`: diagnosis, reducer murni, orkestrasi |
| Laporan | `reports.py`, `report_*.py`, `mastery_*.py`: laporan dan penguasaan berbasis bukti |
| Layanan lain | `assistant_http_common.py`: parser/response/rate-limit Pendamping; `assistant_inline_http.py`: alur inline; `assistant_http.py`: façade dan adapter GET/POST legacy; `assistant_memory_store.py`: memori/consent penggunaan; `assistant_*`/`ai_*`: alur Pendamping lain; `subscription_*`/`midtrans_*`: langganan/pembayaran; `admin_store_core.py`: koneksi/schema; `admin_journal_store.py`: journal/audit/config; `admin_batch_store.py`: batch durable; `admin_bulk_transient.py`: draft batch transient; `admin_history_store.py`: proyeksi histori; `admin_*`: layanan pengelola lain; `support_settings.py`: konfigurasi dukungan; `family_deletion.py`: preview dan bundle hasil penghapusan keluarga lintas penyimpanan |

Alur domain: topik → generator/kontrak soal → penyajian → hasil tersimpan →
tinjauan/diagnosis → bukti terkonfirmasi → reducer siklus → rekomendasi/laporan.
`learning_cycle.py` sumber tunggal status/rekomendasi; reducer tidak menulis DB.

## Struktur folder

```text
jagomat/                  # repo Git luar, branch kanonis main
├── mesin/                # modul aplikasi, Dockerfile, alat operasional
│   ├── __tests__/        # pytest dan fixture sintetis
│   ├── aset/             # aset runtime
│   ├── publik/           # artefak publik statis tanpa data keluarga
│   ├── konten/           # JSON internal guru, bukan aset publik
│   └── cadangan/         # privat/lokal, tidak dilacak
├── scripts/              # palang repo, otomasi CI dan rilis
├── docs/                 # spesifikasi, keputusan, runbook
│   └── plan/             # rencana kerja lokal/gitignored
├── .github/workflows/    # CI, build, pemasangan
└── CLAUDE.md             # aturan pengembangan lengkap
```

Riset/materi/mockup: `../osn-resources/referensi/`, lokal di luar repo; bukan
kebutuhan runtime/test/build. Data wawancara operasional berada pada SQLite privat
`riset-konsumen.db`, terpisah dari `latihan.db`, `admin-control.db`, auth, dan
Pendamping; ia tidak menautkan responden ke akun/siswa. `.venv`, DB, kredensial,
cache dan cadangan tetap privat.

## Konvensi dan keputusan penting

- **Istilah UI** (keputusan 22 Okt 2026): orang dewasa disebut "Guru" (label) atau
  "Anda" (kalimat); "Pendamping" hanya untuk fitur AI. Landing publik dan panel
  pengelola belum diseragamkan; "pendampingan" tetap berarti kegiatan mendampingi.
- **Stdlib saja**, tanpa framework/dependensi runtime pihak ketiga; dev dependency
  hanya `pytest` dan `pytest-xdist`. Dependency baru perlu persetujuan pengguna.
- **Zero-JS default**: `<details>` dan navigasi query server-side; anchor lama
  memiliki tautan penerus. Pengecualian disetujui:
  mata sandi, `confirm()` destruktif, salin tautan satu sesi langsung, serta
  Kirim/Periksa Pendamping inline, serta accordion/penanda isian/konfirmasi lewati
  pada tinjauan sesi (`review_browser.py`, tanpa penilaian atau kirim otomatis).
  Kartu tinjauan memakai article/header button + panel hidden, bukan details
  bersarang; hidden tidak men-disable field. Tanpa JS seluruh kartu terbaca dan
  checkbox lewati native tersedia. Status penilaian tetap dekat dropdown, bukan
  menggantikan pertanyaan; hash/formaction/nama field tidak diubah oleh layout.
  Skrip berhash CSP, same-origin dan punya fallback
  form native; bukan izin menambah JavaScript umum. `practice_workspace.py`
  merender satu form latihan dengan fieldset nonaktif disabled; `practice_browser.py`
  mengganti mode/action dan menahan Gabungan <2 topik, tanpa network/autosave.
  Hash exact didaftarkan lewat `assistant_browser` hanya pada marker form aktual;
  fallback mode GET tetap tersedia. Salinan draf Pendamping mengecualikan kontrol
  dalam fieldset disabled, bukan hanya atribut disabled langsung. Semua tab akun memakai font
  sistem tanpa CDN; `account_browser.py` memuat mata sandi, konfirmasi via atribut
  data escaped, penanda perubahan kelas, dan validasi Indonesia semua field secara
  lokal tanpa network/autosave. Hash exact pada respons GET/POST `account_http.py`;
  validasi server dan fallback form native tetap otoritatif.
  Tab arsip percakapan tetap read-only tanpa skrip. Refresh pilihan isi lama tidak
  lagi dipakai karena alur baru tidak meminta variasi A–D.
- Nama modul Inggris; fungsi/variabel, docstring, UI dan commit Bahasa Indonesia.
  Commit conventional (`fix(murid): …`). Nilai visual melalui `design_tokens.py`
  (`T.*`); jangan hardcode hex di modul lain. Panel pengelola memakai token
  `ADMIN_*` terisolasi, komponen `admin_style.py`, dan label/tanggal WIB bersama
  `admin_labels.py`; font sistem tanpa aset jaringan. Tema admin Sistem/Terang/Gelap
  memakai form native server-side dan cookie preferensi browser `HttpOnly` scoped
  `/admin`; tidak menambah JavaScript atau state akun/database. Antrean Ringkasan dirakit
  `admin_antrean.py` (read-only, tanpa skema baru), dirender `admin_antrean_pages.py`;
  sinyal sidebar memakai antrean yang sama. Markup bersama panel ada di `admin_komponen.py`;
  daftar Keluarga/Siswa (chip berhitungan dari `jumlah_facet` query, avatar, pill kondisi)
  dirender `admin_daftar_pages.py`; tiga tampilan riwayat (tindakan, batch, AI) dirender
  `admin_riwayat_pages.py`. Satu aksi, satu entry point.
- Primitive `family_deletion.py` tidak menulis state live: ia memerlukan verifikasi
  independen, preview exact dan backup coherent lima berkas, lalu menghasilkan bundle
  privat baru dengan receipt idempoten. Cutover/recovery tetap operasi terkontrol;
  bukti dan ledger immutable tidak di-hard-delete.
- Aplikasi interviewer memakai form native Zero-JS dan hanya admin bersesi cookie.
  `research_instrument.py` menyimpan snapshot instrumen immutable; jawaban responden,
  kutipan, coding, dan catatan interviewer tetap field terpisah. Reader database
  riset tidak membuat/memperbaiki file; startup/migrator eksplisit melakukan bootstrap.
  Draf tidak masuk matriks default, denominator per pertanyaan selalu terlihat,
  ekspor menetralkan formula spreadsheet, dan maintenance menghapus isi saat retensi.
- Konfigurasi dukungan berada pada namespace schema aditif optional-absent-or-exact
  di `admin-control.db`, tanpa menaikkan admin7/8/9. `support_settings.migrasikan`
  adalah migrator opt-in; reader tidak membuat/memperbaiki DB dan fail-closed bila
  schema atau nilai rusak. Admin Operasional memakai CSRF, tinjauan signed, reauth,
  revisi optimistik, transaksi config+audit, dan replay operation ID. Renderer publik
  hanya menerima DTO nomor/jam/SLA yang sudah tervalidasi.
- Registrasi menyimpan `siswa.tingkat=''` sampai pemetaan pertama disiapkan, tanpa
  default dari kelas atau backfill. Layanan kemudian menetapkan P3 sebagai konteks
  fondasi internal secara atomik; P3–P6 tetap codec histori, bukan pilihan pengguna.
  `question_context.profil_otomatis()` memilih profil efektif manual/gabungan yang
  didukung dan paling dekat tanpa mengubah profil rencana. Generator mempertahankan
  komposisi historis sambil memvariasikan parameter dan urutan sesuai seed.
  `profile_home.py` menyajikan Beranda dengan helper CTA/tahap siklus existing,
  terpisah dari renderer hasil sesi; `profile_history.tinjauan_terlama()` membatasi
  tiga sesi terkirim sebelum proyeksi, dan tautan progres memakai adapter/peta
  laporan yang sama (gagal verifikasi: tanpa angka). Pilot aktif/pemulihan tetap
  memakai renderer khususnya, bukan diproyeksikan sebagai rencana utama.
- `teacher_home_priority.py` memberi beranda guru langkah, kelompok, dan urutan per anak:
  pilot aktif lewat `skill_pilot_ui.keadaan`, selain itu `rencana_berikutnya`; label dari
  `cycle_report.TINDAKAN`; kegagalan baca per anak dicatat tanpa nama dan menjadi kartu
  fallback; `urutkan` mendahulukan sesi yang terlama menunggu konfirmasi (tanggal sesi,
  `menunggu_sejak`) lalu nama. Murni turunan reducer (tanpa tulis DB, tanpa penilaian baru); render di
  `teacher_pages._daftar_anak_berkelompok`. `normalkan_filter`/`cocok_filter` menyaring
  proyeksi owner-scoped melalui GET `cari`/`kelompok` yang diteruskan `teacher_http`;
  pencarian login memakai lookup `students.akun_murid_dari_siswa` existing hanya saat
  kata pencarian terisi, tanpa query/writer DB baru. Form/CSS HP scoped di `teacher_pages`
  memakai T.*; filter tidak menambah JS. Shell beranda mempertahankan dua skrip
  existing (mata sandi/cegah kirim ganda) dan Google Fonts. Respons no-store/no-referrer
  memakai opsi CSP khusus beranda di `web._kirim_privat`: dua hash exact, sumber font
  existing dan manifest same-origin; CSP halaman privat lain tidak diperluas.
  Biaya baseline sebelum filter terukur ±13 ms untuk 30 anak sintetis; bukan klaim
  performa pencarian akun atau produksi.
  Keempat tab `/anak/<id>` berbagi satu kontainer isi 960px (`child_style.py`, token
  `ANAK_*`, mockup di `docs/mockup/`) dan komponen HTML bersama `child_components.py`
  (chip status, pil filter, disclosure, banner tautan, kartu sesi); CSS per tab ada di
  `child_*_style.py` (Beranda, Latihan, Riwayat, Perkembangan); warna badge review bersama di
  `child_badge_style.py`, durasi sesi dari `profile_history.durasi_detik`. Jangan menambal lebar per tab.
  `child_header.py` mengisolasi markup/style header orang tua `/anak/<id>` dengan
  marker `anak-header-st`, tanpa mengubah shell halaman lain. Sticky dan bayangan
  memakai CSS (bayangan sebagai progressive enhancement); pemicu Pendamping melayang
  tetap memakai binding/form native existing, termasuk ketika mode latihan berganti.
  `assistant_context` membangun snapshot baca konsisten berkontrak v2: fakta minimum
  dan binding alias lokal ikut fingerprint, kategori netral existing tanpa migrasi.
  Antrean memakai predicate konfirmasi aktif bersama `profile_history`; izin versi
  lama tidak mengesahkan payload baru. Empat posisi tab tetap resource anak sama;
  navigasi membawa chat berizin tanpa draf/storage. `assistant_browser` menambah
  contoh isi-draf, Esc dan scroll percakapan; `style_stitch` memisahkan composer
  dari area gulir pada overlay desktop/sheet HP.
  `profile_workspace.py` menjadi sumber navigasi empat tujuan profil: **Beranda**,
  **Latihan**, **Riwayat**, dan **Perkembangan**. Pascapendaftaran dan default
  `/anak/<id>` sama-sama membuka Beranda; POST latihan kembali eksplisit ke
  `?section=latihan`, aksi siklus ke `?section=rencana`, dan arsip ke
  `?section=riwayat`; starter pilot opsional hanya dirender oleh tab latihan,
  sedangkan kartu/status/pemulihan pilot aktif tetap berasal dari reducer di
  Beranda; tab Perkembangan di `?section=perkembangan` memakai konten
  `reports.konten_laporan()` yang sama dengan halaman lama. Deep link laporan lama dialihkan oleh `teacher_http.py` setelah
  guard ownership. `reports.py` dan
  `report_metrics.py` menyediakan filter periode aktivitas
  server-side; Semua memakai agregat existing. `reports.konten_laporan()` hanya
  merender Ringkasan atau Per materi; histori lama lewat disclosure, tanpa reducer
  kedua. Catatan putaran aktif dan histori variasi tetap dapat dibuka tanpa
  stepper/CTA ganda; pencabutan tautan tetap tersedia di halaman sesi. Daftar materi
  lengkap, mini bar dan status memakai denominator katalog. Layanan siklus menginisialisasi konteks fondasi dan
  pemetaan pertama secara atomik dari satu tindakan eksplisit orang tua.
- Konfirmasi foto di `attachments.py` memakai `<details>` native: preview bacaan
  awal tetap terlihat, pengecualian terbuka, seluruh field berada dalam form Terapkan.
  Lipatan bukan penilaian/disabled; GET tidak menerapkan AI. Entry upload PG tanpa
  lampiran disembunyikan pada renderer guru/akun anak, bukan pada guard HTTP.
  CTA foto tinjauan hanya muncul bila tujuan upload tersedia; tidak ada JS/schema
  atau kapabilitas tautan anak baru.
  `halaman_konfirmasi_guru` memilih mode lewat `ai_pembacaan_aktif()` (kunci vision);
  `halaman_konfirmasi(ai_aktif=False)` menyajikan isi-manual tanpa menyentuh jalur
  tulis (`terapkan`), arsip `sumber='foto'`, atau schema.
- `teaching_playbook.py` memvalidasi JSON internal `konten/playbook_p3.json`, tanpa
  I/O saat impor, DB, network, atau cache konten. Selector hanya guru, fokus/profil
  exact dan pendekatan existing; saksi seed memeriksa pasangan malrule/kode, bukan
  mengesahkan pedagogi. `_boleh_tampil` menerima draf dengan metadata review seluruhnya
  null (pengecualian eksplisit pemilik), atau disahkan dengan ulasan/hash sah.
  Invalid/duplikat/review usang tetap kosong; tidak fallback dari disahkan rusak ke draf.
  Hash mengikat ulasan ke isi/versi, bukan membuktikan identitas manusia. JSON ikut
  image lewat COPY internal, bukan aset publik. Slot `teacher_session_pages` memakai
  kode efektif dan malrule usulan yang cocok; `profile_home` menerima peran eksplisit
  melalui `teacher_workspace`/`learning_cycle_ui`, mengikuti fokus/pendekatan reducer.
  Bukan guru tidak membaca isi. Draf memakai warning permanen di summary native
  tertutup/terbuka, metadata “belum ada pengesahan manusia”; tanpa identitas reviewer rekaan.
  Tidak mengubah reducer/materi existing. [Kontrak dan ulasan](playbook-guru.md); prioritas guru in-house, data sintetis dulu.
- `parent_help.py` merender kartu pra-tulis dan FAQ kontekstual pada permukaan
  guru melalui `teacher_workspace`/`teacher_session_pages`, tanpa DB/AI atau route
  baru. Disclosure native menjaga form/draf; kunci/pembahasan tetap dari loader
  soal existing, escaped dan ditampilkan sekali dekat soal pada tinjauan.
- Kunci/diagnosis tetap deterministik; `llm.py` hanya memparafrase kalimat soal.
  `story_frames.py` menyediakan bingkai offline opt-in default0 di proyeksi snapshot
  baru, bukan reader histori; visual/custom dan KPK murni tetap utuh. Provenance
  bank ada pada artefak rilis, bukan field snapshotv1. Cache B2 bersnapshot diikat
  fingerprint sumber; detail [bank kalimat](story-frames.md).
  `scripts/challenge_packet.py` mengekspor paket cetak terpisah beserta solusi dan
  manifest; hanya stdlib, tanpa impor/runtime aplikasi atau jalur bukti belajar.
  `number_theory_expansion.py` menyediakan empat jenis hitung murni P4/P5 melalui
  registry `topic_number_theory`; kartu/inventaris/katalog target eksplisit.
  `number_theory_versions.py` memisahkan komposisi writer recovery (1) dan batch
  baru (2); `Topik.komposisi_writer` hanya memilih latihan baru, sedangkan
  `komposisi` tetap inventaris histori untuk konteks/laporan pada kedua versi. Probe rilis
  `release_question_pair.py` wajib membuktikan bank/PG/cetak/diagnosis C→B→C.
  Katalog materi `jagomat-2026-10-v2` menambah target, tidak mengubah bukti lama.
  `catalog_versions.py` memisahkan versi konten untuk [koreksi katalog](catalog-corrections.md):
  marker parameter membedakan identitas bank baru, reader tanpa marker mempertahankan
  fungsi historis. Kandidat/produksi writer2, recoveryedd323c writer1 dan reader lengkap
  termasuk pilot kisi; konten telah ditinjau manusia. Probe selalu membuat katalog2
  di sandbox agar kompatibilitas tidak lolos akibat flag nonaktif. Konteks umur
  Ari/Bima memiliki marker sendiri; reader tetap mengenali konteks ayah–anak lama.
  `catalog_preview.py` membekukan contoh sintetis+hash pada artefak CI.
  [Pilot bank terkurasi](catalog-pilot.md) memakai `assessment_revision.py` opt-in
  default0 untuk codec/prosedur baru tanpa mengubah histori. `scripts/catalog_pilot*`
  membandingkan90 draf offline A/B/C dengan oracle terpisah; belum jalur serving
  atau keputusan migrasi bank, dan belum memiliki hasil review manusia.
  Cetak guru membaca kunci/malrule bank tersimpan, bukan aturan template terbaru;
  pembahasan masih dari template sesuai versi parameter. Identitas bank idempoten tidak menulis ulang
  malrule historis ketika soal dipakai kembali. Pendamping tidak boleh mengambil
  alih reducer atau konfirmasi bukti belajar.
  Adapter GET/POST lama sengaja tetap di `assistant_http.py`: alurnya berbagi helper
  privat dengan façade dan compatibility lookup dari alur inline; ekstraksi lanjutan
  akan menambah siklus/duplikasi guard tanpa boundary yang lebih aman.
  `learning_cycle.py` sengaja tetap utuh: reducer rekomendasi, evaluasi/checkpoint,
  penguasaan, dan adapter pilot berbagi model immutable serta primitive keputusan;
  pemisahan lebih lanjut berisiko membuat sumber keputusan paralel hanya demi LOC.
- Lock file/thread dan session fence batch admin sengaja tetap bersama orkestrasi
  `admin_bulk.py`: callback durable/transient dan test crash mem-patch boundary façade
  tersebut; memindahkannya akan menambah callback/cycle pada batas crash dua SQLite.
- `assistant_manage.py` menangani `/pendamping/kelola` sebelum gate feature/provider
  melalui `assistant_http`; principal cookie guru, ownership sumber, versi dan
  CSRF tetap wajib. GET metadata read-only tidak bootstrap DB; POST memakai
  primitive tombstone/revoke existing dalam satu transaksi. Pagar client dalam
  `assistant_service` mengecek ulang chat/izin setelah admission AI menunggu.
- `assistant_store.py` kini sekitar 890 baris setelah concern memori dipisah;
  chat/pesan, persetujuan, usulan, operasi, dan retensi tetap satu agregat owner-scoped
  dengan transaksi/foreign key bersama, sehingga tidak dipecah lagi hanya demi LOC.
- KPI onboarding admin7 lama tetap terpisah dan tidak mengukur nilai pertama ≤48 jam.
  `sensor_schema/store/http/domain/report/pages` menyediakan sensor internal optional-additive
  pada admin DB: consent mandiri keluarga lama/baru, episode HMAC, milestone setelah
  commit, turunan konfirmasi pertama/chat tanpa teks, TTL/cascade/family deletion,
  health best-effort dan supresi ≥5 keluarga per sel. Gate deployment tersendiri;
  `policy_schema/store/http/pages/terms` menambahkan receipt dan satu layar persetujuan
  awal. Epoch host terpisah backup mempertahankan izin saat restart; restore wajib
  rotasi epoch+recreate. Decline/revoke tetap di receipt, tidak memicu gate ulang.
  Migrator opt-in serta backup `target_sensor/target_policy` mengenal namespace;
  [kontrak persetujuan](persetujuan-awal.md). Bukan aktivasi WS5 lama.
- Lokal memakai `mesin/.venv/bin/python` (3.9.6); CI/container 3.12. Kode kompatibel
  3.9. Verifikasi sesuai risiko: Ringan/Normal/Kritis; tes scoped lokal, push CI cepat,
  full kandidat mingguan, dan gate rilis lengkap via dispatch pada SHA target. Palang
  index: `mesin/.venv/bin/python scripts/check_repo.py` setelah stage.
- Git selalu `git -C /Users/nugroho/Documents/jagomat …`; hindari repo basi
  `mesin/.git`, jaga WIP sesi lain. Repo `clarinovist/jagomat`; domain `jagomat.id`.
- Image tetap `ghcr.io/clarinovist/osn-mesin-latihan` demi kompatibilitas recovery.
  Rilis mengikuti **uji → bangun → pasang**, artifact/digest yang sama. Fingerprint
  recovery memproyeksikan AST operasi/guard persistensi sehingga ekstraksi murni
  lintas modul tidak mengubah kontrak, sedangkan perubahan SQL/guard/transaksi tetap
  tertangkap; ID kontrak lama dipetakan eksplisit hanya untuk proyeksi yang identik.
  CI hijau bukan bukti pemasangan; jangan build di VPS atau menyalakan Docker lokal.

Detail: [workflow](workflow-reference.md) · [design system](design-system.md) ·
[CI selektif](ci-selective.md) · [rilis produksi](production-release.md) ·
[penamaan repo](repository-naming.md). Ringkasan ini bukan izin mengubah palang.
