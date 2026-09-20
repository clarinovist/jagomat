# Jagomat — Codebase

Aplikasi web latihan matematika SD: generator soal, diagnosis kesalahan,
siklus belajar terpandu, lembar cetak, dan laporan per anak.
Pure Python stdlib; dependensi pengembangan hanya pytest dan pytest-xdist.

## Identitas repo dan folder

Brand publik **Jagomat**, domain kanonis **https://jagomat.id**. Folder lokal
kanonis `~/Documents/jagomat/`; `~/Documents/osn/` menjadi alias kompatibilitas
sementara, bukan salinan repo kedua. Struktur internal `mesin/` tetap.

Target nama GitHub adalah `clarinovist/jagomat`. **Rename GitHub belum dilakukan**:
origin masih `clarinovist/osn-mesin-latihan` sampai patch pin image masuk `main`
dan lolos CI. Namespace image GHCR lama sengaja dipertahankan untuk deploy/recovery.
Urutan cutover dan pemulihan: [panduan penamaan](docs/repository-naming.md).

## Struktur

| Path | Peran |
|---|---|
| [`mesin/`](mesin/README.md) | Kode aplikasi, tes, aset runtime, Dockerfile, dan skrip cadangan |
| [`docs/`](docs/README.md) | Spesifikasi dan dokumentasi teknis aktif |
| `scripts/check_repo.py` | Palang isi repo dan nama berkas sensitif untuk CI |
| `.github/workflows/deploy.yml` | Test, build image, dan deploy |
| [`CLAUDE.md`](CLAUDE.md) | Panduan kontributor dan palang keamanan/arsitektur |

## Pengembangan

Jalankan dari root repo, dengan venv aplikasi yang sudah disiapkan:

```bash
mesin/.venv/bin/python -m pytest mesin/__tests__/ -q -n auto -W error
mesin/.venv/bin/python scripts/check_repo.py
```

Palang repo memeriksa nama berkas di index Git, bukan isi berkas atau data
runtime. Kegagalan membaca Git membuat pemeriksaan gagal, bukan dianggap
bersih. Panduan penggunaan dan setup ada di [`mesin/README.md`](mesin/README.md).

## Batas isi repo

Yang dilacak: kode, tes/fixture sintetis, aset yang digunakan aplikasi,
konfigurasi build/deploy, skrip operasional, dan dokumentasi teknis aktif.
Spesifikasi siklus berada di
[`docs/siklus-belajar-terpandu.md`](docs/siklus-belajar-terpandu.md).

Riset pasar, mockup, kurikulum, lembar contoh, dokumen bisnis, dan eksperimen
lama disimpan terpisah di folder lokal `../osn-resources/referensi/`. Folder itu bukan
dependensi aplikasi dan tidak diperlukan untuk menjalankan tes atau build.
Jangan menyalinnya kembali ke repo; `.gitignore` dan palang CI mencegahnya.

Data anak, kredensial, sesi, cadangan, cache, dan rencana kerja lokal tidak
boleh dilacak. Sebagian data lokal lama tetap berada di direktori ignored;
keberadaannya bukan izin untuk memasukkannya ke Git. Jangan gunakan
`git add -f` untuk melewati palang. Pembersihan berkas terkini tidak
menghapus salinan dalam riwayat Git.
