"""Dasar domain langganan Latihan Harian: paket, konstanta, galat, waktu dan kalender WIB.

Tanpa jaringan, env, atau DB. Nominal paket HANYA konstanta di sini (server); tidak pernah dari form.
Waktu disimpan sebagai UTC naif `YYYY-MM-DDTHH:MM:SS` (format ledger pesanan) dan dihitung dalam WIB
(UTC+7 tetap, seperti `domain_clock`) hanya untuk penambahan bulan kalender.

Rentang nominal tiap paket (harga + kode unik 1..999) SENGAJA tidak saling beririsan dan tidak beririsan
dengan Paket Coba (Rp49.001 sampai Rp49.999): selama harga paket berjarak lebih dari 999 satu sama lain,
nominal transfer sebuah tagihan tidak mungkin sama dengan nominal tagihan produk lain (dijaga tes).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import re
import secrets
from types import MappingProxyType
from typing import Optional

import pesanan_dasar as d
from schema_transfer import BATAS_ALASAN, BATAS_UKURAN_BUKTI, KODE_MAKS, KODE_MIN, MAKS_BUKTI, MIME_BUKTI

PAKET_BULANAN = "bulanan"
PAKET_TAHUNAN = "tahunan"
RUPIAH_PAKET_COBA = d.RUPIAH_PAKET
KEDALUWARSA_JAM = d.KEDALUWARSA_JAM
HARI_TAHAN_KODE_LUNAS = 30
HARI_PENGINGAT = 3
WIB_JAM = 7
JAM_PER_HARI = 24
DETIK_PER_HARI = 86400
PREFIX_ORDER = "hor_"
FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"
KEPUTUSAN_SETUJU = "setuju"
KEPUTUSAN_TOLAK = "tolak"

STATUS_BELUM_BAYAR = d.STATUS_BELUM_BAYAR
STATUS_MENUNGGU = d.STATUS_MENUNGGU_VERIFIKASI
STATUS_DITOLAK = d.STATUS_DITOLAK
STATUS_KEDALUWARSA = d.STATUS_KEDALUWARSA
STATUS_AKTIF = "aktif"
STATUS_TERBUKA = (STATUS_BELUM_BAYAR, STATUS_MENUNGGU, STATUS_DITOLAK)

_POLA_ORDER = re.compile(r"hor_[0-9a-f]{32}")
_POLA_BERKAS = re.compile(r"[0-9a-f]{32}")
_POLA_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Paket:
    kode: str
    nama: str
    rupiah: int
    bulan: int


_DAFTAR_PAKET = (
    Paket(PAKET_BULANAN, "Bulanan", 39000, 1),
    Paket(PAKET_TAHUNAN, "Tahunan", 349000, 12),
)
PAKET = MappingProxyType({p.kode: p for p in _DAFTAR_PAKET})


class LanggananKonflik(d.PesananKonflik):
    """Keadaan bentrok (tagihan lain berjalan, status tak menerima bukti, dst.); pesan tetap."""


class KodeUnikHabis(LanggananKonflik):
    def __init__(self):
        super().__init__("kode unik langganan habis")


class BatasBukti(LanggananKonflik):
    def __init__(self):
        super().__init__("batas bukti langganan tercapai")


def paket_sah(kode) -> Paket:
    """Paket dari kode; kode asing, bukan str, atau nominal apa pun -> PesananDataTidakSah."""
    if type(kode) is not str or kode not in PAKET:
        raise d.PesananDataTidakSah("paket tidak sah")
    return PAKET[kode]


def id_order_baru() -> str:
    return PREFIX_ORDER + secrets.token_hex(16)


def periksa_order_id(nilai) -> str:
    if type(nilai) is not str or _POLA_ORDER.fullmatch(nilai) is None:
        raise d.PesananDataTidakSah("order_id tidak sah")
    return nilai


def periksa_siswa_id(nilai) -> int:
    if type(nilai) is not int or nilai < 1:
        raise d.PesananDataTidakSah("siswa_id tidak sah")
    return nilai


def periksa_meta_bukti(mime, ukuran, sha256, nama_tersimpan) -> None:
    """Metadata bukti harus sah sebelum DB disentuh (pesan tetap, tanpa gema)."""
    if mime not in MIME_BUKTI:
        raise d.PesananDataTidakSah("tipe bukti tidak sah")
    if type(ukuran) is not int or not 1 <= ukuran <= BATAS_UKURAN_BUKTI:
        raise d.PesananDataTidakSah("ukuran bukti tidak sah")
    if type(sha256) is not str or _POLA_SHA256.fullmatch(sha256) is None:
        raise d.PesananDataTidakSah("sha256 bukti tidak sah")
    if type(nama_tersimpan) is not str or _POLA_BERKAS.fullmatch(nama_tersimpan) is None:
        raise d.PesananDataTidakSah("nama berkas bukti tidak sah")


# --- waktu dan kalender -------------------------------------------------------------

def ke_baku(nilai) -> str:
    """Waktu baku UTC naif dari str ISO (tanggal saja = tengah malam; naif = UTC), datetime, date, atau epoch.

    Satu pintu normalisasi untuk `kini` yang disuntik pemanggil (kontrak `akses_harian`): format
    pemanggil tidak pernah diasumsikan.
    """
    if isinstance(nilai, datetime):
        waktu = nilai
    elif isinstance(nilai, date):
        waktu = datetime(nilai.year, nilai.month, nilai.day)
    elif type(nilai) in (int, float):
        waktu = datetime.fromtimestamp(nilai, timezone.utc)
    else:
        return d.waktu_baku(nilai)
    if waktu.tzinfo is not None:
        waktu = waktu.astimezone(timezone.utc).replace(tzinfo=None)
    return waktu.strftime(FORMAT_WAKTU)


def _ke_datetime(baku: str) -> datetime:
    return datetime.strptime(baku, FORMAT_WAKTU)


def tambah_bulan_wib(baku: str, bulan: int) -> str:
    """`baku` + `bulan` bulan kalender dihitung dalam WIB; hari dijepit ke akhir bulan (31 Jan -> 28/29 Feb)."""
    wib = _ke_datetime(baku) + timedelta(hours=WIB_JAM)
    indeks = wib.year * 12 + (wib.month - 1) + bulan
    tahun, bulan_baru = divmod(indeks, 12)
    hari = min(wib.day, calendar.monthrange(tahun, bulan_baru + 1)[1])
    hasil = wib.replace(year=tahun, month=bulan_baru + 1, day=hari) - timedelta(hours=WIB_JAM)
    return hasil.strftime(FORMAT_WAKTU)


def tambah_jam(baku: str, jam: int) -> str:
    return d.tambah_jam(baku, jam)


def tanggal_wib(baku: str) -> date:
    return (_ke_datetime(baku) + timedelta(hours=WIB_JAM)).date()


def sisa_hari(berakhir: str, kini) -> int:
    """Sisa hari dibulatkan ke atas (>= 1 selama masih aktif); 0 bila sudah berakhir."""
    selisih = (_ke_datetime(berakhir) - _ke_datetime(ke_baku(kini))).total_seconds()
    if selisih <= 0:
        return 0
    return max(1, -int(-selisih // DETIK_PER_HARI))


def batas_hari_lalu(kini: str, hari: int) -> str:
    return d.tambah_jam(kini, -JAM_PER_HARI * hari)


def alasan_sah(alasan) -> str:
    """Alasan penolakan: str, 1..BATAS_ALASAN setelah strip, tanpa karakter kontrol."""
    import unicodedata
    if type(alasan) is not str:
        raise d.PesananDataTidakSah("alasan penolakan wajib diisi")
    bersih = alasan.strip()
    if not 1 <= len(bersih) <= BATAS_ALASAN:
        raise d.PesananDataTidakSah("alasan penolakan tidak sah")
    if any(unicodedata.category(c).startswith("C") for c in bersih):
        raise d.PesananDataTidakSah("alasan penolakan tidak sah")
    return bersih


def paket_dari_baris(baris) -> Optional[Paket]:
    return None if baris is None else PAKET[baris["paket"]]
