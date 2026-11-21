"""Template topik Bilangan untuk Latihan Lomba, bagian kartu angka (id berawalan `bil_`).

Bagian pola dan syarat jumlah angka ada di `contest_templates_number_b`, bagian cacah di
`contest_templates_number_c`; ketiganya terdaftar saat modul ini diimpor (b lewat impor di atas).
Kunci dihitung `bangun` dari parameter; verifikator memakai cara kedua yang berdiri sendiri.
"""
from __future__ import annotations

import itertools
from typing import Dict, List, Mapping

import contest_core as C
import contest_svg_number as G
from contest_templates_number_b import soal_bilangan

TOPIK = "bilangan"
NAMA_TEMPAT = ("satuan", "puluhan", "ratusan", "ribuan")
RATUSAN_MAKS = 4
KARTU_MAKS_PER_JENIS = 9
GENAP_GANJIL_JUMLAH_KARTU = (6, 7, 8)
GENAP_GANJIL_NILAI_MAKS = 10


# --- 1. bil_kartu_nilai_tempat -----------------------------------------------------------

def _sampler_kartu_nilai_tempat(rng) -> Dict:
    ratusan = rng.choice((0, 0, 1, 2, 3, RATUSAN_MAKS))
    puluhan = rng.randint(0 if ratusan else 1, KARTU_MAKS_PER_JENIS)
    satuan = rng.randint(1, KARTU_MAKS_PER_JENIS)
    return {"ratusan": ratusan, "puluhan": puluhan, "satuan": satuan}


def _teks_kartu_nilai_tempat(ratusan: int, puluhan: int, satuan: int) -> str:
    ada = []
    if ratusan:
        ada.append("Setiap kartu 100 bernilai 100.")
    if puluhan:
        ada.append("Setiap kartu 10 bernilai 10.")
    ada.append("Setiap kartu 1 bernilai 1.")
    return " ".join(ada) + " Bilangan yang ditunjukkan kartu-kartu itu adalah ..."


def _bangun_kartu_nilai_tempat(p: Mapping) -> C.SoalLomba:
    h, t, s = p["ratusan"], p["puluhan"], p["satuan"]
    nilai = 100 * h + 10 * t + s
    kunci = str(nilai)
    kandidat = [
        C.Pengecoh(str(100 * h + 10 * s + t), "menukar banyak kartu puluhan dengan kartu satuan"),
        C.Pengecoh(str(h + t + s), "menjumlah banyak kartu tanpa memperhatikan nilai tiap kartu"),
        C.Pengecoh(f"{t}10" if t else "0",
                   "menggabungkan banyak kartu puluhan dengan tulisan 10 pada kartunya"),
        C.Pengecoh(str(100 * h + 10 * (t + s)), "menganggap kartu satuan juga bernilai 10"),
        C.Pengecoh(str(10 * t + s), "lupa menghitung kartu ratusan"),
        C.Pengecoh(str(100 * h + t + s), "menganggap kartu puluhan hanya bernilai 1"),
    ]
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    langkah: List[str] = []
    suku: List[str] = []
    for banyak, nilai_kartu in ((h, 100), (t, 10), (s, 1)):
        if banyak:
            langkah.append(f"{banyak} kartu {nilai_kartu} bernilai {banyak} x {nilai_kartu} "
                           f"= {banyak * nilai_kartu}.")
            suku.append(str(banyak * nilai_kartu))
    langkah.append(f"Jumlahkan: {' + '.join(suku)} = {kunci}. Jadi bilangannya {kunci}.")
    return soal_bilangan("bil_kartu_nilai_tempat", C.JENIS_PG, 1, _teks_kartu_nilai_tempat(h, t, s),
                 G.svg_kartu_nilai_tempat(h, t, s), kunci, pengecoh, langkah, p)


def _verifikator_kartu_nilai_tempat(p: Mapping) -> str:
    kartu = [100] * p["ratusan"] + [10] * p["puluhan"] + [1] * p["satuan"]
    total = 0
    for nilai_kartu in kartu:
        total += nilai_kartu
    return str(total)


# --- 2. bil_nilai_angka ------------------------------------------------------------------

def _sampler_nilai_angka(rng) -> Dict:
    banyak = rng.choice((3, 4))
    angka = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(banyak - 1)]
    unik = [i for i, d in enumerate(angka) if d != 0 and angka.count(d) == 1]
    if not unik:
        raise C.ParameterTidakSah("tidak ada angka bukan nol yang muncul sekali")
    return {"angka": angka, "tanya": rng.choice(unik)}


def _bangun_nilai_angka(p: Mapping) -> C.SoalLomba:
    angka, tanya = list(p["angka"]), p["tanya"]
    banyak = len(angka)
    pangkat = banyak - 1 - tanya
    d = angka[tanya]
    nilai = d * 10 ** pangkat
    kunci = str(nilai)
    kandidat = [
        C.Pengecoh(str(d), "menjawab angkanya sendiri, bukan nilai tempatnya"),
        C.Pengecoh(str(nilai // 10), "mengira angka itu berada satu tempat di sebelah kanan"),
        C.Pengecoh("".join(str(x) for x in angka[tanya:]),
                   "membaca bilangan mulai dari angka itu sampai satuan"),
        C.Pengecoh("".join(str(x) for x in angka), "menjawab seluruh bilangan"),
    ]
    if tanya > 0:
        kandidat.append(C.Pengecoh(str(angka[tanya - 1] * 10 ** (pangkat + 1)),
                                   "mengambil nilai angka di sebelah kirinya"))
    if tanya < banyak - 1:
        kandidat.append(C.Pengecoh(str(angka[tanya + 1] * 10 ** (pangkat - 1)),
                                   "mengambil nilai angka di sebelah kanannya"))
    kandidat.append(C.Pengecoh(str(nilai * 10), "menambah satu nol terlalu banyak"))
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    bilangan = "".join(str(x) for x in angka)
    langkah = (
        f"Angka {d} berada di tempat {NAMA_TEMPAT[pangkat]}.",
        f"Nilainya {d} x {10 ** pangkat} = {kunci}.",
        f"Jadi nilai angka {d} pada bilangan {bilangan} adalah {kunci}.",
    )
    teks = (f"Kartu-kartu berikut disusun dari kiri ke kanan menjadi satu bilangan. "
            f"Nilai angka {d} pada bilangan itu adalah ...")
    return soal_bilangan("bil_nilai_angka", C.JENIS_PG, 1, teks, G.svg_deret_kartu(angka), kunci,
                 pengecoh, langkah, p)


def _verifikator_nilai_angka(p: Mapping) -> str:
    angka, tanya = p["angka"], p["tanya"]
    nilai_tiap_kartu = [d * 10 ** (len(angka) - 1 - i) for i, d in enumerate(angka)]
    return str(nilai_tiap_kartu[tanya])


# --- 3. bil_genap_ganjil -----------------------------------------------------------------

def _sampler_genap_ganjil(rng) -> Dict:
    banyak = rng.choice(GENAP_GANJIL_JUMLAH_KARTU)
    kartu = rng.sample(range(1, GENAP_GANJIL_NILAI_MAKS + 1), banyak)
    return {"kartu": kartu, "jenis": rng.choice(("genap", "ganjil"))}


def _bangun_genap_ganjil(p: Mapping) -> C.SoalLomba:
    kartu, jenis = list(p["kartu"]), p["jenis"]
    genap = [v for v in kartu if v % 2 == 0]
    ganjil = [v for v in kartu if v % 2 == 1]
    cocok, lawan = (genap, ganjil) if jenis == "genap" else (ganjil, genap)
    kunci = str(len(cocok))
    arah = -1 if jenis == "genap" else 1
    kandidat = [C.Pengecoh(str(len(lawan)), f"menghitung bilangan yang bukan {jenis}"),
                C.Pengecoh(str(len(kartu)), "menjawab banyak semua kartu")]
    if GENAP_GANJIL_NILAI_MAKS in kartu:
        kandidat.append(C.Pengecoh(
            str(len(cocok) + arah),
            "salah menilai kartu 10 (bilangan dua angka dikira beda jenis)"))
    kandidat.append(C.Pengecoh(str(len(cocok) + 1), "salah hitung lebih satu"))
    kandidat.append(C.Pengecoh(str(len(cocok) - 1), "salah hitung kurang satu"))
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    daftar = ", ".join(str(v) for v in cocok)
    langkah = (
        f"Bilangan {jenis} berakhir dengan angka "
        f"{'0, 2, 4, 6, 8' if jenis == 'genap' else '1, 3, 5, 7, 9'}.",
        f"Kartu {jenis} pada gambar: {daftar}.",
        f"Banyaknya ada {kunci}. Jadi ada {kunci} kartu {jenis}.",
    )
    teks = f"Pada kartu-kartu berikut, ada berapa kartu yang bernomor bilangan {jenis}?"
    return soal_bilangan("bil_genap_ganjil", C.JENIS_PG, 1, teks, G.svg_deret_kartu(kartu), kunci,
                 pengecoh, langkah, p)


def _verifikator_genap_ganjil(p: Mapping) -> str:
    sisa_dicari = 0 if p["jenis"] == "genap" else 1
    hitung = 0
    for nomor in p["kartu"]:
        if nomor % 2 == sisa_dicari:
            hitung += 1
    return str(hitung)


# --- 9. bil_selisih_kartu ----------------------------------------------------------------

def _sampler_selisih_kartu(rng) -> Dict:
    return {"kartu": [rng.randint(0, 9) for _ in range(3)]}


def _susun_terbesar_terkecil(kartu: List[int]) -> "tuple[int, int]":
    turun = sorted(kartu, reverse=True)
    naik = sorted(kartu)
    indeks_awal = next(i for i, d in enumerate(naik) if d != 0)
    awal = naik.pop(indeks_awal)
    return int("".join(map(str, turun))), int(str(awal) + "".join(map(str, naik)))


def _bangun_selisih_kartu(p: Mapping) -> C.SoalLomba:
    kartu = list(p["kartu"])
    if max(kartu) == 0:
        raise C.ParameterTidakSah("semua kartu nol")
    terbesar, terkecil = _susun_terbesar_terkecil(kartu)
    if terbesar == terkecil:
        raise C.ParameterTidakSah("kartu hanya bisa disusun satu bilangan, selisih nol")
    kunci = str(terbesar - terkecil)
    teks = ("Tiga kartu angka disusun menjadi bilangan tiga angka, dan angka 0 tidak boleh di depan. "
            "Berapa selisih bilangan terbesar dan bilangan terkecil yang bisa disusun?")
    langkah = (
        f"Bilangan terbesar: susun dari angka terbesar, yaitu {terbesar}.",
        f"Bilangan terkecil: angka terkecil yang bukan 0 di depan, lalu sisanya "
        f"dari kecil ke besar, yaitu {terkecil}.",
        f"Selisihnya {terbesar} - {terkecil} = {kunci}. Jadi jawabannya {kunci}.",
    )
    return soal_bilangan("bil_selisih_kartu", C.JENIS_ISIAN, 2, teks, G.svg_deret_kartu(kartu), kunci,
                 (), langkah, p)


def _verifikator_selisih_kartu(p: Mapping) -> str:
    bilangan = [int("".join(map(str, susunan))) for susunan in itertools.permutations(p["kartu"])
                if susunan[0] != 0]
    return str(max(bilangan) - min(bilangan))


C.daftarkan(C.Template(id="bil_kartu_nilai_tempat", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
                       sampler=_sampler_kartu_nilai_tempat, bangun=_bangun_kartu_nilai_tempat,
                       verifikator=_verifikator_kartu_nilai_tempat))
C.daftarkan(C.Template(id="bil_nilai_angka", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
                       sampler=_sampler_nilai_angka, bangun=_bangun_nilai_angka,
                       verifikator=_verifikator_nilai_angka))
C.daftarkan(C.Template(id="bil_genap_ganjil", topik=TOPIK, jenis=C.JENIS_PG, tingkat=1,
                       sampler=_sampler_genap_ganjil, bangun=_bangun_genap_ganjil,
                       verifikator=_verifikator_genap_ganjil))
C.daftarkan(C.Template(id="bil_selisih_kartu", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=2,
                       sampler=_sampler_selisih_kartu, bangun=_bangun_selisih_kartu,
                       verifikator=_verifikator_selisih_kartu))

import contest_templates_number_c  # noqa: E402,F401  (mendaftarkan template bagian cacah)
