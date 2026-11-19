"""Data CONTOH sintetis laporan Peta Kemampuan (Aisyah, kelas 4).

Bukan anak sungguhan. Angkanya saling cocok dan diperiksa `periksa_konsisten`:
30 soal, 22 benar, 8 salah, skor 73 ("Cukup baik"); 8 salah = 4 + 2 + 1 + 1 pola.
Posisi tidak ditulis tangan: daftar 214 skor pembanding sintetis dibangun
deterministik dari sebaran per sepuluh, lalu `peta_posisi.hitung_posisi` yang
menghitung persentil dan peringkat. Daftar itu memuat skor Aisyah sendiri.
"""
from __future__ import annotations

from datetime import date

from peta_data import (
    Bagian, ContohSoal, Guru, LaporanPeta, Langkah, Lencana, Materi, Misi, Pilihan,
    Pola, Resep, Susun, Tantangan, Temuan, periksa_konsisten,
)

__all__ = ["DATA_CONTOH", "SEBARAN_PEMBANDING_CONTOH", "bangun_pembanding_contoh", "periksa_konsisten"]

# Banyak anak sintetis per kelompok skor 0-9, 10-19, ..., 90-100 (total 214).
SEBARAN_PEMBANDING_CONTOH = (3, 6, 11, 18, 26, 32, 36, 38, 30, 14)
LEBAR_KELOMPOK = 10


def bangun_pembanding_contoh() -> tuple:
    """214 skor sintetis deterministik: tiap kelompok disebar rata di rentangnya."""
    skor = []
    terakhir = len(SEBARAN_PEMBANDING_CONTOH) - 1
    for indeks, jumlah in enumerate(SEBARAN_PEMBANDING_CONTOH):
        bawah = indeks * LEBAR_KELOMPOK
        lebar = LEBAR_KELOMPOK + (1 if indeks == terakhir else 0)
        skor.extend(bawah + (urutan * lebar) // jumlah for urutan in range(jumlah))
    return tuple(skor)


_MATERI = (
    Materi(
        kunci="penjumlahan", nama="Penjumlahan dan pengurangan", soal=8, benar=7,
        ringkas="Bersusun dengan meminjam sudah lancar. Satu soal salah karena angka simpanan lupa ditambahkan.",
        yang_dilatih="Hitungannya benar. Yang terlewat: angka simpanan di kolom satuan tidak ditambahkan ke kolom puluhan.",
        latihan="Dua soal penjumlahan bersusun yang berpindah puluhan, diselipkan di antara soal lain. Tulis simpanan kecil di atas kolom.",
        contoh=ContohSoal(
            soal="58 + 27 = …", jawaban_anak="75", jawaban_benar="85",
            langkah=(
                Langkah("8 + 7 = 15, tulis 5, simpan 1."),
                Langkah("5 + 2 = 7, langsung ditulis 7.", True, "Di sini salahnya: simpanan 1 belum ditambahkan (5 + 2 + 1 = 8)."),
                Langkah("Hasil ditulis 75."),
            ),
        ),
    ),
    Materi(
        kunci="perkalian", nama="Perkalian", soal=6, benar=3,
        ringkas="Perkalian satu angka lancar. Di perkalian bersusun, angka simpanan sering lupa ditambahkan.",
        yang_dilatih="Perkaliannya sudah benar. Angka simpanan tidak ditambahkan di kolom puluhan.",
        latihan="Lima soal perkalian bersusun. Minta Aisyah menulis angka simpanan kecil di atas kolom puluhan, lalu mencoretnya setelah ditambahkan.",
        contoh=ContohSoal(
            soal="47 × 6 = …", jawaban_anak="242", jawaban_benar="282",
            langkah=(
                Langkah("7 × 6 = 42, tulis 2, simpan 4."),
                Langkah("4 × 6 = 24, langsung ditulis 24.", True, "Di sini salahnya: simpanan 4 belum ditambahkan (24 + 4 = 28)."),
                Langkah("Hasil ditulis 242."),
            ),
            visual=Susun(atas=47, bawah=6, simpanan=4, hasil_anak=242),
        ),
    ),
    Materi(
        kunci="pembagian", nama="Pembagian", soal=6, benar=5,
        ringkas="Pembagian sudah kuat. Satu soal salah karena sisa tidak ditulis.",
        yang_dilatih="Hasil baginya benar. Yang terlewat hanya menuliskan sisa pembagian.",
        latihan="Tiga soal pembagian bersisa. Setelah dicek balik dengan perkalian, tanya: \"Masih ada sisa?\"",
        contoh=ContohSoal(
            soal="47 : 5 = …", jawaban_anak="9", jawaban_benar="9 sisa 2",
            langkah=(
                Langkah("5 × 9 = 45, hasil bagi 9."),
                Langkah("47 − 45 = 2, sisa tidak ditulis.", True, "Di sini salahnya: sisa 2 terlewat, jawaban seharusnya 9 sisa 2."),
            ),
        ),
    ),
    Materi(
        kunci="pecahan", nama="Pecahan", soal=6, benar=4,
        ringkas="Pembilang sudah benar. Penyebut ikut dijumlahkan saat penyebutnya sama.",
        yang_dilatih="Arti penyebut sebagai ukuran potongan. Gambar membantu lebih dulu daripada aturan.",
        latihan="Gambar satu kotak, bagi empat, arsir 1 lalu 2 bagian lagi. Tanya: \"Sekarang berapa bagian dari empat?\"",
        contoh=ContohSoal(
            soal="1/4 + 2/4 = …", jawaban_anak="3/8", jawaban_benar="3/4",
            langkah=(
                Langkah("Pembilang: 1 + 2 = 3. Benar."),
                Langkah("Penyebut: 4 + 4 = 8.", True, "Di sini salahnya: penyebut tetap 4 karena ukuran potongannya sama."),
            ),
            visual=Bagian(terisi=3, total=4),
        ),
    ),
    Materi(
        kunci="soal-cerita", nama="Soal cerita", soal=4, benar=3,
        ringkas="Sebagian besar soal cerita benar. Satu soal salah di langkah memilih operasi.",
        yang_dilatih="Hitungan Aisyah sudah benar. Yang tertinggal: mengubah kalimat menjadi operasi, terutama kata \"setiap\" dan \"masing-masing\".",
        latihan="Baca soal pelan-pelan, lalu gambar dulu (3 kotak, isi 12) sebelum menulis angka. Cukup tanya: \"Ini ditambah, dikali, atau dikurang?\"",
        contoh=ContohSoal(
            soal="Ibu membeli 3 kotak kue. Setiap kotak berisi 12 kue. Sebanyak 8 kue dimakan. Berapa kue yang tersisa?",
            jawaban_anak="7", jawaban_benar="28",
            langkah=(
                Langkah("Menemukan angka 3, 12, dan 8."),
                Langkah("Menulis 3 + 12 − 8.", True, "Di sini salahnya: \"setiap kotak berisi\" berarti perkalian, 3 × 12."),
                Langkah("Menghitung 15 − 8 = 7. Hitungannya benar."),
            ),
        ),
    ),
)

_POLA = (
    Pola(
        kunci="p1", nama="Lupa angka simpanan", sebaran=(("perkalian", 3), ("penjumlahan", 1)),
        asal="Perkalian, penjumlahan", contoh="47 × 6 ditulis 242, seharusnya 282.",
        penjelasan="Hitungannya benar, tetapi angka simpanan tidak ditambahkan ke kolom berikutnya. Paling sering muncul di perkalian bersusun.",
        simbol="×", materi_tujuan="perkalian",
    ),
    Pola(
        kunci="p2", nama="Penyebut ikut dijumlahkan", sebaran=(("pecahan", 2),),
        asal="Pecahan", contoh="1/4 + 2/4 ditulis 3/8, seharusnya 3/4.",
        penjelasan="Arti penyebut sebagai ukuran potongan perlu dibangun dengan gambar lebih dulu.",
        simbol="½", materi_tujuan="pecahan",
    ),
    Pola(
        kunci="p3", nama="Sisa pembagian terlewat", sebaran=(("pembagian", 1),),
        asal="Pembagian", contoh="47 : 5 ditulis 9, seharusnya 9 sisa 2.",
        penjelasan="Hasil baginya benar; sisa belum dibiasakan untuk ditulis.",
        simbol="÷", materi_tujuan="pembagian",
    ),
    Pola(
        kunci="p4", nama="Salah pilih operasi di soal cerita", sebaran=(("soal-cerita", 1),),
        asal="Soal cerita", contoh="3 kotak isi 12, dimakan 8, ditulis 3 + 12 − 8.",
        penjelasan="Hitungannya benar; langkah yang perlu dilatih adalah memilih operasi dari kalimat soal.",
        simbol="?", materi_tujuan="soal-cerita",
    ),
)

_MISI = (
    Misi(
        materi_kunci="perkalian", pola_kunci="p1", judul="Perkalian bersusun: membawa simpanan",
        catatan="Langkah kecil, cepat dibereskan.",
        langkah=(
            "Tulis angka simpanan kecil di atas kolom, coret setelah ditambahkan.",
            "Mulai dari soal dua angka, lalu naik ke tiga angka.",
        ),
        minggu="Perkalian bersusun dengan simpanan",
    ),
    Misi(
        materi_kunci="pecahan", pola_kunci="p2", judul="Pecahan: arti penyebut",
        catatan="Mulai dari gambar, bukan aturan.",
        langkah=(
            "Pakai kertas atau roti yang dipotong sama besar.",
            "Tanya \"berapa bagian dari berapa?\" sebelum menulis angka.",
        ),
        minggu="Pecahan berpenyebut sama, dengan gambar",
    ),
    Misi(
        materi_kunci="soal-cerita", pola_kunci="p4", judul="Soal cerita: pilih operasi dari kalimat",
        catatan="Gambar dulu, hitung belakangan.",
        langkah=(
            "Gambar dulu, hitung belakangan.",
            "Cari kata kunci: \"setiap\", \"masing-masing\", \"sisa\", \"dibagi rata\".",
        ),
        minggu="Soal cerita: gambar dulu, pilih operasi",
    ),
)

DATA_CONTOH = LaporanPeta(
    nama_anak="Aisyah", kelas=4,
    tanggal_cek=date(2026, 11, 1), tanggal_terbit=date(2026, 11, 19),
    jumlah_soal=30, jumlah_benar=22,
    materi=_MATERI, pola=_POLA,
    temuan=(
        Temuan("p1", "Perkalian bersusun: angka simpanan lupa ditambahkan."),
        Temuan("p2", "Pecahan: penyebut ikut dijumlahkan."),
        Temuan("p3", "Pembagian: sisa tidak ditulis."),
    ),
    misi=_MISI,
    guru=Guru("Bu Contoh (sintetis)", "S1 Pendidikan Matematika (contoh)", "6 tahun mengajar SD (contoh)"),
    catatan_guru=(
        "Aisyah teliti dan cepat di hitungan dasar, itu modal yang bagus. Salahnya banyak "
        "berasal dari satu kebiasaan kecil: angka simpanan belum ditambahkan. Kalau itu dibereskan, "
        "perkalian bersusun akan terasa jauh lebih ringan."
    ),
    resep=Resep(
        "10 menit sehari: perkalian bersusun",
        "Tulis angka simpanan kecil di atas kolom puluhan, lalu coret setelah ditambahkan. "
        "Beri tanda di lingkaran setiap hari yang sudah dicoba.",
    ),
    lencana=(
        Lencana("Jago Tambah-Kurang", "7 dari 8 benar", "tambah", True),
        Lencana("Langkah Rapi", "Caranya mudah dilacak", "pena", True),
        Lencana("Ahli Simpanan", "Belum didapat", "kali", False),
        Lencana("Detektif Soal Cerita", "Belum didapat", "buku", False),
    ),
    tantangan=Tantangan(
        soal="Rina punya 4 kantong. Setiap kantong berisi 5 kelereng. Berapa kelereng Rina?",
        petunjuk="Minta Aisyah memilih operasinya dulu, sebelum menghitung.",
        pilihan=(Pilihan("tambah", "4 + 5"), Pilihan("kali", "4 × 5"), Pilihan("kurang", "5 − 4")),
        benar="kali",
        umpan_benar="Tepat. \"Setiap kantong berisi 5\" berarti 4 kali 5, jadi 20 kelereng. Minta Aisyah menjelaskan kenapa memilih kali.",
        umpan_salah="Belum tepat. Coba gambar 4 kantong, isi masing-masing 5 kelereng, lalu hitung lagi.",
        kata_maskot="Hebat! Itu dia caranya: pilih operasinya dulu, baru menghitung.",
    ),
    skor_pembanding=bangun_pembanding_contoh(),
)

periksa_konsisten(DATA_CONTOH)
