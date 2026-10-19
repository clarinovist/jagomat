# Keputusan redesain admin

Acuan: `redesign-plan.md` dan brief privat 19 Oktober 2026. Semua fase disetujui
pengguna; hasil branch untuk review, tanpa deploy.

1. **Font:** gunakan font sistem existing, bukan Google Fonts. Mockup mengasumsikan
   Be Vietnam Pro aktif; panel privat sebenarnya tanpa aset eksternal. Tema admin
   mendapat token scoped agar halaman orang tua/murid tidak ikut berubah.
2. **Form privat:** cari keluarga/siswa dan langganan tetap POST; nama tidak masuk
   URL. Chip hanya menuju filter yang backend sudah dukung; saat pencarian aktif,
   pertahankan form/pager POST. Dimensi tambahan tetap tersedia di disclosure.
   `normal`/gabungan perhatian siswa belum tersedia, jadi tidak ada chip palsu.
   Total filter aktif ditampilkan, count semua facet tidak direka dari halaman 25.
3. **Antrean:** satu kategori satu baris, label total menghitung kategori, bukan
   entitas unik. Sumber gabungan operasi/pembayaran tidak disebut invoice saja.
   Rincian jumlah kondisi bisa overlap; jangan menjumlahkan menjadi orang unik.
   Waktu awal masalah tidak tersedia, sehingga umur tampil —. Backup Ringkasan
   hanya mengarahkan ke pemeriksaan, tidak diasumsikan gagal/terverifikasi.
4. **Pendaftaran:** pesan merupakan pilihan `pesan_kode`, bukan judul/textarea bebas.
   Preview statis menampilkan pesan tersimpan; tidak menambah field atau JavaScript.
5. **AI:** `dihentikan` adalah checkbox pada form pengaturan. Tampilan kendali
   penghentian dipisah secara visual, tetapi tetap form/payload yang sama, tanpa
   endpoint atau tombol kedua yang dapat mengirim form berbeda. Nilai input USD
   tetap desimal titik; hanya teks uang diformat koma.
6. **Riset:** ekspor CSV/JSON tetap form POST signed. Boleh dipindah ke header,
   tidak diganti GET. Persetujuan wawancara/rekaman tetap terpisah.
7. **Opsional:** deteksi duplikat alias, assignment, pencarian global, tambahan
   query kartu belum diikutkan/banner invoice ditunda. Menu tetap Langganan.
8. **Fitur existing:** sensor KPI, biaya/eksperimen, bulk CSV, detail/tinjauan,
   filter lanjutan, arsip, dan semua guardrail tetap tersedia walaupun tidak
   tergambar dalam mockup. Tidak mengurutkan ulang data lintas halaman di renderer
   karena akan menyiratkan urutan global palsu; urutan kanonis query dipertahankan.
9. **Isolasi:** main memiliki WIP sesi lain. Branch dikerjakan pada worktree
   saudara; venv yang sama dipakai via path absolut, tidak memasang dependency.
