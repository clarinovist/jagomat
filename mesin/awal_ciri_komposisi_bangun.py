"""Matematika Awal, jenis `ciri_komposisi_bangun`: ciri, penyusunan, dan penguraian bangun datar (P4), teks saja.

Bab K4 B5 "Bangun datar" (Ciri-ciri bangun datar; Menyusun dan mengurai bangun datar).
Enam bentuk soal (`varian`):
  - `ciri`: banyak sisi, banyak sudut, pasang sisi sejajar, sudut siku-siku, atau banyak
    sisi yang sama panjang pada satu bangun (kunci angka bulat);
  - `dua_persegi`: dua persegi sama besar dirapatkan pada satu sisi penuh; ditanya nama
    bangunnya (kunci nama, pilihan tertutup di soal) atau sisi terpanjangnya (kunci angka);
  - `susun_persegi`: persegi kecil disusun jadi persegi panjang b baris x k kolom,
    ditanya banyak persegi kecil (kunci angka);
  - `susun_gabung`: dua kelompok persegi kecil (b1 x k1 dan b2 x k2), ditanya jumlahnya;
  - `uraikan_banyak`: segiempat dipotong menurut salah satu / kedua diagonalnya, ditanya
    banyak bagian (2 atau 4);
  - `uraikan_nama`: persegi panjang p x l (p > l) dipotong menurut satu diagonal, ditanya
    nama bagiannya (kunci nama, pilihan tertutup di soal).

DAFTAR FAKTA (definisi umum buku siswa Matematika SD Kelas IV; MOHON DIULAS MUTIA
sebelum rilis; hanya fakta yang tak diperdebatkan yang dipakai):
  banyak sisi / sudut : persegi 4, persegi panjang 4, segitiga 3, jajar genjang 4,
                        belah ketupat 4, layang-layang 4.
  pasang sisi sejajar : persegi 2, persegi panjang 2, jajar genjang 2, belah ketupat 2,
                        layang-layang (yang bukan belah ketupat) 0, segitiga 0.
  sudut siku-siku     : persegi 4, persegi panjang 4, segitiga siku-siku 1, segitiga
                        sama sisi 0.
  sisi sama panjang   : persegi 4, belah ketupat 4, segitiga sama sisi 3.
  komposisi/uraian    : dua persegi sama besar rapat satu sisi penuh = persegi panjang
                        2s x s (bukan persegi); satu diagonal membagi segiempat cembung
                        (persegi panjang, persegi, jajar genjang, belah ketupat) menjadi
                        2 segitiga, kedua diagonal menjadi 4 segitiga; persegi panjang
                        p x l dengan p > l dipotong satu diagonal menjadi dua segitiga
                        siku-siku yang sama persis.
Istilah "sejajar" didefinisikan di pembahasan (belum pasti sudah dipakai buku Kelas IV);
Mutia diminta memastikan istilah itu dan "diagonal" sudah dikenal di kelas ini.

Sengaja TIDAK dipakai:
  - dua segitiga siku-siku yang sama persis ditempel pada sisi miringnya: hasilnya persegi
    panjang (satu diputar 180 derajat) ATAU layang-layang (satu dicerminkan); jajar genjang
    baru muncul bila ditempel pada sisi siku-sikunya. Teks tanpa gambar tak bisa memilih
    satu tanpa menguraikan arah tempel. Versi sama kaki (hasil selalu persegi) sah secara
    geometri tetapi nama persegi bertabrakan dengan "persegi panjang" pada definisi
    inklusif, jadi dilepas.
  - sudut siku jajar genjang / belah ketupat / layang-layang / segitiga umum (bergantung
    bentuk); sisi sama panjang persegi panjang (dua pasang, ambigu); trapesium; lingkaran;
    layang-layang cekung; pemotongan layang-layang menurut diagonal.

Kualifikasi nama: soal sisi sejajar menulis "layang-layang yang bukan belah ketupat"
(belah ketupat juga layang-layang pada definisi inklusif, dan punya 2 pasang). Kunci
nama hanya ditanyakan dengan pilihan tertutup yang jawaban lainnya pasti salah, baik
di definisi inklusif maupun eksklusif: dua persegi rapat -> "persegi panjang" di antara
persegi, persegi panjang, belah ketupat ("jajar genjang" sengaja tak dipilihkan karena
juga benar pada definisi inklusif); diagonal persegi panjang -> "segitiga siku-siku" di
antara segitiga siku-siku, segitiga sama sisi, persegi. Kunci nama ditulis huruf kecil
dan dibandingkan lewat `diagnosis.normalisasi`.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari
satu jawaban: nilai bangun lain yang tertukar, banyak sisi/sudut/diagonal/pasang yang
disebut sebagai ciri yang ditanya, menjumlah alih-alih mengalikan, menghitung satu
kelompok saja (semuanya K), serta salah hitung lebih/kurang satu (H, hanya bila nyata
berbeda dari kunci). Jalur K selalu ada; minimal dua pengecoh berbeda nilai per parameter.

Domain eksplisit (`domain_parameter`): sampler memilih `varian` seragam dulu, lalu
kelompok (ciri / tanya / jenis potongan) seragam dalam varian itu, lalu satu parameter
seragam; hanya dari `rng` (tanpa `hash()`). Nama anak pada soal susunan diturunkan dari
parameter angka (jumlahnya mod 4), jadi identitas soal tetap ditentukan parameter.
Daftar nama bangun pada FAKTA APPEND-ONLY (nama bangun, bukan indeks, jadi parameter).
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "ciri_komposisi_bangun"
LEVEL = ("P4",)
VARIAN = ("ciri", "dua_persegi", "susun_persegi", "susun_gabung", "uraikan_banyak",
          "uraikan_nama")
PESAN_LUAR_DOMAIN = "parameter ciri komposisi bangun di luar domain"
CIRI = ("banyak_sisi", "banyak_sudut", "pasang_sejajar", "sudut_siku", "sisi_sama")
_SEGIEMPAT = ("persegi", "persegi panjang", "jajar genjang", "belah ketupat", "layang-layang")
FAKTA = {
    "banyak_sisi": tuple((b, 3 if b == "segitiga" else 4) for b in
                         ("persegi", "persegi panjang", "segitiga", "jajar genjang",
                          "belah ketupat", "layang-layang")),
    "pasang_sejajar": (("persegi", 2), ("persegi panjang", 2), ("jajar genjang", 2),
                       ("belah ketupat", 2), ("layang-layang", 0), ("segitiga", 0)),
    "sudut_siku": (("persegi", 4), ("persegi panjang", 4), ("segitiga siku-siku", 1),
                   ("segitiga sama sisi", 0)),
    "sisi_sama": (("persegi", 4), ("belah ketupat", 4), ("segitiga sama sisi", 3)),
}
FAKTA["banyak_sudut"] = FAKTA["banyak_sisi"]
NAMA_ANAK = ("Rina", "Budi", "Dita", "Eko")  # dipilih dari parameter, urutan APPEND-ONLY
SISI_PERSEGI = tuple(range(2, 10))
BARIS_SUSUN = tuple(range(2, 7))
KOLOM_SUSUN = tuple(range(3, 9))
KELOMPOK_1 = tuple(range(2, 6))
KELOMPOK_2 = tuple(range(2, 5))
SEGIEMPAT_CEMBUNG = ("persegi panjang", "persegi", "jajar genjang", "belah ketupat")
PANJANG_POTONG = tuple(range(6, 11))
LEBAR_POTONG = tuple(range(3, 6))
KETERANGAN_DIAGONAL = "(diagonal: garis lurus dari satu sudut ke sudut yang berhadapan)"

PENGANTAR = {
    "banyak_sisi": "Sisi adalah garis lurus yang membatasi bangun.",
    "banyak_sudut": "Sudut adalah pojok tempat dua sisi bertemu.",
    "pasang_sejajar": "Sisi sejajar adalah dua sisi yang tidak akan bertemu walau "
                      "diperpanjang sejauh apa pun.",
    "sudut_siku": "Sudut siku-siku adalah sudut seperti pojok kertas, besarnya 90 derajat.",
    "sisi_sama": "Dua sisi sama panjang kalau diukur hasilnya sama.",
}
ALASAN_SEJAJAR = {
    "persegi": "sisi atas dengan sisi bawah, dan sisi kiri dengan sisi kanan",
    "persegi panjang": "sisi atas dengan sisi bawah, dan sisi kiri dengan sisi kanan",
    "jajar genjang": "sisi atas dengan sisi bawah, dan dua sisi miringnya yang berhadapan",
    "belah ketupat": "tiap sisi sejajar dengan sisi di seberangnya",
    "layang-layang": "tidak ada sisi yang sejajar, sebab dua sisi pendeknya bertemu di satu "
                     "sudut dan dua sisi panjangnya bertemu di sudut lain",
    "segitiga": "tidak ada dua sisi yang berhadapan, sebab ketiga sisinya saling bertemu "
                "di sudut",
}
ALASAN_SIKU = {
    "persegi": "keempat sudutnya siku-siku",
    "persegi panjang": "keempat sudutnya siku-siku",
    "segitiga siku-siku": "hanya satu sudutnya yang siku-siku, dua sudut lainnya lebih kecil",
    "segitiga sama sisi": "ketiga sudutnya sama besar dan lebih kecil dari sudut siku-siku",
}
ALASAN_SAMA = {
    "persegi": "keempat sisinya sama panjang",
    "belah ketupat": "keempat sisinya sama panjang",
    "segitiga sama sisi": "ketiga sisinya sama panjang",
}
_BENTUK_FAKTA = {"banyak_sisi": "sisi", "banyak_sudut": "sudut",
                 "pasang_sejajar": "pasang sisi sejajar", "sudut_siku": "sudut siku-siku",
                 "sisi_sama": "sisi yang sama panjang"}


def _kapital(teks: str) -> str:
    return teks[0].upper() + teks[1:]


def _nilai(ciri: str, bangun: str) -> int:
    return dict(FAKTA[ciri])[bangun]


def _nama_dalam_soal(ciri: str, bangun: str) -> str:
    if ciri == "pasang_sejajar" and bangun == "layang-layang":
        return "layang-layang yang bukan belah ketupat"
    return bangun


def _nama_anak(angka: int) -> str:
    return NAMA_ANAK[angka % len(NAMA_ANAK)]


# ── domain eksplisit dan validasi ────────────────────────────────────────

def _enumerasi() -> tuple:
    hasil = []
    for ciri in CIRI:
        hasil += [{"varian": "ciri", "ciri": ciri, "bangun": b} for b, _ in FAKTA[ciri]]
    hasil += [{"varian": "dua_persegi", "tanya": t, "sisi": s}
              for t in ("nama", "panjang") for s in SISI_PERSEGI]
    hasil += [{"varian": "susun_persegi", "baris": b, "kolom": k}
              for b in BARIS_SUSUN for k in KOLOM_SUSUN if b != k]
    hasil += [{"varian": "susun_gabung", "baris1": b1, "kolom1": k1, "baris2": b2,
               "kolom2": k2}
              for b1 in KELOMPOK_1 for k1 in KELOMPOK_1
              for b2 in KELOMPOK_2 for k2 in KELOMPOK_2]
    hasil += [{"varian": "uraikan_banyak", "bangun": b, "potong": p}
              for b in SEGIEMPAT_CEMBUNG for p in ("satu", "dua")]
    hasil += [{"varian": "uraikan_nama", "panjang": p, "lebar": l}
              for p in PANJANG_POTONG for l in LEBAR_POTONG]
    return tuple(hasil)


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _kanon(p: dict) -> tuple:
    return tuple(sorted(p.items()))


@lru_cache(maxsize=None)
def _himpunan_sah() -> frozenset:
    return frozenset(_kanon(dict(item)) for item in _domain_beku())


def _tipe_polos(p: dict) -> bool:
    """Hanya int/str murni: 3.0 dan True sama-hash dengan 3 sehingga harus ditolak lebih dulu."""
    return all(type(v) in (int, str) for v in p.values())


def _sah(p: dict) -> bool:
    return _tipe_polos(p) and _kanon(p) in _himpunan_sah()


def _kunci_kelompok(p: dict) -> str:
    return p.get("ciri") or p.get("tanya") or p.get("potong") or ""


@lru_cache(maxsize=None)
def _peta_varian() -> tuple:
    """((varian, (kelompok, ...)), ...); kelompok = tuple item parameter."""
    hasil = []
    for varian in VARIAN:
        kelompok = {}
        for item in _domain_beku():
            if item[0][1] == varian:
                kelompok.setdefault(_kunci_kelompok(dict(item)), []).append(item)
        hasil.append((varian, tuple(tuple(v) for v in kelompok.values())))
    return tuple(hasil)


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level ciri komposisi bangun harus P4")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku())


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu kelompok seragam, lalu satu parameter seragam; hanya dari rng."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    kelompok = dict(_peta_varian())[varian]
    return dict(rng.choice(rng.choice(kelompok)))


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _h_satu(unit: str, v: int) -> list:
    return [
        _mal(f"{_slug(unit)}_berlebih", v + 1, "H",
             f"Sudah mengerti caranya, tetapi satu {unit} terhitung dua kali sehingga "
             f"jawabannya {v + 1}."),
        *([_mal(f"{_slug(unit)}_terlewat", v - 1, "H",
                f"Sudah mengerti caranya, tetapi satu {unit} terlewat sehingga "
                f"jawabannya {v - 1}.")] if v >= 1 else []),
    ]


def _slug(teks: str) -> str:
    return teks.replace(" ", "_").replace("-", "_")


def _kandidat_hitung(unit: str, v: int) -> list:
    lain, nama_lain = (3, "segitiga") if v == 4 else (4, "segiempat")
    kandidat = [_mal("bangun_lain", lain, "K",
                     f"Menyebut banyak {unit} {nama_lain} ({lain}), kemungkinan tertukar "
                     "dengan bangun lain.")]
    if v == 4:
        kandidat.append(_mal("pasangan_bukan_satuan", 2, "K",
                             f"Menyebut banyak pasang {unit} yang berhadapan (2), bukan "
                             f"banyak {unit}."))
    kandidat.append(_mal("sisi_dan_sudut_dijumlah", 2 * v, "K",
                         f"Menjumlah banyak sisi dan banyak sudut ({2 * v}) padahal yang "
                         f"ditanya hanya banyak {unit}."))
    return kandidat + _h_satu(unit, v)


def _kandidat_sejajar(bangun: str, v: int) -> list:
    if bangun == "segitiga":
        return [
            _mal("sisi_disebut", 3, "K", "Menyebut banyak sisi (3), bukan banyak pasang "
                                         "sisi sejajar."),
            _mal("dua_sisi_bertemu_dikira_sejajar", 1, "K",
                 "Mengira dua sisi yang bertemu di satu sudut adalah sepasang sisi "
                 "sejajar (1)."),
            _mal("tertukar_segiempat", 2, "K",
                 "Menyebut banyak pasang sisi sejajar segiempat (2), kemungkinan "
                 "tertukar dengan segiempat."),
        ]
    if bangun == "layang-layang":
        return [
            _mal("dikira_seperti_jajar_genjang", 2, "K",
                 "Mengira layang-layang punya dua pasang sisi sejajar seperti jajar "
                 "genjang (2)."),
            _mal("sisi_disebut", 4, "K", "Menyebut banyak sisi (4), bukan banyak pasang "
                                         "sisi sejajar."),
            _mal("dikira_satu_pasang", 1, "K",
                 "Mengira ada sepasang sisi berhadapan yang sejajar (1)."),
        ]
    kandidat = [_mal("sisi_sejajar_bukan_pasangan", 4, "K",
                     "Menghitung sisi yang sejajar satu per satu (4), bukan pasangannya.")]
    if bangun in ("jajar genjang", "belah ketupat"):
        kandidat.append(_mal("miring_dikira_tidak_sejajar", 1, "K",
                             "Mengira sisi yang miring tidak sejajar sehingga hanya satu "
                             "pasang (1)."))
    else:
        kandidat.append(_mal("satu_pasang_terlewat", 1, "H",
                             "Sudah mengerti caranya, tetapi satu pasang terlewat "
                             "sehingga jawabannya 1."))
    kandidat.append(_mal("satu_pasang_berlebih", v + 1, "H",
                         f"Sudah mengerti caranya, tetapi satu pasang terhitung dua kali "
                         f"sehingga jawabannya {v + 1}."))
    return kandidat


def _kandidat_siku(bangun: str, v: int) -> list:
    if bangun == "segitiga sama sisi":
        return [
            _mal("ketiga_dikira_siku", 3, "K", "Mengira ketiga sudutnya siku-siku (3)."),
            _mal("tertukar_persegi", 4, "K",
                 "Menyebut banyak sudut siku-siku persegi (4), kemungkinan tertukar."),
            _mal("dikira_seperti_segitiga_siku", 1, "K",
                 "Mengira ada satu sudut siku-siku seperti pada segitiga siku-siku (1)."),
        ]
    if bangun == "segitiga siku-siku":
        return [
            _mal("sudut_disebut", 3, "K",
                 "Menyebut banyak sudut (3), bukan banyak sudut siku-siku."),
            _mal("tertukar_persegi", 4, "K",
                 "Menyebut banyak sudut siku-siku persegi (4), kemungkinan tertukar."),
            _mal("sudut_lancip_disebut", 2, "K",
                 "Menyebut banyak sudut lancip (2), bukan sudut siku-siku."),
            *_h_satu("sudut", v),
        ]
    return [
        _mal("pasang_sisi_disebut", 2, "K",
             "Menyebut banyak pasang sisi yang berhadapan (2), bukan banyak sudut "
             "siku-siku."),
        _mal("sudut_segitiga_disebut", 3, "K",
             "Menyebut banyak sudut segitiga (3), kemungkinan tertukar dengan segitiga."),
        _mal("sisi_dan_sudut_dijumlah", 8, "K",
             "Menjumlah banyak sisi dan banyak sudut (8) padahal yang ditanya hanya "
             "banyak sudut siku-siku."),
        *_h_satu("sudut", v),
    ]


def _kandidat_sisi_sama(bangun: str, v: int) -> list:
    if bangun == "segitiga sama sisi":
        return [
            _mal("tertukar_segiempat", 4, "K",
                 "Menyebut banyak sisi segiempat (4), kemungkinan tertukar dengan "
                 "segiempat."),
            _mal("dikira_dua_sisi_sama", 2, "K",
                 "Mengira hanya dua sisi yang sama panjang seperti pada segitiga sama "
                 "kaki (2)."),
            _mal("sisi_dan_sudut_dijumlah", 6, "K",
                 "Menjumlah banyak sisi dan banyak sudut (6) padahal yang ditanya hanya "
                 "banyak sisi yang sama panjang."),
        ]
    return [
        _mal("tertukar_segitiga", 3, "K",
             "Menyebut banyak sisi segitiga sama sisi (3), kemungkinan tertukar."),
        _mal("hanya_yang_berhadapan_sama", 2, "K",
             "Mengira hanya sisi yang berhadapan yang sama panjang (2)."),
        _mal("sisi_dan_sudut_dijumlah", 8, "K",
             "Menjumlah banyak sisi dan banyak sudut (8) padahal yang ditanya hanya "
             "banyak sisi yang sama panjang."),
        *_h_satu("sisi", v),
    ]


def _kandidat_ciri(ciri: str, bangun: str, v: int) -> list:
    if ciri in ("banyak_sisi", "banyak_sudut"):
        return _kandidat_hitung(_BENTUK_FAKTA[ciri], v)
    if ciri == "pasang_sejajar":
        return _kandidat_sejajar(bangun, v)
    if ciri == "sudut_siku":
        return _kandidat_siku(bangun, v)
    return _kandidat_sisi_sama(bangun, v)


def _kandidat_dua_persegi(p: dict) -> list:
    s, kunci = p["sisi"], 2 * p["sisi"]
    if p["tanya"] == "nama":
        return [
            _mal("tetap_persegi", "persegi", "K",
                 "Mengira bangunnya tetap persegi karena asalnya dua persegi."),
            _mal("dikira_miring", "belah ketupat", "K",
                 "Mengira bangun yang terbentuk menjadi miring seperti belah ketupat."),
        ]
    return [
        _mal("sisi_satu_persegi", s, "K",
             f"Menyebut panjang sisi satu persegi ({s}), belum menggabungkan dua persegi."),
        _mal("panjang_dan_lebar_dijumlah", 3 * s, "K",
             f"Menjumlah panjang dan lebar ({3 * s}) padahal yang ditanya sisi terpanjang."),
        _mal("keliling_disebut", 6 * s, "K",
             f"Menyebut keliling bangun ({6 * s}), bukan sisi terpanjang."),
        _mal("luas_disebut", 2 * s * s, "K",
             f"Menyebut luas bangun ({2 * s * s}), bukan sisi terpanjang."),
        _mal("lebih_satu", kunci + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga "
             f"jawabannya {kunci + 1}."),
        _mal("kurang_satu", kunci - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga "
             f"jawabannya {kunci - 1}."),
    ]


def _kandidat_susun_persegi(p: dict, kunci: int) -> list:
    b, k = p["baris"], p["kolom"]
    return [
        _mal("baris_kolom_dijumlah", b + k, "K",
             f"Menjumlah banyak baris dan kolom ({b + k}), bukan mengalikannya."),
        _mal("hanya_pinggir_dihitung", 2 * (b + k) - 4, "K",
             f"Menghitung persegi kecil di pinggir saja ({2 * (b + k) - 4})."),
        _mal("satu_baris_terlewat", kunci - k, "H",
             f"Sudah mengerti caranya, tetapi satu baris terlewat sehingga jawabannya "
             f"{kunci - k}."),
        _mal("satu_baris_berlebih", kunci + k, "H",
             f"Sudah mengerti caranya, tetapi satu baris terhitung dua kali sehingga "
             f"jawabannya {kunci + k}."),
    ]


def _kandidat_susun_gabung(p: dict, kunci: int) -> list:
    b1, k1, b2, k2 = p["baris1"], p["kolom1"], p["baris2"], p["kolom2"]
    pertama, kedua = b1 * k1, b2 * k2
    return [
        _mal("hanya_kelompok_pertama", pertama, "K",
             f"Hanya menghitung kelompok pertama ({pertama}) dan lupa kelompok kedua."),
        _mal("hanya_kelompok_kedua", kedua, "K",
             f"Hanya menghitung kelompok kedua ({kedua}) dan lupa kelompok pertama."),
        _mal("semua_angka_dikali", pertama * kedua, "K",
             f"Mengalikan hasil kedua kelompok ({pertama * kedua}), bukan menjumlahkannya."),
        _mal("semua_angka_dijumlah", b1 + k1 + b2 + k2, "K",
             f"Menjumlah keempat bilangan yang tertulis ({b1 + k1 + b2 + k2}) tanpa "
             "mengalikan baris dengan kolom."),
        _mal("satu_baris_terlewat", kunci - k1, "H",
             f"Sudah mengerti caranya, tetapi satu baris kelompok pertama terlewat "
             f"sehingga jawabannya {kunci - k1}."),
        _mal("satu_baris_berlebih", kunci + k2, "H",
             f"Sudah mengerti caranya, tetapi satu baris kelompok kedua terhitung dua "
             f"kali sehingga jawabannya {kunci + k2}."),
    ]


def _kandidat_uraikan_banyak(p: dict, kunci: int) -> list:
    if p["potong"] == "satu":
        return [
            _mal("banyak_sisi_disebut", 4, "K",
                 "Menyebut banyak sisi atau sudut bangun (4), bukan banyak bagian."),
            _mal("garis_potong_disebut", 1, "K",
                 "Menyebut banyak garis potong (1), bukan banyak bagian."),
            _mal("satu_bagian_berlebih", 3, "H",
                 "Sudah mengerti caranya, tetapi satu bagian terhitung dua kali sehingga "
                 "jawabannya 3."),
        ]
    return [
        _mal("banyak_diagonal_disebut", 2, "K",
             "Menyebut banyak diagonal (2), bukan banyak bagian."),
        _mal("dibagi_dua_lagi", 8, "K",
             "Mengira tiap bagian dibagi dua lagi oleh diagonal kedua (8)."),
        _mal("satu_bagian_terlewat", 3, "H",
             "Sudah mengerti caranya, tetapi satu bagian terlewat sehingga jawabannya 3."),
        _mal("satu_bagian_berlebih", 5, "H",
             "Sudah mengerti caranya, tetapi satu bagian terhitung dua kali sehingga "
             "jawabannya 5."),
    ]


def _kandidat_uraikan_nama() -> list:
    return [
        _mal("semua_segitiga_sama_sisi", "segitiga sama sisi", "K",
             "Mengira semua segitiga berbentuk segitiga sama sisi."),
        _mal("bentuk_tak_berubah", "persegi", "K",
             "Mengira bagian yang terbentuk tetap persegi atau persegi panjang, belum "
             "melihat bahwa dipotong menurut diagonal menghasilkan segitiga."),
    ]


# ── kunci, teks, pembahasan per varian ───────────────────────────────────

def _ciri(p: dict) -> tuple:
    ciri, bangun = p["ciri"], p["bangun"]
    v = _nilai(ciri, bangun)
    nama = _nama_dalam_soal(ciri, bangun)
    if ciri == "banyak_sisi":
        teks = f"Berapa banyak sisi {nama}?"
        alasan = ""
    elif ciri == "banyak_sudut":
        teks = f"Berapa banyak sudut {nama}?"
        alasan = ""
    elif ciri == "pasang_sejajar":
        teks = f"Berapa pasang sisi sejajar yang dimiliki {nama}?"
        alasan = f": {ALASAN_SEJAJAR[bangun]}"
    elif ciri == "sudut_siku":
        teks = f"Berapa banyak sudut siku-siku yang dimiliki {nama}?"
        alasan = f": {ALASAN_SIKU[bangun]}"
    else:
        teks = f"Berapa banyak sisi yang sama panjang pada {nama}?"
        alasan = f": {ALASAN_SAMA[bangun]}"
    pembahasan = (f"{PENGANTAR[ciri]} {_kapital(nama)} punya {v} {_BENTUK_FAKTA[ciri]}"
                  f"{alasan}. Jadi jawabannya {v}.")
    return teks, str(v), pembahasan, _kandidat_ciri(ciri, bangun, v)


def _dua_persegi(p: dict) -> tuple:
    s = p["sisi"]
    awal = (f"Dua persegi yang sama besar, masing-masing bersisi {s} cm, dirapatkan pada "
            "satu sisi penuh tanpa saling menumpuk")
    ukuran = (f"Panjangnya jadi {s} + {s} = {2 * s} cm dan lebarnya tetap {s} cm.")
    if p["tanya"] == "nama":
        teks = (f"{awal}. Bangun apa yang terbentuk? Pilih: persegi, persegi panjang, "
                "atau belah ketupat.")
        pembahasan = (f"Dua persegi dirapatkan pada satu sisi penuh. {ukuran} Karena "
                      "panjang dan lebarnya berbeda, bangunnya persegi panjang. Jadi "
                      "jawabannya persegi panjang.")
        return teks, "persegi panjang", pembahasan, _kandidat_dua_persegi(p)
    teks = (f"{awal} sehingga membentuk sebuah persegi panjang. Berapa cm panjang sisi "
            "terpanjang bangun itu?")
    pembahasan = (f"Dua persegi dirapatkan pada satu sisi penuh. {ukuran} Sisi terpanjang "
                  f"adalah {2 * s} cm. Jadi jawabannya {2 * s}.")
    return teks, str(2 * s), pembahasan, _kandidat_dua_persegi(p)


def _susun_persegi(p: dict) -> tuple:
    b, k = p["baris"], p["kolom"]
    kunci = b * k
    teks = (f"{_nama_anak(b + k)} menyusun persegi-persegi kecil yang sama besar menjadi "
            f"sebuah persegi panjang. Susunannya ada {b} baris, dan tiap baris berisi {k} "
            f"persegi kecil. Berapa banyak persegi kecil yang dipakai {_nama_anak(b + k)}?")
    pembahasan = (f"Ada {b} baris dan tiap baris berisi {k} persegi kecil, jadi semuanya "
                  f"{b} × {k} = {kunci} persegi kecil. Jadi jawabannya {kunci}.")
    return teks, str(kunci), pembahasan, _kandidat_susun_persegi(p, kunci)


def _susun_gabung(p: dict) -> tuple:
    b1, k1, b2, k2 = p["baris1"], p["kolom1"], p["baris2"], p["kolom2"]
    pertama, kedua = b1 * k1, b2 * k2
    kunci = pertama + kedua
    teks = (f"{_nama_anak(b1 + k1 + b2 + k2)} menyusun dua kelompok persegi kecil yang "
            "sama besar tanpa saling menumpuk. "
            f"Kelompok pertama berisi {b1} baris dengan {k1} persegi kecil tiap baris. "
            f"Kelompok kedua berisi {b2} baris dengan {k2} persegi kecil tiap baris. "
            "Berapa banyak persegi kecil semuanya?")
    pembahasan = (f"Kelompok pertama: {b1} × {k1} = {pertama} persegi kecil. Kelompok "
                  f"kedua: {b2} × {k2} = {kedua} persegi kecil. Semuanya {pertama} + "
                  f"{kedua} = {kunci}. Jadi jawabannya {kunci}.")
    return teks, str(kunci), pembahasan, _kandidat_susun_gabung(p, kunci)


def _uraikan_banyak(p: dict) -> tuple:
    bangun, satu = p["bangun"], p["potong"] == "satu"
    kunci = 2 if satu else 4
    cara = "salah satu" if satu else "kedua"
    teks = (f"Sebuah {bangun} dipotong lurus menurut {cara} diagonalnya "
            f"{KETERANGAN_DIAGONAL}. Berapa banyak bagian yang terbentuk?")
    if satu:
        isi = f"Satu diagonal membagi {bangun} menjadi 2 segitiga."
    else:
        isi = (f"Dua diagonal berpotongan di tengah dan membagi {bangun} menjadi "
               "4 segitiga.")
    pembahasan = (f"Diagonal adalah garis lurus dari satu sudut ke sudut yang berhadapan. "
                  f"{isi} Jadi jawabannya {kunci}.")
    return teks, str(kunci), pembahasan, _kandidat_uraikan_banyak(p, kunci)


def _uraikan_nama(p: dict) -> tuple:
    teks = (f"Sebuah persegi panjang dengan panjang {p['panjang']} cm dan lebar "
            f"{p['lebar']} cm dipotong lurus menurut salah satu diagonalnya "
            f"{KETERANGAN_DIAGONAL}. Dua bagian yang terbentuk berbentuk bangun apa? "
            "Pilih: segitiga siku-siku, segitiga sama sisi, atau persegi.")
    pembahasan = ("Satu diagonal memotong persegi panjang menjadi dua bagian yang sama "
                  "persis. Pojok persegi panjang siku-siku, jadi tiap bagian punya satu "
                  "sudut siku-siku, dan panjang sisinya tidak semuanya sama. Bangun itu "
                  "segitiga siku-siku. Jadi jawabannya segitiga siku-siku.")
    return teks, "segitiga siku-siku", pembahasan, _kandidat_uraikan_nama()


_PEMBANGUN = {"ciri": _ciri, "dua_persegi": _dua_persegi, "susun_persegi": _susun_persegi,
              "susun_gabung": _susun_gabung, "uraikan_banyak": _uraikan_banyak,
              "uraikan_nama": _uraikan_nama}


def ciri_komposisi_bangun(varian: str, **parameter) -> Soal:
    """Ciri, susunan, atau uraian bangun datar; kunci dihitung dari parameter."""
    lengkap = {"varian": varian, **parameter}
    if not _sah(lengkap):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, pembahasan, kandidat = _PEMBANGUN[varian](lengkap)
    return Soal(
        template_id=TEMPLATE_ID, parameter=lengkap, teks=teks, kunci=kunci,
        malrule=saring_malrule(kunci, kandidat), pembahasan=pembahasan, bagian="A")
