# Usulan rubrik tuntutan dan kontrak sesi campuran

**Status: pilot dua tuntutan disetujui pada 21 September 2026; katalog luas tetap draft.**
Implementasi pilot lokal memakai `skill_pilot*.py`, bukan mengaktifkan modul draft
atau codec campuran v2. Persetujuan mencakup rujukan terbatas luas kotak satuan P3,
variasi matematis tambahan, serta tawaran probe balik melalui keputusan orang tua.
Kontrak aktif dirinci pada [siklus belajar](siklus-belajar-terpandu.md).
Bagian usulan historis di bawah merekam dasar keputusan, bukan izin rilis produksi.

## 1. Audit yang dapat diulang

Dari root repo, tanpa DB, akun, atau jaringan:

```bash
mesin/.venv/bin/python -B scripts/audit_skill_demands.py --jumlah-seed 25
```

Output JSON hanya soal sintetis dan metadata source. Simpan ke lokasi privat bila
perlu; bukan fixture data keluarga. Versi generator aktual tercatat di output.
Hasil checkpoint: **93 pola, 196 pasangan pola/profil, 4.900 soal** pada seed0..24.
Jumlah ini inventaris teknis, bukan target wajib atau ukuran siap OSN.

Setiap baris mengandung profil, target katalog warisan, varian/kategori parameter,
rentang angka sampel, contoh soal/kunci/pembahasan per varian, representasi snapshot
yang tersedia beserta hash render, kartu rumus, pendekatan K, serta source/baris/hash.
Representasi teks warisan dapat memuat gambar dari renderer lama; label `teks-v1`
bukan pernyataan semua tampilan tanpa gambar. Audit juga menjalankan proyektor visual
secara eksplisit, bukan membaca konfigurasi visual keluarga.

**Batas:** sampel tidak membuktikan seluruh cabang telah muncul. Parameter seperti
warna/nama benda bisa hanya hiasan, bukan tuntutan baru. Adanya kartu/intervensi
bukan bukti cocok bagi setiap varian/malrule. Audit tidak mengesahkan prasyarat.
Di luar pilot, deskripsi fungsi source dan contoh tersedia untuk review manusia;
`prasyarat_terverifikasi=null` dan `belum direview per tuntutan` sengaja dipertahankan.

### Temuan lintas materi existing

| Materi | Perbedaan tugas yang teramati | Pemeriksaan pedagogis berikutnya (belum disahkan) |
| --- | --- | --- |
| Pola bilangan | Meneruskan, mengisi bagian hilang, posisi suku, jumlah, siklus, pola gambar | Bedakan menemukan relasi dari substitusi posisi/jumlah; teks/korek/titik tidak otomatis setara |
| Aritmetika dasar | Urutan operasi, tanda kurung, FPB, operasi/urut pecahan, taksiran | Urutan dan representasi pecahan perlu ditinjau; angka lebih besar bukan otomatis penalaran baru |
| Geometri datar | Keliling langsung/balik-luas; sudut langsung/rasio; diagonal balik; juring/arsiran | Relasi langsung, operasi balik, komposisi area, serta pemilihan informasi perlu dipisah |
| Geometri ruang | Volume/luas permukaan langsung atau mencari sisi/tinggi; jaring/kubus dicat | Jangan samakan inversi rumus dengan visualisasi ruang; prasyarat akar/pangkat perlu review |
| Kombinatorik | Menjumlah/mengalikan pilihan, menyusun dengan nol/syarat, memilih, blok, jalur/himpunan | Urutan penting/tidak, kasus terlarang dan pencacahan ganda perlu contoh pembeda |
| Teori bilangan | Keterbagian, prima, KPK/FPB, sisa/paritas, siklus satuan pangkat | Kenali sifat bilangan versus hitung prosedural; daftar profil tidak menjadi rantai penguasaan |
| Aritmatika lanjut | Jarak/waktu/kecepatan dan debit mencari besaran berbeda; rasio, kerja, persen bertahap | Pembalikan relasi, senilai/berbalik dan perubahan basis persen perlu rubrik terpisah |
| Statistika | Baca/jumlah/selisih; rata-rata langsung/data hilang; nilai/sudut diagram; median/modus | Membaca visual, mengagregasi dan membalik hubungan bukan tugas yang sama |
| Logika | Pengandaian, tabel, jumlah-selisih, umur/uang | Perlu review strategi eliminasi/pemodelan, bukan mengurutkan ukuran nominal |
| Pengukuran | Konversi maju/balik; durasi/mulai/selesai; skala/peta/sebenarnya | Bedakan operasi balik dan basis satuan panjang/luas/volume; jangan satukan representasi |

Tabel ini triase review, **bukan 10 rubrik final**. Inventaris lengkap ada pada output
alat, termasuk rujukan fungsi dan contoh tiap pola/profil. Tidak ada perubahan topik,
parameter, kunci, malrule, rumus atau pembahasan pada checkpoint ini.

## 2. Pilot yang direkomendasikan untuk disetujui

Versi usulan: `pilot-keliling-luas-draft-v1`. Dua ID berikut stabil terhadap perubahan
angka/profil, tetapi **belum menyatakan kesetaraan bukti antarprofil/representasi**.
Bila makna tugas berubah, buat versi baru; jangan mengganti arti ID historis.

| ID tuntutan | Deskriptor | Pemetaan existing | Contoh sintetis |
| --- | --- | --- | --- |
| `persegi-panjang.keliling-langsung.v1` | Menentukan keliling dari panjang dan lebar serta menjelaskan dua pasang sisi | `keliling_luas_datar`, `varian=keliling` | Panjang8cm, lebar3cm → keliling22cm; jelaskan mengapa `(8+3)×2`, bukan `8×3` |
| `persegi-panjang.luas-dari-keliling.v1` | Menentukan sisi yang hilang dari keliling, lalu menghitung luas | `keliling_luas_datar`, `varian=balik_luas` | Keliling22cm, panjang8cm → lebar3cm → luas24cm²; jelaskan arti `22÷2−8` dan perkalian berikutnya |

Source pemetaan: `mesin/skill_demand_draft.py`. Ia menerima pola/parameter/representasi,
bukan nilai/kelas/kemampuan anak. Varian, field, ukuran dan versi asing ditolak;
pola di luar pilot tidak dipetakan. Ini untuk audit, tidak menulis metadata sesi.

Fakta parameter: P3 menghasilkan langsung (batas source sisi2..16), P4–P6 memilih
langsung (sisi3..40) **atau** balik (panjang3..30, lebar2..25 yang disembunyikan).
P4–P6 bukan tiga tahap terurut. Sisi lebih besar pada varian langsung tidak memberi
ID tuntutan baru. Keberhasilan P6 tidak meluluskan konteks P3, dan sebaliknya.

### Prasyarat, pengenalan, dan intervensi usulan

- **Langsung:** makna keliling sebagai panjang batas, pasangan sisi, penjumlahan.
  Minta anak menunjuk empat sisi. Kartu existing memberi contoh8×3, tetapi cocoknya
  setiap malrule tetap harus ditinjau, bukan menganggap `tersedia=True` cukup.
- **Balik:** hubungan keliling dengan jumlah dua sisi, operasi balik penjumlahan,
  luas sebagai perkalian dan satuan persegi. **Belum ada contoh intervensi balik
  spesifik** dalam kartu existing: dua pendekatan K menggunakan contoh langsung
  yang sama. Ini blocker penawaran intervensi balik otomatis.
- Usulan konten balik untuk persetujuan: “Separuh keliling memuat satu panjang dan
  satu lebar. Pada keliling22cm, separuhnya11cm. Panjang8cm, jadi lebar3cm. Luasnya
  8×3=24cm².” Pendekatan alternatif: gambar empat sisi lalu cari jumlah sisi yang
  belum diketahui sebelum memakai luas. Belum ditambahkan ke materi anak.
- T/materi belum dikenal → pengenalan lalu probe mandiri; bukan fokus kelemahan.
  Jawaban setelah contoh/bantuan tidak menjadi bukti mandiri. Jika konten yang
  cocok belum tersedia, tampilkan kebutuhan pendampingan, bukan drill generik.

### Syarat bukti yang dipertahankan

Unit bukti kelak mencakup tuntutan+versi, pola, profil aktual, representasi, serta
provenance sumber. ID sama tidak berarti bukti beda profil/representasi digabung.
Pemetaan kesetaraan awal **kosong**, termasuk antarrepresentasi. Tidak memproyeksikan
histori ke tuntutan dengan membaca kemampuan terbaru atau menciptakan konfirmasi.

Tetap: snapshot aktif terkonfirmasi, manual opt-in pada konfirmasi yang sama,
bukan PG manual/drill/bantuan/terbimbing/penguatan. Jalur pemetaan memerlukan dua
pemeriksaan berjarak≥3hari, ≥4 probe matematis bervariasi, tiap pemeriksaan≥75%,
bisa menjelaskan dan tanpa K/N/T/hasil belum jelas. Evaluasi ≥4 probe per fokus,
≥75%, tanpa K dan memenuhi guard tambahan penguasaan. Checkpoint dua bagian pada
occurrence yang sama, ≥3 probe/fokus, seluruhnya benar dan bisa menjelaskan;
28hari dan retensi/invalidasi existing tetap. Pembanding tidak masuk kuota fokus.

Keberhasilan langsung tidak meluluskan balik. Gagal balik tidak menghapus
keberhasilan langsung. Bukti usang tetap perlu cek kembali. Perubahan kelas tidak
mereset bukti. Tidak ada status global anak atau sertifikasi permanen.

### Aturan menawarkan berikutnya yang diusulkan (belum aktif)

1. Pertahankan urutan prioritas reducer: tugas aktif/konfirmasi/eskalasi dan tugas
   wajib existing mengalahkan penawaran baru; hanya satu CTA.
2. Materi belum dikenal mengikuti pengenalan→probe. Titik masuk tidak ditentukan
   kelas; catatan prasyarat adalah bahan memilih probe, bukan kelulusan otomatis.
3. Setelah tuntutan langsung memiliki bukti sah dan prasyarat luas terverifikasi,
   tawarkan **probe tugas balik**, melalui keputusan orang tua. Ini tawaran
   pemeriksaan, bukan klaim anak sudah memahami tugas balik.
4. Gunakan profil sumber jika mendukung varian tujuan; bila tidak (misalnya P3
   menuju balik), minta pilihan konfigurasi eksplisit, **jangan otomatis P4/P6**.
   Kebijakan memilih angka otomatis lintas profil tetap keputusan berikutnya.
5. Calon probe deterministik atas seed+konteks beku; tidak dipilih LLM. Ketika
   kuota/variasi tidak tersedia, gagal terlihat dan atomik, bukan fallback varian.
6. Latihan manual selalu tersedia tanpa pemetaan wajib. Tuntutan di luar pilot
   tetap latihan/riwayat, tidak diberi klaim baru.

### Penyebut yang direkomendasikan

**Tahap pilot:** tampilkan dua deskriptor secara terpisah di rincian laporan,
tanpa persentase baru/global. Ini menghindari mengesahkan penyebut seluruh katalog
sebelum 92 pola lainnya direview. Bukan membagi jumlah latihan atau hanya materi
yang pernah dicoba. Belum dinilai tetap tampil sebagai belum dinilai.

**Usulan untuk tahap katalog final:** satu target persegi-panjang lengkap hanya
bila kedua deskriptor wajib menunjukkan pemahaman pada cakupan bukti yang disahkan;
keberhasilan sebagian tetap terlihat. Katalog eksplisit berversi yang sama untuk
semua kelas memegang penyebut, bukan inventaris196. Daftar sasaran dan kesetaraan
parameter/representasi perlu persetujuan terpisah sebelum persentase diaktifkan.

**Keputusan yang diminta:** setujui dua deskriptor pilot, prasyarat/isi pengenalan
balik di atas, dan urutan *bukti langsung + prasyarat luas → tawaran probe balik*,
tanpa kelulusan otomatis atau persen baru. Konsekuensi: implementasi berikutnya
bisa menyiapkan intervensi spesifik dan selector pilot; profil angka yang belum
punya aturan tetap pilihan eksplisit orang tua. Ini bukan persetujuan seluruh
kurikulum, kesetaraan P3–P6, atau aktivasi produksi.

### Implementasi pilot lokal setelah persetujuan

- Dua tuntutan memakai rubrik `pilot-keliling-luas-v1`; P3–P6 dan representasi
  tetap konteks berbeda. `skill_demand_draft.py` tetap alat audit historis.
- Pilihan opsional ada di Rencana belajar. Satu profil per sesi; tugas balik baru
  tersedia bila bukti langsung dan rujukan luas sah, tanpa kenaikan profil otomatis.
- `skill_pilot_sessions.py` membekukan butir/penyajian/seed/tujuan/putaran/sumber.
  `skill_pilot_contract.py` adalah kontrak homogen pilot tersendiri, **bukan v2 campuran**.
- Konfirmasi mengikat kontrak pada fingerprint baru dan arsip append-only; konfirmasi
  v1/PG tidak diganti. Rujukan kisi lama harus terverifikasi dan memenuhi opt-in,
  variasi, penjelasan, jeda serta retensi; nama benda/satuan saja bukan variasi baru.
- Status/rekomendasi berasal dari `learning_cycle.py`; laporan Tuntutan pilot tanpa
  persen baru. Kartu orang tua menyediakan contoh spesifik; anak hanya tahap netral.
- Fokus yang sumbernya dicabut ditahan pada putaran terkait, tidak memakai diagnosis
  mutable atau sumber lain diam-diam. Orang tua dapat mengonfirmasi penutupan putaran
  dan pembatalan seluruh sesinya tanpa menghapus histori, lalu memilih pemeriksaan
  baru. Status konteks sehat tetap terpisah. Latihan manual tetap tersedia. Remedial/serupa
  warisan tidak meneruskan pilot tanpa konteks; gunakan rencana pilot.
- CLI/Pendamping tetap pembuat latihan manual, bukan pemilih/pembuat pilot. Sesi
  campuran, kesetaraan lintas profil, katalog seluruh pola dan recovery produksi
  tetap di luar aktivasi ini. Gate lokal tidak membuktikan image/live siap.

## 3. Kontrak sesi v2 nonaktif yang sudah diimplementasikan

`mesin/session_demand_contract.py` menyediakan dataclass frozen dan codec JSON
kanonis. Tidak mengimpor rubrik draft atau menganggap ID nonkosong sebagai rubrik
aktif. Semantik katalog divalidasi adapter kelak; codec hanya memvalidasi struktur.

- Per butir: nomor berurutan, pola, profil aktual, representasi, versi rubrik,
  ID tuntutan, serta target fokus opsional. Pembanding tidak memiliki target fokus.
- Per fokus: kunci kanonis `(template_id,kode_intervensi,malrule_id)`, tepat satu
  konteks, dan daftar ID konfirmasi sumber (bisa lebih dari satu sesi asal).
- Maksimal dua kunci fokus, unik, setiap fokus mempunyai butir sasaran. Kunci sama
  dengan dua tuntutan tidak dibuat menjadi dua fokus tersamar.
- Konteks probe harus persis konteks sumber masing-masing fokus. Kuota kelulusan,
  validitas konfirmasi dan ownership bukan tugas codec dan tetap wajib di domain.
- Sesi campuran diringkas **Profil campuran: P3, P6**, tidak memiliki `level=P3`
  atau `P6` palsu. Satu profil tetap berlabel ProfilPn, bukan tingkat anak.
- JSON parsial, duplikat field, field asing, versi asing/v1, fokus ambigu, nomor
  ganda/lompat dan container mutable ditolak. Pembaca v1 existing tidak diubah.
- Kontrak bersifat metadata tertanam; identitas sesi/siswa/tujuan/putaran/seed serta
  snapshot soal tetap disimpan oleh envelope domain saat integrasi kelak.

### Integrasi wajib sebelum writer v2 boleh aktif

| Jalur | Titik source saat ini | Kontrak penerimaan v2 yang masih harus dikerjakan |
| --- | --- | --- |
| Manual/gabungan | `web.py`, `database.buat_sesi*` | Pilihan eksplisit per butir; snapshot atomik; tidak pemetaan wajib |
| Terpandu | `learning_cycle.py`, `learning_cycle_service.py`, `learning_sessions.py` | Rekomendasi per tuntutan, dua fokus; seed/idempotensi mencakup kontrak; kuota fokus sumber |
| Latihan serupa/remedial | `teacher_pages.buat_sesi_seed_baru`, `database.buat_sesi_remedial` | Baca konteks sesi sumber beku, bukan profil/kemampuan terbaru |
| CLI | `generate_worksheet.py` | Render jujur kontrak baru; tidak menyamar sebagai v1 homogen |
| Pendamping | `assistant_actions.py`, `assistant_http.py`, `assistant_inline.py` | Payload usulan berversi, validasi ulang deterministik; usulan lama tidak ditafsir sebagai v2; tanpa tambahan data ke AI |
| Cetak/bagi/murid | `teacher_pages.halaman_lembar`, `worksheets.py`, `question_views.py`, `student_pages.py` | Cetak ulang memakai snapshot; anak hanya tahap netral, tanpa diagnosis/ID internal |
| Koreksi/pengiriman | `review_store.py`, `student_submissions.py`, `teacher_pages.simpan_sesi` | Konteks ikut ikatan revisi/provenance; tab stale ditolak tanpa efek samping |
| Konfirmasi | `database.konfirmasi_hasil`, `context_store.py`, `learning_cycle_service.py` | Arsip v2 append-only, fingerprint mencakup metadata baru, retry/crash atomik; jangan rusak retry v1/PG |
| Laporan/histori | `mastery_evidence.py`, `learning_cycle.py`, `context_report.py`, `reports.py`, `learning_history.py` | Status per tuntutan/versi, tanpa global level; bukti dicabut tidak hidup; penyebut hanya katalog disahkan |
| Admin/recovery | `admin_backup.py`, `admin_contracts.py`, `scripts/verify_release_image.py`, `scripts/verify_submission_pair.py` | Linkage/schema baru lengkap, FK/integrity/pair setelah penulisan v2; approval perubahan release terpisah |

Daftar ini bukan klaim caller sudah terintegrasi. Codec belum menyimpan sesi atau
memilih soal. Tidak cukup menghapus guard homogen dalam `context_store`/schema.

## 4. Migrasi, histori, dan batas recovery

Checkpoint ini **tanpa migrasi**. Tidak ada penulis v2, backfill, reset bukti,
perubahan schema/fingerprint existing atau rilis. Kontrak v1 dan histori tanpa
marker tetap dibaca dengan aturan lamanya. Dokumen ini tidak mengubah kebijakan
transisi putaran aktif; usulan aman adalah menyelesaikan putaran v1 melalui reader
v1, lalu membuka putaran baru eksplisit ketika v2 siap. Jangan mengubah tuntutan
sesi yang sudah dicetak atau membatalkan semua putaran otomatis.

Aktivasi v2 nanti memerlukan tabel/metadata aditif berversi, reader dua versi,
migrasi idempoten dalam transaksi yang gagal atomik, preservasi ID/hash histori,
FK/integrity dan replay konfirmasi/cetak. Bukti lama ambigu tetap histori, bukan
konfirmasi baru. Kasus `diganti_level` historis/invalidasi tidak dihapus.

Mode tetap **persiapan**, pasang false. Pin recovery PG belum kompatibel dengan
admin5/konteks kandidat existing, apalagi kontrak v2 baru. Tidak mengubah pin,
workflow, policy/probe atau deployer untuk menyembunyikan mismatch. Setelah writer
v2 aktif, recovery harus pembaca v2 yang teruji; rollback ke codec lama tidak
membuktikan keselamatan data. Lihat [panduan rilis](production-release.md).

Orphan admin tetap follow-up terpisah, tanpa melemahkan guard owner guru.
