# Dokumentasi teknis

Folder ini berisi spesifikasi aktif, keputusan desain, dan prosedur verifikasi
codebase. Kode dan tes di `../mesin/` membuktikan perilaku yang tersedia;
`../CLAUDE.md` menetapkan palang arsitektur, privasi, dan pengujian.

## Keputusan pembatalan pengembangan — 18 September 2026

Keputusan pengguna pada 18 September membatalkan pekerjaan terbuka dari
pemeriksaan dokumen yang tercantum di bawah. Statusnya **DIBATALKAN (cancelled)**,
bukan tertunda atau antrean untuk dilanjutkan otomatis. Keputusan ini tidak
membatalkan tugas baru yang disetujui setelah tanggal tersebut:

| Pekerjaan | Status |
| --- | --- |
| Sisa alur kerjakan di kertas, jawab lewat HP | DIBATALKAN |
| Demo video produk di landing, termasuk demo lanjutan | DIBATALKAN |
| Penyempurnaan kendali Pendamping: UI hapus chat/cabut izin, pengelolaan saat provider tidak dikonfigurasi, dan pesan editor memori | DIBATALKAN |
| Penerimaan soal visual pada HP/printer fisik serta walkthrough pengguna, Safari/keyboard HP, dan aksesibilitas Pendamping | DIBATALKAN |
| Pengembangan/penerimaan representasi nonvisual K4 untuk pembaca layar | DIBATALKAN |
| Evaluasi lanjutan mutu penjelasan matematika Pendamping | DIBATALKAN |
| Ringkasan perkembangan AI v1 yang sebelumnya ditahan | DIBATALKAN |

Fitur yang sudah diimplementasikan tetap utuh. Pembatalan tidak mengubah kode,
konfigurasi, data, atau produksi; tidak menyatakan pengujian yang belum dilakukan
sudah lulus dan tidak melemahkan gerbang aktivasi maupun batas klaim. Pekerjaan
tersebut hanya dapat dibuka kembali lewat keputusan baru pengguna. Checklist lama
tetap menjadi histori, bukan backlog aktif atau bukti kelulusan.

## Acuan teknis dan historis

- [Siklus belajar terpandu](siklus-belajar-terpandu.md): kontrak alur belajar,
  bukti terkonfirmasi, fokus, intervensi, evaluasi, dan checkpoint.
- [Ringkasan perkembangan berbasis bukti](ringkasan-perkembangan.md): baseline
  dashboard deterministik tetap tersedia; pengembangan AI v1 dibatalkan setelah
  sebelumnya ditahan oleh hasil spike sintetis.
- [Design system](design-system.md): dokumentasi token dan gaya aplikasi.
- [Runtime Pendamping](pendamping-runtime.md): kontrak implementasi inline yang
  tersedia; pengembangan lanjutan yang dicatat di atas dibatalkan.
- [Pendamping Jagomat](pendamping-jagomat.md): spesifikasi awal/historis; arah
  halaman chat terpisah sudah digantikan oleh Pendamping inline.
- [Referensi workflow](workflow-reference.md): prosedur soal/malrule, test/mutation,
  preview sintetis, dan batas klaim produk; jalur risiko/gate tetap di `../CLAUDE.md`.
- [CI selektif](ci-selective.md): daftar dokumen aman, pemeriksaan ringan,
  jalur lengkap/manual, dan check Status CI tanpa melemahkan gate rilis.
- [Rilis produksi](production-release.md): status source/CI dan snapshot live
  terpisah, gate pemasangan, backup/recovery, serta histori operasi.
- [Koreksi kalender WIB](domain-clock-release.md): penyebab CI gagal, kontrak
  tanggal belajar, dan pasangan recovery yang memperbaikinya.
- [Rilis pusat kendali admin](admin-control-release.md): runbook historis admin4,
  prinsip bundle backup, batas helper, dan rujukan koreksi admin5; bukan prosedur
  siap-eksekusi untuk produksi sekarang.
- [Verifikasi siklus belajar](verifikasi-siklus-belajar.md).
- [Verifikasi penyajian soal](verifikasi-penyajian-soal.md).
- [Verifikasi soal visual](verifikasi-soal-visual.md).
- [Verifikasi statistika visual](verifikasi-statistika-visual.md).
- [Keputusan cleanup dead code](dead-code-cleanup.md): bukti penghapusan,
  migrasi assertion ke jalur aktif, dan kandidat yang sengaja dipertahankan.

## Berkas lokal

`plan/` menyimpan rencana bertanggal dan alat preview kerja, serta tetap
gitignored. Rincian implementasi siklus ada di
`plan/2026-09-06-siklus-belajar-terpandu.md`; berkas lokal ini tidak dijamin
tersedia pada clone lain. Kontrak permanen tidak boleh hanya tinggal di plan.

Riset kurikulum dan pasar, materi, mockup, serta keputusan bisnis historis
berada di folder saudara lokal `../../osn-resources/referensi/`, bukan di codebase.
Arsip tidak diperlukan untuk tes atau build, dan tidak menggantikan
spesifikasi aktif di folder ini.
