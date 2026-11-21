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

Perluasan v2 (varian BARU, ditambahkan di belakang; enam varian lama, parameter, dan domainnya
tidak berubah sedikit pun, urutan `domain_parameter` lama tetap di depan): bab K6 B1 "Pecahan dan
desimal" juga menuntut hasil tak wajar dan pembulatan, jadi ada enam varian tambahan (level P6):
  - `kali_asli_tak_wajar`: pecahan x bilangan asli dengan hasil LEBIH dari 1 (urutan "3/4 × 5"
    atau "5 × 3/4"); kunci pecahan biasa paling sederhana "15/4", atau bilangan bulat "6";
  - `bagi_asli_tak_wajar`: pecahan tak wajar ("5/3 ÷ 2") atau pecahan campuran ("1 2/3 ÷ 2")
    dibagi bilangan asli; hasilnya selalu pecahan kurang dari 1 ("5/6"), tidak pernah campuran;
  - `campur_ke_biasa`: "2 1/4 ditulis sebagai pecahan biasa" = "9/4";
  - `ke_desimal_berulang_dibulatkan`: pecahan berpenyebut 3, 6, 7, 9, 11, 12 menjadi desimal
    yang dibulatkan sampai SATU angka di belakang koma (kalimat soal menyatakannya tegas);
    tidak ada kasus yang tepat di tengah (x,x5), jadi aturan pembulatan tidak berperan;
  - `desimal_ke_persen_pecahan`: "0,25 = ... persen" (kunci 25) atau "75% = ... pecahan
    paling sederhana" (kunci "3/4");
  - `cerita_kali_bagi_pecahan`: satu langkah kali (hasil lebih dari 1) atau bagi, cerita baru
    (`CERITA_TAK_WAJAR`, juga APPEND-ONLY).
Konvensi kunci pecahan tak wajar: "a/b" paling sederhana (bukan campuran), dan kalimat soal
menyatakan "tulis hasilnya sebagai pecahan biasa" dengan contoh bentuknya, supaya kunci tunggal;
bila hasil kali bulat, kuncinya bilangan bulat ("6"). Contoh bentuk dipilih dari kunci agar tidak
pernah sama dengan jawabannya. Pecahan campuran TIDAK dipakai sebagai kunci: `nilai_semantis`
(pilihan ganda) tidak membaca "2 1/4", jadi varian "pecahan biasa ke campuran" sengaja belum ada.
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
from math import gcd
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "pecahan_bilangan_asli_desimal"
LEVEL = ("P6",)
VARIAN_LAMA = ("kali_asli", "bagi_asli", "asli_kali", "ke_desimal", "desimal_ke_pecahan", "cerita")
VARIAN_BARU = ("kali_asli_tak_wajar", "bagi_asli_tak_wajar", "campur_ke_biasa",
               "ke_desimal_berulang_dibulatkan", "desimal_ke_persen_pecahan",
               "cerita_kali_bagi_pecahan")
VARIAN = VARIAN_LAMA + VARIAN_BARU
PESAN_LUAR_DOMAIN = "parameter pecahan dan bilangan asli di luar domain"

PENYEBUT_OPERAN = range(2, 13)
BILANGAN_ASLI = range(2, 13)
PENYEBUT_BAGI_MAKS = 24
PENYEBUT_KE_DESIMAL = (2, 4, 5, 8, 10, 20, 25)
PENYEBUT_DARI_DESIMAL = (2, 4, 5, 10, 20, 25)
AKHIRAN = "(tulis hasilnya dalam bentuk paling sederhana)"
BULAT_CAMPUR = range(1, 6)
PENYEBUT_BERULANG = (3, 6, 7, 9, 11, 12)
ARAH_PERSEN = ("ke_persen", "ke_pecahan")
BENTUK_BAGI = ("biasa", "campur")
CONTOH_PECAHAN_BIASA = "7/3"
CONTOH_PECAHAN_BIASA_LAIN = "5/2"
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
# Cerita varian `cerita_kali_bagi_pecahan`. Append-only menurut indeks.
CERITA_TAK_WAJAR = (
    ("kali", "Satu kantong beras beratnya {f} kg. Berapa kilogram berat {n} kantong beras yang sama?"),
    ("kali", "Setiap hari Dita membaca buku selama {f} jam. Berapa jam Dita membaca dalam {n} hari?"),
    ("kali", "Satu botol sirup berisi {f} liter. Berapa liter sirup dalam {n} botol yang sama?"),
    ("kali", "Eko membuat sebuah gelang dari tali sepanjang {f} m. "
             "Berapa meter tali yang ia perlukan untuk {n} gelang yang sama?"),
    ("bagi", "Sebuah botol berisi {f} liter air. Air itu dituang sama banyak ke dalam {n} gelas kecil. "
             "Berapa liter air di tiap gelas?"),
    ("bagi", "Rina mempunyai pita sepanjang {f} m. Pita itu dipotong sama panjang menjadi {n} potong. "
             "Berapa meter panjang tiap potongan?"),
    ("bagi", "Budi membagi {f} kg tepung sama banyak ke dalam {n} plastik. "
             "Berapa kilogram tepung di tiap plastik?"),
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


# ── perluasan v2: hasil tak wajar, campuran, pembulatan, persen ──────────

def _contoh_bentuk(kunci: str) -> str:
    """Contoh penulisan pecahan biasa di kalimat soal; tidak pernah sama dengan jawabannya."""
    return CONTOH_PECAHAN_BIASA_LAIN if kunci == CONTOH_PECAHAN_BIASA else CONTOH_PECAHAN_BIASA


def _akhiran_tak_wajar(kunci: str) -> str:
    return (f"(tulis hasilnya sebagai pecahan biasa paling sederhana, contoh {_contoh_bentuk(kunci)}; "
            "bila hasilnya bilangan bulat, tulis bilangannya saja)")


def _hasil_kali_tak_wajar_sah(a: int, b: int, n: int) -> bool:
    return Fraction(a * n, b) > 1


def _hasil_bagi_tak_wajar_sah(a: int, b: int, n: int) -> bool:
    """Operan lebih dari 1 dan kurang dari 3; hasil bagi pecahan kurang dari 1 berpenyebut <= 24."""
    hasil = Fraction(a, b * n)
    return hasil < 1 and hasil.denominator <= PENYEBUT_BAGI_MAKS


def _kandidat_kali_tak_wajar(a: int, b: int, n: int) -> list:
    return _kandidat_kali(a, b, n) + [
        _mal("pecahan_dibalik_lalu_dikali", Fraction(b * n, a),
             f"Menjawab {_teks_pecahan(Fraction(b * n, a))}: kemungkinan pecahan {a}/{b} dibalik "
             f"dulu menjadi {b}/{a}, baru dikalikan {n}."),
    ]


def _keterangan_tak_wajar(kunci: str) -> str:
    if "/" not in kunci:
        return ""
    return " Pembilang lebih besar dari penyebut tidak apa-apa: itu pecahan biasa yang nilainya lebih dari 1."


def _bangun_kali_tak_wajar(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    kunci = _teks_pecahan(Fraction(a * n, b))
    ekspresi = f"{a}/{b} × {n}" if p["urut"] == 0 else f"{n} × {a}/{b}"
    teks = f"Hitung: {ekspresi} = ... {_akhiran_tak_wajar(kunci)}"
    tukar = (f"Bilangan asli boleh ditukar tempatnya: {n} × {a}/{b} = {a}/{b} × {n}. "
             if p["urut"] == 1 else "")
    cara = (f"{tukar}{_cara_kali(a, b, n, kunci)}{_keterangan_tak_wajar(kunci)} "
            f"Jadi {ekspresi} = {kunci}.")
    return teks, kunci, _kandidat_kali_tak_wajar(a, b, n), cara


def _teks_operan_bagi(p: dict) -> str:
    a, b = p["a"], p["b"]
    if p["bentuk"] == "biasa":
        return f"{a}/{b}"
    return f"{a // b} {a % b}/{b}"


def _kandidat_bagi_tak_wajar(p: dict) -> list:
    a, b, n = p["a"], p["b"], p["n"]
    kandidat = _kandidat_bagi(a, b, n)
    if p["bentuk"] == "campur":
        sisa = a % b
        kandidat.append(
            _mal("bulat_terlupa", Fraction(sisa, b * n),
                 f"Menjawab {_teks_pecahan(Fraction(sisa, b * n))}: kemungkinan hanya bagian pecahan "
                 f"{sisa}/{b} yang dibagi {n}, sedangkan bilangan bulatnya terlupa."))
    return kandidat


def _bangun_bagi_tak_wajar(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    kunci = _teks_pecahan(Fraction(a, b * n))
    operan = _teks_operan_bagi(p)
    teks = f"Hitung: {operan} ÷ {n} = ... {AKHIRAN}"
    ubah = (f"Ubah dulu {operan} menjadi pecahan biasa: {a // b} × {b} + {a % b} = {a}, jadi {a}/{b}. "
            if p["bentuk"] == "campur" else "")
    cara = f"{ubah}{_cara_bagi(a, b, n, kunci)} Jadi {operan} ÷ {n} = {kunci}."
    return teks, kunci, _kandidat_bagi_tak_wajar(p), cara


def _bangun_campur_ke_biasa(p: dict) -> tuple:
    w, a, b = p["w"], p["a"], p["b"]
    x = Fraction(w * b + a, b)
    kunci = _teks_pecahan(x)
    teks = (f"Pecahan campuran {w} {a}/{b} ditulis sebagai pecahan biasa menjadi ... "
            f"(tulis dengan garis miring, contoh {_contoh_bentuk(kunci)})")
    kandidat = [
        _mal("bulat_ditambah_pembilang", f"{w + a}/{b}",
             f"Menjawab {w + a}/{b}: kemungkinan bilangan bulat {w} dijumlahkan dengan "
             f"pembilang {a}, bukan dikalikan dengan penyebut {b}."),
        _mal("bulat_dikali_pembilang", f"{w * a}/{b}",
             f"Menjawab {w * a}/{b}: kemungkinan bilangan bulat {w} dikalikan dengan "
             f"pembilang {a}."),
        _mal("angka_berdampingan", f"{w}{a}/{b}",
             f"Menjawab {w}{a}/{b}: kemungkinan bilangan bulat dan pembilang ditulis berdampingan "
             "sebagai pembilang."),
        _mal("pembilang_tidak_ditambah", f"{w * b}/{b}",
             f"Menjawab {w * b}/{b}: kemungkinan bilangan bulat dikalikan penyebut, tetapi "
             f"pembilang {a} lupa ditambahkan."),
        _mal("pembilang_penyebut_tertukar", Fraction(b, w * b + a),
             f"Menjawab {_teks_pecahan(Fraction(b, w * b + a))}: kemungkinan pembilang dan penyebut "
             "hasilnya tertukar."),
    ]
    cara = (f"Kalikan bilangan bulat dengan penyebut, lalu tambahkan pembilangnya: "
            f"{w} × {b} + {a} = {w * b + a}. Penyebutnya tetap {b}. "
            f"Jadi {w} {a}/{b} = {kunci}.")
    return teks, kunci, kandidat, cara


def _bulatkan_satu_angka(x: Fraction) -> Fraction:
    """Bulatkan ke satu angka di belakang koma (setengah ke atas; kasus tengah tidak ada di domain)."""
    return Fraction((x * 20 + 1) // 2, 10)


def _bangun_berulang_dibulatkan(p: dict) -> tuple:
    a, b = p["a"], p["b"]
    x = Fraction(a, b)
    bulat = _bulatkan_satu_angka(x)
    kunci = _teks_desimal(bulat)
    teks = (f"Ubah pecahan {a}/{b} menjadi bilangan desimal, dibulatkan sampai satu angka "
            "di belakang koma. Jawabannya ... (tulis dengan tanda koma)")
    potong = Fraction((x * 10).numerator // (x * 10).denominator, 10)
    dua_angka = Fraction((x * 200 + 1) // 2, 100)
    kandidat = [
        _mal("dibulatkan_ke_atas", Fraction((-(-x.numerator * 10 // x.denominator)), 10),
             f"Menjawab {_teks_desimal(Fraction(-(-x.numerator * 10 // x.denominator), 10))}: "
             "kemungkinan angka terakhir selalu dinaikkan satu, padahal angka berikutnya "
             "kurang dari 5.", _teks_desimal),
        _mal("dipotong_tanpa_dibulatkan", potong,
             f"Menjawab {_teks_desimal(potong)}: kemungkinan angka setelahnya dibuang saja, "
             "padahal angka berikutnya 5 atau lebih sehingga harus dinaikkan.", _teks_desimal),
        _mal("dua_angka_belakang_koma", dua_angka,
             f"Menjawab {_teks_desimal(dua_angka)}: kemungkinan dibulatkan sampai dua angka di "
             "belakang koma, bukan satu.", _teks_desimal),
        _mal("koma_geser_kiri", bulat / 10,
             f"Menjawab {_teks_desimal(bulat / 10)}: kemungkinan titik desimalnya bergeser satu "
             "tempat ke kiri.", _teks_desimal),
        _mal("koma_geser_kanan", bulat * 10,
             f"Menjawab {_teks_desimal(bulat * 10)}: kemungkinan titik desimalnya bergeser satu "
             "tempat ke kanan.", _teks_desimal),
        _mal("pisah_koma", f"{a},{b}",
             f"Menjawab {a},{b}: kemungkinan pembilang dan penyebut hanya dipisah dengan koma."),
    ]
    tiga = _teks_desimal(Fraction((1000 * a) // b, 1000))
    angka_dua = (100 * a // b) % 10
    aturan = ("Karena 5 atau lebih, angka pertama di belakang koma naik satu."
              if angka_dua >= 5 else "Karena kurang dari 5, angka pertama di belakang koma tetap.")
    cara = (f"Bagi {a} dengan {b}: {a} ÷ {b} = {tiga}... Angka kedua di belakang koma adalah "
            f"{angka_dua}. {aturan} Jadi {a}/{b} dibulatkan sampai satu angka di belakang koma "
            f"menjadi {kunci}.")
    return teks, kunci, kandidat, cara


def _bangun_persen_ke_persen(perseratus: int) -> tuple:
    x = Fraction(perseratus, 100)
    kunci = str(perseratus)
    tulis = _teks_desimal(x)
    teks = f"Nyatakan {tulis} sebagai persen. Jawabannya ... persen (tulis angkanya saja)"
    kandidat = [
        _mal("koma_geser_satu_tempat", Fraction(perseratus, 10),
             f"Menjawab {_teks_desimal(Fraction(perseratus, 10))}: kemungkinan titik desimalnya "
             "hanya bergeser satu tempat.", _teks_desimal),
        _mal("tidak_dikali_seratus", x,
             f"Menjawab {tulis}: kemungkinan bilangan desimalnya hanya ditulis ulang tanpa "
             "dikalikan 100.", _teks_desimal),
        _mal("dikali_seribu", perseratus * 10,
             f"Menjawab {perseratus * 10}: kemungkinan desimalnya dikalikan 1000, bukan 100."),
    ]
    cara = (f"Persen berarti per seratus. {tulis} = {perseratus}/100 = {perseratus} persen. "
            "Cara cepatnya: kalikan dengan 100, yaitu geser koma dua tempat ke kanan.")
    return teks, kunci, kandidat, cara


def _bangun_persen_ke_pecahan(perseratus: int) -> tuple:
    x = Fraction(perseratus, 100)
    kunci = _teks_pecahan(x)
    teks = (f"Nyatakan {perseratus}% sebagai pecahan paling sederhana. "
            "Jawabannya ... (tulis dengan garis miring, contoh 2/3)")
    kandidat = [
        _mal("pecahan_tertukar", 1 / x,
             f"Menjawab {_teks_pecahan(1 / x)}: kemungkinan pembilang dan penyebut tertukar."),
        _mal("penyebut_sepuluh", Fraction(perseratus, 10),
             f"Menjawab {_teks_pecahan(Fraction(perseratus, 10))}: kemungkinan penyebutnya "
             "ditulis 10, bukan 100."),
        _mal("penyebut_seribu", Fraction(perseratus, 1000),
             f"Menjawab {_teks_pecahan(Fraction(perseratus, 1000))}: kemungkinan penyebutnya "
             "ditulis 1000, bukan 100."),
        _mal("satu_per_angka", Fraction(1, perseratus),
             f"Menjawab {_teks_pecahan(Fraction(1, perseratus))}: kemungkinan angka persennya "
             "langsung dijadikan penyebut dengan pembilang 1."),
    ]
    g = gcd(perseratus, 100)
    cara = (f"Persen berarti per seratus. {perseratus}% = {perseratus}/100. "
            f"Sederhanakan dengan membagi pembilang dan penyebut dengan {g}: {kunci}.")
    return teks, kunci, kandidat, cara


def _bangun_persen_pecahan(p: dict) -> tuple:
    if p["arah"] == "ke_persen":
        return _bangun_persen_ke_persen(p["perseratus"])
    return _bangun_persen_ke_pecahan(p["perseratus"])


def _bangun_cerita_tak_wajar(p: dict) -> tuple:
    a, b, n = p["a"], p["b"], p["n"]
    operasi, kalimat = CERITA_TAK_WAJAR[p["cerita"]]
    cerita = kalimat.format(f=f"{a}/{b}", n=n)
    if operasi == "kali":
        kunci = _teks_pecahan(Fraction(a * n, b))
        cara = (f"Banyaknya sama dan diulang {n} kali, jadi dikalikan: {a}/{b} × {n}. "
                f"{_cara_kali(a, b, n, kunci)}{_keterangan_tak_wajar(kunci)} "
                f"Jadi jawabannya {kunci}.")
        return f"{cerita} {_akhiran_tak_wajar(kunci)}", kunci, _kandidat_kali_tak_wajar(a, b, n), cara
    kunci = _teks_pecahan(Fraction(a, b * n))
    cara = (f"Dibagi sama banyak menjadi {n} bagian, jadi dibagi: {a}/{b} ÷ {n}. "
            f"{_cara_bagi(a, b, n, kunci)} Jadi jawabannya {kunci}.")
    return f"{cerita} {AKHIRAN}", kunci, _kandidat_bagi(a, b, n), cara


_BANGUN = {
    "kali_asli": _bangun_kali_asli,
    "bagi_asli": _bangun_bagi_asli,
    "asli_kali": _bangun_asli_kali,
    "ke_desimal": _bangun_ke_desimal,
    "desimal_ke_pecahan": _bangun_desimal_ke_pecahan,
    "cerita": _bangun_cerita,
    "kali_asli_tak_wajar": _bangun_kali_tak_wajar,
    "bagi_asli_tak_wajar": _bangun_bagi_tak_wajar,
    "campur_ke_biasa": _bangun_campur_ke_biasa,
    "ke_desimal_berulang_dibulatkan": _bangun_berulang_dibulatkan,
    "desimal_ke_persen_pecahan": _bangun_persen_pecahan,
    "cerita_kali_bagi_pecahan": _bangun_cerita_tak_wajar,
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


def _enumerasi_kali_tak_wajar() -> list:
    return [{"varian": "kali_asli_tak_wajar", "a": a, "b": b, "n": n, "urut": urut}
            for a, b in _operan() for n in BILANGAN_ASLI if _hasil_kali_tak_wajar_sah(a, b, n)
            for urut in (0, 1)]


def _enumerasi_bagi_tak_wajar() -> list:
    hasil = []
    for b in PENYEBUT_OPERAN:
        for a in range(b + 1, 3 * b):
            if gcd(a, b) != 1:
                continue
            hasil.extend({"varian": "bagi_asli_tak_wajar", "a": a, "b": b, "n": n, "bentuk": bentuk}
                         for n in BILANGAN_ASLI if _hasil_bagi_tak_wajar_sah(a, b, n)
                         for bentuk in BENTUK_BAGI)
    return hasil


def _enumerasi_campur_ke_biasa() -> list:
    return [{"varian": "campur_ke_biasa", "w": w, "a": a, "b": b}
            for w in BULAT_CAMPUR for a, b in _operan()]


def _enumerasi_berulang_dibulatkan() -> list:
    return [{"varian": "ke_desimal_berulang_dibulatkan", "a": a, "b": b}
            for b in PENYEBUT_BERULANG for a in range(1, b) if gcd(a, b) == 1]


def _enumerasi_persen_pecahan() -> list:
    ke_persen = [{"varian": "desimal_ke_persen_pecahan", "arah": "ke_persen", "perseratus": m}
                 for m in range(1, 100)]
    ke_pecahan = [{"varian": "desimal_ke_persen_pecahan", "arah": "ke_pecahan", "perseratus": m}
                  for m in range(1, 100)
                  if Fraction(m, 100).denominator in PENYEBUT_DARI_DESIMAL]
    return ke_persen + ke_pecahan


def _enumerasi_cerita_tak_wajar() -> list:
    hasil = []
    for i, (operasi, _) in enumerate(CERITA_TAK_WAJAR):
        sah = _hasil_kali_tak_wajar_sah if operasi == "kali" else _hasil_bagi_sah
        hasil.extend({"varian": "cerita_kali_bagi_pecahan", "cerita": i, "a": a, "b": b, "n": n}
                     for a, b in _operan() for n in BILANGAN_ASLI if sah(a, b, n))
    return hasil


_ENUMERATOR = {
    "kali_asli": lambda: _enumerasi_kali("kali_asli"),
    "bagi_asli": _enumerasi_bagi,
    "asli_kali": lambda: _enumerasi_kali("asli_kali"),
    "ke_desimal": _enumerasi_ke_desimal,
    "desimal_ke_pecahan": _enumerasi_desimal_ke_pecahan,
    "cerita": _enumerasi_cerita,
    "kali_asli_tak_wajar": _enumerasi_kali_tak_wajar,
    "bagi_asli_tak_wajar": _enumerasi_bagi_tak_wajar,
    "campur_ke_biasa": _enumerasi_campur_ke_biasa,
    "ke_desimal_berulang_dibulatkan": _enumerasi_berulang_dibulatkan,
    "desimal_ke_persen_pecahan": _enumerasi_persen_pecahan,
    "cerita_kali_bagi_pecahan": _enumerasi_cerita_tak_wajar,
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
                                  cerita: int | None = None, w: int | None = None,
                                  urut: int | None = None, bentuk: str | None = None,
                                  arah: str | None = None) -> Soal:
    """Pecahan dengan bilangan asli dan pecahan-desimal; kunci dihitung dari parameter sah."""
    diberi = {"varian": varian, "a": a, "b": b, "n": n, "perseratus": perseratus, "cerita": cerita,
              "w": w, "urut": urut, "bentuk": bentuk, "arah": arah}
    p = {nama: nilai for nama, nilai in diberi.items() if nilai is not None}
    if not _sah(p):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, kandidat, pembahasan = _BANGUN[varian](p)
    return Soal(template_id=TEMPLATE_ID, parameter=p, teks=teks, kunci=kunci,
                malrule=_rapikan(kunci, kandidat), pembahasan=pembahasan, bagian="A")
