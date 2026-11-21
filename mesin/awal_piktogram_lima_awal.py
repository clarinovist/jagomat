"""Matematika Awal, jenis `piktogram_lima_awal`: piktogram berskala besar (P5).

Melatih K5 B8 "Pengumpulan dan penyajian data": "Piktogram dan diagram batang". Piktogram kelas 3 sampai 4
(statistika `piktogram`) hanya berskala kecil; di sini satu gambar mewakili 2, 5, 10, atau 20 benda,
dengan 3..5 kategori dan tiap kategori 1..10 gambar utuh (gambar setengah SENGAJA tidak dibuat, supaya
nilai tiap baris selalu kelipatan bulat skala). Jawaban selalu bilangan bulat positif, paling besar 999
(aturan umum "kunci <= 100" dilonggarkan untuk jenis ini).

Teks (tanpa flag visual, juga lembar cetak) memakai simbol "●" seperti `baca_diagram_gambar`:

    Piktogram mainan terjual di toko. Satu titik hitam mewakili 5 mainan.
    Bola: ●●●●
    Mobil: ●●●●●●●
    Boneka: ●●
    Berapa banyak mobil?

Simbol "●" HANYA muncul pada baris data, jadi banyaknya "●" di seluruh teks sama dengan jumlah semua
gambar yang ditampilkan. Lima bentuk soal (`varian`), semua jawaban angka; `n` = banyak gambar, `N` = skala:
  - `baca_nilai`: nilai satu kategori = n x N;
  - `terbanyak_selisih`: selisih kategori terbanyak dan paling sedikit = (n_maks - n_min) x N;
  - `total`: jumlah semua kategori = (jumlah n) x N;
  - `rata_rata`: rata-rata tiap kategori = (jumlah n / banyak kategori) x N; domain hanya memuat susunan
    yang jumlah n-nya habis dibagi banyak kategori, jadi rata-rata gambar selalu bulat;
  - `berapa_ikon` (kebalikan): satu kategori diketahui bernilai V benda tetapi barisnya BELUM digambar;
    jawaban = V / N = banyak gambar yang harus digambar. Baris yang ditanya tidak ikut ditampilkan (teks
    maupun gambar), kalau tidak jawabannya terbaca langsung. Karena itu varian ini hanya memakai 4..5
    kategori (sisanya 3..4 baris tertampil; descriptor visual minimal 3 baris).

Banyak gambar tiap kategori pada satu soal SELALU berbeda (kategori terbanyak dan paling sedikit tunggal,
dan jalur malrule "baris lain" tidak pernah kebetulan sama dengan kunci).

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu jawaban:
lupa mengalikan skala (K), membaca baris lain (K), menjumlah alih-alih mengurang atau tidak membagi
(K), menghilangkan satu baris (K), memakai nilai tengah (K), mengalikan alih-alih membagi (K), meleset satu
skala atau satu gambar (H).
Jalur K selalu ada.

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu anggota seragam dari
domain varian itu memakai `rng` (tanpa `hash()`). Domain dibangun per KELOMPOK (tema, banyak kategori,
skala): dari semua susunan jumlah gambar yang berbeda satu sama lain (urut leksikografis, disaring syarat
varian), tiap kelompok mengambil susunan berselang `LANGKAH = banyak // ANGGOTA_PER_KELOMPOK` mulai dari
offset `indeks kelompok % LANGKAH` (tanpa acak; angka-angka ini ikut identitas domain). Urutan enumerasi:
varian -> tema -> banyak kategori -> skala -> susunan -> kategori yang ditanya. Daftar TEMA dan kategori
bersifat APPEND-ONLY menurut urutan: nama tema dan indeks kategori ikut dalam identitas soal.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import permutations
import random
from typing import NamedTuple

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "piktogram_lima_awal"
LEVEL = ("P5",)
VARIAN = ("baca_nilai", "terbanyak_selisih", "total", "rata_rata", "berapa_ikon")
SIMBOL = "●"
SKALA = (2, 5, 10, 20)
JUMLAH_MIN, JUMLAH_MAKS = 1, 10
KATEGORI_MIN, KATEGORI_MAKS = 3, 5
KATEGORI_MIN_BERAPA_IKON = 4  # satu baris tidak digambar; descriptor visual butuh >= 3 baris
KUNCI_MAKS = 999
ANGGOTA_PER_KELOMPOK = 12
VARIAN_BERTANYA = ("baca_nilai", "berapa_ikon")  # varian dengan parameter `tanya` (indeks kategori)
FIELD_DASAR = ("tema", "skala", "jumlah")  # tanpa "varian" (argumen terpisah)
LAMBANG_TEKS = "titik hitam"
LAMBANG_VISUAL = "gambar"
PESAN_LUAR_DOMAIN = "parameter piktogram lima awal di luar domain"
PESAN_LEVEL = "level piktogram lima awal harus P5"


class Tema(NamedTuple):
    """Kepala kalimat, kata benda satuan, dan kategori (nama, ikon di allow-list); APPEND-ONLY."""

    kepala: str
    kata: str
    kategori: tuple


TEMA = {
    "mainan": Tema("mainan terjual di toko", "mainan", (
        ("Bola", "bola"), ("Mobil", "mobil"), ("Boneka", "boneka"), ("Balok", "balok"),
        ("Kelereng", "kelereng"))),
    "jajanan": Tema("jajanan terjual di bazar sekolah", "jajanan", (
        ("Kue", "kue"), ("Roti", "roti"), ("Pizza", "pizza"), ("Permen", "permen"),
        ("Pisang", "pisang"))),
    "barang": Tema("barang terjual di toko serba ada", "barang", (
        ("Meja", "meja"), ("Lemari", "lemari"), ("Karpet", "karpet"), ("Sapu", "sapu"),
        ("Payung", "payung"))),
    "alat_tulis": Tema("perlengkapan terjual di koperasi sekolah", "perlengkapan", (
        ("Buku", "buku"), ("Pensil", "pensil"), ("Klip", "klip"), ("Stiker", "stiker"))),
    "hewan": Tema("hewan di peternakan", "ekor", (
        ("Ayam", "ayam"), ("Bebek", "bebek"), ("Kelinci", "kelinci"))),
    "buah": Tema("buah yang dijual di pasar", "buah", (
        ("Apel", "apel"), ("Jeruk", "jeruk"), ("Pisang", "pisang"))),
}


# ── hitungan ─────────────────────────────────────────────────────────────

def hitung_kunci(varian: str, jumlah, skala: int, tanya) -> int:
    """Jawaban dari parameter: nilai benda (gambar x skala), kecuali berapa_ikon (banyak gambar)."""
    if varian == "baca_nilai":
        return jumlah[tanya] * skala
    if varian == "terbanyak_selisih":
        return (max(jumlah) - min(jumlah)) * skala
    if varian == "total":
        return sum(jumlah) * skala
    if varian == "rata_rata":
        return sum(jumlah) // len(jumlah) * skala
    return jumlah[tanya]


def _nama(tema: str, indeks: int) -> str:
    return TEMA[tema].kategori[indeks][0]


def _huruf_kecil(tema: str, indeks: int) -> str:
    return _nama(tema, indeks).lower()


def indeks_digambar(varian: str, banyak: int, tanya) -> tuple:
    """Indeks kategori yang barisnya tampil: semua, kecuali yang ditanya pada berapa_ikon."""
    return tuple(i for i in range(banyak) if not (varian == "berapa_ikon" and i == tanya))


# ── teks ─────────────────────────────────────────────────────────────────

def kepala(tema: str, skala: int, lambang: str = LAMBANG_TEKS) -> str:
    return f"Piktogram {TEMA[tema].kepala}. Satu {lambang} mewakili {skala} {TEMA[tema].kata}."


def pertanyaan(varian: str, tema: str, skala: int, jumlah, tanya, lambang: str = LAMBANG_TEKS) -> str:
    """Baris pertanyaan (terakhir); proyektor visual memanggilnya lagi dengan `LAMBANG_VISUAL`."""
    kata = TEMA[tema].kata
    if varian == "baca_nilai":
        return f"Berapa banyak {_huruf_kecil(tema, tanya)}?"
    if varian == "terbanyak_selisih":
        return f"Kategori yang paling banyak lebih banyak berapa {kata} daripada kategori yang paling sedikit?"
    if varian == "total":
        return f"Berapa jumlah semua {kata}?"
    if varian == "rata_rata":
        return f"Berapa rata-rata banyak {kata} untuk tiap jenis?"
    nilai = jumlah[tanya] * skala
    return (f"{_nama(tema, tanya)} ada {nilai} {kata}, tetapi barisnya belum digambar. "
            f"Berapa {lambang} yang harus digambar pada baris {_huruf_kecil(tema, tanya)}?")


def _baris(tema: str, jumlah, tampil: tuple) -> str:
    return "\n".join(f"{_nama(tema, i)}: {SIMBOL * jumlah[i]}" for i in tampil)


def _teks(varian, tema, skala, jumlah, tanya) -> str:
    tampil = indeks_digambar(varian, len(jumlah), tanya)
    return (f"{kepala(tema, skala)}\n{_baris(tema, jumlah, tampil)}\n"
            f"{pertanyaan(varian, tema, skala, jumlah, tanya)}")


# ── pembahasan ───────────────────────────────────────────────────────────

def _pecah(tema: str, jumlah, skala: int) -> str:
    """'bola 4 x 5 = 20, mobil ...' untuk semua kategori."""
    return ", ".join(f"{_huruf_kecil(tema, i)} {n} × {skala} = {n * skala}" for i, n in enumerate(jumlah))


def _jumlahkan(nilai) -> str:
    return " + ".join(str(n) for n in nilai)


def _dasar(tema: str, skala: int) -> str:
    return f"Satu gambar (satu titik hitam) mewakili {skala} {TEMA[tema].kata}."


def _pembahasan_baca(tema, jumlah, skala, tanya, kunci) -> str:
    n = jumlah[tanya]
    return (f"{_dasar(tema, skala)} Hitung gambar pada baris {_huruf_kecil(tema, tanya)}: ada {n}. "
            f"Tiap gambar bernilai {skala}, jadi {n} × {skala} = {kunci}. Jadi banyaknya {kunci}.")


def _pembahasan_selisih(tema, jumlah, skala, kunci) -> str:
    terbanyak, tersedikit = jumlah.index(max(jumlah)), jumlah.index(min(jumlah))
    besar, kecil = max(jumlah) * skala, min(jumlah) * skala
    return (f"{_dasar(tema, skala)} Hitung gambar tiap baris lalu kalikan {skala}: "
            f"{_pecah(tema, jumlah, skala)}. Yang paling banyak {_huruf_kecil(tema, terbanyak)} ({besar}), "
            f"yang paling sedikit {_huruf_kecil(tema, tersedikit)} ({kecil}). "
            f"Selisihnya dicari dengan mengurangi: {besar} - {kecil} = {kunci}.")


def _pembahasan_total(tema, jumlah, skala, kunci) -> str:
    return (f"{_dasar(tema, skala)} Hitung gambar tiap baris: {_jumlahkan(jumlah)} = {sum(jumlah)} gambar. "
            f"Tiap gambar bernilai {skala}, jadi {sum(jumlah)} × {skala} = {kunci}. "
            f"Jadi jumlah semuanya {kunci}.")


def _pembahasan_rata(tema, jumlah, skala, kunci) -> str:
    rata = sum(jumlah) // len(jumlah)
    return (f"{_dasar(tema, skala)} Hitung gambar tiap baris: {_jumlahkan(jumlah)} = {sum(jumlah)} gambar. "
            f"Ada {len(jumlah)} jenis, jadi rata-rata gambar {sum(jumlah)} ÷ {len(jumlah)} = {rata}. "
            f"Tiap gambar bernilai {skala}, jadi {rata} × {skala} = {kunci}. Jadi rata-ratanya {kunci}.")


def _pembahasan_berapa(tema, jumlah, skala, tanya, kunci) -> str:
    nilai = jumlah[tanya] * skala
    return (f"{_dasar(tema, skala)} {_nama(tema, tanya)} ada {nilai} {TEMA[tema].kata}. "
            f"Tiap gambar bernilai {skala}, jadi gambarnya {nilai} ÷ {skala} = {kunci}. "
            f"Jadi harus digambar {kunci} gambar.")


def _pembahasan(varian, tema, jumlah, skala, tanya, kunci) -> str:
    if varian == "baca_nilai":
        return _pembahasan_baca(tema, jumlah, skala, tanya, kunci)
    if varian == "terbanyak_selisih":
        return _pembahasan_selisih(tema, jumlah, skala, kunci)
    if varian == "total":
        return _pembahasan_total(tema, jumlah, skala, kunci)
    if varian == "rata_rata":
        return _pembahasan_rata(tema, jumlah, skala, kunci)
    return _pembahasan_berapa(tema, jumlah, skala, tanya, kunci)


# ── malrule ──────────────────────────────────────────────────────────────

def _mal(nama: str, jawaban: int, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _lupa_kali(jawaban: int, skala: int) -> Malrule:
    return _mal("lupa_kali_skala", jawaban, "K",
                f"Hanya menghitung gambarnya, lupa mengalikan {skala} padahal satu gambar mewakili "
                f"{skala} benda.")


def _meleset_skala(kunci: int, skala: int) -> list:
    """H: salah hitung satu gambar sehingga nilai bergeser sebesar skala."""
    hasil = [_mal("terhitung_dobel", kunci + skala, "H",
                  f"Sudah mengerti caranya, tetapi satu gambar terhitung dua kali sehingga lebih {skala}.")]
    if kunci - skala >= 1:
        hasil.append(_mal("terlewat", kunci - skala, "H",
                          f"Sudah mengerti caranya, tetapi satu gambar terlewat sehingga kurang {skala}."))
    return hasil


def _malrule_baca(tema, jumlah, skala, tanya) -> list:
    banyak = len(jumlah)
    lain = [(tanya + 1) % banyak, (tanya + 2) % banyak]
    baris_lain = [_mal(f"baris_lain_{urut}", jumlah[i] * skala, "K",
                       f"Menghitung gambar pada baris {_huruf_kecil(tema, i)} (nilainya {jumlah[i] * skala}), "
                       "kemungkinan salah baris.") for urut, i in enumerate(lain, 1)]
    kunci = jumlah[tanya] * skala
    return [_lupa_kali(jumlah[tanya], skala)] + baris_lain + _meleset_skala(kunci, skala)


def _malrule_selisih(jumlah, skala) -> list:
    urut = sorted(jumlah)
    kunci = (urut[-1] - urut[0]) * skala
    return [
        _lupa_kali(urut[-1] - urut[0], skala),
        _mal("jumlah_bukan_selisih", (urut[-1] + urut[0]) * skala, "K",
             "Menjumlahkan kategori terbanyak dan paling sedikit, padahal yang ditanya selisihnya, "
             "jadi seharusnya dikurangi."),
        _mal("hanya_terbanyak", urut[-1] * skala, "K",
             "Hanya menyebut nilai kategori terbanyak, tidak dikurangi nilai kategori paling sedikit."),
        _mal("dua_terbanyak", (urut[-1] - urut[-2]) * skala, "K",
             "Membandingkan dua kategori terbanyak, padahal pembandingnya kategori paling sedikit."),
    ] + _meleset_skala(kunci, skala)


def _malrule_total(jumlah, skala) -> list:
    total = sum(jumlah)
    return [
        _lupa_kali(total, skala),
        _mal("lupa_baris_terakhir", (total - jumlah[-1]) * skala, "K",
             "Menjumlahkan semua baris kecuali baris terakhir."),
        _mal("lupa_baris_pertama", (total - jumlah[0]) * skala, "K",
             "Menjumlahkan semua baris kecuali baris pertama."),
    ] + _meleset_skala(total * skala, skala)


def _malrule_rata(jumlah, skala) -> list:
    rata = sum(jumlah) // len(jumlah)
    return [
        _lupa_kali(rata, skala),
        _mal("tidak_dibagi", sum(jumlah) * skala, "K",
             "Hanya menjumlahkan semua baris, lupa membaginya dengan banyak jenis untuk mencari rata-rata."),
        _mal("nilai_tengah", sorted(jumlah)[len(jumlah) // 2] * skala, "K",
             "Menyebut nilai baris yang di tengah, padahal rata-rata dicari dengan menjumlah lalu membagi."),
    ] + _meleset_skala(rata * skala, skala)


def _malrule_berapa(jumlah, skala, tanya) -> list:
    banyak, nilai = jumlah[tanya], jumlah[tanya] * skala
    hasil = [_mal("tidak_dibagi", nilai, "K",
                  "Menyebut nilai bendanya, lupa membaginya dengan banyak benda yang diwakili satu gambar.")]
    if nilai - skala >= 1:
        hasil.append(_mal("dikurang_bukan_dibagi", nilai - skala, "K",
                          "Mengurangi nilai benda dengan skala, padahal seharusnya dibagi."))
    if nilai * skala <= KUNCI_MAKS:
        hasil.append(_mal("dikali_bukan_dibagi", nilai * skala, "K",
                          "Mengalikan nilai benda dengan skala, padahal seharusnya dibagi."))
    hasil.append(_mal("lebih_satu", banyak + 1, "H", "Sudah mengerti caranya, tetapi salah hitung lebih satu."))
    if banyak - 1 >= 1:
        hasil.append(_mal("kurang_satu", banyak - 1, "H", "Sudah mengerti caranya, tetapi salah hitung kurang satu."))
    return hasil


def _kandidat(varian, tema, jumlah, skala, tanya) -> list:
    if varian == "baca_nilai":
        return _malrule_baca(tema, jumlah, skala, tanya)
    if varian == "terbanyak_selisih":
        return _malrule_selisih(jumlah, skala)
    if varian == "total":
        return _malrule_total(jumlah, skala)
    if varian == "rata_rata":
        return _malrule_rata(jumlah, skala)
    return _malrule_berapa(jumlah, skala, tanya)


# ── domain ───────────────────────────────────────────────────────────────

def _banyak_kategori(tema: str) -> range:
    return range(KATEGORI_MIN, len(TEMA[tema].kategori) + 1)


def _kelompok(varian: str) -> tuple:
    """Kelompok (tema, banyak kategori, skala) urut tema -> banyak kategori -> skala."""
    awal = KATEGORI_MIN_BERAPA_IKON if varian == "berapa_ikon" else KATEGORI_MIN
    return tuple((tema, k, skala) for tema in TEMA for k in _banyak_kategori(tema)
                 if k >= awal for skala in SKALA)


def _layak(varian: str, jumlah: tuple) -> bool:
    return varian != "rata_rata" or sum(jumlah) % len(jumlah) == 0


@lru_cache(maxsize=None)
def _kolam(varian: str, banyak: int) -> tuple:
    """Semua susunan jumlah yang berbeda satu sama lain dan lolos syarat varian, urut leksikografis."""
    return tuple(j for j in permutations(range(JUMLAH_MIN, JUMLAH_MAKS + 1), banyak) if _layak(varian, j))


def _terpilih(varian: str, banyak: int, indeks: int) -> tuple:
    kolam = _kolam(varian, banyak)
    langkah = max(1, len(kolam) // ANGGOTA_PER_KELOMPOK)
    return kolam[indeks % langkah::langkah]


def _tanya_kelompok(varian: str, banyak: int) -> tuple:
    return tuple(range(banyak)) if varian in VARIAN_BERTANYA else (None,)


@lru_cache(maxsize=None)
def _domain_varian(varian: str) -> tuple:
    """Anggota satu varian: (tema, skala, jumlah tuple, tanya); urutan enumerasi = urutan undian."""
    hasil = []
    for indeks, (tema, banyak, skala) in enumerate(_kelompok(varian)):
        for jumlah in _terpilih(varian, banyak, indeks):
            for tanya in _tanya_kelompok(varian, banyak):
                if hitung_kunci(varian, jumlah, skala, tanya) <= KUNCI_MAKS:
                    hasil.append((tema, skala, jumlah, tanya))
    return tuple(hasil)


@lru_cache(maxsize=None)
def _anggota_set(varian: str) -> frozenset:
    return frozenset(_domain_varian(varian))


def _parameter(varian: str, anggota: tuple) -> dict:
    tema, skala, jumlah, tanya = anggota
    isi = {"varian": varian, "tema": tema, "skala": skala, "jumlah": list(jumlah)}
    return isi if tanya is None else {**isi, "tanya": tanya}


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError(PESAN_LEVEL)


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict dan daftar baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(_parameter(v, a) for v in VARIAN for a in _domain_varian(v))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu anggota seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return _parameter(varian, rng.choice(_domain_varian(varian)))


# ── validasi dan soal ────────────────────────────────────────────────────

def _anggota_dari(varian, isi: dict):
    """Anggota domain dari parameter mentah (tipe int murni), atau None bila bentuknya salah."""
    bertanya = varian in VARIAN_BERTANYA
    if set(isi) != set(FIELD_DASAR) | ({"tanya"} if bertanya else set()):
        return None
    tema, skala, jumlah = isi["tema"], isi["skala"], isi["jumlah"]
    tanya = isi.get("tanya")
    if type(tema) is not str or type(skala) is not int or type(jumlah) is not list:
        return None
    if any(type(n) is not int for n in jumlah) or (bertanya and type(tanya) is not int):
        return None
    return (tema, skala, tuple(jumlah), tanya)


def _sah(varian, isi: dict) -> bool:
    """Parameter sah = anggota domain (bool, float, dan teks ditolak)."""
    if type(varian) is not str or varian not in VARIAN:
        return False
    anggota = _anggota_dari(varian, isi)
    return anggota is not None and anggota in _anggota_set(varian)


def piktogram_lima_awal(varian: str, **isi) -> Soal:
    """Piktogram berskala: baca satu kategori, selisih terbanyak-tersedikit, total, rata-rata, atau kebalikan."""
    if not _sah(varian, isi):
        raise ValueError(PESAN_LUAR_DOMAIN)
    tema, skala, jumlah, tanya = isi["tema"], isi["skala"], tuple(isi["jumlah"]), isi.get("tanya")
    kunci = str(hitung_kunci(varian, jumlah, skala, tanya))
    return Soal(
        template_id=TEMPLATE_ID, parameter=_parameter(varian, (tema, skala, jumlah, tanya)),
        teks=_teks(varian, tema, skala, jumlah, tanya), kunci=kunci,
        malrule=saring_malrule(kunci, _kandidat(varian, tema, jumlah, skala, tanya)),
        pembahasan=_pembahasan(varian, tema, jumlah, skala, tanya, kunci), bagian="A")
