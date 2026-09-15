"""Target keterampilan Jagomat v1; bukan silabus sekolah atau bobot soal.

Grup menyatukan variasi satu keterampilan, bukan sekadar kartu rumus bersama.
Semua pola dalam grup yang tersedia di kelas anak wajib memiliki bukti. Satu
pola hanya berada pada satu target dan satu topik; jumlah soal tidak memberi bobot.
"""
from dataclasses import dataclass
from typing import Tuple

import topics
from templates import LEVEL

VERSI_KATALOG = "jagomat-2026-09-v1"


@dataclass(frozen=True)
class TargetMateri:
    id: str
    nama: str
    topik_id: str
    topik: str
    pola: Tuple[str, ...]


# Pemetaan eksplisit: FPB tidak dianggap KPK; luas segiempat tidak mewakili
# arsiran; rata-rata sederhana belum membuktikan rata-rata gabungan. Varian
# yang memang berbagi keterampilan tetap diuji semuanya, bukan salah satunya.
KELOMPOK = {
    "aritmatika-lanjut": (
        ("konversi", "Konversi satuan", ("satuan_konversi",)),
        ("kecepatan", "Kecepatan, jarak, dan waktu", ("kecepatan_jarak_waktu",)),
        ("gerak_relatif", "Berpapasan dan menyusul", ("berpapasan", "menyusul")),
        ("debit", "Debit", ("debit",)),
        ("senilai", "Perbandingan senilai", ("perbandingan_senilai",)),
        ("berbalik", "Perbandingan berbalik nilai", ("perbandingan_berbalik",)),
        ("kerja", "Kerja bersama", ("kerja_bersama",)),
        ("diskon", "Persen dan diskon", ("persen_diskon",)),
        ("untung", "Untung dan rugi", ("persen_untung_rugi",)),
        ("persen_bertahap", "Persen bertingkat", ("persen_bertingkat",)),
    ),
    "aritmetika-dasar": (
        ("operasi", "Urutan operasi dan tanda kurung", ("urutan_operasi_1", "operasi_berkurung")),
        ("fpb", "Faktor persekutuan terbesar", ("fpb_dua_bilangan",)),
        ("pecahan_campuran", "Operasi campuran pecahan", ("pecahan_operasi_campuran",)),
        ("urut_bilangan", "Mengurutkan pecahan, desimal, dan persen", ("urut_pecahan_desimal_persen",)),
        ("pecahan_kali_bagi", "Mengalikan dan membagi pecahan", ("pecahan_kali_bagi",)),
        ("taksiran", "Pembulatan dan taksiran", ("pembulatan_taksiran",)),
    ),
    "geometri-datar": (
        ("sudut", "Hubungan sudut", ("sudut_pelurus_berpenyiku", "jumlah_sudut_segitiga", "sudut_luar_segitiga")),
        ("keliling_luas", "Keliling dan luas persegi panjang", ("keliling_luas_datar",)),
        ("segitiga", "Luas segitiga dan jajargenjang", ("luas_segitiga_jajargenjang",)),
        ("segiempat", "Luas segiempat lainnya", ("luas_segiempat_lain",)),
        ("lingkaran", "Keliling dan luas lingkaran", ("lingkaran_keliling_luas",)),
        ("juring", "Juring lingkaran", ("juring",)),
        ("arsiran", "Luas daerah arsiran", ("luas_arsiran",)),
        ("perbandingan", "Perbandingan ukuran bangun", ("perbandingan_ukuran",)),
        ("kotak", "Luas dengan kotak satuan", ("luas_kotak_satuan",)),
        ("simetri", "Simetri bangun", ("simetri_bangun",)),
    ),
    "geometri-ruang": (
        ("unsur", "Unsur bangun ruang", ("unsur_bangun",)),
        ("volume_balok", "Volume kubus dan balok", ("volume_kubus_balok",)),
        ("volume_prisma", "Volume prisma dan tabung", ("volume_prisma_tabung",)),
        ("permukaan", "Luas permukaan", ("luas_permukaan",)),
        ("jaring", "Jaring-jaring bangun ruang", ("jaring_jaring",)),
        ("dicat", "Kubus yang dicat", ("kubus_dicat",)),
        ("perbandingan", "Perbandingan volume", ("perbandingan_volume",)),
    ),
    "kombinatorik": (
        ("mencacah", "Aturan penjumlahan dan perkalian", ("aturan_tambah", "aturan_kali")),
        ("susun", "Menyusun bilangan dengan syarat", ("susun_bilangan", "susun_bilangan_syarat")),
        ("permutasi", "Permutasi dan blok", ("permutasi_urutan", "permutasi_blok")),
        ("kombinasi", "Memilih kelompok", ("kombinasi_pilih",)),
        ("pasangan", "Menghitung pasangan", ("jabat_tangan",)),
        ("jalur", "Menghitung jalur pada petak", ("jalur_petak",)),
        ("merpati", "Prinsip sarang merpati", ("sarang_merpati",)),
        ("himpunan", "Gabungan dua himpunan", ("inklusi_eksklusi_2",)),
    ),
    "logika": (
        ("pengandaian", "Penalaran benar-salah dan pengandaian", ("benar_salah_pengandaian",)),
        ("tabel", "Penalaran dengan tabel", ("tabel_penalaran",)),
        ("jumlah_selisih", "Hubungan jumlah dan selisih", ("jumlah_selisih", "dua_besaran_selisih")),
        ("umur", "Penalaran soal umur", ("soal_umur",)),
        ("uang", "Penalaran soal uang", ("soal_uang",)),
    ),
    "pengukuran": (
        ("skala", "Skala peta", ("skala_peta",)),
        ("waktu", "Konversi satuan waktu", ("satuan_waktu_lama", "jam_menit_detik")),
        ("kuantitas", "Satuan kuantitas", ("satuan_kuantitas",)),
        ("konversi", "Konversi satuan campuran", ("tangga_satuan_campuran",)),
        ("luas_volume", "Satuan luas dan volume", ("satuan_luas_volume",)),
        ("jam", "Waktu selesai kegiatan", ("jam_selesai",)),
    ),
    "pola-bilangan": (
        ("aritmetika", "Barisan aritmetika dan posisi suku", ("deret_aritmetika", "deret_aritmetika_turun", "deret_terbalik_aritmetika", "suku_ke_n")),
        ("geometri", "Barisan geometri dan posisi suku", ("deret_geometri", "deret_terbalik_geometri")),
        ("bertingkat", "Barisan bertingkat", ("deret_bertingkat",)),
        ("siklus", "Pola berulang dan jumlah siklus", ("siklus_huruf", "siklus_warna", "jumlah_siklus")),
        ("korek", "Pola korek api", ("korek_api",)),
        ("titik", "Pola titik segitiga", ("titik_segitiga",)),
        ("hari", "Siklus hari", ("siklus_hari",)),
        ("sisa", "Sisa pembagian dalam siklus", ("sisa_bagi_siklus",)),
        ("pecahan", "Pola pecahan", ("pola_pecahan",)),
        ("jumlah", "Jumlah barisan aritmetika", ("jumlah_deret",)),
    ),
    "statistika": (
        ("rata", "Rata-rata", ("rata_rata",)),
        ("gabungan", "Rata-rata gabungan", ("rata_rata_gabungan",)),
        ("median_modus", "Median dan modus", ("median_modus",)),
        ("lingkaran", "Membaca diagram lingkaran", ("diagram_lingkaran",)),
        ("diagram", "Membaca diagram batang dan garis", ("diagram_batang_garis",)),
        ("turus", "Membaca tabel turus", ("tabel_turus",)),
        ("piktogram", "Membaca piktogram", ("piktogram",)),
        ("jangkauan", "Jangkauan data", ("jangkauan_data",)),
    ),
    "teori-bilangan": (
        ("keterbagian", "Ciri keterbagian", ("keterbagian",)),
        ("prima", "Bilangan prima dan faktorisasi", ("prima_faktorisasi",)),
        ("kpk", "Kelipatan persekutuan terkecil", ("kpk_dua_bilangan",)),
        ("fpb_kpk", "Hubungan FPB dan KPK", ("fpb_kpk_hubungan",)),
        ("sisa", "Sisa pembagian", ("sisa_pembagian",)),
        ("paritas", "Bilangan ganjil dan genap", ("paritas",)),
        ("pangkat", "Angka satuan perpangkatan", ("angka_satuan_pangkat",)),
        ("gauss", "Penjumlahan berpasangan", ("gauss_deret",)),
    ),
}


def katalog_target(level: str) -> Tuple[TargetMateri, ...]:
    """Kelas tidak dikenal tidak diam-diam diberi target kelas lain."""
    if level not in LEVEL:
        return ()
    hasil = []
    for topik_id in topics.daftar_topik():
        if topik_id == "campuran":
            continue
        paket = topics.ambil(topik_id)
        pola_kelas = set(paket.komposisi.get(level, ()))
        for kode, nama, pola in KELOMPOK.get(topik_id, ()):
            tersedia = tuple(t for t in pola if t in pola_kelas)
            if tersedia:
                hasil.append(TargetMateri(topik_id + "." + kode, nama, topik_id, paket.nama, tersedia))
    return tuple(hasil)
