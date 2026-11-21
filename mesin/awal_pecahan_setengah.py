"""Matematika Awal, jenis `pecahan_setengah`: separuh dan seperempat (P2), teks saja.

Empat bentuk soal (`varian`), semuanya kunci ANGKA agar mudah diisi:
  - `separuh`: "Dita punya 12 kelereng. Separuhnya diberikan kepada Budi. Berapa
    kelereng yang diberikan kepada Budi?";
  - `seperempat`: seperempat dari n (n kelipatan 4, n >= 8, n <= 40);
  - `potong_sama`: dari nama pecahan ("Satu bagian besarnya seperempat roti") ke
    banyak bagian sama besar yang menyusun satu utuh (2 atau 4);
  - `sisa`: setelah separuh atau seperempat diberikan, berapa yang masih dimiliki.

Semua hasil bagi bilangan bulat dan angka kecil kelas 2 (<= 40). Angka TIDAK
dilebarkan demi hitungan: tiap daftar jumlah benda ditulis eksplisit di bawah.
`separuh` n genap; `seperempat` dan `sisa` memakai kelipatan 4 pada bagian
seperempat (dan separuh pada `sisa` juga dibatasi ke kelipatan 4 supaya jalur K
"separuh dikira seperempat" selalu berupa bilangan bulat). `seperempat` n=4
dikeluarkan: hasilnya 1, jadi "kurang satu" menjadi 0 (bukan kesalahan nyata).

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban. K: tidak membagi (menyebut jumlah semuanya), pecahan tertukar
(separuh dikira seperempat dan sebaliknya), menjawab bagian yang diberikan padahal
yang ditanya sisa, atau menyebut hanya "1 bagian" pada `potong_sama`. H: salah
hitung kurang satu. Jawaban yang kebetulan sama dengan kunci dibuang
`saring_malrule`; setiap soal tetap menyisakan >= 2 jawaban salah berbeda (cukup
untuk pilihan ganda `tiga-v1` tanpa pengecoh tambahan).

Kunci angka tanpa spasi. Domain kecil dan eksplisit (`domain_parameter`): sampler
hanya mengundi dari domain itu memakai `rng` (tanpa `hash()`), jadi seed yang sama
selalu menghasilkan soal yang sama lintas proses. Semua parameter skalar; `cerita`
dan `benda` adalah indeks ke CERITA/BENDA_UTUH yang bersifat APPEND-ONLY karena
indeks ikut dalam identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "pecahan_setengah"
LEVEL = ("P2",)
VARIAN = ("separuh", "seperempat", "potong_sama", "sisa")
PESAN_LUAR_DOMAIN = "parameter pecahan setengah di luar domain"

# (pemilik, penerima, benda jamak); nama sintetis umum. Append-only menurut indeks.
CERITA = (("Dita", "Budi", "kelereng"), ("Rina", "Eko", "permen"), ("Sari", "Tono", "stiker"))
BENDA_UTUH = ("roti", "pizza", "kue")
PECAHAN_POTONG = {"setengah": 2, "seperempat": 4}
PENYEBUT = {"separuh": 2, "seperempat": 4}
# Jumlah benda yang sah, eksplisit (genap untuk separuh, kelipatan 4 untuk seperempat).
N_SEPARUH = (6, 8, 10, 12, 14, 16, 18, 20)
N_SEPEREMPAT = (8, 12, 16, 20, 24, 28, 32, 40)
N_SISA = {"separuh": (8, 12, 16, 20), "seperempat": (8, 12, 16, 20, 24, 32)}

KUNCI_BAGIAN = frozenset({"varian", "n", "cerita"})
KUNCI_POTONG = frozenset({"varian", "pecahan", "benda"})
KUNCI_SISA = frozenset({"varian", "bagian", "n", "cerita"})


def _int_sah(nilai, bawah: int, atas: int) -> bool:
    """Bilangan bulat murni (bukan bool, bukan float) dalam bawah..atas termasuk."""
    return type(nilai) is int and bawah <= nilai <= atas


def _teks_sah(nilai, pilihan) -> bool:
    return type(nilai) is str and nilai in pilihan


def _sah(p: dict) -> bool:
    varian = p.get("varian")
    if varian in ("separuh", "seperempat"):
        daftar = N_SEPARUH if varian == "separuh" else N_SEPEREMPAT
        return (set(p) == KUNCI_BAGIAN and type(p["n"]) is int and p["n"] in daftar
                and _int_sah(p["cerita"], 0, len(CERITA) - 1))
    if varian == "potong_sama":
        return (set(p) == KUNCI_POTONG and _teks_sah(p["pecahan"], PECAHAN_POTONG)
                and _int_sah(p["benda"], 0, len(BENDA_UTUH) - 1))
    if varian == "sisa":
        return (set(p) == KUNCI_SISA and _teks_sah(p["bagian"], N_SISA)
                and type(p["n"]) is int and p["n"] in N_SISA[p["bagian"]]
                and _int_sah(p["cerita"], 0, len(CERITA) - 1))
    return False


# ── teks, malrule, pembahasan ────────────────────────────────────────────

def _frasa_bagian(bagian: str, benda: str) -> str:
    return "Separuhnya" if bagian == "separuh" else f"Seperempat dari {benda} itu"


def _soal_cerita(p: dict) -> Soal:
    varian = p["varian"]
    bagian = p["bagian"] if varian == "sisa" else varian
    n, d = p["n"], PENYEBUT[bagian]
    pemilik, penerima, benda = CERITA[p["cerita"]]
    diberikan = n // d
    if varian == "sisa":
        tanya = f"Berapa {benda} yang masih dimiliki {pemilik}?"
        kunci = n - diberikan
        pembahasan = (f"Yang diberikan: {n} ÷ {d} = {diberikan}. Sisanya: {n} − {diberikan} = {kunci}. "
                      f"Jadi {pemilik} masih punya {kunci} {benda}.")
        kandidat = _malrule_sisa(bagian, n)
    else:
        tanya = f"Berapa {benda} yang diberikan kepada {penerima}?"
        kunci = diberikan
        kata = "dibagi 2" if d == 2 else "dibagi 4"
        pembahasan = (f"{bagian.capitalize()} berarti {kata} sama banyak. {n} ÷ {d} = {diberikan}. "
                      f"Jadi {penerima} mendapat {diberikan} {benda}.")
        kandidat = _malrule_bagian(bagian, n)
    teks = (f"{pemilik} punya {n} {benda}. {_frasa_bagian(bagian, benda)} diberikan kepada "
            f"{penerima}. {tanya}")
    return _bangun(p, teks, str(kunci), kandidat, pembahasan)


def _k(nama: str, nilai: int, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(nilai), "K", alasan)


def _h(nama: str, nilai: int, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(nilai), "H", alasan)


def _malrule_bagian(bagian: str, n: int) -> list:
    k = n // PENYEBUT[bagian]
    if bagian == "separuh":
        kandidat = [_k("separuh_tidak_dibagi", n,
                       "Menyebut jumlah semuanya, kemungkinan belum membagi dua sama banyak.")]
        if n % 4 == 0:
            kandidat.append(_k("separuh_dikira_seperempat", n // 4,
                               "Membagi 4 padahal yang diminta separuh, kemungkinan tertukar "
                               "dengan seperempat."))
    else:
        kandidat = [
            _k("seperempat_dikira_separuh", n // 2,
               "Membagi 2 padahal yang diminta seperempat, kemungkinan tertukar dengan separuh."),
            _k("seperempat_jawab_sisa", 3 * k,
               "Menyebut banyak yang tersisa, bukan yang diberikan."),
        ]
    kandidat.append(_h("kurang_satu", k - 1,
                       "Sudah mengerti caranya, tetapi salah hitung kurang satu."))
    return kandidat


def _malrule_sisa(bagian: str, n: int) -> list:
    sisa = n - n // PENYEBUT[bagian]
    if bagian == "separuh":
        kandidat = [_k("sisa_separuh_dikira_seperempat", 3 * n // 4,
                       "Menghitung sisa setelah seperempat, kemungkinan tertukar dengan separuh.")]
    else:
        kandidat = [
            _k("sisa_jawab_bagian", n // 4,
               "Menyebut banyak yang diberikan, bukan yang masih tersisa."),
            _k("sisa_seperempat_dikira_separuh", n // 2,
               "Menghitung sisa setelah separuh, kemungkinan tertukar dengan seperempat."),
        ]
    kandidat.append(_k("sisa_belum_dikurangi", n,
                       "Menyebut jumlah awal, kemungkinan belum mengurangi yang diberikan."))
    kandidat.append(_h("sisa_kurang_satu", sisa - 1,
                       "Sudah mengerti caranya, tetapi salah hitung kurang satu."))
    return kandidat


def _soal_potong(p: dict) -> Soal:
    pecahan, benda = p["pecahan"], BENDA_UTUH[p["benda"]]
    d = PECAHAN_POTONG[pecahan]
    teks = (f"Sebuah {benda} dipotong menjadi bagian-bagian yang sama besar. Satu bagian besarnya "
            f"{pecahan} {benda}. Berapa bagian sama besar itu yang menyusun satu {benda} utuh?")
    pembahasan = (f"{pecahan.capitalize()} berarti satu dari {d} bagian yang sama besar. "
                  f"Jadi untuk membuat satu {benda} utuh, perlu {d} bagian sama besar. "
                  f"Jawabannya {d}.")
    lain = 2 if d == 4 else 4
    kandidat = [
        _k("potong_pecahan_tertukar", lain,
           f"Menjawab {lain}, kemungkinan tertukar antara setengah dan seperempat."),
        _k("potong_satu_bagian", 1,
           "Menjawab 1 karena yang disebut hanya satu bagian, belum mengulang bagian itu "
           "sampai membentuk satu utuh."),
        _h("potong_kurang_satu", d - 1,
           "Sudah mengerti caranya, tetapi salah hitung kurang satu."),
    ]
    return _bangun(p, teks, str(d), kandidat, pembahasan)


def _bangun(p: dict, teks: str, kunci: str, kandidat: list, pembahasan: str) -> Soal:
    return Soal(template_id=TEMPLATE_ID, parameter=dict(p), teks=teks, kunci=kunci,
                malrule=saring_malrule(kunci, kandidat), pembahasan=pembahasan, bagian="A")


def pecahan_setengah(varian: str, **parameter) -> Soal:
    """Separuh/seperempat dari jumlah benda, banyak potongan, atau sisa (kunci dari parameter)."""
    lengkap = {"varian": varian, **parameter}
    if not _sah(lengkap):
        raise ValueError(PESAN_LUAR_DOMAIN)
    if varian == "potong_sama":
        return _soal_potong(lengkap)
    return _soal_cerita(lengkap)


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi() -> list:
    ada = range(len(CERITA))
    hasil = [{"varian": "separuh", "n": n, "cerita": c} for n in N_SEPARUH for c in ada]
    hasil += [{"varian": "seperempat", "n": n, "cerita": c} for n in N_SEPEREMPAT for c in ada]
    hasil += [{"varian": "potong_sama", "pecahan": f, "benda": b}
              for f in PECAHAN_POTONG for b in range(len(BENDA_UTUH))]
    hasil += [{"varian": "sisa", "bagian": g, "n": n, "cerita": c}
              for g in N_SISA for n in N_SISA[g] for c in ada]
    return hasil


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level pecahan setengah harus P2")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku())


def parameter(rng: random.Random, level: str) -> dict:
    """Satu undian seragam dari domain terbatas; tanpa rejection atau nudge."""
    _pastikan_level(level)
    return dict(rng.choice(_domain_beku()))
