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
| Metrik runtime | `metrik_runtime.py` (di memori, label rute daftar putih tanpa path mentah; p95 per rute, `locked`, CPU); dipasang di `do_GET`/`do_POST`, dilihat admin di `/admin/metrik` (JSON) dan satu baris stdout per 600 detik bila ada request |
| Identitas | `auth.py`, `sessions.py`, `students.py`; guard principal/kepemilikan server-side |
| Soal | `topics.py`, `topic_*.py`, `templates.py`, `generator.py`; parameter dan versi deterministik |
| Penyajian | `question_views.py`, `render.py`, `worksheets.py`, `*_pages.py`, `*_ui.py` |
| Persistensi | `database.py`/`schema.py` sebagai façade; `*_store.py`, `*_schema.py` menjaga transaksi/provenance; `berkas_data.py` saat start: DB durable + sidecar 0600 dan WAL pulih bila berkas ada (tanpa DDL) |
| Belajar/laporan | `diagnosis.py`; `learning_cycle.py` reducer murni tunggal; service/sessions mengorkestrasi; `reports.py`, `mastery_*`, `report_*` memproyeksi bukti |
| Layanan | `assistant_*`/`ai_*`, `subscription_*`/`midtrans_*`, `admin_*`, `research_*`, `support_settings.py` |

## Struktur dan data

- `mesin/`: aplikasi, `__tests__/`, aset, `publik/`, konten internal `konten/`, Dockerfile.
- Email transaksional E1 (25 Nov 2026, belum dipasang): `mesin/surel_resend.py` (pengirim Resend stdlib; gagal tertutup bila env `RESEND_API_KEY` kosong, `SUREL_PENGIRIM` opsional) dan `mesin/surel_tunggakan_admin.py` (CLI `--database`, ringkasan agregat tunggakan kelas ke env `SUREL_ADMIN`, DB dibuka baca-saja). E1 tanpa DB atau tabel baru; pemasangan env di server dan baris cron host adalah tindakan terpisah.
- `scripts/`: palang repo, shard CI, build/probe/pair/deployer, katalog desain luring, ekspor token untuk alat desain, dan eksperimen sintetis. Modul `release_*_pair.py` adalah data probe; bentuknya (konstanta wajib + penanda unik) dijaga `release_pair_common.py` dan test kontrak, bukan disalin manual.
- `docs/`: kontrak permanen; `docs/plan/` lokal/gitignored, bukan satu-satunya sumber keputusan.
- Empat DB durable inti: belajar, Pendamping, kontrol AI, kontrol admin; auth
  `sandi.json` ikut bundle backup. Riset konsumen mempunyai DB/retensi/backup terpisah.
  Sesi/transient bukan pengganti state durable; detail inventaris di runbook.
  `scripts/operational_backup.py` menambahkan envelope core+riset+lampiran
  (+ `sakelar.db`/`kurikulum.db`/`cetakan.db` opsional, manifest v2) saat quiescent dan transfer privat tervalidasi; `mesin/cadangkan.sh` fetch-only, tanpa prune.
  Off-site dari VPS (terpasang 21 Nov 2026): `scripts/backup_offsite_vps.py` (enkripsi hibrida kunci publik, klien SigV4 `r2_s3.py`, format `offsite_kripto.py`, retensi/penanda/tar `offsite_retensi.py`, `offsite_penanda.py`, `offsite_kerja.py`) dan `scripts/pulihkan_offsite.py` (Mac, kunci privat); kunci dekripsi tidak pernah di VPS. Monitor kesehatannya jalan di Mac: `scripts/pantau_offsite_vps.py` (job Hermes pagi, alert Telegram).
- Riset/materi historis di `../riset/referensi/`; bukan dependency runtime.
  DB, credential, `.venv`, cache, backup dan artefak privat tidak dilacak Git.

## Konvensi dan keputusan teknis

- `templates.LEVEL` mencakup variasi Latihan P1–P6; `LEVEL_TINGKAT` menjaga
  `siswa.tingkat` dan siklus P3–P6 (kosong tetap sah saat onboarding).
  `skill_pilot.LEVEL_PILOT` membatasi konten pilot P3–P6. `context_migration.py`
  memperluas CHECK konteks lama saat startup lewat rebuild transaksional dengan
  verifikasi jumlah/SHA-256 baris; DDL baru menerima P1/P2. `topic_basic_numbers.py`
  memuat lima jenis manual P1/P2 (`tambah_dasar`, `kurang_dasar`, `bilangan_hilang`;
  `nilai_tempat` dan `bandingkan_bilangan` di `basic_numbers_place_compare.py`) dengan
  domain eksplisit, cakupan ≥ min(90% domain, 200) dalam 500 seed; `basic_numbers_versions`
  memegang sakelar writer `OSN_DASAR_LENGKAP` (bawaan kode 0 = 10× `tambah_dasar`;
  produksi 1 sejak 6 Nov 2026 = dua soal per jenis) lewat
  `komposisi_writer`, palang pembuat di `generator.buat_lembar` dan saringan penawaran;
  `komposisi` pembaca memuat kelima jenis. PG tiga opsi (simbol `<`/`>`/`=` lewat jenis
  `simbol_perbandingan`), tanpa marker koreksi histori atau
  target mastery; grup katalog terdaftar untuk audit, bukan target siklus.
  `topic_school_numbers.py` (topik `bilangan-sekolah`, lima jenis P3–P5; pembangun per jenis di
  `school_numbers_order/column/muldiv/equation/common.py`) dijaga sakelar
  `school_numbers_versions` (`OSN_BILANGAN_SEKOLAH`, env-only, "0"/"1", bawaan 0; palang lewat
  `basic_numbers_versions.template_dibuka` dan `question_context`). Palang **manual-saja**:
  `Topik.hanya_manual` mengecualikan topik dari Campuran (`_daftarkan_campuran`) dan, lewat
  `topics.daftar_topik_siklus()`/`template_hanya_manual()`, dari pemetaan, probe, ubah fokus,
  katalog mastery, penawaran Pendamping, dan remedial inline. Alasan: topik P3+ otomatis ikut siklus
  bila hanya bergantung pada `LEVEL_TINGKAT`, padahal belum punya grup mastery, kartu intervensi,
  dan playbook. Pembaca histori tetap mengenal ID-nya.
  `topic_matematika_awal.py` (topik `matematika-awal`, manual-saja, P1 sampai P6, 25 jenis di
  `awal_<jenis>.py`; sakelar `matematika_awal_versions` `OSN_MATEMATIKA_AWAL`, env-only, "0"/"1", bawaan 1,
  kunci jenis di `TEMPLATE_BARU`; palang lewat `basic_numbers_versions.template_dibuka` dan `question_context`).
  Komposisi level dibangun dari tuple `JENIS` (jenis level itu diulang bergiliran sampai 10 soal; P4 punya
  tiga jenis sejak gelombang 1). **Menambah satu jenis**: modul `awal_<jenis>.py` (fungsi soal, `LEVEL`,
  `domain_parameter`, `parameter`, solver terpisah di tesnya), satu entri `Jenis(...)`, lalu titik sentuh
  bersama: `TEMPLATE_BARU`, `template_labels`, `rumus.KARTU`+`KONSEP_TEMPLATE`, `visual_inventory`
  (`_BUKTI_TEMPLATE`+`_ROWS`), `choice_generation` (`TIGA`, `kebijakan_soal`/`KATEGORI_AWAL`, `kandidat`;
  pengecoh di luar malrule lewat `pengecoh_tambahan` modul), `konten/pancingan/matematika-awal.json`,
  `kurikulum_katalog` (grup), `kurikulum_cp` (peta CP), `kurikulum_kelas` (pelatih bab), dan tes bersama
  (`baseline_matematika_awal.LEVEL_JENIS`, baseline `test_kualitas_soal_generik`). Kecocokan pelatih bab
  "ada" hanya bila SETIAP sub-materi bab punya jenis di level kelas itu; bab bergambar yang hanya
  bersoal teks tetap "sebagian" (kecuali lima bab yang sub-materinya tertutup soal teks, keputusan pemilik 21 Nov 2026).
  K3 B5 dan K4 B6 (statistika) "ada" karena tiap template pelatihnya `wajib_visual` di inventaris dan dipetakan
  `proyeksi_statistika`. Flag visual menyala di produksi per `/opt/osn/visual.conf` (dibaca read-only 21 Nov 2026, berkas bertanggal 19 Nov): `OSN_VISUAL_KELUARGA=statistika,geometri-datar,geometri-ruang,pengukuran,kombinatorik,pola-bilangan`. Keterbatasan: status "ada" kedua bab ini bergantung pada flag visual menyala; tanpa flag soalnya berupa teks (tes `test_bab_data_ada_bergantung_pada_flag_visual_soal_tanpa_flag_berupa_teks`). Status bab sekarang 40 ada, 0 sebagian, 0 belum (22 Nov 2026). Keluarga visual `matematika-awal` (`topic_matematika_awal_visual`, descriptor `adegan_awal` v1 dengan sub-adegan `deret_ikon`, `turus`, `pita_ukur`, `bentuk`, `jam_analog`, `busur`, `tumpukan_kubus` (modul `adegan_awal_*`, tiap sub-adegan validator dan renderer sendiri), `adegan_awal_data`/`adegan_awal_svg`, 29 ikon WebP `aset/ikon-<nama>-v1.webp` terdaftar di `brand.ASET`) membuat sembilan bab bergambar: K1 B4 dan K2 B3 (`kenali_bangun_awal`: bangun datar dan ruang dari gambar), K1 B7 (`ukur_satuan_tak_baku`), K1 B8 dan K2 B8 (`baca_diagram_gambar` P1/P2 skala 1 atau 2, `turus_gambar_awal`), K2 B6 (`baca_jam_awal`: jam analog), K5 B6 (`ukur_sudut_awal`: busur derajat), K5 B8 (`piktogram_lima_awal`: `deret_ikon` diperluas sampai 5 baris dan `satuan_ikon` 1/2/5/10/20), K6 B3 (`tampak_kubus_awal`: tumpukan kubus isometrik); K6 B1 "ada" lewat `pecahan_campur_awal` (teks; kunci bilangan campur "1 1/5" dibandingkan sebagai teks persis oleh `diagnosis.setara`, jadi `diagnosis.py` tidak berubah; `multiple_choice` punya jenis jawaban `pecahan_campur` yang hanya dipakai template ini). Teks tanpa flag selalu bisa dijawab (varian bergambar memuat ciri, letak jarum, angka skala, atau tinggi petak di teks; lembar cetak memakai teks); gambar tidak memakai kelas atau atribut yang menyebut kunci; flag `matematika-awal` di `OSN_VISUAL_KELUARGA` belum menyala dan descriptor baru ini ditolak reader image lama (`cek_bab` lokal).
  Opt-in `Topik.unik_per_lembar` + enumerator domain menjaga soal
  tidak kembar; retry terbatas memilih sisa domain, pengulangan boleh setelah habis.
  Flag mati mempertahankan RNG lama. Campuran tetap P3–P6; lembar 10 soal satu jenis
  berutang variasi. `question_context.topik_dasar` berbagi definisi komposisi di luar
  `LEVEL_TINGKAT` untuk UI/server; radio manual `variasi_dasar` ditampilkan dengan CSS
  `:has()` (fallback tetap terlihat), terpisah dari payload warisan `profil_parameter`.
  Metadata opsional `Topik.keterangan_level` menjelaskan rentang kartu tanpa mengubah generator.
  `question_context.materi_dasar_aktif()` membaca `OSN_MATERI_DASAR` ketat 0/1 (default0; produksi diset 1 lewat `/opt/osn/visual.conf` sejak 4 Nov 2026):
  penawaran UI/AI dan pembuat sesi dikunci, registri/generator serta pembaca histori tetap utuh.
  `choice_pages.cetak_ringkas_aktif()` membaca `OSN_CETAK_RINGKAS` ketat 0/1 (default0, agar hash cetak
  PG identik dengan recovery; produksi 1 sejak 4 Nov 2026): bila 1, lembar cetak PG memakai opsi dua kolom dan jarak kertas.
- Tandai benar dari lembar (5 Nov 2026): `attachments.terapkan` menerima `benar_<ssid>`,
  menyimpan jawaban = kunci dan diagnosis manual benar berpenanda
  `diagnosis.catatan='ditandai_benar'` (`answer_marks.py`). Penanda tidak memakai
  `tinjauan_guru.provenance` (CHECK skema; nilai resmi menunggu migrasi). `reports.diagnosa_murid`
  melepas tanda yang jawabannya bukan kunci lagi lalu menilai ulang. Logika ini sengaja di luar
  berkas kontrak persistensi (nama `*store*`/`*schema*`/`*migrat*`/`database`): mengubah berkas
  itu menggeser sidik kontrak dan memutus pasangan recovery yang di-pin. Parser
  `/lampiran/<id>/terapkan` menerima 400 field dan menjawab 400 untuk kiriman yang ditolak.
- Satu alur sesi (6 Nov 2026): `attachment_http._terapkan` mengalihkan (303) ke `/sesi/<id>` bila sesi
  menjadi selesai; pesan memakai kode allowlist di `session_http`, bukan teks query. Ringkasan wajib di
  tinjauan memakai `review_navigation.wajib_sebelum_konfirmasi` (konservatif: tidak boleh lebih kecil dari
  yang ditolak konfirmasi; diuji dua arah terhadap `konfirmasi_dari_form`); kartu memakai penanda yang sama.
  Kalimat pembuka catatan laporan (`parent_report_guru_pages.KALIMAT_PEMBUKA`, penanda `[isi]`) hanya render;
  guard simpan di `parent_report_http`, bukan `parent_report_store` (berkas kontrak).
- Soal tidak dikerjakan (6 Nov 2026): `attachments.terapkan` menerima `kosong_<ssid>` (ditolak utuh bila
  bertentangan dengan isian, soal sudah berjawaban, atau semua soal kosong) dan menghitung soal itu lengkap
  tanpa menulis `jawaban`. Bawaan dilewati di tinjauan = `answer_marks.tidak_dikerjakan_bawaan` (proyeksi UI
  sesudah draf/tinjauan/snapshot; sesi tanpa jawaban dikecualikan). Bukti memakai `snapshot_outcome.dilewati`
  yang sudah ada; “salah tanpa kode” tidak dipakai karena CHECK snapshot mewajibkan kode (butuh migrasi).
- HP anak (6 Nov 2026): `qr_code.py` encoder QR stdlib (byte, ECC M, versi 1–10, SVG; golden libqrencode per mask).
  `share_http._situs_tautan` memakai Host hanya bila ada di `HOST_TAUTAN` (`jagomat.id`, `uji.jagomat.id`), selain
  itu `brand.URL_SITUS`. `share_links.TTL_DETIK` 12 jam. Form sesi tidak lagi beratribut `data-bagikan-sesi`, jadi
  `SKRIP_BAGIKAN` tidak disisipkan (follow-up: buang). Cabang `fetch` JSON tetap: dipakai verifikasi lingkungan uji.
- `probe_questions.py`: pertanyaan pancingan untuk halaman tinjauan guru saat `diagnosa` tidak
  punya dugaan. Urutan: entri per template di `konten/pancingan/<topik>.json` (3 pertanyaan +
  tindak lanjut, status draf, 106 template termasuk `berhitung-sekolah`; 15 Nov 2026) → topik
  pemilik template → topik sesi → umum.
  Berkas divalidasi gagal-tertutup (berkas rusak dilewati, uji CI memastikan berkas terkirim sah);
  `render()` kosong untuk peran selain guru.
- `teacher_usage.py` (SELECT saja, dari kolom sesi/pengiriman/laporan yang ada; tanpa migrasi)
  → `admin_usage_pages.py` → `admin_usage_http.py` untuk `/admin/pemakaian`. SQL sengaja di modul
  bernama non-`*store*` karena hanya membaca; sidik kontrak persistensi tidak berubah.
- `admin_cek_topik_pages.py` → `admin_cek_topik_http.py` untuk `/admin/cek-topik`: render murni dari
  `cek_gratis_skor.TOPIK_PER_KELAS` dan registri `topics`, tanpa DB.
- `admin_kurikulum_pages.py` → `admin_kurikulum_http.py` untuk `/admin/kurikulum/cp-detail` (Detail CP; baca-saja; render murni):
  `kurikulum_katalog` + `kurikulum_cp` + pemetaan efektif; bar tab tiga butir `admin_kurikulum_tab.py` dibagi dengan cek-topik.
- `kurikulum_kelas.py` (data bab, stdlib) + `kurikulum_kelas_hitung.py` (status/jenis/variasi dari komposisi level,
  variasi di-`lru_cache` per (topik, template, level), palang rilis `template_dibuka` dibaca di luar cache, COUNT `soal`
  lewat `database.buka()` + `query_only`) + `kurikulum_buat_soal.py` → `admin_kurikulum_merdeka_pages.py` /
  `admin_kurikulum_buat_pages.py` → `admin_kurikulum_merdeka_http.py` untuk `/admin/kurikulum` dan `/admin/kurikulum/buat`
  (query ketat, 404 identik non-admin; badan soal memakai `render._badan_soal`, tidak menulis DB).
- `admin_kurikulum_cp_pages.py` → `admin_kurikulum_cp_http.py` (3c): GET `/admin/kurikulum/cp?grup=<topik>/<kode>` (form 12 baris
  tetap `butir_N`/`cocok_N`, riwayat `kurikulum_override.riwayat_cp`), POST `/admin/kurikulum/cp` dan `/cp/kembalikan`. Guard = pola
  sakelar (`h._token_final`: csrf + tinjauan terikat aksi + sandi ulang; grup dan revisi hanya dari tinjauan; `wajib_field`).
  Batas field eksplisit `MAKS_FIELD_CP` (27) lewat `admin_pesanan_aksi.terima_form(maksimum_field=)`; `MAKS_FIELD` global tetap 8.
  `/admin/kurikulum` kini membaca `kurikulum_override.daftar_cp()` (efektif), `ui.halaman()` tanpa argumen = bawaan kode.
- `admin_kurikulum_label_pages.py` → `admin_kurikulum_label_http.py` (3d): GET `/admin/kurikulum/label?topik=<id>` (field tunggal `label`,
  riwayat `riwayat_label`), POST `/admin/kurikulum/label` dan `/label/kembalikan`; guard sama dengan 3c (topik dan revisi hanya dari tinjauan,
  `wajib_field`). Label yang sama persis dengan nama resmi yang dipetakan `topik_awam.dari_nama_lama` ditolak (`topik_awam.bentrok_nama_resmi`).
  Pembaca label dibaca saat request: `topik_awam.nama` (label efektif; `NAMA_AWAM` tetap bawaan kode), `cek_anak_komponen.nama_topik`
  (warna ubin tetap konstanta `WARNA_TOPIK`). `dari_nama_lama` memetakan nama resmi ke label efektif, tetapi label tersimpan (bawaan atau hasil
  ubah) tidak dipetakan ulang, supaya ringkasan cek yang sudah dinilai tidak berubah. Tautan "Ubah label" ada di Detail CP per topik.
- `kurikulum_override.py` (3b peta kurikulum; dipakai admin CP 3c dan label awam 3d): override CP per grup dan label awam di DB terpisah
  `/data/kurikulum.db` (env `KURIKULUM_BERKAS_DB`, skema v1, revisi per kunci + audit). Beda dari `feature_switch`: DB/baris rusak
  **fail ke bawaan kode** (bawaan sah) + log; tulis ke skema asing ditolak. Ikut backup opsional (cek skema di `operational_backup`).
- `admin_kurikulum_cetakan_form.py` + `_pages.py` + `_http.py` (C2): GET `/admin/kurikulum/cetakan` (daftar per bab), `/cetakan/baru`,
  `/cetakan/periksa?id=` (10 contoh dari `cetakan_pola.contoh`, `uji_kelayakan`, `riwayat`); POST `/cetakan/baru|ubah|setujui|nonaktifkan|aktifkan`.
  Guard = pola CP (`h._token_final`; target HANYA dari tinjauan: buat = `target_id` "kelas/bab", lainnya = id + revisi; `wajib_field`; sandi ulang
  di semua aksi), batas field eksplisit `MAKS_FIELD_CETAKAN` (25: 22 isian + csrf/tinjauan/reauth); form field tetap (`nama` = select ya/tidak,
  `var_N_*`, `syarat_N`), `sumber="manual"`. Isi tak sah = render ulang 400 (nilai ketikan di-escape, sandi kosong, tanpa PRG), KonflikRevisi 409,
  DB rusak/baris tak terbaca 503. `kurikulum_kelas_hitung.RingkasanBab.cetakan` dan `kurikulum_buat_soal` membaca HANYA
  `cetakan_store.aktif_untuk_bab` (invarian: draf/nonaktif tak tampil di luar halaman cetakan); variasi cetakan = "banyak" tanpa dijalankan.
- `cetakan_ai.py` + `cetakan_ai_store.py` + `admin_kurikulum_cetakan_ai_{pages,http}.py` (C3 draf AI cetakan): POST `/admin/kurikulum/cetakan/draf-ai`
  (`AKSI_DRAF_AI`; guard sama dengan buat: `terima_form(maksimum_field=3)`, `wajib_field` kosong, target (kelas, bab) HANYA dari tinjauan
  "kelas/bab" revisi 0, sandi ulang). Urutan: kunci `DEEPSEEK_API_KEY` ada (kosong = 503) -> `cetakan_ai_store.reservasi` (kuota 20/hari WIB
  global, `BEGIN IMMEDIATE`; penuh 429, DB kuota rusak 503, keduanya tanpa panggilan AI) -> satu `cetakan_ai.minta_kandidat` -> tiap kandidat:
  kelas/bab DIPAKSA dari tinjauan, `cetakan_pola.validasi` + `uji_kelayakan`, lolos = `buat_draf(sumber="ai")` (selalu draf, tak pernah aktif
  otomatis) -> PRG ke `/cetakan?kelas=&bab=&permintaan=<id>` yang merender ringkasan (N draf + tautan, alasan penolakan, di-escape; hanya bila
  kelas/bab permintaan cocok). Tombol di halaman cetakan bab (dan tautan "Buatkan draf cetakan" di tabel Kurikulum Merdeka untuk bab belum/sebagian)
  hanya bila kunci ada DAN `sisa_hari_ini()` > 0 (DB kuota tak terbaca = `None` = sembunyi, fail-closed); kuota dibaca sekali per render.
  `cetakan_ai` = klien urllib langsung (timeout 30 dtk, balasan maks 8192 byte dibaca `read(BATAS+1)`, 1-3 kandidat, `GalatAI` ramah tanpa kunci/URL/badan;
  badan mengirim `thinking: disabled` karena thinking bawaan DeepSeek menghabiskan `max_tokens` 1500 untuk reasoning sehingga `content` kosong);
  `muatan(kelas, bab)` murni hanya kelas, judul bab, sub-materi, aturan cetakan (dari konstanta `cetakan_pola`), dan satu contoh format.
  **Sengaja TIDAK lewat `llm.py`/`ai_service`/`ai_store` dan tak mengecek `AI_NONAKTIF`**: "Hentikan"/batas fitur di /admin/ai tak mematikan draf cetakan,
  dan panggilannya TIDAK tercatat di ledger /admin/ai (audit-nya `permintaan` di DB kuota). DB kuota terpisah `/data/cetakan_ai.db` (env
  `CETAKAN_AI_BERKAS_DB`, skema v1, tabel `permintaan`: id, kelas, bab, actor_id, dibuat UTC, hari_wib, status berjalan/selesai/gagal, jumlah_draf,
  hasil_json ringkas); ikut backup opsional (cek skema di `operational_backup`). Slot terpakai walau AI gagal.
- `cetakan_pola.py` + `cetakan_store.py` (C1 plan cetakan-ai; stdlib; dipakai halaman admin C2, belum sesi anak): cetakan soal berpola = data JSON; validator AST
  bertipe + evaluator sendiri (tanpa `eval`), bangkitan deterministik, `uji_kelayakan`. DB terpisah `/data/cetakan.db` (env `CETAKAN_BERKAS_DB`; draf/aktif/
  nonaktif, revisi + audit, `setujui` wajib lolos kelayakan dalam transaksi); baca rusak = kosong. Di luar penutupan impor `generator`; ikut backup opsional.
- `admin_sakelar_pages.py` → `admin_sakelar_http.py` untuk `/admin/sakelar`: lima sakelar di
  `feature_switch.py` (DB terpisah, fail-closed, env fallback; `VERSI_SKEMA` tetap 1, `ubah()` memperlebar CHECK nama DB lama dalam satu transaksi sehingga kode lama tetap bisa membaca) + `sakelar_registry.py`; guard aksi sama
  dengan panel rekening (tinjauan bertanda tangan, sandi ulang, konflik revisi, audit). Database sakelar
  rusak = 503 jujur. GET `/admin/sakelar` kini halaman Pengaturan layanan (menggabungkan Operasional:
  `admin_launch_http.halaman_pengaturan` + kartu rekening `admin_rekening_http.bagian_pengaturan`; rombak 23 Nov 2026: `admin_sakelar_pages.bagian`
  mengembalikan `BagianSakelar` (kartu per kelompok dari `sakelar_registry.kelompok`, plus `akibat_mati` untuk konfirmasi), `admin_launch_pages.operasional` menyusun ringkasan,
  kelompok, checklist transfer (`admin_sakelar_pages.checklist_transfer`, bahan: `admin_rekening_http.status_keadaan`, tahap QRIS, sakelar transfer), dan Kesehatan sistem terlipat;
  tindakan terlipat memakai `admin_komponen.lipat_aksi`/`badge_aktif`, tanpa JS baru: konfirmasi lewat `data-konfirmasi` + skrip admin yang sudah ada);
  `/admin?section=operasional` hanya 303 ke sana. Bagian pendaftaran mandiri dirender
  `admin_pages.render_bagian_pendaftaran` lewat `admin_sakelar_http.bagian_pendaftaran` (handler POST
  `admin_http._post_pendaftaran` tidak berubah; `?section=pendaftaran` = 303). "Perlu perhatian" memakai
  `admin_queries.butuh_perhatian` (`student_without_login` netral). Menu: `admin_pages.GRUP_SECTION`/`MENU_INDUK`; tab
  guru di `admin_guru_tab.py`.
- `admin_profil_guru_pages.py` → `admin_profil_guru_http.py` + `profil_guru_settings.py` untuk
  `/admin/profil-guru`; `funnel_http._profil_guru` membaca `tampil=1` dengan cache 30 detik dan
  mengoper kartu ke halaman contoh/paket coba.
- Kontak WhatsApp per akun: `schema_contact.py` (tabel aditif `kontak_akun`, kunci `id_akun`, bukan
  nama login, supaya nama yang dipakai ulang tidak mewarisi kontak) + `kontak_akun.py` (normalisasi
  628…, simpan/ambil/hapus di transaksi pemanggil, `sentuh_aktivitas` maks 1 tulis/hari,
  `sapu_kontak` 365 hari + yatim, menolak daftar akun kosong). SQL-nya di modul non-`*store*`;
  periksa bila ada pemindai kontrak persistensi berbasis nama. Jalur funnel: `funnel_flag.py` (satu-satunya
  pembaca `FUNNEL_AKTIF`, hanya "1" yang hidup) + `registration_contact.py` (field/validasi di
  `/daftar?jalur=cek`, kontak ditulis di transaksi yang sama dengan baris anak di
  `admin_registration`; WA ikut `sidik` hanya jalur ini). `kontak_http.py`/`kontak_pages.py` untuk
  `/akun/kontak` (guru; admin 404). Login mencatat aktivitas fail-open di `auth_http`;
  `family_deletion._ubah_belajar` menghapus kontak keluarga target.
- Pendaftaran guru mandiri (25 Nov 2026, sakelar admin `DAFTAR_GURU`, bawaan mati; env hanya fallback): `guru_daftar_gate.py` (via `feature_switch`) + `guru_daftar_http.py` + `guru_daftar_pages.py` + `admin_antrean_guru.py` (butir antrean, dari receipt tanpa profil); tab admin "Akun guru": `admin_guru_akun.py` (data) + `_pages` + `_http` (section `guru`, aksi lewat /admin/tinjau `dari=guru`), dicabangkan `registration_http` hanya untuk query persis `peran=guru`; akun guru tanpa profil anak lewat `admin_registration.daftar_publik`, laju lima akun per IP per 15 menit, tidak otomatis masuk lembaga. Pilih jadwal mandiri Mini: `jadwal_pilih.py` (bukan berkas `*store*`; meminjam primitif `jadwal_store`), rute `POST /murid/paket/jadwal`.
- Pendaftaran akun anak (F2a, di balik sakelar `DAFTAR_AKUN_ANAK`): `daftar_anak_gate.py` (sakelar + env
  `OSN_LEMBAGA_ANTREAN` dibaca tiap panggilan; `keadaan()` = LAMA/ANAK/BELUM_SIAP fail-closed; env dipilih karena
  `admin_store` bukan key-value dan perlu migrasi), `registration_anak_http.py` + `daftar_anak_pages.py`
  (`registration_http`/`landing.halaman_daftar` hanya bercabang; form lama byte-identik), saga SAMA
  `admin_registration.daftar_dengan_profil(mode_anak=ModeAnak)` (peran murid + `siswa_id`, receipt `child_created`
  = `KODE_HASIL_SAH` bersama `teacher_created`, intent bertanda `pemilik_sidik`, siswa baru milik koordinator via
  `_insert_siswa_baru` + `lembaga_store.nama_bebas`, bukan `tambah_siswa`). Pembaca receipt lain (`admin_backup`,
  `product_analytics_store`, `subscription_service`) menerima kedua kode. Tabel aditif `schema_daftar_anak.py`:
  `persetujuan_daftar_anak` (`daftar_anak_store`) dan `pin_orang_tua` (`pin_orang_tua_store`: simpan/periksa
  waktu-tetap/hapus; dipakai F3). Hook akun guru (kebijakan, analitik KPI, sinkron langganan) tidak dipanggil untuk murid.
- Halaman orang tua di akun murid (F3, di balik sakelar yang sama): `orang_tua_http.py` (GET `/murid/orang-tua`, POST `/pin`, `/pin/atur`,
  `/pin/hapus`; dipanggil `student_http` sebelum `_lolos_sandi`, mati = `False` sehingga jatuh ke perilaku rute tak dikenal),
  Langganan Latihan Harian (F5, di DB belajar, aditif): `schema_harian_langganan.py` (tabel `harian_order/tagihan/bukti/verifikasi/akses`, append-only + trigger: satu order terbuka per anak, akses hanya dengan verifikasi setuju, nominal paket dikunci), `harian_langganan_dasar.py` (paket, kalender WIB), `_store.py` (tagihan, bukti), `_putusan.py` (admin: antrean, setuju/tolak + akses satu transaksi), `_akses.py` (kait `akses_harian._langganan_aktif`), `_ringkas.py`, `_berkas.py` (bukti di subfolder `harian/` supaya sapuan yatim Paket Coba tidak menghapusnya), `harian_bukti_retensi.py` (retensi 30 hari sesudah keputusan: hapus berkas lalu tandai di tabel penanda `harian_bukti_hapus` yang append-only; dipanggil `pesanan_retensi.main` di jalur cron harian yang sama, DB belajar dari `--database-belajar`/env `OSN_BERKAS_DB`/`latihan.db` di samping admin-control.db, dilewati bila tak ada; tanpa sapuan yatim di `harian/`), `_murid_http.py`/`_pages.py` (`/murid/langganan`), `_admin_http.py`/`_admin_pages.py` (`/admin/langganan`). Rute murid di balik sakelar `LATIHAN_HARIAN` (mati = 404 rute tak dikenal); rute admin tidak bergantung sakelar (bukti yang sudah masuk tetap bisa diputuskan); rentang nominal tidak beririsan dengan Paket Coba.
  Paket Belajar 1 Bulan (24 Nov 2026; LIVE sejak 25 Nov 2026 rilis c2d89fe, sakelar `PAKET_BELAJAR` mati; plan lokal `docs/plan/2026-11-24-paket-belajar-bulanan.md`): tabel `kelas_*` ada di **`admin-control.db`** (bukan DB belajar) supaya pemakaian deposit `purna_*` atomik dengan persetujuan; namespace opt-in seperti `purna_*` (absen sah, parsial ditolak, tanpa bump `VERSI_SKEMA`, TIDAK diwire ke `admin_store.siapkan`; dibuka lewat `kelas_store.buka` yang memakai `schema_kelas.validasi`). Modul: `paket_belajar_katalog.py` (katalog + `hitung_rincian` + model bersama; satu-satunya sumber harga), `schema_kelas.py` (DDL, ledger append-only, trigger: satu order terbuka per anak dan paket, satu akun per anak, deposit hanya dari order Peta akun dan anak yang sama, bukti maks 5/dalam jendela/satu berkas satu kali, keputusan atas bukti terbaru, akses hanya dari verifikasi setuju), `kelas_dasar.py` (galat, waktu WIB, validasi), `kelas_status.py`, `kelas_rincian.py` (deposit aktif), `kelas_store.py` (tagihan, bukti, kartu, antrean; `buat_tagihan(..., tolak_paket_lain_terbuka)` atomik di `BEGIN IMMEDIATE`), `kelas_putusan.py` (setuju/tolak; setuju = verifikasi + akses + `purna.catat_pakai_dalam_transaksi` satu transaksi; deposit dicek ulang di dalamnya), `kelas_berkas.py` (subfolder `kelas/`), `paket_belajar_gate.py` (sakelar `PAKET_BELAJAR`, bawaan mati; sakelar ini hanya menutup rute MURID, rute admin `/admin/kelas` tetap terbuka seperti Harian), HTTP `kelas_murid_http.py` (`/murid/paket`, `/buat`, `/bukti`; `akun_id`/`siswa_id` hanya dari sesi) dan `kelas_admin_http.py` (`/admin/kelas`, `/verifikasi`, `/bukti?id=<bilangan ledger>`, `/setujui`, `/tolak`), render murni `kelas_pages.py`/`kelas_admin_pages.py`. `purna.py`: `catat_pakai` dan `catat_pakai_dalam_transaksi` berbagi satu badan (`_catat_pakai`); varian baru wajib sudah dalam transaksi pemanggil. Berkas bernama `schema_*`/`*_store*` MENGGESER sidik kontrak recovery (`PROBE_KONTRAK` di `scripts/deploy.py`): pin recovery sudah disiapkan lokal ke `85bbd52` (kontrak `fec2fd5`, lapisan data kelas_* di atas `6613e5d`; branch `recovery-kelas-paket` wajib dipush sebelum `main`), ditambah probe `PROBE_KELAS_SKEMA` (live `mode=ro`, blok lulus bila tabel belum ada) + blok `PROBE_IMAGE` (migrasi dua kali), probe pasangan `scripts/release_kelas_pair.py` (`kelas_pair_checks` 8), dan opt-in backup `admin_backup_pesanan.deteksi_kelas`/`migrasikan_kelas` + `rehearsal_bundle(target_kelas=...)`. Jadwal/penempatan (LIVE sejak 25 Nov 2026 rilis 5c7849f, perpanjangan + kartu orang tua rilis 0d5d046, recovery 36eb20d kontrak 50a32be; sakelar mati): tabel `jadwal_*` di `admin-control.db` dengan namespace SENDIRI (bukan `kelas_*`) supaya image recovery sekarang tetap dapat membuka DB; modul `schema_jadwal.py` (DDL + trigger kuota/paket/satu-anak/identitas), `jadwal_dasar.py` (validasi, WIB→UTC, 8 pertemuan dua kali seminggu selama empat pekan, selesai dalam masa akses 1 bulan), `jadwal_tautan.py` (validator tautan Zoom/Google Meet untuk kolom `lokasi` Mini: https, host daftar izin, tanpa userinfo/port; dipakai admin dan kartu orang tua), `jadwal_store.py` (kelompok, penempatan Mini/Private, lepas, ubah/batal sesi; batas akhir akses ditegakkan di penempatan dan geser sesi, kelompok selesai/kembar ditolak, pendaftaran Mini ditutup saat `TUTUP_SETELAH_PERTEMUAN_MULAI` (di store, = 2) pertemuan aktif sudah mulai; `_id_sesi_bentrok` hanya-baca menandai sesi aktif guru yang sama yang beririsan sebagai `bentrok` untuk peringatan di render, tanpa menolak apa pun; `lepas_penempatan(..., versi=)` wajib sama dengan `jadwal_penempatan.dibuat`, dibawa tinjauan lepas lewat kunci `target_revisi`, jadi form lama 409), `jadwal_admin_pages.py` + `jadwal_admin_http.py` (blok di `/admin/kelas`, detail `/admin/kelas/kelompok`, aksi tanpa sandi ulang tetapi CSRF+tinjauan bertanda tangan), dan CLI `jadwal_migrasi.py` (idempoten, prasyarat `kelas_*`). Pin recovery jadwal: `37307ed` (branch `recovery-jadwal-3`, kontrak `1bd09a6`, `jadwal_store` tutup pendaftaran/bentrok/versi lepas di atas `36eb20d`; wajib dipush sebelum `main`; `36eb20d` kontrak `50a32be` = pin yang live), dengan `PROBE_JADWAL_SKEMA`, `scripts/release_jadwal_pair.py` (`jadwal_pair_checks` 8), dan opt-in backup `deteksi_jadwal`/`migrasikan_jadwal` + `rehearsal_bundle(target_jadwal=...)`. `blok_penempatan` muncul di detail order yang sudah aktif; Mini wajib kelompok, Private wajib guru+tanggal. Perpanjangan: `tempatkan` memensiunkan penempatan lama anak yang sama (hapus baris `jadwal_penempatan` saja, sesi Private tetap riwayat) bila `MAX(berakhir)` order lama <= sekarang, atau <= `MIN(mulai)` order baru DAN tak ada pertemuan aktif lama yang belum mulai (`_sesi_lama_tersisa`), dalam transaksi yang sama (gagal = rollback); Private menolak order yang sudah bersesi, dan `lepas_penempatan` Private hanya bila tak ada sesi aktif yang sudah mulai. Pembaca murni `jadwal_untuk_murid` / `jadwal_terbaru_murid` (hanya lokasi + sesi; order dari akun dan anak sesi) dipakai kartu "Jadwal pertemuan" di `/murid/paket` (`kelas_murid_http._jadwal_anak`, gagal-diam khusus jadwal; kode siap lokal, belum dirilis, mengubah sidik kontrak recovery). Perpanjangan (kode lokal, baca-saja, tanpa tabel/skema baru dan di luar sidik kontrak): `kelas_masa.py` (`masa_paket_anak`: MAX(`kelas_akses.berakhir`) per akun+anak+paket, status aktif/segera/habis, `HARI_PENGINGAT=3`; paket dengan order terbuka atau yang berakhir lebih awal daripada paket lain anak itu dilewati) dipakai `orang_tua_http._masa_paket` (hanya bila `paket_belajar_gate.aktif()`, galat DB = tanpa banner) dan `kelas_pages.banner_orang_tua`; `kelas_tunggakan.py` (`daftar_tunggakan`, jendela 30-120 hari, tanpa akun pembeli) dibaca `admin_antrean_bayar.kelas_tunggakan` dan masuk `admin_antrean.kumpulkan` (antrean diurutkan per tingkat mendesak/penting/tinjau). Waitlist, absensi, jadwal di sisi anak, dan retensi bukti `kelas/` masih BELUM ada. `subscription_packages.py` (paket "jago") katalog lain yang HIDUP untuk langganan/kuota asisten, bukan bagian fitur ini.
- Harga admin Private/Mini (25 Nov 2026, kode lokal, belum rilis; irisan 1–3): namespace opt-in `harga_*` di `admin-control.db` (`schema_harga.py`: `harga_produk` nilai aktif, `harga_riwayat` append-only; absen sah, parsial/berbeda ditolak, tanpa bump `user_version`, TIDAK diwire ke `admin_store.siapkan`; dipasang lewat `harga_migrasi.py`). `harga.py` = pembaca/penulis (`harga_aktif`/`harga_semua`: tabel belum terpasang atau baris tak ada = nilai awal `HARGA_AWAL`, skema rusak = `ValueError`; `ubah_harga` satu transaksi, cek konflik harga-lama, validasi ulang di dalam transaksi), `harga_aturan.py` (konstanta: rentang Rp10.000–9.000.000, kelipatan Rp1.000, `nominal_proporsional`), `harga_validasi.py` (rentang, kelipatan, Peta hanya-baca, nominal positif setelah deposit, pita nominal lintas produk > 999). Private disimpan per BULAN (Rp640.000), Mini Rp300.000; Peta dan Latihan Harian hanya dibaca. `kelas_rincian.rincian_untuk` memakai harga aktif untuk tagihan BARU (tagihan lama tetap `harga_dasar` tersimpan; skema harga rusak = tagihan baru gagal tertutup); `kartu_paket` dan contoh publik Peta (`funnel_http._harga_mini_aktif`, fail-soft ke katalog) memakai harga aktif. Layar admin `/admin/harga` (`admin_harga_http.py`, `admin_harga_pages.py`, `admin_harga_baca.py`; pola tinjauan bertanda tangan + sandi ulang + CSRF + PRG, produk hanya dari tinjauan, non-pengelola 404 identik; tautan di Pengaturan layanan, grup Penjualan). `schema_harga.py` MENGGESER sidik kontrak recovery (stem `schema`): rilis butuh pin recovery baru dan `PROBE_HARGA_SKEMA`; `kelas_store.py` juga berubah. Fase 2/3 (Peta, Latihan Harian) dan pilih kelompok/tagihan proporsional belum dibangun (plan `docs/plan/2026-11-25-prorata-mini-dan-harga-admin.md` §11).
  `orang_tua_data.py` (hasil cek via `cek_gratis.hasil_siswa`, `parent_report_store.terbit_terbaru`, status order lewat koneksi
  read-only ledger), `orang_tua_pages.py` + `orang_tua_style.py` (render; pakai ulang blok `cek_pages`, `parent_report_page.isi_laporan(
  tanpa_batas_berlaku=True)`, `pesanan_pages.COPY_STATUS`; satu-satunya skrip = `SKRIP_MATA_SANDI`, hash CSP lewat opsi `skrip_sandi` pada
  `web._kirim_privat`; isi halaman memakai `playful_components`, urutan blok dan PIN `<details>` ada di `halaman_isi`). Status tirai di `tirai_orang_tua.py`: peta memori proses (Lock) berkunci (sha256 token cookie, id_akun, siswa_id),
  30 menit, dibersihkan di `/keluar`; bukan cookie dan bukan `sessions.py` (berkas kontrak rilis). Restart menutup semua tirai (fail-closed).
  Laju PIN: `laju_masuk` ruang `pin-orang-tua` per (anak, IP), dicek sebelum PBKDF2. Basic auth tidak pernah membuka tirai. Nama modul
  sengaja tanpa `store`/`schema` (sidik jari kontrak), kecuali `parent_report_store` yang bertambah `terbit_terbaru` (ikut pin recovery).
- **Halaman langganan Latihan Harian** (`harian_langganan_pages` + `harian_langganan_style`, CSS lewat parameter opsional `css_tambahan` pada `pesanan_murid_pages.halaman_murid`; halaman Peta pesanan tetap byte-identik): render `/murid/langganan` dan kartu langganan di halaman Ayah/Bunda (judul kartu level 2). Hemat/setara Tahunan dihitung dari `harian_langganan_dasar.PAKET`; `Ringkasan.alasan_tolak` hanya terisi saat tagihan ditolak. Escape lokal berkutip (`quote=True`).
- Cek di sesi anak (F2b): `cek_murid.py` (domain: `gerbang_aktif` = sakelar anak DAN funnel karena `share_http._sesi_cek` hanya
  melayani layar cek anak saat funnel hidup; `mulai` = id_akun murid + persetujuan sah sebelum `cek_gratis.mulai`; `status`/
  `kartu_html`/`untuk_beranda`) dan `cek_murid_http.py` (pola `contest_http`: gerbang mati = False; satu `BEGIN IMMEDIATE`
  `siswa_dari_akun` -> `mulai` -> `share_links.buat` -> 303 `/mulai/<token>`, sesi login tidak dihapus, tanpa `?di=hp-ini`).
  Memakai ulang `cek_anak_http`; satu-satunya sentuhan berkas bersama: cabang di rantai POST `web.py`, entri `AKSES_RUTE_POST`,
  dua kwarg `halaman_daftar_sesi_baru` (kartu + sesi cek disembunyikan) dari `student_http`.
  waktu-tetap/hapus; dipakai F3). Pesanan dari akun anak (F2c): `pesanan_murid_http.py` (GET/POST `/murid/pesanan...`,
  dipanggil di `web.py` setelah `contest_http` sebelum `student_http`; sakelar mati/bukan murid tertaut = `False`) hanya penentu
  pembeli + alamat; mesin SAMA lewat `pesanan_http.layani_get/layani_post` dan `pesanan_transfer_http.layani_post` (alamat murid
  dipetakan ke alamat kanonik guru via `pesanan_permukaan.MURID_KE_KANONIK`). `pesanan_permukaan.py` = peta rute beku per peran
  (`rute_untuk(principal)`; renderer `pesanan_pages`/`pesanan_transfer_pages` memakainya, default guru byte-identik),
  `pesanan_murid_pages.py` = shell murid + kartu "Pesan"; `pesanan_alur._anak_pembeli` memilih anak dari peran principal (murid:
  `students.siswa_dari_akun`). Hook akun guru (kebijakan, analitik KPI, sinkron langganan) tidak dipanggil untuk murid.
- Funnel Cek Kemampuan Fase 1 (hanya permukaan publik): `funnel_http.py` (GET `/cek-kemampuan`, `/paket-coba`,
  sebelum `_lolos_sandi`, tanpa POST; `tangani_beranda` dipanggil `public_http.py` untuk `/` anonim, False saat
  sakelar mati agar landing lama jadi cadangan) + `funnel_pages.py` (markup, copy §7 plan) + `funnel_style.py`
  (`GAYA_FUNNEL`, hanya ikut `gaya_stitch()` saat `FUNNEL_AKTIF=1` agar byte halaman lain tak berubah).
  Sakelar mati = halaman "belum dibuka" 200 tanpa CTA; hidup = satu CTA ke `/daftar?jalur=cek`, tautan nav
  di landing. Landing playful: `funnel_landing_pages.py` + `funnel_landing_style.py` + `funnel_landing_browser.py`.
  Laporan Peta Kemampuan: kontrak data `peta_data.py` (`periksa_konsisten`), contoh `peta_contoh_data.py`, posisi
  murni `peta_posisi.py`, renderer `peta_laporan.py` (+ `peta_ringkasan/materi/pola/misi/donat/ikon/komponen/teks`),
  lembar `peta_lembar.py`, CSS `peta_style*.py`, skrip `peta_browser.py`. Semua respons funnel memakai
  `funnel_http._kirim_funnel` dengan CSP berhash dari skrip inline aktual (`web.csp_tautan`).
- Funnel Fase 2 (cek gratis): `schema_cek.py` (tabel aditif `cek_gratis`, UNIQUE per anak, kunci `id_akun`, FK ke siswa
  ON DELETE CASCADE) + `cek_gratis.py` (`mulai` idempoten dengan persetujuan eksplisit, `selesaikan_jika_siap`,
  `baca_hasil`, `hapus_cek_keluarga`), `cek_gratis_skor.py` (fungsi murni skor/kategori/ringkasan, kelas→`P{kelas}`),
  `topik_awam.py` (label topik pendek untuk anak/orang tua; nama resmi tetap di lembar/penilaian guru, nama lama
  tersimpan dipetakan saat render; diturunkan dari `kurikulum_katalog.py`, katalog data beku peta kurikulum yang juga
  menjadi sumber `mastery_catalog.KELOMPOK` dan topik cek per kelas, lihat `docs/kurikulum-katalog.md`),
  `cek_gratis_sapu.py` (retensi 30/7 hari, guard daftar akun kosong, foreign_keys wajib aktif; dijalankan
  harian oleh `cek_retensi.py` lewat cron host `osn-cek-retensi`). `cek_http.py` +
  `cek_pages.py`: rute guru di belakang `_lolos_sandi` dan `FUNNEL_AKTIF` (token HMAC per aksi, pembatas laju 10/IP/hari
  in-memory, admin 404). Sesi cek = sesi gabungan 3 topik yang mengikuti kelas (`cek_gratis_skor.TOPIK_PER_KELAS`, kelas 3–6; `TOPIK_LAMA`
  hanya untuk menilai sesi lama) atau `bilangan-dasar` (kelas 1–2, butuh flag materi dasar), PG, tanpa bukti siklus. `family_deletion` ikut menghapus baris cek. Perubahan skema menggeser fingerprint kontrak
  rilis: pin recovery diganti pada langkah rilis (tes `test_kontrak_candidate_identik_dengan_recovery_pinned` merah sampai itu).
  Alur UI (19 Nov 2026): sisi anak `cek_anak_http.py` (dispatch dari `share_http` hanya bila funnel hidup dan sesi ada di
  `cek_gratis`; GET berquery `soal/jeda/peta/keluar`, POST `mulai/simpan/keluar/kumpul` + PRG, daftar putih field, revisi
  wajib) + `cek_anak_pages.py`/`cek_anak_komponen.py`/`cek_anak_style.py` (CSS hanya di halaman ini); finalisasi tautan
  bersama di `share_finalisasi.py`. Sisi orang tua: `cek_pages_mulai.py` (siap mulai + QR), `cek_status.py` (status
  belum/berjalan/selesai, hitung terjawab), `daftar_cek_pages.py` (form daftar jalur cek, kelas wajib),
  `funnel_style_alur.py` (ikut `GAYA_FUNNEL`); allow-list `lanjut` cek di `auth_http.tujuan_lanjut`.
  Sakelar `FUNNEL_AKTIF` jangan dinyalakan sebelum keputusan copy refund/retensi otomatis dan pin recovery.
- Funnel Fase 3 (pesanan Paket Coba): `schema_pesanan.py` (tabel aditif `pesanan_order/jendela/pengamatan/receipt/yatim/refund`,
  append-only, DB admin) + domain `pesanan.py` fasad atas `pesanan_dasar/order/status/jendela/provider/callback/admin`
  (ledger, receipt dari hasil provider saja, jendela QR, yatim, refund manual). Transport: `pesanan_midtrans.py` (adapter tipis ke
  kontrak Midtrans; order `ord_` dibedakan dari invoice langganan di callback). HTTP pelanggan: `pesanan_http.py` (+`pesanan_pages.py`,
  `pesanan_alur.py`; guru saja, token HMAC `pesanan-form-v1`, laju per akun+IP, gerbang `pesanan.baca_gerbang` fail-closed,
  hasil cek dibaca per anak lewat `cek_gratis.hasil_siswa`). Admin: `admin_pesanan_http.py`/`admin_pesanan_pages.py` di
  `/admin/pesanan` (daftar tanpa form/kolom sandi, chip saringan `?status=menunggu|belum_bayar|dibayar|ditolak` dari
  `pesanan_admin.daftar_tersaring`; satu tautan per baris: Periksa bukti atau Detail; kolom Order memakai referensi
  pendek `#xxxxxxxx` — id penuh hanya di `title` dan halaman Detail lewat `admin_labels.referensi_pendek`/`referensi` —
  dan kolom Nominal memakai tagihan transfer, atau `pesanan_admin` item `rupiah` bila order lewat penyedia) dan Detail order `/admin/pesanan/order?id=`
  (`admin_pesanan_detail_pages.py` + `pesanan_admin_order.py`, admin saja, 404 identik bila tak sah): periksa status dan catat uang
  kembali (pengecualian) ada di sini sebagai `<details>`, token final admin (CSRF + tinjauan + sandi ulang), PRG ke detail; tidak
  menulis jurnal `operasi_admin`, jejak refund = baris `pesanan_refund`/`transfer_refund`). Server menegakkan sendiri: refund hanya untuk status
  `pesanan_dasar.STATUS_BISA_REFUND` (satu sumber dengan tombol UI) dan satu catatan per order di KEDUA tabel refund
  (`pesanan_refund_aturan.py`); sandi ulang aksi berisiko dibatasi 5 gagal/15 menit per akun admin (`admin_http._reauth` memakai
  `laju_masuk` pada ruang kunci `reauth`). Panggilan jaringan tidak pernah di dalam
  transaksi tulis. Kontrak rilis bergeser seperti Fase 2.
- Transfer rekening (jalur utama pembayaran, verifikasi manual admin; tahap 1 = skema + logika inti; tahap 2 = alur guru di bawah; tahap 3 = admin, retensi, jendela ulang):
  `schema_transfer.py` (namespace `transfer_*`, sengaja BUKAN `pesanan_*` agar `schema_pesanan.validasi` dan rollback image lama utuh;
  tagihan per jendela bayar, bukti, penanda hapus, verifikasi, `transfer_lunas`, `transfer_refund`; append-only) + `pesanan_transfer.py`
  (tagihan nominal unik 49.000+kode 1..999 dengan kode lunas ditahan 30 hari, bukti, setujui/tolak, retensi bukti 30 hari; satu akun
  maksimal satu order `menunggu_verifikasi`; order yang sudah punya receipt Midtrans tidak ditagih transfer; receipt lunas + jejak transfer
  aktif = `perlu_diperiksa` "dua jalur") + `pesanan_transfer_baca.py` (fakta untuk status
  turunan, aman pada DB tanpa `transfer_*`). Status baru `menunggu_verifikasi` (tidak kedaluwarsa) dan `ditolak`. Rekening tujuan:
  `pesanan_rekening.py` (`rekening_*`, pola `support_settings`, tanpa seed; admin wajib mengisi). Migrasi opt-in eksplisit
  (`schema_pesanan.migrasikan`, `schema_transfer.migrasikan`, `pesanan_rekening.migrasikan`); QRIS Midtrans tetap ada, nonaktif.
  Alur guru (tahap 2): gerbang SENDIRI `pesanan_transfer_gerbang.py` (env `PESANAN_TRANSFER_AKTIF` tepat "1" + `FUNNEL_AKTIF` + runtime
  produksi terpasang + rekening terisi; tidak membaca sakelar/tahap Midtrans; bawaan tutup). `/pesanan` menampilkan kartu transfer
  (`pesanan_transfer_pages.py`/`pesanan_transfer_tampil.py`) lalu QRIS sebagai pilihan kedua bila gerbang Midtrans juga terbuka; POST
  `/pesanan/tagihan` dan `/pesanan/bukti` (+ `/paket-coba/pesan` saat hanya transfer terbuka, tanpa panggilan provider) di
  `pesanan_transfer_http.py`. Unggah multipart sempit (`bukti_multipart.py`), tipe dari magic bytes, berkas di folder khusus
  (`bukti_berkas.py`, env `OSN_DIREKTORI_BUKTI`, bawaan `bukti-transfer` di samping DB admin, 0700/0600, nama acak 32 hex, tidak
  pernah disajikan rute publik/murid, sengaja TIDAK ikut backup admin: keputusan Pemilik, bukti sementara 30 hari).
  Admin (tahap 3; di bawah gerbang admin `/admin/pesanan`, tidak bergantung gerbang transfer): kolom nominal persis + bukti dan tab
  "Menunggu verifikasi" (`admin_pesanan_pages/http`, `pesanan_admin_transfer.py`); detail `/admin/pesanan/verifikasi`, pratinjau
  `/admin/pesanan/bukti?id=` (tipe dari ledger, `nosniff`, `no-store`, CSP `default-src 'none'; sandbox`, nama unduhan generik) dan aksi
  `setujui`/`tolak` (`admin_verifikasi_pages/http`; `_token_final`, `admin_id` dari sesi, keputusan hanya atas bukti terbaru yang dilihat
  admin; setelah keputusan, admin dialihkan ke transfer menunggu tertua berikutnya, atau ke daftar menunggu bila habis); `/admin/pesanan/rekening` (`admin_rekening_pages/http`; nomor ter-mask, revisi+sidik di tinjauan = optimistic concurrency);
  pola bersama `admin_pesanan_aksi.py`. Guru: `POST /pesanan/tagihan/ulang` (`pesanan_transfer_ulang.py`) membuka jendela bayar baru
  (maks 5, tagihan + kode unik baru) hanya bila waktu habis tanpa bukti dan Midtrans tertutup. Operator (tidak dijadwalkan aplikasi):
  `pesanan_retensi.py` (juga menyapu bukti langganan Latihan Harian lewat `harian_bukti_retensi.py`; hapus berkas lalu tandai, bukti 30 hari sesudah keputusan, sisa `.tmp-*` > 1 jam, berkas yatim tak dirujuk
  ledger > 24 jam; bukti belum diputuskan tidak dihapus karena trigger skema, admin ditandai "Menunggu > 72 jam") dan `pesanan_transfer_migrasi.py`.
- Voucher/deposit purna (V1b skema + V2 domain + V3 permukaan admin + V4a permukaan pembeli; 24 Nov 2026: Rp49.000 = deposit yang memotong tagihan bulan pertama kelas bersama Guru, tanpa pilihan terlambat/uang kembali otomatis): `schema_purna.py` (namespace `purna_*`, sengaja BUKAN `pesanan_*`/`transfer_*` agar validasi dan rollback image lama utuh; `purna_voucher_pakai` (deposit dipakai), `purna_laporan_terbit`; append-only; trigger hanya untuk order lunas, tolak bila sudah direfund, terbit tidak boleh lebih awal dari waktu lunas; migrasi opt-in `schema_purna.migrasikan`, probe image memasangnya setelah transfer). `purna.py` = domain murni (voucher, kedaluwarsa 90 hari, janji terbit SLA beku 48 jam per waktu lunas, `JAM_TOLERANSI_TERLAMBAT = 0` sehingga terlambat segera setelah lewat 48 jam, `catat_pakai`/`catat_terbit`; semua turunan dari kedua ledger lunas/refund, netral bila `purna_*` belum terpasang). Voucher `ditahan` (urutan status: batal > dipakai > ditahan > kedaluwarsa > aktif): order lunas, belum direfund, tetapi status turunan bukan `sudah_dibayar` (praktis `perlu_diperiksa`: dua jalur bayar atau observasi refund/chargeback penyedia) tidak bisa dipakai atau diterbitkan laporannya, sedangkan refund tetap boleh dicatat, dan voucher tidak bisa dipakai pada keadaan itu. Guard refund: `pesanan_refund_aturan.periksa_layak_refund` menolak refund bila `purna.voucher_dipakai` (kedua jalur refund); skema tidak bisa menegakkannya karena tabel refund milik namespace lain. V3 (admin): satu rute POST `/admin/pesanan/voucher` (aksi `catat_voucher_pakai`, form hanya `catatan_kode` kelas/lainnya, `operasi_id` `vch_`+sha256 per order) di `admin_pesanan_http.py` (rute `/admin/pesanan/terbit` dihapus di D1-2: 404 identik rute tak dikenal) (pola refund: tinjauan per aksi, CSRF, sandi ulang, PRG, 404 identik, `PesananKonflik` = 409, skema belum terpasang = 409); `pesanan_admin_order.purna_ringkas` = whitelist `purna` pada detail order (12 kunci termasuk `ditahan`; tanpa PII, netral bila belum terpasang); kartu "Voucher dan laporan" di Detail order dan kolom Laporan di daftar; `admin_pesanan_pages.aksi_tersedia` = gerbang tunggal form dan token (form refund disembunyikan setelah voucher dipakai, penegakan tetap di domain). V4a (pembeli, hanya murid): kartu "Deposit dan laporan" di `pesanan_pages.halaman_status` (render di `pesanan_voucher_pages.kartu_voucher(k)`, data dari `pesanan_voucher_baca.keadaan_kartu`: hanya status `sudah_dibayar` + lunas + purna terpasang, selain itu halaman lama; guru lama `/pesanan` tanpa kartu): baris "Deposit Rp49.000" (nominal `pesanan_dasar.RUPIAH_PAKET`), "Memotong tagihan bulan pertama kelas bersama Guru bila Anda mendaftar.", masa berlaku, status deposit (aktif/terpakai/kedaluwarsa/ditahan/batal), janji terbit laporan dan kalimat maaf + arahkan WhatsApp bila `terlambat`; tanpa kode voucher (kode internal tetap di domain/admin), tanpa tombol, tanpa kontak/order_id/operasi_id; satu baris janji terbit serta tautan "Lihat deposit & rincian pesanan" ke `/murid/pesanan` di `orang_tua_pages._blok_pesanan` (data `orang_tua_data.purna`), serta teks status terbit bila laporan sudah terbit. Rute `/murid/pesanan/pilih`, `pesanan_pilih_http`, `purna.catat_pilihan`, tabel `purna_pilihan_terlambat`, dan field `KeadaanPurna.pilihan`/`bisa_pilih` DIHAPUS. Pencatatan terbit dilakukan jalur Guru (`peta_laporan_guru_http` memanggil `catat_terbit`; aksi admin terbit dihapus 24 Nov 2026). `/contoh-peta-kemampuan` (`funnel_contoh.py`) memakai `peta_laporan_ortu_pages.blok_peta` dengan `CONTOH_PETA_V1` sintetis + CSS `GAYA_CERIA + GAYA_ORTU` via `css_tambahan` di `_halaman_publik_stitch` (tanpa tab Pola kesalahan / peringkat / lencana / JS tambahan). Penyaring catatan Guru (`peta_laporan_store`) memisahkan pemisah telepon umum (`_SEP_TELEPON` tanpa `,`, `/`, `:`) dari `_POLA_TELEPON_ID_LONGGAR` (`08`/`628`/`+628`) agar deret angka/pecahan/tanggal+jam matematika tidak tertolak.
- Data cek untuk laporan (irisan D1, admin saja): `cek_ringkasan_admin.py` = pembaca MURNI SELECT `ringkasan_untuk_order(kon, siswa_id, cek_id, id_akun, sekarang)` -> dict allowlist 11 kunci (status, kelas, skor, kategori, jumlah_soal, selesai_pada, ringkasan_kuat/perlu, per_materi benar/total per topik awam, bahan ada|dihapus|belum_dinilai, hari_tersisa) atau None; baris `cek_gratis` dicocokkan lewat TIGA kunci (id cek, siswa, akun) dari `pesanan_order` (`pesanan_admin_order.kunci_cek`), tanpa nama anak/kontak/soal/jawaban/kunci/kode diagnosis, tidak memanggil `diagnosa_murid` (jawaban tanpa diagnosis = `belum_dinilai`, tidak ditebak). Retensi memakai `RETENSI_SELESAI_HARI` dan jam yang sama dengan `cek_gratis_sapu` (floor, tidak negatif). `admin_pesanan_http._dengan_cek` menambah kunci `cek` ke detail hanya untuk status `sudah_dibayar` (`kartu_cek_berlaku`), membaca DB belajar lewat `database.buka()` + `PRAGMA query_only`; galat baca = kartu "Data cek tidak terbaca" (log hanya nama tipe). Kartu di `admin_pesanan_cek_pages.py` (setelah kartu Voucher dan laporan; baca-saja, tanpa form/JS). Bukan laporan orang tua dan bukan tampilan Guru.
- Lembaga les: `schema_lembaga.py` (tabel aditif `lembaga`, `anggota_lembaga`, `pindah_siswa`
  append-only lewat trigger) + `lembaga_store.py` (semua SQL; `pindahkan` mengecek ulang semua
  predikat dalam `BEGIN IMMEDIATE`) → `lembaga_pages.py`/`lembaga_http.py` (`/lembaga`) dan
  `admin_lembaga_*` (`/admin/lembaga`). Kemampuan pemilik di DB, bukan nilai `peran`, agar format
  `sandi.json` tetap dan recovery lama bisa login. `siswa_milik`/`sesi_milik` tidak dilonggarkan.
  Penghapusan keluarga melepas keanggotaan/membubarkan lembaga dan memseudonimkan jejak pindah.
  Tabel baru menggeser sidik kontrak persistensi, jadi recovery dipatok ke baseline
  `cb3c5f5` + schema/store lembaga (pola baseline G3).
- Teks yang dibaca guru mengikuti [`docs/glosarium-guru.md`](glosarium-guru.md): kalimat pendek,
  istilah internal tidak tampil; palang `test_bahasa_guru_tinjauan.py` memeriksa halaman tinjauan.
- Stdlib runtime; dev dependency hanya pytest/pytest-xdist. Python lokal3.9.6 dan
  CI/container3.12. Nama modul Inggris; fungsi/docstring/UI/commit Bahasa Indonesia.
- JS terbatas per kasus (revisi 10 Nov 2026; sebelumnya Zero-JS default). Enhancement
  yang disetujui berhash CSP dan fallback native; validasi server tetap otoritatif.
  Tidak ada izin JS/dependency umum dari pola ini.
  `offline_browser.py` hanya mendengar event `offline`/`online` dan mengganti teks
  banner di halaman terbuka; tanpa network/storage/autosave; hash diizinkan di
  respons privat.
  Daftar pengecualian/perilaku lengkap di [arsitektur](architecture-reference.md#konvensi-dan-keputusan-penting).
  `web.Penangan` menetapkan batas waktu socket dan membaca body POST berbatas
  ketat (menolak `Content-Length` negatif/ganda/raksasa dan `Transfer-Encoding`);
  POST permukaan guru/admin/murid menolak lintas situs lewat `admin_security._asal_sama`,
  sementara form publik tetap dilayani. Halaman kredensial (`/masuk`, `/daftar`)
  mengirim CSP berhash sendiri; semua respons mendapat `nosniff`/`X-Frame-Options`
  default. Pembatas laju memakai IP klien sadar proxy (`sessions.ip_klien`,
  entri kanan `X-Forwarded-For` hanya bila peer loopback/privat).
  `scripts/check_repo.py` juga menolak media/spreadsheet/arsip di luar folder aset
  resmi, bukan hanya ekstensi basis data.
- Token visual di `design_tokens.py`; peran semantik per permukaan dan pasangan kontras
  di `design_roles.py` (rujukan + guard test, bukan import runtime); kontrak di
  [design system](design-system.md). Admin berbagi token terang/skala/brand dan acuan
  komponen (tombol sekunder, pil, tab, tautan kembali, header) dengan keluarga;
  `ADMIN_*` hanya adapter tema, sidebar/tabel tetap layout admin. Empat tab
  profil dan laporan lama berbagi shell/lebar `ANAK_*`. CSS rincian legacy hanya dimuat
  pada laporan, sebelum override profil; [audit UI](ui-consistency-audit.md) dan
  [audit admin](admin-ui-audit.md) (fokus, kontrol, state dan tema/cetak).
- Font merek same-origin (`font_lokal`, `/aset/font-*-v1.ttf`) di halaman guru dan semua halaman
  anak, termasuk `/masuk` dan Latihan Lomba; halaman anak tidak memanggil host pihak ketiga
  (ikon SVG lokal, bukan Material Symbols). Halaman publik (landing, daftar, Pusat Cek anak,
  riset), halaman pesan, dan foto lembar juga font lokal; host Google tinggal untuk Material
  Symbols di halaman guru nonprivat. CSP `csp_tautan`/kredensial membuka host Google hanya bila
  isi halaman memuatnya (`web.izin_gaya_font`). Halaman pesan umum memakai lockup `st-topbar` guru. Shell anak `murid_shell` (satu topbar, kolom
  `LEBAR_KONTEN`, keputusan 22 Nov 2026); CSS lembar/hasil murid tambahan di
  `murid_lembar_style`. Aksi utama anak (termasuk Lomba `body.lomba`) koral, guru teal.
- `session_prep.py` membungkus `learning_cycle_ui.kartu_rencana` menjadi lembar cetak
  persiapan (form dibuang, playbook `open`), dirutekan `teacher_http.tangani_persiapan_get`
  setelah `_lolos_sandi` dan sebelum rute profil; tanpa logika rencana sendiri atau tulis DB.
- Laporan orang tua (G3, live sejak 5 Nov 2026, `efb9a03`): `parent_report_store.py` (dua tabel `laporan_ortu`/`tautan_laporan`
  dari `schema_parent_report.py`, token SHA-256 di `parent_report_links.py`), `parent_report_snapshot.py`
  (allowlist topik/tahap/langkah, hanya baca), `parent_report_page.py` (renderer murni: hanya stdlib +
  token desain), `parent_report_http.py` (`/laporan-ortu/<token>` sebelum login, 404 identik, `_kirim_tautan`
  dengan `csp` sempit; rute guru `/anak/<id>/laporan-ortu...` setelah `_lolos_sandi`, sebelum profil) dan
  `parent_report_guru_pages.py`. Hanya menulis dua tabel sendiri; dijaga M1 authorizer SQLite, M2 allowlist,
  M3 teks terlarang, M4 tanpa tulis bukti (`test_laporan_ortu_field_guard.py`).
- Laporan Peta Kemampuan untuk orang tua ditulis Guru (D1-1 fondasi data, D1-2 halaman Guru; belum dirilis; plan lokal `docs/plan/2026-11-24-d1-laporan-guru.md`):
  `schema_peta_laporan.py` (tabel aditif `peta_laporan` di DB belajar, satu baris per anak, FK `siswa` CASCADE, tanpa FK ke
  `sesi`/`cek_gratis`; trigger: terbit tak bisa di-UPDATE, `isi`/`siswa_id`/`guru`/`dibuat` tak berubah, terbit butuh catatan,
  baris baru wajib draf; sengaja TANPA trigger DELETE agar cascade dan penghapusan keluarga tetap jalan),
  `peta_laporan_store.py` (semua SQL: draf, catatan, terbit, hapus draf, `terbit_terakhir` tanpa akun Guru; transaksi pemanggil, waktu
  disuntik; `periksa_catatan` = satu-satunya aturan catatan Guru: tanpa kontak/tautan/istilah internal, dipakai simpan, terbit, dan form Guru) dan `peta_laporan_snapshot.py` (pembangun murni dari `cek_ringkasan_admin.ringkasan_untuk_order` hanya bila bahan `ada`,
  plus `periksa_isi` yang dipakai store saat menulis dan membaca). Snapshot dibekukan saat draf dibuat karena data per materi hilang
  oleh retensi 30 hari. Siswa hanya dianonimkan saat hapus keluarga, jadi `family_deletion._hapus_peta_laporan` menghapusnya eksplisit
  (draf dan terbit), dan `family_deletion._hapus_laporan_ortu` menghapus `tautan_laporan` lalu `laporan_ortu` anak target (tanpa ini tautan lama tetap membuka laporan; kini 404 identik).
  Terbit butuh catatan efektif >= 10 karakter (`MIN_CATATAN_TERBIT`, huruf/angka/tanda baca; karakter tak terlihat dan spasi Unicode tidak dihitung); draf boleh catatan kosong.
  Penyaring kontak/istilah di `periksa_catatan` (pemisah digit, homoglyph, domain, istilah berpemisah) adalah pengingat, bukan batas keamanan. Probe deploy `PROBE_PETA_LAPORAN_SKEMA`: tabel belum ada lulus (preflight sebelum migrasi), sudah ada wajib persis DDL source.
  D1-2 (sisi Guru): `peta_laporan_guru_http.py` (GET `/anak/<id>/peta`, POST `/buat` `/catatan` `/terbitkan` `/hapus`; pola `parent_report_http`, dipasang di `web.py` setelah `parent_report_http.tangani_guru_*` dan sebelum penangkap `/anak/`) dan `peta_laporan_guru_pages.py` (renderer murni zero-JS).
  Order dicari lewat `pesanan_admin_order.order_peta_untuk_siswa(kon_admin, siswa_id, sekarang)` (5 kunci: order_id, siswa_id, cek_id, akun_id, status) HANYA sesudah `_bisa_lihat_siswa`; kunci cek/akun dibaca server dari ledger, bukan URL/form. Anak bukan milik Guru, tak ada, atau tanpa order = 404 identik tanpa efek; order bukan `sudah_dibayar` = halaman info (GET) / 409 (POST) tanpa data cek; ledger tak terbaca = 503 "belum bisa dibuka". Hanya peran guru menulis (admin GET baca-saja, POST 403). Isi draf selalu dibangun server (`cek_ringkasan_admin` -> `peta_laporan_snapshot.bangun`); form tepat: buat kosong, catatan `{catatan}` (maks 2000), terbitkan/hapus `{konfirmasi}`="1" (kotak centang ditegakkan server). Tombol "Buat draf" hanya bila bahan `ada`. Kartu kecil "Peta Kemampuan" di tab Perkembangan `/anak/<id>` (`teacher_workspace`, lewat `kartu_untuk_anak`; baca-saja, tanpa kartu bila order belum lunas atau ledger tak terbaca).
  Terbit: commit DB belajar dulu (ledger admin dan DB belajar tak dipegang bersamaan), lalu `purna.catat_terbit` dengan pelaku = akun Guru dan waktu = waktu terbit laporan; kegagalan pencatatan TIDAK membatalkan laporan (log hanya nama tipe galat) dan diulang idempoten tiap Guru (bukan admin) membuka halaman Peta. Aksi admin `/admin/pesanan/terbit` (RUTE/AKSI/`_terbit`/form/copy hasil) DIHAPUS; kartu admin tetap menampilkan status laporan (terbit/terlambat) dan data cek.
  D1-3 (sisi orang tua): `peta_laporan_ortu_pages.py` (renderer murni: skor/kategori, benar/total per materi dengan `<meter>` native, materi yang perlu dilatih dulu, catatan Guru ter-escape, label "Ditinjau Guru Jagomat" tanpa nama; tanpa JS, tanpa style inline) dan `orang_tua_data.peta_terbit` (isi hanya bila laporan TERBIT dan status pesanan `sudah_dibayar`; galat baca = blok tersembunyi, halaman tetap 200). Blok tampil setelah hasil cek di `/murid/orang-tua`, juga untuk sesi murid (pengecualian palang murid 23 Nov), dan mengikuti tirai PIN.
- Tes diagnostik tajam (live 15 Nov 2026, `7b57cc7`): `diagnostic_battery.py` komposer murni paket
  berpasangan per jenjang (triase prasyarat + minimal dua probe per sub-konsep; P1/P2 10, P3 20,
  P4–P6 24 butir). `database.buat_sesi_diagnostik` (berkas kontrak, memakai `buat_sesi_dari_urutan`
  + `soal_terpilih`) dan `session_http.tangani_pembuatan_diagnostik` membuka `POST
  /sesi-diagnostik/<siswa>` dengan `mode='diagnostik'`; UI-nya kartu di `practice_workspace.py`.
  `topic_school_basics.py` mendaftarkan paket `berhitung-sekolah` P3–P4 (perkalian, pembagian,
  pecahan sederhana, nilai tempat ratusan/ribuan) lewat `topics.py`; grup mastery-nya menggeser
  pemetaan terpandu P3 (bukti `teaching_playbook`/pancingan diselaraskan, keduanya draf).
  Diagnosis: `students.PILIHAN_CARA` menambah `hitung_kertas`; `diagnosis.diagnosa` memakai jejak
  cara itu sebelum fallback `N`, sedangkan penanda `tebak` tetap `N`; `diagnosis.evaluasi_pasangan_diagnostik`
  mengelompokkan hasil per sub-konsep (`kuat`, `konsisten_k`, `konsep_awal`, `teliti`, `tebak`,
  `belum_diajari`, `belum_dinilai`) dengan penanda sesi `triase_macet`. `diagnostic_summary.py`
  memanggil agregator itu dari `teacher_session_pages.halaman_sesi_stitch`, hanya untuk sesi
  berkomposisi baterai exact dan peran guru/admin (read-only, tanpa kode/malrule ke murid). Karena
  `database.py` berubah, recovery dipatok `6a5f0ec` (kontrak `dd3e0fce`, pengganti `461c2bc`).
- Laporan orang tua snapshot v2 (15 Nov 2026): `parent_report_snapshot.VERSI=2` menambah
  `peta_topik`, `alur_berpikir`, `kuat`, `fokus`, `langkah_rumah`, `cakupan`, `ringkasan_teruskan`
  di dalam allowlist yang sama (tanpa skor/kode/level); `parent_report_page.py` merender **SVG
  sebaris** murni-Python (tanpa skrip/gambar/tautan) dan snapshot v1 lama tetap dirender dengan
  fallback. `mastery_report._pilih_materi` memilih materi default yang sudah punya bukti konteks,
  bukan sekadar urutan alfabetis topik, agar topik baru tidak menyembunyikan bukti materi lain.
- `teacher_home_priority.py` hanya memproyeksi reducer; `guru_beranda_pages.py` merender /guru
  (chip GET owner-scoped dengan filter instan berhash/fallback native, petunjuk langkah
  ringkas, panduan guru baru yang hilang setelah sesi pertama) tanpa menulis DB atau
  membuat ranking kemampuan. Respons privat no-store/no-referrer.
- `teaching_playbook.py` membaca JSON internal dengan validasi identitas/versi/hash;
  draf berlabel diizinkan tampil, bukan disahkan. `assistant_manage.py` menangani
  pengelolaan data sebelum gate provider; AI tidak mengambil alih konfirmasi/reducer.
- `catalog_versions.py`/`number_theory_versions.py` memisahkan writer dan reader
  historis. Bank kalimat hanya mengubah snapshot baru. `assessment_revision.py`
  revisi1 default0; `catalog_followup.py` menyediakan draf revisi2 terpisah
  (`OSN_KATALOG_LANJUTAN=0`), reader berdasarkan marker dan tanpa backfill.
  Codec sesi campuran v2 belum terhubung writer.
- **Latihan Lomba** (`contest_*.py`, `schema_lomba.py`; plan lokal `docs/plan/2026-11-21-latihan-lomba-corexis.md`): `contest_core` kontrak soal (`SoalLomba`, `Template`, validasi soal/SVG,
  `ambil_pengecoh`, `susun_pilihan`); 38 template di `contest_templates_{number,arithmetic,measurement,geometry}*.py` (id berawalan `bil_/ops_/ukur_/bgn_`, verifikator independen, SVG di `contest_svg_*`);
  `contest_session.rakit_sesi` (komposisi, tingkat, rotasi, dedup lintas sesi; Latihan dan Simulasi di jalur perakitan terpisah supaya Latihan identik per seed, dikunci sidik 40 seed di `test_contest_simulasi`; `rakit_dengan_pelonggaran` melepas larangan sesi tertua bila perakitan gagal); `contest_store` (timer epoch dari jam server, finalisasi malas, simpan jawaban atomik; `mulai_atau_lanjut(mode, durasi_detik)`, batas disalin ke sesi; `SesiRingkas.mode/jumlah_soal` dipakai layar sebagai jumlah soal sesi, bukan konstanta paket; halaman anak hanya membaca kolom
  aman); `contest_results` (satu-satunya pembaca kunci; hanya sesi tidak berjalan; hasil rinci, riwayat, progress; `RingkasSesi.asal_kumpul` memakai `contest_paket.asal_kumpul` dan mengecualikan sesi dikumpulkan asal dari agregat; label jenis Guru di `contest_label_jenis`); HTTP `contest_http` (murid, di bawah `/murid`, sebelum `student_http`) dan
  `contest_guru_http` (`/anak/<id>/lomba`, sebelum penangkap `/anak/`); satu-satunya JS `contest_browser.SKRIP_TIMER`; `contest_paket` (paket sebagai konfigurasi kode: `PaketLomba`/`PAKET_AKTIF` dengan `format_mode` Latihan/Simulasi, hari WIB, hitung mundur, `asal_kumpul` per mode, `menit_sah` 5-180; `contest_session.JUMLAH_*` diturunkan darinya; `contest_store.PAKET_ID/DURASI_DETIK` tetap literal agar fingerprint kontrak persistensi rilis tidak bergeser, kesamaannya dikunci tes; spasi isian dibuang di `contest_http.buang_spasi`); `contest_anak` (ringkasan anak: sesi berjalan, nilai terbaik, target harian, banding, soal kosong siklis untuk auto-pindah di `contest_http`);
  render murni `contest_pages` (soal, konfirmasi), `contest_awal`, `contest_home` (kartu beranda murid, CSS `GAYA_BERANDA` hanya dimuat saat sakelar hidup), `contest_komponen`; gerbang `contest_gate`: `aktif()` = sakelar induk `OSN_LOMBA`, `aktif_untuk(kon, siswa_id)` = induk DAN penugasan anak aktif (fail-closed; dipakai beranda murid dan semua rute `/murid/lomba`, 404 identik tanpa efek samping). Penugasan per anak: tabel `lomba_penugasan` + `contest_assignment_store` (`ambil`, `atur` yang mewajibkan semua nilai termasuk durasi per mode supaya pemanggil meneruskan nilai lama secara eksplisit; satu-satunya SQL tabel itu, ikut fingerprint kontrak persistensi rilis sehingga tidak diubah di luar commit basis recovery); Guru mengaturnya lewat `contest_guru_http.tangani_post` (POST `/anak/<id>/lomba/pengaturan`, setelah `_lolos_sandi` dan `_asal_sama_post`, kepemilikan lewat `_bisa_lihat_siswa`, 404 identik tanpa tulis) dan kartu `contest_guru_pages.kartu_pengaturan`, serta tombol per anak di halaman akun (`contest_account`: aksi `mode_lomba` di `account_pages.proses_akun`, kepemilikan `database.siswa_milik`/admin, hanya `aktif`); `contest_anak.paket_untuk_anak` menimpa target harian/hitung mundur/durasi paket dengan nilai penugasan bila diisi. Tanggal dan nama lomba milik tiap anak (23 Nov 2026): kolom `lomba_penugasan.tanggal_lomba`/`nama_lomba` (migrasi aditif `schema.MIGRASI`, baris lama ber-DEFAULT 12 Des 2026 / Grand Final Corexis, `atur` selalu menulis keduanya eksplisit sehingga anak baru NULL); bila anak punya baris penugasan, hitung mundur memakai tanggal barisnya (NULL = tanpa hitung mundur), tanpa baris = tanggal paket; nama hanya tampil ke Guru (di-escape), tombol `/akun` mempertahankan keduanya. Tabel `lomba_sesi/soal/jawaban/penugasan` di
  latihan.db: indeks unik parsial satu sesi berjalan per anak, soal disimpan beku, CASCADE ke siswa, dihapus eksplisit di `family_deletion._hapus_lomba` (per tabel, tabel yang belum ada dilewati). `lomba_sesi.mode` dan durasi penugasan lewat `schema.MIGRASI`; CHECK nomor `lomba_soal` 1..35 lewat `schema_lomba.perlebar_nomor_soal` (rebuild di `database.siapkan` dengan FK nonaktif, salin kolom eksplisit, DROP lalu RENAME, cek jumlah baris dan `foreign_key_check`; idempoten). Waktu selalu parameter `sekarang` (epoch detik).
- **Latihan Harian** (F4; `harian_*.py`, `schema_harian_latihan.py`; plan lokal `docs/plan/2026-11-23-f4-f5-latihan-harian-langganan.md`): `harian_pg` (PG 4 opsi murni dari generator + `choice_generation.kandidat(soal, 3)` + `multiple_choice.buat_pilihan`/`validasi_kebenaran`; `audit_template` deterministik dari 40 seed), `harian_tingkat` (8 tingkat; judul tampil "Kelas 1-6" + dua Tantangan OSN, kode `t1`..`t6` yang disimpan DB tidak berubah; sumber = bab atau grup pengayaan, `audit_tingkat`/`laporan_audit`), `harian_rakit` (10 soal per seed `secrets`, RNG berbasis string, tanpa `hash()`), `harian_latihan_store` (sesi, soal beku, jawab sekali lewat PRIMARY KEY, kuota WIB lewat `akses_harian`; proyeksi aman `SoalAnak` vs `UmpanBalik` yang hanya dibaca setelah terjawab), `harian_http` (rute murid sebelum `_lolos_sandi`, dipasang di `web.py`; `siswa_id` hanya dari sesi), `harian_pages`/`harian_style` (render murni; tanpa JS baru), `harian_waktu` (hari WIB). Tampilan memakai komponen ceria bersama (butir berikut); `harian_http` hanya mengoper bendera tampilan `ada_ortu` dari `daftar_anak_gate.aktif()` dan `tampil_ajakan_ortu` dari `kuota().akses.tanpa_batas`, bukan gerbang. Tabel `harian_sesi/soal/jawaban` aditif (CASCADE ke siswa, dihapus eksplisit di `family_deletion._hapus_harian`); argumen `kini` ke `akses_harian.akses` = waktu UTC `%Y-%m-%dT%H:%M:%S`.
- **Komponen ceria bersama** (`playful_components` + `playful_style`, plan lokal `docs/plan/2026-11-24-ui-anak-ayah-bunda.md`): markup murni ter-escape bergaya landing page (hero dengan simbol/konfeti, maskot + gelembung bicara, stiker, kata sorot, kartu navy "Untuk Ayah/Bunda", kartu status berlencana teks, titik 7 hari, progres 10 kotak, skor besar, banner umpan balik); tautan kartu hanya alamat dalam aplikasi (ditolak: `//`, backslash, spasi, karakter kontrol). CSS `playful_style.GAYA_CERIA` ber-namespace `ceria-`, token-only, animasi hanya di `prefers-reduced-motion: no-preference`; sengaja tidak ikut `gaya_stitch()`, tiap halaman pemakai menambahkannya ke `<head>`. Pemakai: halaman anak (`harian_pages`, hero beranda di `student_pages`), halaman Ayah/Bunda (`orang_tua_pages`), dan halaman langganan (`harian_langganan_pages`). Maskot berupa hiasan (alt kosong, pesan dibawa teks); satu maskot per layar dan level judul dijaga pemanggil, bukan modul. Pose: enam v3 (`brand.POSE_MASKOT`) + sepuluh v4 (`brand.POSE_MASKOT_V4`, disetujui 24 Nov 2026; aset terdaftar, pemasangan per layar bertahap).
- `family_deletion.py` menghasilkan bundle privat tervalidasi, bukan mutasi live
  langsung. Sensor/policy, billing dan riset tetap mempunyai consent/retensi berbeda.
- Façade/adapter legacy dan reducer besar sengaja dipertahankan ketika pemisahan
  akan merusak boundary transaksi/retry; lihat alasan di referensi arsitektur.

## Git, verifikasi dan produksi

Repo luar `/Users/nugroho/Documents/jagomat/aplikasi`, branch `main`, origin
`clarinovist/jagomat`; repo Git hanya satu di root (`mesin/.git` lama sudah dihapus). Gunakan `git -C` ke repo
luar dan jaga WIP sesi lain. Folder induk lokal `~/Documents/jagomat/` (disusun 8 Nov 2026)
berisi `aplikasi` (repo ini), `berkas`, `cek`, `tim`, `web`, dan `riset` (dulu `osn-resources`);
saudara-saudaranya bukan bagian Git repo ini. Lokal: scoped test/compile/review, bukan full suite default.
Push memberi CI cepat; dispatch rilis = palang lalu build/probe/pair (tanpa suite);
full suite kandidat/recovery empat shard mingguan atau dispatch `audit: true`. [CI hybrid](ci-selective.md).

Image tetap `ghcr.io/clarinovist/osn-mesin-latihan`; domain `https://jagomat.id`;
SSH alias `biznet-sekolahdesain`. Tidak build di VPS. Auto-pasang tetap nonaktif;
preflight sebelum maintenance, backup/rehearsal, exact digest, health dan recovery
mengikuti [runbook](production-release.md), bukan disimpulkan dari CI hijau.
