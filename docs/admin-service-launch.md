# Panel layanan dan KPI — kandidat admin7

Status: implementasi kandidat; bukan bukti deployment atau pengaktifan pembayaran/analitik.

## Empat bagian

- **Langganan**: pencarian keluarga enrolled, masa coba/grant, cakupan dan sisa promo,
  invoice serta receipt. Pembayaran dan akses ditampilkan terpisah. Query provider
  hanya lewat POST cookie admin+reauth+token signed, intent existing, order sama,
  pemeriksaan owner/principal sebelum-sesudah jaringan, journal dan deduplikasi.
  Runtime sekarang mengikuti preview sandbox loopback terisolasi; produksi belum
  mempunyai adapter/callback siap. Tidak ada override lunas, refund, atau grant manual.
- **Perlu ditangani**: halaman antrean berpaginasi untuk journal admin, pemeriksaan
  pembayaran, invoice bermasalah. Tautan menuju sumber. Operasi admin lama yang
  tidak mempunyai perintah/receipt lengkap tetap memerlukan operator teknis;
  panel tidak mengarang perintah recovery atau memaksa sukses.
- **Operasional**: kesiapan DB/config, AI efektif, jumlah kegagalan/tak pasti 24 jam,
  dan validitas bundle backup bila operator menyediakan referensi lokal tepercaya.
  Tidak ada SSH/Docker/provider saat GET. Default backup belum terverifikasi;
  keberadaan panel bukan jadwal backup/off-site/rehearsal. Tidak ada tombol restore.
- **KPI Uji Coba**: empat metrik aktivitas/survei serta biaya manual bulanan.
  Aktivasi/retensi memakai peserta matang14hari; retensi utama bukan hanya peserta
  teraktivasi. Organik khusus minggu5–8, unknown masuk denominator. Angka kecil
  ditandai; tabel cohort kelompok <5 tidak ditampilkan. Tidak ada drill-down anak.

## Consent, koleksi, dan recovery

Koleksi default OFF. `KPI_KOLEKSI_SIAP=1` adalah gate deployment tambahan, bukan
pengganti pengaturan eksperimen di admin atau consent keluarga. Jangan mengaktifkan
sebelum source/artifact exact, notice, seluruh hook, backup/restore dan eksperimen
siap. Form consent tidak dicentang; penolakan tidak mengubah hak akses/billing.

Receipt registrasi baru committed menjadi t0. Replay receipt tidak mendaftarkan
ulang analitik atau menghidupkan consent yang dicabut. Tidak ada backfill aktivitas.
Hanya kode aktivitas/hari/jendela; tidak ada jawaban, diagnosis, foto, chat, kontak,
IP/UA, ID anak/sesi, atau URL privat pada tabel analitik. Pemetaan akun privat terpisah
secara logis dari proyeksi dashboard. Survei native berkode tanpa teks bebas.

Setelah restart/restore, boot lama tidak memberi izin koleksi atau status kualitas
lengkap. Admin perlu membuka koleksi kembali; keluarga perlu persetujuan ulang.
Detail dari boot lama tidak dipakai pada metrik. Persetujuan ulang membuang aktivitas/
survei lama terkait dan menandai cakupan terlambat, bukan mengaku merekam interval
hilang. Ini konservatif, bukan mekanisme high-availability tanpa kehilangan sampel.

Pencabutan menghapus mapping/event/survei aktif atomik; data belajar/billing tidak
berubah. Detail maksimum90hari sejak enrollment, agregat kelompok≥5 tanpa mapping
maksimum12bulan kalender setelah akhir rekrutmen. Kelompok terlalu kecil dibuang,
bukan dipertahankan hingga melampaui TTL. Purge bounded oleh janitor existing.
Kartu aktif setelah retensi tidak menampilkan 0 palsu; arsip agregat terpisah.

Kegagalan koleksi tidak membatalkan latihan/registrasi. Sink pendek50ms, kategori log
tertutup dan flag kegagalan dalam proses menahan KPI hijau meskipun penulisan status
kegagalan ikut gagal. Tidak mengarang event dari histori anak untuk menutup gap.

## Persistensi/rilis

Migrasi admin6→7 additive melalui `admin_store.siapkan`; tidak ada migrasi GET.
Bundle tetap empat DB+auth; versi7/struktur/linkage diverifikasi. Probe image baru
mensyaratkan admin7 dan `admin_launch_checks=4`; pair lintas image menambah
`admin_launch_pair_checks=4`, termasuk replay biaya, preservasi tahap pembayaran,
dan consent lama tertahan.

## Sakelar pembayaran

Panel **Operasional** menyimpan tahap pembayaran berversi di admin-control.db:
`nonaktif → rekonsiliasi → checkout → penegakan`. Kenaikan hanya satu tahap;
penurunan boleh langsung saat insiden. Setiap perubahan memerlukan sesi admin cookie,
CSRF, tinjauan bertanda tangan, reauth, konfirmasi, revisi optimistic, dan audit
append-only. `subscription.SAKELAR` tetap OFF; reader DB hanya menghasilkan sakelar
injeksi eksplisit. Missing/rusak kembali OFF tanpa membuat DB.

Readiness bukan checkbox admin: key/provider produksi, callback, recovery exact-pair,
dan kebijakan D8/D9 diinjeksi oleh artifact/server tepercaya. Nilai secret tidak
pernah tampil/tersimpan di panel. Sampai semua gate tersedia, panel hanya menampilkan
status “belum siap” dan menolak kenaikan tahap. Ini menggantikan perubahan `.env`
berulang untuk operasi rutin, tetapi bukan cara melewati gate rilis.
Baseline recovery admin6 tidak kompatibel. Bootstrap memakai mode persiapan dan
pasang literal false; setelah baseline admin7 teruji, kandidat mematok SHA/fingerprint
baseline yang sama, mode migrasi dan pair exact digest. Tidak downgrade schema,
restore otomatis, atau aktivasi produksi melalui perubahan metadata.

## Batas yang tidak disamarkan

- Pembayaran produksi/paywall, D8/D9 dan tanggal launch tetap pekerjaan terpisah.
- Antrean bukan CRM/ticketing atau editor data bebas.
- Backup operasional lengkap terjadwal tidak diselesaikan oleh panel status.
- KPI hanya peserta sukarela; bukan semua keluarga atau bukti kemampuan matematika.
- Bukti lokal/CI/visual/deploy harus dilaporkan per checkpoint, bukan dianggap selesai
  karena dokumen ini ada. Plan/evidence privat: `docs/plan/2026-09-25-admin-service-launch.md`.
