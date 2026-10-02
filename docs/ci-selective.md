# GitHub Actions hybrid

Workflow **CI Hybrid** memisahkan feedback pengembangan dari bukti rilis. Palang
awal tetap berjalan pada setiap event; full suite, recovery, dan build tidak lagi
dijalankan pada setiap push kode.

## Tiga jalur

| Pemicu | Pemeriksaan | Artefak rilis |
| --- | --- | --- |
| Push `main`, hanya dokumen allow-list | Palang nama berkas/index, validasi dokumen, test helper CI, dan kompilasi Python | Tidak ada |
| Push `main`, ada berkas lain | Pemeriksaan awal di atas + satu job test cepat: smoke inti dan test yang langsung terdampak | Tidak ada |
| Schedule Senin 03.00 WIB | Pemeriksaan awal + full suite kandidat empat shard dan verifikasi exact-once | Tidak ada |
| `workflow_dispatch` | Pemeriksaan awal + full suite kandidat dan recovery, build/probe dua image, verifikasi pasangan, dan manifest | Candidate/recovery exact; deploy tetap nonaktif |

Push baru pada ref yang sama membatalkan run push lama. Schedule dan dispatch
berbagi antrean release, tidak dibatalkan oleh push, dan tidak berjalan bersamaan.

## Test cepat pada push

`scripts/ci_fast_tests.py` selalu menjalankan smoke test tetap untuk auth, database,
diagnosis, generator, reducer siklus belajar, palang murid, dan dispatch web. Ia
menambahkan:

- berkas test yang diubah;
- semua `test_<nama-modul>*` untuk modul Python aplikasi atau helper script yang
  berubah;
- test yang mengimpor modul terdampak, termasuk reverse-import transitif antarmodul
  aplikasi;
- pemetaan khusus untuk workflow, palang repo, Dockerfile/aset runtime, sharding,
  metadata rilis, deployer, dan verifier image.

Helper membaca seluruh rentang `before..after`, bukan hanya commit terakhir.
Metadata event/Git yang meragukan jatuh ke smoke tetap, bukan daftar kosong. Daftar
path tidak dicetak ke log atau summary. Seleksi ini memberi feedback awal; ia **bukan
bukti full regression** dan tidak boleh dipakai sebagai izin rilis.

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

## Audit mingguan

Cron workflow adalah:

```yaml
schedule:
  - cron: "0 20 * * 0" # Senin 03.00 WIB
```

Audit menjalankan seluruh test kandidat pada empat runner terisolasi. Tiap runner
tetap serial karena test HTTP berbagi socket. Manifest shard membuktikan setiap
nodeid kandidat berjalan tepat sekali. Audit tidak mengetes recovery, membangun
image, menerbitkan manifest pasangan, atau memasang aplikasi.

## Gate rilis manual

Sebelum release/cutover, jalankan workflow manual pada SHA `main` yang akan dirilis:

```bash
gh workflow run deploy.yml --repo clarinovist/jagomat --ref main
gh run list --repo clarinovist/jagomat --branch main
gh run watch <id-run> --repo clarinovist/jagomat --exit-status
```

Di GitHub: **Actions → CI Hybrid → Run workflow → main → Run workflow**. Dispatch
tidak punya input untuk melewati gate. Ia menjalankan full suite kandidat dan
recovery pinned, build/probe kedua image, uji pasangan exact, dan manifest pada SHA
yang sama. Job `pasang` tetap literal false selama mode migrasi. Aktivasi rutin
kelak harus mereview gate workflow, metadata, policy host, dan runbook bersama.

Full suite mingguan pada SHA lama tidak menggantikan dispatch rilis pada SHA target.
CI push maupun audit hijau bukan bukti artefak tersedia atau produksi sudah berubah.

## Status akhir

Check **Status CI** memvalidasi kombinasi job berdasarkan event:

- push dokumen: job test cepat/full/build harus skipped;
- push kode: test cepat harus sukses; full candidate/recovery/build harus skipped;
- schedule: full kandidat+agregat harus sukses; recovery/build harus skipped;
- dispatch: kandidat, recovery, agregat, dan build harus sukses;
- deploy harus tetap skipped pada mode saat ini.

Kegagalan, pembatalan, output klasifikasi invalid, event tak dikenal, atau skip yang
tidak sesuai membuat Status CI gagal. Jika memakai required check/branch protection,
gunakan **Status CI** sebagai check lintas jalur.

Penghematan berasal dari tidak menjalankan delapan runner suite dan dua build image
pada setiap push. Besarnya tetap dipantau dari runner-minute aktual; paralelisme
mengurangi waktu tunggu, bukan jumlah menit komputasi.
