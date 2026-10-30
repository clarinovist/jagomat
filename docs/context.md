# Jagomat — Konteks teknis ringkas

Peta orientasi; detail di [referensi arsitektur](architecture-reference.md), kontrak
produk di [spec.md](spec.md), palang kerja di [CLAUDE.md](../CLAUDE.md).
Status deployment/eksperimen: [status proyek](status-proyek.md).

## Arsitektur

**Monolit Python stdlib, HTML server-side, SQLite.** Nama modul berikut relatif
terhadap `mesin/`. Alur: topik/generator → penyajian tersimpan → tinjauan/diagnosis
→ bukti terkonfirmasi → reducer siklus → rekomendasi/laporan.

| Lapisan | Sumber utama |
| --- | --- |
| HTTP | `serve.py`, `web.py`, router `*_http.py`; murid/share dipisahkan dari guru/admin |
| Identitas | `auth.py`, `sessions.py`, `students.py`; guard principal/kepemilikan server-side |
| Soal | `topics.py`, `topic_*.py`, `templates.py`, `generator.py`; parameter dan versi deterministik |
| Penyajian | `question_views.py`, `render.py`, `worksheets.py`, `*_pages.py`, `*_ui.py` |
| Persistensi | `database.py`/`schema.py` sebagai façade; `*_store.py`, `*_schema.py` menjaga transaksi/provenance |
| Belajar/laporan | `diagnosis.py`; `learning_cycle.py` reducer murni tunggal; service/sessions mengorkestrasi; `reports.py`, `mastery_*`, `report_*` memproyeksi bukti |
| Layanan | `assistant_*`/`ai_*`, `subscription_*`/`midtrans_*`, `admin_*`, `research_*`, `support_settings.py` |

## Struktur dan data

- `mesin/`: aplikasi, `__tests__/`, aset, `publik/`, konten internal `konten/`, Dockerfile.
- `scripts/`: palang repo, shard CI, build/probe/pair/deployer, katalog desain luring dan eksperimen sintetis.
- `docs/`: kontrak permanen; `docs/plan/` lokal/gitignored, bukan satu-satunya sumber keputusan.
- Empat DB durable inti: belajar, Pendamping, kontrol AI, kontrol admin; auth
  `sandi.json` ikut bundle backup. Riset konsumen mempunyai DB/retensi/backup terpisah.
  Sesi/transient bukan pengganti state durable; detail inventaris di runbook.
  `scripts/operational_backup.py` menambahkan envelope core+riset+lampiran saat
  quiescent dan transfer privat tervalidasi; `mesin/cadangkan.sh` fetch-only, tanpa prune.
- Riset/materi historis di `../osn-resources/referensi/`; bukan dependency runtime.
  DB, credential, `.venv`, cache, backup dan artefak privat tidak dilacak Git.

## Konvensi dan keputusan teknis

- `templates.LEVEL` mencakup variasi Latihan P1–P6; `LEVEL_TINGKAT` menjaga
  `siswa.tingkat` dan siklus P3–P6 (kosong tetap sah saat onboarding).
  `skill_pilot.LEVEL_PILOT` membatasi konten pilot P3–P6. `context_migration.py`
  memperluas CHECK konteks lama saat startup lewat rebuild transaksional dengan
  verifikasi jumlah/SHA-256 baris; DDL baru menerima P1/P2. Konten dasar tetap terpisah.
- Stdlib runtime; dev dependency hanya pytest/pytest-xdist. Python lokal3.9.6 dan
  CI/container3.12. Nama modul Inggris; fungsi/docstring/UI/commit Bahasa Indonesia.
- Zero-JS default. Enhancement yang disetujui berhash CSP dan fallback native;
  validasi server tetap otoritatif. Tidak ada izin JS/dependency umum dari pola ini.
  Daftar pengecualian/perilaku lengkap di [arsitektur](architecture-reference.md#konvensi-dan-keputusan-penting).
- Token visual di `design_tokens.py`; peran semantik per permukaan dan pasangan kontras
  di `design_roles.py` (rujukan + guard test, bukan import runtime); kontrak di
  [design system](design-system.md). Admin berbagi token terang/skala/brand dan acuan
  komponen (tombol sekunder, pil, tab, tautan kembali, header) dengan keluarga;
  `ADMIN_*` hanya adapter tema, sidebar/tabel tetap layout admin. Empat tab
  profil dan laporan lama berbagi shell/lebar `ANAK_*`. CSS rincian legacy hanya dimuat
  pada laporan, sebelum override profil; [audit UI](ui-consistency-audit.md) dan
  [audit admin](admin-ui-audit.md) (fokus, kontrol, state dan tema/cetak).
- `teacher_home_priority.py` hanya memproyeksi reducer; `guru_beranda_pages.py` merender /guru
  (chip GET owner-scoped dengan filter instan berhash/fallback native) tanpa menulis DB atau membuat ranking
  kemampuan. Respons privat no-store/no-referrer.
- `teaching_playbook.py` membaca JSON internal dengan validasi identitas/versi/hash;
  draf berlabel diizinkan tampil, bukan disahkan. `assistant_manage.py` menangani
  pengelolaan data sebelum gate provider; AI tidak mengambil alih konfirmasi/reducer.
- `catalog_versions.py`/`number_theory_versions.py` memisahkan writer dan reader
  historis. Bank kalimat hanya mengubah snapshot baru. `assessment_revision.py`
  revisi1 default0; `catalog_followup.py` menyediakan draf revisi2 terpisah
  (`OSN_KATALOG_LANJUTAN=0`), reader berdasarkan marker dan tanpa backfill.
  Codec sesi campuran v2 belum terhubung writer.
- `family_deletion.py` menghasilkan bundle privat tervalidasi, bukan mutasi live
  langsung. Sensor/policy, billing dan riset tetap mempunyai consent/retensi berbeda.
- Façade/adapter legacy dan reducer besar sengaja dipertahankan ketika pemisahan
  akan merusak boundary transaksi/retry; lihat alasan di referensi arsitektur.

## Git, verifikasi dan produksi

Repo luar `/Users/nugroho/Documents/jagomat`, branch `main`, origin
`clarinovist/jagomat`; `mesin/.git` basi bukan repo kerja. Gunakan `git -C` ke repo
luar dan jaga WIP sesi lain. Lokal: scoped test/compile/review, bukan full suite default.
Push memberi CI cepat; dispatch manual membuktikan kandidat/recovery exact empat
shard, build/probe/pair. [CI hybrid](ci-selective.md).

Image tetap `ghcr.io/clarinovist/osn-mesin-latihan`; domain `https://jagomat.id`;
SSH alias `biznet-sekolahdesain`. Tidak build di VPS. Auto-pasang tetap nonaktif;
preflight sebelum maintenance, backup/rehearsal, exact digest, health dan recovery
mengikuti [runbook](production-release.md), bukan disimpulkan dari CI hijau.
