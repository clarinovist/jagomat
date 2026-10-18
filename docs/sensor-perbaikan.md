# Sensor perbaikan Jagomat

Status: kontrak source sensor v1; pemasangan dan aktivasi dilaporkan terpisah.

## Tujuan dan izin

Sensor internal first-party membantu menemukan hambatan alur dan mengevaluasi produk,
bukan menentukan diagnosis/rekomendasi atau membuktikan efektivitas belajar. KPI v1
(`kpi_*`, cohort registrasi) tetap terpisah dan tidak diubah.

[Kesepakatan awal](persetujuan-awal.md) berversi menawarkan persetujuan keluarga
lama/baru di awal, dengan pengaturan lanjut dari Akun. Codec sensor tetap
`sensor-keluarga-v1`; tujuan yang disetujui:
- alur operasional (opt-in, tidak dicentang);
- opsi terpisah ringkasan hasil pada konfirmasi pertama;
- opsi terpisah kategori topik pesan Pendamping baru.

Menolak tidak mengurangi layanan. Izin provider Pendamping bukan izin sensor. Menyimpan
pilihan baru menghapus seluruh detail sensor sebelumnya dan membuat generasi/salt baru.
Pencabutan bekerja meski koleksi dimatikan. Restart/redeploy tanpa restore mempertahankan
epoch host dan consent. Restore wajib rotasi epoch di luar backup lalu recreate proses;
izin backup tidak diwariskan. Consent sensor maksimum90hari; detail maksimum30hari.
Receipt Terms dan pilihan OFF tetap ada agar penolakan tidak memicu gate berulang.
Tidak ada auto-enrollment, ekspor provider, backfill, arsip agregat baru, atau scan histori.

## Sumber dan semantik

Hanya sesi dibuat sesudah detik consent dan event persiapan teramati yang masuk episode.
Sesi sebelum/sedetik consent sengaja tidak dihitung untuk mencegah ambiguitas waktu.
Label: **Siklus teramati setelah opt-in**, bukan nilai pertama sejak registrasi ≤48 jam.

Hook setelah commit: persiapan manual biasa/gabungan/serupa/remedial dan siklus utama;
penyimpanan pekerjaan akun/tautan (termasuk sebelum refleksi), pengiriman akun/tautan/
penerapan foto, tinjauan legacy/terpandu, konfirmasi, pembatalan, serta pembuatan sesi
terpandu berikut setelah sesi terkonfirmasi. Penerapan foto hanya milestone pengiriman,
bukan analisis foto. Pilot/CLI/Pendamping pembuat latihan yang tidak tercakup tidak
menghasilkan episode penuh. Lembar dicatat setelah respons berhasil dikirim.

Pekerjaan disimpan berarti write diterima, bukan anak mulai berpikir atau durasi aktif.
Milestone disimpan sekali per episode; simpan tinjauan bukan wajib sebelum konfirmasi.
Kelanjutan berarti sesi terpandu baru setelah sesi terkonfirmasi sebelumnya pada anak
yang sama, bukan bukti rekomendasi dibaca atau hubungan sebab-akibat hasil belajar.
Penanda ≥48 jam adalah umur kesempatan yang konservatif (jam dibulatkan; margin 1 jam),
bukan label ditinggalkan atau SLA. Cetak/manual tidak disamakan dengan siklus terpandu.

Hasil bersumber receipt immutable konfirmasi pertama (nomor urut 1), dibawa dari
transaksi ke hook; bila event pertama hilang, koreksi kedua tidak mengisinya: jumlah benar, dilewati/
belum jelas, dan hitungan kategori B/K/H/E/N/T. Tidak menyalin jawaban/cara/kunci/nilai
bebas. Ini **potret historis konfirmasi pertama**, bukan penguasaan/nilai aktif; koreksi
berikutnya tidak ditafsirkan sebagai kemunduran dan tidak membuat event hasil kedua.
Kategori chat berasal hanya pesan pengguna baru yang berhasil committed. Aturan kata
lokal berversi, ambigu → belum_diketahui; bukan model semantik/diagnosis dan bukan hasil
kepuasan. Tidak membaca ulang histori/context/memori, menyimpan kata/kutipan/hash teks,
atau memanggil provider. Replay/polling tidak dihitung.

## Privasi dan penyimpanan

Namespace optional-additive `sensor_*` di admin-control.db, tanpa menaikkan admin7/8/9.
Mapping akun, generasi consent, dan salt privat terpisah logis dari proyeksi. Token
sesi/request berupa HMAC namespace dengan salt per consent; tetap pseudonim, bukan anonim.
Tidak menyimpan ID anak/sesi/request mentah, URL, IP, UA, foto, kontak atau teks.
Jam event dibulatkan; waktu cohort/episode diperlukan untuk TTL dan eligibility.

Funnel/hambatan terbatas episode terpandu tanpa penanda lembar cetak; manual dan cetak
tidak digabung ke denominator tersebut. Ringkasan hasil/chat lintas episode berizin
dilabeli terpisah. Dashboard tanpa drill-down/filter silang. Minimal 5 keluarga berbeda per sel, bukan
5 sesi; sel kurang cukup ditahan (termasuk nol), dan total komposisi tidak dipublikasikan
untuk menghindari penurunan nilai sel tersembunyi melalui selisih. Turunan hasil/chat
hanya dari keluarga dengan tujuan izin terkait. Angka bukan estimasi populasi.

Janitor existing menghapus episode/chat 30 hari dan peserta 90 hari; FK cascade menghapus
turunannya. Penghapusan sesi mem-purge token sesudah commit, termasuk saat koleksi OFF.
Rekonsiliasi berkala ID-saja membersihkan sumber sesi/chat terhapus atau consent provider
chat dicabut; tidak membaca isi. Kegagalan rekonsiliasi menahan laporan. Ada jeda janitor,
bukan jaminan penghapusan lintas DB atomik. Penghapusan keluarga menghapus mapping sensor dan seluruh detail. Backup
mengikuti bundle admin existing serta perlindungan/retensi operasi; restore menahan
izin. Pencabutan sensor adalah jalur penghapusan analitik terpisah dari catatan domain.
Potret historis anonim-kelompok yang sudah ditampilkan bukan sertifikasi sumber aktif.

## Kesehatan dan keterbatasan delivery

`SENSOR_KOLEKSI_SIAP=1` hanya gate deployment; tidak memberi consent keluarga.
Default OFF. Status: belum dipasang/nonaktif/tidak teramati/terganggu/menunggu izin ulang/
menunggu peserta/siap best-effort. Tidak ada jaminan delivery lengkap: commit domain
lalu sink admin bukan transaksi tunggal; crash di antaranya dapat kehilangan event.
Tidak ada replay histori/outbox untuk menutup gap. Error sink menahan proyeksi; kegagalan
sink tidak membatalkan belajar. Epoch restore baru tidak mengklaim interval lama lengkap.

## Rilis

Migrator eksplisit `sensor_schema.migrasikan`, absent-or-exact, tidak dari GET/startup.
Backup validator/rehearsal mengenal `skema_sensor` dan `target_sensor=True`; migrasi dua
kali pada turunan tanpa mengubah tabel lama. Recovery harus memahami schema, consent,
purge, dan hooks. B fondasi lengkap, C dashboard; fingerprint sama dan exact pair diuji.
Gate lokal scoped/mutation dan CI full kandidat/recovery/build/pair wajib sebelum deploy.
Controlled deploy-v2, preflight metadata sebelum hold, backup coherent, rehearsal,
aktivasi hanya setelah notice/guard/pair terbukti. Tidak membuka job pasang otomatis.
