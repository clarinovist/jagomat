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
- `scripts/`: palang repo, shard CI, build/probe/pair/deployer, katalog desain luring, ekspor token untuk alat desain, dan eksperimen sintetis. Modul `release_*_pair.py` adalah data probe; bentuknya (konstanta wajib + penanda unik) dijaga `release_pair_common.py` dan test kontrak, bukan disalin manual.
- `docs/`: kontrak permanen; `docs/plan/` lokal/gitignored, bukan satu-satunya sumber keputusan.
- Empat DB durable inti: belajar, Pendamping, kontrol AI, kontrol admin; auth
  `sandi.json` ikut bundle backup. Riset konsumen mempunyai DB/retensi/backup terpisah.
  Sesi/transient bukan pengganti state durable; detail inventaris di runbook.
  `scripts/operational_backup.py` menambahkan envelope core+riset+lampiran saat
  quiescent dan transfer privat tervalidasi; `mesin/cadangkan.sh` fetch-only, tanpa prune.
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
- `admin_sakelar_pages.py` → `admin_sakelar_http.py` untuk `/admin/sakelar`: empat sakelar di
  `feature_switch.py` (DB terpisah, fail-closed, env fallback) + `sakelar_registry.py`; guard aksi sama
  dengan panel rekening (tinjauan bertanda tangan, sandi ulang, konflik revisi, audit). Database sakelar
  rusak = 503 jujur.
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
  tersimpan dipetakan saat render),
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
  `/admin/pesanan` (token final admin, aksi periksa dan catat refund; tidak menulis jurnal `operasi_admin`, jejak refund = baris
  `pesanan_refund`). Panggilan jaringan tidak pernah di dalam transaksi tulis. Kontrak rilis bergeser seperti Fase 2.
- Transfer rekening (jalur utama pembayaran, verifikasi manual admin; tahap 1 = skema + logika inti; tahap 2 = alur guru di bawah; tahap 3 = admin, retensi, jendela ulang):
  `schema_transfer.py` (namespace `transfer_*`, sengaja BUKAN `pesanan_*` agar `schema_pesanan.validasi` dan rollback image lama utuh;
  tagihan per jendela bayar, bukti, penanda hapus, verifikasi, `transfer_lunas`, `transfer_refund`; append-only) + `pesanan_transfer.py`
  (tagihan nominal unik 49.000+kode 1..999, bukti, setujui/tolak, retensi bukti 30 hari) + `pesanan_transfer_baca.py` (fakta untuk status
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
  `pesanan_retensi.py` (hapus berkas lalu tandai, bukti 30 hari sesudah keputusan, sisa `.tmp-*` > 1 jam) dan `pesanan_transfer_migrasi.py`.
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
Push memberi CI cepat; dispatch manual membuktikan kandidat/recovery exact empat
shard, build/probe/pair. [CI hybrid](ci-selective.md).

Image tetap `ghcr.io/clarinovist/osn-mesin-latihan`; domain `https://jagomat.id`;
SSH alias `biznet-sekolahdesain`. Tidak build di VPS. Auto-pasang tetap nonaktif;
preflight sebelum maintenance, backup/rehearsal, exact digest, health dan recovery
mengikuti [runbook](production-release.md), bukan disimpulkan dari CI hijau.
