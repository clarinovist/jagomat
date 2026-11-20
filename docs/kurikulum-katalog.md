# Katalog kurikulum dan resep menambah jenis soal

`mesin/kurikulum_katalog.py` adalah **peta kurikulum** (data beku): label topik untuk
awam, topik cek gratis per kelas, dan grup mastery per topik. **Mesin soal** (kode:
`topics.py`, `topic_*.py`, `templates.py`, `generator.py`) tetap pembuat soal.
Katalog hanya mengimpor stdlib dan tidak boleh diimpor modul inti soal (`generator`
dan penutupan impornya).

`mesin/kurikulum_cp.py` memuat 85 butir CP Matematika Fase A–D (Kepka BSKAP 046/H/KR/2025)
dan `CP_PER_GRUP`: tiap grup katalog → butir CP + kecocokan (penuh/sebagian/prasyarat/
pengayaan; kosong = di luar CP, pengayaan olimpiade). Status pemetaan: **draf, menunggu
tinjauan Guru Mutia** (`STATUS_PEMETAAN`). `butir_tanpa_grup()` = celah cakupan.

Nama publik berikut diturunkan dari katalog (tipe dan urutan tidak berubah):
`topik_awam.NAMA_AWAM`, `mastery_catalog.KELOMPOK`, `cek_gratis_skor.TOPIK_PER_KELAS`
dan `TOPIK_DASAR`. `TOPIK_LAMA` (riwayat sesi) dan `VERSI_KATALOG` (versi) tetap di tempat lama.

## Menambah jenis soal ke topik yang ada

1. **Mesin:** tambah template di modul topiknya (`topic_*.py`), daftarkan di `templates`
   dan `komposisi` level. Ikuti aturan soal di `docs/workflow-reference.md`
   (uji lintas seed x level, malrule, determinisme, kartu rumus, pembahasan).
2. **Katalog:** tambahkan id template ke pola grup yang sesuai di `KATALOG`
   (atau grup baru `(kode, nama, pola)`). Satu pola hanya di satu grup/topik.
   Naikkan `mastery_catalog.VERSI_KATALOG` bila target mastery berubah.
   Grup baru wajib punya entri `CP_PER_GRUP` (tes memaksa); nilai pemetaan dari isi soal.
3. **Flag rilis:** jika jenis soal masuk produksi bertahap, ikuti pola env di
   `*_versions.py` dan `docs/production-release.md`; cetak PG wajib di balik flag.
4. **Pin recovery:** perubahan yang menggeser fingerprint kontrak rilis butuh
   pin recovery diganti pada langkah rilis.
5. **Tes:** tes topik (seed x level), `test_mastery_targets.py`,
   `test_golden_identity.py`, `test_kurikulum_keselarasan.py`, dan `test_kurikulum_cp.py`.

## Menambah topik baru

1. Buat modul `topic_<nama>.py` yang mendaftarkan `Topik` (impor malas di
   `topics._pastikan_dimuat`, lihat komentar registry di `topics.py`).
2. Tambah `EntriTopik(topik_id, label_awam, grup)` di `KATALOG`. `label_awam=None`
   bila topik tidak tampil ke awam; bila ada, tambahkan id ke `URUTAN_LABEL_AWAM`
   dan pastikan labelnya unik.
3. Jadi topik cek? Tambahkan ke `TOPIK_CEK_PER_KELAS` (wajib punya label awam dan
   bukan `hanya_manual`). Topik baru yang belum siap mastery: pakai `hanya_manual=True`.
4. Jalankan `test_kurikulum_keselarasan.py` dan tes topik/mastery terkait.
