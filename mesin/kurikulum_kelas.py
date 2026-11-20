"""Materi Kurikulum Merdeka per kelas: kelas 1-6 -> bab (materi) -> sub-materi -> grup soal.

Sumber bab: buku siswa resmi *Matematika untuk SD/MI Kelas I-VI* (Kemendikbudristek, cetakan
pertama 2022, satu jilid per kelas), daftar isi; dicek ulang di
`riset/referensi/kurikulum/2026-11-12-cek-per-kelas-buku-teks.md`. CP resmi dibagi per fase (dua
kelas), sedangkan pembagian per kelas di sini mengikuti buku teks tersebut.

Tiap bab menunjuk grup di `kurikulum_katalog.KATALOG` (topik_id, kode grup) dengan kecocokan:
"ada" (grup melatih isi bab) atau "sebagian" (rentang/bentuk/kelas belum pas, atau soal hanya teks
padahal bab butuh gambar). Bab tanpa grup = belum ada soal. Ketersediaan grup di level kelas itu
(P1-P6) TIDAK ditulis di sini; dihitung dari komposisi topik oleh pemakai (halaman admin).

Modul ini data beku, hanya stdlib, dan tidak diimpor modul inti soal.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

KECOCOKAN_BAB = ("ada", "sebagian")
SUMBER_BAB = "Buku siswa Matematika SD/MI Kelas I-VI, Kemendikbudristek 2022"

# (topik_id, kode grup, kecocokan)
Pelatih = Tuple[str, str, str]


@dataclass(frozen=True)
class Bab:
    nomor: int
    judul: str
    sub_materi: Tuple[str, ...]
    pelatih: Tuple[Pelatih, ...]


@dataclass(frozen=True)
class Kelas:
    kelas: int
    bab: Tuple[Bab, ...]


KELAS: Tuple[Kelas, ...] = (
    Kelas(1, (
        Bab(1, "Membilang sampai 10",
            ("Membilang banyak benda", "Membaca dan menulis lambang bilangan",
             "Lebih dari, kurang dari, sama dengan"),
            (("bilangan-dasar", "membandingkan", "sebagian"),)),
        Bab(2, "Penjumlahan sampai 10",
            ("Menggabungkan dua kumpulan benda", "Kalimat penjumlahan", "Bilangan yang hilang"),
            (("bilangan-dasar", "penjumlahan_dasar", "ada"),
             ("bilangan-dasar", "bilangan_hilang", "sebagian"))),
        Bab(3, "Pengurangan sampai 10",
            ("Mengambil sebagian dari kumpulan benda", "Kalimat pengurangan"),
            (("bilangan-dasar", "pengurangan_dasar", "ada"),)),
        Bab(4, "Mengenal bentuk",
            ("Bangun datar: segitiga, segiempat, lingkaran", "Bangun ruang di sekitar kita"),
            ()),
        Bab(5, "Membilang sampai 20 dan nilai tempat",
            ("Puluhan dan satuan", "Membandingkan dan mengurutkan bilangan sampai 20"),
            (("bilangan-dasar", "nilai_tempat", "ada"),
             ("bilangan-dasar", "membandingkan", "ada"))),
        Bab(6, "Penjumlahan dan pengurangan sampai 20",
            ("Penjumlahan dengan hasil sampai 20", "Pengurangan dari bilangan sampai 20"),
            (("bilangan-dasar", "penjumlahan_dasar", "sebagian"),
             ("bilangan-dasar", "pengurangan_dasar", "sebagian"))),
        Bab(7, "Mengukur panjang benda",
            ("Membandingkan panjang secara langsung", "Mengukur dengan satuan tidak baku"),
            ()),
        Bab(8, "Mengenal diagram",
            ("Diagram gambar sederhana",),
            ()),
    )),
    Kelas(2, (
        Bab(1, "Membilang sampai 50 dan nilai tempat",
            ("Puluhan dan satuan", "Membandingkan bilangan sampai 50"),
            (("bilangan-dasar", "nilai_tempat", "ada"),
             ("bilangan-dasar", "membandingkan", "ada"))),
        Bab(2, "Penjumlahan dan pengurangan",
            ("Penjumlahan dan pengurangan sampai 100", "Bilangan yang hilang"),
            (("bilangan-dasar", "penjumlahan_dasar", "sebagian"),
             ("bilangan-dasar", "pengurangan_dasar", "sebagian"),
             ("bilangan-dasar", "bilangan_hilang", "sebagian"))),
        Bab(3, "Bentuk di sekitar kita",
            ("Bangun datar", "Bangun ruang"),
            ()),
        Bab(4, "Posisi benda dan pola",
            ("Kanan, kiri, depan, belakang, atas, bawah", "Pola gambar dan warna"),
            (("pola-bilangan", "siklus", "sebagian"),)),
        Bab(5, "Pecahan setengah dan seperempat",
            ("Membagi benda sama besar", "Mengenal ½ dan ¼"),
            (("berhitung-sekolah", "pecahan_sederhana", "sebagian"),)),
        Bab(6, "Pengukuran berat dan waktu",
            ("Membandingkan berat", "Membaca jam"),
            (("pengukuran", "jam", "sebagian"),)),
        Bab(7, "Membilang sampai 100",
            ("Nilai tempat puluhan dan satuan", "Membandingkan dan mengurutkan bilangan sampai 100"),
            (("bilangan-dasar", "membandingkan", "ada"),
             ("bilangan-dasar", "nilai_tempat", "ada"))),
        Bab(8, "Diagram turus dan diagram gambar",
            ("Mencatat data dengan turus", "Membaca diagram gambar"),
            (("statistika", "turus", "sebagian"),
             ("statistika", "piktogram", "sebagian"))),
    )),
    Kelas(3, (
        Bab(1, "Bilangan cacah sampai 1.000 dan operasi hitung",
            ("Nilai tempat ratusan, puluhan, satuan", "Membandingkan dan mengurutkan bilangan",
             "Penjumlahan dan pengurangan bersusun", "Perkalian dan pembagian sampai 100"),
            (("bilangan-sekolah", "nilai_tempat_besar", "ada"),
             ("bilangan-sekolah", "urutkan_bilangan", "ada"),
             ("bilangan-sekolah", "tambah_kurang_bersusun", "ada"),
             ("berhitung-sekolah", "nilai_tempat_besar", "ada"),
             ("berhitung-sekolah", "perkalian_dasar", "ada"),
             ("berhitung-sekolah", "pembagian_dasar", "ada"),
             ("bilangan-sekolah", "kali_bagi_sekolah", "ada"))),
        Bab(2, "Kalimat matematika",
            ("Mencari nilai yang belum diketahui", "Soal cerita penjumlahan dan pengurangan"),
            (("bilangan-sekolah", "kalimat_matematika", "ada"),)),
        Bab(3, "Pengukuran panjang dan berat",
            ("Satuan baku panjang (cm, m)", "Satuan baku berat (g, kg)"),
            (("pengukuran", "konversi", "sebagian"),)),
        Bab(4, "Unsur bangun datar",
            ("Sisi dan sudut", "Garis tegak lurus dan sejajar", "Simetri"),
            (("geometri-datar", "simetri", "sebagian"),
             ("geometri-datar", "keliling_luas", "sebagian"))),
        Bab(5, "Penyajian data dalam tabel",
            ("Tabel turus", "Piktogram", "Diagram batang sederhana"),
            (("statistika", "turus", "sebagian"),
             ("statistika", "piktogram", "sebagian"),
             ("statistika", "diagram", "sebagian"))),
    )),
    Kelas(4, (
        Bab(1, "Bilangan sampai 10.000, operasi hitung, faktor dan kelipatan",
            ("Nilai tempat ribuan", "Penjumlahan dan pengurangan sampai 1.000",
             "Perkalian dan pembagian sampai 100", "Faktor dan kelipatan"),
            (("berhitung-sekolah", "nilai_tempat_besar", "ada"),
             ("bilangan-sekolah", "nilai_tempat_besar", "ada"),
             ("bilangan-sekolah", "tambah_kurang_bersusun", "ada"),
             ("berhitung-sekolah", "perkalian_dasar", "ada"),
             ("berhitung-sekolah", "pembagian_dasar", "ada"),
             ("teori-bilangan", "keterbagian", "sebagian"),
             ("teori-bilangan", "kelipatan_rentang", "sebagian"))),
        Bab(2, "Pecahan",
            ("Pecahan berpembilang satu", "Pecahan senilai", "Pecahan, desimal, dan persen"),
            (("berhitung-sekolah", "pecahan_sederhana", "sebagian"),
             ("aritmetika-dasar", "urut_bilangan", "sebagian"))),
        Bab(3, "Pola gambar dan pola bilangan",
            ("Pola bilangan membesar dan mengecil", "Pola gambar"),
            (("pola-bilangan", "aritmetika", "ada"),
             ("pola-bilangan", "korek", "ada"),
             ("pola-bilangan", "titik", "ada"))),
        Bab(4, "Pengukuran luas dan volume",
            ("Luas dengan petak satuan", "Volume dengan kubus satuan"),
            (("geometri-datar", "kotak", "sebagian"),
             ("geometri-datar", "keliling_luas", "sebagian"),
             ("pengukuran", "luas_volume", "sebagian"))),
        Bab(5, "Bangun datar",
            ("Ciri-ciri bangun datar", "Menyusun dan mengurai bangun datar"),
            (("geometri-datar", "sudut", "sebagian"),
             ("geometri-datar", "segitiga", "sebagian"))),
        Bab(6, "Piktogram dan diagram batang",
            ("Membaca piktogram", "Membaca diagram batang"),
            (("statistika", "piktogram", "sebagian"),
             ("statistika", "diagram", "sebagian"))),
    )),
    Kelas(5, (
        Bab(1, "Bilangan cacah sampai 100.000 dan operasi hitung",
            ("Operasi hitung campuran", "Penjumlahan dan pengurangan bersusun",
             "Perkalian dan pembagian bilangan besar"),
            (("bilangan-sekolah", "tambah_kurang_bersusun", "ada"),
             ("bilangan-sekolah", "kali_bagi_sekolah", "ada"),
             ("aritmetika-dasar", "operasi", "sebagian"))),
        Bab(2, "KPK dan FPB",
            ("Faktor dan faktorisasi prima", "Kelipatan Persekutuan Terkecil", "Faktor Persekutuan Terbesar"),
            (("teori-bilangan", "kpk", "ada"),
             ("aritmetika-dasar", "fpb", "ada"),
             ("teori-bilangan", "prima", "ada"),
             ("teori-bilangan", "fpb_kpk", "ada"))),
        Bab(3, "Pecahan",
            ("Membandingkan dan mengurutkan pecahan", "Penjumlahan dan pengurangan pecahan"),
            (("aritmetika-dasar", "pecahan_campuran", "ada"),
             ("aritmetika-dasar", "urut_bilangan", "ada"))),
        Bab(4, "Keliling bangun datar",
            ("Keliling bangun datar", "Keliling bangun gabungan"),
            (("geometri-datar", "keliling_luas", "sebagian"),
             ("geometri-datar", "arsiran", "sebagian"))),
        Bab(5, "Luas bangun datar",
            ("Luas segitiga dan jajargenjang", "Luas trapesium dan layang-layang", "Luas bangun gabungan"),
            (("geometri-datar", "segitiga", "ada"),
             ("geometri-datar", "segiempat", "ada"),
             ("geometri-datar", "arsiran", "ada"))),
        Bab(6, "Sudut",
            ("Mengukur sudut", "Membandingkan sudut", "Hubungan sudut"),
            (("geometri-datar", "sudut", "sebagian"),)),
        Bab(7, "Membandingkan ciri bangun datar",
            ("Sifat-sifat segiempat dan segitiga",),
            ()),
        Bab(8, "Pengumpulan dan penyajian data",
            ("Piktogram dan diagram batang", "Rata-rata, median, modus"),
            (("statistika", "diagram", "sebagian"),
             ("statistika", "rata", "sebagian"),
             ("statistika", "median_modus", "sebagian"))),
        Bab(9, "Bilangan cacah sampai 1.000.000",
            ("Nilai tempat ratusan ribu", "Membandingkan dan mengurutkan bilangan besar"),
            (("bilangan-sekolah", "nilai_tempat_besar", "ada"),
             ("bilangan-sekolah", "urutkan_bilangan", "ada"))),
    )),
    Kelas(6, (
        Bab(1, "Pecahan dan desimal",
            ("Perkalian dan pembagian pecahan dengan bilangan asli", "Mengubah pecahan ke desimal"),
            (("aritmetika-dasar", "pecahan_kali_bagi", "sebagian"),
             ("aritmetika-dasar", "urut_bilangan", "sebagian"))),
        Bab(2, "Rasio",
            ("Rasio satuan", "Kesamaan rasio", "Skala dan perbandingan"),
            (("aritmatika-lanjut", "senilai", "ada"),
             ("aritmatika-lanjut", "berbalik", "ada"),
             ("pengukuran", "skala", "ada"))),
        Bab(3, "Kubus dan balok",
            ("Jaring-jaring", "Volume kubus dan balok", "Tampak depan, atas, samping"),
            (("geometri-ruang", "jaring", "sebagian"),
             ("geometri-ruang", "volume_balok", "sebagian"),
             ("geometri-ruang", "dicat", "sebagian"))),
        Bab(4, "Peluang",
            ("Kejadian lebih mungkin dan kurang mungkin",),
            ()),
    )),
)


def status_bab(bab: Bab) -> str:
    """'ada' bila ada pelatih 'ada', 'sebagian' bila hanya sebagian, 'belum' bila tanpa pelatih."""
    if any(k == "ada" for _t, _g, k in bab.pelatih):
        return "ada"
    return "sebagian" if bab.pelatih else "belum"


def grup_terpakai() -> frozenset:
    """Semua (topik_id, kode grup) yang ditunjuk bab mana pun."""
    return frozenset((t, g) for k in KELAS for b in k.bab for t, g, _c in b.pelatih)
