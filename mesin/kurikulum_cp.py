"""Capaian Pembelajaran (CP) Matematika Kurikulum Merdeka dan pemetaannya ke grup katalog.

Sumber: Keputusan Kepala BSKAP No. 046/H/KR/2025, Lampiran IV.1 (CP Matematika Fase A-D).
Butir CP dipecah atomik; `teks` adalah kutipan resmi dengan spasi dirapatkan. Fase A = kelas
I-II, B = III-IV, C = V-VI, D = VII-IX (di atas SD, dipakai grup pengayaan). CP tidak membagi
materi per semester.

`CP_PER_GRUP` memetakan (topik_id, kode grup) di `kurikulum_katalog.KATALOG` ke butir CP dengan
tingkat kecocokan: penuh, sebagian, prasyarat (melatih dasar butir itu), pengayaan (melampaui
butir itu). Tuple kosong = di luar CP SD-SMP (pengayaan olimpiade). Pemetaan = penilaian isi
soal, BUKAN kode level P1-P6. Status lihat `STATUS_PEMETAAN`; diturunkan dari peta per
template di riset lokal (`riset/referensi/kurikulum/merdeka-046-2025/`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

STATUS_PEMETAAN = "disahkan pemilik 2026-11-20"
KECOCOKAN = ("penuh", "sebagian", "prasyarat", "pengayaan")
FASE = {"A": "Kelas 1-2", "B": "Kelas 3-4", "C": "Kelas 5-6", "D": "Kelas 7-9"}
ELEMEN = {
    "bilangan": "Bilangan",
    "aljabar": "Aljabar",
    "pengukuran": "Pengukuran",
    "geometri": "Geometri",
    "data": "Analisis Data dan Peluang",
}


@dataclass(frozen=True)
class ButirCP:
    id: str
    fase: str
    elemen: str
    teks: str


CAPAIAN: Tuple[ButirCP, ...] = (
    ButirCP('A.bilangan.1', 'A', 'bilangan', 'Menunjukkan pemahaman dan memiliki intuisi bilangan (number sense) pada bilangan cacah sampai 100'),
    ButirCP('A.bilangan.2', 'A', 'bilangan', 'membaca, menulis, menentukan nilai tempat'),
    ButirCP('A.bilangan.3', 'A', 'bilangan', 'membandingkan, mengurutkan'),
    ButirCP('A.bilangan.4', 'A', 'bilangan', 'serta melakukan komposisi (menyusun) dan dekomposisi (mengurai) bilangan'),
    ButirCP('A.bilangan.5', 'A', 'bilangan', 'operasi penjumlahan dan pengurangan menggunakan benda-benda konkret yang banyaknya sampai 20'),
    ButirCP('A.bilangan.6', 'A', 'bilangan', 'pemahaman pecahan sebagai bagian dari keseluruhan melalui konteks membagi sebuah benda atau kumpulan benda sama banyak (pecahan yang diperkenalkan adalah setengah dan seperempat)'),
    ButirCP('A.aljabar.1', 'A', 'aljabar', 'Menunjukan pemahaman makna simbol matematika "=" dalam suatu kalimat matematika yang terkait dengan penjumlahan dan pengurangan bilangan cacah sampai 20 menggunakan gambar'),
    ButirCP('A.aljabar.2', 'A', 'aljabar', 'Murid dapat mengenali, meniru, dan melanjutkan pola bukan bilangan (misalnya, gambar, warna, bunyi/suara)'),
    ButirCP('A.pengukuran.1', 'A', 'pengukuran', 'Membandingkan panjang dan berat benda secara langsung, dan membandingkan durasi'),
    ButirCP('A.pengukuran.2', 'A', 'pengukuran', 'mengukur dan mengestimasi panjang dan berat benda menggunakan satuan tidak baku'),
    ButirCP('A.geometri.1', 'A', 'geometri', 'Mengenal berbagai bangun datar (segitiga, segiempat, segi banyak, lingkaran)'),
    ButirCP('A.geometri.2', 'A', 'geometri', 'dan bangun ruang (balok, kubus, kerucut, dan bola)'),
    ButirCP('A.geometri.3', 'A', 'geometri', 'melakukan komposisi (penyusunan) dan dekomposisi (penguraian) suatu bangun datar (segitiga, segiempat, dan segi banyak)'),
    ButirCP('A.geometri.4', 'A', 'geometri', 'menentukan posisi benda terhadap benda lain (kanan, kiri, depan belakang, bawah, atas)'),
    ButirCP('A.data.1', 'A', 'data', 'Mengurutkan, menyortir, mengelompokkan, membandingkan, dan menyajikan data dari banyak benda'),
    ButirCP('A.data.2', 'A', 'data', 'dengan menggunakan turus dan piktogram paling banyak 4 kategori'),
    ButirCP('B.bilangan.1', 'B', 'bilangan', 'Memiliki pemahaman dan intuisi bilangan (number sense) pada bilangan cacah sampai 10.000'),
    ButirCP('B.bilangan.2', 'B', 'bilangan', 'membaca, menulis, membandingkan, dan mengurutkan bilangan'),
    ButirCP('B.bilangan.3', 'B', 'bilangan', 'menentukan dan menggunakan nilai tempat'),
    ButirCP('B.bilangan.4', 'B', 'bilangan', 'melakukan komposisi dan dekomposisi bilangan cacah sampai 10.000'),
    ButirCP('B.bilangan.5', 'B', 'bilangan', 'masalah operasi bilangan penjumlahan dan pengurangan bilangan cacah sampai 1.000'),
    ButirCP('B.bilangan.6', 'B', 'bilangan', 'melakukan dan menyelesaikan masalah operasi perkalian dan pembagian bilangan cacah sampai 100 dengan bantuan benda konkret, gambar dan'),
    ButirCP('B.bilangan.7', 'B', 'bilangan', 'mengenal kelipatan dan faktor'),
    ButirCP('B.bilangan.8', 'B', 'bilangan', 'Murid dapat melakukan perbandingan dan pengurutan pecahan dengan pembilang satu dan antar pecahan dengan penyebut yang sama'),
    ButirCP('B.bilangan.9', 'B', 'bilangan', 'mengenal dan dapat menerapkan pecahan senilai'),
    ButirCP('B.bilangan.10', 'B', 'bilangan', 'memiliki intuisi pecahan dan desimal'),
    ButirCP('B.bilangan.11', 'B', 'bilangan', 'serta dapat menentukan pecahan sebagai desimal dan persen'),
    ButirCP('B.aljabar.1', 'B', 'aljabar', 'Menemukan nilai yang tidak diketahui dalam kalimat matematika yang melibatkan penjumlahan dan pengurangan pada bilangan cacah sampai 100, dengan menggunakan sifat-sifat bilangan dan'),
    ButirCP('B.aljabar.2', 'B', 'aljabar', 'Murid dapat mengidentifikasi, meniru, dan mengembangkan pola gambar atau objek sederhana dan pola bilangan membesar dan mengecil yang dapat melibatkan penjumlahan dan pengurangan pada bilangan cacah sampai 100'),
    ButirCP('B.pengukuran.1', 'B', 'pengukuran', 'Mengukur panjang dan berat benda menggunakan satuan baku'),
    ButirCP('B.pengukuran.2', 'B', 'pengukuran', 'menentukan hubungan antar-satuan baku panjang (cm, m) dan antar-satuan berat (g, kg)'),
    ButirCP('B.pengukuran.3', 'B', 'pengukuran', 'serta mengukur dan mengestimasi luas dan volume menggunakan satuan tidak baku dan satuan baku berupa bilangan cacah'),
    ButirCP('B.geometri.1', 'B', 'geometri', 'Mendeskripsikan ciri berbagai bentuk bangun datar (segiempat, segitiga, segi banyak)'),
    ButirCP('B.geometri.2', 'B', 'geometri', 'menyusun (komposisi) dan mengurai (dekomposisi) berbagai bangun datar dengan lebih dari satu cara jika memungkinkan'),
    ButirCP('B.data.1', 'B', 'data', 'Mengurutkan, membandingkan, menyajikan, menganalisis dan menginterpretasi data dalam bentuk tabel, diagram gambar, piktogram, dan diagram batang (skala satu satuan)'),
    ButirCP('C.bilangan.1', 'C', 'bilangan', 'Menunjukkan pemahaman dan intuisi bilangan (number sense) pada bilangan cacah sampai 1.000.000'),
    ButirCP('C.bilangan.2', 'C', 'bilangan', 'membaca, menulis, menentukan nilai tempat, membandingkan, mengurutkan,'),
    ButirCP('C.bilangan.3', 'C', 'bilangan', 'melakukan komposisi dan dekomposisi bilangan'),
    ButirCP('C.bilangan.4', 'C', 'bilangan', 'menyelesaikan masalah yang berkaitan dengan uang'),
    ButirCP('C.bilangan.5', 'C', 'bilangan', 'melakukan operasi penjumlahan, pengurangan, perkalian, dan pembagian bilangan cacah sampai 100.000'),
    ButirCP('C.bilangan.6', 'C', 'bilangan', 'serta menyelesaikan masalah yang berkaitan dengan KPK dan FPB'),
    ButirCP('C.bilangan.7', 'C', 'bilangan', 'Murid dapat membandingkan dan mengurutkan berbagai pecahan termasuk pecahan campuran'),
    ButirCP('C.bilangan.8', 'C', 'bilangan', 'melakukan operasi penjumlahan dan pengurangan pecahan'),
    ButirCP('C.bilangan.9', 'C', 'bilangan', 'serta melakukan operasi perkalian dan pembagian pecahan dengan bilangan asli'),
    ButirCP('C.bilangan.10', 'C', 'bilangan', 'mengubah pecahan menjadi berbagai bentuk pecahan lain'),
    ButirCP('C.bilangan.11', 'C', 'bilangan', 'serta membandingkan dan mengurutkan bilangan desimal (satu angka di belakang koma)'),
    ButirCP('C.aljabar.1', 'C', 'aljabar', 'Menemukan nilai yang belum diketahui dalam kalimat matematika yang melibatkan penjumlahan, pengurangan, perkalian, dan pembagian pada bilangan cacah sampai 1000 dengan menggunakan sifat-sifat bilangan dan operasinya'),
    ButirCP('C.aljabar.2', 'C', 'aljabar', 'Murid dapat mengidentifikasi, meniru, dan mengembangkan pola bilangan membesar dan mengecil yang melibatkan perkalian dan pembagian'),
    ButirCP('C.aljabar.3', 'C', 'aljabar', 'bernalar secara proporsional untuk menyelesaikan masalah sehari-hari dengan rasio'),
    ButirCP('C.aljabar.4', 'C', 'aljabar', 'menggunakan operasi perkalian dan pembagian dalam menyelesaikan masalah sehari- hari yang terkait dengan proporsi'),
    ButirCP('C.pengukuran.1', 'C', 'pengukuran', 'Menentukan keliling dan luas berbagai bentuk bangun datar (segitiga, segiempat, dan segi banyak) serta gabungannya'),
    ButirCP('C.pengukuran.2', 'C', 'pengukuran', 'menghitung durasi waktu'),
    ButirCP('C.pengukuran.3', 'C', 'pengukuran', 'dan mengukur besar sudut pada bangun datar atau yang dibentuk dari dua garis berpotongan'),
    ButirCP('C.geometri.1', 'C', 'geometri', 'Mengkonstruksi dan mengurai bangun ruang (kubus, balok, dan gabungannya)'),
    ButirCP('C.geometri.2', 'C', 'geometri', 'dan mengenali visualisasi spasial (bagian depan, atas, dan samping)'),
    ButirCP('C.geometri.3', 'C', 'geometri', 'membandingkan karakteristik antar bangun datar dan antar bangun ruang'),
    ButirCP('C.geometri.4', 'C', 'geometri', 'menentukan lokasi pada peta yang menggunakan sistem berpetak'),
    ButirCP('C.data.1', 'C', 'data', 'Mengurutkan, membandingkan, menyajikan, dan menganalisis data banyak benda dan data hasil pengukuran dalam bentuk gambar, piktogram, diagram batang, dan tabel frekuensi untuk mendapatkan informasi'),
    ButirCP('C.data.2', 'C', 'data', 'menentukan kejadian dengan kemungkinan yang lebih besar atau lebih kecil dalam suatu percobaan acak'),
    ButirCP('D.bilangan.1', 'D', 'bilangan', 'Membaca, menulis, dan membandingkan bilangan bulat, bilangan rasional, bilangan desimal, bilangan berpangkat bulat dan akar, bilangan dalam notasi ilmiah'),
    ButirCP('D.bilangan.2', 'D', 'bilangan', 'menerapkan operasi aritmatika pada bilangan real'),
    ButirCP('D.bilangan.3', 'D', 'bilangan', 'dan memberikan estimasi/perkiraan dalam menyelesaikan masalah (termasuk berkaitan dengan literasi finansial)'),
    ButirCP('D.bilangan.4', 'D', 'bilangan', 'Murid dapat menggunakan rasio (skala, proporsi, dan laju perubahan) dalam penyelesaian masalah'),
    ButirCP('D.aljabar.1', 'D', 'aljabar', 'Mengenali, memprediksi dan menggeneralisasi pola dalam bentuk susunan benda dan bilangan'),
    ButirCP('D.aljabar.2', 'D', 'aljabar', 'Menyatakan suatu situasi ke dalam bentuk aljabar'),
    ButirCP('D.aljabar.3', 'D', 'aljabar', 'menggunakan sifat-sifat operasi (komutatif, asosiatif, dan distributif) untuk menghasilkan bentuk aljabar yang ekuivalen'),
    ButirCP('D.aljabar.4', 'D', 'aljabar', 'Murid dapat memahami relasi dan fungsi (domain, kodomain, range) serta menyajikannya dalam bentuk diagram panah, tabel, himpunan pasangan berurutan, dan grafik'),
    ButirCP('D.aljabar.5', 'D', 'aljabar', 'membedakan beberapa fungsi non linear dari fungsi linear secara grafik'),
    ButirCP('D.aljabar.6', 'D', 'aljabar', 'menyelesaikan persamaan dan pertidaksamaan linear satu variabel'),
    ButirCP('D.aljabar.7', 'D', 'aljabar', 'menyajikan, menganalisis, dan menyelesaikan masalah dengan menggunakan relasi, fungsi dan persamaan linear'),
    ButirCP('D.aljabar.8', 'D', 'aljabar', 'serta menyelesaikan sistem persaman linear dua variabel melalui beberapa cara untuk penyelesaian masalah'),
    ButirCP('D.pengukuran.1', 'D', 'pengukuran', 'Menentukan keliling, luas, panjang busur, sudut dan luas juring lingkaran, serta menyelesaikan masalah yang terkait'),
    ButirCP('D.pengukuran.2', 'D', 'pengukuran', 'menjelaskan cara untuk menentukan luas permukaan dan volume bangun ruang (prisma, tabung, bola, limas dan kerucut) dan menyelesaikan masalah yang'),
    ButirCP('D.pengukuran.3', 'D', 'pengukuran', 'dan menjelaskan pengaruh perubahan secara proporsional dari bangun datar dan bangun ruang terhadap ukuran panjang, besar sudut, luas, dan/atau volume'),
    ButirCP('D.geometri.1', 'D', 'geometri', 'Membuat jaring-jaring bangun ruang (prisma, tabung, limas dan kerucut) dan membuat bangun ruang dari jaring-jaringnya'),
    ButirCP('D.geometri.2', 'D', 'geometri', 'Murid dapat menggunakan hubungan antar-sudut yang terbentuk oleh dua garis yang berpotongan, dan oleh dua garis sejajar yang dipotong sebuah garis transversal untuk menyelesaikan masalah (termasuk menentukan jumlah besar sudut dalam sebuah segitiga, menentukan besar sudut yang belum diketahui pada sebuah segitiga)'),
    ButirCP('D.geometri.3', 'D', 'geometri', 'menjelaskan sifat-sifat kekongruenan dan kesebangunan pada segitiga dan segiempat, dan menggunakannya untuk menyelesaikan masalah'),
    ButirCP('D.geometri.4', 'D', 'geometri', 'menunjukkan kebenaran teorema Pythagoras dan menggunakannya dalam menyelesaikan masalah (termasuk pengenalan bilangan irasional dan jarak antara dua titik pada bidang koordinat Kartesius)'),
    ButirCP('D.geometri.5', 'D', 'geometri', 'Murid dapat melakukan transformasi tunggal (refleksi, translasi, rotasi, dan dilatasi) titik, garis, dan bangun datar pada bidang koordinat Kartesius dan menggunakannya untuk menyelesaikan masalah'),
    ButirCP('D.data.1', 'D', 'data', 'Merumuskan pertanyaan, mengumpulkan, menyajikan, dan menganalisis data untuk menjawab pertanyaan dari situasi atau masalah'),
    ButirCP('D.data.2', 'D', 'data', 'menggunakan diagram batang dan diagram lingkaran untuk menyajikan dan menginterpretasi data'),
    ButirCP('D.data.3', 'D', 'data', 'mengambil sampel yang mewakili suatu populasi untuk mendapatkan data yang terkait dengan diri dan lingkungan'),
    ButirCP('D.data.4', 'D', 'data', 'menentukan dan menafsirkan rerata (mean), median, modus, dan jangkauan (range) dari data tersebut untuk menyelesaikan masalah (termasuk membandingkan suatu data terhadap kelompoknya, membandingkan dua kelompok data, memprediksi, membuat keputusan'),
    ButirCP('D.data.5', 'D', 'data', 'menyelidiki kemungkinan adanya perubahan pengukuran pusat tersebut akibat perubahan'),
    ButirCP('D.data.6', 'D', 'data', 'Murid dapat menjelaskan dan menggunakan pengertian peluang dan frekuensi relatif untuk menentukan frekuensi harapan satu kejadian pada suatu percobaan sederhana (semua hasil percobaan dapat muncul secara merata)'),
)

CP_PER_GRUP: Dict[Tuple[str, str], Tuple[Tuple[str, str], ...]] = {
    ('aritmatika-lanjut', 'konversi'): (('B.pengukuran.2', 'sebagian'),),
    ('aritmatika-lanjut', 'kecepatan'): (('D.bilangan.4', 'sebagian'),),
    ('aritmatika-lanjut', 'gerak_relatif'): (('D.bilangan.4', 'sebagian'),),
    ('aritmatika-lanjut', 'debit'): (('D.bilangan.4', 'sebagian'),),
    ('aritmatika-lanjut', 'senilai'): (('C.aljabar.3', 'penuh'), ('C.aljabar.4', 'sebagian'), ('D.bilangan.4', 'sebagian')),
    ('aritmatika-lanjut', 'berbalik'): (('C.aljabar.4', 'sebagian'),),
    ('aritmatika-lanjut', 'kerja'): (('C.aljabar.4', 'sebagian'),),
    ('aritmatika-lanjut', 'diskon'): (('C.bilangan.4', 'sebagian'), ('D.bilangan.3', 'sebagian')),
    ('aritmatika-lanjut', 'untung'): (('D.bilangan.3', 'sebagian'),),
    ('aritmatika-lanjut', 'persen_bertahap'): (('D.bilangan.3', 'sebagian'),),
    ('aritmetika-dasar', 'operasi'): (('B.bilangan.5', 'sebagian'), ('B.bilangan.6', 'sebagian'), ('C.bilangan.5', 'sebagian'), ('D.bilangan.2', 'sebagian'), ('D.aljabar.3', 'prasyarat')),
    ('aritmetika-dasar', 'fpb'): (('B.bilangan.6', 'prasyarat'), ('B.bilangan.7', 'sebagian'), ('C.bilangan.6', 'sebagian')),
    ('aritmetika-dasar', 'pecahan_campuran'): (('B.bilangan.9', 'sebagian'), ('C.bilangan.8', 'penuh'), ('D.bilangan.2', 'sebagian')),
    ('aritmetika-dasar', 'urut_bilangan'): (('B.bilangan.8', 'sebagian'), ('B.bilangan.10', 'sebagian'), ('B.bilangan.11', 'sebagian'), ('C.bilangan.7', 'sebagian'), ('C.bilangan.10', 'sebagian'), ('C.bilangan.11', 'sebagian'), ('D.bilangan.1', 'sebagian')),
    ('aritmetika-dasar', 'pecahan_kali_bagi'): (('C.bilangan.9', 'sebagian'),),
    ('aritmetika-dasar', 'taksiran'): (('B.bilangan.3', 'prasyarat'), ('D.bilangan.3', 'sebagian')),
    ('bilangan-dasar', 'penjumlahan_dasar'): (('A.bilangan.5', 'sebagian'), ('A.aljabar.1', 'sebagian'), ('B.bilangan.5', 'prasyarat')),
    ('bilangan-dasar', 'pengurangan_dasar'): (('A.bilangan.5', 'sebagian'), ('A.aljabar.1', 'sebagian')),
    ('bilangan-dasar', 'bilangan_hilang'): (('A.aljabar.1', 'sebagian'), ('B.aljabar.1', 'prasyarat')),
    ('bilangan-dasar', 'nilai_tempat'): (('A.bilangan.2', 'sebagian'), ('A.bilangan.4', 'sebagian')),
    ('bilangan-dasar', 'membandingkan'): (('A.bilangan.1', 'sebagian'), ('A.bilangan.3', 'sebagian')),
    ('bilangan-sekolah', 'nilai_tempat_besar'): (('B.bilangan.3', 'sebagian'), ('B.bilangan.4', 'sebagian'), ('C.bilangan.3', 'sebagian')),
    ('bilangan-sekolah', 'urutkan_bilangan'): (('B.bilangan.2', 'sebagian'), ('C.bilangan.1', 'sebagian'), ('C.bilangan.2', 'sebagian')),
    ('bilangan-sekolah', 'tambah_kurang_bersusun'): (('B.bilangan.5', 'sebagian'), ('C.bilangan.5', 'sebagian')),
    ('bilangan-sekolah', 'kali_bagi_sekolah'): (('B.bilangan.6', 'sebagian'), ('C.bilangan.5', 'sebagian')),
    ('bilangan-sekolah', 'kalimat_matematika'): (('B.aljabar.1', 'sebagian'), ('C.aljabar.1', 'sebagian')),
    ('matematika-awal', 'kenali_bentuk'): (('A.geometri.1', 'sebagian'), ('B.geometri.1', 'sebagian')),
    ('matematika-awal', 'ukur_satuan_tak_baku'): (('A.pengukuran.2', 'sebagian'), ('A.pengukuran.1', 'sebagian')),
    ('matematika-awal', 'baca_diagram_gambar'): (('A.data.2', 'sebagian'), ('A.data.1', 'sebagian')),
    ('matematika-awal', 'pola_posisi'): (('A.aljabar.2', 'sebagian'), ('A.geometri.4', 'sebagian')),
    ('matematika-awal', 'pecahan_setengah'): (('A.bilangan.6', 'sebagian'),),
    ('matematika-awal', 'waktu_berat_awal'): (('A.pengukuran.1', 'sebagian'), ('B.pengukuran.1', 'sebagian'), ('C.pengukuran.2', 'prasyarat')),
    ('matematika-awal', 'turus_gambar_awal'): (('A.data.2', 'sebagian'), ('B.data.1', 'prasyarat')),
    ('matematika-awal', 'ukur_konversi_awal'): (('B.pengukuran.2', 'sebagian'),),
    ('matematika-awal', 'bandingkan_ciri_bangun'): (('C.geometri.3', 'sebagian'),),
    ('matematika-awal', 'peluang_dasar'): (('C.data.2', 'sebagian'),),
    ('matematika-awal', 'bilang_benda_awal'): (('A.bilangan.1', 'sebagian'), ('A.bilangan.2', 'sebagian'), ('A.bilangan.3', 'sebagian')),
    ('matematika-awal', 'tambah_kurang_20'): (('A.bilangan.5', 'sebagian'), ('A.aljabar.1', 'sebagian')),
    ('matematika-awal', 'tambah_kurang_100'): (('B.aljabar.1', 'sebagian'), ('B.bilangan.5', 'prasyarat')),
    ('matematika-awal', 'unsur_bangun_datar'): (('B.geometri.1', 'sebagian'),),
    ('matematika-awal', 'pecahan_senilai_desimal'): (('B.bilangan.9', 'sebagian'), ('B.bilangan.10', 'sebagian'), ('B.bilangan.11', 'sebagian')),
    ('matematika-awal', 'luas_petak_volume_kubus'): (('B.pengukuran.3', 'sebagian'),),
    ('matematika-awal', 'ciri_komposisi_bangun'): (('B.geometri.1', 'sebagian'), ('B.geometri.2', 'sebagian')),
    ('matematika-awal', 'keliling_gabungan'): (('C.pengukuran.1', 'sebagian'),),
    ('matematika-awal', 'pecahan_bilangan_asli_desimal'): (('C.bilangan.9', 'sebagian'), ('C.bilangan.10', 'sebagian'), ('B.bilangan.11', 'sebagian')),
    ('matematika-awal', 'pecahan_campur_awal'): (('C.bilangan.9', 'sebagian'), ('C.bilangan.10', 'sebagian')),
    ('berhitung-sekolah', 'perkalian_dasar'): (('B.bilangan.6', 'sebagian'),),
    ('berhitung-sekolah', 'pembagian_dasar'): (('B.bilangan.6', 'sebagian'),),
    ('berhitung-sekolah', 'pecahan_sederhana'): (('A.bilangan.6', 'sebagian'), ('C.bilangan.8', 'sebagian')),
    ('berhitung-sekolah', 'nilai_tempat_besar'): (('B.bilangan.1', 'sebagian'), ('B.bilangan.3', 'sebagian')),
    ('geometri-datar', 'sudut'): (('C.pengukuran.3', 'sebagian'), ('D.geometri.2', 'sebagian')),
    ('geometri-datar', 'keliling_luas'): (('C.pengukuran.1', 'sebagian'),),
    ('geometri-datar', 'segitiga'): (('C.pengukuran.1', 'penuh'),),
    ('geometri-datar', 'segiempat'): (('C.pengukuran.1', 'sebagian'),),
    ('geometri-datar', 'lingkaran'): (('D.pengukuran.1', 'sebagian'),),
    ('geometri-datar', 'juring'): (('D.pengukuran.1', 'sebagian'),),
    ('geometri-datar', 'arsiran'): (('C.pengukuran.1', 'sebagian'), ('D.pengukuran.1', 'sebagian')),
    ('geometri-datar', 'perbandingan'): (('D.pengukuran.3', 'sebagian'),),
    ('geometri-datar', 'kotak'): (('A.geometri.3', 'sebagian'), ('B.pengukuran.3', 'sebagian'), ('B.geometri.2', 'sebagian'), ('C.pengukuran.1', 'sebagian')),
    ('geometri-datar', 'simetri'): (('B.geometri.1', 'sebagian'), ('D.geometri.5', 'prasyarat')),
    ('geometri-ruang', 'unsur'): (('A.geometri.2', 'sebagian'), ('C.geometri.1', 'prasyarat'), ('C.geometri.3', 'sebagian')),
    ('geometri-ruang', 'volume_balok'): (('D.pengukuran.2', 'sebagian'),),
    ('geometri-ruang', 'volume_prisma'): (('D.pengukuran.2', 'sebagian'),),
    ('geometri-ruang', 'permukaan'): (('D.pengukuran.2', 'sebagian'),),
    ('geometri-ruang', 'jaring'): (('D.geometri.1', 'sebagian'),),
    ('geometri-ruang', 'dicat'): (('C.geometri.1', 'sebagian'),),
    ('geometri-ruang', 'perbandingan'): (('D.pengukuran.3', 'sebagian'),),
    ('kombinatorik', 'mencacah'): (),
    ('kombinatorik', 'susun'): (),
    ('kombinatorik', 'permutasi'): (),
    ('kombinatorik', 'kombinasi'): (),
    ('kombinatorik', 'pasangan'): (),
    ('kombinatorik', 'jalur'): (('C.geometri.4', 'prasyarat'),),
    ('kombinatorik', 'merpati'): (),
    ('kombinatorik', 'himpunan'): (),
    ('logika', 'pengandaian'): (),
    ('logika', 'tabel'): (),
    ('logika', 'jumlah_selisih'): (('B.aljabar.1', 'sebagian'), ('C.aljabar.1', 'sebagian'), ('D.aljabar.6', 'sebagian'), ('D.aljabar.7', 'sebagian'), ('D.aljabar.8', 'sebagian')),
    ('logika', 'umur'): (('D.aljabar.6', 'sebagian'),),
    ('logika', 'uang'): (('B.aljabar.1', 'sebagian'), ('C.bilangan.4', 'sebagian'), ('C.aljabar.1', 'sebagian'), ('D.aljabar.7', 'sebagian')),
    ('pengukuran', 'skala'): (('C.aljabar.3', 'sebagian'), ('D.bilangan.4', 'sebagian')),
    ('pengukuran', 'waktu'): (('C.pengukuran.2', 'sebagian'),),
    ('pengukuran', 'kuantitas'): (('B.pengukuran.2', 'pengayaan'),),
    ('pengukuran', 'konversi'): (('B.pengukuran.1', 'sebagian'), ('B.pengukuran.2', 'penuh')),
    ('pengukuran', 'luas_volume'): (('B.pengukuran.3', 'sebagian'),),
    ('pengukuran', 'jam'): (('C.pengukuran.2', 'penuh'),),
    ('pola-bilangan', 'aritmetika'): (('B.aljabar.2', 'sebagian'), ('D.aljabar.1', 'penuh')),
    ('pola-bilangan', 'geometri'): (('C.aljabar.2', 'penuh'),),
    ('pola-bilangan', 'bertingkat'): (('D.aljabar.1', 'sebagian'),),
    ('pola-bilangan', 'siklus'): (('A.aljabar.2', 'sebagian'),),
    ('pola-bilangan', 'korek'): (('B.aljabar.2', 'sebagian'),),
    ('pola-bilangan', 'titik'): (('D.aljabar.1', 'sebagian'),),
    ('pola-bilangan', 'hari'): (('A.aljabar.2', 'sebagian'),),
    ('pola-bilangan', 'sisa'): (('D.aljabar.1', 'pengayaan'),),
    ('pola-bilangan', 'pecahan'): (('B.bilangan.8', 'sebagian'),),
    ('pola-bilangan', 'jumlah'): (('D.aljabar.1', 'sebagian'),),
    ('statistika', 'rata'): (('D.data.4', 'sebagian'), ('D.data.5', 'sebagian')),
    ('statistika', 'gabungan'): (('D.data.4', 'sebagian'),),
    ('statistika', 'median_modus'): (('D.data.4', 'sebagian'),),
    ('statistika', 'lingkaran'): (('D.data.2', 'sebagian'),),
    ('statistika', 'diagram'): (('B.data.1', 'sebagian'), ('C.data.1', 'sebagian'), ('D.data.2', 'sebagian')),
    ('statistika', 'turus'): (('A.data.1', 'sebagian'), ('A.data.2', 'sebagian'), ('B.data.1', 'sebagian'), ('C.data.1', 'sebagian')),
    ('statistika', 'piktogram'): (('A.data.2', 'sebagian'), ('B.data.1', 'sebagian'), ('C.data.1', 'sebagian')),
    ('statistika', 'jangkauan'): (('A.data.1', 'sebagian'), ('D.data.4', 'sebagian')),
    ('teori-bilangan', 'kelipatan_rentang'): (('B.bilangan.7', 'sebagian'),),
    ('teori-bilangan', 'sisa_operasi'): (('B.bilangan.6', 'pengayaan'),),
    ('teori-bilangan', 'prima_rentang'): (('B.bilangan.7', 'pengayaan'),),
    ('teori-bilangan', 'jumlah_kelipatan'): (('B.bilangan.7', 'pengayaan'),),
    ('teori-bilangan', 'keterbagian'): (('B.bilangan.7', 'pengayaan'),),
    ('teori-bilangan', 'prima'): (('B.bilangan.7', 'pengayaan'),),
    ('teori-bilangan', 'kpk'): (('C.bilangan.6', 'penuh'),),
    ('teori-bilangan', 'fpb_kpk'): (('C.bilangan.6', 'sebagian'),),
    ('teori-bilangan', 'sisa'): (('B.bilangan.6', 'pengayaan'),),
    ('teori-bilangan', 'paritas'): (('B.bilangan.6', 'pengayaan'),),
    ('teori-bilangan', 'pangkat'): (('D.bilangan.1', 'pengayaan'),),
    ('teori-bilangan', 'gauss'): (('D.aljabar.1', 'pengayaan'),),
}


def butir(capaian_id: str) -> ButirCP:
    """Butir CP menurut id; `KeyError` bila tidak dikenal."""
    return _PER_ID[capaian_id]


def butir_tanpa_grup() -> Tuple[ButirCP, ...]:
    """Butir CP yang belum dilatih grup mana pun (celah cakupan), urut fase dan elemen."""
    terpakai = {cid for isi in CP_PER_GRUP.values() for cid, _ in isi}
    return tuple(b for b in CAPAIAN if b.id not in terpakai)


_PER_ID: Dict[str, ButirCP] = {b.id: b for b in CAPAIAN}
