"""Saran "Yang bisa dilakukan di rumah" untuk laporan Peta Kemampuan versi 2 (F4): templat tetap, tanpa AI.

Pilihan deterministik: materi `perlu_dilatih` (urutan laporan) yang punya templat, lalu satu saran umum bila ada soal
dilewati. Maksimal `MAKS_SARAN`; saran umum selalu mendapat satu slot bila `dilewati > 0`. Kunci `SARAN_PER_MATERI`
adalah label awam bawaan (`kurikulum_katalog.label_awam()`). Materi dengan label admin yang diubah tidak punya templat
dan tidak diberi saran. Semua teks templat ada di `DAFTAR_TEKS_TEMPLAT`. Tanpa klaim hasil atau jaminan, tanpa kata Guru.
"""
from __future__ import annotations

MAKS_SARAN = 3

SARAN_PER_MATERI = {
    "Pola bilangan": "Ajak anak membuat pola dari biji, kancing, atau kerikil, lalu minta ia menjelaskan bentuk berikutnya.",
    "Statistika": "Ajak anak mencatat hal sederhana di rumah, misalnya buah kesukaan keluarga, lalu menghitung jumlah tiap jenisnya.",
    "Geometri datar": "Ajak anak mencari persegi, segitiga, dan persegi panjang di sekitar rumah, lalu menyebut jumlah sisinya.",
    "Bilangan dasar": "Main jual-beli dengan uang mainan, lalu minta anak menyusun nilai uang yang dipakai.",
    "Berhitung": "Ajak anak menghitung benda di rumah, misalnya sendok atau buah, lalu minta ia menjelaskan cara menghitungnya.",
    "Pengukuran": "Ajak anak mengukur buku atau meja dengan penggaris, lalu minta ia menyebut satuannya dan mengubahnya, misalnya cm ke m.",
    "Aritmetika dasar": "Ajak anak menjumlahkan dan mengurangkan dengan benda nyata, misalnya kelereng, lalu minta ia menceritakan langkahnya.",
    "Aritmetika lanjut": "Ajak anak membuat soal cerita dari kejadian sehari-hari, lalu minta ia menceritakan langkah penyelesaiannya.",
}
SARAN_DILEWATI = "Ajak anak kembali ke soal yang tadi dilewati, lalu biarkan ia mencoba meski belum yakin jawabannya."
DAFTAR_TEKS_TEMPLAT = (*SARAN_PER_MATERI.values(), SARAN_DILEWATI)


def pilih_saran(perlu_dilatih, dilewati: int) -> list:
    """Saran teks (maks `MAKS_SARAN`) dari materi perlu dilatih yang punya templat, lalu saran dilewati bila ada.

    Slot saran dilewati disisakan lebih dulu, jadi materi mendapat `MAKS_SARAN - 1` slot saat ada soal dilewati.
    """
    ada_dilewati = dilewati > 0
    sisa_slot = MAKS_SARAN - (1 if ada_dilewati else 0)
    materi = [SARAN_PER_MATERI[nama] for nama in perlu_dilatih if nama in SARAN_PER_MATERI][:sisa_slot]
    return materi + ([SARAN_DILEWATI] if ada_dilewati else [])
