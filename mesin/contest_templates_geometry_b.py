"""Template topik Bangun Datar/Ruang untuk Latihan Lomba (bagian 2: tingkat 2-3, ruang dan hitung bangun).

Dimuat dari `contest_templates_geometry.py`. Isi: `bgn_rusuk_titik_sisi`, `bgn_persegi_kisi`,
`bgn_segitiga_diagonal`, `bgn_kubus_berlapis`. Verifikator selalu menghitung ulang dengan
enumerasi (titik sudut dan rusuk kubus 0/1, semua posisi persegi, semua tiga titik pada gambar).
"""
from __future__ import annotations

import random
from fractions import Fraction
from itertools import combinations, product
from math import gcd
from typing import List, Mapping, Optional, Sequence, Tuple

import contest_core as C
import contest_svg_geometry as G
import design_tokens as T
from contest_templates_geometry import TOPIK, nama_dari

MINUS = "−"
KELAS_SIFAT = ("rusuk", "titik sudut", "sisi")
BANGUN_RUANG = ("balok", "kubus")
SIFAT_RUANG = {"rusuk": 12, "titik sudut": 8, "sisi": 6}     # balok dan kubus sama
PETA_SALAH = (
    ("menukar banyak rusuk dengan banyak titik sudut", {"rusuk": 8, "titik sudut": 12, "sisi": 6}),
    ("menukar banyak rusuk dengan banyak sisi", {"rusuk": 6, "titik sudut": 8, "sisi": 12}),
    ("menukar banyak titik sudut dengan banyak sisi", {"rusuk": 12, "titik sudut": 6, "sisi": 8}),
)
SISI_SAMPING = 4


# ------------------------------------------------------------ bgn_rusuk_titik_sisi
def _hitung_suku(suku: Sequence[Sequence[str]], tanda: Sequence[int], tabel: Mapping[str, int],
                 banyak: int = 3) -> int:
    total = tabel[suku[0][0]]
    for tanda_i, (sifat, _) in zip(tanda[:banyak - 1], suku[1:banyak]):
        total += tanda_i * tabel[sifat]
    return total


def _sampler_rusuk_titik_sisi(rng: random.Random) -> Mapping:
    semua = [[sifat, bangun] for sifat in KELAS_SIFAT for bangun in BANGUN_RUANG]
    suku = rng.sample(semua, 3)
    tanda = [rng.choice((1, -1)), rng.choice((1, -1))]
    if _hitung_suku(suku, tanda, SIFAT_RUANG, 2) < 1 or _hitung_suku(suku, tanda, SIFAT_RUANG) < 1:
        raise C.ParameterTidakSah("hasil antara atau akhir tidak positif")
    return {"suku": suku, "tanda": tanda}


def _ekspresi(suku: Sequence[Sequence[str]], tanda: Sequence[int]) -> str:
    bagian = [f"banyak {s} {b}" for s, b in suku]
    simbol = ["+" if t > 0 else MINUS for t in tanda]
    return f"{bagian[0]} {simbol[0]} {bagian[1]} {simbol[1]} {bagian[2]}"


def _bangun_rusuk_titik_sisi(p: Mapping) -> C.SoalLomba:
    suku, tanda = p["suku"], p["tanda"]
    hasil = _hitung_suku(suku, tanda, SIFAT_RUANG)
    kunci = str(hasil)
    kandidat = [C.Pengecoh(str(_hitung_suku(suku, tanda, peta)), salah) for salah, peta in PETA_SALAH]
    kandidat.append(C.Pengecoh(str(_hitung_suku(suku, tanda, SIFAT_RUANG, 2)),
                               "lupa menghitung suku terakhir"))
    kandidat.append(C.Pengecoh(str(sum(SIFAT_RUANG[s] for s, _ in suku)),
                               "mengabaikan tanda kurang: semua suku dijumlahkan"))
    kandidat.append(C.Pengecoh(str(_hitung_suku(suku, tanda, dict(SIFAT_RUANG, sisi=SISI_SAMPING))),
                               "mengira sisi balok dan kubus hanya 4 (sisi samping saja)"))
    kandidat.append(C.Pengecoh(str(SIFAT_RUANG[suku[0][0]]), "hanya menghitung suku pertama"))
    kandidat.append(C.Pengecoh(str(_hitung_suku(suku, [-t for t in tanda], SIFAT_RUANG)),
                               "membalik tanda tambah dan kurang"))
    nilai_suku = [SIFAT_RUANG[s] for s, _ in suku]
    rumus = f"{nilai_suku[0]} {'+' if tanda[0] > 0 else MINUS} {nilai_suku[1]} " \
            f"{'+' if tanda[1] > 0 else MINUS} {nilai_suku[2]} = {hasil}"
    nilai_teks = ", ".join(f"banyak {s} {b} = {SIFAT_RUANG[s]}" for s, b in suku)
    return C.SoalLomba(
        template_id="bgn_rusuk_titik_sisi", topik=TOPIK, jenis=C.JENIS_PG, tingkat=2,
        teks=f"{_ekspresi(suku, tanda).capitalize()} = ...", svg=G.gambar_balok_dan_kubus(),
        kunci=kunci, pengecoh=C.ambil_pengecoh(kunci, kandidat),
        pembahasan=("Balok dan kubus sama-sama mempunyai 12 rusuk, 8 titik sudut, dan 6 sisi.",
                    f"{nilai_teks.capitalize()}.", rumus, f"Jadi hasilnya {kunci}."),
        parameter=C.kanonik(p), nilai=hasil)


def _sifat_kotak_verif() -> Mapping[str, int]:
    """Balok/kubus sebagai titik 0/1 pada tiga sumbu: titik sudut, rusuk, dan sisi dihitung langsung."""
    titik = list(product((0, 1), repeat=3))
    rusuk = sum(1 for a, b in combinations(titik, 2) if sum(x != y for x, y in zip(a, b)) == 1)
    sisi = sum(1 for sumbu in range(3) for nilai in (0, 1)
               if sum(1 for t in titik if t[sumbu] == nilai) == 4)
    return {"rusuk": rusuk, "titik sudut": len(titik), "sisi": sisi}


def _verifikator_rusuk_titik_sisi(p: Mapping) -> str:
    sifat = _sifat_kotak_verif()
    nilai = [sifat[s] for s, _ in p["suku"]]
    return str(nilai[0] + p["tanda"][0] * nilai[1] + p["tanda"][1] * nilai[2])


# ------------------------------------------------------------ bgn_persegi_kisi
UKURAN_KISI_MIN, UKURAN_KISI_MAKS = 2, 5
TEKS_KISI = {
    "semua": "Berapa banyak semua persegi (kecil dan besar) pada papan ini?",
    "besar": "Berapa banyak persegi besar pada papan ini? Persegi besar adalah persegi yang tersusun "
             "dari lebih dari 1 kotak kecil.",
    "dua": "Berapa banyak persegi yang tersusun dari 4 kotak kecil (2 x 2) pada papan ini? "
           "Persegi yang saling menumpuk tetap dihitung.",
}
UKURAN_PERSEGI = {"semua": (1, None), "besar": (2, None), "dua": (2, 2)}   # (terkecil, terbesar atau None)
TEKS_TITIK_TEMU = "mengalikan (baris + 1) dengan (kolom + 1), yaitu titik pertemuan garis"


def _sampler_persegi_kisi(rng: random.Random) -> Mapping:
    return {"baris": rng.randint(UKURAN_KISI_MIN, UKURAN_KISI_MAKS),
            "kolom": rng.randint(UKURAN_KISI_MIN, UKURAN_KISI_MAKS), "mode": rng.choice(sorted(TEKS_KISI))}


def _kandidat_kisi(mode: str, m: int, n: int, hasil: int, per_ukuran: Mapping[int, int]) -> List[C.Pengecoh]:
    terbesar = per_ukuran[min(m, n)]
    if mode == "semua":
        return [
            C.Pengecoh(str(m * n), "hanya menghitung persegi kecil"),
            C.Pengecoh(str(m * n + terbesar), "menghitung persegi kecil dan yang terbesar saja"),
            C.Pengecoh(str((m + 1) * (n + 1)), TEKS_TITIK_TEMU),
            C.Pengecoh(str(2 * m * n), "mengira persegi besar sama banyak dengan persegi kecil"),
            C.Pengecoh(str(hasil - terbesar), "lupa persegi yang paling besar"),
            C.Pengecoh(str(m * n + m + n), "menghitung juga tiap baris dan tiap kolom sebagai persegi"),
        ]
    if mode == "besar":
        return [
            C.Pengecoh(str(hasil + m * n), "ikut menghitung persegi kecil"),
            C.Pengecoh(str(m * n), "menghitung kotak kecil, bukan persegi besar"),
            C.Pengecoh(str(per_ukuran[2]), "hanya menghitung persegi yang tersusun dari 4 kotak"),
            C.Pengecoh(str(terbesar), "hanya menghitung persegi yang paling besar"),
            C.Pengecoh(str((m + 1) * (n + 1)), TEKS_TITIK_TEMU),
        ]
    return [
        C.Pengecoh(str((m // 2) * (n // 2)), "hanya menghitung persegi 2 x 2 yang tidak saling menumpuk"),
        C.Pengecoh(str(m * n), "menghitung kotak kecil, bukan persegi 2 x 2"),
        C.Pengecoh(str(m * n // 4), "membagi banyak kotak dengan 4"),
        C.Pengecoh(str((m + 1) * (n + 1)), TEKS_TITIK_TEMU),
        C.Pengecoh(str(hasil + m * n), "ikut menghitung persegi kecil"),
    ]


def _bangun_persegi_kisi(p: Mapping) -> C.SoalLomba:
    m, n, mode = p["baris"], p["kolom"], p["mode"]
    kecil, besar = UKURAN_PERSEGI[mode]
    ukuran = [k for k in range(1, min(m, n) + 1) if k >= kecil and (besar is None or k <= besar)]
    per_ukuran = {k: (m - k + 1) * (n - k + 1) for k in range(1, min(m, n) + 1)}
    hasil = sum(per_ukuran[k] for k in ukuran)
    kunci = str(hasil)
    langkah = [f"Hitung persegi menurut ukurannya, mulai dari {kecil} x {kecil}."]
    langkah += [f"Persegi {k} x {k}: {m - k + 1} x {n - k + 1} = {per_ukuran[k]} buah." for k in ukuran]
    if len(ukuran) > 1:
        langkah.append(" + ".join(str(per_ukuran[k]) for k in ukuran) + f" = {hasil}")
    langkah.append(f"Jadi ada {kunci} persegi.")
    sel = [[r, c] for r in range(m) for c in range(n)]
    return C.SoalLomba(
        template_id="bgn_persegi_kisi", topik=TOPIK, jenis=C.JENIS_PG, tingkat=3,
        teks=TEKS_KISI[mode], svg=G.gambar_sel(sel, T.GEO_LOMBA_KREM, "Gambar papan kotak-kotak",
                                               baris=m, kolom=n),
        kunci=kunci, pengecoh=C.ambil_pengecoh(kunci, _kandidat_kisi(mode, m, n, hasil, per_ukuran)),
        pembahasan=tuple(langkah), parameter=C.kanonik(p), nilai=hasil)


def _verifikator_persegi_kisi(p: Mapping) -> str:
    papan = {(r, c) for r in range(p["baris"]) for c in range(p["kolom"])}
    kecil, besar = UKURAN_PERSEGI[p["mode"]]
    cacah = 0
    for r, c in papan:
        for sisi in range(kecil, (besar or max(p["baris"], p["kolom"])) + 1):
            if all((r + i, c + j) in papan for i in range(sisi) for j in range(sisi)):
                cacah += 1
    return str(cacah)


# ------------------------------------------------------------ bgn_segitiga_diagonal
UKURAN_GAMBAR_GARIS = ((1, 1), (2, 1), (2, 2), (3, 1))
GARIS_DALAM_MIN, GARIS_DALAM_MAKS = 1, 4
SEGITIGA_MIN, SEGITIGA_MAKS = 2, 24
Ruas = Tuple[int, int, int, int]


def _tepi(w: int, h: int) -> List[Ruas]:
    return [(0, 0, w, 0), (w, 0, w, h), (w, h, 0, h), (0, h, 0, 0)]


def _kandidat_garis(w: int, h: int) -> List[Ruas]:
    ruas = {(0, 0, w, h), (0, h, w, 0)}
    ruas |= {(i, 0, i, h) for i in range(1, w)} | {(0, j, w, j) for j in range(1, h)}
    for i in range(w):
        for j in range(h):
            ruas |= {(i, j, i + 1, j + 1), (i, j + 1, i + 1, j)}
    return sorted(ruas)


def _kunci_garis(ruas: Ruas) -> Tuple[int, int, int]:
    """Persamaan garis pendukung ruas (a x + b y = c) yang dinormalkan, untuk mendeteksi garis sejajar-berimpit."""
    x1, y1, x2, y2 = ruas
    a, b = y2 - y1, x1 - x2
    c = a * x1 + b * y1
    d = gcd(gcd(abs(a), abs(b)), abs(c)) or 1
    a, b, c = a // d, b // d, c // d
    return (-a, -b, -c) if (a < 0 or (a == 0 and b < 0)) else (a, b, c)


def _potong(r1: Ruas, r2: Ruas) -> Optional[Tuple[Fraction, Fraction]]:
    x1, y1, x2, y2 = r1
    x3, y3, x4, y4 = r2
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if d == 0:
        return None
    t = Fraction((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3), d)
    u = Fraction((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1), d)
    if not (0 <= t <= 1 and 0 <= u <= 1):
        return None
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def segitiga_dari_ruas(ruas: Sequence[Ruas]) -> List[Fraction]:
    """Luas dua kali tiap segitiga: tiga ruas berbeda yang berpotongan di tiga titik berlainan."""
    hasil = []
    for a, b, c in combinations(ruas, 3):
        titik = [_potong(a, b), _potong(b, c), _potong(a, c)]
        if None in titik or len(set(titik)) < 3:
            continue
        (xa, ya), (xb, yb), (xc, yc) = titik
        hasil.append(abs((xb - xa) * (yc - ya) - (yb - ya) * (xc - xa)))
    return hasil


def _sampler_segitiga_diagonal(rng: random.Random) -> Mapping:
    w, h = rng.choice(UKURAN_GAMBAR_GARIS)
    kandidat = _kandidat_garis(w, h)
    pilih = rng.sample(kandidat, rng.randint(GARIS_DALAM_MIN, min(GARIS_DALAM_MAKS, len(kandidat))))
    if len({_kunci_garis(r) for r in pilih}) < len(pilih):
        raise C.ParameterTidakSah("dua garis dalam berada pada garis pendukung yang sama")
    if not SEGITIGA_MIN <= len(segitiga_dari_ruas(_tepi(w, h) + pilih)) <= SEGITIGA_MAKS:
        raise C.ParameterTidakSah("banyak segitiga di luar rentang soal")
    return {"w": w, "h": h, "garis": [list(r) for r in sorted(pilih)]}


def _bangun_segitiga_diagonal(p: Mapping) -> C.SoalLomba:
    w, h = p["w"], p["h"]
    luas = sorted(segitiga_dari_ruas(_tepi(w, h) + [tuple(r) for r in p["garis"]]))
    total = len(luas)
    kelompok = [luas.count(nilai) for nilai in sorted(set(luas))]
    rincian = ", ".join(f"ukuran ke-{i + 1}: {n} buah" for i, n in enumerate(kelompok))
    bentuk = "persegi" if w == h else "persegi panjang"
    return C.SoalLomba(
        template_id="bgn_segitiga_diagonal", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=3,
        teks=f"Gambar ini berbentuk {bentuk} dan diberi beberapa garis di dalamnya. "
             f"Ada berapa segitiga semuanya (yang kecil dan yang besar)? Tulis banyaknya saja.",
        svg=G.diagram_garis(w, h, p["garis"]), kunci=str(total), pengecoh=(),
        pembahasan=("Hitung segitiga menurut ukurannya, mulai dari yang paling kecil.", f"Banyaknya: {rincian}.",
                    " + ".join(str(n) for n in kelompok) + f" = {total}", f"Jadi ada {total} segitiga."),
        parameter=C.kanonik(p), nilai=total)


def _titik_garis(a: Ruas, b: Ruas) -> Optional[Tuple[Fraction, Fraction]]:
    """Perpotongan dua garis (aturan Cramer pada a x + b y = c), lalu diperiksa berada di kedua ruas."""
    (p1, q1, p2, q2), (p3, q3, p4, q4) = a, b
    a1, b1, c1 = q2 - q1, p1 - p2, (q2 - q1) * p1 + (p1 - p2) * q1
    a2, b2, c2 = q4 - q3, p3 - p4, (q4 - q3) * p3 + (p3 - p4) * q3
    det = a1 * b2 - a2 * b1
    if det == 0:
        return None
    x, y = Fraction(c1 * b2 - c2 * b1, det), Fraction(a1 * c2 - a2 * c1, det)
    return (x, y) if _di_ruas(x, y, a) and _di_ruas(x, y, b) else None


def _di_ruas(x, y, ruas: Ruas) -> bool:
    x1, y1, x2, y2 = ruas
    sejajar = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1) == 0
    return sejajar and min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def _verifikator_segitiga_diagonal(p: Mapping) -> str:
    ruas = _tepi(p["w"], p["h"]) + [tuple(r) for r in p["garis"]]
    titik = {(Fraction(r[0]), Fraction(r[1])) for r in ruas} | {(Fraction(r[2]), Fraction(r[3])) for r in ruas}
    for a, b in combinations(ruas, 2):
        potongan = _titik_garis(a, b)
        if potongan is not None:
            titik.add(potongan)
    terhubung = set()
    for r in ruas:
        di_garis = [t for t in titik if _di_ruas(t[0], t[1], r)]
        terhubung |= {frozenset(pasang) for pasang in combinations(di_garis, 2)}
    cacah = 0
    for a, b, c in combinations(sorted(titik), 3):
        lurus = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) == 0
        if not lurus and {frozenset((a, b)), frozenset((b, c)), frozenset((a, c))} <= terhubung:
            cacah += 1
    return str(cacah)


# ------------------------------------------------------------ bgn_kubus_berlapis
LAPIS_MIN, LAPIS_MAKS = 2, 5
UKURAN_LAPISAN_MIN, UKURAN_LAPISAN_MAKS = 2, 5


def _sampler_kubus_berlapis(rng: random.Random) -> Mapping:
    return {"baris": rng.randint(UKURAN_LAPISAN_MIN, UKURAN_LAPISAN_MAKS),
            "kolom": rng.randint(UKURAN_LAPISAN_MIN, UKURAN_LAPISAN_MAKS),
            "lapis": rng.randint(LAPIS_MIN, LAPIS_MAKS)}


def _bangun_kubus_berlapis(p: Mapping) -> C.SoalLomba:
    a, b, n = p["baris"], p["kolom"], p["lapis"]
    per_lapis = a * b
    total = per_lapis * n
    return C.SoalLomba(
        template_id="bgn_kubus_berlapis", topik=TOPIK, jenis=C.JENIS_ISIAN, tingkat=3,
        teks=f"{nama_dari(per_lapis + n)} menyusun kubus-kubus kecil. Gambar ini adalah lapisan paling bawah. "
             f"Ada {n} lapisan yang sama persis, ditumpuk ke atas. Berapa kubus kecil semuanya?",
        svg=G.gambar_lapisan_kubus(a, b), kunci=str(total), pengecoh=(),
        pembahasan=(f"Lapisan bawah: {a} baris, tiap baris {b} kubus.", f"{a} x {b} = {per_lapis} kubus tiap lapisan.",
                    f"{per_lapis} x {n} = {total}", f"Jadi ada {total} kubus kecil."),
        parameter=C.kanonik(p), nilai=total)


def _verifikator_kubus_berlapis(p: Mapping) -> str:
    cacah = 0
    for _ in range(p["lapis"]):
        for _ in range(p["baris"]):
            cacah += p["kolom"]
    return str(cacah)


for _id, _jenis, _tingkat, _sampler, _bangun, _verif in (
        ("bgn_rusuk_titik_sisi", C.JENIS_PG, 2, _sampler_rusuk_titik_sisi, _bangun_rusuk_titik_sisi,
         _verifikator_rusuk_titik_sisi),
        ("bgn_persegi_kisi", C.JENIS_PG, 3, _sampler_persegi_kisi, _bangun_persegi_kisi, _verifikator_persegi_kisi),
        ("bgn_segitiga_diagonal", C.JENIS_ISIAN, 3, _sampler_segitiga_diagonal, _bangun_segitiga_diagonal,
         _verifikator_segitiga_diagonal),
        ("bgn_kubus_berlapis", C.JENIS_ISIAN, 3, _sampler_kubus_berlapis, _bangun_kubus_berlapis,
         _verifikator_kubus_berlapis)):
    C.daftarkan(C.Template(id=_id, topik=TOPIK, jenis=_jenis, tingkat=_tingkat,
                           sampler=_sampler, bangun=_bangun, verifikator=_verif))
