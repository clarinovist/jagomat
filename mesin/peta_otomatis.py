"""Penerbitan otomatis laporan Peta Kemampuan setelah pembayaran lunas, tanpa Guru.

Keputusan Pemilik (26 Nov 2026): laporan terbit begitu pembayaran sah. Modul ini MEMAKAI ULANG pembaca dan toko yang
sudah ada (`cek_ringkasan_admin`, `peta_laporan_snapshot`, `peta_laporan_store`, `purna`), tanpa skema baru dan
tanpa SQL tabel `peta_laporan`. Penulis laporan = PELAKU_SISTEM, bukan akun Guru; draf Guru yang sudah ada tidak disentuh.

Dua DB tidak pernah dipegang bersamaan dalam transaksi: ledger admin dibaca lalu ditutup (`baca_izin`), DB belajar
ditulis dan di-commit (`terbitkan_bila_siap`), baru sesudah itu purna dicatat (`catat_purna_sistem`).

Transaksi: koneksi yang SUDAH dalam transaksi ditolak (GAGAL, tanpa tulis), seperti `pesanan_dasar.tulis`. SAVEPOINT
sengaja tidak dipakai: laporan di dalam transaksi pemanggil belum commit saat purna sudah tercatat, dan rollback
pemanggil kemudian menghapus laporan yang purnanya sudah tercatat.

Pemicu: `setelah_lunas` (titik pembayaran lunas) dan `pastikan_untuk_siswa` (halaman orang tua dibuka). Keduanya
best-effort: tidak pernah melempar ke pemanggil dan tidak menggagalkan pembayaran. Log hanya memuat NAMA tipe galat.
"""
from __future__ import annotations

import calendar
import contextlib
import logging
import sqlite3
from datetime import datetime, timedelta

import admin_store
import cek_ringkasan_admin
import database
import pesanan
import pesanan_admin_order as po
import pesanan_alur
import pesanan_dasar as d
import peta_laporan_snapshot as snapshot
import peta_laporan_store as toko
import purna

PELAKU_SISTEM = "sistem"
CATATAN_SISTEM = "Laporan ini disusun otomatis dari hasil cek kemampuan setelah pembayaran terverifikasi."
TERBIT = "terbit"
SUDAH_ADA = "sudah_ada"
TIDAK_LAYAK = "tidak_layak"
BAHAN_BELUM = "bahan_belum"
GAGAL = "gagal"

_FORMAT_BAKU = "%Y-%m-%dT%H:%M:%S"
_FORMAT_WIB = "%Y-%m-%d %H:%M:%S"
_SELISIH_WIB = timedelta(hours=7)
_GALAT_LEDGER = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)
_GALAT_TULIS = (ValueError, sqlite3.Error)
_log = logging.getLogger(__name__)


@contextlib.contextmanager
def _buka_ledger(tulis=False):
    """Satu-satunya pintu ke ledger admin; `admin_store.BAWAAN` dibaca saat dipanggil."""
    with pesanan.buka(admin_store.BAWAAN, tulis_data=tulis) as kon:
        yield kon


def _epoch(sekarang: str) -> int:
    return calendar.timegm(datetime.strptime(d.waktu_baku(sekarang), _FORMAT_BAKU).timetuple())


def _wib_ke_baku(waktu_wib: str) -> str:
    return (datetime.strptime(waktu_wib, _FORMAT_WIB) - _SELISIH_WIB).strftime(_FORMAT_BAKU)


def _kini(sekarang):
    return pesanan_alur.waktu_sekarang() if sekarang is None else sekarang


def _terbit_oleh_sistem(laporan) -> bool:
    return (laporan is not None and laporan["diterbitkan"] is not None
            and laporan["diterbitkan_oleh"] == PELAKU_SISTEM)


def _purna_lunas_aman(purna_ringkas) -> bool:
    return (purna_ringkas["terpasang"] is True and purna_ringkas["lunas"] is True
            and purna_ringkas["direfund"] is False and purna_ringkas["ditahan"] is False)


def izin_bila_sah(order, purna_ringkas, id_akun=None):
    """Izin terbit dari keadaan order (murni); None bila salah satu guard gagal (fail-closed).

    Guard: akun cocok (bila `id_akun` diberikan), status turunan sudah_dibayar, purna terpasang dan lunas, tidak
    direfund, tidak ditahan. Kunci hasil hanya dari `order` (baris ledger di server), tidak dari argumen lain.
    """
    if id_akun is not None and order["akun_id"] != id_akun:
        return None
    if order["status"] != d.STATUS_SUDAH_DIBAYAR:
        return None
    if not _purna_lunas_aman(purna_ringkas):
        return None
    return {"order_id": order["order_id"], "siswa_id": order["siswa_id"], "cek_id": order["cek_id"],
            "akun_id": order["akun_id"], "terbit": purna_ringkas["terbit"]}


def baca_izin(siswa_id, sekarang, id_akun=None):
    """Izin terbit satu anak dari ledger admin (read-only, ditutup sebelum kembali); None bila tidak layak atau galat."""
    try:
        with _buka_ledger() as kon:
            order = po.order_peta_untuk_siswa(kon, siswa_id, sekarang)
            if order is None:
                return None
            purna_ringkas = po.purna_ringkas(kon, order["order_id"], sekarang)
    except _GALAT_LEDGER as galat:
        _log.warning("ledger Peta tidak terbaca: %s", type(galat).__name__)
        return None
    return izin_bila_sah(order, purna_ringkas, id_akun)


def _isi_bila_layak(kon, izin, sekarang):
    """Isi laporan dari bahan server, atau None bila bahan belum layak (dihapus, belum dinilai, tidak cocok)."""
    try:
        ringkasan = cek_ringkasan_admin.ringkasan_untuk_order(
            kon, izin["siswa_id"], izin["cek_id"], izin["akun_id"], sekarang)
        return snapshot.bangun(ringkasan)
    except ValueError:
        return None


def _hasil_setelah_batal(kon, siswa_id) -> str:
    """Setelah transaksi batal: laporan sudah ada (penerbit lain menang) = SUDAH_ADA; selain itu GAGAL."""
    if kon.in_transaction:
        kon.rollback()  # transaksi ini milik kita: koneksi tidak dalam transaksi saat masuk (dicek pemanggil)
    try:
        ada = toko.ambil(kon, siswa_id)
    except _GALAT_TULIS:
        return GAGAL
    return GAGAL if ada is None else SUDAH_ADA


def _tulis_terbit(kon, siswa_id, isi, epoch) -> str:
    """Draf, catatan sistem, dan terbit dalam SATU transaksi (`d.tulis`); galat apa pun membatalkan seluruhnya."""
    try:
        with d.tulis(kon):
            toko.buat_draf(kon, siswa_id, PELAKU_SISTEM, isi, epoch)
            toko.simpan_catatan(kon, siswa_id, CATATAN_SISTEM)
            toko.terbitkan(kon, siswa_id, PELAKU_SISTEM, epoch)
    except _GALAT_TULIS as galat:
        _log.warning("terbit laporan sistem dibatalkan: %s", type(galat).__name__)
        return _hasil_setelah_batal(kon, siswa_id)
    return TERBIT


def terbitkan_bila_siap(kon, izin, sekarang) -> str:
    """Terbitkan laporan sistem bila belum ada dan bahannya layak; mengembalikan salah satu konstanta hasil.

    Urutan: izin kosong -> TIDAK_LAYAK; koneksi sudah dalam transaksi -> GAGAL tanpa tulis; draf atau terbit yang sudah
    ada -> SUDAH_ADA tanpa sentuhan; bahan belum layak -> BAHAN_BELUM; selain itu tulis dalam satu transaksi.
    `sekarang` = waktu baku ISO UTC.
    """
    if izin is None:
        return TIDAK_LAYAK
    if kon.in_transaction:
        _log.warning("terbit laporan sistem dilewati: koneksi sudah dalam transaksi")
        return GAGAL
    try:
        if toko.ambil(kon, izin["siswa_id"]) is not None:
            return SUDAH_ADA
        epoch = _epoch(sekarang)
        isi = _isi_bila_layak(kon, izin, sekarang)
    except _GALAT_TULIS as galat:
        _log.warning("laporan sistem tidak bisa disiapkan: %s", type(galat).__name__)
        return GAGAL
    if isi is None:
        return BAHAN_BELUM
    return _tulis_terbit(kon, izin["siswa_id"], isi, epoch)


def catat_purna_sistem(order_id, waktu_terbit_wib) -> bool:
    """Catat terbit di purna sebagai penulis `sistem` (idempoten). Dipanggil SESUDAH commit laporan; tidak melempar."""
    try:
        terbit = _wib_ke_baku(waktu_terbit_wib)
        with _buka_ledger(tulis=True) as kon:
            purna.catat_terbit(kon, order_id, PELAKU_SISTEM, terbit)
    except Exception as galat:  # noqa: BLE001
        # Disengaja: laporan sudah sah; galat pencatatan tidak boleh mengubah hasil penerbitan. Log hanya NAMA tipe.
        _log.warning("pencatatan terbit purna sistem gagal: %s", type(galat).__name__)
        return False
    return True


def _waktu_catat_purna(kon, izin, hasil):
    """Waktu terbit (WIB) yang perlu dicatat ke purna, atau None: hanya laporan `sistem` yang belum tercatat."""
    if izin is None or hasil not in (TERBIT, SUDAH_ADA):
        return None
    laporan = toko.ambil(kon, izin["siswa_id"])
    if not _terbit_oleh_sistem(laporan):
        return None
    if hasil == TERBIT or izin["terbit"] is None:
        return laporan["diterbitkan"]
    return None


def pastikan_untuk_siswa(kon, id_akun, siswa_id, sekarang=None) -> str:
    """Jalur halaman orang tua: terbitkan bila layak, lalu sinkronkan purna. Tidak pernah melempar ke pemanggil.

    `kon` = DB belajar milik pemanggil; `id_akun` dan `siswa_id` berasal dari sesi server. Pencatatan purna
    dilakukan setelah laporan ditulis, tanpa transaksi terbuka di DB belajar.
    """
    kini = _kini(sekarang)
    try:
        izin = baca_izin(siswa_id, kini, id_akun)
        hasil = terbitkan_bila_siap(kon, izin, kini)
        waktu = _waktu_catat_purna(kon, izin, hasil)
    except Exception as galat:  # noqa: BLE001
        _log.warning("pastikan laporan sistem gagal: %s", type(galat).__name__)
        return GAGAL
    if waktu is not None:
        catat_purna_sistem(izin["order_id"], waktu)
    return hasil


def _terbitkan_setelah_lunas(order_id, kini) -> None:
    with _buka_ledger() as kon:
        kunci = po.kunci_cek(kon, order_id)
    if kunci is None:
        return
    siswa_id, _cek_id, id_akun = kunci
    izin = baca_izin(siswa_id, kini, id_akun)
    if izin is None or izin["order_id"] != order_id:
        return
    with database.buka() as belajar:
        hasil = terbitkan_bila_siap(belajar, izin, kini)
        waktu = _waktu_catat_purna(belajar, izin, hasil)
    if waktu is not None:
        catat_purna_sistem(order_id, waktu)


def setelah_lunas(order_id, sekarang=None) -> None:
    """Pemicu setelah pembayaran lunas (persetujuan transfer, pencatatan QRIS). Tidak pernah melempar."""
    try:
        _terbitkan_setelah_lunas(order_id, _kini(sekarang))
    except Exception as galat:  # noqa: BLE001
        # Disengaja: pembayaran sudah sah dan tidak boleh gagal karena penerbitan laporan. Log hanya NAMA tipe.
        _log.warning("terbit laporan setelah lunas dilewati: %s", type(galat).__name__)


def oleh_sistem(kon, siswa_id) -> bool:
    """True hanya bila laporan anak ini sudah terbit oleh `sistem` (tanpa membandingkan teks catatan); galat = False."""
    try:
        return _terbit_oleh_sistem(toko.ambil(kon, siswa_id))
    except _GALAT_TULIS:
        return False
