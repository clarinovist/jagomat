"""Matematika Awal, jenis `baca_diagram_gambar`: membaca diagram gambar sederhana (P1), teks saja.

Diagram gambar berupa tiga baris teks; satu simbol "●" mewakili tepat 1 benda:

    Diagram gambar mainan di rak. Satu titik hitam mewakili 1 mainan.
    Bola: ●●●
    Mobil: ●●●●●
    Boneka: ●●
    Berapa banyak mobil?

Simbol "●" HANYA muncul pada baris data (penjelasan satu simbol memakai kata
"titik hitam"), sehingga banyaknya "●" di seluruh teks sama dengan jumlah semua baris
dan tidak ada simbol yang terhitung dua kali.

Empat bentuk soal (`varian`):
  - `baca`: "Berapa banyak mobil?" (jawaban: angka);
  - `terbanyak`: "Mana yang paling banyak?" (jawaban: nama kategori, huruf kecil);
  - `selisih`: "Mobil lebih banyak berapa daripada boneka?" (jawaban: angka);
  - `jumlah`: "Berapa jumlah mobil dan boneka?" (jawaban: angka).

Tiga kategori per tema (mainan, buah, hewan), tiap jumlah 1..8 dan ketiga jumlah SELALU
berbeda: kategori terbanyak tunggal, dan pada `selisih` kategori pertama pasti lebih
banyak dari yang kedua. `jumlah` hanya menjumlah DUA kategori (paling besar 15, jadi
semua angka jawaban <= 20).

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban: membaca baris yang salah atau menyebut kategori lain (K); `selisih`
menjumlah dan `jumlah` mengurangi (K); salah hitung lebih/kurang satu (H, hanya pada
jawaban angka). Jalur K selalu ada.

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu anggota
seragam dari domain varian itu memakai `rng` (tanpa `hash()`), jadi seed yang sama
menghasilkan soal yang sama lintas proses. Daftar TEMA dan kategori bersifat
APPEND-ONLY menurut urutan: nama tema dan indeks kategori ikut dalam identitas soal.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import combinations, permutations
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "baca_diagram_gambar"
LEVEL = ("P1",)
VARIAN = ("baca", "terbanyak", "selisih", "jumlah")
SIMBOL = "●"
JUMLAH_MIN, JUMLAH_MAKS = 1, 8
JUMLAH_KATEGORI = 3
PESAN_LUAR_DOMAIN = "parameter baca diagram gambar di luar domain"
PESAN_LEVEL = "level baca diagram gambar harus P1"

# tema -> (tempat, kata benda satuan, tiga kategori); APPEND-ONLY.
TEMA = {
    "mainan": ("di rak", "mainan", ("Bola", "Mobil", "Boneka")),
    "buah": ("di keranjang", "buah", ("Apel", "Jeruk", "Pisang")),
    "hewan": ("di kandang", "hewan", ("Ayam", "Bebek", "Kelinci")),
}
# Kunci parameter jumlah ketiga kategori, urut menurut indeks kategori.
KUNCI_JUMLAH = ("n1", "n2", "n3")


def _nama(tema: str, indeks: int) -> str:
    return TEMA[tema][2][indeks].lower()


def _baris(tema: str, banyak: tuple) -> str:
    return "\n".join(f"{kat}: {SIMBOL * n}" for kat, n in zip(TEMA[tema][2], banyak))


def _kepala(tema: str) -> str:
    tempat, kata, _ = TEMA[tema]
    return f"Diagram gambar {tema} {tempat}. Satu titik hitam mewakili 1 {kata}."


def _pertanyaan(varian: str, tema: str, tanya, x, y) -> str:
    if varian == "baca":
        return f"Berapa banyak {_nama(tema, tanya)}?"
    if varian == "terbanyak":
        return "Mana yang paling banyak?"
    if varian == "selisih":
        return f"{_nama(tema, x).capitalize()} lebih banyak berapa daripada {_nama(tema, y)}?"
    return f"Berapa jumlah {_nama(tema, x)} dan {_nama(tema, y)}?"


def _teks(varian, tema, banyak, tanya, x, y) -> str:
    return f"{_kepala(tema)}\n{_baris(tema, banyak)}\n{_pertanyaan(varian, tema, tanya, x, y)}"


def _kunci(varian, tema, banyak, tanya, x, y) -> str:
    if varian == "baca":
        return str(banyak[tanya])
    if varian == "terbanyak":
        return _nama(tema, banyak.index(max(banyak)))
    if varian == "selisih":
        return str(banyak[x] - banyak[y])
    return str(banyak[x] + banyak[y])


def _pembahasan(varian, tema, banyak, tanya, x, y) -> str:
    kunci = _kunci(varian, tema, banyak, tanya, x, y)
    if varian == "baca":
        return (f"Hitung titik hitam pada baris {_nama(tema, tanya)} satu per satu "
                f"sambil menunjuk. Ada {kunci}. Jadi banyaknya {kunci}.")
    if varian == "terbanyak":
        return (f"Lihat baris mana yang titiknya paling panjang. Baris {kunci} punya "
                f"titik terbanyak, yaitu {max(banyak)}. Jadi yang paling banyak adalah {kunci}.")
    if varian == "selisih":
        return (f"Hitung dulu tiap baris: {_nama(tema, x)} {banyak[x]}, {_nama(tema, y)} "
                f"{banyak[y]}. Lebihnya dicari dengan mengurangi: {banyak[x]} - {banyak[y]} = {kunci}.")
    return (f"Hitung dulu tiap baris: {_nama(tema, x)} {banyak[x]}, {_nama(tema, y)} "
            f"{banyak[y]}. Lalu ditambah: {banyak[x]} + {banyak[y]} = {kunci}.")


def _malrule_hitung(kunci: int) -> list:
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.terhitung_dobel", str(kunci + 1), "H",
        "Sudah mengerti caranya, tetapi satu titik terhitung dua kali sehingga jawabannya lebih satu.")]
    if kunci - 1 >= 1:
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.terlewat", str(kunci - 1), "H",
            "Sudah mengerti caranya, tetapi satu titik terlewat sehingga jawabannya kurang satu."))
    return kandidat


def _malrule_baca(tema, banyak, tanya) -> list:
    lain = [i for i in range(JUMLAH_KATEGORI) if i != tanya]
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.baris_lain_{urut}", str(banyak[i]), "K",
        f"Menghitung titik pada baris {_nama(tema, i)} (ada {banyak[i]}), kemungkinan salah baris.")
        for urut, i in enumerate(lain, 1)]
    return kandidat + _malrule_hitung(banyak[tanya])


def _malrule_terbanyak(tema, banyak) -> list:
    urut = sorted(range(JUMLAH_KATEGORI), key=lambda i: banyak[i])
    sedikit, tengah = urut[0], urut[1]
    return [
        Malrule(f"{TEMPLATE_ID}.sebut_paling_sedikit", _nama(tema, sedikit), "K",
                f"Menyebut {_nama(tema, sedikit)}, kemungkinan tertukar arti paling banyak "
                "dan paling sedikit."),
        Malrule(f"{TEMPLATE_ID}.sebut_tengah", _nama(tema, tengah), "K",
                f"Menyebut {_nama(tema, tengah)}, kemungkinan belum membandingkan ketiga baris."),
    ]


def _malrule_selisih(banyak, x, y) -> list:
    return [Malrule(
        f"{TEMPLATE_ID}.jumlah_bukan_selisih", str(banyak[x] + banyak[y]), "K",
        "Menjumlahkan kedua baris, padahal yang ditanya lebihnya (selisih), "
        "jadi seharusnya dikurangi.")] + _malrule_hitung(banyak[x] - banyak[y])


def _malrule_jumlah(banyak, x, y) -> list:
    return [Malrule(
        f"{TEMPLATE_ID}.selisih_bukan_jumlah", str(abs(banyak[x] - banyak[y])), "K",
        "Mengurangkan kedua baris, padahal yang ditanya jumlahnya, "
        "jadi seharusnya ditambah.")] + _malrule_hitung(banyak[x] + banyak[y])


def _kandidat_malrule(varian, tema, banyak, tanya, x, y) -> list:
    if varian == "baca":
        return _malrule_baca(tema, banyak, tanya)
    if varian == "terbanyak":
        return _malrule_terbanyak(tema, banyak)
    if varian == "selisih":
        return _malrule_selisih(banyak, x, y)
    return _malrule_jumlah(banyak, x, y)


def _indeks_sah(nilai) -> bool:
    return type(nilai) is int and 0 <= nilai < JUMLAH_KATEGORI


def _banyak_sah(banyak: tuple) -> bool:
    bulat = all(type(n) is int and JUMLAH_MIN <= n <= JUMLAH_MAKS for n in banyak)
    return bulat and len(set(banyak)) == JUMLAH_KATEGORI


def _pilihan_sah(varian: str, banyak: tuple, tanya, x, y) -> bool:
    if varian == "baca":
        return x is None and y is None and _indeks_sah(tanya)
    if varian == "terbanyak":
        return tanya is None and x is None and y is None
    if tanya is not None or not (_indeks_sah(x) and _indeks_sah(y)):
        return False
    if varian == "selisih":
        return banyak[x] > banyak[y]
    return x < y


def _sah(varian, tema, banyak, tanya, x, y) -> bool:
    if type(varian) is not str or varian not in VARIAN:
        return False
    if type(tema) is not str or tema not in TEMA:
        return False
    return _banyak_sah(banyak) and _pilihan_sah(varian, banyak, tanya, x, y)


def baca_diagram_gambar(varian: str, tema: str, n1: int, n2: int, n3: int,
                        tanya: int | None = None, x: int | None = None,
                        y: int | None = None) -> Soal:
    """Baca satu baris, kategori terbanyak, selisih, atau jumlah dua baris (kunci dari parameter)."""
    banyak = (n1, n2, n3)
    if not _sah(varian, tema, banyak, tanya, x, y):
        raise ValueError(PESAN_LUAR_DOMAIN)
    parameter = {"varian": varian, "tema": tema, "n1": n1, "n2": n2, "n3": n3}
    for nama, nilai in (("tanya", tanya), ("x", x), ("y", y)):
        if nilai is not None:
            parameter[nama] = nilai
    kunci = _kunci(varian, tema, banyak, tanya, x, y)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter,
        teks=_teks(varian, tema, banyak, tanya, x, y), kunci=kunci,
        malrule=saring_malrule(kunci, _kandidat_malrule(varian, tema, banyak, tanya, x, y)),
        pembahasan=_pembahasan(varian, tema, banyak, tanya, x, y), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _dasar(varian: str, tema: str, banyak: tuple) -> dict:
    return {"varian": varian, "tema": tema,
            **{k: n for k, n in zip(KUNCI_JUMLAH, banyak)}}


def _tambahan(varian: str, banyak: tuple) -> list:
    """Pilihan tambahan per varian: indeks yang ditanya, atau pasangan kategori."""
    semua = range(JUMLAH_KATEGORI)
    if varian == "baca":
        return [{"tanya": i} for i in semua]
    if varian == "terbanyak":
        return [{}]
    if varian == "selisih":
        return [{"x": x, "y": y} for x, y in permutations(semua, 2) if banyak[x] > banyak[y]]
    return [{"x": x, "y": y} for x, y in combinations(semua, 2)]


def _enumerasi(varian: str) -> list:
    hasil = []
    for tema in TEMA:
        for banyak in permutations(range(JUMLAH_MIN, JUMLAH_MAKS + 1), JUMLAH_KATEGORI):
            for tambah in _tambahan(varian, banyak):
                hasil.append({**_dasar(varian, tema, banyak), **tambah})
    return hasil


@lru_cache(maxsize=None)
def _domain_varian(varian: str) -> tuple:
    """Anggota domain satu varian sebagai tuple item immutable (urutan enumerasi = urutan undian)."""
    return tuple(tuple(p.items()) for p in _enumerasi(varian))


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError(PESAN_LEVEL)


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for varian in VARIAN for item in _domain_varian(varian))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu anggota seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return dict(rng.choice(_domain_varian(varian)))
