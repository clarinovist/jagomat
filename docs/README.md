# Dokumentasi teknis

Folder ini berisi spesifikasi aktif, keputusan desain, dan prosedur verifikasi
codebase. Kode dan tes di `../mesin/` membuktikan perilaku yang tersedia;
`../CLAUDE.md` menetapkan palang arsitektur, privasi, dan pengujian.

## Acuan aktif

- [Siklus belajar terpandu](siklus-belajar-terpandu.md): kontrak alur belajar,
  bukti terkonfirmasi, fokus, intervensi, evaluasi, dan checkpoint.
- [Ringkasan perkembangan berbasis bukti](ringkasan-perkembangan.md): baseline
  Opsi 2 dan palang manfaat; implementasi AI ditahan setelah spike sintetis.
- [Design system](design-system.md): dokumentasi token dan gaya aplikasi.
- [Pendamping Jagomat](pendamping-jagomat.md): rancangan chat orang tua, katalog,
  konteks, riwayat, dan memori; belum diimplementasikan.
- [Referensi workflow](workflow-reference.md): prosedur soal/malrule, test/mutation,
  preview sintetis, dan batas klaim produk; jalur risiko/gate tetap di `../CLAUDE.md`.
- [Rilis pusat kendali admin](admin-control-release.md): kontrak persistensi,
  validasi bundle backup, rehearsal migrasi, dan batas klaim produksi.
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
