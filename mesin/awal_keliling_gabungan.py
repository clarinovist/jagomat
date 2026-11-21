"""Matematika Awal, jenis `keliling_gabungan`: keliling persegi, persegi panjang, dan bangun gabungan (P5), teks saja.

Bab K5 B4 "Keliling bangun datar" (Keliling bangun datar; Keliling bangun gabungan).
Bangun dideskripsikan TANPA gambar dengan semua panjang sisi disebutkan. Empat bentuk
soal (`varian`), semua berkunci angka bulat positif:
  - `persegi_persegipanjang` dengan `tanya`: `keliling_persegi` (sisi -> keliling),
    `keliling_persegipanjang` (panjang, lebar -> keliling), `sisi_dari_keliling`
    (keliling persegi -> sisi), `panjang_dari_keliling` (keliling dan lebar -> panjang);
  - `dua_persegipanjang`: dua persegi panjang berlebar sama disambung rapat pada sisi
    lebarnya sehingga membentuk satu persegi panjang; keliling = 2 x ((p1 + p2) + lebar);
  - `bentuk_L`: persegi panjang p x l dengan satu pojok persegi kecil bersisi s dipotong
    (s < sisi terpendek, jadi hasilnya benar-benar huruf L); keliling = 2 x (p + l),
    sama dengan keliling persegi panjang asal;
  - `segitiga_sama_sisi_di_persegi`: segitiga sama sisi bersisi s menempel pada satu sisi
    persegi bersisi s; keliling = 5 x s.

Kepastian bangun: pada `dua_persegipanjang` kedua lebar sama, sisi lebar yang disambung
adalah sisi terpendek kedua bangun (p1, p2 > lebar) dan p1 > p2, sehingga bangun gabungan
selalu persegi panjang (p1 + p2) x lebar dan rumusnya tunggal. Pada `bentuk_L` panjang >
lebar dan s < lebar; pada s sama dengan sisi terpendek satu jalur utuh ikut terbuang dan
keliling berubah, jadi s sama atau lebih besar tidak masuk domain. Panjang sisi 2..30
dengan satuan cm atau m yang konsisten satu soal; kunci angka polos tanpa satuan.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari
satu jawaban: menjumlah semua sisi termasuk sisi yang menempel (K), melupakan sisi (K),
menghitung luas alih-alih keliling (K), salah memahami bagian yang dipotong (K), serta
kurang/lebih satu sisi (H, hanya bila nyata berbeda dari kunci). Jalur K selalu ada.
Kunci yang bertabrakan dengan malrule (mis. luas = keliling pada s = 4) dibuang
`saring_malrule`; jalur K lain tetap tersisa.

Lima varian tambahan (P5, semua panjang disebut di teks; ditambahkan SETELAH parameter lama
sehingga identitas parameter lama tidak berubah). Kunci angka bulat atau desimal berkoma
pendek (konvensi `urut_pecahan_desimal_persen`: "62,8", tanpa nol di belakang koma):
  - `segitiga` (`tanya`): `keliling_sembarang`, `keliling_sama_kaki`, `keliling_sama_sisi`,
    `cari_sisi_ketiga`, `cari_sisi_sama_sisi`, `cari_alas_sama_kaki`; sisi sah menurut
    ketidaksamaan segitiga;
  - `jajar_genjang_belah_ketupat` (`tanya`): `jajar_genjang` (alas, sisi miring),
    `jajar_genjang_tinggi` (tinggi ikut disebut sebagai pengecoh), `belah_ketupat`,
    `cari_sisi_belah_ketupat`, `layang_layang` (dua sisi pendek, dua sisi panjang);
  - `trapesium` (`tanya`): `trapesium_sembarang` (keempat sisi; sisi miring sah menurut
    ketidaksamaan segitiga dengan selisih sisi sejajar), `trapesium_sama_kaki`,
    `trapesium_sama_kaki_tinggi` (tinggi dan kaki cocok tripel Pythagoras);
  - `lingkaran` (`tanya`): `keliling_dari_jari`, `keliling_dari_diameter`,
    `keliling_setengah_lingkaran` (teks menyatakan: keliling = lengkungan + sisi lurus);
    `pi` "22/7" hanya jari-jari 7..35 (diameter 14, 28, 42), `pi` "3,14" jari-jari dan
    diameter kelipatan 10 sampai 50;
  - `bentuk_T_U_tangga` (`bentuk`): `tangga` dan `huruf_T` berkeliling sama dengan persegi
    panjang pembatasnya; `huruf_U` = keliling pembatas + 2 x kedalaman celah (celah dibuang
    dari tengah sisi atas; sisi atas celah hilang, dasar celah muncul sebagai pengganti).

Domain eksplisit (`domain_parameter`): sampler memilih `varian` seragam dulu, lalu
sub-bentuk (`tanya`/`bentuk`) seragam bila ada, lalu satu parameter seragam; hanya dari
`rng` (tanpa `hash()`).
"""
from __future__ import annotations

from fractions import Fraction
from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "keliling_gabungan"
LEVEL = ("P5",)
VARIAN_LAMA = ("persegi_persegipanjang", "dua_persegipanjang", "bentuk_L",
               "segitiga_sama_sisi_di_persegi")
VARIAN_BARU = ("segitiga", "jajar_genjang_belah_ketupat", "trapesium", "lingkaran",
               "bentuk_T_U_tangga")
VARIAN = VARIAN_LAMA + VARIAN_BARU
TANYA = ("keliling_persegi", "keliling_persegipanjang", "sisi_dari_keliling",
         "panjang_dari_keliling")
SATUAN = ("cm", "m")
PESAN_LUAR_DOMAIN = "parameter keliling gabungan di luar domain"
SISI_PERSEGI = tuple(range(2, 31))
PANJANG_PP = tuple(range(3, 16))
LEBAR_DARI_KELILING = tuple(range(2, 9))
PANJANG_MAKS_DARI_KELILING = 16
LEBAR_GABUNG = tuple(range(2, 7))
PANJANG_GABUNG_MAKS = (10, 11)  # p2 sampai 10, p1 sampai 11
PANJANG_L = tuple(range(6, 15))
LEBAR_L_MIN = 4
POTONG_L = (2, 3)

# Varian tambahan: batas angka (semua <= 50 satuan).
TANYA_SEGITIGA = ("keliling_sembarang", "keliling_sama_kaki", "keliling_sama_sisi",
                  "cari_sisi_ketiga", "cari_sisi_sama_sisi", "cari_alas_sama_kaki")
TANYA_JAJAR = ("jajar_genjang", "jajar_genjang_tinggi", "belah_ketupat",
               "cari_sisi_belah_ketupat", "layang_layang")
TANYA_TRAPESIUM = ("trapesium_sembarang", "trapesium_sama_kaki",
                   "trapesium_sama_kaki_tinggi")
TANYA_LINGKARAN = ("keliling_dari_jari", "keliling_dari_diameter",
                   "keliling_setengah_lingkaran")
BENTUK_TUA = ("tangga", "huruf_U", "huruf_T")
SISI_SEGITIGA_MAKS = 10
KAKI_SEGITIGA = tuple(range(3, 9))
ALAS_SEGITIGA_MAKS = 12
SISI_SAMA_SISI = tuple(range(2, 31))
ALAS_JAJAR = tuple(range(3, 13))
SISI_JAJAR_TINGGI = ((6, 5, 3), (6, 5, 4), (8, 5, 4), (8, 7, 4), (10, 7, 4), (10, 9, 4),
                     (12, 9, 4), (12, 5, 3))  # (alas, sisi miring, tinggi), tinggi < sisi miring
SISI_LAYANG = tuple(range(3, 13))
SEJAJAR_ATAS = tuple(range(3, 7))
SELISIH_SEJAJAR = (2, 3, 4)
KAKI_TRAPESIUM = tuple(range(3, 9))
SELISIH_SAMA_KAKI = (2, 4, 6)
TRIPEL_TRAPESIUM = ((5, 4, 3), (10, 8, 6), (13, 12, 5), (15, 12, 9), (17, 15, 8))  # kaki, tinggi, proyeksi
ATAS_TRAPESIUM_TINGGI = tuple(range(4, 10))
PI_LINGKARAN = {"22/7": Fraction(22, 7), "3,14": Fraction(314, 100)}
PI_SALAH = {"22/7": Fraction(314, 100), "3,14": Fraction(3)}
JARI_PI = {"22/7": (7, 14, 21, 28, 35), "3,14": (10, 20, 30, 40, 50)}
DIAMETER_PI = {"22/7": (14, 28, 42), "3,14": (10, 20, 30, 40, 50)}
BANYAK_TANGGA = (2, 3, 4)
UKURAN_TANGGA = (2, 3, 4, 5)
PALANG_T = ((8, (2, 4)), (10, (2, 4, 6)), (12, (2, 4, 6)))  # (lebar palang, lebar tiang)
TINGGI_PALANG_T = (2, 3, 4)
TINGGI_TIANG_T = (6, 8, 10)
LEBAR_U = ((8, (2, 4)), (10, (2, 4, 6)), (12, (2, 4, 6)))  # (lebar luar, lebar celah)
TINGGI_U = (8, 10, 12)
DALAM_CELAH_U = (3, 4, 5)


# ── domain eksplisit dan validasi ────────────────────────────────────────

def _enumerasi() -> tuple:
    hasil = []
    for u in SATUAN:
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "keliling_persegi",
                   "satuan": u, "sisi": s} for s in SISI_PERSEGI]
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "keliling_persegipanjang",
                   "satuan": u, "panjang": p, "lebar": l}
                  for p in PANJANG_PP for l in range(2, p)]
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "sisi_dari_keliling",
                   "satuan": u, "sisi": s} for s in SISI_PERSEGI]
        hasil += [{"varian": "persegi_persegipanjang", "tanya": "panjang_dari_keliling",
                   "satuan": u, "panjang": p, "lebar": l}
                  for l in LEBAR_DARI_KELILING
                  for p in range(l + 1, PANJANG_MAKS_DARI_KELILING + 1)]
        hasil += [{"varian": "dua_persegipanjang", "satuan": u, "lebar": w,
                   "panjang1": p1, "panjang2": p2}
                  for w in LEBAR_GABUNG
                  for p2 in range(w + 1, PANJANG_GABUNG_MAKS[0] + 1)
                  for p1 in range(p2 + 1, PANJANG_GABUNG_MAKS[1] + 1)]
        hasil += [{"varian": "bentuk_L", "satuan": u, "panjang": p, "lebar": l,
                   "potong": s}
                  for p in PANJANG_L for l in range(LEBAR_L_MIN, p) for s in POTONG_L]
        hasil += [{"varian": "segitiga_sama_sisi_di_persegi", "satuan": u, "sisi": s}
                  for s in SISI_PERSEGI]
    return tuple(hasil) + _enumerasi_baru()


def _enumerasi_baru() -> tuple:
    """Varian tambahan; selalu SETELAH seluruh parameter lama (append-only)."""
    hasil = []
    for u in SATUAN:
        for varian, daftar in (("segitiga", _segitiga_param()),
                               ("jajar_genjang_belah_ketupat", _jajar_param()),
                               ("trapesium", _trapesium_param()),
                               ("lingkaran", _lingkaran_param()),
                               ("bentuk_T_U_tangga", _bentuk_param())):
            hasil += [{"varian": varian, "satuan": u, **d} for d in daftar]
    return tuple(hasil)


def _segitiga_param() -> list:
    r = range(3, SISI_SEGITIGA_MAKS + 1)
    tiga = [(a, b, c) for a in r for b in r for c in r if a < b < c < a + b]
    hasil = [{"tanya": "keliling_sembarang", "a": a, "b": b, "c": c} for a, b, c in tiga]
    hasil += [{"tanya": "keliling_sama_kaki", "kaki": k, "alas": a}
              for k in KAKI_SEGITIGA for a in range(2, min(2 * k - 1, ALAS_SEGITIGA_MAKS) + 1)
              if a != k]
    hasil += [{"tanya": "keliling_sama_sisi", "sisi": s} for s in SISI_SAMA_SISI]
    hasil += [{"tanya": "cari_sisi_ketiga", "a": a, "b": b, "c": c} for a, b, c in tiga]
    hasil += [{"tanya": "cari_sisi_sama_sisi", "sisi": s} for s in SISI_SAMA_SISI]
    hasil += [{"tanya": "cari_alas_sama_kaki", "kaki": k, "alas": a}
              for k in KAKI_SEGITIGA for a in range(2, min(2 * k - 1, ALAS_SEGITIGA_MAKS) + 1)
              if a != k]
    return hasil


def _jajar_param() -> list:
    hasil = [{"tanya": "jajar_genjang", "alas": a, "miring": b}
             for a in ALAS_JAJAR for b in ALAS_JAJAR if a != b]
    hasil += [{"tanya": "jajar_genjang_tinggi", "alas": a, "miring": b, "tinggi": t}
              for a, b, t in SISI_JAJAR_TINGGI]
    hasil += [{"tanya": "belah_ketupat", "sisi": s} for s in SISI_SAMA_SISI]
    hasil += [{"tanya": "cari_sisi_belah_ketupat", "sisi": s} for s in SISI_SAMA_SISI]
    hasil += [{"tanya": "layang_layang", "pendek": a, "panjang": b}
              for a in SISI_LAYANG for b in SISI_LAYANG if a < b]
    return hasil


def _trapesium_param() -> list:
    hasil = [{"tanya": "trapesium_sembarang", "atas": a, "bawah": a + s, "kaki1": c,
              "kaki2": d}
             for a in SEJAJAR_ATAS for s in SELISIH_SEJAJAR
             for c in KAKI_TRAPESIUM for d in KAKI_TRAPESIUM if d - c < s < c + d and c < d]
    hasil += [{"tanya": "trapesium_sama_kaki", "atas": a, "bawah": a + s, "kaki": c}
              for a in SEJAJAR_ATAS for s in SELISIH_SAMA_KAKI
              for c in KAKI_TRAPESIUM if s < 2 * c]
    hasil += [{"tanya": "trapesium_sama_kaki_tinggi", "atas": a, "bawah": a + 2 * pr,
               "kaki": c, "tinggi": t}
              for c, t, pr in TRIPEL_TRAPESIUM for a in ATAS_TRAPESIUM_TINGGI]
    return hasil


def _lingkaran_param() -> list:
    hasil = []
    for pi in PI_LINGKARAN:
        hasil += [{"tanya": "keliling_dari_jari", "pi": pi, "jari": r} for r in JARI_PI[pi]]
        hasil += [{"tanya": "keliling_dari_diameter", "pi": pi, "diameter": d}
                  for d in DIAMETER_PI[pi]]
        hasil += [{"tanya": "keliling_setengah_lingkaran", "pi": pi, "jari": r}
                  for r in JARI_PI[pi]]
    return hasil


def _bentuk_param() -> list:
    hasil = [{"bentuk": "tangga", "anak_tangga": n, "lebar": m, "tinggi": h}
             for n in BANYAK_TANGGA for m in UKURAN_TANGGA for h in UKURAN_TANGGA]
    hasil += [{"bentuk": "huruf_U", "lebar": w, "tinggi": h, "celah": g, "dalam": d}
              for w, celah in LEBAR_U for g in celah for h in TINGGI_U for d in DALAM_CELAH_U]
    hasil += [{"bentuk": "huruf_T", "palang": w, "tinggi_palang": a, "tiang": t,
               "tinggi_tiang": h}
              for w, tiang in PALANG_T for t in tiang for a in TINGGI_PALANG_T
              for h in TINGGI_TIANG_T]
    return hasil


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
    """Hanya int/str murni: 4.0 dan True sama-hash dengan 4 sehingga harus ditolak lebih dulu."""
    return all(type(v) in (int, str) for v in p.values())


def _sah(p: dict) -> bool:
    return _tipe_polos(p) and _kanon(p) in _himpunan_sah()


@lru_cache(maxsize=None)
def _peta_varian() -> tuple:
    """((varian, (kelompok, ...)), ...); kelompok = tuple item parameter, per `tanya`."""
    hasil = []
    for varian in VARIAN:
        kelompok = {}
        for item in _domain_beku():
            p = dict(item)
            if p["varian"] == varian:
                kelompok.setdefault(p.get("tanya") or p.get("bentuk", ""), []).append(item)
        hasil.append((varian, tuple(tuple(v) for v in kelompok.values())))
    return tuple(hasil)


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level keliling gabungan harus P5")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku())


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu sub-bentuk seragam, lalu satu parameter seragam; hanya dari rng."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    kelompok = dict(_peta_varian())[varian]
    return dict(rng.choice(rng.choice(kelompok)))


# ── malrule ──────────────────────────────────────────────────────────────

def _fmt(nilai) -> str:
    """Bilangan bulat polos atau desimal berkoma (paling banyak dua angka), tanpa nol buntut."""
    if isinstance(nilai, int):
        return str(nilai)
    senti = Fraction(nilai) * 100
    if senti.denominator != 1:
        raise ValueError("hasil bukan desimal pendek")
    bulat, sisa = divmod(int(senti), 100)
    return str(bulat) if sisa == 0 else f"{bulat},{sisa:02d}".rstrip("0")


def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", _fmt(jawaban), kode, alasan)


def _kandidat_persegi(s: int) -> list:
    return [
        _mal("luas_bukan_keliling", s * s, "K",
             f"Menghitung luas persegi ({s} × {s} = {s * s}), bukan keliling."),
        _mal("hanya_dua_sisi", 2 * s, "K",
             f"Menjumlah hanya dua sisi ({2 * s}), kemungkinan lupa bahwa persegi punya "
             "empat sisi."),
        _mal("satu_sisi_terlewat", 3 * s, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi terlewat "
             f"sehingga jawabannya {3 * s}."),
        _mal("satu_sisi_berlebih", 5 * s, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi terhitung dua "
             f"kali sehingga jawabannya {5 * s}."),
    ]


def _kandidat_persegipanjang(p: int, l: int) -> list:
    kunci = 2 * (p + l)
    return [
        _mal("luas_bukan_keliling", p * l, "K",
             f"Menghitung luas ({p} × {l} = {p * l}), bukan keliling."),
        _mal("hanya_panjang_ditambah_lebar", p + l, "K",
             f"Menjumlah panjang dan lebar saja ({p + l}), lupa dua sisi lainnya."),
        _mal("hanya_dua_sisi_panjang", 2 * p, "K",
             f"Menjumlah dua sisi panjang saja ({2 * p}), lupa dua sisi lebar."),
        _mal("satu_sisi_lebar_terlewat", kunci - l, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi lebar terlewat "
             f"sehingga jawabannya {kunci - l}."),
        _mal("satu_sisi_lebar_berlebih", kunci + l, "H",
             f"Sudah tahu kelilingnya jumlah semua sisi, tetapi satu sisi lebar terhitung "
             f"dua kali sehingga jawabannya {kunci + l}."),
    ]


def _kandidat_sisi_dari_keliling(s: int) -> list:
    return [
        _mal("dibagi_dua_bukan_empat", 2 * s, "K",
             f"Membagi keliling dengan 2, bukan dengan 4, sehingga jawabannya {2 * s}."),
        _mal("keliling_ditulis_ulang", 4 * s, "K",
             f"Menulis angka kelilingnya saja ({4 * s}), belum mencari panjang sisi."),
        _mal("sisi_lebih_satu", s + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{s + 1}."),
        _mal("sisi_kurang_satu", s - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{s - 1}."),
    ]


def _kandidat_panjang_dari_keliling(p: int, l: int) -> list:
    keliling = 2 * (p + l)
    return [
        _mal("lebar_belum_dikurangkan", p + l, "K",
             f"Membagi keliling dengan 2 ({p + l}) tetapi lupa mengurangkan lebar."),
        _mal("lebar_dikurangkan_dari_keliling", keliling - l, "K",
             f"Mengurangkan lebar dari keliling ({keliling - l}) tanpa membagi dua dulu."),
        _mal("lebar_disebut", l, "K", f"Menyebut lebar ({l}), bukan panjang."),
        _mal("panjang_lebih_satu", p + 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{p + 1}."),
        _mal("panjang_kurang_satu", p - 1, "H",
             f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
             f"{p - 1}."),
    ]


def _kandidat_dua_pp(w: int, p1: int, p2: int) -> list:
    kunci = 2 * (p1 + p2 + w)
    return [
        _mal("sisi_menempel_ikut_dihitung", kunci + 2 * w, "K",
             f"Menjumlah keliling kedua persegi panjang ({kunci + 2 * w}), sehingga sisi "
             "yang menempel ikut terhitung."),
        _mal("luas_bukan_keliling", (p1 + p2) * w, "K",
             f"Menghitung luas bangun gabungan ({p1 + p2} × {w} = {(p1 + p2) * w}), "
             "bukan keliling."),
        _mal("hanya_setengah_keliling", p1 + p2 + w, "K",
             f"Menjumlah panjang gabungan dan satu lebar saja ({p1 + p2 + w}), lupa dua "
             "sisi lainnya."),
        _mal("satu_sisi_lebar_terlewat", kunci - w, "H",
             f"Sudah mengerti caranya, tetapi satu sisi lebar terlewat sehingga "
             f"jawabannya {kunci - w}."),
        _mal("satu_sisi_lebar_berlebih", kunci + w, "H",
             f"Sudah mengerti caranya, tetapi satu sisi lebar terhitung dua kali "
             f"sehingga jawabannya {kunci + w}."),
    ]


def _kandidat_bentuk_l(p: int, l: int, s: int) -> list:
    kunci = 2 * (p + l)
    return [
        _mal("luas_bangun_l_bukan_keliling", p * l - s * s, "K",
             f"Menghitung luas bangun L ({p * l} − {s * s} = {p * l - s * s}), bukan "
             "keliling."),
        _mal("potongan_dikira_memperpendek", kunci - 2 * s, "K",
             f"Mengira bagian yang dipotong mengurangi keliling sebesar 2 × {s} tanpa "
             f"menghitung dua sisi baru bekas potongan ({kunci - 2 * s})."),
        _mal("sisi_potongan_ditambah_saja", kunci + 2 * s, "K",
             f"Menambah dua sisi bekas potongan tanpa mengurangi bagian yang hilang "
             f"({kunci + 2 * s})."),
        _mal("satu_sisi_potongan_terlewat", kunci - s, "H",
             f"Sudah mengerti caranya, tetapi satu sisi bekas potongan terlewat "
             f"sehingga jawabannya {kunci - s}."),
        _mal("satu_sisi_potongan_berlebih", kunci + s, "H",
             f"Sudah mengerti caranya, tetapi satu sisi bekas potongan terhitung dua "
             f"kali sehingga jawabannya {kunci + s}."),
    ]


def _kandidat_atap(s: int) -> list:
    return [
        _mal("sisi_menempel_ikut_dihitung", 7 * s, "K",
             f"Menjumlah semua sisi persegi dan segitiga ({7 * s}), sehingga sisi yang "
             "menempel ikut terhitung."),
        _mal("sisi_segitiga_terlupa", 4 * s, "K",
             f"Hanya menghitung keliling persegi ({4 * s}), lupa sisi segitiga."),
        _mal("luas_persegi_bukan_keliling", s * s, "K",
             f"Menghitung luas persegi ({s} × {s} = {s * s}), bukan keliling."),
        _mal("sisi_menempel_terhitung_sekali", 6 * s, "H",
             f"Sudah mengerti caranya, tetapi satu sisi yang menempel masih terhitung "
             f"sekali sehingga jawabannya {6 * s}."),
    ]


# ── kunci, teks, pembahasan per bentuk ───────────────────────────────────

def _persegi(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    kunci = 4 * s
    teks = f"Sebuah persegi mempunyai panjang sisi {s} {u}. Berapa {u} keliling persegi itu?"
    pembahasan = (f"Keliling persegi = 4 × sisi. Sisinya {s} {u}, jadi kelilingnya "
                  f"4 × {s} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_persegi(s)


def _persegipanjang(p: dict) -> tuple:
    pj, l, u = p["panjang"], p["lebar"], p["satuan"]
    kunci = 2 * (pj + l)
    teks = (f"Sebuah persegi panjang mempunyai panjang {pj} {u} dan lebar {l} {u}. "
            f"Berapa {u} keliling persegi panjang itu?")
    pembahasan = (f"Keliling persegi panjang = 2 × (panjang + lebar). Jadi kelilingnya "
                  f"2 × ({pj} + {l}) = 2 × {pj + l} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_persegipanjang(pj, l)


def _sisi_dari_keliling(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    keliling = 4 * s
    teks = (f"Keliling sebuah persegi adalah {keliling} {u}. Berapa {u} panjang sisi "
            "persegi itu?")
    pembahasan = (f"Persegi punya 4 sisi yang sama panjang, jadi keliling = 4 × sisi. "
                  f"Sisinya = {keliling} ÷ 4 = {s} {u}. Jadi jawabannya {s}.")
    return teks, s, pembahasan, _kandidat_sisi_dari_keliling(s)


def _panjang_dari_keliling(p: dict) -> tuple:
    pj, l, u = p["panjang"], p["lebar"], p["satuan"]
    keliling = 2 * (pj + l)
    teks = (f"Keliling sebuah persegi panjang adalah {keliling} {u} dan lebarnya {l} {u}. "
            f"Berapa {u} panjang sisinya yang lebih panjang?")
    pembahasan = (f"Keliling = 2 × (panjang + lebar), jadi panjang + lebar = {keliling} ÷ 2 "
                  f"= {pj + l} {u}. Lebarnya {l} {u}, jadi panjangnya {pj + l} − {l} = "
                  f"{pj} {u}. Jadi jawabannya {pj}.")
    return teks, pj, pembahasan, _kandidat_panjang_dari_keliling(pj, l)


_PERSEGI_PERSEGIPANJANG = {
    "keliling_persegi": _persegi, "keliling_persegipanjang": _persegipanjang,
    "sisi_dari_keliling": _sisi_dari_keliling,
    "panjang_dari_keliling": _panjang_dari_keliling,
}


def _dua_persegipanjang(p: dict) -> tuple:
    w, p1, p2, u = p["lebar"], p["panjang1"], p["panjang2"], p["satuan"]
    gabung = p1 + p2
    kunci = 2 * (gabung + w)
    teks = (f"Persegi panjang pertama panjangnya {p1} {u} dan lebarnya {w} {u}. Persegi "
            f"panjang kedua panjangnya {p2} {u} dan lebarnya {w} {u}. Keduanya disambung "
            f"rapat pada sisi lebarnya ({w} {u}) tanpa saling menumpuk sehingga membentuk "
            f"satu persegi panjang yang lebih besar. Berapa {u} keliling bangun gabungan "
            "itu?")
    pembahasan = (f"Sisi {w} {u} yang saling menempel tidak ikut menjadi keliling. Bangun "
                  f"gabungannya berupa persegi panjang dengan panjang {p1} + {p2} = "
                  f"{gabung} {u} dan lebar {w} {u}. Keliling = 2 × ({gabung} + {w}) = "
                  f"{kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_dua_pp(w, p1, p2)


def _bentuk_l(p: dict) -> tuple:
    pj, l, s, u = p["panjang"], p["lebar"], p["potong"], p["satuan"]
    kunci = 2 * (pj + l)
    teks = (f"Sebuah persegi panjang mempunyai panjang {pj} {u} dan lebar {l} {u}. Pada "
            f"salah satu pojoknya dipotong sebuah persegi kecil dengan sisi {s} {u} "
            f"sehingga bangunnya berbentuk huruf L. Berapa {u} keliling bangun berbentuk "
            "L itu?")
    pembahasan = (f"Keliling bangun L sama dengan keliling persegi panjang asalnya. Bagian "
                  f"yang dipotong mengurangi {s} {u} dari panjang dan {s} {u} dari lebar, "
                  f"tetapi menambah dua sisi baru yang masing-masing {s} {u}. "
                  f"Kelilingnya 2 × ({pj} + {l}) = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_bentuk_l(pj, l, s)


def _atap(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    kunci = 5 * s
    teks = (f"Sebuah persegi mempunyai panjang sisi {s} {u}. Pada salah satu sisinya "
            f"ditempelkan sebuah segitiga sama sisi yang panjang sisinya juga {s} {u}, "
            f"tepat berimpit dengan sisi persegi itu (seperti atap rumah). Berapa {u} "
            "keliling bangun gabungan itu?")
    pembahasan = (f"Persegi punya 4 sisi, tetapi satu sisinya menempel pada segitiga "
                  f"sehingga tidak ikut keliling. Sisi luar yang tersisa adalah 3 sisi "
                  f"persegi dan 2 sisi segitiga, jadi ada 5 sisi sepanjang {s} {u}. "
                  f"Keliling = 5 × {s} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, _kandidat_atap(s)


# ── varian tambahan: malrule, teks, pembahasan ───────────────────────────

def _k(nama: str, jawaban, alasan: str) -> Malrule:
    return _mal(nama, jawaban, "K", alasan)


def _meleset(kunci) -> list:
    """Dua jalur H: hitungan meleset satu ke atas atau ke bawah."""
    return [_mal("hitungan_lebih_satu", kunci + 1, "H",
                 f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
                 f"{_fmt(kunci + 1)}."),
            _mal("hitungan_kurang_satu", kunci - 1, "H",
                 f"Sudah mengerti caranya, tetapi hitungan meleset satu sehingga jawabannya "
                 f"{_fmt(kunci - 1)}.")]


def _soal_baru(teks: str, kunci, pembahasan: str, kandidat: list) -> tuple:
    return teks, kunci, pembahasan, kandidat + _meleset(kunci)


def _jumlah_sisi(sisi: tuple, satuan: str, kunci) -> str:
    rumus = " + ".join(str(x) for x in sisi)
    return (f"Keliling = jumlah semua sisinya. Jadi kelilingnya {rumus} = {_fmt(kunci)} "
            f"{satuan}. Jadi jawabannya {_fmt(kunci)}.")


# segitiga

def _segitiga_sembarang(p: dict) -> tuple:
    a, b, c, u = p["a"], p["b"], p["c"], p["satuan"]
    kunci = a + b + c
    teks = (f"Sebuah segitiga mempunyai sisi-sisi sepanjang {a} {u}, {b} {u}, dan {c} {u}. "
            f"Berapa {u} keliling segitiga itu?")
    return _soal_baru(teks, kunci, _jumlah_sisi((a, b, c), u, kunci), [
        _k("sisi_terpanjang_terlupa", a + b, f"Menjumlah dua sisi terpendek saja ({a + b}), "
           "sisi yang terpanjang terlewat."),
        _k("sisi_terpendek_terlupa", b + c, f"Menjumlah dua sisi terpanjang saja ({b + c}), "
           "sisi yang terpendek terlewat."),
        _k("semua_sisi_dikira_sama", 3 * c, f"Mengira ketiga sisi sama panjang seperti sisi "
           f"terpanjang (3 × {c} = {3 * c})."),
    ])


def _segitiga_sama_kaki(p: dict) -> tuple:
    k, a, u = p["kaki"], p["alas"], p["satuan"]
    kunci = 2 * k + a
    teks = (f"Sebuah segitiga sama kaki mempunyai dua kaki yang sama panjang, masing-masing "
            f"{k} {u}, dan alas {a} {u}. Berapa {u} keliling segitiga itu?")
    return _soal_baru(teks, kunci, _jumlah_sisi((k, k, a), u, kunci), [
        _k("satu_kaki_terlupa", k + a, f"Menjumlah satu kaki dan alas ({k + a}); kaki yang "
           "kedua terlewat."),
        _k("kaki_saja", 2 * k, f"Menjumlah dua kaki saja ({2 * k}); alas terlewat."),
        _k("semua_dikira_kaki", 3 * k, f"Mengira ketiga sisi sama panjang seperti kaki "
           f"(3 × {k} = {3 * k})."),
        _k("semua_dikira_alas", 3 * a, f"Mengira ketiga sisi sama panjang seperti alas "
           f"(3 × {a} = {3 * a})."),
    ])


def _segitiga_sama_sisi(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    kunci = 3 * s
    teks = (f"Sebuah segitiga sama sisi mempunyai panjang sisi {s} {u}. Berapa {u} keliling "
            "segitiga itu?")
    pembahasan = (f"Segitiga sama sisi punya 3 sisi yang sama panjang, jadi keliling = 3 × sisi. "
                  f"Kelilingnya 3 × {s} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("satu_sisi_saja", s, f"Menyebut panjang satu sisi saja ({s})."),
        _k("dua_sisi_saja", 2 * s, f"Menjumlah dua sisi saja ({2 * s}); satu sisi terlewat."),
        _k("empat_sisi_seperti_persegi", 4 * s, f"Mengira segitiga punya empat sisi seperti "
           f"persegi (4 × {s} = {4 * s})."),
        _k("sisi_dikali_sisi", s * s, f"Mengalikan sisi dengan sisi ({s} × {s} = {s * s}), "
           "bukan menjumlah ketiga sisi."),
    ])


def _cari_sisi_ketiga(p: dict) -> tuple:
    a, b, c, u = p["a"], p["b"], p["c"], p["satuan"]
    keliling = a + b + c
    teks = (f"Keliling sebuah segitiga adalah {keliling} {u}. Dua sisinya panjangnya {a} {u} "
            f"dan {b} {u}. Berapa {u} panjang sisi yang ketiga?")
    pembahasan = (f"Keliling = jumlah ketiga sisi, jadi sisi ketiga = keliling dikurangi dua "
                  f"sisi yang sudah diketahui. Sisi ketiga = {keliling} − {a} − {b} = {c} {u}. "
                  f"Jadi jawabannya {c}.")
    return _soal_baru(teks, c, pembahasan, [
        _k("hanya_satu_sisi_dikurangkan", keliling - a, f"Mengurangkan satu sisi saja dari "
           f"keliling ({keliling - a}); sisi yang lain belum dikurangkan."),
        _k("hanya_sisi_lain_dikurangkan", keliling - b, f"Mengurangkan satu sisi saja dari "
           f"keliling ({keliling - b}); sisi yang lain belum dikurangkan."),
        _k("dua_sisi_dijumlah", a + b, f"Menjumlah dua sisi yang sudah diketahui ({a + b}), "
           "bukan mencari sisi yang ketiga."),
        _k("keliling_ditulis_ulang", keliling, f"Menulis angka kelilingnya saja ({keliling})."),
    ])


def _cari_sisi_sama_sisi(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    keliling = 3 * s
    teks = (f"Keliling sebuah segitiga sama sisi adalah {keliling} {u}. Berapa {u} panjang "
            "sisi segitiga itu?")
    pembahasan = (f"Segitiga sama sisi punya 3 sisi yang sama panjang, jadi keliling = 3 × "
                  f"sisi. Sisinya = {keliling} ÷ 3 = {s} {u}. Jadi jawabannya {s}.")
    kandidat = [
        _k("keliling_ditulis_ulang", keliling, f"Menulis angka kelilingnya saja ({keliling})."),
        _k("dikali_tiga_bukan_dibagi", 3 * keliling, f"Mengalikan keliling dengan 3 "
           f"({3 * keliling}), bukan membaginya."),
        _k("dikurangi_tiga_bukan_dibagi", keliling - 3, f"Mengurangi keliling dengan 3 "
           f"({keliling - 3}), bukan membaginya."),
    ]
    if keliling % 2 == 0:
        kandidat.append(_k("dibagi_dua_bukan_tiga", keliling // 2, f"Membagi keliling dengan "
                           f"2, bukan dengan 3, sehingga jawabannya {keliling // 2}."))
    return _soal_baru(teks, s, pembahasan, kandidat)


def _cari_alas_sama_kaki(p: dict) -> tuple:
    k, a, u = p["kaki"], p["alas"], p["satuan"]
    keliling = 2 * k + a
    teks = (f"Keliling sebuah segitiga sama kaki adalah {keliling} {u}. Panjang kedua "
            f"kakinya masing-masing {k} {u}. Berapa {u} panjang alasnya?")
    pembahasan = (f"Dua kaki bersama-sama sepanjang {k} + {k} = {2 * k} {u}. Alas = keliling "
                  f"dikurangi kedua kaki = {keliling} − {2 * k} = {a} {u}. "
                  f"Jadi jawabannya {a}.")
    return _soal_baru(teks, a, pembahasan, [
        _k("satu_kaki_dikurangkan", keliling - k, f"Mengurangkan satu kaki saja dari keliling "
           f"({keliling - k}); kaki yang kedua belum dikurangkan."),
        _k("keliling_ditulis_ulang", keliling, f"Menulis angka kelilingnya saja ({keliling})."),
        _k("dua_kaki_dijumlah", 2 * k, f"Menjumlah dua kaki ({2 * k}), bukan mencari alas."),
    ])


_SEGITIGA = {
    "keliling_sembarang": _segitiga_sembarang, "keliling_sama_kaki": _segitiga_sama_kaki,
    "keliling_sama_sisi": _segitiga_sama_sisi, "cari_sisi_ketiga": _cari_sisi_ketiga,
    "cari_sisi_sama_sisi": _cari_sisi_sama_sisi, "cari_alas_sama_kaki": _cari_alas_sama_kaki,
}


# jajar genjang, belah ketupat, layang-layang

def _jajar_genjang(p: dict) -> tuple:
    a, b, u = p["alas"], p["miring"], p["satuan"]
    kunci = 2 * (a + b)
    teks = (f"Sebuah jajar genjang mempunyai alas {a} {u} dan sisi miring {b} {u}. "
            f"Sisi-sisi yang berhadapan sama panjang. Berapa {u} keliling jajar genjang itu?")
    pembahasan = (f"Jajar genjang punya dua pasang sisi sejajar yang sama panjang, jadi "
                  f"keliling = 2 × (alas + sisi miring). Kelilingnya 2 × ({a} + {b}) = "
                  f"2 × {a + b} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("alas_kali_miring", a * b, f"Mengalikan alas dan sisi miring ({a} × {b} = {a * b}), "
           "bukan keliling."),
        _k("hanya_alas_dan_miring", a + b, f"Menjumlah alas dan sisi miring saja ({a + b}); "
           "dua sisi lainnya terlewat."),
        _k("semua_dikira_alas", 4 * a, f"Mengira keempat sisi sama dengan alas "
           f"(4 × {a} = {4 * a})."),
        _k("semua_dikira_miring", 4 * b, f"Mengira keempat sisi sama dengan sisi miring "
           f"(4 × {b} = {4 * b})."),
    ])


def _jajar_genjang_tinggi(p: dict) -> tuple:
    a, b, t, u = p["alas"], p["miring"], p["tinggi"], p["satuan"]
    kunci = 2 * (a + b)
    teks = (f"Sebuah jajar genjang mempunyai alas {a} {u}, sisi miring {b} {u}, dan tinggi "
            f"{t} {u}. Sisi-sisi yang berhadapan sama panjang. Berapa {u} keliling jajar "
            "genjang itu?")
    pembahasan = (f"Tinggi bukan salah satu sisi jajar genjang, jadi tidak ikut dijumlah. "
                  f"Keliling = 2 × (alas + sisi miring) = 2 × ({a} + {b}) = {kunci} {u}. "
                  f"Jadi jawabannya {kunci}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("tinggi_dipakai_sebagai_sisi", 2 * (a + t), f"Memakai tinggi sebagai sisi miring "
           f"(2 × ({a} + {t}) = {2 * (a + t)})."),
        _k("alas_kali_tinggi", a * t, f"Menghitung luas ({a} × {t} = {a * t}), bukan keliling."),
        _k("tiga_angka_dijumlah_dua_kali", 2 * (a + b + t), f"Menjumlah alas, sisi miring, dan "
           f"tinggi lalu menggandakannya ({2 * (a + b + t)})."),
        _k("hanya_alas_dan_miring", a + b, f"Menjumlah alas dan sisi miring saja ({a + b}); "
           "dua sisi lainnya terlewat."),
    ])


def _belah_ketupat(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    kunci = 4 * s
    teks = (f"Sebuah belah ketupat mempunyai empat sisi yang sama panjang, masing-masing "
            f"{s} {u}. Berapa {u} keliling belah ketupat itu?")
    pembahasan = (f"Belah ketupat punya 4 sisi yang sama panjang, jadi keliling = 4 × sisi. "
                  f"Kelilingnya 4 × {s} = {kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, [
        _k("sisi_dikali_sisi", s * s, f"Menghitung luas seperti persegi ({s} × {s} = {s * s}), "
           "bukan keliling."),
        _k("dua_sisi_saja", 2 * s, f"Menjumlah dua sisi saja ({2 * s}); dua sisi lainnya "
           "terlewat."),
        _k("satu_sisi_saja", s, f"Menyebut panjang satu sisi saja ({s})."),
        _mal("satu_sisi_terlewat", 3 * s, "H", f"Sudah tahu kelilingnya jumlah semua sisi, "
             f"tetapi satu sisi terlewat sehingga jawabannya {3 * s}."),
        _mal("satu_sisi_berlebih", 5 * s, "H", f"Sudah tahu kelilingnya jumlah semua sisi, "
             f"tetapi satu sisi terhitung dua kali sehingga jawabannya {5 * s}."),
    ]


def _cari_sisi_belah_ketupat(p: dict) -> tuple:
    s, u = p["sisi"], p["satuan"]
    keliling = 4 * s
    teks = (f"Keliling sebuah belah ketupat adalah {keliling} {u}. Berapa {u} panjang sisi "
            "belah ketupat itu?")
    pembahasan = (f"Belah ketupat punya 4 sisi yang sama panjang, jadi keliling = 4 × sisi. "
                  f"Sisinya = {keliling} ÷ 4 = {s} {u}. Jadi jawabannya {s}.")
    return _soal_baru(teks, s, pembahasan, [
        _k("dibagi_dua_bukan_empat", 2 * s, f"Membagi keliling dengan 2, bukan dengan 4, "
           f"sehingga jawabannya {2 * s}."),
        _k("keliling_ditulis_ulang", keliling, f"Menulis angka kelilingnya saja ({keliling})."),
    ])


def _layang_layang(p: dict) -> tuple:
    a, b, u = p["pendek"], p["panjang"], p["satuan"]
    kunci = 2 * (a + b)
    teks = (f"Sebuah layang-layang mempunyai dua sisi pendek yang sama panjang, masing-masing "
            f"{a} {u}, dan dua sisi panjang yang sama panjang, masing-masing {b} {u}. Berapa "
            f"{u} keliling layang-layang itu?")
    pembahasan = (f"Layang-layang punya dua sisi pendek dan dua sisi panjang. Keliling = "
                  f"2 × (sisi pendek + sisi panjang) = 2 × ({a} + {b}) = 2 × {a + b} = "
                  f"{kunci} {u}. Jadi jawabannya {kunci}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("satu_pasang_saja", a + b, f"Menjumlah satu sisi pendek dan satu sisi panjang "
           f"({a + b}); dua sisi lainnya terlewat."),
        _k("semua_dikira_pendek", 4 * a, f"Mengira keempat sisi sama dengan sisi pendek "
           f"(4 × {a} = {4 * a})."),
        _k("semua_dikira_panjang", 4 * b, f"Mengira keempat sisi sama dengan sisi panjang "
           f"(4 × {b} = {4 * b})."),
        _k("pendek_kali_panjang", a * b, f"Mengalikan sisi pendek dan sisi panjang "
           f"({a} × {b} = {a * b}), bukan keliling."),
    ])


_JAJAR = {
    "jajar_genjang": _jajar_genjang, "jajar_genjang_tinggi": _jajar_genjang_tinggi,
    "belah_ketupat": _belah_ketupat, "cari_sisi_belah_ketupat": _cari_sisi_belah_ketupat,
    "layang_layang": _layang_layang,
}


# trapesium

def _trapesium_sembarang(p: dict) -> tuple:
    a, b, c, d, u = p["atas"], p["bawah"], p["kaki1"], p["kaki2"], p["satuan"]
    kunci = a + b + c + d
    teks = (f"Sebuah trapesium mempunyai sepasang sisi sejajar dengan panjang {a} {u} dan "
            f"{b} {u}. Dua sisi miringnya panjangnya {c} {u} dan {d} {u}. Berapa {u} keliling "
            "trapesium itu?")
    return _soal_baru(teks, kunci, _jumlah_sisi((a, b, c, d), u, kunci), [
        _k("sisi_sejajar_saja", a + b, f"Menjumlah dua sisi sejajar saja ({a + b}); dua sisi "
           "miring terlewat."),
        _k("sisi_miring_saja", c + d, f"Menjumlah dua sisi miring saja ({c + d}); dua sisi "
           "sejajar terlewat."),
        _k("satu_sisi_miring_terlewat", a + b + c, f"Menjumlah tiga sisi saja ({a + b + c}); "
           "satu sisi miring terlewat."),
        _k("sisi_miring_lain_terlewat", a + b + d, f"Menjumlah tiga sisi saja ({a + b + d}); "
           "satu sisi miring terlewat."),
    ])


def _trapesium_sama_kaki(p: dict) -> tuple:
    a, b, c, u = p["atas"], p["bawah"], p["kaki"], p["satuan"]
    kunci = a + b + 2 * c
    teks = (f"Sebuah trapesium sama kaki mempunyai sisi sejajar {a} {u} dan {b} {u}. Kedua "
            f"kakinya sama panjang, masing-masing {c} {u}. Berapa {u} keliling trapesium itu?")
    return _soal_baru(teks, kunci, _jumlah_sisi((a, b, c, c), u, kunci), [
        _k("satu_kaki_terlewat", a + b + c, f"Menjumlah dua sisi sejajar dan satu kaki saja "
           f"({a + b + c}); kaki yang kedua terlewat."),
        _k("sisi_sejajar_saja", a + b, f"Menjumlah dua sisi sejajar saja ({a + b}); kedua kaki "
           "terlewat."),
        _k("kaki_saja", 2 * c, f"Menjumlah dua kaki saja ({2 * c}); dua sisi sejajar terlewat."),
        _k("dikira_jajar_genjang", 2 * (a + b), f"Memakai rumus jajar genjang "
           f"(2 × ({a} + {b}) = {2 * (a + b)}), padahal kaki trapesium bukan sisi sejajar."),
    ])


def _trapesium_sama_kaki_tinggi(p: dict) -> tuple:
    a, b, c, t, u = p["atas"], p["bawah"], p["kaki"], p["tinggi"], p["satuan"]
    kunci = a + b + 2 * c
    teks = (f"Sebuah trapesium sama kaki mempunyai sisi sejajar {a} {u} dan {b} {u}. Kedua "
            f"kakinya sama panjang, masing-masing {c} {u}, dan tingginya {t} {u}. Berapa {u} "
            "keliling trapesium itu?")
    pembahasan = (f"Tinggi bukan salah satu sisi trapesium, jadi tidak ikut dijumlah. Keliling "
                  f"= sisi sejajar + dua kaki = {a} + {b} + {c} + {c} = {kunci} {u}. "
                  f"Jadi jawabannya {kunci}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("tinggi_dikira_kaki", a + b + 2 * t, f"Memakai tinggi sebagai kaki "
           f"({a} + {b} + 2 × {t} = {a + b + 2 * t})."),
        _k("luas_bukan_keliling", (a + b) * t // 2, f"Menghitung luas trapesium "
           f"({(a + b) * t // 2}), bukan keliling."),
        _k("satu_kaki_terlewat", a + b + c, f"Menjumlah dua sisi sejajar dan satu kaki saja "
           f"({a + b + c}); kaki yang kedua terlewat."),
        _k("tinggi_ikut_dijumlah", kunci + t, f"Menjumlah keempat sisi lalu menambah tinggi "
           f"({kunci + t})."),
    ])


_TRAPESIUM = {
    "trapesium_sembarang": _trapesium_sembarang, "trapesium_sama_kaki": _trapesium_sama_kaki,
    "trapesium_sama_kaki_tinggi": _trapesium_sama_kaki_tinggi,
}


# lingkaran

def _lingkaran_jari(p: dict) -> tuple:
    r, pi, u = p["jari"], p["pi"], p["satuan"]
    nilai, salah = PI_LINGKARAN[pi], PI_SALAH[pi]
    kunci = 2 * nilai * r
    teks = (f"Sebuah lingkaran mempunyai jari-jari {r} {u}. Gunakan π = {pi}. Berapa {u} "
            "keliling lingkaran itu?")
    pembahasan = (f"Keliling lingkaran = 2 × π × jari-jari. Jadi kelilingnya 2 × {pi} × {r} = "
                  f"{_fmt(kunci)} {u}. Jadi jawabannya {_fmt(kunci)}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("jari_dipakai_seperti_diameter", nilai * r, f"Memakai rumus π × diameter dengan "
           f"jari-jari sebagai diameternya ({_fmt(nilai * r)})."),
        _k("luas_bukan_keliling", nilai * r * r, f"Menghitung luas lingkaran (π × {r} × {r} = "
           f"{_fmt(nilai * r * r)}), bukan keliling."),
        _k("nilai_pi_salah", 2 * salah * r, f"Memakai π = {_fmt(salah)} "
           f"sehingga jawabannya {_fmt(2 * salah * r)}."),
    ])


def _lingkaran_diameter(p: dict) -> tuple:
    d, pi, u = p["diameter"], p["pi"], p["satuan"]
    nilai, salah = PI_LINGKARAN[pi], PI_SALAH[pi]
    kunci = nilai * d
    r = Fraction(d, 2)
    teks = (f"Sebuah lingkaran mempunyai diameter {d} {u}. Gunakan π = {pi}. Berapa {u} "
            "keliling lingkaran itu?")
    pembahasan = (f"Keliling lingkaran = π × diameter. Jadi kelilingnya {pi} × {d} = "
                  f"{_fmt(kunci)} {u}. Jadi jawabannya {_fmt(kunci)}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("diameter_dipakai_seperti_jari", 2 * nilai * d, f"Memakai rumus 2 × π × jari-jari "
           f"dengan diameter sebagai jari-jarinya ({_fmt(2 * nilai * d)})."),
        _k("hanya_pi_kali_jari", nilai * r, f"Memakai π × jari-jari saja, lupa dikali 2 "
           f"({_fmt(nilai * r)})."),
        _k("luas_bukan_keliling", nilai * r * r, f"Menghitung luas lingkaran "
           f"({_fmt(nilai * r * r)}), bukan keliling."),
        _k("nilai_pi_salah", salah * d, f"Memakai π = {_fmt(salah)} sehingga jawabannya "
           f"{_fmt(salah * d)}."),
    ])


def _lingkaran_setengah(p: dict) -> tuple:
    r, pi, u = p["jari"], p["pi"], p["satuan"]
    nilai = PI_LINGKARAN[pi]
    busur = nilai * r
    kunci = busur + 2 * r
    teks = (f"Sebuah bangun berbentuk setengah lingkaran dengan jari-jari {r} {u}. Keliling "
            f"bangun itu adalah panjang lengkungannya ditambah panjang sisi lurusnya "
            f"(diameter). Gunakan π = {pi}. Berapa {u} keliling bangun itu?")
    pembahasan = (f"Lengkungannya setengah keliling lingkaran = π × jari-jari = {pi} × {r} = "
                  f"{_fmt(busur)} {u}. Sisi lurusnya diameter = 2 × {r} = {2 * r} {u}. Keliling "
                  f"= {_fmt(busur)} + {2 * r} = {_fmt(kunci)} {u}. Jadi jawabannya "
                  f"{_fmt(kunci)}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("lengkungan_saja", busur, f"Menghitung panjang lengkungan saja ({_fmt(busur)}); sisi "
           "lurusnya terlewat."),
        _k("lingkaran_penuh", 2 * busur, f"Menghitung keliling lingkaran penuh "
           f"({_fmt(2 * busur)}), bukan setengahnya ditambah sisi lurus."),
        _k("sisi_lurus_dikira_jari", busur + r, f"Menambah satu jari-jari, bukan diameter, "
           f"sebagai sisi lurus ({_fmt(busur + r)})."),
        _k("luas_setengah_lingkaran", nilai * r * r / 2, f"Menghitung luas setengah lingkaran "
           f"({_fmt(nilai * r * r / 2)}), bukan keliling."),
    ])


_LINGKARAN = {
    "keliling_dari_jari": _lingkaran_jari, "keliling_dari_diameter": _lingkaran_diameter,
    "keliling_setengah_lingkaran": _lingkaran_setengah,
}


# bentuk tangga, huruf U, huruf T

def _bentuk_tangga(p: dict) -> tuple:
    n, m, h, u = p["anak_tangga"], p["lebar"], p["tinggi"], p["satuan"]
    lebar, tinggi = n * m, n * h
    kunci = 2 * (lebar + tinggi)
    teks = (f"Sebuah bangun berbentuk tangga memiliki {n} anak tangga. Sisi bawahnya datar "
            f"dan sisi kirinya tegak lurus. Dari kiri ke kanan, setiap anak tangga lebarnya "
            f"{m} {u} dan lebih rendah {h} {u} daripada anak tangga di sebelah kirinya, "
            f"sedangkan anak tangga paling kanan tingginya {h} {u}. Berapa {u} keliling "
            "bangun itu?")
    pembahasan = (f"Lebar seluruh bangun {n} × {m} = {lebar} {u} dan tingginya {n} × {h} = "
                  f"{tinggi} {u}. Pada sisi bergerigi, kalau semua bagian datarnya "
                  f"digabung dan semua bagian tegaknya digabung, panjangnya sama dengan lebar dan "
                  f"tinggi tadi. Jadi kelilingnya sama dengan keliling persegi panjang {lebar} × "
                  f"{tinggi}: 2 × ({lebar} + {tinggi}) = {kunci} {u}. Jadi jawabannya {kunci}.")
    luas = m * h * n * (n + 1) // 2
    return _soal_baru(teks, kunci, pembahasan, [
        _k("luas_tangga", luas, f"Menghitung luas bangun tangga ({luas}), bukan keliling."),
        _k("sisi_bergerigi_terlewat", lebar + tinggi, f"Menjumlah sisi bawah dan sisi kiri saja "
           f"({lebar + tinggi}); sisi bergerigi terlewat."),
        _k("tinggi_satu_anak_tangga", 2 * (lebar + h), f"Mengira tinggi bangun hanya setinggi "
           f"satu anak tangga (2 × ({lebar} + {h}) = {2 * (lebar + h)})."),
        _k("lebar_satu_anak_tangga", 2 * (m + tinggi), f"Mengira lebar bangun hanya selebar "
           f"satu anak tangga (2 × ({m} + {tinggi}) = {2 * (m + tinggi)})."),
    ])


def _bentuk_u(p: dict) -> tuple:
    w, h, g, d, u = p["lebar"], p["tinggi"], p["celah"], p["dalam"], p["satuan"]
    pembatas = 2 * (w + h)
    kunci = pembatas + 2 * d
    teks = (f"Sebuah bangun berbentuk huruf U dibuat dari persegi panjang berukuran {w} {u} × "
            f"{h} {u} (mendatar × tegak). Dari tengah sisi atasnya dibuang persegi panjang "
            f"berukuran {g} {u} × {d} {u} (mendatar × tegak), sehingga tersisa dua tiang yang "
            f"sama lebar. Berapa {u} keliling bangun itu?")
    pembahasan = (f"Keliling persegi panjang utuh 2 × ({w} + {h}) = {pembatas} {u}. Sisi atas "
                  f"sepanjang {g} {u} yang dibuang hilang dari keliling, tetapi dasar celah "
                  f"sepanjang {g} {u} muncul sebagai gantinya, dan dua dinding celah ikut "
                  f"menambah 2 × {d} = {2 * d} {u}. Kelilingnya {pembatas} + {2 * d} = "
                  f"{kunci} {u}. Jadi jawabannya {kunci}.")
    return teks, kunci, pembahasan, [
        _k("dinding_celah_terlupa", pembatas, f"Hanya menghitung keliling persegi panjang utuh "
           f"({pembatas}); dinding celah terlewat."),
        _k("luas_bangun_u", w * h - g * d, f"Menghitung luas bangun U ({w * h} − {g * d} = "
           f"{w * h - g * d}), bukan keliling."),
        _k("celah_dikira_memperpendek", pembatas - 2 * d, f"Mengira bagian yang dibuang "
           f"mengurangi keliling sebesar 2 × {d} ({pembatas - 2 * d})."),
        _k("sisi_atas_celah_masih_dihitung", kunci + g, f"Menambah dinding dan dasar celah "
           f"tanpa membuang sisi atas yang hilang ({kunci + g})."),
        _mal("satu_dinding_celah", pembatas + d, "H", f"Sudah mengerti caranya, tetapi satu "
             f"dinding celah terlewat sehingga jawabannya {pembatas + d}."),
    ] + _meleset(kunci)


def _bentuk_t(p: dict) -> tuple:
    w, a, t, h, u = p["palang"], p["tinggi_palang"], p["tiang"], p["tinggi_tiang"], p["satuan"]
    kunci = 2 * (w + a + h)
    teks = (f"Sebuah bangun berbentuk huruf T dibuat dari dua persegi panjang. Palang di atas "
            f"berukuran {w} {u} × {a} {u} (mendatar × tegak). Tiang di bawahnya berukuran "
            f"{t} {u} × {h} {u} (mendatar × tegak), menempel rapat di tengah sisi bawah "
            f"palang. Berapa {u} keliling bangun itu?")
    pembahasan = (f"Sisi bawah palang yang tidak tertutup tiang ({w - t} {u}) dan sisi bawah "
                  f"tiang ({t} {u}) bersama-sama sepanjang {w} {u}, sama dengan sisi atas "
                  f"palang. Jadi seluruh sisi mendatar 2 × {w}, dan seluruh sisi tegak "
                  f"2 × {a} + 2 × {h}. Kelilingnya 2 × ({w} + {a} + {h}) = {kunci} {u}. "
                  f"Jadi jawabannya {kunci}.")
    return _soal_baru(teks, kunci, pembahasan, [
        _k("dua_keliling_dijumlah", 2 * (w + a) + 2 * (t + h), f"Menjumlah keliling kedua "
           f"persegi panjang ({2 * (w + a) + 2 * (t + h)}), sehingga sisi yang menempel ikut "
           "terhitung."),
        _k("luas_bangun_t", w * a + t * h, f"Menghitung luas bangun T ({w * a + t * h}), bukan "
           "keliling."),
        _k("bawah_palang_terlewat", kunci - (w - t), f"Melewatkan sisi bawah palang yang tidak "
           f"tertutup tiang ({kunci - (w - t)})."),
        _k("sisi_tegak_tiang_terlewat", kunci - 2 * h, f"Melewatkan dua sisi tegak tiang "
           f"({kunci - 2 * h})."),
    ])


_BENTUK = {"tangga": _bentuk_tangga, "huruf_U": _bentuk_u, "huruf_T": _bentuk_t}


def _per_sub(peta: dict, kunci: str):
    def bangun(p: dict) -> tuple:
        return peta[p[kunci]](p)
    return bangun


_BANGUN_BARU = {
    "segitiga": _per_sub(_SEGITIGA, "tanya"),
    "jajar_genjang_belah_ketupat": _per_sub(_JAJAR, "tanya"),
    "trapesium": _per_sub(_TRAPESIUM, "tanya"),
    "lingkaran": _per_sub(_LINGKARAN, "tanya"),
    "bentuk_T_U_tangga": _per_sub(_BENTUK, "bentuk"),
}


def _bangun(p: dict) -> tuple:
    varian = p["varian"]
    if varian in _BANGUN_BARU:
        return _BANGUN_BARU[varian](p)
    if varian == "persegi_persegipanjang":
        return _PERSEGI_PERSEGIPANJANG[p["tanya"]](p)
    if varian == "dua_persegipanjang":
        return _dua_persegipanjang(p)
    if varian == "bentuk_L":
        return _bentuk_l(p)
    return _atap(p)


def keliling_gabungan(varian: str, **parameter) -> Soal:
    """Keliling persegi, persegi panjang, atau bangun gabungan; kunci dari parameter."""
    lengkap = {"varian": varian, **parameter}
    if not _sah(lengkap):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, pembahasan, kandidat = _bangun(lengkap)
    return Soal(
        template_id=TEMPLATE_ID, parameter=lengkap, teks=teks, kunci=_fmt(kunci),
        malrule=saring_malrule(_fmt(kunci), kandidat), pembahasan=pembahasan, bagian="A")
