"""Matematika Awal, jenis `peluang_dasar` (P6): kemungkinan dan peluang sederhana, teks saja.

Empat bentuk soal (`varian`):
  - `lebih_mungkin`: kantong berisi bola merah/biru/hijau dengan jumlah berbeda,
    "Bola warna apa yang paling mungkin terambil?" atau yang paling kecil
    kemungkinannya (jawaban: nama warna; ketiga jumlah SELALU berbeda, jadi
    jumlah terbanyak dan tersedikit masing-masing tunggal);
  - `kepastian`: kantong berisi bola satu warna saja; apakah terambilnya bola
    suatu warna itu pasti, mungkin, atau mustahil (jawaban sah hanya `pasti`
    atau `mustahil`; `mungkin` tidak pernah benar, karena kantongnya selalu
    satu warna, tetapi disebut di soal supaya anak membedakan ketiga istilah);
  - `banyak_hasil`: banyak kemungkinan angka pada satu dadu bersisi 6 atau
    satu kartu bernomor 1 sampai 10 yang memenuhi satu syarat (jawaban: angka);
  - `peluang_pecahan`: kantong dengan bola merah dan biru, peluang terambil
    satu warna sebagai pecahan "pembilang/penyebut" (jawaban: teks "3/5").

Konvensi kunci pecahan sama dengan `pecahan_kali_bagi`: teks `n/d` dari
`Fraction`. Pembanding jawaban bawaan (`diagnosis.setara`) membandingkan teks
ternormalisasi untuk template yang belum terdaftar khusus, jadi "6/10" TIDAK
dianggap sama dengan "3/5". Karena itu pasangan jumlah bola dipilih agar
pecahannya SUDAH paling sederhana (`gcd(merah, biru) == 1`, kedua jumlah >= 2,
tidak sama, yang otomatis dijamin gcd 1 dan jumlah >= 2): bentuk lain hanya muncul bila anak sendiri mengalikan. Jumlah 1
dibuang agar jawaban "banyak bola" tidak sama nilainya dengan "perbandingan".

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis
pasti dari satu jawaban. Jalur K selalu ada (mis. menjawab banyak semua
kemungkinan, warna yang salah, pecahan terbalik); H hanya salah hitung lebih
atau kurang satu pada `banyak_hasil`.

Domain kecil dan eksplisit (`domain_parameter`). Validasi parameter = menjadi
anggota domain itu, jadi kombinasi tak sah (pecahan tak sederhana, jumlah sama,
syarat dengan satu atau nol hasil) ditolak. Sampler memilih varian dulu (seragam)
lalu satu parameter dari varian itu memakai `rng` saja (tanpa `hash()`), supaya
varian berdomain kecil tidak tenggelam. Daftar `WARNA`, `POLA_JUMLAH`, dan
syarat dadu/kartu bersifat sumber domain: kunci dihitung dari parameter, dan
dicek solver terpisah yang hanya membaca teks.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import permutations
from math import gcd
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "peluang_dasar"
LEVEL = ("P6",)
VARIAN = ("lebih_mungkin", "kepastian", "banyak_hasil", "peluang_pecahan")
PESAN_LUAR_DOMAIN = "parameter peluang dasar di luar domain"

WARNA = ("merah", "biru", "hijau", "kuning")
ARAH = ("terbanyak", "tersedikit")
# Jumlah bola tiga warna (tiga angka berbeda), dipasang ke merah/biru/hijau dalam semua urutan.
POLA_JUMLAH = ((2, 4, 7), (3, 5, 8), (2, 5, 9))
JUMLAH_KEPASTIAN = (4, 6, 9)
TOTAL_PECAHAN = range(5, 11)
# objek -> banyak hasil seluruhnya (dadu 1..6, kartu 1..10)
BANYAK_OBJEK = {"dadu": 6, "kartu": 10}
# Syarat per objek; (syarat, k). Tiap syarat menyisakan 2 sampai total-1 hasil.
SYARAT_OBJEK = {
    "dadu": (("genap", None), ("ganjil", None), ("kelipatan", 3),
             ("lebih_dari", 2), ("lebih_dari", 3), ("lebih_dari", 4),
             ("kurang_dari", 3), ("kurang_dari", 4), ("kurang_dari", 5)),
    "kartu": (("genap", None), ("ganjil", None), ("kelipatan", 3), ("kelipatan", 5),
              ("lebih_dari", 5), ("lebih_dari", 6), ("lebih_dari", 7), ("lebih_dari", 8),
              ("kurang_dari", 3), ("kurang_dari", 4), ("kurang_dari", 5), ("kurang_dari", 6)),
}
KATA_SYARAT = {"genap": "genap", "ganjil": "ganjil", "kelipatan": "kelipatan",
               "lebih_dari": "lebih dari", "kurang_dari": "kurang dari"}


# ── hitungan murni ───────────────────────────────────────────────────────

def _memenuhi(syarat: str, k, x: int) -> bool:
    if syarat == "genap":
        return x % 2 == 0
    if syarat == "ganjil":
        return x % 2 == 1
    if syarat == "kelipatan":
        return x % k == 0
    if syarat == "lebih_dari":
        return x > k
    return x < k


def _himpunan(objek: str, syarat: str, k) -> tuple:
    return tuple(x for x in range(1, BANYAK_OBJEK[objek] + 1) if _memenuhi(syarat, k, x))


def _frasa_syarat(syarat: str, k) -> str:
    return KATA_SYARAT[syarat] if k is None else f"{KATA_SYARAT[syarat]} {k}"


# ── varian lebih_mungkin ─────────────────────────────────────────────────

def _bangun_lebih_mungkin(p: dict) -> tuple:
    jumlah = {"merah": p["merah"], "biru": p["biru"], "hijau": p["hijau"]}
    terbanyak = p["arah"] == "terbanyak"
    pilih = max if terbanyak else min
    kunci = pilih(jumlah, key=jumlah.get)
    tanya = ("Bola warna apa yang paling mungkin terambil?" if terbanyak
             else "Bola warna apa yang paling kecil kemungkinan terambilnya?")
    teks = (f"Dalam kantong ada {p['merah']} bola merah, {p['biru']} bola biru, "
            f"dan {p['hijau']} bola hijau. Satu bola diambil tanpa melihat. {tanya}")
    urut = sorted(jumlah, key=jumlah.get)
    ujung = urut[0] if terbanyak else urut[-1]  # warna di ujung yang salah
    tengah = urut[1]
    alasan_ujung = ("mengira bola yang jumlahnya paling sedikit lebih mudah terambil." if terbanyak
                    else "mengira bola yang jumlahnya paling banyak paling sulit terambil.")
    kandidat = [
        Malrule(f"{TEMPLATE_ID}.warna_ujung_terbalik", ujung, "K",
                f"Menjawab {ujung}: kemungkinan {alasan_ujung}"),
        Malrule(f"{TEMPLATE_ID}.warna_tengah", tengah, "K",
                f"Menjawab {tengah}: kemungkinan hanya membandingkan dua jumlah bola, bukan ketiganya."),
    ]
    if terbanyak:
        cara = (f"Bandingkan jumlahnya: merah {p['merah']}, biru {p['biru']}, hijau {p['hijau']}. "
                f"Yang paling banyak adalah bola {kunci} ({jumlah[kunci]} bola). "
                f"Makin banyak bolanya, makin besar kemungkinan terambil. Jadi bola {kunci} paling mungkin terambil.")
    else:
        cara = (f"Bandingkan jumlahnya: merah {p['merah']}, biru {p['biru']}, hijau {p['hijau']}. "
                f"Yang paling sedikit adalah bola {kunci} ({jumlah[kunci]} bola). "
                f"Makin sedikit bolanya, makin kecil kemungkinan terambil. Jadi bola {kunci} paling kecil kemungkinannya.")
    return teks, kunci, kandidat, cara


# ── varian kepastian ─────────────────────────────────────────────────────

def _bangun_kepastian(p: dict) -> tuple:
    isi, tanya, n = p["isi"], p["tanya"], p["n"]
    kunci = "pasti" if tanya == isi else "mustahil"
    lawan = "mustahil" if kunci == "pasti" else "pasti"
    teks = (f"Kantong berisi {n} bola {isi} saja. Satu bola diambil tanpa melihat. "
            f"Kejadian terambil bola {tanya} itu pasti, mungkin, atau mustahil?")
    kandidat = [
        Malrule(f"{TEMPLATE_ID}.kepastian_terbalik", lawan, "K",
                f"Menjawab {lawan}: kemungkinan tertukar antara kejadian yang pasti terjadi dan yang tidak mungkin terjadi."),
        Malrule(f"{TEMPLATE_ID}.kepastian_mungkin", "mungkin", "K",
                "Menjawab mungkin: kemungkinan ragu karena bola diambil tanpa melihat, "
                "padahal semua bola di kantong sama warnanya."),
    ]
    if kunci == "pasti":
        cara = (f"Semua bola di kantong berwarna {isi}. Bola apa pun yang diambil pasti {isi}. "
                f"Jadi terambil bola {tanya} itu pasti.")
    else:
        cara = (f"Di kantong hanya ada bola {isi}, tidak ada bola {tanya} sama sekali. "
                f"Bola {tanya} tidak mungkin terambil. Kejadian yang tidak mungkin terjadi disebut mustahil.")
    return teks, kunci, kandidat, cara


# ── varian banyak_hasil ──────────────────────────────────────────────────

def _teks_hasil(objek: str, frasa: str) -> str:
    if objek == "dadu":
        return f"Sebuah dadu bersisi 6 dilempar. Ada berapa kemungkinan muncul angka {frasa}?"
    return (f"Satu kartu diambil dari 10 kartu yang bernomor 1 sampai 10. "
            f"Ada berapa kemungkinan kartu itu bernomor {frasa}?")


def _malrule_hasil(objek: str, syarat: str, k, himpunan: tuple) -> list:
    banyak, total = len(himpunan), BANYAK_OBJEK[objek]
    kandidat = [
        Malrule(f"{TEMPLATE_ID}.hitung_semua", str(total), "K",
                f"Menjawab {total}, yaitu banyak semua kemungkinan, tanpa menyaring angka yang memenuhi syarat."),
        Malrule(f"{TEMPLATE_ID}.angka_terbesar", str(max(himpunan)), "K",
                "Menjawab angka terbesar yang memenuhi syarat, bukan banyaknya angka yang memenuhi."),
    ]
    if syarat in ("lebih_dari", "kurang_dari"):
        lawan = k - 1 if syarat == "lebih_dari" else total - k
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.ikut_batas", str(banyak + 1), "K",
            f"Ikut menghitung angka {k} sendiri, padahal '{KATA_SYARAT[syarat]}' tidak memasukkan angka itu."))
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.arah_terbalik", str(lawan), "K",
            "Menghitung angka di arah yang berlawanan dari yang ditanyakan."))
    if syarat == "kelipatan":
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.angka_kelipatan", str(k), "K",
            f"Menjawab {k}, yaitu bilangan pengalinya, bukan banyaknya kelipatan."))
    kandidat.append(Malrule(
        f"{TEMPLATE_ID}.hitung_lebih_satu", str(banyak + 1), "H",
        "Sudah mengerti caranya, tetapi satu angka terhitung dua kali sehingga jawabannya lebih satu."))
    kandidat.append(Malrule(
        f"{TEMPLATE_ID}.hitung_kurang_satu", str(banyak - 1), "H",
        "Sudah mengerti caranya, tetapi satu angka terlewat sehingga jawabannya kurang satu."))
    return kandidat


def _bangun_banyak_hasil(p: dict) -> tuple:
    objek, syarat, k = p["objek"], p["syarat"], p.get("k")
    himpunan = _himpunan(objek, syarat, k)
    frasa = _frasa_syarat(syarat, k)
    daftar = ", ".join(str(x) for x in himpunan)
    catatan = f" Angka {k} sendiri tidak ikut dihitung." if syarat in ("lebih_dari", "kurang_dari") else ""
    cara = (f"Tulis semua angka yang {frasa}: {daftar}.{catatan} "
            f"Hitung banyaknya, ada {len(himpunan)}. Jadi ada {len(himpunan)} kemungkinan.")
    return (_teks_hasil(objek, frasa), str(len(himpunan)),
            _malrule_hasil(objek, syarat, k, himpunan), cara)


# ── varian peluang_pecahan ───────────────────────────────────────────────

def _bangun_peluang_pecahan(p: dict) -> tuple:
    merah, biru, tanya = p["merah"], p["biru"], p["tanya"]
    total = merah + biru
    x, y = (merah, biru) if tanya == "merah" else (biru, merah)
    lain = "biru" if tanya == "merah" else "merah"
    kunci = f"{x}/{total}"
    teks = (f"Dalam kantong ada {merah} bola merah dan {biru} bola biru. "
            f"Satu bola diambil tanpa melihat. Peluang terambil bola {tanya} adalah ... "
            "(tulis dalam bentuk pecahan, contoh 1/4)")
    kandidat = [
        Malrule(f"{TEMPLATE_ID}.hanya_banyak_bola", str(x), "K",
                f"Menjawab {x}, yaitu banyak bola {tanya} saja, belum membaginya dengan banyak semua bola."),
        Malrule(f"{TEMPLATE_ID}.pecahan_terbalik", f"{total}/{x}", "K",
                f"Menulis pecahan terbalik: banyak semua bola di atas dan banyak bola {tanya} di bawah."),
        Malrule(f"{TEMPLATE_ID}.dibanding_warna_lain", f"{x}/{y}", "K",
                f"Membandingkan bola {tanya} dengan bola {lain}, bukan dengan semua bola."),
        Malrule(f"{TEMPLATE_ID}.peluang_warna_lain", f"{y}/{total}", "K",
                f"Menghitung peluang bola {lain}: kemungkinan salah membaca warna yang ditanyakan."),
    ]
    cara = (f"Peluang = banyak bola yang diinginkan dibagi banyak semua bola. "
            f"Semua bola ada {merah} + {biru} = {total}. Bola {tanya} ada {x}. "
            f"Jadi peluang terambil bola {tanya} adalah {kunci}.")
    return teks, kunci, kandidat, cara


_BANGUN = {
    "lebih_mungkin": _bangun_lebih_mungkin,
    "kepastian": _bangun_kepastian,
    "banyak_hasil": _bangun_banyak_hasil,
    "peluang_pecahan": _bangun_peluang_pecahan,
}


# ── domain eksplisit ─────────────────────────────────────────────────────

def _enumerasi_lebih_mungkin() -> list:
    return [{"varian": "lebih_mungkin", "merah": m, "biru": b, "hijau": h, "arah": arah}
            for pola in POLA_JUMLAH for (m, b, h) in permutations(pola) for arah in ARAH]


def _enumerasi_kepastian() -> list:
    hasil = []
    for i, isi in enumerate(WARNA):
        lain = WARNA[(i + 1) % len(WARNA)]  # satu warna lain, bergeser melingkar
        for n in JUMLAH_KEPASTIAN:
            for tanya in (isi, lain):
                hasil.append({"varian": "kepastian", "isi": isi, "n": n, "tanya": tanya})
    return hasil


def _enumerasi_banyak_hasil() -> list:
    hasil = []
    for objek, daftar in SYARAT_OBJEK.items():
        for syarat, k in daftar:
            p = {"varian": "banyak_hasil", "objek": objek, "syarat": syarat}
            if k is not None:
                p["k"] = k
            hasil.append(p)
    return hasil


def _enumerasi_peluang_pecahan() -> list:
    hasil = []
    for merah in range(2, max(TOTAL_PECAHAN)):
        for biru in range(2, max(TOTAL_PECAHAN)):
            if merah + biru not in TOTAL_PECAHAN or gcd(merah, biru) != 1:
                continue
            for tanya in ("merah", "biru"):
                hasil.append({"varian": "peluang_pecahan", "merah": merah, "biru": biru, "tanya": tanya})
    return hasil


_ENUMERATOR = {
    "lebih_mungkin": _enumerasi_lebih_mungkin,
    "kepastian": _enumerasi_kepastian,
    "banyak_hasil": _enumerasi_banyak_hasil,
    "peluang_pecahan": _enumerasi_peluang_pecahan,
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
        raise ValueError("level peluang dasar harus P6")


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


def peluang_dasar(varian: str, merah: int | None = None, biru: int | None = None,
                  hijau: int | None = None, arah: str | None = None,
                  isi: str | None = None, n: int | None = None, tanya: str | None = None,
                  objek: str | None = None, syarat: str | None = None,
                  k: int | None = None) -> Soal:
    """Kemungkinan dan peluang sederhana; kunci dihitung dari parameter sah."""
    diberi = {"varian": varian, "merah": merah, "biru": biru, "hijau": hijau, "arah": arah,
              "isi": isi, "n": n, "tanya": tanya, "objek": objek, "syarat": syarat, "k": k}
    p = {nama: nilai for nama, nilai in diberi.items() if nilai is not None}
    if not _sah(p):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, kandidat, pembahasan = _BANGUN[varian](p)
    return Soal(template_id=TEMPLATE_ID, parameter=p, teks=teks, kunci=kunci,
                malrule=saring_malrule(kunci, kandidat), pembahasan=pembahasan, bagian="A")
