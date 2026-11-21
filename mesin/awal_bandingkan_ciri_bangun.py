"""Matematika Awal, jenis `bandingkan_ciri_bangun`: membandingkan ciri bangun datar (P5), teks saja.

Empat bentuk soal (`varian`), semua berkunci angka bulat:
  - `sumbu_simetri`: "Berapa banyak sumbu simetri persegi?";
  - `pasang_sejajar`: "Berapa pasang sisi sejajar yang dimiliki jajar genjang?";
  - `banyak_sudut_siku`: "Berapa banyak sudut siku-siku yang dimiliki persegi panjang?";
  - `selisih_ciri`: "Persegi punya ... sumbu simetri lebih banyak daripada persegi
    panjang yang bukan persegi." (jawaban: selisih, selalu positif).

DAFTAR FAKTA (definisi umum buku siswa Matematika SD Kelas V; MOHON DIULAS MUTIA
sebelum rilis; hanya fakta yang tak diperdebatkan yang dipakai):
  sumbu simetri : persegi 4; persegi panjang (bukan persegi) 2; segitiga sama sisi 3;
                  belah ketupat (bukan persegi) 2; layang-layang (bukan belah ketupat) 1.
  pasang sejajar: persegi 2; persegi panjang 2; jajar genjang 2; belah ketupat 2;
                  trapesium (bukan jajar genjang) 1; segitiga 0.
  sudut siku    : persegi 4; persegi panjang 4; segitiga siku-siku 1; segitiga sama sisi 0.
Sengaja TIDAK ditanyakan: lingkaran (sumbu tak hingga), sumbu jajar genjang umum
(ada yang mengira 2; sebenarnya 0), sumbu trapesium umum (0), sudut siku jajar
genjang/belah ketupat/trapesium umum (bergantung bentuk), segitiga umum.

Kualifikasi nama: dalam definisi inklusif persegi juga persegi panjang dan belah
ketupat, belah ketupat juga layang-layang, jajar genjang juga trapesium. Agar
jawaban tak ambigu, soal sumbu simetri menulis "persegi panjang yang bukan persegi",
"belah ketupat yang bukan persegi", "layang-layang yang bukan belah ketupat", dan
soal pasang sejajar menulis "trapesium yang bukan jajar genjang". Nama lain tidak
terpengaruh oleh tumpang-tindih itu (fakta sama pada kasus khususnya).

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban: nilai bangun lain yang tertukar, banyak sisi/diagonal/sudut
yang disebut sebagai ciri yang ditanya, menyebut nilai satu bangun saja pada
soal selisih (semuanya K), dan salah hitung seperti selisih dijumlah, dibalik
(negatif), atau meleset satu, serta sudut siku terlewat/terhitung dobel (H, hanya
bila nyata berbeda dari kunci). Jalur K selalu ada; minimal tiga pengecoh angka
tak-negatif berbeda per parameter.

Domain kecil dan eksplisit (`domain_parameter`): sampler memilih `varian` seragam
dulu (supaya selisih_ciri, yang paling banyak, tak mendominasi), lalu satu
parameter seragam dalam varian itu, hanya dari `rng` (tanpa `hash()`).
Urutan daftar FAKTA APPEND-ONLY: nama bangun (bukan indeks) menjadi parameter.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "bandingkan_ciri_bangun"
LEVEL = ("P5",)
CIRI = ("sumbu_simetri", "pasang_sejajar", "banyak_sudut_siku")
VARIAN = CIRI + ("selisih_ciri",)
PESAN_LUAR_DOMAIN = "parameter bandingkan ciri bangun di luar domain"

FAKTA = {
    "sumbu_simetri": (("persegi", 4), ("persegi panjang", 2), ("segitiga sama sisi", 3),
                      ("belah ketupat", 2), ("layang-layang", 1)),
    "pasang_sejajar": (("persegi", 2), ("persegi panjang", 2), ("jajar genjang", 2),
                       ("belah ketupat", 2), ("trapesium", 1), ("segitiga", 0)),
    "banyak_sudut_siku": (("persegi", 4), ("persegi panjang", 4),
                          ("segitiga siku-siku", 1), ("segitiga sama sisi", 0)),
}
# Nama di dalam kalimat soal; kualifikasi hanya di tempat yang jawabannya bisa ambigu.
NAMA = {
    "sumbu_simetri": {
        "persegi": "persegi",
        "persegi panjang": "persegi panjang yang bukan persegi",
        "segitiga sama sisi": "segitiga sama sisi",
        "belah ketupat": "belah ketupat yang bukan persegi",
        "layang-layang": "layang-layang yang bukan belah ketupat",
    },
    "pasang_sejajar": {
        "persegi": "persegi", "persegi panjang": "persegi panjang",
        "jajar genjang": "jajar genjang", "belah ketupat": "belah ketupat",
        "trapesium": "trapesium yang bukan jajar genjang", "segitiga": "segitiga",
    },
    "banyak_sudut_siku": {
        "persegi": "persegi", "persegi panjang": "persegi panjang",
        "segitiga siku-siku": "segitiga siku-siku", "segitiga sama sisi": "segitiga sama sisi",
    },
}
FRASA = {"sumbu_simetri": "sumbu simetri", "pasang_sejajar": "pasang sisi sejajar",
         "banyak_sudut_siku": "sudut siku-siku"}
PENGANTAR = {
    "sumbu_simetri": "Sumbu simetri adalah garis lipat yang membuat dua bagian bangun "
                     "saling menutupi tepat.",
    "pasang_sejajar": "Sisi sejajar adalah dua sisi yang tidak akan bertemu walau "
                      "diperpanjang sejauh apa pun.",
    "banyak_sudut_siku": "Sudut siku-siku adalah sudut seperti pojok kertas, besarnya "
                         "90 derajat.",
}
# Alasan tiap fakta (kalimat sesudah "punya N ...: ").
ALASAN = {
    "sumbu_simetri": {
        "persegi": "2 garis lipat lewat titik tengah sisi yang berhadapan dan 2 garis "
                   "lipat lewat diagonalnya",
        "persegi panjang": "garis lipat tegak dan garis lipat mendatar lewat titik tengah "
                           "sisi yang berhadapan, sedangkan lipatan diagonal tidak menutupi "
                           "tepat karena panjang dan lebarnya berbeda",
        "segitiga sama sisi": "tiap garis lipat lewat satu sudut dan titik tengah sisi di "
                              "depannya, dan ada 3 sudut",
        "belah ketupat": "garis lipat sepanjang kedua diagonalnya, sedangkan lipatan lewat "
                         "titik tengah sisi tidak menutupi tepat",
        "layang-layang": "hanya garis lipat sepanjang diagonal yang membagi dua layang-layang "
                         "itu yang menutupi tepat",
    },
    "pasang_sejajar": {
        "persegi": "sisi atas dengan sisi bawah, dan sisi kiri dengan sisi kanan",
        "persegi panjang": "sisi atas dengan sisi bawah, dan sisi kiri dengan sisi kanan",
        "jajar genjang": "sisi atas dengan sisi bawah, dan dua sisi miringnya yang berhadapan",
        "belah ketupat": "tiap sisi sejajar dengan sisi di seberangnya",
        "trapesium": "hanya sisi atas dan sisi bawah yang sejajar, sedangkan dua sisi "
                     "miringnya tidak sejajar",
        "segitiga": "tidak ada dua sisi yang berhadapan, sebab ketiga sisinya saling "
                    "bertemu di sudut",
    },
    "banyak_sudut_siku": {
        "persegi": "keempat sudutnya siku-siku",
        "persegi panjang": "keempat sudutnya siku-siku",
        "segitiga siku-siku": "hanya satu sudutnya yang siku-siku, dua sudut lainnya "
                              "lebih kecil",
        "segitiga sama sisi": "ketiga sudutnya sama besar dan lebih kecil dari sudut "
                              "siku-siku, jadi tidak ada yang siku-siku",
    },
}
# Ciri pengecoh (hipotesis K): banyak sisi dan sudut tiap bangun; diagonal hanya segiempat.
SISI = {"persegi": 4, "persegi panjang": 4, "jajar genjang": 4, "belah ketupat": 4,
        "layang-layang": 4, "trapesium": 4, "segitiga": 3, "segitiga siku-siku": 3,
        "segitiga sama sisi": 3}
DIAGONAL_SEGIEMPAT = 2


def _nilai(ciri: str, bangun: str) -> int:
    return dict(FAKTA[ciri])[bangun]


def _kapital(teks: str) -> str:
    return teks[0].upper() + teks[1:]


def _pasangan_selisih(ciri: str) -> tuple:
    """Semua (a, b) dengan nilai a > nilai b pada ciri itu."""
    return tuple((a, b) for a, va in FAKTA[ciri] for b, vb in FAKTA[ciri] if va > vb)


def _sah(varian, ciri, bangun, a, b) -> bool:
    if type(varian) is not str or varian not in VARIAN:
        return False
    if varian == "selisih_ciri":
        return (bangun is None and type(ciri) is str and ciri in CIRI
                and type(a) is str and type(b) is str and (a, b) in _pasangan_selisih(ciri))
    nama = [n for n, _ in FAKTA[varian]]
    return (ciri is None and a is None and b is None
            and type(bangun) is str and bangun in nama)


# ── teks, pembahasan, malrule ────────────────────────────────────────────

def _teks(varian: str, ciri, bangun, a, b) -> str:
    if varian == "sumbu_simetri":
        return f"Berapa banyak sumbu simetri {NAMA[varian][bangun]}?"
    if varian == "pasang_sejajar":
        return f"Berapa pasang sisi sejajar yang dimiliki {NAMA[varian][bangun]}?"
    if varian == "banyak_sudut_siku":
        return f"Berapa banyak sudut siku-siku yang dimiliki {NAMA[varian][bangun]}?"
    return (f"{_kapital(NAMA[ciri][a])} punya ... {FRASA[ciri]} lebih banyak daripada "
            f"{NAMA[ciri][b]}.")


def _fakta_kalimat(ciri: str, bangun: str) -> str:
    return (f"{_kapital(NAMA[ciri][bangun])} punya {_nilai(ciri, bangun)} {FRASA[ciri]}: "
            f"{ALASAN[ciri][bangun]}.")


def _pembahasan(varian: str, ciri, bangun, a, b, kunci: int) -> str:
    if varian != "selisih_ciri":
        return (f"{PENGANTAR[varian]} {_fakta_kalimat(varian, bangun)} "
                f"Jadi jawabannya {kunci}.")
    va, vb = _nilai(ciri, a), _nilai(ciri, b)
    return (f"{PENGANTAR[ciri]} Cari dulu banyaknya pada tiap bangun. "
            f"{_fakta_kalimat(ciri, a)} {_fakta_kalimat(ciri, b)} "
            f"Selisihnya {va} − {vb} = {kunci}. Jadi jawabannya {kunci}.")


def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _slug(bangun: str) -> str:
    return bangun.replace(" ", "_").replace("-", "_")


def _kandidat_tertukar(ciri: str, bangun: str) -> list:
    return [
        _mal(f"{ciri}_tertukar_{_slug(lain)}", nilai, "K",
             f"Menyebut banyak {FRASA[ciri]} milik {NAMA[ciri][lain]} ({nilai}), "
             "kemungkinan tertukar dengan bangun di sebelahnya.")
        for lain, nilai in FAKTA[ciri] if lain != bangun
    ]


def _kandidat_ciri_lain(ciri: str, bangun: str, kunci: int) -> list:
    sisi = SISI[bangun]
    kandidat = []
    if ciri == "pasang_sejajar":
        kandidat.append(_mal(
            "sisi_sejajar_bukan_pasangan", 2 * kunci, "K",
            f"Menghitung sisi yang sejajar satu per satu ({2 * kunci}), bukan pasangannya."))
    if ciri == "sumbu_simetri" and SISI[bangun] == 4:
        kandidat.append(_mal(
            "sumbu_dikira_diagonal", DIAGONAL_SEGIEMPAT, "K",
            f"Menyebut banyak diagonal ({DIAGONAL_SEGIEMPAT}), bukan sumbu simetri."))
    nama = {"sumbu_simetri": "sumbu_sama_sisi", "pasang_sejajar": "pasangan_sama_sisi",
            "banyak_sudut_siku": "siku_sama_semua_sudut"}[ciri]
    kandidat.append(_mal(
        nama, sisi, "K",
        f"Menyebut banyak {'sisi' if ciri != 'banyak_sudut_siku' else 'sudut'} bangunnya "
        f"({sisi}), bukan banyak {FRASA[ciri]}."))
    return kandidat


def _kandidat_h_sudut(kunci: int) -> list:
    kandidat = [_mal("siku_terhitung_dobel", kunci + 1, "H",
                     f"Sudah mengerti caranya, tetapi satu sudut terhitung dua kali sehingga "
                     f"jawabannya {kunci + 1}.")]
    if kunci >= 1:
        kandidat.insert(0, _mal("siku_terlewat", kunci - 1, "H",
                                f"Sudah mengerti caranya, tetapi satu sudut terlewat sehingga "
                                f"jawabannya {kunci - 1}."))
    return kandidat


def _kandidat_selisih(ciri: str, a: str, b: str, kunci: int) -> list:
    va, vb = _nilai(ciri, a), _nilai(ciri, b)
    return [
        _mal("selisih_nilai_pertama", va, "K",
             f"Hanya menyebut banyak {FRASA[ciri]} bangun pertama ({va}) tanpa "
             "membandingkan dengan bangun kedua."),
        _mal("selisih_nilai_kedua", vb, "K",
             f"Hanya menyebut banyak {FRASA[ciri]} bangun kedua ({vb}) tanpa "
             "membandingkan dengan bangun pertama."),
        _mal("selisih_dijumlah", va + vb, "H",
             f"Sudah tahu banyaknya, tetapi menjumlahkan {va} dan {vb}, bukan "
             f"mencari selisihnya, sehingga jawabannya {va + vb}."),
        _mal("selisih_dibalik", -kunci, "H",
             f"Sudah tahu banyaknya, tetapi mengurangkan terbalik ({vb} − {va}) "
             f"sehingga jawabannya {-kunci}."),
        _mal("selisih_lebih_satu", kunci + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan selisih meleset satu "
             f"sehingga jawabannya {kunci + 1}."),
        _mal("selisih_kurang_satu", kunci - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan selisih meleset satu "
             f"sehingga jawabannya {kunci - 1}."),
    ]


def _kandidat(varian: str, ciri, bangun, a, b, kunci: int) -> list:
    if varian == "selisih_ciri":
        return _kandidat_selisih(ciri, a, b, kunci)
    kandidat = _kandidat_tertukar(varian, bangun) + _kandidat_ciri_lain(varian, bangun, kunci)
    if varian == "banyak_sudut_siku":
        kandidat += _kandidat_h_sudut(kunci)
    return kandidat


def _kunci(varian: str, ciri, bangun, a, b) -> int:
    if varian == "selisih_ciri":
        return _nilai(ciri, a) - _nilai(ciri, b)
    return _nilai(varian, bangun)


def bandingkan_ciri_bangun(varian: str, ciri: str | None = None, bangun: str | None = None,
                           a: str | None = None, b: str | None = None) -> Soal:
    """Sumbu simetri, pasang sisi sejajar, sudut siku-siku, atau selisihnya (kunci dari fakta)."""
    if not _sah(varian, ciri, bangun, a, b):
        raise ValueError(PESAN_LUAR_DOMAIN)
    parameter = {"varian": varian}
    if varian == "selisih_ciri":
        parameter.update(ciri=ciri, a=a, b=b)
    else:
        parameter["bangun"] = bangun
    kunci = _kunci(varian, ciri, bangun, a, b)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter,
        teks=_teks(varian, ciri, bangun, a, b), kunci=str(kunci),
        malrule=saring_malrule(str(kunci), _kandidat(varian, ciri, bangun, a, b, kunci)),
        pembahasan=_pembahasan(varian, ciri, bangun, a, b, kunci), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi() -> tuple:
    hasil = [{"varian": c, "bangun": nama} for c in CIRI for nama, _ in FAKTA[c]]
    hasil += [{"varian": "selisih_ciri", "ciri": c, "a": a, "b": b}
              for c in CIRI for a, b in _pasangan_selisih(c)]
    return tuple(hasil)


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level bandingkan ciri bangun harus P5")


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
