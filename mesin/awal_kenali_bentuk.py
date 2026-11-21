"""Matematika Awal, jenis `kenali_bentuk`: mengenal bangun datar (P1/P2), teks saja.

Tiga bentuk soal (`varian`):
  - `dari_ciri`: "Bangun apa yang punya 3 sisi dan 3 sudut?" (jawaban: nama bangun);
  - `benda`: "Bentuk uang logam seperti bangun apa?" (jawaban: nama bangun);
  - `banyak_sisi`: "Berapa banyak sisi persegi panjang?" (jawaban: angka).

Himpunan bangun yang dikenal (`himpunan`, mengikuti level):
  - "dasar" (P1): segitiga, persegi, lingkaran;
  - "lengkap" (P2): ditambah persegi panjang, jadi ciri persegi harus
    membedakannya dari persegi panjang (semua sisi sama panjang).
Pilihan jawaban TIDAK tertulis di soal; jawaban dibaca dalam himpunan itu
(bangun lain seperti belah ketupat belum diperkenalkan pada kelas ini). Setiap
ciri dan benda menunjuk TEPAT SATU bangun dalam himpunannya, diuji solver
terpisah di `test_matematika_awal_domain`. Lingkaran tidak dipakai di
`banyak_sisi`: apakah lingkaran punya 0 atau 1 sisi masih diperdebatkan.

Kunci berupa teks huruf kecil ("persegi panjang") atau angka. Jawaban isian
dibandingkan lewat `diagnosis.normalisasi` (huruf besar-kecil dan spasi
berlebih dimaafkan); "persegipanjang" tanpa spasi dianggap salah.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis
pasti dari satu jawaban: bangun lain dalam himpunan (K) dan, pada
`banyak_sisi`, salah hitung lebih/kurang satu (H). Jalur K selalu ada.

Domain kecil dan eksplisit (`domain_parameter`): sampler hanya mengundi dari
domain itu memakai `rng` (tanpa `hash()`), jadi seed yang sama selalu
menghasilkan soal yang sama lintas proses. Daftar CIRI dan BENDA bersifat
APPEND-ONLY menurut indeks: indeks ikut dalam identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "kenali_bentuk"
LEVEL = ("P1", "P2")
VARIAN = ("dari_ciri", "benda", "banyak_sisi")
HIMPUNAN_LEVEL = {"P1": "dasar", "P2": "lengkap"}
BANGUN_HIMPUNAN = {
    "dasar": ("segitiga", "persegi", "lingkaran"),
    "lengkap": ("segitiga", "persegi", "persegi panjang", "lingkaran"),
}
# Bangun bersisi lurus yang boleh ditanya banyak sisinya, dan jawabannya.
SISI = {"segitiga": 3, "persegi": 4, "persegi panjang": 4}
PESAN_LUAR_DOMAIN = "parameter kenali bentuk di luar domain"

# Ciri per himpunan dan bangun (kalimat sesudah "Bangun apa yang ..."). Tiap ciri
# menunjuk tepat satu bangun dalam himpunannya; ciri "dasar" untuk persegi
# ("4 sisi dan 4 sudut") menjadi rancu di himpunan "lengkap", jadi tidak dipakai di sana.
CIRI = {
    "dasar": {
        "segitiga": ("punya 3 sisi dan 3 sudut", "punya 3 sisi lurus", "punya 3 sudut"),
        "persegi": ("punya 4 sisi sama panjang", "punya 4 sisi dan 4 sudut",
                    "punya 4 sisi sama panjang dan 4 sudut sama besar"),
        "lingkaran": ("tidak punya sudut dan tidak punya sisi lurus",
                      "berbentuk bulat dan tidak punya sudut",
                      "tidak punya sudut sama sekali"),
    },
    "lengkap": {
        "segitiga": ("punya 3 sisi dan 3 sudut", "punya 3 sisi lurus", "punya 3 sudut"),
        "persegi": ("punya 4 sisi yang semuanya sama panjang",
                    "punya 4 sisi sama panjang dan 4 sudut sama besar",
                    "punya 4 sudut sama besar dan 4 sisi sama panjang"),
        "persegi panjang": ("punya 4 sisi, yaitu 2 sisi panjang dan 2 sisi pendek",
                            "punya 4 sudut dan sisi yang berhadapan sama panjang, "
                            "tetapi tidak semua sisinya sama panjang",
                            "punya 4 sisi dengan sepasang sisi panjang dan sepasang sisi pendek"),
        "lingkaran": ("tidak punya sudut dan tidak punya sisi lurus",
                      "berbentuk bulat dan tidak punya sudut",
                      "tidak punya sudut sama sekali"),
    },
}
# Benda sehari-hari yang bentuk permukaannya jelas satu bangun datar; sengaja
# bukan benda bangun ruang (bola, kaleng) dan bukan benda yang bisa dua bentuk.
BENDA = {
    "lingkaran": ("uang logam", "bagian depan jam dinding yang bulat", "keping CD"),
    "persegi": ("kertas origami", "satu kotak pada papan catur", "satu permukaan dadu"),
    "segitiga": ("penggaris segitiga",
                 "potongan roti tawar persegi yang dipotong miring dari pojok ke pojok"),
    "persegi panjang": ("sampul buku tulis", "bendera Merah Putih",
                        "pintu kelas yang dilihat dari depan"),
}
FAKTA = {
    "segitiga": "Segitiga punya 3 sisi lurus dan 3 sudut.",
    "persegi": "Persegi punya 4 sisi yang semuanya sama panjang dan 4 sudut.",
    "persegi panjang": ("Persegi panjang punya 4 sisi: 2 sisi panjang dan 2 sisi pendek, "
                        "dan sisi yang berhadapan sama panjang."),
    "lingkaran": "Lingkaran itu bulat. Ia tidak punya sisi lurus dan tidak punya sudut.",
}
# Dugaan tertukar yang lebih spesifik dari kalimat umum, per (kunci, jawaban keliru).
TUKAR_KHUSUS = {
    ("persegi", "persegi panjang"): (
        "Menyebut persegi panjang karena sama-sama punya 4 sisi, tanpa memeriksa bahwa "
        "pada bangun ini semua sisinya sama panjang."),
    ("persegi panjang", "persegi"): (
        "Menyebut persegi karena sama-sama punya 4 sisi dan 4 sudut, tanpa memeriksa bahwa "
        "pada bangun ini sisi panjang dan sisi pendeknya berbeda."),
}


def _alasan_tukar(varian: str, kunci: str, lain: str) -> str:
    if (kunci, lain) in TUKAR_KHUSUS:
        return TUKAR_KHUSUS[(kunci, lain)]
    if varian == "dari_ciri":
        return f"Menyebut {lain}, kemungkinan belum membedakan ciri {kunci} dari ciri {lain}."
    return f"Menyebut {lain}, kemungkinan belum mengaitkan bentuk benda itu dengan ciri {kunci}."


def _teks(varian: str, himpunan: str, bangun: str, ciri, benda) -> str:
    if varian == "dari_ciri":
        return f"Bangun apa yang {CIRI[himpunan][bangun][ciri]}?"
    if varian == "benda":
        return f"Bentuk {BENDA[bangun][benda]} seperti bangun apa?"
    return f"Berapa banyak sisi {bangun}?"


def _pembahasan(varian: str, himpunan: str, bangun: str, ciri, benda) -> str:
    fakta = FAKTA[bangun]
    if varian == "dari_ciri":
        return (f"Cocokkan ciri itu dengan tiap bangun. {fakta} "
                f"Jadi bangun yang {CIRI[himpunan][bangun][ciri]} adalah {bangun}.")
    if varian == "benda":
        return (f"Lihat bentuk {BENDA[bangun][benda]}: sama seperti {bangun}. {fakta} "
                f"Jadi jawabannya {bangun}.")
    return (f"Hitung sisinya satu per satu sambil menunjuk, jangan sampai ada yang terhitung "
            f"dua kali. {fakta} Jadi {bangun} punya {SISI[bangun]} sisi.")


def _malrule_nama(varian: str, himpunan: str, kunci: str) -> list:
    awalan = "ciri" if varian == "dari_ciri" else "benda"
    return [
        Malrule(f"{TEMPLATE_ID}.{awalan}_tertukar_{lain.replace(' ', '_')}", lain, "K",
                _alasan_tukar(varian, kunci, lain))
        for lain in BANGUN_HIMPUNAN[himpunan] if lain != kunci
    ]


def _malrule_sisi(bangun: str) -> list:
    k = SISI[bangun]
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.sisi_dan_sudut", str(2 * k), "K",
        f"Menghitung sisi dan sudut sekaligus sehingga jawabannya {2 * k}, "
        "padahal yang ditanya hanya banyak sisi.")]
    if bangun == "persegi panjang":
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.dua_macam_sisi", "2", "K",
            "Hanya menghitung macam sisinya (panjang dan pendek), bukan semua sisinya."))
    kandidat.append(Malrule(
        f"{TEMPLATE_ID}.sisi_terhitung_dobel", str(k + 1), "H",
        "Sudah mengerti caranya, tetapi satu sisi terhitung dua kali sehingga jawabannya lebih satu."))
    kandidat.append(Malrule(
        f"{TEMPLATE_ID}.sisi_terlewat", str(k - 1), "H",
        "Sudah mengerti caranya, tetapi satu sisi terlewat sehingga jawabannya kurang satu."))
    return kandidat


def _indeks_sah(nilai, panjang: int) -> bool:
    return type(nilai) is int and 0 <= nilai < panjang


def _sah(varian, himpunan, bangun, ciri, benda) -> bool:
    if varian not in VARIAN or himpunan not in ("dasar", "lengkap"):
        return False
    if type(bangun) is not str or bangun not in BANGUN_HIMPUNAN[himpunan]:
        return False
    if varian == "dari_ciri":
        return benda is None and _indeks_sah(ciri, len(CIRI[himpunan][bangun]))
    if varian == "benda":
        return ciri is None and _indeks_sah(benda, len(BENDA[bangun]))
    return ciri is None and benda is None and bangun in SISI


def kenali_bentuk(varian: str, himpunan: str, bangun: str,
                  ciri: int | None = None, benda: int | None = None) -> Soal:
    """Nama bangun dari ciri atau benda, atau banyak sisi bangun (kunci dari parameter)."""
    if not _sah(varian, himpunan, bangun, ciri, benda):
        raise ValueError(PESAN_LUAR_DOMAIN)
    parameter = {"varian": varian, "himpunan": himpunan, "bangun": bangun}
    if ciri is not None:
        parameter["ciri"] = ciri
    if benda is not None:
        parameter["benda"] = benda
    if varian == "banyak_sisi":
        kunci, kandidat = str(SISI[bangun]), _malrule_sisi(bangun)
    else:
        kunci, kandidat = bangun, _malrule_nama(varian, himpunan, bangun)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter,
        teks=_teks(varian, himpunan, bangun, ciri, benda), kunci=kunci,
        malrule=saring_malrule(kunci, kandidat),
        pembahasan=_pembahasan(varian, himpunan, bangun, ciri, benda), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi(himpunan: str) -> tuple:
    hasil = []
    for bangun in BANGUN_HIMPUNAN[himpunan]:
        for ciri in range(len(CIRI[himpunan][bangun])):
            hasil.append({"varian": "dari_ciri", "himpunan": himpunan,
                          "bangun": bangun, "ciri": ciri})
    for bangun in BANGUN_HIMPUNAN[himpunan]:
        for benda in range(len(BENDA[bangun])):
            hasil.append({"varian": "benda", "himpunan": himpunan,
                          "bangun": bangun, "benda": benda})
    for bangun in BANGUN_HIMPUNAN[himpunan]:
        if bangun in SISI:
            hasil.append({"varian": "banyak_sisi", "himpunan": himpunan, "bangun": bangun})
    return tuple(hasil)


@lru_cache(maxsize=None)
def _domain_beku(level: str) -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi(HIMPUNAN_LEVEL[level]))


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level kenali bentuk harus P1 atau P2")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for item in _domain_beku(level))


def parameter(rng: random.Random, level: str) -> dict:
    """Satu undian seragam dari domain terbatas; tanpa rejection atau nudge."""
    _pastikan_level(level)
    return dict(rng.choice(_domain_beku(level)))
