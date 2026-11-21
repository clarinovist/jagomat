"""Matematika Awal, jenis `ukur_konversi_awal`: hubungan m-cm dan kg-g, teks saja (P3).

Enam bentuk soal (`varian`), semua berkunci angka bulat:
  - `m_ke_cm`: "2 m = ... cm" (m 1..9);
  - `cm_ke_m`: "700 cm = ... m" (kelipatan 100 cm, 100..900);
  - `kg_ke_g`: "3 kg = ... g" (kg 1..9);
  - `g_ke_kg`: "4.000 g = ... kg" (kelipatan 1.000 g, 1.000..9.000);
  - `sisa_potong`: "Tali 1 m dipotong 40 cm. Sisa tali ada ... cm." (potong 10..90 cm,
    kelipatan 10, benda tali/pita/selang);
  - `jumlah_campur`: "Sebuah kardus beratnya 2 kg 500 g. Berapa gram semuanya?"
    (kg 1..5, gram sisa kelipatan 100, 100..900, tiga benda).

Hubungan yang dipakai hanya `1 m = 100 cm` dan `1 kg = 1.000 g`; semua bilangan
bulat, tanpa desimal. Teks soal memakai titik ribuan gaya Indonesia (`4.000 g`),
sedangkan KUNCI dan malrule berupa angka polos ("3000"): jawaban "3.000" atau
"3000" sama-sama dianggap benar oleh `diagnosis.normalisasi`. Soal teks tanpa
gambar, jadi kecocokan dengan bab Pengukuran panjang dan berat hanya "sebagian".

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban: faktor konversi keliru atau tertukar antara m-cm dan kg-g, angka
tak diubah satuannya (semuanya K), serta salah hitung seperti lupa menambah bagian
gram, menjumlah alih-alih mengurangi, atau meleset satu puluhan (H, hanya bila
nyata berbeda dari kunci). Tiap parameter sah menyisakan minimal satu jalur K dan
minimal tiga pengecoh angka berbeda.

Domain kecil dan eksplisit (`domain_parameter`): sampler memilih `varian` seragam
dulu supaya `jumlah_campur` yang parameternya paling banyak tidak mendominasi
lembar, lalu satu parameter seragam dalam varian itu, semuanya dari `rng` (tanpa
`hash()`), sehingga seed yang sama menghasilkan soal yang sama lintas proses.
Daftar benda bersifat APPEND-ONLY menurut indeks: indeks ikut identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from school_numbers_common import ribuan
from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "ukur_konversi_awal"
LEVEL = ("P3",)
VARIAN = ("m_ke_cm", "cm_ke_m", "kg_ke_g", "g_ke_kg", "sisa_potong", "jumlah_campur")
CM_PER_M = 100
G_PER_KG = 1000
PESAN_LUAR_DOMAIN = "parameter ukur konversi awal di luar domain"

# APPEND-ONLY menurut indeks.
BENDA_POTONG = ("tali", "pita", "selang")
BENDA_BERAT = ("Sebuah kardus", "Sekantong beras", "Sebuah tas")

# Bidang parameter tiap varian dan nilai sahnya.
BIDANG = {
    "m_ke_cm": ("m",),
    "cm_ke_m": ("cm",),
    "kg_ke_g": ("kg",),
    "g_ke_kg": ("gram",),
    "sisa_potong": ("potong", "benda"),
    "jumlah_campur": ("kg", "sisa_g", "benda"),
}
NILAI_SAH = {
    ("m_ke_cm", "m"): tuple(range(1, 10)),
    ("cm_ke_m", "cm"): tuple(range(CM_PER_M, 10 * CM_PER_M, CM_PER_M)),
    ("kg_ke_g", "kg"): tuple(range(1, 10)),
    ("g_ke_kg", "gram"): tuple(range(G_PER_KG, 10 * G_PER_KG, G_PER_KG)),
    ("sisa_potong", "potong"): tuple(range(10, CM_PER_M, 10)),
    ("sisa_potong", "benda"): tuple(range(len(BENDA_POTONG))),
    ("jumlah_campur", "kg"): tuple(range(1, 6)),
    ("jumlah_campur", "sisa_g"): tuple(range(100, G_PER_KG, 100)),
    ("jumlah_campur", "benda"): tuple(range(len(BENDA_BERAT))),
}


def _sah(varian, isian: dict) -> bool:
    if type(varian) is not str or varian not in BIDANG:
        return False
    if set(isian) != set(BIDANG[varian]):
        return False
    return all(type(nilai) is int and nilai in NILAI_SAH[(varian, bidang)]
               for bidang, nilai in isian.items())


# ── kunci, teks, pembahasan, malrule ─────────────────────────────────────

def _kunci(varian: str, p: dict) -> int:
    if varian == "m_ke_cm":
        return p["m"] * CM_PER_M
    if varian == "cm_ke_m":
        return p["cm"] // CM_PER_M
    if varian == "kg_ke_g":
        return p["kg"] * G_PER_KG
    if varian == "g_ke_kg":
        return p["gram"] // G_PER_KG
    if varian == "sisa_potong":
        return CM_PER_M - p["potong"]
    return p["kg"] * G_PER_KG + p["sisa_g"]


def _teks(varian: str, p: dict) -> str:
    if varian == "m_ke_cm":
        return f"{p['m']} m = ... cm"
    if varian == "cm_ke_m":
        return f"{ribuan(p['cm'])} cm = ... m"
    if varian == "kg_ke_g":
        return f"{p['kg']} kg = ... g"
    if varian == "g_ke_kg":
        return f"{ribuan(p['gram'])} g = ... kg"
    if varian == "sisa_potong":
        benda = BENDA_POTONG[p["benda"]]
        return f"{benda.capitalize()} 1 m dipotong {p['potong']} cm. Sisa {benda} ada ... cm."
    return (f"{BENDA_BERAT[p['benda']]} beratnya {p['kg']} kg {p['sisa_g']} g. "
            "Berapa gram semuanya?")


def _pembahasan(varian: str, p: dict, kunci: int) -> str:
    if varian == "m_ke_cm":
        return (f"1 m sama dengan 100 cm. Jadi {p['m']} m sama dengan "
                f"{p['m']} × 100 cm = {ribuan(kunci)} cm.")
    if varian == "cm_ke_m":
        return (f"100 cm sama dengan 1 m. Jadi {ribuan(p['cm'])} cm dibagi 100 "
                f"menjadi {kunci} m.")
    if varian == "kg_ke_g":
        return (f"1 kg sama dengan 1.000 g. Jadi {p['kg']} kg sama dengan "
                f"{p['kg']} × 1.000 g = {ribuan(kunci)} g.")
    if varian == "g_ke_kg":
        return (f"1.000 g sama dengan 1 kg. Jadi {ribuan(p['gram'])} g dibagi 1.000 "
                f"menjadi {kunci} kg.")
    if varian == "sisa_potong":
        benda = BENDA_POTONG[p["benda"]]
        return (f"1 m sama dengan 100 cm. {benda.capitalize()} dipotong {p['potong']} cm, "
                f"jadi sisanya 100 − {p['potong']} = {kunci} cm.")
    kg = p["kg"] * G_PER_KG
    return (f"1 kg sama dengan 1.000 g, jadi {p['kg']} kg sama dengan {ribuan(kg)} g. "
            f"Lalu tambahkan {p['sisa_g']} g: {ribuan(kg)} + {p['sisa_g']} = {ribuan(kunci)} g.")


def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _kandidat_m_ke_cm(p: dict) -> list:
    m = p["m"]
    return [
        _mal("kali_10_bukan_100", m * 10, "K",
             f"Mengalikan dengan 10, bukan 100, sehingga jawabannya {m * 10}; "
             "kemungkinan mengira 1 m sama dengan 10 cm."),
        _mal("m_cm_tertukar_kg_g", m * G_PER_KG, "K",
             f"Mengalikan dengan 1.000 sehingga jawabannya {m * G_PER_KG}; kemungkinan "
             "menukar hubungan m dan cm dengan hubungan kg dan g."),
        _mal("angka_tetap", m, "K",
             f"Menulis angkanya saja ({m}) tanpa mengubah satuan dari m ke cm."),
    ]


def _kandidat_cm_ke_m(p: dict) -> list:
    cm = p["cm"]
    return [
        _mal("bagi_10_bukan_100", cm // 10, "K",
             f"Membagi dengan 10, bukan 100, sehingga jawabannya {cm // 10}; "
             "kemungkinan mengira 1 m sama dengan 10 cm."),
        _mal("kali_arah_terbalik", cm * CM_PER_M, "K",
             f"Mengalikan dengan 100 sehingga jawabannya {cm * CM_PER_M}; kemungkinan "
             "belum paham bahwa dari satuan kecil ke satuan besar harus dibagi."),
        _mal("angka_tetap", cm, "K",
             f"Menulis angkanya saja ({cm}) tanpa mengubah satuan dari cm ke m."),
    ]


def _kandidat_kg_ke_g(p: dict) -> list:
    kg = p["kg"]
    return [
        _mal("kg_g_tertukar_m_cm", kg * CM_PER_M, "K",
             f"Mengalikan dengan 100 sehingga jawabannya {kg * CM_PER_M}; kemungkinan "
             "menukar hubungan kg dan g dengan hubungan m dan cm."),
        _mal("kali_10_bukan_1000", kg * 10, "K",
             f"Mengalikan dengan 10, bukan 1.000, sehingga jawabannya {kg * 10}; "
             "kemungkinan mengira 1 kg sama dengan 10 g."),
        _mal("angka_tetap", kg, "K",
             f"Menulis angkanya saja ({kg}) tanpa mengubah satuan dari kg ke g."),
    ]


def _kandidat_g_ke_kg(p: dict) -> list:
    gram = p["gram"]
    return [
        _mal("g_kg_tertukar_cm_m", gram // CM_PER_M, "K",
             f"Membagi dengan 100 sehingga jawabannya {gram // CM_PER_M}; kemungkinan "
             "menukar hubungan g dan kg dengan hubungan cm dan m."),
        _mal("bagi_10_bukan_1000", gram // 10, "K",
             f"Membagi dengan 10, bukan 1.000, sehingga jawabannya {gram // 10}; "
             "kemungkinan mengira 1 kg sama dengan 10 g."),
        _mal("angka_tetap", gram, "K",
             f"Menulis angkanya saja ({gram}) tanpa mengubah satuan dari g ke kg."),
    ]


def _kandidat_sisa_potong(p: dict) -> list:
    potong, sisa = p["potong"], CM_PER_M - p["potong"]
    return [
        _mal("satu_m_seribu_cm", 1000 - potong, "K",
             f"Mengurangi {potong} dari 1.000 sehingga jawabannya {1000 - potong}; "
             "kemungkinan mengira 1 m sama dengan 1.000 cm."),
        _mal("dijumlah_bukan_dikurang", CM_PER_M + potong, "H",
             f"Sudah tahu 1 m = 100 cm, tetapi menambah {potong} cm, bukan mengurangi, "
             f"sehingga jawabannya {CM_PER_M + potong}."),
        _mal("selisih_lebih_satu_puluhan", sisa + 10, "H",
             f"Sudah mengerti caranya, tetapi hitungan sisa meleset satu puluhan "
             f"sehingga jawabannya {sisa + 10}."),
    ]


def _kandidat_jumlah_campur(p: dict) -> list:
    kg, g = p["kg"], p["sisa_g"]
    return [
        _mal("kg_g_tertukar_m_cm", kg * CM_PER_M + g, "K",
             f"Mengubah kg menjadi g dengan dikali 100, lalu menambah {g}, sehingga "
             f"jawabannya {kg * CM_PER_M + g}; kemungkinan mengira 1 kg sama dengan 100 g."),
        _mal("kali_10_bukan_1000", kg * 10 + g, "K",
             f"Mengubah kg menjadi g dengan dikali 10, lalu menambah {g}, sehingga "
             f"jawabannya {kg * 10 + g}; kemungkinan mengira 1 kg sama dengan 10 g."),
        _mal("kg_dan_g_dijumlah_langsung", kg + g, "K",
             f"Menjumlah {kg} dan {g} langsung ({kg + g}) tanpa mengubah kg menjadi g."),
        _mal("lupa_bagian_gram", kg * G_PER_KG, "H",
             f"Sudah mengubah {kg} kg menjadi {kg * G_PER_KG} g, tetapi lupa menambah "
             f"bagian {g} g."),
    ]


_KANDIDAT = {
    "m_ke_cm": _kandidat_m_ke_cm,
    "cm_ke_m": _kandidat_cm_ke_m,
    "kg_ke_g": _kandidat_kg_ke_g,
    "g_ke_kg": _kandidat_g_ke_kg,
    "sisa_potong": _kandidat_sisa_potong,
    "jumlah_campur": _kandidat_jumlah_campur,
}


def ukur_konversi_awal(varian: str, m: int | None = None, cm: int | None = None,
                       kg: int | None = None, gram: int | None = None,
                       potong: int | None = None, sisa_g: int | None = None,
                       benda: int | None = None) -> Soal:
    """Konversi m-cm / kg-g, sisa potongan, atau jumlah campuran (kunci dari parameter)."""
    isian = {nama: nilai for nama, nilai in (
        ("m", m), ("cm", cm), ("kg", kg), ("gram", gram),
        ("potong", potong), ("sisa_g", sisa_g), ("benda", benda)) if nilai is not None}
    if not _sah(varian, isian):
        raise ValueError(PESAN_LUAR_DOMAIN)
    parameter = {"varian": varian, **isian}
    kunci = _kunci(varian, isian)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter,
        teks=_teks(varian, isian), kunci=str(kunci),
        malrule=saring_malrule(str(kunci), _KANDIDAT[varian](isian)),
        pembahasan=_pembahasan(varian, isian, kunci), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi() -> tuple:
    hasil = []
    for varian in VARIAN:
        bidang = BIDANG[varian]
        kombinasi = [{}]
        for nama in bidang:
            kombinasi = [{**k, nama: v} for k in kombinasi for v in NILAI_SAH[(varian, nama)]]
        hasil.extend({"varian": varian, **k} for k in kombinasi)
    return tuple(hasil)


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level ukur konversi awal harus P3")


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
