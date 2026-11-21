"""Nama tampilan tipe soal, bukan judul kartu konsep atau ID penyimpanan.

Satu kartu konsep dapat membantu beberapa tipe soal. Ringkasan generate dan
pilihan latihan ulang harus memakai nama tipe yang sama, bukan judul kartu
umum yang dapat menyamarkan perbedaan variasi soal.
"""

NAMA_TIPE_SOAL = {
    "tambah_dasar": "Penjumlahan sampai 20",
    "kurang_dasar": "Pengurangan sampai 20",
    "bilangan_hilang": "Bilangan yang hilang",
    "nilai_tempat": "Nilai tempat puluhan dan satuan",
    "bandingkan_bilangan": "Membandingkan bilangan",
    "perkalian_dasar": "Perkalian bilangan dasar",
    "pembagian_dasar": "Pembagian sama rata",
    "pecahan_bagian_dasar": "Pecahan sederhana",
    "nilai_tempat_ribuan": "Nilai tempat ratusan dan ribuan",
    "nilai_tempat_besar": "Nilai tempat bilangan besar",
    "kenali_bentuk": "Mengenal bentuk bangun datar",
    "ukur_satuan_tak_baku": "Mengukur panjang dengan satuan tak baku",
    "baca_diagram_gambar": "Membaca diagram gambar",
    "pola_posisi": "Pola dan posisi benda",
    "pecahan_setengah": "Pecahan setengah dan seperempat",
    "waktu_berat_awal": "Jam penuh dan berat kg",
    "turus_gambar_awal": "Membaca diagram turus",
    "ukur_konversi_awal": "Mengubah satuan panjang dan berat (m-cm, kg-g)",
    "bandingkan_ciri_bangun": "Membandingkan ciri bangun datar",
    "peluang_dasar": "Peluang dan kemungkinan kejadian",
    "bilang_benda_awal": "Membilang benda dan mengenal bilangan sampai 10",
    "tambah_kurang_20": "Menjumlah dan mengurang sampai 20",
    "tambah_kurang_100": "Penjumlahan dan pengurangan sampai 100",
    "unsur_bangun_datar": "Sisi, sudut, garis sejajar dan tegak lurus pada bangun datar",
    "pecahan_senilai_desimal": "Pecahan senilai, desimal, dan persen",
    "luas_petak_volume_kubus": "Luas dengan petak dan volume dengan kubus satuan",
    "ciri_komposisi_bangun": "Ciri, susunan, dan uraian bangun datar",
    "keliling_gabungan": "Keliling bangun datar dan bangun gabungan",
    "pecahan_bilangan_asli_desimal": "Pecahan dengan bilangan asli dan desimal",
    "urutkan_bilangan": "Bilangan terbesar dan terkecil",
    "tambah_kurang_bersusun": "Penjumlahan dan pengurangan bersusun",
    "kali_bagi_sekolah": "Perkalian dan pembagian habis",
    "kalimat_matematika": "Kalimat matematika",
    "banyak_kelipatan": "Banyak kelipatan dalam rentang",
    "sisa_operasi": "Sisa penjumlahan dan perkalian",
    "banyak_prima": "Banyak prima dalam rentang",
    "jumlah_kelipatan": "Jumlah kelipatan sampai batas",
    "median_modus": "Median & modus",
    "diagram_batang_garis": "Diagram batang & garis",
    "soal_umur": "Soal tentang umur",
    "benar_salah_pengandaian": "Pengandaian benar atau salah",
    "luas_kotak_satuan": "Menghitung luas dengan kotak satuan",
    "simetri_bangun": "Simetri bangun datar",
    "fpb_kpk_hubungan": "Hubungan FPB dan KPK",
    "deret_geometri": "Barisan geometri",
    "deret_terbalik_geometri": "Barisan geometri — mencari posisi",
}


def nama_tipe_soal(template_id: str) -> str:
    """Nama konsisten lintas tampilan; ID warisan tetap dapat ditampilkan."""
    return NAMA_TIPE_SOAL.get(
        template_id,
        template_id.replace("_", " ").replace("-", " ").capitalize(),
    )
