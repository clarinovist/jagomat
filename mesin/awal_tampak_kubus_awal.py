"""Matematika Awal, jenis `tampak_kubus_awal`: kubus satuan dan tampak depan, atas, samping (P6).

Melatih K6 B3 "Kubus dan balok": "Tampak depan, atas, samping". Jaring-jaring dan volume sudah
dilatih keluarga `geometri-ruang` (tidak diulang di sini). Susunan kubus satuan berdiri di lantai
berpetak `baris` x `kolom` (2 atau 3 tiap sisi); tiap petak ditumpuk 0..3 kubus (0 = kosong), tidak
ada kubus melayang. Empat bentuk soal (`varian`), semuanya jawaban angka:
  - `banyak_kubus`: banyak kubus seluruhnya = jumlah tinggi semua tumpukan (kubus yang tertutup
    tetap dihitung karena tumpukan berdiri di lantai);
  - `banyak_persegi_atas`: persegi pada tampak atas = banyak tumpukan yang tidak kosong;
  - `banyak_persegi_depan`: persegi pada tampak depan = jumlah, untuk tiap KOLOM, tinggi tumpukan
    tertinggi di antara semua baris;
  - `banyak_persegi_samping`: persegi pada tampak samping = jumlah, untuk tiap BARIS, tinggi
    tumpukan tertinggi di antara semua kolom.

ORIENTASI TETAP: baris pertama (`tinggi[0:kolom]`) adalah baris DEPAN, yaitu yang terdekat dengan
anak; baris berikutnya makin ke belakang. Kolom dibaca dari kiri ke kanan. Tampak depan dilihat dari
depan, tampak atas dari atas, tampak samping dari sisi KANAN. Parameter `tinggi` adalah daftar rata
(`baris * kolom` bilangan bulat, baris demi baris dari depan, tiap baris dari kiri ke kanan).

Domain hanya memuat susunan yang gambar isometriknya TIDAK ambigu: dari sudut pandang depan-kanan-atas,
kubus (kolom x, baris y, lapis z) jatuh tepat di atas kubus (x + 1, y - 1, z + 1), jadi tumpukan di
belakang-kiri yang lebih rendah dari tetangga depan-kanannya dapat hilang sepenuhnya dari gambar. Karena
itu tinggi tidak boleh naik ke arah kanan maupun ke arah depan (tumpukan paling tinggi di belakang-kiri,
seperti tangga); dengan syarat itu puncak tiap tumpukan selalu terlihat dan tiap puncak punya satu
pembacaan. Syarat lain domain: sedikitnya 3 petak terisi, ada tumpukan setinggi 2 atau lebih (supaya ada
kubus tertutup), bukan seluruh petak terisi dengan tinggi yang sama, dan nilai yang ditanya berbeda dari
ketiga nilai lain (kubus, atas, depan, samping) pada susunan yang sama, supaya jawaban "tampak yang
tertukar" selalu berbeda dari kunci. Alas 1 baris atau 1 kolom tidak masuk domain (tampak depan dan
tampak samping jadi sama dengan jumlah kubus atau satu tumpukan saja).

Dua bentuk penyajian (aturan teks vs visual):
  - TEKS (tanpa flag visual, juga lembar cetak): kalimat pertama menyebut tinggi tiap tumpukan baris
    demi baris dari depan, jadi soal bisa dijawab dari teks;
  - VISUAL (flag `matematika-awal`, proyektor di `topic_matematika_awal_tumpukan_visual`): teks proyeksi
    "Perhatikan gambar kubus-kubus satuan." tanpa tinggi; gambar isometrik membawa informasinya.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu jawaban:
menghitung tampak yang salah atau semua kubus alih-alih persegi yang terlihat, atau hanya tampak tertentu
alih-alih semua kubus (K); meleset satu hitungan (H). Jalur K selalu ada (nilai-nilai lain berbeda dari
kunci menurut syarat domain).

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu anggota seragam dari domain
varian itu memakai `rng` (tanpa `hash()`). Urutan enumerasi: varian -> alas (2x2, 2x3, 3x2, 3x3) -> tinggi
urut leksikografis (baris depan lebih dulu).
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "tampak_kubus_awal"
LEVEL = ("P6",)
VARIAN = ("banyak_kubus", "banyak_persegi_atas", "banyak_persegi_depan", "banyak_persegi_samping")
PESAN_LUAR_DOMAIN = "parameter tampak kubus awal di luar domain"
PESAN_LEVEL = "level tampak kubus awal harus P6"

ALAS = ((2, 2), (2, 3), (3, 2), (3, 3))  # (baris, kolom)
TINGGI_MAKS = 3
TERISI_MIN = 3
TINGGI_TERTINGGI_MIN = 2
FIELD = ("baris", "kolom", "tinggi")
TAMPAK_VARIAN = {"banyak_kubus": "kubus", "banyak_persegi_atas": "atas",
                 "banyak_persegi_depan": "depan", "banyak_persegi_samping": "samping"}
NAMA_BARIS = {2: ("depan", "belakang"), 3: ("depan", "tengah", "belakang")}
KALIMAT_LANTAI = "Tiap tumpukan berdiri di lantai."
PETUNJUK_ANGKA = "Tulis angkanya saja."
SELISIH_SALAH = 1  # meleset satu hitungan


# ── hitungan ─────────────────────────────────────────────────────────────

def _lajur(baris: int, kolom: int, tinggi) -> list:
    """Tinggi per baris, dari baris depan, tiap baris dari kiri ke kanan."""
    return [list(tinggi[y * kolom:(y + 1) * kolom]) for y in range(baris)]


def hitung_tampak(baris: int, kolom: int, tinggi) -> dict:
    """Empat hitungan satu susunan: kubus, atas, depan, samping."""
    lajur = _lajur(baris, kolom, tinggi)
    return {
        "kubus": sum(tinggi),
        "atas": sum(1 for h in tinggi if h),
        "depan": sum(max(lajur[y][x] for y in range(baris)) for x in range(kolom)),
        "samping": sum(max(isi) for isi in lajur),
    }


def tinggi_tertinggi_per_kolom(baris: int, kolom: int, tinggi) -> list:
    lajur = _lajur(baris, kolom, tinggi)
    return [max(lajur[y][x] for y in range(baris)) for x in range(kolom)]


def tinggi_tertinggi_per_baris(baris: int, kolom: int, tinggi) -> list:
    return [max(isi) for isi in _lajur(baris, kolom, tinggi)]


# ── domain ───────────────────────────────────────────────────────────────

def _susunan(baris: int, kolom: int):
    """Semua tinggi 0..3 yang tidak naik ke kanan dan tidak turun ke belakang (urut leksikografis)."""
    jumlah = baris * kolom

    def isi(awal: tuple):
        n = len(awal)
        if n == jumlah:
            yield awal
            return
        y, x = divmod(n, kolom)
        bawah = awal[n - kolom] if y else 0  # petak di depannya (baris sebelumnya)
        atas = awal[n - 1] if x else TINGGI_MAKS  # petak di kirinya
        for h in range(bawah, atas + 1):
            yield from isi(awal + (h,))

    return isi(())


def _layak(baris: int, kolom: int, tinggi: tuple) -> bool:
    terisi = sum(1 for h in tinggi if h)
    if terisi < TERISI_MIN or max(tinggi) < TINGGI_TERTINGGI_MIN:
        return False
    return not (terisi == baris * kolom and len(set(tinggi)) == 1)


def _beda_dari_lain(varian: str, hitungan: dict) -> bool:
    """Nilai yang ditanya berbeda dari ketiga nilai lain pada susunan yang sama."""
    nama = TAMPAK_VARIAN[varian]
    return all(hitungan[nama] != nilai for lain, nilai in hitungan.items() if lain != nama)


@lru_cache(maxsize=None)
def _anggota(varian: str) -> tuple:
    """Anggota domain satu varian: (baris, kolom, tinggi tuple), urutan enumerasi = urutan undian."""
    hasil = []
    for baris, kolom in ALAS:
        for tinggi in _susunan(baris, kolom):
            if _layak(baris, kolom, tinggi) and _beda_dari_lain(varian, hitung_tampak(baris, kolom, tinggi)):
                hasil.append((baris, kolom, tinggi))
    return tuple(hasil)


@lru_cache(maxsize=None)
def _anggota_set(varian: str) -> frozenset:
    return frozenset(_anggota(varian))


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError(PESAN_LEVEL)


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict dan daftar baru setiap panggilan."""
    _pastikan_level(level)
    return tuple({"varian": varian, "baris": b, "kolom": k, "tinggi": list(t)}
                 for varian in VARIAN for b, k, t in _anggota(varian))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu anggota seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    b, k, t = rng.choice(_anggota(varian))
    return {"varian": varian, "baris": b, "kolom": k, "tinggi": list(t)}


# ── validasi parameter ───────────────────────────────────────────────────

def _sah(varian, isi: dict) -> bool:
    """Parameter sah = anggota domain (tipe int murni; bool, float, dan teks ditolak)."""
    if type(varian) is not str or varian not in TAMPAK_VARIAN or set(isi) != set(FIELD):
        return False
    baris, kolom, tinggi = isi["baris"], isi["kolom"], isi["tinggi"]
    if type(baris) is not int or type(kolom) is not int or type(tinggi) is not list:
        return False
    if any(type(h) is not int for h in tinggi):
        return False
    return (baris, kolom, tuple(tinggi)) in _anggota_set(varian)


# ── teks ─────────────────────────────────────────────────────────────────

def _teks_baris(baris: int, kolom: int, tinggi) -> str:
    bagian = [f"baris {nama}: {', '.join(str(h) for h in isi)}"
              for nama, isi in zip(NAMA_BARIS[baris], _lajur(baris, kolom, tinggi))]
    return "; ".join(bagian)


def pengantar_teks(baris: int, kolom: int, tinggi) -> str:
    """Baris pertama versi TEKS: tinggi tiap tumpukan ditulis supaya soal bisa dijawab."""
    return (f"Kubus-kubus satuan disusun pada alas {baris} baris dan {kolom} kolom. "
            f"Tinggi tumpukan dari kiri ke kanan, {_teks_baris(baris, kolom, tinggi)} "
            f"(0 artinya kosong). {KALIMAT_LANTAI}")


def pertanyaan(varian: str) -> str:
    """Baris pertanyaan (terakhir) tiap varian; juga dipakai proyektor visual untuk memeriksa teks."""
    if varian == "banyak_kubus":
        return f"Berapa banyak kubus satuan seluruhnya, termasuk yang tertutup? {PETUNJUK_ANGKA}"
    if varian == "banyak_persegi_atas":
        return f"Berapa banyak persegi pada tampak atas (dilihat dari atas)? {PETUNJUK_ANGKA}"
    if varian == "banyak_persegi_depan":
        return f"Berapa banyak persegi pada tampak depan (dilihat dari depan)? {PETUNJUK_ANGKA}"
    return f"Berapa banyak persegi pada tampak samping (dilihat dari sisi kanan)? {PETUNJUK_ANGKA}"


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _tertukar(nama: str, nilai: int, tampak: str) -> Malrule:
    return _mal(nama, nilai, "K",
                f"Menjawab banyak persegi pada tampak {tampak}, padahal yang ditanya tampak lain.")


def _malrule_kubus(h: dict) -> list:
    return [
        _mal("hanya_tampak_atas", h["atas"], "K",
             "Menghitung satu kubus tiap tumpukan, padahal tiap tumpukan bisa lebih dari satu kubus "
             "dan semuanya harus dihitung."),
        _mal("hanya_tampak_depan", h["depan"], "K",
             "Menghitung hanya kubus yang terlihat dari depan, padahal ada kubus lain di belakang "
             "atau di bawahnya yang tertutup."),
        _mal("hanya_tampak_samping", h["samping"], "K",
             "Menghitung hanya kubus yang terlihat dari sisi kanan, padahal ada kubus lain yang "
             "tertutup."),
    ]


def _malrule_atas(h: dict) -> list:
    return [
        _mal("hitung_semua_kubus", h["kubus"], "K",
             "Menghitung semua kubus, padahal tampak atas hanya memperlihatkan satu persegi untuk "
             "tiap tumpukan."),
        _tertukar("tertukar_tampak_depan", h["depan"], "depan"),
        _tertukar("tertukar_tampak_samping", h["samping"], "samping"),
    ]


def _malrule_depan(h: dict) -> list:
    return [
        _mal("hitung_semua_kubus", h["kubus"], "K",
             "Menghitung semua kubus, padahal tampak depan hanya memperlihatkan tumpukan tertinggi "
             "di tiap kolom."),
        _tertukar("tertukar_tampak_atas", h["atas"], "atas"),
        _tertukar("tertukar_tampak_samping", h["samping"], "samping"),
    ]


def _malrule_samping(h: dict) -> list:
    return [
        _mal("hitung_semua_kubus", h["kubus"], "K",
             "Menghitung semua kubus, padahal tampak samping hanya memperlihatkan tumpukan tertinggi "
             "di tiap baris."),
        _tertukar("tertukar_tampak_atas", h["atas"], "atas"),
        _tertukar("tertukar_tampak_depan", h["depan"], "depan"),
    ]


_MALRULE_K = {"banyak_kubus": _malrule_kubus, "banyak_persegi_atas": _malrule_atas,
              "banyak_persegi_depan": _malrule_depan, "banyak_persegi_samping": _malrule_samping}


def _meleset(nilai: int) -> list:
    """Malrule H: meleset satu hitungan; nilai 0 tidak pernah jadi jawaban."""
    hasil = [_mal("lebih_satu", nilai + SELISIH_SALAH, "H",
                  "Sudah mengerti caranya, tetapi salah hitung lebih satu.")]
    if nilai - SELISIH_SALAH >= 1:
        hasil.append(_mal("kurang_satu", nilai - SELISIH_SALAH, "H",
                          "Sudah mengerti caranya, tetapi salah hitung kurang satu."))
    return hasil


# ── pembahasan ───────────────────────────────────────────────────────────

def _jumlahkan(nilai) -> str:
    return " + ".join(str(n) for n in nilai)


def _per_baris_teks(baris: int, daftar) -> str:
    return ", ".join(f"baris {nama} {n}" for nama, n in zip(NAMA_BARIS[baris], daftar))


def _pembahasan_kubus(baris: int, kolom: int, tinggi) -> str:
    isi = [h for h in tinggi if h]
    return (f"Hitung tinggi semua tumpukan: {_jumlahkan(isi)} = {sum(tinggi)}. Kubus yang tertutup "
            f"tetap dihitung karena semua tumpukan berdiri di lantai. Jadi ada {sum(tinggi)} kubus satuan.")


def _pembahasan_atas(baris: int, kolom: int, tinggi) -> str:
    per_baris = [sum(1 for h in isi if h) for isi in _lajur(baris, kolom, tinggi)]
    total = sum(per_baris)
    return (f"Dilihat dari atas, tiap tumpukan tampak sebagai satu persegi, berapa pun tingginya. "
            f"Tumpukan yang tidak kosong: {_per_baris_teks(baris, per_baris)}. "
            f"Jadi {_jumlahkan(per_baris)} = {total} persegi pada tampak atas.")


def _pembahasan_depan(baris: int, kolom: int, tinggi) -> str:
    per_kolom = tinggi_tertinggi_per_kolom(baris, kolom, tinggi)
    return (f"Dilihat dari depan, tiap kolom tampak setinggi tumpukan tertinggi di kolom itu. Dari kiri "
            f"ke kanan: {', '.join(str(n) for n in per_kolom)}. Jadi {_jumlahkan(per_kolom)} = "
            f"{sum(per_kolom)} persegi pada tampak depan.")


def _pembahasan_samping(baris: int, kolom: int, tinggi) -> str:
    per_baris = tinggi_tertinggi_per_baris(baris, kolom, tinggi)
    return (f"Dilihat dari sisi kanan, tiap baris tampak setinggi tumpukan tertinggi di baris itu: "
            f"{_per_baris_teks(baris, per_baris)}. Jadi {_jumlahkan(per_baris)} = {sum(per_baris)} "
            f"persegi pada tampak samping.")


_PEMBAHASAN = {"banyak_kubus": _pembahasan_kubus, "banyak_persegi_atas": _pembahasan_atas,
               "banyak_persegi_depan": _pembahasan_depan, "banyak_persegi_samping": _pembahasan_samping}


# ── soal ─────────────────────────────────────────────────────────────────

def _kandidat(varian: str, hitungan: dict) -> list:
    """Jalur K lebih dulu, lalu H (saring_malrule membuang jawaban kembar dengan urutan ini)."""
    return _MALRULE_K[varian](hitungan) + _meleset(hitungan[TAMPAK_VARIAN[varian]])


def tampak_kubus_awal(varian: str, **isi) -> Soal:
    """Kubus satuan: banyak kubus seluruhnya atau persegi pada tampak atas, depan, atau samping."""
    if not _sah(varian, isi):
        raise ValueError(PESAN_LUAR_DOMAIN)
    baris, kolom, tinggi = isi["baris"], isi["kolom"], isi["tinggi"]
    hitungan = hitung_tampak(baris, kolom, tinggi)
    kunci = str(hitungan[TAMPAK_VARIAN[varian]])
    teks = f"{pengantar_teks(baris, kolom, tinggi)}\n{pertanyaan(varian)}"
    return Soal(
        template_id=TEMPLATE_ID,
        parameter={"varian": varian, "baris": baris, "kolom": kolom, "tinggi": list(tinggi)},
        teks=teks, kunci=kunci, malrule=saring_malrule(kunci, _kandidat(varian, hitungan)),
        pembahasan=_PEMBAHASAN[varian](baris, kolom, tinggi), bagian="A")
