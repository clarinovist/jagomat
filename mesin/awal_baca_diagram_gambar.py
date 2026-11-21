"""Matematika Awal, jenis `baca_diagram_gambar`: membaca diagram gambar sederhana (P1, P2), teks saja.

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

Level P2 (kelas 2) menambah SATU konsep, skala: satu titik hitam bisa mewakili lebih dari
1 benda. Parameter `skala` (1 atau 2) HANYA ada pada soal P2; soal P1 tanpa field itu
(`skala=None` pada fungsi) dan tidak berubah sama sekali (identitas, kunci, malrule,
pembahasan, urutan enumerasi, urutan undian). P2 mencampur dua kelompok: skala 1 dengan
jumlah titik 5..12 (bilangan lebih besar; 1..4 sudah dilatih di P1), dan skala 2 dengan jumlah
titik 1..8 (ketiga jumlah tetap berbeda). Domain P2 = 20160 anggota, dua kali domain P1.
Nilai benda = banyak titik x skala: `baca` = n x skala, `selisih` = (n_x - n_y) x skala,
`jumlah` = (n_x + n_y) x skala, `terbanyak` = kategori dengan titik terbanyak (skala tidak
mengubahnya). Jawaban angka paling besar 30 (skala 2, jumlah (8 + 7) x 2). Angka skala
hanya ada pada kalimat kepala ("Satu titik hitam mewakili 2 mainan."); simbol "●" tetap
hanya pada baris data. Malrule P2 menambah hipotesis "lupa mengalikan skala" (K): jawaban
sama dengan jumlah titik tanpa dikali skala. Salah hitung satu titik (H) bergeser sebesar
skala, karena satu titik bernilai skala benda.

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu anggota
seragam dari domain varian itu memakai `rng` (tanpa `hash()`), jadi seed yang sama
menghasilkan soal yang sama lintas proses. Urutan enumerasi satu varian (urutan undian):
tema -> kelompok skala (P2: skala 1 lalu skala 2) -> permutasi jumlah -> pilihan tambahan;
domain satu level = varian demi varian menurut `VARIAN`. Daftar TEMA dan kategori bersifat
APPEND-ONLY menurut urutan: nama tema dan indeks kategori ikut dalam identitas soal.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import combinations, permutations
import random
from types import MappingProxyType

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "baca_diagram_gambar"
LEVEL = ("P1", "P2")
VARIAN = ("baca", "terbanyak", "selisih", "jumlah")
SIMBOL = "●"
JUMLAH_MIN, JUMLAH_MAKS = 1, 8  # JUMLAH_MAKS = batas P1 (tanpa skala)
JUMLAH_KATEGORI = 3
# Skala P2 -> (jumlah titik paling sedikit, paling banyak) per kategori.
BATAS_JUMLAH_SKALA = MappingProxyType({1: (5, 12), 2: (1, 8)})  # skala -> (minimum, maksimum)
SKALA_P2 = tuple(BATAS_JUMLAH_SKALA)
PESAN_LUAR_DOMAIN = "parameter baca diagram gambar di luar domain"
PESAN_LEVEL = "level baca diagram gambar harus P1 atau P2"

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


def _faktor(skala) -> int:
    """Benda per titik: 1 untuk P1 (tanpa skala) dan P2 skala 1."""
    return 1 if skala is None else skala


def _baris(tema: str, banyak: tuple) -> str:
    return "\n".join(f"{kat}: {SIMBOL * n}" for kat, n in zip(TEMA[tema][2], banyak))


def _kepala(tema: str, skala=None) -> str:
    tempat, kata, _ = TEMA[tema]
    return f"Diagram gambar {tema} {tempat}. Satu titik hitam mewakili {_faktor(skala)} {kata}."


def _pertanyaan(varian: str, tema: str, tanya, x, y) -> str:
    if varian == "baca":
        return f"Berapa banyak {_nama(tema, tanya)}?"
    if varian == "terbanyak":
        return "Mana yang paling banyak?"
    if varian == "selisih":
        return f"{_nama(tema, x).capitalize()} lebih banyak berapa daripada {_nama(tema, y)}?"
    return f"Berapa jumlah {_nama(tema, x)} dan {_nama(tema, y)}?"


def _teks(varian, tema, banyak, tanya, x, y, skala=None) -> str:
    return (f"{_kepala(tema, skala)}\n{_baris(tema, banyak)}\n"
            f"{_pertanyaan(varian, tema, tanya, x, y)}")


def _kunci(varian, tema, banyak, tanya, x, y, skala=None) -> str:
    faktor = _faktor(skala)
    if varian == "baca":
        return str(banyak[tanya] * faktor)
    if varian == "terbanyak":
        return _nama(tema, banyak.index(max(banyak)))
    if varian == "selisih":
        return str((banyak[x] - banyak[y]) * faktor)
    return str((banyak[x] + banyak[y]) * faktor)


def _pembahasan_skala_dua(varian, tema, banyak, tanya, x, y, kunci) -> str:
    """Pembahasan skala 2: hitung titiknya, lalu kalikan 2 (atau tambah 2 berulang)."""
    kata = TEMA[tema][1]
    if varian == "baca":
        n = banyak[tanya]
        return (f"Satu titik hitam mewakili 2 {kata}. Hitung titik pada baris {_nama(tema, tanya)} "
                f"satu per satu: ada {n} titik. Tiap titik bernilai 2, jadi {n} × 2 = {kunci} "
                f"(sama dengan menambah 2 sebanyak {n} kali). Jadi banyaknya {kunci}.")
    nilai_x, nilai_y = banyak[x] * 2, banyak[y] * 2
    awal = (f"Satu titik hitam mewakili 2 {kata}. Hitung titik tiap baris lalu kalikan 2: "
            f"{_nama(tema, x)} {banyak[x]} × 2 = {nilai_x}, {_nama(tema, y)} {banyak[y]} × 2 = {nilai_y}. ")
    if varian == "selisih":
        return awal + f"Lebihnya dicari dengan mengurangi: {nilai_x} - {nilai_y} = {kunci}."
    return awal + f"Lalu ditambah: {nilai_x} + {nilai_y} = {kunci}."


def _pembahasan(varian, tema, banyak, tanya, x, y, skala=None) -> str:
    kunci = _kunci(varian, tema, banyak, tanya, x, y, skala)
    if skala == 2 and varian != "terbanyak":
        return _pembahasan_skala_dua(varian, tema, banyak, tanya, x, y, kunci)
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


def _malrule_hitung(kunci: int, langkah: int = 1) -> list:
    """Salah hitung satu titik (H): bergeser sebesar `langkah` (= benda per titik)."""
    if langkah == 1:
        lebih = "satu titik terhitung dua kali sehingga jawabannya lebih satu."
        kurang = "satu titik terlewat sehingga jawabannya kurang satu."
    else:
        lebih = f"satu titik terhitung dua kali sehingga jawabannya lebih {langkah}."
        kurang = f"satu titik terlewat sehingga jawabannya kurang {langkah}."
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.terhitung_dobel", str(kunci + langkah), "H",
        f"Sudah mengerti caranya, tetapi {lebih}")]
    if kunci - langkah >= 1:
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.terlewat", str(kunci - langkah), "H",
            f"Sudah mengerti caranya, tetapi {kurang}"))
    return kandidat


def _malrule_lupa_kali(jawaban: int) -> Malrule:
    """K khas skala 2: jawaban = jumlah titik tanpa dikali skala."""
    return Malrule(
        f"{TEMPLATE_ID}.lupa_kali_skala", str(jawaban), "K",
        "Hanya menghitung titiknya, lupa mengalikan 2 padahal satu titik mewakili 2 benda.")


def _malrule_baca(tema, banyak, tanya, skala=None) -> list:
    faktor = _faktor(skala)
    lain = [i for i in range(JUMLAH_KATEGORI) if i != tanya]
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.baris_lain_{urut}", str(banyak[i] * faktor), "K",
        f"Menghitung titik pada baris {_nama(tema, i)} (ada {banyak[i] * faktor}), kemungkinan salah baris.")
        for urut, i in enumerate(lain, 1)]
    awal = [_malrule_lupa_kali(banyak[tanya])] if skala == 2 else []
    return awal + kandidat + _malrule_hitung(banyak[tanya] * faktor, faktor)


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


def _malrule_selisih(banyak, x, y, skala=None) -> list:
    faktor = _faktor(skala)
    selisih = banyak[x] - banyak[y]
    awal = [_malrule_lupa_kali(selisih)] if skala == 2 else []
    return awal + [Malrule(
        f"{TEMPLATE_ID}.jumlah_bukan_selisih", str((banyak[x] + banyak[y]) * faktor), "K",
        "Menjumlahkan kedua baris, padahal yang ditanya lebihnya (selisih), "
        "jadi seharusnya dikurangi.")] + _malrule_hitung(selisih * faktor, faktor)


def _malrule_jumlah(banyak, x, y, skala=None) -> list:
    faktor = _faktor(skala)
    jumlah = banyak[x] + banyak[y]
    awal = [_malrule_lupa_kali(jumlah)] if skala == 2 else []
    return awal + [Malrule(
        f"{TEMPLATE_ID}.selisih_bukan_jumlah", str(abs(banyak[x] - banyak[y]) * faktor), "K",
        "Mengurangkan kedua baris, padahal yang ditanya jumlahnya, "
        "jadi seharusnya ditambah.")] + _malrule_hitung(jumlah * faktor, faktor)


def _kandidat_malrule(varian, tema, banyak, tanya, x, y, skala=None) -> list:
    if varian == "baca":
        return _malrule_baca(tema, banyak, tanya, skala)
    if varian == "terbanyak":
        return _malrule_terbanyak(tema, banyak)
    if varian == "selisih":
        return _malrule_selisih(banyak, x, y, skala)
    return _malrule_jumlah(banyak, x, y, skala)


def _indeks_sah(nilai) -> bool:
    return type(nilai) is int and 0 <= nilai < JUMLAH_KATEGORI


def _skala_sah(skala) -> bool:
    return skala is None or (type(skala) is int and skala in BATAS_JUMLAH_SKALA)


def _batas_jumlah(skala) -> tuple:
    """(minimum, maksimum) jumlah titik: P1 (tanpa skala) 1..8, P2 menurut skala."""
    return (JUMLAH_MIN, JUMLAH_MAKS) if skala is None else BATAS_JUMLAH_SKALA[skala]


def _banyak_sah(banyak: tuple, batas: tuple = (JUMLAH_MIN, JUMLAH_MAKS)) -> bool:
    terkecil, terbesar = batas
    bulat = all(type(n) is int and terkecil <= n <= terbesar for n in banyak)
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


def _sah(varian, tema, banyak, tanya, x, y, skala=None) -> bool:
    if type(varian) is not str or varian not in VARIAN:
        return False
    if type(tema) is not str or tema not in TEMA:
        return False
    if not _skala_sah(skala):
        return False
    return _banyak_sah(banyak, _batas_jumlah(skala)) and _pilihan_sah(varian, banyak, tanya, x, y)


def baca_diagram_gambar(varian: str, tema: str, n1: int, n2: int, n3: int,
                        tanya: int | None = None, x: int | None = None,
                        y: int | None = None, skala: int | None = None) -> Soal:
    """Baca satu baris, kategori terbanyak, selisih, atau jumlah dua baris (kunci dari parameter).

    `skala=None` = soal P1 (satu titik = 1 benda, tanpa field skala); `skala` 1 atau 2 = soal P2.
    """
    banyak = (n1, n2, n3)
    if not _sah(varian, tema, banyak, tanya, x, y, skala):
        raise ValueError(PESAN_LUAR_DOMAIN)
    parameter = {"varian": varian, "tema": tema, "n1": n1, "n2": n2, "n3": n3}
    for nama, nilai in (("skala", skala), ("tanya", tanya), ("x", x), ("y", y)):
        if nilai is not None:
            parameter[nama] = nilai
    kunci = _kunci(varian, tema, banyak, tanya, x, y, skala)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter,
        teks=_teks(varian, tema, banyak, tanya, x, y, skala), kunci=kunci,
        malrule=saring_malrule(kunci, _kandidat_malrule(varian, tema, banyak, tanya, x, y, skala)),
        pembahasan=_pembahasan(varian, tema, banyak, tanya, x, y, skala), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

# Level -> kelompok (skala, jumlah paling sedikit, jumlah paling banyak); P1 tanpa skala (None).
KELOMPOK_LEVEL = MappingProxyType({
    "P1": ((None, JUMLAH_MIN, JUMLAH_MAKS),),
    "P2": tuple((skala, *BATAS_JUMLAH_SKALA[skala]) for skala in SKALA_P2),
})


def _dasar(varian: str, tema: str, banyak: tuple, skala=None) -> dict:
    dasar = {"varian": varian, "tema": tema,
             **{k: n for k, n in zip(KUNCI_JUMLAH, banyak)}}
    return dasar if skala is None else {**dasar, "skala": skala}


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


def _enumerasi(level: str, varian: str) -> list:
    hasil = []
    for tema in TEMA:
        for skala, terkecil, terbesar in KELOMPOK_LEVEL[level]:
            for banyak in permutations(range(terkecil, terbesar + 1), JUMLAH_KATEGORI):
                for tambah in _tambahan(varian, banyak):
                    hasil.append({**_dasar(varian, tema, banyak, skala), **tambah})
    return hasil


@lru_cache(maxsize=None)
def _domain_varian(level: str, varian: str) -> tuple:
    """Anggota domain satu varian sebagai tuple item immutable (urutan enumerasi = urutan undian)."""
    return tuple(tuple(p.items()) for p in _enumerasi(level, varian))


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError(PESAN_LEVEL)


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for varian in VARIAN for item in _domain_varian(level, varian))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu anggota seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return dict(rng.choice(_domain_varian(level, varian)))
