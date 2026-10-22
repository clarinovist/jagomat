# Riwayat variasi dan keterbatasan soal

Catatan eksperimen 2 September dan 20 Oktober 2026, dipertahankan dari README
mesin pada 22 Oktober. Angka di bawah adalah sampel pada source/tanggal tersebut,
bukan inventaris terkini, bukti efektivitas, atau izin menambah template.
Status aktif: [katalog](catalog-corrections.md), [pilot](catalog-pilot.md),
[bank kalimat](story-frames.md), dan [pekerjaan tersisa](status-proyek.md).

### Melawan monoton (2 Sep 2026)

Monoton diukur sebagai "pola-kalimat unik": teks soal dengan seluruh
angka dinormalkan jadi `N`. Tiga jalur dipakai, urut dari yang paling
ampuh:

1. **Tambah template.** Statistika P3 dulu cuma 2 template — 3000 soal
   hanya melahirkan 6 bentuk kalimat. Ditambah `tabel_turus`,
   `piktogram`, `jangkauan_data` → 53 bentuk. Nol biaya per soal, dan
   `piktogram` sekaligus menambah jalur diagnosis baru (lupa mengali
   skala) yang tidak ada di template mana pun.
2. **Latar turunan parameter.** Beberapa template kombinatorik dulu
   punya satu cerita yang ditulis mati di f-string (roti & selai,
   pertemuan). Latarnya kini dipilih dari parameter lewat `_putar()` —
   deterministik, tanpa menambah parameter (parameter ikut
   `tanda_tangan`, menambahnya membatalkan bank soal + snapshot golden).
   Kombinatorik P5: 14 → 30 bentuk.
3. **Variasi cerita LLM** (`llm.py`, tombol manual di halaman cetak).
   Lapisan paling mahal dan paling rapuh — dipakai terakhir, bukan
   pertama. Kini punya latar berputar: `PERCOBAAN_LATAR` latar dicoba
   per soal, tiap (soal, latar) punya entri cache sendiri, jadi satu
   soal bisa punya beberapa cerita tanpa satu pun dibayar dua kali.

Catatan patch VPS di fase ini bersifat historis. Deployer sekarang bersumber
dari `scripts/deploy.py`; source teruji dan hash host harus cocok menurut
[runbook rilis](production-release.md), bukan menyalin patch lama.

### Gelombang 2 — akar masalahnya lebih luas (2 Sep 2026)

Gelombang 1 menutup dengan dugaan "template sudah ada, tinggal dipakai".
Dugaan itu **diverifikasi salah**: tidak ada satu pun template tidur di
topik mana pun. Yang benar:

```
SELURUH APLIKASI: 43 dari 85 template hanya punya <= 2 bentuk kalimat.
```

Separuh bank template menulis satu kalimat mati di f-string. Empat
perbaikan, dan yang menentukan bukan tekniknya melainkan **pilihan obat
per paket**:

| paket | obat | hasil |
|---|---|---|
| aritmatika-lanjut | latar berputar (8 template) | P5 18→34, P6 22→94 |
| geometri-datar | objek nyata seukuran cm | P4 11→39, P5 21→60, P6 21→63 |
| aritmetika-dasar | **tambah jenis soal**, bukan latar | 3→7 jenis, 3→11 bentuk |
| teori-bilangan | latar untuk KPK **saja** | P5/P6 7→11 |
| pengukuran | **tambah jenis soal**, bukan latar | 3→7 jenis; P4 18→67, P5 21→146, P6 21→147 |

`_putar()` naik jadi `templates.putar` karena dipakai bersama; kontrak
lengkapnya (deterministik atas parameter, bukan `hash()`, tanpa parameter
baru) ada di docstringnya.

**Kapan latar BUKAN obatnya.** Soal hitung murni tidak selalu penyakit.
`Hitung: 24 + 54 ÷ 3 × 2 − 7` memang bentuk yang benar untuk melatih
urutan operasi; membungkusnya jadi cerita menambah beban baca yang bukan
sedang diuji. Untuk paket seperti itu obatnya menambah **jenis soal**.
Aturan yang dipakai: latar diberi kalau ia bagian dari konsepnya (KPK
lewat "lampu berkedip bersamaan" — bentuk baku di naskah OSN), ditolak
kalau ia cuma bungkus (keterbagian, sisa pembagian, paritas).

**Metrik ada batasnya.** Untuk paket hitung murni, "pola-kalimat unik"
menabrak langit-langit struktural: satu template = satu pola, berapa pun
angkanya, jadi ambang 25 berarti 25 template untuk satu paket P5/P6.
Untuk aritmetika-dasar yang dikunci adalah **berapa jenis soal yang
dilatih** (≥7) — metrik yang benar untuk paket seperti itu.

Sisa di bawah ambang 25: 5 dari 29 kombinasi topik×level (dari 13).

**Pengukuran (2 Sep 2026).** Paket terakhir yang tercatat sebagai batas
yang diketahui. Obatnya menambah jenis soal, karena akar masalahnya bukan
kalimat mati — ketiga template lama sudah punya 3, 10, dan 8 varian —
melainkan paketnya cuma punya TIGA template dan dua di antaranya
sama-sama konversi waktu. Empat jenis baru dipilih karena masing-masing
membawa **jalur diagnosis yang belum ada**, bukan sekadar kalimat baru:

| jenis | miskonsepsi yang jadi bisa dibaca |
|---|---|
| `satuan_kuantitas` | lusin/kodi/gros/rim tertukar isinya (kodi dihitung 12) |
| `tangga_satuan_campuran` | satu faktor dipakai untuk semua suku |
| `satuan_luas_volume` | faktor 10 dipakai di satuan luas (harusnya 100/1.000) |
| `jam_selesai` | menit dijumlahkan melewati 60 tanpa menaikkan jam |

Tiga cacat ketahuan hanya dengan MEMBACA keluaran nyatanya, bukan dari
test yang lolos: `satuan_luas_volume` jarak 1 tangga kehilangan jalur H
(malrule "satu tangga kurang" = kunci); `satuan_kuantitas` angka kecil
kehilangan H juga (24 buah → 2 lusin: K dan H sama-sama 1); dan malrule
"arah terbalik" pada kuantitas menghasilkan angka seperti 1.250.000 yang
tidak akan ditulis anak mana pun — diganti "menyalin angka soal apa
adanya". Ketiganya diperbaiki di sumber parameternya dan dikunci test.


## Batas yang diketahui

- **Posisi kunci dan malrule modus (20 Okt 2026).** Generator keterbagian kini
  merotasi tiga bilangan tanpa mengubah arti malrule; data modus diacak setelah
  modus tunggal dipastikan. `modus.pertama` yang kebetulan benar dibuang, bukan
  diganti kunci+1. Data modus baru memiliki sedikitnya dua nilai berbeda agar
  jalur K tidak dibuat-buat. Kunci/malrule bank lama tetap dipertahankan, termasuk
  saat identitas soal dipakai ulang pada sesi baru; cetak guru membaca tabel
  tersimpan. Tidak ada koreksi diagnosis historis otomatis. Pola pengecoh
  keterbagian "dua dekat, satu jauh" masih terbuka. Guard baseline G1–G4 ada
  di `test_kualitas_soal_generik.py`: 204 pasangan
  template×level, lantai bentuk/parameter, jumlah jenis dan konsentrasi lembar.
  Lantai ini provisional, bukan skor kualitas; audit posisi semantik masih terbatas
  pada keterbagian/modus, dan klasifikasi bentuk lainnya belum final. Regresi: `test_question_position.py`
  dan `test_question_history.py` (seed tetap, solver mentah, snapshot sintetis).
  H modus dibuang bila kedua nilai berselisih satu sudah dipakai K, bukan digeser
  lebih jauh. Recovery wajib mempertahankan reader bank; revert seluruh patch
  tidak kompatibel dengan bank baru. Pasangan image recovery perlu diverifikasi
  sebelum deploy; hasil tes source bukan bukti kesiapan image pinned.

- **Hitung murni diukur lewat jenis, bukan ambang 25 kalimat.** Batch terpilih
  20 Okt menambah banyak kelipatan rentang, sisa jumlah/hasil kali, banyak prima
  rentang, dan jumlah kelipatan. Teori-bilangan P4 naik 3→7 jenis, P5 6→10;
  10 soal per lembar tetap. Sampel 100 seed: P4 71,3% kerangka unik (sebelumnya
  32%), P5 100% (sebelumnya67%); maksimum sebunyi rata-rata P4 2,0/P5 1,0.
  P6 tetap7 jenis/70%—tidak diubah batch ini. Ini ukuran bentuk, bukan bukti
  hasil belajar. Empat jenis memakai solver independen, malrule semantik dan
  mutation di `test_number_theory_expansion.py`. ID baru membutuhkan reader
  recovery yang mengenal template sebelum deploy; tidak mengubah soal lama.
  Aritmetika-dasar tetap7 jenis, dan batas ruang pola-bilangan di bawah tidak
  dilebarkan. `test_latar_teori_bilangan.py` tetap menolak cerita buatan.

- **Lembar 12 soal = 5 halaman.** Sudah dicoba dipadatkan; memangkas kotak
  Caraku mengurangi ruang tulis tanpa mengurangi halaman. Kotak yang terlalu
  kecil membuat anak berhenti menulis, dan kotak kosong tidak bisa dibedakan
  dari tidak bisa mengerjakan.

- **Tiga tipe soal variasinya tipis**: `titik_segitiga` 7 varian,
  `deret_geometri` 18, `deret_terbalik_geometri` 24. Batas matematis, bukan
  bug — memperlebar akan melewati level P3. Untuk 2 anak mingguan,
  `titik_segitiga` mulai berulang setelah ~2 bulan. Solusinya menambah tipe
  soal baru, bukan memaksa parameter yang ada.

- **Tabel malrule belum diuji ke anak nyata.** Disusun dari bentuk soalnya.
  Sebagian pasti meleset. Kalau anak menjawab di luar tabel, mesin mengaku
  tidak tahu dan menyerahkan ke guru — itu disengaja. Kolom `kode_usulan`
  dan `kode_final` disimpan terpisah supaya nanti bisa diukur seberapa
  sering mesin salah.
