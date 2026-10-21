# Bank kalimat offline (Fase 4A)

Implementasi opt-in; **aktif di produksi sejak 21 Oktober 2026** setelah tinjauan
manusia Fase4 dan gate pasangan image lulus. Bukti exact di [runbook rilis](production-release.md).
AI membantu menyusun/memeriksa draf di luar aplikasi. Runtime tidak memanggil AI
untuk memilih bingkai, menentukan kunci, atau membuat malrule.

## Scope

`story_frames.py` memuat bank immutable `bingkai-2026-10-v1`: 18 bingkai untuk
KPK kejadian berulang (P5/P6), aturan perkalian pilihan (P5), dan jabat tangan (P5).
Ini variasi penyajian tiga konsep existing, bukan penambahan jenis/kurikulum.

- `OSN_BANK_KALIMAT=1` mengaktifkan bank **untuk snapshot baru**; default `0`.
  Produksi memasang flag1 secara eksplisit; default source tetap0. Nilai konfigurasi lain ditolak. Bank invalid gagal sebelum sesi tersimpan;
  savepoint writer menggulung perubahan parsial.
- Hook `question_views.penyajian_dari_soal` mendahulukan proyektor visual. Template
  di luar allowlist, level tak didukung, soal dengan penyajian, dan teks custom
  tidak ditimpa. KPK perintah murni/bentuk tak dikenal tetap memakai teks existing.
- Kunci, parameter, malrule, signature dan pembahasan tidak berubah. Fungsi template
  lama tidak diedit; semua reader riwayat menggunakan snapshot atau fallback lama.
- Snapshot tetap v1: teks exact + fingerprint existing, `asal_teks=bawaan`,
  `mode_representasi=teks-v1`. **Tidak ada ID/versi bank per baris DB**. Provenance
  minimum adalah bank immutable, hash konten, SHA rilis dan contoh sintetis di
  manifest artefak; jangan menyisipkannya ke field snapshot lain.
- Cache parafrase B2 untuk input bersnapshot menyertakan fingerprint sumber.
  Ini mencegah cerita dari sumber lain dipakai kembali; bukan pemeriksa makna
  seluruh keluaran LLM. Cache tanpa snapshot tetap kompatibel; tidak ada penghapusan
  cache atau perubahan database historis.

## Review dan rollout

Ekspor contoh tanpa DB/akun/provider:

```sh
mesin/.venv/bin/python scripts/story_frames_preview.py --output docs/plan/bingkai-review
```

Tujuan harus belum ada. `manifest.json` mencatat apakah bank sesuai commit; draf
belum committed tidak boleh diklaim artefak rilis. CI mengekspor dengan
`--require-committed` ke artefak manifest pasangan image. Teks bank yang berubah
memerlukan versi baru dan tinjauan; hash/versi bukan bukti semantik benar.

Tes meliputi seluruh bingkai, parameter publik, KPK murni, visual/custom, cache
sumber berbeda, rollback transaksi, snapshot lama dan C→B→C memakai recovery pinned.
CI image exact menguji opt-in pada data sintetis meskipun default aplikasi mati.
Hook pada `question_views.py` mengubah fingerprint operasi penyajian meskipun
schema JSON tetap v1. Baseline recovery Fase4 karena itu memuat hook/cache yang
sama, dengan komposisi writer teori-bilangan konservatif1; kandidat memakai2.
Fingerprint baru diukur, bukan dipetakan paksa ke hash lama. Probe soal C→B→C
juga membuktikan cache dua sumber berbeda tetap terpisah dan dibaca tanpa provider.
Full gate pasangan exact tetap wajib sebelum rilis.
Sebelum aktivasi produksi: tinjauan manusia atas 18 contoh, gate kandidat/recovery
exact, lalu perubahan konfigurasi dalam rollout terkontrol. Menonaktifkan bank
menghentikan penggunaan baru, tidak merender ulang atau mengubah riwayat.

## Fase 4B — paket cetak mandiri

Pemilik memilih **6 tantangan dua langkah KPK dan pencacahan untuk kelas 5**,
dengan solusi terpisah. `scripts/challenge_packet.py` memuat paket statis terkurasi,
tanpa akun/sesi/DB/Soal/REGISTRI/diagnosis/bukti penguasaan. Penanda `tantangan`
existing hanya tampilan, **bukan** pengaman pengecualian bukti, dan tidak dipakai di sini.

```sh
mesin/.venv/bin/python scripts/challenge_packet.py --output docs/plan/tantangan-review
```

Hasil: `soal.html` (tanpa solusi tersembunyi), `solusi.html`, dan manifest versi/hash.
Masing-masing tiga halaman A4, dua soal per halaman dengan ruang tulis50mm. Bisa
cetak/Simpan sebagai PDF melalui browser. Tidak ada menu aplikasi atau pengiriman
jawaban; tidak ada penilaian otomatis. Enam kunci diuji dengan enumerasi kejadian,
pasangan dan rute yang berbeda dari perhitungan pembahasan. JEV memberi second
opinion, bukan sertifikasi atau pengganti tinjauan manusia atas paket yang baru dibuat.
Ini tidak membuka kembali audit Pendamping atau fitur yang dibatalkan pada [indeks](README.md).
