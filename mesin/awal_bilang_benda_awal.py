"""Matematika Awal, jenis `bilang_benda_awal`: membilang benda dan bilangan 1..10, teks saja (P1).

Tujuh bentuk soal (`varian`), menutup tiga sub-materi bab K1 B1 "Membilang sampai 10":
  - `hitung` (Membilang banyak benda): "Ada ● ● ● ● kelereng di dalam kotak. Berapa
    banyak kelereng?" (1..10 simbol, empat benda); kunci angka;
  - `sama_banyak` (Membilang banyak benda, sama dengan): "Rina punya ● ● ● kelereng.
    Budi punya kelereng sama banyak dengan Rina. Berapa kelereng milik Budi?"; kunci angka;
  - `kata_ke_angka` (Membaca dan menulis lambang bilangan): "Tujuh ditulis dengan
    angka ..." (kata 1..10); kunci angka;
  - `angka_ke_kata`: "Angka 7 ditulis dengan kata ..." (kunci huruf kecil "tujuh");
  - `antara` (Lebih dari, kurang dari): "Bilangan yang lebih dari 6 dan kurang dari 8
    adalah ..." (selisih batas selalu 2, jadi jawabannya satu bilangan);
  - `satu_lebih`: "Bilangan satu lebih banyak dari 4 adalah ..." (n 1..9);
  - `satu_kurang`: "Bilangan satu lebih sedikit dari 4 adalah ..." (n 2..10).

Simbol "●" HANYA muncul pada kalimat yang memuat benda (satu simbol = satu benda) dan
tidak pernah di keterangan atau di pembahasan, sehingga banyaknya "●" di seluruh teks
sama dengan banyaknya benda yang ditanyakan. Semua bilangan 1..10 (kunci), tanpa
bilangan negatif.

Jenis ini memakai dua tipe kunci: angka (enam varian) dan kata huruf kecil
(`angka_ke_kata`). Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan
diagnosis pasti dari satu jawaban: lambang yang mirip bentuknya tertukar, batas ikut
dijawab, "lebih" dan "kurang" tertukar, angka soal diulang, membilang dari nol, dua
anak dijumlah (semuanya K), serta meleset satu atau dua benda (H). Urutan kandidat:
K lebih dulu, lalu H. Daftar benda, tempat, dan anak bersifat APPEND-ONLY menurut
indeks: indeks ikut identitas soal di bank.
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "bilang_benda_awal"
LEVEL = ("P1",)
VARIAN = ("hitung", "sama_banyak", "kata_ke_angka", "angka_ke_kata",
          "antara", "satu_lebih", "satu_kurang")
SIMBOL = "●"
BATAS_ATAS = 10
PESAN_LUAR_DOMAIN = "parameter bilang benda awal di luar domain"

# APPEND-ONLY menurut indeks.
KATA = ("satu", "dua", "tiga", "empat", "lima", "enam", "tujuh", "delapan",
        "sembilan", "sepuluh")
BENDA = ("kelereng", "kancing", "bunga", "apel")
TEMPAT = ("di dalam kotak", "di atas meja", "di dalam vas", "di dalam keranjang")
ANAK = (("Rina", "Budi"), ("Dita", "Eko"))
# Lambang yang bentuk tulisannya sering dikira sama oleh anak kelas 1.
MIRIP = {1: 7, 2: 5, 3: 8, 4: 9, 5: 2, 6: 9, 7: 1, 8: 3, 9: 6, 10: 1}

BIDANG = {
    "hitung": ("n", "benda"),
    "sama_banyak": ("n", "anak", "benda"),
    "kata_ke_angka": ("n",),
    "angka_ke_kata": ("n",),
    "antara": ("a",),
    "satu_lebih": ("n",),
    "satu_kurang": ("n",),
}
NILAI_SAH = {
    ("hitung", "n"): tuple(range(1, BATAS_ATAS + 1)),
    ("hitung", "benda"): tuple(range(len(BENDA))),
    ("sama_banyak", "n"): tuple(range(1, BATAS_ATAS + 1)),
    ("sama_banyak", "anak"): tuple(range(len(ANAK))),
    ("sama_banyak", "benda"): tuple(range(len(BENDA))),
    ("kata_ke_angka", "n"): tuple(range(1, BATAS_ATAS + 1)),
    ("angka_ke_kata", "n"): tuple(range(1, BATAS_ATAS + 1)),
    ("antara", "a"): tuple(range(1, BATAS_ATAS - 1)),
    ("satu_lebih", "n"): tuple(range(1, BATAS_ATAS)),
    ("satu_kurang", "n"): tuple(range(2, BATAS_ATAS + 1)),
}


def _sah(varian, isian: dict) -> bool:
    if type(varian) is not str or varian not in BIDANG:
        return False
    if set(isian) != set(BIDANG[varian]):
        return False
    return all(type(nilai) is int and nilai in NILAI_SAH[(varian, bidang)]
               for bidang, nilai in isian.items())


# ── kunci, teks, pembahasan ──────────────────────────────────────────────

def _simbol(n: int) -> str:
    return " ".join([SIMBOL] * n)


def _kunci(varian: str, p: dict) -> str:
    if varian in ("hitung", "sama_banyak", "kata_ke_angka"):
        return str(p["n"])
    if varian == "angka_ke_kata":
        return KATA[p["n"] - 1]
    if varian == "antara":
        return str(p["a"] + 1)
    if varian == "satu_lebih":
        return str(p["n"] + 1)
    return str(p["n"] - 1)


def _teks(varian: str, p: dict) -> str:
    if varian == "hitung":
        benda = BENDA[p["benda"]]
        return f"Ada {_simbol(p['n'])} {benda} {TEMPAT[p['benda']]}. Berapa banyak {benda}?"
    if varian == "sama_banyak":
        x, y = ANAK[p["anak"]]
        benda = BENDA[p["benda"]]
        return (f"{x} punya {_simbol(p['n'])} {benda}. {y} punya {benda} sama banyak "
                f"dengan {x}. Berapa {benda} milik {y}?")
    if varian == "kata_ke_angka":
        return f"{KATA[p['n'] - 1].capitalize()} ditulis dengan angka ..."
    if varian == "angka_ke_kata":
        return f"Angka {p['n']} ditulis dengan kata ..."
    if varian == "antara":
        return f"Bilangan yang lebih dari {p['a']} dan kurang dari {p['a'] + 2} adalah ..."
    if varian == "satu_lebih":
        return f"Bilangan satu lebih banyak dari {p['n']} adalah ..."
    return f"Bilangan satu lebih sedikit dari {p['n']} adalah ..."


def _urut(n: int) -> str:
    return ", ".join(str(i) for i in range(1, n + 1))


def _pembahasan(varian: str, p: dict) -> str:
    if varian == "hitung":
        n = p["n"]
        return (f"Hitung satu per satu sambil menunjuk: {_urut(n)}. "
                f"Jadi ada {n} {BENDA[p['benda']]}.")
    if varian == "sama_banyak":
        x, y = ANAK[p["anak"]]
        n, benda = p["n"], BENDA[p["benda"]]
        return (f"Hitung dulu milik {x}: {_urut(n)}, jadi {n} {benda}. Sama banyak "
                f"berarti jumlahnya tidak berbeda, jadi {y} juga punya {n} {benda}.")
    if varian == "kata_ke_angka":
        n = p["n"]
        return (f"Bilang dari satu: {', '.join(KATA[:n])}. Bilangan {KATA[n - 1]} "
                f"ditulis dengan angka {n}.")
    if varian == "angka_ke_kata":
        n = p["n"]
        return (f"Bilang dari satu: {', '.join(KATA[:n])}. Angka {n} dibaca "
                f"{KATA[n - 1]}.")
    if varian == "antara":
        a = p["a"]
        return (f"Pada urutan bilangan: {a}, {a + 1}, {a + 2}. Bilangan di antara {a} "
                f"dan {a + 2} adalah {a + 1}. Ia lebih dari {a} dan kurang dari {a + 2}.")
    n = p["n"]
    if varian == "satu_lebih":
        return (f"Satu lebih banyak dari {n} berarti maju satu langkah: {n}, {n + 1}. "
                f"Jadi jawabannya {n + 1}.")
    return (f"Satu lebih sedikit dari {n} berarti mundur satu langkah: {n}, {n - 1}. "
            f"Jadi jawabannya {n - 1}.")


# ── malrule (K dulu, lalu H) ─────────────────────────────────────────────

def _mal(nama: str, jawaban: str, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", jawaban, kode, alasan)


def _dalam(nilai: int, bawah: int = 0) -> bool:
    return bawah <= nilai <= BATAS_ATAS


def _alasan_mirip(n: int) -> str:
    if n == BATAS_ATAS:
        return ("Menulis 1 saja untuk sepuluh; kemungkinan hanya menulis angka "
                "depannya.")
    return (f"Menulis {MIRIP[n]} sebagai ganti {n}; kemungkinan lambang bilangan "
            "yang bentuknya mirip tertukar.")


def _kandidat_hitung(p: dict) -> list:
    n = p["n"]
    hasil = [_mal("mulai_dari_nol", str(n - 1), "K",
                  f"Menjawab {n - 1}; kemungkinan membilang dimulai dari nol sehingga "
                  "benda pertama tidak dihitung satu.")]
    for nama, nilai, alasan in (
            ("terhitung_dua_kali", n + 1, "satu benda terhitung dua kali"),
            ("terlewat_dua_benda", n - 2, "dua benda terlewat saat menghitung"),
            ("terhitung_dua_dua_kali", n + 2, "dua benda terhitung dua kali")):
        if _dalam(nilai):
            hasil.append(_mal(nama, str(nilai), "H",
                              f"Sudah membilang, tetapi meleset: {alasan} sehingga "
                              f"jawabannya {nilai}."))
    return hasil


def _kandidat_sama_banyak(p: dict) -> list:
    n = p["n"]
    jumlah = _mal("dua_anak_dijumlah", str(2 * n), "K",
                  f"Menjawab {2 * n}; kemungkinan menjumlah milik kedua anak, "
                  "padahal sama banyak berarti jumlahnya tidak berbeda.")
    hasil = []
    for nama, nilai, alasan in (
            ("terlewat_satu", n - 1, "satu benda terlewat saat menghitung"),
            ("terhitung_dua_kali", n + 1, "satu benda terhitung dua kali"),
            ("terlewat_dua_benda", n - 2, "dua benda terlewat saat menghitung")):
        if _dalam(nilai) and nilai != 2 * n:
            hasil.append(_mal(nama, str(nilai), "H",
                              f"Sudah membilang, tetapi meleset: {alasan} sehingga "
                              f"jawabannya {nilai}."))
    # Jumlah dua anak di atas 10 bukan bilangan kelas 1 bab ini: pilihan ganda
    # memakainya paling akhir (K tetap ada di setiap parameter).
    return [jumlah] + hasil if 2 * n <= BATAS_ATAS else hasil + [jumlah]


def _kandidat_lambang(p: dict, ke_kata: bool) -> list:
    n = p["n"]

    def tulis(m: int) -> str:
        return KATA[m - 1] if ke_kata else str(m)

    hasil = [_mal("lambang_mirip_tertukar", tulis(MIRIP[n]), "K", _alasan_mirip(n))]
    for nama, nilai, alasan in (
            ("bilangan_sebelumnya", n - 1, "tertukar dengan bilangan sebelumnya"),
            ("bilangan_sesudahnya", n + 1, "tertukar dengan bilangan sesudahnya")):
        if _dalam(nilai, 1):
            hasil.append(_mal(nama, tulis(nilai), "H",
                              f"Sudah mengenal lambangnya, tetapi {alasan} sehingga "
                              f"jawabannya {tulis(nilai)}."))
    return hasil


def _kandidat_antara(p: dict) -> list:
    a = p["a"]
    return [
        _mal("batas_kecil_ikut", str(a), "K",
             f"Menjawab {a}; kemungkinan mengira bilangan batas ikut menjadi jawaban."),
        _mal("batas_besar_ikut", str(a + 2), "K",
             f"Menjawab {a + 2}; kemungkinan mengira bilangan batas ikut menjadi jawaban."),
    ]


def _kandidat_satu_lebih(p: dict) -> list:
    n = p["n"]
    hasil = [
        _mal("lebih_dikira_kurang", str(n - 1), "K",
             f"Menjawab {n - 1}; kemungkinan menukar arti lebih banyak dengan lebih sedikit."),
        _mal("angka_soal_diulang", str(n), "K",
             f"Menjawab {n}; kemungkinan menyalin bilangan di soal tanpa menambah satu."),
    ]
    if _dalam(n + 2):
        hasil.append(_mal("maju_dua_langkah", str(n + 2), "H",
                          f"Sudah tahu harus maju, tetapi maju dua langkah sehingga "
                          f"jawabannya {n + 2}."))
    return hasil


def _kandidat_satu_kurang(p: dict) -> list:
    n = p["n"]
    hasil = []
    if _dalam(n + 1):
        hasil.append(_mal("kurang_dikira_lebih", str(n + 1), "K",
                          f"Menjawab {n + 1}; kemungkinan menukar arti lebih sedikit "
                          "dengan lebih banyak."))
    hasil.append(_mal("angka_soal_diulang", str(n), "K",
                      f"Menjawab {n}; kemungkinan menyalin bilangan di soal tanpa "
                      "mengurangi satu."))
    if _dalam(n - 2):
        hasil.append(_mal("mundur_dua_langkah", str(n - 2), "H",
                          f"Sudah tahu harus mundur, tetapi mundur dua langkah sehingga "
                          f"jawabannya {n - 2}."))
    return hasil


def _kandidat(varian: str, p: dict) -> list:
    if varian == "hitung":
        return _kandidat_hitung(p)
    if varian == "sama_banyak":
        return _kandidat_sama_banyak(p)
    if varian == "kata_ke_angka":
        return _kandidat_lambang(p, False)
    if varian == "angka_ke_kata":
        return _kandidat_lambang(p, True)
    if varian == "antara":
        return _kandidat_antara(p)
    if varian == "satu_lebih":
        return _kandidat_satu_lebih(p)
    return _kandidat_satu_kurang(p)


def bilang_benda_awal(varian: str, n: int | None = None, benda: int | None = None,
                      anak: int | None = None, a: int | None = None) -> Soal:
    """Soal membilang benda dan bilangan 1..10 (kunci dari parameter)."""
    isian = {nama: nilai for nama, nilai in (
        ("n", n), ("benda", benda), ("anak", anak), ("a", a)) if nilai is not None}
    if not _sah(varian, isian):
        raise ValueError(PESAN_LUAR_DOMAIN)
    kunci = _kunci(varian, isian)
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isian},
        teks=_teks(varian, isian), kunci=kunci,
        malrule=saring_malrule(kunci, _kandidat(varian, isian)),
        pembahasan=_pembahasan(varian, isian), bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi() -> tuple:
    hasil = []
    for varian in VARIAN:
        kombinasi = [{}]
        for nama in BIDANG[varian]:
            kombinasi = [{**k, nama: v} for k in kombinasi
                         for v in NILAI_SAH[(varian, nama)]]
        hasil.extend({"varian": varian, **k} for k in kombinasi)
    return tuple(hasil)


@lru_cache(maxsize=None)
def _domain_beku() -> tuple:
    """Domain sebagai tuple item immutable; urutan enumerasi = urutan undian."""
    return tuple(tuple(p.items()) for p in _enumerasi())


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError("level bilang benda awal harus P1")


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
