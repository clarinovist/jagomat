"""Matematika Awal, jenis `waktu_berat_awal`: jam penuh dan berat kg, teks saja (P2).

Empat bentuk soal (`varian`), semuanya jawaban angka:
  - `lama_kegiatan`: "Rina mulai belajar pukul 2 dan selesai pukul 5. Berapa jam Rina
    belajar?" (jam penuh, lama 1-6 jam, selesai paling lambat pukul 12 sehingga tak
    pernah melewati tengah hari);
  - `jam_penuh_setelah`: "Sekarang pukul 4. Tiga jam lagi pukul berapa?" (maju 1-6
    jam, hasil paling lambat pukul 12);
  - `jumlah_berat`: "Satu kantong berisi 2 kg beras dan kantong lain berisi 3 kg
    gula. Berapa kg semuanya?" (satuan sama-sama kg, tiap kantong 1-10 kg, total <= 20);
  - `banding_berat`: "Beras 5 kg, gula 3 kg. Berapa kg lebih berat beras?" (selisih;
    yang ditanya selalu yang lebih berat, jadi hasilnya tak pernah negatif).

Tahap ini sengaja hanya satuan baku kg dan jam penuh: tanpa gram, tanpa menit, tanpa
setengah jam, dan tanpa konversi satuan. Jam ditulis "pukul N" dengan N 1..12 tanpa
keterangan pagi/siang: karena soal tak pernah melewati pukul 12, lamanya tidak
bergantung pada pagi atau siang.

Dua berat pada `jumlah_berat` dan `banding_berat` sengaja berbeda (a != b): pada
`jumlah_berat` itu membuat "mengurangi, bukan menjumlah" selalu menghasilkan angka
lain yang tak kembar kunci, dan pada `banding_berat` selisih nol bukan soal.

Kunci angka tanpa spasi. Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru,
bukan diagnosis pasti dari satu jawaban: menjawab jam akhir bukan lamanya, menjumlah
bukan mengurang atau sebaliknya, atau salah hitung satu (H, hanya yang nyata: jam
mulai ikut terhitung satu jam, dan salah hitung lebih/kurang satu pada angka kecil).
Jalur K selalu ada di setiap parameter sah.

Domain eksplisit (`domain_parameter`); sampler mengundi varian lebih dulu (seragam),
baru parameter di dalam varian itu, hanya dari domain dan hanya lewat `rng` (tanpa
`hash()`), jadi seed yang sama selalu menghasilkan soal yang sama lintas proses.
Daftar KEGIATAN dan BARANG bersifat APPEND-ONLY menurut indeks: indeks ikut dalam
identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "waktu_berat_awal"
LEVEL = ("P2",)
VARIAN = ("lama_kegiatan", "jam_penuh_setelah", "jumlah_berat", "banding_berat")
PESAN_LUAR_DOMAIN = "parameter waktu berat awal di luar domain"

JAM_MIN, JAM_MAKS = 1, 12
LAMA_MIN, LAMA_MAKS = 1, 6
BERAT_MIN, BERAT_MAKS = 1, 10  # dua kantong beda berat: total paling banyak 19

# Tokoh sintetis dan kegiatannya (kata kerja yang pas setelah "mulai" dan "Berapa jam X").
KEGIATAN = (("Rina", "belajar"), ("Budi", "menggambar"),
            ("Dita", "membaca buku"), ("Eko", "bermain bola"))
# Dua barang yang ditimbang per soal berat; keduanya muat dalam satuan kg.
BARANG = (("beras", "gula"), ("tepung", "jagung"))
KATA_JAM = {1: "Satu", 2: "Dua", 3: "Tiga", 4: "Empat", 5: "Lima", 6: "Enam"}

FIELD = {
    "lama_kegiatan": ("kegiatan", "mulai", "lama"),
    "jam_penuh_setelah": ("sekarang", "tambah"),
    "jumlah_berat": ("barang", "a", "b"),
    "banding_berat": ("barang", "a", "b"),
}


# ── validasi parameter ───────────────────────────────────────────────────

def _int_antara(nilai, bawah: int, atas: int) -> bool:
    return type(nilai) is int and bawah <= nilai <= atas


def _sah_lama(kegiatan, mulai, lama) -> bool:
    return (_int_antara(kegiatan, 0, len(KEGIATAN) - 1)
            and _int_antara(lama, LAMA_MIN, LAMA_MAKS)
            and _int_antara(mulai, JAM_MIN, JAM_MAKS - lama))


def _sah_setelah(sekarang, tambah) -> bool:
    return (_int_antara(tambah, LAMA_MIN, LAMA_MAKS)
            and _int_antara(sekarang, JAM_MIN, JAM_MAKS - tambah))


def _sah_berat(barang, a, b) -> bool:
    return (_int_antara(barang, 0, len(BARANG) - 1)
            and _int_antara(a, BERAT_MIN, BERAT_MAKS)
            and _int_antara(b, BERAT_MIN, BERAT_MAKS) and a != b)


_SAH = {"lama_kegiatan": _sah_lama, "jam_penuh_setelah": _sah_setelah,
        "jumlah_berat": _sah_berat, "banding_berat": _sah_berat}


def _sah(varian, isi: dict) -> bool:
    if type(varian) is not str or varian not in FIELD:
        return False
    if set(isi) != set(FIELD[varian]):
        return False
    return _SAH[varian](**isi)


# ── soal per varian: (teks, kunci, kandidat malrule, pembahasan) ─────────

def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _bangun_lama(kegiatan: int, mulai: int, lama: int) -> tuple:
    nama, kerja = KEGIATAN[kegiatan]
    selesai = mulai + lama
    teks = (f"{nama} mulai {kerja} pukul {mulai} dan selesai pukul {selesai}. "
            f"Berapa jam {nama} {kerja}?")
    loncatan = ", ".join(f"{j} ke {j + 1}" for j in range(mulai, selesai))
    pembahasan = (f"Jam bergeser satu per satu dari pukul {mulai} sampai pukul {selesai}: "
                  f"{loncatan}. Ada {lama} loncatan, jadi {nama} {kerja} selama {lama} jam. "
                  f"Cara cepat: {selesai} - {mulai} = {lama}.")
    kandidat = [
        _mal("jam_akhir", selesai, "K",
             f"Menjawab jam selesainya (pukul {selesai}), padahal yang ditanya berapa jam lamanya."),
        _mal("dijumlah", mulai + selesai, "K",
             "Menjumlahkan jam mulai dan jam selesai, padahal lamanya dicari dengan mengurangkan."),
        _mal("hitung_dobel", lama + 1, "H",
             "Sudah mengerti caranya, tetapi jam mulai ikut terhitung sebagai satu jam "
             "sehingga jawabannya lebih satu."),
    ]
    return teks, str(lama), kandidat, pembahasan


def _bangun_setelah(sekarang: int, tambah: int) -> tuple:
    hasil = sekarang + tambah
    teks = f"Sekarang pukul {sekarang}. {KATA_JAM[tambah]} jam lagi pukul berapa?"
    maju = ", ".join(str(j) for j in range(sekarang + 1, hasil + 1))
    pembahasan = (f"Hitung maju dari pukul {sekarang}, satu jam tiap langkah: {maju}. "
                  f"Setelah {tambah} langkah sampai pukul {hasil}. "
                  f"Cara cepat: {sekarang} + {tambah} = {hasil}.")
    kandidat = [
        _mal("lama_saja", tambah, "K",
             f"Menjawab lamanya ({tambah} jam), padahal yang ditanya pukul berapa nanti."),
        _mal("hitung_dobel", hasil - 1, "H",
             "Sudah mengerti caranya, tetapi jam sekarang ikut terhitung sebagai satu jam "
             "sehingga jawabannya kurang satu."),
        _mal("jam_sekarang", sekarang, "K",
             "Menyebut jam sekarang saja, belum menambahkan jam yang akan datang."),
    ]
    if hasil + 1 <= JAM_MAKS:
        kandidat.append(_mal(
            "lebih_satu", hasil + 1, "H",
            "Sudah mengerti caranya, tetapi salah hitung maju sehingga jawabannya lebih satu."))
    if sekarang - tambah >= 1:
        kandidat.insert(1, _mal(
            "dikurangi", sekarang - tambah, "K",
            "Mengurangi jam sekarang dengan lamanya, padahal 'lagi' berarti maju, jadi ditambah."))
    return teks, str(hasil), kandidat, pembahasan


def _bangun_jumlah(barang: int, a: int, b: int) -> tuple:
    satu, dua = BARANG[barang]
    total = a + b
    teks = (f"Satu kantong berisi {a} kg {satu} dan kantong lain berisi {b} kg {dua}. "
            "Berapa kg semuanya?")
    pembahasan = (f"Satuannya sama-sama kg, jadi beratnya boleh ditambah: {a} + {b} = {total}. "
                  f"Jadi semuanya {total} kg.")
    kandidat = [
        _mal("dikurangi", abs(a - b), "K",
             f"Mengurangi kedua berat sehingga jawabannya {abs(a - b)}, "
             "padahal 'semuanya' berarti ditambah."),
        _mal("kurang_satu", total - 1, "H",
             "Sudah mengerti caranya, tetapi salah hitung sehingga jawabannya kurang satu."),
        _mal("lebih_satu", total + 1, "H",
             "Sudah mengerti caranya, tetapi salah hitung sehingga jawabannya lebih satu."),
    ]
    return teks, str(total), kandidat, pembahasan


def _bangun_banding(barang: int, a: int, b: int) -> tuple:
    satu, dua = BARANG[barang]
    berat, ringan = (satu, dua) if a > b else (dua, satu)
    besar, kecil = max(a, b), min(a, b)
    selisih = besar - kecil
    teks = (f"{satu.capitalize()} {a} kg, {dua} {b} kg. "
            f"Berapa kg lebih berat {berat}?")
    pembahasan = (f"{berat.capitalize()} {besar} kg dan {ringan} {kecil} kg, jadi yang lebih "
                  f"berat adalah {berat}. Cari selisihnya dengan mengurangkan: {besar} - {kecil} = {selisih}. "
                  f"Jadi {berat} lebih berat {selisih} kg.")
    kandidat = [
        _mal("dijumlah", a + b, "K",
             f"Menjumlahkan kedua berat sehingga jawabannya {a + b}, "
             "padahal 'lebih berat' berarti dicari selisihnya."),
        _mal("berat_terberat", besar, "K",
             f"Menyebut berat {berat} saja ({besar} kg), belum membandingkannya dengan {ringan}."),
        _mal("lebih_satu", selisih + 1, "H",
             "Sudah mengerti caranya, tetapi salah hitung sehingga jawabannya lebih satu."),
    ]
    if selisih > 1:
        kandidat.append(_mal(
            "kurang_satu", selisih - 1, "H",
            "Sudah mengerti caranya, tetapi salah hitung sehingga jawabannya kurang satu."))
    return teks, str(selisih), kandidat, pembahasan


_BANGUN = {"lama_kegiatan": _bangun_lama, "jam_penuh_setelah": _bangun_setelah,
           "jumlah_berat": _bangun_jumlah, "banding_berat": _bangun_banding}


def waktu_berat_awal(varian: str, **isi) -> Soal:
    """Lama kegiatan, jam setelah beberapa jam, jumlah atau selisih berat (kunci dari parameter)."""
    if not _sah(varian, isi):
        raise ValueError(PESAN_LUAR_DOMAIN)
    teks, kunci, kandidat, pembahasan = _BANGUN[varian](**isi)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isi},
        teks=teks, kunci=kunci, malrule=saring_malrule(kunci, kandidat),
        pembahasan=pembahasan, bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi_lama() -> list:
    return [{"varian": "lama_kegiatan", "kegiatan": k, "mulai": mulai, "lama": lama}
            for k in range(len(KEGIATAN))
            for lama in range(LAMA_MIN, LAMA_MAKS + 1)
            for mulai in range(JAM_MIN, JAM_MAKS - lama + 1)]


def _enumerasi_setelah() -> list:
    return [{"varian": "jam_penuh_setelah", "sekarang": sekarang, "tambah": tambah}
            for tambah in range(LAMA_MIN, LAMA_MAKS + 1)
            for sekarang in range(JAM_MIN, JAM_MAKS - tambah + 1)]


def _enumerasi_berat(varian: str) -> list:
    return [{"varian": varian, "barang": barang, "a": a, "b": b}
            for barang in range(len(BARANG))
            for a in range(BERAT_MIN, BERAT_MAKS + 1)
            for b in range(BERAT_MIN, BERAT_MAKS + 1) if a != b]


@lru_cache(maxsize=None)
def _domain_beku() -> dict:
    """Varian -> tuple item immutable; urutan enumerasi = urutan undian."""
    enumerasi = {"lama_kegiatan": _enumerasi_lama(), "jam_penuh_setelah": _enumerasi_setelah(),
                 "jumlah_berat": _enumerasi_berat("jumlah_berat"),
                 "banding_berat": _enumerasi_berat("banding_berat")}
    return {v: tuple(tuple(p.items()) for p in enumerasi[v]) for v in VARIAN}


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level waktu berat awal harus P2")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    beku = _domain_beku()
    return tuple(dict(item) for v in VARIAN for item in beku[v])


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu undian seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return dict(rng.choice(_domain_beku()[varian]))
