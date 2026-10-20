"""Empat jenis hitung murni terpilih; fungsi murni dan sampler berdomain terbatas."""
from __future__ import annotations

from math import isqrt

from templates import Malrule, Soal, saring_malrule


def _bulat(nilai, minimum):
    if type(nilai) is not int or nilai < minimum:
        raise ValueError("parameter bilangan di luar domain")


def _rentang(a, b):
    _bulat(a, 1)
    _bulat(b, a)


def _soal(tid, parameter, teks, kunci, kandidat, pembahasan, bagian):
    # Kandidat yang tidak berlaku dibuang, tidak digeser ke jawaban rekaan.
    mal = [Malrule(ident, str(nilai), kode, alasan)
           for ident, nilai, kode, alasan in kandidat if nilai >= 0]
    return Soal(tid, parameter, teks, str(kunci), saring_malrule(str(kunci), mal),
                pembahasan=pembahasan, bagian=bagian)


def banyak_kelipatan(k: int, a: int, b: int) -> Soal:
    """Cacah kelipatan pada kedua batas inklusif, termasuk rentang kosong kelipatan."""
    _bulat(k, 2)
    _rentang(a, b)
    akhir, sebelum = b // k, (a - 1) // k
    kunci = akhir - sebelum
    return _soal(
        "banyak_kelipatan", {"k": k, "a": a, "b": b},
        f"Berapa banyak kelipatan {k} dari {a} sampai {b}, termasuk kedua batasnya?", kunci,
        [("kelipatan.abaikan_awal", akhir, "K", "menghitung kelipatan dari 1 dan mengabaikan batas awal"),
         ("kelipatan.semua_bilangan", b - a + 1, "K", "menghitung semua bilangan, bukan hanya kelipatan"),
         ("kelipatan.kurang_satu", kunci - 1, "H", "hasil hitungan kelipatan kurang satu")],
        f"Sampai {b} ada {akhir} kelipatan {k}. Sebelum {a}, yaitu sampai {a - 1}, "
        f"ada {sebelum}. Jadi banyaknya = {akhir} − {sebelum} = {kunci}.", "A",
    )


def sisa_operasi(d: int, r1: int, r2: int, varian: str) -> Soal:
    """Gabungkan dua sisa dengan pembagi sama, lalu ambil sisanya lagi."""
    _bulat(d, 2)
    _bulat(r1, 0)
    _bulat(r2, 0)
    if r1 >= d or r2 >= d or varian not in ("jumlah", "kali"):
        raise ValueError("sisa atau operasi tidak sah")
    jumlah = varian == "jumlah"
    mentah = r1 + r2 if jumlah else r1 * r2
    tertukar = r1 * r2 if jumlah else r1 + r2
    kunci = mentah % d
    tanda = "+" if jumlah else "×"
    nama = "A + B" if jumlah else "A × B"
    return _soal(
        "sisa_operasi", {"d": d, "r1": r1, "r2": r2, "varian": varian},
        f"A dibagi {d} bersisa {r1}. B dibagi {d} bersisa {r2}. Berapa sisa {nama} jika dibagi {d}?", kunci,
        [("sisa_operasi.tanpa_modulo", mentah, "K", "menggabungkan sisa tanpa mengambil sisa pembagian lagi"),
         ("sisa_operasi.tertukar", tertukar % d, "K", "menukar operasi penjumlahan dan perkalian sisa"),
         ("sisa_operasi.lebih_satu", kunci + 1, "H", "sisa akhir meleset satu lebih besar")],
        f"Cukup gunakan sisa kedua bilangan: {r1} {tanda} {r2} = {mentah}. "
        f"Karena {mentah} = {mentah // d} × {d} + {kunci}, sisanya {kunci}.", "C",
    )


def _prima(n):
    return n >= 2 and all(n % d for d in range(2, isqrt(n) + 1))


def banyak_prima(a: int, b: int) -> Soal:
    """Cacah prima; 1 bukan prima maupun komposit, 2 adalah prima genap."""
    _rentang(a, b)
    prima = [x for x in range(a, b + 1) if _prima(x)]
    kunci = len(prima)
    komposit = sum(x > 1 and not _prima(x) for x in range(a, b + 1))
    daftar = ", ".join(map(str, prima)) if prima else "tidak ada"
    return _soal(
        "banyak_prima", {"a": a, "b": b},
        f"Berapa banyak bilangan prima dari {a} sampai {b}, termasuk kedua batasnya?", kunci,
        [("prima.semua_ganjil", sum(x % 2 for x in range(a, b + 1)), "K", "menganggap semua bilangan ganjil sebagai prima"),
         ("prima.komposit", komposit, "K", "menghitung bilangan komposit, bukan prima"),
         ("prima.lebih_satu", kunci + 1, "H", "jumlah bilangan prima lebih satu")],
        f"Prima mempunyai tepat dua faktor positif: 1 dan dirinya. Bilangan 1 bukan prima. "
        f"Prima pada rentang ini: {daftar}. Jadi banyaknya {kunci}.", "B",
    )


def jumlah_kelipatan(k: int, n: int) -> Soal:
    """Jumlah kelipatan positif hingga batas inklusif; jumlah kosong bernilai nol."""
    _bulat(k, 2)
    _bulat(n, 1)
    q = n // k
    indeks = q * (q + 1) // 2
    kunci = k * indeks
    langkah = (f"Tidak ada kelipatan positif {k} yang tidak melebihi {n}; jumlahnya 0."
               if q == 0 else
               f"Ada {q} kelipatan: {k} × 1 sampai {k} × {q}. "
               f"Jumlahnya = {k} × ({q} × {q + 1} ÷ 2) = {kunci}.")
    return _soal(
        "jumlah_kelipatan", {"k": k, "n": n},
        f"Berapa jumlah semua kelipatan positif {k} yang tidak lebih dari {n}?", kunci,
        [("jumlah_kelipatan.hanya_banyak", q, "K", "menjawab banyak kelipatan, bukan jumlah nilainya"),
         ("jumlah_kelipatan.tanpa_faktor", indeks, "K", "menjumlah indeks kelipatan tanpa mengalikannya dengan pembentuk kelipatan"),
         ("jumlah_kelipatan.kurang_satu", kunci - 1, "H", "jumlah akhir kurang satu")], langkah, "D",
    )


TEMPLATE = {f.__name__: f for f in (banyak_kelipatan, sisa_operasi, banyak_prima, jumlah_kelipatan)}


def parameter(template_id, rng, level):
    """Rejection terbatas demi malrule sah, bukan nudge jawaban atau pelebaran domain."""
    kecil = level == "P4"
    for _ in range(500):
        if template_id == "banyak_kelipatan":
            k = rng.randint(2, 12 if kecil else 20)
            a = rng.randint(k + 1, 100 if kecil else 300)
            p = {"k": k, "a": a, "b": a + rng.randint(2 * k, 5 * k)}
        elif template_id == "sisa_operasi":
            d = rng.randint(4, 15 if kecil else 25)
            p = {"d": d, "r1": rng.randrange(d), "r2": rng.randrange(d), "varian": rng.choice(("jumlah", "kali"))}
        elif template_id == "banyak_prima":
            a = rng.randint(1, 60 if kecil else 140)
            p = {"a": a, "b": a + rng.randint(8, 30 if kecil else 40)}
        elif template_id == "jumlah_kelipatan":
            k = rng.randint(2, 12 if kecil else 20)
            p = {"k": k, "n": k * rng.randint(3, 25 if kecil else 50) + rng.randrange(k)}
        else:
            raise KeyError(template_id)
        soal = TEMPLATE[template_id](**p)
        if len(soal.malrule) != 3 or int(soal.kunci) < (2 if template_id in ("banyak_kelipatan", "banyak_prima") else 0):
            continue
        if template_id == "sisa_operasi":
            mentah = p["r1"] + p["r2"] if p["varian"] == "jumlah" else p["r1"] * p["r2"]
            if mentah < p["d"]:
                continue
        return p
    raise RuntimeError(f"{template_id}: tidak mendapat parameter diagnostik dalam 500 percobaan")
