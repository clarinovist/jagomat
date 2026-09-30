# Operasi dukungan akun dan permintaan hak data

Dokumen ini adalah runbook manusia. WhatsApp Business hanya kanal komunikasi;
bukan autentikasi, bukan tempat menyimpan profil kontak, dan tidak terhubung ke
WhatsApp API atau pengiriman otomatis.

## Jadwal dan SLA

- Layanan: **Senin–Jumat, 09.00–17.00 WIB**.
- Respons awal: maksimal **1 hari kerja**.
- Status atau penyelesaian awal: maksimal **3 hari kerja**.
- Operator utama memantau kanal pada jam layanan. Pengganti yang ditunjuk memakai
  akun adminnya sendiri; credential dan sesi admin tidak boleh dibagikan.
- Bila kanal tidak tersedia, operator menutup pendaftaran baru melalui kontrol
  existing. Login keluarga yang sudah ada tidak ditutup hanya karena kanal gagal.

## Minimisasi data tiket

Catat hanya waktu, kategori permintaan, status, operator, dan referensi operasi
internal bila tindakan panel dilakukan. Jangan menyalin isi latihan, diagnosis,
foto, chat, sandi, token, atau identitas anak ke sistem catatan di luar Jagomat.
Jangan meminta email atau nomor telepon untuk ditambahkan ke profil keluarga.

## Reset sandi orang tua — kebijakan A+C

1. Jangan mengonfirmasi bahwa nama akun ada atau tidak ada kepada pemohon yang
   belum terverifikasi.
2. Pesan dari nomor WhatsApp tertentu **bukan** bukti bahwa pengirim menguasai akun.
   Nama akun, nama panggilan anak, hasil latihan, atau informasi keluarga yang
   mungkin diketahui pihak lain juga tidak boleh menjadi bukti tunggal.
3. Lanjutkan hanya bila operator dapat memverifikasi pemohon melalui hubungan
   independen yang sudah dipercaya di luar Jagomat, misalnya hubungan langsung
   yang sudah dikenal dan dapat dikonfirmasi melalui kanal terpisah.
4. Bila verifikasi independen tidak tersedia atau meragukan, **tahan reset**.
   Sampaikan bahwa permintaan belum dapat diproses tanpa mengungkap keberadaan akun.
5. Setelah verifikasi, cari akun hanya di panel privat. Gunakan tindakan
   **Reset sandi** existing; jangan mengedit `sandi.json`, database, atau sesi
   secara manual.
6. Sandi pengganti ditampilkan sekali. Serahkan lewat kanal terverifikasi dan
   minta pengguna segera menggantinya. Jangan menaruh sandi pada catatan tiket.
7. Pastikan revisi autentikasi target naik dan sesi lamanya tidak lagi berlaku.
   Periksa audit memakai operation ID yang sama; jangan membuat operasi pengganti
   bila hasil commit belum pasti.

Jalur panel existing menolak target admin, memvalidasi principal admin mutakhir,
CSRF, token tinjauan bertanda tangan, autentikasi ulang, dan revisi target. Reset
hanya mengubah akun target; akun lain tidak boleh berubah.

## Permintaan penghapusan seluruh keluarga

Pesan WhatsApp hanya **memulai permintaan**, bukan menghapus data. Primitive domain
untuk penghapusan keluarga lengkap belum tersedia. `hapus_akun_guru()` hanya
menghapus login dan secara eksplisit mempertahankan data siswa/riwayat; fungsi itu
tidak boleh dirangkai menjadi penghapusan keluarga.

Sampai workstream Kritis terpisah menyediakan primitive teruji, operator harus:

1. mengikuti verifikasi independen A+C di atas;
2. menahan eksekusi dan tidak menjanjikan penghapusan selesai;
3. menginventarisasi state durable terkait secara privat tanpa menyalin isi anak;
4. membuat plan khusus dengan preview, backup coherent empat DB + `sandi.json`,
   atomicity, idempotensi, audit/provenance, preservasi ledger append-only, tes
   mutation, recovery, dan pemberitahuan selesai;
5. tidak memakai produksi sebagai tempat eksperimen dan tidak melakukan hard-delete
   sesi berbukti atau ledger immutable.

## Eskalasi dan insiden

- Identitas tidak dapat diverifikasi: tahan tindakan dan eskalasi ke pengelola.
- Hasil reset tidak pasti: periksa receipt/audit operation ID yang sama; jangan
  mengulang dengan ID baru.
- Konfigurasi dukungan hilang/rusak: status panel menjadi **Belum siap** dan halaman
  publik tidak menampilkan nomor atau janji SLA. Jalankan migrator opt-in hanya
  melalui rilis terkontrol dengan backup/recovery exact.
- Dugaan pengambilalihan akun: jangan reset, jangan mengonfirmasi akun, dan simpan
  bukti operasional minimum untuk peninjauan pengelola.
