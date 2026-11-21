"""Matematika Awal, jenis `kenali_bangun_awal`: mengenal bangun datar dari gambar dan bangun ruang (P1, P2).

Melengkapi `kenali_bentuk` (teks saja, hanya bangun datar; jenis lama itu TIDAK berubah).
Empat bentuk soal (`varian`):
  - `datar_gambar`: "Bangun datar apa ini?" (kunci: nama bangun datar yang digambar);
  - `ruang_gambar`: "Bangun ruang apa ini?" (kunci: nama bangun ruang yang digambar);
  - `benda_ruang`: "Dadu berbentuk seperti bangun ruang apa?" (teks SAJA, tanpa gambar);
  - `hitung_bentuk`: "Berapa banyak segitiga?" pada deretan bangun datar campur (kunci: angka).

Himpunan bangun (`himpunan`, mengikuti level): "dasar" (P1) datar {segitiga, persegi, persegi
panjang, lingkaran} dan ruang {kubus, balok, bola, tabung}; "lengkap" (P2) datar sama dan ruang
menambah kerucut. Persegi dan persegi panjang dibedakan lewat sisi yang semuanya sama panjang
atau yang berhadapan saja yang sama panjang.
Pilihan jawaban TIDAK tertulis di soal; jawaban dibaca dalam himpunan itu. Kunci berupa nama
huruf kecil ("persegi panjang"; dibandingkan lewat `diagnosis.normalisasi`) atau angka.

Dua bentuk penyajian (aturan teks vs visual):
  - TEKS (tanpa flag visual, juga lembar cetak): kalimat ciri memuat ciri yang cukup untuk satu
    jawaban pada himpunan level ("Bangun ini punya 3 sisi lurus dan 3 sudut."); `hitung_bentuk`
    memuat daftar berurutan ("Bu Rina menggambar: segitiga, lingkaran, segitiga.");
  - VISUAL (flag `matematika-awal`, proyektor di `topic_matematika_awal_bentuk_visual`): teks
    proyeksi tanpa ciri dan tanpa daftar; gambar SVG membawa informasinya.
Kalimat ciri dipilih lewat indeks `warna` (tiga ciri per bangun), jadi tiap gambar punya satu
teks tetap dan fingerprint matematis sama antara dua mode.

Parameter gambar (`ragam`, `putar`, `ukuran`, `warna`) adalah bagian domain: segitiga samasisi,
siku, atau sembarang dengan empat putaran; persegi panjang dan balok mendatar atau tegak.
`hitung_bentuk`: `banyak` = jumlah tiap bangun datar menurut urutan himpunan, `tanya` = indeks
bangun yang ditanya, `tata` = satu dari tiga tata (susunan urutan, warna baris, kalimat pembuka).
Aturan: 4 sampai 10 bangun, paling sedikit dua jenis, jumlah bangun yang ditanya >= 1 dan
BERBEDA dari jumlah tiap jenis lain (jadi pengecoh jumlah-jenis-lain tak pernah sama kunci).

Malrule hanya HIPOTESIS kesalahan umum untuk ditinjau guru, bukan diagnosis pasti: tertukar
dengan bangun lain pada himpunan level (persegi dan persegi panjang, kubus dan balok, tabung
dan kerucut), menyebut bangun datar untuk bangun ruang (K); pada `hitung_bentuk` menghitung
jenis lain atau semua bangun (K) dan salah hitung lebih/kurang satu (H). Jalur K selalu ada.

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu anggota seragam
dari domain varian itu memakai `rng` (tanpa `hash()`). Urutan enumerasi satu varian: bangun
menurut himpunan -> ragam -> putar -> ukuran -> warna; `hitung_bentuk`: `banyak` leksikografis
-> `tanya` -> `tata`. Daftar BENDA (di `bentuk_katalog`) bersifat APPEND-ONLY menurut indeks.
"""
from __future__ import annotations

from functools import lru_cache
from itertools import product
import random

import bentuk_katalog as K
from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "kenali_bangun_awal"
LEVEL = ("P1", "P2")
VARIAN = ("datar_gambar", "ruang_gambar", "benda_ruang", "hitung_bentuk")
VARIAN_GAMBAR = ("datar_gambar", "ruang_gambar")
PESAN_LUAR_DOMAIN = "parameter kenali bangun awal di luar domain"
PESAN_LEVEL = "level kenali bangun awal harus P1 atau P2"
# Jumlah paling banyak per jenis bangun pada hitung_bentuk (kedua level kini punya empat jenis datar,
# jadi sama; total tetap <= TOTAL_MAKS).
BANYAK_JENIS_MAKS = {"dasar": 4, "lengkap": 4}
TOTAL_MIN, TOTAL_MAKS = 4, 10
JENIS_MIN = 2
# Tata (indeks = indeks warna): susunan urutan bangun dan kalimat pembuka versi teks.
SUSUN = ("berkelompok", "bergantian", "bergantian_terbalik")
PEMBUKA = ("Bu Rina menggambar", "Pak Dedi menggambar", "Bu Sari menggambar")
JUMLAH_TATA = len(SUSUN)

# Penjelasan tertukar yang lebih spesifik dari kalimat umum, per (kunci, jawaban keliru).
TUKAR_KHUSUS = {
    ("persegi", "persegi panjang"): (
        "Menyebut persegi panjang karena sama-sama punya 4 sisi, tanpa memeriksa bahwa "
        "pada bangun ini semua sisinya sama panjang."),
    ("persegi panjang", "persegi"): (
        "Menyebut persegi karena sama-sama punya 4 sisi dan 4 sudut, tanpa memeriksa bahwa "
        "pada bangun ini sisi panjang dan sisi pendeknya berbeda."),
    ("kubus", "balok"): (
        "Menyebut balok karena sama-sama punya 6 sisi, tanpa memeriksa bahwa pada bangun ini "
        "semua sisinya persegi yang sama besar."),
    ("balok", "kubus"): (
        "Menyebut kubus karena sama-sama punya 6 sisi, tanpa memeriksa bahwa pada bangun ini "
        "sisinya persegi panjang, bukan persegi semua."),
    ("tabung", "kerucut"): (
        "Menyebut kerucut karena sama-sama punya sisi lengkung, tanpa menghitung sisi datarnya: "
        "tabung punya 2 sisi datar, kerucut hanya 1 dan punya titik puncak."),
    ("kerucut", "tabung"): (
        "Menyebut tabung karena sama-sama punya sisi lengkung, tanpa menghitung sisi datarnya: "
        "kerucut hanya punya 1 sisi datar dan 1 titik puncak."),
}


def _kapital(teks: str) -> str:
    return teks[:1].upper() + teks[1:]


def _nama_id(nama: str) -> str:
    return nama.replace(" ", "_")


# ── susunan bangun untuk hitung_bentuk ───────────────────────────────────

def urutan_bangun(banyak, tata: int) -> tuple:
    """Indeks jenis bangun urut tampil dari kiri ke kanan; panjang = jumlah semua bangun."""
    if tata == 0:
        return tuple(i for i, n in enumerate(banyak) for _ in range(n))
    sisa, hasil = list(banyak), []
    jalur = range(len(sisa)) if tata == 1 else reversed(range(len(sisa)))
    jalur = tuple(jalur)
    while any(sisa):
        for i in jalur:
            if sisa[i]:
                sisa[i] -= 1
                hasil.append(i)
    return tuple(hasil)


def nama_berurutan(himpunan: str, banyak, tata: int) -> tuple:
    nama = K.DATAR_HIMPUNAN[himpunan]
    return tuple(nama[i] for i in urutan_bangun(banyak, tata))


# ── validasi parameter ───────────────────────────────────────────────────

def _int_murni(nilai) -> bool:
    return type(nilai) is int


def _dalam(nilai, pilihan) -> bool:
    return type(nilai) is type(pilihan[0]) and nilai in pilihan


def _gambar_sah(varian, himpunan, bangun, ragam, putar, ukuran, warna) -> bool:
    daftar = K.DATAR_HIMPUNAN if varian == "datar_gambar" else K.RUANG_HIMPUNAN
    if not (type(bangun) is str and bangun in daftar[himpunan]):
        return False
    return (_dalam(ragam, K.RAGAM[bangun]) and _dalam(putar, K.PUTAR[bangun])
            and _dalam(ukuran, K.UKURAN) and _dalam(warna, K.WARNA))


def _banyak_sah(himpunan: str, banyak, tanya) -> bool:
    jenis = len(K.DATAR_HIMPUNAN[himpunan])
    if not isinstance(banyak, (list, tuple)) or len(banyak) != jenis:
        return False
    if not all(_int_murni(n) and 0 <= n <= BANYAK_JENIS_MAKS[himpunan] for n in banyak):
        return False
    if not TOTAL_MIN <= sum(banyak) <= TOTAL_MAKS or sum(1 for n in banyak if n) < JENIS_MIN:
        return False
    if not (_int_murni(tanya) and 0 <= tanya < jenis) or banyak[tanya] < 1:
        return False
    return all(n != banyak[tanya] for i, n in enumerate(banyak) if i != tanya)


def _sah(varian, himpunan, bangun, ragam, putar, ukuran, warna, benda, banyak, tanya, tata) -> bool:
    if not (type(varian) is str and varian in VARIAN and type(himpunan) is str
            and himpunan in K.HIMPUNAN_LEVEL.values()):
        return False
    if varian in VARIAN_GAMBAR:
        return (benda is None and banyak is None and tanya is None and tata is None
                and _gambar_sah(varian, himpunan, bangun, ragam, putar, ukuran, warna))
    lain_kosong = ragam is None and putar is None and ukuran is None and warna is None
    if varian == "benda_ruang":
        if not (lain_kosong and banyak is None and tanya is None and tata is None):
            return False
        ada = type(bangun) is str and bangun in K.RUANG_HIMPUNAN[himpunan]
        return ada and _int_murni(benda) and 0 <= benda < len(K.BENDA[bangun])
    return (lain_kosong and bangun is None and benda is None
            and _int_murni(tata) and 0 <= tata < JUMLAH_TATA
            and _banyak_sah(himpunan, banyak, tanya))


# ── teks, kunci, pembahasan ──────────────────────────────────────────────

def _ciri(bangun: str, warna: str) -> str:
    return K.CIRI[bangun][K.WARNA.index(warna)]


def _teks(varian, himpunan, bangun, warna, benda, banyak, tanya, tata) -> str:
    if varian == "datar_gambar":
        return f"Bangun ini {_ciri(bangun, warna)}.\nBangun datar apa ini?"
    if varian == "ruang_gambar":
        return f"Bangun ruang ini {_ciri(bangun, warna)}.\nBangun ruang apa ini?"
    if varian == "benda_ruang":
        return f"{_kapital(K.BENDA[bangun][benda])} berbentuk seperti bangun ruang apa?"
    daftar = ", ".join(nama_berurutan(himpunan, banyak, tata))
    return f"{PEMBUKA[tata]}: {daftar}.\nBerapa banyak {K.DATAR_HIMPUNAN[himpunan][tanya]}?"


def _pembahasan(varian, himpunan, bangun, warna, benda, banyak, tanya) -> str:
    if varian in VARIAN_GAMBAR:
        return (f"Cocokkan ciri bangun itu dengan tiap bangun. {K.FAKTA[bangun]} "
                f"Jadi bangun itu adalah {bangun}.")
    if varian == "benda_ruang":
        return (f"Bayangkan bentuk {K.BENDA[bangun][benda]}: sama seperti {bangun}. "
                f"{K.FAKTA[bangun]} Jadi jawabannya {bangun}.")
    nama = K.DATAR_HIMPUNAN[himpunan][tanya]
    return (f"Hitung {nama} satu per satu sambil memberi tanda, jangan sampai ada yang "
            f"terhitung dua kali atau terlewat. Ada {banyak[tanya]} {nama}. "
            f"Jadi jawabannya {banyak[tanya]}.")


# ── malrule ──────────────────────────────────────────────────────────────

def _alasan_tukar(varian: str, kunci: str, lain: str) -> str:
    if (kunci, lain) in TUKAR_KHUSUS:
        return TUKAR_KHUSUS[(kunci, lain)]
    if varian == "benda_ruang":
        return f"Menyebut {lain}, kemungkinan belum mengaitkan bentuk benda itu dengan ciri {kunci}."
    return f"Menyebut {lain}, kemungkinan belum membedakan ciri {kunci} dari ciri {lain}."


def _malrule_nama(varian: str, himpunan: str, kunci: str) -> list:
    ruang = K.jenis_bangun(kunci) == K.JENIS_RUANG
    daftar = K.RUANG_HIMPUNAN[himpunan] if ruang else K.DATAR_HIMPUNAN[himpunan]
    awalan = "ruang" if ruang else "bangun"
    kandidat = [Malrule(f"{TEMPLATE_ID}.{awalan}_tertukar_{_nama_id(lain)}", lain, "K",
                        _alasan_tukar(varian, kunci, lain))
                for lain in daftar if lain != kunci]
    keliru = K.DATAR_KELIRU[himpunan].get(kunci) if ruang else None
    if keliru is not None:
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.datar_untuk_ruang", keliru, "K",
            f"Menyebut {keliru}, yaitu bangun datar, padahal yang ditanya bangun ruang; "
            "kemungkinan hanya memperhatikan satu sisinya."))
    return kandidat


def _malrule_hitung(himpunan: str, banyak, tanya: int) -> list:
    nama, kunci = K.DATAR_HIMPUNAN[himpunan], banyak[tanya]
    kandidat = [Malrule(
        f"{TEMPLATE_ID}.hitung_{_nama_id(nama[i])}", str(n), "K",
        f"Menghitung {nama[i]} (ada {n}), kemungkinan salah mengira bangun yang ditanya.")
        for i, n in enumerate(banyak) if i != tanya and n]
    kandidat.append(Malrule(
        f"{TEMPLATE_ID}.hitung_semua", str(sum(banyak)), "K",
        f"Menghitung semua bangun (ada {sum(banyak)}), padahal hanya {nama[tanya]} yang ditanya."))
    kandidat.append(Malrule(
        f"{TEMPLATE_ID}.hitung_dobel", str(kunci + 1), "H",
        "Sudah mengerti caranya, tetapi satu bangun terhitung dua kali sehingga jawabannya lebih satu."))
    if kunci > 1:
        kandidat.append(Malrule(
            f"{TEMPLATE_ID}.hitung_terlewat", str(kunci - 1), "H",
            "Sudah mengerti caranya, tetapi satu bangun terlewat sehingga jawabannya kurang satu."))
    return kandidat


# ── soal ─────────────────────────────────────────────────────────────────

def kenali_bangun_awal(varian: str, himpunan: str, bangun: str | None = None,
                       ragam: str | None = None, putar: int | None = None,
                       ukuran: str | None = None, warna: str | None = None,
                       benda: int | None = None, banyak=None, tanya: int | None = None,
                       tata: int | None = None) -> Soal:
    """Nama bangun dari gambar atau benda, atau banyak satu jenis bangun datar (kunci dari parameter)."""
    if not _sah(varian, himpunan, bangun, ragam, putar, ukuran, warna, benda, banyak, tanya, tata):
        raise ValueError(PESAN_LUAR_DOMAIN)
    isi = (("bangun", bangun), ("ragam", ragam), ("putar", putar), ("ukuran", ukuran),
           ("warna", warna), ("benda", benda), ("banyak", None if banyak is None else list(banyak)),
           ("tanya", tanya), ("tata", tata))
    parameter = {"varian": varian, "himpunan": himpunan,
                 **{nama: nilai for nama, nilai in isi if nilai is not None}}
    if varian == "hitung_bentuk":
        kunci, kandidat = str(banyak[tanya]), _malrule_hitung(himpunan, banyak, tanya)
    else:
        kunci, kandidat = bangun, _malrule_nama(varian, himpunan, bangun)
    return Soal(
        template_id=TEMPLATE_ID, parameter=parameter,
        teks=_teks(varian, himpunan, bangun, warna, benda, banyak, tanya, tata), kunci=kunci,
        malrule=saring_malrule(kunci, kandidat),
        pembahasan=_pembahasan(varian, himpunan, bangun, warna, benda, banyak, tanya),
        bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi_gambar(varian: str, himpunan: str) -> list:
    daftar = K.DATAR_HIMPUNAN if varian == "datar_gambar" else K.RUANG_HIMPUNAN
    return [{"varian": varian, "himpunan": himpunan, "bangun": bangun, "ragam": ragam,
             "putar": putar, "ukuran": ukuran, "warna": warna}
            for bangun in daftar[himpunan]
            for ragam, putar, ukuran, warna in product(
                K.RAGAM[bangun], K.PUTAR[bangun], K.UKURAN, K.WARNA)]


def _enumerasi_benda(himpunan: str) -> list:
    return [{"varian": "benda_ruang", "himpunan": himpunan, "bangun": bangun, "benda": benda}
            for bangun in K.RUANG_HIMPUNAN[himpunan] for benda in range(len(K.BENDA[bangun]))]


def _enumerasi_hitung(himpunan: str) -> list:
    jenis, maks = len(K.DATAR_HIMPUNAN[himpunan]), BANYAK_JENIS_MAKS[himpunan]
    hasil = []
    for banyak in product(range(maks + 1), repeat=jenis):
        for tanya in range(jenis):
            if not _banyak_sah(himpunan, banyak, tanya):
                continue
            hasil.extend({"varian": "hitung_bentuk", "himpunan": himpunan,
                          "banyak": banyak, "tanya": tanya, "tata": tata}
                         for tata in range(JUMLAH_TATA))
    return hasil


def _enumerasi(varian: str, himpunan: str) -> list:
    if varian in VARIAN_GAMBAR:
        return _enumerasi_gambar(varian, himpunan)
    if varian == "benda_ruang":
        return _enumerasi_benda(himpunan)
    return _enumerasi_hitung(himpunan)


@lru_cache(maxsize=None)
def _domain_varian(level: str, varian: str) -> tuple:
    """Anggota domain satu varian sebagai tuple item immutable (urutan enumerasi = urutan undian)."""
    himpunan = K.HIMPUNAN_LEVEL[level]
    return tuple(tuple((k, tuple(v) if isinstance(v, list) else v) for k, v in p.items())
                 for p in _enumerasi(varian, himpunan))


def _buka(item: tuple) -> dict:
    """Dict baru dari item beku; `banyak` kembali menjadi list baru."""
    return {k: list(v) if k == "banyak" else v for k, v in item}


def _pastikan_level(level: str) -> None:
    if level not in LEVEL:
        raise ValueError(PESAN_LEVEL)


def domain_parameter(level: str) -> tuple:
    """Seluruh parameter sah satu level; dict baru setiap panggilan."""
    _pastikan_level(level)
    return tuple(_buka(item) for varian in VARIAN for item in _domain_varian(level, varian))


def parameter(rng: random.Random, level: str) -> dict:
    """Varian seragam, lalu satu anggota seragam dari domain varian itu."""
    _pastikan_level(level)
    varian = rng.choice(VARIAN)
    return _buka(rng.choice(_domain_varian(level, varian)))
