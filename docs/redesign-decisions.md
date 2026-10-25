# Keputusan redesain admin

Acuan: `redesign-plan.md` dan brief privat 19 Oktober 2026. Semua fase disetujui
pengguna; hasil branch awal untuk review tanpa deploy. **Pembaruan 22 Oktober:**
branch sudah diintegrasikan dan tercakup rilis `ccb8906`; lihat [verifikasi](redesign-verification.md).
Keputusan bernomor berikut mencatat keadaan/desain fase awal. Antrean per-item,
badge/sidebar dan hitungan facet kemudian berkembang; peta implementasi terbaru
ada di [arsitektur](architecture-reference.md). Opsi global search/assignment
yang dikecualikan tetap bukan fitur tersedia.

**Keputusan lanjutan setelah audit25 Oktober:** pengguna meminta satu design system.
Admin kini memakai token terang, logo, tipografi dewasa, radius, spacing dan ukuran
kontrol Jagomat bersama. `ADMIN_*` hanya adapter warna terang/gelap, bukan palet/skala
independen. Ini menggantikan isolasi fondasi visual pada poin1; batas font privat,
form/POST, akses dan keputusan operasional lain tetap. Kontrak aktif ada di
[design system](design-system.md).

1. **Font:** gunakan font sistem existing, bukan Google Fonts. Mockup mengasumsikan
   Be Vietnam Pro aktif; panel privat sebenarnya tanpa aset eksternal. Tema admin
   mendapat token scoped agar halaman orang tua/murid tidak ikut berubah.
   Menu akun tetap satu disclosure di atas, bukan menduplikasi form logout antara
   sidebar/mobile; footer privat hanya sekali.
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
   Badge Ringkasan tidak direka pada halaman lain: shell tidak menerima total
   antrean global. Total kategori yang sah tampil di kartu Ringkasan.
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
10. **Review:** ID panjang tetap teks lengkap yang dapat dipilih/disalin, bukan
    elipsis dengan ID hanya di tooltip; tidak menambah JS clipboard. Status login
    memakai "Belum ada login tertaut" dengan catatan akun lama mungkin masih bisa
    masuk melalui kecocokan nama. Ini menjaga makna query existing tanpa jargon
    "eksplisit" yang membingungkan. Hover bahaya diberi selector khusus agar
    teks putih tidak jatuh pada latar terang.
11. **Gate pada penutupan branch awal (historis):** instruksi terbaru pengguna menahan push sampai seluruh fase
    selesai. Seluruh pekerjaan dan commit tetap lokal. Full suite CI/build belum
    dijalankan; bukan klaim siap deploy atau seluruh gate rilis hijau.
