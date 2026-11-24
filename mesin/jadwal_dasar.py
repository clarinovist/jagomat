"""Dasar domain jadwal Paket Belajar: galat, validasi isian, dan kalender WIB untuk 8 pertemuan mingguan.

Tanpa DB/jaringan. Waktu disimpan UTC naif `YYYY-MM-DDTHH:MM:SS` (format ledger), sedangkan admin mengisi
tanggal + jam WIB. Jadwal bukan ledger keuangan: waktu dan status batal boleh berubah, tetapi identitas baris
(kelompok/order/ke) dijaga skema.
"""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone

import harian_langganan_dasar as h
import pesanan_dasar as d
import schema_jadwal as s

WIB = timezone(timedelta(hours=7))
PERTEMUAN = s.PERTEMUAN_PER_PAKET
_POLA_KELOMPOK = re.compile(r"klp_[0-9a-f]{32}")
_POLA_GURU = re.compile(r"akun_[0-9a-f]{32}")
_POLA_TANGGAL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_POLA_JAM = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")


class JadwalKonflik(d.PesananKonflik):
    """Keadaan bentrok (kuota penuh, sudah ditempatkan, status belum aktif); pesan tanpa data."""


class JadwalPenuh(JadwalKonflik):
    def __init__(self):
        super().__init__("kelompok jadwal penuh")


class JadwalTidakSah(d.PesananDataTidakSah):
    """Isian jadwal tidak sah; tidak ada yang ditulis."""


class JadwalTidakDitemukan(d.PesananTidakDitemukan):
    """Kelompok/pertemuan tidak ada; diperlakukan seperti tidak ada, tanpa efek samping."""


def id_kelompok_baru() -> str:
    return s.ID_KELOMPOK + secrets.token_hex(16)


def periksa_kelompok_id(nilai) -> str:
    if type(nilai) is not str or _POLA_KELOMPOK.fullmatch(nilai) is None:
        raise JadwalTidakSah("id kelompok tidak sah")
    return nilai


def periksa_guru_id(nilai) -> str:
    if type(nilai) is not str or _POLA_GURU.fullmatch(nilai) is None:
        raise JadwalTidakSah("guru tidak sah")
    return nilai


def periksa_pertemuan_id(nilai) -> int:
    if type(nilai) is int and nilai >= 1:
        return nilai
    if type(nilai) is str and nilai.isascii() and nilai.isdigit() and 1 <= int(nilai) <= 999999:
        return int(nilai)
    raise JadwalTidakSah("pertemuan tidak sah")


def periksa_teks(nilai, label: str, maks: int) -> str:
    """Teks satu baris: di-strip, 1..maks karakter, tanpa karakter kontrol."""
    if type(nilai) is not str:
        raise JadwalTidakSah("%s tidak sah" % label)
    teks = nilai.strip()
    if not 1 <= len(teks) <= maks or any(ord(karakter) < 32 for karakter in teks):
        raise JadwalTidakSah("%s tidak sah" % label)
    return teks


def periksa_kuota(nilai) -> int:
    if type(nilai) is not int or not 1 <= nilai <= s.KUOTA_MAKS:
        raise JadwalTidakSah("kuota tidak sah")
    return nilai


def periksa_tanggal_jam(tanggal, jam) -> datetime:
    """WIB `YYYY-MM-DD` + `HH:MM` -> datetime WIB; isian tidak sah ditolak tanpa gema."""
    if type(tanggal) is not str or _POLA_TANGGAL.fullmatch(tanggal) is None:
        raise JadwalTidakSah("tanggal tidak sah")
    if type(jam) is not str or _POLA_JAM.fullmatch(jam) is None:
        raise JadwalTidakSah("jam tidak sah")
    try:
        return datetime.strptime(tanggal + "T" + jam, "%Y-%m-%dT%H:%M").replace(tzinfo=WIB)
    except ValueError:
        raise JadwalTidakSah("tanggal tidak sah") from None


def pertemuan_pertama(tanggal, jam, sekarang_baku: str, *, izinkan_lampau=False) -> str:
    """Baku UTC pertemuan pertama; tanggal WIB di masa lalu ditolak kecuali diminta."""
    waktu = periksa_tanggal_jam(tanggal, jam)
    if not izinkan_lampau and waktu.date() < h.tanggal_wib(sekarang_baku):
        raise JadwalTidakSah("tanggal mulai sudah lewat")
    return waktu.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def delapan_pertemuan(mulai_baku: str) -> tuple:
    """Delapan waktu baku mingguan mulai dari `mulai_baku`."""
    awal = datetime.strptime(mulai_baku, "%Y-%m-%dT%H:%M:%S")
    return tuple((awal + timedelta(days=7 * (ke - 1))).strftime("%Y-%m-%dT%H:%M:%S")
                 for ke in range(1, PERTEMUAN + 1))


def tanggal_jam_wib(baku: str) -> tuple:
    """Baku UTC -> (tanggal WIB `YYYY-MM-DD`, jam WIB `HH:MM`) untuk isian form."""
    waktu = datetime.strptime(baku, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).astimezone(WIB)
    return waktu.date().isoformat(), waktu.strftime("%H:%M")


def tanggal_wib(baku: str) -> date:
    return datetime.strptime(baku, "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc).astimezone(WIB).date()
