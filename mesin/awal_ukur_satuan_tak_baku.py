"""Matematika Awal, jenis `ukur_satuan_tak_baku`: mengukur panjang dengan satuan tak baku (P1), teks saja.

Tiga bentuk soal (`varian`), semua panjang dinyatakan dalam klip, ubin, atau balok
(satuan buatan sendiri, BUKAN cm atau m):
  - `banding`: "Pensil panjangnya 6 klip. Buku panjangnya 9 klip. Mana yang lebih
    panjang?" (jawaban: nama benda, huruf kecil);
  - `selisih`: "... Buku lebih panjang berapa klip daripada pensil?" (jawaban: angka);
  - `sambung`: "Pita merah panjangnya 7 klip. Pita biru panjangnya 5 klip. Kedua pita
    disambung ujung ke ujung. Berapa klip panjang semuanya?" (jawaban: angka).

Panjang tiap benda 3..10 satuan dan SELALU berbeda (tidak ada soal `banding` yang
kedua panjangnya sama); jumlah dua panjang paling besar 19, jadi semua angka <= 20.
Tiap satuan punya benda yang masuk akal diukur dengannya (klip untuk benda kecil,
ubin untuk perabot, balok untuk benda panjang); soal membandingkan DUA benda dari
satuan yang sama, jadi perbandingan selalu adil.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban: `banding` menjawab benda yang lebih pendek (K); `selisih` menjumlah
bukan mengurangi (K) dan salah hitung lebih/kurang satu (H); `sambung` mengurangi bukan
menjumlah (K) dan salah hitung lebih/kurang satu (H). Jalur K selalu ada.

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu
anggota seragam dari domain varian itu memakai `rng` (tanpa `hash()`), jadi seed
yang sama menghasilkan soal yang sama lintas proses. Daftar BENDA bersifat
APPEND-ONLY menurut indeks: indeks ikut dalam identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import combinations, permutations
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "ukur_satuan_tak_baku"
LEVEL = ("P1",)
VARIAN = ("banding", "selisih", "sambung")
SATUAN = ("klip", "ubin", "balok")
PANJANG = tuple(range(3, 11))
PESAN_LUAR_DOMAIN = "parameter ukur satuan tak baku di luar domain"
PESAN_LEVEL = "level ukur satuan tak baku harus P1"

# Benda yang diukur per satuan (APPEND-ONLY menurut indeks).
BENDA_BANDING = {
    "klip": ("pensil", "buku", "sendok"),
    "ubin": ("meja", "lemari", "karpet"),
    "balok": ("sapu", "tongkat", "payung"),
}
# Benda yang bisa disambung ujung ke ujung (APPEND-ONLY menurut indeks).
BENDA_SAMBUNG = ("pita", "tali", "kain")
WARNA_SAMBUNG = ("merah", "biru")


def _kapital(kata: str) -> str:
    return kata[:1].upper() + kata[1:]


def _nama_banding(satuan: str, benda: int) -> str:
    return BENDA_BANDING[satuan][benda]


def _nama_sambung(benda: int, urutan: int) -> str:
    return f"{BENDA_SAMBUNG[benda]} {WARNA_SAMBUNG[urutan]}"


def _kalimat_panjang(nama: str, panjang: int, satuan: str) -> str:
    return f"{_kapital(nama)} panjangnya {panjang} {satuan}."


def _nama_pasangan(varian: str, satuan: str, benda: int, benda2) -> tuple:
    if varian == "sambung":
        return _nama_sambung(benda, 0), _nama_sambung(benda, 1)
    return _nama_banding(satuan, benda), _nama_banding(satuan, benda2)


def _teks(varian: str, satuan: str, benda: int, benda2, p1: int, p2: int) -> str:
    n1, n2 = _nama_pasangan(varian, satuan, benda, benda2)
    data = f"{_kalimat_panjang(n1, p1, satuan)} {_kalimat_panjang(n2, p2, satuan)}"
    if varian == "banding":
        return f"{data} Mana yang lebih panjang?"
    if varian == "selisih":
        panjang, pendek = (n1, n2) if p1 > p2 else (n2, n1)
        return f"{data} {_kapital(panjang)} lebih panjang berapa {satuan} daripada {pendek}?"
    return (f"{data} Kedua {BENDA_SAMBUNG[benda]} disambung ujung ke ujung. "
            f"Berapa {satuan} panjang semuanya?")


def _kunci(varian: str, satuan: str, benda: int, benda2, p1: int, p2: int) -> str:
    if varian == "sambung":
        return str(p1 + p2)
    if varian == "selisih":
        return str(abs(p1 - p2))
    n1, n2 = _nama_pasangan(varian, satuan, benda, benda2)
    return n1 if p1 > p2 else n2


def _pembahasan(varian: str, satuan: str, benda: int, benda2, p1: int, p2: int) -> str:
    n1, n2 = _nama_pasangan(varian, satuan, benda, benda2)
    kunci = _kunci(varian, satuan, benda, benda2, p1, p2)
    if varian == "banding":
        return (f"Bandingkan angkanya: {n1} {p1} {satuan}, {n2} {p2} {satuan}. "
                f"Makin banyak {satuan} yang muat, makin panjang bendanya. "
                f"Jadi yang lebih panjang adalah {kunci}.")
    if varian == "selisih":
        besar, kecil = max(p1, p2), min(p1, p2)
        return (f"Cari lebihnya dengan mengurangi: {besar} - {kecil} = {kunci}. "
                f"Jadi selisih panjangnya {kunci} {satuan}.")
    return (f"Dua {BENDA_SAMBUNG[benda]} disambung, jadi panjangnya ditambah: "
            f"{p1} + {p2} = {kunci}. Panjang semuanya {kunci} {satuan}.")


def _malrule_banding(satuan, benda, benda2, p1, p2) -> list:
    n1, n2 = _nama_pasangan("banding", satuan, benda, benda2)
    pendek = n2 if p1 > p2 else n1
    return [Malrule(
        f"{TEMPLATE_ID}.pilih_lebih_pendek", pendek, "K",
        f"Menjawab {pendek}, benda yang lebih pendek, kemungkinan tertukar arti "
        "lebih panjang dan lebih pendek.")]


def _malrule_hitung(kunci: int) -> list:
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.terhitung_dobel", str(kunci + 1), "H",
        "Sudah mengerti caranya, tetapi satu satuan terhitung dua kali sehingga jawabannya lebih satu.")]
    if kunci - 1 >= 1:
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.terlewat", str(kunci - 1), "H",
            "Sudah mengerti caranya, tetapi satu satuan terlewat sehingga jawabannya kurang satu."))
    return kandidat


def _malrule_selisih(p1: int, p2: int) -> list:
    kunci = abs(p1 - p2)
    return [Malrule(
        f"{TEMPLATE_ID}.jumlah_bukan_selisih", str(p1 + p2), "K",
        "Menjumlahkan kedua panjang, padahal yang ditanya lebihnya (selisih), "
        "jadi seharusnya dikurangi.")] + _malrule_hitung(kunci)


def _malrule_sambung(benda: int, p1: int, p2: int) -> list:
    kunci = p1 + p2
    return [Malrule(
        f"{TEMPLATE_ID}.selisih_bukan_jumlah", str(abs(p1 - p2)), "K",
        f"Mengurangkan kedua panjang, padahal {BENDA_SAMBUNG[benda]} yang disambung "
        "panjangnya bertambah, jadi seharusnya dijumlahkan.")] + _malrule_hitung(kunci)


def _kandidat_malrule(varian, satuan, benda, benda2, p1, p2) -> list:
    if varian == "banding":
        return _malrule_banding(satuan, benda, benda2, p1, p2)
    if varian == "selisih":
        return _malrule_selisih(p1, p2)
    return _malrule_sambung(benda, p1, p2)


def _indeks_sah(nilai, panjang: int) -> bool:
    return type(nilai) is int and 0 <= nilai < panjang


def _panjang_sah(p1, p2) -> bool:
    return (type(p1) is int and type(p2) is int and p1 in PANJANG and p2 in PANJANG
            and p1 != p2)


def _benda_sah(varian: str, satuan: str, benda, benda2) -> bool:
    if varian == "sambung":
        return benda2 is None and _indeks_sah(benda, len(BENDA_SAMBUNG))
    daftar = BENDA_BANDING[satuan]
    return (_indeks_sah(benda, len(daftar)) and _indeks_sah(benda2, len(daftar))
            and benda < benda2)


def _sah(varian, satuan, benda, benda2, p1, p2) -> bool:
    if varian not in VARIAN or satuan not in SATUAN:
        return False
    return _benda_sah(varian, satuan, benda, benda2) and _panjang_sah(p1, p2)


def ukur_satuan_tak_baku(varian: str, satuan: str, benda: int, p1: int, p2: int,
                         benda2: int | None = None) -> Soal:
    """Banding dua benda, selisih panjang, atau dua pita disambung (kunci dari parameter)."""
    if type(varian) is not str or type(satuan) is not str or not _sah(
            varian, satuan, benda, benda2, p1, p2):
        raise ValueError(PESAN_LUAR_DOMAIN)
    parameter = {"varian": varian, "satuan": satuan, "benda": benda, "p1": p1, "p2": p2}
    if benda2 is not None:
        parameter["benda2"] = benda2
    kunci = _kunci(varian, satuan, benda, benda2, p1, p2)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter,
        teks=_teks(varian, satuan, benda, benda2, p1, p2), kunci=kunci,
        malrule=saring_malrule(kunci, _kandidat_malrule(varian, satuan, benda, benda2, p1, p2)),
        pembahasan=_pembahasan(varian, satuan, benda, benda2, p1, p2), bagian="A")


def pengecoh_tambahan(parameter: dict) -> tuple:
    """Pengecoh pilihan ganda di luar malrule: varian `banding` hanya punya satu malrule.

    "sama panjang" bukan hipotesis kesalahan (panjang tiap soal selalu berbeda), jadi
    sengaja tidak menjadi malrule; ia hanya mengisi opsi PG. Varian lain tidak butuh.
    """
    return ("sama panjang",) if parameter["varian"] == "banding" else ()


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _pasangan_panjang() -> tuple:
    return tuple(permutations(PANJANG, 2))


def _enumerasi_dua_benda(varian: str) -> list:
    hasil = []
    for satuan in SATUAN:
        for benda, benda2 in combinations(range(len(BENDA_BANDING[satuan])), 2):
            for p1, p2 in _pasangan_panjang():
                hasil.append({"varian": varian, "satuan": satuan, "benda": benda,
                              "benda2": benda2, "p1": p1, "p2": p2})
    return hasil


def _enumerasi_sambung() -> list:
    return [{"varian": "sambung", "satuan": satuan, "benda": benda, "p1": p1, "p2": p2}
            for satuan in SATUAN
            for benda in range(len(BENDA_SAMBUNG))
            for p1, p2 in _pasangan_panjang()]


def _enumerasi(varian: str) -> list:
    if varian == "sambung":
        return _enumerasi_sambung()
    return _enumerasi_dua_benda(varian)


@lru_cache(maxsize=None)
def _domain_varian(varian: str) -> tuple:
    """Anggota domain satu varian sebagai tuple item immutable (urutan enumerasi = urutan undian)."""
    return tuple(tuple(p.items()) for p in _enumerasi(varian))


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError(PESAN_LEVEL)


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for varian in VARIAN for item in _domain_varian(varian))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu anggota seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return dict(rng.choice(_domain_varian(varian)))
