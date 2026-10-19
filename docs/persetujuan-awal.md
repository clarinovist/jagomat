# Persetujuan awal terpadu

Versi `jagomat-2026-10-18-v2`. Satu form saat registrasi atau kunjungan HTML guru
ber-cookie (`/`, `/guru`, `/anak/*`), bukan penghalang untuk murid/admin/publik.
`/persetujuan` juga menjadi halaman pengaturan. Terms `/syarat-penggunaan` dan Privacy
`/kebijakan-privasi` tersedia publik. Tombol **Setuju & aktifkan semua** secara afirmatif
menyetujui penggunaan internal yang disebutkan; **Atur pilihan** pada layar yang sama
membolehkan memilih nol atau sebagian. Tidak ada perluasan iklan/pelatihan model/provider.
Izin provider Pendamping dan KPI uji coba lama tetap terpisah. Tambah anak tidak
meminta checkbox privasi berulang: penggunaan inti mengikuti kesepakatan awal.
Aksi tersebut tidak menulis receipt persetujuan baru, mengubah pilihan opsional,
atau mengaktifkan kembali izin yang ditolak, kedaluwarsa, maupun dicabut.

## Receipt dan lifecycle

`policy_receipt` optional-additive di admin DB, terpisah dari peserta sensor. Ia memuat
versi, epoch, revisi, operasi terakhir, waktu, dan pilihan alur/hasil/chat. Receipt dan
perubahan peserta sensor atomik di bawah guard pemilik. Form bersesi ditandatangani
terhadap akun, sesi, revisi auth, versi, epoch, operasi dan revisi receipt. Stale/replay
setelah perubahan/cabut tidak boleh menimpa keputusan terbaru. Replay identik no-op.

Pendaftaran memakai notice/pilihan yang sama. Hook hanya pada akun benar-benar baru,
create-if-absent. Akun+profil sudah committed sebelum hook: gagal/crash receipt berarti
sensor OFF dan pengguna masuk gate; replay registrasi tidak memulihkan izin. Payload
lama tanpa versi tidak ditafsirkan sebagai consent baru. Tidak ada backfill.

Receipt Terms tetap ada saat analitik dicabut atau izin sensor90hari habis. Penolakan
tersimpan tidak memicu gate ulang; sensor yang habis tidak dibuat otomatis dari receipt.
Perubahan pilihan memulai sumber prospektif baru dan menghapus derivasi lama. Penghapusan
keluarga menghapus receipt. Detail sensor tetap30hari, tidak ada penambahan raw data.

Panel Akun menampilkan pilihan tersimpan, tanggal persetujuan terakhir (WIB), dan
status izin efektif/masa berakhir secara terpisah. Waktu receipt bukan tanggal
pencabutan; panel tidak mengarang waktu tersebut. Pencabutan memakai checkbox
wajib dan konfirmasi dengan konsekuensi eksplisit: detail analitik tambahan dihapus,
data belajar dan percakapan sumber tetap ada. Token dan validasi server tetap wajib.

## Restart dibanding restore

`SENSOR_CONSENT_EPOCH` adalah 32 karakter hex acak, root-controlled di konfigurasi host
**di luar bundle backup DB/auth**. Tidak boleh menaruh epoch di DB atau membackupnya
sebagai state yang otomatis dipulihkan bersama DB. Restart/redeploy/rollback image tanpa
restore data mempertahankan epoch. Collector/receipt/report menggunakan epoch yang sama.
Epoch hilang/invalid menahan pemberian izin dan koleksi, tidak fallback ke boot lama.

**Restore wajib:** tahan ingress, hentikan seluruh proses/collector; rotasi epoch host
sebelum memasang data backup; restore; recreate container/proses dengan environment baru
(bukan docker restart); verifikasi izin/receipt epoch lama ditolak dan sensor tidak
mengirim; baru buka layanan. Jangan memulihkan file epoch lama. Restore di luar prosedur
ini tidak terdeteksi otomatis. Deployer tidak auto-restore DB. Data backup yang memuat
consent sebelum pencabutan tidak dihidupkan di generasi baru.

## Rilis

`policy_schema.migrasikan()` eksplisit/idempoten, reader absent/exact. Backup/rehearsal
`target_policy=True`, family deletion, dan pair C→B→C wajib memverifikasi receipt,
restart epoch sama, stale/cabut, dan epoch restore berubah. Baseline recovery baru harus
memahami persistensi; mode persiapan hanya bootstrap, final migrasi tetap exact-pair.
Notice menjelaskan perilaku teknis, bukan jaminan kepatuhan hukum universal.
