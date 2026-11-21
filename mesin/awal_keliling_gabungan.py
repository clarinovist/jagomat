"""Matematika Awal, jenis `keliling_gabungan`: keliling persegi, persegi panjang, dan bangun gabungan (P5), teks saja.

Bab K5 B4 "Keliling bangun datar" (Keliling bangun datar; Keliling bangun gabungan).
Bangun dideskripsikan TANPA gambar dengan semua panjang sisi disebutkan. Empat bentuk
soal (`varian`), semua berkunci angka bulat positif:
  - `persegi_persegipanjang` dengan `tanya`: `keliling_persegi` (sisi -> keliling),
    `keliling_persegipanjang` (panjang, lebar -> keliling), `sisi_dari_keliling`
    (keliling persegi -> sisi), `panjang_dari_keliling` (keliling dan lebar -> panjang);
  - `dua_persegipanjang`: dua persegi panjang berlebar sama disambung rapat pada sisi
    lebarnya sehingga membentuk satu persegi panjang; keliling = 2 x ((p1 + p2) + lebar);
  - `bentuk_L`: persegi panjang p x l dengan satu pojok persegi kecil bersisi s dipotong
    (s < sisi terpendek, jadi hasilnya benar-benar huruf L); keliling = 2 x (p + l),
    sama dengan keliling persegi panjang asal;
  - `segitiga_sama_sisi_di_persegi`: segitiga sama sisi bersisi s menempel pada satu sisi
    persegi bersisi s; keliling = 5 x s.

Kepastian bangun: pada `dua_persegipanjang` kedua lebar sama, sisi lebar yang disambung
adalah sisi terpendek kedua bangun (p1, p2 > lebar) dan p1 > p2, sehingga bangun gabungan
selalu persegi panjang (p1 + p2) x lebar dan rumusnya tunggal. Pada `bentuk_L` panjang >
lebar dan s < lebar; pada s sama dengan sisi terpendek satu jalur utuh ikut terbuang dan
keliling berubah, jadi s sama atau lebih besar tidak masuk domain. Panjang sisi 2..30
dengan satuan cm atau m yang konsisten satu soal; kunci angka polos tanpa satuan.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari
satu jawaban: menjumlah semua sisi termasuk sisi yang menempel (K), melupakan sisi (K),
menghitung luas alih-alih keliling (K), salah memahami bagian yang dipotong (K), serta
kurang/lebih satu sisi (H, hanya bila nyata berbeda dari kunci). Jalur K selalu ada.
Kunci yang bertabrakan dengan malrule (mis. luas = keliling pada s = 4) dibuang
`saring_malrule`; jalur K lain tetap tersisa.

Domain eksplisit (`domain_parameter`): sampler memilih `varian` seragam dulu, lalu
`tanya` seragam bila ada, lalu satu parameter seragam; hanya dari `rng` (tanpa `hash()`).
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "keliling_gabungan"
LEVEL = ("P5",)
VARIAN = ("persegi_persegipanjang", "dua_persegipanjang", "bentuk_L",
          "segitiga_sama_sisi_di_persegi")
TANYA = ("keliling_persegi", "keliling_persegipanjang", "sisi_dari_keliling",
         "panjang_dari_keliling")
SATUAN = ("cm", "m")
PESAN_LUAR_DOMAIN = "parameter keliling gabungan di luar domain"
SISI_PERSEGI = tuple(range(2, 31))
PANJANG_PP = tuple(range(3, 16))
LEBAR_DARI_KELILING = tuple(range(2, 9))
PANJANG_MAKS_DARI_KELILING = 16
LEBAR_GABUNG = tuple(range(2, 7))
PANJANG_GABUNG_MAKS = (10, 11)  # p2 sampai 10, p1 sampai 11
PANJANG_L = tuple(range(6, 15))
LEBAR_L_MIN = 4
POTONG_L = (2, 3)


# ── domain eksplisit dan validasi ────────────────────────────────────────

def _enumerasi() -> tuple:
    hasil = []
    for u in SATUAN:
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "keliling_persegi",
                   "satuan": u, "sisi": s} for s in SISI_PERSEGI]
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "keliling_persegipanjang",
                   "satuan": u, "panjang": p, "lebar": l}
                  for p in PANJANG_PP for l in range(2, p)]
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "sisi_dari_keliling",
                   "satuan": u, "sisi": s} for s in SISI_PERSEGI]
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "panjang_dari_keliling",
                   "satuan": u, "panjang": p, "lebar": l}
                  for l in LEBAR_DARI_KELILING
                  for p in range(l + 1, PANJANG_MAKS_DARI_KELILING + 1)]
        hasil += [{"varian": "dua_persegipanjang", "satuan": u, "lebar": w,
                   "panjang1": p1, "panjang2": p2}
                  for w in LEBAR_GABUNG
                  for p2 in range(w + 1, PANJANG_GABUNG_MAKS[0] + 1)
                  for p1 in range(p2 + 1, PANJANG_GABUNG_MAKS[1] + 1)]
        hasil += [{"varian": "bentuk_L", "satuan": u, "panjang": p, "lebar": l,
                   "potong": s}
                  for p in PANJANG_L for l in range(LEBAR_L_MIN, p) for s in POTONG_L]
        hasil += [{"varian": "segitiga_sama_sisi_di_persegi", "satuan": u, "sisi": s}
                  for s in SISI_PERSEGI]
    return tuple(hasil)


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _kanon(p: dict) -> tuple:
    return tuple(sorted(p.items()))


@lru_cache(maxsize=None)
def _himpunan_sah() -> frozenset:
    return frozenset(_kanon(dict(item)) for item in _domain_beku())


def _tipe_polos(p: dict) -> bool:
    """Hanya int/str murni: 4.0 dan True sama-hash dengan 4 sehingga harus ditolak lebih dulu."""
    return all(type(v) in (int, str) for v in p.values())


def _sah(p: dict) -> bool:
    return _tipe_polos(p) and _kanon(p) in _himpunan_sah()


@lru_cache(maxsize=None)
def _peta_varian() -> tuple:
    """((varian, (kelompok, ...)), ...); kelompok = tuple item parameter, per `tanya`."""
    hasil = []
    for varian in VARIAN:
        kelompok = {}
        for item in _domain_beku():
            p = dict(item)
            if p["varian"] == varian:
                kelompok.setdefault(p.get("tanya", ""), []).append(item)
        hasil.append((varian, tuple(tuple(v) for v in kelompok.values())))
    return tuple(hasil)


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level keliling gabungan harus P5")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku())


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu tanya seragam, lalu satu parameter seragam; hanya dari rng."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    kelompok = dict(_peta_varian())[varian]
    return dict(rng.choice(rng.choice(kelompok)))


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _kandidat_persegi(s: int) -> list:
    return [
        _mal("luas_bukan_keliling", s * s, "K",
             f"Menghitung luas persegi ({s} × {s} = {s * s}), bukan keliling."),
        _mal("hanya_dua_sisi", 2 * s, "K",
             f"Menjumlah hanya dua sisi ({2 * s}), kemungkinan lupa bahwa persegi punya "
             "empat sisi."),
        _mal("satu_sisi_terlewat", 3 * s, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi terlewat "
             f"sehingga jawabannya {3 * s}."),
        _mal("satu_sisi_berlebih", 5 * s, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi terhitung dua "
             f"kali sehingga jawabannya {5 * s}."),
    ]


def _kandidat_persegipanjang(p: int, l: int) -> list:
    kunci = 2 * (p + l)
    return [
        _mal("luas_bukan_keliling", p * l, "K",
             f"Menghitung luas ({p} × {l} = {p * l}), bukan keliling."),
        _mal("hanya_panjang_ditambah_lebar", p + l, "K",
             f"Menjumlah panjang dan lebar saja ({p + l}), lupa dua sisi lainnya."),
        _mal("hanya_dua_sisi_panjang", 2 * p, "K",
             f"Menjumlah dua sisi panjang saja ({2 * p}), lupa dua sisi lebar."),
        _mal("satu_sisi_lebar_terlewat", kunci - l, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi lebar terlewat "
             f"sehingga jawabannya {kunci - l}."),
        _mal("satu_sisi_lebar_berlebih", kunci + l, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi lebar terhitung "
             f"dua kali sehingga jawabannya {kunci + l}."),
    ]


def _kandidat_sisi_dari_keliling(s: int) -> list:
    return [
        _mal("dibagi_dua_bukan_empat", 2 * s, "K",
             f"Membagi keliling dengan 2, bukan dengan 4, sehingga jawabannya {2 * s}."),
        _mal("keliling_ditulis_ulang", 4 * s, "K",
             f"Menulis angka kelilingnya saja ({4 * s}), belum mencari panjang sisi."),
        _mal("sisi_lebih_satu", s + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{s + 1}."),
        _mal("sisi_kurang_satu", s - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{s - 1}."),
    ]


def _kandidat_panjang_dari_keliling(p: int, l: int) -> list:
    keliling = 2 * (p + l)
    return [
        _mal("lebar_belum_dikurangkan", p + l, "K",
             f"Membagi keliling dengan 2 ({p + l}) tetapi lupa mengurangkan lebar."),
        _mal("lebar_dikurangkan_dari_keliling", keliling - l, "K",
             f"Mengurangkan lebar dari keliling ({keliling - l}) tanpa membagi dua dulu."),
        _mal("lebar_disebut", l, "K", f"Menyebut lebar ({l}), bukan panjang."),
        _mal("panjang_lebih_satu", p + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{p + 1}."),
        _mal("panjang_kurang_satu", p - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{p - 1}."),
    ]


def _kandidat_dua_pp(w: int, p1: int, p2: int) -> list:
    kunci = 2 * (p1 + p2 + w)
    return [
        _mal("sisi_menempel_ikut_dihitung", kunci + 2 * w, "K",
             f"Menjumlah keliling kedua persegi panjang ({kunci + 2 * w}), sehingga sisi "
             "yang menempel ikut terhitung."),
        _mal("luas_bukan_keliling", (p1 + p2) * w, "K",
             f"Menghitung luas bangun gabungan ({p1 + p2} × {w} = {(p1 + p2) * w}), "
             "bukan keliling."),
        _mal("hanya_setengah_keliling", p1 + p2 + w, "K",
             f"Menjumlah panjang gabungan dan satu lebar saja ({p1 + p2 + w}), lupa dua "
             "sisi lainnya."),
        _mal("satu_sisi_lebar_terlewat", kunci - w, "H",
             f"Sudah mengerti caranya, tetapi satu sisi lebar terlewat sehingga "
             f"jawabannya {kunci - w}."),
        _mal("satu_sisi_lebar_berlebih", kunci + w, "H",
             f"Sudah mengerti caranya, tetapi satu sisi lebar terhitung dua kali "
             f"sehingga jawabannya {kunci + w}."),
    ]


def _kandidat_bentuk_l(p: int, l: int, s: int) -> list:
    kunci = 2 * (p + l)
    return [
        _mal("luas_bangun_l_bukan_keliling", p * l - s * s, "K",
             f"Menghitung luas bangun L ({p * l} − {s * s} = {p * l - s * s}), bukan "
             "keliling."),
        _mal("potongan_dikira_memperpendek", kunci - 2 * s, "K",
             f"Mengira bagian yang dipotong mengurangi keliling sebesar 2 × {s} tanpa "
             f"menghitung dua sisi baru bekas potongan ({kunci - 2 * s})."),
        _mal("sisi_potongan_ditambah_saja", kunci + 2 * s, "K",
             f"Menambah dua sisi bekas potongan tanpa mengurangi bagian yang hilang "
             f"({kunci + 2 * s})."),
        _mal("satu_sisi_potongan_terlewat", kunci - s, "H",
             f"Sudah mengerti caranya, tetapi satu sisi bekas potongan terlewat "
             f"sehingga jawabannya {kunci - s}."),
        _mal("satu_sisi_potongan_berlebih", kunci + s, "H",
             f"Sudah mengerti caranya, tetapi satu sisi bekas potongan terhitung dua "
             f"kali sehingga jawabannya {kunci + s}."),
    ]


def _kandidat_atap(s: int) -> list:
    return [
        _mal("sisi_menempel_ikut_dihitung", 7 * s, "K",
             f"Menjumlah semua sisi persegi dan segitiga ({7 * s}), sehingga sisi yang "
             "menempel ikut terhitung."),
        _mal("sisi_segitiga_terlupa", 4 * s, "K",
             f"Hanya menghitung keliling persegi ({4 * s}), lupa sisi segitiga."),
        _mal("luas_persegi_bukan_keliling", s * s, "K",
             f"Menghitung luas persegi ({s} × {s} = {s * s}), bukan keliling."),
        _mal("sisi_menempel_terhitung_sekali", 6 * s, "H",
             f"Sudah mengerti caranya, tetapi satu sisi yang menempel masih terhitung "
             f"sekali sehingga jawabannya {6 * s}."),
    ]


# ── kunci, teks, pembahasan per bentuk ───────────────────────────────────

def _persegi(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    kunci = 4 * s
    teks = f"Sebuah persegi mempunyai panjang sisi {s} {u}. Berapa {u} keliling persegi itu?"
    pembahasan = (f"Keliling persegi = 4 × sisi. Sisinya {s} {u}, jadi kelilingnya "
                  f"4 × {s} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_persegi(s)


def _persegipanjang(p: dict) -> tuple:
    pj, l, u = p["panjang"], p["lebar"], p["satuan"]
    kunci = 2 * (pj + l)
    teks = (f"Sebuah persegi panjang mempunyai panjang {pj} {u} dan lebar {l} {u}. "
            f"Berapa {u} keliling persegi panjang itu?")
    pembahasan = (f"Keliling persegi panjang = 2 × (panjang + lebar). Jadi kelilingnya "
                  f"2 × ({pj} + {l}) = 2 × {pj + l} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_persegipanjang(pj, l)


def _sisi_dari_keliling(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    keliling = 4 * s
    teks = (f"Keliling sebuah persegi adalah {keliling} {u}. Berapa {u} panjang sisi "
            "persegi itu?")
    pembahasan = (f"Persegi punya 4 sisi yang sama panjang, jadi keliling = 4 × sisi. "
                  f"Sisinya = {keliling} ÷ 4 = {s} {u}. Jadi jawabannya {s}.")
    return teks, s, pembahasan, _kandidat_sisi_dari_keliling(s)


def _panjang_dari_keliling(p: dict) -> tuple:
    pj, l, u = p["panjang"], p["lebar"], p["satuan"]
    keliling = 2 * (pj + l)
    teks = (f"Keliling sebuah persegi panjang adalah {keliling} {u} dan lebarnya {l} {u}. "
            f"Berapa {u} panjang sisinya yang lebih panjang?")
    pembahasan = (f"Keliling = 2 × (panjang + lebar), jadi panjang + lebar = {keliling} ÷ 2 "
                  f"= {pj + l} {u}. Lebarnya {l} {u}, jadi panjangnya {pj + l} − {l} = "
                  f"{pj} {u}. Jadi jawabannya {pj}.")
    return teks, pj, pembahasan, _kandidat_panjang_dari_keliling(pj, l)


_PERSEGI_PERSEGIPANJANG = {
    "keliling_persegi": _persegi, "keliling_persegipanjang": _persegipanjang,
    "sisi_dari_keliling": _sisi_dari_keliling,
    "panjang_dari_keliling": _panjang_dari_keliling,
}


def _dua_persegipanjang(p: dict) -> tuple:
    w, p1, p2, u = p["lebar"], p["panjang1"], p["panjang2"], p["satuan"]
    gabung = p1 + p2
    kunci = 2 * (gabung + w)
    teks = (f"Persegi panjang pertama panjangnya {p1} {u} dan lebarnya {w} {u}. Persegi "
            f"panjang kedua panjangnya {p2} {u} dan lebarnya {w} {u}. Keduanya disambung "
            f"rapat pada sisi lebarnya ({w} {u}) tanpa saling menumpuk sehingga membentuk "
            f"satu persegi panjang yang lebih besar. Berapa {u} keliling bangun gabungan "
            "itu?")
    pembahasan = (f"Sisi {w} {u} yang saling menempel tidak ikut menjadi keliling. Bangun "
                  f"gabungannya berupa persegi panjang dengan panjang {p1} + {p2} = "
                  f"{gabung} {u} dan lebar {w} {u}. Keliling = 2 × ({gabung} + {w}) = "
                  f"{kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_dua_pp(w, p1, p2)


def _bentuk_l(p: dict) -> tuple:
    pj, l, s, u = p["panjang"], p["lebar"], p["potong"], p["satuan"]
    kunci = 2 * (pj + l)
    teks = (f"Sebuah persegi panjang mempunyai panjang {pj} {u} dan lebar {l} {u}. Pada "
            f"salah satu pojoknya dipotong sebuah persegi kecil dengan sisi {s} {u} "
            f"sehingga bangunnya berbentuk huruf L. Berapa {u} keliling bangun berbentuk "
            "L itu?")
    pembahasan = (f"Keliling bangun L sama dengan keliling persegi panjang asalnya. Bagian "
                  f"yang dipotong mengurangi {s} {u} dari panjang dan {s} {u} dari lebar, "
                  f"tetapi menambah dua sisi baru yang masing-masing {s} {u}. "
                  f"Kelilingnya 2 × ({pj} + {l}) = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_bentuk_l(pj, l, s)


def _atap(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    kunci = 5 * s
    teks = (f"Sebuah persegi mempunyai panjang sisi {s} {u}. Pada salah satu sisinya "
            f"ditempelkan sebuah segitiga sama sisi yang panjang sisinya juga {s} {u}, "
            f"tepat berimpit dengan sisi persegi itu (seperti atap rumah). Berapa {u} "
            "keliling bangun gabungan itu?")
    pembahasan = (f"Persegi punya 4 sisi, tetapi satu sisinya menempel pada segitiga "
                  f"sehingga tidak ikut keliling. Sisi luar yang tersisa adalah 3 sisi "
                  f"persegi dan 2 sisi segitiga, jadi ada 5 sisi sepanjang {s} {u}. "
                  f"Keliling = 5 × {s} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_atap(s)


def _bangun(p: dict) -> tuple:
    varian = p["varian"]
    if varian == "persegi_persegipanjang":
        return _PERSEGI_PERSEGIPANJANG[p["tanya"]](p)
    if varian == "dua_persegipanjang":
        return _dua_persegipanjang(p)
    if varian == "bentuk_L":
        return _bentuk_l(p)
    return _atap(p)


def keliling_gabungan(varian: str, **parameter) -> Soal:
    """Keliling persegi, persegi panjang, atau bangun gabungan; kunci dari parameter."""
    lengkap = {"varian": varian, **parameter}
    if not _sah(lengkap):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, pembahasan, kandidat = _bangun(lengkap)
    return Soal(
        template_id=TEMPLATE_ID, parameter=lengkap, teks=teks, kunci=str(kunci),
        malrule=saring_malrule(str(kunci), kandidat), pembahasan=pembahasan, bagian="A")
