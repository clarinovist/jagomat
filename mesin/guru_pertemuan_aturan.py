"""Aturan murni jurnal dan kehadiran pertemuan guru: tanpa I/O, tanpa DB.

Waktu berupa string baku UTC naif `YYYY-MM-DDTHH:MM:SS` (format jadwal_pertemuan.mulai). Jendela dihitung
dari `selesai = mulai + menit`. Batas akhir jendela koreksi (`selesai + 7 hari`) bersifat eksklusif: tepat
di batas itu pertemuan sudah terkunci bagi guru.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import topics

STATUS_KEHADIRAN = ("hadir", "izin", "tidak_hadir")
TOPIK_LAINNYA = "lainnya"
TOPIK_SINTETIS = "campuran"
LABEL_TOPIK_LAINNYA = "Topik lain"
JEDA_TERLAMBAT = timedelta(hours=24)
JENDELA_KOREKSI = timedelta(days=7)
# None = butir antrean "lewat tanpa jurnal" mati. Diisi di commit rilis: 28 Nov 2026 00.00 WIB (= 27 Nov 17.00 UTC),
# supaya pertemuan sebelum guru bisa mengisi jurnal tidak ditagih. Geser ke saat deploy bila deploy lebih lambat.
# Tes mengubahnya lewat monkeypatch.
PERTEMUAN_WAJIB_SEJAK = "2026-11-27T17:00:00"
PERTEMUAN_KE_MIN = 1
PERTEMUAN_KE_MAKS = 8
MENIT_MIN = 1
ALASAN_DIBATALKAN = "dibatalkan"
ALASAN_BELUM_MULAI = "belum_mulai"
ALASAN_TERKUNCI = "terkunci"
ANTREAN_TIDAK = "tidak"
ANTREAN_BELUM = "belum"
ANTREAN_AKSI = "aksi"
ANTREAN_RIWAYAT = "riwayat"

FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
_POLA_WAKTU = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")
_POLA_ID_AWAL = re.compile(r"(klp|kor)_[0-9a-f]{32}")
_POLA_KUNCI = re.compile("(klp|kor)_[0-9a-f]{32}:[%d-%d]" % (PERTEMUAN_KE_MIN, PERTEMUAN_KE_MAKS))
_POLA_ORDER = re.compile(r"kor_[0-9a-f]{32}")


# --- waktu dan kunci --------------------------------------------------------------------

def _ke_datetime(baku) -> datetime:
    """Waktu baku -> datetime naif. Selain format baku ditolak tanpa menggemakan nilainya."""
    if type(baku) is not str or _POLA_WAKTU.fullmatch(baku) is None:
        raise ValueError("Waktu harus format baku UTC YYYY-MM-DDTHH:MM:SS.")
    try:
        return datetime.strptime(baku, FORMAT_WAKTU)
    except ValueError:
        raise ValueError("Waktu pertemuan tidak valid.") from None


def _ke_baku(waktu: datetime) -> str:
    return waktu.strftime(FORMAT_WAKTU)


def _periksa_bool(nilai, nama: str) -> None:
    if type(nilai) is not bool:
        raise ValueError(f"{nama} harus bool.")


def _selesai_dt(mulai: datetime, menit: int) -> datetime:
    if type(menit) is not int or menit < MENIT_MIN:
        raise ValueError("Durasi pertemuan harus bilangan bulat positif (menit).")
    return mulai + timedelta(minutes=menit)


def _batas_jendela(mulai: str, menit: int) -> Tuple[datetime, datetime]:
    """(awal aksi, akhir koreksi): selesai + 24 jam dan selesai + 7 hari. Dipakai bersama oleh semua aturan jendela."""
    selesai_dt = _selesai_dt(_ke_datetime(mulai), menit)
    return selesai_dt + JEDA_TERLAMBAT, selesai_dt + JENDELA_KOREKSI


def kunci_pertemuan(id_awal: str, ke: int) -> str:
    """Kunci `<klp_|kor_><32 hex>:<ke>`. ID atau nomor pertemuan tidak sah -> ValueError."""
    if type(id_awal) is not str or _POLA_ID_AWAL.fullmatch(id_awal) is None:
        raise ValueError("ID awal kunci pertemuan tidak sah.")
    if type(ke) is not int or not (PERTEMUAN_KE_MIN <= ke <= PERTEMUAN_KE_MAKS):
        raise ValueError("Nomor pertemuan harus 1 sampai 8.")
    return f"{id_awal}:{ke}"


def kunci_sah(nilai) -> bool:
    return type(nilai) is str and _POLA_KUNCI.fullmatch(nilai) is not None


def order_id_sah(nilai) -> bool:
    return type(nilai) is str and _POLA_ORDER.fullmatch(nilai) is not None


def waktu_sah(nilai) -> bool:
    try:
        _ke_datetime(nilai)
    except ValueError:
        return False
    return True


def selesai(mulai: str, menit: int) -> str:
    return _ke_baku(_selesai_dt(_ke_datetime(mulai), menit))


# --- jendela catat dan antrean ----------------------------------------------------------

def boleh_catat(mulai: str, menit: int, dibatalkan: bool, kini: str) -> Optional[str]:
    """None bila boleh dicatat; selain itu alasan. Urutan: dibatalkan, belum mulai, terkunci."""
    _periksa_bool(dibatalkan, "dibatalkan")
    waktu_kini = _ke_datetime(kini)
    _, batas_koreksi = _batas_jendela(mulai, menit)
    if dibatalkan:
        return ALASAN_DIBATALKAN
    if _ke_datetime(mulai) > waktu_kini:
        return ALASAN_BELUM_MULAI
    if waktu_kini >= batas_koreksi:
        return ALASAN_TERKUNCI
    return None


def status_antrean(mulai: str, menit: int, dibatalkan: bool, kini: str) -> str:
    """Tempat pertemuan di antrean admin: tidak, belum, aksi (24 jam s.d. 7 hari), atau riwayat."""
    _periksa_bool(dibatalkan, "dibatalkan")
    waktu_kini = _ke_datetime(kini)
    batas_aksi, batas_koreksi = _batas_jendela(mulai, menit)
    if dibatalkan:
        return ANTREAN_TIDAK
    if waktu_kini < batas_aksi:
        return ANTREAN_BELUM
    if waktu_kini < batas_koreksi:
        return ANTREAN_AKSI
    return ANTREAN_RIWAYAT


def wajib_aktif(mulai: str) -> bool:
    """True bila cutoff sudah diisi dan pertemuan mulai pada atau sesudahnya. Cutoff dibaca saat dipanggil."""
    cutoff = PERTEMUAN_WAJIB_SEJAK
    if cutoff is None:
        return False
    return _ke_datetime(mulai) >= _ke_datetime(cutoff)


def anggota_masuk_form(penempatan_dibuat: str, mulai: str) -> bool:
    """Anggota ikut form bila penempatannya sudah ada sebelum atau pada saat pertemuan mulai."""
    return _ke_datetime(penempatan_dibuat) <= _ke_datetime(mulai)


# --- topik dan status -------------------------------------------------------------------

def daftar_topik_jurnal() -> List[str]:
    """Topik yang boleh dicatat: daftar topik tanpa paket sintetis, lalu `lainnya`. Salinan baru tiap panggilan."""
    terpilih = [topik for topik in topics.daftar_topik() if topik != TOPIK_SINTETIS]
    return terpilih + [TOPIK_LAINNYA]


def topik_sah(nilai) -> bool:
    return type(nilai) is str and nilai in daftar_topik_jurnal()


def label_topik(nilai: str) -> str:
    """Judul tampil topik. `lainnya` = 'Topik lain'; id yang tak dikenal modul topik dikembalikan apa adanya."""
    if type(nilai) is not str:
        raise ValueError("Topik harus berupa teks.")
    if nilai == TOPIK_LAINNYA:
        return LABEL_TOPIK_LAINNYA
    try:
        return topics.ambil(nilai).nama
    except KeyError:
        return nilai


def status_sah(nilai) -> bool:
    return type(nilai) is str and nilai in STATUS_KEHADIRAN
