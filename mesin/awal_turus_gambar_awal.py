"""Matematika Awal, jenis `turus_gambar_awal`: membaca diagram turus teks (P2).

Data ditampilkan sebagai turus teks, satu baris per kategori, tiga kategori:

    Rina menghitung buah di keranjang dengan turus. Satu garis (|) berarti satu buah, dan tiap lima garis dikelompokkan.
    Apel: ||||| ||
    Jeruk: |||
    Pisang: ||||
    Berapa buah apel?

Tiap kategori punya 1..12 garis, ditulis dalam kelompok lima yang dipisah spasi
(`|||||`) lalu sisanya. Keempat bentuk soal (`varian`):
  - `baca`: "Berapa buah apel?" (angka);
  - `terbanyak`: "Buah apa yang paling banyak?" (nama kategori, huruf kecil);
  - `selisih`: "Berapa buah lebih banyak apel daripada jeruk?" (angka; yang
    ditanya selalu yang lebih banyak, jadi hasilnya tak pernah nol atau negatif);
  - `jumlah`: "Berapa buah semuanya?" (angka).

Tiga jumlah garis dalam satu soal SELALU berbeda: kategori terbanyak jadi tunggal
dan "yang lebih banyak" tak pernah ambigu. Soal teks saja, tanpa gambar; baris
terakhir teks adalah pertanyaan (renderer mengikuti kebiasaan "baris terakhir
= tanya"). Jumlah garis dibaca dengan MENGHITUNG karakter `|` pada tiap baris
kategori; baris pengantar memuat satu `|` di dalam tanda kurung dan tidak dihitung.

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti
dari satu jawaban: kelompok lima garis dihitung sebagai satu garis (K, hanya bila
jawabannya memang berbeda dari kunci), membaca baris kategori lain atau menyebut
kategori yang salah (K), menjumlah bukan mengurang (K), dan terlewat satu garis (H,
kurang satu). Jalur K selalu ada di setiap parameter sah.

Domain eksplisit (`domain_parameter`): 220 himpunan tiga angka berbeda dari 1..12, tiap
himpunan satu susunan tetap (lihat `_triple_jumlah`), dua tema, dan tiap cabang. Domain
ini bagian dari ruang parameter yang SAH: `turus_gambar_awal(...)` tetap menerima susunan
angka lain asal tiga angka berbeda dalam 1..12. Generator membangun seluruh domain tiap
kali menyusun lembar, jadi domain sengaja dijaga kecil (3.520). Sampler mengundi varian lebih dulu (seragam),
baru parameter di dalam varian itu, hanya dari domain dan hanya lewat `rng` (tanpa
`hash()`). Daftar TEMA bersifat APPEND-ONLY menurut indeks: indeks ikut dalam
identitas soal di bank. Nilai `jumlah` dalam parameter berupa list tiga bilangan
(urutan = urutan kategori pada TEMA).
"""
from __future__ import annotations

from functools import lru_cache
from itertools import combinations, permutations
import random
from typing import NamedTuple

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "turus_gambar_awal"
LEVEL = ("P2",)
VARIAN = ("baca", "terbanyak", "selisih", "jumlah")
PESAN_LUAR_DOMAIN = "parameter turus gambar awal di luar domain"

TURUS_MIN, TURUS_MAKS = 1, 12
JUMLAH_KATEGORI = 3
KELOMPOK = 5


class Tema(NamedTuple):
    tokoh: str
    kumpulan: str  # yang dihitung, setelah "menghitung"
    jenis: str  # untuk "<Jenis> apa yang paling banyak?"
    satuan: str  # untuk "Berapa <satuan> ...?"
    nama: tuple  # tiga kategori, berawalan huruf besar


# APPEND-ONLY menurut indeks. Nama kategori hanya huruf (tanpa angka) agar sah sebagai kunci teks.
TEMA = (
    Tema("Rina", "buah di keranjang", "buah", "buah", ("Apel", "Jeruk", "Pisang")),
    Tema("Budi", "hewan di halaman", "hewan", "ekor", ("Kucing", "Ayam", "Bebek")),
)

FIELD = {
    "baca": ("tema", "jumlah", "tanya"),
    "terbanyak": ("tema", "jumlah"),
    "selisih": ("tema", "jumlah", "besar", "kecil"),
    "jumlah": ("tema", "jumlah"),
}


# ── validasi parameter ───────────────────────────────────────────────────

def _int_antara(nilai, bawah: int, atas: int) -> bool:
    return type(nilai) is int and bawah <= nilai <= atas


def _jumlah_sah(jumlah) -> bool:
    if type(jumlah) not in (list, tuple) or len(jumlah) != JUMLAH_KATEGORI:
        return False
    if not all(_int_antara(n, TURUS_MIN, TURUS_MAKS) for n in jumlah):
        return False
    return len(set(jumlah)) == JUMLAH_KATEGORI


def _indeks(nilai) -> bool:
    return _int_antara(nilai, 0, JUMLAH_KATEGORI - 1)


def _sah(varian, isi: dict) -> bool:
    if type(varian) is not str or varian not in FIELD or set(isi) != set(FIELD[varian]):
        return False
    if not _int_antara(isi["tema"], 0, len(TEMA) - 1) or not _jumlah_sah(isi["jumlah"]):
        return False
    if varian == "baca":
        return _indeks(isi["tanya"])
    if varian == "selisih":
        besar, kecil = isi["besar"], isi["kecil"]
        return _indeks(besar) and _indeks(kecil) and isi["jumlah"][besar] > isi["jumlah"][kecil]
    return True


# ── soal per varian: (teks, kunci, kandidat malrule, pembahasan) ─────────

def _mal(nama: str, jawaban, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _turus(n: int) -> str:
    """n garis, tiap lima dikelompokkan: 7 -> '||||| ||'."""
    kelompok = ["|" * KELOMPOK] * (n // KELOMPOK) + (["|" * (n % KELOMPOK)] if n % KELOMPOK else [])
    return " ".join(kelompok)


def _skor_kelompok(n: int) -> int:
    """Banyak garis bila tiap kelompok lima keliru dihitung sebagai satu garis."""
    return n // KELOMPOK + n % KELOMPOK


def _hitung_baris(n: int) -> str:
    """Cara menghitung satu baris dengan penjumlahan berulang (tanpa perkalian): 12 -> 5 + 5 + 2 = 12."""
    kelompok, sisa = divmod(n, KELOMPOK)
    if kelompok == 0:
        return f"{n} garis"
    awal = f"{kelompok} kelompok lima" + (f" dan {sisa} garis sisa" if sisa else "")
    bagian = [KELOMPOK] * kelompok + ([sisa] if sisa else [])
    if len(bagian) == 1:
        return f"{awal}, jadi {n}"
    return f"{awal}, jadi {' + '.join(str(b) for b in bagian)} = {n}"


def _teks_data(tema: Tema, jumlah: list, pertanyaan: str) -> str:
    pengantar = (f"{tema.tokoh} menghitung {tema.kumpulan} dengan turus. Satu garis (|) berarti "
                 f"satu {tema.satuan}, dan tiap lima garis dikelompokkan.")
    baris = [f"{nama}: {_turus(n)}" for nama, n in zip(tema.nama, jumlah)]
    return "\n".join([pengantar, *baris, pertanyaan])


def _rekap(tema: Tema, jumlah: list) -> str:
    return ", ".join(f"{nama} {n}" for nama, n in zip(tema.nama, jumlah))


def _mal_kelompok(skor: int, kunci: int, alasan: str) -> list:
    """Satu malrule K bila hasil salah-kelompok memang berbeda dari kunci dan bilangan positif."""
    if skor == kunci or skor < 1:
        return []
    return [_mal("kelompok_dihitung_satu", skor, "K", alasan)]


def _bangun_baca(tema: int, jumlah: list, tanya: int) -> tuple:
    t, n = TEMA[tema], jumlah[tanya]
    nama = t.nama[tanya].lower()
    teks = _teks_data(t, jumlah, f"Berapa {t.satuan} {nama}?")
    pembahasan = (f"Hitung garis pada baris {t.nama[tanya]}: {_hitung_baris(n)}. "
                  f"Jadi ada {n} {t.satuan} {nama}.")
    kandidat = _mal_kelompok(
        _skor_kelompok(n), n,
        f"Menghitung tiap kelompok lima garis sebagai satu garis saja, sehingga jawabannya "
        f"{_skor_kelompok(n)}.")
    kandidat += [
        _mal(f"salah_baris_{j + 1}", jumlah[j], "K",
             f"Membaca baris {t.nama[j]} sehingga jawabannya {jumlah[j]}, bukan baris {t.nama[tanya]}.")
        for j in range(JUMLAH_KATEGORI) if j != tanya]
    if n > 1:
        kandidat.append(_mal(
            "terlewat_satu", n - 1, "H",
            "Sudah mengerti caranya, tetapi satu garis terlewat sehingga jawabannya kurang satu."))
    return teks, str(n), kandidat, pembahasan


def _bangun_terbanyak(tema: int, jumlah: list) -> tuple:
    t = TEMA[tema]
    urut = sorted(range(JUMLAH_KATEGORI), key=lambda i: -jumlah[i])
    puncak, kedua, sedikit = urut
    kunci = t.nama[puncak].lower()
    teks = _teks_data(t, jumlah, f"{t.jenis.capitalize()} apa yang paling banyak?")
    pembahasan = (f"Hitung garis tiap baris: {_rekap(t, jumlah)}. "
                  f"Yang jumlahnya paling besar adalah {t.nama[puncak]} ({jumlah[puncak]}). "
                  f"Jadi yang paling banyak adalah {kunci}.")
    skor = [_skor_kelompok(n) for n in jumlah]
    kandidat = []
    salah = max(range(JUMLAH_KATEGORI), key=lambda i: skor[i])
    if sorted(skor, reverse=True)[0] != sorted(skor, reverse=True)[1] and salah != puncak:
        kandidat.append(_mal(
            "kelompok_dihitung_satu", t.nama[salah].lower(), "K",
            f"Menghitung tiap kelompok lima garis sebagai satu garis, sehingga {t.nama[salah]} "
            "tampak paling banyak."))
    kandidat += [
        _mal("kedua_terbanyak", t.nama[kedua].lower(), "K",
             f"Menyebut {t.nama[kedua]}, yang jumlahnya nomor dua, kemungkinan salah "
             "membandingkan jumlah garis tiap baris."),
        _mal("paling_sedikit", t.nama[sedikit].lower(), "K",
             f"Menyebut {t.nama[sedikit]}, yang paling sedikit, kemungkinan tertukar antara "
             "'paling banyak' dan 'paling sedikit'."),
    ]
    return teks, kunci, kandidat, pembahasan


def _bangun_selisih(tema: int, jumlah: list, besar: int, kecil: int) -> tuple:
    t = TEMA[tema]
    nb, nk = jumlah[besar], jumlah[kecil]
    selisih = nb - nk
    ab, ak = t.nama[besar], t.nama[kecil]
    teks = _teks_data(t, jumlah, f"Berapa {t.satuan} lebih banyak {ab.lower()} daripada {ak.lower()}?")
    pembahasan = (f"{ab} ada {nb} dan {ak} ada {nk}. Cari selisihnya dengan mengurangkan: "
                  f"{nb} - {nk} = {selisih}. Jadi {ab.lower()} lebih banyak {selisih} {t.satuan} "
                  f"daripada {ak.lower()}.")
    kandidat = [_mal(
        "dijumlah", nb + nk, "K",
        f"Menjumlahkan garis {ab} dan {ak} sehingga jawabannya {nb + nk}, "
        "padahal 'lebih banyak' berarti dicari selisihnya.")]
    kandidat += _mal_kelompok(
        abs(_skor_kelompok(nb) - _skor_kelompok(nk)), selisih,
        "Menghitung tiap kelompok lima garis sebagai satu garis saja, sehingga selisihnya salah.")
    kandidat.append(_mal(
        "satu_baris_saja", nb, "K",
        f"Menyebut jumlah garis {ab} saja ({nb}), belum mengurangkannya dengan {ak}."))
    if selisih > 1:
        kandidat.append(_mal(
            "terlewat_satu", selisih - 1, "H",
            "Sudah mengerti caranya, tetapi satu garis terlewat sehingga jawabannya kurang satu."))
    return teks, str(selisih), kandidat, pembahasan


def _bangun_jumlah(tema: int, jumlah: list) -> tuple:
    t = TEMA[tema]
    total = sum(jumlah)
    teks = _teks_data(t, jumlah, f"Berapa {t.satuan} semuanya?")
    tambah = " + ".join(str(n) for n in jumlah)
    pembahasan = (f"Hitung garis tiap baris: {_rekap(t, jumlah)}. Jumlahkan semuanya: "
                  f"{tambah} = {total}. Jadi semuanya {total} {t.satuan}.")
    kandidat = _mal_kelompok(
        sum(_skor_kelompok(n) for n in jumlah), total,
        "Menghitung tiap kelompok lima garis sebagai satu garis saja, sehingga jumlahnya kurang.")
    kandidat += [
        _mal(f"lupa_baris_{i + 1}", total - jumlah[i], "K",
             f"Lupa menambahkan baris {t.nama[i]} sehingga jawabannya {total - jumlah[i]}.")
        for i in range(JUMLAH_KATEGORI)]
    kandidat.append(_mal(
        "terlewat_satu", total - 1, "H",
        "Sudah mengerti caranya, tetapi satu garis terlewat sehingga jawabannya kurang satu."))
    return teks, str(total), kandidat, pembahasan


_BANGUN = {"baca": _bangun_baca, "terbanyak": _bangun_terbanyak,
           "selisih": _bangun_selisih, "jumlah": _bangun_jumlah}


def turus_gambar_awal(varian: str, **isi) -> Soal:
    """Baca turus, kategori terbanyak, selisih, atau jumlah semua (kunci dari parameter)."""
    if not _sah(varian, isi):
        raise ValueError(PESAN_LUAR_DOMAIN)
    isi = {**isi, "jumlah": list(isi["jumlah"])}
    teks, kunci, kandidat, pembahasan = _BANGUN[varian](**isi)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isi},
        teks=teks, kunci=kunci, malrule=saring_malrule(kunci, kandidat),
        pembahasan=pembahasan, bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _triple_jumlah() -> tuple:
    """Satu susunan untuk tiap himpunan tiga angka berbeda dari 1..12 (220 himpunan).

    Susunan dipilih tetap menurut jumlah angkanya, jadi kategori terbanyak bergantian
    tanpa mengalikan ruang domain enam kali (domain dibangun penuh tiap lembar oleh
    generator, jadi ukurannya dijaga kecil). Validasi soal tetap menerima susunan lain.
    """
    susunan = tuple(permutations(range(JUMLAH_KATEGORI)))
    hasil = []
    for himpunan in combinations(range(TURUS_MIN, TURUS_MAKS + 1), JUMLAH_KATEGORI):
        urut = susunan[sum(himpunan) % len(susunan)]
        hasil.append(tuple(himpunan[i] for i in urut))
    return tuple(hasil)


def _enumerasi(varian: str) -> list:
    hasil = []
    for tema in range(len(TEMA)):
        for jumlah in _triple_jumlah():
            dasar = {"varian": varian, "tema": tema, "jumlah": jumlah}
            if varian == "baca":
                hasil += [{**dasar, "tanya": t} for t in range(JUMLAH_KATEGORI)]
            elif varian == "selisih":
                hasil += [{**dasar, "besar": i, "kecil": j}
                          for i in range(JUMLAH_KATEGORI) for j in range(JUMLAH_KATEGORI)
                          if jumlah[i] > jumlah[j]]
            else:
                hasil.append(dasar)
    return hasil


@lru_cache(maxsize=None)
def _domain_beku() -> dict:
    """Varian -> tuple item immutable (jumlah berupa tuple); urutan enumerasi = urutan undian."""
    return {v: tuple(tuple(p.items()) for p in _enumerasi(v)) for v in VARIAN}


def _segar(item: tuple) -> dict:
    """Dict baru dari item beku; jumlah menjadi list baru supaya domain tak bisa dinodai."""
    return {k: (list(v) if k == "jumlah" else v) for k, v in item}


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level turus gambar awal harus P2")


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict dan list baru setiap panggilan."""
    _pastikan_level(level)
    beku = _domain_beku()
    return tuple(_segar(item) for v in VARIAN for item in beku[v])


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu undian seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return _segar(rng.choice(_domain_beku()[varian]))
