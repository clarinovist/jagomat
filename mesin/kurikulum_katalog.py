"""Peta kurikulum Jagomat sebagai data beku: satu sumber untuk label topik, topik cek, dan grup mastery.

Pemisahan tanggung jawab: modul ini adalah PETA KURIKULUM (data: topik mana
diberi nama apa untuk awam, topik cek tiap kelas, dan keterampilan/grup mana
yang diaudit mastery), sedangkan MESIN SOAL (kode: `topics`, `topic_*`,
`templates`, `generator`) tetap yang membuat soal. Modul ini lapisan aplikasi:
hanya mengimpor stdlib dan tidak boleh diimpor modul inti soal (`generator` dan
penutupan impornya). Keselarasan dengan registry `topics.PAKET` dijaga tes
`test_kurikulum_keselarasan.py`.

`topik_awam.NAMA_AWAM`, `mastery_catalog.KELOMPOK`, `cek_gratis_skor.TOPIK_PER_KELAS`
dan `TOPIK_DASAR` diturunkan dari sini. CP/elemen Kurikulum Merdeka menyusul di
Fase 2 dan belum ada di entri.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

# Satu grup mastery: (kode, nama, pola template). Bentuk sama dengan KELOMPOK lama.
Grup = Tuple[str, str, Tuple[str, ...]]


@dataclass(frozen=True)
class EntriTopik:
    topik_id: str
    label_awam: Optional[str]
    grup: Tuple[Grup, ...]


# Urutan entri = urutan `mastery_catalog.KELOMPOK` (dipertahankan persis).
KATALOG: Tuple[EntriTopik, ...] = (
    EntriTopik(
        'aritmatika-lanjut',
        'Aritmetika lanjut',
        (
            ('konversi', 'Konversi satuan', ('satuan_konversi',)),
            ('kecepatan', 'Kecepatan, jarak, dan waktu', ('kecepatan_jarak_waktu',)),
            ('gerak_relatif', 'Berpapasan dan menyusul', ('berpapasan', 'menyusul')),
            ('debit', 'Debit', ('debit',)),
            ('senilai', 'Perbandingan senilai', ('perbandingan_senilai',)),
            ('berbalik', 'Perbandingan berbalik nilai', ('perbandingan_berbalik',)),
            ('kerja', 'Kerja bersama', ('kerja_bersama',)),
            ('diskon', 'Persen dan diskon', ('persen_diskon',)),
            ('untung', 'Untung dan rugi', ('persen_untung_rugi',)),
            ('persen_bertahap', 'Persen bertingkat', ('persen_bertingkat',)),
        ),
    ),
    EntriTopik(
        'aritmetika-dasar',
        'Aritmetika dasar',
        (
            ('operasi', 'Urutan operasi dan tanda kurung', ('urutan_operasi_1', 'operasi_berkurung')),
            ('fpb', 'Faktor persekutuan terbesar', ('fpb_dua_bilangan',)),
            ('pecahan_campuran', 'Operasi campuran pecahan', ('pecahan_operasi_campuran',)),
            ('urut_bilangan', 'Mengurutkan pecahan, desimal, dan persen', ('urut_pecahan_desimal_persen',)),
            ('pecahan_kali_bagi', 'Mengalikan dan membagi pecahan', ('pecahan_kali_bagi',)),
            ('taksiran', 'Pembulatan dan taksiran', ('pembulatan_taksiran',)),
        ),
    ),
    EntriTopik(
        'bilangan-dasar',
        'Bilangan dasar',
        (
            ('penjumlahan_dasar', 'Penjumlahan sampai 20', ('tambah_dasar',)),
            ('pengurangan_dasar', 'Pengurangan sampai 20', ('kurang_dasar',)),
            ('bilangan_hilang', 'Bilangan yang hilang', ('bilangan_hilang',)),
            ('nilai_tempat', 'Nilai tempat puluhan dan satuan', ('nilai_tempat',)),
            ('membandingkan', 'Membandingkan bilangan', ('bandingkan_bilangan',)),
        ),
    ),
    EntriTopik(
        'bilangan-sekolah',
        None,
        (
            ('nilai_tempat_besar', 'Nilai tempat bilangan besar', ('nilai_tempat_besar',)),
            ('urutkan_bilangan', 'Bilangan terbesar dan terkecil', ('urutkan_bilangan',)),
            ('tambah_kurang_bersusun', 'Penjumlahan dan pengurangan bersusun', ('tambah_kurang_bersusun',)),
            ('kali_bagi_sekolah', 'Perkalian dan pembagian habis', ('kali_bagi_sekolah',)),
            ('kalimat_matematika', 'Kalimat matematika', ('kalimat_matematika',)),
        ),
    ),
    EntriTopik(
        'berhitung-sekolah',
        'Berhitung',
        (
            ('perkalian_dasar', 'Perkalian dasar kelas 3–4', ('perkalian_dasar',)),
            ('pembagian_dasar', 'Pembagian dasar kelas 3–4', ('pembagian_dasar',)),
            ('pecahan_sederhana', 'Pecahan sederhana kelas 3–4', ('pecahan_bagian_dasar',)),
            ('nilai_tempat_besar', 'Nilai tempat ratusan dan ribuan', ('nilai_tempat_ribuan',)),
        ),
    ),
    EntriTopik(
        'geometri-datar',
        'Geometri datar',
        (
            ('sudut', 'Hubungan sudut', ('sudut_pelurus_berpenyiku', 'jumlah_sudut_segitiga', 'sudut_luar_segitiga')),
            ('keliling_luas', 'Keliling dan luas persegi panjang', ('keliling_luas_datar',)),
            ('segitiga', 'Luas segitiga dan jajargenjang', ('luas_segitiga_jajargenjang',)),
            ('segiempat', 'Luas segiempat lainnya', ('luas_segiempat_lain',)),
            ('lingkaran', 'Keliling dan luas lingkaran', ('lingkaran_keliling_luas',)),
            ('juring', 'Juring lingkaran', ('juring',)),
            ('arsiran', 'Luas daerah arsiran', ('luas_arsiran',)),
            ('perbandingan', 'Perbandingan ukuran bangun', ('perbandingan_ukuran',)),
            ('kotak', 'Luas dengan kotak satuan', ('luas_kotak_satuan',)),
            ('simetri', 'Simetri bangun', ('simetri_bangun',)),
        ),
    ),
    EntriTopik(
        'geometri-ruang',
        None,
        (
            ('unsur', 'Unsur bangun ruang', ('unsur_bangun',)),
            ('volume_balok', 'Volume kubus dan balok', ('volume_kubus_balok',)),
            ('volume_prisma', 'Volume prisma dan tabung', ('volume_prisma_tabung',)),
            ('permukaan', 'Luas permukaan', ('luas_permukaan',)),
            ('jaring', 'Jaring-jaring bangun ruang', ('jaring_jaring',)),
            ('dicat', 'Kubus yang dicat', ('kubus_dicat',)),
            ('perbandingan', 'Perbandingan volume', ('perbandingan_volume',)),
        ),
    ),
    EntriTopik(
        'kombinatorik',
        None,
        (
            ('mencacah', 'Aturan penjumlahan dan perkalian', ('aturan_tambah', 'aturan_kali')),
            ('susun', 'Menyusun bilangan dengan syarat', ('susun_bilangan', 'susun_bilangan_syarat')),
            ('permutasi', 'Permutasi dan blok', ('permutasi_urutan', 'permutasi_blok')),
            ('kombinasi', 'Memilih kelompok', ('kombinasi_pilih',)),
            ('pasangan', 'Menghitung pasangan', ('jabat_tangan',)),
            ('jalur', 'Menghitung jalur pada petak', ('jalur_petak',)),
            ('merpati', 'Prinsip sarang merpati', ('sarang_merpati',)),
            ('himpunan', 'Gabungan dua himpunan', ('inklusi_eksklusi_2',)),
        ),
    ),
    EntriTopik(
        'logika',
        None,
        (
            ('pengandaian', 'Penalaran benar-salah dan pengandaian', ('benar_salah_pengandaian',)),
            ('tabel', 'Penalaran dengan tabel', ('tabel_penalaran',)),
            ('jumlah_selisih', 'Hubungan jumlah dan selisih', ('jumlah_selisih', 'dua_besaran_selisih')),
            ('umur', 'Penalaran soal umur', ('soal_umur',)),
            ('uang', 'Penalaran soal uang', ('soal_uang',)),
        ),
    ),
    EntriTopik(
        'pengukuran',
        'Pengukuran',
        (
            ('skala', 'Skala peta', ('skala_peta',)),
            ('waktu', 'Konversi satuan waktu', ('satuan_waktu_lama', 'jam_menit_detik')),
            ('kuantitas', 'Satuan kuantitas', ('satuan_kuantitas',)),
            ('konversi', 'Konversi satuan campuran', ('tangga_satuan_campuran',)),
            ('luas_volume', 'Satuan luas dan volume', ('satuan_luas_volume',)),
            ('jam', 'Waktu selesai kegiatan', ('jam_selesai',)),
        ),
    ),
    EntriTopik(
        'pola-bilangan',
        'Pola bilangan',
        (
            ('aritmetika', 'Barisan aritmetika dan posisi suku', ('deret_aritmetika', 'deret_aritmetika_turun', 'deret_terbalik_aritmetika', 'suku_ke_n')),
            ('geometri', 'Barisan geometri dan posisi suku', ('deret_geometri', 'deret_terbalik_geometri')),
            ('bertingkat', 'Barisan bertingkat', ('deret_bertingkat',)),
            ('siklus', 'Pola berulang dan jumlah siklus', ('siklus_huruf', 'siklus_warna', 'jumlah_siklus')),
            ('korek', 'Pola korek api', ('korek_api',)),
            ('titik', 'Pola titik segitiga', ('titik_segitiga',)),
            ('hari', 'Siklus hari', ('siklus_hari',)),
            ('sisa', 'Sisa pembagian dalam siklus', ('sisa_bagi_siklus',)),
            ('pecahan', 'Pola pecahan', ('pola_pecahan',)),
            ('jumlah', 'Jumlah barisan aritmetika', ('jumlah_deret',)),
        ),
    ),
    EntriTopik(
        'statistika',
        'Statistika',
        (
            ('rata', 'Rata-rata', ('rata_rata',)),
            ('gabungan', 'Rata-rata gabungan', ('rata_rata_gabungan',)),
            ('median_modus', 'Median dan modus', ('median_modus',)),
            ('lingkaran', 'Membaca diagram lingkaran', ('diagram_lingkaran',)),
            ('diagram', 'Membaca diagram batang dan garis', ('diagram_batang_garis',)),
            ('turus', 'Membaca tabel turus', ('tabel_turus',)),
            ('piktogram', 'Membaca piktogram', ('piktogram',)),
            ('jangkauan', 'Jangkauan data', ('jangkauan_data',)),
        ),
    ),
    EntriTopik(
        'teori-bilangan',
        None,
        (
            ('kelipatan_rentang', 'Banyak kelipatan dalam rentang', ('banyak_kelipatan',)),
            ('sisa_operasi', 'Sisa penjumlahan dan perkalian', ('sisa_operasi',)),
            ('prima_rentang', 'Banyak bilangan prima', ('banyak_prima',)),
            ('jumlah_kelipatan', 'Jumlah kelipatan', ('jumlah_kelipatan',)),
            ('keterbagian', 'Ciri keterbagian', ('keterbagian',)),
            ('prima', 'Bilangan prima dan faktorisasi', ('prima_faktorisasi',)),
            ('kpk', 'Kelipatan persekutuan terkecil', ('kpk_dua_bilangan',)),
            ('fpb_kpk', 'Hubungan FPB dan KPK', ('fpb_kpk_hubungan',)),
            ('sisa', 'Sisa pembagian', ('sisa_pembagian',)),
            ('paritas', 'Bilangan ganjil dan genap', ('paritas',)),
            ('pangkat', 'Angka satuan perpangkatan', ('angka_satuan_pangkat',)),
            ('gauss', 'Penjumlahan berpasangan', ('gauss_deret',)),
        ),
    ),
    EntriTopik(
        'matematika-awal',
        None,
        (
            ('kenali_bentuk', 'Mengenal bentuk bangun datar', ('kenali_bentuk',)),
            ('ukur_satuan_tak_baku', 'Mengukur panjang dengan satuan tak baku', ('ukur_satuan_tak_baku',)),
            ('baca_diagram_gambar', 'Membaca diagram gambar', ('baca_diagram_gambar',)),
            ('pola_posisi', 'Pola dan posisi benda', ('pola_posisi',)),
            ('pecahan_setengah', 'Pecahan setengah dan seperempat', ('pecahan_setengah',)),
            ('waktu_berat_awal', 'Jam penuh dan berat kg', ('waktu_berat_awal',)),
            ('turus_gambar_awal', 'Membaca diagram turus', ('turus_gambar_awal',)),
            ('ukur_konversi_awal', 'Mengubah satuan panjang dan berat', ('ukur_konversi_awal',)),
            ('bandingkan_ciri_bangun', 'Membandingkan ciri bangun datar', ('bandingkan_ciri_bangun',)),
            ('peluang_dasar', 'Peluang dan kemungkinan kejadian', ('peluang_dasar',)),
            ('bilang_benda_awal', 'Membilang benda dan mengenal bilangan sampai 10', ('bilang_benda_awal',)),
            ('tambah_kurang_20', 'Menjumlah dan mengurang sampai 20', ('tambah_kurang_20',)),
            ('tambah_kurang_100', 'Penjumlahan dan pengurangan sampai 100', ('tambah_kurang_100',)),
            ('unsur_bangun_datar', 'Sisi, sudut, garis sejajar dan tegak lurus', ('unsur_bangun_datar',)),
            ('pecahan_senilai_desimal', 'Pecahan senilai, desimal, dan persen', ('pecahan_senilai_desimal',)),
            ('luas_petak_volume_kubus', 'Luas petak dan volume kubus satuan', ('luas_petak_volume_kubus',)),
            ('ciri_komposisi_bangun', 'Ciri, susunan, dan uraian bangun datar', ('ciri_komposisi_bangun',)),
            ('keliling_gabungan', 'Keliling bangun datar dan gabungan', ('keliling_gabungan',)),
            ('pecahan_bilangan_asli_desimal', 'Pecahan dengan bilangan asli dan desimal', ('pecahan_bilangan_asli_desimal',)),
        ),
    ),
)

# Urutan tampil label awam (berbeda dari urutan KATALOG; dipertahankan persis).
URUTAN_LABEL_AWAM: Tuple[str, ...] = (
    'pola-bilangan',
    'statistika',
    'geometri-datar',
    'bilangan-dasar',
    'berhitung-sekolah',
    'pengukuran',
    'aritmetika-dasar',
    'aritmatika-lanjut',
)

# Topik cek gratis (keputusan pemilik, 19 Nov 2026): kelas 3-6 mengikuti kelas.
TOPIK_CEK_PER_KELAS: Dict[int, Tuple[str, ...]] = {
    3: ("berhitung-sekolah", "geometri-datar", "statistika"),
    4: ("berhitung-sekolah", "pengukuran", "geometri-datar"),
    5: ("aritmetika-dasar", "aritmatika-lanjut", "geometri-datar"),
    6: ("aritmetika-dasar", "aritmatika-lanjut", "geometri-datar"),
}
# Topik cek kelas 1-2.
TOPIK_CEK_DASAR = "bilangan-dasar"


def label_awam() -> Dict[str, str]:
    """Peta topik_id -> label awam, urut `URUTAN_LABEL_AWAM`."""
    per_id = {e.topik_id: e.label_awam for e in KATALOG if e.label_awam is not None}
    return {topik_id: per_id[topik_id] for topik_id in URUTAN_LABEL_AWAM}


def kelompok_mastery() -> Dict[str, Tuple[Grup, ...]]:
    """Peta topik_id -> grup mastery, urut `KATALOG`."""
    return {e.topik_id: e.grup for e in KATALOG}
