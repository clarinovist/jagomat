# Statistika visual — Fase 3 internal

Catatan lanjutan: pemisahan provenance/bukti dan gate lintas keluarga dikerjakan
pada Fase 8. Status rilis terkini ada di `verifikasi-soal-visual.md`; daftar
blocker di bawah adalah catatan historis Fase 3, bukan status implementasi terbaru.

Catatan 21 Nov 2026: Flag visual menyala di produksi per `/opt/osn/visual.conf` (dibaca read-only 21 Nov 2026, berkas bertanggal 19 Nov): `OSN_VISUAL_KELUARGA=statistika,geometri-datar,geometri-ruang,pengukuran,kombinatorik,pola-bilangan`. Kalimat "fixture/internal pada fase ini" di bawah adalah catatan historis Fase 3, bukan status produksi.

## Cakupan

Empat renderer SVG deterministik: batang (baca/jumlah/selisih), turus
(baca/terbanyak/jumlah), piktogram (baca/total/selisih), dan lingkaran
(cari_nilai/cari_sudut). Tidak menambah grafik garis, pecahan piktogram,
atau jenis materi baru. Generator teks, kunci, malrule, dan golden tidak berubah.

`statistics_visual_data.py` memvalidasi allow-list per jenis/varian;
`topic_statistics_visual.py` memproyeksikan parameter menjadi fakta pertanyaan;
`statistics_svg.py` merender tanpa membaca kunci/DB. Snapshot tetap memakai
adapter dan renderer yang sama pada anak/share/guru/cetak/hasil/lampiran.

## Penggunaan terbatas dan blocker aktivasi

Default tetap teks. `OSN_VISUAL_KELUARGA=statistika` hanya untuk fixture/internal
pada fase ini, BUKAN rekomendasi menyalakannya di produksi. Nilai konfigurasi
asing ditolak. Mematikan konfigurasi menghentikan writer visual, tidak mengubah
snapshot visual yang sudah tersimpan; reader baru tetap dapat membacanya.

Sebelum aktivasi nyata wajib dituntaskan:

1. Outcome teks-v1 dan jenis-v1 belum dipisahkan dalam identitas fokus belajar.
   Jangan menganggap penguasaan membaca teks dan membaca diagram ekuivalen.
2. Reader image 67930f3 menolak descriptor baru. Rollback ke image itu tidak
   menjamin sesi visual tetap bisa dibuka. Deploy reader kompatibel dahulu
   dan uji matriks rollback setelah snapshot baru dibuat.
3. Alternatif nonvisual beridentitas terpisah dan uji pembaca layar penuh masih
   gate aksesibilitas/rollout. `desc` SVG tidak membocorkan angka yang harus dibaca.
4. HP fisik dan cetak kertas belum diuji. Viewport browser/PDF bukan penggantinya.

Tidak ada migrasi, backfill, perubahan konfigurasi, atau data anak produksi
pada pekerjaan Fase 3. Cerita LLM melewati butir visual agar fakta diagram tidak
kembali menjadi narasi angka; butir teks tetap dapat memperoleh cerita.

## Bukti pengujian

- TDD: test matematika SVG awal 35 gagal → 35 lulus; integrasi awal 8 gagal → hijau.
- Sweep statistika: 4 jenis × 4 level × 500 seed = 8.000 instans; kunci diturunkan
  secara independen dari geometri/jumlah objek SVG lalu dibandingkan kunci lama.
- Sweep generator semua topik: 9.800 instans, nol exception. Golden: 24 lulus.
- Mutation: turus +1, tinggi batang +1, sektor +1° masing-masing tertangkap;
  guard default nonvisual dan skip cerita juga terbukti merah ketika dimutasi.
- HTTP fixture: share/murid/guru/cetak, visual/fingerprint identik, simpan jawaban
  dan reload tidak mengubah snapshot; rollback gagal pembuatan tidak menyisakan sesi.
- Browser fixture halaman aplikasi: 4 permukaan × 320/390/1280px = 12 kombinasi,
  masing-masing empat SVG, nol overflow/label keluar viewBox. Preview keluarga
  juga diuji 768px. PDF A4 dihasilkan; screenshot diperiksa.
- Determinisme: 400 snapshot+SVG, dua proses dengan PYTHONHASHSEED berbeda,
  menghasilkan SHA256 identik.
- Trace final stdlib `--count --missing --summary`, 236 test lulus:
  statistics_svg 105 baris/99%, statistics_visual_data 106/94%,
  topic_statistics_visual 152/94%, question_views 140/92%,
  visual_contract 370/94%, visual_renderer 141/91%. Denominator adalah baris
  executable menurut trace; bukan branch coverage. Baris tersisa terutama
  penolakan input/guard defensif yang belum dieksekusi oleh subset test trace.
- Suite penuh final: 6.363 passed, 31,97s, Python 3.9, `-W error`.
  Kompilasi seluruh modul dan `git diff --check` lulus.
- Review spesifikasi dan kualitas independen menyetujui scope internal/fixture;
  temuan surrogate diperbaiki dengan test RED/GREEN. Tombol variasi cerita
  tidak ditawarkan bila semua butir visual/sudah punya cerita.
- Mutation dispatch SVG dikosongkan: E2E HTTP merah; pemulihan 12 test hijau.

Hasil final dan commit dicatat dalam plan eksekusi lokal. Dokumen ini tidak
mengklaim aktivasi produksi atau penyelesaian Fase 4–8.
