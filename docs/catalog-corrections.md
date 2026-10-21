# Koreksi katalog soal dan perlindungan histori

Status: **Batch A–C diimplementasikan, writer baru belum diaktifkan**. Audit
semantik mendalam hanya subset, bukan sertifikasi seluruh 97 template.
Tidak ada koreksi otomatis terhadap data historis.

## Kontrak versi konten

`catalog_versions.py` memisahkan versi konten dari versi matematika pengukuran/
geometri existing. Parameter `versi_katalog=2` ikut tanda tangan bank, sehingga
kunci/malrule baru tidak memakai ID soal lama. Tanpa marker, fungsi historis tetap
dipakai, termasuk pembahasan; reader tidak membaca flag writer.

`OSN_KATALOG_VERSI` hanya menerima `1` atau `2`. Bawaan masih `1` (jembatan reader).
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
writer2 menambah bank lama/baru, PG, konfirmasi dan pembahasan ke C→B→C. Reader yang
belum mendukung marker diblokir eksplisit sebelum memuat data. Writer1 masih
memakai jalur existing. Tes source bukan bukti pasangan image exact sudah lulus.

Recovery pinned belum mendukung katalog baru. **Jangan aktifkan/deploy writer2**
sebelum reader jembatan, full CI/build, review manusia konten berubah dan gate
pasangan exact lulus. Pin tidak diubah untuk meloloskan gate; review versi sebelumnya
tidak mengesahkan konten baru. Tidak ada runtime LLM untuk kunci/diagnosis.

## Batas dan follow-up

- Kewajaran ayah12/anak3 sudah ditangani pada soal baru dengan melepas hubungan
  keluarga (Ari/Bima); histori lama tidak ditulis ulang. Contoh baru tetap menunggu
  tinjauan manusia. Ekspor `scripts/catalog_preview.py` menghasilkan HTML dan
  manifest hash konten yang terikat SHA; disertakan pada artefak CI.
- Cabang tabung existing, pembagian pecahan terpotong di rule lain, dan template
  tak ditandai tidak otomatis benar. Audit lanjutan di luar temuan ini tetap perlu.
- Second opinion JEV atas ringkasan nonsensitif mendukung usulan kategori terbatas
  dan rule jenis unsur. Itu sinyal probabilistik, bukan review manusia atau gate.
