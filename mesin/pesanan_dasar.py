"""Dasar domain pesanan Paket Coba: konstanta, galat, validasi, transaksi.

Tanpa jaringan, tanpa env, tanpa DB belajar, tanpa tabel `langganan_*`. Waktu dan
id disuntik pemanggil. Galat memakai pesan tetap: tidak pernah memuat id,
nominal, nama, atau payload.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3

RUPIAH_PAKET = 49000
KUOTA_ORDER = 20
PREFIX_ORDER = "ord_"
KEDALUWARSA_JAM = 24
PROVIDER = "midtrans"
CHANNEL = "qris"
MATA_UANG = "IDR"

STATUS_BELUM_BAYAR = "belum_bayar"
STATUS_SUDAH_DIBAYAR = "sudah_dibayar"
STATUS_PERLU_DIPERIKSA = "perlu_diperiksa"
STATUS_KEDALUWARSA = "kedaluwarsa"
STATUS_DIREFUND = "direfund"
# Khusus jalur transfer rekening: ada bukti belum diputuskan admin / keputusan terakhir menolak.
STATUS_MENUNGGU_VERIFIKASI = "menunggu_verifikasi"
STATUS_DITOLAK = "ditolak"
STATUS_TURUNAN = (STATUS_BELUM_BAYAR, STATUS_SUDAH_DIBAYAR, STATUS_PERLU_DIPERIKSA,
                  STATUS_KEDALUWARSA, STATUS_DIREFUND, STATUS_MENUNGGU_VERIFIKASI,
                  STATUS_DITOLAK)

# Status turunan yang boleh dicatat refund manualnya. SATU sumber: dipakai server (`pesanan_refund_aturan`)
# dan UI (`admin_pesanan_pages.STATUS_REFUND`), jadi tombol dan penegakan tidak bisa berbeda.
STATUS_BISA_REFUND = (STATUS_SUDAH_DIBAYAR, STATUS_PERLU_DIPERIKSA)

# Status provider kelas refund/chargeback: tidak pernah menjadi lunas.
STATUS_REFUND_PROVIDER = ("refund", "partial_refund", "chargeback")

_POLA_ORDER = re.compile(r"ord_[0-9a-f]{32}")
_POLA_AKUN = re.compile(r"akun_[0-9a-f]{32}")
_POLA_OPERASI = re.compile(r"[A-Za-z0-9_-]{8,64}")
_POLA_REFERENSI = re.compile(r"[A-Za-z0-9_-]{1,64}")
_POLA_PELAKU = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_POLA_STATUS = re.compile(r"[a-z_]{1,32}")
_POLA_HEX64 = re.compile(r"[0-9a-f]{64}")
_FORMAT_WAKTU = "%Y-%m-%dT%H:%M:%S"


class PesananError(Exception):
    """Dasar galat domain pesanan; pesan tetap tanpa data sensitif."""


class PesananTidakDitemukan(PesananError):
    """Order/prasyarat tidak ada atau bukan milik akun: jawaban identik (404)."""

    def __init__(self):
        super().__init__("pesanan tidak ditemukan")


class PesananButuhKontak(PesananError):
    def __init__(self):
        super().__init__("kontak akun belum tersedia")


class PesananKuotaHabis(PesananError):
    def __init__(self):
        super().__init__("kuota pesanan habis")


class PesananKonflik(PesananError):
    """Operasi/identitas yang sama dipakai dengan isi berbeda atau keadaan bentrok."""


class PesananDataTidakSah(PesananError, ValueError):
    """Input tidak memenuhi kontrak domain."""


def _cocok(pola, nilai, nama):
    if type(nilai) is not str or pola.fullmatch(nilai) is None:
        raise PesananDataTidakSah("%s tidak sah" % nama)
    return nilai


def periksa_order_id(nilai):
    return _cocok(_POLA_ORDER, nilai, "order_id")


def periksa_akun_id(nilai):
    return _cocok(_POLA_AKUN, nilai, "akun_id")


def periksa_operasi_id(nilai):
    return _cocok(_POLA_OPERASI, nilai, "operasi_id")


def periksa_referensi(nilai, nama="referensi"):
    return _cocok(_POLA_REFERENSI, nilai, nama)


def periksa_pelaku(nilai):
    return _cocok(_POLA_PELAKU, nilai, "dicatat_oleh")


def periksa_hash(nilai):
    return _cocok(_POLA_HEX64, nilai, "hash_payload")


def periksa_bilangan(nilai, nama):
    if type(nilai) is not int or nilai < 1:
        raise PesananDataTidakSah("%s tidak sah" % nama)
    return nilai


def status_aman(nilai):
    """Status provider yang aman disimpan; selain itu 'tidak_dikenal' (tanpa gema)."""
    if type(nilai) is str and _POLA_STATUS.fullmatch(nilai):
        return nilai
    return "tidak_dikenal"


def waktu_baku(sekarang):
    """ISO string menjadi 'YYYY-MM-DDTHH:MM:SS' UTC naif; selain itu galat."""
    if type(sekarang) is not str:
        raise PesananDataTidakSah("waktu tidak sah")
    try:
        waktu = datetime.fromisoformat(sekarang)
    except ValueError:
        raise PesananDataTidakSah("waktu tidak sah") from None
    if waktu.tzinfo is not None:
        waktu = waktu.astimezone(timezone.utc).replace(tzinfo=None)
    return waktu.strftime(_FORMAT_WAKTU)


def tambah_jam(waktu_teks, jam):
    awal = datetime.strptime(waktu_teks, _FORMAT_WAKTU)
    return (awal + timedelta(hours=jam)).strftime(_FORMAT_WAKTU)


def periksa_koneksi(kon):
    """Koneksi wajib `row_factory=sqlite3.Row` (dibuat oleh :func:`buka`)."""
    if getattr(kon, "row_factory", None) is not sqlite3.Row:
        raise PesananDataTidakSah("koneksi tidak sah")
    return kon


@contextmanager
def tulis(kon):
    """Satu transaksi tulis `BEGIN IMMEDIATE`; domain yang memiliki transaksinya.

    Koneksi yang sudah dalam transaksi ditolak: pengecekan kuota/unik harus
    atomik dan tidak boleh bergantung pada kehati-hatian pemanggil.
    """
    periksa_koneksi(kon)
    if kon.in_transaction:
        raise PesananDataTidakSah("koneksi sudah dalam transaksi")
    kon.execute("BEGIN IMMEDIATE")
    try:
        yield kon
    except BaseException:
        kon.rollback()
        raise
    kon.commit()


@contextmanager
def buka(path, *, tulis_data=False):
    """Koneksi ke DB admin existing (mode ro/rw), tanpa transaksi terbuka.

    Skema admin dan skema pesanan wajib sah; pesanan yang belum dimigrasikan
    ditolak (StoreBelumSiap). Tidak membuat file dan tidak memigrasi.
    """
    import admin_store_core
    import schema_pesanan
    kon = admin_store_core.koneksi(Path(path), "rw" if tulis_data else "ro")
    try:
        if not tulis_data:
            kon.execute("PRAGMA query_only=ON")
        admin_store_core.validasi_skema(kon)
        if not schema_pesanan.validasi(kon):
            raise admin_store_core.StoreBelumSiap("pesanan belum dipasang")
        yield kon
    finally:
        kon.close()
