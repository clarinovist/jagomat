"""Matematika Awal, jenis `baca_jam_awal`: membaca jam analog, jam penuh dan setengah jam (P2).

Melengkapi `waktu_berat_awal` (teks saja, jam penuh; jenis lama itu TIDAK berubah). Empat bentuk
soal (`varian`), semuanya jawaban pendek:
  - `baca_penuh`: "Pukul berapa jam ini?" pada jam penuh (kunci: "N", N 1..12);
  - `baca_setengah`: jarum pendek tepat di tengah dua angka, jarum panjang di 6 (kunci: "N.30");
  - `jam_kemudian`: jam penuh N, lalu k jam lagi (k 1..4), jam dinding berputar kembali ke 1
    setelah 12 (kunci: jam penuh hasil, ((N + k - 1) mod 12) + 1);
  - `kegiatan_selesai`: cerita kegiatan yang mulai pada jam penuh N dan berlangsung k jam
    (k 1..4), ditanya jam selesainya (kunci sama rumusnya dengan `jam_kemudian`).

Jam mulai pada `jam_kemudian` dan `kegiatan_selesai` hanya 1..11, bukan 12: bila mulai pukul 12
hasilnya persis k, sehingga "k jam lagi" yang tertulis di soal akan sama dengan kunci.

Dua bentuk penyajian (aturan teks vs visual):
  - TEKS (tanpa flag visual, juga lembar cetak): kalimat pertama melukiskan jarum jam ("Jarum
    pendek menunjuk angka 3 dan jarum panjang menunjuk angka 12."; setengah jam: "Jarum pendek ada
    di antara angka 2 dan 3, jarum panjang menunjuk angka 6."), jadi soal bisa dijawab dari teks;
  - VISUAL (flag `matematika-awal`, proyektor di `topic_matematika_awal_jam_visual`): teks
    proyeksi "Perhatikan gambar jam." tanpa letak jarum; gambar SVG jam analog membawa informasinya.
Kalimat petunjuk menulis jawaban setengah jam tidak memuat contoh waktu sungguhan (contoh seperti
"2.30" sama dengan kunci untuk satu jam) dan tidak memuat angka sama sekali.

Kunci berupa teks pendek "N" atau "N.30" (nilai semantis: angka). Malrule hanya HIPOTESIS
kesalahan umum untuk ditinjau guru, bukan diagnosis pasti dari satu jawaban: jarum tertukar (jarum
panjang dibaca sebagai jam), angka jarum panjang ditulis sebagai menit ("3.12", "2.6"), lupa menit
atau salah jam pada setengah jam, jam awal atau lamanya saja, menghitung mundur, lupa kembali ke 1
setelah 12 (K); salah hitung lebih atau kurang satu (H). Jalur K selalu ada.

Domain eksplisit (`domain_parameter`); sampler memilih varian seragam lalu satu anggota seragam dari
domain varian itu memakai `rng` (tanpa `hash()`). Urutan enumerasi: `baca_penuh` jam; `baca_setengah`
jam; `jam_kemudian` jam -> tambah; `kegiatan_selesai` kegiatan -> jam -> lama. Daftar KEGIATAN
bersifat APPEND-ONLY menurut indeks (indeks ikut identitas soal di bank).
"""
from __future__ import annotations

from functools import lru_cache
import random

from templates import Malrule, Soal, saring_malrule

TEMPLATE_ID = "baca_jam_awal"
LEVEL = ("P2",)
VARIAN = ("baca_penuh", "baca_setengah", "jam_kemudian", "kegiatan_selesai")
PESAN_LUAR_DOMAIN = "parameter baca jam awal di luar domain"
PESAN_LEVEL = "level baca jam awal harus P2"

JAM_MIN, JAM_BACA_MAKS, JAM_MULAI_MAKS = 1, 12, 11
LAMA_MIN, LAMA_MAKS = 1, 4
JAM_PUTAR = 12
MENIT_SETENGAH = 30
MENIT_JARUM_PANJANG = {"penuh": 12, "setengah": 6}  # angka yang ditunjuk jarum panjang

# Tokoh sintetis dan kegiatannya (kata kerja yang pas setelah "mulai" dan "<nama> ... selama").
KEGIATAN = (("Sari", "membaca cerita"), ("Tono", "membuat layang-layang"),
            ("Mira", "berlatih menari"), ("Hadi", "bermain di taman"))

PETUNJUK_PENUH = "Tulis angka jamnya."
PETUNJUK_SETENGAH = "Tulis jam, lalu titik, lalu menitnya."
PERTANYAAN_BACA = "Pukul berapa jam ini?"

FIELD = {
    "baca_penuh": ("jam",),
    "baca_setengah": ("jam",),
    "jam_kemudian": ("jam", "tambah"),
    "kegiatan_selesai": ("kegiatan", "jam", "lama"),
}


# ── hitungan jam ─────────────────────────────────────────────────────────

def jam_berikut(jam: int) -> int:
    """Angka sesudah `jam` pada muka jam (12 diikuti 1)."""
    return jam % JAM_PUTAR + 1


def jam_hasil(jam: int, tambah: int) -> int:
    """Jam penuh sesudah `tambah` jam dari `jam`; kembali ke 1 setelah 12."""
    return (jam + tambah - 1) % JAM_PUTAR + 1


def jam_mundur(jam: int, kurang: int) -> int:
    return (jam - kurang - 1) % JAM_PUTAR + 1


# ── validasi parameter ───────────────────────────────────────────────────

def _int_antara(nilai, bawah: int, atas: int) -> bool:
    return type(nilai) is int and bawah <= nilai <= atas


def _sah_baca(jam) -> bool:
    return _int_antara(jam, JAM_MIN, JAM_BACA_MAKS)


def _sah_kemudian(jam, tambah) -> bool:
    return _int_antara(jam, JAM_MIN, JAM_MULAI_MAKS) and _int_antara(tambah, LAMA_MIN, LAMA_MAKS)


def _sah_selesai(kegiatan, jam, lama) -> bool:
    return (_int_antara(kegiatan, 0, len(KEGIATAN) - 1)
            and _int_antara(jam, JAM_MIN, JAM_MULAI_MAKS) and _int_antara(lama, LAMA_MIN, LAMA_MAKS))


_SAH = {"baca_penuh": _sah_baca, "baca_setengah": _sah_baca,
        "jam_kemudian": _sah_kemudian, "kegiatan_selesai": _sah_selesai}


def _sah(varian, isi: dict) -> bool:
    if type(varian) is not str or varian not in FIELD:
        return False
    if set(isi) != set(FIELD[varian]):
        return False
    return _SAH[varian](**isi)


# ── teks ─────────────────────────────────────────────────────────────────

def kalimat_jarum_penuh(jam: int) -> str:
    return f"jarum pendek menunjuk angka {jam} dan jarum panjang menunjuk angka {MENIT_JARUM_PANJANG['penuh']}"


def kalimat_jarum_setengah(jam: int) -> str:
    return (f"jarum pendek ada di antara angka {jam} dan {jam_berikut(jam)}, "
            f"jarum panjang menunjuk angka {MENIT_JARUM_PANJANG['setengah']}")


def _kapital(teks: str) -> str:
    return teks[:1].upper() + teks[1:]


def pertanyaan(varian: str, isi: dict) -> str:
    """Baris pertanyaan (terakhir) tiap varian; juga dipakai proyektor visual untuk memeriksa teks."""
    if varian == "baca_penuh":
        return f"{PERTANYAAN_BACA} {PETUNJUK_PENUH}"
    if varian == "baca_setengah":
        return f"{PERTANYAAN_BACA} {PETUNJUK_SETENGAH}"
    if varian == "jam_kemudian":
        return f"{isi['tambah']} jam lagi, pukul berapa? {PETUNJUK_PENUH}"
    nama, kerja = KEGIATAN[isi["kegiatan"]]
    return f"{nama} {kerja} selama {isi['lama']} jam. Pukul berapa {nama} selesai? {PETUNJUK_PENUH}"


def pengantar_teks(varian: str, isi: dict) -> str:
    """Baris pertama versi TEKS: letak jarum ditulis supaya soal bisa dijawab tanpa gambar."""
    if varian == "baca_penuh":
        return f"{_kapital(kalimat_jarum_penuh(isi['jam']))}."
    if varian == "baca_setengah":
        return f"{_kapital(kalimat_jarum_setengah(isi['jam']))}."
    if varian == "jam_kemudian":
        return f"Sekarang {kalimat_jarum_penuh(isi['jam'])}."
    nama, kerja = KEGIATAN[isi["kegiatan"]]
    return f"{nama} mulai {kerja} ketika {kalimat_jarum_penuh(isi['jam'])}."


# ── kunci, pembahasan, malrule ───────────────────────────────────────────

def _kunci_baca(varian: str, jam: int) -> str:
    return f"{jam}.{MENIT_SETENGAH}" if varian == "baca_setengah" else str(jam)


def _mal(nama: str, jawaban, kode: str, alasan: str) -> Malrule:
    return Malrule(f"{TEMPLATE_ID}.{nama}", str(jawaban), kode, alasan)


def _malrule_penuh(jam: int) -> list:
    return [
        _mal("jarum_tertukar", MENIT_JARUM_PANJANG["penuh"], "K",
             "Membaca angka yang ditunjuk jarum panjang (12) sebagai jam, padahal jam dibaca dari jarum pendek."),
        _mal("angka_jarum_jadi_menit", f"{jam}.{MENIT_JARUM_PANJANG['penuh']}", "K",
             f"Menulis angka jarum panjang sebagai menit ({jam}.{MENIT_JARUM_PANJANG['penuh']}), "
             "padahal jarum panjang di angka 12 berarti jam tepat."),
        _mal("lebih_satu", jam_berikut(jam), "H",
             "Sudah mengerti caranya, tetapi salah membaca angka sesudahnya sehingga jawabannya lebih satu jam."),
        _mal("kurang_satu", jam_mundur(jam, 1), "H",
             "Sudah mengerti caranya, tetapi salah membaca angka sebelumnya sehingga jawabannya kurang satu jam."),
    ]


def _malrule_setengah(jam: int) -> list:
    return [
        _mal("jam_sesudahnya", f"{jam_berikut(jam)}.{MENIT_SETENGAH}", "K",
             f"Membaca jam dari angka yang akan dicapai jarum pendek ({jam_berikut(jam)}), padahal jam yang "
             f"dipakai adalah angka yang sudah dilewati ({jam})."),
        _mal("angka_jarum_jadi_menit", f"{jam}.{MENIT_JARUM_PANJANG['setengah']}", "K",
             f"Menulis angka jarum panjang sebagai menit ({jam}.{MENIT_JARUM_PANJANG['setengah']}), "
             "padahal jarum panjang di angka 6 berarti 30 menit."),
        _mal("lupa_menit", jam, "K",
             f"Hanya menulis jamnya ({jam}), padahal jarum panjang di angka 6 berarti ada 30 menit lagi."),
        _mal("jarum_tertukar", MENIT_JARUM_PANJANG["setengah"], "K",
             "Membaca angka yang ditunjuk jarum panjang (6) sebagai jam, padahal jam dibaca dari jarum pendek."),
    ]


def _malrule_hitung(jam: int, lama: int, hasil: int) -> list:
    kandidat = [
        _mal("jam_awal", jam, "K",
             f"Menyebut jam awal ({jam}) saja, belum menambahkan {lama} jam yang berlalu."),
        _mal("lama_saja", lama, "K",
             f"Menjawab lamanya ({lama}), padahal yang ditanya pukul berapa nantinya."),
        _mal("hitung_mundur", jam_mundur(jam, lama), "K",
             "Menghitung mundur dari jam awal, padahal 'lagi' atau 'selesai' berarti jam bergerak maju."),
    ]
    if jam + lama > JAM_PUTAR:
        kandidat.append(_mal(
            "lupa_kembali_ke_satu", jam + lama, "K",
            f"Menjumlahkan begitu saja ({jam + lama}), padahal sesudah angka 12 jam kembali ke angka 1."))
    kandidat.append(_mal(
        "lebih_satu", jam_berikut(hasil), "H",
        "Sudah mengerti caranya, tetapi salah hitung maju sehingga jawabannya lebih satu jam."))
    kandidat.append(_mal(
        "kurang_satu", jam_mundur(hasil, 1), "H",
        "Sudah mengerti caranya, tetapi jam awal ikut terhitung satu jam sehingga jawabannya kurang satu."))
    return kandidat


def _pembahasan_baca(varian: str, jam: int) -> str:
    if varian == "baca_penuh":
        return (f"Jarum pendek menunjuk angka {jam}, dan jarum panjang tepat di angka 12. "
                f"Jam dibaca dari jarum pendek, jadi sekarang pukul {jam}.")
    return (f"Jarum panjang menunjuk angka 6, artinya lewat 30 menit. Jarum pendek ada di antara angka "
            f"{jam} dan {jam_berikut(jam)}, belum sampai {jam_berikut(jam)}, jadi jamnya {jam}. "
            f"Jadi sekarang pukul {jam}.{MENIT_SETENGAH}.")


def _pembahasan_hitung(jam: int, lama: int, hasil: int) -> str:
    langkah = ", ".join(str(jam_hasil(jam, i)) for i in range(1, lama + 1))
    balik = " Setelah angka 12, jam kembali ke angka 1." if jam + lama > JAM_PUTAR else ""
    return (f"Mulai dari pukul {jam}. Maju satu jam tiap langkah: {langkah}.{balik} "
            f"Setelah {lama} langkah sampai pukul {hasil}.")


# ── soal ─────────────────────────────────────────────────────────────────

def _isi_baca(varian: str, jam: int) -> tuple:
    kandidat = _malrule_setengah(jam) if varian == "baca_setengah" else _malrule_penuh(jam)
    return _kunci_baca(varian, jam), kandidat, _pembahasan_baca(varian, jam)


def _isi_hitung(jam: int, lama: int) -> tuple:
    hasil = jam_hasil(jam, lama)
    return str(hasil), _malrule_hitung(jam, lama, hasil), _pembahasan_hitung(jam, lama, hasil)


def baca_jam_awal(varian: str, **isi) -> Soal:
    """Jam analog: baca jam penuh atau setengah, jam kemudian, atau jam selesai kegiatan."""
    if not _sah(varian, isi):
        raise ValueError(PESAN_LUAR_DOMAIN)
    if varian in ("baca_penuh", "baca_setengah"):
        kunci, kandidat, pembahasan = _isi_baca(varian, isi["jam"])
    else:
        kunci, kandidat, pembahasan = _isi_hitung(isi["jam"], isi.get("tambah", isi.get("lama")))
    teks = f"{pengantar_teks(varian, isi)}\n{pertanyaan(varian, isi)}"
    return Soal(
        template_id=TEMPLATE_ID, parameter={"varian": varian, **isi},
        teks=teks, kunci=kunci, malrule=saring_malrule(kunci, kandidat),
        pembahasan=pembahasan, bagian="A")


# ── domain eksplisit dan sampler ─────────────────────────────────────────

def _enumerasi(varian: str) -> list:
    if varian in ("baca_penuh", "baca_setengah"):
        return [{"varian": varian, "jam": jam} for jam in range(JAM_MIN, JAM_BACA_MAKS + 1)]
    jam_mulai = range(JAM_MIN, JAM_MULAI_MAKS + 1)
    lama_ = range(LAMA_MIN, LAMA_MAKS + 1)
    if varian == "jam_kemudian":
        return [{"varian": varian, "jam": jam, "tambah": tambah}
                for jam in jam_mulai for tambah in lama_]
    return [{"varian": varian, "kegiatan": kegiatan, "jam": jam, "lama": lama}
            for kegiatan in range(len(KEGIATAN)) for jam in jam_mulai for lama in lama_]


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
