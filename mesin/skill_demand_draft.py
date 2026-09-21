"""Rubrik pilot untuk audit, BUKAN kebijakan kemampuan atau katalog aktif.

Tidak dipanggil penulis sesi/reducer. ID mendeskripsikan tugas, bukan P3–P6.
Pemetaan hanya mengelompokkan contoh sintetis; tidak menyetarakan bukti antarprofil
atau representasi. Aktivasi memerlukan keputusan pedagogis dan integrasi terpisah.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

VERSI_RUBRIK = "pilot-keliling-luas-draft-v1"
POLA_PILOT = "keliling_luas_datar"


@dataclass(frozen=True)
class DeskriptorTuntutan:
    id: str
    nama: str
    varian: str
    penalaran: str
    prasyarat_usulan: Tuple[str, ...]
    cek_penjelasan: Tuple[str, ...]
    batas_intervensi: str


DESKRIPTOR = (
    DeskriptorTuntutan(
        "persegi-panjang.keliling-langsung.v1",
        "Menentukan keliling dari panjang dan lebar", "keliling",
        "Menghubungkan empat sisi dengan dua pasang sisi sama panjang.",
        ("Penjumlahan panjang", "Makna keliling dan satuan panjang"),
        ("Mengapa panjang dan lebar dijumlahkan lalu dikali dua?",
         "Mengapa bukan panjang dikali lebar?"),
        "Kartu keliling/luas memiliki contoh langsung; kecocokan tiap malrule tetap perlu ditinjau.",
    ),
    DeskriptorTuntutan(
        "persegi-panjang.luas-dari-keliling.v1",
        "Menentukan luas dari keliling dan satu sisi", "balik_luas",
        "Membalik hubungan keliling untuk mencari sisi yang hilang, lalu menghitung luas.",
        ("Hubungan keliling dengan pasangan sisi", "Operasi balik penjumlahan",
         "Makna luas sebagai hasil kali panjang dan lebar"),
        ("Mengapa keliling dibagi dua sebelum mengurangi panjang?",
         "Apa arti hasil pengurangan itu?",
         "Mengapa perlu perkalian lagi dan memakai satuan persegi?"),
        "Kartu existing hanya mencontohkan tugas langsung; contoh balik spesifik belum tersedia.",
    ),
)


def deskriptor(tuntutan_id: str, versi: str = VERSI_RUBRIK) -> DeskriptorTuntutan:
    """ID/versi asing gagal terlihat, bukan ditafsir sebagai tahap termudah."""
    if versi != VERSI_RUBRIK:
        raise ValueError("versi rubrik draft tidak dikenal")
    for tuntutan in DESKRIPTOR:
        if tuntutan.id == tuntutan_id:
            return tuntutan
    raise ValueError("tuntutan draft tidak dikenal")


def petakan_draft(template_id: str, parameter, mode_representasi: str,
                  *, versi: str = VERSI_RUBRIK) -> Optional[DeskriptorTuntutan]:
    """Klasifikasikan bentuk tugas nyata tanpa kelas, profil, nilai, atau data anak.

    Pola di luar pilot menghasilkan None. Bentuk pilot rusak/asing ditolak;
    tidak memakai cabang else template warisan untuk menebak tugas balik.
    """
    if versi != VERSI_RUBRIK:
        raise ValueError("versi rubrik draft tidak dikenal")
    if template_id != POLA_PILOT:
        return None
    if mode_representasi not in ("teks-v1", "geometri_datar-v1"):
        raise ValueError("representasi pilot belum direview")
    if type(parameter) is not dict:
        raise ValueError("parameter pilot wajib objek")
    varian = parameter.get("varian")
    tuntutan = next((t for t in DESKRIPTOR if t.varian == varian), None)
    if tuntutan is None:
        raise ValueError("varian pilot tidak dikenal")
    angka = ("p", "l") if varian == "keliling" else ("p", "K")
    if set(parameter) != {"varian", *angka}:
        raise ValueError("field parameter pilot tidak tepat")
    if any(type(parameter[k]) is not int or parameter[k] <= 0 for k in angka):
        raise ValueError("ukuran pilot wajib bilangan bulat positif")
    if varian == "balik_luas" and (parameter["K"] % 2 or parameter["K"] // 2 <= parameter["p"]):
        raise ValueError("keliling tidak menghasilkan lebar bulat positif")
    return tuntutan
