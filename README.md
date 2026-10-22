# Jagomat — Codebase

Aplikasi web latihan matematika SD: generator soal, diagnosis kesalahan,
siklus belajar terpandu, lembar cetak, dan laporan per anak. Prioritas saat ini
adalah alat guru les in-house, dengan pilot pivot memakai data sintetis dan
akses awal nonkomersial. [Status proyek dan pekerjaan tersisa](docs/status-proyek.md).
Pure Python stdlib; dependensi pengembangan hanya pytest dan pytest-xdist.

## Identitas repo dan folder

Brand publik **Jagomat**, domain kanonis **https://jagomat.id**. Folder lokal
kanonis `~/Documents/jagomat/`; `~/Documents/osn/` menjadi alias kompatibilitas
sementara, bukan salinan repo kedua. Struktur internal `mesin/` tetap.

Repo kanonis: **[clarinovist/jagomat](https://github.com/clarinovist/jagomat)**;
origin SSH `git@github.com:clarinovist/jagomat.git`. Nama GitHub lama mengalihkan ke
repo yang sama. Namespace image `ghcr.io/clarinovist/osn-mesin-latihan` sengaja
dipertahankan untuk deploy/recovery, bukan repo aplikasi kedua.
Kompatibilitas dan pemulihan: [panduan penamaan](docs/repository-naming.md).

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
cd /Users/nugroho/Documents/jagomat
# Contoh scoped test; pilih area yang diubah.
mesin/.venv/bin/python -m pytest mesin/__tests__/test_generator.py -q -W error -p no:cacheprovider
# Palang membaca index Git; jalankan setelah stage scope yang direview.
mesin/.venv/bin/python scripts/check_repo.py
```

Gunakan interpreter venv existing (lokal3.9.6; CI/container3.12). Full suite
sebelum rilis dijalankan melalui CI empat shard; jangan memakai `-n auto`
secara lokal karena test HTTP berbagi socket. Aturan lengkap di [CLAUDE.md](CLAUDE.md).

Palang repo memeriksa nama berkas di index Git, bukan isi berkas atau data
runtime. Kegagalan membaca Git membuat pemeriksaan gagal, bukan dianggap
bersih. Panduan penggunaan dan setup ada di [`mesin/README.md`](mesin/README.md).

### GitHub Actions hybrid

Setiap push ke `main` tetap mendapat palang, kompilasi, test kontrak CI, dan—untuk
kode—smoke test inti plus test langsung terdampak. Full suite kandidat berjalan
terjadwal setiap Senin 03.00 WIB. **Run workflow** manual adalah gate rilis lengkap:
full kandidat dan recovery, build/probe dua image, serta verifikasi pasangan exact.
Job deploy otomatis tetap nonaktif pada mode migrasi sekarang. Pantau check
**Status CI** dan lihat [panduan CI hybrid](docs/ci-selective.md).

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
