"""Label jenis soal Latihan Lomba yang jelas untuk Guru, satu per template terdaftar.

Dipakai halaman guru ("Paling sering salah"); anak tidak melihat label ini. Id baru yang belum ada di sini
jatuh ke label turunan id (`contest_results.label_jenis`), dan tes mewajibkan setiap id terdaftar punya label.
"""
from __future__ import annotations

from typing import Dict

LABEL_JENIS: Dict[str, str] = {
    # Bangun datar dan ruang
    "bgn_benda_ruang": "Mengenali benda berbentuk bangun ruang",
    "bgn_jumlah_sisi": "Menjumlah sisi dari beberapa bangun datar",
    "bgn_keliling_susun": "Keliling bangun dari kotak yang disusun",
    "bgn_kubus_berlapis": "Menghitung kubus kecil yang ditumpuk berlapis",
    "bgn_persegi_kisi": "Menghitung persegi di papan kotak",
    "bgn_rusuk_titik_sisi": "Titik sudut, sisi, dan rusuk balok/kubus",
    "bgn_segitiga_diagonal": "Menghitung segitiga pada persegi panjang bergaris",
    "bgn_tempel_persegi": "Keliling setelah persegi ditempel",
    "bgn_titik_sudut": "Mengenali bangun dari titik sudut dan sisinya",
    # Bilangan
    "bil_cacah_syarat": "Menghitung bilangan dengan syarat angka",
    "bil_dua_angka_jumlah": "Bilangan dua angka dengan jumlah angka tertentu",
    "bil_genap_ganjil": "Menghitung kartu genap atau ganjil",
    "bil_kartu_nilai_tempat": "Membaca bilangan dari kartu puluhan dan satuan",
    "bil_nilai_angka": "Nilai angka menurut nilai tempat",
    "bil_pola_bertambah": "Pola gambar yang bertambah",
    "bil_pola_berulang": "Pola berulang",
    "bil_selisih_kartu": "Selisih bilangan terbesar dan terkecil dari kartu",
    "bil_syarat_jumlah_angka": "Bilangan terkecil dengan jumlah angka tertentu",
    # Operasi hitung
    "ops_ayam_kambing": "Kaki ayam dan kambing (jumlah kepala dan kaki)",
    "ops_berbagi_sisa": "Membagi sisa setelah diambil",
    "ops_cerita_dua_langkah": "Soal cerita dua langkah",
    "ops_deret_pasangan": "Menjumlah deret dengan memasangkan",
    "ops_hitung_gambar": "Menghitung dari gambar benda",
    "ops_inggris_dua_langkah": "Soal cerita dua langkah (bahasa Inggris)",
    "ops_inggris_jumlah_selisih": "Jumlah dan selisih dua gambar (bahasa Inggris)",
    "ops_jumlah_selisih": "Jumlah dan selisih dua gambar",
    "ops_kaki_hewan": "Menghitung kaki semua hewan",
    "ops_kotak_kosong": "Mencari nilai gambar pada persamaan",
    "ops_umur": "Selisih umur",
    # Pengukuran
    "ukur_jam_analog": "Membaca jam analog",
    "ukur_kalender_hari": "Mencari hari dari tanggal di kalender",
    "ukur_kalender_n_hari_lagi": "Mencari hari setelah sekian hari",
    "ukur_lama_kegiatan": "Lama kegiatan dari dua jam",
    "ukur_lama_menit": "Lama kegiatan dalam menit",
    "ukur_minggu_hari": "Mengubah minggu dan hari menjadi hari",
    "ukur_panjang_klip": "Mengukur panjang dengan klip",
    "ukur_timbangan_berantai": "Timbangan seimbang berantai",
    "ukur_uang_kembalian": "Uang kembalian",
}
