"""Matematika Awal, jenis `tambah_kurang_100`: tambah-kurang sampai 100, teks saja (P2).

Empat bentuk soal (`varian`), semua berkunci angka bulat:
  - `tambah`: "38 + 27 = ..." (bilangan dua angka ditambah satu atau dua angka, hasil
    paling besar 100);
  - `kurang`: "52 − 28 = ..." (hasil paling kecil 1);
  - `lengkapi`: bilangan yang hilang, empat bentuk (`bentuk`): `cari_tambahan`
    "47 + ... = 83", `cari_awal_tambah` "... + 25 = 83", `cari_pengurang`
    "83 − ... = 47", `cari_awal_kurang` "... − 25 = 40";
  - `cerita`: satu langkah, kalimat pendek, benda dan nama sintetis (`op` tambah atau
    kurang, `pola` = indeks kalimat).

Semua bilangan yang tampil (kecuali hasil/selisih yang dihitung) bukan kelipatan 10,
sehingga satuan selalu ikut menentukan ada tidaknya "menyimpan" (tambah) atau
"meminjam" (kurang). Pada tiap varian ruang soal terbagi dua kelas, TANPA dan DENGAN
menyimpan/meminjam; sampler memilih varian seragam, lalu kelas seragam (kira-kira
setengah-setengah), lalu satu parameter seragam dalam kelas itu, semuanya dari `rng`
(tanpa `hash()`), sehingga seed yang sama menghasilkan soal yang sama lintas proses.
`tambah` dan `kurang` memakai SELURUH pasangan sah; `lengkapi` dan `cerita` memakai
pasangan yang dijarangkan (hanya yang (a + 3b) habis dibagi 7 atau 11, lihat
`_jarangkan`) supaya domain tetap sekitar sebelas ribu dan tidak didominasi dua varian itu. Parameter sah
persis anggota `domain_parameter`; selain itu `ValueError`.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari
satu jawaban:
  - K, tambah: lupa menyimpan (38 + 27 jadi 55), menulis hasil satuan utuh (jadi 515),
    operasi dibalik (dikurang, bukan ditambah);
  - K, kurang: per kolom bilangan kecil dikurangkan dari yang besar (52 − 28 jadi 36),
    lupa mengurangi puluhan yang dipinjam (jadi 34), operasi dibalik (ditambah);
  - H, semuanya: lebih/kurang 10 atau lebih/kurang 1 dari kunci bila masih wajar
    (1..100). Kandidat yang kebetulan sama dengan kunci atau dengan kandidat lain
    dibuang `saring_malrule`; tiap parameter sah menyisakan minimal satu jalur K dan
    minimal tiga pengecoh angka berbeda.
Pada `lengkapi` dan `cerita` malrule mengikuti operasi yang SEBENARNYA dihitung anak
(mis. "47 + ... = 83" dihitung 83 − 47, jadi operasi dibalik = 83 + 47 = 130).

Kunci angka polos tanpa titik ribuan (hasil paling besar 100). Soal teks tanpa gambar.
Daftar kalimat cerita bersifat APPEND-ONLY menurut indeks: indeks ikut identitas soal
di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "tambah_kurang_100"
LEVEL = ("P2",)
VARIAN = ("tambah", "kurang", "lengkapi", "cerita")
BENTUK = ("cari_tambahan", "cari_awal_tambah", "cari_pengurang", "cari_awal_kurang")
OPERASI_CERITA = ("tambah", "kurang")
KELAS = ("tanpa", "dengan")  # tanpa / dengan menyimpan atau meminjam
BATAS = 100
TANDA_KURANG = "−"
PESAN_LUAR_DOMAIN = "parameter tambah kurang 100 di luar domain"
JARANG_LENGKAPI = 7  # bilangan prima; lihat _jarangkan
JARANG_CERITA = 11

# APPEND-ONLY menurut indeks (indeks ikut identitas soal).
CERITA_TAMBAH = (
    "Rina punya {a} kelereng. Budi memberinya {b} kelereng lagi. "
    "Berapa kelereng Rina sekarang?",
    "Di rak ada {a} buku. Dita menaruh {b} buku lagi di rak itu. "
    "Berapa banyak buku di rak sekarang?",
    "Eko mengumpulkan {a} stiker kemarin dan {b} stiker hari ini. "
    "Berapa stiker yang Eko kumpulkan semuanya?",
)
CERITA_KURANG = (
    "Rina punya {a} manik-manik. Sebanyak {b} manik-manik ia pakai untuk gelang. "
    "Berapa manik-manik yang masih tersisa?",
    "Di kebun ada {a} bunga. Eko memetik {b} bunga. "
    "Berapa bunga yang masih ada di kebun?",
    "Dita punya {a} lembar kertas. Ia memakai {b} lembar untuk menggambar. "
    "Berapa lembar kertas yang tersisa?",
)

# Nama bidang tiap varian, urut seperti tampil di parameter.
SKEMA = {
    "tambah": ("a", "b"),
    "kurang": ("a", "b"),
    "lengkapi": ("bentuk", "x", "c"),
    "cerita": ("op", "a", "b", "pola"),
}
BIDANG_TEKS = frozenset({"varian", "bentuk", "op"})


# ── pasangan bilangan ────────────────────────────────────────────────────

def _bukan_puluhan(n: int) -> bool:
    return n % 10 != 0


def _pasangan_tambah() -> tuple:
    """(a, b): a dua angka, b satu atau dua angka, tanpa kelipatan 10, a + b <= 100."""
    return tuple((a, b) for a in range(11, BATAS) if _bukan_puluhan(a)
                 for b in range(2, BATAS) if _bukan_puluhan(b) and a + b <= BATAS)


def _pasangan_kurang() -> tuple:
    """(a, b): a dua angka, b satu atau dua angka, tanpa kelipatan 10, a > b."""
    return tuple((a, b) for a in range(11, BATAS) if _bukan_puluhan(a)
                 for b in range(2, BATAS) if _bukan_puluhan(b) and a > b)


def _jarangkan(pasangan: tuple, modulus: int) -> tuple:
    """Sisakan sekitar 1/modulus pasangan: (a + 3b) habis dibagi modulus (prima).

    Bukan loncatan menurut urutan, supaya satuan dan puluhan a dan b tetap beragam.
    """
    return tuple((a, b) for a, b in pasangan if (a + 3 * b) % modulus == 0)


def _dua_angka(pasangan: tuple) -> tuple:
    return tuple((a, b) for a, b in pasangan if a >= 11 and b >= 11)


def _ada_simpan(a: int, b: int) -> bool:
    return a % 10 + b % 10 >= 10


def _ada_pinjam(a: int, b: int) -> bool:
    return a % 10 < b % 10


# ── operasi yang sebenarnya dihitung anak ────────────────────────────────

def _operasi(varian: str, p: dict) -> tuple:
    """(jenis, kiri, kanan): jenis 'tambah' = kiri + kanan, 'kurang' = kiri - kanan."""
    if varian in ("tambah", "kurang"):
        return varian, p["a"], p["b"]
    if varian == "cerita":
        return p["op"], p["a"], p["b"]
    bentuk, x, c = p["bentuk"], p["x"], p["c"]
    if bentuk in ("cari_tambahan", "cari_awal_tambah"):
        return "kurang", c, x
    if bentuk == "cari_pengurang":
        return "kurang", x, c
    return "tambah", c, x


def _kunci(varian: str, p: dict) -> int:
    jenis, kiri, kanan = _operasi(varian, p)
    return kiri + kanan if jenis == "tambah" else kiri - kanan


def _kelas(varian: str, p: dict) -> str:
    jenis, kiri, kanan = _operasi(varian, p)
    ada = _ada_simpan(kiri, kanan) if jenis == "tambah" else _ada_pinjam(kiri, kanan)
    return KELAS[1] if ada else KELAS[0]


# ── teks ─────────────────────────────────────────────────────────────────

def _teks(varian: str, p: dict) -> str:
    if varian == "tambah":
        return f"{p['a']} + {p['b']} = ..."
    if varian == "kurang":
        return f"{p['a']} {TANDA_KURANG} {p['b']} = ..."
    if varian == "cerita":
        pola = CERITA_TAMBAH if p["op"] == "tambah" else CERITA_KURANG
        return pola[p["pola"]].format(a=p["a"], b=p["b"])
    x, c = p["x"], p["c"]
    return {
        "cari_tambahan": f"{x} + ... = {c}",
        "cari_awal_tambah": f"... + {x} = {c}",
        "cari_pengurang": f"{x} {TANDA_KURANG} ... = {c}",
        "cari_awal_kurang": f"... {TANDA_KURANG} {x} = {c}",
    }[p["bentuk"]]


# ── pembahasan ───────────────────────────────────────────────────────────

def _pembahasan_tambah(a: int, b: int) -> str:
    ta, sa, tb, sb = a // 10, a % 10, b // 10, b % 10
    kunci = a + b
    if not _ada_simpan(a, b):
        return (f"Tambahkan satuannya: {sa} + {sb} = {sa + sb}. "
                f"Tambahkan puluhannya: {ta * 10} + {tb * 10} = {(ta + tb) * 10}. "
                f"Jadi {a} + {b} = {(ta + tb) * 10} + {sa + sb} = {kunci}.")
    satuan = sa + sb
    return (f"Tambahkan satuannya: {sa} + {sb} = {satuan}. Tulis {satuan - 10} dan "
            f"simpan 1 puluhan. Tambahkan puluhannya: {ta} + {tb} + 1 = {ta + tb + 1} "
            f"puluhan, yaitu {(ta + tb + 1) * 10}. "
            f"Jadi {a} + {b} = {(ta + tb + 1) * 10} + {satuan - 10} = {kunci}.")


def _pembahasan_kurang(a: int, b: int) -> str:
    ta, sa, tb, sb = a // 10, a % 10, b // 10, b % 10
    kunci = a - b
    if not _ada_pinjam(a, b):
        return (f"Kurangi satuannya: {sa} {TANDA_KURANG} {sb} = {sa - sb}. "
                f"Kurangi puluhannya: {ta * 10} {TANDA_KURANG} {tb * 10} = {(ta - tb) * 10}. "
                f"Jadi {a} {TANDA_KURANG} {b} = {(ta - tb) * 10} + {sa - sb} = {kunci}.")
    pinjam = (f"Satuan {sa} tidak cukup untuk dikurangi {sb}, jadi pinjam 1 puluhan: "
              f"{sa + 10} {TANDA_KURANG} {sb} = {sa + 10 - sb}. Puluhan {ta} tinggal {ta - 1}")
    if tb == 0:
        puluhan = ". " if ta == 1 else f", yaitu {(ta - 1) * 10}. "
    else:
        puluhan = (f", lalu {ta - 1} {TANDA_KURANG} {tb} = {ta - 1 - tb} puluhan, yaitu "
                   f"{(ta - 1 - tb) * 10}. ")
    return (f"{pinjam}{puluhan}Jadi {a} {TANDA_KURANG} {b} = "
            f"{(ta - 1 - tb) * 10} + {sa + 10 - sb} = {kunci}.")


def _pembahasan_operasi(jenis: str, kiri: int, kanan: int) -> str:
    if jenis == "tambah":
        return _pembahasan_tambah(kiri, kanan)
    return _pembahasan_kurang(kiri, kanan)


def _pembahasan_lengkapi(p: dict, kunci: int) -> str:
    jenis, kiri, kanan = _operasi("lengkapi", p)
    x, c = p["x"], p["c"]
    awal = {
        "cari_tambahan": f"Bilangan yang hilang adalah selisih {c} dan {x}, yaitu "
                         f"{c} {TANDA_KURANG} {x}.",
        "cari_awal_tambah": f"Bilangan yang hilang adalah {c} {TANDA_KURANG} {x}.",
        "cari_pengurang": f"Bilangan yang hilang adalah selisih {x} dan {c}, yaitu "
                          f"{x} {TANDA_KURANG} {c}.",
        "cari_awal_kurang": f"Sebelum dikurangi {x}, bilangannya lebih besar. "
                            f"Bilangan yang hilang adalah {c} + {x}.",
    }[p["bentuk"]]
    cek = {
        "cari_tambahan": f"{x} + {kunci} = {c}",
        "cari_awal_tambah": f"{kunci} + {x} = {c}",
        "cari_pengurang": f"{x} {TANDA_KURANG} {kunci} = {c}",
        "cari_awal_kurang": f"{kunci} {TANDA_KURANG} {x} = {c}",
    }[p["bentuk"]]
    return (f"{awal} {_pembahasan_operasi(jenis, kiri, kanan)} "
            f"Cek: {cek}, jadi bilangan yang hilang adalah {kunci}.")


def _pembahasan(varian: str, p: dict, kunci: int) -> str:
    if varian == "lengkapi":
        return _pembahasan_lengkapi(p, kunci)
    jenis, kiri, kanan = _operasi(varian, p)
    isi = _pembahasan_operasi(jenis, kiri, kanan)
    if varian != "cerita":
        return isi
    tanda = "+" if jenis == "tambah" else TANDA_KURANG
    arah = "menambah" if jenis == "tambah" else "mengurangi"
    return f"Ceritanya {arah}, jadi hitung {kiri} {tanda} {kanan}. {isi}"


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _wajar(n: int) -> bool:
    return 1 <= n <= BATAS


def _meleset(kunci: int) -> list:
    """H: lebih/kurang 10 dan lebih/kurang 1, hanya bila hasilnya masih wajar."""
    kandidat = [
        ("lebih_sepuluh", kunci + 10, "Sudah paham caranya, tetapi hasilnya lebih sepuluh "
                                      f"sehingga jawabannya {kunci + 10}."),
        ("kurang_sepuluh", kunci - 10, "Sudah paham caranya, tetapi hasilnya kurang sepuluh "
                                       f"sehingga jawabannya {kunci - 10}."),
        ("lebih_satu", kunci + 1, "Sudah paham caranya, tetapi hitungan satuannya meleset "
                                  f"satu sehingga jawabannya {kunci + 1}."),
        ("kurang_satu", kunci - 1, "Sudah paham caranya, tetapi hitungan satuannya meleset "
                                   f"satu sehingga jawabannya {kunci - 1}."),
    ]
    return [_mal(nama, n, "H", alasan) for nama, n, alasan in kandidat if _wajar(n)]


def _kandidat_tambah(a: int, b: int) -> list:
    ta, sa, tb, sb = a // 10, a % 10, b // 10, b % 10
    hasil = []
    if _ada_simpan(a, b):
        satuan = sa + sb
        lupa = (ta + tb) * 10 + satuan - 10
        utuh = (ta + tb) * 100 + satuan
        hasil.append(_mal(
            "lupa_menyimpan", lupa, "K",
            f"Lupa menyimpan satu puluhan dari penjumlahan satuan ({sa} + {sb} = {satuan}), "
            f"sehingga jawabannya {lupa}."))
        hasil.append(_mal(
            "satuan_ditulis_utuh", utuh, "K",
            f"Menulis hasil satuan ({satuan}) utuh di belakang jumlah puluhan tanpa "
            f"menyimpan, sehingga jawabannya {utuh}."))
    hasil.append(_mal(
        "operasi_dibalik", abs(a - b), "K",
        "Mengurangkan bilangan yang lebih kecil dari yang lebih besar, bukan menjumlahkan "
        f"keduanya, sehingga jawabannya {abs(a - b)}."))
    return hasil + _meleset(a + b)


def _kandidat_kurang(a: int, b: int) -> list:
    ta, sa, tb, sb = a // 10, a % 10, b // 10, b % 10
    kunci = a - b
    hasil = []
    if _ada_pinjam(a, b):
        tertukar = (ta - tb) * 10 + (sb - sa)
        hasil.append(_mal(
            "kolom_tertukar", tertukar, "K",
            f"Pada kolom satuan mengurangkan yang kecil dari yang besar ({sb} {TANDA_KURANG} "
            f"{sa}), bukan meminjam, sehingga jawabannya {tertukar}."))
        hasil.append(_mal(
            "lupa_kurangi_pinjaman", kunci + 10, "K",
            "Sudah meminjam 1 puluhan untuk satuan, tetapi puluhannya tidak dikurangi satu, "
            f"sehingga jawabannya {kunci + 10}."))
    hasil.append(_mal(
        "operasi_dibalik", a + b, "K",
        f"Menjumlahkan kedua bilangan, bukan mengurangkan, sehingga jawabannya {a + b}."))
    return hasil + _meleset(kunci)


def _kandidat(varian: str, p: dict) -> list:
    jenis, kiri, kanan = _operasi(varian, p)
    if jenis == "tambah":
        return _kandidat_tambah(kiri, kanan)
    return _kandidat_kurang(kiri, kanan)


# ── validasi ─────────────────────────────────────────────────────────────

def _tipe_sah(nama: str, nilai) -> bool:
    if nama in BIDANG_TEKS:
        return type(nilai) is str
    return type(nilai) is int


def _kanon(varian, isian: dict):
    """Bentuk beku parameter sah, atau None bila nama/tipe bidang tidak cocok."""
    if type(varian) is not str or varian not in SKEMA:
        return None
    if set(isian) != set(SKEMA[varian]):
        return None
    if not all(_tipe_sah(nama, isian[nama]) for nama in SKEMA[varian]):
        return None
    return (("varian", varian),) + tuple((nama, isian[nama]) for nama in SKEMA[varian])


@lru_cache(maxsize=None)
def _himpunan_domain() -> frozenset:
    return frozenset(_domain_beku())


def _sah(varian, isian: dict) -> bool:
    kanon = _kanon(varian, isian)
    return kanon is not None and kanon in _himpunan_domain()


# ── soal ─────────────────────────────────────────────────────────────────

def tambah_kurang_100(varian: str, a: int | None = None, b: int | None = None,
                      bentuk: str | None = None, x: int | None = None,
                      c: int | None = None, op: str | None = None,
                      pola: int | None = None) -> Soal:
    """Tambah/kurang sampai 100, bilangan hilang, atau cerita satu langkah (kunci dari parameter)."""
    isian = {nama: nilai for nama, nilai in (
        ("a", a), ("b", b), ("bentuk", bentuk), ("x", x), ("c", c), ("op", op),
        ("pola", pola)) if nilai is not None}
    if not _sah(varian, isian):
        raise ValueError(PESAN_LUAR_DOMAIN)
    kunci = _kunci(varian, isian)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isian},
        teks=_teks(varian, isian), kunci=str(kunci),
        malrule=saring_malrule(str(kunci), _kandidat(varian, isian)),
        pembahasan=_pembahasan(varian, isian, kunci), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _item_tambah_kurang(varian: str, pasangan: tuple) -> list:
    return [{"varian": varian, "a": a, "b": b} for a, b in pasangan]


def _item_lengkapi(tambah: tuple, kurang: tuple) -> list:
    pool_tambah = _jarangkan(_dua_angka(tambah), JARANG_LENGKAPI)
    pool_kurang = _jarangkan(_dua_angka(kurang), JARANG_LENGKAPI)
    hasil = []
    for a, b in pool_tambah:
        hasil.append({"varian": "lengkapi", "bentuk": "cari_tambahan", "x": a, "c": a + b})
    for a, b in pool_tambah:
        hasil.append({"varian": "lengkapi", "bentuk": "cari_awal_tambah", "x": b, "c": a + b})
    for a, b in pool_kurang:
        hasil.append({"varian": "lengkapi", "bentuk": "cari_pengurang", "x": a, "c": a - b})
    for a, b in pool_kurang:
        hasil.append({"varian": "lengkapi", "bentuk": "cari_awal_kurang", "x": b, "c": a - b})
    return hasil


def _item_cerita(tambah: tuple, kurang: tuple) -> list:
    hasil = []
    for op, pasangan, pola in (("tambah", tambah, CERITA_TAMBAH),
                               ("kurang", kurang, CERITA_KURANG)):
        for a, b in _jarangkan(pasangan, JARANG_CERITA):
            for indeks in range(len(pola)):
                hasil.append({"varian": "cerita", "op": op, "a": a, "b": b, "pola": indeks})
    return hasil


def _enumerasi() -> list:
    tambah, kurang = _pasangan_tambah(), _pasangan_kurang()
    return (_item_tambah_kurang("tambah", tambah) + _item_tambah_kurang("kurang", kurang)
            + _item_lengkapi(tambah, kurang) + _item_cerita(tambah, kurang))


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(item.items()) for item in _enumerasi())


@lru_cache(maxsize=None)
def _kolam() -> dict:
    """{(varian, kelas): tuple item beku}; tiap kolam tidak kosong."""
    kolam = {(v, k): [] for v in VARIAN for k in KELAS}
    for item in _domain_beku():
        p = dict(item)
        kolam[(p["varian"], _kelas(p["varian"], p))].append(item)
    return {kunci: tuple(isi) for kunci, isi in kolam.items()}


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level tambah kurang 100 harus P2")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku())


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu kelas (tanpa/dengan simpan-pinjam) seragam, lalu satu parameter."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    kelas = rng.choice(KELAS)
    return dict(rng.choice(_kolam()[(varian, kelas)]))
