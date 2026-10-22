# Verifikasi penyajian soal — Fase 1–2

**Catatan historis fase1–2.** Scope visual/bukti kemudian dilanjutkan pada
[Fase8](verifikasi-soal-visual.md). Status pekerjaan dan pembatalan di
[status proyek](status-proyek.md). Pernyataan aktivasi/nonvisual awal bukan status
konfigurasi sekarang, dan dokumen ini bukan perintah backfill produksi.

## Cakupan

Snapshot per `sesi_soal` dan satu renderer aman seluruh permukaan sesi. Writer default tetap `teks-v1`, tanpa aktivasi keluarga diagram baru. Descriptor korek/titik tersedia sebagai jembatan teruji dengan fixture. Fase 3–8 bukan bagian penyelesaian ini.

## Matriks jalur

| Permukaan | Jalur data/tampilan | Bukti |
|---|---|---|
| Anak diagnostik/drill lama & Stitch | students.soal_murid → PenyajianPertanyaan → visual_renderer | test_students, test_presentation_surfaces/http |
| Share satu sesi | handler /mulai → halaman anak yang sama | test_share_link, test_presentation_http |
| Cetak/layar/PDF sesi | halaman_lembar → question_views → Soal.penyajian → render → visual_renderer | test_web_worksheet, test_presentation_surfaces/http |
| Koreksi guru/pengelola | halaman_sesi → adapter snapshot → visual_renderer | test_presentation_surfaces/http |
| Hasil anak setelah review | hasil_murid → penyajian → visual_renderer | test_murid_pembahasan, test_presentation_surfaces |
| Campuran/gabungan/remedial/siklus | semua pembuat sesi → _simpan_butir_sesi | test_snapshot_writer, test_learning_cycle_* |
| Konteks foto | query whitelist penyajian_sesi_aman → ringkasan_pertanyaan | test_presentation_surfaces + SQLite authorizer |
| Konfirmasi foto | _soal_konteks → snapshot → visual_renderer | test_presentation_surfaces |

Laporan tidak merender badan pertanyaan; jalur diagnosis tetap terpisah. CLI lembar tanpa sesi mempertahankan adapter renderer topik lama. Snapshot sesi tidak memakai jalur tersebut.

## Integritas

- Snapshot all-or-none; field, JSON kanonis, dan fingerprint divalidasi.
- Cerita ditulis per sesi dengan CAS, bukan ke bank bersama.
- Sesi mulai, selesai, dicetak, dibatalkan, memiliki jawaban/bukti/konfirmasi dikunci. Penguncian mencakup identitas soal dan nomor.
- Startup migrasi atomik tanpa implicit commit executescript; kegagalan skema diuji pada database baru dan warisan.
- Backfill eksplisit, tidak berjalan otomatis pada startup. Teks warisan dibekukan sesuai keadaan migrasi; bukan klaim rekonstruksi historis persis.

## Bukti lokal

- Unit/integrasi/E2E HTTP lewat pytest Python 3.9: 6.204 passed, warning dijadikan error.
- Mutasi bypass snapshot cetak dan renderer anak benar-benar membuat test merah; pemulihan membuatnya hijau.
- Sweep 9.800 instans di dua PYTHONHASHSEED menghasilkan hash identik.
- Trace stdlib dengan `--missing`: kontrak 93%, renderer 92%, adapter 91%, lock 92%, backfill 85%. Ini line execution, bukan branch coverage.
- Browser fixture: lima permukaan × 320/390/768/1280 px, 20 kombinasi tanpa overflow; CSS SVG diperbaiki dari tinggi tetap menjadi proporsional. Screenshot HP diperiksa dan PDF A4 berhasil dibuat.
- Backup produksi diuji hanya pada salinan sementara: 451 snapshot lengkap/fingerprint valid, integrity_check ok, foreign_key_check 0, migrasi dan backfill ulang idempoten.

## Batas dan deploy

- HP fisik serta hasil cetak kertas belum diuji; browser responsif/PDF bukan pengganti keduanya.
- Korek fixture masih membutuhkan penanda batas ruas yang jelas sebelum aktivasi Fase 7; jumlah ruas matematis saja belum membuktikan keterbacaan ruas yang segaris.
- Tidak ada aktivasi SVG otomatis untuk sesi baru pada fase ini. Lembar sesi yang sebelumnya menyisipkan SVG korek/titik dari renderer topik kini mengikuti snapshot teks, sama dengan anak/guru. Isian deret tetap berupa karakter garis bawah dari teks snapshot, bukan span khusus renderer lama. Ini transisi nonvisual eksplisit, bukan klaim bahwa gambar lama sudah dibekukan. CLI tanpa sesi tetap kompatibel.
- Deploy additive tanpa backfill dapat melayani sesi warisan, tetapi tampilan baris all-NULL masih direkonstruksi. Backfill tidak wajib untuk startup, namun wajib sebelum mengklaim seluruh histori stabil terhadap perubahan template berikutnya.
- Build image dan smoke container menjadi gate CI/deploy integrator. Uji lokal bukan klaim produksi sudah berubah.
- Sebelum rilis skema, gunakan [runbook aktif](production-release.md): backup coherent
  seluruh state durable, rehearsal dan pasangan image exact. `cadangkan.sh` dua DB
  lama tidak memenuhi bundle saat ini. Push bukan izin mengubah data.
- Backfill bukan langkah otomatis setiap deploy. Jika diperlukan dan diotorisasi,
  preview target/backup dan tahan writer. Pada helper backfill fase ini, gunakan
  satu `BEGIN IMMEDIATE`, panggil `jalankan` lalu `verifikasi` sebelum commit;
  buktikan idempotensi, preservasi/integritas dan smoke. Jangan mengulang backfill historis
  hanya karena checkbox fase ini belum diperbarui.
