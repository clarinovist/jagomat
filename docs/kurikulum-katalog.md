# Katalog kurikulum dan resep menambah jenis soal

`mesin/kurikulum_katalog.py` adalah **peta kurikulum** (data beku): label topik untuk
awam, topik cek gratis per kelas, dan grup mastery per topik. **Mesin soal** (kode:
`topics.py`, `topic_*.py`, `templates.py`, `generator.py`) tetap pembuat soal.
Katalog hanya mengimpor stdlib dan tidak boleh diimpor modul inti soal (`generator`
dan penutupan impornya).

`mesin/kurikulum_cp.py` memuat 85 butir CP Matematika Fase A–D (Kepka BSKAP 046/H/KR/2025)
dan `CP_PER_GRUP`: tiap grup katalog → butir CP + kecocokan (penuh/sebagian/prasyarat/
pengayaan; kosong = di luar CP, pengayaan olimpiade). Status pemetaan: **disahkan pemilik
20 Nov 2026** (`STATUS_PEMETAAN`); revisi Guru tetap lewat perubahan data ini. `butir_tanpa_grup()` = celah cakupan.

`mesin/kurikulum_override.py` menyimpan override admin untuk pemetaan CP per grup dan label awam per topik
di `/data/kurikulum.db` (DB terpisah; env `KURIKULUM_BERKAS_DB`). Katalog di kode tetap nilai bawaan: tanpa berkas, DB rusak,
atau baris tak sah berarti bawaan (dicatat di log). Tulis memakai revisi per kunci (konflik ditolak, "kembalikan ke bawaan" tetap
menaikkan revisi) dan audit; label harus 1-40 karakter, tanpa karakter kontrol, dan unik antar-topik. Grup/pola, urutan `KATALOG`,
`VERSI_KATALOG`, dan `hanya_manual` tidak bisa diubah. Penyambungan ke admin dan konsumen menyusul (3c/3d).

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

## Materi per kelas (`kurikulum_kelas.py`)

`kurikulum_kelas.py` memuat 40 bab Kurikulum Merdeka kelas 1–6 (sumber: daftar isi buku siswa Matematika SD/MI
2022, satu jilid per kelas) beserta sub-materi dan grup `KATALOG` yang melatihnya (kecocokan "ada"/"sebagian").
Data beku, hanya stdlib. Ketersediaan grup TIDAK ditulis di sana: status bab ("Sudah ada soal", "Perlu disempurnakan",
"Belum ada soal") dihitung halaman admin dari `Topik.komposisi["P<kelas>"]`, jadi grup yang baru ada di kelas lain
tidak dihitung. Mengubah bab atau rujukan grup = mengubah data ini dan menjalankan `test_kurikulum_kelas.py`.

Cetakan soal berpola AKTIF (`cetakan_store.aktif_untuk_bab`, C2) menambah jenis soal bab itu dan variasi "banyak" (tanpa dijalankan
saat render tabel). Aturan status: bab "belum" (tanpa soal kode) yang punya >= 1 cetakan aktif menjadi "sebagian" (Perlu
disempurnakan); status "ada"/"sebagian" dari kode tidak berubah. Kolom Dipakai tidak berubah (cetakan belum masuk sesi anak).
Tautan "Buatkan draf cetakan" (C3) tampil di bab berstatus belum/sebagian hanya bila kunci AI ada dan kuota draf harian tersisa; tautannya ke halaman
cetakan bab (tombol POST ada di sana). Draf AI tersimpan sebagai draf, jadi tidak mengubah status/jenis/variasi sampai disetujui.
