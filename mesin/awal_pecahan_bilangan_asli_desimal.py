"""Matematika Awal, jenis `pecahan_bilangan_asli_desimal` (P6): pecahan x bilangan asli, ke desimal. Teks saja.

Menutup dua celah template lama `pecahan_kali_bagi` (hanya pecahan x/÷ pecahan): perkalian
dan pembagian pecahan DENGAN BILANGAN ASLI, serta mengubah pecahan dan desimal satu sama lain.

Enam bentuk soal (`varian`):
  - `kali_asli`: "Hitung: 3/8 × 2 = ..." (pecahan x bilangan asli);
  - `bagi_asli`: "Hitung: 2/3 ÷ 4 = ..." (pecahan ÷ bilangan asli);
  - `asli_kali`: "Hitung: 6 × 2/3 = ..." (bilangan asli x pecahan);
  - `ke_desimal`: pecahan berpenyebut 2, 4, 5, 8, 10, 20, atau 25 menjadi desimal berhenti;
  - `desimal_ke_pecahan`: desimal satu atau dua angka menjadi pecahan paling sederhana;
  - `cerita`: satu langkah kali atau bagi pecahan dengan bilangan asli (tali dipotong, gula
    dibagi, minum per hari, berat sejumlah bungkus).

Konvensi kunci (sama dengan `pecahan_kali_bagi` dan `urut_pecahan_desimal_persen`): pecahan
"a/b" PALING SEDERHANA, atau bilangan bulat tanpa penyebut ("6", bukan "6/1"), atau desimal
dengan KOMA dan tanpa nol di belakang ("0,375", "0,5"). Pembanding bawaan (`diagnosis.setara`)
membandingkan teks ternormalisasi: pecahan hanya cocok sebagai string persis (jadi "6/8"
TIDAK sama dengan "3/4"; soal memintanya "paling sederhana"), desimal dinormalisasi koma/titik.

Domain disaring supaya kunci tunggal dan tidak berupa bilangan campur:
  - operan pecahan memakai pembilang < penyebut, penyebut 2..12, FPB 1 (sudah sederhana);
    bilangan asli 2..12;
  - hasil kali: bilangan bulat atau pecahan kurang dari 1 (tidak pernah bilangan campur);
  - hasil bagi (selalu pecahan kurang dari 1): penyebut hasil sederhana paling besar 24;
  - desimal ke pecahan: penyebut paling sederhana 2, 4, 5, 10, 20, atau 25 (desimal satu
    atau dua angka, tanpa bilangan campur).
Penyebut 20 dan 25 pada `ke_desimal` dan `desimal_ke_pecahan` mengikuti sub-materi "Mengubah
pecahan ke desimal"; di luar itu operan tetap berpenyebut paling banyak 12.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu
jawaban. Jalur K: penyebut ikut dikalikan (pembilang dan penyebut sama-sama dikalikan,
nilai tidak berubah), hanya penyebut yang dikalikan, ditambah bukan dikali, pembagian
dikerjakan sebagai perkalian, pecahan yang dibalik padahal pembagi, pembilang dan penyebut
tertukar, titik desimal bergeser, pembilang dan penyebut dipisah koma, angka disusun
di belakang koma, penyebut tak sesuai banyak angka di belakang koma. Tidak ada jalur H
(tidak ada salah hitung yang nyata dan khas di sini). Kandidat yang bernilai sama dengan kunci
atau dengan kandidat lain dibuang menurut NILAI (bukan hanya teks), jadi tiap parameter sah
menyisakan >= 3 jawaban salah berbeda nilai (cukup untuk pilihan ganda `empat-v1` bawaan).

Domain eksplisit (`domain_parameter`); validasi = menjadi anggota domain itu. Sampler memilih
varian seragam dulu lalu satu parameter dalam varian itu memakai `rng` saja (tanpa `hash()`).
`CERITA` bersifat APPEND-ONLY: indeksnya ikut identitas soal di bank.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from math import gcd
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "pecahan_bilangan_asli_desimal"
LEVEL = ("P6",)
VARIAN = ("kali_asli", "bagi_asli", "asli_kali", "ke_desimal", "desimal_ke_pecahan", "cerita")
PESAN_LUAR_DOMAIN = "parameter pecahan dan bilangan asli di luar domain"

PENYEBUT_OPERAN = range(2, 13)
BILANGAN_ASLI = range(2, 13)
PENYEBUT_BAGI_MAKS = 24
PENYEBUT_KE_DESIMAL = (2, 4, 5, 8, 10, 20, 25)
PENYEBUT_DARI_DESIMAL = (2, 4, 5, 10, 20, 25)
AKHIRAN = "(tulis hasilnya dalam bentuk paling sederhana)"
# (operasi, kalimat); {f} = pecahan, {n} = bilangan asli. Append-only menurut indeks.
CERITA = (
    ("bagi", "Sebuah tali panjangnya {f} m dipotong menjadi {n} bagian sama panjang. "
             "Berapa meter panjang tiap bagian?"),
    ("bagi", "Rina mempunyai {f} kg gula. Gula itu dibagi sama banyak ke dalam {n} kantong. "
             "Berapa kilogram gula di tiap kantong?"),
    ("kali", "Setiap hari Budi minum {f} liter air putih. "
             "Berapa liter air putih yang ia minum dalam {n} hari?"),
    ("kali", "Satu bungkus kue beratnya {f} kg. Berapa kilogram berat {n} bungkus kue yang sama?"),
)
# ── hitungan dan penulisan murni ─────────────────────────────────────────

def _teks_pecahan(x: Fraction) -> str:
    """Pecahan paling sederhana; bilangan bulat tanpa penyebut."""
    return str(x.numerator) if x.denominator == 1 else f"{x.numerator}/{x.denominator}"


def _teks_desimal(x: Fraction) -> str:
    """Desimal berhenti dengan KOMA, tanpa nol di belakang ("0,375", "0,5", "5")."""
    k = 0
    while (x * 10 ** k).denominator != 1:
        k += 1
        if k > 6:
            raise ValueError("bukan desimal berhenti")
    angka = int(x * 10 ** k)
    if k == 0:
        return str(angka)
    s = str(angka).rjust(k + 1, "0")
    return f"{s[:-k]},{s[-k:]}"


def _nilai(teks: str) -> Fraction:
    return Fraction(teks.replace(",", "."))


def _pecahan_sah(a: int, b: int) -> bool:
    return b in PENYEBUT_OPERAN and 0 < a < b and gcd(a, b) == 1


def _hasil_kali_sah(a: int, b: int, n: int) -> bool:
    hasil = Fraction(a * n, b)
    return hasil.denominator == 1 or hasil < 1


def _hasil_bagi_sah(a: int, b: int, n: int) -> bool:
    return Fraction(a, b * n).denominator <= PENYEBUT_BAGI_MAKS


def _mal(nama: str, jawaban, alasan: str, teks=_teks_pecahan) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", jawaban if isinstance(jawaban, str) else teks(jawaban),
                   "K", alasan)


def _rapikan(kunci: str, kandidat: list) -> tuple:
    """Buang kandidat yang bernilai sama dengan kunci atau kandidat sebelumnya, lalu saring teks."""
    terpakai = {_nilai(kunci)}
    unik = []
    for m in kandidat:
        nilai = _nilai(m.jawaban)
        if nilai in terpakai:
            continue
        terpakai.add(nilai)
        unik.append(m)
    return saring_malrule(kunci, unik)


# ── kali dan bagi pecahan dengan bilangan asli (dipakai tiga varian + cerita) ─

def _kandidat_kali(a: int, b: int, n: int) -> list:
    hasil = Fraction(a * n, b)
    return [
        _mal("kali_dua_sisi", Fraction(a, b),
             f"Menjawab {_teks_pecahan(Fraction(a, b))}: kemungkinan pembilang dan penyebut "
             f"sama-sama dikalikan {n}, sehingga nilai pecahannya tidak berubah."),
        _mal("kali_penyebut_saja", Fraction(a, b * n),
             f"Menjawab {_teks_pecahan(Fraction(a, b * n))}: kemungkinan hanya penyebut yang "
             f"dikalikan {n}, sedangkan pembilangnya dibiarkan."),
        _mal("tambah_pembilang", Fraction(a + n, b),
             f"Menjawab {_teks_pecahan(Fraction(a + n, b))}: kemungkinan pembilang ditambah {n}, "
             f"bukan dikalikan {n}."),
        _mal("hasil_terbalik", 1 / hasil,
             f"Menjawab {_teks_pecahan(1 / hasil)}: kemungkinan pembilang dan penyebut hasilnya "
             "tertukar."),
    ]


def _kandidat_bagi(a: int, b: int, n: int) -> list:
    hasil = Fraction(a, b * n)
    return [
        _mal("bagi_jadi_kali", Fraction(a * n, b),
             f"Menjawab {_teks_pecahan(Fraction(a * n, b))}: kemungkinan pecahan dikalikan {n}, "
             f"padahal diminta dibagi {n}."),
        _mal("kali_dua_sisi", Fraction(a, b),
             f"Menjawab {_teks_pecahan(Fraction(a, b))}: kemungkinan pembilang dan penyebut "
             f"sama-sama dikalikan {n}, sehingga nilai pecahannya tidak berubah."),
        _mal("pecahan_dibalik", Fraction(b, a * n),
             f"Menjawab {_teks_pecahan(Fraction(b, a * n))}: kemungkinan pecahan yang dibagi ikut "
             f"dibalik, padahal yang dibalik hanya pembagi {n}."),
        _mal("hasil_terbalik", 1 / hasil,
             f"Menjawab {_teks_pecahan(1 / hasil)}: kemungkinan pembilang dan penyebut hasilnya "
             "tertukar."),
    ]


def _sederhanakan_teks(pembilang: int, penyebut: int, kunci: str) -> str:
    g = gcd(pembilang, penyebut)
    if g == 1:
        return ""
    return (f" Sederhanakan {pembilang}/{penyebut} dengan membagi pembilang dan penyebut "
            f"dengan {g}, hasilnya {kunci}.")


def _cara_kali(a: int, b: int, n: int, kunci: str) -> str:
    return (f"Kalikan pembilang dengan {n}, penyebutnya tetap: {a} × {n} = {a * n}, "
            f"jadi {a * n}/{b}." + _sederhanakan_teks(a * n, b, kunci))


def _cara_bagi(a: int, b: int, n: int, kunci: str) -> str:
    return (f"Membagi dengan {n} sama dengan mengalikan dengan 1/{n}. "
            f"{a}/{b} ÷ {n} = {a}/{b} × 1/{n} = {a}/{b * n}."
            + _sederhanakan_teks(a, b * n, kunci))


def _bangun_kali_asli(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    kunci = _teks_pecahan(Fraction(a * n, b))
    teks = f"Hitung: {a}/{b} × {n} = ... {AKHIRAN}"
    cara = f"{_cara_kali(a, b, n, kunci)} Jadi {a}/{b} × {n} = {kunci}."
    return teks, kunci, _kandidat_kali(a, b, n), cara


def _bangun_asli_kali(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    kunci = _teks_pecahan(Fraction(a * n, b))
    teks = f"Hitung: {n} × {a}/{b} = ... {AKHIRAN}"
    cara = (f"Bilangan asli boleh ditukar tempatnya: {n} × {a}/{b} = {a}/{b} × {n}. "
            f"{_cara_kali(a, b, n, kunci)} Jadi {n} × {a}/{b} = {kunci}.")
    return teks, kunci, _kandidat_kali(a, b, n), cara


def _bangun_bagi_asli(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    kunci = _teks_pecahan(Fraction(a, b * n))
    teks = f"Hitung: {a}/{b} ÷ {n} = ... {AKHIRAN}"
    cara = f"{_cara_bagi(a, b, n, kunci)} Jadi {a}/{b} ÷ {n} = {kunci}."
    return teks, kunci, _kandidat_bagi(a, b, n), cara


def _bangun_cerita(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    operasi, kalimat = CERITA[p["cerita"]]
    teks = f"{kalimat.format(f=f'{a}/{b}', n=n)} {AKHIRAN}"
    if operasi == "kali":
        kunci = _teks_pecahan(Fraction(a * n, b))
        cara = (f"Banyaknya sama dan diulang {n} kali, jadi dikalikan: {a}/{b} × {n}. "
                f"{_cara_kali(a, b, n, kunci)} Jadi jawabannya {kunci}.")
        return teks, kunci, _kandidat_kali(a, b, n), cara
    kunci = _teks_pecahan(Fraction(a, b * n))
    cara = (f"Dibagi sama banyak menjadi {n} bagian, jadi dibagi: {a}/{b} ÷ {n}. "
            f"{_cara_bagi(a, b, n, kunci)} Jadi jawabannya {kunci}.")
    return teks, kunci, _kandidat_bagi(a, b, n), cara


# ── pecahan <-> desimal ──────────────────────────────────────────────────

def _bangun_ke_desimal(p: dict) -> tuple:
    a, b = p["a"], p["b"]
    x = Fraction(a, b)
    kunci = _teks_desimal(x)
    teks = (f"Ubah pecahan {a}/{b} menjadi bilangan desimal. "
            "Jawabannya ... (tulis dengan tanda koma)")
    kandidat = [
        _mal("koma_geser_kanan", x * 10,
             f"Menjawab {_teks_desimal(x * 10)}: kemungkinan titik desimalnya bergeser satu tempat "
             "ke kanan.", _teks_desimal),
        _mal("koma_geser_kiri", x / 10,
             f"Menjawab {_teks_desimal(x / 10)}: kemungkinan titik desimalnya bergeser satu tempat "
             "ke kiri.", _teks_desimal),
        _mal("pisah_koma", f"{a},{b}",
             f"Menjawab {a},{b}: kemungkinan pembilang dan penyebut hanya dipisah dengan koma."),
        _mal("susun_belakang_koma", f"0,{a}{b}",
             f"Menjawab 0,{a}{b}: kemungkinan pembilang dan penyebut ditulis berurutan "
             "di belakang koma."),
    ]
    k = next(i for i in range(1, 4) if (10 ** i) % b == 0)
    pengali = 10 ** k // b
    samakan = (f"Samakan penyebutnya menjadi {10 ** k}: {a}/{b} = {a * pengali}/{10 ** k}. "
               if pengali > 1 else f"Penyebutnya sudah {b}. ")
    cara = (f"{samakan}Pecahan per {10 ** k} ditulis dengan {k} angka di belakang koma, "
            f"jadi {a}/{b} = {kunci}.")
    return teks, kunci, kandidat, cara


def _bangun_desimal_ke_pecahan(p: dict) -> tuple:
    perseratus = p["perseratus"]
    x = Fraction(perseratus, 100)
    kunci = _teks_pecahan(x)
    tulis = _teks_desimal(x)
    digit = tulis.split(",")[1]
    k = len(digit)
    angka = int(digit)
    teks = (f"Ubah bilangan desimal {tulis} menjadi pecahan paling sederhana. "
            "Jawabannya ... (tulis dengan garis miring, contoh 2/3)")
    kandidat = [
        _mal("pecahan_tertukar", 1 / x,
             f"Menjawab {_teks_pecahan(1 / x)}: kemungkinan pembilang dan penyebut tertukar."),
        _mal("penyebut_terlalu_kecil", Fraction(angka, 10 ** (k - 1)),
             f"Menjawab {_teks_pecahan(Fraction(angka, 10 ** (k - 1)))}: kemungkinan penyebutnya "
             "tidak disesuaikan dengan banyak angka di belakang koma."),
        _mal("penyebut_terlalu_besar", Fraction(angka, 10 ** (k + 1)),
             f"Menjawab {_teks_pecahan(Fraction(angka, 10 ** (k + 1)))}: kemungkinan penyebutnya "
             "kelebihan satu nol."),
        _mal("satu_per_angka", Fraction(1, angka),
             f"Menjawab {_teks_pecahan(Fraction(1, angka))}: kemungkinan angka di belakang koma "
             "langsung dijadikan penyebut dengan pembilang 1."),
    ]
    g = gcd(angka, 10 ** k)
    cara = (f"Ada {k} angka di belakang koma, jadi penyebutnya {10 ** k}: "
            f"{tulis} = {angka}/{10 ** k}. "
            f"Sederhanakan dengan membagi pembilang dan penyebut dengan {g}: {kunci}.")
    return teks, kunci, kandidat, cara


_BANGUN = {
    "kali_asli": _bangun_kali_asli,
    "bagi_asli": _bangun_bagi_asli,
    "asli_kali": _bangun_asli_kali,
    "ke_desimal": _bangun_ke_desimal,
    "desimal_ke_pecahan": _bangun_desimal_ke_pecahan,
    "cerita": _bangun_cerita,
}


# ── domain eksplisit ─────────────────────────────────────────────────────

def _operan() -> list:
    return [(a, b) for b in PENYEBUT_OPERAN for a in range(1, b) if _pecahan_sah(a, b)]


def _enumerasi_kali(varian: str) -> list:
    return [{"varian": varian, "a": a, "b": b, "n": n}
            for a, b in _operan() for n in BILANGAN_ASLI if _hasil_kali_sah(a, b, n)]


def _enumerasi_bagi() -> list:
    return [{"varian": "bagi_asli", "a": a, "b": b, "n": n}
            for a, b in _operan() for n in BILANGAN_ASLI if _hasil_bagi_sah(a, b, n)]


def _enumerasi_ke_desimal() -> list:
    return [{"varian": "ke_desimal", "a": a, "b": b}
            for b in PENYEBUT_KE_DESIMAL for a in range(1, b) if gcd(a, b) == 1]


def _enumerasi_desimal_ke_pecahan() -> list:
    return [{"varian": "desimal_ke_pecahan", "perseratus": m} for m in range(1, 100)
            if Fraction(m, 100).denominator in PENYEBUT_DARI_DESIMAL]


def _enumerasi_cerita() -> list:
    hasil = []
    for i, (operasi, _) in enumerate(CERITA):
        sah = _hasil_kali_sah if operasi == "kali" else _hasil_bagi_sah
        hasil.extend({"varian": "cerita", "cerita": i, "a": a, "b": b, "n": n}
                     for a, b in _operan() for n in BILANGAN_ASLI if sah(a, b, n))
    return hasil


_ENUMERATOR = {
    "kali_asli": lambda: _enumerasi_kali("kali_asli"),
    "bagi_asli": _enumerasi_bagi,
    "asli_kali": lambda: _enumerasi_kali("asli_kali"),
    "ke_desimal": _enumerasi_ke_desimal,
    "desimal_ke_pecahan": _enumerasi_desimal_ke_pecahan,
    "cerita": _enumerasi_cerita,
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
        raise ValueError("level pecahan dan bilangan asli harus P6")


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


def pecahan_bilangan_asli_desimal(varian: str, a: int | None = None, b: int | None = None,
                                  n: int | None = None, perseratus: int | None = None,
                                  cerita: int | None = None) -> Soal:
    """Pecahan dengan bilangan asli dan pecahan-desimal; kunci dihitung dari parameter sah."""
    diberi = {"varian": varian, "a": a, "b": b, "n": n, "perseratus": perseratus, "cerita": cerita}
    p = {nama: nilai for nama, nilai in diberi.items() if nilai is not None}
    if not _sah(p):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, kandidat, pembahasan = _BANGUN[varian](p)
    return Soal(template_id=TEMPLATE_ID, parameter=p, teks=teks, kunci=kunci,
                malrule=_rapikan(kunci, kandidat), pembahasan=pembahasan, bagian="A")
