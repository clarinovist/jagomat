"""Matematika Awal, jenis `pecahan_campur_awal` (P6): bentuk bilangan campur. Teks saja.

Melengkapi jenis lama `pecahan_bilangan_asli_desimal` (modul itu TIDAK diubah), yang sengaja
menghindari hasil bilangan campur. Buku K6 B1 memakai bilangan campur sebagai hasil kali dan bagi
pecahan dengan bilangan asli; jenis ini melatih bentuk itu.

Lima bentuk soal (`varian`):
  - `tak_wajar_ke_campur`: "Ubah pecahan tak wajar 17/5 menjadi bilangan campur" (kunci "3 2/5");
  - `campur_ke_tak_wajar`: kebalikannya, "3 2/5 menjadi pecahan tak wajar" (kunci "17/5");
  - `kali_asli_campur`: pecahan wajar x bilangan asli (dua urutan), hasil bilangan campur;
  - `campur_kali_asli`: bilangan campur x bilangan asli (dua urutan), hasil bilangan campur;
  - `bagi_campur_asli`: pecahan tak wajar atau bilangan campur dibagi bilangan asli, hasil campur.

Konvensi kunci: teks persis "w n/d" (bilangan bulat, SATU spasi, pecahan wajar paling sederhana),
dengan w >= 1, 0 < n < d, FPB(n, d) = 1, d 2..12, w paling besar 9 ("9 11/12" yang terpanjang).
Satu pengecualian: `campur_ke_tak_wajar` berkunci pecahan tak wajar paling sederhana "a/b".
Kunci tidak pernah bilangan bulat: setiap domain disaring agar hasilnya bukan bilangan bulat.
Pembanding bawaan `diagnosis.setara` membandingkan TEKS ternormalisasi, jadi bentuknya dituntut:
"1 1/5" benar, tetapi "6/5" (bernilai sama, tidak diubah ke campur) salah; karena itu kalimat soal
selalu menyebut bentuk yang diminta dan memberi contoh bentuk yang tidak sama dengan jawabannya.

Domain disaring: pecahan wajar FPB 1 berpenyebut 2..12; bilangan asli 2..9; pembilang pecahan tak
wajar paling besar 99; hasil kali dan bagi kurang dari 10, bukan bilangan bulat, dan (untuk bagi)
berpenyebut paling besar 12 setelah disederhanakan.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu
jawaban. Jalur K: hasil tidak diubah ke campur (nilainya benar, bentuknya salah), pecahan sisa
tidak disederhanakan, bagian bulat dan sisa tertukar, bagian bulat saja yang dikali atau dibagi,
operasi tertukar (bagi jadi kali), pembilang dan penyebut tertukar. Jalur H: bagian bulat atau
sisa meleset satu. Teks jawaban dedupe menurut TEKS (bentuk penting pada isian); lapisan pilihan
ganda membuang yang bernilai sama dengan kunci.

Domain eksplisit (`domain_parameter`); validasi = menjadi anggota domain itu. Sampler memilih
varian seragam dulu lalu satu parameter dalam varian itu memakai `rng` saja (tanpa `hash()`).
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from math import gcd
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "pecahan_campur_awal"
LEVEL = ("P6",)
VARIAN = ("tak_wajar_ke_campur", "campur_ke_tak_wajar", "kali_asli_campur",
          "campur_kali_asli", "bagi_campur_asli")
PESAN_LUAR_DOMAIN = "parameter bilangan campur di luar domain"

PENYEBUT = range(2, 13)
PENYEBUT_HASIL_MAKS = 12
BILANGAN_ASLI = range(2, 10)
BULAT_MAKS = 9
HASIL_MAKS = 10
PEMBILANG_MAKS = 99
OPERAN_BAGI_MAKS = 20
BULAT_OPERAN_KALI = range(1, 5)
ARAH = (0, 1)
BENTUK_BAGI = ("biasa", "campur")
CONTOH_CAMPUR = "2 1/3"
CONTOH_CAMPUR_LAIN = "1 1/2"
CONTOH_TAK_WAJAR = "7/3"
CONTOH_TAK_WAJAR_LAIN = "5/2"


# ── hitungan dan penulisan murni ─────────────────────────────────────────

def _teks_biasa(x: Fraction) -> str:
    """Pecahan paling sederhana; bilangan bulat tanpa penyebut."""
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def _teks_campur(x: Fraction) -> str:
    """"w n/d" untuk nilai lebih dari 1 yang bukan bilangan bulat; selain itu bentuk biasa."""
    bulat, sisa = divmod(x.numerator, x.denominator)
    if bulat == 0 or sisa == 0:
        return _teks_biasa(x)
    return f"{bulat} {sisa}/{x.denominator}"


def _campur_sungguhan(x: Fraction) -> bool:
    return x > 1 and x.denominator != 1


def _pecahan_wajar_sah(a: int, b: int) -> bool:
    return b in PENYEBUT and 0 < a < b and gcd(a, b) == 1


def _operan_wajar() -> list:
    return [(a, b) for b in PENYEBUT for a in range(1, b) if _pecahan_wajar_sah(a, b)]


def _hasil_campur_sah(x: Fraction) -> bool:
    """Bilangan campur sungguhan: lebih dari 1, bukan bulat, bagian bulat <= 9, penyebut <= 12."""
    return (_campur_sungguhan(x) and x < HASIL_MAKS
            and x.denominator <= PENYEBUT_HASIL_MAKS)


def _contoh_campur(kunci: str) -> str:
    return CONTOH_CAMPUR_LAIN if kunci == CONTOH_CAMPUR else CONTOH_CAMPUR


def _contoh_tak_wajar(kunci: str) -> str:
    return CONTOH_TAK_WAJAR_LAIN if kunci == CONTOH_TAK_WAJAR else CONTOH_TAK_WAJAR


def _akhiran_campur(kunci: str) -> str:
    return (f"(tulis hasilnya sebagai bilangan campur paling sederhana, contoh bentuknya "
            f"{_contoh_campur(kunci)})")


def _mal(nama: str, jawaban: str, kode: str, kemungkinan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", jawaban, kode,
                   f"Menjawab {jawaban}: kemungkinan {kemungkinan}.")


def _rapikan(kunci: str, kandidat: list) -> tuple:
    """Buang kandidat yang sama dengan kunci atau kandidat sebelumnya (menurut teks)."""
    return saring_malrule(kunci, kandidat)


def _varian_hitung(x: Fraction) -> list:
    """Jalur H: bagian bulat atau pecahan sisa meleset satu dari bilangan campur `x`."""
    bulat, sisa = divmod(x.numerator, x.denominator)
    d = x.denominator
    hasil = [_mal("bulat_lebih_satu", f"{bulat + 1} {sisa}/{d}", "H",
                  "bagian bulatnya salah hitung, lebih satu dari seharusnya")]
    if bulat > 1:
        hasil.append(_mal("bulat_kurang_satu", f"{bulat - 1} {sisa}/{d}", "H",
                          "bagian bulatnya salah hitung, kurang satu dari seharusnya"))
    if sisa + 1 < d:
        hasil.append(_mal("sisa_lebih_satu", f"{bulat} {sisa + 1}/{d}", "H",
                          "pembilang pecahan sisanya salah hitung, lebih satu dari seharusnya"))
    if sisa > 1:
        hasil.append(_mal("sisa_kurang_satu", f"{bulat} {sisa - 1}/{d}", "H",
                          "pembilang pecahan sisanya salah hitung, kurang satu dari seharusnya"))
    return hasil


def _mal_tak_diubah(x: Fraction) -> Malrule:
    return _mal("hasil_tak_diubah_ke_campur", _teks_biasa(x), "K",
                "hasilnya sudah benar nilainya tetapi tidak diubah ke bilangan campur, "
                "padahal soal meminta bilangan campur")


def _mal_tak_disederhanakan(pembilang: int, penyebut: int) -> Malrule:
    bulat, sisa = divmod(pembilang, penyebut)
    return _mal("sisa_tidak_disederhanakan", f"{bulat} {sisa}/{penyebut}", "K",
                f"pecahan sisanya {sisa}/{penyebut} tidak disederhanakan")


def _sederhanakan_teks(pembilang: int, penyebut: int, hasil: str) -> str:
    g = gcd(pembilang, penyebut)
    if g == 1:
        return ""
    return (f" Sederhanakan {pembilang}/{penyebut} dengan membagi pembilang dan penyebut "
            f"dengan {g}: {hasil}.")


def _langkah_ke_campur(pembilang: int, penyebut: int) -> str:
    """Pembagian bersisa pembilang oleh penyebut, lalu sederhanakan sisanya bila perlu."""
    bulat, sisa = divmod(pembilang, penyebut)
    x = Fraction(sisa, penyebut)
    awal = (f"Ubah {pembilang}/{penyebut} menjadi bilangan campur: {pembilang} ÷ {penyebut} = "
            f"{bulat} sisa {sisa}. Hasil bagi {bulat} menjadi bilangan bulat, sisa {sisa} menjadi "
            f"pembilang, penyebut tetap {penyebut}, jadi {bulat} {sisa}/{penyebut}.")
    return awal + _sederhanakan_teks(sisa, penyebut, f"{x.numerator}/{x.denominator}")


# ── tak wajar -> campur ──────────────────────────────────────────────────

def _tertukar(bulat: int, sisa: int, b: int) -> list:
    """Jalur K bulat dan sisa tertukar; hanya bila hasilnya bilangan campur sah (bagian pecahan < 1)."""
    if bulat >= b:
        return []
    return [_mal("bulat_dan_sisa_tertukar", f"{sisa} {bulat}/{b}", "K",
                 "hasil bagi dan sisanya tertukar, sisa ditulis sebagai bilangan bulat")]


def _bangun_tak_wajar_ke_campur(p: dict) -> tuple:
    a, b = p["a"], p["b"]
    x = Fraction(a, b)
    kunci = _teks_campur(x)
    bulat, sisa = divmod(a, b)
    teks = (f"Ubah pecahan tak wajar {a}/{b} menjadi bilangan campur. Jawabannya ... "
            f"(tulis bilangan bulat, spasi, lalu pecahan; contoh {_contoh_campur(kunci)})")
    kandidat = _tertukar(bulat, sisa, b) + [
        _mal("sisa_per_pembilang", f"{bulat} {sisa}/{a}", "K",
             f"sisa dibagikan pada pembilang {a}, bukan pada penyebut {b}"),
        _mal("sisa_terlupa", str(bulat), "K",
             "hanya hasil bagi yang ditulis, sisa pembagiannya terlupa"),
    ] + _varian_hitung(x)
    return teks, kunci, kandidat, f"{_langkah_ke_campur(a, b)} Jadi {a}/{b} = {kunci}."


# ── campur -> tak wajar ──────────────────────────────────────────────────

def _bangun_campur_ke_tak_wajar(p: dict) -> tuple:
    w, a, b = p["w"], p["a"], p["b"]
    x = Fraction(w * b + a, b)
    kunci = _teks_biasa(x)
    teks = (f"Ubah bilangan campur {w} {a}/{b} menjadi pecahan tak wajar paling sederhana. "
            f"Jawabannya ... (tulis dengan garis miring, contoh {_contoh_tak_wajar(kunci)})")
    kandidat = [
        _mal("bulat_ditambah_pembilang", f"{w + a}/{b}", "K",
             f"bilangan bulat {w} dijumlahkan dengan pembilang {a}, bukan dikalikan dengan "
             f"penyebut {b}"),
        _mal("bulat_dikali_pembilang", f"{w * a}/{b}", "K",
             f"bilangan bulat {w} dikalikan dengan pembilang {a}"),
        _mal("angka_berdampingan", f"{w}{a}/{b}", "K",
             "bilangan bulat dan pembilang ditulis berdampingan sebagai pembilang"),
        _mal("pembilang_tidak_ditambah", f"{w * b}/{b}", "K",
             f"bilangan bulat dikalikan penyebut, tetapi pembilang {a} lupa ditambahkan"),
        _mal("pembilang_penyebut_tertukar", f"{b}/{w * b + a}", "K",
             "pembilang dan penyebut hasilnya tertukar"),
    ]
    cara = (f"Kalikan bilangan bulat dengan penyebut, lalu tambahkan pembilangnya: "
            f"{w} × {b} + {a} = {w * b + a}. Penyebutnya tetap {b}. "
            f"Jadi {w} {a}/{b} = {kunci}.")
    return teks, kunci, kandidat, cara


# ── kali pecahan dengan bilangan asli ────────────────────────────────────

def _bangun_kali_asli_campur(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    x = Fraction(a * n, b)
    kunci = _teks_campur(x)
    ekspresi = f"{a}/{b} × {n}" if p["urut"] == 0 else f"{n} × {a}/{b}"
    teks = f"Hitung: {ekspresi} = ... {_akhiran_campur(kunci)}"
    kandidat = [
        _mal_tak_diubah(x),
        _mal_tak_disederhanakan(a * n, b),
        _mal("pembilang_penyebut_sama_dikali", _teks_biasa(Fraction(a, b)), "K",
             f"pembilang dan penyebut sama-sama dikalikan {n}, sehingga nilai pecahannya tidak "
             "berubah"),
        _mal("kali_penyebut_saja", _teks_biasa(Fraction(a, b * n)), "K",
             f"hanya penyebut yang dikalikan {n}, sedangkan pembilangnya dibiarkan"),
        _mal("tambah_pembilang", _teks_biasa(Fraction(a + n, b)), "K",
             f"pembilang ditambah {n}, bukan dikalikan {n}"),
    ] + _varian_hitung(x)
    tukar = (f"Bilangan asli boleh ditukar tempatnya: {n} × {a}/{b} = {a}/{b} × {n}. "
             if p["urut"] == 1 else "")
    cara = (f"{tukar}Kalikan pembilang dengan {n}, penyebutnya tetap: {a} × {n} = {a * n}, "
            f"jadi {a * n}/{b}. {_langkah_ke_campur(a * n, b)} "
            f"Jadi {ekspresi} = {kunci}.")
    return teks, kunci, kandidat, cara


def _bulat_tidak_ikut_dikali(w: int, a: int, b: int, n: int) -> list:
    """Jalur K bagian bulat tidak dikali; hanya bila a x n < b (bagian pecahan tetap wajar)."""
    if a * n >= b:
        return []
    return [_mal("bulat_tidak_ikut_dikali", f"{w} {a * n}/{b}", "K",
                 f"hanya pembilang {a} yang dikalikan {n}, bilangan bulat {w} dibiarkan")]


def _bangun_campur_kali_asli(p: dict) -> tuple:
    w, a, b, n = p["w"], p["a"], p["b"], p["n"]
    atas = w * b + a
    x = Fraction(atas * n, b)
    kunci = _teks_campur(x)
    operan = f"{w} {a}/{b}"
    ekspresi = f"{operan} × {n}" if p["urut"] == 0 else f"{n} × {operan}"
    teks = f"Hitung: {ekspresi} = ... {_akhiran_campur(kunci)}"
    kandidat = [
        _mal_tak_diubah(x),
        _mal("pecahan_tidak_ikut_dikali", f"{w * n} {a}/{b}", "K",
             f"hanya bilangan bulat {w} yang dikalikan {n}, pecahan {a}/{b} dibiarkan"),
        _mal_tak_disederhanakan(atas * n, b),
        _mal("nilai_awal_tidak_berubah", operan, "K",
             f"pembilang dan penyebut sama-sama dikalikan {n}, sehingga nilainya tidak berubah"),
    ] + _bulat_tidak_ikut_dikali(w, a, b, n) + _varian_hitung(x)
    tukar = (f"Bilangan asli boleh ditukar tempatnya: {n} × {operan} = {operan} × {n}. "
             if p["urut"] == 1 else "")
    cara = (f"{tukar}Ubah {operan} menjadi pecahan biasa: {w} × {b} + {a} = {atas}, jadi "
            f"{atas}/{b}. Kalikan pembilang dengan {n}: {atas} × {n} = {atas * n}, jadi "
            f"{atas * n}/{b}. {_langkah_ke_campur(atas * n, b)} "
            f"Jadi {ekspresi} = {kunci}.")
    return teks, kunci, kandidat, cara


# ── bagi dengan bilangan asli ────────────────────────────────────────────

def _teks_operan_bagi(p: dict) -> str:
    a, b = p["a"], p["b"]
    return f"{a}/{b}" if p["bentuk"] == "biasa" else f"{a // b} {a % b}/{b}"


def _kandidat_bagi(p: dict, y: Fraction) -> list:
    a, b, n = p["a"], p["b"], p["n"]
    x = Fraction(a, b)
    kandidat = [
        _mal_tak_diubah(y),
        _mal("bagi_jadi_kali", _teks_campur(x * n), "K",
             f"pecahan dikalikan {n}, padahal diminta dibagi {n}"),
        _mal("operan_tidak_berubah", _teks_operan_bagi(p), "K",
             f"pembilang dan penyebut sama-sama dikalikan {n}, sehingga nilainya tidak berubah"),
        _mal("bilangan_asli_dibagi_pecahan", _teks_campur(Fraction(n) / x), "K",
             f"yang dibagi dan pembagi tertukar, jadi {n} dibagi pecahan"),
    ]
    if a // b >= n:
        kandidat.append(_mal("bulat_dibagi_pecahan_tetap", f"{a // b // n} {a % b}/{b}", "K",
                             f"hanya bilangan bulat {a // b} yang dibagi {n}, pecahan "
                             f"{a % b}/{b} dibiarkan"))
    return kandidat + _varian_hitung(y)


def _bangun_bagi_campur_asli(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    y = Fraction(a, b * n)
    kunci = _teks_campur(y)
    operan = _teks_operan_bagi(p)
    teks = f"Hitung: {operan} ÷ {n} = ... {_akhiran_campur(kunci)}"
    ubah = (f"Ubah dulu {operan} menjadi pecahan biasa: {a // b} × {b} + {a % b} = {a}, jadi "
            f"{a}/{b}. " if p["bentuk"] == "campur" else "")
    bagi = (f"Membagi dengan {n} sama dengan mengalikan dengan 1/{n}: {a}/{b} ÷ {n} = "
            f"{a}/{b} × 1/{n} = {a}/{b * n}.")
    sederhana = _sederhanakan_teks(a, b * n, f"{y.numerator}/{y.denominator}")
    cara = (f"{ubah}{bagi}{sederhana} {_langkah_ke_campur(y.numerator, y.denominator)} "
            f"Jadi {operan} ÷ {n} = {kunci}.")
    return teks, kunci, _kandidat_bagi(p, y), cara


_BANGUN = {
    "tak_wajar_ke_campur": _bangun_tak_wajar_ke_campur,
    "campur_ke_tak_wajar": _bangun_campur_ke_tak_wajar,
    "kali_asli_campur": _bangun_kali_asli_campur,
    "campur_kali_asli": _bangun_campur_kali_asli,
    "bagi_campur_asli": _bangun_bagi_campur_asli,
}


# ── domain eksplisit ─────────────────────────────────────────────────────

def _enumerasi_tak_wajar_ke_campur() -> list:
    return [{"varian": "tak_wajar_ke_campur", "a": a, "b": b}
            for b in PENYEBUT for a in range(b + 1, BULAT_MAKS * b + b)
            if a <= PEMBILANG_MAKS and a % b != 0 and gcd(a % b, b) == 1]


def _enumerasi_campur_ke_tak_wajar() -> list:
    return [{"varian": "campur_ke_tak_wajar", "w": w, "a": a, "b": b}
            for a, b in _operan_wajar() for w in range(1, BULAT_MAKS + 1)
            if w * b + a <= PEMBILANG_MAKS]


def _enumerasi_kali_asli_campur() -> list:
    return [{"varian": "kali_asli_campur", "a": a, "b": b, "n": n, "urut": urut}
            for a, b in _operan_wajar() for n in BILANGAN_ASLI
            if _hasil_campur_sah(Fraction(a * n, b)) for urut in ARAH]


def _enumerasi_campur_kali_asli() -> list:
    return [{"varian": "campur_kali_asli", "w": w, "a": a, "b": b, "n": n, "urut": urut}
            for w in BULAT_OPERAN_KALI for a, b in _operan_wajar() for n in BILANGAN_ASLI
            if _hasil_campur_sah(Fraction((w * b + a) * n, b)) for urut in ARAH]


def _enumerasi_bagi_campur_asli() -> list:
    hasil = []
    for b in PENYEBUT:
        for a in range(b + 1, OPERAN_BAGI_MAKS * b):
            if a > PEMBILANG_MAKS or gcd(a, b) != 1:
                continue
            hasil.extend({"varian": "bagi_campur_asli", "a": a, "b": b, "n": n, "bentuk": bentuk}
                         for n in BILANGAN_ASLI if _hasil_campur_sah(Fraction(a, b * n))
                         for bentuk in BENTUK_BAGI)
    return hasil


_ENUMERATOR = {
    "tak_wajar_ke_campur": _enumerasi_tak_wajar_ke_campur,
    "campur_ke_tak_wajar": _enumerasi_campur_ke_tak_wajar,
    "kali_asli_campur": _enumerasi_kali_asli_campur,
    "campur_kali_asli": _enumerasi_campur_kali_asli,
    "bagi_campur_asli": _enumerasi_bagi_campur_asli,
}


def _beku(p: dict) -> tuple:
    return tuple(sorted(p.items()))


@lru_cache(maxsize=None)
def _domain_varian_beku(varian: str) -> tuple:
    """Parameter satu varian sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(_beku(p) for p in _ENUMERATOR[varian]())


@lru_cache(maxsize=None)
def _anggota() -> frozenset:
    return frozenset(item for varian in VARIAN for item in _domain_varian_beku(varian))


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level bilangan campur harus P6")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah (P6); dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for varian in VARIAN for item in _domain_varian_beku(varian))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu parameter seragam dalam varian itu; tanpa rejection."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return dict(rng.choice(_domain_varian_beku(varian)))


# ── soal ─────────────────────────────────────────────────────────────────

def _sah(parameter_: dict) -> bool:
    if any(type(nilai) not in (int, str) for nilai in parameter_.values()):
        return False
    try:
        return _beku(parameter_) in _anggota()
    except TypeError:
        return False


def pecahan_campur_awal(varian: str, a: int | None = None, b: int | None = None,
                        n: int | None = None, w: int | None = None, urut: int | None = None,
                        bentuk: str | None = None) -> Soal:
    """Bentuk bilangan campur; kunci dihitung dari parameter sah."""
    diberi = {"varian": varian, "a": a, "b": b, "n": n, "w": w, "urut": urut, "bentuk": bentuk}
    p = {nama: nilai for nama, nilai in diberi.items() if nilai is not None}
    if not _sah(p):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, kandidat, pembahasan = _BANGUN[varian](p)
    return Soal(template_id=TEMPLATE_ID, parameter=p, teks=teks, kunci=kunci,
                malrule=_rapikan(kunci, kandidat), pembahasan=pembahasan, bagian="A")
