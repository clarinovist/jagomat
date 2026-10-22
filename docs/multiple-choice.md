# Pilihan ganda manual

Orang tua memilih **Format jawaban → Pilihan ganda (3–5 opsi)** pada form sesi
manual atau gabungan topik. Default tetap Isian; sesi terpandu/Pendamping tetap
isian. Tidak ada JavaScript atau layanan AI tambahan untuk membentuk opsi.

## Perilaku

- Jumlah opsi ditetapkan oleh pola/varian, bukan diturunkan ketika kandidat kurang.
  Tiga untuk pola yang ruang pengecohnya terbatas; umumnya empat; lima untuk
  pengandaian dan jaring-jaring yang sudah memakai A–E.
- Anak memilih satu jawaban; **Belum menjawab** mengosongkan pilihan. Cara dan
  catatan boleh kosong. Simpan sementara tidak memberi diagnosis; finalisasi
  boleh memuat butir kosong dan tetap mengarsipkan semua butir.
- Kecocokan pilihan tidak otomatis menjadi diagnosis atau bukti pemahaman.
  Hasil PG tidak masuk pemetaan, penguasaan, atau remedial otomatis. Lihat
  [kontrak siklus](siklus-belajar-terpandu.md).
- Opsi dan urutannya immutable per butir, sama di layar/cetak/tinjauan.
  Penilaian guru menampilkan label dan nilai. Foto memakai konfirmasi pilihan
  manual; hasil OCR tidak diterapkan sebagai huruf/nilai secara otomatis.
  Form upload guru/akun anak disembunyikan pada PG tanpa lampiran; lampiran lama
  tetap dapat dibuka dan dikonfirmasi manual (kartu PG selalu terbuka), tanpa
  perubahan handler maupun kapabilitas tautan anak.
- Setelah pengiriman, koreksi harus melalui tinjauan dengan sumber koreksi
  transkripsi; hasil setelah bantuan tetap terpisah dari pekerjaan asli.

## Pembentukan dan integritas

`choice_generation.py` memilih kebijakan serta kandidat dari malrule atau
kategori yang memang ada pada soal. Tambahan khusus tabung tanpa titik sudut:
pengecoh menghitung dua alas/tutup sebagai titik sudut (dikalikan jumlah tabung
untuk varian banyak tabung). Modus boleh menambah nilai lain yang memang ada
pada data sebagai kandidat PG, tanpa menambah label diagnosis atau mengarang
malrule isian. Jumlah opsi tetap empat; bila kandidat kurang, retry terbatas
memakai cabang yang sama. Tidak mengubah malrule atau template isian.
Kandidat setara dan bentuk yang tidak didukung disaring; parameter dapat diulang
terbatas pada template, cabang, kelas, dan kebijakan jumlah yang sama. Kekurangan
tetap gagal atomik dengan pesan untuk memakai isian, bukan mengganti materi.

`multiple_choice.py` membentuk opsi terkurasi dan memeriksa kesetaraan bertipe.
`choice_contract.py` membaca snapshot publik tanpa mengimpor kunci/template.
`choice_store.py` mengikat snapshot ke butir/penyajian dan memeriksa kepemilikan
siswa; caller HTTP tetap menegakkan peran dan kepemilikan keluarga.

Nilai jawaban kanonis tersimpan di tabel jawaban. ID/label pilihan diturunkan
secara unik dari snapshot immutable, bukan kolom duplikat mutable. Tabel
`pengiriman_pilihan` dan `konfirmasi_pilihan` menyimpan salinan opsi untuk replay.
Snapshot hilang/rusak bukan fallback isian dan tidak diregenerasi saat dibaca.

Sisi anak tentu melihat nilai kunci sebagai salah satu opsi, tetapi tidak
mendapat penanda opsi benar, ID malrule, kode diagnosis, atau alasan guru.

## Rilis

Perubahan skema membutuhkan pasangan recovery baru yang diuji sebelum pemasangan.
Fase persiapan/build-only recovery PG adalah histori yang telah dilanjutkan oleh
rilis profil/katalog. Pada rilis22Oktober mode source **migrasi**, recovery pinned
`edd323c` dan pasangan exact telah lolos gate. Jangan memakai baseline PG lama
untuk skema sekarang. Job pasang otomatis tetap nonaktif; pin/digest otoritatif
ada di metadata dan [status rilis](production-release.md).
Pada setiap rilis migrasi/rutin, uji pasangan tetap wajib mencakup sesi PG dan arsipnya,
selain metadata baru. Push tidak sama dengan deploy. Jangan downgrade ke pembaca
pra-PG setelah data PG terbuat. Pemulihan mempertahankan reader dan arsip, bukan
menghapus data PG.
