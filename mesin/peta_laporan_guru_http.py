"""Rute Guru laporan Peta Kemampuan untuk orang tua (D1-2): `/anak/<id>/peta` (GET) dan POST buat/catatan/terbitkan/hapus.

Pola `parent_report_http` (sisi Guru): dipasang SESUDAH palang login dan cek asal POST, SEBELUM penangkap `/anak/`.
- Kepemilikan: anak bukan milik Guru, anak tak ada, ATAU anak tanpa order Peta = satu halaman 404 identik, tanpa efek.
  Order dicari lewat `siswa_id` di ledger admin HANYA sesudah kepemilikan terbukti; kunci cek/akun dibaca server dari
  ledger, bukan dari URL atau form.
- Order belum sudah_dibayar (belum bayar, ditahan, direfund, dst.): GET = halaman informasi tanpa form dan tanpa data
  cek; POST = 409 tanpa efek. Ledger admin tak terbaca = halaman "belum bisa dibuka" 503, tanpa efek.
- Hanya peran guru yang menulis (POST admin = 403); admin boleh GET (baca saja, tanpa efek tulis apa pun).
- Isi laporan SELALU dibangun server (`cek_ringkasan_admin` -> `peta_laporan_snapshot.bangun`); form tidak pernah
  membawa isi. Form: buat = kosong; catatan = {catatan}; terbitkan/hapus = {konfirmasi} bernilai "1" (ditegakkan server).
- Dua DB tak pernah dipegang bersamaan: ledger admin dibaca lalu ditutup; DB belajar ditulis dan di-commit; baru
  sesudah itu `purna.catat_terbit` ditulis ke ledger admin. Kegagalan pencatatan purna TIDAK membatalkan laporan
  terbit: hanya NAMA tipe galat yang dicatat di log, dan pencatatan diulang (idempoten) tiap Guru membuka halaman Peta
  selagi laporan terbit tetapi purna belum mencatat. Waktu terbit purna = waktu terbit laporan, bukan jam pengulangan.
"""
from __future__ import annotations

import calendar
import logging
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

import admin_store
import cek_ringkasan_admin
import database
import parent_report_http as dasar
import pesanan
import pesanan_admin_order as po
import pesanan_alur as alur
import pesanan_dasar as d
import peta_laporan_guru_pages as hal
import peta_laporan_snapshot as snapshot
import peta_laporan_store as toko
import purna

_POLA = re.compile(r"/anak/(\d{1,18})/peta(?:/(buat|catatan|terbitkan|hapus))?")
_GALAT_ADMIN = (admin_store.StoreBelumSiap, pesanan.PesananError, sqlite3.Error, OSError)
_GALAT_LAPORAN = (ValueError, sqlite3.Error)
_PELAKU_BAWAAN = "guru"
_SELISIH_WIB = timedelta(hours=7)
_FORMAT_BAKU = "%Y-%m-%dT%H:%M:%S"
_FORMAT_WIB = "%Y-%m-%d %H:%M:%S"
PESAN_STATUS = "Aksi tidak dapat dilakukan pada laporan dengan status ini."
PESAN_BAHAN = "Laporan belum bisa dibuat: data per materi tidak tersedia atau draf sudah ada."
PESAN_CATATAN_PANJANG = "Catatan terlalu panjang (maksimal 2000 karakter)."
PESAN_CATATAN_ISI = "Catatan berisi karakter yang tidak diperbolehkan."
PESAN_CATATAN_TERLARANG = (
    "Catatan tidak boleh memuat nomor telepon, tautan, alamat email, atau istilah internal "
    "seperti kode diagnosis atau kunci jawaban.")
PESAN_CATATAN_TERSIMPAN = (
    "Catatan yang tersimpan tidak memenuhi aturan (tanpa nomor telepon, tautan, alamat email, atau istilah internal). "
    "Ubah dan simpan catatan dulu sebelum menerbitkan.")
_PESAN_KODE_CATATAN = {
    toko.CATATAN_PANJANG: PESAN_CATATAN_PANJANG,
    toko.CATATAN_KONTROL: PESAN_CATATAN_ISI,
    toko.CATATAN_KONTAK: PESAN_CATATAN_TERLARANG,
    toko.CATATAN_ISTILAH_INTERNAL: PESAN_CATATAN_TERLARANG,
}
PESAN_CATATAN_KOSONG = "Isi catatan untuk orang tua dan simpan dulu sebelum menerbitkan."
PESAN_FORM = "Isian tidak sah atau terlalu besar."
PESAN_KONFIRMASI = "Centang kotak konfirmasi dulu. Tidak ada yang diubah."
_log = logging.getLogger(__name__)


class OrderTakTerbaca(Exception):
    """Ledger admin tidak bisa dibaca (pesan tetap; tipe galat asli hanya di log)."""


@contextmanager
def _buka_admin(tulis: bool = False):
    """Satu-satunya pintu ke ledger admin. `admin_store.BAWAAN` dibaca saat dipanggil (bukan salinan impor)."""
    with pesanan.buka(admin_store.BAWAAN, tulis_data=tulis) as kon:
        yield kon


def _kini() -> str:
    return alur.waktu_sekarang()


def _epoch(kini: str) -> int:
    return calendar.timegm(datetime.strptime(d.waktu_baku(kini), _FORMAT_BAKU).timetuple())


def _wib_ke_baku(waktu_wib: str) -> str:
    """Waktu terbit tersimpan (WIB) menjadi waktu baku UTC naif untuk domain purna."""
    return (datetime.strptime(waktu_wib, _FORMAT_WIB) - _SELISIH_WIB).strftime(_FORMAT_BAKU)


def _pelaku(akun) -> str:
    try:
        return d.periksa_pelaku(akun)
    except d.PesananDataTidakSah:
        return _PELAKU_BAWAAN


def _baca_order(siswa_id: int, kini: str):
    """(order, ringkasan purna) dari ledger admin; ringkasan hanya untuk order lunas normal (selain itu None)."""
    try:
        with _buka_admin() as kon:
            order = po.order_peta_untuk_siswa(kon, siswa_id, kini)
            if order is None or not po.kartu_cek_berlaku(order["status"]):
                return order, None
            return order, po.purna_ringkas(kon, order["order_id"], kini)
    except _GALAT_ADMIN as galat:
        _log.warning("ledger Peta tidak terbaca: %s", type(galat).__name__)
        raise OrderTakTerbaca() from None


def _catat_purna(order_id: str, laporan: dict) -> bool:
    """Catat terbit di purna (idempoten) dengan waktu terbit laporan. Gagal = log tipe galat, False; tidak melempar.

    `except Exception` disengaja: dipanggil SESUDAH commit laporan, jadi galat apa pun tidak boleh mengubah hasil
    penerbitan menjadi 500.
    """
    try:
        terbit = _wib_ke_baku(laporan["diterbitkan"])
        with _buka_admin(True) as kon:
            purna.catat_terbit(kon, order_id, _pelaku(laporan["diterbitkan_oleh"]), terbit)
        return True
    except Exception as galat:  # noqa: BLE001
        _log.warning("pencatatan terbit purna gagal: %s", type(galat).__name__)
        return False


def _sinkron_bila_perlu(ident, order: dict, purna_ringkas: dict, laporan, kini: str) -> dict:
    """Ulangi pencatatan terbit purna (hanya Guru; admin baca-saja). Mengembalikan ringkasan purna terbaru."""
    perlu = (ident and ident[1] == "guru" and laporan is not None and laporan["diterbitkan"]
             and purna_ringkas["terpasang"] and purna_ringkas["terbit"] is None)
    if not perlu or not _catat_purna(order["order_id"], laporan):
        return purna_ringkas
    try:
        return _baca_order(order["siswa_id"], kini)[1] or purna_ringkas
    except OrderTakTerbaca:
        return purna_ringkas


def _cek_untuk(kon, order: dict, kini: str):
    """Ringkasan allowlist data cek, atau None bila tak terbaca (galat dicatat tanpa isi)."""
    try:
        return cek_ringkasan_admin.ringkasan_untuk_order(
            kon, order["siswa_id"], order["cek_id"], order["akun_id"], kini)
    except (ValueError, LookupError, sqlite3.Error) as galat:
        _log.warning("data cek Peta tidak terbaca: %s", type(galat).__name__)
        return None


def _kirim_halaman(penangan, isi: bytes, kode: int = 200) -> bool:
    penangan._kirim_tautan(isi, kode)
    return True


def _render(penangan, kon, siswa, ident, order, purna_ringkas, kini, *, galat="", kode=200,
            catatan_kiriman=None) -> bool:
    """Halaman Peta (order lunas); data cek hanya dibaca bila belum ada laporan."""
    try:
        laporan = toko.ambil(kon, siswa["id"])
    except _GALAT_LAPORAN as err:
        _log.warning("laporan Peta tidak terbaca: %s", type(err).__name__)
        return _kirim_halaman(penangan, hal.halaman_belum_bisa(siswa, ident), 503)
    if laporan is not None and kode == 200:
        purna_ringkas = _sinkron_bila_perlu(ident, order, purna_ringkas, laporan, kini)
    cek = _cek_untuk(kon, order, kini) if laporan is None else None
    isi = hal.halaman_peta(
        siswa, ident, purna=purna_ringkas, laporan=laporan, cek=cek, hanya_lihat=not ident or ident[1] != "guru",
        galat=galat, catatan_kiriman=catatan_kiriman)
    return _kirim_halaman(penangan, isi, kode)


def _konteks(penangan, kon, anak_id: int):
    """(siswa, ident) bila anak ada dan milik pemirsa; selain itu None (pemanggil menjawab 404 identik)."""
    siswa = kon.execute("SELECT * FROM siswa WHERE id = ?", (anak_id,)).fetchone()
    if siswa is None or not penangan._bisa_lihat_siswa(kon, anak_id):
        return None
    return siswa, penangan._identitas()


def tangani_get(penangan, jalur: str) -> bool:
    cocok = _POLA.fullmatch(jalur)
    if cocok is None:
        return False
    anak_id, aksi = int(cocok.group(1)), cocok.group(2)
    with database.buka() as kon:
        konteks = None if aksi else _konteks(penangan, kon, anak_id)
        if konteks is None:
            dasar._tidak_ada(penangan)
            return True
        siswa, ident = konteks
        kini = _kini()
        try:
            order, purna_ringkas = _baca_order(anak_id, kini)
        except OrderTakTerbaca:
            return _kirim_halaman(penangan, hal.halaman_belum_bisa(siswa, ident), 503)
        if order is None:
            dasar._tidak_ada(penangan)
            return True
        if purna_ringkas is None:
            return _kirim_halaman(penangan, hal.halaman_info(siswa, ident, order["status"]))
        return _render(penangan, kon, siswa, ident, order, purna_ringkas, kini)


def tangani_post(penangan, jalur: str) -> bool:
    cocok = _POLA.fullmatch(jalur)
    if cocok is None:
        return False
    anak_id, aksi = int(cocok.group(1)), cocok.group(2)
    with database.buka() as kon:
        konteks = None if aksi is None else _konteks(penangan, kon, anak_id)
        if konteks is None:
            dasar._tidak_ada(penangan)
            return True
        siswa, ident = konteks
        if not ident or ident[1] != "guru":
            from support_pages import halaman_pesan

            penangan._kirim(halaman_pesan("Hanya guru", "<h1>Hanya guru yang dapat mengubah laporan</h1>"), 403)
            return True
        kini = _kini()
        try:
            order, purna_ringkas = _baca_order(anak_id, kini)
        except OrderTakTerbaca:
            return _kirim_halaman(penangan, hal.halaman_belum_bisa(siswa, ident), 503)
        if order is None:
            dasar._tidak_ada(penangan)
            return True
        if purna_ringkas is None:
            return _kirim_halaman(penangan, hal.halaman_info(siswa, ident, order["status"]), 409)
        return _jalankan(penangan, kon, siswa, ident, order, purna_ringkas, kini, aksi)


def _galat_form(ctx, pesan: str, kode: int = 400, **kw) -> bool:
    penangan, kon, siswa, ident, order, purna_ringkas, kini = ctx
    return _render(penangan, kon, siswa, ident, order, purna_ringkas, kini, galat=pesan, kode=kode, **kw)


def _jalankan(penangan, kon, siswa, ident, order, purna_ringkas, kini, aksi) -> bool:
    ctx = (penangan, kon, siswa, ident, order, purna_ringkas, kini)
    data = dasar._baca_form(penangan)
    if data is None:
        return _galat_form(ctx, PESAN_FORM)
    if aksi == "buat":
        return _buat(ctx) if not data else _galat_form(ctx, PESAN_FORM)
    if aksi == "catatan":
        return _catatan(ctx, data) if set(data) == {"catatan"} else _galat_form(ctx, PESAN_FORM)
    if set(data) != {"konfirmasi"}:
        return _galat_form(ctx, PESAN_FORM)
    return _terbitkan(ctx, data) if aksi == "terbitkan" else _hapus(ctx, data)


def _alihkan_peta(penangan, siswa) -> bool:
    dasar._alihkan(penangan, hal.RUTE_DASAR % int(siswa["id"]))
    return True


def _gagal_domain(ctx, pesan: str) -> bool:
    """ValueError domain: batalkan transaksi, 409 dengan pesan tetap (tanpa str(galat))."""
    ctx[1].rollback()
    return _galat_form(ctx, pesan, 409)


def _buat(ctx) -> bool:
    penangan, kon, siswa, ident, order, _purna, kini = ctx
    kon.execute("BEGIN IMMEDIATE")
    try:
        cek = cek_ringkasan_admin.ringkasan_untuk_order(
            kon, siswa["id"], order["cek_id"], order["akun_id"], kini)
        isi = snapshot.bangun(cek)
        toko.buat_draf(kon, siswa["id"], ident[0], isi, _epoch(kini))
    except ValueError:
        return _gagal_domain(ctx, PESAN_BAHAN)
    kon.commit()
    return _alihkan_peta(penangan, siswa)


def _catatan_sah(catatan: str):
    """Pesan galat untuk catatan yang tak boleh disimpan, atau None (aturan hanya di toko.periksa_catatan)."""
    kode = toko.periksa_catatan(catatan)
    return None if kode is None else _PESAN_KODE_CATATAN.get(kode, PESAN_CATATAN_ISI)


def _catatan(ctx, data) -> bool:
    penangan, kon, siswa = ctx[0], ctx[1], ctx[2]
    catatan = data["catatan"].replace("\r\n", "\n").replace("\r", "\n")
    galat = _catatan_sah(catatan)
    if galat:
        return _galat_form(ctx, galat, catatan_kiriman=catatan)
    kon.execute("BEGIN IMMEDIATE")
    try:
        toko.simpan_catatan(kon, siswa["id"], catatan)
    except ValueError:
        return _gagal_domain(ctx, PESAN_STATUS)
    kon.commit()
    return _alihkan_peta(penangan, siswa)


def _pesan_draf_belum_layak(laporan):
    """Pesan tetap bila catatan draf kosong atau (data lama) tak lolos aturan sekarang; None bila layak/bukan draf."""
    if laporan is None or laporan["diterbitkan"] is not None:
        return None
    if not laporan["catatan"].strip():
        return PESAN_CATATAN_KOSONG
    return PESAN_CATATAN_TERSIMPAN if toko.periksa_catatan(laporan["catatan"]) is not None else None


def _terbitkan(ctx, data) -> bool:
    penangan, kon, siswa, ident, order, _purna, kini = ctx
    if data["konfirmasi"] != "1":
        return _galat_form(ctx, PESAN_KONFIRMASI)
    kon.execute("BEGIN IMMEDIATE")
    try:
        laporan = toko.ambil(kon, siswa["id"])
        pesan = _pesan_draf_belum_layak(laporan)
        if pesan:
            kon.rollback()
            return _galat_form(ctx, pesan, 409)
        toko.terbitkan(kon, siswa["id"], ident[0], _epoch(kini))
    except ValueError:
        return _gagal_domain(ctx, PESAN_STATUS)
    kon.commit()
    try:
        laporan = toko.ambil(kon, siswa["id"])
    except _GALAT_LAPORAN as galat:
        _log.warning("laporan terbit tidak terbaca untuk purna: %s", type(galat).__name__)
        laporan = None
    if laporan is not None:
        _catat_purna(order["order_id"], laporan)
    return _alihkan_peta(penangan, siswa)


def _hapus(ctx, data) -> bool:
    penangan, kon, siswa = ctx[0], ctx[1], ctx[2]
    if data["konfirmasi"] != "1":
        return _galat_form(ctx, PESAN_KONFIRMASI)
    kon.execute("BEGIN IMMEDIATE")
    try:
        terhapus = toko.hapus_draf(kon, siswa["id"])
    except ValueError:
        terhapus = False
    if not terhapus:
        return _gagal_domain(ctx, PESAN_STATUS)
    kon.commit()
    return _alihkan_peta(penangan, siswa)


def kartu_untuk_anak(kon, siswa_id: int) -> str:
    """Kartu kecil untuk halaman anak: hanya bila anak punya order Peta lunas; apa pun galatnya = "" (tanpa kartu).

    Hanya membaca; tidak pernah mengulang pencatatan purna dan tidak membaca data cek.
    """
    try:
        order, purna_ringkas = _baca_order(siswa_id, _kini())
        if order is None or purna_ringkas is None:
            return ""
        laporan = toko.ambil(kon, siswa_id)
    except (OrderTakTerbaca, ValueError, sqlite3.Error):
        return ""
    return hal.kartu_masuk(siswa_id, purna=purna_ringkas, laporan=laporan)
