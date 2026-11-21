"""Matematika Awal, jenis `pecahan_senilai_desimal` (P4): pecahan, pecahan senilai, desimal, persen.

Menutup tiga sub-materi bab Kelas 4 B2 "Pecahan": pecahan berpembilang satu, pecahan
senilai, serta pecahan-desimal-persen. Soal teks saja, enam bentuk (`varian`):
  - `bagian_dari`: "Rina memiliki 20 kelereng. 1/4 dari kelereng itu diberikan kepada Budi.
    Banyak kelereng yang diberikan ada ... butir." (penyebut 2, 3, 4, 5, 10; kunci angka);
  - `senilai_isi`: "2/3 = .../12" (kunci: pembilang baru, angka);
  - `senilai_sederhana`: "Pecahan senilai dengan 6/9 yang paling sederhana adalah ..."
    (kunci pecahan "2/3");
  - `ke_desimal`: "Pecahan 3/4 jika ditulis sebagai desimal adalah ..." (penyebut 2, 4, 5,
    10, 20, 25, 100; kunci desimal koma "0,75");
  - `ke_persen`: "3/4 = ... %" (penyebut 2, 4, 5, 10, 20, 25; kunci angka persen tanpa tanda);
  - `desimal_ke_pecahan`: "Desimal 0,25 jika ditulis sebagai pecahan paling sederhana
    adalah ..." (kunci tunggal pecahan paling sederhana "1/4").

Konvensi kunci. Desimal memakai KOMA dan bentuk paling ringkas tanpa nol di belakang
("0,5", bukan "0,50"; "0,25"), sama seperti kunci desimal template lain yang dinormalisasi
`diagnosis.normalisasi` (koma menjadi titik). Pecahan memakai teks "a/b" paling sederhana
seperti `pecahan_kali_bagi`; pembanding bawaan membandingkan teks ternormalisasi, jadi "2/4"
TIDAK sama dengan "1/2" (itu memang yang diminta pada `senilai_sederhana`). Persen berupa
angka polos tanpa tanda "%". Pembanding bawaan juga tidak menyamakan "0,50" dengan "0,5";
ini keterbatasan yang sama dengan template desimal lain.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu
jawaban: pembilang dan penyebut tertukar, hanya pembilang yang dikalikan atau diabaikan,
pembilang dibaca sebagai persen, titik desimal salah tempat (semuanya K); salah hitung
berupa menjawab bagian yang tersisa atau pecahan yang belum paling sederhana (H). Tidak ada
malrule K yang bernilai sama dengan kunci (dijaga tes menurut nilai); satu-satunya yang
sengaja bernilai sama adalah H "belum paling sederhana". Tiap parameter sah menyisakan minimal satu jalur K dan minimal dua pengecoh berbeda nilai.

Domain kecil dan eksplisit (`domain_parameter`): sampler memilih `varian` seragam dulu, lalu satu
parameter seragam dalam varian itu, semuanya dari `rng` (tanpa `hash()`). Daftar `BENDA`
bersifat APPEND-ONLY menurut indeks: indeks ikut identitas soal di bank.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from math import gcd
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "pecahan_senilai_desimal"
LEVEL = ("P4",)
VARIAN = ("bagian_dari", "senilai_isi", "senilai_sederhana", "ke_desimal", "ke_persen",
          "desimal_ke_pecahan")
PESAN_LUAR_DOMAIN = "parameter pecahan senilai desimal di luar domain"

# APPEND-ONLY menurut indeks: (benda, satuan, pemilik, penerima).
BENDA = (
    ("kelereng", "butir", "Rina", "Budi"),
    ("permen", "butir", "Dita", "Eko"),
    ("apel", "buah", "Budi", "Rina"),
)
PENYEBUT_BAGIAN = (2, 3, 4, 5, 10)
HASIL_BAGIAN = tuple(range(2, 10))
FAKTOR = (2, 3, 4, 5)
BATAS_PENYEBUT_SENILAI = 24
# Pecahan paling sederhana (pembilang, penyebut) untuk pecahan senilai.
SEDERHANA = ((1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (1, 5), (2, 5), (3, 5), (4, 5),
             (1, 6), (5, 6))
# Penyebut -> pembilang yang dipakai (semua saling prima dengan penyebutnya).
PEMBILANG_DESIMAL = {
    2: (1,), 4: (1, 3), 5: (1, 2, 3, 4), 10: (1, 3, 7, 9),
    20: (1, 3, 7, 9, 11, 13, 17, 19), 25: (1, 2, 3, 4, 6, 7, 8, 9),
    100: (7, 9, 23, 37, 49, 63, 81, 91),
}
PEMBILANG_PERSEN = {k: v for k, v in PEMBILANG_DESIMAL.items() if k != 100}
# Desimal (dalam seperseratus) untuk desimal_ke_pecahan: pecahan paling sederhananya punya
# penyebut 2, 4, 5, 10, atau 20 dan pembilangnya bukan 1 hanya bila perlu.
SERATUS_DESIMAL = (50, 25, 75, 20, 40, 60, 80, 30, 70, 90, 5, 15, 35, 45, 65, 85, 95)

BIDANG = {
    "bagian_dari": ("d", "k", "benda"),
    "senilai_isi": ("a", "b", "f"),
    "senilai_sederhana": ("a", "b", "f"),
    "ke_desimal": ("n", "d"),
    "ke_persen": ("n", "d"),
    "desimal_ke_pecahan": ("perseratus",),
}


# ── hitungan murni ───────────────────────────────────────────────────────

def _desimal(nilai: Fraction) -> str:
    """Desimal koma paling ringkas dari bilangan berpecahan desimal berhingga."""
    for banyak in range(5):
        x = nilai * 10 ** banyak
        if x.denominator == 1:
            digit = str(int(x)).zfill(banyak + 1)
            return digit if banyak == 0 else f"{digit[:-banyak]},{digit[-banyak:]}"
    raise ValueError("bukan desimal berhingga")


def _berhingga(nilai: Fraction) -> bool:
    penyebut = nilai.denominator
    for pembagi in (2, 5):
        while penyebut % pembagi == 0:
            penyebut //= pembagi
    return penyebut == 1


def _seratus(n: int, d: int) -> int:
    """Pembilang saat n/d disamakan penyebutnya menjadi 100 (d pembagi 100)."""
    return n * (100 // d)


def _teks_pecahan(nilai: Fraction) -> str:
    return f"{nilai.numerator}/{nilai.denominator}"


def _domain_varian(varian: str) -> list:
    if varian == "bagian_dari":
        return [{"d": d, "k": k, "benda": i} for d in PENYEBUT_BAGIAN for k in HASIL_BAGIAN
                for i in range(len(BENDA))]
    if varian in ("senilai_isi", "senilai_sederhana"):
        return [{"a": a, "b": b, "f": f} for a, b in SEDERHANA for f in FAKTOR
                if b * f <= BATAS_PENYEBUT_SENILAI]
    if varian == "ke_desimal":
        return [{"n": n, "d": d} for d, ns in PEMBILANG_DESIMAL.items() for n in ns]
    if varian == "ke_persen":
        return [{"n": n, "d": d} for d, ns in PEMBILANG_PERSEN.items() for n in ns]
    return [{"perseratus": x} for x in SERATUS_DESIMAL]


def _enumerasi() -> tuple:
    return tuple({"varian": varian, **isian} for varian in VARIAN
                 for isian in _domain_varian(varian))


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


@lru_cache(maxsize=None)
def _himpunan_sah() -> frozenset:
    return frozenset(tuple(sorted(item)) for item in _domain_beku())


def _sah(varian, isian: dict) -> bool:
    if type(varian) is not str or varian not in BIDANG:
        return False
    if set(isian) != set(BIDANG[varian]):
        return False
    if not all(type(nilai) is int for nilai in isian.values()):
        return False
    return tuple(sorted({"varian": varian, **isian}.items())) in _himpunan_sah()


# ── kunci ────────────────────────────────────────────────────────────────

def _kunci(varian: str, p: dict) -> str:
    if varian == "bagian_dari":
        return str(p["k"])
    if varian == "senilai_isi":
        return str(p["a"] * p["f"])
    if varian == "senilai_sederhana":
        return f"{p['a']}/{p['b']}"
    if varian == "ke_desimal":
        return _desimal(Fraction(p["n"], p["d"]))
    if varian == "ke_persen":
        return str(_seratus(p["n"], p["d"]))
    return _teks_pecahan(Fraction(p["perseratus"], 100))


def _teks(varian: str, p: dict) -> str:
    if varian == "bagian_dari":
        benda, satuan, pemilik, penerima = BENDA[p["benda"]]
        return (f"{pemilik} memiliki {p['d'] * p['k']} {benda}. 1/{p['d']} dari {benda} itu "
                f"diberikan kepada {penerima}. Banyak {benda} yang diberikan ada ... {satuan}.")
    if varian == "senilai_isi":
        return f"{p['a']}/{p['b']} = .../{p['b'] * p['f']}"
    if varian == "senilai_sederhana":
        return (f"Pecahan senilai dengan {p['a'] * p['f']}/{p['b'] * p['f']} "
                "yang paling sederhana adalah ...")
    if varian == "ke_desimal":
        return f"Pecahan {p['n']}/{p['d']} jika ditulis sebagai desimal adalah ..."
    if varian == "ke_persen":
        return f"{p['n']}/{p['d']} = ... %"
    return (f"Desimal {_desimal(Fraction(p['perseratus'], 100))} jika ditulis sebagai pecahan "
            "paling sederhana adalah ...")


# ── pembahasan ───────────────────────────────────────────────────────────

def _pembahasan_desimal(p: dict, kunci: str) -> str:
    n, d = p["n"], p["d"]
    x = _seratus(n, d)
    dua = f"{x // 100},{x % 100:02d}"
    akhir = f"{dua}, ditulis {kunci}" if dua != kunci else kunci
    return (f"Samakan penyebutnya menjadi 100: {n}/{d} = {x}/100, sebab {d} × {100 // d} = 100 "
            f"dan {n} × {100 // d} = {x}. Jadi {n}/{d} = {akhir}.")


def _pembahasan_desimal_ke_pecahan(p: dict, kunci: str) -> str:
    x = p["perseratus"]
    if x % 10 == 0:
        awal, bawah = x // 10, 10
    else:
        awal, bawah = x, 100
    pembagi = gcd(awal, bawah)
    return (f"{_desimal(Fraction(x, 100))} dibaca {awal} per {bawah}, jadi {awal}/{bawah}. "
            f"Bagi pembilang dan penyebut dengan {pembagi}: {awal} ÷ {pembagi} = {awal // pembagi} "
            f"dan {bawah} ÷ {pembagi} = {bawah // pembagi}. Hasilnya {kunci}, dan tidak bisa "
            "disederhanakan lagi.")


def _pembahasan(varian: str, p: dict, kunci: str) -> str:
    if varian == "bagian_dari":
        benda, satuan = BENDA[p["benda"]][:2]
        return (f"1/{p['d']} bagian berarti dibagi menjadi {p['d']} bagian sama banyak, lalu "
                f"diambil 1 bagian. {p['d'] * p['k']} ÷ {p['d']} = {kunci}. "
                f"Jadi ada {kunci} {satuan} {benda}.")
    if varian == "senilai_isi":
        awal, baru = p["b"], p["b"] * p["f"]
        return (f"Penyebut berubah dari {awal} menjadi {baru}, jadi dikali {p['f']}. Pembilang "
                f"harus dikali bilangan yang sama: {p['a']} × {p['f']} = {kunci}. "
                f"Jadi {p['a']}/{p['b']} = {kunci}/{baru}.")
    if varian == "senilai_sederhana":
        atas, bawah = p["a"] * p["f"], p["b"] * p["f"]
        return (f"Bagi pembilang dan penyebut dengan bilangan yang sama, yaitu {p['f']}: "
                f"{atas} ÷ {p['f']} = {p['a']} dan {bawah} ÷ {p['f']} = {p['b']}. "
                f"Jadi bentuk paling sederhananya {kunci}; angka itu tidak bisa dibagi lagi.")
    if varian == "ke_desimal":
        return _pembahasan_desimal(p, kunci)
    if varian == "ke_persen":
        x = _seratus(p["n"], p["d"])
        return (f"Persen artinya per seratus. Samakan penyebutnya menjadi 100: "
                f"{p['n']}/{p['d']} = {x}/100 = {kunci}%.")
    return _pembahasan_desimal_ke_pecahan(p, kunci)


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban: str, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", jawaban, kode, alasan)


def _kandidat_bagian_dari(p: dict) -> list:
    d, k = p["d"], p["k"]
    total = d * k
    return [
        _mal("penyebut_dikali", str(total * d), "K",
             f"Mengalikan {total} dengan {d} sehingga jawabannya {total * d}; kemungkinan "
             f"membaca 1/{d} sebagai {d} kali."),
        _mal("pembilang_saja", str(total), "K",
             f"Mengalikan {total} dengan pembilang 1 saja, sehingga jawabannya tetap {total}; "
             "kemungkinan penyebut diabaikan."),
        _mal("dikurangi_penyebut", str(total - d), "K",
             f"Mengurangi {total} dengan {d} sehingga jawabannya {total - d}; kemungkinan "
             "mengira kata \"dari\" berarti dikurangi."),
        _mal("jawab_sisa", str(total - k), "H",
             f"Sudah membagi dengan benar, tetapi menjawab banyak yang tersisa "
             f"({total - k}), bukan yang diberikan."),
    ]


def _kandidat_senilai_isi(p: dict) -> list:
    a, b, f = p["a"], p["b"], p["f"]
    baru = b * f
    return [
        _mal("pembilang_ditambah", str(a + baru - b), "K",
             f"Menambah pembilang dengan selisih penyebut ({baru} − {b}) sehingga jawabannya "
             f"{a + baru - b}; kemungkinan mengira senilai berarti ditambah, bukan dikali."),
        _mal("pembilang_tetap", str(a), "K",
             f"Pembilang dibiarkan {a} dan hanya penyebut yang berubah; kemungkinan lupa bahwa "
             "pembilang harus dikali bilangan yang sama."),
        _mal("penyebut_jadi_pembilang", str(baru), "K",
             f"Menulis penyebut baru ({baru}) sebagai pembilang."),
    ]


def _kandidat_senilai_sederhana(p: dict) -> list:
    a, b, f = p["a"], p["b"], p["f"]
    atas, bawah = a * f, b * f
    return [
        _mal("hanya_pembilang_dibagi", f"{a}/{bawah}", "K",
             f"Hanya pembilang yang dibagi {f} ({atas} jadi {a}) sedangkan penyebut {bawah} "
             "dibiarkan."),
        _mal("hanya_penyebut_dibagi", f"{atas}/{b}", "K",
             f"Hanya penyebut yang dibagi {f} ({bawah} jadi {b}) sedangkan pembilang {atas} "
             "dibiarkan."),
        _mal("pembilang_penyebut_tertukar", f"{b}/{a}", "K",
             f"Menulis hasil dengan pembilang dan penyebut tertukar ({b}/{a})."),
    ]


def _geser(nilai: Fraction, kali: Fraction) -> str:
    return _desimal(nilai * kali)


def _kandidat_ke_desimal(p: dict) -> list:
    n, d = p["n"], p["d"]
    nilai = Fraction(n, d)
    hasil = [
        _mal("titik_geser_kanan", _geser(nilai, Fraction(10)), "K",
             "Titik desimal bergeser satu tempat ke kanan sehingga nilainya 10 kali terlalu "
             "besar; kemungkinan salah menaruh koma saat menyamakan penyebut menjadi 100."),
        _mal("titik_geser_kiri", _geser(nilai, Fraction(1, 10)), "K",
             "Titik desimal bergeser satu tempat ke kiri sehingga nilainya 10 kali terlalu "
             "kecil; kemungkinan salah menaruh koma."),
        _mal("pembilang_di_belakang_koma", f"0,{n}", "K",
             f"Menulis pembilang {n} langsung di belakang koma tanpa melihat penyebutnya."),
    ]
    terbalik = Fraction(d, n)
    if _berhingga(terbalik):
        hasil.append(_mal(
            "pembilang_penyebut_tertukar", _desimal(terbalik), "K",
            f"Membagi penyebut dengan pembilang ({d} ÷ {n}), kemungkinan menukar pembilang "
            "dan penyebut."))
    return hasil


def _kandidat_ke_persen(p: dict) -> list:
    n, d = p["n"], p["d"]
    benar = _seratus(n, d)
    return [
        _mal("persen_sama_pembilang", str(n), "K",
             f"Menulis pembilang {n} sebagai persen; kemungkinan mengira angka di atas garis "
             "pecahan langsung menjadi persen."),
        _mal("pembilang_kali_seratus", str(n * 100), "K",
             f"Hanya pembilang yang dikali 100 ({n} × 100) tanpa dibagi penyebut {d}."),
        _mal("pembilang_diabaikan", str(100 // d), "K",
             f"Hanya menghitung 100 ÷ {d} = {100 // d}; kemungkinan pembilang {n} tidak "
             "ikut dikalikan."),
        _mal("penyebut_jadi_persen", str(d), "K",
             f"Menulis penyebut {d} sebagai persen."),
        _mal("jawab_sisa", str(100 - benar), "H",
             f"Sudah mengubah ke persen, tetapi menjawab bagian yang tersisa dari 100% "
             f"({100 - benar}%)."),
    ]


def _kandidat_desimal_ke_pecahan(p: dict) -> list:
    x = p["perseratus"]
    nilai = Fraction(x, 100)
    dua_digit = x % 10 != 0
    hasil = [
        _mal("pembilang_penyebut_tertukar", _teks_pecahan(1 / nilai), "K",
             "Menulis pecahan dengan pembilang dan penyebut tertukar."),
        _mal("angka_koma_jadi_penyebut", f"1/{x if dua_digit else x // 10}", "K",
             "Angka di belakang koma dijadikan penyebut dengan pembilang 1."),
    ]
    if dua_digit:
        hasil.append(_mal(
            "angka_koma_per_sepuluh", f"{x}/10", "K",
            "Angka di belakang koma dijadikan pembilang, tetapi penyebutnya ditulis 10, "
            "bukan 100."))
    belum = f"{x // 10}/10" if not dua_digit else f"{x}/100"
    hasil.append(_mal(
        "belum_paling_sederhana", belum, "H",
        "Sudah mengubah ke pecahan, tetapi belum disederhanakan sampai paling sederhana."))
    return hasil


_KANDIDAT = {
    "bagian_dari": _kandidat_bagian_dari,
    "senilai_isi": _kandidat_senilai_isi,
    "senilai_sederhana": _kandidat_senilai_sederhana,
    "ke_desimal": _kandidat_ke_desimal,
    "ke_persen": _kandidat_ke_persen,
    "desimal_ke_pecahan": _kandidat_desimal_ke_pecahan,
}
def pecahan_senilai_desimal(varian: str, d: int | None = None, k: int | None = None,
                            benda: int | None = None, a: int | None = None,
                            b: int | None = None, f: int | None = None,
                            n: int | None = None, perseratus: int | None = None) -> Soal:
    """Pecahan berpembilang satu, senilai, desimal, atau persen (kunci dari parameter)."""
    isian = {nama: nilai for nama, nilai in (
        ("d", d), ("k", k), ("benda", benda), ("a", a), ("b", b), ("f", f), ("n", n),
        ("perseratus", perseratus)) if nilai is not None}
    if not _sah(varian, isian):
        raise ValueError(PESAN_LUAR_DOMAIN)
    kunci = _kunci(varian, isian)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isian},
        teks=_teks(varian, isian), kunci=kunci,
        malrule=saring_malrule(kunci, _KANDIDAT[varian](isian)),
        pembahasan=_pembahasan(varian, isian, kunci), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level pecahan senilai desimal harus P4")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku())


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu parameter seragam dalam varian itu; hanya dari rng."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    kolam = tuple(item for item in _domain_beku() if item[0][1] == varian)
    return dict(rng.choice(kolam))
