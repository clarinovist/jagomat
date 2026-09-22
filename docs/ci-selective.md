# GitHub Actions sesuai perubahan

Workflow `Build & Deploy` tetap dipicu setiap push ke `main`. Job **Palang dan
klasifikasi perubahan** selalu berjalan; yang dipilih adalah job beratnya,
bukan melewati seluruh workflow dengan `paths-ignore` atau pesan skip CI.

## Jalur otomatis

| Isi seluruh perubahan dalam satu push | Yang dijalankan |
| --- | --- |
| Hanya dokumen dalam daftar aman | Palang nama berkas di index, pemeriksaan dokumen, test kecil untuk seleksi CI/workflow/palang, kompilasi Python, dan Status CI |
| Ada berkas di luar daftar aman, termasuk campuran dokumen dan kode | Pemeriksaan awal + seluruh suite kandidat dan recovery + build/probe kedua image dan verifikasi pasangan |
| Rentang Git/event tidak pasti atau delta kosong | Jalur lengkap; kegagalan pemeriksaan awal tetap menahan proses |

Daftar aman eksplisit di `scripts/ci_changes.py`:

- `README.md`
- `docs/README.md`
- `docs/ci-selective.md`

Tidak ada pengecualian menyeluruh untuk `*.md` atau `docs/**`. Dokumen kontrak
belajar, runbook produksi, `CLAUDE.md`, `mesin/README.md`, dan berkas baru yang
belum ditinjau tetap memicu jalur lengkap. Perubahan daftar aman sendiri juga
memicu jalur lengkap karena helper merupakan kode.

Deteksi membaca seluruh diff `before..after` dari Git, bukan commit terakhir
atau daftar berkas payload/API yang bisa terpotong. Rename diperiksa sebagai
penghapusan dan penambahan sehingga path asal tidak hilang. SHA/checkout harus
cocok, `before` harus ancestor `after`, dan forced push tidak mendapat jalur
ringan. Riwayat hilang atau Git gagal dibaca tidak dianggap dokumen aman.

Pemeriksaan dokumen menolak teks non-UTF-8, konflik merge, symlink, dan tautan
inline lokal ke target yang tidak tersedia di repo. Tidak memeriksa jaringan,
anchor Markdown, semua ragam sintaks tautan, atau kebenaran makna dokumen.
Palang repo memeriksa **nama berkas**, bukan pemindai secret di dalam isi.
Review manusia dan larangan memasukkan data anak/kredensial tetap wajib.

## Menjalankan verifikasi lengkap secara manual

Di GitHub: **Actions → Build & Deploy → Run workflow → main → Run workflow**.
Dispatch manual selalu lengkap; tidak ada opsi untuk memaksa kode masuk jalur
dokumen. Dari CLI:

```bash
gh workflow run deploy.yml --repo clarinovist/jagomat --ref main
gh run list --repo clarinovist/jagomat --branch main
gh run watch <id-run> --repo clarinovist/jagomat --exit-status
```

Untuk setiap run, ringkasan **Pemilihan pemeriksaan** menjelaskan jalur dan
alasan pemilihannya tanpa mencetak nama berkas atau isi event.

## Status akhir dan rilis

**Status CI** selalu mengevaluasi hasil job yang diperlukan:

- Jalur dokumen sukses hanya jika pemeriksaan awal sukses dan seluruh job
  suite/agregat/build dilewati sesuai rencana.
- Jalur lengkap sukses hanya jika pemeriksaan awal, seluruh suite kandidat dan
  recovery, agregat manifest kandidat, serta build/probe/pair sukses.
- Kegagalan, pembatalan, output klasifikasi invalid/hilang, atau skip yang tidak
  semestinya tidak boleh menjadi hijau.
- Job `pasang` tetap literal false pada mode migrasi sekarang, termasuk manual.
  Status akhir juga menjaga job tersebut tetap dilewati. Aktivasi mode rutin
  kelak harus mereview keduanya bersama, bukan sekadar mengganti variable.

Jika kelak memakai required check/branch protection, gunakan **Status CI**
sebagai check lintas jalur. Nama check **Test kandidat** tetap ada untuk agregat
suite, tetapi memang skipped pada jalur dokumen. Konfigurasi branch protection
tidak diubah oleh optimasi ini.

**CI dokumen hijau bukan bukti kelayakan rilis**: tidak ada image atau manifest
rilis baru. Semua gate suite/image/pair tetap wajib pada pasangan SHA/digest
yang sama sebelum pemasangan. Rincian pin/mode, recovery dan status produksi
ada di [runbook rilis](production-release.md); CI sukses tidak otomatis deploy.

Tidak ada cache hasil test, seleksi subset test aplikasi, pengurangan probe,
perubahan recovery pinned, atau build lokal/VPS. Penghematan terjadi karena
job berat tidak dimulai pada push dokumen aman, bukan dengan mengurangi gate
pada perubahan aplikasi. Besar penghematan/tagihan bergantung runner dan kuota;
durasi job paralel tetap dijumlahkan sebagai pemakaian komputasi.
