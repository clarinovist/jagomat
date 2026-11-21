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
Lima varian TAMBAHAN (v2, APPEND-ONLY di belakang enam di atas; parameter lama tak berubah):
  - `ciri_segitiga`: jenis segitiga dari sisi/sudutnya (kunci nama, pilihan tertutup) dan banyak
    sisi yang sama panjang pada segitiga sama kaki / sama sisi (kunci angka);
  - `ciri_trapesium`: pasang sisi sejajar, banyak sisi, banyak sudut, dan panjang kaki kedua
    trapesium sama kaki (kunci angka);
  - `ciri_empat_sisi_lain`: layang-layang, belah ketupat, jajar genjang: banyak pasang sisi
    sama panjang, panjang sisi yang ditanya dari sisi yang diketahui, dan banyak sudut siku-siku
    (kunci angka);
  - `susun_dua_cara`: menutup persegi panjang dengan keping persegi / persegi panjang (banyak
    keping, dihitung dengan luas atau dengan baris x kolom) dan luas bangun hasil susun
    (kunci angka);
  - `uraikan_segi_banyak`: segi-n cembung dipotong dari satu titik sudut ke titik sudut yang
    tidak bersebelahan: banyak segitiga (n-2) atau banyak garis potong (n-3) (kunci angka).

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
DAFTAR FAKTA TAMBAHAN v2 (MOHON DIULAS MUTIA; tiap butir ditandai [ULAS-MUTIA]):
  [ULAS-MUTIA] segitiga sama sisi = tiga sisi sama panjang (3 sisi sama); segitiga sama kaki
      yang BUKAN sama sisi = tepat dua sisi sama panjang (definisi eksklusif ditulis eksplisit di
      soal; pada definisi inklusif sama sisi juga sama kaki, jadi "sama kaki" tak pernah menjadi
      pengecoh dari kunci "sama sisi" dan "sama sisi" tidak jadi pengecoh jenis lain);
  [ULAS-MUTIA] segitiga sembarang = ketiga sisi berbeda panjang (didefinisikan dalam kurung di
      soal), segitiga lancip = ketiga sudut lebih kecil dari siku-siku (didefinisikan dalam
      kurung); istilah "sembarang" dan "lancip" belum pasti sudah dipakai buku Kelas IV;
  [ULAS-MUTIA] segitiga siku-siku = punya satu sudut siku-siku;
  [ULAS-MUTIA] trapesium = segiempat dengan TEPAT satu pasang sisi sejajar (definisi
      eksklusif; soal sejajar menulis "trapesium yang bukan jajar genjang" sehingga hasilnya 1
      pada definisi inklusif juga); trapesium punya 4 sisi dan 4 sudut; trapesium sama kaki:
      kedua kaki (sisi miring yang tidak sejajar) sama panjang; istilah "trapesium sama kaki"
      dan "kaki" belum pasti dikenal di Kelas IV;
  [ULAS-MUTIA] layang-layang yang bukan belah ketupat: dua pasang sisi sama panjang yang
      berdekatan (AB = AD dan CB = CD, pasangan berbeda panjang); belah ketupat: keempat sisi
      sama panjang; jajar genjang: sisi berhadapan sama panjang (2 pasang), dan jajar genjang
      yang bukan persegi panjang, belah ketupat yang bukan persegi: tidak ada sudut siku-siku
      (jika satu sudutnya siku-siku, bangunnya persegi panjang / persegi);
  [ULAS-MUTIA] penutupan persegi panjang dengan keping: banyak keping = luas bangun : luas
      keping = (sepanjang) x (selebar), ukuran dipilih habis dibagi; luas hasil susun = banyak
      keping x luas satu keping (cm²);
  [ULAS-MUTIA] segi-n cembung dipotong dari satu titik sudut ke titik sudut yang tidak
      bersebelahan: n-3 garis potong dan n-2 segitiga (segiempat 2, segilima 3, segienam 4).
Sengaja TIDAK dipakai v2: "dua persegi sama besar disusun menjadi persegi panjang dengan ...
cara" (ambigu: cara menempel tak terhitung tegas), "sembarang" sebagai KUNCI (segitiga
siku-siku 3-4-5 juga sembarang; "sembarang" hanya muncul sebagai pilihan yang pasti salah),
"banyak sisi sama panjang" trapesium sama kaki (kaki bisa sama panjang dengan salah satu
alas), sudut siku layang-layang dan trapesium siku-siku (bergantung bentuk), segi banyak
cekung, n > 6.

Istilah "sejajar" didefinisikan di pembahasan (belum pasti sudah dipakai buku Kelas IV);
Mutia diminta memastikan istilah itu dan "diagonal" sudah dikenal di kelas ini.

Sengaja TIDAK dipakai di enam varian lama (varian v2 di bawah memakai sebagian dengan
kualifikasi eksplisit):
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
VARIAN_LAMA = ("ciri", "dua_persegi", "susun_persegi", "susun_gabung", "uraikan_banyak",
               "uraikan_nama")
VARIAN_BARU = ("ciri_segitiga", "ciri_trapesium", "ciri_empat_sisi_lain", "susun_dua_cara",
               "uraikan_segi_banyak")
VARIAN = VARIAN_LAMA + VARIAN_BARU  # APPEND-ONLY: varian baru hanya di belakang
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
# Domain varian baru (v2); semua APPEND-ONLY.
SISI_TIGA_SAMA = tuple(range(3, 10))
KAKI_ALAS = tuple((a, b) for a in range(3, 8) for b in range(2, 11) if b != a and b < 2 * a)
TEGAK_SIKU = tuple((a, b) for a in range(3, 9) for b in range(a + 1, 9))
TRAPESIUM_KAKI = tuple((a, b, k) for a in range(3, 6) for b in range(7, 10)
                       for k in range(4, 9))
BELAH_KETUPAT_SISI = tuple(range(3, 10))
LAYANG_SISI = tuple((a, b) for a in range(3, 8) for b in range(3, 10) if a != b)
JAJAR_SISI = tuple((p, q) for p in range(4, 10) for q in range(2, 8) if p != q)
SISI_KEPING_PERSEGI = tuple(range(2, 5))
KALI_KEPING = tuple(range(2, 6))
KEPING_PANJANG = ((3, 2), (4, 2), (4, 3), (5, 2))  # (p, q) dengan p > q
KALI_KEPING_PANJANG = tuple(range(2, 5))
BANYAK_KEPING = tuple(range(3, 10))
BANYAK_KEPING_PANJANG = tuple(range(3, 9))
SISI_KEPING_LUAS = tuple(range(2, 6))
JUMLAH_SISI_SEGI = (4, 5, 6)
NAMA_SEGI = {4: "segiempat", 5: "segilima", 6: "segienam"}  # kunci: n; APPEND-ONLY
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

def _enumerasi_baru() -> list:
    """Parameter varian v2, urutan tetap di belakang parameter lama."""
    v = "varian"
    hasil = [{v: "ciri_segitiga", "tanya": "jenis_tiga_sama", "sisi": s}
             for s in SISI_TIGA_SAMA]
    hasil += [{v: "ciri_segitiga", "tanya": "jenis_dua_sama", "kaki": a, "alas": b}
              for a, b in KAKI_ALAS]
    hasil += [{v: "ciri_segitiga", "tanya": "jenis_siku", "tegak_a": a, "tegak_b": b}
              for a, b in TEGAK_SIKU]
    hasil += [{v: "ciri_segitiga", "tanya": "banyak_sama_kaki", "kaki": a, "alas": b}
              for a, b in KAKI_ALAS]
    hasil += [{v: "ciri_segitiga", "tanya": "banyak_sama_sisi", "sisi": s}
              for s in SISI_TIGA_SAMA]
    hasil += [{v: "ciri_trapesium", "tanya": t} for t in
              ("trapesium_sejajar", "trapesium_sisi", "trapesium_sudut")]
    hasil += [{v: "ciri_trapesium", "tanya": "trapesium_kaki", "atas": a, "bawah": b,
               "kaki": k} for a, b, k in TRAPESIUM_KAKI]
    hasil += [{v: "ciri_empat_sisi_lain", "tanya": t} for t in
              ("layang_pasang", "jajar_pasang", "jajar_siku", "belah_siku")]
    hasil += [{v: "ciri_empat_sisi_lain", "tanya": "belah_sisi", "sisi": s}
              for s in BELAH_KETUPAT_SISI]
    hasil += [{v: "ciri_empat_sisi_lain", "tanya": "layang_sisi", "ab": a, "bc": b}
              for a, b in LAYANG_SISI]
    hasil += [{v: "ciri_empat_sisi_lain", "tanya": "jajar_sisi", "ab": a, "bc": b}
              for a, b in JAJAR_SISI]
    hasil += _enumerasi_susun_dua_cara()
    hasil += [{v: "uraikan_segi_banyak", "tanya": t, "n": n}
              for t in ("segitiga", "garis") for n in JUMLAH_SISI_SEGI]
    return hasil


def _enumerasi_susun_dua_cara() -> list:
    v = "susun_dua_cara"
    hasil = [{"varian": v, "tanya": "tutup_persegi", "panjang": s * m, "lebar": s * n,
              "sisi": s}
             for s in SISI_KEPING_PERSEGI for m in KALI_KEPING for n in KALI_KEPING
             if m != n]
    hasil += [{"varian": v, "tanya": "tutup_panjang", "panjang": p * m, "lebar": q * n,
               "keping_p": p, "keping_q": q}
              for p, q in KEPING_PANJANG for m in KALI_KEPING_PANJANG
              for n in KALI_KEPING_PANJANG if p * m != q * n]
    hasil += [{"varian": v, "tanya": "luas_persegi", "banyak": n, "sisi": s}
              for n in BANYAK_KEPING for s in SISI_KEPING_LUAS]
    hasil += [{"varian": v, "tanya": "luas_keping", "banyak": n, "keping_p": p,
               "keping_q": q} for n in BANYAK_KEPING_PANJANG for p, q in KEPING_PANJANG]
    return hasil


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
    hasil += _enumerasi_baru()
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


# ── varian baru v2: segitiga, trapesium, empat sisi lain, susun dua cara, segi banyak ──

_SEMBARANG = "sembarang (ketiga sisinya berbeda panjang)"
_LANCIP = "lancip (ketiga sudutnya lebih kecil dari sudut siku-siku)"
_DEF_SEJAJAR = "Sisi sejajar adalah dua sisi yang tidak akan bertemu walau diperpanjang sejauh apa pun."
_DEF_SIKU = "Sudut siku-siku adalah sudut seperti pojok kertas, besarnya 90 derajat."


def _hitung_menjadi(satuan: str, ke: int) -> Malrule:
    return _mal("sisi_dan_sudut_dijumlah", ke, "K",
                f"Menjumlah banyak sisi dan banyak sudut ({ke}) padahal yang ditanya hanya "
                f"banyak {satuan}.")


def _seg_tiga_sama(p: dict) -> tuple:
    teks = (f"Sebuah segitiga mempunyai tiga sisi yang sama panjang, yaitu {p['sisi']} cm "
            f"tiap sisinya. Segitiga itu disebut segitiga apa? Pilih: sama sisi, siku-siku, "
            f"atau {_SEMBARANG}.")
    pembahasan = ("Segitiga yang ketiga sisinya sama panjang disebut segitiga sama sisi. "
                  "Segitiga siku-siku punya satu sudut siku-siku dan segitiga sembarang "
                  "ketiga sisinya berbeda panjang, jadi keduanya bukan. Jadi jawabannya "
                  "sama sisi.")
    return teks, "sama sisi", pembahasan, [
        _mal("dikira_siku_siku", "siku-siku", "K",
             "Mengira segitiga yang sisinya sama panjang disebut segitiga siku-siku."),
        _mal("dikira_sembarang", "sembarang", "K",
             "Mengira segitiga yang sisinya sama panjang hanya segitiga sembarang."),
    ]


def _seg_dua_sama(p: dict) -> tuple:
    a, b = p["kaki"], p["alas"]
    teks = (f"Sebuah segitiga mempunyai tepat dua sisi yang sama panjang, masing-masing "
            f"{a} cm, dan sisi ketiganya {b} cm. Segitiga itu disebut segitiga apa? "
            f"Pilih: sama kaki, sama sisi, atau {_SEMBARANG}.")
    pembahasan = (f"Segitiga yang tepat dua sisinya sama panjang disebut segitiga sama kaki. "
                  f"Di sini dua sisinya {a} cm dan sisi ketiganya {b} cm, jadi sisinya tidak "
                  "semuanya sama dan tidak semuanya berbeda. Jadi jawabannya sama kaki.")
    return teks, "sama kaki", pembahasan, [
        _mal("dikira_sama_sisi", "sama sisi", "K",
             "Menyamakan segitiga yang dua sisinya sama panjang dengan segitiga sama sisi "
             "(tiga sisi sama panjang)."),
        _mal("dikira_sembarang", "sembarang", "K",
             "Mengira segitiga yang sisinya tidak semuanya sama hanya segitiga sembarang."),
    ]


def _seg_siku(p: dict) -> tuple:
    a, b = p["tegak_a"], p["tegak_b"]
    teks = (f"Sebuah segitiga mempunyai satu sudut siku-siku, dan dua sisi yang mengapit "
            f"sudut itu panjangnya {a} cm dan {b} cm. Segitiga itu disebut segitiga apa? "
            f"Pilih: siku-siku, sama sisi, atau {_LANCIP}.")
    pembahasan = (f"{_DEF_SIKU} Segitiga yang punya satu sudut siku-siku disebut segitiga "
                  "siku-siku. Segitiga sama sisi dan segitiga lancip tidak punya sudut "
                  "siku-siku. Jadi jawabannya siku-siku.")
    return teks, "siku-siku", pembahasan, [
        _mal("dikira_sama_sisi", "sama sisi", "K",
             "Menyebut segitiga sama sisi, kemungkinan tertukar dengan segitiga lain."),
        _mal("dikira_lancip", "lancip", "K",
             "Mengira semua sudutnya lebih kecil dari sudut siku-siku."),
    ]


def _seg_banyak_sama_kaki(p: dict) -> tuple:
    a, b = p["kaki"], p["alas"]
    teks = (f"Sebuah segitiga sama kaki yang bukan segitiga sama sisi mempunyai sisi {a} cm, "
            f"{a} cm, dan {b} cm. Berapa banyak sisinya yang sama panjang?")
    pembahasan = (f"Dua sisinya sama panjang, yaitu {a} cm, sedangkan sisi yang {b} cm "
                  "berbeda dari keduanya. Segitiga sama kaki yang bukan sama sisi punya "
                  "tepat 2 sisi sama panjang. Jadi jawabannya 2.")
    return teks, "2", pembahasan, [
        _mal("tertukar_sama_sisi", 3, "K",
             "Menyebut banyak sisi segitiga sama sisi (3), kemungkinan tertukar atau "
             "menghitung semua sisinya."),
        _mal("hanya_sisi_berbeda", 1, "K",
             "Menyebut banyak sisi yang berbeda panjang (1), bukan yang sama panjang."),
        _mal("tertukar_segiempat", 4, "K",
             "Menyebut banyak sisi segiempat (4), kemungkinan tertukar dengan segiempat."),
        _hitung_menjadi("sisi yang sama panjang", 6),
    ]


def _seg_banyak_sama_sisi(p: dict) -> tuple:
    s = p["sisi"]
    teks = (f"Sebuah segitiga sama sisi mempunyai sisi {s} cm tiap sisinya. Berapa banyak "
            "sisinya yang sama panjang?")
    pembahasan = (f"Segitiga sama sisi punya tiga sisi sama panjang, masing-masing {s} cm. "
                  "Jadi jawabannya 3.")
    return teks, "3", pembahasan, [
        _mal("dikira_dua_sisi_sama", 2, "K",
             "Mengira hanya dua sisi yang sama panjang seperti pada segitiga sama kaki (2)."),
        _mal("tertukar_segiempat", 4, "K",
             "Menyebut banyak sisi segiempat (4), kemungkinan tertukar dengan segiempat."),
        _hitung_menjadi("sisi yang sama panjang", 6),
    ]


def _trapesium_sejajar(p: dict) -> tuple:
    teks = "Berapa pasang sisi sejajar yang dimiliki trapesium yang bukan jajar genjang?"
    pembahasan = (f"{_DEF_SEJAJAR} Trapesium punya satu pasang sisi sejajar, yaitu sisi atas "
                  "dan sisi bawahnya, sedangkan dua sisi miringnya tidak sejajar. Trapesium "
                  "yang bukan jajar genjang punya tepat 1 pasang. Jadi jawabannya 1.")
    return teks, "1", pembahasan, [
        _mal("dikira_seperti_jajar_genjang", 2, "K",
             "Mengira trapesium punya dua pasang sisi sejajar seperti jajar genjang (2)."),
        _mal("dikira_tidak_ada", 0, "K",
             "Mengira tidak ada sisi yang sejajar karena bentuknya miring (0)."),
        _mal("sisi_disebut", 4, "K",
             "Menyebut banyak sisi (4), bukan banyak pasang sisi sejajar."),
    ]


def _trapesium_sisi(p: dict) -> tuple:
    teks = "Berapa banyak sisi trapesium?"
    pembahasan = ("Trapesium adalah segiempat yang punya tepat satu pasang sisi sejajar. "
                  "Sisinya ada sisi atas, sisi bawah, dan dua sisi miring, jadi semuanya "
                  "4 sisi. Jadi jawabannya 4.")
    return teks, "4", pembahasan, [
        _mal("bangun_lain", 3, "K",
             "Menyebut banyak sisi segitiga (3), kemungkinan tertukar dengan bangun lain."),
        _mal("sisi_sejajar_disebut", 2, "K",
             "Menyebut banyak sisi yang sejajar (2), bukan banyak seluruh sisi."),
        _hitung_menjadi("sisi", 8),
        *_h_satu("sisi", 4)[:1],
    ]


def _trapesium_sudut(p: dict) -> tuple:
    teks = "Berapa banyak sudut trapesium?"
    pembahasan = ("Trapesium adalah segiempat yang punya tepat satu pasang sisi sejajar. "
                  "Di tiap pojoknya ada satu sudut, jadi trapesium punya 4 sudut. Jadi "
                  "jawabannya 4.")
    return teks, "4", pembahasan, [
        _mal("bangun_lain", 3, "K",
             "Menyebut banyak sudut segitiga (3), kemungkinan tertukar dengan bangun lain."),
        _mal("sisi_sejajar_disebut", 2, "K",
             "Menyebut banyak sisi yang sejajar (2), bukan banyak sudut."),
        _hitung_menjadi("sudut", 8),
        *_h_satu("sudut", 4)[:1],
    ]


def _trapesium_kaki(p: dict) -> tuple:
    a, b, k = p["atas"], p["bawah"], p["kaki"]
    teks = (f"Sebuah trapesium sama kaki mempunyai sisi sejajar {a} cm dan {b} cm, dan salah "
            f"satu kakinya (sisi miring yang tidak sejajar) {k} cm. Berapa cm panjang kaki "
            "yang satunya?")
    pembahasan = (f"Pada trapesium sama kaki, kedua kakinya sama panjang. Salah satu kakinya "
                  f"{k} cm, jadi kaki yang satunya juga {k} cm. Sisi sejajar {a} cm dan {b} cm "
                  f"bukan kaki. Jadi jawabannya {k}.")
    return teks, str(k), pembahasan, [
        _mal("sisi_atas_disebut", a, "K",
             f"Menyebut panjang sisi sejajar yang pendek ({a}), bukan panjang kaki."),
        _mal("sisi_bawah_disebut", b, "K",
             f"Menyebut panjang sisi sejajar yang panjang ({b}), bukan panjang kaki."),
        _mal("sisi_sejajar_dijumlah", a + b, "K",
             f"Menjumlah kedua sisi sejajar ({a + b}), bukan panjang kaki."),
        _mal("selisih_sisi_sejajar", b - a, "K",
             f"Menyebut selisih kedua sisi sejajar ({b - a}), bukan panjang kaki."),
        _mal("lebih_satu", k + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {k + 1}."),
        _mal("kurang_satu", k - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {k - 1}."),
    ]


def _layang_pasang(p: dict) -> tuple:
    teks = ("Dua sisi berdekatan adalah dua sisi yang bertemu di satu sudut. Berapa pasang "
            "sisi berdekatan yang sama panjang pada layang-layang yang bukan belah ketupat?")
    pembahasan = ("Layang-layang yang bukan belah ketupat punya dua sisi pendek yang bertemu "
                  "di satu sudut dan dua sisi panjang yang bertemu di sudut lain. Sisi "
                  "pendeknya sama panjang dan sisi panjangnya sama panjang, jadi ada 2 pasang. "
                  "Jadi jawabannya 2.")
    return teks, "2", pembahasan, [
        _mal("sisi_disebut", 4, "K",
             "Menyebut banyak sisi (4), bukan banyak pasang sisi yang sama panjang."),
        _mal("hanya_satu_pasang", 1, "K",
             "Hanya menghitung satu pasang sisi yang sama panjang dan melewatkan pasangan "
             "satunya (1)."),
        _mal("berhadapan_dikira_sama", 0, "K",
             "Mengira yang sama panjang hanya sisi berhadapan, sehingga tidak ada sisi "
             "berdekatan yang sama panjang (0)."),
        _mal("satu_pasang_berlebih", 3, "H",
             "Sudah mengerti caranya, tetapi satu pasang terhitung dua kali sehingga "
             "jawabannya 3."),
    ]


def _jajar_pasang(p: dict) -> tuple:
    teks = "Berapa pasang sisi berhadapan yang sama panjang pada jajar genjang?"
    pembahasan = ("Pada jajar genjang, sisi atas sama panjang dengan sisi bawah, dan sisi "
                  "miring kiri sama panjang dengan sisi miring kanan. Jadi ada 2 pasang "
                  "sisi berhadapan yang sama panjang. Jadi jawabannya 2.")
    return teks, "2", pembahasan, [
        _mal("sisi_disebut", 4, "K",
             "Menyebut banyak sisi (4), bukan banyak pasang sisi berhadapan."),
        _mal("hanya_satu_pasang", 1, "K",
             "Mengira hanya sisi atas dan bawah yang sama panjang, sedangkan sisi miring "
             "tidak (1)."),
        _mal("miring_dikira_tidak_sama", 0, "K",
             "Mengira tidak ada sisi yang sama panjang karena bentuknya miring (0)."),
        _mal("satu_pasang_berlebih", 3, "H",
             "Sudah mengerti caranya, tetapi satu pasang terhitung dua kali sehingga "
             "jawabannya 3."),
    ]


def _belah_siku_nol(nama: str, bukan: str, sebab: str) -> tuple:
    teks = f"Berapa banyak sudut siku-siku pada {nama} yang bukan {bukan}?"
    pembahasan = (f"{_DEF_SIKU} Kalau satu sudutnya siku-siku, bangunnya menjadi {bukan}. "
                  f"Karena {nama} ini bukan {bukan}, {sebab}. Jadi jawabannya 0.")
    return teks, "0", pembahasan, [
        _mal("dikira_empat_siku", 4, "K",
             f"Mengira keempat sudutnya siku-siku seperti {bukan} (4)."),
        _mal("dikira_dua_siku", 2, "K",
             "Mengira ada dua sudut siku-siku karena ada dua pasang sisi sejajar (2)."),
        _mal("sudut_segitiga_disebut", 3, "K",
             "Menyebut banyak sudut segitiga (3), kemungkinan tertukar dengan segitiga."),
        _mal("satu_sudut_terhitung", 1, "H",
             "Sudah mengerti caranya, tetapi satu sudut terhitung siku-siku sehingga "
             "jawabannya 1."),
    ]


def _jajar_siku(p: dict) -> tuple:
    return _belah_siku_nol("jajar genjang", "persegi panjang",
                           "bentuknya miring dan tidak ada pojoknya yang siku-siku")


def _belah_siku(p: dict) -> tuple:
    return _belah_siku_nol("belah ketupat", "persegi",
                           "bentuknya miring dan tidak ada pojoknya yang siku-siku")


def _belah_sisi(p: dict) -> tuple:
    s = p["sisi"]
    teks = f"Sebuah belah ketupat ABCD mempunyai sisi AB = {s} cm. Berapa cm panjang sisi BC?"
    pembahasan = (f"Belah ketupat punya empat sisi sama panjang. Jadi BC sama panjang dengan "
                  f"AB, yaitu {s} cm. Jadi jawabannya {s}.")
    return teks, str(s), pembahasan, [
        _mal("keliling_disebut", 4 * s, "K",
             f"Menyebut jumlah keempat sisi ({4 * s}), bukan panjang satu sisi."),
        _mal("banyak_sisi_disebut", 4, "K",
             "Menyebut banyak sisi (4), bukan panjang sisi BC."),
        _mal("dua_sisi_dijumlah", 2 * s, "K",
             f"Menjumlah dua sisi ({2 * s}), bukan panjang satu sisi."),
        _mal("lebih_satu", s + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {s + 1}."),
        _mal("kurang_satu", s - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {s - 1}."),
    ]


def _layang_sisi(p: dict) -> tuple:
    a, b = p["ab"], p["bc"]
    teks = (f"Pada layang-layang ABCD yang bukan belah ketupat, AB = AD = {a} cm dan "
            f"BC = {b} cm. Berapa cm panjang CD?")
    pembahasan = (f"Layang-layang punya dua pasang sisi sama panjang yang berdekatan. "
                  f"Pasangan pertama AB dan AD ({a} cm), pasangan kedua BC dan CD. Karena "
                  f"BC = {b} cm, maka CD = {b} cm. Jadi jawabannya {b}.")
    return teks, str(b), pembahasan, [
        _mal("tertukar_pasangan", a, "K",
             f"Menyebut panjang AB dan AD ({a}), tertukar dengan pasangan sisi di sebelahnya."),
        _mal("dua_sisi_dijumlah", a + b, "K",
             f"Menjumlah dua sisi yang diketahui ({a + b}), bukan panjang CD."),
        _mal("keliling_disebut", 2 * (a + b), "K",
             f"Menyebut jumlah keempat sisi ({2 * (a + b)}), bukan panjang CD."),
        _mal("lebih_satu", b + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {b + 1}."),
        _mal("kurang_satu", b - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {b - 1}."),
    ]


def _jajar_sisi(p: dict) -> tuple:
    a, b = p["ab"], p["bc"]
    teks = (f"Pada jajar genjang ABCD, sisi AB = {a} cm dan sisi BC = {b} cm. Berapa cm "
            "panjang sisi CD?")
    pembahasan = (f"Pada jajar genjang, sisi yang berhadapan sama panjang. CD berhadapan "
                  f"dengan AB, jadi CD = {a} cm. Jadi jawabannya {a}.")
    return teks, str(a), pembahasan, [
        _mal("tertukar_sisi_sebelah", b, "K",
             f"Menyebut panjang BC ({b}), tertukar dengan sisi di sebelahnya."),
        _mal("dua_sisi_dijumlah", a + b, "K",
             f"Menjumlah dua sisi yang diketahui ({a + b}), bukan panjang CD."),
        _mal("keliling_disebut", 2 * (a + b), "K",
             f"Menyebut jumlah keempat sisi ({2 * (a + b)}), bukan panjang CD."),
        _mal("lebih_satu", a + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {a + 1}."),
        _mal("kurang_satu", a - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungannya meleset satu sehingga jawabannya {a - 1}."),
    ]


def _tutup_persegi(p: dict) -> tuple:
    pj, lb, s = p["panjang"], p["lebar"], p["sisi"]
    m, n = pj // s, lb // s
    kunci = m * n
    nama = _nama_anak(pj + lb + s)
    teks = (f"{nama} akan menutup penuh sebuah persegi panjang berukuran {pj} cm × {lb} cm "
            f"dengan keping persegi berukuran {s} cm × {s} cm, tanpa celah dan tidak saling "
            "menumpuk. Berapa banyak keping persegi yang diperlukan?")
    pembahasan = (f"Cara pertama: sepanjang {pj} cm muat {pj} ÷ {s} = {m} keping dan selebar "
                  f"{lb} cm muat {lb} ÷ {s} = {n} keping, jadi {m} × {n} = {kunci} keping. "
                  f"Cara kedua: luas bangun {pj} × {lb} = {pj * lb} cm² dibagi luas satu "
                  f"keping {s} × {s} = {s * s} cm², hasilnya juga {kunci}. Jadi jawabannya "
                  f"{kunci}.")
    return teks, str(kunci), pembahasan, [
        _mal("baris_kolom_dijumlah", m + n, "K",
             f"Menjumlah banyak keping sepanjang dan selebar ({m + n}), bukan mengalikannya."),
        _mal("luas_bangun_disebut", pj * lb, "K",
             f"Menyebut luas bangun ({pj * lb}), belum dibagi luas satu keping."),
        _mal("dibagi_sisi_saja", pj * lb // s, "K",
             f"Membagi luas bangun dengan panjang sisi keping saja ({pj * lb // s}), bukan "
             "dengan luas satu keping."),
        _mal("satu_baris_terlewat", kunci - m, "H",
             f"Sudah mengerti caranya, tetapi satu baris terlewat sehingga jawabannya {kunci - m}."),
        _mal("satu_baris_berlebih", kunci + m, "H",
             f"Sudah mengerti caranya, tetapi satu baris terhitung dua kali sehingga "
             f"jawabannya {kunci + m}."),
    ]


def _tutup_panjang(p: dict) -> tuple:
    pj, lb, kp, kq = p["panjang"], p["lebar"], p["keping_p"], p["keping_q"]
    m, n = pj // kp, lb // kq
    kunci = m * n
    nama = _nama_anak(pj + lb + kp + kq)
    teks = (f"{nama} akan menutup penuh sebuah persegi panjang berukuran {pj} cm × {lb} cm "
            f"dengan keping persegi panjang berukuran {kp} cm × {kq} cm, tanpa celah dan "
            "tidak saling menumpuk. Berapa banyak keping yang diperlukan?")
    pembahasan = (f"Cara pertama: luas bangun {pj} × {lb} = {pj * lb} cm² dibagi luas satu "
                  f"keping {kp} × {kq} = {kp * kq} cm², hasilnya {kunci}. Cara kedua: "
                  f"sepanjang {pj} cm muat {pj} ÷ {kp} = {m} keping dan selebar {lb} cm "
                  f"muat {lb} ÷ {kq} = {n} keping, jadi {m} × {n} = {kunci}. Jadi "
                  f"jawabannya {kunci}.")
    return teks, str(kunci), pembahasan, [
        _mal("baris_kolom_dijumlah", m + n, "K",
             f"Menjumlah banyak keping sepanjang dan selebar ({m + n}), bukan mengalikannya."),
        _mal("luas_bangun_disebut", pj * lb, "K",
             f"Menyebut luas bangun ({pj * lb}), belum dibagi luas satu keping."),
        _mal("dibagi_satu_sisi_saja", pj * lb // kp, "K",
             f"Membagi luas bangun dengan satu sisi keping saja ({pj * lb // kp}), bukan "
             "dengan luas satu keping."),
        _mal("satu_baris_terlewat", kunci - m, "H",
             f"Sudah mengerti caranya, tetapi satu baris terlewat sehingga jawabannya {kunci - m}."),
        _mal("satu_baris_berlebih", kunci + m, "H",
             f"Sudah mengerti caranya, tetapi satu baris terhitung dua kali sehingga "
             f"jawabannya {kunci + m}."),
    ]


def _luas_persegi(p: dict) -> tuple:
    n, s = p["banyak"], p["sisi"]
    satu, kunci = s * s, n * s * s
    nama = _nama_anak(n + s)
    teks = (f"{nama} menyusun {n} keping persegi yang sama besar, tiap keping bersisi {s} cm. "
            "Keping-keping itu dirapatkan tanpa celah dan tidak saling menumpuk menjadi satu "
            "bangun. Berapa cm² luas bangun itu?")
    pembahasan = (f"Luas satu keping {s} × {s} = {satu} cm². Ada {n} keping, jadi luas "
                  f"bangun {n} × {satu} = {kunci} cm². Jadi jawabannya {kunci}.")
    return teks, str(kunci), pembahasan, [
        _mal("luas_satu_keping", satu, "K",
             f"Menyebut luas satu keping ({satu}), belum dikalikan banyak keping."),
        _mal("sisi_dikali_banyak", n * s, "K",
             f"Mengalikan banyak keping dengan sisi saja ({n * s}), belum menghitung luas "
             "satu keping."),
        _mal("keliling_dikali_banyak", 4 * s * n, "K",
             f"Menjumlah keliling semua keping ({4 * s * n}), bukan luasnya."),
        _mal("satu_keping_terlewat", kunci - satu, "H",
             f"Sudah mengerti caranya, tetapi satu keping terlewat sehingga jawabannya {kunci - satu}."),
        _mal("satu_keping_berlebih", kunci + satu, "H",
             f"Sudah mengerti caranya, tetapi satu keping terhitung dua kali sehingga "
             f"jawabannya {kunci + satu}."),
    ]


def _luas_keping(p: dict) -> tuple:
    n, kp, kq = p["banyak"], p["keping_p"], p["keping_q"]
    satu, kunci = kp * kq, n * kp * kq
    nama = _nama_anak(n + kp + kq)
    teks = (f"{nama} menyusun {n} keping persegi panjang yang sama besar, tiap keping "
            f"berukuran {kp} cm × {kq} cm. Keping-keping itu dirapatkan tanpa celah dan "
            "tidak saling menumpuk menjadi satu bangun. Berapa cm² luas bangun itu?")
    pembahasan = (f"Luas satu keping {kp} × {kq} = {satu} cm². Ada {n} keping, jadi luas "
                  f"bangun {n} × {satu} = {kunci} cm². Jadi jawabannya {kunci}.")
    return teks, str(kunci), pembahasan, [
        _mal("luas_satu_keping", satu, "K",
             f"Menyebut luas satu keping ({satu}), belum dikalikan banyak keping."),
        _mal("panjang_lebar_dijumlah", n * (kp + kq), "K",
             f"Menjumlah panjang dan lebar tiap keping lalu mengalikannya dengan banyak "
             f"keping ({n * (kp + kq)}), bukan luasnya."),
        _mal("semua_angka_dijumlah", n + kp + kq, "K",
             f"Menjumlah ketiga bilangan yang tertulis ({n + kp + kq}) tanpa mengalikan."),
        _mal("satu_keping_terlewat", kunci - satu, "H",
             f"Sudah mengerti caranya, tetapi satu keping terlewat sehingga jawabannya {kunci - satu}."),
        _mal("satu_keping_berlebih", kunci + satu, "H",
             f"Sudah mengerti caranya, tetapi satu keping terhitung dua kali sehingga "
             f"jawabannya {kunci + satu}."),
    ]


def _awal_segi(n: int) -> str:
    return (f"Sebuah {NAMA_SEGI[n]} (bangun datar dengan {n} sisi, tidak ada sudutnya yang "
            "menjorok ke dalam) dipotong dengan garis lurus dari satu titik sudut ke semua "
            "titik sudut lain yang tidak bersebelahan dengan titik sudut itu. Semua garis "
            "potong keluar dari titik sudut yang sama, jadi tidak saling berpotongan di "
            "dalam bangun.")


def _segi_segitiga(p: dict) -> tuple:
    n = p["n"]
    teks = f"{_awal_segi(n)} Berapa banyak segitiga yang terbentuk?"
    pembahasan = (f"Dari satu titik sudut ditarik {n} − 3 = {n - 3} garis potong ke titik "
                  f"sudut yang tidak bersebelahan. {n - 3} garis potong membagi "
                  f"{NAMA_SEGI[n]} menjadi {n - 3} + 1 = {n - 2} segitiga. Jadi jawabannya "
                  f"{n - 2}.")
    return teks, str(n - 2), pembahasan, [
        _mal("banyak_sisi_disebut", n, "K",
             f"Menyebut banyak sisi bangun ({n}), bukan banyak segitiga."),
        _mal("garis_potong_disebut", n - 3, "K",
             f"Menyebut banyak garis potong ({n - 3}), bukan banyak segitiga."),
        _mal("satu_segitiga_berlebih", n - 1, "H",
             f"Sudah mengerti caranya, tetapi satu segitiga terhitung dua kali sehingga "
             f"jawabannya {n - 1}."),
    ]


def _segi_garis(p: dict) -> tuple:
    n = p["n"]
    teks = f"{_awal_segi(n)} Berapa banyak garis potong yang dibuat?"
    pembahasan = (f"Titik sudut yang dipilih tidak dihubungkan ke dirinya sendiri dan ke 2 "
                  f"titik sudut yang bersebelahan dengannya, jadi dari {n} titik sudut "
                  f"tersisa {n} − 3 = {n - 3}. Jadi jawabannya {n - 3}.")
    return teks, str(n - 3), pembahasan, [
        _mal("banyak_segitiga_disebut", n - 2, "K",
             f"Menyebut banyak segitiga ({n - 2}), bukan banyak garis potong."),
        _mal("banyak_sisi_disebut", n, "K",
             f"Menyebut banyak sisi bangun ({n}), bukan banyak garis potong."),
        _mal("ke_semua_titik", n - 1, "K",
             f"Menghubungkan titik sudut ke semua titik sudut lain ({n - 1}), termasuk dua "
             "yang bersebelahan yang sebenarnya sisi bangun."),
        _mal("satu_garis_terlewat", n - 4, "H",
             f"Sudah mengerti caranya, tetapi satu garis terlewat sehingga jawabannya {n - 4}."),
    ]


_PER_TANYA = {
    "jenis_tiga_sama": _seg_tiga_sama, "jenis_dua_sama": _seg_dua_sama,
    "jenis_siku": _seg_siku, "banyak_sama_kaki": _seg_banyak_sama_kaki,
    "banyak_sama_sisi": _seg_banyak_sama_sisi,
    "trapesium_sejajar": _trapesium_sejajar, "trapesium_sisi": _trapesium_sisi,
    "trapesium_sudut": _trapesium_sudut, "trapesium_kaki": _trapesium_kaki,
    "layang_pasang": _layang_pasang, "jajar_pasang": _jajar_pasang,
    "jajar_siku": _jajar_siku, "belah_siku": _belah_siku, "belah_sisi": _belah_sisi,
    "layang_sisi": _layang_sisi, "jajar_sisi": _jajar_sisi,
    "tutup_persegi": _tutup_persegi, "tutup_panjang": _tutup_panjang,
    "luas_persegi": _luas_persegi, "luas_keping": _luas_keping,
    "segitiga": _segi_segitiga, "garis": _segi_garis,
}


def _varian_baru(p: dict) -> tuple:
    return _PER_TANYA[p["tanya"]](p)


_PEMBANGUN = {"ciri": _ciri, "dua_persegi": _dua_persegi, "susun_persegi": _susun_persegi,
              "susun_gabung": _susun_gabung, "uraikan_banyak": _uraikan_banyak,
              "uraikan_nama": _uraikan_nama,
              **{v: _varian_baru for v in VARIAN_BARU}}


def ciri_komposisi_bangun(varian: str, **parameter) -> Soal:
    """Ciri, susunan, atau uraian bangun datar; kunci dihitung dari parameter."""
    lengkap = {"varian": varian, **parameter}
    if not _sah(lengkap):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, pembahasan, kandidat = _PEMBANGUN[varian](lengkap)
    return Soal(
        template_id=TEMPLATE_ID, parameter=lengkap, teks=teks, kunci=kunci,
        malrule=saring_malrule(kunci, kandidat), pembahasan=pembahasan, bagian="A")
