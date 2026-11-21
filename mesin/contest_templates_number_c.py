"""Template topik Bilangan untuk Latihan Lomba, bagian cacah bilangan (id berawalan `bil_`).

Diimpor dari `contest_templates_number`; jangan diimpor sendiri. Verifikator menghitung ulang
dengan enumerasi semua bilangan 10..99 atau 100..999, bukan dengan loop angka yang dipakai `bangun`.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Mapping, Sequence

import contest_core as C
from contest_templates_number_b import TOPIK, soal_bilangan

SYARAT_KUNCI_MIN = 2


def _jumlah_angka(n: int) -> int:
    return sum(int(c) for c in str(n))


# --- 7. bil_cacah_syarat -----------------------------------------------------------------

SYARAT_TEKS = {
    "puluhan_lebih": "angka puluhannya lebih besar dari angka satuannya",
    "satuan_lebih": "angka satuannya lebih besar dari angka puluhannya",
    "jumlah_k": "jumlah kedua angkanya {k}",
    "keduanya_ganjil": "kedua angkanya ganjil",
    "kembar": "kedua angkanya sama",
}

# (syarat sebenarnya, syarat longgar yang menjadi kesalahan khas)
SYARAT_PREDIKAT: Dict[str, Callable[[int, int, int], bool]] = {
    "puluhan_lebih": lambda t, s, k: t > s,
    "satuan_lebih": lambda t, s, k: s > t,
    "jumlah_k": lambda t, s, k: t + s == k,
    "keduanya_ganjil": lambda t, s, k: t % 2 == 1 and s % 2 == 1,
    "kembar": lambda t, s, k: t == s,
}
SYARAT_LONGGAR: Dict[str, Callable[[int, int, int], bool]] = {
    "puluhan_lebih": lambda t, s, k: t >= s,
    "satuan_lebih": lambda t, s, k: s >= t,
    "jumlah_k": lambda t, s, k: t + s >= k,
    "keduanya_ganjil": lambda t, s, k: t % 2 == 1 or s % 2 == 1,
    "kembar": lambda t, s, k: abs(t - s) <= 1,
}
SYARAT_LABEL_LONGGAR = {
    "puluhan_lebih": "ikut menghitung bilangan yang angkanya sama (memakai lebih besar atau sama dengan)",
    "satuan_lebih": "ikut menghitung bilangan yang angkanya sama (memakai lebih besar atau sama dengan)",
    "jumlah_k": "menghitung bilangan yang jumlah angkanya k atau lebih",
    "keduanya_ganjil": "menghitung bilangan yang cukup satu angkanya ganjil",
    "kembar": "ikut menghitung bilangan yang angkanya hampir sama (selisih satu)",
}


def _sampler_cacah_syarat(rng) -> Dict:
    syarat = rng.choice(sorted(SYARAT_TEKS))
    a = rng.randint(10, 40)
    b = rng.randint(a + 20, 99)
    p = {"syarat": syarat, "a": a, "b": b}
    if syarat == "jumlah_k":
        p["k"] = rng.randint(5, 12)
    return p


def _cacah(a: int, b: int, predikat: Callable[[int, int, int], bool], k: int) -> List[int]:
    return [n for n in range(a, b + 1) if predikat(*divmod(n, 10), k)]


def _langkah_cacah(a: int, b: int, cocok: Sequence[int]) -> List[str]:
    per_puluhan: Dict[int, List[str]] = {}
    for n in cocok:
        per_puluhan.setdefault(n // 10, []).append(str(n))
    daftar = "; ".join(f"puluhan {t}: {', '.join(isi)}" for t, isi in sorted(per_puluhan.items()))
    return [
        f"Periksa angka puluhan dan satuan setiap bilangan dari {a} sampai {b}; "
        f"bilangan {a} dan {b} ikut diperiksa.",
        f"Yang memenuhi: {daftar}.",
        f"Banyaknya {len(cocok)}. Jadi ada {len(cocok)} bilangan.",
    ]


def _bangun_cacah_syarat(p: Mapping) -> C.SoalLomba:
    syarat, a, b = p["syarat"], p["a"], p["b"]
    k = p.get("k", 0)
    cocok = _cacah(a, b, SYARAT_PREDIKAT[syarat], k)
    ujung_cocok = any(SYARAT_PREDIKAT[syarat](*divmod(n, 10), k) for n in (a, b))
    if not ujung_cocok or len(cocok) < SYARAT_KUNCI_MIN:
        raise C.ParameterTidakSah("batas tidak memenuhi syarat atau kunci terlalu kecil")
    kunci = str(len(cocok))
    longgar = _cacah(a, b, SYARAT_LONGGAR[syarat], k)
    tanpa_batas = _cacah(a + 1, b - 1, SYARAT_PREDIKAT[syarat], k)
    kandidat = [
        C.Pengecoh(str(len(tanpa_batas)), f"lupa menghitung bilangan batas ({a} atau {b})"),
        C.Pengecoh(str(len(longgar)), SYARAT_LABEL_LONGGAR[syarat]),
        C.Pengecoh(str(b - a + 1), "menghitung semua bilangan tanpa memeriksa syarat"),
        C.Pengecoh(str(len(cocok) + 1), "salah hitung lebih satu"),
        C.Pengecoh(str(len(cocok) - 1), "salah hitung kurang satu"),
    ]
    pengecoh = C.ambil_pengecoh(kunci, kandidat)
    teks = (f"Ada berapa bilangan dari {a} sampai {b} yang "
            f"{SYARAT_TEKS[syarat].format(k=k)}?")
    return soal_bilangan("bil_cacah_syarat", C.JENIS_PG, 3, teks, "", kunci, pengecoh,
                 _langkah_cacah(a, b, cocok), p)


def _verifikator_cacah_syarat(p: Mapping) -> str:
    hitung = 0
    for n in range(p["a"], p["b"] + 1):
        t, s = int(str(n)[0]), int(str(n)[1])
        if p["syarat"] == "puluhan_lebih":
            ok = t > s
        elif p["syarat"] == "satuan_lebih":
            ok = s > t
        elif p["syarat"] == "jumlah_k":
            ok = t + s == p["k"]
        elif p["syarat"] == "keduanya_ganjil":
            ok = t in (1, 3, 5, 7, 9) and s in (1, 3, 5, 7, 9)
        else:
            ok = str(n)[0] == str(n)[1]
        hitung += 1 if ok else 0
    return str(hitung)


# --- 8. bil_dua_angka_jumlah -------------------------------------------------------------

SYARAT_TAMBAHAN_TEKS = {
    "tanpa": "",
    "genap": " dan bilangannya genap",
    "ganjil": " dan bilangannya ganjil",
    "berbeda": " dan kedua angkanya berbeda",
}
NAMA_BANYAK_ANGKA = {2: "dua", 3: "tiga"}
NAMA_SEMUA_ANGKA = {2: "kedua", 3: "ketiga"}
K_MAKS = {2: 13, 3: 6}
K_MIN = 2


def _sampler_dua_angka_jumlah(rng) -> Dict:
    banyak = rng.choice((2, 2, 3))
    syarat = rng.choice(sorted(SYARAT_TAMBAHAN_TEKS))
    if banyak == 3 and syarat == "berbeda":
        syarat = "tanpa"
    return {"angka": banyak, "k": rng.randint(K_MIN, K_MAKS[banyak]), "syarat": syarat}


def _daftar_bilangan(banyak: int, k: int, syarat: str) -> List[int]:
    """Semua bilangan `banyak` angka berjumlah angka k yang memenuhi syarat tambahan."""
    hasil: List[int] = []
    for depan in range(1, 10):
        for tengah in (range(10) if banyak == 3 else (None,)):
            for belakang in range(10):
                angka = [depan] + ([] if tengah is None else [tengah]) + [belakang]
                if sum(angka) != k:
                    continue
                if syarat == "genap" and belakang % 2:
                    continue
                if syarat == "ganjil" and belakang % 2 == 0:
                    continue
                if syarat == "berbeda" and len(set(angka)) != len(angka):
                    continue
                hasil.append(int("".join(map(str, angka))))
    return hasil


def _langkah_dua_angka(banyak: int, daftar: Sequence[int], kunci: str) -> List[str]:
    if banyak == 2:
        isi = [f"Bilangan yang memenuhi: {', '.join(map(str, daftar))}."]
    else:
        per_depan: Dict[int, List[str]] = {}
        for n in daftar:
            per_depan.setdefault(n // 100, []).append(str(n))
        isi = [f"Angka depan {depan}: {', '.join(nilai)}." for depan, nilai in sorted(per_depan.items())]
    return isi + [f"Banyaknya {kunci}. Jadi jawabannya {kunci}."]


def _bangun_dua_angka_jumlah(p: Mapping) -> C.SoalLomba:
    banyak, k, syarat = p["angka"], p["k"], p["syarat"]
    daftar = _daftar_bilangan(banyak, k, syarat)
    if len(daftar) < SYARAT_KUNCI_MIN:
        raise C.ParameterTidakSah("bilangan yang memenuhi terlalu sedikit")
    kunci = str(len(daftar))
    teks = (f"Ada berapa bilangan {NAMA_BANYAK_ANGKA[banyak]} angka yang jumlah "
            f"{NAMA_SEMUA_ANGKA[banyak]} angkanya {k}{SYARAT_TAMBAHAN_TEKS[syarat]}? "
            f"Jawab dengan banyak bilangan.")
    return soal_bilangan("bil_dua_angka_jumlah", C.JENIS_ISIAN, 2, teks, "", kunci, (),
                 _langkah_dua_angka(banyak, daftar, kunci), p)


def _verifikator_dua_angka_jumlah(p: Mapping) -> str:
    awal, akhir = (10, 100) if p["angka"] == 2 else (100, 1000)
    hitung = 0
    for n in range(awal, akhir):
        teks = str(n)
        if _jumlah_angka(n) != p["k"]:
            continue
        if p["syarat"] == "genap" and n % 2 != 0:
            continue
        if p["syarat"] == "ganjil" and n % 2 != 1:
            continue
        if p["syarat"] == "berbeda" and len(set(teks)) != len(teks):
            continue
        hitung += 1
    return str(hitung)


C.daftarkan(C.Template(id="bil_cacah_syarat", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
                       sampler=_sampler_cacah_syarat, bangun=_bangun_cacah_syarat,
                       verifikator=_verifikator_cacah_syarat))
C.daftarkan(C.Template(id="bil_dua_angka_jumlah", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=2,
                       sampler=_sampler_dua_angka_jumlah, bangun=_bangun_dua_angka_jumlah,
                       verifikator=_verifikator_dua_angka_jumlah))
