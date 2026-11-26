"""Dasar domain Paket Belajar 1 Bulan (kelas): konstanta, galat, validasi id, dan alat waktu.

Tanpa jaringan, env, atau DB. Harga dan aturan nominal HANYA di `paket_belajar_katalog`; modul ini tidak menyimpan
harga. Waktu disimpan UTC naif `YYYY-MM-DDTHH:MM:SS` (format ledger pesanan) dan dihitung WIB hanya untuk menambah
bulan kalender; alat waktu dan validasi bukti dipakai ulang dari `harian_langganan_dasar` (fungsi murni, tanpa
mengubahnya) supaya aturan kalender dan metadata bukti tidak bercabang.
"""
from __future__ import annotations

import re
import secrets

import harian_langganan_dasar as h
import paket_belajar_katalog as katalog
import pesanan_dasar as d

PREFIX_ORDER = "kor_"
PREFIX_KELUARGA = "kel_"
PREFIX_OPERASI_DEPOSIT = "kelas-"      # 'kelas-' + order_id: pola operasi purna hanya mengizinkan [A-Za-z0-9_-]
CATATAN_PAKAI_DEPOSIT = "kelas"
KEDALUWARSA_JAM = d.KEDALUWARSA_JAM
HARI_TAHAN_KODE_LUNAS = 30
BULAN_PER_PAKET = 1
KEPUTUSAN_SETUJU = h.KEPUTUSAN_SETUJU
KEPUTUSAN_TOLAK = h.KEPUTUSAN_TOLAK
MAKS_BUKTI = h.MAKS_BUKTI
KODE_MIN = h.KODE_MIN
KODE_MAKS = h.KODE_MAKS

STATUS_BELUM_BAYAR = katalog.STATUS_BELUM_BAYAR
STATUS_MENUNGGU = katalog.STATUS_MENUNGGU
STATUS_AKTIF = katalog.STATUS_AKTIF
STATUS_KEDALUWARSA = katalog.STATUS_KEDALUWARSA
STATUS_DITOLAK = katalog.STATUS_DITOLAK
STATUS_TERBUKA = (STATUS_BELUM_BAYAR, STATUS_MENUNGGU, STATUS_DITOLAK)
# Dibatalkan pembeli selama jendela bayar belum lewat. SENGAJA di luar STATUS_TERBUKA: tagihan batal tidak dihitung belum
# bayar, tidak diingatkan, tidak masuk antrean, dan tidak menerima bukti atau putusan.
STATUS_DIBATALKAN = katalog.STATUS_DIBATALKAN

_POLA_ORDER = re.compile(r"kor_[0-9a-f]{32}")

# Alat waktu dan validasi bukti: fungsi murni milik harian, dipakai apa adanya.
ke_baku = h.ke_baku
tambah_bulan_wib = h.tambah_bulan_wib
tambah_jam = h.tambah_jam
batas_hari_lalu = h.batas_hari_lalu
alasan_sah = h.alasan_sah
periksa_meta_bukti = h.periksa_meta_bukti


class KelasKonflik(d.PesananKonflik):
    """Keadaan bentrok (tagihan lain berjalan, status tak menerima bukti, dst.); pesan tetap tanpa data."""


class KodeUnikHabis(KelasKonflik):
    def __init__(self):
        super().__init__("kode unik paket belajar habis")


class BatasBukti(KelasKonflik):
    def __init__(self):
        super().__init__("batas bukti paket belajar tercapai")


class DepositTidakAktif(KelasKonflik):
    """Deposit yang dipotongkan di tagihan tidak lagi bisa dipakai saat lunas; tidak ada yang ditulis."""


class TagihanTidakSah(KelasKonflik):
    """Hitungan tagihan tersimpan tidak konsisten (nominal/total); tidak pernah disetujui."""


def kode_paket_sah(kode) -> str:
    """Kode paket dari katalog; selain itu (asing, bukan str) -> PesananDataTidakSah tanpa gema."""
    if type(kode) is not str:
        raise d.PesananDataTidakSah("paket tidak sah")
    try:
        return katalog.ambil(kode).kode
    except ValueError:
        raise d.PesananDataTidakSah("paket tidak sah") from None


def id_order_baru() -> str:
    return PREFIX_ORDER + secrets.token_hex(16)


def id_keluarga_baru() -> str:
    return PREFIX_KELUARGA + secrets.token_hex(16)


def periksa_order_id(nilai) -> str:
    if type(nilai) is not str or _POLA_ORDER.fullmatch(nilai) is None:
        raise d.PesananDataTidakSah("order_id tidak sah")
    return nilai


def periksa_siswa_id(nilai) -> int:
    if type(nilai) is not int or nilai < 1:
        raise d.PesananDataTidakSah("siswa_id tidak sah")
    return nilai


def operasi_deposit(order_id: str) -> str:
    """Id operasi purna deterministik untuk pemakaian deposit oleh satu order kelas (idempoten per order)."""
    return PREFIX_OPERASI_DEPOSIT + periksa_order_id(order_id)
