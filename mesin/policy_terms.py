"""Syarat penggunaan publik untuk cakupan layanan Jagomat yang nyata."""

def halaman():
    from landing import _halaman_publik_stitch,_topbar_publik_st
    isi=('<main class="dukungan-editorial-st"><div class="publik-bungkus-st">'+_topbar_publik_st()+
         '<section class="publik-kartu-st lebar"><h1>Syarat Penggunaan</h1>'
         '<p>Versi jagomat-2026-10-18-v2 · Berlaku untuk kesepakatan baru yang diterima pengguna.</p>'
         '<h2>Siapa yang menggunakan</h2><p>Akun pendamping digunakan orang tua/wali atau pendidik '
         'yang memiliki izin orang tua/wali untuk data anak. Anak tidak mendaftar sendiri. '
         'Gunakan nama panggilan; jaga sandi dan akses akun.</p>'
         '<h2>Layanan dan batasnya</h2><p>Jagomat menyediakan latihan, tinjauan dan langkah belajar '
         'berbasis bukti. Akses awal nonkomersial tidak mengaktifkan pembayaran atau langganan. '
         'Kami tidak menjamin nilai ujian, kemenangan lomba atau penguasaan seluruh kurikulum. '
         'Usulan AI perlu ditinjau; kunci dan keputusan belajar tidak diserahkan kepada chatbot.</p>'
         '<h2>Data dan pilihan Anda</h2><p>Pemrosesan untuk menyediakan layanan dijelaskan dalam '
         '<a href="/kebijakan-privasi">Kebijakan Privasi</a>. Penggunaan tambahan untuk perbaikan '
         'produk mengikuti pilihan pada layar persetujuan. Tombol Setuju &amp; aktifkan semua '
         'menyetujui penggunaan opsional yang disebutkan secara jelas, bukan penggunaan apa pun. '
         'Menolak atau mencabut analitik tidak mengurangi fitur belajar inti. Pengaturan tersedia di Akun.</p>'
         '<h2>Batas penggunaan</h2><p>Jangan mengakses data keluarga lain, menyalahgunakan akun, '
         'mengunggah data yang tidak berhak Anda gunakan, atau mengganggu keamanan layanan. '
         'Data tidak menjadi milik Jagomat hanya karena Anda menyetujui syarat ini.</p>'
         '<h2>Perubahan dan bantuan</h2><p>Perubahan material tujuan pemrosesan diberitahukan sebelum '
         'diberlakukan dan memerlukan dasar pemrosesan serta pilihan yang sesuai. Restart biasa '
         'tidak memerlukan persetujuan ulang. Pemulihan backup dapat meminta konfirmasi kembali '
         'untuk mencegah izin yang telah dicabut aktif kembali. Informasi penghapusan dan kanal '
         'bantuan tercantum pada Kebijakan Privasi. Hak pengguna yang diwajibkan hukum tetap berlaku.</p>'
         '</section></div></main>')
    return _halaman_publik_stitch('Syarat Penggunaan — Jagomat',isi)
