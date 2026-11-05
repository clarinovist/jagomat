# Glosarium teks guru

Berlaku untuk semua teks yang dibaca guru di aplikasi: halaman tinjauan, beranda,
profil anak, lembar persiapan, laporan. Aturannya: **kalimat pendek (paling banyak
sekitar 20 kata), kata kerja aktif, istilah internal tidak tampil.** Sapaan **Anda**,
peran **Guru**; "Pendamping" hanya nama fitur AI. Pegangan bahasa yang sama dengan
`docs/glosarium-cek.md` di Pusat Cek. Palang otomatis untuk halaman tinjauan:
`mesin/__tests__/test_bahasa_guru_tinjauan.py`.

## Istilah internal → kata guru

| Jangan tampil | Pakai |
|---|---|
| usulan / usulan mesin | dugaan Jagomat |
| provenance | dari mana penjelasan atau koreksi ini |
| koreksi transkripsi | koreksi salinan (yang diketik tidak sama dengan tulisan anak) |
| malrule / pola kesalahan terdaftar | pola kesalahan |
| probe | soal pemeriksaan |
| reducer / rencana reducer | langkah berikutnya |
| outcome / snapshot / bukti append-only | hasil yang sudah final |
| mengesahkan | membuat final / menjadi final |
| konfirmasi (sebagai kata kerja bebas) | tetap "Konfirmasi hasil sesi" bila merujuk tombol |
| server memeriksa | Jagomat memeriksa |
| dropdown | pilihan (kecuali kalimat yang sudah dikunci test lama) |
| prompt | pertanyaan yang tertulis |
| restatement | kotak "soal ini mintanya apa" |
| jawaban mandiri | jawaban sendiri |
| butir | soal |
| checkpoint | cek ulang |
| evaluasi berjeda | evaluasi setelah jeda |
| template / seed / level P3 | tidak disebut; sebut nama topik atau kelas |

## Istilah yang dipertahankan

`Belum yakin`, `Simpan draf`, `Konfirmasi hasil sesi`, `Tinjauan tercatat`, `Perlu diperiksa`,
`Tanyakan cara anak`, `Perlu pengenalan`, kode diagnosis B/K/H/E/T/N hanya pada pil kode guru,
`pancingan` (istilah pedagogi), `fokus`, `latihan`, `langkah berikutnya`.

## Pola kalimat

- Satu kalimat satu maksud. Pecah kalimat bertingkat.
- Sebut akibatnya ke guru, bukan mekanisme sistem: "hasil belum final", bukan
  "tidak mengesahkan outcome".
- Pertanyaan ke anak ditulis sebagai perintah ke guru: "Tanya: ...", "Minta anak ...".
- Peringatan menyebut yang harus dilakukan, bukan hanya larangan.
