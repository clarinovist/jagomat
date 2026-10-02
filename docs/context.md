# Jagomat — Konteks teknis ringkas

> Peta orientasi ±1 halaman; baca [spec.md](spec.md) untuk kontrak produk.
> [CLAUDE.md](../CLAUDE.md) tetap acuan palang dan workflow; status produksi diperiksa terpisah.
> Wajib disinkronkan saat arsitektur/struktur/konvensi/keputusan teknis berubah,
> dalam perubahan yang sama; tetap ±1 halaman. Aturan: [sinkronisasi ringkasan](../CLAUDE.md#jaga-ringkasan-proyek-tetap-sinkron).

## Arsitektur

**Monolit Python stdlib, HTML dirender server, penyimpanan SQLite.**
`serve.py` menjalankan server HTTP; `web.py` mengatur transport, dispatch, dan
palang akses. `student_http.py` memiliki alur GET/POST akun murid,
`session_http.py` memiliki pembuatan, tampilan/cetak, review, dan latihan tindak
lanjut sesi guru; `share_http.py` memiliki capability satu sesi dan aksi bagikan guru;
`public_http.py` memiliki halaman publik tanpa data keluarga; `auth_http.py` memiliki
login/logout; `registration_http.py` memiliki pendaftaran keluarga;
`account_http.py` memiliki halaman dan mutasi akun guru; `teacher_http.py` memiliki
beranda, workspace anak, dan laporan; sementara `attachment_http.py` memagari baca,
upload, dan penerapan foto guru.
Nama modul di bawah relatif terhadap `mesin/`, bukan direktori baru.

| Lapisan | Modul dan tanggung jawab |
| --- | --- |
| Identitas | `auth.py`, `sessions.py`: akun dan sesi login; `students.py`: data anak |
| Soal | `topics.py` + `topic_*.py`: topik; `generator.py`: pembangkitan; `templates.py`: kontrak soal |
| Penyajian | `render.py`, `worksheets.py`, `*_pages.py`, `*_ui.py`: HTML/layar; `teacher_shell.py`: bingkai/topbar; `teacher_workspace.py`: profil/form; `teacher_session_pages.py`: tinjauan; `teacher_print_pages.py`: cetak/lampiran; `teacher_review_service.py`: koreksi |
| Data | `database.py`, `schema.py`, `*_store.py`, `*_schema.py`: penyimpanan dan migrasi; `attachment_store.py`: metadata lampiran; `report_store.py`: proyeksi laporan; `student_profile_store.py`: profil/kepemilikan siswa; `question_bank_store.py`: bank soal |
| Belajar | `diagnosis.py`, `learning_cycle.py`, `learning_cycle_service.py`: diagnosis, reducer murni, orkestrasi |
| Laporan | `reports.py`, `report_*.py`, `mastery_*.py`: laporan dan penguasaan berbasis bukti |
| Layanan lain | `assistant_http_common.py`: parser/response/rate-limit Pendamping; `assistant_inline_http.py`: alur inline; `assistant_memory_store.py`: memori/consent penggunaan; `assistant_*`/`ai_*`: alur Pendamping lain; `subscription_*`/`midtrans_*`: langganan/pembayaran; `admin_store_core.py`: koneksi/schema; `admin_journal_store.py`: journal/audit/config; `admin_batch_store.py`: batch durable; `admin_bulk_transient.py`: draft batch transient; `admin_history_store.py`: proyeksi histori; `admin_*`: layanan pengelola lain; `support_settings.py`: konfigurasi dukungan; `family_deletion.py`: preview dan bundle hasil penghapusan keluarga lintas penyimpanan |

Alur domain: topik → generator/kontrak soal → penyajian → hasil tersimpan →
tinjauan/diagnosis → bukti terkonfirmasi → reducer siklus → rekomendasi/laporan.
`learning_cycle.py` sumber tunggal status/rekomendasi; reducer tidak menulis DB.

## Struktur folder

```text
jagomat/                  # repo Git luar, branch kanonis main
├── mesin/                # modul aplikasi, Dockerfile, alat operasional
│   ├── __tests__/        # pytest dan fixture sintetis
│   ├── aset/             # aset runtime
│   └── cadangan/         # privat/lokal, tidak dilacak
├── scripts/              # palang repo, otomasi CI dan rilis
├── docs/                 # spesifikasi, keputusan, runbook
│   └── plan/             # rencana kerja lokal/gitignored
├── .github/workflows/    # CI, build, pemasangan
└── CLAUDE.md             # aturan pengembangan lengkap
```

Riset/materi/mockup: `../osn-resources/referensi/`, lokal di luar repo; bukan
kebutuhan runtime/test/build. `.venv`, DB, kredensial, cache dan cadangan tetap privat.

## Konvensi dan keputusan penting

- **Stdlib saja**, tanpa framework/dependensi runtime pihak ketiga; dev dependency
  hanya `pytest` dan `pytest-xdist`. Dependency baru perlu persetujuan pengguna.
- **Zero-JS default**: `<details>` dan `?section=` server-side. Pengecualian disetujui:
  mata sandi, `confirm()` destruktif, salin tautan satu sesi langsung, serta
  Kirim/Periksa Pendamping inline. Skrip berhash CSP, same-origin dan punya fallback
  form native; bukan izin menambah JavaScript umum. Refresh pilihan isi lama tidak
  lagi dipakai karena alur baru tidak meminta variasi A–D.
- Nama modul Inggris; fungsi/variabel, docstring, UI dan commit Bahasa Indonesia.
  Commit conventional (`fix(murid): …`). Nilai visual melalui `design_tokens.py`
  (`T.*`); jangan hardcode hex di modul lain. Satu aksi, satu entry point.
- Primitive `family_deletion.py` tidak menulis state live: ia memerlukan verifikasi
  independen, preview exact dan backup coherent lima berkas, lalu menghasilkan bundle
  privat baru dengan receipt idempoten. Cutover/recovery tetap operasi terkontrol;
  bukti dan ledger immutable tidak di-hard-delete.
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
  `profile_workspace.py` menjadi sumber navigasi empat tujuan profil. Pascapendaftaran
  membuka `?section=rencana` yang dilabeli **Langkah berikutnya**, sedangkan default
  `/anak/<id>` tetap membuka latihan manual untuk kompatibilitas. Kartu beranda hanya
  mengarahkan profil yang rencananya belum dimulai ke tab tersebut. `reports.py` dan
  `report_metrics.py` menyediakan filter periode aktivitas
  server-side melalui query GET. Layanan siklus menginisialisasi konteks fondasi dan
  pemetaan pertama secara atomik dari satu tindakan eksplisit orang tua.
- Kunci/diagnosis tetap deterministik; `llm.py` hanya memparafrase kalimat soal.
  Pendamping tidak boleh mengambil alih reducer atau konfirmasi bukti belajar.
  `learning_cycle.py` sengaja tetap utuh: reducer rekomendasi, evaluasi/checkpoint,
  penguasaan, dan adapter pilot berbagi model immutable serta primitive keputusan;
  pemisahan lebih lanjut berisiko membuat sumber keputusan paralel hanya demi LOC.
- Analitik onboarding tetap pada kontrak KPI admin7 lama dan belum mengukur nilai
  pertama ≤48 jam: event existing hanya pengiriman/penyajian, bukan gabungan selesai,
  ditinjau, dikonfirmasi, lalu langkah berikutnya tersaji. WS5 dihentikan sampai
  schema, migrasi, retensi, purge, backup, dan recovery exact memahami event baru.
- Lokal memakai `mesin/.venv/bin/python` (3.9.6); CI/container 3.12. Kode kompatibel
  3.9. Verifikasi sesuai risiko: Ringan/Normal/Kritis; tes scoped lokal, gate berat
  di CI. Palang index: `mesin/.venv/bin/python scripts/check_repo.py` setelah stage.
- Git selalu `git -C /Users/nugroho/Documents/jagomat …`; hindari repo basi
  `mesin/.git`, jaga WIP sesi lain. Repo `clarinovist/jagomat`; domain `jagomat.id`.
- Image tetap `ghcr.io/clarinovist/osn-mesin-latihan` demi kompatibilitas recovery.
  Rilis mengikuti **uji → bangun → pasang**, artifact/digest yang sama. CI hijau
  bukan bukti pemasangan; jangan build di VPS atau otomatis menyalakan Docker lokal.

Detail: [workflow](workflow-reference.md) · [design system](design-system.md) ·
[CI selektif](ci-selective.md) · [rilis produksi](production-release.md) ·
[penamaan repo](repository-naming.md). Ringkasan ini bukan izin mengubah palang.
