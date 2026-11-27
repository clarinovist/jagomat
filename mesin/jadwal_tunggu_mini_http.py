"""Rute murid daftar tunggu Mini (F2c): POST masuk dan keluar, serta status untuk kartu pilih kelompok.

Dipanggil `kelas_murid_http` setelah gerbang sakelar PAKET_BELAJAR, sesi anak, rekening, dan PIN tirai (sama dengan rute
Private). Order dan anak TIDAK pernah dari form: domain menurunkannya dari (akun sesi, anak sesi). Form masuk persis
`{token, kelompok}` (token terikat `AKSI_TUNGGU` + kelompok); form keluar persis `{token}` (token terikat
`AKSI_TUNGGU_KELUAR`). Respons: tidak milik / tidak ada / tidak memenuhi syarat = 404 murid identik tanpa efek;
kelompok masih ada kursi = 409; isian tidak sah = 400; galat layanan = 503. Baca status gagal-diam: `None` = kartu
tanpa tombol tunggu, halaman tetap utuh.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

import admin_store
import admin_store_core
import jadwal_dasar as jd
import jadwal_private_dasar as dsr
import jadwal_store as js
import jadwal_tunggu_mini as jt
import kelas_pages as halaman
import pesanan_alur as alur
import pesanan_dasar as d
import pesanan_http
from kontak_http import _alihkan, _baca_form
from support_pages import halaman_pesan_murid

KUNCI_FORM_MASUK = frozenset({"token", "kelompok"})
KUNCI_FORM_KELUAR = frozenset({"token"})
KUNCI_TOKEN = "token"
JUDUL_GAGAL = "Daftar tunggu belum bisa diubah"
JUDUL_BELUM_SIAP = "Belum bisa diproses"
COPY_ISIAN = "Isian daftar tunggu tidak sah. Muat ulang halaman, lalu coba lagi. Tidak ada yang diubah."
COPY_KONFLIK_MASUK = ("Daftar tunggu belum bisa dipakai sekarang. Bila kelompok masih ada kursi, pilih kelompok "
                      "itu langsung. Tidak ada yang diubah.")
COPY_KONFLIK_KELUAR = "Anak ini tidak sedang menunggu di daftar mana pun. Muat ulang halaman."
COPY_BELUM_SIAP = "Belum bisa diproses sekarang. Coba lagi nanti."
KODE_ISIAN = 400
KODE_KONFLIK = 409
KODE_TIDAK_SIAP = 503
# Galat yang dibaca gagal-diam (kartu tanpa tombol tunggu) atau dijawab 503 (tulis). Galat domain Jadwal* ikut sebagai PesananError.
GALAT_LAYANAN = (admin_store_core.StoreBelumSiap, sqlite3.Error, OSError, ValueError, d.PesananError,
                 dsr.GalatJadwalPrivate)


def status_untuk(akun_id: str, siswa_id: int, kini: str) -> Optional[jt.StatusTunggu]:
    """Keadaan daftar tunggu anak untuk kartu pilih kelompok, atau None bila tidak bisa dibaca (gagal-diam)."""
    try:
        with js.buka(admin_store.BAWAAN) as kon:
            return jt.status_tunggu(kon, akun_id, siswa_id, kini)
    except GALAT_LAYANAN:
        return None


def _tidak_ada(penangan) -> None:
    """Sama persis dengan 404 murid di kelas_murid_http (impor siklik dihindari)."""
    penangan._kirim(halaman_pesan_murid("404", "<h1>Halaman tidak ada</h1>"), 404)


def _info(penangan, judul: str, teks: str, kode: int) -> None:
    penangan._kirim_privat(halaman.halaman_info(judul, teks), kode)


def _balas_galat(penangan, galat: Exception, copy_konflik: str) -> None:
    """Tidak milik / tidak ada = 404 identik; isian = 400; konflik = 409; sisanya 503 tanpa detail."""
    if isinstance(galat, d.PesananTidakDitemukan):
        _tidak_ada(penangan)
    elif isinstance(galat, d.PesananDataTidakSah):
        _info(penangan, JUDUL_GAGAL, COPY_ISIAN, KODE_ISIAN)
    elif isinstance(galat, d.PesananKonflik):
        _info(penangan, JUDUL_GAGAL, copy_konflik, KODE_KONFLIK)
    else:
        _info(penangan, JUDUL_BELUM_SIAP, COPY_BELUM_SIAP, KODE_TIDAK_SIAP)


def _form_masuk(penangan, principal) -> Optional[str]:
    """Id kelompok dari form `{token, kelompok}` yang bertoken sah, atau None bila respons penolakan sudah dikirim."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_MASUK:
        penangan._tolak_isian()
        return None
    try:
        kelompok = jd.periksa_kelompok_id(data["kelompok"])
    except d.PesananDataTidakSah:
        penangan._tolak_isian()
        return None
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), halaman.AKSI_TUNGGU + kelompok,
                                  data[KUNCI_TOKEN]):
        penangan._tolak_isian(403)
        return None
    return kelompok


def _form_keluar(penangan, principal) -> bool:
    """True bila form `{token}` bertoken keluar sah; False bila respons penolakan sudah dikirim."""
    data = _baca_form(penangan)
    if data is None or set(data) != KUNCI_FORM_KELUAR:
        penangan._tolak_isian()
        return False
    if not pesanan_http.token_sah(principal, penangan._ambil_token(), halaman.AKSI_TUNGGU_KELUAR,
                                  data[KUNCI_TOKEN]):
        penangan._tolak_isian(403)
        return False
    return True


def _tulis_masuk(akun_id: str, siswa_id: int, kelompok: str) -> None:
    with js.buka(admin_store.BAWAAN) as kon_admin:
        jt.masuk(kon_admin, akun_id, siswa_id, kelompok, alur.waktu_sekarang())


def _tulis_keluar(akun_id: str, siswa_id: int) -> None:
    with js.buka(admin_store.BAWAAN) as kon_admin:
        jt.keluar(kon_admin, akun_id, siswa_id, alur.waktu_sekarang())


def post_masuk(penangan, principal, siswa_id: int) -> None:
    """Orang tua masuk daftar tunggu kelompok penuh untuk anak sesi; semua syarat dicek di domain."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    kelompok = _form_masuk(penangan, principal)
    if kelompok is None:
        return
    try:
        _tulis_masuk(principal.id_akun, siswa_id, kelompok)
    except GALAT_LAYANAN as galat:
        _balas_galat(penangan, galat, COPY_KONFLIK_MASUK)
        return
    _alihkan(penangan, halaman.RUTE)


def post_keluar(penangan, principal, siswa_id: int) -> None:
    """Orang tua keluar dari daftar tunggu anak sesi."""
    if not pesanan_http._izinkan(penangan, principal):
        pesanan_http._tolak_laju(penangan)
        return
    if not _form_keluar(penangan, principal):
        return
    try:
        _tulis_keluar(principal.id_akun, siswa_id)
    except GALAT_LAYANAN as galat:
        _balas_galat(penangan, galat, COPY_KONFLIK_KELUAR)
        return
    _alihkan(penangan, halaman.RUTE)
