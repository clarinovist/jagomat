# Koreksi katalog soal dan perlindungan histori

Status: **konten Batch A–C disetujui manusia dan writer2 aktif di produksi**
pada kandidat `1472f8c` (21 Oktober 2026). Audit
semantik mendalam hanya subset, bukan sertifikasi seluruh 97 template.
Tidak ada koreksi otomatis terhadap data historis.

## Kontrak versi konten

`catalog_versions.py` memisahkan versi konten dari versi matematika pengukuran/
geometri existing. Parameter `versi_katalog=2` ikut tanda tangan bank, sehingga
kunci/malrule baru tidak memakai ID soal lama. Tanpa marker, fungsi historis tetap
dipakai, termasuk pembahasan; reader tidak membaca flag writer.

`OSN_KATALOG_VERSI` hanya menerima `1` atau `2`. Bawaan kandidat kini `2`, recovery
`edd323c` tetap `1`; tidak memasang override bersama yang mengaktifkan recovery.
`2` memilih koreksi untuk 26 template terdaftar, tidak mengubah rentang parameter
atau komposisi. Pengukuran, jaring, perbandingan volume dan tabung mensyaratkan
matematika versi2; kombinasi tidak didukung ditolak, bukan memakai kunci warisan.
Tidak ada migrasi/backfill bank, snapshot, konteks, outcome atau diagnosis.

## Batch A — kunci, teks, pembahasan

- Umur: rasio memakai kedua umur pada waktu yang diminta, bukan k×umur anak
  sekarang. Pembahasan menunjukkan substitusi. Soal baru memakai Ari/Bima tanpa
  hubungan keluarga dengan marker `konteks_umur=dua_orang_v1`; angka dan RNG tetap.
  Tanpa marker, pembacaan katalog2 ayah–anak lama tetap persis. Kandidat besaran
  berbeda memakai ID prosedur baru, tanpa memetakan ulang fokus/malrule historis.
- Senilai, berbalik dan kerja bersama: hasil rasional eksak, tanpa ceiling.
- Lingkaran/juring: π sesuai fakta soal dihitung rasional, tanpa pembulatan satu
  desimal tersembunyi. Teks biasa maupun visual menyebut jawaban tanpa pembulatan.
- Paritas: deret/rentang existing tetap; istilah genap/ganjil mengikuti suku awal.
  Pembahasan memakai suku terakhir berjarak2. Tidak memperlebar rentang atau
  menurunkan guard200 yang akan bertentangan jika domain dipaksa ganjil saja.
- Kartu umur/juring/paritas diperjelas; contoh kerja bersama eksak. Kartu adalah
  bantuan kini, bukan snapshot jawaban/diagnosis historis.

`catalog_exact.py` memformat desimal berhingga utuh dan pecahan berulang sebagai
`a/b`, tanpa float. Diagnosis menerima pecahan/desimal ekuivalen hanya untuk
skalar pada template+versi yang eksplisit; tidak menafsirkan ekspresi, daftar,
notasi ilmiah atau satuan asing. Reader histori tetap memakai pencocokan lama.

## Batch B — arti malrule

- Median, rata-rata gabungan, batang, turus, piktogram, jangkauan dan jumlah–selisih:
  kandidat mengikuti prosedur tertulis, collision dibuang, tidak dinudge.
- FPB: kandidat faktor bersama kecil benar-benar membagi kedua angka.
- Prisma balik: lupa setengah berarti membagi volume dengan alas×tinggi segitiga.
- Unsur: pertukaran bangun bernilai sama dan nol×n bukan miskonsepsi. Jika tidak ada
  pembeda, kandidat menghitung jenis unsur lain pada bangun yang sama diberi alasan
  eksplisit; bukan angka arbitrer. H tetap ±1 nonnegatif atau dihilangkan.
- Cari faktor panjang: rule membagi faktor volume dengan3 dijelaskan sesuai operasi,
  bukan disebut memakai faktor panjang untuk volume.
- Skala: lupa km→cm benar-benar mengikuti rasio/pembagian tanpa konversi.
- Waktu: angka durasi dan alasan sesuai komponen yang diabaikan; pembalikan
  konversi rasional tidak dipotong untuk memaksa opsi. PG tetap memakai guard jumlah
  opsi existing, tanpa pengecoh acak atau pengurangan jumlah opsi.

## Batch C — diagnosis dan Medium terkonfirmasi

- Jaring: semua pola salah yang bertumpuk diberi usulan konsep lipatan K; ID melekat
  pola, bukan huruf/ordinal. Jawaban tidak membuktikan penyebab tanpa tinjauan guru.
- Pengandaian: usulan kesimpulan K, bukan H tanpa perhitungan. Warna dibatasi satu
  warna; bekal tambahan/cuaca tidak dijamin fakta, penyangkalan bertentangan.
- Jumlah deret: malrule rata-rata ujung eksak, tidak floor tersembunyi.
- Kotak tepi: setiap sel batas dihitung sekali, kode K untuk isi vs tepi.
- Konversi satuan: faktor60 pada waktu, faktor1000 pada pasangan metrik terkait.
- Korek: fallback teks memakai pola bertumbuh generik, bukan klaim segitiga yang
  tidak sesuai sampler. Visual existing juga tetap generik.

## Verifikasi dan gate aktivasi

Tes `test_catalog_keys`, `malrules`, `diagnosis` memakai invariant dari fakta
mentah, bukan expected yang menyalin rumus rusak. Mutation terisolasi mematikan
kunci, presisi, prosedur, kategori, identitas dan pemisahan reader/writer.
`test_catalog_integration` menyapu seed×level, visual, PG, bank, diagnosis,
pembahasan/cetak serta konfirmasi/outcome/konteks dengan data sintetis.
Baseline kualitas generik yang sama diuji pada kedua writer, tanpa penurunan guard.

Probe `release_catalog_pair.py` terhubung ke `release_question_pair.py`:
probe selalu mengaktifkan writer2 hanya dalam proses sandbox sintetis dan
memulihkan flag setelah menambah bank lama/baru, PG, konfirmasi dan pembahasan ke
C→B→C. Gate tidak boleh lolos karena default writer1. Reader yang belum mendukung
marker diblokir eksplisit sebelum memuat data. Tes source bukan bukti image exact.

Recovery pinned `edd323c4822347f6d584bb0f311e76cac4962e40` mendukung katalog2,
kedua konteks umur dan validator pilot kisi; tetap menulis katalog1/komposisi1.
Baseline ini lulus CI39609036312 dalam mode persiapan sebelum dipatok kandidat;
koleksi13.896 tes diukur dari arsip dan identik empat manifest CI.
Tinjauan manusia dinyatakan disetujui pengguna pada paket hash
`6522bc48bc9cce2c8edcf354fa1a50adf7b317ea8c6a9a2c83c1097d039e32bc`.
Aktivasi produksi tetap memerlukan full CI/build kandidat aktif, gate pasangan
exact, preflight, backup/rehearsal, dan cutover terkontrol. Persetujuan ini bukan
bukti deployment dan tidak mencakup perubahan konten berikutnya.
Deployment `1472f8c` telah lulus CI39610870417, pair exact dengan recoveryedd323c,
backup/rehearsal dan smoke produksi; rincian bukti pada [runbook](production-release.md). Pin tidak diubah untuk meloloskan gate; review versi sebelumnya
tidak mengesahkan konten baru. Tidak ada runtime LLM untuk kunci/diagnosis.

## Kompatibilitas pilot keterampilan

Aktivasi default menemukan validator kisi pilot yang masih menolak marker katalog2.
Reader kini menerima tepat marker2 pada sumber kisi yang sah, tanpa mengubah sidik
ukuran atau melonggarkan field/rentang. Fokus tepi K baru dan H historis tetap
dibedakan oleh kode; selector mencocokkan malrule aktual. Baseline recovery berikutnya
sudah memuat reader ini sebelum kandidat aktif dirilis. Tidak ada retag bukti lama.

## Batas dan follow-up

- Kewajaran ayah12/anak3 sudah ditangani pada soal baru dengan melepas hubungan
  keluarga (Ari/Bima); histori lama tidak ditulis ulang. Contoh baru sudah ditinjau
  dan disetujui pengguna pada hash di atas. Ekspor `scripts/catalog_preview.py` menghasilkan HTML dan
  manifest hash konten yang terikat SHA; disertakan pada artefak CI.
- Cabang tabung existing, pembagian pecahan terpotong di rule lain, dan template
  tak ditandai tidak otomatis benar. Audit lanjutan di luar temuan ini tetap perlu.
- Second opinion JEV atas ringkasan nonsensitif mendukung usulan kategori terbatas
  dan rule jenis unsur. Itu sinyal probabilistik, bukan review manusia atau gate.
