"""Nama tampilan tipe soal, bukan judul kartu konsep atau ID penyimpanan.

Satu kartu konsep dapat membantu beberapa tipe soal. Ringkasan generate dan
pilihan latihan ulang harus memakai nama tipe yang sama, bukan judul kartu
umum yang dapat menyamarkan perbedaan variasi soal.
"""

NAMA_TIPE_SOAL = {
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
