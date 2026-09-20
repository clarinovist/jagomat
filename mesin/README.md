# Jagomat — Mesin Latihan

Alur mingguan: cetak lembar -> anak kerjakan di kertas -> masukkan hasil ->
baca laporan.

Folder proyek kanonis `~/Documents/jagomat/`. Alias `~/Documents/osn/` sementara
tetap tersedia untuk sesi/venv lama. Repo GitHub masih memakai nama lama sampai
cutover aman; lihat [panduan penamaan](../docs/repository-naming.md).

## Sekali saja (sudah dilakukan)

```bash
cd ~/Documents/jagomat/mesin
python3 -m venv .venv
./.venv/bin/pip install pytest
./.venv/bin/python setup_db.py
```

## Dipakai lewat website (cara utama)

**https://<domain-anda>** — akun `guru` (orang tua) atau `admin`
(pengelola).

Semuanya dari satu tempat, tidak perlu terminal:

**1. Buat sesi** — tombol "Buat sesi baru untuk <nama>" di halaman utama.
Seed-nya selalu baru dan berbeda antar anak, jadi soalnya tidak pernah
terulang dan Andi tidak bisa menyalin Bila.

**2. Cetak lembar** — kolom **Lembar** di tabel sesi:

- `soal` — untuk anak. Buka lalu Ctrl+P (Cmd+P).
- `kunci` — untuk kamu. Memuat kunci + tabel diagnosis, **jangan sampai
  terlihat anak**.

Cetak pada **skala 100%**, jangan "fit to page". Menyekalakan mengecilkan
kotak Caraku, padahal itu inti lembarnya.

**3. Masukkan hasil** — klik nomor sesinya. Ketik jawaban anak dan ringkasan
kotak "Caraku". Kode diagnosis muncul otomatis; kolom Kode hanya diisi kalau
kamu tidak setuju dengan usulan mesin.

**4. Baca laporan** — tautan "Lihat laporan perkembangan" di profil anak:

- **Progres penguasaan materi Jagomat** — seluruh target keterampilan kelas anak,
  bukan hanya yang sudah dikerjakan. Grafik memisahkan target menunjukkan pemahaman,
  masih dipelajari, perlu cek kembali, dan belum dinilai. Bukan seluruh kurikulum sekolah.
- **Penguasaan per materi** — persentase target yang sudah terbukti; buka topik untuk
  melihat target, pola, dan bukti. Belum dinilai bukan berarti tidak mampu.
- **Aktivitas 7 hari terakhir** — soal dikerjakan, benar, salah, dan ketepatan jawaban
  sebagai catatan sekunder. Rincian/tren latihan dapat dibuka, bukan skor penguasaan.
- **Lihat rencana belajar** — buka resume di laporan: tugas belum selesai, posisi
  belajar, materi/langkah berikutnya, jadwal, dan satu tindakan utama.
- **Perjalanan dan bukti / Detail per sesi** — rincian opsional dalam `<details>`.
  Panduan hitungan ada di bawah data, kamus penilaian ada di rincian teknis.

Tanggal aktivitas mengikuti pencatatan jawaban pertama, termasuk latihan berjalan;
untuk hasil kertas, ini tanggal input. Koreksi dapat mengubah hasil statistik, tetapi
status belajar tetap memakai bukti terkonfirmasi dan reducer yang sama dengan profil.

## Membaca kodenya

| Kode | Artinya | Tindakan |
|---|---|---|
| **K** | salah konsep | **yang paling penting** — ajar ulang |
| **B** | salah baca soal | latih baca, bukan ajar ulang materi |
| **H** | salah hitung | paling ringan, latihan saja |
| **E** | salah tulis akhir | kecerobohan menyalin |
| **T** | belum pernah lihat | bukan kegagalan, ini peta materi |
| **N** | menebak | berhenti nilai, tanya lisan dulu |

**Metrik utama jumlah K, bukan skor.** Anak dengan 9 H skor 3 lebih siap
daripada anak dengan 3 K skor 9.

Cara membaca polanya:

- **K = 0, H banyak** -> konsep sudah terbentuk; latih aritmetika, jangan
  tambah soal pola
- **K = 1-2 terkumpul di satu tipe** -> sasaran jelas, ajar ulang satu topik
  itu lalu uji dengan soal beda angka
- **K >= 3 tersebar** -> jangan naik level, turunkan dulu
- **B banyak** -> bukan masalah matematika; latihannya kotak "mintanya apa"
- **N banyak** -> hentikan penilaian, tanya lisan; kode lain tidak bisa
  dipercaya tanpa coretan

## Dipakai lokal di Mac (cadangan)

Berguna kalau VPS bermasalah, atau untuk menghasilkan PDF (container tidak
punya Chrome, jadi tautan `soal` di website menghasilkan halaman untuk
dicetak langsung dari browser, bukan berkas PDF).

```bash
cd ~/Documents/jagomat/mesin
./.venv/bin/python generate_worksheet.py --pdf   # cetak lembar + PDF
./.venv/bin/python serve.py             # halaman guru di 127.0.0.1:8724
```

Basis data lokal terpisah dari VPS. Pakai salah satu saja supaya datanya
tidak bercabang.

## Masuk & akun

Buka **/masuk**, isi nama & sandi. Sesi disimpan sebagai kuki HttpOnly
(`osn_sesi`, TTL 14 hari, SameSite=Lax; atribut Secure hanya dipasang saat
permintaan benar-benar lewat HTTPS — terdeteksi dari `X-Forwarded-Proto`
proxy atau env `OSN_HTTPS=1`, bukan nama host, supaya kuki tetap tersimpan
di peramban anak yang membuka lewat HTTP LAN) — tidak ada popup peramban. Admin diarahkan ke **/admin** setelah masuk; guru ke beranda;
murid ke halaman kerja. Keluar lewat tombol **Keluar** (POST /keluar) yang
menghapus sesi di server dan kuki di peramban. Percobaan masuk yang gagal
dibatasi 5 kali / 15 menit per nama+IP; akun yang tidak ada tetap menjalankan
PBKDF2 umpan (~120 ms) sehingga tidak dapat dibedakan lewat waktu respons.

## Akun & siswa

Tautan **"Akun & Siswa"** di menu pengguna (dropdown topbar) membuka
**/akun** — halaman dengan nav samping (sidebar) dan tiga section via
`?section=`:

- **akun** — ganti sandi (minimal 12 karakter, perlu sandi lama). Ganti
  sandi acak bawaan deploy dengan yang kamu ingat.
- **siswa** — tabel siswa: select tingkat + simpan, kolom status akun
  latihan (nama login anak, atau "belum ada login"), dan tombol Hapus.
  Anak baru ditambahkan lewat kartu "Tambah anak" (satu pintu: siswa +
  akun latihannya sekaligus; nama login opsional, bawaan sama dengan
  nama anak). Anak yang kamu buat otomatis jadi milik keluargamu.
- **akun-murid** — tabel status akun latihan anak, setel sandi, tambah akun
  murid, hapus akun.

Section tak dikenal jatuh ke "akun". Setelah aksi POST, kamu kembali ke
section asalnya.

Menghapus akun latihan TIDAK menghapus anaknya — anak tetap ada di
tabel siswa, tinggal dikasih login baru dari section akun-murid. Sebaliknya,
menghapus siswa menghapus sesi, jawaban, dan diagnosisnya (riwayat yang
tidak bisa dibangun ulang), jadi siswa ber-riwayat sengaja tidak bisa
dihapus; siswa tanpa riwayat (salah ketik / data uji) boleh dihapus dan
akun latihannya ikut dihapus sekalian.

Admin melihat ketiga section dengan daftar SEMUA keluarga.

Untuk pemasangan lokal di Mac, daftar awal ada di `SISWA` pada
`setup_db.py` (aman dijalankan ulang).

### Tiga peran (multi-keluarga)

Aplikasi ini sekarang dipakai beberapa keluarga. Setiap akun di
`sandi.json` punya salah satu dari tiga peran:

- **admin** — pengelola produk: dashboard khusus di **/admin** berisi
  ringkasan jumlah keluarga/siswa/sesi, tabel keluarga dengan nama anak
  sebagai tautan ke `/laporan/<id>`, form buat akun orang tua, setel ulang
  sandi, dan hapus akun orang tua (typo/duplikat — anak & sesinya tetap).
  Admin full-write: boleh menulis data murid keluarga mana pun persis
  seperti guru (sesi baru, simpan/hapus sesi, cerita, lampiran, /akun
  semua section). Satu-satunya yang tetap tertutup: menyentuh akun/sandi
  sesama pengelola (milik deploy).
- **guru** — orang tua: hanya melihat anak yang jadi miliknya. Keluarga
  lain tidak lewat di matamu — bukan disembunyikan setengah-setengah,
  memang tidak ada di datamu.
- **murid** — anak: terikat ke satu siswa lewat `siswa_id` di akunnya,
  jadi nama login boleh berbeda dari nama tampilan anak.

Setiap halaman pengelola (guru & admin) punya **topbar dengan menu
pengguna** — dropdown CSS-only (`<details>`). Guru melihat "Akun & Siswa"
+ "Keluar"; admin melihat "Dashboard admin" + "Ganti sandi" + "Keluar".
Brand di topbar adalah tautan beranda (`/` untuk guru, `/admin` untuk admin).

Kepemilikan tertulis di kolom `siswa.pemilik` — username orang tuanya.
Guru membaca `WHERE pemilik = username-nya`; admin tanpa filter. Baris
ber-pemilik kosong itu warisan lama dan hanya terlihat admin. Kalau belum
ada admin, `serve.py` saat startup mempromosikan akun guru PERTAMA jadi
admin lalu membubuhkan namanya ke semua siswa warisan — otomatis,
idempoten, tanpa menyunting `sandi.json` lewat tangan.

Nama siswa kini unik per keluarga, bukan global: dua keluarga boleh
sama-sama punya "Bima". Nama akun (login) tetap unik global — kalau
tabrakan, pakai variasi nama.

Rute guru yang ber-id (sesi, laporan, lembar, lampiran, cerita) menolak
milik orang lain dengan **404**, bukan 403 — keberadaan id orang lain
bukan informasi yang boleh bocor. Orang tua baru boleh daftar sendiri di
**/daftar**; itu tetap terbuka justru karena isolasinya — pendaftar baru
melihat nol data keluarga mana pun.

## Cetak ulang lembar yang hilang

Seed tercantum di kolom terakhir tabel sesi dan di lembar kunci. Sesi lama
tetap bisa dibuka lewat tautan `soal` — lembarnya dibangkitkan ulang dari
seed, jadi selalu sama persis.

## Menjalankan test

```bash
# paralel di semua inti CPU — butuh pytest-xdist (pip install pytest-xdist)
./.venv/bin/python -m pytest __tests__/ -q -n auto

# atau serial
./.venv/bin/python -m pytest __tests__/ -q
```

## Susunan berkas

| Berkas | Isi |
|---|---|
| `templates.py` | tipe soal per level P3–P6 — soal, kunci, dan malrule dihitung dari parameter |
| `generator.py` | seed -> parameter, dibatasi profil level (`PROFIL_LEVEL`) |
| `schema.py` | definisi tabel |
| `database.py` | akses basis data |
| `diagnosis.py` | jawaban -> kode B/K/H/E/T/N |
| `worksheets.py` | fasad render HTML lembar soal & penilaian |
| `render.py` + `screen_style.py` + `print_style.py` | satu sumber render, dua tampilan (layar & cetak) |
| `generate_worksheet.py` | perintah cetak |
| `web.py` | router HTTP + palang peran/kepemilikan |
| `teacher_pages.py` | halaman guru: dashboard, sesi, konfirmasi hapus, lembar |
| `reports.py` | laporan per anak + diagnosa otomatis |
| `report_summary.py` | ringkasan deterministik berbasis perjalanan belajar |
| `account_pages.py` | halaman akun guru & admin |
| `landing.py` | halaman publik (daftar, masuk) — brand tautan beranda |
| `teacher_style.py` | CSS terpusat untuk halaman pengelola — token dari `design_tokens.py` |
| `students.py` | lapisan data siswa: soal, jawaban, kepemilikan akun |
| `student_pages.py` | halaman kerja murid — tanpa kunci/malrule/diagnosis (palang test) |
| `llm.py` | klien DeepSeek untuk variasi cerita — gagal-diam tanpa key |
| `sessions.py` | sesi cookie (berkas JSON atomik, TTL 14 hari, rate-limit) |
| `auth.py` | palang sandi, akun ber-peran admin/guru/murid |
| `serve.py` | menjalankan server + bootstrap admin |
| `cadangkan.sh` | tarik cadangan basis data latihan dan Pendamping dari VPS ke Mac |
| `Dockerfile` | container untuk VPS |

Generator soal per topik: `topics.py` (registrasi) + `topic_*.py`
(generator), topik besar punya pasangan `topic_*_param.py` (pembatas
parameter) dan `topic_*_svg.py` (renderer visual).

## Di VPS

| | |
|---|---|
| Alamat | https://<domain-anda> |
| Container | `osn-mesin`, restart otomatis |
| Data | `/opt/osn/data` (basis data, sandi, lembar) |
| Cadangan | harian 22:00 ke `mesin/cadangan/` di Mac; DB latihan dan Pendamping dipisah |

```bash
ssh <host-vps> "sudo docker ps --filter name=osn-mesin"
ssh <host-vps> "sudo docker logs osn-mesin --tail 30"
./cadangkan.sh          # cadangan manual kapan saja
```

Perubahan kode dideploy otomatis lewat GitHub Actions:

```
push ke main -> test -> build image -> dorong ke GHCR -> VPS tarik & ganti
             -> verifikasi situs hidup dari internet
```

Cukup `git push`. Tidak ada langkah manual di VPS, dan **jangan build di
VPS** — build yang gagal di sana bisa menjatuhkan situs yang sedang jalan.

Pantau:

```bash
gh run list --repo clarinovist/osn-mesin-latihan
gh run watch <id> --exit-status
```

**Kenapa deploy memakai digest, bukan tag `latest`**: tag bisa berubah
antara build dan deploy. Yang terpasang harus persis image yang baru saja
lolos test.

**Kalau deploy gagal**, skrip di VPS memulihkan image sebelumnya sendiri.
Container hanya diganti setelah image baru terbukti ada, dan hanya
dipertahankan kalau lolos pemeriksaan sehat. Sehat berarti menjawab **401**
tanpa kredensial — server hidup dan palang sandi aktif. Menjawab 200 tanpa
diminta sandi justru berarti palangnya jebol.

### Akses deploy

Kunci deploy terpisah dari kunci pribadi, dipasang dengan `command=` di
`authorized_keys` sehingga hanya `/usr/local/bin/osn-deploy` yang bisa
jalan. Kalau kunci itu bocor, yang bisa dilakukan penyerang terbatas pada
menarik image dan mengganti satu container — bukan shell, bukan sudo.

Secret yang dipakai: `VPS_DEPLOY_KEY`, `VPS_HOST_KEY`, `VPS_HOST`,
`VPS_USER`, `SITUS`.

### Kunci DeepSeek (fitur variasi cerita)

Fitur "variasi cerita" (`llm.py`) membaca kunci API dari env
`DEEPSEEK_API_KEY` di dalam container. Rantainya di VPS:

1. Kunci disimpan sebagai berkas `/opt/osn/data/deepseek.key`
   (volume data, owner `osn`, mode 640). Sumber aslinya script monitoring
   cron di `/root/monitoring/deepseek-balance.py` — salin manual dari sana
   kalau berkasnya hilang. Kunci TIDAK pernah ada di repo, image, atau log.
2. `osn-deploy` (di VPS) membaca berkas itu saat deploy dan menyuntikkannya
   sebagai `-e DEEPSEEK_API_KEY=...` ke `docker run` — di jalur deploy baru
   maupun rollback.
3. Tanpa berkas/env itu, fitur mati diam-diam sesuai desain gagal-diam:
   tombol cerita hanya melapor bahwa LLM tidak aktif, aplikasi tetap jalan.
4. `DEEPSEEK_MODEL=deepseek-flash` dan
   `DEEPSEEK_VISION_MODEL=deepseek-flash` diset eksplisit di `osn-deploy`
   (pola sama dengan kunci: env `docker run`). Nama kanonik ini dipakai
   agar aplikasi tidak bergantung pada alias atau nama eksperimen berversi.
   Model reasoning tetap membutuhkan `max_tokens` besar (sudah diatur di
   `llm.MAX_TOKENS` dan `llm.MAX_TOKENS_VISION`). Kedua env harus hadir di
   jalur deploy utama maupun rollback.

Respons API LLM di-cache per soal (`llm_cache`) — satu soal tidak dibayar
dua kali. Kunci cache = hash(`template_id` + parameter + latar + versi
prompt + model). `template_id` WAJIB ada di situ: tanpa itu dua template
berbeda yang kebetulan berparameter sama berbagi entri (terukur 354
tabrakan di bank soal), dan karena cache hit pulang tanpa verifikasi,
soal yang satu tampil memakai cerita milik soal yang lain. Saldo dipantau
oleh cron harian yang sama dengan sumber kuncinya.

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

Patch ini hanya ada di VPS (`/usr/local/bin/osn-deploy` tidak ter-track);
backup sebelum patch: `/root/osn-deploy.bak.<tanggal>`.

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

- **Tiga paket masih di bawah ambang variasi, dan itu disengaja**
  (gelombang 2, 2 Sep 2026). `teori-bilangan` P4 tetap 4 bentuk kalimat
  karena ketiga templatenya (keterbagian, sisa pembagian, paritas)
  hitung murni — memberi cerita akan mengaburkan konsep yang sedang
  diuji. `aritmetika-dasar` berhenti di 11 karena metriknya menabrak
  langit-langit struktural (lihat "Melawan monoton"). `pengukuran` SUDAH
  dikerjakan (2 Sep 2026): empat jenis soal baru membawanya dari 18/21/21
  ke 67/146/147, jadi paket ini tidak lagi jadi batas. Perbaikan yang
  benar untuk dua sisanya **menambah jenis soal**, bukan menambah latar —
  pekerjaan tersendiri.
  Angka-angka itu dikunci test supaya tidak diam-diam turun, dan
  `test_latar_teori_bilangan.py` juga akan MENOLAK kalau seseorang
  membungkus template hitung murni dengan cerita demi menaikkan metrik.

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

- **Data anak tidak masuk git.** `latihan.db` dan `lembar/` diblokir
  .gitignore.

- **Variasi cerita menulis ke bank soal bersama.** Baris `soal` di-share
  antar keluarga (dedup per tanda tangan), jadi kalau dua keluarga kebetulan
  dapat sesi ber-seed identik dan salah satunya menekan "variasi cerita",
  teks kalimat di lembar keluarga lain ikut berubah — angka, kunci, dan
  diagnosis tidak. Perbaikan yang benar (cerita per `sesi_soal`) butuh
  migrasi sendiri. Selain itu, POST `/daftar` masih mengungkap keberadaan
  username yang sudah dipakai — perilaku lama, risikonya enumerasi akun.
