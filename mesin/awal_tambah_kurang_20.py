"""Matematika Awal, jenis `tambah_kurang_20`: penjumlahan dan pengurangan sampai 20 (P1), teks saja.

Lima bentuk soal (`varian`), semua berkunci angka bulat 1..20:
  - `tambah`: "8 + 5 = ..." (hasil 11..20; 36 dari 60 pasangan melewati sepuluh,
    yaitu satuan a < 10 dan a + b > 10; sisanya 10, 11, 12 ditambah satuan tanpa
    melewati sepuluh);
  - `kurang`: "15 − 7 = ..." (a 11..20, b 1..9; separuh pasangan memerlukan
    meminjam puluhan);
  - `cerita_tambah` dan `cerita_kurang`: kalimat pendek satu langkah (tiga konteks
    tiap varian, nama dan benda sintetis) atas pasangan bilangan yang sama;
  - `lengkapi`: "9 + ... = 15" atau "15 − ... = 8" (yang dicari adalah bilangan kedua).

Semua bilangan dan hasil <= 20 dan tanpa bilangan negatif. Teks memakai tanda
"−" (minus matematika) seperti `school_numbers_common.KURANG`.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban: operasi dibalik, lupa melewati puluhan, satuan dikurangkan terbalik,
lupa mengurangi puluhan setelah meminjam, menulis hasil atau bilangan awal saja
(semuanya K), serta meleset satu (H). Urutan kandidat: jawaban yang masih dalam
rentang sampai 20 lebih dulu, lalu jawaban hasil penjumlahan yang bisa melewati 20
(operasi dibalik pada pengurangan dan `lengkapi`) paling akhir, supaya pilihan ganda
hanya memakainya bila pengecoh lain kurang. Konteks cerita bersifat APPEND-ONLY
menurut indeks: indeks ikut identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from school_numbers_common import KURANG
from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "tambah_kurang_20"
LEVEL = ("P1",)
VARIAN = ("tambah", "kurang", "cerita_tambah", "cerita_kurang", "lengkapi")
BENTUK = ("tambah", "kurang")
PULUHAN = 10
BATAS = 20
PESAN_LUAR_DOMAIN = "parameter tambah kurang 20 di luar domain"

# Pasangan (a, b) sah. tambah: satuan melewati sepuluh, atau 10..12 + satuan tanpa
# melewati sepuluh. kurang: a 11..20 dikurangi satuan 1..9.
PASANGAN_TAMBAH = tuple(
    [(a, b) for a in range(1, 10) for b in range(1, 10) if a + b > PULUHAN]
    + [(a, b) for a in range(PULUHAN, PULUHAN + 3) for b in range(1, 10)
       if a % PULUHAN + b < PULUHAN])
PASANGAN_KURANG = tuple((a, b) for a in range(PULUHAN + 1, BATAS + 1) for b in range(1, 10))
PASANGAN = {"tambah": PASANGAN_TAMBAH, "kurang": PASANGAN_KURANG}

# APPEND-ONLY menurut indeks.
KONTEKS_TAMBAH = (
    "Rina punya {a} kelereng. Budi memberinya {b} kelereng lagi. "
    "Berapa kelereng Rina sekarang?",
    "Di dalam keranjang ada {a} apel. Dita memasukkan {b} apel lagi. "
    "Berapa apel di dalam keranjang sekarang?",
    "Eko menempel {a} stiker di bukunya. Lalu ia menempel {b} stiker lagi. "
    "Berapa stiker Eko sekarang?",
)
KONTEKS_KURANG = (
    "Budi punya {a} kelereng. Ia memberikan {b} kelereng kepada Rina. "
    "Berapa kelereng Budi sekarang?",
    "Di atas piring ada {a} kue. Dita memakan {b} kue. Berapa kue yang tersisa?",
    "Eko punya {a} balon. Lalu {b} balon terbang lepas. Berapa balon Eko sekarang?",
)
JUMLAH_KONTEKS = len(KONTEKS_TAMBAH)

BIDANG = {
    "tambah": ("a", "b"),
    "kurang": ("a", "b"),
    "cerita_tambah": ("a", "b", "konteks"),
    "cerita_kurang": ("a", "b", "konteks"),
    "lengkapi": ("bentuk", "a", "b"),
}


def _jenis_operasi(varian: str, isian: dict):
    """'tambah' atau 'kurang' menurut varian (lengkapi: menurut bentuk); None bila tak sah."""
    if varian in ("tambah", "cerita_tambah"):
        return "tambah"
    if varian in ("kurang", "cerita_kurang"):
        return "kurang"
    bentuk = isian.get("bentuk")
    return bentuk if type(bentuk) is str and bentuk in BENTUK else None


def _sah(varian, isian: dict) -> bool:
    if type(varian) is not str or varian not in BIDANG:
        return False
    if set(isian) != set(BIDANG[varian]):
        return False
    operasi = _jenis_operasi(varian, isian)
    if operasi is None:
        return False
    if any(type(isian[k]) is not int for k in ("a", "b")):
        return False
    if (isian["a"], isian["b"]) not in PASANGAN[operasi]:
        return False
    if "konteks" in isian:
        return type(isian["konteks"]) is int and 0 <= isian["konteks"] < JUMLAH_KONTEKS
    return True


# ── kunci, teks, pembahasan ──────────────────────────────────────────────

def _kunci(varian: str, p: dict) -> int:
    if varian in ("tambah", "cerita_tambah"):
        return p["a"] + p["b"]
    if varian in ("kurang", "cerita_kurang"):
        return p["a"] - p["b"]
    return p["b"]


def _teks(varian: str, p: dict) -> str:
    a, b = p["a"], p["b"]
    if varian == "tambah":
        return f"{a} + {b} = ..."
    if varian == "kurang":
        return f"{a} {KURANG} {b} = ..."
    if varian == "cerita_tambah":
        return KONTEKS_TAMBAH[p["konteks"]].format(a=a, b=b)
    if varian == "cerita_kurang":
        return KONTEKS_KURANG[p["konteks"]].format(a=a, b=b)
    if p["bentuk"] == "tambah":
        return f"{a} + ... = {a + b}"
    return f"{a} {KURANG} ... = {a - b}"


def _bahas_tambah(a: int, b: int) -> str:
    jumlah = a + b
    if a < PULUHAN:
        butuh = PULUHAN - a
        return (f"{a} + {b}: genapkan {a} menjadi 10 dengan mengambil {butuh} dari {b}. "
                f"Sisanya {b - butuh}. Jadi 10 + {b - butuh} = {jumlah}.")
    satuan = a % PULUHAN
    return (f"{a} + {b}: puluhannya tetap 10, satuannya {satuan} + {b} = {satuan + b}. "
            f"Jadi 10 + {satuan + b} = {jumlah}.")


def _bahas_kurang(a: int, b: int) -> str:
    selisih = a - b
    satuan = a % PULUHAN
    if a == BATAS:
        return (f"{a} {KURANG} {b}: ambil {b} dari 10 yang bawah, 10 {KURANG} {b} = "
                f"{PULUHAN - b}. Jadi 10 + {PULUHAN - b} = {selisih}.")
    if satuan < b:
        return (f"{a} {KURANG} {b}: kurangi dulu {satuan} supaya jadi 10 "
                f"({a} {KURANG} {satuan} = 10). Masih perlu mengurangi {b - satuan} lagi: "
                f"10 {KURANG} {b - satuan} = {selisih}.")
    return (f"{a} {KURANG} {b}: satuannya {satuan} {KURANG} {b} = {satuan - b}. "
            f"Jadi 10 + {satuan - b} = {selisih}.")


def _pembahasan(varian: str, p: dict) -> str:
    a, b = p["a"], p["b"]
    if varian == "tambah":
        return _bahas_tambah(a, b)
    if varian == "kurang":
        return _bahas_kurang(a, b)
    if varian == "cerita_tambah":
        return f"Banyaknya bertambah, jadi dijumlahkan. {_bahas_tambah(a, b)}"
    if varian == "cerita_kurang":
        return f"Banyaknya berkurang, jadi dikurangkan. {_bahas_kurang(a, b)}"
    if p["bentuk"] == "tambah":
        return (f"Cari bilangan yang jika ditambah {a} hasilnya {a + b}. Hitung "
                f"selisihnya: {a + b} {KURANG} {a} = {b}. Cek: {a} + {b} = {a + b}.")
    return (f"Cari bilangan yang dikurangkan dari {a} agar sisanya {a - b}. Hitung "
            f"selisihnya: {a} {KURANG} {a - b} = {b}. Cek: {a} {KURANG} {b} = {a - b}.")


# ── malrule (dalam rentang dulu, hasil jumlah di akhir) ─────────────────

def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _dalam(nilai: int) -> bool:
    return 0 <= nilai <= BATAS


def _meleset(kunci: int) -> list:
    hasil = []
    for nama, nilai, kata in (("kurang_satu", kunci - 1, "kurang satu"),
                              ("lebih_satu", kunci + 1, "lebih satu")):
        if _dalam(nilai):
            hasil.append(_mal(nama, nilai, "H",
                              f"Sudah memakai operasi yang benar, tetapi hitungannya "
                              f"{kata} sehingga jawabannya {nilai}."))
    return hasil


def _kandidat_tambah(a: int, b: int) -> list:
    jumlah = a + b
    lewat = a < PULUHAN
    alasan_puluhan = (
        f"Menjawab {jumlah - PULUHAN}; kemungkinan lupa melewati sepuluh sehingga "
        "hanya satuannya yang ditulis." if lewat else
        f"Menjawab {jumlah - PULUHAN}; kemungkinan lupa menambahkan puluhannya.")
    return [
        _mal("lupa_puluhan", jumlah - PULUHAN, "K", alasan_puluhan),
        _mal("dikurang_bukan_dijumlah", abs(a - b), "K",
             f"Menjawab {abs(a - b)}; kemungkinan mengurangi, bukan menjumlah "
             f"({a} dan {b} dibalik operasinya)."),
    ] + _meleset(jumlah)


def _kandidat_kurang(a: int, b: int) -> list:
    selisih, satuan = a - b, a % PULUHAN
    meminjam = satuan < b
    hasil = []
    if meminjam:
        hasil.append(_mal("satuan_dikurang_terbalik", PULUHAN + (b - satuan), "K",
                          f"Menjawab {PULUHAN + (b - satuan)}; kemungkinan satuan yang "
                          f"kecil dikurangkan terbalik ({b} {KURANG} {satuan}), "
                          "padahal 10 lebih dulu harus dipinjam."))
    else:
        hasil.append(_mal("puluhan_hilang", satuan - b, "K",
                          f"Menjawab {satuan - b}; kemungkinan hanya satuannya yang "
                          "dikurangkan dan puluhannya tidak ditulis."))
    if meminjam and a < BATAS:
        hasil.append(_mal("lupa_kurangi_puluhan", selisih + PULUHAN, "K",
                          f"Menjawab {selisih + PULUHAN}; kemungkinan sudah meminjam "
                          "sepuluh tetapi puluhannya tidak dikurangi."))
    hasil.extend(_meleset(selisih))
    hasil.append(_mal("dijumlah_bukan_dikurang", a + b, "K",
                      f"Menjawab {a + b}; kemungkinan menjumlah, bukan mengurang "
                      f"({a} dan {b} dibalik operasinya)."))
    return hasil


def _kandidat_lengkapi(bentuk: str, a: int, b: int) -> list:
    ruas_kanan = a + b if bentuk == "tambah" else a - b
    hasil = [_mal("hasil_ditulis", ruas_kanan, "K",
                  f"Menjawab {ruas_kanan}; kemungkinan menulis hasil di ruas kanan, "
                  "bukan bilangan yang dicari.")]
    if bentuk == "kurang":
        hasil.append(_mal("bilangan_awal_diulang", a, "K",
                          f"Menjawab {a}; kemungkinan menyalin bilangan awal."))
    return hasil + _meleset(b) + [
        _mal("dijumlah_dua_bilangan", a + ruas_kanan, "K",
             f"Menjawab {a + ruas_kanan}; kemungkinan menjumlah dua bilangan yang "
             "tampak, bukan mencari yang hilang.")]


def _kandidat(varian: str, p: dict) -> list:
    a, b = p["a"], p["b"]
    if varian in ("tambah", "cerita_tambah"):
        return _kandidat_tambah(a, b)
    if varian in ("kurang", "cerita_kurang"):
        return _kandidat_kurang(a, b)
    return _kandidat_lengkapi(p["bentuk"], a, b)


def tambah_kurang_20(varian: str, a: int | None = None, b: int | None = None,
                     konteks: int | None = None, bentuk: str | None = None) -> Soal:
    """Penjumlahan/pengurangan sampai 20: kunci dari parameter, malrule hipotesis."""
    isian = {nama: nilai for nama, nilai in (
        ("bentuk", bentuk), ("a", a), ("b", b), ("konteks", konteks)) if nilai is not None}
    if not _sah(varian, isian):
        raise ValueError(PESAN_LUAR_DOMAIN)
    kunci = str(_kunci(varian, isian))
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isian},
        teks=_teks(varian, isian), kunci=kunci,
        malrule=saring_malrule(kunci, _kandidat(varian, isian)),
        pembahasan=_pembahasan(varian, isian), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi() -> tuple:
    hasil = []
    for varian in ("tambah", "kurang"):
        hasil.extend({"varian": varian, "a": a, "b": b} for a, b in PASANGAN[varian])
    for varian, operasi in (("cerita_tambah", "tambah"), ("cerita_kurang", "kurang")):
        hasil.extend({"varian": varian, "a": a, "b": b, "konteks": k}
                     for a, b in PASANGAN[operasi] for k in range(JUMLAH_KONTEKS))
    for bentuk in BENTUK:
        hasil.extend({"varian": "lengkapi", "bentuk": bentuk, "a": a, "b": b}
                     for a, b in PASANGAN[bentuk])
    return tuple(hasil)


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level tambah kurang 20 harus P1")


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
