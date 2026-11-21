"""Matematika Awal, jenis `unsur_bangun_datar`: sisi, sudut, sejajar, tegak lurus (P3), teks saja.

Enam bentuk soal (`varian`), hanya FAKTA TAK TERBANTAHKAN (ditandai untuk ulasan Mutia):
  - `banyak_sisi`: segitiga 3, persegi 4, persegi panjang 4, segilima 5, segienam 6;
  - `banyak_sudut`: banyak sudut sama dengan banyak sisi pada kelima bangun itu;
  - `sudut_siku`: banyak sudut siku-siku persegi 4, persegi panjang 4, segitiga
    siku-siku 1;
  - `pasang_sejajar`: banyak pasang sisi sejajar persegi 2 dan persegi panjang 2
    (sisi yang berhadapan);
  - `pasang_tegak_lurus`: banyak pasang sisi BERSEBELAHAN yang saling tegak lurus pada
    persegi 4 dan persegi panjang 4 (satu pasang tiap pojok; soal selalu menyebut
    "bersebelahan" supaya tidak ambigu dengan hitungan lain);
  - `istilah`: "Dua garis yang tidak pernah berpotongan walaupun diperpanjang disebut
    garis ..." (sejajar) dan "Dua garis yang membentuk sudut siku-siku disebut garis ..."
    (tegak lurus).

Daftar fakta untuk Mutia (semua berlaku untuk bangun bersisi lurus biasa): jumlah sisi
= jumlah sudut pada segi banyak; persegi dan persegi panjang punya 4 sudut yang semuanya
siku-siku; segitiga siku-siku punya tepat 1 sudut siku-siku; sisi yang berhadapan pada
persegi dan persegi panjang sejajar (2 pasang) dan sisi yang bersebelahan saling tegak
lurus (4 pasang). Tanpa jajar genjang, trapesium, belah ketupat, dan layang-layang
(bab kelas 4-5). Simetri tidak dilatih di sini (sudah ada jenis `simetri_bangun`).
Segilima dan segienam dalam arti biasa (bentuk apa pun, banyak sisi dan sudut tetap).

Kunci angka polos ("4") atau satu atau dua kata huruf kecil ("sejajar", "tegak lurus");
jawaban isian dibandingkan lewat `diagnosis.normalisasi` ("tegaklurus" tanpa spasi
dianggap salah, seperti "persegipanjang").

Sisi dan sudut pada bangun bersisi lurus selalu berjumlah sama, jadi tertukarnya
"sisi" dengan "sudut" tidak menghasilkan jawaban salah yang bisa dibedakan. Gantinya
malrule yang BISA dibedakan: sisi dan sudut dihitung bersama (dua kali lipat, K),
tertukar dengan bangun sebelah (segilima 6, segienam 5, K), "hanya macam sisi" pada
persegi panjang (2, K), sudut siku-siku disangka 2 atau 1 atau 0 atau semua sudut (K),
pasang sejajar dihitung sebagai semua sisi atau sepasang (K), pasang tegak lurus
tertukar dengan pasang sejajar atau dihitung dua arah (K), istilah sejajar dan tegak
lurus tertukar (K), serta lebih/kurang satu (H, hanya bila nyata).
Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari
satu jawaban.

Pilihan ganda: untuk `istilah` pengecoh kategori dari malrule ditambah "miring"
(`pengecoh_tambahan`); varian lain berkunci angka dengan minimal tiga pengecoh angka.

Domain kecil dan eksplisit (`domain_parameter`): sampler memilih `varian` seragam dulu,
lalu satu parameter seragam dalam varian itu, semuanya dari `rng` (tanpa `hash()`), jadi
seed yang sama menghasilkan soal yang sama lintas proses. `gaya` = indeks kalimat soal;
daftar kalimat bersifat APPEND-ONLY menurut indeks (indeks ikut identitas soal di bank).
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "unsur_bangun_datar"
LEVEL = ("P3",)
VARIAN = ("banyak_sisi", "banyak_sudut", "sudut_siku", "pasang_sejajar",
          "pasang_tegak_lurus", "istilah")
PESAN_LUAR_DOMAIN = "parameter unsur bangun datar di luar domain"
JUMLAH_GAYA = 3
PASANG_SEJAJAR = 2
PASANG_TEGAK_LURUS = 4

# Banyak sisi (= banyak sudut), urut sederhana ke banyak.
SISI = {"segitiga": 3, "persegi": 4, "persegi panjang": 4, "segilima": 5, "segienam": 6}
# Banyak sudut siku-siku.
SIKU = {"persegi": 4, "persegi panjang": 4, "segitiga siku-siku": 1}
BANGUN_PERSEGI = ("persegi", "persegi panjang")
ISTILAH = ("sejajar", "tegak lurus")
# Bangun sebelah yang tertukar (segilima/segienam); selain itu tanpa tetangga.
TETANGGA = {"segilima": "segienam", "segienam": "segilima"}

# APPEND-ONLY menurut indeks gaya; {b} nama bangun, {B} nama bangun berhuruf awal besar.
TEKS = {
    "banyak_sisi": ("Berapa banyak sisi {b}?", "{B} mempunyai ... sisi.",
                    "Ada berapa sisi pada {b}?"),
    "banyak_sudut": ("Berapa banyak sudut {b}?", "{B} mempunyai ... sudut.",
                     "Ada berapa sudut pada {b}?"),
    "sudut_siku": ("Berapa banyak sudut siku-siku pada {b}?",
                   "{B} mempunyai ... sudut siku-siku.",
                   "Ada berapa sudut siku-siku pada {b}?"),
    "pasang_sejajar": ("Berapa pasang sisi sejajar pada {b}?",
                       "{B} mempunyai ... pasang sisi yang sejajar.",
                       "Sisi yang berhadapan pada {b} sejajar. Ada berapa pasang sisi sejajar itu?"),
    "pasang_tegak_lurus": (
        "Berapa pasang sisi bersebelahan yang saling tegak lurus pada {b}?",
        "Pada {b}, sisi yang bersebelahan saling tegak lurus. "
        "Ada berapa pasang sisi bersebelahan itu?",
        "{B} mempunyai ... pasang sisi bersebelahan yang saling tegak lurus."),
}
TEKS_ISTILAH = {
    "sejajar": ("Dua garis yang tidak pernah berpotongan walaupun diperpanjang disebut garis ...",
                "Dua garis yang selalu berjarak sama dan tidak pernah berpotongan "
                "disebut garis ...",
                "Dua garis lurus yang tidak akan bertemu walaupun diperpanjang terus "
                "disebut garis ..."),
    "tegak lurus": ("Dua garis yang membentuk sudut siku-siku disebut garis ...",
                    "Jika dua garis membentuk sudut siku-siku, kedua garis itu disebut garis ...",
                    "Dua garis lurus yang membentuk sudut siku-siku disebut garis ..."),
}
# Bidang parameter tiap varian: yang menunjuk bangun/istilah, lalu gaya.
BANGUN_VARIAN = {
    "banyak_sisi": tuple(SISI),
    "banyak_sudut": tuple(SISI),
    "sudut_siku": tuple(SIKU),
    "pasang_sejajar": BANGUN_PERSEGI,
    "pasang_tegak_lurus": BANGUN_PERSEGI,
}


def _kunci(varian: str, p: dict) -> str:
    if varian in ("banyak_sisi", "banyak_sudut"):
        return str(SISI[p["bangun"]])
    if varian == "sudut_siku":
        return str(SIKU[p["bangun"]])
    if varian == "pasang_sejajar":
        return str(PASANG_SEJAJAR)
    if varian == "pasang_tegak_lurus":
        return str(PASANG_TEGAK_LURUS)
    return p["istilah"]


def _teks(varian: str, p: dict) -> str:
    if varian == "istilah":
        return TEKS_ISTILAH[p["istilah"]][p["gaya"]]
    bangun = p["bangun"]
    return TEKS[varian][p["gaya"]].format(b=bangun, B=bangun[0].upper() + bangun[1:])


# ── pembahasan ───────────────────────────────────────────────────────────

def _pembahasan(varian: str, p: dict, kunci: str) -> str:
    if varian == "istilah":
        return _pembahasan_istilah(p["istilah"])
    bangun = p["bangun"]
    if varian == "banyak_sisi":
        return (f"Hitung sisinya satu per satu sambil menunjuk, jangan sampai ada yang "
                f"terhitung dua kali. Jadi {bangun} punya {kunci} sisi.")
    if varian == "banyak_sudut":
        return (f"Sudut ada di tiap pojok. Hitung pojoknya satu per satu. Pada bangun "
                f"bersisi lurus, banyak sudut sama dengan banyak sisi. "
                f"Jadi {bangun} punya {kunci} sudut.")
    if varian == "sudut_siku":
        return _pembahasan_siku(bangun, kunci)
    if varian == "pasang_sejajar":
        return (f"Sisi yang berhadapan pada {bangun} sejajar: sepasang sisi atas dan "
                f"bawah, dan sepasang sisi kiri dan kanan. Jadi ada {kunci} pasang "
                f"sisi sejajar.")
    return (f"Di tiap pojok {bangun}, dua sisi yang bersebelahan membentuk sudut "
            f"siku-siku, jadi keduanya saling tegak lurus. Ada 4 pojok, jadi ada "
            f"{kunci} pasang sisi bersebelahan yang saling tegak lurus.")


def _pembahasan_siku(bangun: str, kunci: str) -> str:
    if bangun == "segitiga siku-siku":
        return ("Sudut siku-siku bentuknya seperti pojok kertas. Segitiga siku-siku "
                "hanya punya satu pojok seperti itu; dua sudut lainnya bukan sudut "
                f"siku-siku. Jadi ada {kunci} sudut siku-siku.")
    return (f"Sudut siku-siku bentuknya seperti pojok kertas. Keempat pojok {bangun} "
            f"semuanya seperti itu. Jadi ada {kunci} sudut siku-siku.")


def _pembahasan_istilah(istilah: str) -> str:
    if istilah == "sejajar":
        return ("Dua garis yang tidak pernah berpotongan walaupun diperpanjang disebut "
                "garis sejajar, seperti dua sisi yang berhadapan pada persegi panjang. "
                "Jadi jawabannya sejajar.")
    return ("Dua garis yang membentuk sudut siku-siku disebut garis tegak lurus, seperti "
            "dua sisi yang bersebelahan di pojok kertas. Jadi jawabannya tegak lurus.")


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _lebih_kurang_satu(k: int) -> list:
    return [
        _mal("lebih_satu", k + 1, "H",
             f"Sudah mengerti caranya, tetapi satu terhitung dua kali sehingga jawabannya {k + 1}."),
        _mal("kurang_satu", k - 1, "H",
             f"Sudah mengerti caranya, tetapi satu terlewat sehingga jawabannya {k - 1}."),
    ]


def _kandidat_hitung(varian: str, bangun: str) -> list:
    k = SISI[bangun]
    objek = "sisi" if varian == "banyak_sisi" else "sudut"
    kandidat = [_mal(
        "sisi_dan_sudut_dihitung_bersama", 2 * k, "K",
        f"Menghitung sisi dan sudut sekaligus sehingga jawabannya {2 * k}, padahal yang "
        f"ditanya hanya banyak {objek}.")]
    if bangun in TETANGGA:
        lain = TETANGGA[bangun]
        kandidat.append(_mal(
            f"tertukar_{lain}", SISI[lain], "K",
            f"Menyebut {SISI[lain]}, kemungkinan menyamakan {bangun} dengan {lain}."))
    if bangun == "persegi panjang" and varian == "banyak_sisi":
        kandidat.append(_mal(
            "hanya_macam_sisi", 2, "K",
            "Hanya menghitung macam sisinya (panjang dan pendek), bukan semua sisinya."))
    return kandidat + _lebih_kurang_satu(k)


def _kandidat_siku(bangun: str) -> list:
    k = SIKU[bangun]
    if bangun == "segitiga siku-siku":
        return [
            _mal("semua_sudut_dihitung", 3, "K",
                 "Menghitung semua sudut segitiga (3), bukan hanya yang siku-siku."),
            _mal("disamakan_persegi", 4, "K",
                 "Menyebut 4, kemungkinan menyamakan dengan persegi yang keempat sudutnya siku-siku."),
            _mal("lebih_satu", 2, "H",
                 "Sudah mengerti caranya, tetapi satu sudut terhitung dua kali sehingga jawabannya 2."),
        ]
    kandidat = [
        _mal("dua_sudut_saja", 2, "K",
             f"Menyebut 2 sudut siku-siku pada {bangun}, kemungkinan sudut yang berhadapan "
             "dihitung satu."),
        _mal("satu_sudut_saja", 1, "K",
             "Menyebut 1 sudut siku-siku, kemungkinan menyamakan dengan segitiga siku-siku."),
    ]
    if bangun == "persegi panjang":
        kandidat.append(_mal(
            "bukan_persegi_nol", 0, "K",
            "Menyebut 0, kemungkinan mengira sudut siku-siku hanya ada pada persegi, "
            "bukan pada persegi panjang."))
    return kandidat + _lebih_kurang_satu(k)


def _kandidat_sejajar() -> list:
    return [
        _mal("semua_sisi_dihitung", 4, "K",
             "Menghitung semua sisi (4), bukan pasangannya."),
        _mal("satu_pasang_saja", 1, "K",
             "Menyebut sepasang saja, kemungkinan hanya menghitung sisi atas dan bawah."),
        _mal("lebih_satu", 3, "H",
             "Sudah mengerti caranya, tetapi satu pasang terhitung dua kali sehingga jawabannya 3."),
    ]


def _kandidat_tegak_lurus() -> list:
    return [
        _mal("tertukar_pasang_sejajar", 2, "K",
             "Menyebut 2, kemungkinan tertukar dengan banyak pasang sisi sejajar."),
        _mal("pasang_dihitung_dua_arah", 8, "K",
             "Menghitung tiap pasang dua kali (sisi A dengan B, lalu B dengan A), "
             "sehingga jawabannya 8."),
        _mal("lebih_satu", 5, "H",
             "Sudah mengerti caranya, tetapi satu pasang terhitung dua kali sehingga jawabannya 5."),
        _mal("kurang_satu", 3, "H",
             "Sudah mengerti caranya, tetapi satu pasang terlewat sehingga jawabannya 3."),
    ]


def _kandidat_istilah(istilah: str) -> list:
    if istilah == "sejajar":
        return [
            _mal("tertukar_tegak_lurus", "tegak lurus", "K",
                 "Menyebut tegak lurus, kemungkinan tertukar dengan garis yang membentuk "
                 "sudut siku-siku."),
            _mal("arti_terbalik_berpotongan", "berpotongan", "K",
                 "Menyebut berpotongan, kemungkinan membalik arti: garis yang tidak "
                 "pernah berpotongan dikira garis berpotongan."),
        ]
    return [_mal("tertukar_sejajar", "sejajar", "K",
                 "Menyebut sejajar, kemungkinan tertukar dengan garis yang tidak pernah "
                 "berpotongan.")]


def _kandidat(varian: str, p: dict) -> list:
    if varian in ("banyak_sisi", "banyak_sudut"):
        return _kandidat_hitung(varian, p["bangun"])
    if varian == "sudut_siku":
        return _kandidat_siku(p["bangun"])
    if varian == "pasang_sejajar":
        return _kandidat_sejajar()
    if varian == "pasang_tegak_lurus":
        return _kandidat_tegak_lurus()
    return _kandidat_istilah(p["istilah"])


def pengecoh_tambahan(parameter: dict) -> tuple:
    """Pengecoh PG kategori tambahan (bukan hipotesis kesalahan, tidak masuk malrule)."""
    return ("miring",) if parameter["varian"] == "istilah" else ()


# ── validasi dan soal ────────────────────────────────────────────────────

def _pokok(varian: str) -> str:
    return "istilah" if varian == "istilah" else "bangun"


def _kanon(varian, bangun, istilah, gaya):
    """Bentuk beku parameter bila tipe dan bidangnya cocok; selain itu None."""
    if type(varian) is not str or varian not in VARIAN or type(gaya) is not int:
        return None
    pokok, nilai = _pokok(varian), istilah if varian == "istilah" else bangun
    lawan = bangun if varian == "istilah" else istilah
    if lawan is not None or type(nilai) is not str:
        return None
    return (("varian", varian), (pokok, nilai), ("gaya", gaya))


@lru_cache(maxsize=None)
def _himpunan_domain() -> frozenset:
    return frozenset(_domain_beku())


def unsur_bangun_datar(varian: str, bangun: str | None = None,
                       istilah: str | None = None, gaya: int | None = None) -> Soal:
    """Sisi, sudut, siku-siku, sejajar, tegak lurus, atau istilah garis (kunci dari parameter)."""
    kanon = _kanon(varian, bangun, istilah, gaya)
    if kanon is None or kanon not in _himpunan_domain():
        raise ValueError(PESAN_LUAR_DOMAIN)
    isian = dict(kanon)
    kunci = _kunci(varian, isian)
    return Soal(
        template_id=TEMPLATE_ID, parameter=isian,
        teks=_teks(varian, isian), kunci=kunci,
        malrule=saring_malrule(kunci, _kandidat(varian, isian)),
        pembahasan=_pembahasan(varian, isian, kunci), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi() -> list:
    hasil = []
    for varian in VARIAN:
        pokok = _pokok(varian)
        daftar = ISTILAH if varian == "istilah" else BANGUN_VARIAN[varian]
        for nilai in daftar:
            for gaya in range(JUMLAH_GAYA):
                hasil.append({"varian": varian, pokok: nilai, "gaya": gaya})
    return hasil


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level unsur bangun datar harus P3")


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
