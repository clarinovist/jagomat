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
        contoh="21 jam dan 10 jam → 1/21 + 1/10, waktu bersama ≈ 7 jam.",
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
    "soal_umur": "jumlah_selisih",
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
    "juring": "lingkaran",
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
    "paritas": "pola_bilangan",
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
