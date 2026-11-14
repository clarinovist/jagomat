"""Paket berhitung dasar sekolah untuk Kelas 3–4 (P3 dan P4).

Menutup celah kurikulum antara bilangan-dasar (P1–P2) dan paket OSN/aritmetika
lanjut (P5–P6): perkalian dasar, pembagian dasar, pecahan sederhana, dan
nilai tempat ratusan/ribuan beserta miskonsepsi khas kelas 3–4.
"""

from __future__ import annotations

import math
import random

from templates import Malrule, Soal, putar, saring_malrule
from topics import Topik, daftarkan


_BENDA_KALI = (
    ("kotak pensil", "pensil"),
    ("dus buku", "buku"),
    ("kantong kelereng", "kelereng"),
    ("keranjang jeruk", "jeruk"),
)

_NAMA_ANAK = ("Rafi", "Nadia", "Bimo", "Sinta")

_POSISI_ANGKA = (
    ("satuan", 1),
    ("puluhan", 10),
    ("ratusan", 100),
    ("ribuan", 1000),
)


def perkalian_dasar(a: int, b: int, varian: str = "hitung") -> Soal:
    """Perkalian 2 digit dengan 1–2 digit; menangkap salah tambah dan lupa simpan."""
    hasil = a * b
    if varian == "cerita":
        wadah, isi = putar(_BENDA_KALI, a, b)
        teks = f"Ada {b} {wadah}. Setiap wadah berisi {a} {isi}. Berapa jumlah semua {isi}?"
    else:
        teks = f"Hitung: {a} × {b}"

    satuan_a = a % 10
    puluhan_a = a // 10
    mal: list[Malrule] = [
        Malrule("perkalian.dijumlahkan", str(a + b), "K", "menjumlahkan bilangan bukannya mengalikan"),
    ]
    if b < 10 and satuan_a * b >= 10:
        lupa_simpan = puluhan_a * b * 10 + (satuan_a * b) % 10
        mal.append(
            Malrule(
                "perkalian.lupa_simpan",
                str(lupa_simpan),
                "K",
                "lupa menambahkan simpanan puluhan saat mengalikan bersusun",
            )
        )
    elif b >= 10:
        lupa_geser = (b % 10) * a + (b // 10) * a
        mal.append(
            Malrule(
                "perkalian.lupa_geser_puluhan",
                str(lupa_geser),
                "K",
                "lupa menggeser nilai puluhan pengali ke kiri satu tempat",
            )
        )
    else:
        mal.append(
            Malrule(
                "perkalian.salah_puluhan",
                str(puluhan_a * 10 + satuan_a * b),
                "K",
                "hanya mengalikan angka satuan tanpa mengalikan puluhannya",
            )
        )
    mal.append(
        Malrule(
            "perkalian.meleset_satu_kelompok",
            str(hasil - a),
            "H",
            "strategi perkalian tepat, meleset satu kelompok pengali",
        )
    )
    return Soal(
        "perkalian_dasar",
        {"a": a, "b": b, "varian": varian},
        teks,
        str(hasil),
        saring_malrule(str(hasil), mal),
        pembahasan=(
            f"Kalikan satuannya dulu lalu puluhannya (atau ulangi {a} sebanyak {b} kali): "
            f"{a} × {b} = {hasil}."
        ),
        bagian="A",
    )


def pembagian_dasar(hasil: int, pembagi: int, varian: str = "bagi_rata") -> Soal:
    """Pembagian bilangan 2–3 digit tanpa sisa; memisahkan salah operasi vs meleset."""
    terbagi = hasil * pembagi
    if varian == "bagi_rata":
        wadah, isi = putar(_BENDA_KALI, hasil, pembagi)
        teks = f"{terbagi} {isi} dibagikan sama rata ke {pembagi} anak. Berapa {isi} yang diterima setiap anak?"
    else:
        teks = f"Hitung: {terbagi} ÷ {pembagi}"

    mal = [
        Malrule("pembagian.dikalikan", str(terbagi * pembagi), "K", "mengalikan bilangan padahal diminta membagi rata"),
        Malrule("pembagian.dikurangi", str(terbagi - pembagi), "K", "mengurangi sekali bukannya membagi rata"),
        Malrule("pembagian.meleset_satu", str(hasil - 1), "H", "prosedur pembagian sudah tepat, hasilnya meleset satu"),
    ]
    return Soal(
        "pembagian_dasar",
        {"hasil": hasil, "pembagi": pembagi, "varian": varian},
        teks,
        str(hasil),
        saring_malrule(str(hasil), mal),
        pembahasan=(
            f"Bagi {terbagi} secara merata menjadi {pembagi} bagian sama besar: "
            f"{terbagi} ÷ {pembagi} = {hasil} (karena {hasil} × {pembagi} = {terbagi})."
        ),
        bagian="A",
    )


def pecahan_bagian_dasar(varian: str, penyebut: int, a: int, b: int) -> Soal:
    """Pecahan sederhana berpenyebut sama & sisa bagian (Kelas 3–4)."""
    if varian == "sisa_bagian":
        sisa = penyebut - a
        kunci = f"{sisa}/{penyebut}"
        nama = putar(_NAMA_ANAK, penyebut, a)
        teks = (
            f"Sebuah pita dipotong menjadi {penyebut} bagian sama panjang. "
            f"{nama} memakai {a} bagian. Berapa pecahan pita yang masih tersisa?"
        )
        mal = [
            Malrule("pecahan_dasar.ambil_bagian_terpakai", f"{a}/{penyebut}", "K", "menulis bagian yang dipakai, bukan yang tersisa"),
            Malrule("pecahan_dasar.tanpa_penyebut", str(sisa), "K", "hanya menulis banyak potong tanpa penyebut keseluruhan"),
            Malrule("pecahan_dasar.meleset_pembilang", f"{sisa - 1}/{penyebut}", "H", "memahami sisa pecahan, salah hitung pembilang satu bagian"),
        ]
        pembahasan = (
            f"Total ada {penyebut} bagian; setelah dipakai {a} bagian, "
            f"tersisa {penyebut} − {a} = {sisa} bagian dari {penyebut}, ditulis {kunci}."
        )
    elif varian == "jumlah_sama_penyebut":
        jumlah = a + b
        kunci = f"{jumlah}/{penyebut}"
        teks = f"Hitung hasil pecahan berikut (tulis a/b): {a}/{penyebut} + {b}/{penyebut}"
        mal = [
            Malrule("pecahan_dasar.jumlah_penyebut", f"{jumlah}/{penyebut * 2}", "K", "menjumlahkan penyebut juga padahal penyebutnya tetap"),
            Malrule("pecahan_dasar.kurang_bukan_tambah", f"{abs(a - b)}/{penyebut}", "K", "mengurangkan pembilang padahal tandanya tambah"),
            Malrule("pecahan_dasar.meleset_pembilang", f"{jumlah - 1}/{penyebut}", "H", "penyebut sudah benar tetap, pembilang meleset satu"),
        ]
        pembahasan = (
            f"Karena penyebut sudah sama ({penyebut}), cukup jumlahkan pembilangnya: "
            f"({a} + {b})/{penyebut} = {kunci}."
        )
    else:  # selisih_sama_penyebut
        selisih = a - b
        kunci = f"{selisih}/{penyebut}"
        teks = f"Hitung hasil pecahan berikut (tulis a/b): {a}/{penyebut} − {b}/{penyebut}"
        mal = [
            Malrule("pecahan_dasar.tambah_bukan_kurang", f"{a + b}/{penyebut}", "K", "menjumlahkan pembilang padahal tandanya kurang"),
            Malrule("pecahan_dasar.tanpa_penyebut", str(selisih), "K", "menulis selisih pembilang saja tanpa penyebut"),
            Malrule("pecahan_dasar.meleset_pembilang", f"{selisih + 1}/{penyebut}", "H", "penyebut sudah benar tetap, pembilang meleset satu"),
        ]
        pembahasan = (
            f"Karena penyebut sudah sama ({penyebut}), kurangkan pembilangnya saja: "
            f"({a} − {b})/{penyebut} = {kunci}."
        )
    return Soal(
        "pecahan_bagian_dasar",
        {"varian": varian, "penyebut": penyebut, "a": a, "b": b},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        pembahasan=pembahasan,
        bagian="B",
    )


def nilai_tempat_ribuan(varian: str, angka: int, posisi_idx: int) -> Soal:
    """Nilai tempat ratusan/ribuan dan selisih nilai dua posisi."""
    nama_pos, faktor = _POSISI_ANGKA[posisi_idx]
    digit = (angka // faktor) % 10
    if varian == "nilai_angka":
        nilai = digit * faktor
        kunci = str(nilai)
        teks = f"Pada bilangan {angka}, berapa nilai angka yang menempati posisi {nama_pos}?"
        faktor_salah = faktor // 10 if faktor >= 100 else faktor * 10
        tetangga_faktor = faktor // 10 if posisi_idx > 1 else faktor * 10
        digit_tetangga = (angka // tetangga_faktor) % 10
        mal = [
            Malrule("nilai_tempat.digit_saja", str(digit), "K", "menyebut digitnya saja tanpa nilai tempatnya"),
            Malrule("nilai_tempat.salah_tingkat", str(digit * faktor_salah), "K", "keliru satu tingkat nilai tempat (nol kurang atau berlebih)"),
            Malrule("nilai_tempat.tertukar_posisi", str(digit_tetangga * faktor), "H", "mengambil angka di posisi sebelahnya"),
        ]
        pembahasan = (
            f"Digit pada tempat {nama_pos} adalah {digit}, sehingga nilainya "
            f"{digit} × {faktor} = {kunci}."
        )
    else:  # selisih_nilai
        nama_kecil, faktor_kecil = _POSISI_ANGKA[1]  # puluhan
        digit_kecil = (angka // faktor_kecil) % 10
        nilai_besar = digit * faktor
        nilai_kecil = digit_kecil * faktor_kecil
        kunci = str(nilai_besar - nilai_kecil)
        teks = (
            f"Pada bilangan {angka}, berapa selisih nilai angka {nama_pos} "
            f"dan nilai angka {nama_kecil}?"
        )
        mal = [
            Malrule("nilai_tempat.selisih_digit", str(abs(digit - digit_kecil)), "K", "mengurangkan digitnya saja tanpa nilai tempat"),
            Malrule("nilai_tempat.jumlah_nilai", str(nilai_besar + nilai_kecil), "K", "menjumlahkan kedua nilai padahal ditanya selisih"),
            Malrule("nilai_tempat.selisih_meleset_sepuluh", str(nilai_besar - nilai_kecil - 10), "H", "konsep nilai tempat tepat, salah kurang satu puluhan"),
        ]
        pembahasan = (
            f"Nilai {nama_pos} adalah {nilai_besar} dan nilai {nama_kecil} adalah {nilai_kecil}, "
            f"jadi selisihnya {nilai_besar} − {nilai_kecil} = {kunci}."
        )
    return Soal(
        "nilai_tempat_ribuan",
        {"varian": varian, "angka": angka, "posisi_idx": posisi_idx},
        teks,
        kunci,
        saring_malrule(kunci, mal),
        minta_restatement=(varian == "selisih_nilai"),
        pembahasan=pembahasan,
        bagian="C",
    )


def _parameter(template_id: str, rng: random.Random, level: str) -> dict:
    if template_id == "perkalian_dasar":
        varian = rng.choice(("hitung", "cerita"))
        while True:
            if level == "P3":
                a = rng.randint(12, 49)
                b = rng.randint(3, 9)
            else:
                a = rng.randint(14, 89)
                b = rng.randint(4, 15)
            if a % 10 == 0 or b == 10:
                continue
            s = perkalian_dasar(a, b, varian)
            if len([m for m in s.malrule if m.kode == "K"]) >= 2 and any(m.kode == "H" for m in s.malrule):
                return {"a": a, "b": b, "varian": varian}

    if template_id == "pembagian_dasar":
        varian = rng.choice(("bagi_rata", "operasi"))
        while True:
            if level == "P3":
                pembagi = rng.randint(3, 9)
                hasil = rng.randint(12, 39)
            else:
                pembagi = rng.randint(4, 12)
                hasil = rng.randint(14, 68)
            if hasil % 10 == 0 or pembagi == hasil:
                continue
            s = pembagian_dasar(hasil, pembagi, varian)
            if len([m for m in s.malrule if m.kode == "K"]) >= 2 and any(m.kode == "H" for m in s.malrule):
                return {"hasil": hasil, "pembagi": pembagi, "varian": varian}

    if template_id == "pecahan_bagian_dasar":
        varian = rng.choice(("sisa_bagian", "jumlah_sama_penyebut", "selisih_sama_penyebut"))
        penyebut_pool = tuple(range(5, 17)) if level == "P3" else tuple(range(6, 21))
        while True:
            penyebut = rng.choice(penyebut_pool)
            if varian == "sisa_bagian":
                a = rng.randint(1, penyebut - 3)
                b = 0
                kunci_num = penyebut - a
            elif varian == "jumlah_sama_penyebut":
                a = rng.randint(1, penyebut - 2)
                b = rng.randint(1, penyebut - a - 1)
                if abs(a - b) == 0:
                    continue
                kunci_num = a + b
            else:
                a = rng.randint(3, penyebut - 1)
                b = rng.randint(1, a - 2)
                if a + b >= penyebut:
                    continue
                kunci_num = a - b
            if math.gcd(kunci_num, penyebut) != 1:
                continue
            s = pecahan_bagian_dasar(varian, penyebut, a, b)
            if len([m for m in s.malrule if m.kode == "K"]) >= 2 and any(m.kode == "H" for m in s.malrule):
                return {"varian": varian, "penyebut": penyebut, "a": a, "b": b}

    if template_id == "nilai_tempat_ribuan":
        varian = rng.choice(("nilai_angka", "selisih_nilai"))
        while True:
            if level == "P3":
                digits = rng.sample(range(1, 10), 3)
                angka = digits[0] * 100 + digits[1] * 10 + digits[2]
                posisi_idx = 2  # ratusan
            else:
                digits = rng.sample(range(1, 10), 4)
                angka = digits[0] * 1000 + digits[1] * 100 + digits[2] * 10 + digits[3]
                posisi_idx = rng.choice((2, 3))  # ratusan atau ribuan
            s = nilai_tempat_ribuan(varian, angka, posisi_idx)
            if len([m for m in s.malrule if m.kode == "K"]) >= 2 and any(m.kode == "H" for m in s.malrule):
                return {"varian": varian, "angka": angka, "posisi_idx": posisi_idx}

    raise KeyError(f"template tidak dikenal: {template_id}")


REGISTRI_TOPIK = {
    "perkalian_dasar": perkalian_dasar,
    "pembagian_dasar": pembagian_dasar,
    "pecahan_bagian_dasar": pecahan_bagian_dasar,
    "nilai_tempat_ribuan": nilai_tempat_ribuan,
}

KOMPOSISI = {
    "P3": (
        "perkalian_dasar",
        "pembagian_dasar",
        "pecahan_bagian_dasar",
        "nilai_tempat_ribuan",
        "perkalian_dasar",
        "pembagian_dasar",
        "pecahan_bagian_dasar",
        "nilai_tempat_ribuan",
    ),
    "P4": (
        "perkalian_dasar",
        "pembagian_dasar",
        "pecahan_bagian_dasar",
        "nilai_tempat_ribuan",
        "perkalian_dasar",
        "pembagian_dasar",
        "pecahan_bagian_dasar",
        "nilai_tempat_ribuan",
    ),
}

TOPIK = Topik(
    id="berhitung-sekolah",
    nama="Berhitung Dasar Sekolah",
    judul_lembar="Latihan Berhitung Dasar Sekolah (Kelas 3–4)",
    judul_penilaian="Penilaian — Berhitung Dasar Sekolah",
    templates=REGISTRI_TOPIK,
    komposisi=KOMPOSISI,
    profil={"P3": {}, "P4": {}},
    judul_bagian={
        "A": "Bagian A — Perkalian dan pembagian dasar",
        "B": "Bagian B — Pecahan sederhana",
        "C": "Bagian C — Nilai tempat ratusan dan ribuan",
    },
    catatan_bagian={
        "A": "Gunakan kertas coretan untuk perkalian/pembagian bersusun.",
        "B": "Tulis pecahan sebagai pembilang/penyebut (contoh: 3/8).",
        "C": "Perhatikan perbedaan antara angka (digit) dan nilai tempatnya.",
    },
    parameter_untuk=_parameter,
)

daftarkan(TOPIK)
