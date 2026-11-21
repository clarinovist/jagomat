"""Kartu rumus/teori singkat per konsep (poin c feedback Filia).

Pertanyaan Filia: "Apakah kita perlu menambahkan teori atau rumus untuk
anak pelajari, kemudian membuatkan soal lagi sesuai dengan rumus yg sudah
di pelajari?"

Jawaban yang diambil: ya, tapi TIDAK sebagai modul materi terpisah yang
harus dibaca sebelum boleh berlatih. Alasannya jujur — anak SD tidak
membaca teori yang tidak sedang ia butuhkan. Yang dipasang:

  1. kartu rumus muncul di halaman HASIL, tepat di konsep yang anak salah
     (saat ia paling siap menerima penjelasannya);
  2. kartu rumus juga bisa dibuka dari halaman kerja sebagai bantuan
     opsional (bukan gerbang).

Satu template TIDAK dapat satu kartu. 82 template hanya punya belasan
konsep; kartu dipetakan per KONSEP dan template menunjuk ke konsepnya.
Template tanpa pemetaan -> tidak ada kartu (lebih baik kosong daripada
teori basa-basi yang salah sasaran).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from learning_visuals import BantuanVisual
from template_labels import nama_tipe_soal


@dataclass(frozen=True)
class Kartu:
    """Satu kartu teori: judul + rumus/aturan + contoh singkat."""

    judul: str
    inti: str
    contoh: str = ""
    bantuan: Optional[BantuanVisual] = None


# Kartu per KONSEP. Bahasa sengaja bahasa anak SD: rumus ditulis dengan
# kata, bukan notasi aljabar, dan selalu disertai satu contoh berangka.
KARTU: dict[str, Kartu] = {
    "tambah_dasar": Kartu(
        judul="Menjumlah sampai 20",
        inti="Hitung maju dari bilangan yang lebih besar. Bila lewat 10, lengkapi ke 10 dulu.",
        contoh="8 + 5 = 8 + 2 + 3 = 13",
    ),
    "kurang_dasar": Kartu(
        judul="Mengurang sampai 20",
        inti="Hitung mundur dari bilangan awal. Bila lewat 10, kurangi sampai 10 dulu, lalu kurangi sisanya.",
        contoh="13 − 5 = 13 − 3 − 2 = 8",
    ),
    "nilai_tempat": Kartu(
        judul="Puluhan dan satuan",
        inti="Bilangan dua angka terdiri dari puluhan dan satuan. Angka kiri menyatakan banyak puluhan, angka kanan banyak satuan.",
        contoh="47 = 4 puluhan dan 7 satuan, karena 40 + 7 = 47.",
    ),
    "bandingkan_bilangan": Kartu(
        judul="Membandingkan bilangan",
        inti="Bandingkan puluhannya dulu. Bila sama, bandingkan satuannya. Tanda < dan > membuka ke bilangan yang lebih besar.",
        contoh="35 dan 53: puluhan 3 lebih kecil dari 5, jadi 35 < 53.",
    ),
    "bilangan_hilang": Kartu(
        judul="Mencari bilangan yang hilang",
        inti="Pakai operasi kebalikan: tambah dicari dengan kurang, kurang dicari dengan tambah. Lalu isi kotak dan cek hasilnya.",
        contoh="5 + ... = 8, maka 8 − 5 = 3. Cek: 5 + 3 = 8.",
    ),
    "perkalian_dasar": Kartu(
        judul="Perkalian bilangan dasar",
        inti="Perkalian berarti penjumlahan berulang dengan kelompok sama besar. Kalikan satuan dulu, lalu simpan puluhannya saat menjumlah hasil puluhan.",
        contoh="24 × 3: 4×3 = 12 (tulis 2, simpan 1), 2×3 + 1 = 7, hasilnya 72.",
    ),
    "pembagian_dasar": Kartu(
        judul="Pembagian sama rata",
        inti="Pembagian membagi jumlah total ke beberapa kelompok sama banyak — kebalikan dari perkalian.",
        contoh="72 ÷ 3 = 24, karena 24 × 3 = 72.",
    ),
    "nilai_tempat_ribuan": Kartu(
        judul="Nilai tempat ratusan dan ribuan",
        inti="Setiap posisi angka punya nilai pengali berbeda: satuan ×1, puluhan ×10, ratusan ×100, ribuan ×1.000.",
        contoh="Pada 4.528, angka 5 berada di ratusan sehingga nilainya 500, bukan 5.",
    ),
    "nilai_tempat_besar": Kartu(
        judul="Nilai tempat bilangan besar",
        inti="Nilai angka = angka × nilai tempatnya: satuan ×1, puluhan ×10, ratusan ×100, ribuan ×1.000, dan seterusnya. Bentuk panjang menjumlahkan nilai semua angka.",
        contoh="Pada 345.678, angka 4 di puluhan ribu bernilai 40.000. 345.678 = 300.000 + 40.000 + 5.000 + 600 + 70 + 8.",
    ),
    "urutkan_bilangan": Kartu(
        judul="Terbesar dan terkecil",
        inti="Lihat banyak angka dulu: bilangan yang angkanya lebih banyak lebih besar. Kalau banyak angkanya sama, bandingkan dari angka paling depan, lalu angka berikutnya.",
        contoh="Dari 4.372, 87, dan 5.210: 87 hanya 2 angka, jadi terkecil. Terbesar 5.210, sebab 5 lebih besar dari 4.",
    ),
    "tambah_kurang_bersusun": Kartu(
        judul="Penjumlahan dan pengurangan bersusun",
        inti="Mulai dari kolom satuan. Jumlah 10 atau lebih: tulis satuannya dan simpan 1 ke kolom berikutnya. Angka atas lebih kecil: pinjam 1 dari kolom berikutnya (jadi 10 lebih banyak), kolom itu berkurang 1.",
        contoh="468 + 357: 8 + 7 = 15, tulis 5 simpan 1; 6 + 5 + 1 = 12, tulis 2 simpan 1; 4 + 3 + 1 = 8. Hasilnya 825.",
    ),
    "kali_bagi_sekolah": Kartu(
        judul="Perkalian dan pembagian habis",
        inti="Pecah bilangan menurut nilai tempat lalu kalikan tiap bagian, jumlahkan hasilnya. Pembagian dicek dengan perkalian: hasil bagi dikali pembagi harus sama dengan bilangan yang dibagi.",
        contoh="348 × 25 = (348 × 20) + (348 × 5) = 6.960 + 1.740 = 8.700. 7.200 ÷ 36 = 200, karena 36 × 200 = 7.200.",
    ),
    "kalimat_matematika": Kartu(
        judul="Kalimat matematika",
        inti="Bilangan yang hilang dicari dengan operasi kebalikan: tambah dengan kurang, kali dengan bagi. Cek dengan memasukkan jawaban ke kalimatnya.",
        contoh="45 + ... = 120, maka 120 − 45 = 75. Cek: 45 + 75 = 120.",
    ),
    "kenali_bentuk": Kartu(
        judul="Mengenal bentuk bangun datar",
        inti="Segitiga punya 3 sisi dan 3 sudut. Persegi punya 4 sisi yang semuanya sama panjang. Persegi panjang punya 4 sisi: sisi yang berhadapan sama panjang, tetapi sisi panjang dan sisi pendeknya berbeda. Lingkaran itu bulat, tanpa sisi lurus dan tanpa sudut.",
        contoh="Uang logam itu bulat dan tidak punya sudut, jadi bentuknya lingkaran.",
    ),
    "ukur_satuan_tak_baku": Kartu(
        judul="Mengukur panjang dengan satuan buatan sendiri",
        inti="Ukur benda dengan satuan yang sama, lalu bandingkan angkanya: makin banyak satuan yang muat, makin panjang bendanya. Lebihnya dicari dengan mengurangi. Dua benda yang disambung panjangnya ditambah.",
        contoh="Pensil 6 klip dan buku 9 klip. Buku lebih panjang 3 klip, karena 9 - 6 = 3. Kalau disambung, 6 + 9 = 15 klip.",
    ),
    "baca_diagram_gambar": Kartu(
        judul="Membaca diagram gambar",
        inti="Satu titik mewakili satu benda. Hitung titik pada tiap baris satu per satu. Baris yang titiknya paling banyak adalah yang terbanyak. Lebihnya dicari dengan mengurangi, jumlahnya dengan menambah.",
        contoh="Bola 3 titik dan mobil 5 titik. Mobil yang terbanyak. Lebihnya 5 - 3 = 2, jumlahnya 3 + 5 = 8.",
    ),
    "pola_posisi": Kartu(
        judul="Pola dan posisi benda",
        inti="Pola berulang punya bagian yang diulang terus. Cari bagian itu, lalu lanjutkan ke benda berikutnya. Untuk posisi, susun bendanya dulu dari kiri ke kanan, dari atas ke bawah, atau dari depan ke belakang, baru jawab.",
        contoh="Merah, biru, merah, biru, merah, ... Bagian yang berulang: merah, biru. Setelah merah datang biru.",
    ),
    "pecahan_setengah": Kartu(
        judul="Setengah dan seperempat",
        inti="Setengah berarti dibagi 2 sama banyak. Seperempat berarti dibagi 4 sama banyak. Untuk mencari yang tersisa, kurangkan: jumlah semua dikurangi bagian yang sudah diberikan.",
        contoh="Setengah dari 12: 12 ÷ 2 = 6. Seperempat dari 12: 12 ÷ 4 = 3. Sisa setelah seperempat diberikan: 12 − 3 = 9.",
    ),
    "waktu_berat_awal": Kartu(
        judul="Jam penuh dan berat dalam kg",
        inti="Lama kegiatan = jam selesai dikurangi jam mulai. Waktu setelah beberapa jam = jam sekarang ditambah jam yang berlalu. Berat yang satuannya sama, yaitu kg, ditambah untuk mencari jumlah dan dikurangi untuk mencari selisih.",
        contoh="Mulai pukul 2, selesai pukul 5: 5 - 2 = 3 jam. Kantong 2 kg dan 3 kg: 2 + 3 = 5 kg, selisihnya 3 - 2 = 1 kg.",
    ),
    "turus_gambar_awal": Kartu(
        judul="Membaca diagram turus",
        inti="Satu garis (|) berarti satu benda. Lima garis ditulis sebagai satu kelompok yang bernilai 5, jadi hitung 5, 5 + 5, dan seterusnya, lalu tambahkan garis sisanya. Yang terbanyak adalah baris dengan garis paling banyak. Selisih dicari dengan mengurangkan, jumlah semuanya dengan menambahkan.",
        contoh="||||| || berarti 5 + 2 = 7. Apel 7 dan jeruk 3: selisihnya 7 - 3 = 4, jumlahnya 7 + 3 = 10.",
    ),
    "ukur_konversi_awal": Kartu(
        judul="Mengubah satuan panjang dan berat",
        inti="1 m = 100 cm dan 1 kg = 1.000 g. Dari satuan besar ke satuan kecil angkanya DIKALI (m ke cm dikali 100, kg ke g dikali 1.000); dari satuan kecil ke satuan besar DIBAGI. Kalau ada dua satuan, ubah dulu yang besar menjadi satuan kecil, lalu tambahkan sisanya.",
        contoh="2 kg 500 g = 2 × 1.000 g + 500 g = 2.500 g. 300 cm = 300 : 100 = 3 m.",
    ),
    "bandingkan_ciri_bangun": Kartu(
        judul="Membandingkan ciri bangun datar",
        inti="Sumbu simetri adalah garis lipat yang membuat dua bagian saling menutupi tepat: persegi 4, persegi panjang (bukan persegi) 2, segitiga sama sisi 3, belah ketupat (bukan persegi) 2, layang-layang (bukan belah ketupat) 1. Sisi sejajar tidak akan bertemu walau diperpanjang: persegi, persegi panjang, jajar genjang, dan belah ketupat punya 2 pasang, trapesium 1 pasang, segitiga 0. Sudut siku-siku seperti pojok kertas: persegi dan persegi panjang punya 4, segitiga siku-siku 1. Untuk membandingkan, cari dulu banyaknya pada tiap bangun, lalu kurangkan.",
        contoh="Persegi punya 4 sumbu simetri dan persegi panjang 2. Selisihnya 4 − 2 = 2.",
    ),
    "peluang_dasar": Kartu(
        judul="Kemungkinan dan peluang sederhana",
        inti="Warna yang bolanya paling banyak paling mungkin terambil. Kejadian yang pasti terjadi disebut pasti, yang tidak mungkin terjadi disebut mustahil. Peluang = banyak yang diinginkan dibagi banyak semua kemungkinan.",
        contoh="Kantong berisi 3 bola merah dan 2 bola biru. Peluang terambil bola merah = 3/5, karena ada 3 bola merah dari 5 bola.",
    ),
    "bilang_benda_awal": Kartu(
        judul="Membilang benda dan mengenal bilangan sampai 10",
        inti="Hitung benda satu per satu sambil menunjuk, mulai dari satu. Bilangan terakhir yang kamu sebut adalah banyak bendanya. Kata bilangan: satu, dua, tiga, empat, lima, enam, tujuh, delapan, sembilan, sepuluh. Satu lebih banyak berarti maju satu langkah, satu lebih sedikit berarti mundur satu langkah.",
        contoh="● ● ● ● ● dihitung 1, 2, 3, 4, 5, jadi ada lima benda. Bilangan yang lebih dari 6 dan kurang dari 8 adalah 7.",
    ),
    "tambah_kurang_20": Kartu(
        judul="Menjumlah dan mengurang sampai 20",
        inti="Menjumlah melewati 10: genapkan dulu bilangan pertama menjadi 10, lalu tambahkan sisanya. Mengurang dengan meminjam: kurangi satuannya dulu sampai 10, lalu kurangi sisanya dari 10. Bilangan yang hilang dicari dengan operasi kebalikan: dari hasil ambil bilangan yang sudah ada.",
        contoh="8 + 5: 8 butuh 2 supaya 10, sisa 3, jadi 13. 15 − 7: 15 − 5 = 10, sisa 2, jadi 10 − 2 = 8. 9 + ... = 15: 15 − 9 = 6.",
    ),
    "tambah_kurang_100": Kartu(
        judul="Menambah dan mengurang sampai 100",
        inti="Tambah dan kurang dari satuan dulu, lalu puluhan. Kalau satuan ditambah lebih dari 9, tulis satuannya dan simpan 1 puluhan. Kalau satuan tidak cukup untuk dikurangi, pinjam 1 puluhan dari puluhan. Bilangan yang hilang dicari dengan kebalikan: hilang pada penjumlahan dicari dengan mengurang, hilang pada pengurangan bagian depan dicari dengan menambah.",
        contoh="38 + 27: satuan 8 + 7 = 15, tulis 5 simpan 1; puluhan 3 + 2 + 1 = 6; jadi 65. 52 − 28: satuan 2 kurang dari 8, pinjam 1 puluhan: 12 − 8 = 4; puluhan 4 − 2 = 2; jadi 24.",
    ),
    "unsur_bangun_datar": Kartu(
        judul="Sisi, sudut, sejajar, dan tegak lurus",
        inti="Segitiga punya 3 sisi dan 3 sudut, persegi dan persegi panjang 4 sisi dan 4 sudut, segilima 5, segienam 6. Sudut siku-siku seperti pojok kertas: persegi dan persegi panjang punya 4, segitiga siku-siku punya 1. Garis sejajar tidak pernah berpotongan walaupun diperpanjang. Garis tegak lurus membentuk sudut siku-siku.",
        contoh="Persegi panjang: sisi yang berhadapan sejajar, ada 2 pasang. Dua sisi yang bersebelahan membentuk sudut siku-siku, jadi saling tegak lurus.",
    ),
    "pecahan_senilai_desimal": Kartu(
        judul="Pecahan senilai, desimal, dan persen",
        inti="1/4 dari 20 berarti 20 dibagi 4. Pecahan senilai: pembilang dan penyebut dikali (atau dibagi) bilangan yang sama, nilainya tidak berubah. Untuk desimal dan persen, samakan penyebutnya menjadi 100: 3/4 = 75/100 = 0,75 = 75%. Persen artinya per seratus.",
        contoh="2/3 = 8/12 karena 2 × 4 = 8 dan 3 × 4 = 12. 3/4 = 75/100 = 0,75 = 75%.",
    ),
    "luas_petak_volume_kubus": Kartu(
        judul="Luas dengan petak dan volume dengan kubus satuan",
        inti="Luas persegi panjang = banyak petak satuannya = banyak baris × petak tiap baris. Volume balok = banyak kubus satuannya: hitung kubus satu lapis (baris × kubus tiap baris), lalu kalikan dengan banyak lapis. Untuk selisih, hitung dulu kedua luas atau volume, lalu kurangkan; kalau ada kubus tambahan, tambahkan di akhir.",
        contoh="3 baris, tiap baris 5 petak: luas 3 × 5 = 15 petak satuan. 3 lapis, tiap lapis 2 baris dan tiap baris 4 kubus: 2 × 4 = 8 kubus tiap lapis, jadi 3 × 8 = 24 kubus satuan.",
    ),
    "ciri_komposisi_bangun": Kartu(
        judul="Ciri, susunan, dan uraian bangun datar",
        inti="Sisi adalah garis lurus yang membatasi bangun, sudut adalah pojok tempat dua sisi bertemu. Persegi, persegi panjang, jajar genjang, belah ketupat, dan layang-layang punya 4 sisi dan 4 sudut; segitiga punya 3. Sisi sejajar tidak akan bertemu walau diperpanjang: persegi, persegi panjang, jajar genjang, dan belah ketupat punya 2 pasang. Dua persegi sama besar yang dirapatkan pada satu sisi penuh membentuk persegi panjang. Satu diagonal membagi segiempat menjadi 2 segitiga, kedua diagonal menjadi 4. Banyak persegi kecil pada susunan = banyak baris × banyak persegi tiap baris. Segitiga sama sisi: tiga sisi sama panjang; sama kaki: tepat dua sisi sama panjang; siku-siku: satu sudut siku-siku. Trapesium: tepat satu pasang sisi sejajar. Jajar genjang: sisi berhadapan sama panjang. Banyak keping penutup = luas bangun : luas satu keping. Segi-n dipotong dari satu titik sudut: n - 3 garis potong, n - 2 segitiga.",
        contoh="Susunan 3 baris, tiap baris 5 persegi kecil: 3 × 5 = 15 persegi kecil.",
    ),
    "keliling_gabungan": Kartu(
        judul="Keliling bangun datar dan bangun gabungan",
        inti="Keliling adalah panjang garis di sekeliling bangun: jumlahkan semua sisi di bagian luar. Persegi: 4 × sisi. Persegi panjang dan jajar genjang: 2 × (dua sisi yang berbeda). Belah ketupat: 4 × sisi. Layang-layang: 2 × (sisi pendek + sisi panjang). Segitiga dan trapesium: jumlah semua sisinya (tinggi bukan sisi). Lingkaran: π × diameter atau 2 × π × jari-jari, dengan π = 22/7 atau 3,14. Pada bangun gabungan, sisi yang saling menempel tidak ikut keliling. Bangun L, bangun T, dan bangun tangga berkeliling sama dengan persegi panjang yang membatasinya; pada bentuk U, dua dinding celah ikut menambah keliling.",
        contoh="Setengah lingkaran berjari-jari 7 cm (π = 22/7): lengkungan 22/7 × 7 = 22 cm, ditambah diameter 14 cm, jadi 36 cm.",
    ),
    "pecahan_bilangan_asli_desimal": Kartu(
        judul="Pecahan dengan bilangan asli, dan pecahan ke desimal",
        inti="Pecahan dikali bilangan asli: kalikan pembilangnya, penyebut tetap. Pecahan dibagi bilangan asli: kalikan penyebutnya. Sederhanakan hasilnya. Pecahan jadi desimal: buat penyebutnya 10, 100, atau 1000, lalu tulis dengan koma. Pecahan campuran jadi pecahan biasa: bulat × penyebut + pembilang, penyebut tetap. Hasil kali bisa lebih dari 1 dan ditulis 15/4. Dibulatkan satu angka: lihat angka kedua di belakang koma. Persen = per seratus.",
        contoh="3/8 x 2 = 6/8 = 3/4. 2/3 : 4 = 2/12 = 1/6. 3/4 = 75/100 = 0,75.",
    ),
    "kelipatan_rentang": Kartu(
        judul="Menghitung kelipatan dalam rentang",
        inti="Hitung kelipatan sampai batas akhir, lalu kurangi kelipatan sebelum batas awal. Kedua batas ikut dihitung.",
        contoh="Kelipatan 3 dari 10 sampai 25: 12, 15, 18, 21, 24. Banyaknya 5.",
    ),
    "sisa_operasi": Kartu(
        judul="Sisa penjumlahan dan perkalian",
        inti="Jika pembaginya sama, jumlahkan atau kalikan sisanya, lalu ambil sisa pembagian lagi.",
        contoh="Sisa 3 dan 4 terhadap 5: jumlah sisanya 7, lalu 7 dibagi 5 bersisa 2.",
    ),
    "prima_rentang": Kartu(
        judul="Menghitung bilangan prima",
        inti="Prima punya tepat dua faktor positif: 1 dan dirinya. Bilangan 1 bukan prima; 2 adalah prima genap.",
        contoh="Prima dari 10 sampai 20 adalah 11, 13, 17, 19: ada 4 bilangan.",
    ),
    "jumlah_kelipatan": Kartu(
        judul="Menjumlah kelipatan",
        inti="Kelipatan k berurutan adalah k×1, k×2, dan seterusnya. Jika ada q kelipatan, jumlahnya k×q×(q+1)÷2.",
        contoh="Kelipatan 3 sampai 14: 3+6+9+12 = 3×4×5÷2 = 30.",
    ),
    "rata_rata": Kartu(
        judul="Rata-rata",
        inti="Rata-rata = jumlah semua data ÷ banyaknya data.",
        contoh="Nilai 8, 6, 7 → (8+6+7) ÷ 3 = 21 ÷ 3 = 7.",
    ),
    "median_modus": Kartu(
        judul="Median dan Modus",
        inti="Median = nilai TENGAH setelah data diurutkan. "
             "Modus = nilai yang PALING SERING muncul.",
        contoh="Data 3, 7, 5 → urut jadi 3, 5, 7 → median 5. "
               "Data 2, 4, 4, 9 → modus 4.",
    ),
    "pola_bilangan": Kartu(
        judul="Pola bilangan",
        inti="Cari BEDA antara dua suku berdekatan. Kalau bedanya tetap, "
             "tambahkan beda itu untuk suku berikutnya.",
        contoh="7, 11, 15, … beda 4 → berikutnya 15 + 4 = 19.",
    ),
    "pola_korek": Kartu(
        judul="Pola korek api",
        inti="Hitung batang awal, lalu amati batang baru pada setiap langkah. "
             "Dari gambar 1 ke gambar 4 ada tiga langkah penambahan.",
        contoh="Awal 4 batang, tambah 3 tiap langkah: 4, 7, 10, 13. "
               "Ada 3 kali penambahan: 4 + 3 × 3 = 13.",
        bantuan=BantuanVisual("korek"),
    ),
    "pola_titik_segitiga": Kartu(
        judul="Pola titik segitiga",
        inti="Setiap gambar menambah satu baris yang lebih panjang. "
             "Jumlahkan banyak titik di setiap baris; pertambahannya bukan beda tetap.",
        contoh="Gambar 1–4 berisi 1, 3, 6, 10 titik. "
               "Empat baris pada gambar 4: 1 + 2 + 3 + 4 = 10.",
        bantuan=BantuanVisual("titik"),
    ),
    "pola_geometri": Kartu(
        judul=nama_tipe_soal("deret_geometri"),
        inti="Kalau tiap suku didapat dengan DIKALI angka yang sama, "
             "kalikan lagi untuk suku berikutnya.",
        contoh="1, 3, 9, 27, … dikali 3 → berikutnya 27 × 3 = 81.",
    ),
    "keliling_luas": Kartu(
        judul="Keliling dan Luas persegi panjang",
        inti="Keliling = 2 × (panjang + lebar). Luas = panjang × lebar.",
        contoh="p = 8, l = 3 → keliling = 2 × 11 = 22; luas = 8 × 3 = 24.",
    ),
    "luas_segitiga": Kartu(
        judul="Luas segitiga",
        inti="Luas = alas × tinggi ÷ 2. Tingginya harus TEGAK LURUS alas.",
        contoh="alas 10, tinggi 6 → 10 × 6 ÷ 2 = 30.",
    ),
    "volume": Kartu(
        judul="Volume kubus dan balok",
        inti="Volume balok = panjang × lebar × tinggi. "
             "Volume kubus = rusuk × rusuk × rusuk.",
        contoh="Balok 5 × 3 × 2 = 30. Kubus rusuk 4 → 4 × 4 × 4 = 64.",
    ),
    "sudut": Kartu(
        judul="Sudut",
        inti="Jumlah sudut dalam segitiga = 180°. "
             "Dua sudut berpelurus jumlahnya 180°; berpenyiku 90°.",
        contoh="Segitiga dengan 60° dan 70° → sudut ketiga = 180 − 130 = 50°.",
    ),
    "fpb_kpk": Kartu(
        judul="FPB dan KPK",
        inti="FPB = bilangan TERBESAR yang membagi habis keduanya. "
             "KPK = bilangan TERKECIL yang habis dibagi keduanya.",
        contoh="12 dan 18 → FPB 6, KPK 36.",
    ),
    "keterbagian": Kartu(
        judul="Ciri habis dibagi",
        inti="Habis dibagi 2 kalau satuannya genap; dibagi 3 kalau jumlah "
             "angkanya habis dibagi 3; dibagi 5 kalau satuannya 0 atau 5.",
        contoh="132 → 1+3+2 = 6, habis dibagi 3, jadi 132 habis dibagi 3.",
    ),
    "sisa_pembagian": Kartu(
        judul="Sisa pembagian",
        inti="Bagi, lalu SISANYA yang dipakai. Sisa selalu lebih kecil "
             "dari pembaginya.",
        contoh="115 ÷ 3 = 38 sisa 1 (karena 38 × 3 = 114, kurang 1).",
    ),
    "urutan_operasi": Kartu(
        judul="Urutan operasi",
        inti="Kerjakan kurung dulu, lalu kali/bagi (dari kiri), "
             "baru tambah/kurang (dari kiri).",
        contoh="2 + 3 × 4 = 2 + 12 = 14, bukan 20.",
    ),
    "pecahan": Kartu(
        judul="Pecahan",
        inti="Untuk menambah/mengurang, samakan penyebut dulu. "
             "Untuk mengali, kalikan atas dengan atas dan bawah dengan bawah.",
        contoh="1/2 + 1/3 = 3/6 + 2/6 = 5/6.",
    ),
    "pecahan_kali_bagi": Kartu(
        judul="Kali dan bagi pecahan",
        inti="MENGALI: atas × atas, bawah × bawah — penyebut TIDAK perlu "
             "disamakan. MEMBAGI: balik pecahan kedua, lalu kalikan.",
        contoh="2/3 × 3/4 = 6/12 = 1/2. "
               "2/3 : 3/4 = 2/3 × 4/3 = 8/9.",
    ),
    "bentuk_bilangan": Kartu(
        judul="Pecahan, desimal, dan persen",
        inti="Ketiganya bisa ditulis dalam bentuk yang sama. "
             "Pecahan → desimal: atas dibagi bawah. "
             "Desimal → persen: dikali 100. Persen → desimal: dibagi 100.",
        contoh="3/5 = 0,6 = 60%. Jadi 3/5 lebih besar dari 55%.",
    ),
    "pembulatan": Kartu(
        judul="Pembulatan dan taksiran",
        inti="Lihat angka di sebelah kanan tempat yang dibulatkan. "
             "Kurang dari 5 → dibulatkan ke bawah; 5 atau lebih → ke atas. "
             "Untuk menaksir: bulatkan DULU, baru dihitung.",
        contoh="248 ke ratusan = 200 (karena 48 kurang dari 50). "
               "248 + 173 ditaksir 200 + 200 = 400.",
    ),
    "perbandingan": Kartu(
        judul="Perbandingan dan skala",
        inti="Skala 1 : n berarti 1 cm di peta = n cm asli. "
             "Perbandingan senilai: kalau satu naik, yang lain ikut naik.",
        contoh="Skala 1 : 1.000 dan jarak peta 4 cm → asli 4.000 cm = 40 m.",
    ),
    "waktu": Kartu(
        judul="Satuan waktu",
        inti="1 menit = 60 detik, 1 jam = 60 menit. "
             "1 windu = 8 tahun, 1 dasawarsa = 10 tahun, 1 abad = 100 tahun.",
        contoh="70 windu = 70 × 8 = 560 tahun.",
    ),
    "persen": Kartu(
        judul="Persen, diskon, untung-rugi",
        inti="x% dari harga = harga × x ÷ 100. Setelah DISKON x%, "
             "harga tinggal (100 − x)% dari harga awal. "
             "Untung/rugi selalu dihitung dari harga BELI.",
        contoh="Harga 200.000 diskon 25% → 200.000 × 75 ÷ 100 = 150.000.",
    ),
    "kecepatan": Kartu(
        judul="Kecepatan, jarak, waktu",
        inti="Jarak = kecepatan × waktu. Kecepatan = jarak ÷ waktu. "
             "Waktu = jarak ÷ kecepatan.",
        contoh="Jarak 343 km, kecepatan 49 km/jam → waktu = 343 ÷ 49 = 7 jam.",
    ),
    "berpapasan": Kartu(
        judul="Berpapasan dan menyusul",
        inti="BERPAPASAN (berlawanan arah): kecepatan DIJUMLAH, "
             "waktu = jarak ÷ jumlah kecepatan. "
             "MENYUSUL (searah): kecepatan DIKURANG, "
             "waktu = selisih jarak ÷ selisih kecepatan.",
        contoh="Jarak 285 km, 59 + 36 = 95 km/jam → 285 ÷ 95 = 3 jam.",
    ),
    "debit": Kartu(
        judul="Debit",
        inti="Debit = volume ÷ waktu. Volume = debit × waktu. "
             "Waktu = volume ÷ debit.",
        contoh="200 liter dengan debit 25 liter/menit → 200 ÷ 25 = 8 menit.",
    ),
    "satuan_konversi": Kartu(
        judul="Tangga satuan",
        inti="Turun satu tangga DIKALI 10, naik satu tangga DIBAGI 10 "
             "(km-hm-dam-m-dm-cm-mm). Satuan berat sama polanya "
             "(kg-hg-dag-g-dg-cg-mg).",
        contoh="380 kg → g turun 3 tangga → 380 × 1.000 = 380.000 g.",
    ),
    "satuan_kuantitas": Kartu(
        judul="Lusin, kodi, gros, rim",
        inti="1 lusin = 12, 1 kodi = 20, 1 gros = 144 (= 12 lusin), "
             "1 rim = 500 lembar. Satuan ini TIDAK memakai tangga ×10.",
        contoh="5 lusin = 5 × 12 = 60 buah. 240 buah = 240 : 12 = 20 lusin.",
    ),
    "satuan_luas_volume": Kartu(
        judul="Satuan luas dan volume",
        inti="Satuan LUAS turun satu tangga dikali 100 (km²-hm²-dam²-m²-dm²-cm²). "
             "Satuan VOLUME dikali 1.000 (m³-dm³-cm³). Bukan ×10 seperti "
             "satuan panjang. 1 hektar = 1 hm², 1 are = 1 dam².",
        contoh="3 dam² → m² turun 1 tangga → 3 × 100 = 300 m². "
               "2 m³ → dm³ → 2 × 1.000 = 2.000 dm³.",
    ),
    "jam_selesai": Kartu(
        judul="Waktu mulai, lama, dan selesai",
        inti="Selesai = mulai + lama. Mulai = selesai − lama. "
             "Setiap 60 menit menjadi 1 jam — menit tidak boleh ditulis "
             "lebih dari 59.",
        contoh="Mulai 09.45, lama 2 jam 40 menit → 09.45 + 2 jam = 11.45, "
               "+ 40 menit = 12.25.",
    ),
    "lingkaran": Kartu(
        judul="Lingkaran",
        inti="Keliling = 2 × π × jari-jari. Luas = π × jari-jari × jari-jari. "
             "Pakai π = 22/7 kalau jari-jarinya kelipatan 7, selain itu 3,14.",
        contoh="r = 84 cm, π = 22/7 → luas = 22/7 × 84 × 84 = 22.176 cm².",
    ),
    "juring": Kartu(
        judul="Juring lingkaran",
        inti="Bagian lingkaran = sudut pusat ÷ 360°. Luas juring = bagian × πr². "
             "Keliling juring = bagian × 2πr + 2r; kedua sisi lurus tetap dihitung.",
        contoh="Sudut 90°, r = 7 cm, π = 22/7: busur = 11 cm, "
               "keliling juring = 11 + 14 = 25 cm.",
    ),
    "paritas": Kartu(
        judul="Jumlah deret genap atau ganjil",
        inti="Bilangan genap atau ganjil berurutan memiliki beda 2. Suku terakhir "
             "= awal + 2 × (banyak suku − 1). Jumlah = banyak suku × (awal + akhir) ÷ 2.",
        contoh="4 + 6 + 8 + 10 = 4 × (4 + 10) ÷ 2 = 28.",
    ),
    "luas_permukaan": Kartu(
        judul="Luas permukaan bangun ruang",
        inti="Kubus = 6 × rusuk × rusuk. Balok = 2 × (pl + pt + lt). "
             "Tabung = 2 × π × r × (r + tinggi).",
        contoh="Kubus rusuk 5 → 6 × 5 × 5 = 150.",
    ),
    "siklus": Kartu(
        judul="Pola berulang (siklus)",
        inti="Cari PANJANG satu putaran, lalu bagi dan ambil SISANYA. "
             "Sisa itu yang menunjukkan posisi di dalam putaran.",
        contoh="Pola 5 huruf, cari ke-35 → 35 ÷ 5 = 7 sisa 0 → huruf terakhir.",
    ),
    "hari_siklus": Kartu(
        judul="Menghitung hari",
        inti="Satu minggu 7 hari, jadi bagi dengan 7 dan ambil SISANYA. "
             "Sisa itu jumlah hari yang dimajukan dari hari sekarang.",
        contoh="Jumat, 23 hari lagi → 23 ÷ 7 = 3 sisa 2 → Jumat + 2 = Minggu.",
    ),
    "mencacah": Kartu(
        judul="Aturan kali dan aturan tambah",
        inti="Kalau memilih satu ini DAN satu itu → DIKALI. "
             "Kalau memilih satu ini ATAU satu itu → DITAMBAH.",
        contoh="10 roti dan 13 selai, pilih satu-satu → 10 × 13 = 130 cara.",
    ),
    "himpunan": Kartu(
        judul="Irisan dua kelompok",
        inti="Yang suka salah satu = A + B − keduanya. "
             "Yang tidak suka dua-duanya = total − (A + B − keduanya).",
        contoh="19 + 25 − 17 = 27 suka setidaknya satu.",
    ),
    "susun_bilangan": Kartu(
        judul="Menyusun bilangan",
        inti="Hitung pilihan tiap digit lalu KALIKAN. Kalau digit depan "
             "tidak boleh 0, kurangi satu pilihan untuk digit itu.",
        contoh="5 angka, 5 digit, depan tak boleh 0 → 4 × 4 × 3 × 2 × 1 = 96.",
    ),
    "penalaran": Kartu(
        judul="Penalaran urutan",
        inti="Tulis urutannya jadi satu baris dari yang paling besar ke "
             "paling kecil, baru jawab pertanyaannya.",
        contoh="Eko > Citra > Fajar → urutan kedua dari atas = Citra.",
    ),
    "logika_pasti": Kartu(
        judul="Pernyataan yang PASTI benar",
        inti="Gabungkan FAKTANYA: siapa orangnya + aturannya. "
             "Yang pasti benar hanya yang mengikuti kedua fakta itu.",
        contoh="Citra anak kelas 3, semua anak kelas 3 bersepatu merah → "
               "pasti: Citra bersepatu merah.",
    ),
    "unsur_bangun": Kartu(
        judul="Sisi, rusuk, titik sudut",
        inti="Kubus/balok: 6 sisi, 12 rusuk, 8 titik sudut. "
             "Limas segiempat: 5 sisi, 8 rusuk, 5 titik sudut.",
        contoh="Limas segiempat → alas 1 + tegak 4 = 5 sisi.",
    ),
    "simetri": Kartu(
        judul="Simetri",
        inti="Sumbu simetri = garis yang membelah bangun jadi dua bagian "
             "yang persis sama. Segitiga sama sisi 3, persegi 4, "
             "persegi panjang 2.",
        contoh="Segitiga sama sisi → 3 sumbu simetri.",
    ),
    "perbandingan_ukuran": Kartu(
        judul="Ukuran diperbesar",
        inti="Kalau rusuk diperbesar n kali: LUAS jadi n × n kali, "
             "VOLUME jadi n × n × n kali.",
        contoh="Rusuk 4× → volume 4 × 4 × 4 = 64 kali semula.",
    ),
    "kerja_bersama": Kartu(
        judul="Bekerja bersama",
        inti="Ubah ke bagian per jam: 1/a + 1/b, lalu waktu bersama = "
             "1 dibagi hasil penjumlahan itu.",
        contoh="6 jam dan 3 jam → 1/6 + 1/3 = 1/2 pekerjaan per jam; "
               "waktu bersama = 2 jam. Jangan membulatkan bila soal tidak memintanya.",
    ),
    "umur": Kartu(
        judul="Perbandingan umur",
        inti="Selisih umur tetap, tetapi rasio umur berubah. Untuk n tahun lagi, "
             "tambahkan n pada KEDUA umur, lalu bagi umur yang lebih tua dengan "
             "umur yang lebih muda. Untuk mencari waktunya, cocokkan kedua umur "
             "pada tahun yang sama dengan rasio yang diminta.",
        contoh="Ari 44 tahun, Bima 8 tahun. Setahun lagi: 45 : 9 = 5 kali.",
    ),
    "jumlah_selisih": Kartu(
        judul="Jumlah dan selisih",
        inti="Bilangan besar = (jumlah + selisih) ÷ 2. "
             "Bilangan kecil = (jumlah − selisih) ÷ 2.",
        contoh="Jumlah 83, selisih 25 → kecil = (83 − 25) ÷ 2 = 29.",
    ),
    "faktor_prima": Kartu(
        judul="Faktorisasi prima",
        inti="Pecah bilangan jadi perkalian bilangan prima. Banyak faktor = "
             "kalikan (pangkat + 1) dari tiap prima.",
        contoh="1287 = 3² × 11 × 13 → (2+1)(1+1)(1+1) = 12 faktor.",
    ),
    "diagram": Kartu(
        judul="Membaca diagram",
        inti="Diagram batang: baca tinggi tiap batang. "
             "Diagram lingkaran: bagian = besar sudut ÷ 360 × total, "
             "atau persen ÷ 100 × total. "
             "Tabel turus: baca angka pada baris yang DITANYA.",
        contoh="752 dari 1.504 = setengah → sudutnya 180°.",
    ),
    "piktogram": Kartu(
        judul="Piktogram (diagram gambar)",
        inti="Satu gambar mewakili beberapa benda. Banyak benda = "
             "banyak gambar × nilai satu gambar. Jangan berhenti di "
             "banyaknya gambar — itu belum jawabannya.",
        contoh="1 gambar = 5 buah. Senin 4 gambar → 4 × 5 = 20 buah.",
    ),
    "jangkauan": Kartu(
        judul="Terbesar, terkecil, jangkauan",
        inti="Terbesar = nilai paling tinggi, terkecil = paling rendah. "
             "Jangkauan = terbesar − terkecil (dikurangi, bukan ditambah).",
        contoh="Data 7, 3, 9, 5 → terbesar 9, terkecil 3, jangkauan 9 − 3 = 6.",
    ),
    "sarang_merpati": Kartu(
        judul="Prinsip sarang merpati",
        inti="Bagi rata dulu, lalu SISANYA dibagikan satu-satu. "
             "Jadi yang terbanyak pasti = hasil bagi, ditambah 1 kalau ada sisa.",
        contoh="52 merpati, 6 sangkar → 52 ÷ 6 = 8 sisa 4 → pasti ada 9.",
    ),
    "jalur_petak": Kartu(
        judul="Menghitung jalur di petak",
        inti="Kalau hanya boleh ke kanan dan ke bawah, tulis angka di tiap "
             "titik = jumlah angka dari kiri dan dari atas. Angka di pojok "
             "tujuan adalah jawabannya.",
        contoh="Petak 2×2 → jalurnya 6.",
    ),
    "kombinatorik": Kartu(
        judul="Mencacah kemungkinan",
        inti="Kalau URUTAN penting, itu permutasi. Kalau urutan TIDAK "
             "penting (sekadar memilih), itu kombinasi.",
        contoh="Memilih 2 dari 4 anak untuk piket (urutan tak penting) = 6 cara.",
    ),
}


# template_id -> konsep. Dibangun dari daftar template NYATA (bukan dikira),
# dan sengaja tidak lengkap: template yang tidak punya kartu yang benar-benar
# pas lebih baik tidak menampilkan apa pun. Guard test menjaga setiap nilai
# di sini menunjuk konsep yang ADA di KARTU dan kunci yang ADA di REGISTRI.
KONSEP_TEMPLATE: dict[str, str] = {
    "tambah_dasar": "tambah_dasar",
    "kurang_dasar": "kurang_dasar",
    "bilangan_hilang": "bilangan_hilang",
    "nilai_tempat": "nilai_tempat",
    "bandingkan_bilangan": "bandingkan_bilangan",
    "perkalian_dasar": "perkalian_dasar",
    "pembagian_dasar": "pembagian_dasar",
    "pecahan_bagian_dasar": "pecahan",
    "nilai_tempat_ribuan": "nilai_tempat_ribuan",
    "nilai_tempat_besar": "nilai_tempat_besar",
    "kenali_bentuk": "kenali_bentuk",
    "ukur_satuan_tak_baku": "ukur_satuan_tak_baku",
    "baca_diagram_gambar": "baca_diagram_gambar",
    "pola_posisi": "pola_posisi",
    "pecahan_setengah": "pecahan_setengah",
    "waktu_berat_awal": "waktu_berat_awal",
    "turus_gambar_awal": "turus_gambar_awal",
    "ukur_konversi_awal": "ukur_konversi_awal",
    "bandingkan_ciri_bangun": "bandingkan_ciri_bangun",
    "peluang_dasar": "peluang_dasar",
    "bilang_benda_awal": "bilang_benda_awal",
    "tambah_kurang_20": "tambah_kurang_20",
    "tambah_kurang_100": "tambah_kurang_100",
    "unsur_bangun_datar": "unsur_bangun_datar",
    "pecahan_senilai_desimal": "pecahan_senilai_desimal",
    "luas_petak_volume_kubus": "luas_petak_volume_kubus",
    "ciri_komposisi_bangun": "ciri_komposisi_bangun",
    "keliling_gabungan": "keliling_gabungan",
    "pecahan_bilangan_asli_desimal": "pecahan_bilangan_asli_desimal",
    "urutkan_bilangan": "urutkan_bilangan",
    "tambah_kurang_bersusun": "tambah_kurang_bersusun",
    "kali_bagi_sekolah": "kali_bagi_sekolah",
    "kalimat_matematika": "kalimat_matematika",
    # statistika
    "rata_rata": "rata_rata",
    "rata_rata_gabungan": "rata_rata",
    "median_modus": "median_modus",
    # pola bilangan
    "deret_aritmetika": "pola_bilangan",
    "deret_aritmetika_turun": "pola_bilangan",
    "deret_terbalik_aritmetika": "pola_bilangan",
    "suku_ke_n": "pola_bilangan",
    "jumlah_deret": "pola_bilangan",
    "gauss_deret": "pola_bilangan",
    "deret_geometri": "pola_geometri",
    "deret_terbalik_geometri": "pola_geometri",
    "pola_pecahan": "pecahan",
    # geometri datar
    "keliling_luas_datar": "keliling_luas",
    "luas_kotak_satuan": "keliling_luas",
    "luas_segiempat_lain": "keliling_luas",
    "luas_segitiga_jajargenjang": "luas_segitiga",
    "jumlah_sudut_segitiga": "sudut",
    "sudut_luar_segitiga": "sudut",
    "sudut_pelurus_berpenyiku": "sudut",
    # geometri ruang
    "volume_kubus_balok": "volume",
    "volume_prisma_tabung": "volume",
    # teori bilangan
    "banyak_kelipatan": "kelipatan_rentang",
    "sisa_operasi": "sisa_operasi",
    "banyak_prima": "prima_rentang",
    "jumlah_kelipatan": "jumlah_kelipatan",
    "fpb_dua_bilangan": "fpb_kpk",
    "kpk_dua_bilangan": "fpb_kpk",
    "fpb_kpk_hubungan": "fpb_kpk",
    "keterbagian": "keterbagian",
    "sisa_pembagian": "sisa_pembagian",
    "sisa_bagi_siklus": "sisa_pembagian",
    # aritmetika
    "urutan_operasi_1": "urutan_operasi",
    "operasi_berkurung": "urutan_operasi",
    "pecahan_operasi_campuran": "pecahan",
    "pecahan_kali_bagi": "pecahan_kali_bagi",
    "urut_pecahan_desimal_persen": "bentuk_bilangan",
    "pembulatan_taksiran": "pembulatan",
    # perbandingan & pengukuran
    "skala_peta": "perbandingan",
    "perbandingan_senilai": "perbandingan",
    "perbandingan_berbalik": "perbandingan",
    "jam_menit_detik": "waktu",
    "satuan_waktu_lama": "waktu",
    "jam_selesai": "jam_selesai",
    "satuan_kuantitas": "satuan_kuantitas",
    "tangga_satuan_campuran": "satuan_konversi",
    "satuan_luas_volume": "satuan_luas_volume",
    # persen & uang
    "persen_diskon": "persen",
    "persen_untung_rugi": "persen",
    "persen_bertingkat": "persen",
    "soal_uang": "jumlah_selisih",
    "jumlah_selisih": "jumlah_selisih",
    "dua_besaran_selisih": "jumlah_selisih",
    "soal_umur": "umur",
    # kecepatan & debit
    "kecepatan_jarak_waktu": "kecepatan",
    "berpapasan": "berpapasan",
    "menyusul": "berpapasan",
    "debit": "debit",
    "kerja_bersama": "kerja_bersama",
    # pengukuran
    "satuan_konversi": "satuan_konversi",
    "perbandingan_ukuran": "perbandingan_ukuran",
    "perbandingan_volume": "perbandingan_ukuran",
    # geometri lanjut
    "lingkaran_keliling_luas": "lingkaran",
    "juring": "juring",
    "luas_arsiran": "keliling_luas",
    "luas_permukaan": "luas_permukaan",
    "jaring_jaring": "unsur_bangun",
    "unsur_bangun": "unsur_bangun",
    "kubus_dicat": "unsur_bangun",
    "simetri_bangun": "simetri",
    # pola & siklus
    "deret_bertingkat": "pola_bilangan",
    "titik_segitiga": "pola_titik_segitiga",
    "siklus_huruf": "siklus",
    "siklus_warna": "siklus",
    "jumlah_siklus": "siklus",
    "siklus_hari": "hari_siklus",
    # kombinatorik lanjut
    "aturan_kali": "mencacah",
    "aturan_tambah": "mencacah",
    "inklusi_eksklusi_2": "himpunan",
    "susun_bilangan": "susun_bilangan",
    "susun_bilangan_syarat": "susun_bilangan",
    # logika
    "tabel_penalaran": "penalaran",
    "benar_salah_pengandaian": "logika_pasti",
    # teori bilangan lanjut
    "prima_faktorisasi": "faktor_prima",
    "angka_satuan_pangkat": "siklus",
    "paritas": "paritas",
    # statistika: diagram
    "diagram_batang_garis": "diagram",
    "diagram_lingkaran": "diagram",
    "tabel_turus": "diagram",
    "piktogram": "piktogram",
    "jangkauan_data": "jangkauan",
    "sarang_merpati": "sarang_merpati",
    "jalur_petak": "jalur_petak",
    "korek_api": "pola_korek",
    # kombinatorik
    "permutasi_urutan": "kombinatorik",
    "permutasi_blok": "kombinatorik",
    "kombinasi_pilih": "kombinatorik",
    "jabat_tangan": "kombinatorik",
}


def kartu_untuk(template_id: str) -> Kartu | None:
    """Kartu teori untuk satu template, atau None kalau belum dipetakan.

    None BUKAN kegagalan: lebih baik tidak menampilkan apa pun daripada
    menempelkan teori yang tidak menjelaskan soal di depan anak.
    """
    konsep = KONSEP_TEMPLATE.get(template_id)
    return KARTU.get(konsep) if konsep else None


def kartu_untuk_banyak(template_id_list) -> list[Kartu]:
    """Kartu unik untuk sekumpulan template, urutan pertama-muncul dijaga.

    Dipakai halaman hasil: beberapa soal yang salah bisa berbagi satu
    konsep, dan anak tidak perlu membaca kartu yang sama tiga kali.
    """
    keluar: list[Kartu] = []
    terlihat: set[str] = set()
    for tid in template_id_list:
        konsep = KONSEP_TEMPLATE.get(tid)
        if konsep and konsep not in terlihat:
            terlihat.add(konsep)
            keluar.append(KARTU[konsep])
    return keluar
