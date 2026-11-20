"""kali_bagi_sekolah: perkalian dan pembagian bilangan bulat (pembagian selalu habis).

Tiga jenis soal menurut tingkat:
  fakta  P3  fakta kali 2..10 x 2..10 dan pembagian padanannya;
  2x1    P4  bilangan 2 angka x 1 angka dan pembagian padanannya (hasil 2 angka);
  3x2    P5  bilangan 3 angka x 2 angka (mis. 348 x 25) dan pembagian habis
             dengan pembagi 2 angka (mis. 7.200 : 36), dividen sampai 100.000.
Parameter `a`, `b`: kali = a x b; bagi = a dibagi b (a dividen, b pembagi).
Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru.
"""
from __future__ import annotations

from functools import lru_cache
import random

from school_numbers_common import (BAGI, BATAS_UNDI, KALI, bilangan_bulat, dari_kolom,
                                   kolom, ribuan)
from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "kali_bagi_sekolah"
VARIAN = ("kali", "bagi")
BATAS_DIVIDEN = 100_000
JENIS_FAKTA, JENIS_2X1, JENIS_3X2 = "fakta", "2x1", "3x2"
ID_DIJUMLAHKAN = TEMPLATE_ID + ".dijumlahkan"
ID_LUPA_MENYIMPAN = TEMPLATE_ID + ".lupa_menyimpan"
ID_LUPA_GESER = TEMPLATE_ID + ".lupa_geser"
ID_KALI_KURANG = TEMPLATE_ID + ".kali_kurang_satu_kelompok"
ID_KALI_LEBIH = TEMPLATE_ID + ".kali_lebih_satu_kelompok"
ID_DIKALIKAN = TEMPLATE_ID + ".dikalikan"
ID_LETAK_NOL = TEMPLATE_ID + ".salah_letak_nol"
ID_NOL_TERLEWAT = TEMPLATE_ID + ".nol_terlewat"
ID_BAGI_KURANG = TEMPLATE_ID + ".bagi_kurang_satu"
ID_BAGI_LEBIH = TEMPLATE_ID + ".bagi_lebih_satu"


def _jenis_kali(a: int, b: int):
    if 2 <= a <= 10 and 2 <= b <= 10:
        return JENIS_FAKTA
    if 11 <= a <= 99 and 2 <= b <= 9:
        return JENIS_2X1
    if 100 <= a <= 999 and 11 <= b <= 99:
        return JENIS_3X2
    return None


def _jenis_bagi(dividen: int, pembagi: int):
    if pembagi < 2 or dividen % pembagi:
        return None
    q = dividen // pembagi
    if 2 <= pembagi <= 10 and 2 <= q <= 10:
        return JENIS_FAKTA
    if 2 <= pembagi <= 9 and 10 <= q <= 99:
        return JENIS_2X1
    if 11 <= pembagi <= 99 and 12 <= q <= 999 and dividen <= BATAS_DIVIDEN:
        return JENIS_3X2
    return None


def _lupa_kali_satu(a: int, pengali: int) -> int:
    """Kali per angka: kolom kanan hanya menulis satuannya, kolom paling kiri menulis utuh."""
    isi = kolom(a)
    atas = len(isi) - 1
    bawah = sum((d * pengali % 10) * 10 ** i for i, d in enumerate(isi[:atas]))
    return bawah + isi[atas] * pengali * 10 ** atas


def _lupa_menyimpan(a: int, b: int) -> int:
    return sum(_lupa_kali_satu(a, m) * 10 ** j for j, m in enumerate(kolom(b)))


def _lupa_geser(a: int, b: int) -> int:
    """Hasil kali per angka pengali dijumlahkan tanpa digeser satu tempat ke kiri."""
    return sum(a * m for m in kolom(b))


def _nol_terlewat(q: int):
    sisa = str(q).replace("0", "")
    return int(sisa) if "0" in str(q) and sisa else None


def _kandidat_kali(a: int, b: int, jenis: str) -> list:
    hasil = [Malrule(ID_DIJUMLAHKAN, str(a + b), "K",
                     "Menjumlahkan kedua bilangan, padahal tandanya kali.")]
    if jenis != JENIS_FAKTA:
        hasil.append(Malrule(ID_LUPA_MENYIMPAN, str(_lupa_menyimpan(a, b)), "K",
                             "Lupa menyimpan: hasil kali tiap kolom ditulis tanpa menambahkan simpanan."))
    if b >= 10:
        hasil.append(Malrule(ID_LUPA_GESER, str(_lupa_geser(a, b)), "K",
                             "Lupa menggeser hasil kali puluhan pengali satu tempat ke kiri sebelum dijumlahkan."))
    if jenis != JENIS_3X2:
        kunci = a * b
        hasil.append(Malrule(ID_KALI_KURANG, str(kunci - b), "H",
                             "Salah menghitung banyak kelompok, kurang satu kelompok."))
        hasil.append(Malrule(ID_KALI_LEBIH, str(kunci + b), "H",
                             "Salah menghitung banyak kelompok, lebih satu kelompok."))
    return hasil


def _kandidat_bagi(dividen: int, pembagi: int) -> list:
    q = dividen // pembagi
    hasil = [
        Malrule(ID_DIKALIKAN, str(dividen * pembagi), "K",
                "Mengalikan kedua bilangan, padahal tandanya bagi."),
        Malrule(ID_LETAK_NOL, str(q // 10 if q % 10 == 0 else q * 10), "K",
                "Salah letak nol pada hasil: hasilnya kurang atau lebih satu tempat nilai."),
    ]
    tanpa_nol = _nol_terlewat(q)
    if tanpa_nol is not None:
        hasil.append(Malrule(ID_NOL_TERLEWAT, str(tanpa_nol), "K",
                             "Melewatkan angka nol di tengah hasil pembagian."))
    hasil.append(Malrule(ID_BAGI_KURANG, str(q - 1), "H",
                         "Salah hitung pada satu langkah, hasilnya kurang satu."))
    hasil.append(Malrule(ID_BAGI_LEBIH, str(q + 1), "H",
                         "Salah hitung pada satu langkah, hasilnya lebih satu."))
    return hasil


def _paket(varian: str, a: int, b: int):
    """(jenis, kunci, kandidat) bila parameter sah, selain itu None."""
    if varian == "kali":
        jenis = _jenis_kali(a, b)
        if jenis is None or (jenis == JENIS_2X1 and a % 10 == 0) or (jenis == JENIS_3X2 and b % 10 == 0):
            return None
        return jenis, a * b, _kandidat_kali(a, b, jenis)
    jenis = _jenis_bagi(a, b)
    if jenis is None:
        return None
    return jenis, a // b, _kandidat_bagi(a, b)


def _lengkap(varian: str, a: int, b: int):
    """(jenis, kunci, malrule tersaring) bila sah dan cukup untuk diagnosis dan PG."""
    paket = _paket(varian, a, b)
    if paket is None:
        return None
    jenis, kunci, kandidat = paket
    sisa = saring_malrule(str(kunci), kandidat)
    ada_k = any(m.kode == "K" for m in sisa)
    perlu_lupa = varian == "kali" and jenis != JENIS_FAKTA
    if not ada_k or len(sisa) < 2:
        return None
    if perlu_lupa and not any(m.id == ID_LUPA_MENYIMPAN for m in sisa):
        return None
    return jenis, kunci, sisa


def _sah(varian, a, b) -> bool:
    if varian not in VARIAN or not (bilangan_bulat(a) and bilangan_bulat(b)):
        return False
    return _lengkap(varian, a, b) is not None


def _pembahasan_kali(a: int, b: int, jenis: str) -> str:
    kunci = a * b
    if jenis == JENIS_FAKTA:
        return (f"{a} {KALI} {b} berarti {a} kelompok yang masing-masing berisi {b}. "
                f"Jumlahnya {ribuan(kunci)}, jadi {a} {KALI} {b} = {ribuan(kunci)}.")
    if jenis == JENIS_2X1:
        puluhan, satuan = a // 10 * 10, a % 10
        return (f"Pecah {a} menjadi {puluhan} dan {satuan}: {a} {KALI} {b} = "
                f"({puluhan} {KALI} {b}) + ({satuan} {KALI} {b}) = "
                f"{ribuan(puluhan * b)} + {ribuan(satuan * b)} = {ribuan(kunci)}.")
    puluhan, satuan = b // 10 * 10, b % 10
    return (f"Pecah {b} menjadi {puluhan} dan {satuan}: {ribuan(a)} {KALI} {b} = "
            f"({ribuan(a)} {KALI} {puluhan}) + ({ribuan(a)} {KALI} {satuan}) = "
            f"{ribuan(a * puluhan)} + {ribuan(a * satuan)} = {ribuan(kunci)}.")


def _pembahasan_bagi(dividen: int, pembagi: int) -> str:
    q = dividen // pembagi
    return (f"Cari bilangan yang jika dikali {pembagi} hasilnya {ribuan(dividen)}. "
            f"Karena {pembagi} {KALI} {ribuan(q)} = {ribuan(dividen)}, "
            f"maka {ribuan(dividen)} {BAGI} {pembagi} = {ribuan(q)}.")


def kali_bagi_sekolah(varian: str, a: int, b: int) -> Soal:
    """Hitung a x b, atau a dibagi b (habis); jenis soal mengikuti besar bilangan."""
    if varian not in VARIAN or not (bilangan_bulat(a) and bilangan_bulat(b)):
        raise ValueError("parameter kali/bagi di luar domain")
    lengkap = _lengkap(varian, a, b)
    if lengkap is None:
        raise ValueError("parameter kali/bagi di luar domain")
    jenis, kunci, malrule = lengkap
    tanda = KALI if varian == "kali" else BAGI
    pembahasan = _pembahasan_kali(a, b, jenis) if varian == "kali" else _pembahasan_bagi(a, b)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, "a": a, "b": b},
        teks=f"Hitung: {ribuan(a)} {tanda} {ribuan(b)} = ...", kunci=str(kunci),
        malrule=malrule, pembahasan=pembahasan, bagian="D")


@lru_cache(maxsize=None)
def _domain_p3() -> tuple:
    kali = tuple({"varian": "kali", "a": a, "b": b}
                 for a in range(2, 11) for b in range(2, 11) if _sah("kali", a, b))
    bagi = tuple({"varian": "bagi", "a": b * q, "b": b}
                 for b in range(2, 11) for q in range(2, 11) if _sah("bagi", b * q, b))
    return kali + bagi


def domain_parameter(template_id: str, level: str) -> tuple:
    """Seluruh parameter sah P3 (fakta); domain level lain terlalu besar untuk dienumerasi."""
    if template_id != TEMPLATE_ID or level != "P3":
        raise KeyError((template_id, level))
    return tuple(dict(item) for item in _domain_p3())


def _acak_p4_p5(rng: random.Random, level: str) -> dict:
    varian = rng.choice(VARIAN)
    if level == "P4":
        pengali, hasil_bagi = rng.randint(2, 9), rng.randint(11, 99)
        besar = rng.randint(11, 99)
    else:
        pengali, hasil_bagi = rng.randint(11, 99), rng.randint(12, 999)
        besar = rng.randint(100, 999)
    if varian == "kali":
        return {"varian": varian, "a": besar, "b": pengali}
    return {"varian": varian, "a": pengali * hasil_bagi, "b": pengali}


def parameter(rng: random.Random, level: str) -> dict:
    if level == "P3":
        return dict(rng.choice(_domain_p3()))
    for _ in range(BATAS_UNDI):
        calon = _acak_p4_p5(rng, level)
        if _sah(calon["varian"], calon["a"], calon["b"]):
            return calon
    raise RuntimeError(f"{TEMPLATE_ID}: tak ada parameter sah dalam {BATAS_UNDI} percobaan")
