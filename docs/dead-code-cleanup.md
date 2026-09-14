# Keputusan cleanup dead code

Cleanup berdasarkan audit baseline `e432eea`. Tujuannya menghapus implementasi
usang, bukan mengubah perilaku aktif atau mengurangi palang keamanan. Nomor baris
audit tidak dijadikan patokan penghapusan; nama simbol dan pemanggil diperiksa ulang.

## Bukti dan keputusan per kelompok

### A1 — router

- **Dihapus:** cabang GET kedua di `assistant_http.tangani_get` untuk konteks,
  riwayat, memori, usulan, operasi, dan pembacaan chat. Pola/URL yang sama sudah
  ditangani dan `return` sebelumnya. Fallback provider tidak siap (503), form
  persetujuan sebelum consent, dan 404 tetap dipertahankan.
- **Dihapus:** `web.Penangan._handle_daftar`, tanpa caller AST, referensi teks,
  maupun dispatch dinamis. POST `/daftar` tetap memakai token form,
  `admin_registration.daftar_publik`, status pendaftaran, dan principal mutakhir.
- **Dipertahankan:** redirect URL lama, adapter POST, `_chat_html`, renderer memori,
  status, persetujuan, serta guard kepemilikan. Sebagian masih dipakai POST.

### A2 — admin dan audit AI

- **Dihapus:** `account_pages.proses_admin` dan `account_pages.halaman_admin`.
  Caller hanya test; router memakai `admin_http` dan renderer `admin_pages`.
- **Dihapus:** modul `ai_admin` (dua DTO dan pembaca audit lama). Caller hanya test;
  pembaca aktif adalah `ai_service.riwayat_admin` →
  `ai_admin_operations.riwayat_operasi`, termasuk proyeksi data audit warisan.
- **Dihapus:** `admin_pages.render_belum_tersedia`, placeholder sebelum integrasi
  pendaftaran/riwayat. Missing store tetap ditangani jalur HTTP aktif.

Assertion bernilai dipindahkan, bukan sekadar dibuang:

| Kontrak lama | Pengganti/pengaman aktif |
| --- | --- |
| Target kosong/hilang/admin ditolak tanpa mutasi | `test_admin_http_c.test_tinjauan_target_kosong_hilang_dan_admin_tanpa_efek`, dua aksi, body/status identik dan auth/audit tidak berubah |
| Sandi guru minimal 12; reset berhasil dan akun lain tidak berubah | `test_reset_guru_sandi_pendek_ditolak_lalu_sukses_terisolasi`, melalui review, CSRF, reauth dan POST |
| Hapus login tidak menghapus siswa/riwayat | `test_hapus_login_guru_tidak_menghapus_siswa_atau_riwayat`, snapshot DB dan audit hasil |
| Aksi asing ditolak | `test_aksi_akun_tidak_dikenal_ditolak_tanpa_efek` |
| Tidak menawarkan reset tanpa target / admin hanya-baca | `test_admin_pages.test_tindakan_tanpa_target_tidak_menyediakan_form_reset` |
| Riwayat kosong jujur / storage belum siap | `test_riwayat_kosong_jujur_dan_tanpa_kontrol_mutasi` dan test existing `test_get_admin_tidak_membuat_store_yang_hilang` |
| Landmark, escaping, label aksesibel panel | `test_parent_editorial` kini merender `admin_pages` dengan DTO `admin_queries` |
| Audit AI atomik, retensi 180 vs ledger 90 hari, reader missing DB, filter invalid | `test_ai_admin_audit` memakai `ai_service.riwayat_admin` dan waktu sintetis eksplisit |

Penolakan semua murid oleh helper guru lama bukan kontrak panel baru: admin kini
sah mengelola login murid lewat target/review yang sesuai. Guard khusus adapter
`auth.setel_sandi_guru`/`hapus_akun_guru` tetap diuji, tidak dilemahkan. Test domain
langsung pada adapter auth tersebut tidak dihapus. Field DTO/status AI disesuaikan
ke kontrak operasi aktif (`uncertain`, `operasi_id`, `revisi`), bukan payload privat.

### A3/B — helper, import, konstanta, dan assignment

Tidak ada pemanggil aktif/test/dokumen untuk simbol berikut setelah AST, referensi
teks, registrasi, dan caller dinamis relevan diperiksa:

- `admin_store.buat_batch_durable`, `hentikan_batch_durable`,
  `konfirmasi_penyerahan_durable`, dan
  `assistant_store.versi_persetujuan_konteks` terdeteksi sebagai wrapper tanpa
  pemanggil aktif, tetapi sengaja **dipertahankan** sampai recovery/policy kontrak
  produksi diputar melalui jalur migrasi tersendiri. Cleanup rutin tidak boleh
  mengubah fingerprint persistensi secara sepihak.
- `admin_bulk._status_batch`, `_sinkronkan_transient_durable`;
  `admin_queries._pola_like_literal`; `reports._topik_terlemah`;
  `students._ambil_topik`, `label_pilihan`.
- `topic_number_patterns.susun_lembar`: adapter `templates.__getattr__` sebenarnya
  mengarah ke **method `Topik.susun_lembar`**, bukan fungsi modul ini.
- `sessions._garam_dummy` dan `_ITERASI` lokal terdeteksi tanpa pembaca, tetapi
  dipertahankan bersama berkas kontrak sampai recovery/policy diputar. Proteksi
  timing per login di `auth.autentikasi`/`periksa` tetap utuh.
- Konstanta `BATAS_BODY`, `AKSI_DOMAIN_C`, `STATUS_KELUARGA`, `STATUS_LOGIN`,
  `MIME_SAH`, `_BATAS_TUNGGU`, dan `topic_number_patterns_param.HURUF`.
- Import audit yang dibuang: `admin_bulk_http.admin_pages`,
  `admin_pages.SKRIP_MATA_SANDI`, `admin_queries.Sequence`, `render.GAYA_LAYAR`,
  `topic_number_patterns.html`/`Any`, `topic_plane_geometry.random`, dan
  `verify_release_image.sys`. `sessions.threading`/`hashlib` serta
  `templates.Callable` dipertahankan bersama berkas kontrak sampai rotasi
  recovery/policy. Import non-kontrak yang kehilangan pemakai juga dibuang:
  `students.dari_sesi`, `test_assistant_retry_guards.re`, dan
  `visual_test_support.identitas_varian`.
- Assignment murni tak dibaca: `faktor` pada `satuan_konversi`, `sebenarnya_cm`
  pada `skala_peta`, `genap` pada `susun_bilangan_syarat`, empat `k_lupa` pada
  `perbandingan_volume`, `izin_server` pada `ai_pages.halaman`, dan `n` pada
  `landing.halaman_kebijakan`. Tidak mengubah parameter, kunci, malrule, atau teks.
- Empat helper test: `_id_chat`, `urllib_parse_path_from_html`, `_sesi_drill`,
  `contoh_varian`. Tidak ada caller; bukan fixture/hook pytest atau stdlib.

### C — CSS

**Dihapus setelah pembuktian:** `.grid-utama`, `.kartu-siswa`, `.siswa-kepala`,
`.layout-masuk` di `teacher_style`, serta `.koreksi-baris-st` di `style_stitch`.
Total 26 baris sumber CSS termasuk komentar dan media rule eksklusif.

Bukti: tidak ada pembentuk class statis/dinamis pada halaman aktif; browser fresh
context merender 21 halaman/state sintetis (publik, login/salah-login, guru,
profil, koreksi kosong/terisi, laporan, akun, siswa, admin, cetak, lampiran, hapus,
dan murid) pada lebar 390 dan 1366 px. Semua lima class berjumlah nol elemen;
tidak ada horizontal overflow. Setelah cleanup, **42 hasil DOM/geometri/computed
style dan hash SHA-256 screenshot identik**. Waktu fixture distabilkan dan gambar
ditunggu selesai decode; request eksternal diblokir di kedua sisi. Screenshot
koreksi terisi mobile dan login desktop juga diperiksa visual sebelum/sesudah.

`test_layout_sesi_guru` kini mengunci `.koreksi-bukti-st` pada DOM nyata, jawaban
singkat + Caraku, penilaian pada details terpisah, serta breakpoint 40rem. Tidak
menghidupkan kembali desain jawaban + kode dua kolom yang sudah ditinggalkan.

## Dipertahankan / ditunda secara sengaja

- Semua **93 template** masuk komposisi aktif; registry, `templates.__getattr__`,
  re-export `worksheets`, CLI, migrasi, backup, recovery, inventaris visual, probe
  release dalam string, dan aset maskot immutable **bukan dead code**.
- API test-only/kompatibilitas: `database.sasaran_remedial`,
  `tandai_pengenalan_selesai`, `tautkan_sesi_putaran`, `students.semua_terisi`,
  `reports._rapikan_kalimat`, `generator.profil`, `visual_renderer.render_teks`,
  `auth.periksa_peran`/`peran_dari`, `sessions.ambil`/`cabut_akun`. Kontrak konsumen
  di luar jalur web belum diputus; tidak blanket delete.
- API consent, pencabutan konteks, hapus chat, `admin_service.rekonsiliasi*`,
  `admin_students.siswa_boleh_dihapus`, dan alat audit/katalog tetap. Test memakai
  sebagian untuk failure path; perlu audit lifecycle khusus sebelum penghapusan.
- `assistant_pages.halaman_awal` dan `assistant_service.mulai_chat_dan_kirim`
  belum dihapus: meskipun pembuatan chat umum HTTP sudah 410, helper ini terikat
  test retry/rollback consent. Penghapusan UI standalone beserta dependensinya
  ditunda agar tidak mencampur perubahan kontrak service sensitif; endpoint HTTP
  tertutup tetap diuji. Renderer lain yang kehilangan satu caller GET juga tidak
  otomatis dihapus karena beberapa tetap dipakai POST.
- CSS di luar lima class brief, termasuk `.masuk-kiri`, `.kartu-masuk`,
  `.badge-tingkat`, `.pendamping-awal`: belum dibuktikan seluruh state/konsumennya
  dalam scope ini. `.kolom-sandi`/`.tombol-mata` jelas aktif lewat JavaScript.
- Token `LATAR_INTI`/`BINTANG` masih tercatat dalam design system.
- Binding `akun`/`tinjauan` hasil `_token_final`, `belum` pada `_ubah_fokus`, dan
  unpack `a,b,c` pada `_prisma` tidak dihapus: RHS/struktur membawa validasi,
  guard, atau tuple contract. Tidak menukar ketiadaan pembacaan dengan asumsi
  ketiadaan efek samping.

## Verifikasi lokal

Semua scoped command memakai interpreter workspace Python 3.12.3, pytest
`-q -n auto -W error -p no:cacheprovider`, env worker tetap 2:

| Kelompok | Hasil |
| --- | --- |
| A1 router/pendaftaran/Pendamping | 85 passed, exit 0 |
| A2 admin/AI/editorial | 154 passed, exit 0 |
| A3/B domain/helper/topik/golden | 1561 passed, exit 0 |
| C layout/editorial/login/AI | 181 passed, exit 0 |
| Review cleanup import turunan/landing/router | 118 passed, exit 0 |

Sweep seed 0..24 × template × level seluruh topik (tanpa menggandakan campuran),
versi matematika 1 dan 2: **4.900 kasus per versi**, membandingkan seluruh dataclass
Soal dan HTML soal/kunci. SHA-256 identik sebelum/sesudah:

- v1 `cba2ad59d008752f706c4e3aed2123afefbde5c760aa80eaba2b2a04523ab9a5`
- v2 `d2c1a43199e2ed0bd15ea508c457b6ee4332dcb10d0cfded0ba3a02a9abc9d57`

Mutation salinan source terisolasi: melewati panjang minimum reset sandi membuat
HTTP 200 menggantikan 400 dan test merah; menghilangkan fallback consent membuat
404 menggantikan form 200 dan test merah. Masing-masing exit 1, pulih exit 0.
Tidak ada guard produksi yang diubah; mutation membuktikan assertion yang
migrasi/tambahan benar-benar menggigit jalur aktif.

Preset `.project-gate.json` final: palang repo/privasi lulus (451 berkas),
**9901 passed in 3182.36s (0:53:02)**, kompilasi **386 berkas** lulus;
ketiga command exit **0**. Jumlah kasus tetap 9901: 12 nama test lama
hapus/ganti, 8 nama baru dengan parameterisasi, bukan pengurangan gate.
Source/config/test identik sepanjang suite; hanya catatan hasil ini ditambahkan
setelahnya, lalu palang index diperiksa ulang sebelum commit.

Diff kode/test sebelum dokumentasi: source/skrip 10 baris tambah, 651 hapus;
CSS 26 hapus; test 184 tambah, 179 hapus (termasuk empat helper mati).
Total kode aplikasi/skrip/CSS berkurang bersih **667 baris**.

Tidak build Docker, tidak akses data produksi, tidak menjalankan provider.
Kompilasi/AST 3.9 bukan pengganti uji runtime Python 3.9.
