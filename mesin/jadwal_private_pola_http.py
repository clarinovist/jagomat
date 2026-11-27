"""Rute murid pola Private (2 hari + 1 jam): kartu di /murid/paket, ajukan pola, dan batalkan pilihan. Persetujuan tim di admin.

Dipanggil `kelas_murid_http` setelah gerbang sakelar PAKET_BELAJAR, sesi anak, rekening, dan PIN tirai (sama seperti rute
Private lama). Order TIDAK pernah dari form: domain menurunkannya dari (akun sesi, anak sesi). Respons: tidak milik /
tidak ada = 404 murid yang identik tanpa efek; konflik = 409 pesan tetap; isian tidak sah = 400; galat layanan = 503.
Baca gagal-diam: kartu hilang, halaman tetap utuh.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import admin_store
import admin_store_core
import jadwal_private as jp
import jadwal_private_dasar as dsr
import jadwal_private_murid as pm
import jadwal_private_pola as pola
import jadwal_store as js
import kelas_pages as halaman
import kelas_private_pages as priv
import pesanan_alur as alur
import pesanan_dasar as d
import pesanan_http
from jadwal_private_baca import order_boleh_mengajukan
from kontak_http import _alihkan, _baca_form
from support_pages import halaman_pesan_murid

KUNCI_TOKEN = "token"
JUDUL_GAGAL_AJUKAN = "Pilihan belum bisa dipakai"
JUDUL_GAGAL_BATAL = "Pilihan belum bisa dibatalkan"
JUDUL_BELUM_SIAP = "Belum bisa diproses"
COPY_KONFLIK_AJUKAN = ("Pilihan belum bisa dipakai sekarang. Paket mungkin sudah berjadwal atau masa aksesnya "
                       "sudah habis. Tidak ada yang diubah.")
COPY_ISIAN_AJUKAN = "Pilih dua hari yang berbeda dan satu jam dari daftar. Tidak ada yang diubah."
COPY_GAGAL_BATAL = "Tidak ada pilihan yang bisa dibatalkan. Muat ulang halaman, lalu coba lagi."
COPY_BELUM_SIAP = "Belum bisa diproses sekarang. Coba lagi nanti."
KODE_ISIAN = 400
KODE_KONFLIK = 409
KODE_TIDAK_SIAP = 503
# Galat yang dibaca gagal-diam (kartu tidak tampil) atau dijawab 503 (tulis). Galat domain Jadwal* ikut sebagai PesananError.
GALAT_LAYANAN = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError, d.PesananError,
                 dsr.GalatJadwalPrivate)


def kartu_untuk(akun_id: str, siswa_id: int, kini: str, token_untuk) -> str:
    """Kartu Private pola untuk halaman paket, atau '' bila tidak ditawarkan atau baca gagal (gagal-diam).

    Pengajuan slot lama yang masih menunggu (dari sebelum pola) ikut tampil agar tidak hilang diam-diam.
    """
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            oid = order_boleh_mengajukan(kon, akun_id, siswa_id, kini)
            if oid is None:
                return ""
            lama = jp.status_pengajuan(kon, akun_id, siswa_id, kini, guru_sah=pm.guru_sah())
        terakhir = pola.terbaru_order(oid)
    except GALAT_LAYANAN:
        return ""
    return priv.kartu_pola(terakhir, token_untuk, lama)


def _tidak_ada(penangan) -> None:
    """Sama persis dengan 404 murid di kelas_murid_http (impor siklik dihindari)."""
    penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), 404)


def _info(penangan, judul: str, teks: str, kode: int) -> None:
    penangan._kirim_privat(halaman.halaman_info(judul, teks), kode)


def _balas_galat(penangan, galat: Exception, judul: str, copy_konflik: str) -> None:
    """Tidak milik / tidak ada = 404 identik; isian = 400; konflik = 409; sisanya 503 tanpa detail."""
    if isinstance(galat, d.PesananTidakDitemukan):
        _tidak_ada(penangan)
    elif isinstance(galat, d.PesananDataTidakSah):
        _info(penangan, JUDUL_GAGAL_AJUKAN, COPY_ISIAN_AJUKAN, KODE_ISIAN)
    elif isinstance(galat, d.PesananKonflik):
        _info(penangan, judul, copy_konflik, KODE_KONFLIK)
    else:
        _info(penangan, JUDUL_BELUM_SIAP, COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def _form_ajukan(penangan, principal) -> Optional[dict]:
    """Isian pola (tanpa token) bila token sah; None bila respons penolakan sudah dikirim."""
    data = _baca_form(penangan)
    if data is None or KUNCI_TOKEN not in data:
        penangan._tolak_isian()
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), priv.AKSI_POLA, data[KUNCI_TOKEN]):
        penangan._tolak_isian(403)
        return None
    return {kunci: nilai for kunci, nilai in data.items() if kunci != KUNCI_TOKEN}


def _form_batal(penangan, principal) -> bool:
    """True bila form `{token}` bertoken batal sah; False bila respons penolakan sudah dikirim."""
    data = _baca_form(penangan)
    if data is None or set(data) != {KUNCI_TOKEN}:
        penangan._tolak_isian()
        return False
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), priv.AKSI_POLA_BATAL, data[KUNCI_TOKEN]):
        penangan._tolak_isian(403)
        return False
    return True


def _tulis_ajukan(akun_id: str, siswa_id: int, isian: dict) -> None:
    with js.buka(admin_store.BAWAAN) as kon_admin:
        pola.ajukan(kon_admin, akun_id, siswa_id, isian, alur.waktu_sekarang())


def _tulis_batal(akun_id: str, siswa_id: int) -> None:
    with js.buka(admin_store.BAWAAN) as kon_admin:
        pola.batalkan(kon_admin, akun_id, siswa_id, alur.waktu_sekarang())


def post_ajukan(penangan, principal, siswa_id: int) -> None:
    """Orang tua memilih dua hari dan satu jam untuk anak sesi; semua syarat dicek di domain."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    isian = _form_ajukan(penangan, principal)
    if isian is None:
        return
    try:
        _tulis_ajukan(principal.id_akun, siswa_id, isian)
    except GALAT_LAYANAN as galat:
        _balas_galat(penangan, galat, JUDUL_GAGAL_AJUKAN, COPY_KONFLIK_AJUKAN)
        return
    _alihkan(penangan, halaman.RUTE)


def post_batal(penangan, principal, siswa_id: int) -> None:
    """Orang tua membatalkan pola 'diajukan' milik anak sesi."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    if not _form_batal(penangan, principal):
        return
    try:
        _tulis_batal(principal.id_akun, siswa_id)
    except GALAT_LAYANAN as galat:
        _balas_galat(penangan, galat, JUDUL_GAGAL_BATAL, COPY_GAGAL_BATAL)
        return
    _alihkan(penangan, halaman.RUTE)
