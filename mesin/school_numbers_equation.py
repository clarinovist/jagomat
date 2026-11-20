"""kalimat_matematika: cari bilangan yang belum diketahui (ditulis "...").

Parameter `tampak` = bilangan yang tertulis di dekat tempat kosong, `hasil` =
bilangan sesudah "=". Bentuk tambah/kurang dipakai P3 (<= 100) dan P4 (<= 1.000);
bentuk kali/bagi dipakai P5 (<= 1.000). Malrule hanya HIPOTESIS kesalahan umum
untuk ditinjau guru: operasi yang salah (K) dan menyalin bilangan yang tampak (H).
"""
from __future__ import annotations

import random

from school_numbers_common import BAGI, BATAS_UNDI, KALI, KURANG, bilangan_bulat, ribuan
from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "kalimat_matematika"
BENTUK_TAMBAH_KURANG = ("tambah_akhir", "tambah_awal", "kurang_akhir", "kurang_awal")
BENTUK_KALI_BAGI = ("kali_akhir", "kali_awal", "bagi_akhir", "bagi_awal")
VARIAN = BENTUK_TAMBAH_KURANG + BENTUK_KALI_BAGI
BATAS_BAWAH, BATAS_ATAS = 2, 1_000
JALUR_MINIMUM = 2
AWALAN = "Isi bilangan yang hilang: "
# level -> (batas hasil, bilangan terkecil yang dipakai sampler)
BATAS_TAMBAH_KURANG = {"P3": (100, 11), "P4": (1_000, 20)}
ID_SAMA = TEMPLATE_ID + ".operasi_sama_bukan_kebalikan"
ID_KEBALIKAN = TEMPLATE_ID + ".operasi_kebalikan_bukan_sama"
ID_SALIN_DEKAT = TEMPLATE_ID + ".salin_dekat"
ID_SALIN_HASIL = TEMPLATE_ID + ".salin_hasil"


def _dicari(varian: str, t: int, h: int):
    """Bilangan yang hilang; None bila tidak bulat."""
    if varian in ("tambah_akhir", "tambah_awal"):
        return h - t
    if varian == "kurang_akhir":
        return t - h
    if varian == "kurang_awal":
        return h + t
    if varian in ("kali_akhir", "kali_awal"):
        return h // t if h % t == 0 else None
    if varian == "bagi_akhir":
        return t // h if t % h == 0 else None
    return h * t  # bagi_awal


# bentuk -> (id malrule K, jawaban salah, operasi yang dipakai, operasi yang seharusnya)
def _operasi_salah(varian: str, t: int, h: int) -> tuple:
    return {
        "tambah_akhir": (ID_SAMA, t + h, "menjumlahkan", "mengurangi"),
        "tambah_awal": (ID_SAMA, t + h, "menjumlahkan", "mengurangi"),
        "kurang_awal": (ID_SAMA, abs(h - t), "mengurangi", "menjumlahkan"),
        "kali_akhir": (ID_SAMA, t * h, "mengalikan", "membagi"),
        "kali_awal": (ID_SAMA, t * h, "mengalikan", "membagi"),
        "bagi_awal": (ID_SAMA, h // t if h % t == 0 else 0, "membagi", "mengalikan"),
        "kurang_akhir": (ID_KEBALIKAN, t + h, "menjumlahkan", "mengurangi"),
        "bagi_akhir": (ID_KEBALIKAN, t * h, "mengalikan", "membagi"),
    }[varian]


def _kandidat(varian: str, t: int, h: int) -> list:
    id_k, jawaban, dipakai, seharusnya = _operasi_salah(varian, t, h)
    if id_k == ID_SAMA:
        alasan = (f"Memakai operasi yang sama ({dipakai} dua bilangan yang tampak), "
                  f"bukan kebalikannya ({seharusnya}).")
    else:
        alasan = (f"Memakai kebalikan ({dipakai} dua bilangan yang tampak) padahal bilangan "
                  f"yang hilang dicari dengan {seharusnya} seperti yang tertulis.")
    return [
        Malrule(id_k, str(jawaban), "K", alasan),
        Malrule(ID_SALIN_DEKAT, str(t), "H",
                "Menyalin bilangan yang tampak di dekat tempat kosong sebagai jawaban."),
        Malrule(ID_SALIN_HASIL, str(h), "H",
                "Menyalin bilangan sesudah tanda sama dengan sebagai jawaban."),
    ]


def _sah(varian, t, h) -> bool:
    if varian not in VARIAN or not (bilangan_bulat(t) and bilangan_bulat(h)):
        return False
    if not (BATAS_BAWAH <= t <= BATAS_ATAS and BATAS_BAWAH <= h <= BATAS_ATAS):
        return False
    if (varian == "bagi_awal" and h % t) or (varian == "kurang_awal" and h == t):
        return False
    kunci = _dicari(varian, t, h)
    if kunci is None or not BATAS_BAWAH <= kunci <= BATAS_ATAS:
        return False
    sisa = saring_malrule(str(kunci), _kandidat(varian, t, h))
    return len(sisa) >= JALUR_MINIMUM and any(m.kode == "K" for m in sisa)


def _teks(varian: str, t: int, h: int) -> str:
    a, b = ribuan(t), ribuan(h)
    kalimat = {
        "tambah_akhir": f"{a} + ... = {b}", "tambah_awal": f"... + {a} = {b}",
        "kurang_akhir": f"{a} {KURANG} ... = {b}", "kurang_awal": f"... {KURANG} {a} = {b}",
        "kali_akhir": f"{a} {KALI} ... = {b}", "kali_awal": f"... {KALI} {a} = {b}",
        "bagi_akhir": f"{a} {BAGI} ... = {b}", "bagi_awal": f"... {BAGI} {a} = {b}",
    }[varian]
    return AWALAN + kalimat


def _pembahasan(varian: str, t: int, h: int, kunci: int) -> str:
    a, b, k = ribuan(t), ribuan(h), ribuan(kunci)
    if varian in ("tambah_akhir", "tambah_awal"):
        cek = f"{a} + {k}" if varian == "tambah_akhir" else f"{k} + {a}"
        return (f"Bilangan yang hilang dicari dengan operasi kebalikan, yaitu pengurangan: "
                f"{b} {KURANG} {a} = {k}. Cek: {cek} = {b}.")
    if varian == "kurang_akhir":
        return (f"{a} dikurangi berapa supaya hasilnya {b}? Kurangkan: {a} {KURANG} {b} = {k}. "
                f"Cek: {a} {KURANG} {k} = {b}.")
    if varian == "kurang_awal":
        return (f"Setelah dikurangi {a}, hasilnya {b}. Bilangan awalnya dicari dengan penjumlahan: "
                f"{b} + {a} = {k}. Cek: {k} {KURANG} {a} = {b}.")
    if varian in ("kali_akhir", "kali_awal"):
        cek = f"{a} {KALI} {k}" if varian == "kali_akhir" else f"{k} {KALI} {a}"
        return (f"Bilangan yang hilang dicari dengan operasi kebalikan, yaitu pembagian: "
                f"{b} {BAGI} {a} = {k}. Cek: {cek} = {b}.")
    if varian == "bagi_akhir":
        return (f"{a} dibagi berapa supaya hasilnya {b}? Bagilah: {a} {BAGI} {b} = {k}. "
                f"Cek: {a} {BAGI} {k} = {b}.")
    return (f"Bilangan itu dibagi {a} hasilnya {b}. Bilangan awalnya dicari dengan perkalian: "
            f"{b} {KALI} {a} = {k}. Cek: {k} {BAGI} {a} = {b}.")


def kalimat_matematika(varian: str, tampak: int, hasil: int) -> Soal:
    """Isi satu bilangan yang hilang pada kalimat tambah, kurang, kali, atau bagi."""
    if not _sah(varian, tampak, hasil):
        raise ValueError("parameter kalimat matematika di luar domain")
    kunci = _dicari(varian, tampak, hasil)
    malrule = saring_malrule(str(kunci), _kandidat(varian, tampak, hasil))
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, "tampak": tampak, "hasil": hasil},
        teks=_teks(varian, tampak, hasil), kunci=str(kunci), malrule=malrule,
        pembahasan=_pembahasan(varian, tampak, hasil, kunci), bagian="E")


def _dari_tripel(bentuk: str, x: int, y: int, z: int) -> tuple:
    """(tampak, hasil) dari tripel x op y = z menurut letak bilangan yang dicari."""
    return {
        "tambah_akhir": (x, z), "tambah_awal": (y, z), "kurang_akhir": (z, x), "kurang_awal": (y, x),
        "kali_akhir": (x, z), "kali_awal": (y, z), "bagi_akhir": (z, x), "bagi_awal": (y, x),
    }[bentuk]


def _tripel_tambah_kurang(rng: random.Random, level: str) -> tuple:
    batas, bawah = BATAS_TAMBAH_KURANG[level]
    x = rng.randint(bawah, batas - bawah)
    y = rng.randint(bawah, batas - x)
    return rng.choice(BENTUK_TAMBAH_KURANG), x, y, x + y


def _tripel_kali_bagi(rng: random.Random) -> tuple:
    bentuk = rng.choice(BENTUK_KALI_BAGI)
    if bentuk == "bagi_awal":
        y = rng.randint(2, 22)
        x = y * rng.randint(2, BATAS_ATAS // (y * y))
        return bentuk, x, y, x * y
    x = rng.randint(3, 60)
    y = rng.randint(3, BATAS_ATAS // x)
    return bentuk, x, y, x * y


def parameter(rng: random.Random, level: str) -> dict:
    for _ in range(BATAS_UNDI):
        if level == "P5":
            bentuk, x, y, z = _tripel_kali_bagi(rng)
        else:
            bentuk, x, y, z = _tripel_tambah_kurang(rng, level)
        tampak, hasil = _dari_tripel(bentuk, x, y, z)
        if _sah(bentuk, tampak, hasil):
            return {"varian": bentuk, "tampak": tampak, "hasil": hasil}
    raise RuntimeError(f"{TEMPLATE_ID}: tak ada parameter sah dalam {BATAS_UNDI} percobaan")
