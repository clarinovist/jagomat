"""Matematika Awal, jenis `ukur_sudut_awal`: mengukur dan membandingkan sudut dengan busur derajat (P5).

Melatih K5 B6 "Sudut": mengukur sudut dengan busur derajat yang punya DUA skala (luar dan dalam),
membandingkan sudut, dan menggolongkan sudut. Hubungan antarsudut (pelurus, segitiga) sudah dilatih
keluarga `geometri-datar` dan TIDAK diulang di sini. Lima bentuk soal (`varian`):
  - `baca_dari_nol`: satu kaki sudut ada di garis alas pada angka 0 (sisi kanan atau kiri), kaki lain
    di sudut x (kelipatan 5, 10..170, tanpa 90); anak harus memakai skala yang dimulai dari 0 di
    kaki alas (kunci: x). Kebalikannya (180 - x) ada pada skala satunya;
  - `baca_geser`: kedua kaki BUKAN di angka 0, pada skala yang sama di angka a dan b (kelipatan 10,
    a != b); besar sudut = selisihnya (kunci: |b - a|);
  - `jenis_sudut`: seperti `baca_dari_nol` tetapi tanpa batasan 90, ditanya jenisnya (kunci: "lancip"
    bila x < 90, "siku" bila x = 90, "tumpul" bila x > 90);
  - `banding`: tiga sinar OA (di angka 0), OB di b, OC di c (kelipatan 10, b != c); "Sudut mana yang
    lebih besar, AOB atau AOC?" (kunci: huruf "B" atau "C");
  - `selisih_dua`: sinar sama seperti `banding`, ditanya selisih besar kedua sudut (kunci: |b - c|).
Kunci sudut sampai 170 (bukan <= 100 seperti jenis lain): busur derajat memang berskala 0..180.

Dua bentuk penyajian (aturan teks vs visual):
  - TEKS (tanpa flag visual, juga lembar cetak): kalimat pertama melukiskan letak kaki sudut pada
    skala. Pada `baca_dari_nol`, `jenis_sudut`, `banding`, dan `selisih_dua` tiap kaki bukan-alas
    disebut angkanya pada KEDUA skala ("angka 70 pada skala luar dan angka 110 pada skala dalam")
    dan kaki alas disebut berada di angka 0 pada salah satu skala, jadi soal bisa dijawab dari teks
    dan tetap menguji pemilihan skala. `baca_geser` menyebut kedua angka pada skala luar;
  - VISUAL (flag `matematika-awal`, proyektor di `topic_matematika_awal_busur_visual`): teks
    proyeksi "Perhatikan gambar busur derajat." tanpa angka; gambar busur membawa informasinya.
Skala luar dimulai dari 0 di sisi kanan, skala dalam dari 0 di sisi kiri (seperti gambar).

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu
jawaban: membaca skala yang salah (180 - x, atau jenis lawannya), lupa mengurangkan, mencampur dua
skala, menjumlahkan alih-alih mengurangkan (K); meleset 5 atau 10 derajat, atau membulatkan sudut
yang hampir siku menjadi siku (H). Jalur K selalu ada. Pilihan ganda: `jenis_sudut` memakai tiga
kata jenis, `banding` memakai "B", "C", dan "sama besar" (lihat `pengecoh_tambahan`).

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu anggota seragam dari
domain varian itu memakai `rng` (tanpa `hash()`). Urutan enumerasi: `baca_dari_nol` arah -> sudut;
`baca_geser` a -> b; `jenis_sudut` arah -> sudut; `banding` arah -> b -> c; `selisih_dua` arah -> b -> c.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "ukur_sudut_awal"
LEVEL = ("P5",)
VARIAN = ("baca_dari_nol", "baca_geser", "jenis_sudut", "banding", "selisih_dua")
ARAH = ("kanan", "kiri")
PESAN_LUAR_DOMAIN = "parameter ukur sudut awal di luar domain"
PESAN_LEVEL = "level ukur sudut awal harus P5"

SUDUT_MIN, SUDUT_MAKS, SUDUT_SIKU, SUDUT_LURUS = 10, 170, 90, 180
LANGKAH_TUNGGAL, LANGKAH_PASANG = 5, 10
SELISIH_SALAH_BESAR, SELISIH_SALAH_KECIL = 10, 5  # meleset satu angka besar atau satu tanda kecil
DEKAT_SIKU = 10  # sudut sejauh ini dari 90 mudah dibulatkan menjadi siku
SAMA_BESAR = "sama besar"

JENIS_LANCIP, JENIS_SIKU, JENIS_TUMPUL = "lancip", "siku", "tumpul"
SKALA_NOL = {"kanan": "luar", "kiri": "dalam"}  # skala yang bernilai 0 di kaki alas
SKALA_LAIN = {"kanan": "dalam", "kiri": "luar"}
PETUNJUK_ANGKA = "Tulis angkanya saja."

FIELD = {
    "baca_dari_nol": ("arah", "sudut"),
    "baca_geser": ("a", "b"),
    "jenis_sudut": ("arah", "sudut"),
    "banding": ("arah", "b", "c"),
    "selisih_dua": ("arah", "b", "c"),
}


# ── hitungan ─────────────────────────────────────────────────────────────

def jenis_dari_sudut(sudut: int) -> str:
    """Golongan sudut menurut besarnya."""
    if sudut < SUDUT_SIKU:
        return JENIS_LANCIP
    return JENIS_SIKU if sudut == SUDUT_SIKU else JENIS_TUMPUL


def sudut_lawan(sudut: int) -> int:
    """Angka yang sama pada skala satunya (jumlah kedua skala selalu 180)."""
    return SUDUT_LURUS - sudut


def huruf_lebih_besar(b: int, c: int) -> str:
    return "B" if b > c else "C"


# ── validasi parameter ───────────────────────────────────────────────────

def _int_kelipatan(nilai, bawah: int, atas: int, langkah: int) -> bool:
    return type(nilai) is int and bawah <= nilai <= atas and nilai % langkah == 0


def _arah_sah(arah) -> bool:
    return type(arah) is str and arah in ARAH


def _sudut_pasang(nilai) -> bool:
    return _int_kelipatan(nilai, SUDUT_MIN, SUDUT_MAKS, LANGKAH_PASANG)


def _sah_baca_dari_nol(arah, sudut) -> bool:
    return (_arah_sah(arah) and _int_kelipatan(sudut, SUDUT_MIN, SUDUT_MAKS, LANGKAH_TUNGGAL)
            and sudut != SUDUT_SIKU)


def _sah_jenis(arah, sudut) -> bool:
    return _arah_sah(arah) and _int_kelipatan(sudut, SUDUT_MIN, SUDUT_MAKS, LANGKAH_TUNGGAL)


def _sah_geser(a, b) -> bool:
    return _sudut_pasang(a) and _sudut_pasang(b) and a != b


def _sah_pasang(arah, b, c) -> bool:
    return _arah_sah(arah) and _sudut_pasang(b) and _sudut_pasang(c) and b != c


_SAH = {"baca_dari_nol": _sah_baca_dari_nol, "baca_geser": _sah_geser, "jenis_sudut": _sah_jenis,
        "banding": _sah_pasang, "selisih_dua": _sah_pasang}


def _sah(varian, isi: dict) -> bool:
    if type(varian) is not str or varian not in FIELD:
        return False
    if set(isi) != set(FIELD[varian]):
        return False
    return _SAH[varian](**isi)


# ── teks ─────────────────────────────────────────────────────────────────

def _kaki_nol(titik: str, arah: str) -> str:
    return f"Kaki {titik}A menunjuk angka 0 pada skala {SKALA_NOL[arah]} busur derajat."


def _kaki_dua_skala(titik: str, huruf: str, sudut: int, arah: str) -> str:
    nol, lain = SKALA_NOL[arah], SKALA_LAIN[arah]
    return (f"Kaki {titik}{huruf} menunjuk angka {sudut} pada skala {nol} "
            f"dan angka {sudut_lawan(sudut)} pada skala {lain}.")


def pengantar_teks(varian: str, isi: dict) -> str:
    """Baris pertama versi TEKS: letak kaki sudut pada skala ditulis supaya soal bisa dijawab."""
    if varian == "baca_geser":
        return (f"Pada skala luar busur derajat, kaki BA menunjuk angka {isi['a']} "
                f"dan kaki BC menunjuk angka {isi['b']}.")
    arah = isi["arah"]
    if varian in ("baca_dari_nol", "jenis_sudut"):
        return f"{_kaki_nol('B', arah)} {_kaki_dua_skala('B', 'C', isi['sudut'], arah)}"
    return (f"{_kaki_nol('O', arah)} {_kaki_dua_skala('O', 'B', isi['b'], arah)} "
            f"{_kaki_dua_skala('O', 'C', isi['c'], arah)}")


def pertanyaan(varian: str) -> str:
    """Baris pertanyaan (terakhir) tiap varian; juga dipakai proyektor visual untuk memeriksa teks."""
    if varian in ("baca_dari_nol", "baca_geser"):
        return f"Berapa besar sudut ABC? {PETUNJUK_ANGKA}"
    if varian == "jenis_sudut":
        return (f"Sudut ABC termasuk jenis apa? Tulis {JENIS_LANCIP}, {JENIS_SIKU}, "
                f"atau {JENIS_TUMPUL}.")
    if varian == "banding":
        return "Sudut mana yang lebih besar, AOB atau AOC? Tulis B atau C."
    return f"Berapa selisih besar sudut AOB dan sudut AOC? {PETUNJUK_ANGKA}"


# ── kunci, pembahasan, malrule ───────────────────────────────────────────

def _mal(nama: str, jawaban, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _meleset(nilai: int, jawaban_sah) -> list:
    """Malrule H: meleset satu angka besar atau satu tanda kecil (hanya yang masih sah)."""
    hasil = []
    for nama, geser in (("lebih_sepuluh", SELISIH_SALAH_BESAR), ("kurang_sepuluh", -SELISIH_SALAH_BESAR),
                        ("lebih_lima", SELISIH_SALAH_KECIL), ("kurang_lima", -SELISIH_SALAH_KECIL)):
        baru = nilai + geser
        if jawaban_sah(baru):
            hasil.append(_mal(nama, baru, "H",
                              "Sudah mengerti caranya, tetapi meleset "
                              f"{abs(geser)} derajat saat membaca angka pada skala."))
    return hasil


def _sah_sudut(angka: int) -> bool:
    return LANGKAH_TUNGGAL <= angka <= SUDUT_LURUS


def _malrule_baca_dari_nol(arah: str, sudut: int) -> list:
    lawan = sudut_lawan(sudut)
    salah = _mal("salah_skala", lawan, "K",
                 f"Membaca angka {lawan} pada skala {SKALA_LAIN[arah]}, padahal skala yang dipakai "
                 f"harus yang bernilai 0 di kaki BA, yaitu skala {SKALA_NOL[arah]}.")
    return [salah] + _meleset(sudut, _sah_sudut)


def _kata_jenis_salah(sudut: int) -> list:
    """Hipotesis jawaban jenis yang salah: (nama, jawaban, kode, alasan)."""
    jenis = jenis_dari_sudut(sudut)
    if jenis == JENIS_SIKU:
        return [("lancip_untuk_siku", JENIS_LANCIP, "K",
                 "Mengira sudut siku termasuk sudut lancip, padahal sudut 90 derajat adalah siku."),
                ("tumpul_untuk_siku", JENIS_TUMPUL, "K",
                 "Mengira sudut siku termasuk sudut tumpul, padahal sudut 90 derajat adalah siku.")]
    lawan = JENIS_TUMPUL if jenis == JENIS_LANCIP else JENIS_LANCIP
    hasil = [("salah_skala", lawan, "K",
              "Membaca skala yang salah sehingga angkanya menjadi 180 dikurangi besar sudut, "
              "dan golongan sudutnya jadi terbalik.")]
    if abs(sudut - SUDUT_SIKU) <= DEKAT_SIKU:
        hasil.append(("dibulatkan_siku", JENIS_SIKU, "H",
                      "Sudah mengerti caranya, tetapi sudut yang hampir 90 derajat dibulatkan "
                      "menjadi sudut siku."))
    return hasil


def _malrule_jenis(sudut: int) -> list:
    return [_mal(nama, jawaban, kode, alasan) for nama, jawaban, kode, alasan in _kata_jenis_salah(sudut)]


def _malrule_geser(a: int, b: int) -> list:
    selisih, besar = abs(b - a), max(a, b)
    kandidat = [_mal("lupa_kurangi", besar, "K",
                     f"Menjawab angka kaki yang lebih jauh ({besar}), padahal besar sudut adalah "
                     "selisih kedua angka karena tidak ada kaki di angka 0.")]
    campur = abs(a + b - SUDUT_LURUS)
    if campur > 0:
        kandidat.append(_mal("campur_skala", campur, "K",
                             "Membaca satu kaki pada skala luar dan kaki lainnya pada skala dalam, "
                             "lalu mengurangkannya; kedua kaki harus dibaca pada skala yang sama."))
    if a + b <= SUDUT_LURUS:
        kandidat.append(_mal("jumlah_bukan_selisih", a + b, "K",
                             f"Menjumlahkan kedua angka ({a} + {b}), padahal besar sudut dicari "
                             "dengan mengurangkan."))
    return kandidat + _meleset(selisih, _sah_sudut)


def _malrule_banding(b: int, c: int) -> list:
    lain = "C" if huruf_lebih_besar(b, c) == "B" else "B"
    return [_mal("salah_skala", lain, "K",
                 "Membandingkan angka pada skala yang bukan dimulai dari 0 di kaki OA, sehingga "
                 "angka yang tampak lebih besar justru milik sudut yang lebih kecil.")]


def _malrule_selisih(b: int, c: int) -> list:
    selisih, besar = abs(b - c), max(b, c)
    kandidat = [_mal("sudut_besar_saja", besar, "K",
                     f"Menjawab besar sudut yang lebih besar saja ({besar}), padahal yang ditanya "
                     "selisih kedua sudut.")]
    campur = abs(SUDUT_LURUS - b - c)
    if campur > 0:
        kandidat.append(_mal("campur_skala", campur, "K",
                             "Membaca satu sudut pada skala luar dan sudut lainnya pada skala "
                             "dalam, lalu mengurangkannya; kedua sudut harus dibaca pada skala yang sama."))
    if b + c <= SUDUT_LURUS:
        kandidat.append(_mal("jumlah_bukan_selisih", b + c, "K",
                             f"Menjumlahkan kedua sudut ({b} + {c}), padahal yang ditanya selisihnya."))
    return kandidat + _meleset(selisih, _sah_sudut)


def _kalimat_jenis(sudut: int) -> str:
    jenis = jenis_dari_sudut(sudut)
    if jenis == JENIS_LANCIP:
        return "Sudut itu lebih kecil dari 90 derajat, jadi sudut lancip."
    if jenis == JENIS_SIKU:
        return "Sudut itu tepat 90 derajat, jadi sudut siku."
    return "Sudut itu lebih besar dari 90 derajat dan kurang dari 180 derajat, jadi sudut tumpul."


def _pembahasan_nol(arah: str, sudut: int) -> str:
    nol, lain = SKALA_NOL[arah], SKALA_LAIN[arah]
    return (f"Kaki BA ada di angka 0 pada skala {nol}, jadi sudutnya dibaca pada skala {nol}. "
            f"Kaki BC menunjuk angka {sudut} pada skala itu. Angka {sudut_lawan(sudut)} pada skala "
            f"{lain} tidak dipakai karena skala itu tidak dimulai dari 0 di kaki BA.")


def _pembahasan_geser(a: int, b: int) -> str:
    kecil, besar = sorted((a, b))
    return (f"Kedua kaki dibaca pada skala yang sama: kaki BA di angka {a} dan kaki BC di angka {b}. "
            f"Tidak ada kaki di angka 0, jadi besar sudut adalah selisihnya: {besar} dikurangi "
            f"{kecil} sama dengan {besar - kecil}. Jadi sudut ABC besarnya {besar - kecil} derajat.")


def _pembahasan_banding(arah: str, b: int, c: int) -> str:
    nol = SKALA_NOL[arah]
    pemenang = huruf_lebih_besar(b, c)
    besar, kecil = max(b, c), min(b, c)
    return (f"Kaki OA ada di angka 0 pada skala {nol}. Pada skala itu kaki OB menunjuk angka {b} dan "
            f"kaki OC menunjuk angka {c}. Angka {besar} lebih besar dari {kecil}, jadi sudut AO{pemenang} "
            f"yang lebih besar. Jawabannya {pemenang}.")


def _pembahasan_selisih(arah: str, b: int, c: int) -> str:
    nol = SKALA_NOL[arah]
    besar, kecil = max(b, c), min(b, c)
    return (f"Kaki OA ada di angka 0 pada skala {nol}. Pada skala itu kaki OB menunjuk angka {b} dan "
            f"kaki OC menunjuk angka {c}. Selisihnya {besar} dikurangi {kecil} sama dengan "
            f"{besar - kecil}. Jadi selisih besar kedua sudut adalah {besar - kecil} derajat.")


# ── soal ─────────────────────────────────────────────────────────────────

def _isi_baca_dari_nol(arah: str, sudut: int) -> tuple:
    pembahasan = f"{_pembahasan_nol(arah, sudut)} Jadi sudut ABC besarnya {sudut} derajat."
    return str(sudut), _malrule_baca_dari_nol(arah, sudut), pembahasan


def _isi_geser(a: int, b: int) -> tuple:
    return str(abs(b - a)), _malrule_geser(a, b), _pembahasan_geser(a, b)


def _isi_jenis(arah: str, sudut: int) -> tuple:
    jenis = jenis_dari_sudut(sudut)
    pembahasan = (f"{_pembahasan_nol(arah, sudut)} Jadi sudut ABC besarnya {sudut} derajat. "
                  f"{_kalimat_jenis(sudut)}")
    return jenis, _malrule_jenis(sudut), pembahasan


def _isi_banding(arah: str, b: int, c: int) -> tuple:
    return huruf_lebih_besar(b, c), _malrule_banding(b, c), _pembahasan_banding(arah, b, c)


def _isi_selisih(arah: str, b: int, c: int) -> tuple:
    return str(abs(b - c)), _malrule_selisih(b, c), _pembahasan_selisih(arah, b, c)


_ISI = {"baca_dari_nol": _isi_baca_dari_nol, "baca_geser": _isi_geser, "jenis_sudut": _isi_jenis,
        "banding": _isi_banding, "selisih_dua": _isi_selisih}


def ukur_sudut_awal(varian: str, **isi) -> Soal:
    """Busur derajat: baca dari 0, baca selisih, golongkan, banding, atau selisih dua sudut."""
    if not _sah(varian, isi):
        raise ValueError(PESAN_LUAR_DOMAIN)
    kunci, kandidat, pembahasan = _ISI[varian](**isi)
    teks = f"{pengantar_teks(varian, isi)}\n{pertanyaan(varian)}"
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isi},
        teks=teks, kunci=kunci, malrule=saring_malrule(kunci, kandidat),
        pembahasan=pembahasan, bagian="A")


def pengecoh_tambahan(parameter: dict) -> tuple:
    """Pengecoh PG selain malrule (bukan hipotesis kesalahan): kata jenis lain atau "sama besar"."""
    if parameter["varian"] == "jenis_sudut":
        return (JENIS_LANCIP, JENIS_SIKU, JENIS_TUMPUL)
    if parameter["varian"] == "banding":
        return (SAMA_BESAR,)
    return ()


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi(varian: str) -> list:
    tunggal = range(SUDUT_MIN, SUDUT_MAKS + 1, LANGKAH_TUNGGAL)
    pasang = range(SUDUT_MIN, SUDUT_MAKS + 1, LANGKAH_PASANG)
    if varian == "baca_dari_nol":
        return [{"varian": varian, "arah": arah, "sudut": s}
                for arah in ARAH for s in tunggal if s != SUDUT_SIKU]
    if varian == "jenis_sudut":
        return [{"varian": varian, "arah": arah, "sudut": s} for arah in ARAH for s in tunggal]
    if varian == "baca_geser":
        return [{"varian": varian, "a": a, "b": b} for a in pasang for b in pasang if a != b]
    return [{"varian": varian, "arah": arah, "b": b, "c": c}
            for arah in ARAH for b in pasang for c in pasang if b != c]


@lru_cache(maxsize=None)
def _domain_varian(varian: str) -> tuple:
    """Anggota domain satu varian sebagai tuple item immutable (urutan enumerasi = urutan undian)."""
    return tuple(tuple(p.items()) for p in _enumerasi(varian))


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError(PESAN_LEVEL)


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(dict(item) for varian in VARIAN for item in _domain_varian(varian))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu anggota seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return dict(rng.choice(_domain_varian(varian)))
