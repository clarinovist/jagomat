# Audit katalog lanjutan — 24 Oktober 2026

## Status

Audit terbatas pada kuantitas, rata-rata, arsiran, tabung, pecahan dan pembagian
berkurung. Bukan pengesahan seluruh97 template. **Draf revisi penilaian2 belum
direview manusia dan writer default nonaktif** (`OSN_KATALOG_LANJUTAN=0`).
Fondasi source `c335ce5` telah dipasang24 Oktober, tetapi kedua writer revisi1/2
terverifikasi nonaktif. Bukti exact CI/deployment di [runbook](production-release.md).
Izin deploy fondasi tidak mengesahkan atau mengaktifkan isi baru.

## Temuan terkonfirmasi dan tindakan

| Area | Contoh sintetis pada writer aktif | Tindakan |
| --- | --- | --- |
| Kuantitas | P4 seed1:100 lembar→kodi; malrule faktor12 menyimpan8, bukan100/12=25/3 | Draf2 memakai rasional eksak dan ID baru |
| Rata-rata | P4 seed1:jumlah301, banyak7; malrule bagi8 menyimpan37, bukan37,625 | Draf2 memakai prosedur `n+1` eksak |
| Data terakhir | P4 seed0:malrule K hanya kunci+1, tanpa prosedur konsep spesifik | Draf2 mengabaikan satu data diketahui saat mengurangi total; bukan angka nudge |
| Arsiran | P5 seed1:r7; mengganti π menjadi3,14 menghasilkan42,14, bukan42,1 | Draf2 tanpa pembulatan tambahan |
| Arsiran teks | Daerah diarsir tidak dijelaskan pada fallback tanpa diagram | Teks draf2 menyebut daerah di dalam persegi dan di luar empat seperempat lingkaran |
| LP tabung balik | P5 seed19:r7, LP1100; malrule LP/luas alas=50/7 dipotong7 | Sudah ada koreksi revisi1 nonaktif; tidak diduplikasi/diaktifkan |
| Pecahan | Revisi0 menolak beberapa penulisan pecahan ekuivalen; alasan kali tidak menggambarkan penyesuaian pembilang yang sesungguhnya | Revisi1 existing menyediakan codec/prosedur baru; tetap menunggu review/aktivasi |
| Operasi berkurung | Malrule membagi seluruh hasil memakai floor, walau prosedur menghasilkan pecahan | Follow-up, belum diperbaiki dalam draf2 |
| Volume tabung | Angka sampel cocok rumus, tetapi label faktor/prosedur terlalu umum dan bisa tidak sesuai cabang balik | Follow-up penjelasan; bukan klaim kunci volume salah |

Probe baseline awal:600 seed×18 konteks=10.800 soal pada delapan template;
operasi berkurung diperiksa tambahan terpisah. Ketiadaan ketidakcocokan di probe
angka bukan bukti seluruh bahasa/prosedur benar. Pembanding independen hanya
memeriksa dimensi yang disebut, tidak menyatakan efektivitas diagnosis anak.

## Kontrak draf2

- Cakupan hanya `satuan_kuantitas`, `rata_rata`, `luas_arsiran`; tidak menambah
  jenis, memperlebar parameter, mengubah komposisi, atau mengaktifkan revisi1.
- Marker `revisi_penilaian=2` masuk tanda tangan bank. Parameter tanpa marker
  tetap fungsi lama; reader tidak membaca flag writer. Tidak ada backfill bank,
  snapshot/outcome, keputusan guru, pembahasan atau diagnosis historis.
- Kunci tidak diubah; malrule2 ber-ID `rev2.*` mengikuti prosedur literal. Semua
  collision numerik dan kandidat setara kunci dibuang, bukan memilih pertama
  atau menggeser angka. Codec rasional eksak existing dipakai hanya pada marker sah.
- Label H/K tetap **draf untuk review manusia**, bukan penetapan bahwa prosedur
  itu benar-benar dipakai anak. Contoh π salah tetap H seperti histori; kelayakan
  kategorinya harus ditinjau, tidak disimpulkan dari tes numerik.
- Proyektor arsiran memvalidasi marker sebelum membuangnya; geometri/diagram
  tetap sama. Kunci, malrule dan metadata guru tidak menjadi descriptor publik.
- Revisi1 tetap arti/cakupan sebelumnya. Marker2 ditolak pada target lain;
  boolean/string/versi tidak dikenal ditolak. Flag writer invalid gagal terlihat.

## Verifikasi dan batas aktivasi

Tes baru: `test_catalog_followup.py`, `stress`, `mutation`, `preview`. Cakupan:
600 seed×8 konteks, solver kunci/prosedur independen, collision, ekuivalensi,
K≥98%, replay reader, bank lama/baru, snapshot outcome tidak berubah, render
25 seed/konteks dan PG. Mutasi terisolasi membuktikan floor, pembulatan, K+1,
filter collision, default aktif dan marker hilang tertangkap. Golden/default
serta gate domain existing tidak diturunkan.

Sebelum aktivasi: review manusia terhadap isi exact, recovery reader marker2,
probe C→B→C konten2 dan pasangan image exact, gate lengkap serta preflight/backup
sesuai runbook. **Recovery pinned saat penulisan belum mendukung marker2.**
Karena itu rilis fondasi hanya boleh dengan writer0; tidak ada alasan mengaktifkan
flag di produksi demi mempercepat penutupan backlog.

## Paket review

Jalankan dari akar repo (output baru, tidak menimpa):

```bash
mesin/.venv/bin/python -B scripts/catalog_followup_preview.py --output /tmp/jagomat-review-katalog2-baru
```

34 pasangan contoh sebelum/draf meliputi varian dan level target. Manifest berisi
source SHA, status WIP/committed dan hash konten; bukan metadata pengesahan.
Reviewer manusia mencatat setuju/ubah/tolak dan alasan atas isi exact; hash bukan
bukti manusia sudah memeriksa. Sampel ini bukan pembuktian semua varian pedagogis.

Acuan: [katalog](catalog-corrections.md), [pilot revisi1](catalog-pilot.md),
[status proyek](status-proyek.md), [workflow soal](workflow-reference.md#soal--baca-sebelum-mengubah-topikgeneratortemplate).
