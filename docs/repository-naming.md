# Penamaan repo dan folder Jagomat

## Identitas dan batas migrasi

| Bagian | Nama |
|---|---|
| Produk / domain | Jagomat / `https://jagomat.id` |
| Folder lokal kanonis | `/Users/nugroho/Documents/jagomat` |
| Alias lokal sementara | `/Users/nugroho/Documents/osn` → `jagomat` |
| Repo GitHub saat transisi | `clarinovist/osn-mesin-latihan` |
| Target repo GitHub | `clarinovist/jagomat` |
| Image candidate **dan** recovery | `ghcr.io/clarinovist/osn-mesin-latihan` (tetap) |

**Rename GitHub belum dilakukan.** Patch pengaman harus masuk `main` dan lolos
CI lebih dulu. Mengubah nama GitHub saat workflow lama masih memakai
`${{ github.repository }}` membuat build menuju image baru, sementara verifier,
metadata, dan deployer menolak image di luar namespace lama.

Folder `mesin/`, `docs/`, `scripts/`, `.github/` tidak dirombak. Nama container
`osn-mesin`, path VPS `/opt/osn`, variabel `OSN_*`, cookie, schema, `.git` lama
terabaikan di dalam `mesin/`, serta arsip lokal `../osn-resources` tidak diubah.
Istilah OSN yang merujuk kompetisi/materi bukan sisa brand yang harus dihapus.

## Kompatibilitas lokal

Folder utama dipindahkan utuh, bukan dibuat clone/salinan baru. Alias `osn`
menjaga path yang sudah dipegang shell, agent, editor, scheduler, dan entry point
venv. Data ignored tetap lokal; perpindahan folder bukan izin membaca atau
mengunggahnya. Git selalu menunjuk **repo luar**, bukan `mesin/.git`.

Gunakan path `jagomat` untuk sesi baru. Jangan hapus alias sampai:

1. Semua sesi/editor memakai path baru dan tidak ada writer aktif di path lama.
2. Entry point/aktivasi venv yang menanam path absolut lama sudah dibuat ulang
   dengan interpreter/dependensi yang disetujui dan diuji.
3. Jadwal backup dan konfigurasi alat lokal telah diperiksa/dipindahkan dengan
   izin tersendiri. Jangan menyalin credential ke repo atau log.

`mesin/cadangkan.sh` menentukan tujuan sebagai `cadangan/` di sebelah skrip,
termasuk ketika folder induk dilewati lewat alias. Tidak bergantung pada `$HOME`
atau cwd pemanggil. Pindahkan **folder proyek utuh**, bukan hanya skrip cadangan.
Retensi, koneksi VPS, pemeriksaan integritas, dan penamaan cadangan tidak diubah.

## Urutan rename GitHub — setelah izin push

1. Review patch pengaman, full gate lokal, commit hanya scope sendiri. Perubahan
   staged milik sesi lain tidak boleh ikut commit.
2. Setelah izin **push eksplisit**, push patch ke repo lama. Pantau run commit
   yang tepat sampai seluruh test/build/probe candidate dan recovery sukses.
   Jangan rename repo saat run masih berjalan. Periksa mode rilis saat itu:
   snapshot transisi memakai `pasang: if false`, bukan izin mengaktifkan deploy.
3. Pastikan tidak ada push/run/workflow lain yang berjalan, target nama masih
   tersedia, dan akses package GHCR tetap terhubung ke repository yang sama.
   Pin namespace tidak membuktikan izin package; build CI harus membuktikannya.
4. Rename **repo yang sama**, bukan membuat repo baru. Sesudah rename, pastikan
   identitas repository, riwayat, default branch, dan visibilitas tetap sama.
   Periksa link package serta akses Actions setelah rename; jangan membuat repo
   baru pada nama lama karena dapat menghilangkan redirect GitHub.
5. Ganti origin lokal ke `git@github.com:clarinovist/jagomat.git`, lalu verifikasi
   remote/akses read-only. Ubah status transisi dan perintah `gh --repo` dalam
   `CLAUDE.md`, README, dan panduan ini menjadi nama aktual. Link run historis
   boleh tetap memakai redirect, tetapi jangan salah menganggap nama lama kanonis.
6. Dengan izin menjalankan CI berikutnya, buktikan workflow di repo baru tetap
   menerbitkan/memverifikasi kedua image di namespace **lama**. Jangan memakai
   hasil CI sebelum rename sebagai bukti izin package setelah rename.

Tidak ada rename image, perubahan policy VPS, SSH produksi, migrasi data, atau
pengaktifan deploy rutin pada pekerjaan penamaan ini. Build/probe image tetap
milik CI; jangan build di VPS. Prosedur rilis: [production-release.md](production-release.md).

## Pemulihan

- Sebelum rename GitHub: kegagalan gate/CI menahan rename; origin tetap valid.
- Sesudah rename GitHub: bila akses package gagal, tahan rilis dan periksa izin
  repo/package; jangan memperlonggar allowlist verifier/deployer agar lolos.
  Rename kembali hanya setelah koordinasi, nama lama masih tersedia, dan tidak
  ada run aktif; remote/status dokumentasi harus mengikuti keadaan aktual.
- Pemulihan lokal dilakukan setelah koordinasi sesi: pastikan `osn` benar-benar
  symlink ke folder ini, lepaskan **symlink saja**, kemudian pindahkan direktori
  `jagomat` kembali ke `osn`. Jangan overwrite direktori yang muncul di nama lama,
  jangan reset/stash/checkout perubahan kerja, dan jangan menghapus data.

Nama repo, lokasi checkout, namespace artefak, dan keadaan produksi adalah empat
hal berbeda. Perubahan salah satunya tidak membuktikan tiga lainnya selesai.
