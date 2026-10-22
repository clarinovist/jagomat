# Jagomat — Spesifikasi ringkas

Ringkasan produk; detail di [referensi produk](product-reference.md), status dan
pekerjaan tersisa di [status proyek](status-proyek.md), arsitektur di [context.md](context.md).
Bukan keputusan produk baru atau bukti deployment.

## Tujuan dan pengguna

Latihan matematika SD untuk persiapan OSN/SASMO, diprioritaskan sebagai alat guru
les **in-house** untuk menentukan satu langkah belajar berikutnya. Pengembangan
pivot memakai data sintetis; pilot dengan data nyata perlu keputusan dan gerbang
privasi tersendiri. Peran teknis `guru` mencakup orang tua dan hanya mengelola data
miliknya; `murid` mengerjakan latihan; `admin` mengelola lintas keluarga dengan
batas khusus. Pada UI guru, orang dewasa disebut **Guru/Anda**, **Pendamping** nama AI.

## Cakupan aktif

- Generator deterministik, lembar cetak, latihan daring/manual, foto atau isi dari
  lembar, tinjauan dan laporan per anak. Kunci/diagnosis bukan keputusan LLM.
- Beranda guru memprioritaskan yang terlama menunggu konfirmasi: kartu anak dengan satu
  tombol aksi, chip kelompok berhitungan, dan pencarian nama/login (untuk daftar panjang),
  semuanya owner-scoped. Query GET tidak di-cache atau dikirim sebagai referrer, tetapi
  tetap berada di URL/riwayat browser.
- Ruang anak: **Beranda → Latihan → Riwayat → Perkembangan**. Satu CTA dari reducer;
  laporan Ringkasan/Per materi memakai bukti yang sama, bukan skor global anak.
  P3–P6 adalah konfigurasi internal/historis, bukan kelas atau ukuran kemampuan.
- Bantuan statis dan **15 draf playbook P3 berperingatan**, bukan materi yang telah
  disahkan manusia. Hanya guru pada fokus/profil yang cocok; tidak dikirim ke murid.
- Pendamping inline memakai konteks berizin dan usulan yang harus ditinjau.
  Hapus chat/cabut izin tersedia walau provider mati; tombstone/purge, memori,
  hasil latihan, backup dan provider mempunyai batas retensi berbeda.
- Akun, persetujuan awal, sensor internal opt-in, panel admin/tema, dukungan akun,
  riset publik dan wawancara privat tersedia. Sensor bukan bukti efektivitas belajar.
- Akses awal **nonkomersial**. Fondasi paket/pembayaran tidak berarti trial,
  kampanye, checkout v2, refund atau penegakan paket telah dibuka.

## Kontrak belajar dan perlindungan

**Pemetaan → fokus → intervensi/contoh → terbimbing → penguatan → evaluasi
berjeda → checkpoint → maju/eskalasi.** [Kontrak lengkap](siklus-belajar-terpandu.md).

- Bukti hanya snapshot outcome append-only yang dikonfirmasi eksplisit; status
  review mutable bukan bukti. Koreksi menginvalidasi bukti aktif tanpa menulis ulang histori.
- Maksimal dua fokus `(template_id, kode_intervensi, malrule_id)`. B/K/H/E/N/T
  mempunyai tindakan masing-masing; T lewat pengenalan, bukan langsung remedial.
- Benar belum cukup tanpa penjelasan. Evaluasi ≥4 probe/fokus; checkpoint 28 hari
  ≥3 probe/fokus; gagal kedua/tidak ada alternatif → eskalasi. Syarat kelulusan
  lengkap tetap mengikuti kontrak, bukan jumlah soal saja.
- Manual/PG/terbimbing/penguatan tidak otomatis menjadi bukti penguasaan;
  konteks profil/representasi dan provenance tidak dicampur diam-diam.
- Guru asing mendapat **404 identik**, tanpa efek samping; murid tidak menerima
  kunci, malrule, diagnosis atau laporan. Admin tidak mengubah akun sesama admin.
- Data anak, credential, sesi, wawancara dan backup tidak masuk Git/log/fixture.
  Tidak menyimpan email/telepon pengguna. Hapus keluarga memerlukan verifikasi,
  preview/backup/cutover; bukan sekadar menghapus login atau bukti immutable.

## Batas dan keputusan

Batch katalog aktif dan bank kalimat tidak mengesahkan seluruh katalog. Revisi
penilaian baru/pilot bank tetap offline/default0; playbook masih draf; efektivitas
pada guru/anak belum dibuktikan. Tidak menjanjikan siap juara atau penguasaan seluruh
kurikulum. Pekerjaan [dibatalkan/ditunda](status-proyek.md) tidak dibuka otomatis.

Acuan: [playbook](playbook-guru.md) · [Pendamping](pendamping-runtime.md) ·
[paket](subscription-packages.md) · [privasi/dukungan](support-operations.md) ·
[aturan proyek](../CLAUDE.md). Perubahan cakupan harus memperbarui ringkasan ini
bersama kontrak detail; status operasi dicatat terpisah di runbook rilis.
