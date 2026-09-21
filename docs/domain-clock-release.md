# Koreksi kalender belajar WIB — 22 September 2026

## Penyebab dan kontrak

CI run `35664314629` gagal pada tes HTTP pilot, baik kandidat maupun recovery
`175d8fb`. Tanggal sesi SQLite sudah memakai UTC+7, tetapi tanggal default Python
mengikuti timezone proses. Pada 17.00–23.59 UTC, sesi hari ini dianggap bertanggal
besok oleh pembaca bukti. Mengubah timezone CI saja akan menyembunyikan bug runtime.

`domain_clock.hari_wib()` kini memakai UTC+7 eksplisit tanpa dependensi zona waktu
host. Default rekomendasi, penguasaan, perjalanan belajar, layanan pilot, dan
statistik laporan memakai kalender tersebut. Argumen tanggal eksplisit tetap
diutamakan. Pemeriksaan pilot memakai satu tanggal untuk seluruh konteks dan
sub-evaluasi dalam operasi yang sama, termasuk saat melintasi tengah malam.

Tidak mengubah tanggal/isi DB, schema, fingerprint, arsip, ambang kelulusan,
kuota/jeda probe, atau penolakan bukti masa depan. Ini koreksi pembacaan hari,
bukan migrasi/backfill atau izin mengonfirmasi bukti secara otomatis.

## Pasangan rilis

- Recovery B: `e206563468afb805af9612711f3c4d0f9ec81539`, memperbaiki default kalender
  WIB. Koleksi terukur: **11.425 tes**. Source B tetap immutable.
- Kandidat C menambahkan konsistensi satu tanggal per operasi pilot; bukan hanya
  mengganti label/digest B. Delta ini mempunyai regresi tersendiri pada batas
  umur bukti dan pembacaan kartu/laporan.
- Kontrak persistensi B terukur tetap
  `0cf42df6d86263c56f03547e8179eca750e23d3dd26c45cde11201bb2043ce53`.
- B dan C diuji penuh dan dibangun sebagai pasangan dalam CI final yang sama.
  Pin ini **bukan klaim** image B pernah lolos run terpisah. Tes recovery lama
  tidak ditambal, di-skip, atau diberi `continue-on-error`; kegagalan kandidat,
  recovery, probe image, atau uji pasangan tetap menahan rilis.
- Mode tetap `migrasi`, job `pasang` tetap `false`, namespace image tetap
  `ghcr.io/clarinovist/osn-mesin-latihan`. Tidak mengubah policy/deployer VPS,
  tidak menjalankan ulang migrasi pilot atau mengaktifkan auto-deploy.

Bagian pin pilot `175d8fb` dalam [runbook rilis](production-release.md) adalah
histori rilis sebelumnya. SHA source saja tidak membuktikan image tersedia,
produksi berubah, atau recovery operasional siap. Gunakan manifest exact pair dari
run final yang lulus; backup/rehearsal serta kesiapan policy host tetap diwajibkan
sebelum operasi produksi. Jangan menghapus image recovery produksi lama hanya
karena ada pin source baru.

## Verifikasi

Regresi membekukan instan sebelum/sesudah 17.00 UTC, pergantian bulan/tahun dan
hari kabisat pada host UTC/WIB. Jalur HTTP yang gagal di CI tetap menggunakan
assertion aslinya. Bukti besok tetap ditolak, tanggal eksplisit tetap dihormati,
GET/operasi baca tidak menulis DB. Mutation terisolasi membuktikan tes merah bila
clock dikembalikan ke UTC/host atau guard masa depan dihilangkan. Gate akhir
adalah full suite kandidat/recovery dan probe pasangan image CI, bukan hanya
hasil scoped lokal.
