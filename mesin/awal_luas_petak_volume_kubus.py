"""Matematika Awal, jenis `luas_petak_volume_kubus` (P4): luas dengan petak, volume dengan kubus satuan.

Menutup dua sub-materi bab Kelas 4 B4 "Pengukuran luas dan volume": luas dengan petak
satuan dan volume dengan kubus satuan. Soal teks saja; susunan petak/kubus dijelaskan
secara eksplisit lewat banyak baris, kolom, dan lapis (tanpa gambar). Empat bentuk
(`varian`), semuanya berkunci angka bulat:
  - `luas_petak`: "Sebuah persegi panjang tersusun dari 3 baris petak satuan, tiap baris 5
    petak. Luasnya ... petak satuan." (baris dan kolom 2..9, tidak sama);
  - `luas_bandingkan`: dua persegi panjang petak, selisih luas "Luas A lebih besar ... petak
    satuan daripada luas B" (A: baris dan kolom 4..8; B: baris dan kolom 2..4; luas A > luas B);
  - `volume_kubus_satuan`: "Sebuah balok tersusun dari kubus satuan: 3 lapis, tiap lapis 2
    baris dan tiap baris 4 kubus. Volumenya ... kubus satuan." (lapis dan baris 2..5, kolom 2..6);
  - `tambah_kubus`: balok seperti di atas, lalu Dita menambahkan 2..5 kubus satuan; volume
    benda sekarang (lapis dan baris 2..4, kolom 2..5).

Hubungan yang dipakai hanya luas = baris × petak tiap baris dan volume = lapis × baris ×
kolom; semua bilangan bulat dan satuan "satuan" (petak/kubus), tanpa cm atau m. Kunci dan
malrule berupa angka polos. Teks tanpa gambar, jadi kecocokan dengan bab hanya "sebagian".

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu
jawaban: menjumlah alih-alih mengalikan, melewatkan satu faktor, menjumlah atau mengalikan
semua angka soal, salah operasi untuk selisih (semuanya K); lebih atau kurang satu saat
menghitung, atau lupa/terbalik menambah kubus (H, hanya bila nyata berbeda dari kunci). Tiap
parameter sah menyisakan minimal satu jalur K dan minimal dua pengecoh angka berbeda.

Domain kecil dan eksplisit (`domain_parameter`): sampler memilih `varian` seragam dulu supaya
`luas_bandingkan` yang parameternya paling banyak tidak mendominasi lembar, lalu satu parameter
seragam dalam varian itu, semuanya dari `rng` (tanpa `hash()`), sehingga seed yang sama
menghasilkan soal yang sama lintas proses.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "luas_petak_volume_kubus"
LEVEL = ("P4",)
VARIAN = ("luas_petak", "luas_bandingkan", "volume_kubus_satuan", "tambah_kubus")
PESAN_LUAR_DOMAIN = "parameter luas petak volume kubus di luar domain"

SISI_LUAS = tuple(range(2, 10))
SISI_A = tuple(range(4, 9))
SISI_B = tuple(range(2, 5))
LAPIS_BARIS_VOLUME = tuple(range(2, 6))
KOLOM_VOLUME = tuple(range(2, 7))
LAPIS_BARIS_TAMBAH = tuple(range(2, 5))
KOLOM_TAMBAH = tuple(range(2, 6))
KUBUS_TAMBAH = (2, 3, 4, 5)
NAMA_ANAK = "Dita"

BIDANG = {
    "luas_petak": ("baris", "kolom"),
    "luas_bandingkan": ("baris_a", "kolom_a", "baris_b", "kolom_b"),
    "volume_kubus_satuan": ("lapis", "baris", "kolom"),
    "tambah_kubus": ("lapis", "baris", "kolom", "tambah"),
}


# ── domain eksplisit ─────────────────────────────────────────────────────

def _domain_varian(varian: str) -> list:
    if varian == "luas_petak":
        return [{"baris": b, "kolom": k} for b in SISI_LUAS for k in SISI_LUAS if b != k]
    if varian == "luas_bandingkan":
        return [{"baris_a": ba, "kolom_a": ka, "baris_b": bb, "kolom_b": kb}
                for ba in SISI_A for ka in SISI_A for bb in SISI_B for kb in SISI_B
                if ba * ka > bb * kb]
    if varian == "volume_kubus_satuan":
        return [{"lapis": le, "baris": b, "kolom": k} for le in LAPIS_BARIS_VOLUME
                for b in LAPIS_BARIS_VOLUME for k in KOLOM_VOLUME]
    return [{"lapis": le, "baris": b, "kolom": k, "tambah": t} for le in LAPIS_BARIS_TAMBAH
            for b in LAPIS_BARIS_TAMBAH for k in KOLOM_TAMBAH for t in KUBUS_TAMBAH]


def _enumerasi() -> tuple:
    return tuple({"varian": varian, **isian} for varian in VARIAN
                 for isian in _domain_varian(varian))


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


@lru_cache(maxsize=None)
def _himpunan_sah() -> frozenset:
    return frozenset(tuple(sorted(item)) for item in _domain_beku())


def _sah(varian, isian: dict) -> bool:
    if type(varian) is not str or varian not in BIDANG:
        return False
    if set(isian) != set(BIDANG[varian]):
        return False
    if not all(type(nilai) is int for nilai in isian.values()):
        return False
    return tuple(sorted({"varian": varian, **isian}.items())) in _himpunan_sah()


# ── kunci, teks, pembahasan ──────────────────────────────────────────────

def _luas(baris: int, kolom: int) -> int:
    return baris * kolom


def _volume(p: dict) -> int:
    return p["lapis"] * p["baris"] * p["kolom"]


def _kunci(varian: str, p: dict) -> int:
    if varian == "luas_petak":
        return _luas(p["baris"], p["kolom"])
    if varian == "luas_bandingkan":
        return _luas(p["baris_a"], p["kolom_a"]) - _luas(p["baris_b"], p["kolom_b"])
    if varian == "volume_kubus_satuan":
        return _volume(p)
    return _volume(p) + p["tambah"]


def _teks_balok(p: dict) -> str:
    return (f"{p['lapis']} lapis, tiap lapis {p['baris']} baris dan tiap baris "
            f"{p['kolom']} kubus")


def _teks(varian: str, p: dict) -> str:
    if varian == "luas_petak":
        return (f"Sebuah persegi panjang tersusun dari {p['baris']} baris petak satuan, "
                f"tiap baris {p['kolom']} petak. Luasnya ... petak satuan.")
    if varian == "luas_bandingkan":
        return (f"Persegi panjang A tersusun dari {p['baris_a']} baris petak satuan, tiap baris "
                f"{p['kolom_a']} petak. Persegi panjang B tersusun dari {p['baris_b']} baris "
                f"petak satuan, tiap baris {p['kolom_b']} petak. Luas A lebih besar ... petak "
                "satuan daripada luas B.")
    if varian == "volume_kubus_satuan":
        return f"Sebuah balok tersusun dari kubus satuan: {_teks_balok(p)}. Volumenya ... kubus satuan."
    return (f"{NAMA_ANAK} menyusun sebuah balok dari kubus satuan: {_teks_balok(p)}. Kemudian "
            f"{NAMA_ANAK} menambahkan {p['tambah']} kubus satuan pada balok itu. Volume benda "
            "sekarang ... kubus satuan.")


def _pembahasan_volume(p: dict, kunci: int) -> str:
    lapisan = p["baris"] * p["kolom"]
    awal = _volume(p)
    dasar = (f"Satu lapis berisi {p['baris']} × {p['kolom']} = {lapisan} kubus. "
             f"Ada {p['lapis']} lapis, jadi {p['lapis']} × {lapisan} = {awal} kubus satuan.")
    if "tambah" not in p:
        return dasar
    return (f"{dasar} Ditambah {p['tambah']} kubus satuan lagi: {awal} + {p['tambah']} = "
            f"{kunci} kubus satuan.")


def _pembahasan(varian: str, p: dict, kunci: int) -> str:
    if varian == "luas_petak":
        return (f"Luas persegi panjang sama dengan banyak petak satuannya. Ada {p['baris']} baris "
                f"dan tiap baris {p['kolom']} petak, jadi {p['baris']} × {p['kolom']} = "
                f"{kunci} petak satuan.")
    if varian == "luas_bandingkan":
        luas_a = _luas(p["baris_a"], p["kolom_a"])
        luas_b = _luas(p["baris_b"], p["kolom_b"])
        return (f"Luas A = {p['baris_a']} × {p['kolom_a']} = {luas_a} petak satuan. "
                f"Luas B = {p['baris_b']} × {p['kolom_b']} = {luas_b} petak satuan. "
                f"Selisihnya {luas_a} − {luas_b} = {kunci} petak satuan.")
    return _pembahasan_volume(p, kunci)


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _kandidat_luas_petak(p: dict) -> list:
    b, k = p["baris"], p["kolom"]
    benar = b * k
    return [
        _mal("dijumlah_bukan_dikali", b + k, "K",
             f"Menjumlah {b} dan {k} sehingga jawabannya {b + k}; kemungkinan belum paham "
             "bahwa luas diperoleh dengan mengalikan."),
        _mal("hanya_banyak_baris", b, "K",
             f"Menjawab banyak baris saja ({b}); kemungkinan melewatkan banyak petak tiap baris."),
        _mal("hanya_petak_satu_baris", k, "K",
             f"Menjawab petak dalam satu baris saja ({k}); kemungkinan melewatkan banyak baris."),
        _mal("menghitung_keliling", 2 * (b + k), "K",
             f"Menghitung 2 × ({b} + {k}) = {2 * (b + k)}; kemungkinan mengira luas sama "
             "dengan petak di sepanjang tepi."),
        _mal("kurang_satu", benar - 1, "H",
             f"Sudah mengalikan, tetapi salah hitung kurang satu sehingga jawabannya {benar - 1}."),
        _mal("lebih_satu", benar + 1, "H",
             f"Sudah mengalikan, tetapi salah hitung lebih satu sehingga jawabannya {benar + 1}."),
    ]


def _kandidat_luas_bandingkan(p: dict) -> list:
    ba, ka, bb, kb = p["baris_a"], p["kolom_a"], p["baris_b"], p["kolom_b"]
    luas_a, luas_b = ba * ka, bb * kb
    return [
        _mal("luas_dijumlah", luas_a + luas_b, "K",
             f"Menjumlah kedua luas ({luas_a} + {luas_b}) sehingga jawabannya {luas_a + luas_b}; "
             "kemungkinan salah memilih operasi untuk mencari selisih."),
        _mal("hanya_luas_a", luas_a, "K",
             f"Menjawab luas A saja ({luas_a}); kemungkinan luas B tidak ikut dikurangkan."),
        _mal("selisih_dijumlah_bukan_dikali", (ba + ka) - (bb + kb), "K",
             f"Menjumlah baris dan petak tiap bangun lalu mengurangkan ({ba + ka} − {bb + kb}); "
             "kemungkinan belum paham bahwa luas diperoleh dengan mengalikan."),
        _mal("baris_kolom_dikurangi_dulu", (ba - bb) * (ka - kb), "K",
             f"Mengurangkan banyak baris dan petak tiap baris lebih dulu lalu mengalikannya "
             f"({ba - bb} × {ka - kb}); kemungkinan mengira selisih luas sama dengan luas selisih."),
    ]


def _kandidat_volume_kubus_satuan(p: dict) -> list:
    le, b, k = p["lapis"], p["baris"], p["kolom"]
    benar = le * b * k
    return [
        _mal("dijumlah_bukan_dikali", le + b + k, "K",
             f"Menjumlah {le}, {b}, dan {k} sehingga jawabannya {le + b + k}; kemungkinan "
             "belum paham bahwa volume diperoleh dengan mengalikan."),
        _mal("tanpa_faktor_lapis", b * k, "K",
             f"Hanya mengalikan {b} × {k} = {b * k}; kemungkinan hanya menghitung satu lapis "
             "dan lupa mengalikan dengan banyak lapis."),
        _mal("tanpa_faktor_kolom", le * b, "K",
             f"Hanya mengalikan {le} × {b} = {le * b}; kemungkinan melewatkan banyak kubus "
             "tiap baris."),
        _mal("tanpa_faktor_baris", le * k, "K",
             f"Hanya mengalikan {le} × {k} = {le * k}; kemungkinan melewatkan banyak baris "
             "tiap lapis."),
        _mal("kurang_satu", benar - 1, "H",
             f"Sudah mengalikan, tetapi salah hitung kurang satu sehingga jawabannya {benar - 1}."),
        _mal("lebih_satu", benar + 1, "H",
             f"Sudah mengalikan, tetapi salah hitung lebih satu sehingga jawabannya {benar + 1}."),
    ]


def _kandidat_tambah_kubus(p: dict) -> list:
    le, b, k, t = p["lapis"], p["baris"], p["kolom"], p["tambah"]
    awal = le * b * k
    return [
        _mal("semua_dijumlah", le + b + k + t, "K",
             f"Menjumlah semua angka ({le} + {b} + {k} + {t}) sehingga jawabannya "
             f"{le + b + k + t}; kemungkinan belum paham bahwa volume diperoleh dengan "
             "mengalikan."),
        _mal("semua_dikali", le * b * k * t, "K",
             f"Mengalikan semua angka termasuk {t} sehingga jawabannya {le * b * k * t}; "
             "kemungkinan mengira kubus yang ditambahkan juga dikalikan."),
        _mal("tanpa_faktor_lapis_ditambah", b * k + t, "K",
             f"Menghitung {b} × {k} + {t} = {b * k + t}; kemungkinan lupa mengalikan dengan "
             "banyak lapis."),
        _mal("lupa_menambah", awal, "H",
             f"Sudah menghitung volume balok ({awal}), tetapi lupa menambah {t} kubus."),
        _mal("dikurangi_bukan_ditambah", awal - t, "H",
             f"Sudah menghitung volume balok ({awal}), tetapi mengurangi {t}, bukan menambah."),
    ]


_KANDIDAT = {
    "luas_petak": _kandidat_luas_petak,
    "luas_bandingkan": _kandidat_luas_bandingkan,
    "volume_kubus_satuan": _kandidat_volume_kubus_satuan,
    "tambah_kubus": _kandidat_tambah_kubus,
}


def _saring(kunci: int, kandidat: list) -> tuple:
    """Buang jawaban tak positif (bukan pengecoh yang wajar), lalu saring yang kembar atau sama kunci."""
    positif = [m for m in kandidat if int(m.jawaban) > 0]
    return saring_malrule(str(kunci), positif)


def luas_petak_volume_kubus(varian: str, baris: int | None = None, kolom: int | None = None,
                            lapis: int | None = None, tambah: int | None = None,
                            baris_a: int | None = None, kolom_a: int | None = None,
                            baris_b: int | None = None, kolom_b: int | None = None) -> Soal:
    """Luas dengan petak satuan atau volume dengan kubus satuan (kunci dari parameter)."""
    isian = {nama: nilai for nama, nilai in (
        ("baris", baris), ("kolom", kolom), ("lapis", lapis), ("tambah", tambah),
        ("baris_a", baris_a), ("kolom_a", kolom_a), ("baris_b", baris_b),
        ("kolom_b", kolom_b)) if nilai is not None}
    if not _sah(varian, isian):
        raise ValueError(PESAN_LUAR_DOMAIN)
    kunci = _kunci(varian, isian)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isian},
        teks=_teks(varian, isian), kunci=str(kunci),
        malrule=_saring(kunci, _KANDIDAT[varian](isian)),
        pembahasan=_pembahasan(varian, isian, kunci), bagian="A")


# ── sampler ──────────────────────────────────────────────────────────────

def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level luas petak volume kubus harus P4")


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
