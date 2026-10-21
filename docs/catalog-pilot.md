# Pilot perbaikan fondasi dan bank terkurasi

Status: **eksperimen offline, bukan migrasi katalog atau serving baru**. Ekspansi
template ditunda dalam pekerjaan ini. Lima konsep existing P6 dibandingkan:
pecahan campuran, kali/bagi pecahan, menyusul, windu→lustrum, LP tabung.

## Fondasi bersama

`assessment_revision.py` menambahkan `revisi_penilaian=1` hanya lewat opt-in
`OSN_PENILAIAN_REVISI=1` (default0). Berlaku pada dua pecahan, kecepatan/menyusul,
waktu lama dan cabang tabung LP. Parameter tanpa marker tetap perilaku lama,
termasuk katalog2 yang sudah terbit. Marker masuk identitas bank, tidak menulis
ulang kunci/malrule, keputusan manual atau snapshot/outcome historis.

Kontrak `rasional-eksak-v1` memakai parser Fraction terbatas: ekuivalen numerik
sah diterima, ekspresi/notasi ilmiah/daftar/satuan tidak ditebak. Kunci pembanding
berasal dari bank yang dibaca caller, bukan dihitung ulang untuk mengoreksi histori.
Kandidat setara kunci dibuang. Semua kandidat bernilai sama dari prosedur berbeda
dibuang, bukan memilih yang pertama; diagnosis payload ambigu menyerahkan ke guru.
Nudge dihapus, nilai prosedur eksak; ID baru memisahkan arti malrule yang berubah.

Tidak ada aktivasi produksi, perubahan pin atau migrasi data pada tahap pilot.
Recovery pinned belum mengenal revisi ini: perlu reader jembatan, pair exact dan
review manusia konten baru sebelum opsi tersebut boleh dipakai dalam produksi.
Persetujuan Batch A–C sebelumnya tidak mengesahkan revisi ini.

## Desain perbandingan

- **A:** generator saat permintaan sintetis, gate sama untuk setiap kandidat.
- **B:** 30 item tetap ditulis offline oleh agent, bukan salinan hasil generator;
  **belum ditinjau manusia**. Saat ini tanpa malrule, sehingga tidak eligible
  untuk diagnosis/PG aplikasi existing. B bukan representasi kualitas penulis manusia.
- **C:** parameter/output yang sama dengan A dihasilkan offline, digate lalu
  dibekukan ke paket draft. Pembacaan paket tidak memanggil generator/registry.

6 item per konsep per lengan =90. Blueprint cabang dan seed A/C dibekukan pada
skrip sebelum evaluasi; pool sama supaya matematika tidak menjadi confound A/C.
A/C belum berbeda seleksi manusia. B belum setara kemampuan diagnosis dengan A/C;
keterbatasan ini wajib dilaporkan, bukan disembunyikan dalam skor kelolosan.

Gate mesin terpisah dari review manusia. Pemeriksaan mesin: domain/fakta, kunci
oracle independen, prosedur tiap malrule, collision, codec invalid/ekuivalen,
integritas paket/replay, dan pemisahan field publik/guru. Ia **tidak membuktikan**
teks cukup menentukan soal, tidak ada bocoran semantik pada bahasa, solusi bagus,
atau siswa sungguh memakai prosedur yang diduga. Hal itu memerlukan review manusia.

Rubrik manusia identik: matematika teks, kewajaran konteks/bahasa, beban baca,
pembahasan dan diagnosis. Catat menit review/revisi/authoring secara nyata, bukan
waktu generasi mesin. Reviewer menerima urutan acak tanpa label lengan; perbedaan
jumlah malrule masih dapat memberi petunjuk lengan, jadi kebutaan tidak sempurna.

## Menjalankan dan membaca hasil

```bash
mesin/.venv/bin/python -B scripts/catalog_pilot.py --output /tmp/jagomat-pilot-baru
```

Output tidak boleh menimpa paket sebelumnya:
- `semua-kandidat.json`: seluruh90, termasuk kegagalan; bukan hanya yang lolos.
- `A/B/C-draft.json`: paket lolos gate mesin, semua masih draft dan terbit0.
- `review.html`, `review-buta.json`, `review.csv`: paket review guru dan lembar isian.
- `review-map.json`: pemetaan lengan untuk analisis setelah review.
- `hasil.json`: denominator, kegagalan, ketersediaan PG/malrule, replay dan waktu mesin.

Base SHA, status committed/WIP dan hash bytes source dicatat pada manifest yang
ikut paket; envelope item diikat pada digest manifest itu. Paket WIP belum bukti
release exact. Hash payload mengikat
fakta, teks, kunci, solusi, dan rule. Hash bukan pengesahan manusia atau autentikasi.
Tidak ada API yang memasukkan paket B/C ke `question_bank_store`: bank existing
masih memerlukan registry dan pembahasan dari template. Perubahan itu proyek lain.

## Cara mengambil keputusan

Jangan menyimpulkan unggul dari90 item yang semuanya lolos mesin. Lanjutkan review
manusia, catat semua kandidat yang ditolak, lalu bandingkan biaya per item layak,
kelengkapan cabang dan stok probe. Stress seed terpisah menguji keluarga matematika,
bukan menambah ukuran sampel review manusia. Outcome belajar, retensi, ketepatan
diagnosis pada anak, dan reliabilitas antarpenilai belum diukur.

Temuan audit lain (kuantitas, rata-rata, arsiran dan cabang di luar pilot) tetap
follow-up; jangan menyatakan seluruh97 template telah benar. Rujukan kontrak
sebelumnya: [koreksi katalog](catalog-corrections.md).
