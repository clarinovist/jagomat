"""Aturan murni jadwal tetap guru: tanpa I/O berkas, tanpa DB. Gerbang rilis, validasi blok, formulir, dan luar_jam.

Jadwal tetap = kumpulan blok mingguan jam mengajar guru menurut WIB: (hari ISO 1=Senin..7=Minggu, mulai, selesai)
dalam menit sejak 00.00. Modul ini tidak membaca jam. Waktu pertemuan masuk sebagai teks UTC naif (format baku).
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Iterator, Optional, Tuple

import jadwal_dasar as jd

# Gerbang rilis jadwal tetap guru. MATI = rute guru dan admin 404 identik, tidak ada peringatan. Dinyalakan di commit
# rilis; tes yang butuh keadaan aktif menyalakannya lewat monkeypatch.
GURU_JADWAL_TETAP_AKTIF = False

MAKS_BLOK = 14
MAKS_BLOK_PER_HARI = 2
LANGKAH_MENIT = 30
PANJANG_MIN_MENIT = 60
MENIT_SEHARI = 1440
HARI_MIN = 1
HARI_MAKS = 7
BATAS_USULAN_PER_HARI = 10
NAMA_HARI = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")

MAKS_PANJANG_TEKS = 200
MENIT_PER_JAM = 60
DETIK_PER_MENIT = 60
JUMLAH_FIELD_BLOK = 3
PANJANG_MAKS_ANGKA_FORM = len(str(MENIT_SEHARI))
SLOT_FORM = ("a", "b")
UJUNG_FORM = ("m", "s")

_POLA_BLOK = re.compile(r"([0-9]+)@([0-9]+)-([0-9]+)")
_POLA_ANGKA_FORM = re.compile(r"[0-9]+")


# --- gerbang ----------------------------------------------------------------------------

def guru_jadwal_tetap_aktif() -> bool:
    """Gerbang rilis. Konstanta dibaca saat dipanggil, bukan saat impor, supaya monkeypatch di tes berlaku."""
    return GURU_JADWAL_TETAP_AKTIF is True


# --- validasi blok ----------------------------------------------------------------------

def _periksa_jumlah_blok(jumlah: int) -> None:
    if jumlah > MAKS_BLOK:
        raise ValueError(f"Jadwal tetap maksimal {MAKS_BLOK} blok.")


def _periksa_blok(item) -> None:
    """Satu blok: tuple tiga bilangan bulat murni (bool ditolak), rentang hari dan jam, kelipatan 30, panjang minimum."""
    if not isinstance(item, tuple) or len(item) != JUMLAH_FIELD_BLOK:
        raise ValueError("Blok jadwal tetap harus berupa (hari, mulai, selesai).")
    if any(type(nilai) is not int for nilai in item):
        raise ValueError("Nilai blok jadwal tetap harus bilangan bulat.")
    hari, mulai, selesai = item
    if not HARI_MIN <= hari <= HARI_MAKS:
        raise ValueError("Hari blok harus 1 sampai 7.")
    if mulai < 0 or selesai > MENIT_SEHARI:
        raise ValueError("Jam blok harus berada dalam satu hari WIB.")
    if mulai % LANGKAH_MENIT or selesai % LANGKAH_MENIT:
        raise ValueError("Jam blok harus kelipatan 30 menit.")
    if selesai <= mulai:
        raise ValueError("Jam selesai harus setelah jam mulai.")
    if selesai - mulai < PANJANG_MIN_MENIT:
        raise ValueError("Blok jadwal minimal 60 menit.")


def _periksa_per_hari(urut: tuple) -> None:
    """Dipanggil dengan blok terurut (hari, mulai). Cukup membandingkan pasangan bertetangga: bila ada irisan, pasangan
    bertetangga di hari yang sama juga beririsan. Bersentuhan tepat (mulai = selesai sebelumnya) boleh."""
    jumlah_per_hari = Counter(hari for hari, _, _ in urut)
    if any(jumlah > MAKS_BLOK_PER_HARI for jumlah in jumlah_per_hari.values()):
        raise ValueError(f"Jadwal tetap maksimal {MAKS_BLOK_PER_HARI} blok per hari.")
    for sebelumnya, berikut in zip(urut, urut[1:]):
        if sebelumnya[0] == berikut[0] and berikut[1] < sebelumnya[2]:
            raise ValueError("Blok dalam satu hari tidak boleh beririsan.")


def _normal(blok) -> tuple:
    """Blok tervalidasi dalam urutan kanonik (hari, mulai, selesai). Dilalui semua jalur masuk."""
    if not isinstance(blok, tuple):
        raise ValueError("Jadwal tetap harus berupa tuple blok.")
    _periksa_jumlah_blok(len(blok))
    for item in blok:
        _periksa_blok(item)
    urut = tuple(sorted(blok))
    _periksa_per_hari(urut)
    return urut


def _ke_teks(urut: tuple) -> str:
    return ";".join(f"{hari}@{mulai}-{selesai}" for hari, mulai, selesai in urut)


# --- teks kanonik -----------------------------------------------------------------------

def _periksa_teks_masukan(teks) -> None:
    if type(teks) is not str:
        raise ValueError("Jadwal tetap harus berupa teks.")
    if len(teks) > MAKS_PANJANG_TEKS:
        raise ValueError("Teks jadwal tetap terlalu panjang.")
    if not teks.isascii():
        raise ValueError("Teks jadwal tetap harus ASCII.")


def _urai_potongan(potongan: str) -> Tuple[int, int, int]:
    cocok = _POLA_BLOK.fullmatch(potongan)
    if cocok is None:
        raise ValueError("Format blok jadwal tetap tidak sah.")
    hari, mulai, selesai = (int(nilai) for nilai in cocok.groups())
    return (hari, mulai, selesai)


def urai_blok(teks) -> tuple:
    """Teks kanonik menjadi tuple blok terurut. Teks yang tidak dalam bentuk kanonik ditolak (urutan, nol di depan, spasi)."""
    _periksa_teks_masukan(teks)
    if teks == "":
        return ()
    potongan = teks.split(";")
    _periksa_jumlah_blok(len(potongan))
    blok = _normal(tuple(_urai_potongan(item) for item in potongan))
    if _ke_teks(blok) != teks:
        raise ValueError("Teks jadwal tetap tidak dalam bentuk kanonik.")
    return blok


def kanonik(blok) -> str:
    """Bentuk teks kanonik dari blok. Blok diurutkan dahulu; masukan yang tidak sah melempar ValueError."""
    return _ke_teks(_normal(blok))


def sama_blok(a, b) -> bool:
    """Dua teks kanonik identik. Bukan teks: False."""
    return type(a) is str and type(b) is str and a == b


# --- formulir ---------------------------------------------------------------------------

def _kunci_form(hari: int, slot: str, ujung: str) -> str:
    return f"h{hari}{slot}_{ujung}"


KUNCI_FORM = frozenset(
    _kunci_form(hari, slot, ujung)
    for hari in range(HARI_MIN, HARI_MAKS + 1)
    for slot in SLOT_FORM
    for ujung in UJUNG_FORM
)


def _periksa_kunci_form(data) -> None:
    if not isinstance(data, dict):
        raise ValueError("Formulir jadwal tetap harus berupa dict.")
    if set(data) != KUNCI_FORM:
        raise ValueError(f"Formulir jadwal tetap harus berisi tepat {len(KUNCI_FORM)} field.")


def _nilai_menit(teks) -> Optional[int]:
    """None bila kosong; bilangan bulat ASCII tanpa tanda, paling banyak PANJANG_MAKS_ANGKA_FORM karakter."""
    if type(teks) is not str:
        raise ValueError("Nilai formulir jadwal tetap harus berupa teks.")
    if teks == "":
        return None
    if len(teks) > PANJANG_MAKS_ANGKA_FORM or _POLA_ANGKA_FORM.fullmatch(teks) is None:
        raise ValueError("Jam formulir harus bilangan bulat desimal.")
    return int(teks)


def _blok_slot(data: dict, hari: int, slot: str) -> Optional[Tuple[int, int, int]]:
    """Blok satu slot. Kedua field kosong = tidak ada blok; hanya salah satu terisi = ValueError."""
    mulai = _nilai_menit(data[_kunci_form(hari, slot, "m")])
    selesai = _nilai_menit(data[_kunci_form(hari, slot, "s")])
    if mulai is None and selesai is None:
        return None
    if mulai is None or selesai is None:
        raise ValueError("Blok harus mengisi jam mulai dan selesai bersama.")
    return (hari, mulai, selesai)


def _blok_terisi(data: dict) -> Iterator[Tuple[int, int, int]]:
    for hari in range(HARI_MIN, HARI_MAKS + 1):
        for slot in SLOT_FORM:
            blok = _blok_slot(data, hari, slot)
            if blok is not None:
                yield blok


def blok_dari_form(data) -> tuple:
    """Blok dari 28 field formulir. Urutan field tidak penting: hasil diurutkan lalu divalidasi."""
    _periksa_kunci_form(data)
    return _normal(tuple(_blok_terisi(data)))


# --- opsi dan label jam -----------------------------------------------------------------

def opsi_menit() -> tuple:
    return tuple(range(0, MENIT_SEHARI + 1, LANGKAH_MENIT))


def opsi_mulai() -> tuple:
    """Pilihan jam mulai untuk `<select>`: 00.00 sampai 23.30 per 30 menit. Tidak semua pilihan membentuk blok sah."""
    return tuple(range(0, MENIT_SEHARI, LANGKAH_MENIT))


def opsi_selesai() -> tuple:
    return tuple(range(LANGKAH_MENIT, MENIT_SEHARI + 1, LANGKAH_MENIT))


def label_menit(menit) -> str:
    """Label jam untuk `<select>`: 480 -> "08.00", 1440 -> "24.00"."""
    if type(menit) is not int or not 0 <= menit <= MENIT_SEHARI:
        raise ValueError("Menit harus bilangan bulat 0 sampai 1440.")
    jam, sisa = divmod(menit, MENIT_PER_JAM)
    return f"{jam:02d}.{sisa:02d}"


# --- luar_jam ---------------------------------------------------------------------------

def _ke_waktu_utc(mulai_baku) -> datetime:
    if type(mulai_baku) is not str:
        raise ValueError("Waktu mulai harus berupa teks.")
    try:
        naif = datetime.strptime(mulai_baku, jd.FORMAT_BAKU)
    except ValueError:
        raise ValueError("Waktu mulai harus format UTC baku.") from None
    return naif.replace(tzinfo=timezone.utc)


def _hari_dan_detik_wib(mulai_baku) -> Tuple[int, int]:
    """Hari ISO dan detik sejak 00.00 WIB untuk waktu UTC naif. Konversi dari UTC, bukan label zona pada teks."""
    waktu_wib = _ke_waktu_utc(mulai_baku).astimezone(jd.WIB)
    detik = (waktu_wib.hour * MENIT_PER_JAM + waktu_wib.minute) * DETIK_PER_MENIT + waktu_wib.second
    return waktu_wib.isoweekday(), detik


def _periksa_durasi(menit) -> int:
    if type(menit) is not int or menit < 1:
        raise ValueError("Durasi pertemuan harus bilangan bulat minimal 1 menit.")
    return menit


def _pertemuan_dalam_blok(blok: tuple, hari: int, awal: int, akhir: int) -> bool:
    """True bila seluruh [awal, akhir) berada di dalam blok pada hari yang sama. Batas pas dihitung dalam."""
    hari_blok, mulai, selesai = blok
    return (
        hari_blok == hari
        and mulai * DETIK_PER_MENIT <= awal
        and akhir <= selesai * DETIK_PER_MENIT
    )


def luar_jam(blok, mulai_baku, menit) -> bool:
    """True bila pertemuan di luar jam tetap guru. Pemanggil hanya memakai ini bila guru punya jadwal tetap aktif.

    `blok` hasil urai_blok; `mulai_baku` waktu UTC naif (jd.FORMAT_BAKU); `menit` durasi pertemuan. Pertemuan di luar
    jam bila tidak seluruhnya berada dalam SATU blok pada hari WIB yang sama. Pertemuan yang melewati tengah malam WIB
    selalu di luar jam. Blok kosong: semua pertemuan di luar jam.
    """
    blok_urut = _normal(blok)
    hari, awal = _hari_dan_detik_wib(mulai_baku)
    durasi_detik = _periksa_durasi(menit) * DETIK_PER_MENIT
    akhir = awal + durasi_detik
    if akhir > MENIT_SEHARI * DETIK_PER_MENIT:
        return True
    return not any(_pertemuan_dalam_blok(item, hari, awal, akhir) for item in blok_urut)
