"""urutkan_bilangan: pilih bilangan terbesar atau terkecil dari empat bilangan.

Empat bilangan berbeda dan SELALU berbeda banyak angka, supaya pengecoh
"bandingkan angka paling depan saja" bermakna. Batas atas sama dengan
nilai_tempat_besar (P3 999, P4 9.999, P5 999.999); batas bawah satu tingkat
lebih rendah (P3 mulai 10, P4 100, P5 5 angka) supaya ada bilangan yang lebih
pendek. Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru.
"""
from __future__ import annotations

import random

from school_numbers_common import (BATAS_UNDI, NAMA_TEMPAT, bilangan_bulat, gabung,
                                   ribuan)
from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "urutkan_bilangan"
VARIAN = ("terbesar", "terkecil")
JUMLAH_BILANGAN = 4
BATAS_BAWAH, BATAS_ATAS = 10, 999_999
# (banyak angka bilangan pendek, banyak angka bilangan panjang) per level.
PANJANG_PER_LEVEL = {"P3": (2, 3), "P4": (3, 4), "P5": (5, 6)}
ID_ANGKA_DEPAN = TEMPLATE_ID + ".angka_depan_saja"
ID_TERBALIK = TEMPLATE_ID + ".terbalik"


def _kunci(varian: str, bilangan: list) -> int:
    return max(bilangan) if varian == "terbesar" else min(bilangan)


def _lawan(varian: str, bilangan: list) -> int:
    return min(bilangan) if varian == "terbesar" else max(bilangan)


def _pilihan_angka_depan(varian: str, bilangan: list):
    """Bilangan yang dipilih bila hanya angka paling depan dibandingkan; None bila seri."""
    depan = [int(str(n)[0]) for n in bilangan]
    target = max(depan) if varian == "terbesar" else min(depan)
    if depan.count(target) != 1:
        return None
    return bilangan[depan.index(target)]


def _sah(varian, bilangan) -> bool:
    if varian not in VARIAN or type(bilangan) is not list or len(bilangan) != JUMLAH_BILANGAN:
        return False
    if not all(bilangan_bulat(n) and BATAS_BAWAH <= n <= BATAS_ATAS for n in bilangan):
        return False
    if len(set(bilangan)) != JUMLAH_BILANGAN or len({len(str(n)) for n in bilangan}) < 2:
        return False
    pilihan = _pilihan_angka_depan(varian, bilangan)
    return pilihan is not None and pilihan != _kunci(varian, bilangan)


def _tempat(panjang: int, indeks: int) -> str:
    return NAMA_TEMPAT[panjang - 1 - indeks]


def _langkah_angka(sisa: list, panjang: int, terbesar: bool) -> tuple:
    """(kalimat, hasil): angka dibandingkan dari tempat tertinggi sampai tersisa satu bilangan."""
    kalimat, indeks, sama = [], 0, []
    while len(sisa) > 1:
        angka = [str(n)[indeks] for n in sisa]
        if len(set(angka)) == 1:
            sama.append(indeks)
            indeks += 1
            continue
        if sama:
            kalimat.append(_kalimat_sama(sama, panjang))
            sama = []
        pilih = max(angka) if terbesar else min(angka)
        kata = "terbesar" if terbesar else "terkecil"
        kalimat.append(f"Di tempat {_tempat(panjang, indeks)}, angkanya {gabung(angka)}; "
                       f"yang {kata} {pilih}.")
        sisa = [n for n in sisa if str(n)[indeks] == pilih]
        indeks += 1
    return kalimat, sisa[0]


def _kalimat_sama(indeks_sama: list, panjang: int) -> str:
    awal, akhir = _tempat(panjang, indeks_sama[0]), _tempat(panjang, indeks_sama[-1])
    if awal == akhir:
        return f"Angka di tempat {awal} sama."
    return f"Angka di tempat {awal} sampai {akhir} sama."


def _pembahasan(varian: str, bilangan: list) -> str:
    terbesar = varian == "terbesar"
    panjang = {n: len(str(n)) for n in bilangan}
    daftar = ", ".join(f"{ribuan(n)} ada {panjang[n]} angka" for n in bilangan)
    target = max(panjang.values()) if terbesar else min(panjang.values())
    sisa = [n for n in bilangan if panjang[n] == target]
    banyak = "paling banyak" if terbesar else "paling sedikit"
    arah = "besar" if terbesar else "kecil"
    kalimat = [f"Hitung banyak angka tiap bilangan: {daftar}.",
               f"Bilangan yang angkanya {banyak} lebih {arah}."]
    if len(sisa) == 1:
        hasil = sisa[0]
        kalimat.append(f"Hanya {ribuan(hasil)} yang punya {target} angka, jadi bilangan "
                       f"{varian} adalah {ribuan(hasil)}.")
        return " ".join(kalimat)
    kalimat.append(f"Bilangan yang punya {target} angka: {gabung(ribuan(n) for n in sisa)}.")
    langkah, hasil = _langkah_angka(sisa, target, terbesar)
    kalimat.extend(langkah)
    kalimat.append(f"Jadi bilangan {varian} adalah {ribuan(hasil)}.")
    return " ".join(kalimat)


def urutkan_bilangan(varian: str, bilangan: list) -> Soal:
    """Pilih bilangan terbesar atau terkecil dari empat bilangan berbeda panjang."""
    if not _sah(varian, bilangan):
        raise ValueError("parameter urutkan bilangan di luar domain")
    kunci = str(_kunci(varian, bilangan))
    kandidat = [
        Malrule(ID_ANGKA_DEPAN, str(_pilihan_angka_depan(varian, bilangan)), "K",
                "Membandingkan angka paling depan saja tanpa melihat banyak angka, "
                "padahal bilangan dengan angka lebih banyak lebih besar."),
        Malrule(ID_TERBALIK, str(_lawan(varian, bilangan)), "H",
                "Tertukar antara terbesar dan terkecil, sehingga memilih ujung yang berlawanan."),
    ]
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, "bilangan": list(bilangan)},
        teks=f"Bilangan {varian} di antara {gabung(ribuan(n) for n in bilangan)} adalah ...",
        kunci=kunci, malrule=saring_malrule(kunci, kandidat),
        pembahasan=_pembahasan(varian, bilangan), bagian="B")


def _acak_bilangan(rng: random.Random, pendek: int, panjang: int) -> list:
    banyak_pendek = rng.choice((1, 2, 3))
    hasil = set()
    while len(hasil) < banyak_pendek:
        hasil.add(rng.randint(10 ** (pendek - 1), 10 ** pendek - 1))
    while len(hasil) < JUMLAH_BILANGAN:
        hasil.add(rng.randint(10 ** (panjang - 1), 10 ** panjang - 1))
    urut = sorted(hasil)
    rng.shuffle(urut)
    return urut


def parameter(rng: random.Random, level: str) -> dict:
    pendek, panjang = PANJANG_PER_LEVEL[level]
    for _ in range(BATAS_UNDI):
        varian = rng.choice(VARIAN)
        bilangan = _acak_bilangan(rng, pendek, panjang)
        if _sah(varian, bilangan):
            return {"varian": varian, "bilangan": bilangan}
    raise RuntimeError(f"{TEMPLATE_ID}: tak ada parameter sah dalam {BATAS_UNDI} percobaan")
