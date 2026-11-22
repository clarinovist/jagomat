# GitHub Actions

Workflow **CI Hybrid** memisahkan palang pengembangan dan build rilis. Sejak 22 Nov 2026
(keputusan pemilik) CI **tidak lagi menjalankan suite test**: job test cepat push, full
suite kandidat (empat shard + agregat), suite recovery, jadwal audit mingguan, dan input
`audit` sudah dihapus. Test dijalankan lokal secara terarah sesuai scope perubahan.

## Dua jalur

| Pemicu | Pemeriksaan | Artefak rilis |
| --- | --- | --- |
| Push `main` | Palang nama berkas/index, klasifikasi (validasi dokumen allow-list), test helper/kontrak CI, dan kompilasi Python | Tidak ada |
| `workflow_dispatch` | Pemeriksaan awal, lalu build/probe dua image, verifikasi pasangan, dan manifest; **tanpa** suite test | Candidate/recovery exact; deploy tetap nonaktif |

Push baru pada ref yang sama membatalkan run push lama. Dispatch memakai antrean
release, tidak dibatalkan oleh push, dan tidak berjalan bersamaan.

`scripts/ci_fast_tests.py`, `scripts/pytest_shard.py`, dan
`scripts/verify_pytest_shards.py` tidak lagi dipanggil workflow; ketiganya masih ada
di repo bila suatu saat jalur test CI dihidupkan kembali.

## Dokumen aman

Daftar eksplisit di `scripts/ci_changes.py`:

- `README.md`
- `docs/README.md`
- `docs/ci-selective.md`
- `CLAUDE.md`

Tidak ada wildcard `*.md` atau `docs/**`. Dokumen kontrak belajar, runbook produksi,
`docs/workflow-reference.md`, `mesin/README.md`, berkas baru, dan campuran dengan
kode tetap masuk jalur push kode. Rename diperiksa sebagai delete+add. Pemeriksaan
dokumen menolak non-UTF-8, konflik merge, symlink, dan tautan inline lokal yang
hilang. Palang repo memeriksa nama berkas, bukan pemindai secret isi berkas; review
manusia dan larangan data anak/kredensial tetap berlaku.

## Gate rilis manual

Dokumentasi kontrak/runbook di luar allow-list tetap menjalankan jalur push kode;
jangan memperluas allow-list untuk meloloskan harmonisasi. Commit dokumentasi
tanpa perubahan artifact aplikasi tidak memerlukan rebuild/restart produksi.
Catat revision image terakhir terpisah dari HEAD dokumentasi.

Sebelum release, jalankan workflow manual pada SHA `main` yang akan dirilis (±3–5 menit):

```bash
gh workflow run deploy.yml --repo clarinovist/jagomat --ref main
gh run list --repo clarinovist/jagomat --branch main
gh run watch <id-run> --repo clarinovist/jagomat --exit-status
```

Di GitHub: **Actions → CI Hybrid → Run workflow → main → Run workflow**. Dispatch
rilis menjalankan palang privasi/kompilasi, build/probe kedua image, uji pasangan
exact, dan manifest pada SHA yang sama, tanpa suite test. Job `pasang` tetap
literal false selama mode migrasi. Aktivasi rutin
kelak harus mereview gate workflow, metadata, policy host, dan runbook bersama.

Image hasil dispatch rilis tidak dibuktikan oleh suite test di CI; bukti test adalah
test terarah lokal pada scope yang berubah. CI push hijau bukan bukti artefak tersedia
atau produksi sudah berubah.

## Status akhir

Check **Status CI** memvalidasi kombinasi job berdasarkan event:

- push (dokumen maupun kode): palang harus sukses; build harus skipped;
- dispatch rilis: palang dan build harus sukses;
- deploy harus tetap skipped pada mode saat ini.

Kegagalan, pembatalan, output klasifikasi invalid, event tak dikenal, atau skip yang
tidak sesuai membuat Status CI gagal. Jika memakai required check/branch protection,
gunakan **Status CI** sebagai check lintas jalur.
