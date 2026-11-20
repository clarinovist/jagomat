"""tambah_kurang_bersusun: penjumlahan dan pengurangan bersusun yang wajib simpan/pinjam.

Setiap soal benar-benar memerlukan menyimpan (penjumlahan) atau meminjam
(pengurangan), supaya kesalahan "lupa menyimpan/meminjam" menghasilkan jawaban
yang berbeda dari kunci. Hasil: P3 sampai 1.000, P4 sampai 10.000, P5 sampai
100.000. Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru.
"""
from __future__ import annotations

import random

from school_numbers_common import (BATAS_UNDI, KURANG, NAMA_TEMPAT, bilangan_bulat,
                                   dari_kolom, kolom, ribuan)
from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "tambah_kurang_bersusun"
VARIAN = ("tambah", "kurang")
BATAS_OPERAN = (10, 99_999)
BATAS_JUMLAH = 100_000
JALUR_K_MINIMUM = 2
# level -> (rentang a, rentang b, batas hasil penjumlahan)
RENTANG_PER_LEVEL = {
    "P3": ((100, 999), (10, 999), 1_000),
    "P4": ((1_000, 9_999), (100, 9_999), 10_000),
    "P5": ((10_000, 99_999), (1_000, 99_999), 100_000),
}
ID_LUPA_MENYIMPAN = TEMPLATE_ID + ".lupa_menyimpan"
ID_TULIS_KOLOM = TEMPLATE_ID + ".tulis_hasil_kolom"
ID_BESAR_KURANG_KECIL = TEMPLATE_ID + ".besar_kurang_kecil"
ID_LUPA_MEMINJAM = TEMPLATE_ID + ".lupa_meminjam"


def _kolom_sejajar(a: int, b: int) -> tuple:
    """Angka a dan b dari satuan ke atas, diisi nol sampai sama panjang."""
    ka, kb = kolom(a), kolom(b)
    n = max(len(ka), len(kb))
    return ka + [0] * (n - len(ka)), kb + [0] * (n - len(kb))


def _ada_simpanan(a: int, b: int) -> bool:
    """Simpanan pertama hanya bisa muncul dari satu kolom yang jumlahnya sudah >= 10."""
    return any(x + y >= 10 for x, y in zip(*_kolom_sejajar(a, b)))


def _ada_pinjaman(a: int, b: int) -> bool:
    """Pinjaman pertama hanya bisa muncul dari satu kolom yang angka atasnya lebih kecil."""
    return any(x < y for x, y in zip(*_kolom_sejajar(a, b)))


def _lupa_menyimpan(a: int, b: int) -> int:
    """Jumlah tiap kolom ditulis satuannya saja; semua simpanan terlupa."""
    return dari_kolom([(x + y) % 10 for x, y in zip(*_kolom_sejajar(a, b))])


def _tulis_hasil_kolom(a: int, b: int) -> int:
    """Hasil tiap kolom ditulis utuh berurutan tanpa menyimpan."""
    x, y = _kolom_sejajar(a, b)
    return int("".join(str(p + q) for p, q in reversed(list(zip(x, y)))))


def _besar_kurang_kecil(a: int, b: int) -> int:
    """Tiap kolom: angka besar dikurangi angka kecil, tanpa meminjam."""
    return dari_kolom([abs(x - y) for x, y in zip(*_kolom_sejajar(a, b))])


def _lupa_meminjam(a: int, b: int) -> int:
    """Menambah 10 pada kolom yang kurang, tetapi kolom di sebelahnya tidak dikurangi 1."""
    return dari_kolom([x + 10 - y if x < y else x - y for x, y in zip(*_kolom_sejajar(a, b))])


def _kunci(varian: str, a: int, b: int) -> int:
    return a + b if varian == "tambah" else a - b


def _kandidat(varian: str, a: int, b: int) -> list:
    if varian == "tambah":
        return [
            Malrule(ID_LUPA_MENYIMPAN, str(_lupa_menyimpan(a, b)), "K",
                    "Lupa menyimpan: hanya satuan tiap kolom yang ditulis, sehingga simpanan hilang."),
            Malrule(ID_TULIS_KOLOM, str(_tulis_hasil_kolom(a, b)), "K",
                    "Menulis hasil tiap kolom utuh (dua angka) berderet tanpa menyimpan ke kolom berikutnya."),
        ]
    return [
        Malrule(ID_BESAR_KURANG_KECIL, str(_besar_kurang_kecil(a, b)), "K",
                "Pada tiap kolom angka besar dikurangi angka kecil, walau angka atasnya lebih kecil, tanpa meminjam."),
        Malrule(ID_LUPA_MEMINJAM, str(_lupa_meminjam(a, b)), "K",
                "Meminjam 10 untuk kolom yang kurang tetapi lupa mengurangi 1 di kolom sebelahnya."),
    ]


def _sah(varian, a, b) -> bool:
    if varian not in VARIAN or not (bilangan_bulat(a) and bilangan_bulat(b)):
        return False
    bawah, atas = BATAS_OPERAN
    if not (bawah <= a <= atas and bawah <= b <= atas):
        return False
    if varian == "tambah":
        sah = a + b <= BATAS_JUMLAH and _ada_simpanan(a, b)
    else:
        sah = a > b and _ada_pinjaman(a, b)
    if not sah:
        return False
    sisa = saring_malrule(str(_kunci(varian, a, b)), _kandidat(varian, a, b))
    return sum(m.kode == "K" for m in sisa) >= JALUR_K_MINIMUM


def _nama(indeks: int) -> str:
    return NAMA_TEMPAT[indeks].capitalize()


def _pembahasan_tambah(a: int, b: int) -> str:
    ka, kb = kolom(a), kolom(b)
    n = max(len(ka), len(kb))
    kalimat, simpan = ["Jumlahkan kolom dari kanan."], 0
    for i in range(n):
        suku = [k[i] for k in (ka, kb) if i < len(k)]
        total = sum(suku) + simpan
        if len(suku) == 1 and not simpan:
            kalimat.append(f"{_nama(i)}: tulis {suku[0]}.")
            continue
        teks = " + ".join(str(d) for d in suku) + (" + 1 (simpanan)" if simpan else "")
        akhir = " dan simpan 1." if total >= 10 else "."
        kalimat.append(f"{_nama(i)}: {teks} = {total}, tulis {total % 10}{akhir}")
        simpan = 1 if total >= 10 else 0
    if simpan:
        kalimat.append(f"Simpanan 1 ditulis di tempat {NAMA_TEMPAT[n]}.")
    kalimat.append(f"Jadi {ribuan(a)} + {ribuan(b)} = {ribuan(a + b)}.")
    return " ".join(kalimat)


def _kolom_kurang(i: int, x: int, y, pinjam: int) -> tuple:
    """(kalimat, pinjam_ke_kolom_berikut) untuk satu kolom pengurangan."""
    nama, atas = _nama(i), NAMA_TEMPAT[i + 1] if i + 1 < len(NAMA_TEMPAT) else ""
    if pinjam and x == 0:
        awal = f"{nama}: 0 sudah dipinjam 1, jadi harus pinjam 1 {atas} dulu: 10 − 1 = 9"
        if y is None:
            return f"{awal}, tulis 9.", 1
        return f"{awal}. Lalu 9 − {y} = {9 - y}.", 1
    sisa = x - pinjam
    if y is None:
        if not pinjam:
            return f"{nama}: tulis {x}.", 0
        return f"{nama}: {x} sudah dipinjam 1 jadi {sisa}, tulis {sisa}.", 0
    depan = f"{x} sudah dipinjam 1 jadi {sisa}, " if pinjam else ""
    if sisa >= y:
        return f"{nama}: {depan}{sisa} {KURANG} {y} = {sisa - y}.", 0
    return (f"{nama}: {depan}{sisa} tidak cukup dikurangi {y}, pinjam 1 {atas} "
            f"sehingga {sisa + 10} {KURANG} {y} = {sisa + 10 - y}."), 1


def _pembahasan_kurang(a: int, b: int) -> str:
    ka, kb = kolom(a), kolom(b)
    kalimat, pinjam = ["Kurangkan kolom dari kanan."], 0
    for i, x in enumerate(ka):
        y = kb[i] if i < len(kb) else None
        teks, pinjam = _kolom_kurang(i, x, y, pinjam)
        kalimat.append(teks)
    kalimat.append(f"Jadi {ribuan(a)} {KURANG} {ribuan(b)} = {ribuan(a - b)}.")
    return " ".join(kalimat)


def tambah_kurang_bersusun(varian: str, a: int, b: int) -> Soal:
    """a + b (wajib ada simpanan) atau a - b (wajib ada pinjaman), ditulis bersusun."""
    if not _sah(varian, a, b):
        raise ValueError("parameter penjumlahan/pengurangan bersusun di luar domain")
    kunci = str(_kunci(varian, a, b))
    tanda = "+" if varian == "tambah" else KURANG
    pembahasan = _pembahasan_tambah(a, b) if varian == "tambah" else _pembahasan_kurang(a, b)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, "a": a, "b": b},
        teks=f"Hitung dengan cara bersusun: {ribuan(a)} {tanda} {ribuan(b)} = ...",
        kunci=kunci, malrule=saring_malrule(kunci, _kandidat(varian, a, b)),
        pembahasan=pembahasan, bagian="C")


def parameter(rng: random.Random, level: str) -> dict:
    (a_bawah, a_atas), (b_bawah, b_atas), batas = RENTANG_PER_LEVEL[level]
    for _ in range(BATAS_UNDI):
        varian = rng.choice(VARIAN)
        a, b = rng.randint(a_bawah, a_atas), rng.randint(b_bawah, b_atas)
        if varian == "tambah" and a + b > batas:
            continue
        if _sah(varian, a, b):
            return {"varian": varian, "a": a, "b": b}
    raise RuntimeError(f"{TEMPLATE_ID}: tak ada parameter sah dalam {BATAS_UNDI} percobaan")
